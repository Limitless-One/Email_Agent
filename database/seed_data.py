"""
NovaGear E-Commerce Database Schema and Seed Generator.
Creates SQLite database and JSON fixtures aligned with NovaGear Knowledge Base.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "novagear.db")
SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")
FIXTURES_DIR = os.path.join(DB_DIR, "fixtures")

SCHEMA_SQL = """
-- NovaGear E-Commerce Relational Database Schema
-- Aligned with NovaGear Knowledge Base (Products, Shipping, Returns, Warranties, Escalations)

PRAGMA foreign_keys = ON;

-- 1. PRODUCTS
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    name TEXT NOT NULL,
    variant TEXT NOT NULL,
    color TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    standard_warranty_months INTEGER NOT NULL DEFAULT 12,
    extended_warranty_months INTEGER NOT NULL DEFAULT 18,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. CUSTOMERS
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    street_address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT 'USA',
    is_vip BOOLEAN DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. ORDERS
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    order_date TIMESTAMP NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'confirmed', 'shipped', 'out_for_delivery', 'delivered', 'cancelled', 'returned')),
    shipping_tier TEXT NOT NULL CHECK(shipping_tier IN ('Standard Shipping', 'Expedited Shipping', 'Priority Overnight', 'International Connect')),
    carrier TEXT CHECK(carrier IN ('UPS', 'USPS', 'FedEx', 'DHL')),
    tracking_number TEXT,
    subtotal REAL NOT NULL,
    shipping_cost REAL NOT NULL DEFAULT 0.00,
    tax REAL NOT NULL DEFAULT 0.00,
    discount_amount REAL NOT NULL DEFAULT 0.00,
    total_amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    payment_status TEXT NOT NULL CHECK(payment_status IN ('paid', 'pending', 'refunded', 'partially_refunded', 'voided')),
    shipping_street TEXT NOT NULL,
    shipping_city TEXT NOT NULL,
    shipping_state TEXT NOT NULL,
    shipping_zip TEXT NOT NULL,
    shipping_country TEXT NOT NULL DEFAULT 'USA',
    estimated_delivery_date DATE,
    actual_delivery_date TIMESTAMP,
    cancellation_deadline TIMESTAMP, -- 30 minutes from order_date
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- 4. ORDER ITEMS
CREATE TABLE IF NOT EXISTS order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (sku) REFERENCES products(sku)
);

-- 5. WARRANTIES & PRODUCT REGISTRATIONS
CREATE TABLE IF NOT EXISTS warranties (
    warranty_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    serial_number TEXT UNIQUE NOT NULL,
    purchase_date DATE NOT NULL,
    registration_date DATE, -- registered within 30 days extends warranty to 18 mos
    is_registered BOOLEAN DEFAULT 0,
    warranty_period_months INTEGER NOT NULL DEFAULT 12,
    warranty_start_date DATE NOT NULL,
    warranty_end_date DATE NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active', 'expired', 'voided', 'claimed')),
    void_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (sku) REFERENCES products(sku)
);

-- 6. RMA CLAIMS (Returns, Exchanges, Warranty Claims)
CREATE TABLE IF NOT EXISTS rma_claims (
    rma_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    serial_number TEXT,
    claim_type TEXT NOT NULL CHECK(claim_type IN ('warranty_replacement', 'refund_return', 'damaged_on_arrival', 'wrong_item_received')),
    reason_category TEXT NOT NULL,
    customer_complaint TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('requested', 'approved', 'label_emailed', 'in_transit', 'received_at_warehouse', 'inspected', 'replacement_shipped', 'refund_issued', 'rejected', 'closed')),
    shipping_fee_deducted REAL DEFAULT 0.00, -- e.g. $5.99 for buyer remorse, 0 for defects
    repackaging_fee_deducted REAL DEFAULT 0.00, -- 15% if missing accessories/packaging
    refund_amount REAL DEFAULT 0.00,
    return_tracking_number TEXT,
    replacement_order_id TEXT,
    replacement_tracking_number TEXT,
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (sku) REFERENCES products(sku)
);

-- 7. SHIPMENT TRACKING EVENTS (Real-time tracking history)
CREATE TABLE IF NOT EXISTS tracking_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_number TEXT NOT NULL,
    carrier TEXT NOT NULL,
    event_time TIMESTAMP NOT NULL,
    status TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT NOT NULL
);

-- 8. SUPPORT TICKETS & ESCALATIONS
CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    order_id TEXT,
    channel TEXT NOT NULL DEFAULT 'email',
    customer_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high', 'urgent_safety_hazard')),
    assigned_team TEXT NOT NULL CHECK(assigned_team IN ('Tier 1 AI Support', 'Tier 2 Customer Care', 'Hardware Warranty Team', 'Safety & Compliance Team', 'Executive Escalations Desk')),
    status TEXT NOT NULL CHECK(status IN ('open', 'pending_customer', 'in_investigation', 'escalated_to_tier2', 'resolved', 'closed')),
    issue_summary TEXT NOT NULL,
    resolution_notes TEXT,
    escalation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- 9. PROMOTIONS & DISCOUNT CODES
CREATE TABLE IF NOT EXISTS promo_codes (
    code TEXT PRIMARY KEY,
    discount_type TEXT NOT NULL CHECK(discount_type IN ('percentage', 'fixed_amount')),
    discount_value REAL NOT NULL,
    min_order_value REAL DEFAULT 0.00,
    is_active BOOLEAN DEFAULT 1,
    expires_at DATE,
    description TEXT
);

-- INDEXES for fast lookup by Email Agent
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_warranties_order ON warranties(order_id);
CREATE INDEX IF NOT EXISTS idx_warranties_sn ON warranties(serial_number);
CREATE INDEX IF NOT EXISTS idx_rma_order ON rma_claims(order_id);
CREATE INDEX IF NOT EXISTS idx_rma_status ON rma_claims(status);
CREATE INDEX IF NOT EXISTS idx_tracking_number ON tracking_events(tracking_number);
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON support_tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_email ON support_tickets(customer_email);
"""


def seed_database():
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    with open(SCHEMA_PATH, "w") as f:
        f.write(SCHEMA_SQL.strip() + "\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript(SCHEMA_SQL)

    # 1. Clear existing data
    tables = [
        "tracking_events", "support_tickets", "rma_claims", "warranties",
        "order_items", "orders", "customers", "products", "promo_codes"
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table};")

    # 2. Insert Products
    products_data = [
        (
            "NG-ASU-SLV", "apexstand-ultra", "ApexStand Ultra Ergonomic Aluminum Laptop Stand",
            "Silver Edition", "Silver", "Ergonomic Accessories", 49.99, 142, 12, 18,
            "Dual-axis heavy-duty aluminum laptop stand supporting 10-17.3 inch laptops up to 13.2 lbs (6 kg)."
        ),
        (
            "NG-ASU-GRY", "apexstand-ultra", "ApexStand Ultra Ergonomic Aluminum Laptop Stand",
            "Space Gray Edition", "Space Gray", "Ergonomic Accessories", 49.99, 88, 12, 18,
            "Dual-axis heavy-duty aluminum laptop stand supporting 10-17.3 inch laptops up to 13.2 lbs (6 kg)."
        ),
        (
            "NG-VBP-BLK", "voltboost-pro-20k", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank",
            "Midnight Black", "Black", "Portable Power & Batteries", 69.99, 95, 12, 18,
            "20,000mAh / 74Wh power bank with 65W USB-C PD output, digital wattage OLED display, and pass-through."
        ),
        (
            "NG-VBP-WHT", "voltboost-pro-20k", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank",
            "Glacier White", "White", "Portable Power & Batteries", 69.99, 34, 12, 18,
            "20,000mAh / 74Wh power bank with 65W USB-C PD output, digital wattage OLED display, and pass-through."
        ),
        (
            "NG-NC100-2M", "nexuscord-c-to-c", "NexusCord Braided 100W USB-C to USB-C Cable (2m / 6.6ft)",
            "Matte Black 2m", "Black", "Cables & Connectivity", 19.99, 310, 12, 18,
            "2-meter double-braided nylon 100W (20V/5A) USB-C to USB-C cable with E-Marker smart chip."
        )
    ]
    cursor.executemany("""
        INSERT INTO products (sku, product_id, name, variant, color, category, price, stock_quantity, standard_warranty_months, extended_warranty_months, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, products_data)

    # 3. Insert Customers
    customers_data = [
        (
            "CUST-1001", "Marcus", "Vance", "marcus.vance@example.com", "+1-415-555-0142",
            "742 Evergreen Terrace", "San Francisco", "CA", "94102", "USA",
            1, "Tech reviewer & early adopter. Prefers fast email responses."
        ),
        (
            "CUST-1002", "Elena", "Rostova", "elena.rostova@example.com", "+1-206-555-0188",
            "1208 Pine Street, Apt 4B", "Seattle", "WA", "98101", "USA",
            0, "Standard customer. Purchased powerbank for frequent travel."
        ),
        (
            "CUST-1003", "David", "Kim", "david.kim@example.com", "+1-512-555-0199",
            "3401 Congress Ave, Suite 210", "Austin", "TX", "78704", "USA",
            0, "Software engineer working remotely. Bought stand and cables."
        ),
        (
            "CUST-1004", "Sarah", "Jenkins", "sarah.jenkins@example.com", "+1-617-555-0123",
            "88 Beacon Street", "Boston", "MA", "02108", "USA",
            0, "Inquired about warranty replacement for intermittent cable."
        ),
        (
            "CUST-1005", "Michael", "Chang", "mchang.design@example.com", "+1-312-555-0177",
            "450 N Michigan Ave, Unit 12A", "Chicago", "IL", "60611", "USA",
            1, "Architectural designer. Purchased full setup."
        ),
        (
            "CUST-1006", "Rachel", "Greenwood", "rachel.g@example.com", "+1-303-555-0164",
            "1420 Boulder Creek Way", "Boulder", "CO", "80302", "USA",
            0, "Safety hazard report scenario customer (overheating powerbank)."
        ),
        (
            "CUST-1007", "James", "Wilson", "jwilson99@example.com", "+1-404-555-0131",
            "52 Peachtree Blvd", "Atlanta", "GA", "30303", "USA",
            0, "Lost package inquiry scenario."
        ),
        (
            "CUST-1008", "Aisha", "Patel", "aisha.patel@example.com", "+1-212-555-0155",
            "350 5th Avenue, Fl 18", "New York", "NY", "10118", "USA",
            0, "Just ordered 10 minutes ago, looking to modify address / cancel."
        )
    ]
    cursor.executemany("""
        INSERT INTO customers (customer_id, first_name, last_name, email, phone, street_address, city, state, zip_code, country, is_vip, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, customers_data)

    # 4. Insert Orders
    # Reference Date: October 16, 2026, 16:45:00
    now = datetime(2026, 10, 16, 16, 45, 0)

    orders_data = [
        # Order 1: Recent order placed 12 minutes ago (eligible for 30-min cancellation / modification!)
        (
            "NG-104835", "CUST-1008", (now - timedelta(minutes=12)).strftime("%Y-%m-%d %H:%M:%S"),
            "processing", "Standard Shipping", "USPS", None,
            49.99, 0.00, 4.12, 0.00, 54.11, "Apple Pay", "paid",
            "350 5th Avenue, Fl 18", "New York", "NY", "10118", "USA",
            (now + timedelta(days=4)).strftime("%Y-%m-%d"), None,
            (now - timedelta(minutes=12) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 2: Placed 2 hours ago (cancellation window closed, fulfillment locked)
        (
            "NG-104834", "CUST-1003", (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "confirmed", "Expedited Shipping", "UPS", "1Z999AA10123456784",
            89.98, 9.99, 7.42, 0.00, 107.39, "Visa ending in 4242", "paid",
            "3401 Congress Ave, Suite 210", "Austin", "TX", "78704", "USA",
            (now + timedelta(days=2)).strftime("%Y-%m-%d"), None,
            (now - timedelta(hours=2) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 3: Shipped, currently Out for Delivery today via UPS
        (
            "NG-104833", "CUST-1002", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "out_for_delivery", "Standard Shipping", "UPS", "1Z999AA10198765432",
            69.99, 0.00, 5.77, 0.00, 75.76, "PayPal (elena.rostova@example.com)", "paid",
            "1208 Pine Street, Apt 4B", "Seattle", "WA", "98101", "USA",
            now.strftime("%Y-%m-%d"), None,
            (now - timedelta(days=2) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 4: Shipped, tracking stalled in transit exception (5+ days in transit) -> Triggers replacement / carrier trace
        (
            "NG-104832", "CUST-1007", (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
            "shipped", "Standard Shipping", "FedEx", "748902194812",
            49.99, 0.00, 4.00, 0.00, 53.99, "Mastercard ending in 8812", "paid",
            "52 Peachtree Blvd", "Atlanta", "GA", "30303", "USA",
            (now - timedelta(days=2)).strftime("%Y-%m-%d"), None,
            (now - timedelta(days=7) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 5: Delivered 4 days ago -> Customer within 30-day return window
        (
            "NG-104831", "CUST-1001", (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
            "delivered", "Priority Overnight", "UPS", "1Z999AA10111223344",
            139.97, 19.99, 11.55, 10.00, 161.51, "Visa ending in 1004", "paid",
            "742 Evergreen Terrace", "San Francisco", "CA", "94102", "USA",
            (now - timedelta(days=4)).strftime("%Y-%m-%d"), (now - timedelta(days=4, hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=7) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 6: Delivered 20 days ago -> Active registered warranty, cable defective claim
        (
            "NG-104830", "CUST-1004", (now - timedelta(days=25)).strftime("%Y-%m-%d %H:%M:%S"),
            "delivered", "Standard Shipping", "USPS", "9400111899562537119283",
            19.99, 4.99, 1.65, 0.00, 26.63, "Visa ending in 6721", "paid",
            "88 Beacon Street", "Boston", "MA", "02108", "USA",
            (now - timedelta(days=20)).strftime("%Y-%m-%d"), (now - timedelta(days=20, hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=25) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 7: Delivered 45 days ago -> Past 30-day return window, but within 12/18 month warranty (Power bank overheating incident)
        (
            "NG-104829", "CUST-1006", (now - timedelta(days=50)).strftime("%Y-%m-%d %H:%M:%S"),
            "delivered", "Expedited Shipping", "UPS", "1Z999AA10155667788",
            69.99, 9.99, 5.77, 0.00, 85.75, "Visa ending in 9043", "paid",
            "1420 Boulder Creek Way", "Boulder", "CO", "80302", "USA",
            (now - timedelta(days=46)).strftime("%Y-%m-%d"), (now - timedelta(days=46, hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=50) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 8: Delivered 5 months ago (May 2026) -> Active warranty, loose hinge issue
        (
            "NG-104810", "CUST-1005", (now - timedelta(days=150)).strftime("%Y-%m-%d %H:%M:%S"),
            "delivered", "Standard Shipping", "UPS", "1Z999AA10199887766",
            119.98, 0.00, 9.90, 15.00, 114.88, "Amex ending in 3009", "paid",
            "450 N Michigan Ave, Unit 12A", "Chicago", "IL", "60611", "USA",
            (now - timedelta(days=145)).strftime("%Y-%m-%d"), (now - timedelta(days=145, hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=150) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 9: Delivered 14 months ago (August 2025) -> Standard 12-month expired, but Extended 18-month active because registered!
        (
            "NG-103550", "CUST-1001", (now - timedelta(days=425)).strftime("%Y-%m-%d %H:%M:%S"),
            "delivered", "Standard Shipping", "UPS", "1Z999AA10100112233",
            69.99, 0.00, 5.77, 0.00, 75.76, "Visa ending in 1004", "paid",
            "742 Evergreen Terrace", "San Francisco", "CA", "94102", "USA",
            (now - timedelta(days=420)).strftime("%Y-%m-%d"), (now - timedelta(days=420, hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=425) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Order 10: Delivered 22 months ago (December 2024) -> All warranties completely expired
        (
            "NG-101200", "CUST-1003", (now - timedelta(days=670)).strftime("%Y-%m-%d %H:%M:%S"),
            "delivered", "Standard Shipping", "USPS", "9400111899562537000011",
            49.99, 0.00, 4.12, 0.00, 54.11, "Visa ending in 4242", "paid",
            "3401 Congress Ave, Suite 210", "Austin", "TX", "78704", "USA",
            (now - timedelta(days=665)).strftime("%Y-%m-%d"), (now - timedelta(days=665, hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=670) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        )
    ]
    cursor.executemany("""
        INSERT INTO orders (order_id, customer_id, order_date, status, shipping_tier, carrier, tracking_number,
                            subtotal, shipping_cost, tax, discount_amount, total_amount, payment_method, payment_status,
                            shipping_street, shipping_city, shipping_state, shipping_zip, shipping_country,
                            estimated_delivery_date, actual_delivery_date, cancellation_deadline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, orders_data)

    # 5. Insert Order Items
    order_items_data = [
        # NG-104835 (CUST-1008)
        ("NG-104835", "NG-ASU-SLV", "ApexStand Ultra Ergonomic Aluminum Laptop Stand", 1, 49.99, 49.99),

        # NG-104834 (CUST-1003)
        ("NG-104834", "NG-VBP-BLK", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank", 1, 69.99, 69.99),
        ("NG-104834", "NG-NC100-2M", "NexusCord Braided 100W USB-C to USB-C Cable (2m / 6.6ft)", 1, 19.99, 19.99),

        # NG-104833 (CUST-1002)
        ("NG-104833", "NG-VBP-BLK", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank", 1, 69.99, 69.99),

        # NG-104832 (CUST-1007)
        ("NG-104832", "NG-ASU-GRY", "ApexStand Ultra Ergonomic Aluminum Laptop Stand", 1, 49.99, 49.99),

        # NG-104831 (CUST-1001)
        ("NG-104831", "NG-ASU-GRY", "ApexStand Ultra Ergonomic Aluminum Laptop Stand", 1, 49.99, 49.99),
        ("NG-104831", "NG-VBP-WHT", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank", 1, 69.99, 69.99),
        ("NG-104831", "NG-NC100-2M", "NexusCord Braided 100W USB-C to USB-C Cable (2m / 6.6ft)", 1, 19.99, 19.99),

        # NG-104830 (CUST-1004)
        ("NG-104830", "NG-NC100-2M", "NexusCord Braided 100W USB-C to USB-C Cable (2m / 6.6ft)", 1, 19.99, 19.99),

        # NG-104829 (CUST-1006)
        ("NG-104829", "NG-VBP-BLK", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank", 1, 69.99, 69.99),

        # NG-104810 (CUST-1005)
        ("NG-104810", "NG-ASU-SLV", "ApexStand Ultra Ergonomic Aluminum Laptop Stand", 1, 49.99, 49.99),
        ("NG-104810", "NG-VBP-BLK", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank", 1, 69.99, 69.99),

        # NG-103550 (CUST-1001)
        ("NG-103550", "NG-VBP-BLK", "VoltBoost Pro 20,000mAh 65W Fast Charge Power Bank", 1, 69.99, 69.99),

        # NG-101200 (CUST-1003)
        ("NG-101200", "NG-ASU-SLV", "ApexStand Ultra Ergonomic Aluminum Laptop Stand", 1, 49.99, 49.99)
    ]
    cursor.executemany("""
        INSERT INTO order_items (order_id, sku, product_name, quantity, unit_price, total_price)
        VALUES (?, ?, ?, ?, ?, ?);
    """, order_items_data)

    # 6. Insert Warranties & Registrations
    # Policy: 12 months standard. 18 months if registered online within 30 days of purchase.
    warranties_data = [
        # Customer 1: Registered VoltBoost from Order NG-103550 (14 months ago -> 18 mo extended active!)
        (
            "WAR-2025-0104", "NG-103550", "CUST-1001", "NG-VBP-BLK", "SN: VB2408-77124",
            (now - timedelta(days=425)).strftime("%Y-%m-%d"),
            (now - timedelta(days=415)).strftime("%Y-%m-%d"),
            1, 18,
            (now - timedelta(days=425)).strftime("%Y-%m-%d"),
            (now - timedelta(days=425) + timedelta(days=548)).strftime("%Y-%m-%d"), # 18 months
            "active", None
        ),
        # Customer 1: Stand from Order NG-104831 (Delivered 4 days ago, not registered yet, standard 12 mo active)
        (
            "WAR-2026-0891", "NG-104831", "CUST-1001", "NG-ASU-GRY", "SN: AS2408-88310",
            (now - timedelta(days=7)).strftime("%Y-%m-%d"), None, 0, 12,
            (now - timedelta(days=7)).strftime("%Y-%m-%d"),
            (now - timedelta(days=7) + timedelta(days=365)).strftime("%Y-%m-%d"),
            "active", None
        ),
        # Customer 1: Power bank from Order NG-104831 (Delivered 4 days ago, registered online yesterday -> 18 mo)
        (
            "WAR-2026-0892", "NG-104831", "CUST-1001", "NG-VBP-WHT", "SN: VB2408-99411",
            (now - timedelta(days=7)).strftime("%Y-%m-%d"),
            (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            1, 18,
            (now - timedelta(days=7)).strftime("%Y-%m-%d"),
            (now - timedelta(days=7) + timedelta(days=548)).strftime("%Y-%m-%d"),
            "active", None
        ),
        # Customer 4: NexusCord cable from Order NG-104830 (25 days ago, standard 12 mo active, defect reported)
        (
            "WAR-2026-0775", "NG-104830", "CUST-1004", "NG-NC100-2M", "SN: NC2410-55421",
            (now - timedelta(days=25)).strftime("%Y-%m-%d"), None, 0, 12,
            (now - timedelta(days=25)).strftime("%Y-%m-%d"),
            (now - timedelta(days=25) + timedelta(days=365)).strftime("%Y-%m-%d"),
            "active", None
        ),
        # Customer 6: VoltBoost from Order NG-104829 (50 days ago, safety hazard reported)
        (
            "WAR-2026-0610", "NG-104829", "CUST-1006", "NG-VBP-BLK", "SN: VB2408-98412",
            (now - timedelta(days=50)).strftime("%Y-%m-%d"),
            (now - timedelta(days=40)).strftime("%Y-%m-%d"),
            1, 18,
            (now - timedelta(days=50)).strftime("%Y-%m-%d"),
            (now - timedelta(days=50) + timedelta(days=548)).strftime("%Y-%m-%d"),
            "claimed", None
        ),
        # Customer 5: ApexStand from Order NG-104810 (150 days ago, standard 12 mo active, loose hinge)
        (
            "WAR-2026-0312", "NG-104810", "CUST-1005", "NG-ASU-SLV", "SN: AS2408-11203",
            (now - timedelta(days=150)).strftime("%Y-%m-%d"), None, 0, 12,
            (now - timedelta(days=150)).strftime("%Y-%m-%d"),
            (now - timedelta(days=150) + timedelta(days=365)).strftime("%Y-%m-%d"),
            "active", None
        ),
        # Customer 3: Order NG-101200 from 22 months ago -> Expired
        (
            "WAR-2024-0019", "NG-101200", "CUST-1003", "NG-ASU-SLV", "SN: AS2401-00122",
            (now - timedelta(days=670)).strftime("%Y-%m-%d"), None, 0, 12,
            (now - timedelta(days=670)).strftime("%Y-%m-%d"),
            (now - timedelta(days=670) + timedelta(days=365)).strftime("%Y-%m-%d"),
            "expired", "Standard 1-year warranty expired on " + (now - timedelta(days=670) + timedelta(days=365)).strftime("%Y-%m-%d")
        )
    ]
    cursor.executemany("""
        INSERT INTO warranties (warranty_id, order_id, customer_id, sku, serial_number, purchase_date,
                                registration_date, is_registered, warranty_period_months, warranty_start_date,
                                warranty_end_date, status, void_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, warranties_data)

    # 7. Insert RMA Claims (Returns & Warranty claims)
    rma_claims_data = [
        # RMA 1: Cable defective claim (Sarah Jenkins / NG-104830) -> Approved, free replacement shipped!
        (
            "RMA-84915", "NG-104830", "CUST-1004", "NG-NC100-2M", "SN: NC2410-55421",
            "warranty_replacement", "e_marker_failure",
            "Cable charges at standard 5W but fails 60W/100W PD fast charge negotiation. Verified across 2 MacBook chargers.",
            "replacement_shipped", 0.00, 0.00, 0.00,
            None, "NG-104836-REP", "9400111899562537999881",
            "Warranty verified. Cable replacement dispatched via USPS First Class per warranty policy.",
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # RMA 2: Return for Buyer's Remorse within 30 days (Marcus Vance / NG-104831 - returned Stand)
        (
            "RMA-84920", "NG-104831", "CUST-1001", "NG-ASU-GRY", "SN: AS2408-88310",
            "refund_return", "buyer_remorse",
            "Decided to use a desktop monitor arm instead. Stand is unopened in pristine retail packaging.",
            "label_emailed", 5.99, 0.00, 44.00,
            "1Z999AA19088776655", None, None,
            "Return approved within 30-day window. Flat $5.99 label fee will be deducted upon receipt.",
            (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            None
        ),
        # RMA 3: Damaged on Arrival (DOA) replacement completed
        (
            "RMA-84880", "NG-104810", "CUST-1005", "NG-ASU-SLV", "SN: AS2408-11203",
            "warranty_replacement", "loose_hinges_stiffness",
            "Customer tried adjusting tension screws with included hex tool twice, but lower pivot hinge slips under 15-inch laptop weight.",
            "approved", 0.00, 0.00, 0.00,
            "1Z999AA19011223344", "NG-104837-REP", None,
            "Tier 2 hardware review passed (repeated failed troubleshooting trigger). Authorized direct RMA replacement.",
            (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
            None
        )
    ]
    cursor.executemany("""
        INSERT INTO rma_claims (rma_id, order_id, customer_id, sku, serial_number, claim_type, reason_category,
                                customer_complaint, status, shipping_fee_deducted, repackaging_fee_deducted,
                                refund_amount, return_tracking_number, replacement_order_id, replacement_tracking_number,
                                admin_notes, created_at, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, rma_claims_data)

    # 8. Insert Tracking Events
    tracking_events_data = [
        # Order NG-104833 (Out for delivery today - UPS 1Z999AA10198765432)
        ("1Z999AA10198765432", "UPS", (now - timedelta(days=2)).strftime("%Y-%m-%d 14:20:00"), "Label Created", "Austin, TX", "Shipping label created, package awaiting courier pickup."),
        ("1Z999AA10198765432", "UPS", (now - timedelta(days=2)).strftime("%Y-%m-%d 18:45:00"), "Departed Origin Facility", "Austin, TX", "Package received by carrier and processed through Austin distribution center."),
        ("1Z999AA10198765432", "UPS", (now - timedelta(days=1)).strftime("%Y-%m-%d 08:30:00"), "In Transit", "Salt Lake City, UT", "Package in transit to destination sorting hub."),
        ("1Z999AA10198765432", "UPS", now.strftime("%Y-%m-%d 06:15:00"), "Arrived at Destination Hub", "Seattle, WA", "Arrived at local Seattle delivery center."),
        ("1Z999AA10198765432", "UPS", now.strftime("%Y-%m-%d 08:45:00"), "Out for Delivery", "Seattle, WA", "Package loaded onto delivery vehicle, expected delivery between 1:00 PM and 5:00 PM today."),

        # Order NG-104832 (Stalled package - FedEx 748902194812 - 5+ days stuck in Louisville)
        ("748902194812", "FedEx", (now - timedelta(days=7)).strftime("%Y-%m-%d 15:00:00"), "Picked Up", "Austin, TX", "Package accepted at FedEx origin sorting facility."),
        ("748902194812", "FedEx", (now - timedelta(days=6)).strftime("%Y-%m-%d 22:10:00"), "Arrived at Sort Facility", "Louisville, KY", "Package arrived at major regional ground hub."),
        ("748902194812", "FedEx", (now - timedelta(days=5)).strftime("%Y-%m-%d 04:30:00"), "Operational Delay", "Louisville, KY", "Severe regional weather delay. Package scan pending further carrier notice."),

        # Order NG-104831 (Delivered 4 days ago - UPS 1Z999AA10111223344)
        ("1Z999AA10111223344", "UPS", (now - timedelta(days=6)).strftime("%Y-%m-%d 16:00:00"), "Origin Scan", "Austin, TX", "Package picked up by UPS Next Day Air."),
        ("1Z999AA10111223344", "UPS", (now - timedelta(days=5)).strftime("%Y-%m-%d 05:30:00"), "Arrived at Airport Hub", "Oakland, CA", "Arrived at San Francisco Bay regional hub."),
        ("1Z999AA10111223344", "UPS", (now - timedelta(days=4)).strftime("%Y-%m-%d 08:00:00"), "Out for Delivery", "San Francisco, CA", "Out for delivery with courier."),
        ("1Z999AA10111223344", "UPS", (now - timedelta(days=4, hours=2)).strftime("%Y-%m-%d 14:15:00"), "Delivered", "San Francisco, CA", "Delivered. Left at Front Door / Porch. Signed by M. Vance."),

        # Order NG-104830 (Delivered 20 days ago - USPS 9400111899562537119283)
        ("9400111899562537119283", "USPS", (now - timedelta(days=24)).strftime("%Y-%m-%d 11:00:00"), "Accepted", "Austin, TX", "Accepted at USPS Origin Facility."),
        ("9400111899562537119283", "USPS", (now - timedelta(days=20, hours=5)).strftime("%Y-%m-%d 13:40:00"), "Delivered", "Boston, MA", "Delivered, In/At Mailbox.")
    ]
    cursor.executemany("""
        INSERT INTO tracking_events (tracking_number, carrier, event_time, status, location, description)
        VALUES (?, ?, ?, ?, ?, ?);
    """, tracking_events_data)

    # 9. Insert Support Tickets (Escalations, inquiries, and historical records)
    support_tickets_data = [
        # Ticket 1: CRITICAL THERMAL SAFETY HAZARD (Trigger 1 from Knowledge Base!)
        (
            "TICK-9021", "CUST-1006", "NG-104829", "email", "rachel.g@example.com",
            "URGENT: My VoltBoost battery is bulging and smells like burning plastic!",
            "urgent_safety_hazard", "Safety & Compliance Team", "escalated_to_tier2",
            "Customer reports VoltBoost Pro 20K casing has visible swelling/bloat and emits a chemical burning odor after charging overnight.",
            "Advised customer immediately to unplug device, cease use, and relocate to a non-flammable cool location. Case flagged as P1 URGENT_SAFETY_HAZARD and transferred directly to escalations@novagear.com.",
            "Safety hazard trigger: Swollen lithium casing and burning odor.",
            (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Ticket 2: Order Modification inquiry within 30-min window
        (
            "TICK-9022", "CUST-1008", "NG-104835", "email", "aisha.patel@example.com",
            "Need to update shipping suite number for order NG-104835",
            "medium", "Tier 1 AI Support", "open",
            "Customer ordered 12 minutes ago, forgot to specify suite number 'Floor 18, Suite 1802'.",
            None,
            None,
            (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Ticket 3: Stalled tracking inquiry (5+ days in transit)
        (
            "TICK-9018", "CUST-1007", "NG-104832", "email", "jwilson99@example.com",
            "Where is my ApexStand? Tracking hasn't moved in 5 days!",
            "high", "Tier 2 Customer Care", "in_investigation",
            "FedEx tracking 748902194812 stalled in Louisville since Oct 11. Customer inquiring on status.",
            "Carrier trace filed with FedEx. Per shipping policy section 5, if not updated within 48 hours, issue replacement shipment.",
            "Carrier tracking exception > 5 business days.",
            (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Ticket 4: Churn risk & anger (threat of chargeback)
        (
            "TICK-9015", "CUST-1007", "NG-104832", "email", "jwilson99@example.com",
            "If this package doesn't arrive by Friday I am doing a chargeback and filing BBB complaint!",
            "high", "Executive Escalations Desk", "escalated_to_tier2",
            "Customer angry about shipping delay, mentions credit card chargeback and BBB filing.",
            "Assigned to Senior Support Lead. Escalation template dispatched.",
            "Customer threatened chargeback and BBB complaint (Trigger 2: Severe Customer Frustration & Churn Risk).",
            (now - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=17)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Ticket 5: Resolved cable warranty claim
        (
            "TICK-8994", "CUST-1004", "NG-104830", "email", "sarah.jenkins@example.com",
            "Warranty Claim - NexusCord USB-C stopped fast charging",
            "medium", "Hardware Warranty Team", "resolved",
            "Customer provided video showing NexusCord failing 100W PD charging. Claim approved.",
            "Issued RMA-84915. Replacement order NG-104836-REP dispatched via USPS First Class.",
            None,
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        )
    ]
    cursor.executemany("""
        INSERT INTO support_tickets (ticket_id, customer_id, order_id, channel, customer_email, subject,
                                    priority, assigned_team, status, issue_summary, resolution_notes,
                                    escalation_reason, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, support_tickets_data)

    # 10. Insert Promo Codes
    promo_codes_data = [
        ("WELCOME10", "percentage", 10.0, 30.00, 1, "2027-12-31", "10% off for first-time customers on orders $30+"),
        ("NOVASAVE15", "percentage", 15.0, 50.00, 1, "2026-12-31", "15% off orders over $50"),
        ("FREECABLE", "fixed_amount", 19.99, 100.00, 1, "2026-11-30", "$19.99 discount on orders over $100"),
        ("VIPCLUB20", "percentage", 20.0, 40.00, 1, "2027-06-30", "Exclusive 20% discount for registered VIP members")
    ]
    cursor.executemany("""
        INSERT INTO promo_codes (code, discount_type, discount_value, min_order_value, is_active, expires_at, description)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, promo_codes_data)

    conn.commit()

    # Export JSON fixtures for each table for quick agent inspection
    for table in tables:
        cursor.execute(f"SELECT * FROM {table};")
        col_names = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        data = [dict(zip(col_names, row)) for row in rows]
        fixture_path = os.path.join(FIXTURES_DIR, f"{table}.json")
        with open(fixture_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    conn.close()
    print("NovaGear SQLite database & JSON fixtures successfully populated!")


if __name__ == "__main__":
    seed_database()
