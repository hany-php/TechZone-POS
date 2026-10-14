"""SQLite schema, connection, initial seed. All money = INTEGER minor units (1/100)."""
import datetime
import hashlib
import os
import pathlib
import shutil
import sqlite3
import sys

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'cashier' CHECK (role IN ('admin','cashier')),
  pin_salt BLOB NOT NULL,
  pin_hash BLOB NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  price INTEGER NOT NULL DEFAULT 0,
  cost INTEGER NOT NULL DEFAULT 0,
  qty INTEGER NOT NULL DEFAULT 0,
  min_qty INTEGER NOT NULL DEFAULT 5,
  tracked INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS serials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  serial TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'in_stock' CHECK (status IN ('in_stock','sold','in_repair')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shifts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  opening_cash INTEGER NOT NULL DEFAULT 0,
  counted_cash INTEGER,
  expected_cash INTEGER,
  diff INTEGER
);
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_no TEXT NOT NULL UNIQUE,
  shift_id INTEGER REFERENCES shifts(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  customer_id INTEGER REFERENCES customers(id),
  created_at TEXT NOT NULL,
  customer_name TEXT,
  customer_phone TEXT,
  subtotal INTEGER NOT NULL DEFAULT 0,
  discount INTEGER NOT NULL DEFAULT 0,
  tax INTEGER NOT NULL DEFAULT 0,
  total INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed','partial_return','returned')),
  notes TEXT
);
CREATE TABLE IF NOT EXISTS sale_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  serial_id INTEGER REFERENCES serials(id),
  name TEXT NOT NULL,
  qty INTEGER NOT NULL DEFAULT 1,
  unit_price INTEGER NOT NULL,
  line_total INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  method TEXT NOT NULL CHECK (method IN ('cash','wallet','credit')),
  amount INTEGER NOT NULL,
  received INTEGER NOT NULL DEFAULT 0,
  change INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sale_returns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sale_id INTEGER NOT NULL REFERENCES sales(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  reason TEXT,
  total INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sale_return_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  return_id INTEGER NOT NULL REFERENCES sale_returns(id) ON DELETE CASCADE,
  sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),
  qty INTEGER NOT NULL,
  amount INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS used_device_purchases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  seller_name TEXT NOT NULL,
  seller_phone TEXT,
  seller_id_no TEXT,
  device_type TEXT,
  brand TEXT,
  model TEXT NOT NULL,
  serial TEXT,
  condition TEXT,
  notes TEXT,
  buy_price INTEGER NOT NULL DEFAULT 0,
  storage TEXT,
  resale_price INTEGER,
  product_id INTEGER REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS repairs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  customer_name TEXT NOT NULL,
  customer_phone TEXT NOT NULL,
  address TEXT,
  device_type TEXT NOT NULL,
  serial TEXT,
  problem TEXT NOT NULL,
  accessories TEXT,
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received','in_review','pending_approval','repaired','rejected','delivered')),
  priority INTEGER NOT NULL DEFAULT 0,
  cost INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS repair_parts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repair_id INTEGER NOT NULL REFERENCES repairs(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  name TEXT NOT NULL,
  qty INTEGER NOT NULL DEFAULT 1,
  unit_price INTEGER NOT NULL DEFAULT 0,
  line_total INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stock_movements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  user_id REFERENCES users(id),
  product_id INTEGER NOT NULL REFERENCES products(id),
  serial_id REFERENCES serials(id),
  qty_change INTEGER NOT NULL,
  qty_after INTEGER NOT NULL,
  reason TEXT NOT NULL,
  ref TEXT
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phone TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(name, phone)
);

CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_movements_product ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_serials_serial ON serials(serial);
"""


def _app_root() -> pathlib.Path:
    """جذر التطبيق: بجانب الـ exe عند التجميد (frozen)، وإلا جذر المشروع."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent.parent


def _legacy_path() -> pathlib.Path:
    """مسار القاعدة القديم (للترحيل لمرة واحدة فقط)؛ تجاوز للفحص عبر SHOP_DB_LEGACY."""
    env = os.environ.get("SHOP_DB_LEGACY")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) / "TechZone" / "shop.db"


def db_path() -> str:
    """data/shop.db بجانب جذر التطبيق، overridable via SHOP_DB (used by selfcheck)."""
    env = os.environ.get("SHOP_DB")
    if env:
        return env
    p = _app_root() / "data" / "shop.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _migrate_once() -> None:
    """ترحيل لمرة واحدة: نسخ القاعدة القديمة إلى data/shop.db إن لم توجد الجديدة."""
    target = pathlib.Path(db_path())
    if target.exists():
        return
    legacy = _legacy_path()
    if legacy.exists() and legacy != target:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
            print(f"migrated legacy db: {legacy} -> {target}")
        except OSError:
            pass


def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_pin(pin: str, salt: bytes) -> bytes:
    # ponytail: PBKDF2-SHA256 @200k بدل argon2id (لا مكتبة خارجية مسموحة)؛ ترقية: argon2-cffi
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)


def connect() -> sqlite3.Connection:
    _migrate_once()  # نسخ القاعدة القديمة لمرة واحدة إن لزم (لا أثر مع SHOP_DB الموجود)
    conn = sqlite3.connect(db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    init_db(conn)
    _ensure_customer_id_column(conn)
    _migrate_customers(conn)
    return conn


def _ensure_customer_id_column(conn):
    """Ensure the customer_id column exists in the sales table."""
    try:
        # Check if column exists
        columns = conn.execute("PRAGMA table_info(sales)").fetchall()
        if not any(col["name"] == "customer_id" for col in columns):
            conn.execute("ALTER TABLE sales ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
            conn.commit()
    except Exception as e:
        print(f"Column ensure error: {e}")


def _migrate_customers(conn):
    """ترحيل العملاء من جدول المبيعات إلى جدول العملاء المنفصل."""
    try:
        # 1. Ensure customers table exists
        conn.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, created_at TEXT NOT NULL, UNIQUE(name, phone))")
        
        # 2. Migrate unique customers from sales to customers table
        count = conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"]
        if count == 0:
            customers = conn.execute(
                "SELECT DISTINCT customer_name, customer_phone FROM sales WHERE customer_name IS NOT NULL"
            ).fetchall()
            for c in customers:
                conn.execute(
                    "INSERT OR IGNORE INTO customers(name, phone, created_at) VALUES(?,?,?)",
                    (c["customer_name"], c["customer_phone"], db.now()),
                )
            conn.commit()
        
        # 3. Link existing sales to customers via name and phone
        conn.execute(
            """UPDATE sales SET customer_id = (
               SELECT id FROM customers 
               WHERE customers.name = sales.customer_name 
               AND (customers.phone = sales.customer_phone OR customers.phone IS NULL)
               LIMIT 1
            ) WHERE customer_id IS NULL AND customer_name IS NOT NULL"""
        )
        conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _seed(conn)
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    """Seed first-run only (settings + users + demo catalog)."""
    if conn.execute("SELECT COUNT(*) c FROM settings").fetchone()["c"]:
        return
    t = now()
    defaults = {
        "store_name": "تك زون للإلكترونيات",
        "store_address": "شارع الملك فهد، الرياض",
        "store_phone": "0500000000",
        "currency": "ر.س",
        "tax_rate": "15",
    }
    conn.executemany("INSERT INTO settings(key, value) VALUES(?, ?)", list(defaults.items()))

    for username, name, role, pin in (("admin", "المدير", "admin", "1234"), ("cashier", "أحمد محمد", "cashier", "1111")):
        salt = os.urandom(16)
        conn.execute(
            "INSERT INTO users(username, name, role, pin_salt, pin_hash, created_at) VALUES(?,?,?,?,?,?)",
            (username, name, role, salt, hash_pin(pin, salt), t),
        )

    cats = ["أجهزة كمبيوتر", "لابتوبات", "إكسسوارات", "شبكات", "كاميرات", "صيانة", "أجهزة لوحية", "صوتيات", "تخزين"]
    for c in cats:
        conn.execute("INSERT INTO categories(name) VALUES(?)", (c,))
    cat_id = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM categories")}

    # sku, name, category, price, cost, qty, min_qty, tracked
    products = [
        ("MBP-M2-16", "ماك بوك برو M2، ذاكرة 16 جيجا، 512 SSD", "لابتوبات", 549900, 480000, 18, 5, 0),
        ("LGM-MX3S", "ماوس لوجيتك لاسلكي MX Master 3S", "إكسسوارات", 45000, 30000, 25, 5, 0),
        ("KB-RGB-002", "كيبورد ميكانيكي RGB للألعاب", "إكسسوارات", 29900, 18000, 12, 5, 0),
        ("TP-SWITCH-8", "سويتش شبكة تي بي لينك 8 منافذ", "شبكات", 12000, 8000, 30, 5, 0),
        ("CAM-WIFI-01", "كاميرا مراقبة خارجية واي فاي", "كاميرات", 35000, 22000, 15, 5, 0),
        ("DL-OPTI-P4", "جهاز مكتبي ديل أوبتيبليكس", "أجهزة كمبيوتر", 210000, 160000, 3, 2, 1),
        ("CPU-I7-12", "معالج إنتل كور i7 الجيل 12", "صيانة", 165000, 130000, 10, 3, 0),
        ("GPU-3060TI", "كرت شاشة RTX 3060 Ti", "صيانة", 189900, 150000, 6, 2, 0),
        ("DX-15-2023", "Dell XPS 15 لابتوب (i7, 16GB, 512GB)", "لابتوبات", 549900, 480000, 2, 5, 0),
        ("SM-SSD-T7", "Samsung T7 SSD 1TB", "تخزين", 42000, 30000, 1, 5, 0),
        ("SN-HP-XM4", "سماعات سوني WH-1000XM4", "صوتيات", 119900, 90000, 24, 5, 0),
        ("CH-25W-USBC", "شاحن 25W USB-C", "إكسسوارات", 5000, 2500, 40, 5, 0),
        ("BAT-14-LT", "بطارية لابتوب 14 إنش", "صيانة", 25000, 15000, 8, 3, 0),
        ("SCR-14-LT", "شاشة لابتوب 14 بوصة", "صيانة", 45000, 30000, 5, 3, 0),
    ]
    for sku, name, cat, price, cost, qty, min_qty, tracked in products:
        cur = conn.execute(
            "INSERT INTO products(sku, name, category_id, price, cost, qty, min_qty, tracked, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (sku, name, cat_id[cat], price, cost, qty, min_qty, tracked, t),
        )
        if tracked:
            for i in range(qty):
                conn.execute(
                    "INSERT INTO serials(product_id, serial, status, created_at) VALUES(?,?,?,?)",
                    (cur.lastrowid, f"DL-{88231 + i}", "in_stock", t),
                )
    conn.commit()
