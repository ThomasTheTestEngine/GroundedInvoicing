# Grounded Invoicing

A free, self-hosted desktop invoicing app for small businesses. No subscriptions, no cloud, no nonsense — your data lives on your machine.

Built with Python + tkinter + SQLite. Generates professional PDF invoices, integrates with Stripe for payment links, and sends emails via ProtonMail Bridge.

## Features

- Client management with notes and CC email addresses
- Invoice creation with dynamic line items, shipping, tax, and carrier tracking
- Status tracking: DUE / OVERDUE / PARTIALLY PAID / PAID
- PDF invoice generation (fpdf2)
- Stripe Payment Link integration (no expiry, auto-deactivates on payment)
- Email sending via ProtonMail Bridge (invoice + paid confirmation)
- Sortable, reorderable column lists for clients and invoices
- Customizable invoice theme (colours + font)
- Settings: company info, Stripe key, ProtonMail Bridge password, DB backup/import
- Dark/light mode toggle (sv-ttk)
- Window size and column layout persistence

## Requirements

- Python 3.13 from [python.org](https://python.org) (macOS — Homebrew Python 3.12 has a broken Tk 9.0 that breaks trackpad scrolling)
- `fpdf2` and `sv-ttk` (`pip install fpdf2 sv-ttk`)

## Setup

```bash
pip install fpdf2 sv-ttk
python3 main.py
```

On first run, `grounded_invoicing.db` is created automatically.

## Building a macOS .app

```bash
pip install pyinstaller
pyinstaller --onedir --windowed \
  --add-data "logo.png:." \
  --collect-all sv_ttk \
  --icon "YourIcon.icns" \
  --name "Grounded Invoicing" \
  main.py
```

## Configuration

All settings are in-app under the ⚙ Settings button:
- **Company info** — your business name, address, tax ID
- **Invoice theme** — colours and font for PDF output
- **Stripe** — paste your `sk_live_...` secret key
- **ProtonMail Bridge** — Bridge SMTP password for sending emails
- **Database** — backup, import from old DB, reset view settings

## Notes

- Your Stripe secret key and Bridge password are stored locally in `grounded_invoicing.db` only
- Invoice numbers auto-increment from GR00001
- The app is designed around a single company per install — edit company info in Settings
- `logo.png` is the invoice logo; replace it with your own

## License

MIT
