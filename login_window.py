import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from utils import db_connect, hash_pw

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🍰 MambaMunchies — Login")
        self.geometry("500x350")

        title = ttk.Label(self, text="MambaMunchies", font=("Segoe UI", 16, "bold"))
        title.pack(pady=(10, 5))

        try:
            logo_img = Image.open("logo.jpg").resize((120, 120))
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            ttk.Label(self, image=self.logo_photo).pack(pady=6)
        except FileNotFoundError:
            ttk.Label(self, text="[Logo Missing]").pack(pady=6)

        self.user = tk.StringVar()
        self.pw = tk.StringVar()

        ttk.Label(self, text="Username:").pack(pady=2)
        ttk.Entry(self, textvariable=self.user).pack(fill="x", padx=30)

        ttk.Label(self, text="Password:").pack(pady=2)
        ttk.Entry(self, textvariable=self.pw, show="*").pack(fill="x", padx=30)

        ttk.Button(
            self,
            text="Login",
            style="Accent.TButton",
            command=self.do_login
        ).pack(pady=10)

    def do_login(self):
        con = db_connect()
        cur = con.cursor()
        cur.execute("SELECT role, password_hash FROM users WHERE username=?", (self.user.get(),))
        r = cur.fetchone()
        con.close()
        
        from app import App 

        if r and r[1] == hash_pw(self.pw.get()):
            self.destroy()
            App(self.user.get(), r[0]).mainloop()
        else:
            messagebox.showerror("Login", "Invalid credentials")
