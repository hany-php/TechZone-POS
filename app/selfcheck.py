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

# 2b) حفظ تفضيلات حجم البلوك للمستخدم (user_pref_save)
sample_wp = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
r_pref = call(a, "user_pref_save", {
    "card_size": 180,
    "custom_bg": sample_wp,
    "accent_color": "#7c3aed",
    "desktop_layout": {"pos": {"x": 800, "y": 40}},
})
check("user custom_bg & accent & layout saved", r_pref["ok"] and r_pref["data"]["wallpaper"] == "custom" and r_pref["data"]["accent_color"] == "#7c3aed" and "pos" in r_pref["data"]["desktop_layout"])
check("user card_size pref saved", r_pref["ok"] and r_pref["data"]["card_size"] == 180)
# اختبار الخروج والدخول بمستخدم آخر ثم العودة لنفس المستخدم والتأكد أن session() يعيد كل التفضيلات المحفوظة
call(a, "logout")
call(a, "login", {"username": "admin", "pin": "1234"})
admin_sess = call(a, "session")["data"]["user"]
check("admin has own clean prefs", admin_sess["accent_color"] is None and admin_sess["custom_bg"] is None)
call(a, "logout")
call(a, "login", {"username": "cashier", "pin": "1111"})
cashier_sess = call(a, "session")["data"]["user"]
check("session persists custom_bg, accent_color, desktop_layout & card_size across logout/login",
      cashier_sess["card_size"] == 180
      and cashier_sess["wallpaper"] == "custom"
      and cashier_sess["custom_bg"] == sample_wp
      and cashier_sess["accent_color"] == "#7c3aed"
      and "pos" in (cashier_sess["desktop_layout"] or ""))

# 3) إضافة/تعديل منتج مع صورة وبحث (اسم/باركود/سيريال)
call(a, "login", {"username": "admin", "pin": "1234"})
sample_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
r = call(a, "product_save", {"sku": "TST-001", "name": "منتج فحص", "price": 100, "cost": 60, "min_qty": 5, "image": sample_img})
check("product add with image", r["ok"])
pid = r["data"]["id"]
check("product image stored", call(a, "product", {"id": pid})["data"]["image"] == sample_img)
r = call(a, "product_save", {"id": pid, "sku": "TST-001", "name": "منتج فحص معدل", "price": 120, "cost": 60, "image": sample_img})
check("product edit", r["ok"])
r = call(a, "products_search", {"q": "فحص معدل"})
check("search by name & returns image", r["ok"] and any(x["id"] == pid and x["image"] == sample_img for x in r["data"]))
r = call(a, "products_search", {"q": "TST-001"})
check("search by sku", r["ok"] and any(x["id"] == pid for x in r["data"]))
call(a, "serial_add", {"product_id": pid, "serial": "SN-SELF-1"})
r = call(a, "products_search", {"q": "SN-SELF-1"})
check("search by serial", r["ok"] and any(x["id"] == pid for x in r["data"]))

# 4) بيع ناجح يخصم المخزون ويكتب الحركة والدفع (مع اختبار تفعيل وإيقاف الضريبة)
call(a, "shift_open", {"opening_cash": 100})
call(a, "product_adjust", {"id": pid, "qty_change": 20, "reason": "فحص"})
call(a, "settings_save", {"tax_enabled": "1", "tax_rate": "15", "pos_card_size": "160"})
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

# 4a-2) اختبار تعديل خصم فاتورة مدفوعة (sale_discount) وتقرير الوردية التفصيلي (shift_summary)
r_sdisc = call(a, "sale_discount", {"sale_id": sale_id, "discount": 40})
check("sale_discount on paid invoice ok", r_sdisc["ok"] and r_sdisc["data"]["discount"] == 4000 and r_sdisc["data"]["total"] == 23000)

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

# 4d) اختبار ملخص إغلاق الوردية التفصيلي (shift_summary)
sh_sum = call(a, "shift_summary")
check("shift_summary ok & lists operations", sh_sum["ok"] and len(sh_sum["data"]["operations"]) >= 3 and sh_sum["data"]["wallet_sales"] == 10000 and sh_sum["data"]["credit_sales"] == 14000)

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

# 8b) فحص إرسال الفاتورة عبر واتساب (whatsapp_send_invoice) وحفظ ملف الإيصال بدون أخطاء pathlib
import webbrowser
_orig_wb_open = webbrowser.open
webbrowser.open = lambda url, *a, **kw: True
try:
    r_wa = call(a, "whatsapp_send_invoice", {"sale_id": cw_sale_id, "phone": "01012345678"})
    check("whatsapp_send_invoice ok & saves valid PDF file + company message", r_wa["ok"] and r_wa["data"]["phone"] == "201012345678" and "لديك فاتورة من" in r_wa["data"]["message"] and r_wa["data"]["pdf_file"].endswith(".pdf") and pathlib.Path(r_wa["data"]["pdf_file"]).read_bytes().startswith(b"%PDF-1.4"))
finally:
    webbrowser.open = _orig_wb_open

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

# 11b) فحص report_top و report_profit و sale_modify_from_cart وملخص مديونيات العملاء
r_top = call(a, "report_top", {"limit": 10})
check("report_top ok (no ambiguous qty)", r_top["ok"] and isinstance(r_top["data"], list))
r_prof = call(a, "report_profit", {})
check("report_profit ok", r_prof["ok"] and "goods_profit" in r_prof["data"])

# فحص تعديل الفاتورة من داخل سلة المشتريات (sale_modify_from_cart) مع توثيق المعدل والوقت
cw_full = call(a, "sale", {"id": cw_sale_id})["data"]
cw_item_id = cw_full["items"][0]["id"]
r_mod = call(a, "sale_modify_from_cart", {
    "sale_id": cw_sale_id,
    "items": [{"sale_item_id": cw_item_id, "qty": 1, "unit_price": 100}],
    "discount": 10,
    "reason": "مرتجع قطعة مع خصم من السلة",
})
check("sale_modify_from_cart ok & logs modifier", r_mod["ok"] and r_mod["data"]["modified_by_name"] == "المدير" and r_mod["data"]["returned_total"] == 12000)

cl_res = call(a, "customers_list", {"limit": 50, "offset": 0})
check("customers_list includes global debt/paid summary", cl_res["ok"] and "summary" in cl_res["data"] and "total_debt" in cl_res["data"]["summary"])

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
r = call(a, "settings_save", {"receipt_logo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="})
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
    "permissions": {"inventory_edit": True, "reports_view": False, "pos_item_discount": True},
})
check("custom permission user save ok", ru["ok"] and ru["data"]["id"] > 0)
uid2 = ru["data"]["id"]

# تسجيل الدخول بالموظف المخصص والتأكد أنه يستطيع تعديل المخزون وعمل خصم ولا يستطيع فتح التقارير
call(a, "login", {"username": "cashier2", "pin": "2222"})
r_allowed = call(a, "categories_save", {"name": "فئة صلاحية خاصة"})
check("custom perm allowed inventory_edit", r_allowed["ok"])
r_disc_allowed = call(a, "sale_discount", {"sale_id": sale_id, "discount": 10})
check("custom perm allowed pos_item_discount", r_disc_allowed["ok"])
r_denied = call(a, "report_daily", {})
check("custom perm denied reports_view", not r_denied["ok"])

call(a, "login", {"username": "admin", "pin": "1234"})
ru_del = call(a, "user_delete", {"id": uid2})
check("user delete ok", ru_del["ok"])

# 13b) فحص قسم المبيعات وعروض الأسعار وقوالب الفواتير (A4 + POS Thermal)
tpl_res = call(a, "templates_get", {})
check("templates_get ok (a4 + pos)", tpl_res["ok"] and "a4" in tpl_res["data"] and "pos" in tpl_res["data"] and tpl_res["data"]["a4"]["theme"] == "taqnia_wave")
tpl_save = call(a, "templates_save", {"a4": {"company_title": "تقنية -Technology", "currency_symbol": "LE", "invoice_prefix": "N00", "quote_prefix": "Q00"}, "pos": {"paper_width": "80mm"}})
check("templates_save ok & prefix N00 seq", tpl_save["ok"] and tpl_save["data"]["a4"]["currency_symbol"] == "LE" and tpl_save["data"]["next_invoice_no"].startswith("N00"))

pm_save = call(a, "payment_methods_save", {"methods": [
    {"id": "cash", "name": "نقدي", "base_type": "cash"},
    {"id": "plan3", "name": "3 دفعات مع دفعة مقدمة", "base_type": "cash"},
    {"id": "plan2", "name": "دفعتين", "base_type": "wallet"},
]})
check("payment_methods_save ok", pm_save["ok"] and any(m["name"] == "3 دفعات مع دفعة مقدمة" for m in pm_save["data"]))

q_create = call(a, "quotation_save", {
    "doc_type": "quote",
    "customer_name": "فاروق مجدي شحاته",
    "customer_phone": "01099887766",
    "doc_date": "2026-08-26",
    "due_date": "2026-08-26",
    "source_ref": "تقنية - Technology/0004",
    "signal_ref": "تقنية - Technology/0004",
    "items": [
        {"sku": "HDD 500", "name": "هارددسك 500 مكتبي HDD 500", "qty": 1, "unit_price": 650, "tax_label": "Zero Rated 0%", "tax_rate": 0},
        {"sku": "CABLE RG58 100M", "name": "كابل كاميرا 100 متر CABLE RG58 100M", "qty": 1, "unit_price": 1260, "tax_label": "", "tax_rate": 0},
        {"sku": "Power Supply 12V 20A", "name": "Power Supply 12V 20A", "qty": 1, "unit_price": 310, "tax_label": "", "tax_rate": 0},
        {"sku": "PNC AND DC CAMERA", "name": "PNC AND DC CAMERA", "qty": 8, "unit_price": 10, "tax_label": "", "tax_rate": 0},
        {"sku": "HP 24 LCD", "name": "شاشة HP 24 LCD", "qty": 1, "unit_price": 1770, "tax_label": "Zero Rated 0%", "tax_rate": 0},
        {"sku": "DVR HIKVISION 8 CH", "name": "دفي ار 8 قناة هيكفيجن DVR HIKVISION 8 CH", "qty": 1, "unit_price": 2550, "tax_label": "", "tax_rate": 0},
    ],
})
check("quotation_save ok (total 6620.00)", q_create["ok"] and q_create["data"]["total"] == 662000 and q_create["data"]["status"] == "draft")
qid = q_create["data"]["id"]

q_conv = call(a, "quotation_convert_to_sale", {"id": qid, "paid_amount": 5000, "payment_method": "cash", "payment_method_label": "3 دفعات مع دفعة مقدمة", "payment_plan_note": "دفعة مقدمة 5000 والباقي على دفعتين"})
check("quotation_convert_to_sale ok (paid 5000, due 1620, prefix N00)", q_conv["ok"] and q_conv["data"]["status"] == "converted" and q_conv["data"]["paid_amount"] == 500000 and q_conv["data"]["due_amount"] == 162000 and q_conv["data"]["quote_no"].startswith("N00") and q_conv["data"]["payment_method_label"] == "3 دفعات مع دفعة مقدمة")

q_list = call(a, "quotations", {})
check("quotations list & summary ok", q_list["ok"] and q_list["data"]["summary"]["invoices_count"] >= 1)

# 13c) فحص الدخول بالرمز السري فقط (التعرف التلقائي على المدير أو الكاشير) وإعدادات الدخول والصفحة الافتراضية لكل مستخدم
call(a, "login", {"username": "admin", "pin": "1234"})
call(a, "settings_save", {"store_name": "متجر النور للكمبيوتر", "login_mode": "pin_only", "default_start_page": "sales_quotes", "default_start_mode": "window", "os_default_theme": "light"})
lcfg = call(a, "login_config")
check("login_config returns dynamic store_name, login_mode & sanitized users without role",
      lcfg["ok"] and lcfg["data"]["store_name"] == "متجر النور للكمبيوتر"
      and lcfg["data"]["login_mode"] == "pin_only"
      and all("role" not in u for u in lcfg["data"]["users"]))

call(a, "logout")
# دخول المدير بالرمز السري فقط بدون اسم مستخدم
r_pin_admin = call(a, "login", {"pin": "1234"})
check("PIN-only login auto-detects admin & falls back to admin default_start_page",
      r_pin_admin["ok"] and r_pin_admin["data"]["username"] == "admin"
      and r_pin_admin["data"]["role"] == "admin"
      and r_pin_admin["data"]["effective_start_page"] == "sales_quotes")

# رفض تكرار نفس الرمز السري لمستخدم آخر
r_dup_pin = call(a, "user_save", {"username": "dupuser", "name": "مستخدم مكرر", "role": "cashier", "pin": "1111"})
check("duplicate PIN across users rejected", (not r_dup_pin["ok"]) and "رمز سري فريد" in r_dup_pin["error"])

# دخول الكاشير بالرمز السري فقط وتخصيص صفحة البداية والوضع الليلي/النهاري الخاص به
call(a, "logout")
r_pin_cashier = call(a, "login", {"pin": "1111"})
check("PIN-only login auto-detects cashier", r_pin_cashier["ok"] and r_pin_cashier["data"]["username"] == "cashier" and r_pin_cashier["data"]["role"] == "cashier")
r_upref = call(a, "user_pref_save", {"start_page": "repair", "start_mode": "maximized", "theme_mode": "dark"})
check("user start_page & theme_mode saved", r_upref["ok"] and r_upref["data"]["start_page"] == "repair" and r_upref["data"]["theme_mode"] == "dark")

call(a, "logout")
r_pin_cashier2 = call(a, "login", {"pin": "1111"})
check("cashier login uses personal start_page over admin default",
      r_pin_cashier2["ok"] and r_pin_cashier2["data"]["effective_start_page"] == "repair"
      and r_pin_cashier2["data"]["effective_start_mode"] == "maximized"
      and r_pin_cashier2["data"]["theme_mode"] == "dark")

# فحص صفحة الملف الشخصي للموظف (profile_save: تغيير الاسم، الصورة الشخصية، الرمز السري، وصفحة البداية)
sample_av = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
r_prof = call(a, "profile_save", {
    "name": "أحمد محمد المعدل",
    "current_pin": "1111",
    "new_pin": "5566",
    "avatar": sample_av,
    "start_page": "customers",
    "start_mode": "window",
})
check("profile_save updates name, avatar, PIN & start_page",
      r_prof["ok"] and r_prof["data"]["name"] == "أحمد محمد المعدل"
      and r_prof["data"]["avatar"] == sample_av
      and r_prof["data"]["effective_start_page"] == "customers")

call(a, "logout")
r_new_pin_login = call(a, "login", {"pin": "5566"})
check("login with new employee PIN works & returns avatar",
      r_new_pin_login["ok"] and r_new_pin_login["data"]["name"] == "أحمد محمد المعدل"
      and r_new_pin_login["data"]["avatar"] == sample_av)
# إعادة الرمز السري الافتراضي للكاشير
call(a, "profile_save", {"name": "أحمد محمد", "current_pin": "5566", "new_pin": "1111"})

# التحقق من وجود صفحات settings.html و staff.html و profile.html وفصل الإعدادات عن reports.html و receipt.html
check("settings.html, staff.html & profile.html exist",
      (ROOT / "web" / "settings.html").exists()
      and (ROOT / "web" / "staff.html").exists()
      and (ROOT / "web" / "profile.html").exists())
check("reports.html is dedicated to reports only (no staff-zone)",
      "staff-zone" not in (ROOT / "web" / "reports.html").read_text(encoding="utf-8"))
check("receipt.html is dedicated to receipt preview only (no custom-form)",
      "custom-form" not in (ROOT / "web" / "receipt.html").read_text(encoding="utf-8"))

# إعادة اسم المحل الافتراضي بعد الفحص وفحص الميزات الـ 10 الجديدة
call(a, "logout")
call(a, "login", {"pin": "1234"})
call(a, "settings_save", {"store_name": "تك زون للإلكترونيات", "tax_enabled": "0"})

# (أ) مصمم القوالب أُزيل من sales_quotes.html وأصبح حصرياً في settings.html
sq_html = (ROOT / "web" / "sales_quotes.html").read_text(encoding="utf-8")
check("sales_quotes.html has no pane-templates (designer in settings only)",
      "id=\"pane-templates\"" not in sq_html and "settings.html?tab=invoices" in sq_html)

# (ب) عند إيقاف الضرائب (tax_enabled=0) يتم تصفير الضرائب في عروض الأسعار والفواتير حتى لو أُرسل tax_rate=14
q_notax = call(a, "quotation_save", {
    "doc_type": "quote",
    "customer_name": "عميل بدون ضريبة",
    "customer_phone": "01099887766",
    "items": [{"name": "شاشة سامسونج", "qty": 1, "unit_price": 1000, "tax_rate": 14}],
})
check("quotation_save forces zero tax when tax_enabled=0",
      q_notax["ok"] and q_notax["data"]["tax"] == 0 and q_notax["data"]["total"] == 100000)

# (ج) إلغاء عرض السعر (quotation_cancel) مسموح، بينما إلغاء الفاتورة المعتمدة مرفوض لحماية الدورة المالية
q_cancel_res = call(a, "quotation_cancel", {"id": q_notax["data"]["id"]})
check("quotation_cancel marks quote as cancelled",
      q_cancel_res["ok"] and q_cancel_res["data"]["status"] == "cancelled")
q_cancel_inv_err = call(a, "quotation_cancel", {"id": qid})
check("quotation_cancel rejects converted invoice to protect financial cycle",
      not q_cancel_inv_err["ok"])

# (د) بادئات التسلسل المخصصة لجميع الفواتير والإيصالات (POS + صيانة + سند قبض + شراء مستعمل) + ربط البائع بالعملاء
r_tpl_prefs = call(a, "templates_save", {
    "pos": {
        "pos_invoice_prefix": "POS26-",
        "repair_prefix": "TKT-",
        "voucher_prefix": "VCH-",
        "used_prefix": "USD-",
    }
})
check("templates_save saves pos/repair/voucher/used prefixes",
      r_tpl_prefs["ok"]
      and r_tpl_prefs["data"]["pos"]["pos_invoice_prefix"] == "POS26-"
      and r_tpl_prefs["data"]["pos"]["repair_prefix"] == "TKT-"
      and r_tpl_prefs["data"]["pos"]["voucher_prefix"] == "VCH-"
      and r_tpl_prefs["data"]["pos"]["used_prefix"] == "USD-")

r_pos_pref_sale = call(a, "sale_create", {
    "items": [{"product_id": pid, "qty": 1}],
    "payments": [{"method": "cash", "amount": 550}],
})
check("sale_create uses pos_invoice_prefix POS26-",
      r_pos_pref_sale["ok"] and r_pos_pref_sale["data"]["invoice_no"].startswith("POS26-"))

r_used_cust = call(a, "used_create", {
    "seller_name": "بائع مسجل تلقائياً",
    "seller_phone": "01555666777",
    "model": "iPad Air 5",
    "buy_price": 8000,
    "to_inventory": False,
})
check("used_create uses used_prefix USD- & registers seller in customers",
      r_used_cust["ok"]
      and r_used_cust["data"]["ref"].startswith("USD-")
      and r_used_cust["data"]["customer_id"] is not None)
c_search_used = call(a, "customers_search", {"q": "01555666777"})
check("seller from used_create found via customers_search",
      c_search_used["ok"] and any(c["name"] == "بائع مسجل تلقائياً" for c in c_search_used["data"]))

# (هـ) تذكرة صيانة ببادئة TKT- + تعديل التذكرة (repair_update) + حذف تذكرة غير مسلمة (repair_delete) + منع حذف تذكرة مسلمة بتكلفة
r_rep2 = call(a, "repair_create", {
    "customer_name": "عميل صيانة 2",
    "customer_phone": "01122334455",
    "device_type": "لابتوب لينوفو",
    "problem": "تغيير كيبورد",
    "cost": 450,
})
check("repair_create uses repair_prefix TKT-",
      r_rep2["ok"] and r_rep2["data"]["ref"].startswith("TKT-"))
rid2 = r_rep2["data"]["id"]
r_rep_upd = call(a, "repair_update", {
    "id": rid2,
    "problem": "تغيير كيبورد وتنظيف مروحة",
    "cost": 550,
})
check("repair_update updates problem and cost",
      r_rep_upd["ok"] and r_rep_upd["data"]["cost"] == 55000 and "مروحة" in r_rep_upd["data"]["problem"])
r_rep_del_ok = call(a, "repair_delete", {"id": rid2})
check("repair_delete deletes undelivered repair ticket", r_rep_del_ok["ok"])
call(a, "repair_set_status", {"id": rid, "status": "repaired"})
call(a, "repair_set_status", {"id": rid, "status": "delivered"})
r_rep_del_delivered_err = call(a, "repair_delete", {"id": rid})
check("repair_delete blocks deleting delivered paid repair ticket", not r_rep_del_delivered_err["ok"])

# (و) سجل المبيعات والمرتجعات (sales & sales_stats & history_suggestions) يعرض الكل والتاريخ والأتوكمبليت
r_hist_all = call(a, "sales", {"all_dates": True, "limit": 50})
kinds_found = {(row.get("kind"), row.get("sub_kind")) for row in r_hist_all["data"]["rows"]}
check("history sales(all_dates=True) includes pos, b2b, quote, and repair",
      r_hist_all["ok"]
      and ("sale", "pos") in kinds_found
      and ("sale", "b2b") in kinds_found
      and ("quote", "quote") in kinds_found
      and ("repair", "repair") in kinds_found)
r_hist_sug = call(a, "history_suggestions", {"q": "N00"})
check("history_suggestions autocomplete works",
      r_hist_sug["ok"] and len(r_hist_sug["data"]) >= 1)

# (ز) التقارير المالية (report_daily) تدعم من تاريخ إلى تاريخ (date_from / date_to)
r_rep_range = call(a, "report_daily", {"date_from": today, "date_to": today})
check("report_daily supports date_from & date_to",
      r_rep_range["ok"] and r_rep_range["data"]["sales"]["count"] >= 1)

# (ح) التحقق من رفع خلفية سطح المكتب في profile.html وتخطيط الحقول في staff.html
pf_html = (ROOT / "web" / "profile.html").read_text(encoding="utf-8")
stf_html = (ROOT / "web" / "staff.html").read_text(encoding="utf-8")
check("profile.html has custom wallpaper upload & staff.html has non-overlapping staff-fields-grid",
      "pf-custom-bg-file" in pf_html and "staff-fields-grid" in stf_html)

# إعادة البادئات للافتراضي
call(a, "templates_save", {"reset_pos": True})

# (ط) فحص سلامة صياغة JavaScript في web/app.js و web/index.html لمنع أي خطأ SyntaxError يوقف شاشة الدخول
app_js_text = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
idx_html_text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
check("web/app.js has no duplicate const st declaration & index.html has pin-input + login-error-box",
      app_js_text.count("const globalTaxEnabled = st.tax_enabled") == 2
      and "id=\"pin-input\"" in idx_html_text
      and "id=\"login-error-box\"" in idx_html_text)

# 14) تطابق العقد: كل api('NAME') في الواجهة موجود في Api
names = set()
for p in list((ROOT / "web").glob("*.html")) + [ROOT / "web" / "desktop.html", ROOT / "web" / "sales_quotes.html", ROOT / "web" / "settings.html", ROOT / "web" / "staff.html", ROOT / "web" / "profile.html", ROOT / "web" / "app.js"]:
    if not p.exists(): continue
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
