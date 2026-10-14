"""Backend Api: كل دوال النظام + dispatcher واحد للواجهة (window.pywebview.api.call)."""
import datetime
import hmac
import json
import os
import sqlite3
import sys
import traceback
from decimal import Decimal, ROUND_HALF_UP

import db

# حالة الجلسة (مستخدم واحد، نافذة واحدة) — الدور والصلاحيات تُقرأ من هنا وليس من JS
_STATE = {"user": None}


class ApiError(Exception):
    pass


def _money(v, default=0):
    """عرض/مبالغ من الواجهة (وحدات كاملة 123.45) → INTEGER وحدات صغرى."""
    if v in (None, ""):
        return int(default)
    if isinstance(v, bool):
        raise ApiError("قيمة مبلغ غير صالحة")
    try:
        d = Decimal(str(v).strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        raise ApiError("قيمة مبلغ غير صالحة")
    return int(d * 100)


def _int(v, default=0):
    if v in (None, ""):
        return int(default)
    try:
        return int(v)
    except Exception:
        raise ApiError("قيمة عددية غير صالحة")


def _fmt_money(minor: int) -> str:
    """دالة تنسيق واحدة: وحدات صغرى → نص عرض."""
    return f"{(minor / 100):,.2f}"


REPAIR_FLOW = {
    "received": ["in_review", "rejected"],
    "in_review": ["pending_approval", "repaired", "rejected"],
    "pending_approval": ["in_review", "repaired", "rejected"],
    "repaired": ["delivered"],
    "rejected": [],
    "delivered": [],
}


def _upsert_customer(conn, name, phone=None):
    """إدراج أو استرجاع معرف العميل بأمان مع دعم الهاتف الفارغ."""
    name = (name or "").strip()
    if not name:
        return None
    phone = (phone or "").strip() or None
    row = conn.execute(
        "SELECT id, phone FROM customers WHERE name=? AND (phone=? OR (? IS NULL AND phone IS NULL) OR phone IS NULL) ORDER BY id LIMIT 1",
        (name, phone, phone),
    ).fetchone()
    if row:
        if phone and not row["phone"]:
            try:
                conn.execute("UPDATE customers SET phone=? WHERE id=?", (phone, row["id"]))
            except sqlite3.IntegrityError:
                pass
        return row["id"]
    cur = conn.execute(
        "INSERT INTO customers(name, phone, created_at) VALUES(?,?,?)",
        (name, phone, db.now()),
    )
    return cur.lastrowid


def _customer_debt_summary(conn, cust_row) -> dict:
    """حساب إجمالي المشتريات، إجمالي الآجل الصافي، إجمالي المسدد بسندات قبض، والمديونية المتبقية للعميل."""
    cid = cust_row["id"]
    cname = cust_row["name"]
    cphone = cust_row["phone"]
    sales = conn.execute(
        """SELECT s.id, s.invoice_no, s.created_at, s.total, s.status,
                  COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.sale_id=s.id AND p.method='credit'), 0) AS credit_amt,
                  COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.sale_id=s.id AND p.method='cash'), 0) AS cash_amt,
                  COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.sale_id=s.id AND p.method='wallet'), 0) AS wallet_amt,
                  COALESCE((SELECT SUM(sr.total) FROM sale_returns sr WHERE sr.sale_id=s.id), 0) AS ret_amt
           FROM sales s
           WHERE s.customer_id=?
              OR (s.customer_id IS NULL AND s.customer_name=?)
              OR (? IS NOT NULL AND ? != '' AND s.customer_phone=?)
           ORDER BY s.id DESC""",
        (cid, cname, cphone, cphone, cphone),
    ).fetchall()

    total_purchases = 0
    credit_total = 0
    sales_out = []
    for s in sales:
        d = dict(s)
        net_total = max(0, d["total"] - d["ret_amt"])
        # المرتجعات تخفض أولاً من المديونية الآجلة إن وجدت على نفس الفاتورة
        net_credit = max(0, d["credit_amt"] - d["ret_amt"])
        d["net_total"] = net_total
        d["net_credit"] = net_credit
        total_purchases += net_total
        credit_total += net_credit
        sales_out.append(d)

    vouchers = conn.execute(
        """SELECT cp.*, u.name AS user_name, s.invoice_no
           FROM customer_payments cp
           LEFT JOIN users u ON u.id=cp.user_id
           LEFT JOIN sales s ON s.id=cp.sale_id
           WHERE cp.customer_id=?
           ORDER BY cp.id DESC""",
        (cid,),
    ).fetchall()
    vouchers_out = [dict(v) for v in vouchers]
    paid_total = sum(v["amount"] for v in vouchers_out)
    debt = max(0, credit_total - paid_total)
    return {
        "total_purchases": total_purchases,
        "credit_total": credit_total,
        "paid_total": paid_total,
        "debt": debt,
        "sales": sales_out,
        "vouchers": vouchers_out,
    }


class Api:
    def __init__(self):
        db.connect()  # إنشاء المخطط + الـ seed عند الإقلاع
        self._methods = {
            n for n in dir(self)
            if not n.startswith("_") and callable(getattr(self, n)) and n != "call"
        }

    # ---------------------------------------------------------------- جسر
    def call(self, name, payload=None):
        try:
            if name not in self._methods:
                raise ApiError("نداء غير معروف")
            fn = getattr(self, name)
            if payload is None:
                data = fn()
            elif isinstance(payload, dict):
                data = fn(**payload)
            else:
                data = fn(payload)
            return {"ok": True, "data": data}
        except ApiError as e:
            return {"ok": False, "error": str(e)}
        except TypeError:
            return {"ok": False, "error": "معاملات غير صالحة للطلب"}
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return {"ok": False, "error": "حدث خطأ غير متوقع، راجع سجل البرنامج"}

    # ---------------------------------------------------------- صلاحيات
    def _user(self):
        u = _STATE["user"]
        if not u:
            raise ApiError("يجب تسجيل الدخول أولاً")
        return u

    def _has_perm(self, key: str) -> bool:
        u = _STATE["user"]
        if not u:
            return False
        if u["role"] == "admin":
            return True
        return bool((u.get("permissions") or {}).get(key, False))

    def _perm(self, key: str):
        u = self._user()
        if u["role"] == "admin":
            return u
        if not (u.get("permissions") or {}).get(key, False):
            raise ApiError("ممنوع: للمدير أو لمن يملك الصلاحية فقط")
        return u

    def _admin(self):
        u = self._user()
        if u["role"] != "admin":
            raise ApiError("ممنوع: للمدير فقط")
        return u

    def _settings(self, conn):
        return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}

    def _open_shift(self, conn, user_id):
        return conn.execute(
            "SELECT * FROM shifts WHERE user_id=? AND closed_at IS NULL ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()

    # ---------------------------------------------------------- جلسة ومستخدمون
    def users(self):
        with db.connect() as conn:
            rows = conn.execute("SELECT id, username, name, role, permissions, created_at FROM users ORDER BY id").fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["permissions"] = db.parse_user_perms(d["role"], d.get("permissions"))
                out.append(d)
            return out

    def user_save(self, username, name, role="cashier", pin=None, permissions=None, id=None):
        self._perm("settings_manage")
        username = (username or "").strip()
        name = (name or "").strip()
        if not username or not name:
            raise ApiError("اسم الدخول والاسم الكامل مطلوبان")
        if role not in ("admin", "cashier"):
            raise ApiError("دور المستخدم غير صالح")
        if pin is not None and str(pin).strip() != "":
            pin = str(pin).strip()
            if len(pin) != 4 or not pin.isdigit():
                raise ApiError("الرمز السري يجب أن يتكون من 4 أرقام")
        else:
            pin = None

        perms_dict = dict(db.ALL_ADMIN_PERMS) if role == "admin" else dict(db.DEFAULT_CASHIER_PERMS)
        if role != "admin" and isinstance(permissions, dict):
            for k in perms_dict:
                if k in permissions:
                    perms_dict[k] = bool(permissions[k])
        perms_json = json.dumps(perms_dict, ensure_ascii=False)

        with db.connect() as conn:
            try:
                if id:
                    uid = _int(id)
                    if pin:
                        salt = os.urandom(16)
                        conn.execute(
                            "UPDATE users SET username=?, name=?, role=?, pin_salt=?, pin_hash=?, permissions=? WHERE id=?",
                            (username, name, role, salt, db.hash_pin(pin, salt), perms_json, uid),
                        )
                    else:
                        conn.execute(
                            "UPDATE users SET username=?, name=?, role=?, permissions=? WHERE id=?",
                            (username, name, role, perms_json, uid),
                        )
                    if _STATE["user"] and _STATE["user"]["id"] == uid:
                        _STATE["user"]["name"] = name
                        _STATE["user"]["role"] = role
                        _STATE["user"]["permissions"] = perms_dict
                    return {"id": uid}
                else:
                    if not pin:
                        raise ApiError("الرمز السري (4 أرقام) مطلوب للمستخدم الجديد")
                    salt = os.urandom(16)
                    cur = conn.execute(
                        "INSERT INTO users(username, name, role, pin_salt, pin_hash, permissions, created_at) VALUES(?,?,?,?,?,?,?)",
                        (username, name, role, salt, db.hash_pin(pin, salt), perms_json, db.now()),
                    )
                    return {"id": cur.lastrowid}
            except sqlite3.IntegrityError:
                raise ApiError("اسم الدخول مسجل مسبقاً")

    def user_delete(self, id):
        u = self._perm("settings_manage")
        uid = _int(id)
        if uid == u["id"]:
            raise ApiError("لا يمكنك حذف حسابك الحالي أثناء الجلسة")
        with db.connect() as conn:
            target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not target:
                raise ApiError("المستخدم غير موجود")
            if target["role"] == "admin":
                admins = conn.execute("SELECT COUNT(*) c FROM users WHERE role='admin'").fetchone()["c"]
                if admins <= 1:
                    raise ApiError("لا يمكن حذف المدير الوحيد في النظام")
            try:
                conn.execute("DELETE FROM users WHERE id=?", (uid,))
            except sqlite3.IntegrityError:
                raise ApiError("لا يمكن حذف مستخدم مرتبط بعمليات بيع أو صيانة سابقة")
            return True

    def login(self, username, pin):
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            pin = str(pin or "")
            if not row or len(pin) != 4:
                raise ApiError("اسم المستخدم أو الرمز السري غير صحيح")
            expect = db.hash_pin(pin, row["pin_salt"])
            if not hmac.compare_digest(expect, row["pin_hash"]):
                raise ApiError("اسم المستخدم أو الرمز السري غير صحيح")
            perms = db.parse_user_perms(row["role"], row["permissions"] if "permissions" in row.keys() else None)
            _STATE["user"] = {
                "id": row["id"],
                "username": row["username"],
                "name": row["name"],
                "role": row["role"],
                "permissions": perms,
            }
            return dict(_STATE["user"])

    def session(self):
        if _STATE["user"]:
            with db.connect() as conn:
                row = conn.execute("SELECT id, username, name, role, permissions FROM users WHERE id=?", (_STATE["user"]["id"],)).fetchone()
                if row:
                    _STATE["user"] = {
                        "id": row["id"],
                        "username": row["username"],
                        "name": row["name"],
                        "role": row["role"],
                        "permissions": db.parse_user_perms(row["role"], row["permissions"]),
                    }
        return {"user": _STATE["user"]}

    def logout(self):
        _STATE["user"] = None
        return True

    # ---------------------------------------------------------- إعدادات
    def settings(self):
        self._user()
        with db.connect() as conn:
            return self._settings(conn)

    def settings_save(self, **kv):
        self._perm("settings_manage")
        allowed = {"store_name", "store_address", "store_phone", "currency", "tax_enabled", "tax_rate",
                   "store_email", "store_cr", "store_vat", "receipt_thanks", "receipt_footer",
                   "receipt_logo", "receipt_show_logo", "receipt_show_barcode",
                   "receipt_show_tax", "receipt_show_payments"}
        show = {"tax_enabled", "receipt_show_logo", "receipt_show_barcode", "receipt_show_tax", "receipt_show_payments"}
        with db.connect() as conn:
            for k, v in kv.items():
                if k not in allowed or v is None:
                    continue
                s = str(v)
                if s == "" and k not in show:
                    continue
                if k in show:
                    if s not in ("0", "1"):
                        raise ApiError("قيمة عرض غير صالحة (استخدم 0 أو 1)")
                elif k == "receipt_logo":
                    if not s.startswith("data:image/"):
                        raise ApiError("صيغة الشعار غير صالحة (يجب أن تكون صورة data:image/)")
                    if len(s.encode("utf-8")) > 200 * 1024:
                        raise ApiError("حجم الشعار يتجاوز 200KB")
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, s),
                )
            return self._settings(conn)

    # ---------------------------------------------------------- فئات
    def categories(self):
        self._user()
        with db.connect() as conn:
            rows = conn.execute(
                """SELECT c.id, c.name, COUNT(p.id) n FROM categories c
                   LEFT JOIN products p ON p.category_id=c.id AND p.active=1
                   GROUP BY c.id ORDER BY c.name"""
            ).fetchall()
            return [dict(r) for r in rows]

    def categories_save(self, name):
        self._perm("inventory_edit")
        name = (name or "").strip()
        if not name:
            raise ApiError("اسم الفئة مطلوب")
        with db.connect() as conn:
            try:
                cur = conn.execute("INSERT INTO categories(name) VALUES(?)", (name,))
            except sqlite3.IntegrityError:
                raise ApiError("توجد فئة بهذا الاسم مسبقاً")
            return {"id": cur.lastrowid}

    def categories_delete(self, id):
        self._perm("inventory_edit")
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) c FROM products WHERE category_id=? AND active=1", (id,)).fetchone()["c"]
            if n:
                raise ApiError("لا يمكن حذف فئة عليها منتجات")
            conn.execute("DELETE FROM categories WHERE id=?", (id,))
            return True

    def categories_update(self, id, name):
        self._perm("inventory_edit")
        name = (name or "").strip()
        if not name:
            raise ApiError("اسم الفئة مطلوب")
        with db.connect() as conn:
            try:
                cur = conn.execute("UPDATE categories SET name=? WHERE id=?", (name, _int(id)))
            except sqlite3.IntegrityError:
                raise ApiError("توجد فئة بهذا الاسم مسبقاً")
            if not cur.rowcount:
                raise ApiError("الفئة غير موجودة")
            return True

    # ---------------------------------------------------------- منتجات
    def _product_row(self, r, show_cost):
        d = dict(r)
        if not show_cost:
            d["cost"] = None
        qty, minq = d["qty"], d["min_qty"]
        d["stock_state"] = "out" if qty <= 0 else ("low" if qty <= minq else "in")
        return d

    def products(self, q=None, category_id=None, stock=None, limit=200, offset=0):
        self._user()
        show_cost = self._has_perm("cost_view")
        limit, offset = _int(limit, 200), _int(offset, 0)
        where, args = ["p.active=1"], []
        if q:
            where.append("(p.name LIKE ? OR p.sku LIKE ?)")
            args += [f"%{q}%", f"%{q}%"]
        if category_id:
            where.append("p.category_id=?")
            args.append(_int(category_id))
        if stock == "out":
            where.append("p.qty<=0")
        elif stock == "low":
            where.append("p.qty>0 AND p.qty<=p.min_qty")
        elif stock == "in":
            where.append("p.qty>p.min_qty")
        base_from = "FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE " + " AND ".join(where)
        with db.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) {base_from}", args).fetchone()[0]
            rows = conn.execute(
                f"SELECT p.*, c.name category {base_from} ORDER BY p.name LIMIT ? OFFSET ?",
                args + [limit, offset],
            ).fetchall()
            return {"rows": [self._product_row(r, show_cost) for r in rows], "total": total}

    def product(self, id):
        self._user()
        show_cost = self._has_perm("cost_view")
        with db.connect() as conn:
            r = conn.execute(
                """SELECT p.*, c.name category FROM products p
                   LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=?""", (id,),
            ).fetchone()
            if not r or not r["active"]:
                raise ApiError("المنتج غير موجود")
            return self._product_row(r, show_cost)

    def product_save(self, id=None, sku="", name="", category_id=None, price=0, cost=0,
                     min_qty=5, tracked=0, notes=None, serials=None):
        self._perm("inventory_edit")
        name = (name or "").strip()
        sku = (sku or "").strip()
        if not name or not sku:
            raise ApiError("اسم المنتج والباركود/SKU مطلوبان")
        serials = [s.strip() for s in (serials or []) if s and s.strip()]
        with db.connect() as conn:
            try:
                if id:
                    cur = conn.execute(
                        """UPDATE products SET sku=?, name=?, category_id=?, price=?, cost=?, min_qty=?, tracked=?, notes=?
                           WHERE id=?""",
                        (sku, name, _int(category_id) or None, _money(price), _money(cost),
                         _int(min_qty, 5), _int(tracked), notes, _int(id)),
                    )
                    if not cur.rowcount:
                        raise ApiError("المنتج غير موجود")
                    pid = _int(id)
                else:
                    cur = conn.execute(
                        """INSERT INTO products(sku, name, category_id, price, cost, min_qty, tracked, notes, created_at)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (sku, name, _int(category_id) or None, _money(price), _money(cost),
                         _int(min_qty, 5), _int(tracked), notes, db.now()),
                    )
                    pid = cur.lastrowid
                if serials:
                    self._add_serials(conn, pid, serials)
            except sqlite3.IntegrityError:
                raise ApiError("الباركود/SKU أو أحد الأرقام التسلسلية مسجل مسبقاً")
            return {"id": pid}

    def _add_serials(self, conn, pid, serials):
        added = 0
        for s in serials:
            conn.execute("INSERT INTO serials(product_id, serial, status, created_at) VALUES(?,?,?,?)",
                         (pid, s, "in_stock", db.now()))
            added += 1
        if added:
            conn.execute("UPDATE products SET qty=qty+? WHERE id=?", (added, pid))
            after = conn.execute("SELECT qty FROM products WHERE id=?", (pid,)).fetchone()[0]
            conn.execute(
                "INSERT INTO stock_movements(created_at, user_id, product_id, qty_change, qty_after, reason, ref) VALUES(?,?,?,?,?,?,?)",
                (db.now(), self._user()["id"], pid, added, after, "serial_add", None),
            )

    def product_delete(self, id):
        self._perm("inventory_edit")
        with db.connect() as conn:
            cur = conn.execute("UPDATE products SET active=0 WHERE id=?", (_int(id),))
            if not cur.rowcount:
                raise ApiError("المنتج غير موجود")
            return True

    def products_search(self, q=None, limit=30, category_id=None):
        self._user()
        q = (q or "").strip()
        limit = _int(limit, 30)
        cat = _int(category_id) if category_id not in (None, "") else None
        cat_sql = " AND p.category_id=?" if cat else ""
        cat_args = [cat] if cat else []
        with db.connect() as conn:
            if not q:
                rows = conn.execute(
                    """SELECT p.id, p.name, p.sku, p.price, p.qty, p.tracked, p.min_qty, c.name category
                       FROM products p LEFT JOIN categories c ON c.id=p.category_id
                       WHERE p.active=1""" + cat_sql + """ ORDER BY p.name LIMIT ?""", (*cat_args, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT DISTINCT p.id, p.name, p.sku, p.price, p.qty, p.tracked, p.min_qty, c.name category
                       FROM products p LEFT JOIN categories c ON c.id=p.category_id
                       WHERE p.active=1""" + cat_sql + """ AND (p.name LIKE ? OR p.sku LIKE ? OR EXISTS(
                           SELECT 1 FROM serials s WHERE s.product_id=p.id AND s.serial LIKE ? AND s.status='in_stock'))
                       ORDER BY p.name LIMIT ?""",
                    (*cat_args, f"%{q}%", f"%{q}%", f"%{q}%", limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def product_adjust(self, id, qty_change, reason="تعديل يدوي"):
        u = self._perm("inventory_edit")
        pid, delta = _int(id), _int(qty_change)
        if delta == 0:
            raise ApiError("تغيير الكمية صفري")
        with db.connect() as conn:
            p = conn.execute("SELECT qty FROM products WHERE id=? AND active=1", (pid,)).fetchone()
            if not p:
                raise ApiError("المنتج غير موجود")
            newq = p["qty"] + delta
            if newq < 0:
                raise ApiError(f"لا يمكن تخفيض المخزون إلى سالب (المتوفر {p['qty']})")
            conn.execute("UPDATE products SET qty=? WHERE id=?", (newq, pid))
            conn.execute(
                "INSERT INTO stock_movements(created_at, user_id, product_id, qty_change, qty_after, reason, ref) VALUES(?,?,?,?,?,?,?)",
                (db.now(), u["id"], pid, delta, newq, reason or "تعديل يدوي", None),
            )
            return {"qty": newq}

    def serials(self, product_id):
        self._user()
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM serials WHERE product_id=? ORDER BY id DESC", (_int(product_id),)
            ).fetchall()
            return [dict(r) for r in rows]

    def serial_add(self, product_id, serial):
        self._perm("inventory_edit")
        serial = (serial or "").strip()
        if not serial:
            raise ApiError("الرقم التسلسلي مطلوب")
        with db.connect() as conn:
            p = conn.execute("SELECT id FROM products WHERE id=? AND active=1", (_int(product_id),)).fetchone()
            if not p:
                raise ApiError("المنتج غير موجود")
            try:
                self._add_serials(conn, _int(product_id), [serial])
            except sqlite3.IntegrityError:
                raise ApiError("الرقم التسلسلي مسجل مسبقاً")
            return True

    # ---------------------------------------------------------- عملاء ومديونيات وسندات قبض
    def customers_search(self, q=""):
        self._user()
        q = (q or "").strip()
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name LIMIT 20",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                summary = _customer_debt_summary(conn, r)
                d["credit_total"] = summary["credit_total"]
                d["paid_total"] = summary["paid_total"]
                d["debt"] = summary["debt"]
                out.append(d)
            return out

    def customer(self, id):
        self._user()
        with db.connect() as conn:
            r = conn.execute("SELECT * FROM customers WHERE id=?", (_int(id),)).fetchone()
            if not r:
                raise ApiError("العميل غير موجود")
            d = dict(r)
            summary = _customer_debt_summary(conn, r)
            d["credit_total"] = summary["credit_total"]
            d["paid_total"] = summary["paid_total"]
            d["debt"] = summary["debt"]
            return d

    def customers_save(self, name, phone=None, id=None):
        self._perm("customers_edit")
        name = (name or "").strip()
        phone = (phone or "").strip() or None
        if not name:
            raise ApiError("اسم العميل مطلوب")
        with db.connect() as conn:
            try:
                if id:
                    cid = _int(id)
                    cur = conn.execute("UPDATE customers SET name=?, phone=? WHERE id=?", (name, phone, cid))
                    if not cur.rowcount:
                        raise ApiError("العميل غير موجود")
                    return {"id": cid}
                else:
                    dup = conn.execute(
                        "SELECT id FROM customers WHERE name=? AND COALESCE(phone,'')=COALESCE(?, '')",
                        (name, phone),
                    ).fetchone()
                    if dup:
                        raise ApiError("العميل مسجل مسبقاً بنفس الاسم ورقم الهاتف")
                    cur = conn.execute(
                        "INSERT INTO customers(name, phone, created_at) VALUES(?,?,?)",
                        (name, phone, db.now()),
                    )
                    return {"id": cur.lastrowid}
            except sqlite3.IntegrityError:
                raise ApiError("العميل مسجل مسبقاً بنفس الاسم ورقم الهاتف")

    def customers_delete(self, id):
        self._perm("customers_delete")
        cid = _int(id)
        with db.connect() as conn:
            conn.execute("UPDATE sales SET customer_id=NULL WHERE customer_id=?", (cid,))
            conn.execute("DELETE FROM customers WHERE id=?", (cid,))
            return True

    def customers_list(self, limit=100, offset=0, debt_only=False):
        self._perm("customers_view")
        limit, offset = _int(limit, 100), _int(offset, 0)
        with db.connect() as conn:
            all_rows = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
            enriched = []
            for r in all_rows:
                d = dict(r)
                summary = _customer_debt_summary(conn, r)
                d["total_purchases"] = summary["total_purchases"]
                d["credit_total"] = summary["credit_total"]
                d["paid_total"] = summary["paid_total"]
                d["debt"] = summary["debt"]
                if debt_only and d["debt"] <= 0:
                    continue
                enriched.append(d)
            total = len(enriched)
            return {"rows": enriched[offset:offset + limit], "total": total}

    def customer_history(self, id):
        self._perm("customers_view")
        cid = _int(id)
        with db.connect() as conn:
            cust = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
            if not cust:
                raise ApiError("العميل غير موجود")
            cname = cust["name"]
            cphone = cust["phone"]
            summary = _customer_debt_summary(conn, cust)
            cust_dict = dict(cust)
            cust_dict["total_purchases"] = summary["total_purchases"]
            cust_dict["credit_total"] = summary["credit_total"]
            cust_dict["paid_total"] = summary["paid_total"]
            cust_dict["debt"] = summary["debt"]

            events = []
            for s in summary["sales"]:
                if s["net_credit"] > 0:
                    events.append({
                        "kind": "credit_sale",
                        "ref": s["invoice_no"],
                        "sale_id": s["id"],
                        "created_at": s["created_at"],
                        "debit": s["net_credit"],
                        "credit": 0,
                        "method": "credit",
                        "ref_no": None,
                        "notes": f"فاتورة آجلة ({s['invoice_no']})",
                    })
            for v in summary["vouchers"]:
                events.append({
                    "kind": "voucher",
                    "id": v["id"],
                    "ref": v["ref"],
                    "sale_id": v["sale_id"],
                    "created_at": v["created_at"],
                    "debit": 0,
                    "credit": v["amount"],
                    "method": v["method"],
                    "ref_no": v["ref_no"],
                    "notes": v["notes"] or ("سداد نقدي" if v["method"] == "cash" else "سداد محفظة"),
                    "user_name": v["user_name"],
                })
            events.sort(key=lambda x: (x["created_at"], 0 if x["kind"] == "credit_sale" else 1))
            running = 0
            for ev in events:
                running = max(0, running + ev["debit"] - ev["credit"])
                ev["balance_after"] = running
            events.reverse()

            repairs = conn.execute(
                """SELECT r.id, r.ref, r.created_at, r.device_type, r.problem, r.status, r.cost
                   FROM repairs r
                   WHERE r.customer_name=?
                      OR (? IS NOT NULL AND ? != '' AND r.customer_phone=?)
                   ORDER BY r.id DESC""",
                (cname, cphone, cphone, cphone),
            ).fetchall()
            return {
                "customer": cust_dict,
                "sales": summary["sales"],
                "vouchers": summary["vouchers"],
                "ledger": events,
                "repairs": [dict(r) for r in repairs],
            }

    def customer_payment_create(self, customer_id, amount, method="cash", ref_no=None, sale_id=None, notes=None):
        u = self._perm("customers_edit")
        cid = _int(customer_id)
        amt = _money(amount)
        if amt <= 0:
            raise ApiError("مبلغ السداد يجب أن يكون أكبر من صفر")
        if method not in ("cash", "wallet"):
            raise ApiError("طريقة السداد غير صالحة (نقدي أو محفظة)")
        ref_no = (ref_no or "").strip() or None
        if method == "wallet" and not ref_no:
            raise ApiError("يرجى إدخال رقم العملية المرجعية لتحويل المحفظة")
        with db.connect() as conn:
            cust = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
            if not cust:
                raise ApiError("العميل غير موجود")
            summary = _customer_debt_summary(conn, cust)
            if summary["debt"] <= 0:
                raise ApiError("لا توجد مديونية مستحقة على هذا العميل")
            if amt > summary["debt"]:
                raise ApiError(f"مبلغ السداد ({_fmt_money(amt)}) أكبر من إجمالي المديونية المتبقية ({_fmt_money(summary['debt'])})")
            s = self._open_shift(conn, u["id"])
            shift_id = s["id"] if s else None
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            cnt = conn.execute("SELECT COUNT(*) c FROM customer_payments").fetchone()["c"] + 1
            ref = f"RCV-{ts}-{cnt:03d}"
            cur = conn.execute(
                """INSERT INTO customer_payments(ref, customer_id, sale_id, user_id, shift_id, created_at, amount, method, ref_no, notes)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (ref, cid, _int(sale_id) if sale_id else None, u["id"], shift_id, db.now(), amt, method, ref_no, (notes or "").strip() or None),
            )
            return {"id": cur.lastrowid, "ref": ref, "remaining_debt": summary["debt"] - amt}

    def customer_payment_delete(self, id):
        self._perm("customers_delete")
        with db.connect() as conn:
            cur = conn.execute("DELETE FROM customer_payments WHERE id=?", (_int(id),))
            if not cur.rowcount:
                raise ApiError("سند القبض غير موجود")
            return True

    # ---------------------------------------------------------- ورديات
    def shift(self):
        u = self._user()
        with db.connect() as conn:
            s = self._open_shift(conn, u["id"])
            today = conn.execute(
                """SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM sales
                   WHERE created_at >= date('now','localtime')""",
            ).fetchone()
            shift_sales = None
            if s:
                shift_sales = conn.execute(
                    "SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM sales WHERE shift_id=?", (s["id"],)
                ).fetchone()
            return {
                "shift": dict(s) if s else None,
                "today": {"count": today["n"], "total": today["t"]},
                "shift_sales": dict(shift_sales) if shift_sales else None,
            }

    def shift_open(self, opening_cash=0):
        u = self._user()
        with db.connect() as conn:
            if self._open_shift(conn, u["id"]):
                raise ApiError("توجد وردية مفتوحة بالفعل")
            cur = conn.execute(
                "INSERT INTO shifts(user_id, opened_at, opening_cash) VALUES(?,?,?)",
                (u["id"], db.now(), _money(opening_cash)),
            )
            return dict(conn.execute("SELECT * FROM shifts WHERE id=?", (cur.lastrowid,)).fetchone())

    def shift_close(self, counted_cash):
        u = self._user()
        with db.connect() as conn:
            s = self._open_shift(conn, u["id"])
            if not s:
                raise ApiError("لا توجد وردية مفتوحة")
            cash_sales = conn.execute(
                """SELECT COALESCE(SUM(amount),0) c FROM payments
                   JOIN sales ON sales.id=payments.sale_id
                   WHERE sales.shift_id=? AND payments.method='cash'""",
                (s["id"],),
            ).fetchone()["c"]
            cash_vouchers = conn.execute(
                """SELECT COALESCE(SUM(amount),0) c FROM customer_payments
                   WHERE shift_id=? AND method='cash'""",
                (s["id"],),
            ).fetchone()["c"]
            expected = s["opening_cash"] + cash_sales + cash_vouchers
            counted = _money(counted_cash)
            conn.execute(
                "UPDATE shifts SET closed_at=?, counted_cash=?, expected_cash=?, diff=? WHERE id=?",
                (db.now(), counted, expected, counted - expected, s["id"]),
            )
            return dict(conn.execute("SELECT * FROM shifts WHERE id=?", (s["id"],)).fetchone())

    def shifts(self):
        self._perm("reports_view")
        with db.connect() as conn:
            rows = conn.execute(
                """SELECT s.*, u.name user_name,
                          (SELECT COALESCE(SUM(total),0) FROM sales WHERE shift_id=s.id) sales_total
                   FROM shifts s JOIN users u ON u.id=s.user_id
                   ORDER BY s.id DESC LIMIT 50"""
            ).fetchall()
            return [dict(r) for r in rows]

    # ---------------------------------------------------------- مبيعات
    def sale_create(self, items, discount=0, payments=None, customer_name=None, customer_phone=None, notes=None):
        u = self._perm("pos_sell")
        can_edit_price = self._has_perm("pos_price")
        items = items or []
        if not items:
            raise ApiError("السلة فارغة")
        payments = payments or []
        customer_name = (customer_name or "").strip() or None
        customer_phone = (customer_phone or "").strip() or None
        with db.connect() as conn:
            s = self._open_shift(conn, u["id"])
            if not s:
                raise ApiError("لا يمكن البيع بدون وردية مفتوحة — افتح وردية أولاً")
            st = self._settings(conn)
            tax_enabled = st.get("tax_enabled", "1") != "0"
            rate = int(Decimal(st.get("tax_rate", "14") or 0)) if tax_enabled else 0

            has_credit = any((p.get("method") == "credit" and _money(p.get("amount"), 0) > 0) for p in payments)
            if has_credit and not customer_name:
                raise ApiError("لا يمكن البيع الآجل بدون اختيار أو إدخال اسم العميل")

            customer_id = _upsert_customer(conn, customer_name, customer_phone) if customer_name else None

            lines = []
            for it in items:
                pid = _int(it.get("product_id"))
                qty = _int(it.get("qty", 1))
                if qty <= 0:
                    raise ApiError("كمية غير صالحة")
                p = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
                if not p:
                    raise ApiError("منتج غير موجود في السلة")
                up = it.get("unit_price")
                unit = p["price"]
                if up is not None and can_edit_price:
                    unit = _money(up)
                if p["tracked"]:
                    serial_ids = it.get("serial_ids") or []
                    if len(serial_ids) != qty:
                        raise ApiError(f"منتج متتبّع بالسيريال: يتطلب {qty} رقم تسلسلي متاح")
                    srows = conn.execute(
                        "SELECT * FROM serials WHERE product_id=? AND id IN (%s)" % ",".join("?" * qty),
                        [pid] + [_int(x) for x in serial_ids],
                    ).fetchall()
                    if len(srows) != qty or any(r["status"] != "in_stock" for r in srows):
                        raise ApiError("أحد الأرقام التسلسلية غير متاح")
                    for r in srows:
                        lines.append((p, 1, unit, [r["id"]]))
                else:
                    if p["qty"] < qty:
                        raise ApiError(f"مخزون غير كافٍ لـ {p['name']} (المتوفر {p['qty']})")
                    lines.append((p, qty, unit, []))

            discount = _money(discount)
            subtotal = sum(q * up for _, q, up, _ in lines)
            if discount < 0 or discount > subtotal:
                raise ApiError("قيمة الخصم غير صالحة")
            taxable = subtotal - discount
            tax = int((Decimal(taxable) * rate / 100).to_integral_value(rounding=ROUND_HALF_UP))
            total = taxable + tax

            got = 0
            pays = []
            for pay in payments:
                method = pay.get("method")
                if method not in ("cash", "wallet", "credit"):
                    raise ApiError("طريقة دفع غير معروفة (نقدي/محفظة/آجل)")
                amount = _money(pay.get("amount"))
                raw_rec = pay.get("received")
                received = _money(raw_rec) if raw_rec not in (None, "") else amount
                ref_no = (pay.get("ref_no") or "").strip() or None
                if amount <= 0:
                    raise ApiError("مبلغ دفع غير صالح")
                if len(payments) == 1 and method == "cash" and amount > total:
                    received = max(received, amount)
                    amount = total
                if method == "cash" and received < amount:
                    raise ApiError("المبلغ المستلم أقل من مبلغ الدفع النقدي")
                if method == "wallet" and not ref_no:
                    raise ApiError("يرجى إدخال رقم العملية المرجعية لتحويل المحفظة")
                pays.append((method, amount, received, max(0, received - amount), ref_no))
                got += amount
            if got != total:
                raise ApiError(f"مجموع الدفعات ({_fmt_money(got)}) لا يساوي الإجمالي ({_fmt_money(total)})")

            cur = conn.execute(
                """INSERT INTO sales(invoice_no, shift_id, user_id, customer_id, created_at, customer_name, customer_phone,
                                     subtotal, discount, tax, total, notes)
                    VALUES('INV-00000',?,?,?,?,?,?,?,?,?,?,?)""",
                (s["id"], u["id"], customer_id, db.now(), customer_name, customer_phone,
                 subtotal, discount, tax, total, notes),
            )
            sale_id = cur.lastrowid
            invoice = f"INV-{sale_id:05d}"
            conn.execute("UPDATE sales SET invoice_no=? WHERE id=?", (invoice, sale_id))

            for p, qty, unit, serials in lines:
                sid = serials[0] if serials else None
                conn.execute(
                    """INSERT INTO sale_items(sale_id, product_id, serial_id, name, qty, unit_price, line_total)
                       VALUES(?,?,?,?,?,?,?)""",
                    (sale_id, p["id"], sid, p["name"], qty, unit, unit * qty),
                )
                if serials:
                    conn.execute(
                        "UPDATE serials SET status='sold' WHERE id IN (%s)" % ",".join("?" * len(serials)),
                        serials,
                    )
                conn.execute("UPDATE products SET qty=qty-? WHERE id=?", (qty, p["id"]))
                after = conn.execute("SELECT qty FROM products WHERE id=?", (p["id"],)).fetchone()[0]
                conn.execute(
                    """INSERT INTO stock_movements(created_at, user_id, product_id, qty_change, qty_after, reason, ref)
                       VALUES(?,?,?,?,?,?,?)""",
                    (db.now(), u["id"], p["id"], -qty, after, "sale", invoice),
                )
            for method, amount, received, change, ref_no in pays:
                conn.execute(
                    "INSERT INTO payments(sale_id, method, amount, received, change, ref_no) VALUES(?,?,?,?,?,?)",
                    (sale_id, method, amount, received, change, ref_no),
                )
            return {"sale_id": sale_id, "invoice_no": invoice}

    def sale(self, id):
        self._user()
        with db.connect() as conn:
            r = conn.execute(
                """SELECT s.*, u.name user_name FROM sales s JOIN users u ON u.id=s.user_id WHERE s.id=?""",
                (_int(id),),
            ).fetchone()
            if not r:
                raise ApiError("الفاتورة غير موجودة")
            items = []
            for x in conn.execute("SELECT * FROM sale_items WHERE sale_id=?", (r["id"],)):
                it = dict(x)
                returned_qty = conn.execute(
                    "SELECT COALESCE(SUM(qty),0) q FROM sale_return_items WHERE sale_item_id=?",
                    (it["id"],),
                ).fetchone()["q"]
                it["returned_qty"] = returned_qty
                it["remaining_qty"] = max(0, it["qty"] - returned_qty)
                items.append(it)
            pays = [dict(x) for x in conn.execute("SELECT * FROM payments WHERE sale_id=?", (r["id"],))]
            d = dict(r)
            d["items"] = items
            d["payments"] = pays
            return d

    def receipt_text(self, id):
        """نص إيصال 80 عموداً للطابعة الحرارية."""
        d = self.sale(id)
        with db.connect() as conn:
            st = self._settings(conn)
        name, cur = st.get("store_name", "تك زون للإلكترونيات"), st.get("currency", "ج.م")
        tax_enabled = st.get("tax_enabled", "1") != "0"
        show_tax = tax_enabled and (st.get("receipt_show_tax", "1") != "0")
        show_pays = st.get("receipt_show_payments", "1") != "0"
        thanks = st.get("receipt_thanks") or "شكراً لزيارتكم"
        footer = st.get("receipt_footer") or "يرجى الاحتفاظ بالإيصال للاستبدال"
        W = 80
        L = []
        sep = lambda ch: ch * W

        def center(s):
            s = s[:W]
            return s.center(W)[:W]

        L.append(sep("="))
        L.append(center(name))
        if st.get("store_address"):
            L.append(center(st.get("store_address", "")))
        if st.get("store_phone"):
            L.append(center(f"هاتف: {st.get('store_phone', '')}"))
        if st.get("store_email"):
            L.append(center(st.get("store_email", "")))
        if st.get("store_cr"):
            L.append(center(f"سجل تجاري: {st.get('store_cr', '')}"))
        if st.get("store_vat"):
            L.append(center(f"الرقم الضريبي: {st.get('store_vat', '')}"))
        L.append(sep("="))
        dt = datetime.datetime.strptime(d["created_at"], "%Y-%m-%d %H:%M:%S")
        L.append(f"فاتورة: {d['invoice_no']}".ljust(40) + f"التاريخ: {dt:%d/%m/%Y}".rjust(40))
        L.append(f"الكاشير: {d['user_name']}".ljust(40) + f"الوقت: {dt:%H:%M}".rjust(40))
        if d["customer_name"]:
            L.append("العميل: " + str(d["customer_name"]))
        L.append(sep("-"))
        L.append(f"{'الصنف':<34}{'الكمية':>10}{'السعر':>20}")
        L.append(sep("-"))
        for it in d["items"]:
            nm = it["name"][:32]
            L.append(f"{nm:<34}{it['qty']:>10}{_fmt_money(it['line_total']):>20}")
        L.append(sep("-"))
        L.append(f"{'المجموع الفرعي':<40}{_fmt_money(d['subtotal']):>20}")
        if d["discount"]:
            L.append(f"{'الخصم':<40}{('-' + _fmt_money(d['discount'])):>20}")
        if show_tax and d["tax"]:
            L.append(f"{'ضريبة القيمة المضافة':<40}{_fmt_money(d['tax']):>20}")
        L.append(sep("="))
        L.append(f"{'الإجمالي':<40}{(_fmt_money(d['total']) + ' ' + cur):>20}")
        if show_pays:
            method_ar = {"cash": "نقدي", "wallet": "محفظة", "credit": "آجل"}
            for p in d["payments"]:
                extra = f" (المستلم: {_fmt_money(p['received'])})" if p["received"] > p["amount"] else ""
                ref_part = f" [مرجع: {p['ref_no']}]" if p.get("ref_no") else ""
                L.append(f"الدفع: {method_ar.get(p['method'], p['method'])} {_fmt_money(p['amount'])}{extra}{ref_part}")
            change = sum(p["change"] for p in d["payments"])
            if change:
                L.append(f"المتبقي (الباقي): {_fmt_money(change)}")
        L.append(sep("="))
        L.append(center(thanks))
        L.append(center(footer))
        L.append(sep("="))
        return "\n".join(line[:W] for line in L)

    def sales(self, date=None, kind=None, q=None, limit=100, offset=0):
        u = self._user()
        see_all = self._has_perm("sales_all")
        limit, offset = _int(limit, 100), _int(offset, 0)
        with db.connect() as conn:
            out, tot = [], 0
            kinds = (["sale", "repair"] if not kind else [kind])
            if "sale" in kinds:
                where, args = ["1=1"], []
                if date:
                    where.append("s.created_at LIKE ?")
                    args.append(f"{date}%")
                if q:
                    where.append("(s.invoice_no LIKE ? OR s.customer_name LIKE ?)")
                    args += [f"%{q}%", f"%{q}%"]
                if not see_all:
                    where.append("s.user_id=?")
                    args.append(u["id"])
                base = f"""SELECT s.id, s.invoice_no, s.created_at, u.name user_name,
                                  s.status, s.total, s.customer_name
                           FROM sales s JOIN users u ON u.id=s.user_id
                           WHERE {' AND '.join(where)}"""
                tot += conn.execute(base.replace("SELECT s.id", "SELECT COUNT(*)"), args).fetchone()[0]
                out += [{"kind": "sale", **dict(r)} for r in
                        conn.execute(base + " ORDER BY s.id DESC LIMIT 500", args).fetchall()]
            if "repair" in kinds:
                where, args = ["1=1"], []
                if date:
                    where.append("r.created_at LIKE ?")
                    args.append(f"{date}%")
                if q:
                    where.append("(r.ref LIKE ? OR r.customer_name LIKE ?)")
                    args += [f"%{q}%", f"%{q}%"]
                base = f"""SELECT r.id, r.ref, r.created_at, u.name user_name,
                                  r.status, r.cost, r.customer_name
                           FROM repairs r JOIN users u ON u.id=r.user_id
                           WHERE {' AND '.join(where)}"""
                tot += conn.execute(base.replace("SELECT r.id", "SELECT COUNT(*)"), args).fetchone()[0]
                out += [{"kind": "repair", **dict(r)} for r in
                        conn.execute(base + " ORDER BY r.id DESC LIMIT 500", args).fetchall()]
            out.sort(key=lambda x: x["created_at"], reverse=True)
            return {"rows": out[offset:offset + limit], "total": tot}

    def sales_stats(self, date=None):
        self._user()
        d = date or datetime.datetime.now().strftime("%Y-%m-%d")
        with db.connect() as conn:
            s = conn.execute(
                """SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM sales
                   WHERE created_at LIKE ? AND status != 'returned'""", (f"{d}%",),
            ).fetchone()
            ret = conn.execute(
                """SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM sale_returns WHERE created_at LIKE ?""",
                (f"{d}%",),
            ).fetchone()
            rp = conn.execute(
                """SELECT COUNT(*) n, SUM(CASE WHEN status IN ('received','in_review','pending_approval')
                   THEN 1 ELSE 0 END) active FROM repairs WHERE created_at LIKE ?""", (f"{d}%",),
            ).fetchone()
            return {"sales": {"count": s["n"], "total": s["t"]},
                    "returns": {"count": ret["n"], "total": ret["t"]},
                    "repairs": {"count": rp["n"], "active": rp["active"] or 0}}

    def sale_return(self, sale_id, items, reason=None):
        u = self._perm("sales_return")
        items = items or []
        if not items:
            raise ApiError("اختر أصنافاً للإرجاع")
        with db.connect() as conn:
            s = conn.execute("SELECT * FROM sales WHERE id=?", (_int(sale_id),)).fetchone()
            if not s:
                raise ApiError("الفاتورة غير موجودة")
            if s["status"] == "returned":
                raise ApiError("الفاتورة مرتجعة بالكامل مسبقاً")
            total = 0
            done = []
            for it in items:
                item_id, qty = _int(it.get("sale_item_id")), _int(it.get("qty", 1))
                si = conn.execute("SELECT * FROM sale_items WHERE id=? AND sale_id=?", (item_id, s["id"])).fetchone()
                if not si:
                    raise ApiError("الصنف غير موجود في الفاتورة")
                already = conn.execute(
                    """SELECT COALESCE(SUM(qty),0) q FROM sale_return_items
                       WHERE sale_item_id=?""", (item_id,),
                ).fetchone()["q"]
                if qty <= 0 or qty > si["qty"] - already:
                    raise ApiError(f"كمية الإرجاع غير صالحة (المتبقي {si['qty'] - already})")
                conn.execute("UPDATE products SET qty=qty+? WHERE id=?", (qty, si["product_id"]))
                if si["serial_id"]:
                    conn.execute("UPDATE serials SET status='in_stock' WHERE id=?", (si["serial_id"],))
                after = conn.execute("SELECT qty FROM products WHERE id=?", (si["product_id"],)).fetchone()[0]
                conn.execute(
                    """INSERT INTO stock_movements(created_at, user_id, product_id, qty_change, qty_after, reason, ref)
                       VALUES(?,?,?,?,?,?,?)""",
                    (db.now(), u["id"], si["product_id"], qty, after, "return", s["invoice_no"]),
                )
                amount = si["unit_price"] * qty
                total += amount
                done.append((item_id, qty, amount))
            cur = conn.execute(
                "INSERT INTO sale_returns(sale_id, user_id, created_at, reason, total) VALUES(?,?,?,?,?)",
                (s["id"], u["id"], db.now(), reason, total),
            )
            for item_id, qty, amount in done:
                conn.execute(
                    """INSERT INTO sale_return_items(return_id, sale_item_id, qty, amount)
                       VALUES(?,?,?,?)""",
                    (cur.lastrowid, item_id, qty, amount),
                )
            remaining = conn.execute(
                """SELECT (SELECT COALESCE(SUM(qty),0) FROM sale_items WHERE sale_id=?)
                         - (SELECT COALESCE(SUM(r.qty),0) FROM sale_return_items r
                            JOIN sale_returns sr ON sr.id=r.return_id WHERE sr.sale_id=?)""",
                (s["id"], s["id"]),
            ).fetchone()[0]
            conn.execute(
                "UPDATE sales SET status=? WHERE id=?", ("returned" if not remaining else "partial_return", s["id"]),
            )
            return {"return_id": cur.lastrowid, "total": total}

    # ---------------------------------------------------------- شراء مستعمل
    def used_create(self, seller_name, model, serial=None, seller_phone=None, seller_id_no=None,
                    device_type=None, brand=None, condition=None, notes=None, buy_price=0,
                    storage=None, resale_price=None, to_inventory=True):
        u = self._perm("used_manage")
        seller_name = (seller_name or "").strip()
        model = (model or "").strip()
        if not seller_name or not model:
            raise ApiError("اسم البائع والموديل مطلوبان")
        serial = (serial or "").strip() or None
        buy = _money(buy_price)
        if buy <= 0:
            raise ApiError("سعر الشراء مطلوب")
        ref = "TRX-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        product_id = None
        with db.connect() as conn:
            if to_inventory:
                if not serial:
                    raise ApiError("السيريال مطلوب لإضافة الجهاز للمخزون")
                if conn.execute("SELECT 1 FROM serials WHERE serial=?", (serial,)).fetchone():
                    raise ApiError("هذا الرقم التسلسلي مسجل مسبقاً في المخزون")
                cat_map = {"لابتوب": "لابتوبات", "اكسسوارات": "إكسسوارات", "اكسسوارت": "إكسسوارات", "جهاز لوحي": "أجهزة لوحية"}
                cat_id = None
                if device_type:
                    row = conn.execute("SELECT id FROM categories WHERE name=?", (cat_map.get(device_type, device_type),)).fetchone()
                    cat_id = row["id"] if row else None
                name = f"{brand} {model}".strip() if brand else model
                cur = conn.execute(
                    """INSERT INTO products(sku, name, category_id, price, cost, qty, min_qty, tracked, notes, created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (f"USED-{ref}", name, cat_id, _money(resale_price, 0), buy, 1, 1, 1,
                     f"مستعمل — {condition or 'بدون بيان'}" if condition else "مستعمل", db.now()),
                )
                product_id = cur.lastrowid
                conn.execute("INSERT INTO serials(product_id, serial, status, created_at) VALUES(?,?,?,?)",
                             (product_id, serial, "in_stock", db.now()))
                conn.execute(
                    """INSERT INTO stock_movements(created_at, user_id, product_id, serial_id, qty_change, qty_after, reason, ref)
                       VALUES(?,?,?,?,1,1,'used_purchase',?)""",
                    (db.now(), u["id"], product_id,
                     conn.execute("SELECT id FROM serials WHERE product_id=? AND serial=?", (product_id, serial)).fetchone()["id"],
                     ref),
                )
            conn.execute(
                """INSERT INTO used_device_purchases(ref, user_id, created_at, seller_name, seller_phone, seller_id_no,
                    device_type, brand, model, serial, condition, notes, buy_price, storage, resale_price, product_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ref, u["id"], db.now(), seller_name, seller_phone, seller_id_no, device_type, brand,
                 model, serial, condition, notes, buy, storage, _money(resale_price) if resale_price not in (None, "") else None,
                 product_id),
            )
            return {"ref": ref, "product_id": product_id}

    def used(self, q=None, limit=100, offset=0):
        self._user()
        limit, offset = _int(limit, 100), _int(offset, 0)
        where, args = ["1=1"], []
        if q:
            where.append("(u.ref LIKE ? OR u.seller_name LIKE ? OR u.serial LIKE ? OR u.model LIKE ?)")
            args += [f"%{q}%"] * 4
        with db.connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM used_device_purchases u WHERE {' AND '.join(where)}", args
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT u.* FROM used_device_purchases u WHERE {' AND '.join(where)}
                    ORDER BY u.id DESC LIMIT ? OFFSET ?""",
                args + [limit, offset],
            ).fetchall()
            return {"rows": [dict(r) for r in rows], "total": total}

    def used_stats(self):
        self._user()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        with db.connect() as conn:
            t = conn.execute(
                "SELECT COUNT(*) n, COALESCE(SUM(buy_price),0) sum FROM used_device_purchases WHERE created_at LIKE ?",
                (f"{today}%",),
            ).fetchone()
            stock = conn.execute("SELECT COALESCE(SUM(qty),0) n FROM products WHERE active=1").fetchone()["n"]
            return {"today_count": t["n"], "today_paid": t["sum"], "in_stock": stock}

    # ---------------------------------------------------------- صيانة
    def repair_create(self, customer_name, customer_phone, device_type, problem, address=None,
                      serial=None, accessories=None, notes=None, priority=0, cost=0):
        u = self._perm("repair_view")
        for f, v in (("customer_name", customer_name), ("customer_phone", customer_phone),
                     ("device_type", device_type), ("problem", problem)):
            if not (v or "").strip():
                raise ApiError("حقل مطلوب: " + f)
        ref = "RPR-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        with db.connect() as conn:
            _upsert_customer(conn, customer_name.strip(), customer_phone.strip())
            cur = conn.execute(
                """INSERT INTO repairs(ref, user_id, created_at, updated_at, customer_name, customer_phone, address,
                    device_type, serial, problem, accessories, notes, status, priority, cost)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'received',?,?)""",
                (ref, u["id"], db.now(), db.now(), customer_name.strip(), customer_phone.strip(), address,
                 device_type, serial, problem.strip(), accessories, notes,
                 1 if priority else 0, _money(cost)),
            )
            return {"id": cur.lastrowid, "ref": ref}

    def repairs(self, q=None, status=None, limit=100, offset=0):
        self._user()
        limit, offset = _int(limit, 100), _int(offset, 0)
        where, args = ["1=1"], []
        if status and status in REPAIR_FLOW:
            where.append("r.status=?")
            args.append(status)
        if q:
            where.append("(r.ref LIKE ? OR r.customer_name LIKE ? OR r.serial LIKE ?)")
            args += [f"%{q}%"] * 3
        with db.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM repairs r WHERE {' AND '.join(where)}", args).fetchone()[0]
            rows = conn.execute(
                f"""SELECT r.*, u.name user_name FROM repairs r JOIN users u ON u.id=r.user_id
                    WHERE {' AND '.join(where)} ORDER BY r.id DESC LIMIT ? OFFSET ?""",
                args + [limit, offset],
            ).fetchall()
            return {"rows": [dict(r) for r in rows], "total": total}

    def repair(self, id):
        self._user()
        with db.connect() as conn:
            r = conn.execute(
                """SELECT r.*, u.name user_name FROM repairs r JOIN users u ON u.id=r.user_id WHERE r.id=?""",
                (_int(id),),
            ).fetchone()
            if not r:
                raise ApiError("التذكرة غير موجودة")
            parts = [dict(p) for p in conn.execute("SELECT * FROM repair_parts WHERE repair_id=?", (r["id"],))]
            d = dict(r)
            d["parts"] = parts
            d["transitions"] = REPAIR_FLOW.get(r["status"], [])
            return d

    def repair_set_status(self, id, status):
        self._perm("repair_view")
        if status not in REPAIR_FLOW:
            raise ApiError("حالة غير معروفة")
        with db.connect() as conn:
            r = conn.execute("SELECT * FROM repairs WHERE id=?", (_int(id),)).fetchone()
            if not r:
                raise ApiError("التذكرة غير موجودة")
            if status not in REPAIR_FLOW.get(r["status"], []):
                raise ApiError(f"انتقال غير مسموح: {r['status']} ← {status}")
            conn.execute("UPDATE repairs SET status=?, updated_at=? WHERE id=?", (status, db.now(), r["id"]))
            return {"status": status}

    def repair_add_part(self, repair_id, product_id, qty=1):
        self._perm("repair_edit")
        rid, pid, q = _int(repair_id), _int(product_id), _int(qty, 1)
        if q <= 0:
            raise ApiError("كمية غير صالحة")
        with db.connect() as conn:
            r = conn.execute("SELECT * FROM repairs WHERE id=?", (rid,)).fetchone()
            if not r:
                raise ApiError("التذكرة غير موجودة")
            if r["status"] in ("delivered", "rejected"):
                raise ApiError("لا يمكن إضافة قطع لتذكرة منتهية")
            p = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
            if not p:
                raise ApiError("القطعة غير موجودة")
            if p["qty"] < q:
                raise ApiError(f"مخزون غير كافٍ للقطعة (المتوفر {p['qty']})")
            unit = p["cost"] if p["cost"] > 0 else p["price"]
            conn.execute("UPDATE products SET qty=qty-? WHERE id=?", (q, pid))
            after = conn.execute("SELECT qty FROM products WHERE id=?", (pid,)).fetchone()[0]
            conn.execute(
                """INSERT INTO stock_movements(created_at, user_id, product_id, qty_change, qty_after, reason, ref)
                   VALUES(?,?,?,?,?,?,?)""",
                (db.now(), self._user()["id"], pid, -q, after, "repair_part", r["ref"]),
            )
            conn.execute(
                """INSERT INTO repair_parts(repair_id, product_id, name, qty, unit_price, line_total)
                   VALUES(?,?,?,?,?,?)""",
                (rid, pid, p["name"], q, unit, unit * q),
            )
            conn.execute("UPDATE repairs SET cost=cost+?, updated_at=? WHERE id=?", (unit * q, db.now(), rid))
            return {"cost": conn.execute("SELECT cost FROM repairs WHERE id=?", (rid,)).fetchone()["cost"]}

    # ---------------------------------------------------------- تقارير
    def _range(self, conn, date=None, month=None):
        if date:
            return "created_at LIKE ?", [f"{date}%"]
        if month:
            y, m = _int(month.get("year")), _int(month.get("month"))
            if not (1 <= m <= 12 and 1900 <= y <= 2999):
                raise ApiError("شهر/سنة غير صالح")
            lo = f"{y:04d}-{m:02d}-01"
            hi = (datetime.date(y, m, 1) + datetime.timedelta(days=32)).replace(day=1).strftime("%Y-%m-%d")
            return "created_at >= ? AND created_at < ?", [lo, hi]
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        return "created_at LIKE ?", [f"{today}%"]

    def _period_stats(self, conn, where, args):
        s = conn.execute(
            f"SELECT COUNT(*) n, COALESCE(SUM(subtotal),0) sub, COALESCE(SUM(discount),0) dis, COALESCE(SUM(tax),0) tax, COALESCE(SUM(total),0) tot FROM sales WHERE {where}",
            args,
        ).fetchone()
        ret = conn.execute(
            f"SELECT COUNT(*) n, COALESCE(SUM(total),0) tot FROM sale_returns WHERE {where}", args
        ).fetchone()
        pays = {r["method"]: r["t"] for r in conn.execute(
            f"""SELECT p.method, COALESCE(SUM(p.amount),0) t FROM payments p
                JOIN sales s ON s.id=p.sale_id WHERE s.{where} GROUP BY p.method""", args,
        ).fetchall()}
        vouchers = conn.execute(
            f"SELECT COUNT(*) n, COALESCE(SUM(amount),0) tot FROM customer_payments WHERE {where}", args
        ).fetchone()
        rp = conn.execute(
            f"""SELECT COUNT(*) n, COALESCE(SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END),0) done,
                       COALESCE(SUM(CASE WHEN status='delivered' THEN cost ELSE 0 END),0) rev
                FROM repairs WHERE {where}""",
            args,
        ).fetchone()
        return {
            "sales": {"count": s["n"], "subtotal": s["sub"], "discount": s["dis"], "tax": s["tax"], "total": s["tot"], "net": max(0, s["tot"] - ret["tot"])},
            "returns": {"count": ret["n"], "total": ret["tot"]},
            "payments": pays,
            "vouchers": {"count": vouchers["n"], "total": vouchers["tot"]},
            "repairs": {"count": rp["n"], "delivered": rp["done"], "revenue": rp["rev"]},
        }

    def report_daily(self, date=None):
        self._perm("reports_view")
        d = date or datetime.datetime.now().strftime("%Y-%m-%d")
        with db.connect() as conn:
            where, args = self._range(conn, date=d)
            return self._period_stats(conn, where, args)

    def report_monthly(self, year, month):
        self._perm("reports_view")
        with db.connect() as conn:
            where, args = self._range(conn, month={"year": year, "month": month})
            return self._period_stats(conn, where, args)

    def report_top(self, date_from=None, date_to=None, limit=10):
        self._perm("reports_view")
        limit = _int(limit, 10)
        where, args = ["1=1"], []
        if date_from:
            where.append("s.created_at >= ?")
            args.append(f"{date_from} 00:00:00")
        if date_to:
            where.append("s.created_at <= ?")
            args.append(f"{date_to} 23:59:59")
        with db.connect() as conn:
            rows = conn.execute(
                f"""SELECT p.name, p.sku,
                           SUM(i.qty - COALESCE((SELECT SUM(ri.qty) FROM sale_return_items ri WHERE ri.sale_item_id=i.id), 0)) qty,
                           SUM(i.line_total - COALESCE((SELECT SUM(ri.amount) FROM sale_return_items ri WHERE ri.sale_item_id=i.id), 0)) total
                    FROM sale_items i JOIN sales s ON s.id=i.sale_id JOIN products p ON p.id=i.product_id
                    WHERE {' AND '.join(where)} GROUP BY p.id HAVING qty > 0 ORDER BY qty DESC LIMIT ?""",
                args + [limit],
            ).fetchall()
            return [dict(r) for r in rows]

    def report_profit(self, date_from=None, date_to=None):
        self._perm("reports_view")
        where, args = ["1=1"], []
        if date_from:
            where.append("s.created_at >= ?")
            args.append(f"{date_from} 00:00:00")
        if date_to:
            where.append("s.created_at <= ?")
            args.append(f"{date_to} 23:59:59")
        with db.connect() as conn:
            goods = conn.execute(
                f"""SELECT COALESCE(SUM(
                        (i.line_total - COALESCE((SELECT SUM(ri.amount) FROM sale_return_items ri WHERE ri.sale_item_id=i.id), 0))
                        - p.cost * (i.qty - COALESCE((SELECT SUM(ri.qty) FROM sale_return_items ri WHERE ri.sale_item_id=i.id), 0))
                    ),0) profit,
                    COALESCE(SUM(
                        i.line_total - COALESCE((SELECT SUM(ri.amount) FROM sale_return_items ri WHERE ri.sale_item_id=i.id), 0)
                    ),0) revenue
                    FROM sale_items i JOIN sales s ON s.id=i.sale_id JOIN products p ON p.id=i.product_id
                    WHERE {' AND '.join(where)}""",
                args,
            ).fetchone()
            rep_where, rep_args = "1=1", []
            if date_from:
                rep_where += " AND r.created_at >= ?"
                rep_args.append(f"{date_from} 00:00:00")
            if date_to:
                rep_where += " AND r.created_at <= ?"
                rep_args.append(f"{date_to} 23:59:59")
            rep = conn.execute(
                f"""SELECT COALESCE(SUM(CASE WHEN r.status='delivered' THEN r.cost ELSE 0 END),0) rev,
                           COALESCE((SELECT SUM(lp.line_total) FROM repair_parts lp
                                     JOIN repairs r2 ON r2.id=lp.repair_id WHERE r2.status='delivered' AND {rep_where.replace('r.', 'r2.')}),0) parts
                    FROM repairs r WHERE {rep_where}""",
                rep_args * 2,
            ).fetchone()
            return {
                "goods_revenue": goods["revenue"],
                "goods_profit": goods["profit"],
                "repair_revenue": rep["rev"],
                "repair_parts_cost": rep["parts"],
                "repair_profit": rep["rev"] - rep["parts"],
            }

    def report_low(self):
        self._user()
        with db.connect() as conn:
            rows = conn.execute(
                """SELECT p.id, p.name, p.sku, p.qty, p.min_qty, c.name category
                   FROM products p LEFT JOIN categories c ON c.id=p.category_id
                   WHERE p.active=1 AND p.qty<=p.min_qty ORDER BY p.qty ASC, p.name"""
            ).fetchall()
            return [dict(r) for r in rows]

    def report_movements(self, limit=100):
        self._perm("reports_view")
        limit = _int(limit, 100)
        with db.connect() as conn:
            rows = conn.execute(
                """SELECT m.*, p.name product_name, u.name user_name
                   FROM stock_movements m
                   JOIN products p ON p.id=m.product_id
                   LEFT JOIN users u ON u.id=m.user_id
                   ORDER BY m.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def stock_stats(self):
        self._user()
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) c FROM products WHERE active=1").fetchone()["c"]
            val = conn.execute("SELECT COALESCE(SUM(qty*price),0) v FROM products WHERE active=1").fetchone()["v"]
            low = conn.execute("SELECT COUNT(*) c FROM products WHERE active=1 AND qty>0 AND qty<=min_qty").fetchone()["c"]
            out = conn.execute("SELECT COUNT(*) c FROM products WHERE active=1 AND qty<=0").fetchone()["c"]
            return {"count": n, "value": val, "low": low, "out": out}
