import os
import io
import csv
import math
import base64
import hashlib
import sqlite3
import subprocess
import qrcode, io
from reportlab.lib.utils import ImageReader
from categories import CATEGORY_ITEMS
from database_setup import init_db
from utils import *
from style_config import style_app
from colors import *
from login_window import LoginWindow
from pastry_form import PastryForm
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw, ImageFont

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import utils as rl_utils
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Table, TableStyle, Paragraph, Image as RLImage, Spacer
    from reportlab.lib import colors as rl_colors
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

try:
    import qrcode
    QRCODE_AVAILABLE = True
except Exception:
    QRCODE_AVAILABLE = False

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

MAX_QTY_PER_PRODUCT = 10

# -------------------- Product image helpers --------------------
FONT_CACHE = None

def get_font(size=16):
    global FONT_CACHE
    try:
        if FONT_CACHE is None:
            FONT_CACHE = ImageFont.truetype("arial.ttf", size)
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def load_product_image(name: str) -> ImageTk.PhotoImage:
    for ext in (".png", ".jpg", ".jpeg"):
        fp = os.path.join(IMAGES_DIR, name + ext)
        if os.path.exists(fp):
            try:
                img = Image.open(fp).convert("RGBA")
                img = img.resize(CARD_IMG_SIZE, Image.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception:
                pass
    bg = COL_ACCENT_LIGHT
    img = Image.new("RGBA", CARD_IMG_SIZE, bg)
    d = ImageDraw.Draw(img)
    initials = "".join([w[0] for w in name.split()[:2]]).upper() or "P"
    f = get_font(28)
    tw, th = d.textsize(initials, font=f)
    d.text(((CARD_IMG_SIZE[0]-tw)//2, (CARD_IMG_SIZE[1]-th)//2), initials, fill=COL_TEXT, font=f)
    d.ellipse([4,4,22,22], fill=COL_ACCENT)
    return ImageTk.PhotoImage(img)

# -------------------- App --------------------
class App(tk.Tk):
    def __init__(self, username, role):
        super().__init__()
        self.username = username
        self.role = role

        self.title("🍰 MambaMunchies")
        self.geometry("1200x780")
        self.minsize(1520, 880)

        for i in range(6):
            self.rowconfigure(i, weight=1)
        self.columnconfigure(0, weight=1)

        style_app(self)

        # Top bar
        top = ttk.Frame(self, padding=10)
        top.pack(side="top", fill="x")
        # load logo if present
        logo_fp = os.path.join(BASE_DIR, "logo.jpg")
        try:
            logo_img = Image.open(logo_fp).resize((40, 40))
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            ttk.Label(top, image=self.logo_photo, text="  MambaMunchies Bakery POS", compound="left", font=("Segoe UI", 16, "bold")).pack(side="left")
        except Exception:
            ttk.Label(top, text="  MambaMunchies Bakery POS", font=("Segoe UI", 16, "bold")).pack(side="left")

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

    def add_pastry(self):
        PastryForm(self, None)

    def edit_pastry(self):
        sel = self.inv_tree.selection()
        if not sel:
            return
        vals = self.inv_tree.item(sel[0], "values")
        PastryForm(self, vals[0])

    def delete_pastry(self):
        """Delete the selected pastry record from the inventory."""
        sel = self.inv_tree.selection()
        if not sel:
            return

        vals = self.inv_tree.item(sel[0], "values")
        pastry_id = vals[0]
        pastry_name = vals[1]

        from tkinter import messagebox
        if messagebox.askyesno("Confirm Delete", f"Delete pastry '{pastry_name}'?"):
            from utils import db_connect
            con = db_connect()
            cur = con.cursor()
            cur.execute("DELETE FROM pastries WHERE id=?", (pastry_id,))
            con.commit()
            con.close()
            self.refresh_inventory()
            messagebox.showinfo("Deleted", f"'{pastry_name}' was deleted successfully.")

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
        self.cart_tree = ttk.Treeview(cart_box, columns=cols, show="headings", height=12)
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
        discount_box = ttk.Combobox(
            self.totals_frame, textvariable=self.discount_type_var,
            values=["None", "Senior", "PWD"], state="readonly", width=12
        )
        discount_box.grid(row=r, column=1, sticky="w")
        discount_box.bind("<<ComboboxSelected>>", lambda e: self.update_totals())


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
            # stock badge (improved visibility)
            if qty < LOW_STOCK_THRESHOLD:
                ttk.Label(card, text=f"⚠️ Low stock: {qty}", foreground="#8a1c1c", font=("Segoe UI", 9, "bold")).pack()
            else:
                ttk.Label(card, text=f"In stock: {qty}", foreground="#2c7a2c", font=("Segoe UI", 9)).pack()
            # add buttons
            bt_frame = ttk.Frame(card)
            bt_frame.pack(pady=4)
            ttk.Button(bt_frame, text="Add 1", style="Soft.TButton", command=lambda _id=pid: self.add_to_cart(_id, 1)).pack(side="left", padx=2)
            ttk.Button(bt_frame, text="Add 5", style="Soft.TButton", command=lambda _id=pid: self.add_to_cart(_id, 5)).pack(side="left", padx=2)

            c += 1
            if c >= POS_GRID_COLS:
                c = 0
                r += 1

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

        self.discount_var.set(discount)

        # Always 3% tax
        tax_pct = 3.0

        taxed = max(0.0, (subtotal - discount)) * (tax_pct/100.0)
        total = max(0.0, subtotal - discount + taxed)
        tender = float(self.tender_var.get() or 0.0)
        change = max(0.0, tender - total)
        self.subtotal_var.set(subtotal)
        self.total_var.set(total)
        self.change_var.set(change)
        self.discount_var.set(discount)
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

        # Save receipt as PDF (new behavior)
        self.save_receipt_to_pdf(receipt_no)

    def print_last_receipt(self):
        if not hasattr(self, "last_receipt_no"):
            messagebox.showinfo("Receipt", "No receipt yet.")
            return
        self.save_receipt_to_pdf(self.last_receipt_no)

    def save_receipt_to_pdf(self, receipt_no: int):
        if not REPORTLAB_AVAILABLE:
            self.save_receipt_to_txt(receipt_no)
            messagebox.showwarning("Dependency missing", "reportlab is required to create PDF receipts. Saved as TXT instead. To enable PDF receipts run: pip install reportlab qrcode pillow")
            return

        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id, created_at, staff_username, customer_name, subtotal, discount, tax, total, tendered, change FROM receipts WHERE receipt_no=?", (receipt_no,))
        r = cur.fetchone()
        if not r:
            con.close(); return
        rid, created_at, staff, cust, subtotal, disc, tax, total, tender, change = r
        cur.execute("SELECT name, unit_price, qty, line_total FROM receipt_items WHERE receipt_id=?", (rid,))
        items = cur.fetchall()
        con.close()

        filename = os.path.join(RECEIPTS_DIR, f"Receipt_{receipt_no}.pdf")
        c = rl_canvas.Canvas(filename, pagesize=A4)
        w, h = A4
        y = h - 40*mm
        
        # --- Logo ---
        logo_fp = os.path.join(BASE_DIR, "logo.jpg")
        logo_height = 0
        if os.path.exists(logo_fp):
            try:
                img = rl_utils.ImageReader(logo_fp)
                iw, ih = img.getSize()
                aspect = ih / iw
                draw_w = 35*mm
                draw_h = draw_w * aspect
                c.drawImage(img, 20*mm, y - draw_h, width=draw_w, height=draw_h, mask='auto')
                logo_height = draw_h + 10
                y -= logo_height
            except Exception as e:
                print("Logo error:", e)

        # --- Header ---
        y -= logo_height
        c.setFont("Helvetica-Bold", 16)
        c.drawString(60*mm, y, "MambaMunchies Bakery")
        c.setFont("Helvetica", 9)
        c.drawString(60*mm, y - 12, f"Receipt #: {receipt_no}")
        c.drawString(60*mm, y - 24, f"Date: {created_at}")
        c.drawString(60*mm, y - 36, f"Staff: {staff}")
        if cust:
            c.drawString(60*mm, y - 48, f"Customer: {cust}")
        y -= 70

        # --- Table ---
        data = [["Item", "Unit", "Qty", "Total"]] + [[n, money(p), str(q), money(t)] for n, p, q, t in items]
        tbl = Table(data, colWidths=[80*mm, 30*mm, 20*mm, 30*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), rl_colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.25, rl_colors.grey),
            ("FONT", (0,0), (-1,0), "Helvetica-Bold")
        ]))
        table_h = len(data) * 12
        tbl.wrapOn(c, w, h)
        tbl.drawOn(c, 20*mm, y - table_h)
        y -= table_h + 20

        # --- Totals ---
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20*mm, y, f"Subtotal: {money(subtotal)}")
        c.drawString(20*mm, y - 12, f"Discount: {money(disc)}")
        c.drawString(20*mm, y - 24, f"Tax: {money(tax)}")
        c.drawString(20*mm, y - 36, f"Total: {money(total)}")
        c.drawString(20*mm, y - 48, f"Tendered: {money(tender)}")
        c.drawString(20*mm, y - 60, f"Change: {money(change)}")
        y -= 80

        # --- QR Code ---
        try:
            qr_data = {
                "receipt_no": receipt_no,
                "date": created_at,
                "total": total,
                "items": [{"name": i[0], "qty": i[2]} for i in items]
            }
            qr = qrcode.QRCode(box_size=3, border=1)
            qr.add_data(str(qr_data))
            qr.make(fit=True)
    
            # Generate black-on-white QR
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            buf.seek(0)
    
            c.drawImage(ImageReader(buf), 160*mm, 100*mm, width=35*mm, height=35*mm)
            c.setFont("Helvetica", 8)
            c.drawString(160*mm, 95*mm, "Scan for summary")
            print(f"✅ QR code successfully added to receipt #{receipt_no}")
        except Exception as e:
            print("⚠️ QR Error:", e)

        c.showPage()
        c.save()

        # Auto-open
        try:
            if os.name == 'nt':
                os.startfile(filename)
            else:
                subprocess.Popen(['xdg-open', filename])
        except Exception:
            pass

        messagebox.showinfo("Receipt PDF", f"Receipt saved to: {filename}")

    # ---------------- Inventory ----------------
    def build_inventory_tab(self):
        frm = self.inventory_tab
        top = ttk.Frame(frm)
        top.pack(fill="x", pady=6)
        ttk.Button(top, text="Add Pastry", style="Accent.TButton", command=self.add_pastry).pack(side="left", padx=3)
        ttk.Button(top, text="Edit", style="Soft.TButton", command=self.edit_pastry).pack(side="left", padx=3)
        ttk.Button(top, text="Delete", style="Soft.TButton", command=self.delete_pastry).pack(side="left", padx=3)

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
        ttk.Button(top, text="Export to PDF", command=self.export_reports_pdf).pack(side="left", padx=6)
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

    def export_reports_pdf(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Missing dependency", "reportlab is required to export PDF reports. Install it with: pip install reportlab")
            return

        rows = [self.rep_tree.item(r)["values"] for r in self.rep_tree.get_children()]
        filename = os.path.join(EXPORTS_DIR, f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        try:
            c = rl_canvas.Canvas(filename, pagesize=A4)
            w, h = A4
            y = h - 30*mm

            # --- Draw logo ---
            logo_fp = os.path.join(BASE_DIR, "logo.jpg")
            logo_height = 0
            if os.path.exists(logo_fp):
                try:
                    img = rl_utils.ImageReader(logo_fp)
                    iw, ih = img.getSize()
                    aspect = ih / iw
                    draw_w = 35*mm
                    draw_h = draw_w * aspect
                    c.drawImage(img, 20*mm, y - draw_h, width=draw_w, height=draw_h, mask='auto')
                    logo_height = draw_h + 10  # spacing below logo
                except Exception as e:
                    print("Logo error:", e)

            # --- Header text (shifted down) ---
            y -= logo_height
            c.setFont("Helvetica-Bold", 16)
            c.drawString(60*mm, y, "MambaMunchies Sales Report")
            c.setFont("Helvetica", 10)
            c.drawString(60*mm, y - 14, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            y -= 40

            # --- Table of receipts ---
            data = [["Date", "Receipt#", "Staff", "Customer", "Total"]] + rows
            tbl = Table(data, colWidths=[60*mm, 30*mm, 30*mm, 40*mm, 20*mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), rl_colors.lightgrey),
                ("GRID", (0,0), (-1,-1), 0.25, rl_colors.grey),
                ("FONT", (0,0), (-1,0), "Helvetica-Bold")
            ]))
            table_h = len(data) * 12
            tbl.wrapOn(c, w, h)
            tbl.drawOn(c, 20*mm, y - table_h)
            y -= table_h + 20

            # --- Analytics section ---
            con = db_connect(); cur = con.cursor()
            cur.execute("SELECT SUM(total) FROM receipts WHERE date(created_at) BETWEEN ? AND ?", (self.rep_from.get(), self.rep_to.get()))
            total_sales = cur.fetchone()[0] or 0.0
            cur.execute("SELECT COUNT(*) FROM receipts WHERE date(created_at) BETWEEN ? AND ?", (self.rep_from.get(), self.rep_to.get()))
            tx_count = cur.fetchone()[0] or 0
            cur.execute("SELECT name, SUM(qty) as s FROM receipt_items WHERE date((SELECT created_at FROM receipts WHERE id=receipt_items.receipt_id)) BETWEEN ? AND ? GROUP BY name ORDER BY s DESC LIMIT 5", (self.rep_from.get(), self.rep_to.get()))
            top = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM pastries WHERE quantity < ?", (LOW_STOCK_THRESHOLD,))
            low_count = cur.fetchone()[0]
            con.close()

            c.setFont("Helvetica-Bold", 12)
            c.drawString(20*mm, y, "Summary Analytics")
            c.setFont("Helvetica", 10)
            c.drawString(20*mm, y - 14, f"Total Sales: {money(total_sales)}")
            c.drawString(20*mm, y - 28, f"Total Transactions: {tx_count}")
            c.drawString(20*mm, y - 42, f"Low-stock Items (< {LOW_STOCK_THRESHOLD}): {low_count}")
            y -= 70

            c.setFont("Helvetica-Bold", 11)
            c.drawString(20*mm, y, "Most Popular Products")
            c.setFont("Helvetica", 10)
            y -= 14
            if top:
                for name, s in top:
                    c.drawString(24*mm, y, f"- {name}: {s} sold")
                    y -= 12
            else:
                c.drawString(24*mm, y, "No product sales in range.")

            c.showPage()
            c.save()

            # Auto-open
            try:
                if os.name == 'nt':
                    os.startfile(filename)
                else:
                    subprocess.Popen(['xdg-open', filename])
            except Exception:
                pass

            messagebox.showinfo("Report Exported", f"Saved report to:\n{filename}")
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

if __name__=="__main__":
    init_db(); LoginWindow().mainloop()
