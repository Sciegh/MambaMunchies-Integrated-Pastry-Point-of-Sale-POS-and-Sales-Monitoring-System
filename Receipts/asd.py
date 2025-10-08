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

    def generate_report_data(self):
        """Fetch detailed sales data joined with pastry info for the report."""
        con = db_connect()
        cur = con.cursor()
        cur.execute("""
            SELECT 
                p.name AS item_name,
                s.unit_price,
                s.qty,
                s.total,
                s.sale_time,
                s.staff_username
            FROM sales s
            JOIN pastries p ON s.pastry_id = p.id
            ORDER BY s.sale_time DESC
        """)
        data = cur.fetchall()
        con.close()
        return data

    def generate_summary(self, report_data):
        """Compute totals and most popular product from fetched data."""
        if not report_data:
            return {
                "total_sales": 0.0,
                "total_items": 0,
                "most_popular": "N/A"
            }

        total_sales = sum(row[3] for row in report_data)
        total_items = sum(row[2] for row in report_data)

        # Most popular product by total quantity sold
        from collections import Counter
        counter = Counter()
        for item_name, unit_price, qty, total, sale_time, staff in report_data:
            counter[item_name] += qty
        most_popular = counter.most_common(1)[0][0] if counter else "N/A"

        return {
            "total_sales": total_sales,
            "total_items": total_items,
            "most_popular": most_popular
        }

    def export_reports_pdf(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showwarning("Dependency missing", "ReportLab is required to export PDF reports.")
            return

        # Get date filters
        date_from = self.rep_from.get()
        date_to = self.rep_to.get()

        con = db_connect()
        cur = con.cursor()

        # Fetch filtered data (only items sold within date range)
        cur.execute("""
            SELECT ri.name, SUM(ri.qty) AS total_sold, SUM(ri.line_total) AS total_revenue
            FROM receipt_items ri
            JOIN receipts r ON ri.receipt_id = r.id
            WHERE DATE(r.created_at) BETWEEN ? AND ?
            GROUP BY ri.name
            ORDER BY total_revenue DESC
        """, (date_from, date_to))
        rows = cur.fetchall()

        # --- Analytics ---
        total_sales = sum(r[2] for r in rows) if rows else 0
        total_items = sum(r[1] for r in rows) if rows else 0
        top_product = rows[0][0] if rows else "N/A"

        cur.execute("SELECT COUNT(*) FROM receipts WHERE DATE(created_at) BETWEEN ? AND ?", (date_from, date_to))
        total_receipts = cur.fetchone()[0]

        con.close()

        # --- PDF setup ---
        from reportlab.lib.pagesizes import A4
        filename = os.path.join(EXPORTS_DIR, f"Sales_Report_{date_from}_to_{date_to}.pdf")
        c = rl_canvas.Canvas(filename, pagesize=A4)
        w, h = A4

        # --- Background image ---
        bg_fp = os.path.join(BASE_DIR, "background.jpg")
        if os.path.exists(bg_fp):
            try:
                bg_img = rl_utils.ImageReader(bg_fp)
                c.drawImage(bg_img, 0, 0, width=w, height=h, preserveAspectRatio=False, mask='auto')
            except Exception as e:
                print("Background image error:", e)
        else:
            c.setFillColorRGB(1, 0.9, 0.95)
            c.rect(0, 0, w, h, fill=True, stroke=False)

        # --- Watermark logo ---
        logo_fp = os.path.join(BASE_DIR, "logo.jpg")
        if os.path.exists(logo_fp):
            try:
                img = rl_utils.ImageReader(logo_fp)
                iw, ih = img.getSize()
                aspect = ih / iw
                size = 120 * mm
                c.drawImage(img, (w - size)/2, (h - size)/2, width=size, height=size*aspect, mask='auto')
                c.setFillAlpha(0.15)
            except Exception as e:
                print("Watermark error:", e)
        c.setFillAlpha(1)

        # --- Header ---
        y = h - 40
        c.setFont("Helvetica-Bold", 18)
        c.setFillColorRGB(0.4, 0.1, 0.2)
        c.drawCentredString(w/2, y, "MambaMunchies Bakery")
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawCentredString(w/2, y, "📊 Sales Summary Report")
        y -= 20
        c.setFont("Helvetica", 10)
        c.drawCentredString(w/2, y, f"Period: {date_from} to {date_to}")
        y -= 20
        c.setFont("Helvetica", 9)
        c.drawCentredString(w/2, y, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by {self.username}")
        y -= 35

        # --- Table data ---
        data = [["Product Name", "Quantity Sold", "Total Revenue"]]
        for name, qty, revenue in rows:
            data.append([name, str(qty), money(revenue)])

        if len(data) == 1:
            data.append(["No sales data in this period.", "", ""])

        tbl = Table(data, colWidths=[90*mm, 35*mm, 45*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), rl_colors.lightpink),
            ("TEXTCOLOR", (0,0), (-1,0), rl_colors.black),
            ("GRID", (0,0), (-1,-1), 0.25, rl_colors.grey),
            ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONT", (0,1), (-1,-1), "Helvetica"),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ]))
        table_h = len(data) * 12
        tbl.wrapOn(c, w, h)
        tbl.drawOn(c, 40, y - table_h)
        y -= table_h + 40

        # --- Summary section ---
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.3, 0.1, 0.2)
        c.drawString(40, y, "Summary Overview")
        y -= 16
        c.setFont("Helvetica", 10)
        summary_lines = [
            ("Total Receipts", total_receipts),
            ("Total Items Sold", total_items),
            ("Total Sales", money(total_sales)),
            ("Most Popular Product", top_product),
        ]
        for label, value in summary_lines:
            c.drawString(60, y, f"{label}: {value}")
            y -= 14
        y -= 10

        # --- Footer ---
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(rl_colors.grey)
        c.drawCentredString(w/2, 25, "MambaMunchies Bakery • Confidential Report")

        # Save
        c.save()

        messagebox.showinfo("Export Complete", f"Report exported successfully!\n\nSaved to:\n{filename}")

        # Auto-open
        try:
            os.startfile(filename)
        except Exception:
            subprocess.Popen(["open", filename])

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

if __name__=="__main__":
    init_db(); LoginWindow().mainloop()