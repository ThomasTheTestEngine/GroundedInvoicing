import tkinter as tk
from tkinter import ttk

import db_setup
db_setup.init_db()

import prefs
from views.new_client import NewClientView
from views.new_invoice import NewInvoiceView
from views.clients_list import ClientsListView
from views.invoices_list import InvoicesListView
from views.client_detail import ClientDetailView
from views.settings import SettingsView

try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

DEFAULT_GEOMETRY = "1100x825"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Grounded Invoicing")
        self.minsize(900, 600)

        # Restore saved window geometry
        saved_geo = prefs.get("window_geometry", DEFAULT_GEOMETRY)
        self.geometry(saved_geo)
        self.bind("<Configure>", self._on_window_resize)
        self._resize_job = None

        self._dark_mode = tk.BooleanVar(value=False)

        if HAS_SV_TTK:
            sv_ttk.set_theme("light")

        container = ttk.Frame(self)
        container.pack(side="right", fill="both", expand=True)

        self._build_sidebar()

        self.views = {}
        for ViewClass in (NewClientView, NewInvoiceView, ClientsListView,
                          InvoicesListView, ClientDetailView, SettingsView):
            view = ViewClass(container, self)
            self.views[ViewClass.__name__] = view
            view.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.show_view("InvoicesListView")

        # Single global scroll handler — routes to the active view's canvas if it has one.
        # This catches ALL MouseWheel events regardless of which child widget is under
        # the pointer, which is the only reliable approach on macOS.
        self.bind_all("<MouseWheel>", self._global_scroll)
        self.bind_all("<Button-4>",   self._global_scroll)
        self.bind_all("<Button-5>",   self._global_scroll)
        self._current_view_name = "InvoicesListView"

    def _global_scroll(self, event):
        view = self.views.get(self._current_view_name)
        if view is None:
            return
        # Get the canvas from views that have one
        canvas = getattr(view, "_canvas", None) or getattr(view, "_scroll_canvas", None)
        if canvas is None:
            return
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
        elif event.delta:
            canvas.yview_scroll(int(-1 * event.delta), "units")

    def _build_sidebar(self):
        sidebar = ttk.Frame(self, width=160, padding=(10, 15))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="Grounded Invoicing",
                  font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(0, 12))

        nav_items = [
            ("New client",  "NewClientView"),
            ("New invoice", "NewInvoiceView"),
            ("Clients",     "ClientsListView"),
            ("Invoices",    "InvoicesListView"),
        ]

        for label, view_name in nav_items:
            btn = ttk.Button(sidebar, text=label,
                             command=lambda v=view_name: self.show_view(v))
            btn.pack(fill="x", pady=2)

        ttk.Frame(sidebar).pack(fill="y", expand=True)

        ttk.Button(sidebar, text="⚙  Settings",
                   command=lambda: self.show_view("SettingsView")).pack(fill="x", pady=(0, 6))

        if HAS_SV_TTK:
            toggle_frame = ttk.Frame(sidebar)
            toggle_frame.pack(fill="x", pady=(0, 4))
            ttk.Label(toggle_frame, text="☀", font=("Helvetica", 13)).pack(side="left")
            ttk.Checkbutton(
                toggle_frame,
                style="Switch.TCheckbutton",
                variable=self._dark_mode,
                command=self._apply_theme,
            ).pack(side="left", padx=4)
            ttk.Label(toggle_frame, text="☾", font=("Helvetica", 13)).pack(side="left")

    def _apply_theme(self):
        if HAS_SV_TTK:
            sv_ttk.set_theme("dark" if self._dark_mode.get() else "light")

    def _on_window_resize(self, event):
        # Debounce — only save after resizing stops for 500ms
        if event.widget is self:
            if self._resize_job:
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(500, self._save_geometry)

    def _save_geometry(self):
        prefs.set("window_geometry", self.geometry())

    def show_view(self, view_name, **kwargs):
        view = self.views[view_name]
        view.tkraise()
        self.update_idletasks()
        self._current_view_name = view_name
        if hasattr(view, "on_show"):
            view.on_show(**kwargs)
        self.update()


if __name__ == "__main__":
    app = App()
    app.mainloop()
