import tkinter as tk
from tkinter import ttk, messagebox
from utils import db_connect, now_iso
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

        # ---------------- Variables ----------------
        self.category = tk.StringVar()
        self.name = tk.StringVar()
        self.price = tk.DoubleVar(value=5.00)
        self.qty = tk.IntVar(value=1)

        # ---------------- Header ----------------
        ttk.Label(self, text="Pastry Details", font=("Segoe UI", 12, "bold")).pack(pady=(10, 5))

        # ---------------- Category ----------------
        ttk.Label(self, text="Category:").pack(pady=(6, 2))
        self.cat_cb = ttk.Combobox(self, textvariable=self.category,
                                   values=list(CATEGORY_ITEMS.keys()), state="readonly")
        self.cat_cb.pack(fill="x", padx=40)
        self.cat_cb.bind("<<ComboboxSelected>>", self.update_products)

        # ---------------- Name ----------------
        ttk.Label(self, text="Name:").pack(pady=(6, 2))
        self.name_cb = ttk.Combobox(self, textvariable=self.name, values=[], state="readonly")
        self.name_cb.pack(fill="x", padx=40)

        # ---------------- Price ----------------
        ttk.Label(self, text="Price:").pack(pady=4)
        ttk.Entry(self, textvariable=self.price).pack(fill="x", padx=40)

        # ---------------- Quantity ----------------
        ttk.Label(self, text="Quantity:").pack(pady=4)
        ttk.Entry(self, textvariable=self.qty).pack(fill="x", padx=40)

        # ---------------- Buttons ----------------
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", style="Accent.TButton", command=self.save_pastry).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        # ---------------- Load Existing ----------------
        if self.pastry_id:
            self.load_existing()
        else:
            if CATEGORY_ITEMS:
                self.cat_cb.current(0)
                self.update_products()

    # --------------------------------------------------------
    def update_products(self, event=None):
        cat = self.category.get()
        products = CATEGORY_ITEMS.get(cat, [])
        self.name_cb["values"] = products
        if products:
            self.name_cb.current(0)

    # --------------------------------------------------------
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
            self.update_products()
            self.name_cb.set(row[0])

    # --------------------------------------------------------
    def save_pastry(self):
        name = self.name.get().strip()
        category = self.category.get().strip()

        # ---------------- Validations ----------------
        try:
            price_val = float(self.price.get())
            qty_val = int(self.qty.get())
        except Exception:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values for price and quantity.")
            self.destroy()
            return

        if not category:
            messagebox.showwarning("Missing Category", "Please select a category.")
            self.destroy()
            return
        if not name:
            messagebox.showwarning("Missing Name", "Please select a pastry name.")
            self.destroy()
            return
        if price_val < 5 or price_val > 100:
            messagebox.showerror("Invalid Price", "Price must be between ₱5.00 and ₱100.00.")
            self.destroy()
            return
        if qty_val < 1 or qty_val > 100:
            messagebox.showerror("Invalid Quantity", "Quantity must be between 1 and 100.")
            self.destroy()
            return

        # ---------------- Database Save ----------------
        con = db_connect()
        cur = con.cursor()

        # ✅ Check for duplicates only when adding new pastry
        if not self.pastry_id:
            cur.execute("SELECT id FROM pastries WHERE name=? COLLATE NOCASE", (name,))
            existing = cur.fetchone()
            if existing:
                messagebox.showwarning("Duplicate Item", f"'{name}' already exists in the inventory.")
                self.destroy()
                con.close()
                return

            # Insert new record
            cur.execute("""
                INSERT INTO pastries (name, category, price, quantity, date_added, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, category, price_val, qty_val, now_iso(), now_iso()))

        else:
            # Update existing record
            cur.execute("""
                UPDATE pastries
                SET name=?, category=?, price=?, quantity=?, last_updated=?
                WHERE id=?
            """, (name, category, price_val, qty_val, now_iso(), int(self.pastry_id)))

        con.commit()
        con.close()

        messagebox.showinfo("Success", f"'{name}' saved successfully!")
        self.destroy()

        # Refresh parent views
        try:
            self.master.load_inventory()
        except Exception:
            pass
        try:
            self.master.refresh_catalog()
        except Exception:
            pass
