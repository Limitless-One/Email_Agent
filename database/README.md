# NovaGear Customer Service Databases

This directory contains the operational and customer databases designed for the **NovaGear Customer Service Email Agent**. The schema and dummy data are modeled directly after the business rules, product specifications, shipping tiers, warranty terms, and escalation protocols defined in the [knowledge_base](../knowledge_base/README.md).

---

## 🗄️ Database Architecture

The database is implemented as a lightweight, zero-dependency **SQLite** relational database (`novagear.db`) and accompanied by exported **JSON fixtures** for testing, mock tooling, and context injection.

```text
database/
├── novagear.db                # SQLite database with all tables, constraints & dummy records
├── schema.sql                 # Complete DDL script with constraints and indexes
├── seed_data.py               # Seed script to regenerate and repopulate the database
├── db_service.py              # High-level Python service methods for agent tool calling
├── fixtures/                  # Clean JSON exports of all tables for mock tests / inspection
│   ├── customers.json
│   ├── products.json
│   ├── orders.json
│   ├── order_items.json
│   ├── warranties.json
│   ├── rma_claims.json
│   ├── tracking_events.json
│   ├── support_tickets.json
│   └── promo_codes.json
└── README.md
```

---

## 📊 Database Tables Overview

| Table | Primary Key | Description | Knowledge Base Reference |
| :--- | :--- | :--- | :--- |
| `products` | `sku` | Catalog of the 3 NovaGear products (ApexStand Ultra, VoltBoost Pro 20K, NexusCord) with variants, MSRP, and warranty rules. | `metadata_index.json`, product manuals |
| `customers` | `customer_id` | Customer profiles with names, verified emails, phone numbers, addresses, and VIP flags. | Customer directory |
| `orders` | `order_id` | Purchase records with payment method, shipping tier, costs, timestamps, delivery tracking, and cancellation window deadlines. | `policies/order_cancellation_and_modification.md`, `policies/shipping_and_delivery_policy.md` |
| `order_items` | `item_id` | Line items linking products/SKUs to orders with unit prices and quantities. | Catalog pricing |
| `warranties` | `warranty_id` | Product serial numbers, purchase dates, registration dates, 12-month standard vs 18-month extended coverage, and status. | `policies/warranty_policy.md` |
| `rma_claims` | `rma_id` | Return Merchandise Authorizations for warranty replacements, DOA units, and 30-day customer returns. Tracks return shipping fees ($5.99 remorse vs free defect). | `policies/return_and_refund_policy.md`, `policies/warranty_policy.md` |
| `tracking_events` | `event_id` | Carrier milestones (USPS, UPS, FedEx) showing live status updates, locations, and transit delays. | `policies/shipping_and_delivery_policy.md` |
| `support_tickets` | `ticket_id` | Logged customer service emails and escalations to Tier 2, Hardware Warranty, or Safety & Compliance. | `company_and_support/human_escalation_and_contact.md` |
| `promo_codes` | `code` | Store coupon codes, minimum order requirements, and discount rates. | `company_and_support/general_faq.md` |

---

## 🧪 Test Scenarios & Dummy Data Profiles

The dummy dataset includes realistic scenarios designed to test every branch of your customer service email agent:

| Scenario / Intent | Customer / Order | Key Test Condition | Expected Agent Behavior |
| :--- | :--- | :--- | :--- |
| **30-Min Cancellation Window (Eligible)** | **Aisha Patel**<br>`NG-104835` | Placed 12 minutes ago (`status: processing`). `cancellation_deadline` is 18 mins away. | Allow customer to cancel order or update address immediately. |
| **30-Min Cancellation Window (Expired)** | **David Kim**<br>`NG-104834` | Placed 2 hours ago (`status: confirmed`). Past 30-min window. | Inform customer order has moved to warehouse picking; advise refusing delivery or initiating 30-day return upon arrival. |
| **Out for Delivery Today** | **Elena Rostova**<br>`NG-104833` | Shipped via UPS (`1Z999AA10198765432`), out for delivery today between 1:00 PM – 5:00 PM. | Provide carrier tracking summary and reassurance of imminent delivery. |
| **Stalled In-Transit (Carrier Exception)** | **James Wilson**<br>`NG-104832` | FedEx package stalled > 5 business days in Louisville, KY hub. | Recognize policy trigger (>5 days stall); open carrier trace investigation or prepare replacement. |
| **Severe Frustration / Churn Threat** | **James Wilson**<br>`TICK-9015` | Threatens credit card chargeback and BBB complaint. | Escalate cleanly to `Executive Escalations Desk` using human escalation protocol (Priority 2 High). |
| **30-Day Return (Buyer Remorse)** | **Marcus Vance**<br>`NG-104831` | Delivered 4 days ago (unopened laptop stand). | Within 30-day window; issue RMA and prepaid label, informing them of standard $5.99 label fee deduction. |
| **Warranty Claim (Cable E-Marker failure)** | **Sarah Jenkins**<br>`NG-104830` | Delivered 25 days ago. NexusCord 100W cable stopped fast charging. | Verify warranty (active 12-month); issue RMA replacement free of charge. |
| **Safety / Thermal Hazard (P1 Critical)** | **Rachel Greenwood**<br>`NG-104829` | VoltBoost Pro 20K casing is swollen and smells like burning plastic. | **Immediate safety advisory**: instruct customer to unplug, move to cool non-flammable area. Escalate as `URGENT_SAFETY_HAZARD` to `escalations@novagear.com`. |
| **Extended 18-Month Warranty** | **Marcus Vance**<br>`NG-103550` | Purchased 14 months ago, but registered online within 30 days. | Standard 12-month warranty expired, but 18-month extended warranty is still **Active**! |
| **Expired Warranty** | **David Kim**<br>`NG-101200` | Purchased 22 months ago, unregistered. | Politely explain warranty is expired; offer discount on replacement. |

---

## 💻 Python Agent Integration

Your email agent can use `database.db_service` as tools or functions:

```python
from database import db_service

# 1. Look up customer by email
customer = db_service.get_customer_by_email("marcus.vance@example.com")

# 2. Check order details & cancellation eligibility
order = db_service.get_order_details("NG-104835")
cancellation = db_service.check_cancellation_eligibility("NG-104835")
print(cancellation["eligible"])  # True (18 minutes remaining)

# 3. Check return eligibility
return_status = db_service.check_return_eligibility("NG-104831")
print(return_status["eligible"])  # True (delivered 4 days ago)

# 4. Check warranty status for serial number
warranties = db_service.get_warranty_details("VB2408-77124")
print(warranties[0]["status"])  # 'active' (18-month extended)
```
