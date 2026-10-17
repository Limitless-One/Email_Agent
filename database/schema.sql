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
