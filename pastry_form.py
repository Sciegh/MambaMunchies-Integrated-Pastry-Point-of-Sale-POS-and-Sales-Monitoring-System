import tkinter as tk
from tkinter import ttk, messagebox
from utils import db_connect
from categories import CATEGORY_ITEMS
from colors import COL_BG

class PastryForm(tk.Toplevel):
    def __init__(self, master, pastry_id=None):
        super().__init__(master)
        self.master = master
        self.pastry_id = pastry_id
        self.title("🍰 Add / Edit Pastry")
        self.geometry("400x360")
        self.configure(bg=COL_BG)
        self.resizable(False, False)

        # Form variables
        self.category = tk.StringVar()
        self.name = tk.StringVar()
        self.price = tk.DoubleVar()
        self.qty = tk.IntVar()

        # Title label
        ttk.Label(self, text="Pastry Details", font=("Segoe UI", 12, "bold")).pack(pady=(10, 5))

        # Category selection
        ttk.Label(self, text="Category:").pack(pady=(6, 2))
        self.cat_cb = ttk.Combobox(self, textvariable=self.category, values=list(CATEGORY_ITEMS.keys()), state="readonly")
        self.cat_cb.pack(fill="x", padx=40)
        self.cat_cb.bind("<<ComboboxSelected>>", self.on_category_change)

        # Name selection
        ttk.Label(self, text="Name:").pack(pady=(6, 2))
        self.name_cb = ttk.Combobox(self, textvariable=self.name, values=[], state="readonly")
        self.name_cb.pack(fill="x", padx=40)

        # Price
        ttk.Label(self, text="Price (₱):").pack(pady=(6, 2))
        ttk.Entry(self, textvariable=self.price).pack(fill="x", padx=40)

        # Quantity
        ttk.Label(self, text="Quantity:").pack(pady=(6, 2))
        ttk.Entry(self, textvariable=self.qty).pack(fill="x", padx=40)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", style="Accent.TButton", command=self.save_pastry).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        if self.pastry_id:
            self.load_existing()
        else:
            self.cat_cb.current(0)
            self.on_category_change()

    def on_category_change(self, event=None):
        cat = self.category.get()
        self.name_cb["values"] = CATEGORY_ITEMS.get(cat, [])
        if CATEGORY_ITEMS.get(cat):
            self.name_cb.current(0)

    def load_existing(self):
        con = db_connect()
        cur = con.cursor()
        cur.execute("SELECT name, category, price, quantity FROM pastries WHERE id=?", (self.pastry_id,))
        row = cur.fetchone()
        con.close()
        if row:
            self.name.set(row[0])
            self.category.set(row[1])
            self.price.set(row[2])
            self.qty.set(row[3])
            self.on_category_change()

    def save_pastry(self):
        if not self.name.get() or not self.category.get():
            messagebox.showwarning("Input Error", "Please select category and name.")
            return
        if self.price.get() <= 0:
            messagebox.showwarning("Input Error", "Price must be greater than 0.")
            return
        if self.qty.get() < 0:
            messagebox.showwarning("Input Error", "Quantity cannot be negative.")
            return

        con = db_connect()
        cur = con.cursor()
        if self.pastry_id:
            cur.execute("""
                UPDATE pastries
                SET name=?, category=?, price=?, quantity=?, last_updated=CURRENT_TIMESTAMP
                WHERE id=?
            """, (self.name.get(), self.category.get(), self.price.get(), self.qty.get(), self.pastry_id))
        else:
            cur.execute("""
                INSERT INTO pastries (name, category, price, quantity)
                VALUES (?,?,?,?)
            """, (self.name.get(), self.category.get(), self.price.get(), self.qty.get()))
        con.commit()
        con.close()

        messagebox.showinfo("Saved", "Pastry record saved successfully.")
        self.destroy()

        try:
            self.master.refresh_inventory()
        except Exception:
            pass
