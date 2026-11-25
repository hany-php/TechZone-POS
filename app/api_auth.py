"""مصادقة المستخدمين، الجلسات، الإعدادات، القوالب، والنسخ الاحتياطي."""
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
from permissions import ALL_PERM_KEYS, PERMISSION_GROUPS
from version import get_app_version
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


class AuthSettingsMixin:
    # ---------------------------------------------------------- جلسة ومستخدمون
    def login_config(self):
        """إعدادات شاشة تسجيل الدخول العامة (اسم المحل والشعار وطريقة الدخول وقائمة أسماء الموظفين دون كشف الدور)."""
        with db.connect() as conn:
            st = self._settings(conn)
            rows = conn.execute("SELECT id, username, name, avatar FROM users WHERE COALESCE(is_active,1)=1 ORDER BY id").fetchall()
            try:
                fail_state = json.loads(st.get("login_fail_state") or "{}")
                if not isinstance(fail_state, dict):
                    fail_state = {}
            except Exception:
                fail_state = {}
            info = fail_state.get("pin_only", {}) if isinstance(fail_state, dict) else {}
            try:
                locked_until = float(info.get("locked_until", 0.0) or 0.0)
            except Exception:
                locked_until = 0.0
            enabled_keys = self._enabled_module_keys(conn)
            def_sp = st.get("default_start_page") or "pos"
            if def_sp != "desktop" and def_sp not in enabled_keys:
                def_sp = self._first_enabled_module(conn)
            return {
                "store_name": (st.get("store_name") or "تك زون للإلكترونيات").strip() or "تك زون للإلكترونيات",
                "store_address": st.get("store_address") or "",
                "store_phone": st.get("store_phone") or "",
                "receipt_logo": st.get("receipt_logo") or "",
                "login_mode": st.get("login_mode") or "pin_only",
                "default_start_page": def_sp,
                "default_start_mode": st.get("default_start_mode") or "window",
                "os_default_theme": st.get("os_default_theme") or "dark",
                "app_version": get_app_version(),
                "login_locked_until": locked_until,
                "users": [{"id": r["id"], "username": r["username"], "name": r["name"], "avatar": r["avatar"]} for r in rows],
            }

    def permissions_schema(self):
        """إرجاع المخطط الرسمي للصلاحيات التفصيلية والقوالب الوظيفية المتاحة."""
        self._user()
        with db.connect() as conn:
            roles_rows = conn.execute(
                "SELECT key, name, description, badge_color, perms_json, is_builtin FROM permission_roles ORDER BY is_builtin DESC, name"
            ).fetchall()
            presets = []
            for r in roles_rows:
                try:
                    pdict = db.parse_user_perms("cashier", r["perms_json"])
                except Exception:
                    pdict = dict(db.DEFAULT_CASHIER_PERMS)
                presets.append({
                    "key": r["key"],
                    "name": r["name"],
                    "description": r["description"],
                    "badge_color": r["badge_color"],
                    "is_builtin": bool(r["is_builtin"]),
                    "perms": pdict,
                })
            return {"groups": PERMISSION_GROUPS, "all_keys": list(ALL_PERM_KEYS), "presets": presets}

    def perm_audit_list(self, limit=80):
        """سجل تغييرات صلاحيات وحالات الموظفين."""
        self._perm_any("staff_view", "staff_manage")
        lim = max(1, min(300, _int(limit, 80)))
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM perm_audit_log ORDER BY id DESC LIMIT ?", (lim,)
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["diff"] = json.loads(d.get("diff_json") or "{}")
                except Exception:
                    d["diff"] = {}
                out.append(d)
            return out

    def users(self):
        self._perm_any("staff_view", "staff_manage")
        with db.connect() as conn:
            rows = conn.execute(
                """SELECT id, username, name, role, permissions, is_active, job_preset,
                          card_size, start_page, start_mode, theme_mode, avatar, created_at
                   FROM users ORDER BY id"""
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["is_active"] = bool(d.get("is_active", 1))
                d["permissions"] = self._load_effective_perms(conn, d["id"], d["role"], d.get("permissions"))
                out.append(d)
            return out

    def _load_effective_perms(self, conn, user_id: int, role: str, raw_json: str | None) -> dict:
        if role == "admin":
            return dict(db.ALL_ADMIN_PERMS)
        up_rows = conn.execute(
            "SELECT perm_key, granted FROM user_permissions WHERE user_id=?", (user_id,)
        ).fetchall()
        if up_rows:
            merged = dict(db.DEFAULT_CASHIER_PERMS)
            for ur in up_rows:
                if ur["perm_key"] in merged:
                    merged[ur["perm_key"]] = bool(ur["granted"])
            return merged
        return db.parse_user_perms(role, raw_json)

    def _row_to_user_dict(self, row, conn=None) -> dict:
        keys = row.keys()
        if conn is not None:
            perms = self._load_effective_perms(conn, row["id"], row["role"], row["permissions"] if "permissions" in keys else None)
        else:
            perms = db.parse_user_perms(row["role"], row["permissions"] if "permissions" in keys else None)
        return {
            "id": row["id"],
            "username": row["username"],
            "name": row["name"],
            "role": row["role"],
            "is_active": bool(row["is_active"]) if "is_active" in keys and row["is_active"] is not None else True,
            "job_preset": row["job_preset"] if "job_preset" in keys else None,
            "permissions": perms,
            "card_size": row["card_size"] if "card_size" in keys else None,
            "wallpaper": row["wallpaper"] if "wallpaper" in keys else None,
            "custom_bg": row["custom_bg"] if "custom_bg" in keys else None,
            "accent_color": row["accent_color"] if "accent_color" in keys else None,
            "desktop_layout": row["desktop_layout"] if "desktop_layout" in keys else None,
            "start_page": row["start_page"] if "start_page" in keys else None,
            "start_mode": row["start_mode"] if "start_mode" in keys else None,
            "theme_mode": row["theme_mode"] if "theme_mode" in keys else None,
            "avatar": row["avatar"] if "avatar" in keys else None,
            "lang": (row["lang"] if "lang" in keys and row["lang"] in ("ar", "en") else "ar"),
        }

    def user_pref_save(
        self,
        card_size=None,
        wallpaper=None,
        custom_bg=None,
        accent_color=None,
        desktop_layout=None,
        start_page=None,
        start_mode=None,
        theme_mode=None,
        lang=None,
        reset_theme=False,
    ):
        """حفظ تفضيلات العرض والفتح الخاصة بالمستخدم الحالي في قاعدة البيانات بشكل دائم لكل مستخدم."""
        u = self._user()
        uid = u["id"]
        valid_modes = {"", "window", "maximized", "direct"}
        valid_themes = {"", "light", "dark"}
        with db.connect() as conn:
            valid_pages = {"", "desktop"} | self._enabled_module_keys(conn)
            if reset_theme:
                conn.execute(
                    "UPDATE users SET wallpaper=NULL, custom_bg=NULL, accent_color=NULL, theme_mode=NULL WHERE id=?",
                    (uid,),
                )
            if card_size not in (None, ""):
                cs = _int(card_size, 0)
                if cs < 110 or cs > 360:
                    raise ApiError("حجم البلوك يجب أن يكون بين 110 و 360")
                conn.execute("UPDATE users SET card_size=? WHERE id=?", (cs, uid))
            if wallpaper is not None:
                wp = str(wallpaper).strip()[:60] or None
                conn.execute("UPDATE users SET wallpaper=? WHERE id=?", (wp, uid))
            if custom_bg is not None:
                bg = str(custom_bg).strip()
                if bg == "":
                    conn.execute("UPDATE users SET custom_bg=NULL WHERE id=?", (uid,))
                else:
                    _validate_image_data_url(bg, 950 * 1024)
                    conn.execute("UPDATE users SET custom_bg=?, wallpaper='custom' WHERE id=?", (bg, uid))
            if accent_color is not None:
                ac = str(accent_color).strip()[:20] or None
                conn.execute("UPDATE users SET accent_color=? WHERE id=?", (ac, uid))
            if desktop_layout is not None:
                if isinstance(desktop_layout, dict):
                    dl = json.dumps(desktop_layout, ensure_ascii=False) if desktop_layout else None
                else:
                    dl = str(desktop_layout).strip() or None
                conn.execute("UPDATE users SET desktop_layout=? WHERE id=?", (dl, uid))
            if start_page is not None:
                sp = str(start_page).strip()
                if sp not in valid_pages:
                    raise ApiError("الصفحة الافتراضية المختارة غير صالحة")
                conn.execute("UPDATE users SET start_page=? WHERE id=?", (sp or None, uid))
            if start_mode is not None:
                sm = str(start_mode).strip()
                if sm not in valid_modes:
                    raise ApiError("وضع فتح الصفحة غير صالح")
                conn.execute("UPDATE users SET start_mode=? WHERE id=?", (sm or None, uid))
            if lang is not None:
                lv = str(lang).strip().lower()
                if lv not in ("ar", "en"):
                    raise ApiError("اللغة غير صالحة (استخدم ar أو en)")
                conn.execute("UPDATE users SET lang=? WHERE id=?", (lv, uid))
            if theme_mode is not None:
                tm = str(theme_mode).strip()
                if tm not in valid_themes:
                    raise ApiError("وضع المظهر غير صالح")
                conn.execute("UPDATE users SET theme_mode=? WHERE id=?", (tm or None, uid))
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if row:
                _STATE["user"] = self._row_to_user_dict(row, conn)
        return {
            "card_size": _STATE["user"].get("card_size"),
            "wallpaper": _STATE["user"].get("wallpaper"),
            "custom_bg": _STATE["user"].get("custom_bg"),
            "accent_color": _STATE["user"].get("accent_color"),
            "desktop_layout": _STATE["user"].get("desktop_layout"),
            "start_page": _STATE["user"].get("start_page"),
            "start_mode": _STATE["user"].get("start_mode"),
            "theme_mode": _STATE["user"].get("theme_mode"),
            "avatar": _STATE["user"].get("avatar"),
        }

    def profile_save(
        self,
        name=None,
        username=None,
        current_pin=None,
        new_pin=None,
        avatar=None,
        start_page=None,
        start_mode=None,
        theme_mode=None,
        card_size=None,
        accent_color=None,
        wallpaper=None,
        custom_bg=None,
        desktop_layout=None,
        lang=None,
        pin=None,
    ):
        """تحديث الملف الشخصي للموظف الحالي (الاسم، معرف الدخول، الصورة الشخصية، كلمة السر/الرمز السري، وإعدادات الفتح والمظهر)."""
        u = self._user()
        uid = u["id"]
        if new_pin is None and pin is not None:
            new_pin = pin
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not row:
                raise ApiError("المستخدم غير موجود")

            final_name = (name if name is not None else row["name"]).strip()
            final_username = (username if username is not None else row["username"]).strip()
            if not final_name or not final_username:
                raise ApiError("الاسم الكامل ومعرف الدخول مطلوبان")

            dup_u = conn.execute("SELECT id FROM users WHERE username=? AND id!=?", (final_username, uid)).fetchone()
            if dup_u:
                raise ApiError("معرف الدخول مسجل لموظف آخر مسبقاً")

            if new_pin is not None and str(new_pin).strip() != "":
                np = str(new_pin).strip()
                if len(np) < 4 or len(np) > 24:
                    raise ApiError("كلمة المرور / الرمز السري الجديد يجب أن يتكون من 4 خانات على الأقل")
                if current_pin is not None and str(current_pin).strip() != "":
                    cp = str(current_pin).strip()
                    if not hmac.compare_digest(db.hash_pin(cp, row["pin_salt"]), row["pin_hash"]):
                        raise ApiError("الرمز السري الحالي غير صحيح")
                for other in conn.execute("SELECT id, pin_salt, pin_hash FROM users WHERE id!=?", (uid,)).fetchall():
                    if hmac.compare_digest(db.hash_pin(np, other["pin_salt"]), other["pin_hash"]):
                        raise ApiError("الرمز السري الجديد مستخدم بالفعل لموظف آخر — يرجى اختيار رمز فريد")
                salt = os.urandom(16)
                conn.execute(
                    "UPDATE users SET pin_salt=?, pin_hash=? WHERE id=?",
                    (salt, db.hash_pin(np, salt), uid),
                )

            if avatar is not None:
                av = str(avatar).strip()
                if av == "":
                    conn.execute("UPDATE users SET avatar=NULL WHERE id=?", (uid,))
                else:
                    _validate_image_data_url(av, 450 * 1024)
                    conn.execute("UPDATE users SET avatar=? WHERE id=?", (av, uid))

            conn.execute(
                "UPDATE users SET name=?, username=? WHERE id=?",
                (final_name, final_username, uid),
            )
            conn.commit()

        if any(x is not None for x in (start_page, start_mode, theme_mode, card_size, accent_color, wallpaper, custom_bg, desktop_layout)):
            self.user_pref_save(
                card_size=card_size,
                wallpaper=wallpaper,
                custom_bg=custom_bg,
                accent_color=accent_color,
                desktop_layout=desktop_layout,
                start_page=start_page,
                start_mode=start_mode,
                theme_mode=theme_mode,
            )

        with db.connect() as conn:
            st = self._settings(conn)
            updated = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            _STATE["user"] = self._row_to_user_dict(updated, conn)
            eff_sp = _STATE["user"].get("start_page") or st.get("default_start_page") or "pos"
            enabled_keys = self._enabled_module_keys(conn)
            if eff_sp != "desktop" and eff_sp not in enabled_keys:
                eff_sp = self._first_enabled_module(conn)
            _STATE["user"]["effective_start_page"] = eff_sp
            _STATE["user"]["effective_start_mode"] = _STATE["user"].get("start_mode") or st.get("default_start_mode") or "window"
            _STATE["user"]["force_change_pin"] = bool(
                updated["role"] == "admin" and hmac.compare_digest(db.hash_pin("1234", updated["pin_salt"]), updated["pin_hash"])
            )
        return dict(_STATE["user"])

    def user_save(self, username, name, role="cashier", pin=None, permissions=None, id=None, start_page=None, start_mode=None, avatar=None, job_preset=None, is_active=None):
        actor = self._perm("staff_manage")
        username = (username or "").strip()
        name = (name or "").strip()
        if not username or not name:
            raise ApiError("اسم الدخول والاسم الكامل مطلوبان")
        if role not in ("admin", "cashier"):
            raise ApiError("دور المستخدم غير صالح")
        if pin is not None and str(pin).strip() != "":
            pin = str(pin).strip()
            if len(pin) < 4 or len(pin) > 24:
                raise ApiError("الرمز السري / كلمة المرور يجب أن يتكون من 4 خانات على الأقل")
        else:
            pin = None

        valid_modes = {"", "window", "maximized", "direct"}
        sp_raw = str(start_page).strip() if start_page is not None else None
        sm_val = str(start_mode).strip() if start_mode is not None else None
        if sm_val is not None and sm_val not in valid_modes:
            sm_val = None

        perms_dict = dict(db.ALL_ADMIN_PERMS) if role == "admin" else dict(db.DEFAULT_CASHIER_PERMS)
        if role != "admin" and isinstance(permissions, dict):
            for k in perms_dict:
                if k in permissions:
                    perms_dict[k] = bool(permissions[k])
        perms_json = json.dumps(perms_dict, ensure_ascii=False)
        preset_val = "admin" if role == "admin" else ((str(job_preset).strip()[:60] or None) if job_preset is not None else None)

        with db.connect() as conn:
            valid_pages = {"", "desktop"} | self._enabled_module_keys(conn)
            sp_val = sp_raw if (sp_raw is not None and sp_raw in valid_pages) else None
            # التأكد من عدم تكرار الرمز السري بين المستخدمين لتمييز كل مستخدم تلقائياً من الرمز السري فقط
            if pin:
                target_uid = _int(id) if id else 0
                for other in conn.execute("SELECT id, name, pin_salt, pin_hash FROM users").fetchall():
                    if other["id"] == target_uid:
                        continue
                    if hmac.compare_digest(db.hash_pin(pin, other["pin_salt"]), other["pin_hash"]):
                        raise ApiError("الرمز السري مستخدم بالفعل لموظف آخر — يجب أن يكون لكل مستخدم رمز سري فريد")
            try:
                if id:
                    uid = _int(id)
                    cur_u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                    if not cur_u:
                        raise ApiError("المستخدم غير موجود")
                    old_perms = self._load_effective_perms(conn, uid, cur_u["role"], cur_u["permissions"])
                    final_active = cur_u["is_active"] if is_active is None else (1 if is_active else 0)
                    if uid == actor["id"] and final_active == 0:
                        raise ApiError("لا يمكنك تعطيل حسابك الحالي أثناء الجلسة")
                    if cur_u["role"] == "admin" and (role != "admin" or final_active == 0):
                        active_admins = conn.execute(
                            "SELECT COUNT(*) c FROM users WHERE role='admin' AND is_active=1 AND id!=?", (uid,)
                        ).fetchone()["c"]
                        if active_admins < 1:
                            raise ApiError("لا يمكن إزالة صلاحية المدير أو تعطيل آخر مدير نشط في النظام")
                    final_sp = (sp_val or None) if start_page is not None else cur_u["start_page"]
                    final_sm = (sm_val or None) if start_mode is not None else cur_u["start_mode"]
                    final_av = (str(avatar).strip() or None) if avatar is not None else cur_u["avatar"]
                    final_preset = preset_val if (role == "admin" or job_preset is not None) else cur_u["job_preset"]
                    if final_av:
                        _validate_image_data_url(final_av, 450 * 1024)
                    if pin:
                        salt = os.urandom(16)
                        conn.execute(
                            """UPDATE users SET username=?, name=?, role=?, pin_salt=?, pin_hash=?, permissions=?,
                                      is_active=?, job_preset=?, start_page=?, start_mode=?, avatar=? WHERE id=?""",
                            (username, name, role, salt, db.hash_pin(pin, salt), perms_json, final_active, final_preset, final_sp, final_sm, final_av, uid),
                        )
                    else:
                        conn.execute(
                            """UPDATE users SET username=?, name=?, role=?, permissions=?,
                                      is_active=?, job_preset=?, start_page=?, start_mode=?, avatar=? WHERE id=?""",
                            (username, name, role, perms_json, final_active, final_preset, final_sp, final_sm, final_av, uid),
                        )
                    db.sync_user_permissions_table(conn, uid, role, perms_dict)
                    added = sorted(k for k in ALL_PERM_KEYS if perms_dict.get(k) and not old_perms.get(k))
                    removed = sorted(k for k in ALL_PERM_KEYS if old_perms.get(k) and not perms_dict.get(k))
                    conn.execute(
                        """INSERT INTO perm_audit_log(ts, actor_id, actor_name, target_user_id, target_username, action, diff_json)
                           VALUES(?,?,?,?,?,?,?)""",
                        (
                            db.now(),
                            actor["id"],
                            actor["name"],
                            uid,
                            username,
                            "user_perm_update",
                            json.dumps({
                                "role_from": cur_u["role"],
                                "role_to": role,
                                "is_active": bool(final_active),
                                "preset": final_preset,
                                "added": added,
                                "removed": removed,
                                "pin_changed": bool(pin),
                            }, ensure_ascii=False),
                        ),
                    )
                    if _STATE["user"] and _STATE["user"]["id"] == uid:
                        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                        if row:
                            _STATE["user"] = self._row_to_user_dict(row, conn)
                    return {"id": uid}
                else:
                    if not pin:
                        raise ApiError("الرمز السري (4 أرقام) مطلوب للمستخدم الجديد")
                    final_active = 1 if (is_active is None or is_active) else 0
                    salt = os.urandom(16)
                    cur = conn.execute(
                        """INSERT INTO users(username, name, role, pin_salt, pin_hash, permissions, is_active, job_preset, start_page, start_mode, avatar, created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (username, name, role, salt, db.hash_pin(pin, salt), perms_json, final_active, preset_val or ("admin" if role == "admin" else "cashier_strict"), sp_val or None, sm_val or None, (str(avatar).strip() or None) if avatar else None, db.now()),
                    )
                    new_uid = cur.lastrowid
                    db.sync_user_permissions_table(conn, new_uid, role, perms_dict)
                    conn.execute(
                        """INSERT INTO perm_audit_log(ts, actor_id, actor_name, target_user_id, target_username, action, diff_json)
                           VALUES(?,?,?,?,?,?,?)""",
                        (
                            db.now(),
                            actor["id"],
                            actor["name"],
                            new_uid,
                            username,
                            "user_create",
                            json.dumps({
                                "role": role,
                                "is_active": bool(final_active),
                                "preset": preset_val,
                                "granted": sorted(k for k, v in perms_dict.items() if v),
                            }, ensure_ascii=False),
                        ),
                    )
                    return {"id": new_uid}
            except sqlite3.IntegrityError:
                raise ApiError("اسم الدخول مسجل مسبقاً")

    def user_toggle_active(self, id, is_active=True):
        """تفعيل أو تعطيل حساب موظف بدون حذف سجلاته التاريخية."""
        actor = self._perm("staff_manage")
        uid = _int(id)
        active_val = 1 if is_active else 0
        if uid == actor["id"] and active_val == 0:
            raise ApiError("لا يمكنك تعطيل حسابك الحالي أثناء الجلسة")
        with db.connect() as conn:
            target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not target:
                raise ApiError("المستخدم غير موجود")
            if target["role"] == "admin" and active_val == 0:
                admins = conn.execute("SELECT COUNT(*) c FROM users WHERE role='admin' AND is_active=1 AND id!=?", (uid,)).fetchone()["c"]
                if admins < 1:
                    raise ApiError("لا يمكن تعطيل المدير النشط الوحيد في النظام")
            conn.execute("UPDATE users SET is_active=? WHERE id=?", (active_val, uid))
            conn.execute(
                """INSERT INTO perm_audit_log(ts, actor_id, actor_name, target_user_id, target_username, action, diff_json)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    db.now(),
                    actor["id"],
                    actor["name"],
                    uid,
                    target["username"],
                    "user_toggle_active",
                    json.dumps({"is_active": bool(active_val)}, ensure_ascii=False),
                ),
            )
            return {"id": uid, "is_active": bool(active_val)}

    def user_delete(self, id):
        u = self._perm("staff_manage")
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
                conn.execute("UPDATE sales SET modified_by=NULL WHERE modified_by=?", (uid,))
                conn.execute("DELETE FROM users WHERE id=?", (uid,))
                conn.execute(
                    """INSERT INTO perm_audit_log(ts, actor_id, actor_name, target_user_id, target_username, action, diff_json)
                       VALUES(?,?,?,?,?,?,?)""",
                    (db.now(), u["id"], u["name"], uid, target["username"], "user_delete", json.dumps({"role": target["role"]}, ensure_ascii=False)),
                )
            except sqlite3.IntegrityError:
                raise ApiError("لا يمكن حذف مستخدم مرتبط بعمليات بيع أو صيانة سابقة (يمكنك تعطيل حسابه بدلاً من الحذف)")
            return True

    def login(self, username=None, pin=None):
        """تسجيل الدخول: يدعم الدخول بالرمز السري فقط (يكتشف المستخدم ودوره مدير/كاشير تلقائياً) أو باسم المستخدم والرمز السري."""
        pin = str(pin or "").strip()
        username = str(username or "").strip()
        if len(pin) < 4:
            raise ApiError("اسم المستخدم أو الرمز السري غير صحيح")
        lock_key = username.lower() if username else "pin_only"
        now_ts = time.time()

        with db.connect() as conn:
            st = self._settings(conn)
            max_attempts = max(1, _int(st.get("login_max_attempts", 5), 5))
            lock_minutes = max(1, _int(st.get("login_lockout_minutes", 10), 10))
            try:
                fail_state = json.loads(st.get("login_fail_state") or "{}")
                if not isinstance(fail_state, dict):
                    fail_state = {}
            except Exception:
                fail_state = {}
            info = fail_state.get(lock_key, {"count": 0, "locked_until": 0.0})
            try:
                info["locked_until"] = float(info.get("locked_until", 0.0) or 0.0)
            except Exception:
                info["locked_until"] = 0.0
            info["count"] = int(info.get("count", 0) or 0)

            if info["locked_until"] > now_ts:
                remain = int(info["locked_until"] - now_ts)
                mins = max(1, (remain + 59) // 60)
                raise ApiError(f"تم تجاوز عدد المحاولات المسموح. حاول بعد {mins} دقيقة [LOCKED:{remain}]")

            if info["locked_until"] and info["locked_until"] <= now_ts:
                info = {"count": 0, "locked_until": 0.0}
                fail_state[lock_key] = info

            try:
                if username:
                    row = conn.execute("SELECT * FROM users WHERE username=? OR name=?", (username, username)).fetchone()
                    if not row:
                        raise ApiError("اسم المستخدم أو الرمز السري غير صحيح")
                    expect = db.hash_pin(pin, row["pin_salt"])
                    if not hmac.compare_digest(expect, row["pin_hash"]):
                        raise ApiError("اسم المستخدم أو الرمز السري غير صحيح")
                else:
                    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
                    matched = None
                    for r in rows:
                        expect = db.hash_pin(pin, r["pin_salt"])
                        if hmac.compare_digest(expect, r["pin_hash"]):
                            matched = r
                            break
                    if not matched:
                        raise ApiError("الرمز السري غير صحيح")
                    row = matched
            except ApiError:
                info["count"] = info.get("count", 0) + 1
                if info["count"] >= max_attempts:
                    info["locked_until"] = now_ts + (lock_minutes * 60)
                    info["count"] = 0
                fail_state[lock_key] = info
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("login_fail_state", json.dumps(fail_state)),
                )
                self._settings_cache = None
                conn.commit()
                if info.get("locked_until", 0) > now_ts:
                    mins = max(1, (int(info["locked_until"] - now_ts) + 59) // 60)
                    raise ApiError(f"تم تجاوز عدد المحاولات المسموح. حاول بعد {mins} دقيقة [LOCKED:{int(info['locked_until'] - now_ts)}]")
                raise

            # فحص حالة الحساب قبل إتمام الجلسة
            if "is_active" in row.keys() and row["is_active"] == 0:
                raise ApiError("تم إيقاف هذا الحساب من قبل المدير — يرجى مراجعة الإدارة")
            # نجاح: إعادة تعيين
            fail_state[lock_key] = {"count": 0, "locked_until": 0.0}
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("login_fail_state", json.dumps(fail_state)),
            )
            # إلغاء أي إقفال سابق
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("login_locked_until", "0"),
            )
            self._settings_cache = None
            _STATE["user"] = self._row_to_user_dict(row, conn)
            out = dict(_STATE["user"])
            eff_sp = out.get("start_page") or st.get("default_start_page") or "pos"
            enabled_keys = self._enabled_module_keys(conn)
            if eff_sp != "desktop" and eff_sp not in enabled_keys:
                eff_sp = self._first_enabled_module(conn)
            out["effective_start_page"] = eff_sp
            out["effective_start_mode"] = out.get("start_mode") or st.get("default_start_mode") or "window"
            # فحص أمني: هل الحساب الإداري ما زال يستخدم الرمز السري الافتراضي 1234؟
            if row["role"] == "admin" and hmac.compare_digest(db.hash_pin("1234", row["pin_salt"]), row["pin_hash"]):
                out["force_change_pin"] = True
                out["default_pin_warning"] = "تنبيه أمني: الحساب الإداري يستخدم الرمز الافتراضي (1234). يرجى تعيين رمز جديد لحماية متجرك."
            else:
                out["force_change_pin"] = False
            return out

    def session(self):
        if _STATE["user"]:
            with db.connect() as conn:
                st = self._settings(conn)
                row = conn.execute("SELECT * FROM users WHERE id=?", (_STATE["user"]["id"],)).fetchone()
                if not row or ("is_active" in row.keys() and row["is_active"] == 0):
                    _STATE["user"] = None
                    return {"user": None}
                _STATE["user"] = self._row_to_user_dict(row, conn)
                eff_sp = _STATE["user"].get("start_page") or st.get("default_start_page") or "pos"
                enabled_keys = self._enabled_module_keys(conn)
                if eff_sp != "desktop" and eff_sp not in enabled_keys:
                    eff_sp = self._first_enabled_module(conn)
                _STATE["user"]["effective_start_page"] = eff_sp
                _STATE["user"]["effective_start_mode"] = _STATE["user"].get("start_mode") or st.get("default_start_mode") or "window"
                _STATE["user"]["force_change_pin"] = bool(row["role"] == "admin" and hmac.compare_digest(db.hash_pin("1234", row["pin_salt"]), row["pin_hash"]))
        return {"user": _STATE["user"]}

    def verify_lock_pin(self, pin=""):
        """التحقق من رمز الـ PIN لفك قفل الشاشة التلقائي للمستخدم الحالي دون إنهاء الجلسة أو إغلاق النوافذ."""
        u = self._user()
        pin = str(pin or "").strip()
        if not pin:
            raise ApiError("يرجى إدخال الرمز السري لفك القفل")
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
            if not row or ("is_active" in row.keys() and row["is_active"] == 0):
                _STATE["user"] = None
                raise ApiError("الحساب غير متاح حالياً")
            expected = db.hash_pin(pin, row["pin_salt"])
            if not hmac.compare_digest(expected, row["pin_hash"]):
                self._log_activity(conn, "screen_unlock_failed", "session", u["id"], f"محاولة فك قفل شاشة فاشلة للمستخدم {u['name']}", {}, module_key="core")
                raise ApiError("الرمز السري غير صحيح")
            self._log_activity(conn, "screen_unlock", "session", u["id"], f"فك قفل الشاشة للمستخدم {u['name']}", {}, module_key="core")
            return {"unlocked": True, "user_id": u["id"], "name": u["name"]}

    def activity_audit_list(self, action=None, entity_type=None, user_id=None, date_from=None, date_to=None, q=None, limit=200):
        """استعراض سجل رقابة العمليات اليومية الشامل (Audit Log) مع الفلترة حسب العملية أو القسم أو الموظف أو التاريخ."""
        self._perm_any("settings_view_edit", "staff_manage", "reports_sales_view")
        lim = min(1000, max(1, _int(limit, 200)))
        where, args = ["1=1"], []
        if action and str(action).strip():
            where.append("action=?")
            args.append(str(action).strip())
        if entity_type and str(entity_type).strip():
            where.append("entity_type=?")
            args.append(str(entity_type).strip())
        if user_id not in (None, "", 0, "0"):
            where.append("user_id=?")
            args.append(_int(user_id))
        if date_from and str(date_from).strip():
            where.append("substr(created_at, 1, 10) >= ?")
            args.append(str(date_from).strip()[:10])
        if date_to and str(date_to).strip():
            where.append("substr(created_at, 1, 10) <= ?")
            args.append(str(date_to).strip()[:10])
        if q and str(q).strip():
            qs = f"%{str(q).strip()}%"
            where.append("(summary LIKE ? OR COALESCE(entity_id,'') LIKE ? OR COALESCE(user_name,'') LIKE ? OR COALESCE(details,'') LIKE ?)")
            args.extend([qs, qs, qs, qs])
        where_sql = " AND ".join(where)
        with db.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) c FROM activity_audit_log WHERE {where_sql}", args).fetchone()["c"]
            rows = conn.execute(
                f"SELECT * FROM activity_audit_log WHERE {where_sql} ORDER BY id DESC LIMIT ?",
                args + [lim],
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["details_parsed"] = json.loads(d.get("details") or "{}")
                except Exception:
                    d["details_parsed"] = {}
                out.append(d)
            by_type = [
                dict(r)
                for r in conn.execute(
                    "SELECT entity_type, COUNT(*) count FROM activity_audit_log GROUP BY entity_type ORDER BY count DESC"
                ).fetchall()
            ]
            return {"rows": out, "total": total, "by_type": by_type}

    # ---------------------------------------------------------- إدارة الترجمة (عربي / إنجليزي)
    def _scan_web_translations(self, conn) -> dict:
        """مسح ملفات web/*.html و web/i18n.js واستخراج كافة النصوص العربية وتحديث جدول translations دون الكتابة فوق تعديلات المستخدم."""
        import re
        web_dir = pathlib.Path(__file__).resolve().parent.parent / "web"
        if not web_dir.exists():
            return {"inserted": 0, "total": 0}
        ar_re = re.compile(r"[\u0600-\u06FF]")

        # 1) قراءة القاموس الافتراضي من web/i18n.js (EXACT_MAP)
        default_map = {}
        i18n_file = web_dir / "i18n.js"
        if i18n_file.exists():
            itxt = i18n_file.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"['\"]([^'\"]*[\u0600-\u06FF][^'\"]*)['\"]\s*:\s*['\"]([^'\"]*)['\"]", itxt):
                ar_k = " ".join(m.group(1).split()).strip()
                en_v = m.group(2).strip()
                if ar_k:
                    default_map[ar_k] = en_v

        section_map = {
            "index.html": "login",
            "desktop.html": "desktop",
            "pos.html": "pos",
            "inventory.html": "inventory",
            "customers.html": "customers",
            "customer_details.html": "customers",
            "installments.html": "installments",
            "purchases.html": "purchases",
            "accounting.html": "accounting",
            "reports.html": "reports",
            "settings.html": "settings",
            "profile.html": "profile",
            "staff.html": "staff",
            "repair.html": "repair",
            "buy_used.html": "buy_used",
            "history.html": "history",
            "sales_quotes.html": "sales_quotes",
            "receipt.html": "receipt",
            "owner.html": "owner",
        }

        discovered = {}  # ar_text -> (en_text, section)
        for ar_k, en_v in default_map.items():
            discovered[ar_k] = (en_v, "general")

        for p in sorted(web_dir.glob("*.html")):
            sec = section_map.get(p.name, "general")
            txt = p.read_text(encoding="utf-8", errors="ignore")
            # strip <script> and <style> blocks to capture clean UI text
            clean_html = re.sub(r"<script[\s\S]*?</script>", " ", txt, flags=re.I)
            clean_html = re.sub(r"<style[\s\S]*?</style>", " ", clean_html, flags=re.I)
            for m in re.finditer(r">([^<>{}`$]{2,110})<", clean_html):
                s = " ".join(m.group(1).split()).strip()
                if s and ar_re.search(s):
                    en_v = default_map.get(s, "")
                    if s not in discovered or (not discovered[s][0] and en_v) or discovered[s][1] == "general":
                        discovered[s] = (en_v or (discovered[s][0] if s in discovered else ""), sec)
            for m in re.finditer(r'(?:placeholder|title)="([^"]{2,110})"', clean_html):
                s = " ".join(m.group(1).split()).strip()
                if s and ar_re.search(s):
                    en_v = default_map.get(s, "")
                    if s not in discovered or (not discovered[s][0] and en_v) or discovered[s][1] == "general":
                        discovered[s] = (en_v or (discovered[s][0] if s in discovered else ""), sec)

        now_ts = db.now()
        inserted = 0
        for ar_k, (en_v, sec) in discovered.items():
            ex = conn.execute("SELECT id, en_text, section FROM translations WHERE ar_text=?", (ar_k,)).fetchone()
            if not ex:
                conn.execute(
                    "INSERT INTO translations(ar_text, en_text, section, updated_at) VALUES(?,?,?,?)",
                    (ar_k, en_v, sec, now_ts),
                )
                inserted += 1
            elif not (ex["en_text"] or "").strip() and en_v:
                conn.execute("UPDATE translations SET en_text=?, updated_at=? WHERE id=?", (en_v, now_ts, ex["id"]))
        total = conn.execute("SELECT COUNT(*) c FROM translations").fetchone()["c"]
        return {"inserted": inserted, "total": total}

    def translations_map(self):
        """إرجاع قاموس الترجمات المخصصة (عربي -> إنجليزي) لاستخدامه في كافة الصفحات بما فيها شاشة الدخول."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT ar_text, en_text FROM translations WHERE TRIM(en_text) != ''"
            ).fetchall()
            return {r["ar_text"]: r["en_text"] for r in rows}

    def translations_list(self, q="", section="", untranslated_only=False, limit=500):
        """عرض جدول الكلمات والترجمات في قسم إدارة الترجمة مع البحث والفلترة."""
        self._perm_any("settings_view_edit", "templates_manage")
        lim = min(2000, max(1, _int(limit, 500)))
        with db.connect() as conn:
            cnt = conn.execute("SELECT COUNT(*) c FROM translations").fetchone()["c"]
            if cnt == 0:
                self._scan_web_translations(conn)
            where, args = ["1=1"], []
            if q and str(q).strip():
                qs = f"%{str(q).strip()}%"
                where.append("(ar_text LIKE ? OR en_text LIKE ?)")
                args.extend([qs, qs])
            if section and str(section).strip():
                where.append("section=?")
                args.append(str(section).strip())
            if untranslated_only:
                where.append("TRIM(COALESCE(en_text,'')) = ''")
            w_sql = " AND ".join(where)
            total = conn.execute(f"SELECT COUNT(*) c FROM translations WHERE {w_sql}", args).fetchone()["c"]
            translated_cnt = conn.execute("SELECT COUNT(*) c FROM translations WHERE TRIM(COALESCE(en_text,'')) != ''").fetchone()["c"]
            all_cnt = conn.execute("SELECT COUNT(*) c FROM translations").fetchone()["c"]
            rows = conn.execute(
                f"SELECT id, ar_text, en_text, section, updated_at FROM translations WHERE {w_sql} ORDER BY CASE WHEN TRIM(COALESCE(en_text,''))='' THEN 0 ELSE 1 END, section, id DESC LIMIT ?",
                args + [lim],
            ).fetchall()
            sections = [
                dict(r)
                for r in conn.execute(
                    "SELECT section, COUNT(*) count FROM translations GROUP BY section ORDER BY count DESC"
                ).fetchall()
            ]
            return {
                "rows": [dict(r) for r in rows],
                "total": total,
                "all_total": all_cnt,
                "translated_total": translated_cnt,
                "untranslated_total": max(0, all_cnt - translated_cnt),
                "sections": sections,
            }

    def translations_scan_project(self):
        """فحص واستخراج كافة الكلمات العربية من صفحات المشروع وإضافتها لجدول الترجمة دون المساس بالترجمات المحفوظة."""
        self._perm_any("settings_view_edit", "templates_manage")
        with db.connect() as conn:
            res = self._scan_web_translations(conn)
            self._log_activity(conn, "translations_scan", "translations", None, f"فحص كلمات المشروع للترجمة (جديد: {res['inserted']}، الإجمالي: {res['total']})", res, module_key="settings")
            return res

    def translations_save(self, items=None, ar_text=None, en_text=None, section="general"):
        """حفظ ترجمة مفردة أو دفعة ترجمات في قاعدة البيانات وتطبيقها فوراً."""
        self._perm_any("settings_view_edit", "templates_manage")
        batch = []
        if isinstance(items, list) and items:
            for it in items:
                if not isinstance(it, dict):
                    continue
                ar = " ".join(str(it.get("ar_text") or "").split()).strip()
                en = str(it.get("en_text") or "").strip()
                sec = str(it.get("section") or "general").strip() or "general"
                if ar:
                    batch.append((ar, en, sec))
        elif ar_text is not None:
            ar = " ".join(str(ar_text or "").split()).strip()
            en = str(en_text or "").strip()
            sec = str(section or "general").strip() or "general"
            if not ar:
                raise ApiError("النص العربي مطلوب")
            batch.append((ar, en, sec))
        if not batch:
            raise ApiError("لا توجد ترجمات للحفظ")
        now_ts = db.now()
        with db.connect() as conn:
            for ar, en, sec in batch:
                conn.execute(
                    """INSERT INTO translations(ar_text, en_text, section, updated_at)
                       VALUES(?,?,?,?)
                       ON CONFLICT(ar_text) DO UPDATE SET en_text=excluded.en_text, section=excluded.section, updated_at=excluded.updated_at""",
                    (ar, en, sec, now_ts),
                )
            self._log_activity(conn, "translations_save", "translations", None, f"حفظ وتحديث {len(batch)} ترجمة في قاموس النظام", {"count": len(batch)}, module_key="settings")
        return {"saved": len(batch)}

    def translations_delete(self, id):
        """حذف صف ترجمة من جدول الترجمة."""
        self._perm_any("settings_view_edit", "templates_manage")
        tid = _int(id)
        with db.connect() as conn:
            cur = conn.execute("DELETE FROM translations WHERE id=?", (tid,))
            if not cur.rowcount:
                raise ApiError("الترجمة غير موجودة")
            return True

    def logout(self):
        _STATE["user"] = None
        _STATE["owner"] = None
        return True

    # ---------------------------------------------------------- إعدادات
    def settings(self):
        """قراءة إعدادات التشغيل للمستخدم الحالي (مع حجب بيانات الأمان الداخلية لغير المخولين)."""
        self._user()
        with db.connect() as conn:
            st = dict(self._settings(conn))
            if not self._has_perm("settings_view_edit"):
                for priv in ("login_fail_state", "login_max_attempts", "login_lockout_minutes", "customer_ledger_migrated", "migration_v2_strict_perms"):
                    st.pop(priv, None)
            return st

    def settings_save(self, **kv):
        self._perm("settings_view_edit")
        allowed = {"store_name", "store_address", "store_phone", "currency", "tax_enabled", "tax_rate",
                   "pos_card_size", "os_default_wallpaper", "os_default_custom_bg", "os_default_accent", "os_default_layout",
                   "os_default_theme", "login_mode", "default_start_page", "default_start_mode",
                    "store_email", "store_cr", "store_vat", "receipt_thanks", "receipt_footer",
                    "receipt_logo", "receipt_show_logo", "receipt_show_barcode",
                    "receipt_show_tax", "receipt_show_payments", "whatsapp_send_enabled",
                    "pos_print_preview", "print_show_dialog", "print_printer_name", "close_exit_app", "auto_update_check", "app_default_lang",
                    "idle_lock_minutes", "pos_sound_enabled", "pos_low_stock_alert", "customer_default_credit_limit", "enforce_credit_limit",
                    "login_max_attempts", "login_lockout_minutes",
                    "template_a4_config", "template_pos_config", "pos_categories_config"}
        show = {"tax_enabled", "receipt_show_logo", "receipt_show_barcode", "receipt_show_tax", "receipt_show_payments", "whatsapp_send_enabled", "pos_print_preview", "print_show_dialog", "close_exit_app", "auto_update_check", "pos_sound_enabled", "pos_low_stock_alert", "enforce_credit_limit"}
        valid_login_modes = {"pin_only", "select_user_pin", "username_password"}
        valid_start_modes = {"window", "maximized", "direct"}
        with db.connect() as conn:
            valid_start_pages = {"desktop"} | self._enabled_module_keys(conn)
            for k, v in kv.items():
                if k not in allowed or v is None:
                    continue
                s = str(v)
                if s == "" and k not in show and k not in ("os_default_custom_bg", "os_default_layout", "receipt_logo", "pos_categories_config", "print_printer_name"):
                    continue
                if k in show:
                    if s not in ("0", "1"):
                        raise ApiError("قيمة عرض غير صالحة (استخدم 0 أو 1)")
                elif k == "login_mode":
                    if s not in valid_login_modes:
                        raise ApiError("طريقة تسجيل الدخول غير صالحة")
                elif k == "default_start_page":
                    if s not in valid_start_pages:
                        raise ApiError("الصفحة الافتراضية غير صالحة")
                elif k == "default_start_mode":
                    if s not in valid_start_modes:
                        raise ApiError("وضع فتح الصفحة الافتراضية غير صالح")
                elif k == "app_default_lang":
                    if s not in ("ar", "en"):
                        raise ApiError("اللغة الافتراضية غير صالحة (ar أو en)")
                elif k == "os_default_theme":
                    if s not in ("light", "dark"):
                        raise ApiError("وضع المظهر الافتراضي غير صالح")
                elif k == "login_max_attempts":
                    n = _int(s, 5)
                    if n < 1 or n > 20:
                        raise ApiError("عدد المحاولات يجب أن يكون بين 1 و 20")
                    s = str(n)
                elif k == "login_lockout_minutes":
                    n = _int(s, 10)
                    if n < 1 or n > 1440:
                        raise ApiError("مدة الإقفال يجب أن تكون بين 1 و 1440 دقيقة")
                    s = str(n)
                elif k == "idle_lock_minutes":
                    n = _int(s, 0)
                    if n < 0 or n > 240:
                        raise ApiError("مدة قفل الشاشة التلقائي يجب أن تكون بين 0 و 240 دقيقة")
                    s = str(n)
                elif k == "customer_default_credit_limit":
                    try:
                        d_lim = Decimal(str(s).strip() or "0")
                    except Exception:
                        raise ApiError("حد الائتمان الافتراضي غير صالح")
                    if d_lim < 0:
                        raise ApiError("حد الائتمان الافتراضي لا يمكن أن يكون سالباً")
                    s = str(d_lim.quantize(Decimal("0.01")) if d_lim % 1 else int(d_lim))
                elif k == "pos_card_size":
                    cs = _int(s, 200)
                    if cs < 110 or cs > 360:
                        raise ApiError("حجم البلوك الافتراضي يجب أن يكون بين 110 و 360")
                    s = str(cs)
                elif k == "receipt_logo" and s != "":
                    _validate_image_data_url(s, 200 * 1024)
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, s),
                )
            self._log_activity(conn, "settings_save", "settings", None, "تحديث إعدادات المتجر والنظام", {"keys": [k for k in kv.keys() if k in allowed]}, module_key="settings")
            self._settings_cache = None
            return self._settings(conn)

    def db_optimize_images(self):
        """ترحيل أي صور Base64 متبقية إلى ملفات WebP في data/images/products/ وضغط قاعدة البيانات (VACUUM)."""
        self._perm("backups_manage")
        db_file = pathlib.Path(db.db_path())
        size_before = db_file.stat().st_size if db_file.exists() else 0
        with db.connect() as conn:
            migrated = db._migrate_base64_images_to_disk(conn)
            self._log_activity(conn, "db_optimize_images", "settings", None, f"ترحيل {migrated} صورة إلى القرص وضغط قاعدة البيانات (VACUUM)", {"migrated": migrated}, module_key="settings")
        try:
            conn_v = db.connect()
            try:
                conn_v.isolation_level = None
                conn_v.execute("VACUUM")
            finally:
                conn_v.close()
        except Exception:
            pass
        size_after = db_file.stat().st_size if db_file.exists() else 0
        return {
            "migrated_count": migrated,
            "size_before": size_before,
            "size_after": size_after,
            "saved_bytes": max(0, size_before - size_after),
        }

    def db_backup(self, reason="manual"):
        """إنشاء نسخة احتياطية فورية لقاعدة البيانات (للمخولين فقط)."""
        self._perm("backups_manage")
        path = db.backup_database(str(reason or "manual"))
        if not path:
            raise ApiError("فشل إنشاء النسخة الاحتياطية لقاعدة البيانات")
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        }

    def backups_list(self):
        """استعراض النسخ الاحتياطية المتوفرة (للمخولين فقط)."""
        self._perm("backups_manage")
        return db.list_backups()

    def db_restore(self, backup_name):
        """استرجاع قاعدة البيانات من نسخة احتياطية محددة مع أخذ نسخة أمان مسبقة."""
        self._perm("backups_manage")
        if not backup_name:
            raise ApiError("اسم ملف النسخة الاحتياطية مطلوب")
        try:
            res = db.restore_database(str(backup_name))
            self._settings_cache = None
            return res
        except ValueError as ve:
            raise ApiError(str(ve))
        except Exception as e:
            raise ApiError(f"تعذر استرجاع النسخة الاحتياطية: {e}")

    def _load_payment_methods(self, conn):
        cache = getattr(self, "_pm_cache", None)
        if cache is not None:
            return cache
        st = self._settings(conn)
        result = list(db.DEFAULT_PAYMENT_METHODS)
        if st.get("custom_payment_methods"):
            try:
                loaded = json.loads(st["custom_payment_methods"])
                if isinstance(loaded, list) and loaded:
                    result = loaded
            except Exception:
                pass
        self._pm_cache = result
        return result

    def payment_methods_get(self):
        """جلب قائمة طرق وأنظمة الدفع المخصصة."""
        self._user()
        with db.connect() as conn:
            return self._load_payment_methods(conn)

    def payment_methods_save(self, methods=None):
        """حفظ قائمة طرق وأنظمة الدفع المخصصة (نقدي، محافظ، خطط دفعات مقدمة وأقساط)."""
        self._perm("settings_view_edit")
        cleaned = []
        for idx, m in enumerate(methods or []):
            if isinstance(m, str):
                nm = m.strip()
                if nm:
                    cleaned.append({"id": f"pm_{idx+1}", "name": nm, "base_type": "cash"})
            elif isinstance(m, dict):
                nm = str(m.get("name") or "").strip()
                if nm:
                    bt = "wallet" if m.get("base_type") == "wallet" else "cash"
                    mid = str(m.get("id") or f"pm_{idx+1}").strip()
                    cleaned.append({"id": mid, "name": nm, "base_type": bt})
        if not cleaned:
            cleaned = list(db.DEFAULT_PAYMENT_METHODS)
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('custom_payment_methods', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(cleaned, ensure_ascii=False),),
            )
            self._settings_cache = None
            self._pm_cache = None
            return cleaned

    def _load_templates(self, conn):
        cache = getattr(self, "_tpl_cache", None)
        st = self._settings(conn)
        if cache is None:
            a4 = dict(db.DEFAULT_A4_TEMPLATE)
            pos = dict(db.DEFAULT_POS_TEMPLATE)
            if st.get("template_a4_config"):
                try:
                    loaded_a4 = json.loads(st["template_a4_config"])
                    if isinstance(loaded_a4, dict):
                        a4.update(loaded_a4)
                except Exception:
                    pass
            if st.get("template_pos_config"):
                try:
                    loaded_pos = json.loads(st["template_pos_config"])
                    if isinstance(loaded_pos, dict):
                        pos.update(loaded_pos)
                except Exception:
                    pass
            cache = {"a4": a4, "pos": pos}
            self._tpl_cache = cache
        else:
            a4 = dict(cache["a4"])
            pos = dict(cache["pos"])
        next_sale_seq = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM sales").fetchone()[0]
        next_quote_seq = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM quotations").fetchone()[0]
        inv_pref = a4.get("invoice_prefix") or "الفات/2026/"
        q_pref = a4.get("quote_prefix") or "ع.س/2026/"
        return {
            "a4": a4,
            "pos": pos,
            "payment_methods": self._load_payment_methods(conn),
            "next_invoice_no": _format_doc_seq(inv_pref, next_sale_seq),
            "next_quote_no": _format_doc_seq(q_pref, next_quote_seq),
            "next_sale_seq": next_sale_seq,
            "next_quote_seq": next_quote_seq,
        }

    def templates_get(self):
        """جلب إعدادات قوالب الفواتير (قالب A4 للمبيعات وعروض الأسعار + قالب إيصال الكاشير الحراري 80mm/58mm)."""
        self._user()
        with db.connect() as conn:
            return self._load_templates(conn)

    def templates_save(self, a4=None, pos=None, reset_a4=False, reset_pos=False, sync_receipt_settings=True):
        """حفظ تخصيص قوالب الفواتير (شكل الفاتورة A4، الألوان، الشعار، البيانات، وقالب الكاشير الحراري وجميع إيصالات البرنامج)."""
        self._perm("templates_manage")
        with db.connect() as conn:
            cur = self._load_templates(conn)
            new_a4 = dict(db.DEFAULT_A4_TEMPLATE) if reset_a4 else cur["a4"]
            new_pos = dict(db.DEFAULT_POS_TEMPLATE) if reset_pos else cur["pos"]
            if isinstance(a4, dict) and not reset_a4:
                logo = a4.get("company_logo")
                if logo is not None and logo != "":
                    logo_s = str(logo).strip()
                    _validate_image_data_url(logo_s, 500 * 1024)
                for k in db.DEFAULT_A4_TEMPLATE:
                    if k in a4:
                        new_a4[k] = a4[k]
            if isinstance(pos, dict) and not reset_pos:
                for k in db.DEFAULT_POS_TEMPLATE:
                    if k in pos:
                        new_pos[k] = pos[k]
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('template_a4_config', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(new_a4, ensure_ascii=False),),
            )
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('template_pos_config', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(new_pos, ensure_ascii=False),),
            )
            if sync_receipt_settings and isinstance(pos, dict) and not reset_pos:
                sync_pairs = [
                    ("receipt_thanks", str(new_pos.get("thanks_text") or "شكراً لزيارتكم")),
                    ("receipt_footer", str(new_pos.get("footer_text") or "يرجى الاحتفاظ بالإيصال للاستبدال خلال 14 يوماً")),
                    ("receipt_show_logo", "1" if new_pos.get("show_logo", True) else "0"),
                    ("receipt_show_barcode", "1" if new_pos.get("show_barcode", True) else "0"),
                    ("receipt_show_tax", "1" if new_pos.get("show_tax", True) else "0"),
                    ("receipt_show_payments", "1" if new_pos.get("show_payments", True) else "0"),
                ]
                for sk, sv in sync_pairs:
                    conn.execute(
                        "INSERT INTO settings(key, value) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (sk, sv),
                    )
            self._tpl_cache = None
            self._settings_cache = None
            return self._load_templates(conn)

    # ---------------------------------------------------------- الطباعة المباشرة والطابعات
    def printers_list(self):
        """جلب قائمة الطابعات المثبتة على نظام ويندوز والطابعة الافتراضية."""
        self._user()
        printers = []
        default_printer = ""
        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes as wt

                class _PRINTER_INFO_4W(ctypes.Structure):
                    _fields_ = [
                        ("pPrinterName", wt.LPWSTR),
                        ("pServerName", wt.LPWSTR),
                        ("Attributes", wt.DWORD),
                    ]

                ws = ctypes.WinDLL("winspool.drv", use_last_error=True)
                needed = wt.DWORD(0)
                returned = wt.DWORD(0)
                flags = 2 | 4  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
                ws.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(needed), ctypes.byref(returned))
                if needed.value > 0:
                    buf = ctypes.create_string_buffer(needed.value)
                    if ws.EnumPrintersW(flags, None, 4, buf, needed.value, ctypes.byref(needed), ctypes.byref(returned)):
                        arr = (_PRINTER_INFO_4W * returned.value).from_buffer(buf)
                        for i in range(returned.value):
                            name = arr[i].pPrinterName
                            if name and name not in printers:
                                printers.append(name)
                sz = wt.DWORD(512)
                dbuf = ctypes.create_unicode_buffer(512)
                if ws.GetDefaultPrinterW(dbuf, ctypes.byref(sz)):
                    default_printer = dbuf.value or ""
            except Exception:
                pass
        return {"printers": printers, "default_printer": default_printer}

    def silent_print(self, mode="thermal", printer_name=""):
        """طباعة الصفحة الحالية مباشرة عبر WebView2 PrintAsync دون فتح نافذة إعدادات الطابعة في ويندوز."""
        self._user()
        chosen_printer = str(printer_name or "").strip()
        if not chosen_printer:
            with db.connect() as conn:
                chosen_printer = (self._settings(conn).get("print_printer_name") or "").strip()
        try:
            import webview
        except Exception:
            return {"ok": False, "fallback": "dialog", "reason": "no_webview"}

        wins = getattr(webview, "windows", None) or []
        if not wins:
            return {"ok": False, "fallback": "dialog", "reason": "no_window"}
        if sys.platform != "win32":
            return {"ok": False, "fallback": "dialog", "reason": "unsupported_os"}

        try:
            import threading
            from System import Action, Func, Object
            from System.Threading.Tasks import Task
            from Microsoft.Web.WebView2.Core import CoreWebView2PrintStatus
            from webview.platforms.winforms import BrowserView

            win = wins[0]
            form = BrowserView.instances.get(win.uid)
            if not form or not getattr(form, "browser", None) or not getattr(form.browser, "webview", None):
                return {"ok": False, "fallback": "dialog", "reason": "no_browser"}

            browser = form.browser
            wv = browser.webview
            done = threading.Event()
            outcome = {"ok": False, "status": "OtherError", "error": "تعذر بدء الطباعة المباشرة"}

            def _on_print_done(task):
                try:
                    if task.IsFaulted or task.IsCanceled:
                        ex = getattr(task, "Exception", None)
                        outcome["ok"] = False
                        outcome["status"] = "OtherError"
                        outcome["error"] = str(ex) if ex else "تعذر إتمام الطباعة"
                    else:
                        st = task.Result
                        outcome["status"] = str(st)
                        if st == CoreWebView2PrintStatus.Succeeded:
                            outcome["ok"] = True
                            outcome.pop("error", None)
                        elif st == CoreWebView2PrintStatus.PrinterUnavailable:
                            outcome["ok"] = False
                            outcome["error"] = "الطابعة غير متصلة أو غير متوفرة حالياً — تأكد من تشغيل الطابعة أو فعّل نافذة اختيار الطابعة من الإعدادات"
                        else:
                            outcome["ok"] = False
                            outcome["error"] = "تعذر إرسال أمر الطباعة المباشرة للطابعة"
                except Exception as exc:
                    outcome["ok"] = False
                    outcome["error"] = str(exc)
                finally:
                    done.set()

            def _start_print():
                try:
                    cwv2 = wv.CoreWebView2
                    if not cwv2:
                        outcome["fallback"] = "dialog"
                        done.set()
                        return None
                    ps = cwv2.Environment.CreatePrintSettings()
                    ps.ShouldPrintBackgrounds = True
                    ps.ShouldPrintHeaderAndFooter = False
                    ps.MarginTop = 0.0
                    ps.MarginBottom = 0.0
                    ps.MarginLeft = 0.0
                    ps.MarginRight = 0.0
                    if chosen_printer:
                        ps.PrinterName = chosen_printer
                    task = cwv2.PrintAsync(ps)
                    task.ContinueWith(
                        Action[Task[CoreWebView2PrintStatus]](_on_print_done),
                        browser.syncContextTaskScheduler,
                    )
                except Exception as exc:
                    outcome["ok"] = False
                    outcome["error"] = f"تعذر تشغيل الطباعة المباشرة: {exc}"
                    done.set()
                return None

            wv.Invoke(Func[Object](_start_print))
            if not done.wait(30.0):
                return {"ok": False, "status": "Timeout", "error": "انتهت مهلة انتظار الطابعة"}
            return outcome
        except Exception as exc:
            return {"ok": False, "fallback": "dialog", "reason": str(exc)}

