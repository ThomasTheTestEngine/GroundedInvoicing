import tkinter as tk
from tkinter import ttk, messagebox

import data


STATUS_COLORS = {
    "OVERDUE":        "#cc0000",
    "DUE":            "#555555",
    "PARTIALLY_PAID": "#b36b00",
    "PAID":           "#1a7a1a",
}

INV_COLUMNS = [
    ("invoice_number", "Invoice #",  100),
    ("invoice_date",   "Date",       100),
    ("due_date",       "Due",        100),
    ("status",         "Status",     110),
    ("total",          "Total due",  100),
]


class ClientDetailView(ttk.Frame):
    FIELD_DEFS = [
        ("first_name",    "First name"),
        ("last_name",     "Last name"),
        ("business_name", "Business name (optional)"),
        ("phone",         "Phone"),
        ("email",         "Primary email"),
        ("cc_emails",     "CC email(s) — comma separated"),
        ("address1",      "Address line 1"),
        ("address2",      "Address line 2 (city, province, postal code)"),
    ]

    def __init__(self, parent, app):
        super().__init__(parent, padding=20)
        self.app = app
        self.client_id = None
        self.editing = False
        self.inv_sort_by = "invoice_number"
        self.inv_ascending = False

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ---- Top section: fields (left) + notes (right) ----
        top = ttk.Frame(self)
        top.pack(fill="x")

        fields_frame = ttk.Frame(top)
        fields_frame.pack(side="left", anchor="nw", fill="x", expand=True)

        self.title_label = ttk.Label(fields_frame, text="Client",
                                      font=("Helvetica", 16, "bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.fields = {}
        for i, (key, label) in enumerate(self.FIELD_DEFS, start=1):
            ttk.Label(fields_frame, text=label).grid(
                row=i, column=0, sticky="w", pady=3, padx=(0, 10)
            )
            entry = ttk.Entry(fields_frame, width=38, state="readonly")
            entry.grid(row=i, column=1, sticky="w", pady=3)
            self.fields[key] = entry

        # Notes box — top right
        notes_frame = ttk.Frame(top)
        notes_frame.pack(side="right", anchor="ne", padx=(20, 0), fill="y")

        ttk.Label(notes_frame, text="Notes").pack(anchor="w")
        notes_border = ttk.Frame(notes_frame, borderwidth=1, relief="solid")
        notes_border.pack(fill="both", expand=True, pady=(4, 0))
        self.notes_text = tk.Text(notes_border, width=28, height=10, wrap="word",
                                   font=("Helvetica", 10), state="disabled",
                                   relief="flat", borderwidth=0)
        self.notes_text.pack(fill="both", expand=True)

        # ---- Button row ----
        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", pady=(12, 0))

        self.new_invoice_btn = ttk.Button(btn_row, text="New invoice for this client",
                                           command=self.new_invoice_for_client)

        right_btns = ttk.Frame(btn_row)
        right_btns.pack(side="right")

        self.save_btn = ttk.Button(right_btns, text="Save changes",
                                    command=self.save_changes)
        self.edit_btn = ttk.Button(right_btns, text="Edit", command=self.toggle_edit)
        self.edit_btn.pack(side="right")
        self.new_invoice_btn.pack(side="right", padx=(0, 8))

        self.delete_btn_frame = ttk.Frame(btn_row)
        self.delete_btn = ttk.Button(self.delete_btn_frame, text="Delete",
                                      command=self.delete_client)

        # ---- Separator ----
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(14, 0))

        # ---- Invoices list for this client ----
        inv_header = ttk.Frame(self)
        inv_header.pack(fill="x", pady=(10, 4))
        ttk.Label(inv_header, text="Invoices", font=("Helvetica", 12, "bold")).pack(
            side="left"
        )

        self.inv_tree = ttk.Treeview(
            self,
            columns=[c[0] for c in INV_COLUMNS],
            show="headings",
            selectmode="browse",
            height=12,
        )
        for col_id, label, width in INV_COLUMNS:
            self.inv_tree.heading(col_id, text=label,
                                   command=lambda c=col_id: self._inv_sort_by(c))
            anchor = "e" if col_id == "total" else "w"
            self.inv_tree.column(col_id, width=width, anchor=anchor)

        for status, color in STATUS_COLORS.items():
            self.inv_tree.tag_configure(status, foreground=color)

        self.inv_tree.pack(fill="x")
        self.inv_tree.bind("<Double-1>", self._on_inv_double_click)

        ttk.Label(
            self,
            text="Double-click an invoice to open it.",
            foreground="gray",
        ).pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def on_show(self, client_id=None):
        self.client_id = client_id
        self.editing = False
        self._load_client()
        self._set_edit_mode(False)
        self._refresh_invoices()

    def _load_client(self):
        client = data.get_client(self.client_id)
        if client is None:
            messagebox.showerror("Not found", "Client could not be found.")
            self.app.show_view("ClientsListView")
            return

        self.title_label.config(
            text=f"{client['first_name']} {client['last_name']}"
        )

        for key, _ in self.FIELD_DEFS:
            entry = self.fields[key]
            entry.config(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, client.get(key) or "")

        self.notes_text.config(state="normal")
        self.notes_text.delete("1.0", tk.END)
        if client.get("notes"):
            self.notes_text.insert("1.0", client["notes"])

    def _refresh_invoices(self):
        for row in self.inv_tree.get_children():
            self.inv_tree.delete(row)

        invoices = data.list_invoices_for_client(
            self.client_id,
            sort_by=self.inv_sort_by,
            ascending=self.inv_ascending,
        )

        for col_id, label, width in INV_COLUMNS:
            indicator = ""
            if col_id == self.inv_sort_by:
                indicator = " ▲" if self.inv_ascending else " ▼"
            self.inv_tree.heading(col_id, text=label + indicator)

        for inv in invoices:
            disp = inv["display_status"]
            self.inv_tree.insert("", "end", iid=str(inv["id"]), tags=(disp,), values=(
                inv["invoice_number"],
                inv["invoice_date"],
                inv["due_date"],
                disp,
                f"${inv['total']:,.2f}",
            ))

    def _inv_sort_by(self, col_id):
        if self.inv_sort_by == col_id:
            self.inv_ascending = not self.inv_ascending
        else:
            self.inv_sort_by = col_id
            self.inv_ascending = True
        self._refresh_invoices()

    def _on_inv_double_click(self, event):
        selection = self.inv_tree.selection()
        if not selection:
            return
        invoice_id = int(selection[0])
        self.app.show_view("NewInvoiceView", invoice_id=invoice_id)

    # ------------------------------------------------------------------
    # Edit mode toggle
    # ------------------------------------------------------------------

    def _set_edit_mode(self, editing):
        self.editing = editing
        entry_state = "normal" if editing else "readonly"
        for entry in self.fields.values():
            entry.config(state=entry_state)

        self.notes_text.config(state="normal" if editing else "disabled")

        if editing:
            self.edit_btn.config(text="Cancel", command=self.cancel_edit)
            self.save_btn.pack(side="right", padx=(0, 8))
            self.delete_btn.pack(side="left")
            self.delete_btn_frame.pack(side="left")
        else:
            self.edit_btn.config(text="Edit", command=self.toggle_edit)
            self.save_btn.pack_forget()
            self.delete_btn.pack_forget()
            self.delete_btn_frame.pack_forget()

    def toggle_edit(self):
        self._set_edit_mode(True)

    def cancel_edit(self):
        self._load_client()
        self._set_edit_mode(False)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def new_invoice_for_client(self):
        self.app.show_view("NewInvoiceView", preselect_client_id=self.client_id)

    def save_changes(self):
        first_name = self.fields["first_name"].get().strip()
        last_name = self.fields["last_name"].get().strip()

        if not first_name or not last_name:
            messagebox.showerror("Missing information",
                                  "First and last name are required.")
            return

        notes = self.notes_text.get("1.0", tk.END).strip() or None

        data.update_client(
            self.client_id,
            first_name=first_name,
            last_name=last_name,
            business_name=self.fields["business_name"].get().strip() or None,
            phone=self.fields["phone"].get().strip() or None,
            email=self.fields["email"].get().strip() or None,
            cc_emails=self.fields["cc_emails"].get().strip() or None,
            address1=self.fields["address1"].get().strip() or None,
            address2=self.fields["address2"].get().strip() or None,
            notes=notes,
        )

        messagebox.showinfo("Saved", "Client updated.")
        self._load_client()
        self._set_edit_mode(False)

    def delete_client(self):
        confirm = messagebox.askyesno(
            "Delete client",
            "This permanently removes the client. This can't be undone.\n\n"
            "Clients with existing invoices cannot be deleted.",
            icon="warning",
        )
        if not confirm:
            return

        try:
            data.delete_client(self.client_id)
        except Exception:
            messagebox.showerror(
                "Cannot delete",
                "This client has existing invoices and cannot be deleted.",
            )
            return

        messagebox.showinfo("Deleted", "Client deleted.")
        self.app.show_view("ClientsListView")
