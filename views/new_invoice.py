import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import date, timedelta

import data
from invoice import build_invoice_pdf


class LineItemRow:
    """A single editable line item row within the items table."""

    def __init__(self, parent, on_change, on_remove):
        self.on_change = on_change
        self.on_remove = on_remove

        self.code_entry = ttk.Entry(parent, width=10)
        self.desc_entry = ttk.Entry(parent, width=40)
        self.qty_entry = ttk.Entry(parent, width=6, justify="right")
        self.price_entry = ttk.Entry(parent, width=10, justify="right")
        self.amount_label = ttk.Label(parent, width=10, anchor="e")
        self.remove_btn = ttk.Button(parent, text="x", width=2,
                                      command=lambda: self.on_remove(self))

        self.qty_entry.insert(0, "1")
        self.qty_entry.bind("<KeyRelease>", lambda e: self.on_change())
        self.price_entry.bind("<KeyRelease>", lambda e: self.on_change())

        self.widgets = [
            self.code_entry, self.desc_entry, self.qty_entry,
            self.price_entry, self.amount_label, self.remove_btn,
        ]

    def grid(self, row):
        for col, widget in enumerate(self.widgets):
            widget.grid(row=row, column=col, padx=2, pady=2, sticky="ew")

    def destroy(self):
        for widget in self.widgets:
            widget.destroy()

    def get_values(self):
        try:
            qty = float(self.qty_entry.get() or 0)
        except ValueError:
            qty = 0
        try:
            price = float(self.price_entry.get() or 0)
        except ValueError:
            price = 0
        return {
            "code": self.code_entry.get().strip() or None,
            "description": self.desc_entry.get().strip(),
            "quantity": qty,
            "unit_price": price,
        }

    def set_values(self, item):
        self.code_entry.delete(0, tk.END)
        self.code_entry.insert(0, item.get("code") or "")

        self.desc_entry.delete(0, tk.END)
        self.desc_entry.insert(0, item.get("description") or "")

        self.qty_entry.delete(0, tk.END)
        self.qty_entry.insert(0, f"{item.get('quantity', 0):g}")

        self.price_entry.delete(0, tk.END)
        self.price_entry.insert(0, f"{item.get('unit_price', 0):.2f}")

    def update_amount(self):
        values = self.get_values()
        amount = values["quantity"] * values["unit_price"]
        self.amount_label.config(text=f"${amount:,.2f}")
        return amount

    def is_blank(self):
        v = self.get_values()
        return not v["description"] and v["quantity"] == 0 and v["unit_price"] == 0


class NewInvoiceView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=20)
        self.app = app
        self.editing_invoice_id = None  # None when creating a new invoice
        self.mode = "new"  # "new", "view", or "edit"
        self.all_clients = []  # list of (label, client_dict) for searching

        self._build_ui()
        self.bind_all("<Button-1>", self._maybe_hide_client_listbox, add="+")

    def _reset_scroll(self):
        # Force all pending layout to settle before measuring
        self._inner.update_idletasks()
        canvas_h = self._canvas.winfo_height()
        content_h = self._inner.winfo_reqheight()
        new_h = max(canvas_h, content_h)
        self._canvas.itemconfig(self._canvas_window, height=new_h)
        self._canvas.configure(scrollregion=(0, 0, self._canvas.winfo_width(), new_h))
        self._canvas.yview_moveto(0)

    def _on_inner_configure(self, event):
        # Keep canvas window at least as tall as the canvas so bg never shows
        canvas_h = self._canvas.winfo_height()
        new_h = max(canvas_h, event.height)
        self._canvas.itemconfig(self._canvas_window, height=new_h)

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        self._reset_scroll()

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * event.delta), "units")

    def _maybe_hide_client_listbox(self, event):
        if not self._client_listbox_visible:
            return
        widget = event.widget
        if widget is self.client_search_entry or widget is self.client_listbox:
            return
        self._hide_client_listbox()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Scrollable container — canvas + scrollbar, inner frame holds content
        self._canvas = tk.Canvas(self, highlightthickness=0, bg="white")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = ttk.Frame(self._canvas, padding=20)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # All subsequent widgets use self._inner as parent instead of self
        f = self._inner
        header_frame = ttk.Frame(f)
        header_frame.pack(fill="x", pady=(0, 10))

        self.title_label = ttk.Label(header_frame, text="New invoice",
                                       font=("Helvetica", 16, "bold"))
        self.title_label.pack(side="left")

        self.invoice_number_label = ttk.Label(header_frame, text="", foreground="gray")
        self.invoice_number_label.pack(side="right")

        # --- Client / dates row ---
        top_row = ttk.Frame(f)
        top_row.pack(fill="x", pady=(0, 0))

        ttk.Label(top_row, text="Client").grid(row=0, column=0, sticky="w", padx=(0, 8))

        client_search_frame = ttk.Frame(top_row)
        client_search_frame.grid(row=1, column=0, sticky="nw", padx=(0, 20))

        self.client_search_entry = ttk.Entry(client_search_frame, width=35)
        self.client_search_entry.pack(anchor="w")
        self.client_search_entry.bind("<KeyRelease>", self._on_client_search_changed)
        self.client_search_entry.bind("<FocusIn>", self._on_client_search_focus)
        self.client_search_entry.bind("<Down>", self._focus_client_listbox)
        self.client_search_entry.bind("<Escape>", lambda e: self._hide_client_listbox())

        self.client_listbox = tk.Listbox(client_search_frame, height=5, width=40,
                                          exportselection=False)
        self.client_listbox.bind("<<ListboxSelect>>", self._on_client_listbox_select)
        self.client_listbox.bind("<Return>", self._on_client_listbox_select)
        self.client_listbox.bind("<Escape>", lambda e: self._hide_client_listbox())
        # Not packed initially - shown only while searching

        self._client_listbox_visible = False
        self.selected_client = None  # the currently chosen client dict

        ttk.Label(top_row, text="Invoice date").grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.date_entry = ttk.Entry(top_row, width=14)
        self.date_entry.grid(row=1, column=1, sticky="nw", padx=(0, 20))

        ttk.Label(top_row, text="Due date").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.due_date_entry = ttk.Entry(top_row, width=14)
        self.due_date_entry.grid(row=1, column=2, sticky="nw")

        # --- Client info + client notes side by side ---
        info_notes_row = ttk.Frame(f)
        info_notes_row.pack(fill="x", pady=(8, 10))

        self.client_info_label = ttk.Label(info_notes_row, text="", foreground="gray",
                                            background="#f0f0f0", padding=8)
        self.client_info_label.pack(side="left", fill="x", expand=True)

        client_notes_outer = ttk.Frame(info_notes_row)
        client_notes_outer.pack(side="right", padx=(10, 0), fill="y")
        ttk.Label(client_notes_outer, text="Client notes", foreground="gray").pack(anchor="w")
        client_notes_border = ttk.Frame(client_notes_outer, borderwidth=1, relief="solid")
        client_notes_border.pack(fill="both", expand=True, pady=(2, 0))
        self.client_notes_display = tk.Text(client_notes_border, width=28, height=4,
                                             wrap="word", font=("Helvetica", 9),
                                             relief="flat", borderwidth=0, state="disabled")
        self.client_notes_display.pack(fill="both", expand=True)

        # --- Line items ---
        ttk.Label(f, text="Line items").pack(anchor="w")

        items_outer = ttk.Frame(f)
        items_outer.pack(fill="x", pady=(4, 0))

        header_row = ttk.Frame(items_outer)
        header_row.pack(fill="x")
        headers = ["Code", "Description", "Qty", "Unit price", "Amount", ""]
        widths = [10, 40, 6, 10, 10, 2]
        for col, (text, w) in enumerate(zip(headers, widths)):
            ttk.Label(header_row, text=text, foreground="gray", width=w,
                      anchor="w" if col < 2 else "e").grid(row=0, column=col, padx=2)

        self.items_frame = ttk.Frame(items_outer)
        self.items_frame.pack(fill="x")

        self.line_items = []

        ttk.Button(items_outer, text="+ Add line item", command=self.add_line_item).pack(
            anchor="w", pady=(4, 0)
        )

        # --- Tax / Status / Payment row ---
        tsr_frame = ttk.Frame(f)
        tsr_frame.pack(fill="x", pady=(15, 0))

        ttk.Label(tsr_frame, text="Tax rate (%)").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(tsr_frame, text="Tax label").grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(tsr_frame, text="Status").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Label(tsr_frame, text="Payment method").grid(row=0, column=3, sticky="w")

        self.tax_entry = ttk.Entry(tsr_frame, width=6, justify="right")
        self.tax_entry.grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.tax_entry.insert(0, "13")
        self.tax_entry.bind("<KeyRelease>", lambda e: self.update_totals())

        self.tax_label_entry = ttk.Entry(tsr_frame, width=7)
        self.tax_label_entry.grid(row=1, column=1, sticky="w", padx=(0, 8))
        self.tax_label_entry.insert(0, "HST")
        self.tax_label_entry.bind("<KeyRelease>", lambda e: self.update_totals())

        self.status_combo = ttk.Combobox(
            tsr_frame, width=14, state="readonly",
            values=["DUE", "PARTIALLY_PAID", "PAID"]
        )
        self.status_combo.grid(row=1, column=2, sticky="w", padx=(0, 8))
        self.status_combo.set("DUE")
        self.status_combo.bind("<<ComboboxSelected>>", self._on_status_changed)

        PAYMENT_METHODS = ["E-Transfer", "Credit Card", "ACH", "Cheque", "Cash", "Custom"]
        self.payment_method_combo = ttk.Combobox(
            tsr_frame, width=13, state="readonly", values=PAYMENT_METHODS
        )
        self.payment_method_combo.grid(row=1, column=3, sticky="w")
        self.payment_method_combo.bind("<<ComboboxSelected>>", self._on_payment_method_changed)

        self.custom_payment_entry = ttk.Entry(tsr_frame, width=13)

        # Partial payment amount — shown only when PARTIALLY_PAID
        self.partial_paid_frame = ttk.Frame(tsr_frame)
        self.partial_paid_frame.grid(row=2, column=2, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(self.partial_paid_frame, text="Amount paid:").pack(side="left", padx=(0, 6))
        self.amount_paid_entry = ttk.Entry(self.partial_paid_frame, width=10, justify="right")
        self.amount_paid_entry.pack(side="left")
        self.amount_paid_entry.bind("<KeyRelease>", lambda e: self.update_totals())
        self.partial_paid_frame.grid_remove()

        # --- Shipping / Carrier / Tracking row ---
        sct_frame = ttk.Frame(f)
        sct_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(sct_frame, text="Shipping").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(sct_frame, text="Carrier").grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(sct_frame, text="Tracking #").grid(row=0, column=2, sticky="w", padx=(0, 8))

        self.shipping_entry = ttk.Entry(sct_frame, width=9, justify="right")
        self.shipping_entry.grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.shipping_entry.bind("<KeyRelease>", lambda e: self.update_totals())

        CARRIERS = ["UPS", "Purolator", "Canada Post", "Canpar", "Custom"]
        self.carrier_combo = ttk.Combobox(sct_frame, width=11, state="readonly", values=CARRIERS)
        self.carrier_combo.grid(row=1, column=1, sticky="w", padx=(0, 8))
        self.carrier_combo.set("UPS")
        self.carrier_combo.bind("<<ComboboxSelected>>", self._on_carrier_changed)

        self.tracking_entry = ttk.Entry(sct_frame, width=20)
        self.tracking_entry.grid(row=1, column=2, sticky="w", padx=(0, 8))

        self.custom_carrier_entry = ttk.Entry(sct_frame, width=12)

        self.shipped_var = tk.BooleanVar(value=False)
        self.shipped_check = ttk.Checkbutton(sct_frame, text="Shipped",
                                              variable=self.shipped_var)
        self.shipped_check.grid(row=1, column=4, sticky="w", padx=(4, 0))

        self.sent_var = tk.BooleanVar(value=False)
        self.sent_check = ttk.Checkbutton(sct_frame, text="Sent",
                                           variable=self.sent_var)
        self.sent_check.grid(row=1, column=5, sticky="w", padx=(12, 0))

        # --- Totals ---
        bottom_row = ttk.Frame(f)
        bottom_row.pack(fill="x", pady=(10, 0))
        left_col = ttk.Frame(bottom_row)
        left_col.pack(side="left")

        # Totals box, right-aligned
        totals_frame = ttk.Frame(bottom_row)
        totals_frame.pack(side="right", anchor="n")

        self.subtotal_label = self._totals_row(totals_frame, 0, "Subtotal")
        self.shipping_total_label = self._totals_row(totals_frame, 1, "Shipping")
        self._tax_name_label, self.tax_total_label = self._totals_row_pair(totals_frame, 2, "HST")
        ttk.Separator(totals_frame, orient="horizontal").grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=4
        )
        self.total_gross_label = self._totals_row(totals_frame, 4, "Total")
        self.amount_paid_display = self._totals_row(totals_frame, 5, "Amount paid")
        ttk.Separator(totals_frame, orient="horizontal").grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=4
        )
        self.total_label = self._totals_row(totals_frame, 7, "Total due", bold=True)

        # --- Notes ---
        notes_frame = ttk.Frame(f)
        notes_frame.pack(fill="x", pady=(15, 0))
        ttk.Label(notes_frame, text="Notes (internal — not printed on invoice)").pack(anchor="w")
        # Wrap Text in a ttk.Frame so sv_ttk theme gives it a visible border
        notes_border = ttk.Frame(notes_frame, borderwidth=1, relief="solid")
        notes_border.pack(fill="x", pady=(4, 0))
        self.notes_text = tk.Text(notes_border, height=6, width=0, wrap="word",
                                   font=("Helvetica", 10), relief="flat", borderwidth=0)
        self.notes_text.pack(fill="x")

        # --- Action buttons ---
        self.action_row = ttk.Frame(f)
        self.action_row.pack(fill="x", pady=(20, 0))
        action_row = self.action_row

        # Left side: delete (only visible in edit mode for existing invoices)
        self.delete_btn = ttk.Button(action_row, text="Delete", command=self.delete_invoice)

        # Right side: context-dependent buttons
        self.right_frame = ttk.Frame(action_row)
        self.right_frame.pack(side="right")
        right_frame = self.right_frame

        self.cancel_btn = ttk.Button(right_frame, text="Cancel", command=self.cancel_edit)

        self.save_btn = ttk.Button(right_frame, text="Save", command=self.save)

        self.export_btn = ttk.Button(right_frame, text="Export to PDF",
                                       command=self.save_and_export)

        self.edit_btn = ttk.Button(right_frame, text="Edit", command=self.enable_editing)

        self.client_details_btn = ttk.Button(action_row, text="Client details",
                                              command=self._go_to_client)

        self.new_invoice_for_client_btn = ttk.Button(
            action_row, text="New invoice",
            command=self._new_invoice_for_same_client)

        self.invoice_sent_btn = ttk.Button(
            action_row, text="Copy payment link",
            command=self._copy_payment_link)

        self.send_invoice_btn = ttk.Button(
            action_row, text="Send invoice",
            command=self._confirm_send_invoice)

        self.mark_paid_send_btn = ttk.Button(
            action_row, text="Mark as paid + send",
            command=self._start_mark_paid_send)

        self.confirm_paid_btn = ttk.Button(
            action_row, text="✓ Confirm & send",
            command=self._confirm_mark_paid_send)

        # Status bar — persists until navigation away
        self.status_bar = ttk.Label(action_row, text="", foreground="green")

        # Default layout: new-invoice mode
        self.export_btn.pack(side="right")
        self.save_btn.pack(side="right", padx=(8, 0))

    def _totals_row(self, parent, row, label_text, bold=False):
        font = ("Helvetica", 11, "bold") if bold else ("Helvetica", 10)
        ttk.Label(parent, text=label_text, foreground="gray" if not bold else "black",
                  font=font).grid(row=row, column=0, sticky="e", padx=(0, 12))
        value_label = ttk.Label(parent, text="$0.00", width=10, anchor="e", font=font)
        value_label.grid(row=row, column=1, sticky="e")
        return value_label

    def _totals_row_pair(self, parent, row, label_text):
        """Like _totals_row but returns both the label widget and the value widget."""
        font = ("Helvetica", 10)
        name_lbl = ttk.Label(parent, text=label_text, foreground="gray", font=font)
        name_lbl.grid(row=row, column=0, sticky="e", padx=(0, 12))
        value_lbl = ttk.Label(parent, text="$0.00", width=10, anchor="e", font=font)
        value_lbl.grid(row=row, column=1, sticky="e")
        return name_lbl, value_lbl

    # ------------------------------------------------------------------
    # Line items management
    # ------------------------------------------------------------------

    def add_line_item(self, item_data=None):
        row = LineItemRow(self.items_frame, on_change=self.update_totals,
                          on_remove=self.remove_line_item)
        if item_data:
            row.set_values(item_data)
        self.line_items.append(row)
        self._regrid_line_items()
        self.update_totals()
        return row

    def remove_line_item(self, row):
        row.destroy()
        self.line_items.remove(row)
        self._regrid_line_items()
        self.update_totals()

    def _regrid_line_items(self):
        for i, row in enumerate(self.line_items):
            row.grid(i)

    def update_totals(self):
        subtotal = sum(row.update_amount() for row in self.line_items)

        try:
            shipping = float(self.shipping_entry.get() or 0)
        except ValueError:
            shipping = 0

        try:
            tax_rate = float(self.tax_entry.get() or 0) / 100
        except ValueError:
            tax_rate = 0

        tax_amount = subtotal * tax_rate
        gross_total = subtotal + shipping + tax_amount

        try:
            amount_paid = float(self.amount_paid_entry.get() or 0)
        except ValueError:
            amount_paid = 0

        balance_due = max(0, gross_total - amount_paid)

        tax_label = self.tax_label_entry.get().strip() or "Tax"
        self._tax_name_label.config(text=f"{tax_label} ({self.tax_entry.get() or 0}%)")

        self.subtotal_label.config(text=f"${subtotal:,.2f}")
        self.shipping_total_label.config(text=f"${shipping:,.2f}")
        self.tax_total_label.config(text=f"${tax_amount:,.2f}")
        self.total_gross_label.config(text=f"${gross_total:,.2f}")
        self.amount_paid_display.config(text=f"${amount_paid:,.2f}")
        self.total_label.config(text=f"${balance_due:,.2f}")

    def _on_status_changed(self, event=None):
        status = self.status_combo.get()
        if status == "PARTIALLY_PAID":
            self.partial_paid_frame.grid()
        elif status == "PAID":
            self.partial_paid_frame.grid_remove()
            # Auto-fill amount_paid with the gross total so Total Due = $0.00
            try:
                subtotal = sum(r.get_values()["quantity"] * r.get_values()["unit_price"]
                               for r in self.line_items)
                shipping = float(self.shipping_entry.get() or 0)
                tax_rate = float(self.tax_entry.get() or 0) / 100
                gross = subtotal + shipping + subtotal * tax_rate
                self.amount_paid_entry.delete(0, tk.END)
                self.amount_paid_entry.insert(0, f"{gross:.2f}")
            except Exception:
                pass
        else:
            self.partial_paid_frame.grid_remove()
            self.amount_paid_entry.delete(0, tk.END)
        self.update_totals()

    def _on_payment_method_changed(self, event=None):
        if self.payment_method_combo.get() == "Custom":
            self.custom_payment_entry.grid(row=2, column=3, sticky="w", pady=(6, 0))
        else:
            self.custom_payment_entry.grid_remove()

    def _payment_method_label(self):
        method = self.payment_method_combo.get()
        if not method:
            return None
        if method == "Custom":
            return self.custom_payment_entry.get().strip() or None
        return method

    def _on_carrier_changed(self, event=None):
        if self.carrier_combo.get() == "Custom":
            self.custom_carrier_entry.grid(row=2, column=1, sticky="w",
                                            padx=(0, 8), pady=(2, 0))
        else:
            self.custom_carrier_entry.grid_remove()

    def _carrier_label(self):
        """Returns the display label for the carrier (e.g. 'UPS', 'Custom Name')."""
        carrier = self.carrier_combo.get()
        if carrier == "Custom":
            return self.custom_carrier_entry.get().strip() or "Custom"
        return carrier

    # ------------------------------------------------------------------
    # Client handling (searchable picker)
    # ------------------------------------------------------------------

    def _refresh_clients(self):
        clients = data.list_clients(sort_by="last_name")
        self.all_clients = []
        for c in clients:
            label = f"{c['first_name']} {c['last_name']}"
            if c.get("business_name"):
                label += f" — {c['business_name']}"
            self.all_clients.append((label, c))

    def _client_label(self, client):
        label = f"{client['first_name']} {client['last_name']}"
        if client.get("business_name"):
            label += f" — {client['business_name']}"
        return label

    def _set_selected_client(self, client):
        self.selected_client = client
        if client:
            self.client_search_entry.delete(0, tk.END)
            self.client_search_entry.insert(0, self._client_label(client))
        self._show_client_info()
        self._hide_client_listbox()

    def _on_client_search_focus(self, event):
        self._update_client_listbox()

    def _on_client_search_changed(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        # Typing invalidates any previously selected client until a new
        # selection is made from the list.
        self.selected_client = None
        self._update_client_listbox()

    def _update_client_listbox(self):
        query = self.client_search_entry.get().strip().lower()

        if query:
            matches = [(label, c) for label, c in self.all_clients if query in label.lower()]
        else:
            matches = self.all_clients

        self.client_listbox.delete(0, tk.END)
        for label, c in matches[:50]:
            self.client_listbox.insert(tk.END, label)
        self._client_listbox_matches = matches[:50]

        if matches:
            self._show_client_listbox()
        else:
            self._hide_client_listbox()

    def _show_client_listbox(self):
        if not self._client_listbox_visible:
            self.client_listbox.pack(anchor="w", pady=(2, 0))
            self._client_listbox_visible = True

    def _hide_client_listbox(self):
        if self._client_listbox_visible:
            self.client_listbox.pack_forget()
            self._client_listbox_visible = False

    def _focus_client_listbox(self, event):
        if self._client_listbox_visible and self.client_listbox.size() > 0:
            self.client_listbox.focus_set()
            self.client_listbox.selection_set(0)
            self.client_listbox.activate(0)
        return "break"

    def _on_client_listbox_select(self, event):
        selection = self.client_listbox.curselection()
        if not selection:
            return
        _, client = self._client_listbox_matches[selection[0]]
        self._set_selected_client(client)

    def _show_client_info(self):
        client = self.selected_client
        if not client:
            self.client_info_label.config(text="")
            self.client_notes_display.config(state="normal")
            self.client_notes_display.delete("1.0", tk.END)
            self.client_notes_display.config(state="disabled")
            return

        parts = []
        if client.get("address1"):
            parts.append(client["address1"])
        if client.get("address2"):
            parts.append(client["address2"])
        if client.get("phone"):
            parts.append(client["phone"])
        if client.get("email"):
            parts.append(client["email"])
        if client.get("cc_emails"):
            parts.append(f"CC: {client['cc_emails']}")

        self.client_info_label.config(text="   |   ".join(parts))

        # Refresh client notes from DB in case they've been updated
        fresh = data.get_client(client["id"])
        notes = (fresh or {}).get("notes") or ""
        self.client_notes_display.config(state="normal")
        self.client_notes_display.delete("1.0", tk.END)
        self.client_notes_display.insert("1.0", notes)
        self.client_notes_display.config(state="disabled")

    # ------------------------------------------------------------------
    # Show / load
    # ------------------------------------------------------------------

    def on_show(self, invoice_id=None, preselect_client_id=None):
        self._refresh_clients()
        self._hide_client_listbox()

        # Clear existing line items and force immediate redraw
        for row in list(self.line_items):
            row.destroy()
        self.line_items = []
        self._regrid_line_items()
        self._inner.update_idletasks()  # flush widget destruction before loading new content

        if invoice_id is not None:
            self._load_invoice(invoice_id)
        else:
            self._reset_for_new()
            if preselect_client_id is not None:
                client = data.get_client(preselect_client_id)
                if client:
                    self._set_selected_client(client)

        self.update_totals()
        self._reset_scroll()

    def _reset_for_new(self):
        self.editing_invoice_id = None
        self.mode = "new"

        # Unlock all fields before clearing so delete/insert always work
        self._set_form_state(editable=True)

        self.title_label.config(text="New invoice")
        next_num = data.next_invoice_number()
        self.invoice_number_label.config(text=f"Invoice no. {next_num} · auto-assigned")

        self.client_search_entry.delete(0, tk.END)
        self.selected_client = None
        self.client_info_label.config(text="")

        today = date.today()
        due = today + timedelta(days=14)
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, today.isoformat())
        self.due_date_entry.delete(0, tk.END)
        self.due_date_entry.insert(0, due.isoformat())

        self.shipping_entry.delete(0, tk.END)
        self.tax_entry.delete(0, tk.END)
        self.tax_entry.insert(0, "13")
        self.tax_label_entry.delete(0, tk.END)
        self.tax_label_entry.insert(0, "HST")
        self.carrier_combo.set("UPS")
        self.custom_carrier_entry.delete(0, tk.END)
        self.custom_carrier_entry.grid_remove()
        self.tracking_entry.delete(0, tk.END)
        self.shipped_var.set(False)
        self.sent_var.set(False)
        self.status_combo.set("DUE")
        self.payment_method_combo.set("")
        self.custom_payment_entry.grid_remove()
        self.partial_paid_frame.grid_remove()
        self.amount_paid_entry.delete(0, tk.END)
        self.notes_text.delete("1.0", tk.END)

        self.add_line_item()
        self._apply_button_layout()

    def _load_invoice(self, invoice_id):
        invoice = data.get_invoice(invoice_id)
        if invoice is None:
            messagebox.showerror("Not found", "Invoice could not be found.")
            self._reset_for_new()
            return

        # Unlock all fields first so delete/insert work regardless of previous state
        self._set_form_state(editable=True)

        self.editing_invoice_id = invoice_id
        self.mode = "view"
        self.title_label.config(text=f"Invoice {invoice['invoice_number']}")
        self.invoice_number_label.config(text="")

        # Select the matching client
        client = invoice["client"]
        self._set_selected_client(client)

        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, invoice["invoice_date"])
        self.due_date_entry.delete(0, tk.END)
        self.due_date_entry.insert(0, invoice["due_date"])

        self.shipping_entry.delete(0, tk.END)
        if invoice["shipping"]:
            self.shipping_entry.insert(0, f"{invoice['shipping']:.2f}")

        self.tax_entry.delete(0, tk.END)
        self.tax_entry.insert(0, f"{invoice['tax_rate'] * 100:g}")

        self.tax_label_entry.delete(0, tk.END)
        self.tax_label_entry.insert(0, invoice.get("tax_label") or "HST")

        carrier = invoice.get("carrier") or "UPS"
        known = ["UPS", "Purolator", "Canada Post", "Canpar"]
        if carrier in known:
            self.carrier_combo.set(carrier)
            self.custom_carrier_entry.grid_remove()
        else:
            self.carrier_combo.set("Custom")
            self.custom_carrier_entry.delete(0, tk.END)
            self.custom_carrier_entry.insert(0, carrier)
            self._on_carrier_changed()

        self.tracking_entry.delete(0, tk.END)
        self.tracking_entry.insert(0, invoice.get("tracking_number") or "")

        self.shipped_var.set(bool(invoice.get("shipped", 0)))
        self.sent_var.set(bool(invoice.get("sent", 0)))

        self.status_combo.set(invoice.get("status") or "DUE")
        self._on_status_changed()  # show/hide partial paid frame

        payment_method = invoice.get("payment_method") or ""
        known_methods = ["E-Transfer", "Credit Card", "ACH", "Cheque", "Cash"]
        if payment_method in known_methods:
            self.payment_method_combo.set(payment_method)
            self.custom_payment_entry.grid_remove()
        elif payment_method:
            self.payment_method_combo.set("Custom")
            self.custom_payment_entry.delete(0, tk.END)
            self.custom_payment_entry.insert(0, payment_method)
            self._on_payment_method_changed()
        else:
            self.payment_method_combo.set("")
            self.custom_payment_entry.grid_remove()

        self.amount_paid_entry.delete(0, tk.END)
        if invoice.get("amount_paid"):
            self.amount_paid_entry.insert(0, f"{invoice['amount_paid']:.2f}")

        self.notes_text.delete("1.0", tk.END)
        if invoice.get("notes"):
            self.notes_text.insert("1.0", invoice["notes"])

        for item in invoice["items"]:
            self.add_line_item(item)

        if not invoice["items"]:
            self.add_line_item()

        self._set_form_state(editable=False)
        self._apply_button_layout()
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text="")

    # ------------------------------------------------------------------
    # Mode / form state management
    # ------------------------------------------------------------------

    def _set_form_state(self, editable):
        """Locks or unlocks all input widgets."""
        entry_state = "normal" if editable else "disabled"

        self.date_entry.config(state=entry_state)
        self.due_date_entry.config(state=entry_state)
        self.shipping_entry.config(state=entry_state)
        self.tax_entry.config(state=entry_state)
        self.tax_label_entry.config(state=entry_state)
        self.tracking_entry.config(state=entry_state)
        self.custom_carrier_entry.config(state=entry_state)
        self.carrier_combo.config(state="readonly" if editable else "disabled")
        self.status_combo.config(state="readonly" if editable else "disabled")
        self.payment_method_combo.config(state="readonly" if editable else "disabled")
        self.amount_paid_entry.config(state=entry_state)
        self.custom_payment_entry.config(state=entry_state)
        self.shipped_check.config(state="normal" if editable else "disabled")
        self.sent_check.config(state="normal" if editable else "disabled")
        self.notes_text.config(state="normal" if editable else "disabled")
        self.client_search_entry.config(state=entry_state)
        if not editable:
            self._hide_client_listbox()

        for row in self.line_items:
            for widget in (row.code_entry, row.desc_entry, row.qty_entry, row.price_entry):
                widget.config(state=entry_state)
            row.remove_btn.config(state=("normal" if editable else "disabled"))

        # "Add line item" button is the last child packed directly into
        # items_outer (not items_frame); find it by walking children.
        for child in self.items_frame.master.pack_slaves():
            if isinstance(child, ttk.Button):
                child.config(state=("normal" if editable else "disabled"))

    def _apply_button_layout(self):
        for btn in (self.delete_btn, self.cancel_btn, self.save_btn,
                    self.export_btn, self.edit_btn, self.client_details_btn,
                    self.new_invoice_for_client_btn, self.invoice_sent_btn,
                    self.send_invoice_btn, self.mark_paid_send_btn,
                    self.confirm_paid_btn, self.status_bar):
            btn.pack_forget()

        if self.mode == "new":
            self.export_btn.pack(side="right")
            self.save_btn.pack(side="right", padx=(8, 0))

        elif self.mode == "view":
            self.invoice_sent_btn.pack(side="right")
            self.export_btn.pack(side="right", padx=(0, 8))
            self.send_invoice_btn.pack(side="right", padx=(0, 8))
            self.mark_paid_send_btn.pack(side="right", padx=(0, 8))
            self.edit_btn.pack(side="right", padx=(8, 0))
            self.new_invoice_for_client_btn.pack(side="right", padx=(8, 0))
            self.client_details_btn.pack(side="left")
            self.status_bar.pack(side="left", padx=(12, 0))

        elif self.mode == "view_confirming_paid":
            # Waiting for user to pick payment method and confirm
            self.confirm_paid_btn.pack(side="right")
            self.cancel_btn.pack(side="right", padx=(0, 8))
            self.client_details_btn.pack(side="left")
            self.status_bar.pack(side="left", padx=(12, 0))

        elif self.mode == "edit":
            self.export_btn.pack(side="right")
            self.save_btn.pack(side="right", padx=(8, 0))
            self.cancel_btn.pack(side="right", padx=(8, 0))
            self.delete_btn.pack(side="left")
            self.client_details_btn.pack(side="left", padx=(8, 0))

    def _confirm_send_invoice(self):
        """Show a confirmation before sending the invoice email."""
        if self.editing_invoice_id is None:
            return
        client = self.selected_client
        to_addr = (client or {}).get("email", "the client")
        if not messagebox.askyesno(
            "Confirm send",
            f"Send invoice email to {to_addr}?"
        ):
            return
        self._send_invoice_email()

    def _start_mark_paid_send(self):
        """Enter 'confirming paid' mode — focus payment method, show Confirm button."""
        if self.editing_invoice_id is None:
            return

        bridge_pw = data.get_setting("bridge_password")
        if not bridge_pw:
            messagebox.showerror("Bridge not configured",
                "Add your ProtonMail Bridge password in Settings.")
            return

        client = self.selected_client
        if not client or not client.get("email"):
            messagebox.showerror("No email",
                "This client has no primary email address.")
            return

        # Enable just the payment method combo so the user can pick
        self.payment_method_combo.config(state="readonly")
        self.custom_payment_entry.config(state="normal")
        self.status_bar.config(
            text="Select payment method, then click Confirm & send",
            foreground="orange"
        )
        self.mode = "view_confirming_paid"
        self._apply_button_layout()

        # Scroll down so the payment method row is visible
        self.after(50, lambda: self._canvas.yview_moveto(1.0))

        # Focus the payment method combo
        self.payment_method_combo.focus_set()

        # When user picks a method, that's sufficient — Confirm button is visible
        self.payment_method_combo.bind(
            "<<ComboboxSelected>>", self._on_paid_method_selected, add="+"
        )

    def _on_paid_method_selected(self, event=None):
        """Called when payment method is chosen in confirming-paid mode."""
        if self.mode != "view_confirming_paid":
            return
        method = self._payment_method_label()
        if method:
            self.status_bar.config(
                text=f"Payment method: {method}. Click Confirm & send to proceed.",
                foreground="orange"
            )

    def _confirm_mark_paid_send(self):
        """Actually mark as paid, save, deactivate Stripe link, send email."""
        if self.editing_invoice_id is None:
            return

        method = self._payment_method_label()
        if not method:
            messagebox.showerror("No payment method",
                "Please select a payment method before confirming.")
            self.payment_method_combo.focus_set()
            return

        invoice = data.get_invoice(self.editing_invoice_id)
        gross   = invoice.get("total") or 0

        # Update status to PAID, amount_paid to full gross total
        conn_data = {
            "client_id":       invoice["client_id"],
            "invoice_date":    invoice["invoice_date"],
            "due_date":        invoice["due_date"],
            "shipping":        invoice.get("shipping") or 0,
            "tax_rate":        invoice.get("tax_rate") or 0.13,
            "tracking_number": invoice.get("tracking_number"),
            "carrier":         invoice.get("carrier") or "UPS",
            "tax_label":       invoice.get("tax_label") or "HST",
            "status":          "PAID",
            "payment_method":  method,
            "amount_paid":     gross,
            "shipped":         invoice.get("shipped") or 0,
            "sent":            invoice.get("sent") or 0,
            "notes":           invoice.get("notes"),
            "items":           invoice["items"],
        }
        data.update_invoice(self.editing_invoice_id, **conn_data)
        self._maybe_deactivate_on_paid(self.editing_invoice_id)

        # Reload invoice with updated values and send paid confirmation
        fresh_invoice = data.get_invoice(self.editing_invoice_id)

        # Generate PDF
        import tempfile
        from invoice import build_invoice_pdf
        from views.email_sender import send_invoice_email
        from datetime import date as _date

        tmp_pdf = Path(tempfile.mktemp(suffix=".pdf"))
        try:
            build_invoice_pdf(fresh_invoice, tmp_pdf)
        except Exception as e:
            messagebox.showerror("PDF error", f"Could not generate PDF:\n{e}")
            return

        client   = fresh_invoice["client"]
        to_addr  = client.get("email")
        cc_raw   = client.get("cc_emails") or ""
        cc_list  = [e.strip() for e in cc_raw.split(",") if e.strip()]
        inv_num  = fresh_invoice["invoice_number"]
        subject  = f"Payment received — Invoice {inv_num}"
        bridge_pw = data.get_setting("bridge_password")

        body_lines = [
            f"Hello {client.get('first_name', '')},",
            "",
            f"We have received your payment for invoice {inv_num}. Thank you!",
            "",
            "Please find your updated invoice attached for your records.",
            "",
            "If you have any questions, please don't hesitate to reach out.",
            "",
            "Thank you,",
            "Grounded Repairs",
            "(705) 761 2938",
            "thomas@groundedrepairs.com",
        ]
        body = "\n".join(body_lines)

        try:
            send_invoice_email(
                to_address=to_addr,
                cc_addresses=cc_list,
                subject=subject,
                body=body,
                pdf_path=tmp_pdf,
                bridge_password=bridge_pw,
            )
        except Exception as e:
            messagebox.showerror("Email failed",
                f"Invoice was marked paid but email failed:\n{e}")
        finally:
            try:
                tmp_pdf.unlink()
            except Exception:
                pass

        # Mark as sent too
        data.mark_invoice_sent(self.editing_invoice_id, _date.today().strftime("%Y-%m-%d"))

        # Reload view and show status
        self._load_invoice(self.editing_invoice_id)
        self.mode = "view"
        self._set_form_state(editable=False)
        self._apply_button_layout()

        now = _date.today().strftime("%B %d, %Y")
        self.status_bar.config(
            text=f"✓ Marked paid & confirmation sent  {now}",
            foreground="green"
        )
        self.status_bar.pack(side="left", padx=(12, 0))

    def _go_to_client(self):
        if self.selected_client:
            self.app.show_view("ClientDetailView", client_id=self.selected_client["id"])

    def _new_invoice_for_same_client(self):
        client_id = self.selected_client["id"] if self.selected_client else None
        self.app.show_view("NewInvoiceView", preselect_client_id=client_id)

    def _copy_payment_link(self):
        if self.editing_invoice_id is None:
            return

        import urllib.request, urllib.error, json, base64

        stripe_key = data.get_stripe_key()
        if not stripe_key:
            messagebox.showerror(
                "Stripe not configured",
                "Add your Stripe secret key in Settings → Stripe payments."
            )
            return

        invoice = data.get_invoice(self.editing_invoice_id)
        balance_due = invoice.get("balance_due") or data.invoice_balance_due(invoice)

        if balance_due <= 0:
            messagebox.showinfo("Nothing due", "This invoice has a zero balance.")
            return

        amount_cents = round(balance_due * 100)

        # Check for an existing Payment Link at the same amount
        session_info = data.get_stripe_session(self.editing_invoice_id)
        stored_amount = session_info.get("stripe_session_amount")
        stored_url    = session_info.get("stripe_checkout_url")
        stored_id     = session_info.get("stripe_session_id")

        if stored_url and stored_amount and abs(stored_amount - balance_due) < 0.01:
            # Same amount — reuse existing link (Payment Links don't expire)
            self.clipboard_clear()
            self.clipboard_append(stored_url)
            messagebox.showinfo("Copied",
                f"Payment link copied to clipboard.\n\n{stored_url}")
            return

        # Amount changed — deactivate the old link if there is one
        if stored_id:
            self._deactivate_payment_link(stored_id, stripe_key)

        # Create a new Payment Link
        inv_num     = invoice["invoice_number"]
        client      = invoice["client"]
        description = f"Grounded Repairs \u2014 Invoice {inv_num}"

        def stripe_post(endpoint, params):
            form_data = "&".join(
                f"{k}={urllib.request.quote(str(v), safe='')}"
                for k, v in params
            ).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.stripe.com/v1/{endpoint}",
                data=form_data,
                method="POST",
            )
            creds = base64.b64encode(f"{stripe_key}:".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())

        try:
            # Step 1: create a one-time Price
            price = stripe_post("prices", [
                ("currency", "cad"),
                ("unit_amount", str(amount_cents)),
                ("product_data[name]", description),
            ])
            price_id = price["id"]

            # Step 2: create the Payment Link
            link = stripe_post("payment_links", [
                ("line_items[0][price]", price_id),
                ("line_items[0][quantity]", "1"),
                ("metadata[invoice_id]", str(self.editing_invoice_id)),
                ("metadata[invoice_number]", inv_num),
                ("after_completion[type]", "redirect"),
                ("after_completion[redirect][url]", "https://groundedrepairs.com"),
            ])

            link_id  = link["id"]
            link_url = link["url"]

            data.save_stripe_session(
                self.editing_invoice_id, link_id, link_url, balance_due
            )

            self.clipboard_clear()
            self.clipboard_append(link_url)
            messagebox.showinfo("Copied",
                f"Payment link created and copied to clipboard.\n\n{link_url}")

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                err_msg = json.loads(body).get("error", {}).get("message", body)
            except Exception:
                err_msg = body
            messagebox.showerror("Stripe error", err_msg)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create payment link:\n{e}")

    def _deactivate_payment_link(self, link_id, stripe_key):
        """Deactivate a Stripe Payment Link. Fails silently — not critical."""
        try:
            import urllib.request, base64
            form_data = b"active=false"
            req = urllib.request.Request(
                f"https://api.stripe.com/v1/payment_links/{link_id}",
                data=form_data,
                method="POST",
            )
            creds = base64.b64encode(f"{stripe_key}:".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # Don't block the user if deactivation fails

    def enable_editing(self):
        self.mode = "edit"
        self._set_form_state(editable=True)
        self._apply_button_layout()
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text="")

    def cancel_edit(self):
        if self.mode == "view_confirming_paid":
            # Just return to view mode without saving
            self.mode = "view"
            self._set_form_state(editable=False)
            self._apply_button_layout()
            return
        # Reload the invoice from the database to discard any unsaved changes
        for row in list(self.line_items):
            row.destroy()
        self.line_items = []
        self._regrid_line_items()
        self._load_invoice(self.editing_invoice_id)
        self.update_totals()

    def delete_invoice(self):
        confirm = messagebox.askyesno(
            "Delete invoice",
            f"This permanently removes invoice and its line items. "
            "This can't be undone.",
            icon="warning",
        )
        if not confirm:
            return

        data.delete_invoice(self.editing_invoice_id)
        messagebox.showinfo("Deleted", "Invoice deleted.")
        self.app.show_view("InvoicesListView")

    # ------------------------------------------------------------------
    # Validation / data collection
    # ------------------------------------------------------------------

    def _collect_invoice_data(self):
        client = self.selected_client
        if not client:
            messagebox.showerror("Missing client", "Please select a client.")
            return None

        invoice_date = self.date_entry.get().strip()
        due_date = self.due_date_entry.get().strip()
        if not self._valid_date(invoice_date) or not self._valid_date(due_date):
            messagebox.showerror("Invalid date", "Dates must be in YYYY-MM-DD format.")
            return None

        try:
            shipping = float(self.shipping_entry.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid shipping", "Shipping must be a number.")
            return None

        try:
            tax_rate = float(self.tax_entry.get() or 0) / 100
        except ValueError:
            messagebox.showerror("Invalid tax rate", "Tax rate must be a number.")
            return None

        tracking_number = self.tracking_entry.get().strip() or None
        carrier = self._carrier_label()
        tax_label = self.tax_label_entry.get().strip() or "HST"
        status = self.status_combo.get() or "DUE"
        payment_method = self._payment_method_label()
        try:
            amount_paid = float(self.amount_paid_entry.get() or 0)
        except ValueError:
            amount_paid = 0
        notes = self.notes_text.get("1.0", tk.END).strip() or None

        items = []
        for row in self.line_items:
            if row.is_blank():
                continue
            items.append(row.get_values())

        if not items:
            messagebox.showerror("No line items", "Add at least one line item.")
            return None

        return {
            "client_id": client["id"],
            "invoice_date": invoice_date,
            "due_date": due_date,
            "shipping": shipping,
            "tax_rate": tax_rate,
            "tracking_number": tracking_number,
            "carrier": carrier,
            "tax_label": tax_label,
            "status": status,
            "payment_method": payment_method,
            "amount_paid": amount_paid,
            "shipped": 1 if self.shipped_var.get() else 0,
            "sent":    1 if self.sent_var.get() else 0,
            "notes": notes,
            "items": items,
        }

    @staticmethod
    def _valid_date(value):
        try:
            date.fromisoformat(value)
            return True
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Save / export
    # ------------------------------------------------------------------

    def _after_save(self):
        """Navigate to client card if we have a client, otherwise invoices list."""
        if self.selected_client:
            self.app.show_view("ClientDetailView",
                               client_id=self.selected_client["id"])
        else:
            self.app.show_view("InvoicesListView")

    def _send_invoice_email(self):
        if self.editing_invoice_id is None:
            return

        bridge_pw = data.get_setting("bridge_password")
        if not bridge_pw:
            messagebox.showerror(
                "Bridge not configured",
                "Add your ProtonMail Bridge password in Settings."
            )
            return

        invoice = data.get_invoice(self.editing_invoice_id)
        client  = invoice["client"]
        to_addr = client.get("email")
        if not to_addr:
            messagebox.showerror("No email",
                "This client has no primary email address.")
            return

        cc_raw = client.get("cc_emails") or ""
        cc_list = [e.strip() for e in cc_raw.split(",") if e.strip()]

        # Generate payment link if needed and invoice has a balance
        payment_link = None
        balance_due  = invoice.get("balance_due", 0)
        if balance_due > 0:
            session_info = data.get_stripe_session(self.editing_invoice_id)
            stored_url   = session_info.get("stripe_checkout_url")
            stored_id    = session_info.get("stripe_session_id")
            stored_amt   = session_info.get("stripe_session_amount")

            if stored_url and stored_amt and abs(stored_amt - balance_due) < 0.01:
                payment_link = stored_url
            else:
                # Need to generate one — call the same logic as the button
                stripe_key = data.get_stripe_key()
                if stripe_key:
                    try:
                        payment_link = self._create_payment_link_silent(
                            invoice, balance_due, stripe_key
                        )
                    except Exception as e:
                        if not messagebox.askyesno(
                            "Payment link failed",
                            f"Could not generate payment link: {e}\n\n"
                            "Send email without a payment link?"
                        ):
                            return

        # Generate PDF to a temp file
        import tempfile
        from invoice import build_invoice_pdf
        tmp_pdf = Path(tempfile.mktemp(suffix=".pdf"))
        try:
            build_invoice_pdf(invoice, tmp_pdf)
        except Exception as e:
            messagebox.showerror("PDF error", f"Could not generate PDF:\n{e}")
            return

        from views.email_sender import send_invoice_email, build_invoice_email_body

        inv_num = invoice["invoice_number"]
        subject = f"Invoice {inv_num} from Grounded Repairs"
        body    = build_invoice_email_body(invoice, payment_link=payment_link)

        try:
            send_invoice_email(
                to_address=to_addr,
                cc_addresses=cc_list,
                subject=subject,
                body=body,
                pdf_path=tmp_pdf,
                bridge_password=bridge_pw,
            )
            # Mark as sent in DB and update the checkbox
            from datetime import date as _date
            data.mark_invoice_sent(self.editing_invoice_id,
                                   _date.today().strftime("%Y-%m-%d"))
            self.sent_var.set(True)
            now = _date.today().strftime("%B %d, %Y")
            self.status_bar.config(
                text=f"✓ Invoice sent  {now}",
                foreground="green"
            )
            self.status_bar.pack(side="left", padx=(12, 0))
            messagebox.showinfo("Sent",
                f"Invoice emailed to {to_addr}"
                + (f" (CC: {', '.join(cc_list)})" if cc_list else ""))
        except Exception as e:
            messagebox.showerror("Email failed", str(e))
        finally:
            try:
                tmp_pdf.unlink()
            except Exception:
                pass

    def _create_payment_link_silent(self, invoice, balance_due, stripe_key):
        """Create a Payment Link and store it. Returns the URL."""
        import urllib.request, urllib.error, json, base64

        amount_cents = round(balance_due * 100)
        inv_num      = invoice["invoice_number"]
        description  = f"Grounded Repairs \u2014 Invoice {inv_num}"

        def stripe_post(endpoint, params):
            form_data = "&".join(
                f"{k}={urllib.request.quote(str(v), safe='')}"
                for k, v in params
            ).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.stripe.com/v1/{endpoint}",
                data=form_data, method="POST",
            )
            creds = base64.b64encode(f"{stripe_key}:".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())

        price = stripe_post("prices", [
            ("currency", "cad"),
            ("unit_amount", str(amount_cents)),
            ("product_data[name]", description),
        ])
        link = stripe_post("payment_links", [
            ("line_items[0][price]", price["id"]),
            ("line_items[0][quantity]", "1"),
            ("metadata[invoice_id]", str(self.editing_invoice_id)),
            ("metadata[invoice_number]", inv_num),
            ("after_completion[type]", "redirect"),
            ("after_completion[redirect][url]", "https://groundedrepairs.com"),
        ])

        data.save_stripe_session(
            self.editing_invoice_id, link["id"], link["url"], balance_due
        )
        return link["url"]

    def _maybe_deactivate_on_paid(self, invoice_id):
        """If invoice is now PAID and has a payment link, deactivate it."""
        inv = data.get_invoice(invoice_id)
        if not inv or inv.get("status") != "PAID":
            return
        session_info = data.get_stripe_session(invoice_id)
        link_id = session_info.get("stripe_session_id")
        if not link_id:
            return
        stripe_key = data.get_stripe_key()
        if not stripe_key:
            return
        self._deactivate_payment_link(link_id, stripe_key)
        data.clear_stripe_session(invoice_id)

    def save(self):
        invoice_data = self._collect_invoice_data()
        if invoice_data is None:
            return

        if self.editing_invoice_id is None:
            invoice_id, invoice_number = data.create_invoice(**invoice_data)
            messagebox.showinfo("Saved", f"Invoice {invoice_number} created.")
        else:
            data.update_invoice(self.editing_invoice_id, **invoice_data)
            self._maybe_deactivate_on_paid(self.editing_invoice_id)
            messagebox.showinfo("Saved", "Invoice updated.")

        self._after_save()

    def save_and_export(self):
        invoice_data = self._collect_invoice_data()
        if invoice_data is None:
            return

        if self.editing_invoice_id is None:
            invoice_id, invoice_number = data.create_invoice(**invoice_data)
        else:
            invoice_id = self.editing_invoice_id
            data.update_invoice(invoice_id, **invoice_data)
            self._maybe_deactivate_on_paid(invoice_id)
            invoice_number = data.get_invoice(invoice_id)["invoice_number"]

        invoice = data.get_invoice(invoice_id)

        default_dir = str(Path.home() / "Desktop")
        filepath = filedialog.asksaveasfilename(
            initialdir=default_dir,
            initialfile=f"{invoice_number}.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not filepath:
            return

        build_invoice_pdf(invoice, filepath)
        messagebox.showinfo("Exported", f"Invoice saved to {filepath}")
        self._after_save()
