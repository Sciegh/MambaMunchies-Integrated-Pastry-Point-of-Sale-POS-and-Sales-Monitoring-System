import sqlite3
import hashlib
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk


COL_ACCENT = "#ffb347"
COL_ACCENT_LIGHT = "#ffd9b3"
COL_TEXT = "#000000"
COL_OK = "#66bb6a"

# -------------------- Helper utils --------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "pastry_inventory.db")

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
        d.rectangle([6, 10, w-6, h-10], outline=stroke, width=2)
        d.line([6, 10, 12, 6], fill=stroke, width=2)
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
        d.polygon([(6, h-8), (w-6, h-8), (w-10, h-4), (10, h-4)], fill=COL_ACCENT)
        d.ellipse([8, 6, w-8, h-10], fill=COL_ACCENT_LIGHT, outline=stroke)
        d.ellipse([w//2-2, 4, w//2+2, 8], fill=COL_OK)
    else:
        d.rectangle([4,4,w-4,h-4], outline=stroke, width=2)

    ph = ImageTk.PhotoImage(img)
    ICON_CACHE[key] = ph
    return ph
