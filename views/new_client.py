import tkinter as tk
from tkinter import ttk, messagebox

import data


class NewClientView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=20)
        self.app = app

        # Two-column layout: fields left, notes right
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        left = ttk.Frame(main_frame)
        left.pack(side="left", anchor="nw")

        ttk.Label(left, text="New client", font=("Helvetica", 16, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 15)
        )

        self.fields = {}
        field_defs = [
            ("first_name",    "First name"),
            ("last_name",     "Last name"),
            ("business_name", "Business name (optional)"),
            ("phone",         "Phone"),
            ("email",         "Primary email"),
            ("cc_emails",     "CC email(s) — comma separated"),
            ("address1",      "Address line 1"),
            ("address2",      "Address line 2 (city, province, postal code)"),
        ]

        for i, (key, label) in enumerate(field_defs, start=1):
            ttk.Label(left, text=label).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
            entry = ttk.Entry(left, width=38)
            entry.grid(row=i, column=1, sticky="w", pady=4)
            self.fields[key] = entry

        btn_row = len(field_defs) + 1
        btn_frame = ttk.Frame(left)
        btn_frame.grid(row=btn_row, column=0, columnspan=2, sticky="w", pady=(15, 0))
        ttk.Button(btn_frame, text="Save client", command=self.save).pack(side="left")
        ttk.Button(btn_frame, text="Clear", command=self.clear).pack(side="left", padx=(8, 0))

        # Notes box on the right
        right = ttk.Frame(main_frame)
        right.pack(side="right", anchor="nw", padx=(20, 0), fill="y")

        ttk.Label(right, text="Notes").pack(anchor="w")
        notes_border = ttk.Frame(right, borderwidth=1, relief="solid")
        notes_border.pack(fill="both", expand=True, pady=(4, 0))
        self.notes_text = tk.Text(notes_border, width=28, height=14, wrap="word",
                                   font=("Helvetica", 10), relief="flat", borderwidth=0)
        self.notes_text.pack(fill="both", expand=True)

    def on_show(self):
        self.clear()

    def clear(self):
        for entry in self.fields.values():
            entry.delete(0, tk.END)
        self.notes_text.delete("1.0", tk.END)
        self.fields["first_name"].focus_set()

    def save(self):
        first_name = self.fields["first_name"].get().strip()
        last_name = self.fields["last_name"].get().strip()

        if not first_name or not last_name:
            messagebox.showerror("Missing information", "First and last name are required.")
            return

        notes = self.notes_text.get("1.0", tk.END).strip() or None

        client_id = data.add_client(
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

        self.clear()
        self.app.show_view("ClientDetailView", client_id=client_id)
