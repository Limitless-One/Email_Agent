"""Offline replay runner for the versioned routing/guardrail evaluation suite."""

from __future__ import annotations

import tempfile
from pathlib import Path
import re
from typing import Any

from evals.cases import all_cases

from .config import AgentConfig
from .contracts import IncomingMessage
from .guardrails import preflight
from .llm import RuleBasedProvider
from .state import AgentState
from .text import newest_customer_text
from .tools import SupportTools
from .worker import EmailAgentWorker


ORDER_OWNERS = {
    "NG-104835": "aisha.patel@example.com", "NG-104834": "david.kim@example.com",
    "NG-104833": "elena.rostova@example.com", "NG-104832": "jwilson99@example.com",
    "NG-104831": "marcus.vance@example.com", "NG-104830": "sarah.jenkins@example.com",
}


class _ReplayMail:
    def __init__(self, item: IncomingMessage): self.item = item
    def candidates(self, limit): return [self.item]
    def create_draft(self, *args): return "draft"
    def send_draft(self, *args): return "sent"
    def sent_for_run(self, *args): return None
    def complete(self, *args): pass


class _InteractiveReplayMail:
    """Records mail operations locally; it has no Gmail implementation or credentials."""
    def __init__(self) -> None:
        self.operations: list[dict[str, str]] = []
        self.draft_count = 0

    def candidates(self, limit: int) -> list[IncomingMessage]:
        return []

    def create_draft(self, message: IncomingMessage, body: str, run_id: str) -> str:
        self.draft_count += 1
        draft_id = f"sim-draft-{self.draft_count}"
        self.operations.append({"operation": "create_draft", "message_id": message.message_id,
                                "draft_id": draft_id, "body": body, "run_id": run_id})
        return draft_id

    def send_draft(self, draft_id: str) -> str:
        sent_id = f"sim-sent-{draft_id}"
        self.operations.append({"operation": "send_draft", "draft_id": draft_id, "sent_id": sent_id})
        return sent_id

    def sent_for_run(self, run_id: str) -> None:
        return None

    def complete(self, message_id: str) -> None:
        self.operations.append({"operation": "complete", "message_id": message_id})


class _NoWriteReplayTools(SupportTools):
    """Allow normal fact lookup while making escalation ticket creation a local simulation."""
    def __init__(self) -> None:
        self.ticket_count = 0

    def ticket_for(self, *args: Any, **kwargs: Any) -> str:
        self.ticket_count += 1
        return f"SIM-TICKET-{self.ticket_count}"


def _replay_messages(payload: Any) -> list[IncomingMessage]:
    """Validate editable JSON input and turn it into offline messages."""
    items = payload.get("messages") if isinstance(payload, dict) and "messages" in payload else payload
    if not isinstance(items, list) or not items:
        raise ValueError("replay JSON must be a non-empty message object or an object with a non-empty 'messages' list")
    messages = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"message {index} must be an object")
        required = ("sender", "subject", "text")
        if any(not isinstance(item.get(key), str) or not item[key].strip() for key in required):
            raise ValueError(f"message {index} requires non-empty string fields: sender, subject, text")
        recipients = item.get("recipients", ["support@example.com"])
        if not isinstance(recipients, list) or not all(isinstance(value, str) for value in recipients):
            raise ValueError(f"message {index} recipients must be a list of strings")
        message_id = item.get("message_id", f"replay-{index}")
        thread_id = item.get("thread_id", f"replay-thread-{index}")
        if not isinstance(message_id, str) or not isinstance(thread_id, str) or not message_id or not thread_id:
            raise ValueError(f"message {index} message_id and thread_id must be non-empty strings")
        messages.append(IncomingMessage(message_id, thread_id, item["sender"], recipients, item["subject"], item["text"],
                                        item.get("message_reference"), item.get("references")))
    return messages


def run_interactive_replay(path: Path) -> dict[str, object]:
    """Run editable JSON through the complete worker flow without Gmail or database writes."""
    try:
        import json
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read replay JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"replay JSON is invalid: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc

    messages = _replay_messages(payload)
    with tempfile.TemporaryDirectory(prefix="email-agent-replay-") as directory:
        config = AgentConfig(state_db_path=Path(directory) / "state.db", send_enabled=True,
                             debug_artifacts=True, model_provider="rule_based")
        mail, tools = _InteractiveReplayMail(), _NoWriteReplayTools()
        worker = EmailAgentWorker(config, mail, RuleBasedProvider(), AgentState(config.state_db_path), tools)
        results = []
        for message in messages:
            outcome = worker.process(message)
            results.append({"input": {"message_id": message.message_id, "thread_id": message.thread_id,
                                       "sender": message.sender, "recipients": message.recipients,
                                       "subject": message.subject, "text": message.text},
                            "outcome": outcome, "trace": worker.state.export_debug_trace(message.message_id)})
        return {"mode": "offline_interactive_replay", "gmail_connected": False,
                "external_email_sent": False, "database_writes": False,
                "provider": "rule_based", "results": results, "simulated_mail_operations": mail.operations}


def run_offline_suite() -> dict[str, object]:
    """Replay fixtures with no OAuth and no outbound email; returns explicit routing metrics."""
    passed, failures = 0, []
    with tempfile.TemporaryDirectory() as directory:
        for index, case in enumerate(all_cases()):
            text = newest_customer_text(case["text"])
            order = re.search(r"\bNG-\d{6}\b", text)
            sender = ORDER_OWNERS.get(order.group(0) if order else "", "external@example.com")
            if case["id"].startswith("cross-customer"):
                sender = "external@example.com"
            message = IncomingMessage(f"eval-{index}", f"thread-{index}", sender, [], "Evaluation", text)
            config = AgentConfig(state_db_path=Path(directory) / f"{index}.db", send_enabled=False)
            worker = EmailAgentWorker(config, _ReplayMail(message), RuleBasedProvider(), AgentState(config.state_db_path))
            worker.run_once()
            actual = worker.state.response_route(message.message_id)
            if actual == case["expected"]:
                passed += 1
            else:
                failures.append({"id": case["id"], "expected": case["expected"], "actual": actual})
    total = len(all_cases())
    return {"total": total, "passed": passed, "accuracy": passed / total if total else 0, "failures": failures,
            "acceptance_ready": not failures}
