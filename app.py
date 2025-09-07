import os
import csv
import hashlib
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# -------------------- Paths --------------------
BASE_DIR = r"E:\Downloads\3rdyr1stsem\Elective 3\MambaMunchies Integrated Pastry Point of Sale (POS) and Sales Monitoring System"
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "pastry_inventory.db")

LOW_STOCK_THRESHOLD = 5

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

# -------------------- Helpers --------------------
def db_connect():   # Eto yung function na mag-oopen ng connection sa database (SQLite).
    return sqlite3.connect(DB_PATH) # Pag kailangan natin mag run ng SQL commands, dito dadaan.

def hash_pw(pw: str) -> str: # Simple function to hash a password gamit sha256.
    import hashlib
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def format_money(x): # Eto naman pang-format ng presyo/pera.
    try: # Kapag may error or walang value, default sya sa ₱0.00
        return f"₱{float(x):,.2f}"
    except:
        return "₱0.00"

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# -------------------- DB Init & Seed --------------------
def init_db(): # Time Stamp
    con = db_connect()
    cur = con.cursor()

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('Admin','Staff')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Pastries
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pastries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Sales
    cur.execute("""
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
    """)

    # Seed default admin if none exists
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hash_pw("admin123"), "Admin"),
        )

    con.commit()
    con.close()

# -------------------- App --------------------
class App(tk.Tk):
    def __init__(self, username, role):
        super().__init__()
        self.title("MambaMunchies")
        self.geometry("980x640")
        self.minsize(1920, 1080)

        self.username = username
        self.role = role

        # Top bar
        top = ttk.Frame(self, padding=10)
        top.pack(side="top", fill="x")
        ttk.Label(
            top,
            text=f"Logged in as: {self.username} ({self.role})",
            font=("Segoe UI", 10, "bold")
        ).pack(side="left")
        ttk.Button(top, text="Logout", command=self.logout).pack(side="right", padx=5)

        # Tabs
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.inventory_tab = ttk.Frame(self.nb)
        self.sales_tab = ttk.Frame(self.nb)
        self.reports_tab = ttk.Frame(self.nb)
        self.nb.add(self.inventory_tab, text="Inventory")
        self.nb.add(self.sales_tab, text="Sales")
        self.nb.add(self.reports_tab, text="Reports")

        if self.role == "Admin":
            self.users_tab = ttk.Frame(self.nb)
            self.nb.add(self.users_tab, text="Users")

        self.build_inventory_tab()
        self.build_sales_tab()
        self.build_reports_tab()
        if self.role == "Admin":
            self.build_users_tab()

        self.load_inventory()
        self.refresh_sales_dropdown()
        self.refresh_reports()

    def logout(self):
        self.destroy()
        LoginWindow()

    # ---------------- Inventory ----------------
    def build_inventory_tab(self):
        frm = self.inventory_tab

        form = ttk.LabelFrame(frm, text="Pastry Details", padding=10)
        form.pack(side="top", fill="x", padx=8, pady=8)

        # variables
        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar(value="Pastry")
        self.price_var = tk.StringVar()
        self.qty_var = tk.StringVar()
        self.search_var = tk.StringVar()

        # Name (combobox)
        r = 0
        ttk.Label(form, text="Name:").grid(row=r, column=0, sticky="w", padx=5, pady=4)
        self.name_cb = ttk.Combobox(form, textvariable=self.name_var, width=30, state="readonly")
        self.name_cb.grid(row=r, column=1, padx=5, pady=4)

        # Category (combobox)
        ttk.Label(form, text="Category:").grid(row=r, column=2, sticky="w", padx=5, pady=4)
        self.category_cb = ttk.Combobox(
            form,
            textvariable=self.category_var,
            width=18,
            state="readonly",
            values=list(CATEGORY_ITEMS.keys())
        )
        self.category_cb.grid(row=r, column=3, padx=5, pady=4)
        # populate names for default category
        self.update_names_for_category(self.category_var.get())
        # bind category change -> update names list
        self.category_cb.bind("<<ComboboxSelected>>", self.on_category_change)

        # Price / Quantity
        r += 1
        ttk.Label(form, text="Price:").grid(row=r, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.price_var, width=32).grid(row=r, column=1, padx=5, pady=4)

        ttk.Label(form, text="Quantity:").grid(row=r, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(form, textvariable=self.qty_var, width=20).grid(row=r, column=3, padx=5, pady=4)

        # Buttons
        r += 1
        btns = ttk.Frame(form)
        btns.grid(row=r, column=0, columnspan=4, pady=6, sticky="w")
        ttk.Button(btns, text="Add", width=14, command=self.add_pastry).pack(side="left", padx=4)
        ttk.Button(btns, text="Update", width=14, command=self.update_pastry).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete", width=14, command=self.delete_pastry).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear", width=10, command=self.clear_form).pack(side="left", padx=4)

        # Search + Export + Total Value
        row2 = ttk.Frame(frm)
        row2.pack(side="top", fill="x", padx=8)
        ttk.Label(row2, text="Search by name:").pack(side="left")
        search_entry = ttk.Entry(row2, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=6)
        ttk.Button(row2, text="Search", command=self.search_inventory).pack(side="left", padx=4)
        ttk.Button(row2, text="Show All", command=self.load_inventory).pack(side="left", padx=4)
        ttk.Button(row2, text="Export CSV", command=self.export_inventory_csv).pack(side="left", padx=12)
        self.total_value_lbl = ttk.Label(row2, text="Total Inventory Value: ₱0.00")
        self.total_value_lbl.pack(side="right")

        # Table
        table_frame = ttk.Frame(frm)
        table_frame.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("ID", "Name", "Category", "Price", "Quantity", "Date Added", "Last Updated")
        self.inv_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.inv_tree.heading(c, text=c)
        self.inv_tree.column("ID", width=50, anchor="center")
        self.inv_tree.column("Name", width=220)
        self.inv_tree.column("Category", width=100, anchor="center")
        self.inv_tree.column("Price", width=90, anchor="e")
        self.inv_tree.column("Quantity", width=90, anchor="center")
        self.inv_tree.column("Date Added", width=140, anchor="center")
        self.inv_tree.column("Last Updated", width=140, anchor="center")
        self.inv_tree.pack(side="left", fill="both", expand=True)

        self.inv_tree.tag_configure("low", background="#ffd6d6")
        self.inv_tree.bind("<<TreeviewSelect>>", self.on_inventory_select)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.inv_tree.yview)
        self.inv_tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")

    def on_category_change(self, _event=None):
        self.update_names_for_category(self.category_var.get())

    def update_names_for_category(self, category):
        items = CATEGORY_ITEMS.get(category, [])
        self.name_cb["values"] = items
        if items:
            # if current name not in list, set to first
            current = self.name_var.get()
            if current not in items:
                self.name_var.set(items[0])
        else:
            self.name_var.set("")

    def clear_form(self):
        self.category_var.set("Pastry")
        self.update_names_for_category("Pastry")
        self.price_var.set("")
        self.qty_var.set("")

    def on_inventory_select(self, _):
        sel = self.inv_tree.selection()
        if not sel:
            return
        vals = self.inv_tree.item(sel[0])["values"]
        # (ID, Name, Category, Price, Quantity, Date Added, Last Updated)
        _, name, category, price, qty, *_ = vals
        self.category_var.set(category)
        # update names list for that category
        self.update_names_for_category(category)
        # ensure selected name is visible even if not in preset list
        if name not in self.name_cb["values"]:
            self.name_cb["values"] = list(self.name_cb["values"]) + [name]
        self.name_var.set(name)
        self.price_var.set(price)
        self.qty_var.set(qty)

    def add_pastry(self):
    # Eto yung function na ginagamit kapag nag-add ka ng bagong pastry sa system.
        name = self.name_var.get().strip()
        cat = self.category_var.get().strip() or "Pastry"
        price = self.price_var.get().strip()
        qty = self.qty_var.get().strip()
        if not name or not price or not qty:
            messagebox.showwarning("Input", "Please fill Name, Price, Quantity.")
            return
        try:
            price_f = float(price)
            qty_i = int(qty)
        except ValueError:
            messagebox.showwarning("Input", "Price must be number; Quantity must be integer.")
            return

        con = db_connect(); cur = con.cursor()
        cur.execute("""
            INSERT INTO pastries (name, category, price, quantity, date_added, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, cat, price_f, qty_i, now_iso(), now_iso()))
        con.commit(); con.close()
        self.load_inventory()
        self.clear_form()
        messagebox.showinfo("Success", "Pastry added.")

    def update_pastry(self):
        sel = self.inv_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a pastry to update.")
            return
        pid = self.inv_tree.item(sel[0])["values"][0]

        name = self.name_var.get().strip()
        cat = self.category_var.get().strip() or "Pastry"
        price = self.price_var.get().strip()
        qty = self.qty_var.get().strip()
        if not name or not price or not qty:
            messagebox.showwarning("Input", "Please fill all fields.")
            return
        try:
            price_f = float(price)
            qty_i = int(qty)
        except ValueError:
            messagebox.showwarning("Input", "Price must be number; Quantity must be integer.")
            return

        con = db_connect(); cur = con.cursor()
        cur.execute("""
            UPDATE pastries SET name=?, category=?, price=?, quantity=?, last_updated=?
            WHERE id=?
        """, (name, cat, price_f, qty_i, now_iso(), pid))
        con.commit(); con.close()
        self.load_inventory()
        self.clear_form()
        messagebox.showinfo("Updated", "Pastry updated.")

    def delete_pastry(self):
        sel = self.inv_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a pastry to delete.")
            return
        pid = self.inv_tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm", "Delete selected pastry?"):
            con = db_connect(); cur = con.cursor()
            cur.execute("DELETE FROM pastries WHERE id=?", (pid,))
            con.commit(); con.close()
            self.load_inventory()

    def search_inventory(self):
        kw = self.search_var.get().strip()
        con = db_connect(); cur = con.cursor()
        cur.execute("""SELECT id,name,category,price,quantity,date_added,last_updated
                       FROM pastries WHERE name LIKE ? ORDER BY name ASC""", (f"%{kw}%",))
        rows = cur.fetchall(); con.close()
        self.populate_inventory(rows)

    def load_inventory(self):
        con = db_connect(); cur = con.cursor()
        cur.execute("""SELECT id,name,category,price,quantity,date_added,last_updated
                       FROM pastries ORDER BY name ASC""")
        rows = cur.fetchall()

        # total value
        cur.execute("SELECT COALESCE(SUM(price*quantity),0) FROM pastries")
        total = cur.fetchone()[0]
        con.close()
        self.total_value_lbl.config(text=f"Total Inventory Value: {format_money(total)}")

        self.populate_inventory(rows)

    def populate_inventory(self, rows):
        self.inv_tree.delete(*self.inv_tree.get_children())
        for row in rows:
            pid, name, cat, price, qty, da, lu = row
            tag = "low" if qty < LOW_STOCK_THRESHOLD else ""
            self.inv_tree.insert("", "end",
                                 values=(pid, name, cat, f"{price:.2f}", qty, da, lu),
                                 tags=(tag,) if tag else ())

    def export_inventory_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialdir=BASE_DIR,
            filetypes=[("CSV files","*.csv")], title="Save Inventory CSV"
        )
        if not path: return
        con = db_connect(); cur = con.cursor()
        cur.execute("""SELECT id,name,category,price,quantity,date_added,last_updated FROM pastries""")
        rows = cur.fetchall(); con.close()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ID","Name","Category","Price","Quantity","Date Added","Last Updated"])
            for r in rows: w.writerow(r)
        messagebox.showinfo("Exported", f"Inventory exported to:\n{path}")

    # ---------------- Sales ----------------
    def build_sales_tab(self):
        frm = self.sales_tab

        box = ttk.LabelFrame(frm, text="Record a Sale", padding=10)
        box.pack(side="top", fill="x", padx=8, pady=8)

        self.sale_pastry_var = tk.StringVar()
        self.sale_qty_var = tk.StringVar()

        ttk.Label(box, text="Pastry:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.sale_pastry_cb = ttk.Combobox(box, textvariable=self.sale_pastry_var, width=40, state="readonly")
        self.sale_pastry_cb.grid(row=0, column=1, padx=5, pady=4)

        ttk.Label(box, text="Quantity:").grid(row=0, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(box, textvariable=self.sale_qty_var, width=12).grid(row=0, column=3, padx=5, pady=4)

        ttk.Button(box, text="Add Sale", width=16, command=self.add_sale).grid(row=0, column=4, padx=6, pady=4)

        # Sales table (recent)
        table_frame = ttk.Frame(frm)
        table_frame.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("ID","Time","Pastry","Qty","Unit Price","Total","Staff")
        self.sales_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.sales_tree.heading(c, text=c)
        self.sales_tree.column("ID", width=60, anchor="center")
        self.sales_tree.column("Time", width=160, anchor="center")
        self.sales_tree.column("Pastry", width=260)
        self.sales_tree.column("Qty", width=80, anchor="center")
        self.sales_tree.column("Unit Price", width=100, anchor="e")
        self.sales_tree.column("Total", width=110, anchor="e")
        self.sales_tree.column("Staff", width=120, anchor="center")
        self.sales_tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.sales_tree.yview)
        self.sales_tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")

        self.load_recent_sales()

    def refresh_sales_dropdown(self):
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id, name, price FROM pastries ORDER BY name ASC")
        items = cur.fetchall()
        con.close()
        # Display as "Name (₱price) [id]"
        display = [f"{n} ({format_money(p)}) [#{i}]" for i, n, p in items]
        self.sale_pastry_cb["values"] = display
        if display:
            self.sale_pastry_cb.current(0)

    def add_sale(self):
        sel = self.sale_pastry_var.get()
        qty_s = self.sale_qty_var.get().strip()
        if not sel or not qty_s:
            messagebox.showwarning("Input", "Select a pastry and enter quantity.")
            return
        try:
            qty = int(qty_s)
            if qty <= 0: raise ValueError
        except ValueError:
            messagebox.showwarning("Input", "Quantity must be a positive integer.")
            return

        # Extract pastry id from string "... [#id]"
        try:
            pid = int(sel.split("[#")[-1].rstrip("]"))
        except:
            messagebox.showerror("Error", "Could not parse pastry selection.")
            return

        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT name, price, quantity FROM pastries WHERE id=?", (pid,))
        row = cur.fetchone()
        if not row:
            con.close()
            messagebox.showerror("Error", "Pastry not found.")
            return
        name, unit_price, stock = row
        if qty > stock:
            con.close()
            messagebox.showwarning("Stock", f"Not enough stock for '{name}'. Available: {stock}.")
            return

        total = unit_price * qty
        # Record sale
        cur.execute("""
            INSERT INTO sales (pastry_id, qty, unit_price, total, sale_time, staff_username)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pid, qty, unit_price, total, now_iso(), self.username))
        # Deduct stock
        cur.execute("""
            UPDATE pastries SET quantity = quantity - ?, last_updated=? WHERE id=?
        """, (qty, now_iso(), pid))

        con.commit(); con.close()
        self.load_inventory()
        self.refresh_sales_dropdown()
        self.load_recent_sales()
        self.refresh_reports()
        self.sale_qty_var.set("")
        messagebox.showinfo("Sale Recorded", f"Sold {qty} × {name} = {format_money(total)}")

    def load_recent_sales(self, limit=100):
        self.sales_tree.delete(*self.sales_tree.get_children())
        con = db_connect(); cur = con.cursor()
        cur.execute("""
            SELECT s.id, s.sale_time, p.name, s.qty, s.unit_price, s.total, s.staff_username
            FROM sales s JOIN pastries p ON s.pastry_id=p.id
            ORDER BY s.id DESC LIMIT ?
        """, (limit,))
        for r in cur.fetchall():
            sid, t, name, qty, up, tot, staff = r
            self.sales_tree.insert("", "end",
                                   values=(sid, t, name, qty, f"{up:.2f}", f"{tot:.2f}", staff))
        con.close()

    # ---------------- Reports ----------------
    def build_reports_tab(self):
        frm = self.reports_tab

        filters = ttk.LabelFrame(frm, text="Filters", padding=10)
        filters.pack(side="top", fill="x", padx=8, pady=8)

        self.report_from_var = tk.StringVar()
        self.report_to_var = tk.StringVar()

        ttk.Label(filters, text="From (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(filters, textvariable=self.report_from_var, width=16).grid(row=0, column=1, padx=5, pady=4)
        ttk.Label(filters, text="To (YYYY-MM-DD):").grid(row=0, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(filters, textvariable=self.report_to_var, width=16).grid(row=0, column=3, padx=5, pady=4)

        ttk.Button(filters, text="Apply", command=self.refresh_reports).grid(row=0, column=4, padx=8)
        ttk.Button(filters, text="Clear", command=self.clear_report_filters).grid(row=0, column=5, padx=4)
        ttk.Button(filters, text="Export CSV", command=self.export_sales_csv).grid(row=0, column=6, padx=12)

        # KPI cards
        kpi = ttk.Frame(frm)
        kpi.pack(side="top", fill="x", padx=8)
        self.today_total_lbl = ttk.Label(kpi, text="Today's Sales: ₱0.00", font=("Segoe UI", 11, "bold"))
        self.week_total_lbl = ttk.Label(kpi, text="This Week: ₱0.00", font=("Segoe UI", 11, "bold"))
        self.today_total_lbl.pack(side="left", padx=6, pady=4)
        self.week_total_lbl.pack(side="left", padx=20, pady=4)

        # Sales table
        table_frame = ttk.Frame(frm)
        table_frame.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("ID","Time","Pastry","Qty","Unit Price","Total","Staff")
        self.report_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.report_tree.heading(c, text=c)
        self.report_tree.column("ID", width=60, anchor="center")
        self.report_tree.column("Time", width=160, anchor="center")
        self.report_tree.column("Pastry", width=260)
        self.report_tree.column("Qty", width=80, anchor="center")
        self.report_tree.column("Unit Price", width=100, anchor="e")
        self.report_tree.column("Total", width=110, anchor="e")
        self.report_tree.column("Staff", width=120, anchor="center")
        self.report_tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.report_tree.yview)
        self.report_tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")

    def clear_report_filters(self):
        self.report_from_var.set("")
        self.report_to_var.set("")
        self.refresh_reports()

    def refresh_reports(self):
        # Apply filters
        from_d = self.report_from_var.get().strip()
        to_d = self.report_to_var.get().strip()

        q = """
            SELECT s.id, s.sale_time, p.name, s.qty, s.unit_price, s.total, s.staff_username
            FROM sales s JOIN pastries p ON s.pastry_id=p.id
        """
        params = []
        clauses = []
        if from_d:
            clauses.append("date(s.sale_time) >= date(?)")
            params.append(from_d)
        if to_d:
            clauses.append("date(s.sale_time) <= date(?)")
            params.append(to_d)

        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY s.sale_time DESC"

        self.report_tree.delete(*self.report_tree.get_children())
        con = db_connect(); cur = con.cursor()
        cur.execute(q, tuple(params))
        rows = cur.fetchall()
        for r in rows:
            sid, t, name, qty, up, tot, staff = r
            self.report_tree.insert("", "end", values=(sid, t, name, qty, f"{up:.2f}", f"{tot:.2f}", staff))

        # KPI: Today + This Week
        today_str = datetime.now().strftime("%Y-%m-%d")
        cur.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE date(sale_time)=date(?)", (today_str,))
        today_total = cur.fetchone()[0]

        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)
        cur.execute("""SELECT COALESCE(SUM(total),0) FROM sales
                       WHERE date(sale_time) BETWEEN date(?) AND date(?)""",
                    (start_of_week.strftime("%Y-%m-%d"), end_of_week.strftime("%Y-%m-%d")))
        week_total = cur.fetchone()[0]
        con.close()

        self.today_total_lbl.config(text=f"Today's Sales: {format_money(today_total)}")
        self.week_total_lbl.config(text=f"This Week: {format_money(week_total)}")

    def export_sales_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialdir=BASE_DIR,
            filetypes=[("CSV files","*.csv")], title="Save Sales CSV"
        )
        if not path: return

        from_d = self.report_from_var.get().strip()
        to_d = self.report_to_var.get().strip()
        q = """
            SELECT s.id, s.sale_time, p.name, s.qty, s.unit_price, s.total, s.staff_username
            FROM sales s JOIN pastries p ON s.pastry_id=p.id
        """
        params = []
        clauses = []
        if from_d:
            clauses.append("date(s.sale_time) >= date(?)")
            params.append(from_d)
        if to_d:
            clauses.append("date(s.sale_time) <= date(?)")
            params.append(to_d)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY s.sale_time DESC"

        con = db_connect(); cur = con.cursor()
        cur.execute(q, tuple(params))
        rows = cur.fetchall(); con.close()

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ID","Time","Pastry","Qty","Unit Price","Total","Staff"])
            for r in rows:
                sid, t, name, qty, up, tot, staff = r
                w.writerow([sid, t, name, qty, f"{up:.2f}", f"{tot:.2f}", staff])
        messagebox.showinfo("Exported", f"Sales exported to:\n{path}")

    # ---------------- Users (Admin) ----------------
    def build_users_tab(self):
        frm = self.users_tab

        box = ttk.LabelFrame(frm, text="Add User", padding=10)
        box.pack(side="top", fill="x", padx=8, pady=8)

        self.new_user_var = tk.StringVar()
        self.new_pw_var = tk.StringVar()
        self.new_role_var = tk.StringVar(value="Staff")

        ttk.Label(box, text="Username:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(box, textvariable=self.new_user_var, width=24).grid(row=0, column=1, padx=5, pady=4)

        ttk.Label(box, text="Password:").grid(row=0, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(box, textvariable=self.new_pw_var, show="*", width=24).grid(row=0, column=3, padx=5, pady=4)

        ttk.Label(box, text="Role:").grid(row=0, column=4, sticky="w", padx=5, pady=4)
        ttk.Combobox(box, textvariable=self.new_role_var, values=["Admin","Staff"], width=10, state="readonly").grid(row=0, column=5, padx=5, pady=4)

        ttk.Button(box, text="Add User", command=self.add_user).grid(row=0, column=6, padx=10)

        # Users table
        table_frame = ttk.Frame(frm)
        table_frame.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("ID","Username","Role","Created")
        self.users_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.users_tree.heading(c, text=c)
        self.users_tree.column("ID", width=60, anchor="center")
        self.users_tree.column("Username", width=220)
        self.users_tree.column("Role", width=100, anchor="center")
        self.users_tree.column("Created", width=180, anchor="center")
        self.users_tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.users_tree.yview)
        self.users_tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")

        # bottom buttons
        btns = ttk.Frame(frm)
        btns.pack(side="bottom", fill="x", padx=8, pady=6)
        ttk.Button(btns, text="Delete Selected User", command=self.delete_user).pack(side="left")
        ttk.Button(btns, text="Refresh", command=self.load_users).pack(side="left", padx=8)

        self.load_users()

    def add_user(self):
        u = self.new_user_var.get().strip()
        p = self.new_pw_var.get().strip()
        r = self.new_role_var.get().strip()
        if not u or not p or r not in ("Admin","Staff"):
            messagebox.showwarning("Input", "Fill Username, Password and Role.")
            return
        con = db_connect(); cur = con.cursor()
        try:
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                        (u, hash_pw(p), r))
            con.commit()
            self.new_user_var.set(""); self.new_pw_var.set(""); self.new_role_var.set("Staff")
            self.load_users()
            messagebox.showinfo("Success", "User added.")
        except sqlite3.IntegrityError:
            messagebox.showwarning("Exists", "Username already exists.")
        finally:
            con.close()

    def load_users(self):
        self.users_tree.delete(*self.users_tree.get_children())
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT id, username, role, created_at FROM users ORDER BY id ASC")
        for r in cur.fetchall():
            self.users_tree.insert("", "end", values=r)
        con.close()

    def delete_user(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a user to delete.")
            return
        uid, uname, role, _ = self.users_tree.item(sel[0])["values"]
        if uname == self.username:
            messagebox.showwarning("Action blocked", "You cannot delete your own account while logged in.")
            return
        if messagebox.askyesno("Confirm", f"Delete user '{uname}'?"):
            con = db_connect(); cur = con.cursor()
            cur.execute("DELETE FROM users WHERE id=?", (uid,))
            con.commit(); con.close()
            self.load_users()

# -------------------- Login Window --------------------
class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🍰 MambaMunchies — Login")
        self.geometry("500x300")
        self.resizable(False, False)

        # Center window on screen
        self.update_idletasks()
        w, h = 500, 300
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Title Label
        title = ttk.Label(self, text="MambaMunchies", font=("Segoe UI", 16, "bold"))
        title.pack(pady=(20, 10))

        # Frame with padding
        frame = ttk.LabelFrame(self, text="🔐 Sign In", padding=20)
        frame.pack(padx=40, pady=10)  # removed expand=True so it doesn’t push other widgets

        # Variables
        self.u_var = tk.StringVar()
        self.p_var = tk.StringVar()

        # Username
        ttk.Label(frame, text="Username:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="e", padx=8, pady=10)
        ttk.Entry(frame, textvariable=self.u_var, width=28, font=("Segoe UI", 11)).grid(row=0, column=1, padx=8, pady=10)

        # Password
        ttk.Label(frame, text="Password:", font=("Segoe UI", 11)).grid(row=1, column=0, sticky="e", padx=8, pady=10)
        ttk.Entry(frame, textvariable=self.p_var, show="*", width=28, font=("Segoe UI", 11)).grid(row=1, column=1, padx=8, pady=10)

        # Login button
        ttk.Button(frame, text="Login", command=self.do_login).grid(row=2, column=0, columnspan=2, pady=15)

        # Info text (now inside frame)
        info = ttk.Label(frame, text="Default admin →  admin / admin123", foreground="#666", font=("Segoe UI", 9))
        info.grid(row=3, column=0, columnspan=2, pady=(10, 0))

    def do_login(self):
        u = self.u_var.get().strip()
        p = self.p_var.get().strip()
        if not u or not p:
            messagebox.showwarning("Input", "Enter username and password.")
            return

        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT password_hash, role FROM users WHERE username=?", (u,))
        row = cur.fetchone(); con.close()
        if not row or row[0] != hash_pw(p):
            messagebox.showerror("Login failed", "Invalid username or password.")
            return

        role = row[1]
        self.destroy()
        app = App(username=u, role=role)
        app.mainloop()

# -------------------- Run --------------------
if __name__ == "__main__":
    init_db()
    LoginWindow().mainloop()
