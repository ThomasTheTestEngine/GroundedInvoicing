import tkinter as tk
from tkinter import ttk

import data
import prefs


DEFAULT_COLUMNS = [
    ("first_name",    "First name", 120),
    ("last_name",     "Last name",  120),
    ("business_name", "Business",   180),
    ("phone",         "Phone",      130),
    ("email",         "Email",      200),
]


class ClientsListView(ttk.Frame):
    PREFS_KEY_WIDTHS = "clients_col_widths"
    PREFS_KEY_ORDER  = "clients_col_order"

    def __init__(self, parent, app):
        super().__init__(parent, padding=20)
        self.app = app
        self.sort_by = "last_name"
        self.ascending = True

        ttk.Label(self, text="Clients", font=("Helvetica", 16, "bold")).pack(
            anchor="w", pady=(0, 10)
        )

        col_ids = [c[0] for c in DEFAULT_COLUMNS]
        self.tree = ttk.Treeview(
            self, columns=col_ids, show="headings", selectmode="browse"
        )

        saved_widths = prefs.get(self.PREFS_KEY_WIDTHS, {})
        for col_id, label, default_width in DEFAULT_COLUMNS:
            width = saved_widths.get(col_id, default_width)
            self.tree.heading(col_id, text=label,
                              command=lambda c=col_id: self._sort_by(c))
            self.tree.column(col_id, width=width, anchor="w")

        saved_order = prefs.get(self.PREFS_KEY_ORDER)
        if saved_order:
            try:
                self.tree.config(displaycolumns=saved_order)
            except Exception:
                pass

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_row_double_click)

        self._drag_col = None
        self.tree.bind("<Button-1>", self._col_drag_start)
        self.tree.bind("<B1-Motion>", self._col_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._col_drag_end)

        ttk.Label(
            self,
            text="Double-click to open. Click header to sort. Drag header to reorder columns.",
            foreground="gray",
        ).pack(anchor="w", pady=(8, 0))

    def _col_drag_start(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            self._drag_col = self.tree.identify_column(event.x)
        else:
            self._drag_col = None

    def _col_drag_motion(self, event):
        if not self._drag_col:
            return
        target = self.tree.identify_column(event.x)
        if target and target != self._drag_col:
            cols = list(self.tree.cget("displaycolumns"))
            if cols == ["#all"]:
                cols = list(self.tree.cget("columns"))
            try:
                src_idx = int(self._drag_col.lstrip("#")) - 1
                tgt_idx = int(target.lstrip("#")) - 1
                cols.insert(tgt_idx, cols.pop(src_idx))
                self.tree.config(displaycolumns=cols)
                self._drag_col = target
            except (ValueError, IndexError):
                pass

    def _col_drag_end(self, event):
        self._drag_col = None
        self._save_col_prefs()

    def _save_col_prefs(self):
        widths = {col_id: self.tree.column(col_id, "width")
                  for col_id, _, _ in DEFAULT_COLUMNS}
        prefs.set(self.PREFS_KEY_WIDTHS, widths)
        cols = self.tree.cget("displaycolumns")
        if cols != ("ALL",) and cols != ("#all",):
            prefs.set(self.PREFS_KEY_ORDER, list(cols))

    def on_show(self, **kwargs):
        self._refresh()

    def _sort_by(self, col_id):
        if self.sort_by == col_id:
            self.ascending = not self.ascending
        else:
            self.sort_by = col_id
            self.ascending = True
        self._refresh()

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        clients = data.list_clients(sort_by=self.sort_by, ascending=self.ascending)

        for col_id, label, _ in DEFAULT_COLUMNS:
            indicator = " ▲" if (col_id == self.sort_by and self.ascending) else \
                        " ▼" if col_id == self.sort_by else ""
            self.tree.heading(col_id, text=label + indicator)

        for c in clients:
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["first_name"],
                c["last_name"],
                c.get("business_name") or "",
                c.get("phone") or "",
                c.get("email") or "",
            ))

    def _on_row_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            return
        selection = self.tree.selection()
        if not selection:
            return
        self.app.show_view("ClientDetailView", client_id=int(selection[0]))
