import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from utils import db_connect, hash_pw

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🍰 MambaMunchies — Login")
        self.geometry("500x450")
        self.configure(bg="#FFF7F3")  # Soft pastel background

        title = tk.Label(
            self,
            text="🍰 MambaMunchies",
            font=("Comic Sans MS", 22, "bold"),
            bg="#FFF7F3",
            fg="#D36B82"
        )
        title.pack(pady=(25, 5))

        try:
            logo_img = Image.open("logo.jpg").resize((120, 120))
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            ttk.Label(self, image=self.logo_photo).pack(pady=6)
        except FileNotFoundError:
            ttk.Label(self, text="[Logo Missing]").pack(pady=6)

        self.user = tk.StringVar()
        self.pw = tk.StringVar()

        # ===== LOGIN CARD =====
        self.user = tk.StringVar()
        self.pw = tk.StringVar()

        card = tk.Frame(self, bg="#FFE6EB", bd=0, highlightthickness=2, highlightbackground="#F4C2C2")
        card.pack(pady=15, padx=50, fill="x", ipadx=10, ipady=10)

        # Username
        user_frame = tk.Frame(card, bg="#FFE6EB")
        user_frame.pack(fill="x", padx=20, pady=(5, 5))
        tk.Label(user_frame, text="👩‍💻 Username", font=("Segoe UI", 10, "bold"), bg="#FFE6EB", fg="#A64D79").pack(anchor="w")
        user_entry = ttk.Entry(user_frame, textvariable=self.user, font=("Segoe UI", 10))
        user_entry.pack(fill="x", pady=(3, 0))

        # Password
        pw_frame = tk.Frame(card, bg="#FFE6EB")
        pw_frame.pack(fill="x", padx=20, pady=(5, 10))
        tk.Label(pw_frame, text="🔒 Password", font=("Segoe UI", 10, "bold"), bg="#FFE6EB", fg="#A64D79").pack(anchor="w")
        pw_entry = ttk.Entry(pw_frame, textvariable=self.pw, show="*", font=("Segoe UI", 10))
        pw_entry.pack(fill="x", pady=(3, 0))

        # ===== Login Button =====
        style = ttk.Style()
        style.configure(
            "Cute.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#A64D79",
            background="#E48296",
            padding=8
        )
        style.map(
            "Cute.TButton",
            background=[("active", "#E48296"), ("pressed", "#C95B70")]
        )

        login_btn = ttk.Button(
            card,
            text="Login 🍩",
            style="Cute.TButton",
            command=self.do_login
        )
        login_btn.pack(pady=5, ipadx=5)

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
