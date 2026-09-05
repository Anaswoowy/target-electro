# -*- coding: utf-8 -*-
"""
Seed script — sets up required system structure, and optionally inserts
demo products that are clearly isolated (is_demo=1) so they're trivial
to remove before you go live.

Usage:
    python seed.py                 # required setup only, no demo products
    python seed.py --with-demo     # also inserts demo products
    python seed.py --clear-demo    # removes all is_demo=1 products
"""
import sys
import os
import sqlite3
from werkzeug.security import generate_password_hash
from app import DB_PATH, init_db, now_iso, BRANDS_BY_CATEGORY

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "target1323")  # set ADMIN_PASSWORD env var in production — see README


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def required_setup(conn):
    if not conn.execute("SELECT 1 FROM admin_user WHERE username=?", (ADMIN_USERNAME,)).fetchone():
        conn.execute("INSERT INTO admin_user(username, password_hash) VALUES (?,?)",
                     (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD)))
        print(f"Created admin user '{ADMIN_USERNAME}'.")

    cat_defs = [
        ("الهواتف", "mobile", [("smartphone", "هاتف ذكي"),("feature_phone","هاتف عادي")]),
        ("السماعات والصوتيات", "audio", [("tws", "TWS"),("headphones","سماعات رأس"),("earphones","سماعات أذن"),("speaker","سبيكر بلوتوث"),("microphone","مايكروفون")]),
        ("اللابتوبات والكمبيوترات", "computers", [("laptop", "لابتوب"),("desktop","كمبيوتر مكتبي"),("mini_pc","Mini PC")]),
        ("الساعات الذكية", "smart-devices", [("smartwatch","ساعة ذكية"),("smart_band","سوار ذكي")]),
        ("الألعاب وملحقاتها", "gaming", [("controller","يد تحكم"),("gaming_mouse","ماوس ألعاب"),("gaming_keyboard","كيبورد ألعاب"),("gaming_headset","سماعة ألعاب"),("gaming_monitor","شاشة ألعاب")]),
        ("ملحقات الكمبيوتر", "pc-accessories", [("mouse","ماوس"),("keyboard","كيبورد"),("monitor","شاشة")]),
        ("الكاميرات", "cameras", [("camera","كاميرا")]),
        ("الشاشات والتلفزيونات", "displays", [("tv","تلفزيون")]),
        ("الإكسسوارات", "accessories", [("accessory","إكسسوار")]),
        ("أخرى", "other", [("other_accessory","أخرى")]),
    ]
    for name_ar, slug, types in cat_defs:
        row = conn.execute("SELECT * FROM category WHERE slug=?", (slug,)).fetchone()
        if not row:
            cur = conn.execute("INSERT INTO category(name_ar, slug, enabled) VALUES (?,?,1)", (name_ar, slug))
            cat_id = cur.lastrowid
        else:
            cat_id = row["id"]
        for type_slug, type_name in types:
            if not conn.execute("SELECT 1 FROM product_type WHERE slug=?", (type_slug,)).fetchone():
                conn.execute("INSERT INTO product_type(category_id, slug, name_ar) VALUES (?,?,?)", (cat_id, type_slug, type_name))

    for _name_ar, cat_slug, _types in cat_defs:
        cat = conn.execute("SELECT id FROM category WHERE slug=?", (cat_slug,)).fetchone()
        if not cat: continue
        for brand_name in BRANDS_BY_CATEGORY.get(cat_slug, []):
            b = conn.execute("SELECT id FROM brand WHERE name=?", (brand_name,)).fetchone()
            if not b:
                cur = conn.execute("INSERT INTO brand(name, logo, enabled) VALUES (?, '', 1)", (brand_name,))
                bid = cur.lastrowid
            else:
                bid = b["id"]
            conn.execute("INSERT OR IGNORE INTO brand_category(brand_id, category_id) VALUES (?,?)", (bid, cat["id"]))

    conn.commit()
    print("Required setup complete. Brands/products remain empty until the admin adds real ones.")


def insert_demo(conn):
    def get_or_create_brand(name):
        row = conn.execute("SELECT * FROM brand WHERE name=?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO brand(name, enabled) VALUES (?,1)", (name,))
        return cur.lastrowid

    brand_ids = {n: get_or_create_brand(n) for n in ["Samsung", "Apple", "Xiaomi"]}

    def type_row(slug):
        return conn.execute("SELECT * FROM product_type WHERE slug=?", (slug,)).fetchone()

    smartphone_t = type_row("smartphone")
    tws_t = type_row("tws")
    laptop_t = type_row("laptop")

    demo_products = [
        dict(name="[DEMO] هاتف تجريبي - نموذج A", brand="Samsung", ptype=smartphone_t,
             price=350000, old_price=400000, stock=12, featured=1, new_arrival=1, is_offer=0,
             specs={"ram": "8GB", "storage": "128GB", "soc": "Snapdragon 6 Gen 1",
                    "display_size": "6.5 إنش", "battery": "5000mAh", "network_5g": "نعم"}),
        dict(name="[DEMO] سماعة تجريبية - نموذج B", brand="Xiaomi", ptype=tws_t,
             price=45000, old_price=None, stock=3, featured=0, new_arrival=0, is_offer=0,
             specs={"anc": "نعم", "bluetooth_version": "5.3", "total_battery": "24 ساعة"}),
        dict(name="[DEMO] لابتوب تجريبي - نموذج C", brand="Apple", ptype=laptop_t,
             price=1450000, old_price=1600000, stock=0, featured=0, new_arrival=0, is_offer=1,
             specs={"cpu": "Apple M2", "ram": "8GB", "storage": "256GB SSD", "display_size": "13.6 إنش"}),
    ]

    for d in demo_products:
        if conn.execute("SELECT 1 FROM product WHERE name=?", (d["name"],)).fetchone():
            continue
        ts = now_iso()
        cur = conn.execute(
            "INSERT INTO product(name, brand_id, category_id, product_type_id, price, old_price, stock, "
            "description, visible, featured, new_arrival, is_offer, is_demo, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,1,?,?,?,1,?,?)",
            (d["name"], brand_ids[d["brand"]], d["ptype"]["category_id"], d["ptype"]["id"],
             d["price"], d["old_price"], d["stock"], "منتج تجريبي لأغراض العرض فقط — احذفه قبل الإطلاق.",
             d["featured"], d["new_arrival"], d["is_offer"], ts, ts))
        pid = cur.lastrowid
        for k, v in d["specs"].items():
            conn.execute("INSERT INTO product_spec(product_id, key, value) VALUES (?,?,?)", (pid, k, v))

    conn.commit()
    print("Inserted demo products (flagged is_demo=1). Run 'python seed.py --clear-demo' to remove.")


def clear_demo(conn):
    cur = conn.execute("SELECT id FROM product WHERE is_demo=1")
    ids = [r["id"] for r in cur.fetchall()]
    for pid in ids:
        conn.execute("DELETE FROM product_spec WHERE product_id=?", (pid,))
        conn.execute("DELETE FROM product WHERE id=?", (pid,))
    conn.commit()
    print(f"Removed {len(ids)} demo product(s).")


if __name__ == "__main__":
    init_db()
    conn = connect()
    required_setup(conn)
    if "--with-demo" in sys.argv:
        insert_demo(conn)
    if "--clear-demo" in sys.argv:
        clear_demo(conn)
    conn.close()
