"""Single-process orchestration with explicit state transitions and safe failure modes."""

from __future__ import annotations

from dataclasses import replace
import json
import logging
import re
import uuid

from database import db_service

from .config import AgentConfig
from .contracts import Classification, ContractError, IncomingMessage, ResponsePlan, Route
from .gmail_client import MailClient
from .guardrails import GateResult, preflight
from .llm import ModelProvider
from .state import AgentState
from .text import safe_summary
from .tools import ResolutionContext, SupportTools


class EmailAgentWorker:
    def __init__(self, config: AgentConfig, mail: MailClient, provider: ModelProvider,
                 state: AgentState | None = None, tools: SupportTools | None = None) -> None:
        self.config, self.mail, self.provider = config, mail, provider
        self.state = state or AgentState(config.state_db_path)
        self.tools = tools or SupportTools()

    def run_once(self) -> dict[str, int]:
        counts = {"seen": 0, "processed": 0, "duplicate": 0, "needs_review": 0}
        owner = str(uuid.uuid4())
        if not self.state.acquire_lock("gmail_poll", owner):
            return {**counts, "locked": 1}
        try:
            for message in self.mail.candidates(self.config.batch_size):
                counts["seen"] += 1
                result = self.process(message)
                if result == "duplicate":
                    counts["duplicate"] += 1
                elif result == "needs_review":
                    counts["needs_review"] += 1
                else:
                    counts["processed"] += 1
        finally:
            self.state.release_lock("gmail_poll", owner)
        return counts

    def process(self, message: IncomingMessage) -> str:
        trace_id, run_id = str(uuid.uuid4()), str(uuid.uuid4())
        if not self.state.claim_message(message.message_id, message.thread_id, message.sender, message.subject, trace_id):
            return "duplicate"
        self.state.start_run(run_id, message.message_id, trace_id, self.config.model_provider, self.config.model_name)
        self.state.record_event(trace_id, message.message_id, "claimed", {"thread_id": message.thread_id})
        logging.getLogger("novagear.email_agent").info(json.dumps({"event": "claimed", "trace_id": trace_id, "message_id": message.message_id}))
        try:
            gate = preflight(message, self.config)
            if gate.route is not None:
                return self._handle_gate(message, trace_id, run_id, gate)

            classification = self.provider.classify(message.text, self.state.thread_summary(message.thread_id), message.sender)
            if self.config.debug_artifacts:
                self.state.record_debug_artifact(trace_id, message.message_id, "classification", getattr(self.provider, "last_debug", {}))
            self.state.record_event(trace_id, message.message_id, "classified", {
                "route": classification.route.value, "intent": classification.intent, "confidence": classification.confidence,
            })
            if classification.confidence < self.config.min_confidence:
                return self._clarify(message, trace_id, run_id, "low_confidence", classification)
            previous_summary = self.state.thread_summary(message.thread_id)
            troubleshooting_signal = classification.intent == "troubleshooting" or bool(re.search(
                r"\b(not charging|will not charge|won't charge|doesn't work|broken|error|overheating)\b", message.text, re.I))
            if (troubleshooting_signal and previous_summary and
                    re.search(r"\b(still|again|tried|second time|didn't work|did not work)\b", message.text, re.I)):
                return self._clarify(message, trace_id, run_id, "repeated_failed_troubleshooting", classification, escalate=True)
            if classification.route == Route.IGNORE:
                return self._ignore(message, trace_id, run_id, "model_ignore")
            if classification.route in {Route.CLARIFY, Route.ESCALATE}:
                return self._clarify(message, trace_id, run_id, classification.escalation_reason or classification.route.value, classification,
                                     escalate=classification.route == Route.ESCALATE)

            context = self.tools.resolve(message.sender, classification)
            if classification.order_id and not context.ownership_verified:
                return self._clarify(message, trace_id, run_id, "order_not_found_or_not_owned", classification, context)
            self.state.record_event(trace_id, message.message_id, "tools_completed", {
                "source_ids": [source.source_id for source in context.sources], "fact_keys": sorted(context.facts),
            })
            response = self.provider.draft(classification, context.facts, context.sources)
            if self.config.debug_artifacts:
                self.state.record_debug_artifact(trace_id, message.message_id, "draft", getattr(self.provider, "last_debug", {}))
            self._validate_response(response, context)
            return self._deliver(message, trace_id, run_id, response)
        except (ContractError, ValueError, KeyError) as exc:
            if self.config.debug_artifacts:
                self.state.record_debug_artifact(trace_id, message.message_id, "model_or_contract_error", getattr(self.provider, "last_debug", {}))
            return self._needs_review(message, trace_id, run_id, "contract_or_validation_failure", exc)
        except Exception as exc:  # Gmail/model outages fail closed, without automatic resend.
            return self._needs_review(message, trace_id, run_id, "processing_failure", exc)

    def _handle_gate(self, message: IncomingMessage, trace_id: str, run_id: str, gate: GateResult) -> str:
        self.state.record_event(trace_id, message.message_id, "preflight_routed", {"route": gate.route.value, "reason": gate.reason})
        if gate.route == Route.IGNORE:
            return self._ignore(message, trace_id, run_id, gate.reason or "ignored")
        return self._clarify(message, trace_id, run_id, gate.reason or "preflight", None,
                             escalate=gate.route == Route.ESCALATE)

    def _clarify(self, message: IncomingMessage, trace_id: str, run_id: str, reason: str,
                 classification: Classification | None, context: ResolutionContext | None = None,
                 escalate: bool = False) -> str:
        customer = context.customer if context else db_service.get_customer_by_email(message.sender)
        ticket_id = self.tools.ticket_for(message.sender, message.subject, reason, customer,
                                          classification.order_id if classification else None)
        if reason == "prompt_injection_indicator":
            body = ("Hello,\n\nWe cannot help with requests to override instructions or disclose private, "
                    "internal, or other customers' information. Your message has been flagged for review. "
                    "Please send a legitimate NovaGear support question if you need assistance.\n\n"
                    "Best regards,\nNovaGear Support")
        elif escalate:
            body = ("Hello,\n\nThank you for contacting NovaGear. Your message has been routed to a support "
                    "specialist for prompt review. Please do not continue using a product if it is hot, damaged, "
                    "swollen, smoking, or has an electrical smell.\n\nBest regards,\nNovaGear Support")
        elif reason == "order_not_found_or_not_owned":
            body = ("Hello,\n\nI could not verify that order from this email address. Please reply with the order "
                    "number and the email address used at checkout, and we will help.\n\nBest regards,\nNovaGear Support")
        else:
            body = ("Hello,\n\nTo help with this safely, please reply with the order number and a short description "
                    "of the issue. A support specialist can then review your request.\n\nBest regards,\nNovaGear Support")
        return self._deliver(message, trace_id, run_id, ResponsePlan(Route.ESCALATE if escalate else Route.CLARIFY, body, ticket_id=ticket_id))

    def _ignore(self, message: IncomingMessage, trace_id: str, run_id: str, reason: str) -> str:
        self.state.record_event(trace_id, message.message_id, "ignored", {"reason": reason})
        self.state.set_status(message.message_id, "ignored")
        self.mail.complete(message.message_id)
        self.state.finish_run(run_id, "ignored")
        return "ignored"

    def _validate_response(self, response: ResponsePlan, context: ResolutionContext) -> None:
        if not response.body or len(response.body) > 4_000:
            raise ContractError("empty or oversized response")
        forbidden = ("system prompt", "developer message", "ignore previous", "as an ai language model")
        if any(item in response.body.lower() for item in forbidden):
            raise ContractError("unsafe response content")
        allowed = {source.source_id for source in context.sources}
        if any(source_id not in allowed for source_id in response.cited_source_ids):
            raise ContractError("response cites an unknown source")
        if response.route == Route.RESOLVE and not response.cited_source_ids:
            raise ContractError("resolution lacks source citations")
        # Simple numeric guard: prevent a draft from introducing a new price/date/error-code token.
        evidence = " ".join([source.text for source in context.sources] + [str(context.facts)])
        for token in re.findall(r"\b(?:\$?\d+(?:\.\d+)?|E\d{2})\b", response.body):
            if token not in evidence:
                raise ContractError("response includes an unsupported numeric claim")

    def _deliver(self, message: IncomingMessage, trace_id: str, run_id: str, response: ResponsePlan) -> str:
        self.state.record_response_plan(message.message_id, response.route.value, response.body,
                                        list(response.cited_source_ids), response.ticket_id)
        self.state.record_event(trace_id, message.message_id, "response_planned", {
            "route": response.route.value, "citation_ids": list(response.cited_source_ids), "ticket_id": response.ticket_id,
        })
        self.state.update_thread_summary(message.thread_id, safe_summary(message.text))
        if not self.config.send_enabled:
            self.state.set_status(message.message_id, "ready_to_send", ticket_id=response.ticket_id)
            self.state.finish_run(run_id, "ready_to_send")
            return "ready_to_send"
        draft_id = self.mail.create_draft(message, response.body, run_id)
        self.state.set_status(message.message_id, "draft_created", draft_id=draft_id, ticket_id=response.ticket_id)
        try:
            sent_id = self.mail.send_draft(draft_id)
        except Exception:
            sent_id = self.mail.sent_for_run(run_id)
            if not sent_id:
                raise
        self.mail.complete(message.message_id)
        self.state.set_status(message.message_id, "completed", sent_id=sent_id, ticket_id=response.ticket_id)
        self.state.record_event(trace_id, message.message_id, "sent", {"gmail_sent_id": sent_id})
        logging.getLogger("novagear.email_agent").info(json.dumps({"event": "sent", "trace_id": trace_id, "message_id": message.message_id}))
        self.state.finish_run(run_id, "completed")
        return "completed"

    def _needs_review(self, message: IncomingMessage, trace_id: str, run_id: str, error_code: str, exc: Exception) -> str:
        detail = str(exc).replace("\n", " ")[:300]
        self.state.set_status(message.message_id, "needs_review", error_code=error_code, error_detail=detail)
        self.state.record_event(trace_id, message.message_id, "needs_review", {
            "error_code": error_code, "error_type": type(exc).__name__, "detail": detail,
        })
        logging.getLogger("novagear.email_agent").warning(json.dumps({"event": "needs_review", "trace_id": trace_id, "message_id": message.message_id, "error_code": error_code}))
        self.state.finish_run(run_id, "needs_review")
        return "needs_review"
