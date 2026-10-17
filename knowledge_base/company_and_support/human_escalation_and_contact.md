---
doc_id: "human_escalation_and_contact"
doc_title: "NovaGear Customer Support Directory & AI Human Escalation Protocols"
category: "Support & Escalation"
document_type: "support_protocol"
last_updated: "2026-09-15"
keywords: ["contact info", "customer service phone", "human agent handoff", "escalation matrix", "safety hazard", "ticket escalation", "business hours"]
---

# NovaGear Customer Support Directory & Human Escalation Protocols

This document details official contact channels, customer support SLAs, and specific operating guidelines for **AI email customer service agents** to cleanly escalate complex, high-risk, or unsatisfied tickets to human support specialists.

---

## 1. Official Customer Contact Directory

| Department / Channel | Contact Information | Operating Hours | Target SLA |
| :--- | :--- | :--- | :--- |
| **General Customer Support** | `support@novagear.com` | 24/7 Ingestion | Human reply within **4 to 8 hours** |
| **Warranty & RMA Claims** | `warranty@novagear.com` | Mon – Fri: 9:00 AM – 6:00 PM EST | Claim decision within **24 business hours** |
| **Urgent Escalations / Executive** | `escalations@novagear.com` | Mon – Fri: 9:00 AM – 8:00 PM EST | Priority review within **2 to 4 hours** |
| **Toll-Free Phone Support** | **+1 (800) 555-0199** | Mon – Fri: 9:00 AM – 6:00 PM EST | Average hold time < 3 minutes |
| **Live Web Chat** | `https://www.novagear.com/chat` | Mon – Fri: 8:00 AM – 8:00 PM EST<br>Sat – Sun: 10:00 AM – 4:00 PM EST | Real-time agent assistance |
| **Corporate Headquarters** | NovaGear Innovations LLC<br>742 Tech Ridge Blvd, Suite 400<br>Austin, TX 78758, USA | Mon – Fri: 9:00 AM – 5:00 PM CST | Official correspondence |

---

## 2. AI Customer Service Agent Escalation Rules
When the automated email agent processes customer emails, it must immediately initiate a **warm human handoff** under any of the following 5 trigger conditions:

### Trigger 1: Safety & Thermal Hazards (Priority 1 - Critical)
* **Conditions**: Any mention of burning smells, sparks, smoke, swollen/bloated battery casing on the VoltBoost Pro 20K, electric shocks, or device melting.
* **Agent Action**:
  - Immediately advise customer to disconnect the device, cease usage, and place the battery in a cool, fire-safe area away from flammable materials.
  - Flag ticket as `URGENT_SAFETY_HAZARD`.
  - Transfer ticket directly to `escalations@novagear.com` and notify safety compliance.

### Trigger 2: Severe Customer Frustration & Churn Risk (Priority 2 - High)
* **Conditions**: Customer expresses extreme anger, profanity, threatens chargebacks / credit card fraud reports, mentions the Better Business Bureau (BBB), FTC, or legal action.
* **Agent Action**:
  - Empathize respectfully without admitting legal liability or arguing.
  - Forward the full ticket chain to a Senior Support Lead at `escalations@novagear.com`.

### Trigger 3: Repeated Failed Troubleshooting (Priority 2 - High)
* **Conditions**: The customer has already tried standard troubleshooting steps (e.g., hinge tightening on ApexStand, reset on VoltBoost Pro) 2 or more times and the issue remains unresolved.
* **Agent Action**:
  - Do not ask the customer to repeat troubleshooting steps a third time.
  - Escalate to the Tier 2 Hardware Warranty Team to issue an RMA replacement.

### Trigger 4: High-Value Financial Transactions (> $150.00)
* **Conditions**: Order discrepancies, bulk refund requests, or compensation requests exceeding $150.00.
* **Agent Action**:
  - AI can approve standard returns within the 30-day window. Any non-standard refund or manual payout above policy limits requires Level 2 Manager sign-off.

### Trigger 5: Explicit Customer Request for Human Interaction
* **Conditions**: Customer states *"I want to talk to a human"*, *"agent please"*, *"transfer me to someone real"*, or expresses dissatisfaction with automated replies.
* **Agent Action**:
  - Comply immediately and graciously. Acknowledge the request and provide the transfer ticket ID.

---

## 3. Information Required Prior to Human Handoff
To minimize customer friction, the AI agent should verify or gather the following details before completing the escalation note:
1. **Customer Full Name & Order Number** (e.g., `NG-883921`)
2. **Purchased Product & SKU** (e.g., `VoltBoost Pro 20K - Black / NG-VBP-BLK`)
3. **Verified Email Address** linked to purchase
4. **Summary of Issue & Specific Steps Already Attempted**
5. **Customer's Desired Resolution** (e.g., Replacement, Full Refund to Card, Technical Question)

---

## 4. Standard Escalation Email Response Template
When escalating an email to a human team member, the AI agent should reply to the customer with this professional, reassuring tone:

```text
Subject: Re: [Original Subject] - Escalated to NovaGear Specialist [Ticket #NG-{TicketID}]

Dear [Customer Name],

Thank you for contacting NovaGear Support. 

I understand your concern regarding [brief summary of issue, e.g., the charging issue with your VoltBoost Pro 20K], and I want to make sure you receive the best care possible. 

I have escalated your ticket directly to our Senior Support Team for personal review. A dedicated hardware specialist will review your case details and reply directly to this email thread within 4 to 8 business hours (Monday–Friday, 9:00 AM – 6:00 PM EST).

Case Details:
- Ticket Reference: #NG-[TicketID]
- Order Number: [Order Number or "Pending Verification"]
- Assigned Team: Tier 2 Customer Care

If your issue is urgent during our business hours, you may also reach our phone team directly at +1 (800) 555-0199.

Thank you for your patience while we make this right.

Warm regards,

NovaGear Customer Support Team
support@novagear.com | www.novagear.com
```
