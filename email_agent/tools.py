"""The model can request only these constrained, read-only support tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from database import db_service
from rag import rag_service

from .contracts import Classification, Source, ToolResult


@dataclass
class ResolutionContext:
    customer: dict[str, Any] | None
    order: dict[str, Any] | None
    sources: list[Source]
    facts: dict[str, Any]
    ownership_verified: bool


class SupportTools:
    def resolve(self, sender: str, classification: Classification) -> ResolutionContext:
        customer = db_service.get_customer_by_email(sender)
        order = None
        ownership_verified = False
        facts: dict[str, Any] = {}
        if customer:
            facts["customer_first_name"] = customer["first_name"]
        if classification.order_id:
            candidate = db_service.get_order_details(classification.order_id)
            if candidate and customer and candidate["customer_id"] == customer["customer_id"]:
                order, ownership_verified = candidate, True
                facts["order_id"] = order["order_id"]
                facts["order_status"] = order["status"]
                facts["estimated_delivery_date"] = order.get("estimated_delivery_date")
                facts["shipping_address"] = {
                    "street": order["shipping_street"], "city": order["shipping_city"],
                    "state": order["shipping_state"], "zip": order["shipping_zip"],
                    "country": order["shipping_country"],
                }
            else:
                # Crucially, nothing from another customer's order is retained in the context.
                facts["order_lookup"] = "not_found_or_not_owned"
        shipping_request = classification.intent in {"shipping", "information_request", "order_status"} or any(
            word in classification.requested_action.lower() for word in ("arrival", "delivery", "tracking", "address", "location"))
        if shipping_request and order:
            tracking = db_service.get_tracking_status(order["order_id"])
            if tracking:
                facts["tracking"] = tracking
        elif classification.intent == "return_refund" and order:
            facts["return_eligibility"] = db_service.check_return_eligibility(order["order_id"])
        elif classification.intent == "order_cancellation" and order:
            facts["cancellation_eligibility"] = db_service.check_cancellation_eligibility(order["order_id"])
        elif classification.intent == "warranty":
            lookup = classification.serial_number or (order["order_id"] if order else "")
            if lookup:
                facts["warranties"] = db_service.get_warranty_details(lookup)

        # `requested_action` contains the customer's actual question.  Prepending generic
        # classifier labels (for example, "general_inquiry") gives FTS broad, noisy terms
        # that can outweigh the question's specific nouns such as "laptop" or "ports".
        query = classification.requested_action or classification.intent
        hits = rag_service.query(query, product_id=classification.product_id, top_k=3)
        sources = [Source(source_id=hit["chunk_id"], title=hit["breadcrumb"], text=hit["content"],
                          score=hit.get("relevance_score")) for hit in hits]
        if order and ownership_verified:
            sources.insert(0, Source(source_id=f"order:{order['order_id']}", title="Verified order record",
                text=(f"Order {order['order_id']} is {order['status']}. Estimated delivery: "
                      f"{order.get('estimated_delivery_date') or 'not available'}. Shipping address: "
                      f"{order['shipping_street']}, {order['shipping_city']}, {order['shipping_state']} "
                      f"{order['shipping_zip']}, {order['shipping_country']}.")))
        return ResolutionContext(customer, order, sources, facts, ownership_verified)

    def ticket_for(self, sender: str, subject: str, reason: str, customer: dict[str, Any] | None,
                   order_id: str | None = None) -> str | None:
        if not customer:
            return None
        reason_lower = reason.lower()
        if "safety" in reason_lower:
            priority, team = "urgent_safety_hazard", "Safety & Compliance Team"
        elif "legal" in reason_lower or "chargeback" in reason_lower:
            priority, team = "high", "Executive Escalations Desk"
        else:
            priority, team = "medium", "Tier 2 Customer Care"
        return db_service.create_support_ticket(
            customer_id=customer["customer_id"], customer_email=sender, subject=subject[:250],
            priority=priority, assigned_team=team, issue_summary=reason[:1000],
            order_id=order_id, escalation_reason=reason[:1000],
        )
