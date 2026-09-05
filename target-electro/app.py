# -*- coding: utf-8 -*-
"""
Target Electro — prototype e-commerce platform
------------------------------------------------
Flask + SQLite (stdlib sqlite3 — no ORM dependency, so it runs anywhere
Python 3 + Flask run, no extra native-build packages needed).

The server is the single source of truth: prices/stock/availability are
always re-checked in the backend, never trusted from the client. No fake
store content is ever generated — empty states are rendered instead.

Run:
    pip install -r requirements.txt
    python seed.py --with-demo      # or without --with-demo for a clean store
    python app.py
Then open http://127.0.0.1:5000
Admin panel: http://127.0.0.1:5000/admin/login
"""
import os
import re
import sqlite3
import functools
from datetime import datetime

from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, jsonify, abort, g)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "store.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

# ---------------------------------------------------------------------------
# Product-type spec schema (extensible). Each product type defines the exact
# fields that apply to it — this drives the dynamic admin form and ensures
# the product page never shows an irrelevant "GPU: —" on a pair of earbuds.
# ---------------------------------------------------------------------------
PRODUCT_TYPE_FIELDS = {
    "smartphone": [("ram","الذاكرة العشوائية (RAM)"),("storage","التخزين"),("soc","المعالج (SoC)"),("display_size","حجم الشاشة"),("resolution","الدقة"),("refresh_rate","معدل التحديث"),("rear_camera","الكاميرا الخلفية"),("front_camera","الكاميرا الأمامية"),("battery","البطارية"),("charging_speed","سرعة الشحن"),("network_5g","دعم 5G"),("nfc","NFC"),("gyroscope","جيروسكوب"),("os","نظام التشغيل"),("colors","الألوان"),("warranty","الضمان")],
    "feature_phone": [("battery","البطارية"),("display_size","حجم الشاشة"),("network","الشبكة"),("camera","الكاميرا"),("dual_sim","شريحتان"),("radio","راديو FM"),("colors","الألوان"),("warranty","الضمان")],
    "tws": [("anc","عزل الضوضاء (ANC)"),("transparency_mode","وضع الشفافية"),("battery_life","عمر البطارية"),("case_battery","بطارية العلبة"),("bluetooth_version","إصدار البلوتوث"),("codec","Codec"),("microphones","الميكروفونات"),("water_resistance","مقاومة الماء"),("connection","لاسلكي/سلكي"),("colors","الألوان"),("warranty","الضمان")],
    "headphones": [("anc","عزل الضوضاء (ANC)"),("transparency_mode","وضع الشفافية"),("battery_life","عمر البطارية"),("bluetooth_version","إصدار البلوتوث"),("microphones","الميكروفونات"),("water_resistance","مقاومة الماء"),("connection","لاسلكي/سلكي"),("colors","الألوان"),("warranty","الضمان")],
    "earphones": [("driver","Driver"),("connection","لاسلكي/سلكي"),("microphones","الميكروفونات"),("water_resistance","مقاومة الماء"),("colors","الألوان"),("warranty","الضمان")],
    "speaker": [("power","القدرة"),("battery_life","عمر البطارية"),("bluetooth_version","إصدار البلوتوث"),("water_resistance","مقاومة الماء"),("connection","الاتصال"),("colors","الألوان"),("warranty","الضمان")],
    "microphone": [("connection","الاتصال"),("pickup","نمط الالتقاط"),("frequency","نطاق التردد"),("colors","الألوان"),("warranty","الضمان")],
    "laptop": [("cpu","المعالج (CPU)"),("gpu","كرت الشاشة (GPU)"),("ram","الرام"),("storage","التخزين"),("display_size","حجم الشاشة"),("resolution","الدقة"),("refresh_rate","معدل التحديث"),("battery","البطارية"),("os","نظام التشغيل"),("ports","المنافذ"),("colors","الألوان"),("warranty","الضمان")],
    "desktop": [("cpu","المعالج (CPU)"),("gpu","كرت الشاشة (GPU)"),("ram","الرام"),("storage","التخزين"),("motherboard","اللوحة الأم"),("psu","مزود الطاقة"),("os","نظام التشغيل"),("warranty","الضمان")],
    "mini_pc": [("cpu","المعالج (CPU)"),("gpu","كرت الشاشة (GPU)"),("ram","الرام"),("storage","التخزين"),("ports","المنافذ"),("os","نظام التشغيل"),("warranty","الضمان")],
    "mouse": [("sensor","الحساس"),("dpi","DPI"),("polling_rate","Polling Rate"),("weight","الوزن"),("buttons","الأزرار"),("connection","لاسلكي/سلكي"),("battery","البطارية"),("colors","الألوان"),("warranty","الضمان")],
    "keyboard": [("switch_type","نوع السويتش"),("layout","التخطيط"),("connection","لاسلكي/سلكي"),("rgb","RGB"),("polling_rate","Polling Rate"),("battery","البطارية"),("colors","الألوان"),("warranty","الضمان")],
    "monitor": [("display_size","حجم الشاشة"),("resolution","الدقة"),("panel_type","نوع اللوحة"),("refresh_rate","معدل التحديث"),("response_time","زمن الاستجابة"),("hdr","HDR"),("adaptive_sync","Adaptive Sync"),("ports","المنافذ"),("colors","الألوان"),("warranty","الضمان")],
    "gaming_mouse": [("sensor","الحساس"),("dpi","DPI"),("polling_rate","Polling Rate"),("weight","الوزن"),("buttons","الأزرار"),("connection","لاسلكي/سلكي"),("battery","البطارية"),("warranty","الضمان")],
    "gaming_keyboard": [("switch_type","نوع السويتش"),("layout","التخطيط"),("connection","لاسلكي/سلكي"),("rgb","RGB"),("polling_rate","Polling Rate"),("battery","البطارية"),("warranty","الضمان")],
    "gaming_headset": [("anc","ANC"),("connection","لاسلكي/سلكي"),("microphones","الميكروفونات"),("battery_life","عمر البطارية"),("surround","الصوت المحيطي"),("warranty","الضمان")],
    "gaming_monitor": [("display_size","حجم الشاشة"),("resolution","الدقة"),("panel_type","نوع اللوحة"),("refresh_rate","معدل التحديث"),("response_time","زمن الاستجابة"),("hdr","HDR"),("adaptive_sync","Adaptive Sync"),("ports","المنافذ"),("warranty","الضمان")],
    "controller": [("connection","الاتصال"),("platform","المنصات"),("battery","البطارية"),("vibration","الاهتزاز"),("wireless","لاسلكي"),("colors","الألوان"),("warranty","الضمان")],
    "smartwatch": [("display_size","حجم الشاشة"),("display_type","نوع الشاشة"),("battery_life","عمر البطارية"),("water_resistance","مقاومة الماء"),("gps","GPS"),("nfc","NFC"),("os","النظام"),("colors","الألوان"),("warranty","الضمان")],
    "smart_band": [("display_size","حجم الشاشة"),("battery_life","عمر البطارية"),("water_resistance","مقاومة الماء"),("gps","GPS"),("colors","الألوان"),("warranty","الضمان")],
    "camera": [("sensor","الحساس"),("resolution","الدقة"),("video","الفيديو"),("lens","العدسة"),("stabilization","التثبيت"),("battery","البطارية"),("colors","الألوان"),("warranty","الضمان")],
    "tv": [("display_size","حجم الشاشة"),("resolution","الدقة"),("panel_type","نوع اللوحة"),("refresh_rate","معدل التحديث"),("hdr","HDR"),("os","النظام الذكي"),("ports","المنافذ"),("warranty","الضمان")],
    "accessory": [("connection","الاتصال"),("compatibility","التوافق"),("colors","الألوان"),("warranty","الضمان")],
}

PRODUCT_TYPE_LABELS = {
    "smartphone":"هاتف ذكي","feature_phone":"هاتف عادي","tws":"TWS","headphones":"سماعات رأس","earphones":"سماعات أذن","speaker":"سبيكر بلوتوث","microphone":"مايكروفون",
    "laptop":"لابتوب","desktop":"كمبيوتر مكتبي","mini_pc":"Mini PC","mouse":"ماوس","keyboard":"كيبورد","monitor":"شاشة","controller":"يد تحكم",
    "smartwatch":"ساعة ذكية","smart_band":"سوار ذكي","gaming_mouse":"ماوس ألعاب","gaming_keyboard":"كيبورد ألعاب","gaming_headset":"سماعة ألعاب","gaming_monitor":"شاشة ألعاب","camera":"كاميرا","tv":"تلفزيون","accessory":"إكسسوار"
}

CATEGORY_DEFS = [
    ("الهواتف","mobile",[("smartphone","هاتف ذكي"),("feature_phone","هاتف عادي")]),
    ("السماعات والصوتيات","audio",[("tws","TWS"),("headphones","سماعات رأس"),("earphones","سماعات أذن"),("speaker","سبيكر بلوتوث"),("microphone","مايكروفون")]),
    ("اللابتوبات والكمبيوترات","computers",[("laptop","لابتوب"),("desktop","كمبيوتر مكتبي"),("mini_pc","Mini PC")]),
    ("الساعات الذكية","smart-devices",[("smartwatch","ساعة ذكية"),("smart_band","سوار ذكي")]),
    ("الألعاب وملحقاتها","gaming",[("controller","يد تحكم"),("gaming_mouse","ماوس ألعاب"),("gaming_keyboard","كيبورد ألعاب"),("gaming_headset","سماعة ألعاب"),("gaming_monitor","شاشة ألعاب")]),
    ("ملحقات الكمبيوتر","pc-accessories",[("mouse","ماوس"),("keyboard","كيبورد"),("monitor","شاشة")]),
    ("الكاميرات","cameras",[("camera","كاميرا")]),
    ("الشاشات والتلفزيونات","displays",[("tv","تلفزيون"),("monitor","شاشة")]),
    ("الإكسسوارات","accessories",[("accessory","إكسسوار")]),
    ("أخرى","other",[("accessory","أخرى")]),
]

BRANDS_BY_CATEGORY = {
    "mobile":["Apple","Samsung","Xiaomi","Redmi","POCO","HONOR","Huawei","OPPO","OnePlus","Realme","vivo","Motorola","Tecno","Infinix","Nokia","Google","Sony","ASUS","ZTE","Nothing"],
    "computers":["Lenovo","HP","Dell","ASUS","Acer","MSI","Apple","Microsoft","Huawei","Samsung","Gigabyte"],
    "audio":["Apple","Samsung","Sony","JBL","Anker","Soundcore","Xiaomi","Redmi","Huawei","HONOR","OPPO","OnePlus","Baseus","UGREEN","QCY","Haylou","Edifier","Razer","Logitech","HyperX"],
    "gaming":["Logitech","Razer","HyperX","SteelSeries","Corsair","ASUS","ASUS ROG","MSI","A4Tech","Bloody","Redragon","Cooler Master","Glorious","Zowie"],
    "pc-accessories":["Logitech","Razer","HyperX","SteelSeries","Corsair","ASUS","ASUS ROG","MSI","A4Tech","Bloody","Redragon","Cooler Master","Glorious","Zowie"],
    "smart-devices":["Apple","Samsung","Xiaomi","Redmi","HONOR","Huawei","OPPO","OnePlus","Amazfit","Garmin"],
    "cameras":["Canon","Nikon","Sony","Fujifilm","Panasonic","GoPro","DJI"],
    "displays":["Samsung","LG","Sony","TCL","Hisense","ASUS","Acer","MSI","Dell","Lenovo","Gigabyte"],
    "accessories":["Apple","Samsung","Xiaomi","Redmi","Anker","Baseus","UGREEN","Belkin","Spigen","ESR"],
    "other":[]
}

STOCK_LOW_THRESHOLD = 5
ORDER_STATUSES = ["طلب جديد", "تم التأكيد", "قيد التجهيز", "خرج للتوصيل", "تم التسليم", "ملغي"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_user(
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS category(
    id INTEGER PRIMARY KEY, name_ar TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, enabled INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS product_type(
    id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL, slug TEXT UNIQUE NOT NULL, name_ar TEXT NOT NULL,
    FOREIGN KEY(category_id) REFERENCES category(id));

CREATE TABLE IF NOT EXISTS brand(
    id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, logo TEXT DEFAULT '', enabled INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS brand_category(
    brand_id INTEGER NOT NULL, category_id INTEGER NOT NULL,
    PRIMARY KEY(brand_id, category_id),
    FOREIGN KEY(brand_id) REFERENCES brand(id) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES category(id) ON DELETE CASCADE);

CREATE TABLE IF NOT EXISTS product(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, brand_id INTEGER, category_id INTEGER NOT NULL,
    product_type_id INTEGER NOT NULL, model TEXT, price INTEGER NOT NULL, old_price INTEGER,
    stock INTEGER NOT NULL DEFAULT 0, description TEXT DEFAULT '', images TEXT DEFAULT '',
    visible INTEGER DEFAULT 1, featured INTEGER DEFAULT 0, new_arrival INTEGER DEFAULT 0,
    is_offer INTEGER DEFAULT 0, is_demo INTEGER DEFAULT 0,
    created_at TEXT, updated_at TEXT,
    FOREIGN KEY(brand_id) REFERENCES brand(id),
    FOREIGN KEY(category_id) REFERENCES category(id),
    FOREIGN KEY(product_type_id) REFERENCES product_type(id));

CREATE TABLE IF NOT EXISTS product_spec(
    id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
    FOREIGN KEY(product_id) REFERENCES product(id));

CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL, phone TEXT NOT NULL,
    governorate TEXT, city TEXT, area TEXT, address TEXT, notes TEXT,
    status TEXT DEFAULT 'طلب جديد', total INTEGER DEFAULT 0, created_at TEXT);

CREATE TABLE IF NOT EXISTS order_item(
    id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, product_id INTEGER,
    product_name TEXT, price INTEGER, qty INTEGER DEFAULT 1,
    FOREIGN KEY(order_id) REFERENCES orders(id));
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(brand)").fetchall()}
    if "logo" not in cols:
        conn.execute("ALTER TABLE brand ADD COLUMN logo TEXT DEFAULT ''")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Lightweight model wrappers around sqlite3.Row (attribute access for templates)
# ---------------------------------------------------------------------------

class Brand:
    def __init__(self, row):
        self.id, self.name, self.enabled = row["id"], row["name"], bool(row["enabled"])
        self.logo = row["logo"] if "logo" in row.keys() else ""


class ProductType:
    def __init__(self, row):
        self.id, self.category_id = row["id"], row["category_id"]
        self.slug, self.name_ar = row["slug"], row["name_ar"]

    @property
    def fields(self):
        return PRODUCT_TYPE_FIELDS.get(self.slug, [])


class Category:
    def __init__(self, row):
        self.id, self.name_ar, self.slug = row["id"], row["name_ar"], row["slug"]
        self.enabled = bool(row["enabled"])
        self.product_types = []


class Spec:
    def __init__(self, key, value):
        self.key, self.value = key, value


class Product:
    def __init__(self, row):
        self.id = row["id"]
        self.name = row["name"]
        self.brand_id = row["brand_id"]
        self.category_id = row["category_id"]
        self.product_type_id = row["product_type_id"]
        self.model = row["model"]
        self.price = row["price"]
        self.old_price = row["old_price"]
        self.stock = row["stock"]
        self.description = row["description"] or ""
        self.images = row["images"] or ""
        self.visible = bool(row["visible"])
        self.featured = bool(row["featured"])
        self.new_arrival = bool(row["new_arrival"])
        self.is_offer = bool(row["is_offer"])
        self.is_demo = bool(row["is_demo"])
        self.created_at_raw = row["created_at"]
        self.brand = None
        self.category = None
        self.product_type = None
        self.specs = []

    @property
    def image_list(self):
        return [i.strip() for i in self.images.split(",") if i.strip()]

    @property
    def discount_pct(self):
        if self.old_price and self.old_price > self.price:
            return round((1 - self.price / self.old_price) * 100)
        return 0

    @property
    def stock_status(self):
        if self.stock <= 0:
            return ("غير متوفر", "out")
        if self.stock <= STOCK_LOW_THRESHOLD:
            return ("كمية قليلة", "low")
        return ("متوفر", "in")

    def spec_dict(self):
        return {s.key: s.value for s in self.specs}


class Order:
    def __init__(self, row):
        self.id = row["id"]
        self.customer_name = row["customer_name"]
        self.phone = row["phone"]
        self.governorate = row["governorate"]
        self.city = row["city"]
        self.area = row["area"]
        self.address = row["address"]
        self.notes = row["notes"]
        self.status = row["status"]
        self.total = row["total"]
        self.created_at = datetime.fromisoformat(row["created_at"])
        self.items = []


class OrderItem:
    def __init__(self, row):
        self.id = row["id"]
        self.order_id = row["order_id"]
        self.product_id = row["product_id"]
        self.product_name = row["product_name"]
        self.price = row["price"]
        self.qty = row["qty"]


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

def get_brand(db, brand_id):
    if not brand_id:
        return None
    row = db.execute("SELECT * FROM brand WHERE id=?", (brand_id,)).fetchone()
    return Brand(row) if row else None


def get_category(db, category_id):
    row = db.execute("SELECT * FROM category WHERE id=?", (category_id,)).fetchone()
    return Category(row) if row else None


def get_product_type(db, pt_id):
    row = db.execute("SELECT * FROM product_type WHERE id=?", (pt_id,)).fetchone()
    return ProductType(row) if row else None


def hydrate_product(db, row):
    p = Product(row)
    p.brand = get_brand(db, p.brand_id)
    p.category = get_category(db, p.category_id)
    p.product_type = get_product_type(db, p.product_type_id)
    spec_rows = db.execute("SELECT key, value FROM product_spec WHERE product_id=?", (p.id,)).fetchall()
    p.specs = [Spec(r["key"], r["value"]) for r in spec_rows]
    return p


def hydrate_products(db, rows):
    return [hydrate_product(db, r) for r in rows]


def all_categories(db, enabled_only=True):
    q = "SELECT * FROM category" + (" WHERE enabled=1" if enabled_only else "")
    cats = [Category(r) for r in db.execute(q).fetchall()]
    for c in cats:
        c.product_types = [ProductType(r) for r in
                            db.execute("SELECT * FROM product_type WHERE category_id=?", (c.id,)).fetchall()]
    return cats


def hydrate_order(db, row):
    o = Order(row)
    item_rows = db.execute("SELECT * FROM order_item WHERE order_id=?", (o.id,)).fetchall()
    o.items = [OrderItem(r) for r in item_rows]
    return o


def now_iso():
    return datetime.utcnow().isoformat()


def format_iqd(amount):
    return f"{amount:,.0f} د.ع"


app.jinja_env.filters["iqd"] = format_iqd
app.jinja_env.globals["PRODUCT_TYPE_LABELS"] = PRODUCT_TYPE_LABELS
app.jinja_env.globals["ORDER_STATUSES"] = ORDER_STATUSES


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*a, **kw)
    return wrapped


def get_cart():
    return session.get("cart", {})


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_contents(db):
    """Re-validates the cart against the live DB. Never trusts client data."""
    cart = get_cart()
    items, total, changed = [], 0, False
    clean_cart = {}
    for pid, qty in cart.items():
        row = db.execute("SELECT * FROM product WHERE id=?", (int(pid),)).fetchone()
        if not row or not row["visible"]:
            changed = True
            continue
        product = hydrate_product(db, row)
        qty = max(1, min(int(qty), product.stock)) if product.stock > 0 else 0
        if qty <= 0:
            changed = True
            continue
        clean_cart[pid] = qty
        line_total = product.price * qty
        total += line_total
        items.append({"product": product, "qty": qty, "line_total": line_total})
    if changed:
        save_cart(clean_cart)
    return items, total


# ---------------------------------------------------------------------------
# Target AI — conversational, database-grounded assistant.
# No external model/API is required for the local build. It handles basic
# conversation and shopping intent, while product facts always come from DB.
# ---------------------------------------------------------------------------

AR_NUM_WORDS = {"ألف": 1_000, "الف": 1_000, "آلاف": 1_000, "مليون": 1_000_000}
CATEGORY_KEYWORDS = {
    "smartphone": ["موبايل", "هاتف", "جوال", "آيفون", "ايفون", "iphone", "سامسونگ", "سامسونج"],
    "tws": ["سماعة", "سماعات", "ايربودز", "إيربودز", "airpods", "tws", "anc"],
    "headphones": ["هيدفون", "headphone", "سماعة رأس"],
    "laptop": ["لابتوب", "laptop", "حاسبة", "كمبيوتر محمول"],
}
GREETING_WORDS = ["hello", "hi", "hey", "هلا", "هلو", "هلوو", "السلام عليكم", "سلام عليكم", "السلامعليكم"]
THANKS_WORDS = ["شكرا", "شكرًا", "مشكور", "مشكورة", "thanks", "thank you"]
GOODBYE_WORDS = ["باي", "وداعا", "مع السلامة", "اشوفك", "goodbye", "bye"]
HELP_WORDS = ["شنو تكدر", "شنو تگدر", "ماذا تستطيع", "شنو تسوي", "شلون تساعد", "كيف تساعد", "help"]
CATEGORY_INFO = {
    "هواتف": "mobile", "موبايلات": "mobile", "الهواتف": "mobile",
    "سماعات": "audio", "صوتيات": "audio", "الصوتيات": "audio",
    "لابتوبات": "computers", "حواسيب": "computers", "الحواسيب": "computers",
}


def normalize_ai_text(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def parse_budget(text):
    text = text.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ألف|الف|آلاف|مليون)?", text)
    if not m:
        return None
    num = float(m.group(1))
    scale = AR_NUM_WORDS.get(m.group(2), 1) if m.group(2) else 1
    if scale == 1 and num < 10000 and any(w in text for w in ["بحدود", "أقل من", "اقل من", "ميزانيت", "عندي", "حدود"]):
        scale = 1000
    return int(num * scale)


def detect_category_slug(text):
    text_n = normalize_ai_text(text)
    for slug, words in CATEGORY_KEYWORDS.items():
        if any(w in text_n for w in words):
            return slug
    return None


def detect_brand(db, text):
    text_n = normalize_ai_text(text)
    for row in db.execute("SELECT * FROM brand WHERE enabled=1").fetchall():
        if normalize_ai_text(row["name"]) in text_n:
            return Brand(row)
    return None


def conversational_intent(text):
    n = normalize_ai_text(text)
    if not n:
        return "empty"
    if any(n == w or n.startswith(w + " ") or n.endswith(" " + w) for w in GREETING_WORDS):
        return "greeting"
    if any(w in n for w in THANKS_WORDS):
        return "thanks"
    if any(w in n for w in GOODBYE_WORDS):
        return "goodbye"
    if any(w in n for w in HELP_WORDS):
        return "help"
    if any(k in n for k in ["عندكم", "عندكم شي", "شنو عندكم", "شنو موجود", "المنتجات", "فئاتكم", "الفئات"]):
        return "catalog"
    return "shopping"


def ai_search(db, query):
    text = query.strip()
    intent = conversational_intent(text)

    if intent == "empty":
        return "اكتبلي طلبك، مثلاً: «أريد موبايل للألعاب بأقل من 300 ألف»." , []
    if intent == "greeting":
        return "هلا بيك 👋 شلون أگدر أساعدك؟ أگدر أساعدك تختار من المنتجات المتوفرة حسب النوع والميزانية والمواصفات.", []
    if intent == "thanks":
        return "العفو 🌟 بالخدمة!", []
    if intent == "goodbye":
        return "تدلل 👋 نورت Target Electro.", []
    if intent == "help":
        return "أگدر أساعدك أبحث عن المنتجات، أقارن الخيارات، أتحقق من السعر والتوفر، وأرشحلك شي مناسب لميزانيتك.", []
    if intent == "catalog":
        cats = db.execute("SELECT name_ar FROM category WHERE enabled=1 ORDER BY id").fetchall()
        if not cats:
            return "حالياً ماكو فئات مضافة.", []
        names = "، ".join(r["name_ar"] for r in cats)
        return f"الفئات المضافة حالياً: {names}. شنو النوع اللي تدور عليه؟", []

    budget = parse_budget(text)
    cat_slug = detect_category_slug(text)
    brand = detect_brand(db, text)

    sql = "SELECT * FROM product WHERE visible=1 AND stock>0"
    params = []
    if cat_slug:
        pt = db.execute("SELECT id FROM product_type WHERE slug=?", (cat_slug,)).fetchone()
        if pt:
            sql += " AND product_type_id=?"
            params.append(pt["id"])
    if brand:
        sql += " AND brand_id=?"
        params.append(brand.id)
    if budget:
        sql += " AND price<=?"
        params.append(budget)

    # For a general request, search text in the real catalog too.
    if not (cat_slug or brand or budget):
        terms = [t for t in re.split(r"\s+", normalize_ai_text(text)) if len(t) >= 2]
        if terms:
            clauses = []
            for term in terms[:6]:
                clauses.append("(LOWER(p.name) LIKE ? OR LOWER(COALESCE(b.name,'')) LIKE ? OR LOWER(COALESCE(p.model,'')) LIKE ?)")
                like = f"%{term}%"
                params.extend([like, like, like])
            sql = "SELECT p.* FROM product p LEFT JOIN brand b ON b.id=p.brand_id WHERE p.visible=1 AND p.stock>0 AND (" + " OR ".join(clauses) + ")"

    sql += " ORDER BY price ASC LIMIT 6"
    rows = db.execute(sql, params).fetchall()
    results = hydrate_products(db, rows)

    if not results:
        if budget or cat_slug or brand:
            return "ما عندنا حالياً منتج يطابق طلبك بشكل كامل. جرّب توسع الميزانية أو غيّر النوع/المواصفات.", []
        return "أگدر أساعدك بالبحث عن المنتجات. اذكرلي مثلاً النوع والميزانية: «أريد موبايل للألعاب بأقل من 300 ألف»." , []

    if budget:
        reason = f"لقيتلك {len(results)} خيار متوفر ضمن ميزانيتك." 
    else:
        reason = f"لقيتلك {len(results)} خيار متوفر من الكتالوج الحالي."
    return reason, results


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    db = get_db()
    featured = hydrate_products(db, db.execute(
        "SELECT * FROM product WHERE visible=1 AND featured=1 AND stock>0 LIMIT 8").fetchall())
    new_arrivals = hydrate_products(db, db.execute(
        "SELECT * FROM product WHERE visible=1 AND new_arrival=1 AND stock>0 ORDER BY created_at DESC LIMIT 8").fetchall())
    offers = hydrate_products(db, db.execute(
        "SELECT * FROM product WHERE visible=1 AND is_offer=1 AND stock>0 LIMIT 8").fetchall())
    categories = all_categories(db, enabled_only=True)
    return render_template("index.html", featured=featured, new_arrivals=new_arrivals,
                            offers=offers, categories=categories)


@app.route("/products")
def products():
    db = get_db()
    cat_slug = request.args.get("category")
    type_slug = request.args.get("type")
    brand_id = request.args.get("brand", type=int)
    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)
    sort = request.args.get("sort", "newest")
    keyword = request.args.get("q", "").strip()

    category, ptype = None, None
    sql = "SELECT product.* FROM product"
    joins = ""
    where = ["product.visible=1"]
    params = []

    if cat_slug:
        cat_row = db.execute("SELECT * FROM category WHERE slug=?", (cat_slug,)).fetchone()
        if not cat_row:
            abort(404)
        category = Category(cat_row)
        where.append("product.category_id=?")
        params.append(category.id)
    if type_slug:
        pt_row = db.execute("SELECT * FROM product_type WHERE slug=?", (type_slug,)).fetchone()
        if not pt_row:
            abort(404)
        ptype = ProductType(pt_row)
        where.append("product.product_type_id=?")
        params.append(ptype.id)
    if brand_id:
        where.append("product.brand_id=?")
        params.append(brand_id)
    if min_price is not None:
        where.append("product.price>=?")
        params.append(min_price)
    if max_price is not None:
        where.append("product.price<=?")
        params.append(max_price)
    if keyword:
        joins = " LEFT JOIN brand ON brand.id = product.brand_id"
        where.append("(product.name LIKE ? OR product.model LIKE ? OR brand.name LIKE ?)")
        like = f"%{keyword}%"
        params += [like, like, like]

    sql += joins + " WHERE " + " AND ".join(where)
    if sort == "price_asc":
        sql += " ORDER BY product.price ASC"
    elif sort == "price_desc":
        sql += " ORDER BY product.price DESC"
    else:
        sql += " ORDER BY product.created_at DESC"

    rows = db.execute(sql, params).fetchall()
    results = hydrate_products(db, rows)

    brands = [Brand(r) for r in db.execute("SELECT * FROM brand WHERE enabled=1 ORDER BY name").fetchall()]
    categories = all_categories(db, enabled_only=True)
    types = [ProductType(r) for r in db.execute(
        "SELECT * FROM product_type WHERE category_id=?", (category.id,)).fetchall()] if category else []

    return render_template("products.html", products=results, categories=categories,
                            brands=brands, types=types, category=category, ptype=ptype,
                            keyword=keyword, sort=sort)


@app.route("/product/<int:pid>")
def product_detail(pid):
    db = get_db()
    row = db.execute("SELECT * FROM product WHERE id=? AND visible=1", (pid,)).fetchone()
    if not row:
        abort(404)
    product = hydrate_product(db, row)
    fields = product.product_type.fields
    specs = product.spec_dict()
    display_specs = [(label, specs[key]) for key, label in fields if specs.get(key)]
    related_rows = db.execute(
        "SELECT * FROM product WHERE category_id=? AND id!=? AND visible=1 LIMIT 4",
        (product.category_id, product.id)).fetchall()
    related = hydrate_products(db, related_rows)
    return render_template("product.html", p=product, display_specs=display_specs, related=related)


@app.route("/cart")
def cart_view():
    db = get_db()
    items, total = cart_contents(db)
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add", methods=["POST"])
def cart_add():
    db = get_db()
    pid = request.form.get("product_id")
    qty = max(1, request.form.get("qty", 1, type=int))
    row = db.execute("SELECT * FROM product WHERE id=?", (pid,)).fetchone()
    if not row or not row["visible"] or row["stock"] <= 0:
        flash("هذا المنتج غير متوفر حالياً.", "error")
        return redirect(request.referrer or url_for("home"))
    cart = get_cart()
    current = cart.get(pid, 0)
    cart[pid] = min(current + qty, row["stock"])
    save_cart(cart)
    flash("تمت الإضافة إلى السلة.", "success")
    return redirect(request.referrer or url_for("cart_view"))


@app.route("/cart/update", methods=["POST"])
def cart_update():
    db = get_db()
    pid = request.form.get("product_id")
    qty = request.form.get("qty", 1, type=int)
    cart = get_cart()
    if qty <= 0:
        cart.pop(pid, None)
    else:
        row = db.execute("SELECT stock FROM product WHERE id=?", (pid,)).fetchone()
        if row:
            cart[pid] = min(qty, row["stock"])
    save_cart(cart)
    return redirect(url_for("cart_view"))


@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    pid = request.form.get("product_id")
    cart = get_cart()
    cart.pop(pid, None)
    save_cart(cart)
    return redirect(url_for("cart_view"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    db = get_db()
    items, total = cart_contents(db)

    if request.method == "GET":
        if not items:
            flash("سلتك فارغة.", "error")
            return redirect(url_for("cart_view"))
        return render_template("checkout.html", items=items, total=total)

    if not items:
        flash("سلتك فارغة.", "error")
        return redirect(url_for("cart_view"))

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    governorate = request.form.get("governorate", "").strip()
    city = request.form.get("city", "").strip()
    area = request.form.get("area", "").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()

    if not name or not phone or not governorate or not address:
        flash("الرجاء تعبئة الحقول المطلوبة.", "error")
        return render_template("checkout.html", items=items, total=total)

    try:
        cur = db.cursor()
        cur.execute("BEGIN")
        order_total = 0
        cur.execute(
            "INSERT INTO orders(customer_name, phone, governorate, city, area, address, notes, status, total, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (name, phone, governorate, city, area, address, notes, "طلب جديد", 0, now_iso()))
        order_id = cur.lastrowid

        for entry in items:
            product_id = entry["product"].id
            qty = entry["qty"]
            row = cur.execute("SELECT * FROM product WHERE id=?", (product_id,)).fetchone()
            if not row or not row["visible"] or row["stock"] < qty:
                raise ValueError(f"المنتج «{entry['product'].name}» لم يعد متوفراً بالكمية المطلوبة.")
            cur.execute("UPDATE product SET stock = stock - ? WHERE id=?", (qty, product_id))
            line_total = row["price"] * qty
            order_total += line_total
            cur.execute(
                "INSERT INTO order_item(order_id, product_id, product_name, price, qty) VALUES (?,?,?,?,?)",
                (order_id, product_id, row["name"], row["price"], qty))

        cur.execute("UPDATE orders SET total=? WHERE id=?", (order_total, order_id))
        db.commit()
    except ValueError as e:
        db.rollback()
        flash(str(e), "error")
        items, total = cart_contents(db)
        return render_template("checkout.html", items=items, total=total)

    save_cart({})
    flash("تم استلام طلبك بنجاح!", "success")
    return redirect(url_for("order_track", order_id=order_id))


@app.route("/order/<int:order_id>")
def order_track(order_id):
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        abort(404)
    order = hydrate_order(db, row)
    return render_template("order_track.html", order=order)


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/api/ai", methods=["POST"])
def api_ai():
    db = get_db()
    query = request.json.get("query", "") if request.is_json else request.form.get("query", "")
    message, results = ai_search(db, query)
    return jsonify({
        "message": message,
        "products": [{
            "id": p.id, "name": p.name, "price": format_iqd(p.price),
            "old_price": format_iqd(p.old_price) if p.old_price else None,
            "image": p.image_list[0] if p.image_list else None,
            "url": url_for("product_detail", pid=p.id),
            "stock_status": p.stock_status[0],
        } for p in results]
    })


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = db.execute("SELECT * FROM admin_user WHERE username=?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session["is_admin"] = True
            session["admin_username"] = username
            flash("تم تسجيل الدخول بنجاح.", "success")
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/")
@admin_required
def admin_dashboard():
    db = get_db()
    product_count = db.execute("SELECT COUNT(*) c FROM product").fetchone()["c"]
    low_stock = db.execute("SELECT COUNT(*) c FROM product WHERE stock>0 AND stock<=?", (STOCK_LOW_THRESHOLD,)).fetchone()["c"]
    out_of_stock = db.execute("SELECT COUNT(*) c FROM product WHERE stock<=0").fetchone()["c"]
    order_count = db.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    total_sales = db.execute("SELECT COALESCE(SUM(total),0) s FROM orders WHERE status!='ملغي'").fetchone()["s"]
    recent_rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 5").fetchall()
    recent_orders = [hydrate_order(db, r) for r in recent_rows]
    return render_template("admin/dashboard.html", product_count=product_count, low_stock=low_stock,
                            out_of_stock=out_of_stock, order_count=order_count,
                            recent_orders=recent_orders, total_sales=total_sales)


@app.route("/admin/products")
@admin_required
def admin_products():
    db = get_db()
    rows = db.execute("SELECT * FROM product ORDER BY created_at DESC").fetchall()
    items = hydrate_products(db, rows)
    return render_template("admin/products.html", products=items)


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    return _admin_product_form(None)


@app.route("/admin/products/<int:pid>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(pid):
    db = get_db()
    row = db.execute("SELECT * FROM product WHERE id=?", (pid,)).fetchone()
    if not row:
        abort(404)
    product = hydrate_product(db, row)
    return _admin_product_form(product)


def _admin_product_form(product):
    db = get_db()
    categories = all_categories(db, enabled_only=False)
    brands = [Brand(r) for r in db.execute("SELECT * FROM brand WHERE enabled=1 ORDER BY name").fetchall()]
    brand_category_map = {}
    for b in brands:
        brand_category_map[b.id] = [r["category_id"] for r in db.execute("SELECT category_id FROM brand_category WHERE brand_id=?", (b.id,)).fetchall()]
    types_by_cat = {c.id: [{"id": t.id, "slug": t.slug, "name": t.name_ar} for t in c.product_types] for c in categories}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id", type=int)
        product_type_id = request.form.get("product_type_id", type=int)
        brand_id = request.form.get("brand_id", type=int) or None
        price = request.form.get("price", type=int)
        old_price = request.form.get("old_price", type=int) or None
        stock = request.form.get("stock", type=int) or 0
        model = request.form.get("model", "").strip()
        description = request.form.get("description", "").strip()
        images = request.form.get("images", "").strip()

        if not name or not category_id or not product_type_id or price is None:
            flash("يرجى تعبئة الاسم والفئة والنوع والسعر.", "error")
            return render_template("admin/product_form.html", product=product, categories=categories, brands=brands, types_by_cat=types_by_cat, PRODUCT_TYPE_FIELDS=PRODUCT_TYPE_FIELDS, brand_category_map=brand_category_map)
        if price < 0:
            flash("السعر لا يمكن أن يكون سالباً.", "error")
            return render_template("admin/product_form.html", product=product, categories=categories, brands=brands, types_by_cat=types_by_cat, PRODUCT_TYPE_FIELDS=PRODUCT_TYPE_FIELDS, brand_category_map=brand_category_map)
        if stock < 0:
            flash("الكمية لا يمكن أن تكون سالبة.", "error")
            return render_template("admin/product_form.html", product=product, categories=categories, brands=brands, types_by_cat=types_by_cat, PRODUCT_TYPE_FIELDS=PRODUCT_TYPE_FIELDS, brand_category_map=brand_category_map)

        upload = request.files.get("product_image")
        if upload and upload.filename:
            ext = os.path.splitext(secure_filename(upload.filename))[1].lower()
            if ext not in {".jpg",".jpeg",".png",".webp"}:
                flash("نوع الصورة غير صالح. استخدم JPG أو PNG أو WEBP.", "error")
                return render_template("admin/product_form.html", product=product, categories=categories, brands=brands, types_by_cat=types_by_cat, PRODUCT_TYPE_FIELDS=PRODUCT_TYPE_FIELDS, brand_category_map=brand_category_map)
            upload_dir = os.path.join(BASE_DIR, "static", "uploads", "products")
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"product_{product.id if product else 'new'}_{int(datetime.utcnow().timestamp())}{ext}"
            upload.save(os.path.join(upload_dir, filename))
            images = url_for("static", filename=f"uploads/products/{filename}")

        pt_row = db.execute("SELECT * FROM product_type WHERE id=?", (product_type_id,)).fetchone()
        ptype = ProductType(pt_row)
        visible = 1 if request.form.get("visible") else 0
        featured = 1 if request.form.get("featured") else 0
        new_arrival = 1 if request.form.get("new_arrival") else 0
        is_offer = 1 if request.form.get("is_offer") else 0
        ts = now_iso()

        if product is None:
            cur = db.execute(
                "INSERT INTO product(name, brand_id, category_id, product_type_id, model, price, old_price, "
                "stock, description, images, visible, featured, new_arrival, is_offer, is_demo, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
                (name, brand_id, category_id, product_type_id, model, price, old_price, stock,
                 description, images, visible, featured, new_arrival, is_offer, ts, ts))
            product_id = cur.lastrowid
        else:
            product_id = product.id
            if product.product_type_id != product_type_id:
                db.execute("DELETE FROM product_spec WHERE product_id=?", (product_id,))
            db.execute(
                "UPDATE product SET name=?, brand_id=?, category_id=?, product_type_id=?, model=?, price=?, "
                "old_price=?, stock=?, description=?, images=?, visible=?, featured=?, new_arrival=?, is_offer=?, "
                "updated_at=? WHERE id=?",
                (name, brand_id, category_id, product_type_id, model, price, old_price, stock, description,
                 images, visible, featured, new_arrival, is_offer, ts, product_id))

        db.execute("DELETE FROM product_spec WHERE product_id=?", (product_id,))
        for key, _label in ptype.fields:
            val = request.form.get(f"spec_{key}", "").strip()
            if val:
                db.execute("INSERT INTO product_spec(product_id, key, value) VALUES (?,?,?)",
                           (product_id, key, val))
        db.commit()
        flash("تم حفظ المنتج بنجاح.", "success")
        return redirect(url_for("admin_products"))

    return render_template("admin/product_form.html", product=product, categories=categories,
                            brands=brands, types_by_cat=types_by_cat,
                            PRODUCT_TYPE_FIELDS=PRODUCT_TYPE_FIELDS, brand_category_map=brand_category_map)


@app.route("/admin/products/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_product_delete(pid):
    db = get_db()
    db.execute("DELETE FROM product_spec WHERE product_id=?", (pid,))
    db.execute("DELETE FROM product WHERE id=?", (pid,))
    db.commit()
    flash("تم حذف المنتج.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:pid>/duplicate", methods=["POST"])
@admin_required
def admin_product_duplicate(pid):
    db = get_db()
    row = db.execute("SELECT * FROM product WHERE id=?", (pid,)).fetchone()
    if not row:
        abort(404)
    ts = now_iso()
    cur = db.execute(
        "INSERT INTO product(name, brand_id, category_id, product_type_id, model, price, old_price, stock, "
        "description, images, visible, featured, new_arrival, is_offer, is_demo, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,0,0,0,0,0,?,?)",
        (row["name"] + " (نسخة)", row["brand_id"], row["category_id"], row["product_type_id"], row["model"],
         row["price"], row["old_price"], 0, row["description"], row["images"], ts, ts))
    new_id = cur.lastrowid
    for s in db.execute("SELECT key, value FROM product_spec WHERE product_id=?", (pid,)).fetchall():
        db.execute("INSERT INTO product_spec(product_id, key, value) VALUES (?,?,?)", (new_id, s["key"], s["value"]))
    db.commit()
    flash("تم إنشاء نسخة من المنتج (غير مرئية حتى تراجعها).", "success")
    return redirect(url_for("admin_product_edit", pid=new_id))


@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_category":
            name = request.form.get("name_ar", "").strip()
            slug = request.form.get("slug", "").strip()
            if name and slug:
                db.execute("INSERT INTO category(name_ar, slug, enabled) VALUES (?,?,1)", (name, slug))
                db.commit()
                flash("تمت إضافة الفئة.", "success")
        elif action == "add_type":
            cat_id = request.form.get("category_id", type=int)
            slug = request.form.get("type_slug", "").strip()
            name = request.form.get("type_name", "").strip()
            if cat_id and slug and name:
                db.execute("INSERT INTO product_type(category_id, slug, name_ar) VALUES (?,?,?)",
                           (cat_id, slug, name))
                db.commit()
                flash("تمت إضافة نوع المنتج.", "success")
        elif action == "toggle_category":
            cat_id = request.form.get("category_id", type=int)
            db.execute("UPDATE category SET enabled = 1 - enabled WHERE id=?", (cat_id,))
            db.commit()
        return redirect(url_for("admin_categories"))

    categories = all_categories(db, enabled_only=False)
    known_type_slugs = list(PRODUCT_TYPE_FIELDS.keys())
    return render_template("admin/categories.html", categories=categories, known_type_slugs=known_type_slugs)


@app.route("/admin/brands", methods=["GET", "POST"])
@admin_required
def admin_brands():
    db = get_db()
    categories = all_categories(db, enabled_only=False)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            cat_ids = [int(x) for x in request.form.getlist("category_ids") if x.isdigit()]
            logo = request.files.get("logo")
            logo_path = ""
            if logo and logo.filename:
                ext = os.path.splitext(secure_filename(logo.filename))[1].lower()
                if ext not in {".jpg",".jpeg",".png",".webp",".svg"}:
                    flash("نوع شعار غير صالح. استخدم SVG أو PNG أو JPG أو WEBP.", "error")
                    return redirect(url_for("admin_brands"))
                d = os.path.join(BASE_DIR, "static", "uploads", "brands"); os.makedirs(d, exist_ok=True)
                fn = f"brand_{int(datetime.utcnow().timestamp()*1000)}{ext}"
                logo.save(os.path.join(d, fn)); logo_path = url_for("static", filename=f"uploads/brands/{fn}")
            if name:
                try:
                    bid = db.execute("INSERT INTO brand(name, logo, enabled) VALUES (?,?,1)", (name,logo_path)).lastrowid
                    for cid in cat_ids: db.execute("INSERT OR IGNORE INTO brand_category(brand_id, category_id) VALUES (?,?)", (bid,cid))
                    db.commit(); flash("تمت إضافة العلامة التجارية.", "success")
                except sqlite3.IntegrityError: flash("هذه العلامة التجارية موجودة مسبقاً.", "error")
        elif action == "update":
            bid = request.form.get("brand_id", type=int)
            name = request.form.get("name", "").strip()
            cat_ids = [int(x) for x in request.form.getlist("category_ids") if x.isdigit()]
            logo = request.files.get("logo")
            if bid and name:
                try:
                    if logo and logo.filename:
                        ext=os.path.splitext(secure_filename(logo.filename))[1].lower()
                        if ext not in {".jpg",".jpeg",".png",".webp",".svg"}: raise ValueError("logo")
                        d=os.path.join(BASE_DIR,"static","uploads","brands"); os.makedirs(d,exist_ok=True)
                        fn=f"brand_{bid}_{int(datetime.utcnow().timestamp()*1000)}{ext}"; logo.save(os.path.join(d,fn))
                        db.execute("UPDATE brand SET name=?, logo=? WHERE id=?",(name,url_for("static",filename=f"uploads/brands/{fn}"),bid))
                    else: db.execute("UPDATE brand SET name=? WHERE id=?",(name,bid))
                    db.execute("DELETE FROM brand_category WHERE brand_id=?",(bid,))
                    for cid in cat_ids: db.execute("INSERT OR IGNORE INTO brand_category(brand_id, category_id) VALUES (?,?)",(bid,cid))
                    db.commit(); flash("تم تحديث العلامة التجارية.","success")
                except (sqlite3.IntegrityError, ValueError): flash("تعذر تحديث العلامة التجارية.","error")
        elif action == "toggle":
            db.execute("UPDATE brand SET enabled = 1 - enabled WHERE id=?", (request.form.get("brand_id", type=int),)); db.commit()
        elif action == "delete":
            bid = request.form.get("brand_id", type=int)
            used = db.execute("SELECT COUNT(*) c FROM product WHERE brand_id=?", (bid,)).fetchone()["c"]
            if used: flash("لا يمكن حذف العلامة لأنها مرتبطة بمنتجات. عطّلها بدلاً من ذلك.", "error")
            else: db.execute("DELETE FROM brand WHERE id=?", (bid,)); db.commit(); flash("تم حذف العلامة التجارية.", "success")
        return redirect(url_for("admin_brands"))
    brands=[Brand(r) for r in db.execute("SELECT * FROM brand ORDER BY name").fetchall()]
    brand_cats={b.id:{r["category_id"] for r in db.execute("SELECT category_id FROM brand_category WHERE brand_id=?",(b.id,)).fetchall()} for b in brands}
    return render_template("admin/brands.html", brands=brands, categories=categories, brand_cats=brand_cats)

@app.route("/admin/orders")
@admin_required
def admin_orders():
    db = get_db()
    status_filter = request.args.get("status")
    if status_filter:
        rows = db.execute("SELECT * FROM orders WHERE status=? ORDER BY created_at DESC", (status_filter,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    orders = [hydrate_order(db, r) for r in rows]
    return render_template("admin/orders.html", orders=orders, status_filter=status_filter)


@app.route("/admin/orders/<int:oid>")
@admin_required
def admin_order_detail(oid):
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not row:
        abort(404)
    order = hydrate_order(db, row)
    return render_template("admin/order_detail.html", order=order)


@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@admin_required
def admin_order_status(oid):
    db = get_db()
    new_status = request.form.get("status")
    if new_status not in ORDER_STATUSES:
        abort(400)
    row = db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not row:
        abort(404)

    if new_status == "ملغي" and row["status"] != "ملغي":
        for item in db.execute("SELECT * FROM order_item WHERE order_id=?", (oid,)).fetchall():
            if item["product_id"]:
                db.execute("UPDATE product SET stock = stock + ? WHERE id=?", (item["qty"], item["product_id"]))

    db.execute("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
    db.commit()
    flash("تم تحديث حالة الطلب.", "success")
    return redirect(url_for("admin_order_detail", oid=oid))


if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
