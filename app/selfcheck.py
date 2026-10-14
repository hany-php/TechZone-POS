"""فحص assert واحد قابل للتشغيل: python app/selfcheck.py — يطبع PASS ويعيد 0."""
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SHOP_DB"] = _tmp.name

import api as api_mod
import db

N = 0


def check(name, cond):
    global N
    assert cond, f"FAIL: {name}"
    N += 1
    print(f"PASS {N}: {name}")


def call(a, name, payload=None):
    return a.call(name, payload)


a = api_mod.Api()

# 1) دخول صحيح ورمز خاطئ
r = call(a, "login", {"username": "admin", "pin": "1234"})
check("admin login ok", r["ok"] and r["data"]["role"] == "admin")
r = call(a, "login", {"username": "admin", "pin": "9999"})
check("wrong pin rejected", (not r["ok"]) and "غير صحيح" in r["error"])
r = call(a, "login", {"username": "nope", "pin": "1234"})
check("unknown user rejected", not r["ok"])

# 2) رفض إداري للكاشير الافتراضي
call(a, "login", {"username": "cashier", "pin": "1111"})
r = call(a, "product_save", {"sku": "X", "name": "X"})
check("cashier admin-call rejected", (not r["ok"]) and "للمدير" in r["error"])
r = call(a, "sale_return", {"sale_id": 1, "items": []})
check("cashier return rejected", (not r["ok"]) and "للمدير" in r["error"])
r = call(a, "report_daily", {})
check("cashier report rejected", (not r["ok"]) and "للمدير" in r["error"])

# 3) إضافة/تعديل منتج وبحث (اسم/باركود/سيريال)
call(a, "login", {"username": "admin", "pin": "1234"})
r = call(a, "product_save", {"sku": "TST-001", "name": "منتج فحص", "price": 100, "cost": 60, "min_qty": 5})
check("product add", r["ok"])
pid = r["data"]["id"]
r = call(a, "product_save", {"id": pid, "sku": "TST-001", "name": "منتج فحص معدل", "price": 120, "cost": 60})
check("product edit", r["ok"])
r = call(a, "products_search", {"q": "فحص معدل"})
check("search by name", r["ok"] and any(x["id"] == pid for x in r["data"]))
r = call(a, "products_search", {"q": "TST-001"})
check("search by sku", r["ok"] and any(x["id"] == pid for x in r["data"]))
call(a, "serial_add", {"product_id": pid, "serial": "SN-SELF-1"})
r = call(a, "products_search", {"q": "SN-SELF-1"})
check("search by serial", r["ok"] and any(x["id"] == pid for x in r["data"]))

# 4) بيع ناجح يخصم المخزون ويكتب الحركة والدفع (مع اختبار تفعيل وإيقاف الضريبة)
call(a, "shift_open", {"opening_cash": 100})
call(a, "product_adjust", {"id": pid, "qty_change": 20, "reason": "فحص"})
call(a, "settings_save", {"tax_enabled": "1", "tax_rate": "15"})
before = call(a, "product", {"id": pid})["data"]["qty"]
# سعر 120 للوحدة × 2 = 240، ضريبة 15% = 36، إجمالي 276 (ندخل 300 في الكاش فيحسب الباقي 24 تلقائياً)
r = call(a, "sale_create", {
    "items": [{"product_id": pid, "qty": 2}],
    "discount": 0,
    "payments": [{"method": "cash", "amount": 300}],
    "customer_name": "عميل بدون هاتف",
})
check("sale ok (overpaid cash auto-change)", r["ok"])
sale_id = r["data"]["sale_id"]
check("invoice format", r["data"]["invoice_no"].startswith("INV-"))
after = call(a, "product", {"id": pid})["data"]["qty"]
check("stock deducted", after == before - 2)
with db.connect() as c:
    mv = c.execute("SELECT * FROM stock_movements WHERE product_id=? AND reason='sale' ORDER BY id DESC LIMIT 1",
                   (pid,)).fetchone()
    check("movement written", mv is not None and mv["qty_change"] == -2 and mv["qty_after"] == after)
    pay = c.execute("SELECT * FROM payments WHERE sale_id=?", (sale_id,)).fetchone()
    check("payment written", pay is not None and pay["amount"] == 27600 and pay["change"] == 2400)
    s = c.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
    check("tax correct", s["tax"] == 3600 and s["total"] == 27600)

# 4b) اختبار إيقاف الضريبة (tax_enabled = 0) + الدفع بالمحفظة برقم مرجعي + الدفع الآجل بإلزام العميل
call(a, "settings_save", {"tax_enabled": "0"})
r_no_ref = call(a, "sale_create", {
    "items": [{"product_id": pid, "qty": 1}],
    "payments": [{"method": "wallet", "amount": 120}],
})
check("wallet without ref_no rejected", (not r_no_ref["ok"]) and "مرجعية" in r_no_ref["error"])

r_no_cust = call(a, "sale_create", {
    "items": [{"product_id": pid, "qty": 1}],
    "payments": [{"method": "credit", "amount": 120}],
})
check("credit without customer rejected", (not r_no_cust["ok"]) and "العميل" in r_no_cust["error"])

r_credit_wallet = call(a, "sale_create", {
    "items": [{"product_id": pid, "qty": 2}],  # 2 * 120 = 240 (tax_enabled=0 -> total=240)
    "payments": [
        {"method": "wallet", "amount": 100, "ref_no": "VF-998877"},
        {"method": "credit", "amount": 140},
    ],
    "customer_name": "عميل آجل فحص",
    "customer_phone": "01012345678",
})
check("tax disabled + wallet ref + credit sale ok", r_credit_wallet["ok"])
cw_sale_id = r_credit_wallet["data"]["sale_id"]
cw_sale = call(a, "sale", {"id": cw_sale_id})["data"]
check("zero tax when disabled", cw_sale["tax"] == 0 and cw_sale["total"] == 24000)

# 4c) كشف حساب المديونية وسندات القبض (customer_payment_create / customer_payment_delete)
cust_search = call(a, "customers_search", {"q": "عميل آجل فحص"})["data"]
check("credit customer found with debt", len(cust_search) == 1 and cust_search[0]["debt"] == 14000)
credit_cid = cust_search[0]["id"]

r_overpay_debt = call(a, "customer_payment_create", {"customer_id": credit_cid, "amount": 500, "method": "cash"})
check("overpaying debt rejected", not r_overpay_debt["ok"])

r_voucher = call(a, "customer_payment_create", {
    "customer_id": credit_cid,
    "amount": 60,
    "method": "wallet",
    "ref_no": "INSTA-1122",
    "notes": "دفعة أولى",
})
check("receipt voucher created", r_voucher["ok"] and r_voucher["data"]["remaining_debt"] == 8000)
hist_after = call(a, "customer_history", {"id": credit_cid})["data"]
check("customer ledger updated", hist_after["customer"]["debt"] == 8000 and len(hist_after["ledger"]) == 2)

# 5) رفض بيع عند نقص المخزون
call(a, "settings_save", {"tax_enabled": "1", "tax_rate": "15"})
r = call(a, "sale_create", {"items": [{"product_id": pid, "qty": 10 ** 9}],
                           "payments": [{"method": "cash", "amount": 1}]})
check("oversell rejected", (not r["ok"]) and "مخزون" in r["error"])

# 6) رفض بيع بلا وردية مفتوحة
call(a, "shift_close", {"counted_cash": 100})
r = call(a, "sale_create", {"items": [{"product_id": pid, "qty": 1}],
                            "payments": [{"method": "cash", "amount": 138}]})
check("no-shift sale rejected", (not r["ok"]) and "وردية" in r["error"])
call(a, "shift_open", {"opening_cash": 0})

# 7) مرتجع يعيد المخزون
s = call(a, "sale", {"id": sale_id})["data"]
item_id = s["items"][0]["id"]
r = call(a, "sale_return", {"sale_id": sale_id, "items": [{"sale_item_id": item_id, "qty": 1}], "reason": "فحص"})
check("return ok", r["ok"] and r["data"]["total"] == 12000)
check("return restores stock", call(a, "product", {"id": pid})["data"]["qty"] == after - 2 + 1)
with db.connect() as c:
    mv = c.execute("SELECT * FROM stock_movements WHERE product_id=? AND reason='return' ORDER BY id DESC LIMIT 1",
                   (pid,)).fetchone()
    check("return movement", mv is not None and mv["qty_change"] == 1)

# 8) نص إيصال 80 عموداً
t = call(a, "receipt_text", {"id": cw_sale_id})["data"]
check("receipt 80 cols & includes wallet ref", all(len(line) <= 80 for line in t.splitlines()) and "VF-998877" in t)

# 9) شراء جهاز مستعمل يضيف سيريالاً للمخزون كمنتج متتبّع
r = call(a, "used_create", {"seller_name": "بائع فحص", "model": "Test Phone X",
                            "serial": "SN-USED-SELF-1", "buy_price": 500, "resale_price": 900})
check("used purchase ok", r["ok"] and r["data"]["product_id"])
used_pid = r["data"]["product_id"]
with db.connect() as c:
    sn = c.execute("SELECT * FROM serials WHERE serial='SN-USED-SELF-1'").fetchone()
    up = c.execute("SELECT * FROM products WHERE id=?", (used_pid,)).fetchone()
    check("used serial in stock & tracked", sn is not None and sn["status"] == "in_stock" and up["tracked"] == 1)

# 10) تذكرة صيانة + انتقال مرفوض + قطعة تخصم
r = call(a, "repair_create", {"customer_name": "عميل فحص", "customer_phone": "01000000000",
                              "device_type": "لابتوب", "problem": "لا يعمل"})
check("repair created", r["ok"])
rid = r["data"]["id"]
r = call(a, "repair_set_status", {"id": rid, "status": "delivered"})
check("bad transition rejected", (not r["ok"]) and "غير مسموح" in r["error"])
r = call(a, "repair_set_status", {"id": rid, "status": "in_review"})
check("good transition ok", r["ok"])
pq = call(a, "product", {"id": pid})["data"]["qty"]
r = call(a, "repair_add_part", {"repair_id": rid, "product_id": pid, "qty": 1})
check("part added", r["ok"])
check("part deducts stock", call(a, "product", {"id": pid})["data"]["qty"] == pq - 1)

# 11) أرقام تقرير يومي/شهري مطابقة لحساب يدوي
import datetime
today = datetime.datetime.now().strftime("%Y-%m-%d")
d = call(a, "report_daily", {"date": today})["data"]
with db.connect() as c:
    m = c.execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM sales WHERE created_at LIKE ?",
                  (f"{today}%",)).fetchone()
    check("daily matches manual", d["sales"]["count"] == m["n"] and d["sales"]["total"] == m["t"])
now = datetime.datetime.now()
mo = call(a, "report_monthly", {"year": now.year, "month": now.month})["data"]
with db.connect() as c:
    m = c.execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM sales WHERE created_at >= ? AND created_at < ?",
                  (f"{now.year:04d}-{now.month:02d}-01",
                   (datetime.date(now.year, now.month, 1) + datetime.timedelta(days=32)).replace(day=1).strftime("%Y-%m-%d"))).fetchone()
    check("monthly matches manual", mo["sales"]["count"] == m["n"] and mo["sales"]["total"] == m["t"])

# 12) settings اسم المحل + عملة مصر + مفاتيح التخصيص
st = call(a, "settings", {})["data"]
check("store name & EGP currency setting", st.get("store_name") == "تك زون للإلكترونيات" and st.get("currency") == "ج.م")
r = call(a, "settings_save", {"store_email": "shop@example.com"})
check("new key saved", r["ok"] and r["data"].get("store_email") == "shop@example.com")
check("new key readable", call(a, "settings", {})["data"].get("store_email") == "shop@example.com")
r = call(a, "settings_save", {"receipt_show_barcode": "0"})
check("show flag zero saved", r["ok"] and r["data"].get("receipt_show_barcode") == "0")
check("show flag zero readable", call(a, "settings", {})["data"].get("receipt_show_barcode") == "0")
r = call(a, "settings_save", {"receipt_logo": "not-an-image"})
check("bad logo rejected", (not r["ok"]))
r = call(a, "settings_save", {"receipt_logo": "data:image/png;base64,AAAA"})
check("logo saved", r["ok"])

# 13) إدارة العملاء والموظفين والصلاحيات المخصصة لكل موظف
rc = call(a, "customers_save", {"name": "خالد العمري", "phone": "01055123456"})
check("customer save ok", rc["ok"] and rc["data"]["id"] > 0)
cid = rc["data"]["id"]
rc_dup = call(a, "customers_save", {"name": "خالد العمري", "phone": "01055123456"})
check("duplicate customer rejected", (not rc_dup["ok"]) and "مسجل مسبقاً" in rc_dup["error"])
rc_one = call(a, "customer", {"id": cid})
check("customer single fetch ok", rc_one["ok"] and rc_one["data"]["name"] == "خالد العمري")

ru = call(a, "user_save", {
    "username": "cashier2",
    "name": "سالم علي",
    "role": "cashier",
    "pin": "2222",
    "permissions": {"inventory_edit": True, "reports_view": False},
})
check("custom permission user save ok", ru["ok"] and ru["data"]["id"] > 0)
uid2 = ru["data"]["id"]

# تسجيل الدخول بالموظف المخصص والتأكد أنه يستطيع تعديل المخزون ولا يستطيع فتح التقارير
call(a, "login", {"username": "cashier2", "pin": "2222"})
r_allowed = call(a, "categories_save", {"name": "فئة صلاحية خاصة"})
check("custom perm allowed inventory_edit", r_allowed["ok"])
r_denied = call(a, "report_daily", {})
check("custom perm denied reports_view", not r_denied["ok"])

call(a, "login", {"username": "admin", "pin": "1234"})
ru_del = call(a, "user_delete", {"id": uid2})
check("user delete ok", ru_del["ok"])

# 14) تطابق العقد: كل api('NAME') في الواجهة موجود في Api
names = set()
for p in list((ROOT / "web").glob("*.html")) + [ROOT / "web" / "app.js"]:
    names |= set(re.findall(r"api\(\s*['\"]([A-Za-z_]+)", p.read_text(encoding="utf-8")))
real = {n for n in dir(api_mod.Api) if not n.startswith("_") and callable(getattr(api_mod.Api, n)) and n != "call"}
missing = names - real
check(f"contract ok ({len(names)} names)", not missing)
if missing:
    print("MISSING:", missing)

# 15) مسار القاعدة بجانب المشروع + ترحيل القديمة لمرة واحدة
_shop_db_saved = os.environ.pop("SHOP_DB", None)
try:
    p = pathlib.Path(db.db_path())
    check("db beside project", p.name == "shop.db" and p.parent.name == "data" and ROOT in p.parents)
    with tempfile.TemporaryDirectory() as td:
        legacy = pathlib.Path(td) / "legacy.db"
        target = pathlib.Path(td) / "new.db"
        legacy.write_bytes(b"fake-legacy-db")
        os.environ["SHOP_DB"] = str(target)
        os.environ["SHOP_DB_LEGACY"] = str(legacy)
        try:
            db._migrate_once()
            check("legacy migrated", target.read_bytes() == b"fake-legacy-db")
        finally:
            os.environ.pop("SHOP_DB_LEGACY", None)
finally:
    if _shop_db_saved is not None:
        os.environ["SHOP_DB"] = _shop_db_saved

print(f"\nALL {N} CHECKS PASSED")
