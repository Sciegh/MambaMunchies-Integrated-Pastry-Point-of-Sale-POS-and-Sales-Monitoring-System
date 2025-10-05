import os
import io
import csv
import math
import base64
import hashlib
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw, ImageFont

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# -------------------- Paths & Constants --------------------
BASE_DIR = r"E:\Downloads\3rdyr1stsem\Elective 3\MambaMunchies Integrated Pastry Point of Sale (POS) and Sales Monitoring System"
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "pastry_inventory.db") 
DB_FILE = "pastry_pos.db"
IMAGES_DIR = os.path.join(BASE_DIR, "Images")
os.makedirs(IMAGES_DIR, exist_ok=True)
RECEIPTS_DIR = os.path.join(BASE_DIR, "Receipts")
os.makedirs(RECEIPTS_DIR, exist_ok=True)
EXPORTS_DIR = os.path.join(BASE_DIR, "Exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

LOW_STOCK_THRESHOLD = 5
POS_GRID_COLS = 5
CARD_IMG_SIZE = (120, 90)
LOGO_SIZE = (36, 36)

# Pastel palette
COL_BG = "#fff7f8"  # background
COL_ACCENT = "#ff7aa2"  # primary pink
COL_ACCENT_DARK = "#e0668b"
COL_ACCENT_LIGHT = "#ffd1df"
COL_OK = "#76d39e"
COL_WARN = "#ffd97a"
COL_BAD = "#ffb3c1"
COL_TEXT = "#3a3a3a"

MAX_QTY_PER_PRODUCT = 10

# -------------------- Category -> Name list --------------------
CATEGORY_ITEMS = {
    "Cake": ["Banana Bread", "Chocolate Cake", "Red Velvet", "Carrot Cake", "Cheesecake"],
    "Bread": ["French Baguette", "Garlic Bread", "Pan de Sal", "Ciabatta"],
    "Cookie": ["Chocolate Chip", "Oatmeal Raisin", "Peanut Butter", "Sugar Cookie"],
    "Pastry": ["Croissant", "Danish", "Apple Turnover", "Puff Pastry"],
    "Pie": ["Apple Pie", "Blueberry Pie", "Pumpkin Pie"],
    "Donut": ["Glazed Donut", "Chocolate Donut", "Sugar Donut"],
    "Muffin": ["Blueberry Muffin", "Chocolate Muffin", "Banana Muffin"],
    "Other": ["Brownie", "Cupcake", "Macaron"],
}

# -------------------- Helper utils --------------------
def db_connect():
    return sqlite3.connect(DB_PATH)

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def money(v: float) -> str:
    try:
        return f"₱{float(v):,.2f}"
    except Exception:
        return "₱0.00"

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

ICON_CACHE = {}

def draw_icon(shape: str, size=(28, 28), fill=COL_ACCENT, stroke=COL_TEXT) -> ImageTk.PhotoImage:
    key = (shape, size)
    if key in ICON_CACHE:
        return ICON_CACHE[key]
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shape == "cart":
        # cart body
        d.rectangle([6, 10, w-6, h-10], outline=stroke, width=2)
        # handle
        d.line([6, 10, 12, 6], fill=stroke, width=2)
        # wheels
        d.ellipse([8, h-8, 12, h-4], outline=stroke, width=2, fill=fill)
        d.ellipse([w-12, h-8, w-8, h-4], outline=stroke, width=2, fill=fill)
    elif shape == "inventory":
        d.rectangle([6, 6, w-6, h-6], outline=stroke, width=2)
        d.line([6, (h//2), w-6, (h//2)], fill=stroke, width=2)
        d.line([w//2, 6, w//2, h-6], fill=stroke, width=2)
    elif shape == "report":
        d.rectangle([6, 6, w-10, h-6], outline=stroke, width=2)
        d.line([w-10, 10, w-6, 6], fill=stroke, width=2)
        d.line([w-10, 14, w-6, 10], fill=stroke, width=2)
        # bars
        d.rectangle([10, h-10, 14, h-6], fill=fill)
        d.rectangle([16, h-14, 20, h-6], fill=fill)
        d.rectangle([22, h-18, 26, h-6], fill=fill)
    elif shape == "users":
        d.ellipse([8, 6, 20, 18], outline=stroke, width=2, fill=fill)
        d.rectangle([8, 18, 22, h-6], outline=stroke, width=2)
    elif shape == "logout":
        d.rectangle([8, 6, 18, h-6], outline=stroke, width=2)
        d.polygon([(18, h//2 - 6), (26, h//2), (18, h//2 + 6)], outline=stroke, fill=fill)
        d.line([14, h//2, 22, h//2], fill=stroke, width=2)
    elif shape == "search":
        d.ellipse([6,6,18,18], outline=stroke, width=2)
        d.line([18,18,24,24], fill=stroke, width=2)
    elif shape == "plus":
        d.line([w//2, 6, w//2, h-6], fill=stroke, width=3)
        d.line([6, h//2, w-6, h//2], fill=stroke, width=3)
    elif shape == "minus":
        d.line([6, h//2, w-6, h//2], fill=stroke, width=3)
    elif shape == "bake":
        # cute cupcake
        d.polygon([(6, h-8), (w-6, h-8), (w-10, h-4), (10, h-4)], fill=COL_ACCENT)
        d.ellipse([8, 6, w-8, h-10], fill=COL_ACCENT_LIGHT, outline=stroke)
        d.ellipse([w//2-2, 4, w//2+2, 8], fill=COL_OK)
    else:
        d.rectangle([4,4,w-4,h-4], outline=stroke, width=2)
    ph = ImageTk.PhotoImage(img)
    ICON_CACHE[key] = ph
    return ph

# -------------------- DB setup/upgrade --------------------
def init_db():
    con = db_connect()
    cur = con.cursor()

    # Users
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('Admin','Staff')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Pastries
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pastries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Legacy Sales (line items without receipt grouping)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pastry_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            sale_time TEXT DEFAULT CURRENT_TIMESTAMP,
            staff_username TEXT NOT NULL,
            FOREIGN KEY (pastry_id) REFERENCES pastries(id)
        )
        """
    )

    # New: Receipts (transactions)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no INTEGER UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            staff_username TEXT NOT NULL,
            customer_name TEXT,
            subtotal REAL NOT NULL,
            discount REAL NOT NULL,
            tax REAL NOT NULL,
            total REAL NOT NULL,
            tendered REAL NOT NULL,
            change REAL NOT NULL
        )
        """
    )

    # New: Receipt items
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS receipt_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id INTEGER NOT NULL,
            pastry_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            unit_price REAL NOT NULL,
            qty INTEGER NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY (receipt_id) REFERENCES receipts(id),
            FOREIGN KEY (pastry_id) REFERENCES pastries(id)
        )
        """
    )

    # Seed admin
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            ("admin", hash_pw("admin123"), "Admin"),
        )

    con.commit()
    con.close()

# -------------------- Product image helpers --------------------
FONT_CACHE = None

def get_font(size=16):
    global FONT_CACHE
    try:
        if FONT_CACHE is None:
            FONT_CACHE = ImageFont.truetype("arial.ttf", size)
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        # Fallback font
        return ImageFont.load_default()

def load_product_image(name: str) -> ImageTk.PhotoImage:
    # Try PNG/JPG in IMAGES_DIR
    for ext in (".png", ".jpg", ".jpeg"):
        fp = os.path.join(IMAGES_DIR, name + ext)
        if os.path.exists(fp):
            try:
                img = Image.open(fp).convert("RGBA")
                img = img.resize(CARD_IMG_SIZE, Image.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception:
                pass
    # else make a pastel placeholder with initials
    bg = COL_ACCENT_LIGHT
    img = Image.new("RGBA", CARD_IMG_SIZE, bg)
    d = ImageDraw.Draw(img)
    initials = "".join([w[0] for w in name.split()[:2]]).upper() or "P"
    f = get_font(28)
    tw, th = d.textsize(initials, font=f)
    d.text(((CARD_IMG_SIZE[0]-tw)//2, (CARD_IMG_SIZE[1]-th)//2), initials, fill=COL_TEXT, font=f)
    # cupcake corner
    d.ellipse([4,4,22,22], fill=COL_ACCENT)
    return ImageTk.PhotoImage(img)

# -------------------- Styled ttk --------------------
def style_app(root: tk.Tk):
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
    style.map(
        "Accent.TButton",
        background=[("active", COL_ACCENT_DARK)],
    )

    style.configure("Soft.TButton", font=("Segoe UI", 10), padding=6)

    style.configure(
        "Treeview",
        background="white",
        foreground=COL_TEXT,
        fieldbackground="white",
        rowheight=26,
        font=("Segoe UI", 10),
    )
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    style.configure("TEntry", padding=4)
    style.configure("TCombobox", padding=4)

# -------------------- App --------------------
class App(tk.Tk):
    def __init__(self, username, role):
        super().__init__()
        self.username = username
        self.role = role

        self.title("🍰 MambaMunchies")
        self.geometry("1200x780")
        self.minsize(1920, 1080)

        for i in range(6):
            self.rowconfigure(i, weight=1)
        self.columnconfigure(0, weight=1)

        style_app(self)

        # Top bar
        top = ttk.Frame(self, padding=10)
        top.pack(side="top", fill="x")
        logo_img = Image.open("logo.jpg").resize((40, 40))
        self.logo_photo = ImageTk.PhotoImage(logo_img)
        ttk.Label(top, image=self.logo_photo, text="  MambaMunchies Bakery POS", compound="left", font=("Segoe UI", 16, "bold")).pack(side="left")

        ttk.Label(top, text=f"Signed in: {self.username} ({self.role})", font=("Segoe UI", 10, "bold")).pack(side="right")
        ttk.Button(top, text="Logout", style="Accent.TButton", command=self.logout).pack(side="right", padx=8)

        # Tabs with icons
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.inventory_tab = ttk.Frame(self.nb)
        self.pos_tab = ttk.Frame(self.nb)
        self.reports_tab = ttk.Frame(self.nb)
        self.nb.add(self.pos_tab, text="  POS  ")
        self.nb.add(self.inventory_tab, text="  Inventory  ")
        self.nb.add(self.reports_tab, text="  Reports  ")
        if self.role == "Admin":
            self.users_tab = ttk.Frame(self.nb)
            self.nb.add(self.users_tab, text="  Users  ")

        self.build_pos_tab()
        self.build_inventory_tab()
        self.build_reports_tab()
        if self.role == "Admin":
            self.build_users_tab()

        # Load
        self.load_inventory()
        self.refresh_catalog()
        self.refresh_reports()

        # Shortcuts
        self.bind("<Control-n>", lambda e: self.clear_cart())
        self.bind("<Control-p>", lambda e: self.charge())
        self.bind("<F5>", lambda e: self.refresh_catalog())

    def logout(self):
        self.destroy()
        LoginWindow()

    # ---------------- POS Tab ----------------
    def build_pos_tab(self):
        frm = self.pos_tab

        # Left: catalog; Right: cart
        left = ttk.Frame(frm)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ttk.Frame(frm)
        right.pack(side="right", fill="y")

        # Filters/search
        filt = ttk.Labelframe(left, text="🛒 Catalog")
        filt.pack(side="top", fill="x", padx=2, pady=2)
        self.pos_cat_var = tk.StringVar(value="All")
        cats = ["All"] + list(CATEGORY_ITEMS.keys())
        ttk.Label(filt, text="Category:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Combobox(filt, textvariable=self.pos_cat_var, values=cats, state="readonly", width=16).grid(row=0, column=1, padx=6, pady=6)

        self.pos_search_var = tk.StringVar()
        ttk.Label(filt, text="Search:").grid(row=0, column=2, padx=6)
        ttk.Entry(filt, textvariable=self.pos_search_var, width=26).grid(row=0, column=3, padx=6)
        ttk.Button(filt, text="Find", style="Soft.TButton", command=self.refresh_catalog).grid(row=0, column=4, padx=6)
        ttk.Button(filt, text="Show All", style="Soft.TButton", command=lambda: [self.pos_cat_var.set("All"), self.pos_search_var.set(""), self.refresh_catalog()]).grid(row=0, column=5, padx=6)

        # Catalog grid canvas (scrollable)
        self.catalog_canvas = tk.Canvas(left, bg=COL_BG, highlightthickness=0)
        self.catalog_frame = ttk.Frame(self.catalog_canvas)
        self.catalog_scroll = ttk.Scrollbar(left, orient="vertical", command=self.catalog_canvas.yview)
        self.catalog_canvas.configure(yscrollcommand=self.catalog_scroll.set)
        self.catalog_scroll.pack(side="right", fill="y")
        self.catalog_canvas.pack(side="left", fill="both", expand=True)
        self.catalog_canvas.create_window((0,0), window=self.catalog_frame, anchor="nw")
        self.catalog_frame.bind("<Configure>", lambda e: self.catalog_canvas.configure(scrollregion=self.catalog_canvas.bbox("all")))

        # Right: Cart
        cart_box = ttk.Labelframe(right, text="🧾 Cart")
        cart_box.pack(fill="y", padx=2, pady=2)

        cols = ("Item", "Price", "Qty", "Total")
        self.cart_tree = ttk.Treeview(cart_box, columns=cols, show="headings", height=18)
        for c in cols:
            self.cart_tree.heading(c, text=c)
        self.cart_tree.column("Item", width=180)
        self.cart_tree.column("Price", width=80, anchor="e")
        self.cart_tree.column("Qty", width=60, anchor="center")
        self.cart_tree.column("Total", width=100, anchor="e")
        self.cart_tree.pack(padx=6, pady=6)

        # Cart buttons
        btns = ttk.Frame(cart_box)
        btns.pack(fill="x", padx=6)
        ttk.Button(btns, text="+ Qty", style="Soft.TButton", command=self.cart_inc).pack(side="left", padx=3)
        ttk.Button(btns, text="- Qty", style="Soft.TButton", command=self.cart_dec).pack(side="left", padx=3)
        ttk.Button(btns, text="Remove", style="Soft.TButton", command=self.cart_remove).pack(side="left", padx=3)
        ttk.Button(btns, text="Clear Cart (Ctrl+N)", style="Soft.TButton", command=self.clear_cart).pack(side="right", padx=3)

        # Totals panel
        self.totals_frame = ttk.Frame(cart_box)
        self.totals_frame.pack(fill="x", padx=8, pady=6)

        self.subtotal_var = tk.DoubleVar(value=0.0)
        self.discount_var = tk.DoubleVar(value=0.0)
        self.tax_var = tk.DoubleVar(value=0.0)  # percent
        self.total_var = tk.DoubleVar(value=0.0)
        self.tender_var = tk.DoubleVar(value=0.0)
        self.change_var = tk.DoubleVar(value=0.0)
        self.customer_var = tk.StringVar()

        r = 0
        ttk.Label(self.totals_frame, text="Customer:").grid(row=r, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(self.totals_frame, textvariable=self.customer_var, width=22).grid(row=r, column=1, padx=4, pady=2, columnspan=3, sticky="w")
        r += 1
        ttk.Label(self.totals_frame, text="Subtotal:").grid(row=r, column=0, sticky="e", padx=4, pady=2)
        ttk.Label(self.totals_frame, textvariable=self.subtotal_var, name="subtotal_lbl").grid(row=r, column=1, sticky="w")
        r += 1
        # Discount dropdown
        self.discount_type_var = tk.StringVar(value="None")
        ttk.Label(self.totals_frame, text="Discount:").grid(row=r, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(
            self.totals_frame, textvariable=self.discount_type_var,
            values=["None", "Senior", "PWD"], state="readonly", width=12
        ).grid(row=r, column=1, sticky="w")

        # Fixed tax (3%)
        self.tax_var.set(3.0)
        ttk.Label(self.totals_frame, text="Tax:").grid(row=r, column=2, sticky="e", padx=4)
        ttk.Label(self.totals_frame, text="3%").grid(row=r, column=3, sticky="w")
        r += 1
        ttk.Label(self.totals_frame, text="Total:").grid(row=r, column=0, sticky="e", padx=4, pady=2)
        ttk.Label(self.totals_frame, textvariable=self.total_var, name="total_lbl", font=("Segoe UI", 14, "bold")).grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Label(self.totals_frame, text="Tendered:").grid(row=r, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(self.totals_frame, textvariable=self.tender_var, width=10).grid(row=r, column=1, sticky="w")
        ttk.Label(self.totals_frame, text="Change:").grid(row=r, column=2, sticky="e", padx=4)
        ttk.Label(self.totals_frame, textvariable=self.change_var, name="change_lbl").grid(row=r, column=3, sticky="w")

        # Action buttons
        act = ttk.Frame(cart_box)
        act.pack(fill="x", padx=6, pady=6)
        ttk.Button(act, text="Charge (Ctrl+P)", style="Accent.TButton", command=self.charge).pack(side="left", padx=4)
        ttk.Button(act, text="Print Last Receipt", style="Soft.TButton", command=self.print_last_receipt).pack(side="left", padx=4)

        self.update_totals()

    def refresh_catalog(self):
        # Clear current grid
        for w in self.catalog_frame.winfo_children():
            w.destroy()

        # Query pastries
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id, name, category, price, quantity FROM pastries ORDER BY name ASC")
        rows = cur.fetchall()
        con.close()

        # Apply filters
        cat = self.pos_cat_var.get()
        q = self.pos_search_var.get().strip().lower()
        items = []
        for pid, name, category, price, qty in rows:
            if cat != "All" and category != cat:
                continue
            if q and q not in name.lower():
                continue
            items.append((pid, name, category, price, qty))

        # Build cards
        r = c = 0
        self._card_images_keep = []
        for pid, name, category, price, qty in items:
            card = ttk.Frame(self.catalog_frame, padding=6)
            card.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            # image
            img = load_product_image(name)
            self._card_images_keep.append(img)
            img_lbl = ttk.Label(card, image=img)
            img_lbl.pack()
            # name + price
            name_lbl = ttk.Label(card, text=name, font=("Segoe UI", 10, "bold"))
            name_lbl.pack()
            price_lbl = ttk.Label(card, text=money(price))
            price_lbl.pack()
            # stock badge
            if qty < LOW_STOCK_THRESHOLD:
                ttk.Label(card, text=f"Low stock: {qty}", foreground="#8a1c1c").pack()
            # add buttons
            bt_frame = ttk.Frame(card)
            bt_frame.pack(pady=4)
            ttk.Button(bt_frame, text="Add 1", style="Soft.TButton", command=lambda _id=pid: self.add_to_cart(_id, 1)).pack(side="left", padx=2)
            ttk.Button(bt_frame, text="Add 5", style="Soft.TButton", command=lambda _id=pid: self.add_to_cart(_id, 5)).pack(side="left", padx=2)

            c += 1
            if c >= POS_GRID_COLS:
                c = 0
                r += 1

    # Cart operations
    def add_to_cart(self, pastry_id: int, qty: int):
        # Fetch product
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT name, price, quantity FROM pastries WHERE id=?", (pastry_id,))
        row = cur.fetchone()
        con.close()
        if not row:
            return
        name, price, stock = row

        # check if already in cart
        found = None
        for iid in self.cart_tree.get_children():
            vals = self.cart_tree.item(iid, "values")
            if vals and vals[0] == name:
                found = iid; break
        if found:
            cur_qty = int(self.cart_tree.item(found, "values")[2])
            new_qty = cur_qty + qty
            if new_qty > MAX_QTY_PER_PRODUCT:
                messagebox.showwarning("Quantity limit", f"Cannot add more than {MAX_QTY_PER_PRODUCT} units per product.")
                return
            if new_qty > stock:
                messagebox.showwarning("Stock", f"Not enough stock for {name}. Available: {stock}.")
                return
            self.cart_tree.item(found, values=(name, f"{price:.2f}", new_qty, f"{price*new_qty:.2f}"))
        else:
            if qty > MAX_QTY_PER_PRODUCT:
                messagebox.showwarning("Quantity limit", f"Cannot add more than {MAX_QTY_PER_PRODUCT} units per product.")
                return
            if qty > stock:
                messagebox.showwarning("Stock", f"Not enough stock for {name}. Available: {stock}.")
                return
            self.cart_tree.insert("", "end", values=(name, f"{price:.2f}", qty, f"{price*qty:.2f}"), tags=(str(pastry_id),))
        self.update_totals()

    def cart_inc(self):
        sel = self.cart_tree.selection()
        if not sel: return
        iid = sel[0]
        name, price_s, qty_s, total_s = self.cart_tree.item(iid, "values")
        price = float(price_s)
        qty = int(qty_s) + 1
        if qty > MAX_QTY_PER_PRODUCT:
            messagebox.showwarning("Quantity limit", f"Cannot have more than {MAX_QTY_PER_PRODUCT} units per product.")
            return
        # stock check
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT quantity FROM pastries WHERE name=?", (name,))
        stock = cur.fetchone()[0]
        con.close()
        if qty > stock:
            messagebox.showwarning("Stock", f"Not enough stock for {name}. Available: {stock}.")
            return
        self.cart_tree.item(iid, values=(name, f"{price:.2f}", qty, f"{price*qty:.2f}"))
        self.update_totals()

    def cart_dec(self):
        sel = self.cart_tree.selection()
        if not sel: return
        iid = sel[0]
        name, price_s, qty_s, total_s = self.cart_tree.item(iid, "values")
        price = float(price_s)
        qty = int(qty_s) - 1
        if qty <= 0:
            self.cart_tree.delete(iid)
        else:
            self.cart_tree.item(iid, values=(name, f"{price:.2f}", qty, f"{price*qty:.2f}"))
        self.update_totals()

    def cart_remove(self):
        sel = self.cart_tree.selection()
        if not sel: return
        self.cart_tree.delete(sel[0])
        self.update_totals()

    def clear_cart(self):
        self.cart_tree.delete(*self.cart_tree.get_children())
        self.discount_type_var.set("None")
        self.tax_var.set(3.0)
        self.tender_var.set(0.0)
        self.change_var.set(0.0)
        self.customer_var.set("")
        self.update_totals()

    def update_totals(self):
        subtotal = 0.0
        for iid in self.cart_tree.get_children():
            vals = self.cart_tree.item(iid, "values")
            subtotal += float(vals[1]) * int(vals[2])

        # Discount rules
        discount_type = self.discount_type_var.get()
        if discount_type in ("Senior", "PWD"):
            discount = subtotal * 0.20   # 20% discount
        else:
            discount = 0.0

        # Always 3% tax
        tax_pct = 3.0

        taxed = max(0.0, (subtotal - discount)) * (tax_pct/100.0)
        total = max(0.0, subtotal - discount + taxed)
        tender = float(self.tender_var.get() or 0.0)
        change = max(0.0, tender - total)
        self.subtotal_var.set(subtotal)
        self.total_var.set(total)
        self.change_var.set(change)
        # Update labels by widget name
        self.totals_frame.nametowidget("subtotal_lbl").configure(text=money(subtotal))
        self.totals_frame.nametowidget("total_lbl").configure(text=money(total))
        self.totals_frame.nametowidget("change_lbl").configure(text=money(change))

    def next_receipt_no(self, cur):
        cur.execute("SELECT COALESCE(MAX(receipt_no), 1000) FROM receipts")
        return (cur.fetchone()[0] or 1000) + 1

    def charge(self):
        # Gather cart lines
        lines = []
        for iid in self.cart_tree.get_children():
            name, price_s, qty_s, total_s = self.cart_tree.item(iid, "values")
            qty = int(qty_s)
            price = float(price_s)
            lines.append((name, price, qty))
        if not lines:
            messagebox.showwarning("Cart", "Cart is empty.")
            return
        subtotal = self.subtotal_var.get()
        discount = float(self.discount_var.get() or 0.0)
        tax = float(self.tax_var.get() or 0.0)
        total = self.total_var.get()
        tender = float(self.tender_var.get() or 0.0)
        if tender + 1e-6 < total:
            messagebox.showwarning("Payment", "Tendered amount is less than total.")
            return
        change = tender - total

        con = db_connect(); cur = con.cursor()
        try:
            # Map item names to pastry IDs and stock checks
            items = []
            for name, price, qty in lines:
                cur.execute("SELECT id, quantity FROM pastries WHERE name=?", (name,))
                row = cur.fetchone()
                if not row:
                    raise Exception(f"Item not found: {name}")
                pid, stock = row
                if qty > stock:
                    raise Exception(f"Not enough stock for {name}. Available: {stock}.")
                items.append((pid, name, price, qty))

            # Create receipt
            receipt_no = self.next_receipt_no(cur)
            cur.execute(
                """
                INSERT INTO receipts (receipt_no, created_at, staff_username, customer_name,
                                      subtotal, discount, tax, total, tendered, change)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    receipt_no,
                    now_iso(),
                    self.username,
                    self.customer_var.get().strip() or None,
                    subtotal,
                    discount,
                    tax,
                    total,
                    tender,
                    change,
                ),
            )
            rid = cur.lastrowid

            # Create items + update stock + legacy sales rows
            for pid, name, price, qty in items:
                line_total = price * qty
                cur.execute(
                    "INSERT INTO receipt_items (receipt_id, pastry_id, name, unit_price, qty, line_total) VALUES (?,?,?,?,?,?)",
                    (rid, pid, name, price, qty, line_total),
                )
                cur.execute(
                    "UPDATE pastries SET quantity = quantity - ?, last_updated=? WHERE id=?",
                    (qty, now_iso(), pid),
                )
                # legacy
                cur.execute(
                    "INSERT INTO sales (pastry_id, qty, unit_price, total, sale_time, staff_username) VALUES (?,?,?,?,?,?)",
                    (pid, qty, price, line_total, now_iso(), self.username),
                )

            con.commit()
        except Exception as e:
            con.rollback()
            con.close()
            messagebox.showerror("Charge failed", str(e))
            return
        con.close()

        self.last_receipt_no = receipt_no
        self.load_inventory()
        self.refresh_catalog()
        self.refresh_reports()
        self.clear_cart()
        messagebox.showinfo("Payment complete", f"Receipt #{receipt_no}\nChange: {money(change)}")

        # Auto print
        self.save_receipt_to_txt(receipt_no)

    def print_last_receipt(self):
        if not hasattr(self, "last_receipt_no"):
            messagebox.showinfo("Receipt", "No receipt yet.")
            return
        self.save_receipt_to_txt(self.last_receipt_no)

    def save_receipt_to_txt(self, receipt_no: int):
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id, created_at, staff_username, customer_name, subtotal, discount, tax, total, tendered, change FROM receipts WHERE receipt_no=?", (receipt_no,))
        r = cur.fetchone()
        if not r:
            con.close(); return
        rid, created_at, staff, cust, subtotal, disc, tax, total, tender, change = r
        cur.execute("SELECT name, unit_price, qty, line_total FROM receipt_items WHERE receipt_id=?", (rid,))
        items = cur.fetchall()
        con.close()

        path = os.path.join(RECEIPTS_DIR, f"Receipt_{receipt_no}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("MambaMunchies Bakery POS\n")
            f.write(f"Receipt #: {receipt_no}\n")
            f.write(f"Date: {created_at}\n")
            f.write(f"Staff: {staff}\n")
            if cust:
                f.write(f"Customer: {cust}\n")
            f.write("\nItems:\n")
            for name, up, qty, lt in items:
                f.write(f" - {name}  x{qty}  @ {money(up)}  = {money(lt)}\n")
            f.write("\n")
            f.write(f"Subtotal: {money(subtotal)}\n")
            f.write(f"Discount: {money(disc)}\n")
            f.write(f"Tax ({tax:.2f}%): {money(max(0,(subtotal-disc)*tax/100))}\n")
            f.write(f"TOTAL: {money(total)}\n")
            f.write(f"Tendered: {money(tender)}\n")
            f.write(f"Change: {money(change)}\n")
        messagebox.showinfo("Receipt saved", f"Saved to:\n{path}")

    # ---------------- Inventory (kept from v2, styled) ----------------
    def build_inventory_tab(self):
        frm = self.inventory_tab
        top = ttk.Frame(frm)
        top.pack(fill="x", pady=6)
        ttk.Button(top, text="Add Pastry", style="Accent.TButton", command=self.add_pastry).pack(side="left", padx=3)
        ttk.Button(top, text="Edit", style="Soft.TButton", command=self.edit_pastry).pack(side="left", padx=3)
        ttk.Button(top, text="Delete", style="Soft.TButton", command=self.delete_pastry).pack(side="left", padx=3)
        ttk.Button(top, text="Export CSV", style="Soft.TButton", command=self.export_inventory).pack(side="right", padx=3)

        cols = ("ID","Name","Category","Price","Quantity","Last Updated")
        self.inv_tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c in cols:
            self.inv_tree.heading(c, text=c)
        self.inv_tree.column("ID", width=40)
        self.inv_tree.column("Price", anchor="e")
        self.inv_tree.column("Quantity", anchor="center")
        self.inv_tree.pack(fill="both", expand=True, padx=6, pady=6)

    def load_inventory(self):
        for i in getattr(self,"inv_tree",[]).get_children():
            self.inv_tree.delete(i)
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id,name,category,price,quantity,last_updated FROM pastries ORDER BY name")
        for row in cur.fetchall():
            self.inv_tree.insert("", "end", values=row)
        con.close()

    def add_pastry(self):
        PastryForm(self, None)

    def edit_pastry(self):
        sel = self.inv_tree.selection()
        if not sel: return
        vals = self.inv_tree.item(sel[0],"values")
        PastryForm(self, vals[0])

    def delete_pastry(self):
        sel = self.inv_tree.selection()
        if not sel: return
        pid = self.inv_tree.item(sel[0],"values")[0]
        if messagebox.askyesno("Delete","Delete this pastry?"):
            con = db_connect(); cur = con.cursor()
            cur.execute("DELETE FROM pastries WHERE id=?", (pid,))
            con.commit(); con.close()
            self.load_inventory(); self.refresh_catalog()

    def export_inventory(self):
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id,name,category,price,quantity,last_updated FROM pastries")
        rows = cur.fetchall(); con.close()
        path = os.path.join(EXPORTS_DIR,f"Inventory_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        with open(path,"w",newline="",encoding="utf-8") as f:
            csv.writer(f).writerows([["ID","Name","Category","Price","Quantity","Last Updated"]]+rows)
        messagebox.showinfo("Exported", f"Saved to {path}")

    # ---------------- Reports Tab ----------------
    def build_reports_tab(self):
        frm = self.reports_tab
        top = ttk.Frame(frm)
        top.pack(fill="x", pady=6)
        self.report_type_var = tk.StringVar(value="Monthly")
        ttk.Label(top, text="Report Type:").pack(side="left", padx=4)
        rep_type_cb = ttk.Combobox(top, textvariable=self.report_type_var, values=["Weekly", "Monthly"], state="readonly", width=10)
        rep_type_cb.pack(side="left", padx=4)
        rep_type_cb.bind("<<ComboboxSelected>>", self.on_report_type_change)
        self.rep_from = tk.StringVar()
        self.rep_to = tk.StringVar()
        ttk.Label(top, text="From:").pack(side="left")
        self.rep_from_entry = ttk.Entry(top, textvariable=self.rep_from, width=12)
        self.rep_from_entry.pack(side="left", padx=3)
        ttk.Label(top, text="To:").pack(side="left")
        self.rep_to_entry = ttk.Entry(top, textvariable=self.rep_to, width=12)
        self.rep_to_entry.pack(side="left", padx=3)
        ttk.Button(top, text="Filter", style="Accent.TButton", command=self.refresh_reports).pack(side="left", padx=6)
        ttk.Button(top, text="Export to CSV", command=self.export_reports_csv).pack(side="left", padx=6)
        self.rep_tree = ttk.Treeview(frm, columns=("Date","Receipt#","Staff","Customer","Total"), show="headings")
        for c in ("Date","Receipt#","Staff","Customer","Total"):
            self.rep_tree.heading(c,text=c)
        self.rep_tree.column("Date", width=160)
        self.rep_tree.column("Total", anchor="e")
        self.rep_tree.pack(fill="both", expand=True, padx=6, pady=6)
        # Initialize date range based on default report type
        self.set_report_date_range()

    def on_report_type_change(self, event=None):
        self.set_report_date_range()
        self.refresh_reports()

    def set_report_date_range(self):
        today = datetime.now().date()
        if self.report_type_var.get() == "Weekly":
            start = today - timedelta(days=today.weekday())  # Monday this week
            end = start + timedelta(days=6)  # Sunday
        else:  # Monthly
            start = today.replace(day=1)
            # last day of month
            next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = next_month - timedelta(days=1)
        self.rep_from.set(start.strftime("%Y-%m-%d"))
        self.rep_to.set(end.strftime("%Y-%m-%d"))

    def refresh_reports(self):
        if not hasattr(self,"rep_tree"): return
        for i in self.rep_tree.get_children():
            self.rep_tree.delete(i)
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT created_at,receipt_no,staff_username,COALESCE(customer_name,''),total FROM receipts WHERE date(created_at) BETWEEN ? AND ? ORDER BY created_at DESC",(self.rep_from.get(),self.rep_to.get()))
        for row in cur.fetchall():
            self.rep_tree.insert("","end",values=row)
        con.close()

    def export_reports_csv(self):
        if not hasattr(self, "rep_tree"):
            return

        import os
        from datetime import datetime

        # Ensure "Exports" folder exists
        os.makedirs("Exports", exist_ok=True)

        # Auto filename with timestamp
        filename = f"Exports/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # Get headings
        cols = ("Date", "Receipt#", "Staff", "Customer", "Total")

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)  # header

                # Write rows from Treeview
                for row_id in self.rep_tree.get_children():
                    values = self.rep_tree.item(row_id)["values"]
                    writer.writerow(values)

            messagebox.showinfo("Export Successful", f"Report exported to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))



    # ---------------- Users Tab ----------------
    def build_users_tab(self):
        frm = self.users_tab
        top = ttk.Frame(frm)
        top.pack(fill="x", pady=6)
        ttk.Button(top, text="Add User", style="Accent.TButton", command=self.add_user).pack(side="left", padx=3)
        ttk.Button(top, text="Delete User", style="Soft.TButton", command=self.delete_user).pack(side="left", padx=3)
        self.usr_tree = ttk.Treeview(frm, columns=("ID","Username","Role","Created"), show="headings")
        for c in ("ID","Username","Role","Created"):
            self.usr_tree.heading(c,text=c)
        self.usr_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.load_users()

    def load_users(self):
        for i in self.usr_tree.get_children():
            self.usr_tree.delete(i)
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id,username,role,created_at FROM users")
        for row in cur.fetchall():
            self.usr_tree.insert("","end",values=row)
        con.close()

    def add_user(self):
        UserForm(self)

    def delete_user(self):
        sel = self.usr_tree.selection()
        if not sel: return
        uid = self.usr_tree.item(sel[0],"values")[0]
        if messagebox.askyesno("Delete","Delete this user?"):
            con = db_connect(); cur = con.cursor()
            cur.execute("DELETE FROM users WHERE id=?",(uid,))
            con.commit(); con.close(); self.load_users()

# ---------------- Pastry Form ----------------
class PastryForm(tk.Toplevel):
    def __init__(self, master:App, pastry_id):
        super().__init__(master)
        self.pastry_id = pastry_id
        self.title("Add / Edit Pastry")
        self.geometry("400x360")
        self.resizable(True, True)

                # Category selection
        ttk.Label(self, text="Category:").pack(pady=4)
        self.category = tk.StringVar()
        self.cat_cb = ttk.Combobox(self, textvariable=self.category,
                                   values=list(CATEGORY_ITEMS.keys()), state="readonly")
        self.cat_cb.pack(fill="x", padx=6)

        # Product selection (depends on category)
        ttk.Label(self, text="Name:").pack(pady=4)
        self.name = tk.StringVar()
        self.product_cb = ttk.Combobox(self, textvariable=self.name, state="readonly")
        self.product_cb.pack(fill="x", padx=6)

        # Update products when category changes
        def update_products(event):
            cat = self.category.get()
            products = CATEGORY_ITEMS.get(cat, [])
            self.product_cb["values"] = products
            if products:
                self.product_cb.current(0)  # auto-select first item

        self.cat_cb.bind("<<ComboboxSelected>>", update_products)

        ttk.Label(self,text="Price:").pack(pady=4)
        self.price=tk.DoubleVar(value=5.00); ttk.Entry(self,textvariable=self.price).pack(fill="x",padx=6)
        ttk.Label(self,text="Quantity:").pack(pady=4)
        self.qty=tk.IntVar(value=1); ttk.Entry(self,textvariable=self.qty).pack(fill="x",padx=6)
        ttk.Button(self,text="Save",style="Accent.TButton",command=self.save).pack(pady=8)
        if pastry_id:
            con=db_connect();cur=con.cursor();cur.execute("SELECT name,category,price,quantity FROM pastries WHERE id=?",(pastry_id,))
            r=cur.fetchone();con.close()
            if r: self.name.set(r[0]); self.cat.set(r[1]); self.price.set(r[2]); self.qty.set(r[3])

 # --------------------------------------------------------
    def save(self):
        name = self.name.get().strip()
        category = self.category.get()
        try:
            price_val = float(self.price.get())
            qty_val = int(self.qty.get())
        except Exception:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values for price and quantity.")
            return

        # ---------------- Validations ----------------
        if not category:
            messagebox.showwarning("Missing Category", "Please select a category.")
            return
        if not name:
            messagebox.showwarning("Missing Name", "Please select a pastry name.")
            return
        if price_val < 5:
            messagebox.showwarning("Invalid Price", "Minimum price is ₱5.00.")
            return
        if qty_val < 1:
            messagebox.showwarning("Invalid Quantity", "Quantity must be at least 1.")
            return

        con = db_connect()
        cur = con.cursor()

        # ---------------- Duplicate Check ----------------
        cur.execute("SELECT id FROM pastries WHERE name=? COLLATE NOCASE", (name,))
        existing = cur.fetchone()
        if existing and (not self.pastry_id or existing[0] != self.pastry_id):
            messagebox.showwarning("Duplicate Item", f"'{name}' already exists in the inventory.")
            con.close()
            return

        # ---------------- Save or Update ----------------
        if self.pastry_id:
            cur.execute(
                "UPDATE pastries SET name=?, category=?, price=?, quantity=?, last_updated=? WHERE id=?",
                (name, category, price_val, qty_val, now_iso(), self.pastry_id),
            )
        else:
            cur.execute(
                "INSERT INTO pastries (name, category, price, quantity, date_added, last_updated) VALUES (?,?,?,?,?,?)",
                (name, category, price_val, qty_val, now_iso(), now_iso()),
            )

        con.commit()
        con.close()

        messagebox.showinfo("Success", f"'{name}' saved successfully!")
        self.destroy()
        self.master.load_inventory()
        self.master.refresh_catalog()

# ---------------- User Form ----------------
class UserForm(tk.Toplevel):
    def __init__(self, master:App):
        super().__init__(master)
        self.title("Add User"); self.geometry("280x220")
        self.username=tk.StringVar(); self.password=tk.StringVar(); self.role=tk.StringVar(value="Staff")
        ttk.Label(self,text="Username:").pack(pady=4); ttk.Entry(self,textvariable=self.username).pack(fill="x",padx=6)
        ttk.Label(self,text="Password:").pack(pady=4); ttk.Entry(self,textvariable=self.password,show="*").pack(fill="x",padx=6)
        ttk.Label(self,text="Role:").pack(pady=4); ttk.Combobox(self,textvariable=self.role,values=["Admin","Staff"],state="readonly").pack(fill="x",padx=6)
        ttk.Button(self,text="Save",style="Accent.TButton",command=self.save).pack(pady=8)

    def save(self):
        if not self.username.get() or not self.password.get(): return
        con=db_connect();cur=con.cursor()
        cur.execute("INSERT INTO users (username,password_hash,role) VALUES (?,?,?)",(self.username.get(),hash_pw(self.password.get()),self.role.get()))
        con.commit();con.close(); self.destroy(); self.master.load_users()

# ---------------- Login Window ----------------
class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🍰 MambaMunchies — Login")
        self.geometry("500x350")

        title = ttk.Label(self, text="MambaMunchies", font=("Segoe UI", 16, "bold"))
        title.pack(pady=(10, 5))

        logo_img = Image.open("logo.jpg").resize((120, 120)) 
        self.logo_photo = ImageTk.PhotoImage(logo_img)
        ttk.Label(self, image=self.logo_photo).pack(pady=6)

        self.user=tk.StringVar(); self.pw=tk.StringVar()
        ttk.Label(self,text="Username:").pack(pady=2); ttk.Entry(self,textvariable=self.user).pack(fill="x",padx=30)
        ttk.Label(self,text="Password:").pack(pady=2); ttk.Entry(self,textvariable=self.pw,show="*").pack(fill="x",padx=30)
        ttk.Button(self,text="Login",style="Accent.TButton",command=self.do_login).pack(pady=10)

    def do_login(self):
        con=db_connect();cur=con.cursor()
        cur.execute("SELECT role,password_hash FROM users WHERE username=?",(self.user.get(),))
        r=cur.fetchone();con.close()
        if r and r[1]==hash_pw(self.pw.get()):
            self.destroy(); App(self.user.get(),r[0]).mainloop()
        else:
            messagebox.showerror("Login","Invalid credentials")



# ---------------- Main ----------------
if __name__=="__main__":
    init_db(); LoginWindow().mainloop()
