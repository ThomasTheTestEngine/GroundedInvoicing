"""
Email sending via ProtonMail Bridge.

Bridge runs locally at 127.0.0.1:1025 with STARTTLS.
Username is always thomas@groundedrepairs.com.
Password is the Bridge-specific password stored in app_settings.
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
FROM_ADDRESS = "thomas@groundedrepairs.com"
FROM_NAME = "Grounded Repairs"


def send_invoice_email(to_address, cc_addresses, subject, body,
                       pdf_path=None, bridge_password=None):
    """
    Send an email via ProtonMail Bridge.

    to_address     : primary recipient email string
    cc_addresses   : list of CC email strings (can be empty)
    subject        : email subject line
    body           : plain text body
    pdf_path       : path to PDF attachment (str or Path), or None
    bridge_password: Bridge SMTP password
    """
    if not bridge_password:
        raise ValueError("Bridge password not configured.")

    msg = MIMEMultipart()
    msg["From"]    = f"{FROM_NAME} <{FROM_ADDRESS}>"
    msg["To"]      = to_address
    msg["Subject"] = subject
    if cc_addresses:
        msg["Cc"] = ", ".join(cc_addresses)

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=Path(pdf_path).name,
            )
            msg.attach(part)

    all_recipients = [to_address] + list(cc_addresses)

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(FROM_ADDRESS, bridge_password)
        smtp.sendmail(FROM_ADDRESS, all_recipients, msg.as_string())


def build_invoice_email_body(invoice, payment_link=None):
    """
    Build the canned email body for an invoice.

    invoice      : dict from data.get_invoice()
    payment_link : Stripe payment link URL string or None
    """
    client     = invoice["client"]
    first_name = client.get("first_name", "")
    inv_num    = invoice["invoice_number"]
    due_date   = invoice.get("due_date", "")
    balance    = invoice.get("balance_due", 0)

    # Format due date nicely
    try:
        from datetime import date
        due_fmt = date.fromisoformat(due_date).strftime("%B %d, %Y")
    except Exception:
        due_fmt = due_date

    lines = [
        f"Hello {first_name},",
        "",
        f"Please find your invoice {inv_num} attached.",
        "",
        f"Total due:  ${balance:,.2f}",
        f"Due date:   {due_fmt}",
    ]

    if payment_link:
        lines += [
            "",
            "You can pay securely online here:",
            payment_link,
        ]

    if balance <= 0:
        lines = [
            f"Hello {first_name},",
            "",
            f"Please find invoice {inv_num} attached.",
            "",
            "This invoice has been paid in full. Thank you!",
        ]

    lines += [
        "",
        "If you have any questions, please don't hesitate to reach out.",
        "",
        "Thank you,",
        "Grounded Repairs",
        "(705) 761 2938",
        "thomas@groundedrepairs.com",
    ]

    return "\n".join(lines)
