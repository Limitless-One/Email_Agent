"""
NovaGear Database Service & Agent Query Helper.
Provides high-level functions for the customer service email agent to query
customers, orders, tracking, warranties, RMA claims, and store policies.
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novagear.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_customer_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Look up customer details and addresses by email address."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE LOWER(email) = LOWER(?);", (email.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_customer_by_id(customer_id: str) -> Optional[Dict[str, Any]]:
    """Look up customer details by customer ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE customer_id = ?;", (customer_id.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_order_details(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Get full order details including line items, shipping address,
    fulfillment status, tracking information, and cancellation window.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id.strip(),))
        order_row = cursor.fetchone()
        if not order_row:
            return None

        order = dict(order_row)

        # Fetch items
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?;", (order_id.strip(),))
        order["items"] = [dict(item) for item in cursor.fetchall()]

        # Fetch tracking milestones if tracking number exists
        if order.get("tracking_number"):
            cursor.execute("""
                SELECT * FROM tracking_events
                WHERE tracking_number = ?
                ORDER BY event_time ASC;
            """, (order["tracking_number"],))
            order["tracking_events"] = [dict(ev) for ev in cursor.fetchall()]
        else:
            order["tracking_events"] = []

        return order


def get_customer_orders(email_or_customer_id: str) -> List[Dict[str, Any]]:
    """List all orders associated with a customer email or customer ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if "@" in email_or_customer_id:
            cursor.execute("""
                SELECT o.* FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE LOWER(c.email) = LOWER(?)
                ORDER BY o.order_date DESC;
            """, (email_or_customer_id.strip(),))
        else:
            cursor.execute("""
                SELECT * FROM orders
                WHERE customer_id = ?
                ORDER BY order_date DESC;
            """, (email_or_customer_id.strip(),))

        orders = [dict(row) for row in cursor.fetchall()]
        for order in orders:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?;", (order["order_id"],))
            order["items"] = [dict(item) for item in cursor.fetchall()]
        return orders


def get_tracking_status(tracking_number_or_order_id: str) -> Optional[Dict[str, Any]]:
    """Get latest carrier tracking events and delivery status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        val = tracking_number_or_order_id.strip()

        # Check if it's an order ID
        cursor.execute("SELECT order_id, carrier, tracking_number, status, estimated_delivery_date, actual_delivery_date FROM orders WHERE order_id = ?;", (val,))
        order = cursor.fetchone()
        if order and order["tracking_number"]:
            tracking_number = order["tracking_number"]
            carrier = order["carrier"]
        else:
            tracking_number = val
            carrier = None

        cursor.execute("""
            SELECT * FROM tracking_events
            WHERE tracking_number = ?
            ORDER BY event_time DESC;
        """, (tracking_number,))
        events = [dict(e) for e in cursor.fetchall()]

        if not events and not order:
            return None

        latest_event = events[0] if events else None
        return {
            "tracking_number": tracking_number,
            "carrier": carrier or (latest_event["carrier"] if latest_event else "Unknown"),
            "latest_status": latest_event["status"] if latest_event else "Label Created",
            "latest_location": latest_event["location"] if latest_event else "Unknown",
            "latest_update_time": latest_event["event_time"] if latest_event else None,
            "history": events
        }


def check_cancellation_eligibility(order_id: str, current_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Check if an order can be cancelled or modified according to NovaGear's 30-Minute Policy.
    """
    order = get_order_details(order_id)
    if not order:
        return {"eligible": False, "reason": "Order not found."}

    if order["status"] in ("cancelled", "returned"):
        return {"eligible": False, "reason": f"Order is already {order['status']}."}

    if order["status"] in ("shipped", "out_for_delivery", "delivered"):
        return {
            "eligible": False,
            "reason": f"Order has already reached '{order['status']}' status and cannot be cancelled directly. The customer may refuse delivery or request a return via the returns portal upon arrival."
        }

    # Evaluate against 30-minute deadline
    now = current_time or datetime(2026, 10, 16, 16, 45, 0)
    deadline = datetime.strptime(order["cancellation_deadline"], "%Y-%m-%d %H:%M:%S")

    if now <= deadline:
        remaining_minutes = max(0, int((deadline - now).total_seconds() / 60))
        return {
            "eligible": True,
            "remaining_minutes": remaining_minutes,
            "reason": f"Order is within the 30-minute self-service cancellation window ({remaining_minutes} minutes remaining)."
        }
    else:
        return {
            "eligible": False,
            "reason": "The 30-minute modification window has expired. The order has progressed to automated warehouse picking."
        }


def check_return_eligibility(order_id: str, current_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Check if an order is within the 30-Day Return Window (from confirmed delivery date).
    """
    order = get_order_details(order_id)
    if not order:
        return {"eligible": False, "reason": "Order not found."}

    if not order.get("actual_delivery_date"):
        return {"eligible": False, "reason": "Order has not been delivered yet."}

    delivery_time = datetime.strptime(order["actual_delivery_date"], "%Y-%m-%d %H:%M:%S")
    now = current_time or datetime(2026, 10, 16, 16, 45, 0)
    days_since_delivery = (now - delivery_time).days

    if days_since_delivery <= 30:
        return {
            "eligible": True,
            "days_since_delivery": days_since_delivery,
            "days_remaining": 30 - days_since_delivery,
            "reason": f"Eligible for return. Delivered {days_since_delivery} days ago ({30 - days_since_delivery} days left in 30-day window)."
        }
    else:
        return {
            "eligible": False,
            "days_since_delivery": days_since_delivery,
            "reason": f"Past the 30-day return window (delivered {days_since_delivery} days ago). May still qualify for warranty replacement if hardware is defective."
        }


def get_warranty_details(serial_number_or_order_id: str) -> List[Dict[str, Any]]:
    """Look up warranty status, registration status, and expiry for a device."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        val = serial_number_or_order_id.strip()
        cursor.execute("""
            SELECT w.*, p.name as product_name, p.category
            FROM warranties w
            JOIN products p ON w.sku = p.sku
            WHERE w.serial_number LIKE ? OR w.order_id = ?;
        """, (f"%{val}%", val))
        return [dict(row) for row in cursor.fetchall()]


def get_rma_details(rma_id: str) -> Optional[Dict[str, Any]]:
    """Fetch return/warranty claim status and shipping details."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, c.first_name, c.last_name, c.email, p.name as product_name
            FROM rma_claims r
            JOIN customers c ON r.customer_id = c.customer_id
            JOIN products p ON r.sku = p.sku
            WHERE r.rma_id = ?;
        """, (rma_id.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_support_ticket(
    customer_id: str,
    customer_email: str,
    subject: str,
    priority: str,
    assigned_team: str,
    issue_summary: str,
    order_id: Optional[str] = None,
    escalation_reason: Optional[str] = None
) -> str:
    """Create a new customer service ticket or escalation log."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM support_tickets;")
        count = cursor.fetchone()[0] + 1
        ticket_id = f"TICK-{9020 + count}"

        cursor.execute("""
            INSERT INTO support_tickets (
                ticket_id, customer_id, order_id, channel, customer_email,
                subject, priority, assigned_team, status, issue_summary,
                escalation_reason
            ) VALUES (?, ?, ?, 'email', ?, ?, ?, ?, 'open', ?, ?);
        """, (
            ticket_id, customer_id, order_id, customer_email,
            subject, priority, assigned_team, issue_summary,
            escalation_reason
        ))
        conn.commit()
        return ticket_id
