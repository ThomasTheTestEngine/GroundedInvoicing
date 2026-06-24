"""
Data access layer for the invoicing app.

All functions open a short-lived connection per call. For a single-user
desktop app this is simple and avoids connection lifecycle headaches.
"""

import sqlite3
from datetime import date
from pathlib import Path
from db_setup import DB_PATH, init_db


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

STATUSES = ["DUE", "PARTIALLY_PAID", "PAID"]

def display_status(stored_status, due_date_str):
    """Convert stored status + due date into what to show the user."""
    if stored_status == "DUE":
        try:
            if date.fromisoformat(due_date_str) < date.today():
                return "OVERDUE"
        except (ValueError, TypeError):
            pass
        return "DUE"
    return stored_status


def invoice_total(invoice):
    """Compute gross total from an invoice dict (with 'items' list)."""
    subtotal = sum(i["quantity"] * i["unit_price"] for i in invoice.get("items", []))
    shipping = invoice.get("shipping") or 0
    tax = subtotal * (invoice.get("tax_rate") or 0)
    return subtotal + shipping + tax


def invoice_balance_due(invoice):
    """Total minus any partial payment."""
    total = invoice_total(invoice)
    paid = invoice.get("amount_paid") or 0
    return max(0, total - paid)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def add_client(first_name, last_name, business_name=None, phone=None,
                email=None, address1=None, address2=None, notes=None, cc_emails=None):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO clients
           (first_name, last_name, business_name, phone, email, address1, address2, notes, cc_emails)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (first_name, last_name, business_name, phone, email, address1, address2, notes, cc_emails),
    )
    conn.commit()
    client_id = cur.lastrowid
    conn.close()
    return client_id


def update_client(client_id, first_name, last_name, business_name=None,
                   phone=None, email=None, address1=None, address2=None,
                   notes=None, cc_emails=None):
    conn = get_conn()
    conn.execute(
        """UPDATE clients
           SET first_name=?, last_name=?, business_name=?, phone=?, email=?,
               address1=?, address2=?, notes=?, cc_emails=?
           WHERE id=?""",
        (first_name, last_name, business_name, phone, email,
         address1, address2, notes, cc_emails, client_id),
    )
    conn.commit()
    conn.close()


def delete_client(client_id):
    """Raises sqlite3.IntegrityError if the client has invoices (FK constraint)."""
    conn = get_conn()
    conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
    conn.commit()
    conn.close()


def get_client(client_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_clients(sort_by="last_name", ascending=True):
    allowed = {"first_name", "last_name", "business_name", "phone", "email"}
    if sort_by not in allowed:
        sort_by = "last_name"
    direction = "ASC" if ascending else "DESC"

    conn = get_conn()
    rows = conn.execute(
        f"SELECT * FROM clients ORDER BY {sort_by} COLLATE NOCASE {direction}"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_invoices_for_client(client_id, sort_by="invoice_number", ascending=False):
    """Returns invoices for a specific client with computed total and display status."""
    column_map = {
        "invoice_number": "invoices.invoice_number",
        "invoice_date": "invoices.invoice_date",
        "due_date": "invoices.due_date",
        "status": "invoices.status",
    }
    sort_col = column_map.get(sort_by, "invoices.invoice_number")
    direction = "ASC" if ascending else "DESC"

    conn = get_conn()
    inv_rows = conn.execute(
        f"""SELECT invoices.id, invoices.invoice_number, invoices.invoice_date,
                   invoices.due_date, invoices.status, invoices.shipping,
                   invoices.tax_rate
            FROM invoices
            WHERE invoices.client_id = ?
            ORDER BY {sort_col} COLLATE NOCASE {direction}""",
        (client_id,),
    ).fetchall()

    results = []
    for inv in inv_rows:
        inv_dict = dict(inv)
        item_rows = conn.execute(
            "SELECT quantity, unit_price FROM invoice_items WHERE invoice_id=?",
            (inv_dict["id"],),
        ).fetchall()
        inv_dict["items"] = [dict(r) for r in item_rows]
        inv_dict["total"] = invoice_total(inv_dict)
        inv_dict["balance_due"] = invoice_balance_due(inv_dict)
        inv_dict["display_status"] = display_status(inv_dict["status"], inv_dict["due_date"])
        results.append(inv_dict)

    conn.close()
    return results


# ---------------------------------------------------------------------------
# Invoice numbering
# ---------------------------------------------------------------------------

def next_invoice_number():
    conn = get_conn()
    row = conn.execute("SELECT last_number FROM invoice_counter WHERE id=1").fetchone()
    conn.close()
    next_n = row["last_number"] + 1
    return f"GR{next_n:05d}"


def _consume_invoice_number(conn):
    row = conn.execute("SELECT last_number FROM invoice_counter WHERE id=1").fetchone()
    next_n = row["last_number"] + 1
    conn.execute("UPDATE invoice_counter SET last_number=? WHERE id=1", (next_n,))
    return f"GR{next_n:05d}"


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

def create_invoice(client_id, invoice_date, due_date, shipping, tax_rate,
                    tracking_number, items, status="DUE", notes=None,
                    carrier="UPS", tax_label="HST", amount_paid=0,
                    payment_method=None, shipped=0, sent=0):
    conn = get_conn()
    try:
        invoice_number = _consume_invoice_number(conn)
        cur = conn.execute(
            """INSERT INTO invoices
               (invoice_number, client_id, invoice_date, due_date, shipping,
                tax_rate, tracking_number, status, notes, carrier, tax_label,
                amount_paid, payment_method, shipped, sent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (invoice_number, client_id, invoice_date, due_date, shipping,
             tax_rate, tracking_number, status, notes, carrier, tax_label,
             amount_paid, payment_method, shipped, sent),
        )
        invoice_id = cur.lastrowid

        for i, item in enumerate(items):
            conn.execute(
                """INSERT INTO invoice_items
                   (invoice_id, code, description, quantity, unit_price, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invoice_id, item.get("code"), item["description"],
                 item["quantity"], item["unit_price"], i),
            )

        conn.commit()
        return invoice_id, invoice_number
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_invoice(invoice_id, client_id, invoice_date, due_date, shipping,
                    tax_rate, tracking_number, items, status="DUE", notes=None,
                    carrier="UPS", tax_label="HST", amount_paid=0,
                    payment_method=None, shipped=0, sent=0):
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE invoices
               SET client_id=?, invoice_date=?, due_date=?, shipping=?, tax_rate=?,
                   tracking_number=?, status=?, notes=?, carrier=?, tax_label=?,
                   amount_paid=?, payment_method=?, shipped=?, sent=?
               WHERE id=?""",
            (client_id, invoice_date, due_date, shipping, tax_rate,
             tracking_number, status, notes, carrier, tax_label,
             amount_paid, payment_method, shipped, sent, invoice_id),
        )

        conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (invoice_id,))
        for i, item in enumerate(items):
            conn.execute(
                """INSERT INTO invoice_items
                   (invoice_id, code, description, quantity, unit_price, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invoice_id, item.get("code"), item["description"],
                 item["quantity"], item["unit_price"], i),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_invoice(invoice_id):
    conn = get_conn()
    conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (invoice_id,))
    conn.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
    conn.commit()
    conn.close()


def get_invoice(invoice_id):
    """Returns a dict with invoice fields, nested 'client' dict, and 'items' list."""
    conn = get_conn()
    inv_row = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv_row:
        conn.close()
        return None

    invoice = dict(inv_row)

    client_row = conn.execute(
        "SELECT * FROM clients WHERE id=?", (invoice["client_id"],)
    ).fetchone()
    invoice["client"] = dict(client_row) if client_row else None

    item_rows = conn.execute(
        "SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY sort_order",
        (invoice_id,),
    ).fetchall()
    invoice["items"] = [dict(r) for r in item_rows]
    invoice["total"] = invoice_total(invoice)
    invoice["balance_due"] = invoice_balance_due(invoice)
    invoice["display_status"] = display_status(invoice["status"], invoice["due_date"])

    conn.close()
    return invoice


def mark_invoice_sent(invoice_id, sent_date_str, append_note=True):
    """Mark an invoice as sent, optionally appending a note with the date."""
    conn = get_conn()
    if append_note:
        row = conn.execute(
            "SELECT notes FROM invoices WHERE id=?", (invoice_id,)
        ).fetchone()
        existing = (row["notes"] or "").strip() if row else ""
        stamp = f"Sent on {sent_date_str}"
        new_notes = f"{existing}\n{stamp}".strip() if existing else stamp
        conn.execute(
            "UPDATE invoices SET sent=1, notes=? WHERE id=?",
            (new_notes, invoice_id)
        )
    else:
        conn.execute("UPDATE invoices SET sent=1 WHERE id=?", (invoice_id,))
    conn.commit()
    conn.close()


def list_invoices(sort_by="invoice_number", ascending=False):
    """Returns invoices joined with client info, including computed total and display status."""
    column_map = {
        "invoice_number": "invoices.invoice_number",
        "invoice_date": "invoices.invoice_date",
        "due_date": "invoices.due_date",
        "first_name": "clients.first_name",
        "last_name": "clients.last_name",
        "business_name": "clients.business_name",
        "status": "invoices.status",
        "shipped": "invoices.shipped",
    }
    sort_col = column_map.get(sort_by, "invoices.invoice_number")
    direction = "ASC" if ascending else "DESC"

    conn = get_conn()
    inv_rows = conn.execute(
        f"""SELECT invoices.id, invoices.invoice_number, invoices.invoice_date,
                   invoices.due_date, invoices.status, invoices.shipping,
                   invoices.tax_rate, invoices.amount_paid, invoices.shipped,
                   invoices.sent,
                   clients.first_name, clients.last_name, clients.business_name
            FROM invoices
            JOIN clients ON clients.id = invoices.client_id
            ORDER BY {sort_col} COLLATE NOCASE {direction}"""
    ).fetchall()

    results = []
    for inv in inv_rows:
        inv_dict = dict(inv)
        item_rows = conn.execute(
            "SELECT quantity, unit_price FROM invoice_items WHERE invoice_id=?",
            (inv_dict["id"],),
        ).fetchall()
        inv_dict["items"] = [dict(r) for r in item_rows]
        inv_dict["total"] = invoice_total(inv_dict)
        inv_dict["balance_due"] = invoice_balance_due(inv_dict)
        inv_dict["display_status"] = display_status(inv_dict["status"], inv_dict["due_date"])
        results.append(inv_dict)

    conn.close()
    return results


def get_stripe_key():
    return get_setting("stripe_secret_key")


def set_stripe_key(key):
    set_setting("stripe_secret_key", key)


def get_stripe_session(invoice_id):
    conn = get_conn()
    row = conn.execute(
        """SELECT stripe_session_id, stripe_checkout_url,
                  stripe_session_amount, stripe_session_expires
           FROM invoices WHERE id=?""",
        (invoice_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def save_stripe_session(invoice_id, session_id, checkout_url, amount):
    conn = get_conn()
    conn.execute(
        """UPDATE invoices
           SET stripe_session_id=?, stripe_checkout_url=?,
               stripe_session_amount=?, stripe_session_expires=NULL
           WHERE id=?""",
        (session_id, checkout_url, amount, invoice_id)
    )
    conn.commit()
    conn.close()


def clear_stripe_session(invoice_id):
    conn = get_conn()
    conn.execute(
        """UPDATE invoices
           SET stripe_session_id=NULL, stripe_checkout_url=NULL,
               stripe_session_amount=NULL, stripe_session_expires=NULL
           WHERE id=?""",
        (invoice_id,)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized. Ready for use.")


# ---------------------------------------------------------------------------
# Company info
# ---------------------------------------------------------------------------

def get_company():
    conn = get_conn()
    row = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}


def mark_sent(invoice_id, sent=1, note=None):
    """Quick update — sets sent flag and optionally appends a note."""
    conn = get_conn()
    if note:
        row = conn.execute(
            "SELECT notes FROM invoices WHERE id=?", (invoice_id,)
        ).fetchone()
        existing = (row["notes"] or "").strip() if row else ""
        new_notes = f"{existing}\n{note}".strip() if existing else note
        conn.execute(
            "UPDATE invoices SET sent=?, notes=? WHERE id=?",
            (sent, new_notes, invoice_id)
        )
    else:
        conn.execute(
            "UPDATE invoices SET sent=? WHERE id=?", (sent, invoice_id)
        )
    conn.commit()
    conn.close()


def update_company(name, address1, address2, phone, email, tax_id):
    conn = get_conn()
    conn.execute(
        """UPDATE company
           SET name=?, address1=?, address2=?, phone=?, email=?, tax_id=?
           WHERE id=1""",
        (name, address1, address2, phone, email, tax_id)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# App settings (theme, font, etc.)
# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key=?", (key,)
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def get_theme():
    """Returns theme dict with RGB tuples."""
    from db_setup import DEFAULT_THEME

    def parse(key, default_str):
        raw = get_setting(f"theme_{key}", default_str)
        return tuple(int(x) for x in raw.split(","))

    return {
        "accent":     parse("accent",     DEFAULT_THEME["accent"]),
        "dark":       parse("dark",       DEFAULT_THEME["dark"]),
        "light_gray": parse("light_gray", DEFAULT_THEME["light_gray"]),
        "mid_gray":   parse("mid_gray",   DEFAULT_THEME["mid_gray"]),
        "text":       parse("text",       DEFAULT_THEME["text"]),
        "font":       get_setting("theme_font", DEFAULT_THEME["font"]),
    }


def set_theme(theme_dict):
    """Save theme dict (values as RGB tuples or strings for font)."""
    for key, value in theme_dict.items():
        if key == "font":
            set_setting("theme_font", value)
        else:
            set_setting(f"theme_{key}", ",".join(str(x) for x in value))

