# NovaGear Knowledge Base

Welcome to the **NovaGear** customer support knowledge base. This documentation repository is specifically structured and formatted for **Retrieval-Augmented Generation (RAG)** systems powering automated customer service email agents.

---

## 📂 Directory Structure

```text
knowledge_base/
├── README.md                                  # Knowledge base overview, index, and RAG ingestion guide
├── metadata_index.json                        # Machine-readable catalog, schemas, and routing tags
├── products/
│   ├── apexstand-ultra/                       # Product 1: Ergonomic Laptop Stand
│   │   ├── specifications.md                  # Dimensions, weight, materials, compatibility, SKU
│   │   ├── user_manual.md                     # Setup, hinge tension adjustment, ergonomics, care
│   │   ├── troubleshooting.md                 # Wobble, stiff/loose hinges, fit issues, solutions
│   │   └── faq.md                             # Top customer inquiries specific to ApexStand
│   ├── voltboost-pro-20k/                     # Product 2: 20000mAh 65W Power Bank
│   │   ├── specifications.md                  # Battery specs, port power allocations, TSA limits
│   │   ├── user_manual.md                     # Charging ports, low-current mode, display guide
│   │   ├── troubleshooting.md                 # Fast charging diagnostics, LED error codes, reset
│   │   └── faq.md                             # Flight safety, multi-device usage, thermals
│   └── nexuscord-c-to-c/                      # Product 3: 100W Braided USB-C Cable
│       ├── specifications.md                  # Power specs (E-Marker), transfer speeds, build
│       ├── user_manual.md                     # Usage tips, power delivery matching, strain relief
│       ├── troubleshooting.md                 # Slow charging, intermittent connection, port fit
│       └── faq.md                             # Video display limits, fast charge protocols (PPS)
├── policies/
│   ├── return_and_refund_policy.md            # 30-day return window, fees, process, condition rules
│   ├── warranty_policy.md                     # 1-year standard / 18-mo extended warranty, RMA flow
│   ├── shipping_and_delivery_policy.md        # Shipping tiers, tracking, lost/damaged packages
│   └── order_cancellation_and_modification.md # 30-minute edit window, address change rules
└── company_and_support/
    ├── human_escalation_and_contact.md        # Tiers, SLA, contact channels, AI handoff protocols
    └── general_faq.md                         # Payment methods, invoices, sales tax, security
```

---

## 🏷️ Product Catalog Quick Reference

| Product Name | SKU | MSRP | Category | Short Description |
| :--- | :--- | :--- | :--- | :--- |
| **ApexStand Ultra** | `NG-ASU-SLV` (Silver)<br>`NG-ASU-GRY` (Gray) | $49.99 | Ergonomic Hardware | Heavy-duty dual-axis aluminum laptop stand for laptops 10"–17.3". Supports up to 13.2 lbs (6 kg). |
| **VoltBoost Pro 20K** | `NG-VBP-BLK` (Black)<br>`NG-VBP-WHT` (White) | $69.99 | Power & Charging | 20,000mAh / 74Wh power bank with 65W USB-C PD output, digital wattage display, and pass-through support. |
| **NexusCord 100W USB-C** | `NG-NC100-2M` | $19.99 | Cables & Adapters | 2-meter (6.6 ft) double-braided nylon 100W (20V/5A) USB-C to USB-C cable with E-Marker smart chip. |

---

## 🤖 RAG Ingestion & Chunking Recommendations

1. **Chunk Boundaries**:
   - Each markdown file contains frontmatter YAML (`product_id`, `category`, `document_type`, `keywords`, `last_updated`).
   - Use header-based chunking (`#`, `##`, `###`) to preserve contextual coherence.
   - Recommended chunk size: **400–700 tokens** with a **50–100 token overlap**.
2. **Metadata Filtering**:
   - When an incoming email mentions a specific product name or SKU, filter the RAG query vector search using `product_id` or `sku`.
   - When the intent is identified as policy/logistics (e.g., "refund", "return label", "where is my package"), route or boost chunks tagged with `category: policy` or `document_type: policy`.
3. **Escalation Rules**:
   - If an issue involves battery swelling, electrical fire, legal threats, or multiple failed troubleshooting attempts, refer directly to `company_and_support/human_escalation_and_contact.md` for warm transfer protocol.
