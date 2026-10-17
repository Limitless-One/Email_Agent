"""Strict data contracts at the model and tool boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import re
from typing import Any, Mapping


class ContractError(ValueError):
    """Raised when an untrusted model or API response violates a contract."""


class Route(str, Enum):
    RESOLVE = "resolve"
    CLARIFY = "clarify"
    ESCALATE = "escalate"
    IGNORE = "ignore"


ORDER_ID_RE = re.compile(r"^NG-\d{6}$", re.I)
SERIAL_RE = re.compile(r"^[A-Z]{2}\d{4}-\d{5}$", re.I)
RMA_ID_RE = re.compile(r"^RMA-\d+$", re.I)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    thread_id: str
    sender: str
    recipients: list[str]
    subject: str
    text: str
    message_reference: str | None = None
    references: str | None = None


@dataclass(frozen=True)
class Classification:
    route: Route
    intent: str
    confidence: float
    customer_email: str | None = None
    order_id: str | None = None
    product_id: str | None = None
    sku: str | None = None
    serial_number: str | None = None
    rma_id: str | None = None
    requested_action: str = ""
    facts_needed: tuple[str, ...] = ()
    escalation_reason: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Classification":
        required = {"route", "intent", "confidence"}
        unknown = set(value) - {
            *required, "customer_email", "order_id", "product_id", "sku",
            "serial_number", "rma_id", "requested_action", "facts_needed",
            "escalation_reason",
        }
        if required - set(value) or unknown:
            raise ContractError("classification has missing or unknown fields")
        try:
            route = Route(str(value["route"]))
            confidence = float(value["confidence"])
        except (TypeError, ValueError) as exc:
            raise ContractError("invalid route or confidence") from exc
        if not 0 <= confidence <= 1 or not isinstance(value["intent"], str):
            raise ContractError("invalid intent or confidence range")
        fields = {key: value.get(key) for key in (
            "customer_email", "order_id", "product_id", "sku", "serial_number", "rma_id",
            "requested_action", "escalation_reason",
        )}
        for key, field_value in fields.items():
            if field_value is not None and not isinstance(field_value, str):
                raise ContractError(f"{key} must be a string or null")
        fields["requested_action"] = fields["requested_action"] or ""
        if fields["customer_email"] and not EMAIL_RE.fullmatch(str(fields["customer_email"])):
            raise ContractError("invalid customer email")
        if fields["order_id"] and not ORDER_ID_RE.fullmatch(str(fields["order_id"])):
            raise ContractError("invalid order id")
        if fields["serial_number"] and not SERIAL_RE.fullmatch(str(fields["serial_number"])):
            raise ContractError("invalid serial number")
        if fields["rma_id"] and not RMA_ID_RE.fullmatch(str(fields["rma_id"])):
            raise ContractError("invalid RMA id")
        facts = value.get("facts_needed", [])
        if not isinstance(facts, list) or not all(isinstance(item, str) for item in facts):
            raise ContractError("facts_needed must be a string list")
        return cls(route=route, intent=value["intent"].strip().lower(), confidence=confidence,
                   facts_needed=tuple(facts[:8]), **fields)

    @classmethod
    def from_json(cls, raw: str) -> "Classification":
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractError("classification is not JSON") from exc
        if not isinstance(value, dict):
            raise ContractError("classification must be an object")
        return cls.from_mapping(value)


@dataclass(frozen=True)
class Source:
    source_id: str
    title: str
    text: str
    score: float | None = None


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: Mapping[str, str]


@dataclass(frozen=True)
class ToolResult:
    name: str
    data: Mapping[str, Any]
    sources: tuple[Source, ...] = ()


@dataclass(frozen=True)
class ResponsePlan:
    route: Route
    body: str
    cited_source_ids: tuple[str, ...] = ()
    ticket_id: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    trace_id: str
    event_type: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def as_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, default=str)


CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["route", "intent", "confidence"],
    "properties": {
        "route": {"enum": [route.value for route in Route]},
        "intent": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "customer_email": {"type": ["string", "null"]},
        "order_id": {"type": ["string", "null"]},
        "product_id": {"type": ["string", "null"]},
        "sku": {"type": ["string", "null"]},
        "serial_number": {"type": ["string", "null"]},
        "rma_id": {"type": ["string", "null"]},
        "requested_action": {"type": "string"},
        "facts_needed": {"type": "array", "items": {"type": "string"}},
        "escalation_reason": {"type": ["string", "null"]},
    },
}
