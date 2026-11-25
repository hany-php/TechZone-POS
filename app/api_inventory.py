"""إدارة التصنيفات والمنتجات والأرقام التسلسلية والمخزون."""
import datetime
import hmac
import json
import os
import pathlib
import sqlite3
import sys
import time
from decimal import Decimal, ROUND_HALF_UP

import db
import erp_hooks
from api_common import (
    ApiError,
    _FALLBACK_JPEG,
    _LOGIN_ATTEMPTS,
    _STATE,
    _customer_debt_summary,
    _customers_enriched_cte,
    _fmt_money,
    _format_doc_seq,
    _int,
    _jpeg_to_pdf_bytes,
    _money,
    _upsert_customer,
    _validate_image_data_url,
    _win32_auto_paste_into_whatsapp,
    _win32_copy_pdf_to_clipboard,
    _find_whatsapp_hwnd,
)


class InventoryMixin:
    # ---------------------------------------------------------- فئات
    def categories(self):
        self._perm_any("pos_sell", "inventory_view", "inventory_edit", "quotes_view", "quotes_create_edit", "repair_edit")
        with db.connect() as conn:
            hide_empty = self._settings(conn).get("hide_empty_categories") == "1"
            having = "HAVING COUNT(p.id) > 0" if hide_empty else ""
            rows = conn.execute(
                f"""SELECT c.id, c.name, COUNT(p.id) n FROM categories c
                   LEFT JOIN products p ON p.category_id=c.id AND p.active=1
                   WHERE c.demo_profile IS NULL
                      OR EXISTS (SELECT 1 FROM products p2 WHERE p2.category_id=c.id AND p2.active=1)
                   GROUP BY c.id {having} ORDER BY c.name"""
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
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('hide_empty_categories', '0') "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
            )
            self._settings_cache = None
            return {"id": cur.lastrowid}

    def categories_delete(self, id):
        self._perm("inventory_edit")
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) c FROM products WHERE category_id=? AND active=1", (id,)).fetchone()["c"]
            if n:
                raise ApiError("لا يمكن حذف فئة عليها منتجات")
            conn.execute("DELETE FROM categories WHERE id=?", (id,))
            return True

    def categories_bulk_delete(self, ids=None, detach_products=False):
        """حذف مجموعة محددة من الفئات/التصنيفات دفعة واحدة (مع خيار فك ارتباط المنتجات تلقائياً)."""
        self._perm("inventory_edit")
        if not isinstance(ids, list) or not ids:
            raise ApiError("يرجى تحديد فئة واحدة على الأقل للحذف")
        clean_ids = sorted({_int(x) for x in ids if _int(x) > 0})
        if not clean_ids:
            raise ApiError("معرّفات الفئات المحددة غير صالحة")
        detach = bool(detach_products)
        placeholders = ",".join("?" for _ in clean_ids)
        with db.connect() as conn:
            rows = conn.execute(
                f"""SELECT c.id, c.name, COUNT(p.id) active_products
                    FROM categories c
                    LEFT JOIN products p ON p.category_id=c.id AND p.active=1
                    WHERE c.id IN ({placeholders})
                    GROUP BY c.id""",
                clean_ids,
            ).fetchall()
            if not rows:
                raise ApiError("لم يتم العثور على الفئات المحددة")

            to_delete = []
            skipped = []
            for r in rows:
                if r["active_products"] > 0 and not detach:
                    skipped.append({"id": r["id"], "name": r["name"], "products_count": r["active_products"]})
                else:
                    to_delete.append({"id": r["id"], "name": r["name"], "products_count": r["active_products"]})

            detached_products = 0
            deleted_ids = [d["id"] for d in to_delete]
            if deleted_ids:
                del_ph = ",".join("?" for _ in deleted_ids)
                if detach:
                    cur_u = conn.execute(
                        f"UPDATE products SET category_id=NULL WHERE category_id IN ({del_ph}) AND active=1",
                        deleted_ids,
                    )
                    detached_products = cur_u.rowcount
                conn.execute(f"DELETE FROM categories WHERE id IN ({del_ph})", deleted_ids)
                sample_names = [d["name"] for d in to_delete[:10]]
                self._log_activity(
                    conn,
                    "categories_bulk_delete",
                    "categories",
                    None,
                    f"حذف جماعي لعدد {len(deleted_ids)} فئة" + (f" (مع فك ارتباط {detached_products} منتج)" if detached_products else ""),
                    {"deleted_count": len(deleted_ids), "skipped_count": len(skipped), "detached_products": detached_products, "sample_names": sample_names},
                    module_key="inventory",
                )

            return {
                "deleted": len(deleted_ids),
                "skipped": skipped,
                "detached_products": detached_products,
                "requested": len(clean_ids),
            }

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

    def pos_categories_config_save(self, config=None):
        """حفظ ترتيب وتخصيص الفئات المعروضة في شاشة نقاط البيع (POS)."""
        self._perm("pos_categories_manage")
        if config is None:
            config = ""
        if isinstance(config, (list, dict)):
            s = json.dumps(config, ensure_ascii=False)
        else:
            s = str(config).strip()
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('pos_categories_config', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (s,),
            )
            self._settings_cache = None
            return {"pos_categories_config": s}

    # ---------------------------------------------------------- منتجات
    def _product_row(self, r, show_cost):
        d = dict(r)
        if not show_cost:
            d["cost"] = None
        qty, minq = d["qty"], d["min_qty"]
        d["stock_state"] = "out" if qty <= 0 else ("low" if qty <= minq else "in")
        return d

    def products(self, q=None, category_id=None, stock=None, limit=200, offset=0):
        self._perm("inventory_view")
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
        elif stock == "available":
            where.append("p.qty>0")
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
        self._perm("inventory_view")
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
                     min_qty=5, tracked=0, notes=None, serials=None, image=None):
        self._perm("inventory_edit")
        name = (name or "").strip()
        sku = (sku or "").strip()
        if not name or not sku:
            raise ApiError("اسم المنتج والباركود/SKU مطلوبان")
        if image is not None and image != "":
            image = str(image).strip()
            _validate_image_data_url(image, 600 * 1024)
        serials = [s.strip() for s in (serials or []) if s and s.strip()]
        with db.connect() as conn:
            try:
                if id:
                    pid = _int(id)
                    existing = conn.execute("SELECT name, sku, price, cost, image FROM products WHERE id=?", (pid,)).fetchone()
                    if not existing:
                        raise ApiError("المنتج غير موجود")
                    if image is None:
                        final_img = existing["image"]
                    elif image == "":
                        final_img = None
                    elif image.startswith("data:image/"):
                        final_img = db.save_image_to_disk(image, "products", f"prod_{pid}")
                    else:
                        final_img = image
                    new_p = _money(price)
                    new_c = _money(cost)
                    conn.execute(
                        """UPDATE products SET sku=?, name=?, category_id=?, price=?, cost=?, min_qty=?, tracked=?, image=?, notes=?
                           WHERE id=?""",
                        (sku, name, _int(category_id) or None, new_p, new_c,
                         _int(min_qty, 5), _int(tracked), final_img, notes, pid),
                    )
                    act_name = "product_price_change" if existing["price"] != new_p else "product_update"
                    self._log_activity(
                        conn, act_name, "products", pid,
                        f"تعديل منتج «{name}» ({sku})" + (f" — تغير السعر من {_fmt_money(existing['price'])} إلى {_fmt_money(new_p)}" if existing["price"] != new_p else ""),
                        {"old_price": existing["price"], "new_price": new_p, "old_cost": existing["cost"], "new_cost": new_c, "sku": sku},
                        module_key="inventory",
                    )
                else:
                    cur = conn.execute(
                        """INSERT INTO products(sku, name, category_id, price, cost, min_qty, tracked, image, notes, created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (sku, name, _int(category_id) or None, _money(price), _money(cost),
                         _int(min_qty, 5), _int(tracked), None, notes, db.now()),
                    )
                    pid = cur.lastrowid
                    if image:
                        final_img = db.save_image_to_disk(image, "products", f"prod_{pid}") if image.startswith("data:image/") else image
                        conn.execute("UPDATE products SET image=? WHERE id=?", (final_img, pid))
                    self._log_activity(
                        conn, "product_create", "products", pid,
                        f"إضافة منتج جديد «{name}» ({sku}) بسعر {_fmt_money(_money(price))}",
                        {"sku": sku, "price": _money(price), "cost": _money(cost)},
                        module_key="inventory",
                    )
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
        pid = _int(id)
        with db.connect() as conn:
            p = conn.execute("SELECT name, sku FROM products WHERE id=?", (pid,)).fetchone()
            cur = conn.execute("UPDATE products SET active=0 WHERE id=?", (pid,))
            if not cur.rowcount:
                raise ApiError("المنتج غير موجود")
            self._log_activity(
                conn, "product_delete", "products", pid,
                f"حذف/إيقاف منتج «{p['name'] if p else pid}» ({p['sku'] if p else ''})",
                {"product_id": pid},
                module_key="inventory",
            )
            return True

    def products_bulk_delete(self, ids=None):
        """حذف/إيقاف مجموعة محددة من المنتجات دفعة واحدة مع الحفاظ الكامل على سجل الفواتير السابقة."""
        self._perm("inventory_edit")
        if not isinstance(ids, list) or not ids:
            raise ApiError("يرجى تحديد منتج واحد على الأقل للحذف")
        clean_ids = sorted({_int(x) for x in ids if _int(x) > 0})
        if not clean_ids:
            raise ApiError("معرّفات المنتجات المحددة غير صالحة")
        placeholders = ",".join("?" for _ in clean_ids)
        with db.connect() as conn:
            targets = conn.execute(
                f"SELECT id, name, sku FROM products WHERE id IN ({placeholders}) AND active=1",
                clean_ids,
            ).fetchall()
            if not targets:
                raise ApiError("لم يتم العثور على منتجات نشطة ضمن التحديد")
            target_ids = [r["id"] for r in targets]
            t_ph = ",".join("?" for _ in target_ids)
            cur = conn.execute(f"UPDATE products SET active=0 WHERE id IN ({t_ph})", target_ids)
            sample = [f"{r['name']} ({r['sku']})" for r in targets[:10]]
            self._log_activity(
                conn,
                "products_bulk_delete",
                "products",
                None,
                f"حذف جماعي لعدد {cur.rowcount} منتج من المخزون",
                {"deleted_count": cur.rowcount, "sample_products": sample},
                module_key="inventory",
            )
            return {"deleted": cur.rowcount, "requested": len(clean_ids)}

    def products_search(self, q=None, limit=60, category_id=None):
        self._perm_any("pos_sell", "inventory_view", "quotes_view", "quotes_create_edit", "repair_edit", "purchases_view", "purchases_create_post")
        q = (q or "").strip()
        limit = _int(limit, 60)
        cat = _int(category_id) if category_id not in (None, "") else None
        cat_sql = " AND p.category_id=?" if cat else ""
        cat_args = [cat] if cat else []
        with db.connect() as conn:
            if not q:
                rows = conn.execute(
                    """SELECT p.id, p.name, p.sku, p.price, p.qty, p.tracked, p.min_qty, p.image, c.name category
                       FROM products p LEFT JOIN categories c ON c.id=p.category_id
                       WHERE p.active=1""" + cat_sql + """ ORDER BY p.name LIMIT ?""", (*cat_args, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT DISTINCT p.id, p.name, p.sku, p.price, p.qty, p.tracked, p.min_qty, p.image, c.name category
                       FROM products p LEFT JOIN categories c ON c.id=p.category_id
                       WHERE p.active=1""" + cat_sql + """ AND (p.name LIKE ? OR p.sku LIKE ? OR EXISTS(
                           SELECT 1 FROM serials s WHERE s.product_id=p.id AND s.serial LIKE ? AND s.status='in_stock'))
                       ORDER BY p.name LIMIT ?""",
                    (*cat_args, f"%{q}%", f"%{q}%", f"%{q}%", limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def product_adjust(self, id, qty_change, reason="تعديل يدوي"):
        u = self._perm("inventory_adjust")
        pid, delta = _int(id), _int(qty_change)
        if delta == 0:
            raise ApiError("تغيير الكمية صفري")
        with db.connect() as conn:
            p = conn.execute("SELECT qty, cost FROM products WHERE id=? AND active=1", (pid,)).fetchone()
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
            erp_hooks.on_stock_adjusted(self, conn, pid, delta, int(p["cost"] or 0), reason or "تعديل يدوي", user=u)
            self._log_activity(
                conn, "stock_adjust", "products", pid,
                f"تعديل رصيد مخزون المنتج #{pid} بمقدار ({delta:+d}) ليصبح {newq} — {reason or 'تعديل يدوي'}",
                {"product_id": pid, "qty_change": delta, "qty_after": newq, "reason": reason or "تعديل يدوي"},
                module_key="inventory",
            )
            return {"qty": newq}

    def serials(self, product_id):
        self._perm_any("serials_view", "inventory_view", "pos_sell")
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM serials WHERE product_id=? ORDER BY id DESC", (_int(product_id),)
            ).fetchall()
            return [dict(r) for r in rows]

    def serial_add(self, product_id, serial):
        self._perm("inventory_adjust")
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

