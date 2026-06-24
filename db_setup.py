"""
Database setup for Grounded Invoicing.

DB file is named after the company (from company table once set up,
defaulting to grounded_invoicing.db on first run).
"""

import sqlite3
from pathlib import Path

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "grounded_invoicing.db"

# On startup: if old invoices.db exists and new one doesn't, migrate automatically
def _auto_migrate_old_db():
    old = APP_DIR / "invoices.db"
    if old.exists() and not DB_PATH.exists():
        import shutil
        shutil.copy2(old, DB_PATH)

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    business_name TEXT,
    phone TEXT,
    email TEXT,
    address1 TEXT,
    address2 TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    client_id INTEGER NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    shipping REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0.13,
    tracking_number TEXT,
    status TEXT NOT NULL DEFAULT 'DUE',
    notes TEXT,
    carrier TEXT DEFAULT 'UPS',
    tax_label TEXT DEFAULT 'HST',
    amount_paid REAL DEFAULT 0,
    payment_method TEXT,
    shipped INTEGER DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    code TEXT,
    description TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    sort_order INTEGER NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invoice_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_number INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name        TEXT NOT NULL DEFAULT 'My Company',
    address1    TEXT DEFAULT '',
    address2    TEXT DEFAULT '',
    phone       TEXT DEFAULT '',
    email       TEXT DEFAULT '',
    tax_id      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

MIGRATIONS = [
    "ALTER TABLE clients ADD COLUMN notes TEXT",
    "ALTER TABLE invoices ADD COLUMN status TEXT NOT NULL DEFAULT 'DUE'",
    "ALTER TABLE invoices ADD COLUMN notes TEXT",
    "ALTER TABLE invoices ADD COLUMN carrier TEXT DEFAULT 'UPS'",
    "ALTER TABLE invoices ADD COLUMN tax_label TEXT DEFAULT 'HST'",
    "ALTER TABLE invoices ADD COLUMN amount_paid REAL DEFAULT 0",
    "ALTER TABLE invoices ADD COLUMN payment_method TEXT",
    "ALTER TABLE invoices ADD COLUMN shipped INTEGER DEFAULT 0",
    "ALTER TABLE invoices ADD COLUMN sent INTEGER DEFAULT 0",
    "ALTER TABLE invoices ADD COLUMN stripe_session_id TEXT",
    "ALTER TABLE invoices ADD COLUMN stripe_checkout_url TEXT",
    "ALTER TABLE invoices ADD COLUMN stripe_session_amount REAL",
    "ALTER TABLE invoices ADD COLUMN stripe_session_expires INTEGER",
    "ALTER TABLE clients ADD COLUMN cc_emails TEXT",
]

DEFAULT_COMPANY = {
    "name":     "Grounded Repairs",
    "address1": "560 Weller St.",
    "address2": "Peterborough, ON, K9H 2N6",
    "phone":    "(705) 761 2938",
    "email":    "thomas@groundedrepairs.com",
    "tax_id":   "756577631",
}

DEFAULT_THEME = {
    "accent":     "76,195,235",
    "dark":       "74,84,99",
    "light_gray": "245,246,248",
    "mid_gray":   "110,120,135",
    "text":       "40,45,55",
    "font":       "Helvetica",
}


def init_db(db_path=DB_PATH):
    _auto_migrate_old_db()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    for migration in MIGRATIONS:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass

    conn.execute(
        "INSERT OR IGNORE INTO invoice_counter (id, last_number) VALUES (1, 0)"
    )

    # Seed company row
    conn.execute(
        """INSERT OR IGNORE INTO company
           (id, name, address1, address2, phone, email, tax_id)
           VALUES (1, ?, ?, ?, ?, ?, ?)""",
        (DEFAULT_COMPANY["name"], DEFAULT_COMPANY["address1"],
         DEFAULT_COMPANY["address2"], DEFAULT_COMPANY["phone"],
         DEFAULT_COMPANY["email"], DEFAULT_COMPANY["tax_id"])
    )

    # Seed theme defaults
    for key, value in DEFAULT_THEME.items():
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
            (f"theme_{key}", value)
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH}")
