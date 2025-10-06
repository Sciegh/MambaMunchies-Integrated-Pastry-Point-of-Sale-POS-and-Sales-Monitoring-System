from utils import db_connect, hash_pw

def init_db():
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

    # Legacy Sales
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

    # Receipts
    cur.execute("""
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
    """)

    # Receipt items
    cur.execute("""
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
    """)

    # Seed admin account if none exists
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            ("admin", hash_pw("admin123"), "Admin"),
        )

    con.commit()
    con.close()
