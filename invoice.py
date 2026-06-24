from fpdf import FPDF
from datetime import date
from pathlib import Path

import data as _data

LOGO_PATH = Path(__file__).parent / "logo.png"


def fmt_currency(val):
    return f"${val:,.2f}"


def fmt_date(d):
    return date.fromisoformat(d).strftime("%d/%m/%Y")


def fmt_qty(q):
    return f"{q:g}"


def _rgb(t):
    return t  # already a tuple


class InvoicePDF(FPDF):
    def __init__(self, theme, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.theme = theme

    def footer(self):
        self.set_y(-20)
        self.set_font(self.theme["font"], "", 8)
        self.set_text_color(*self.theme["mid_gray"])
        self.cell(0, 5, "Thank you for choosing Grounded Repairs! We value your business.",
                  align="C", new_x="LMARGIN", new_y="NEXT")


def _load_resources():
    theme = _data.get_theme()
    company = _data.get_company()
    return theme, company


# Lorem ipsum preview invoice used when no real invoices exist
PREVIEW_INVOICE = {
    "invoice_number": "GR00001",
    "invoice_date":   "2026-06-15",
    "due_date":       "2026-06-29",
    "shipping":       12.40,
    "tax_rate":       0.13,
    "tax_label":      "HST",
    "tracking_number":"1Z999AA10123456784",
    "carrier":        "UPS",
    "status":         "DUE",
    "amount_paid":    0,
    "payment_method": None,
    "client": {
        "first_name":    "Lorem",
        "last_name":     "Ipsum",
        "business_name": "Ipsum Industries",
        "address1":      "123 Lorem St.",
        "address2":      "Dolor, ON, L0R 3M1",
        "phone":         "(555) 867 5309",
        "email":         "lorem@ipsum.com",
    },
    "items": [
        {"code": "RPR-001",
         "description": "Diagnostic and inspection of Lorem Ipsum unit - pellentesque habitant morbi tristique senectus.",
         "quantity": 1, "unit_price": 85.00},
        {"code": "PRT-042",
         "description": "Replacement component (sourced and installed)\nIncludes bench testing under load to confirm stable output.",
         "quantity": 1, "unit_price": 32.50},
        {"code": "LAB-002",
         "description": "Labor - component-level repair, consectetur adipiscing elit.",
         "quantity": 2.5, "unit_price": 60.00},
        {"code": "SVC-007",
         "description": "Firmware update and configuration restore, sed do eiusmod tempor.",
         "quantity": 1, "unit_price": 45.00},
    ],
}


def build_invoice_pdf(invoice, output_path, theme=None, company=None, show_codes=False):
    if theme is None or company is None:
        _theme, _company = _load_resources()
        theme = theme or _theme
        company = company or _company

    ACCENT     = theme["accent"]
    DARK       = theme["dark"]
    LIGHT_GRAY = theme["light_gray"]
    MID_GRAY   = theme["mid_gray"]
    TEXT       = theme["text"]
    FONT       = theme["font"]

    pdf = InvoicePDF(theme=theme, format="Letter", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()
    pdf.set_margins(left=18, top=15, right=18)

    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    # ---------- HEADER ----------
    logo_w = 38
    if LOGO_PATH.exists():
        pdf.image(str(LOGO_PATH), x=pdf.l_margin, y=pdf.t_margin, w=logo_w)

    meta_x = pdf.l_margin + page_w - 65
    pdf.set_xy(meta_x, pdf.t_margin)
    pdf.set_font(FONT, "B", 16)
    pdf.set_text_color(*DARK)
    pdf.cell(65, 7, "INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")

    def meta_row(label, value):
        pdf.set_x(meta_x)
        pdf.set_font(FONT, "", 9.5)
        pdf.set_text_color(*MID_GRAY)
        pdf.cell(30, 6, label, align="L")
        pdf.set_font(FONT, "B", 9.5)
        pdf.set_text_color(*TEXT)
        pdf.cell(35, 6, value, align="R", new_x="LMARGIN", new_y="NEXT")

    meta_row("Invoice No.", invoice["invoice_number"])
    meta_row("Date", fmt_date(invoice["invoice_date"]))
    meta_row("Due Date", fmt_date(invoice["due_date"]))

    # ---------- ACCENT RULE ----------
    rule_y = pdf.t_margin + max(logo_w * 0.42, 30) + 4
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, rule_y, pdf.l_margin + page_w, rule_y)

    # ---------- COMPANY / BILL TO ----------
    pdf.set_y(rule_y + 6)
    col_w = page_w / 2 - 4
    start_y = pdf.get_y()

    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "B", 12)
    pdf.set_text_color(*DARK)
    pdf.cell(col_w, 6, company.get("name", ""), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(FONT, "", 9.5)
    pdf.set_text_color(*TEXT)
    for line in [
        company.get("address1", ""),
        company.get("address2", ""),
        company.get("phone", ""),
        company.get("email", ""),
        f"Tax ID: {company.get('tax_id', '')}" if company.get("tax_id") else "",
    ]:
        if line:
            pdf.set_x(pdf.l_margin)
            pdf.cell(col_w, 5.2, line, new_x="LMARGIN", new_y="NEXT")

    left_block_end = pdf.get_y()

    # Bill To
    bill_x = pdf.l_margin + col_w + 8
    bill_w = col_w
    client = invoice["client"]
    client_name = f"{client['first_name']} {client['last_name']}".strip()

    bill_lines = [("name", client_name)]
    if client.get("business_name"):
        bill_lines.append(("business", client["business_name"]))
    for key in ("address1", "address2", "phone"):
        if client.get(key):
            bill_lines.append(("normal", client[key]))
    if client.get("email"):
        bill_lines.append(("normal", client["email"]))
    if client.get("cc_emails"):
        for cc in client["cc_emails"].split(","):
            cc = cc.strip()
            if cc:
                bill_lines.append(("normal", cc))

    box_h = 6 + 5.2 * len(bill_lines) + 4
    pdf.set_fill_color(*LIGHT_GRAY)
    pdf.rect(bill_x, start_y - 2, bill_w, box_h, style="F")

    pdf.set_xy(bill_x + 4, start_y + 1)
    pdf.set_font(FONT, "B", 9)
    pdf.set_text_color(*MID_GRAY)
    pdf.cell(bill_w - 8, 6, "BILL TO", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(*TEXT)
    for kind, line in bill_lines:
        pdf.set_x(bill_x + 4)
        weight = "B" if kind in ("name", "business") else ""
        pdf.set_font(FONT, weight, 9.5)
        pdf.cell(bill_w - 8, 5.2, line, new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(max(left_block_end, start_y - 2 + box_h) + 8)

    # ---------- LINE ITEMS TABLE ----------
    qty_w = 16
    price_w = 26
    amount_w = 28

    if show_codes:
        code_w = 24
        desc_w = page_w - code_w - qty_w - price_w - amount_w
    else:
        code_w = 0
        desc_w = page_w - qty_w - price_w - amount_w

    header_h = 8
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(FONT, "B", 9)
    pdf.set_x(pdf.l_margin)
    if show_codes:
        pdf.cell(code_w, header_h, "Code", fill=True, align="L")
    pdf.cell(desc_w, header_h, "Description", fill=True, align="L")
    pdf.cell(qty_w, header_h, "Qty", fill=True, align="R")
    pdf.cell(price_w, header_h, "Unit Price", fill=True, align="R")
    pdf.cell(amount_w, header_h, "Amount", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    subtotal = 0.0
    pdf.set_font(FONT, "", 9.5)
    pdf.set_text_color(*TEXT)

    for idx, item in enumerate(invoice["items"]):
        qty   = item.get("quantity", item.get("qty", 0))
        price = item.get("unit_price", item.get("price", 0))
        amount = qty * price
        subtotal += amount

        line_h = 5.5
        pad = 2.5

        wrapped_lines = pdf.multi_cell(desc_w - 2 * pad, line_h,
                                        item["description"], align="L",
                                        dry_run=True, output="LINES")
        row_h = max(header_h, line_h * len(wrapped_lines) + 2 * pad)
        fill = (idx % 2 == 1)

        x, y = pdf.l_margin, pdf.get_y()
        if fill:
            pdf.set_fill_color(*LIGHT_GRAY)
            pdf.rect(x, y, page_w, row_h, style="F")

        if show_codes:
            pdf.set_xy(x, y + pad)
            pdf.cell(code_w, line_h, item.get("code") or "", align="L")
            desc_x = x + code_w + pad
        else:
            desc_x = x + pad

        pdf.set_xy(desc_x, y + pad)
        pdf.multi_cell(desc_w - 2 * pad, line_h, item["description"], align="L")

        pdf.set_xy(x + code_w + desc_w, y + pad)
        pdf.cell(qty_w,    line_h, fmt_qty(qty),         align="R")
        pdf.cell(price_w,  line_h, fmt_currency(price),  align="R")
        pdf.cell(amount_w, line_h, fmt_currency(amount), align="R")

        pdf.set_xy(x, y + row_h)

    pdf.set_draw_color(*DARK)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())

    # ---------- TRACKING NUMBER ----------
    if invoice.get("tracking_number"):
        carrier = invoice.get("carrier") or "UPS"
        pdf.ln(3)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(FONT, "B", 9.5)
        pdf.set_text_color(*MID_GRAY)
        pdf.cell(35, 6, f"{carrier} Tracking #:")
        pdf.set_font(FONT, "", 9.5)
        pdf.set_text_color(*TEXT)
        pdf.cell(0, 6, invoice["tracking_number"], new_x="LMARGIN", new_y="NEXT")

    # ---------- TOTALS ----------
    pdf.ln(4)
    tax_rate   = invoice["tax_rate"]
    shipping   = invoice.get("shipping") or 0
    tax_amount = subtotal * tax_rate
    total      = subtotal + shipping + tax_amount
    amount_paid = invoice.get("amount_paid") or 0
    balance_due = max(0.0, total - amount_paid)

    totals_label_w = 40
    totals_val_w   = amount_w
    totals_x = pdf.l_margin + page_w - totals_label_w - totals_val_w

    def totals_row(label, value, bold=False, top_rule=False):
        pdf.set_x(totals_x)
        if top_rule:
            pdf.set_draw_color(*DARK)
            pdf.set_line_width(0.3)
            pdf.line(totals_x, pdf.get_y(),
                     totals_x + totals_label_w + totals_val_w, pdf.get_y())
            pdf.ln(1.5)
            pdf.set_x(totals_x)
        pdf.set_font(FONT, "B" if bold else "", 10)
        pdf.set_text_color(*(DARK if bold else MID_GRAY))
        pdf.cell(totals_label_w, 6.5, label, align="R")
        pdf.set_text_color(*TEXT)
        pdf.cell(totals_val_w, 6.5, value, align="R", new_x="LMARGIN", new_y="NEXT")

    tax_label_str = invoice.get("tax_label") or "HST"
    totals_row("Subtotal",  fmt_currency(subtotal))
    totals_row("Shipping",  fmt_currency(shipping))
    totals_row(f"{tax_label_str} ({tax_rate*100:.0f}%)", fmt_currency(tax_amount))
    totals_row("Total",     fmt_currency(total), top_rule=True)
    if amount_paid:
        totals_row("Amount paid", fmt_currency(amount_paid))
    totals_row("Total Due", fmt_currency(balance_due), bold=True, top_rule=True)

    # Status / payment method note
    status = invoice.get("status", "DUE")
    payment_method = invoice.get("payment_method")
    status_parts = []
    if status == "PAID":
        status_parts.append("PAID")
    elif status == "PARTIALLY_PAID":
        status_parts.append("PARTIALLY PAID")
    if payment_method:
        status_parts.append(f"via {payment_method}")
    if status_parts:
        pdf.set_x(totals_x)
        pdf.set_font(FONT, "I", 8.5)
        pdf.set_text_color(*MID_GRAY)
        pdf.cell(totals_label_w + totals_val_w, 5.5,
                 "  ".join(status_parts), align="R", new_x="LMARGIN", new_y="NEXT")

    # ---------- TERMS ----------
    pdf.ln(10)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "B", 10)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, "Terms & Conditions", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*MID_GRAY)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(page_w, 5,
        "1. Payment is due within 14 days of invoice date.\n"
        "2. All repaired electronics include a 2 year warranty on parts and labor.\n"
        "3. Items left unpaid or unclaimed will be considered abandoned after 90 days "
        "and may be disposed of or recycled without further notice.")

    pdf.output(str(output_path))
