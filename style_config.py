import tkinter as tk
from tkinter import ttk

from colors import (
    COL_BG,
    COL_TEXT,
    COL_ACCENT,
    COL_ACCENT_LIGHT,
    COL_ACCENT_DARK
)

# -------------------- Styled ttk --------------------
def style_app(root: tk.Tk):
    """Apply consistent ttk styling across the application."""
    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=COL_BG)

    style.configure("TFrame", background=COL_BG)
    style.configure("TLabelframe", background=COL_BG, relief="groove")
    style.configure("TLabelframe.Label", background=COL_BG, foreground=COL_TEXT, font=("Segoe UI", 11, "bold"))
    style.configure("TLabel", background=COL_BG, foreground=COL_TEXT, font=("Segoe UI", 10))

    # Accent Buttons
    style.configure(
        "Accent.TButton",
        font=("Segoe UI", 10, "bold"),
        background=COL_ACCENT,
        foreground="white",
        padding=8,
        borderwidth=0,
        focusthickness=3,
        focuscolor=COL_ACCENT_LIGHT,
    )
    style.map("Accent.TButton", background=[("active", COL_ACCENT_DARK)])

    # Soft Buttons
    style.configure("Soft.TButton", font=("Segoe UI", 10), padding=6)

    # Treeview Styles
    style.configure(
        "Treeview",
        background="white",
        foreground=COL_TEXT,
        fieldbackground="white",
        rowheight=26,
        font=("Segoe UI", 10),
    )
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    # Inputs
    style.configure("TEntry", padding=4)
    style.configure("TCombobox", padding=4)
