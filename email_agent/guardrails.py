"""Deterministic gates run before an email reaches a model."""

from __future__ import annotations

from dataclasses import dataclass
import re

from rag.rag_service import check_escalation_protocol

from .config import AgentConfig
from .contracts import IncomingMessage, Route


INJECTION_PATTERNS = (
    r"ignore (all |any |the )?(previous|prior|above) instructions",
    r"system prompt", r"developer message", r"act as (an? )?assistant",
    r"reveal (your|the) instructions", r"jailbreak",
)


@dataclass(frozen=True)
class GateResult:
    route: Route | None = None
    reason: str | None = None
    escalation: dict | None = None


def preflight(message: IncomingMessage, config: AgentConfig) -> GateResult:
    sender = message.sender.strip().lower()
    if not sender or "@" not in sender:
        return GateResult(Route.IGNORE, "invalid_sender")
    if config.own_email and sender == config.own_email:
        return GateResult(Route.IGNORE, "self_reply_loop")
    if config.allowed_sender_domain and not sender.endswith("@" + config.allowed_sender_domain):
        return GateResult(Route.IGNORE, "sender_domain_not_allowed")
    if not message.text.strip():
        return GateResult(Route.CLARIFY, "empty_plain_text")
    if len(message.text) > config.max_body_chars:
        return GateResult(Route.ESCALATE, "message_too_large")
    if any(re.search(pattern, message.text, re.I) for pattern in INJECTION_PATTERNS):
        return GateResult(Route.ESCALATE, "prompt_injection_indicator")
    escalation = check_escalation_protocol(message.text)
    if escalation:
        return GateResult(Route.ESCALATE, "policy_escalation", escalation)
    text_lower = message.text.lower()
    if any(name in text_lower for name in ("powerbank", "power bank", "voltboost")) and any(word in text_lower for word in ("hot", "overheating", "heat")):
        return GateResult(Route.ESCALATE, "battery_thermal_risk")
    # A script-ratio check is intentionally conservative: do not mistake a short English request for another language.
    printable = [char for char in message.text if not char.isspace()]
    ascii_ratio = sum(char.isascii() for char in printable) / max(1, len(printable))
    if len(message.text) > 30 and ascii_ratio < 0.70:
        return GateResult(Route.CLARIFY, "unsupported_or_uncertain_language")
    return GateResult()
