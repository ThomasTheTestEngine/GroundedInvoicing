import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from pathlib import Path
import shutil
import sqlite3
import tempfile
import os

import data
import prefs
from db_setup import DB_PATH, init_db, DEFAULT_THEME

VIEW_PREFS_KEYS = [
    "clients_col_widths", "clients_col_order",
    "invoices_col_widths", "invoices_col_order",
]

THEME_LABELS = {
    "accent":     "Accent (blue rule, header)",
    "dark":       "Dark (table header, text)",
    "light_gray": "Light gray (row stripe, Bill To bg)",
    "mid_gray":   "Mid gray (secondary labels)",
    "text":       "Text (body copy)",
}

FONT_OPTIONS = [
    "Helvetica", "Times", "Courier",
]


class SettingsView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Scrollable canvas
        canvas = tk.Canvas(self, highlightthickness=0, bg="white")
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas, padding=24)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self._scroll_canvas = canvas
        self._scroll_inner  = inner

        ttk.Label(inner, text="Settings", font=("Helvetica", 16, "bold")).pack(
            anchor="w", pady=(0, 16))

        self._build_company(inner)
        self._build_theme(inner)
        self._build_stripe(inner)
        self._build_protonmail(inner)
        self._build_database(inner)
        self._build_view(inner)

    # ------------------------------------------------------------------
    # Company info
    # ------------------------------------------------------------------

    def _build_company(self, parent):
        f = ttk.LabelFrame(parent, text="Company info", padding=14)
        f.pack(fill="x", pady=(0, 12))

        self._co_fields = {}
        field_defs = [
            ("name",     "Company name"),
            ("address1", "Address line 1"),
            ("address2", "Address line 2"),
            ("phone",    "Phone"),
            ("email",    "Email"),
            ("tax_id",   "Tax ID"),
        ]
        for i, (key, label) in enumerate(field_defs):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w",
                                           padx=(0, 10), pady=3)
            e = ttk.Entry(f, width=40)
            e.grid(row=i, column=1, sticky="w", pady=3)
            self._co_fields[key] = e

        ttk.Button(f, text="Save company info",
                   command=self._save_company).grid(
            row=len(field_defs), column=0, columnspan=2,
            sticky="w", pady=(10, 0))

    def _load_company(self):
        co = data.get_company()
        for key, entry in self._co_fields.items():
            entry.delete(0, tk.END)
            entry.insert(0, co.get(key, ""))

    def _save_company(self):
        data.update_company(
            name=self._co_fields["name"].get().strip(),
            address1=self._co_fields["address1"].get().strip(),
            address2=self._co_fields["address2"].get().strip(),
            phone=self._co_fields["phone"].get().strip(),
            email=self._co_fields["email"].get().strip(),
            tax_id=self._co_fields["tax_id"].get().strip(),
        )
        messagebox.showinfo("Saved", "Company info updated.")

    # ------------------------------------------------------------------
    # Theme / font
    # ------------------------------------------------------------------

    def _build_theme(self, parent):
        f = ttk.LabelFrame(parent, text="Invoice theme", padding=14)
        f.pack(fill="x", pady=(0, 12))

        self._color_vars = {}
        self._color_btns = {}

        for i, (key, label) in enumerate(THEME_LABELS.items()):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w",
                                           padx=(0, 10), pady=4)
            var = tk.StringVar()
            self._color_vars[key] = var
            swatch = tk.Label(f, width=4, relief="solid", cursor="hand2")
            swatch.grid(row=i, column=1, padx=(0, 6), pady=4)
            self._color_btns[key] = swatch
            hex_lbl = ttk.Label(f, textvariable=var, width=10)
            hex_lbl.grid(row=i, column=2, padx=(0, 6), pady=4)
            ttk.Button(f, text="Choose…",
                       command=lambda k=key: self._pick_color(k)).grid(
                row=i, column=3, pady=4)

        # Font row
        row = len(THEME_LABELS)
        ttk.Label(f, text="Font").grid(row=row, column=0, sticky="w",
                                        padx=(0, 10), pady=4)
        self._font_var = tk.StringVar(value="Helvetica")
        font_combo = ttk.Combobox(f, textvariable=self._font_var,
                                   values=FONT_OPTIONS, state="readonly", width=18)
        font_combo.grid(row=row, column=1, columnspan=2, sticky="w", pady=4)

        btn_row = row + 1
        ttk.Button(f, text="Save theme", command=self._save_theme).grid(
            row=btn_row, column=0, sticky="w", pady=(10, 0))
        ttk.Button(f, text="Preview PDF", command=self._preview_theme).grid(
            row=btn_row, column=1, columnspan=3, sticky="w",
            padx=(6, 0), pady=(10, 0))

    def _tuple_to_hex(self, t):
        return "#{:02x}{:02x}{:02x}".format(*t)

    def _hex_to_tuple(self, h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _load_theme(self):
        theme = data.get_theme()
        for key in THEME_LABELS:
            rgb = theme[key]
            hex_val = self._tuple_to_hex(rgb)
            self._color_vars[key].set(hex_val)
            self._color_btns[key].config(background=hex_val)
        self._font_var.set(theme.get("font", "Helvetica"))

    def _pick_color(self, key):
        current = self._color_vars[key].get() or "#000000"
        result = colorchooser.askcolor(color=current, title=f"Choose colour — {key}")
        if result and result[1]:
            hex_val = result[1]
            self._color_vars[key].set(hex_val)
            self._color_btns[key].config(background=hex_val)

    def _save_theme(self):
        theme = {}
        for key in THEME_LABELS:
            hex_val = self._color_vars[key].get()
            try:
                theme[key] = self._hex_to_tuple(hex_val)
            except Exception:
                messagebox.showerror("Invalid colour", f"Bad colour value for {key}")
                return
        theme["font"] = self._font_var.get()
        data.set_theme(theme)
        messagebox.showinfo("Saved", "Theme saved.")

    def _preview_theme(self):
        from invoice import build_invoice_pdf, PREVIEW_INVOICE
        import data as _data

        # Build theme from current (unsaved) UI state
        theme = {}
        for key in THEME_LABELS:
            hex_val = self._color_vars[key].get()
            try:
                theme[key] = self._hex_to_tuple(hex_val)
            except Exception:
                theme = _data.get_theme()
                break
        theme["font"] = self._font_var.get()

        company = _data.get_company()

        # Use first real invoice if available, otherwise lorem ipsum
        invoices = _data.list_invoices()
        if invoices:
            invoice = _data.get_invoice(invoices[0]["id"])
        else:
            invoice = PREVIEW_INVOICE

        tmp = Path(tempfile.mktemp(suffix=".pdf"))
        build_invoice_pdf(invoice, tmp, theme=theme, company=company)

        # Open with system viewer
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.run(["open", str(tmp)])
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", str(tmp)])
        else:
            os.startfile(str(tmp))

    # ------------------------------------------------------------------
    # Stripe
    # ------------------------------------------------------------------

    def _build_stripe(self, parent):
        f = ttk.LabelFrame(parent, text="Stripe payments", padding=14)
        f.pack(fill="x", pady=(0, 12))

        ttk.Label(f, text="Secret key (sk_live_... or sk_test_...)").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=3)
        self._stripe_key_entry = ttk.Entry(f, width=52, show="*")
        self._stripe_key_entry.grid(row=0, column=1, sticky="w", pady=3)

        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            self._stripe_key_entry.config(show="" if show_var.get() else "*")
        ttk.Checkbutton(f, text="Show", variable=show_var,
                        command=toggle_show).grid(row=0, column=2, padx=(6, 0))

        ttk.Label(f,
                  text="Key is stored locally in your database only.\n"
                       "Never shared or logged.",
                  foreground="gray").grid(row=1, column=0, columnspan=3,
                                          sticky="w", pady=(2, 6))

        ttk.Button(f, text="Save Stripe key",
                   command=self._save_stripe_key).grid(
            row=2, column=0, sticky="w", pady=(4, 0))

    def _load_stripe(self):
        key = data.get_stripe_key() or ""
        self._stripe_key_entry.delete(0, tk.END)
        self._stripe_key_entry.insert(0, key)

    def _save_stripe_key(self):
        key = self._stripe_key_entry.get().strip()
        if key and not (key.startswith("sk_live_") or key.startswith("sk_test_")):
            messagebox.showerror("Invalid key",
                                  "Stripe secret keys start with sk_live_ or sk_test_")
            return
        data.set_stripe_key(key)
        messagebox.showinfo("Saved", "Stripe key saved.")

    # ------------------------------------------------------------------
    # ProtonMail Bridge
    # ------------------------------------------------------------------

    def _build_protonmail(self, parent):
        f = ttk.LabelFrame(parent, text="ProtonMail Bridge (email sending)", padding=14)
        f.pack(fill="x", pady=(0, 12))

        ttk.Label(f, text="Bridge password").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=3)
        self._bridge_pass_entry = ttk.Entry(f, width=32, show="*")
        self._bridge_pass_entry.grid(row=0, column=1, sticky="w", pady=3)

        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            self._bridge_pass_entry.config(show="" if show_var.get() else "*")
        ttk.Checkbutton(f, text="Show", variable=show_var,
                        command=toggle_show).grid(row=0, column=2, padx=(6, 0))

        ttk.Label(f,
                  text="SMTP: 127.0.0.1:1025  ·  STARTTLS  ·  thomas@groundedrepairs.com\n"
                       "Password stored locally only.",
                  foreground="gray").grid(row=1, column=0, columnspan=3,
                                          sticky="w", pady=(2, 6))

        ttk.Button(f, text="Save Bridge password",
                   command=self._save_bridge_password).grid(
            row=2, column=0, sticky="w", pady=(4, 0))

        ttk.Button(f, text="Send test email",
                   command=self._send_test_email).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

    def _load_protonmail(self):
        pw = data.get_setting("bridge_password") or ""
        self._bridge_pass_entry.delete(0, tk.END)
        self._bridge_pass_entry.insert(0, pw)

    def _save_bridge_password(self):
        pw = self._bridge_pass_entry.get().strip()
        data.set_setting("bridge_password", pw)
        messagebox.showinfo("Saved", "Bridge password saved.")

    def _send_test_email(self):
        from views.email_sender import send_invoice_email
        pw = data.get_setting("bridge_password") or ""
        if not pw:
            messagebox.showerror("Not configured",
                                  "Save your Bridge password first.")
            return
        try:
            send_invoice_email(
                to_address="thomas@groundedrepairs.com",
                cc_addresses=[],
                subject="Grounded Invoicing — test email",
                body="This is a test email from Grounded Invoicing.\n\nIf you received this, Bridge is working correctly.",
                pdf_path=None,
                bridge_password=pw,
            )
            messagebox.showinfo("Sent", "Test email sent to thomas@groundedrepairs.com")
        except Exception as e:
            messagebox.showerror("Failed", str(e))

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _build_database(self, parent):
        f = ttk.LabelFrame(parent, text="Database", padding=14)
        f.pack(fill="x", pady=(0, 12))

        ttk.Label(f, text="Backup a copy of the database to a chosen location.").pack(anchor="w")
        ttk.Button(f, text="Backup database…",
                   command=self._backup_db).pack(anchor="w", pady=(6, 10))

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(0, 10))

        ttk.Label(f, text="Import data from an old invoices.db file.\n"
                          "Existing data is kept; imported data is merged in.").pack(anchor="w")
        ttk.Button(f, text="Import old database…",
                   command=self._import_db).pack(anchor="w", pady=(6, 0))

    def _backup_db(self):
        dest = filedialog.asksaveasfilename(
            initialdir=str(Path.home() / "Desktop"),
            initialfile=DB_PATH.name,
            defaultextension=".db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if not dest:
            return
        shutil.copy2(DB_PATH, dest)
        messagebox.showinfo("Backup complete", f"Database backed up to:\n{dest}")

    def _import_db(self):
        src = filedialog.askopenfilename(
            title="Select old invoices.db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if not src:
            return

        try:
            self._do_import(src)
            messagebox.showinfo("Import complete",
                                "Data imported successfully. Restart the app to see all changes.")
        except Exception as e:
            messagebox.showerror("Import failed", str(e))

    def _do_import(self, src_path):
        """Copy clients and invoices from an old DB into the current one."""
        src = sqlite3.connect(src_path)
        src.row_factory = sqlite3.Row
        dst = sqlite3.connect(DB_PATH)
        dst.execute("PRAGMA foreign_keys = ON")

        # Run migrations on the source to normalise columns
        from db_setup import MIGRATIONS
        for m in MIGRATIONS:
            try:
                src.execute(m)
            except Exception:
                pass

        # Import clients (skip duplicates by email, or insert all with new IDs)
        client_id_map = {}
        for c in src.execute("SELECT * FROM clients").fetchall():
            c = dict(c)
            cur = dst.execute(
                """INSERT OR IGNORE INTO clients
                   (first_name, last_name, business_name, phone, email,
                    address1, address2, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (c.get("first_name"), c.get("last_name"), c.get("business_name"),
                 c.get("phone"), c.get("email"), c.get("address1"),
                 c.get("address2"), c.get("notes"))
            )
            if cur.lastrowid:
                client_id_map[c["id"]] = cur.lastrowid
            else:
                # Already exists — find by email
                row = dst.execute(
                    "SELECT id FROM clients WHERE email=?", (c.get("email"),)
                ).fetchone()
                if row:
                    client_id_map[c["id"]] = row[0]

        # Import invoices
        for inv in src.execute("SELECT * FROM invoices").fetchall():
            inv = dict(inv)
            old_client_id = inv.get("client_id")
            new_client_id = client_id_map.get(old_client_id)
            if not new_client_id:
                continue  # skip orphaned invoices

            # Remove existing invoice with same number so we can overwrite it
            existing = dst.execute(
                "SELECT id FROM invoices WHERE invoice_number=?",
                (inv.get("invoice_number"),)
            ).fetchone()
            if existing:
                dst.execute("DELETE FROM invoice_items WHERE invoice_id=?",
                            (existing[0],))
                dst.execute("DELETE FROM invoices WHERE id=?", (existing[0],))

            cur = dst.execute(
                """INSERT INTO invoices
                   (invoice_number, client_id, invoice_date, due_date,
                    shipping, tax_rate, tracking_number, status, notes,
                    carrier, tax_label, amount_paid, payment_method, shipped, sent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (inv.get("invoice_number"), new_client_id,
                 inv.get("invoice_date"), inv.get("due_date"),
                 inv.get("shipping", 0), inv.get("tax_rate", 0.13),
                 inv.get("tracking_number"), inv.get("status", "DUE"),
                 inv.get("notes"), inv.get("carrier", "UPS"),
                 inv.get("tax_label", "HST"), inv.get("amount_paid", 0),
                 inv.get("payment_method"), inv.get("shipped", 0),
                 inv.get("sent", 0))
            )
            inv_id = cur.lastrowid

            # Import line items
            for item in src.execute(
                "SELECT * FROM invoice_items WHERE invoice_id=?",
                (inv["id"],)
            ).fetchall():
                item = dict(item)
                dst.execute(
                    """INSERT INTO invoice_items
                       (invoice_id, code, description, quantity, unit_price, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (inv_id, item.get("code"), item.get("description"),
                     item.get("quantity"), item.get("unit_price"),
                     item.get("sort_order", 0))
                )

            # Update invoice counter
            num_str = inv.get("invoice_number", "GR00000")
            try:
                num = int(num_str.lstrip("GR").lstrip("0") or "0")
                row = dst.execute(
                    "SELECT last_number FROM invoice_counter WHERE id=1"
                ).fetchone()
                if row and num > row[0]:
                    dst.execute(
                        "UPDATE invoice_counter SET last_number=? WHERE id=1", (num,)
                    )
            except Exception:
                pass

        dst.commit()
        src.close()
        dst.close()

    # ------------------------------------------------------------------
    # View / window resets
    # ------------------------------------------------------------------

    def _build_view(self, parent):
        f = ttk.LabelFrame(parent, text="View & window", padding=14)
        f.pack(fill="x", pady=(0, 12))

        ttk.Label(f, text="Reset column widths, order, and window size back to defaults.").pack(
            anchor="w")
        ttk.Button(f, text="Reset default view settings",
                   command=self._reset_view_settings).pack(anchor="w", pady=(8, 0))

    def _reset_view_settings(self):
        keys_to_clear = VIEW_PREFS_KEYS + ["window_geometry"]
        all_prefs = prefs.load_prefs()
        for key in keys_to_clear:
            all_prefs.pop(key, None)
        prefs.save_prefs(all_prefs)
        messagebox.showinfo(
            "Reset",
            "View settings reset to defaults.\n"
            "Changes take effect next time you open those tabs or relaunch the app."
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_mousewheel(self, event):
        canvas = getattr(self, "_scroll_canvas", None)
        if canvas is None:
            return
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(int(-1 * event.delta), "units")

    def on_show(self, **kwargs):
        self._load_company()
        self._load_theme()
        self._load_stripe()
        self._load_protonmail()
