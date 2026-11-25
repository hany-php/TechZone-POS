"""وضع المالك الرئيسي (Owner Mode): المصادقة، مفتاح الاسترداد، تصفير رمز المدير، وسجل التدقيق."""
import hmac
import json
import os
import re
import secrets
import time

import db
import fresh_db as fresh_db_mod
from api_common import ApiError, OWNER_SESSION_TTL, _STATE, _int, _money
from modules_map import MODULE_REQUIRES
from profiles import BUSINESS_PROFILES, DEFAULT_BUSINESS_PROFILES, DEFAULT_LABELS, DEFAULT_RETAIL_CATS, DEFAULT_RETAIL_SKUS, LABEL_KEYS

OWNER_LOCK_MAX_ATTEMPTS = 5
OWNER_LOCK_SECONDS = 15 * 60
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_WEAK_PINS = {"1234", "0000", "1111"}
_ICON_RE = re.compile(r"^[a-z0-9_]{1,40}$")
_COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|linear-gradient\([#0-9a-zA-Z,.%() -]{1,120}\))$")
_PARAMS_RE = re.compile(r"^[A-Za-z0-9_=&.-]{0,120}$")
_PROFILE_KEY_RE = re.compile(r"^[a-z0-9_]{2,40}$")


def _validate_module_fields(title, icon, color, params="", perm_keys=None):
    t = str(title or "").strip()
    if not t or len(t) > 60:
        raise ApiError("اسم القسم مطلوب (بحد أقصى 60 حرفاً)")
    ic = str(icon or "").strip()
    if not _ICON_RE.match(ic):
        raise ApiError("اسم الأيقونة غير صالح (أحرف إنجليزية صغيرة وأرقام و _ فقط)")
    col = str(color or "").strip()
    if not _COLOR_RE.match(col):
        raise ApiError("صيغة اللون أو التدرج غير صالحة")
    par = str(params or "").strip().lstrip("?")
    if not _PARAMS_RE.match(par):
        raise ApiError("معاملات الرابط غير صالحة (أحرف وأرقام و = & _ - . فقط)")
    if perm_keys is None:
        perms = None
    else:
        if not isinstance(perm_keys, list):
            raise ApiError("صيغة الصلاحيات غير صالحة")
        valid_perms = set(db.DEFAULT_CASHIER_PERMS.keys())
        perms = [str(k) for k in perm_keys if str(k) in valid_perms]
    return t, ic, col, par, perms


def _generate_recovery_key() -> str:
    """توليد مفتاح استرداد عشوائي بطول 20 محرفاً مقسماً إلى 4 مجموعات."""
    chars = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(20))
    return "-".join(chars[i : i + 5] for i in range(0, 20, 5))


def _normalize_recovery_key(raw: str) -> str:
    return "".join(ch for ch in str(raw or "").upper() if ch.isalnum())


def _validate_passphrase(raw: str) -> str:
    p = str(raw or "").strip()
    if len(p) < 8:
        raise ApiError("عبارة مرور المالك يجب أن تتكون من 8 أحرف على الأقل")
    if len(p) > 128:
        raise ApiError("عبارة مرور المالك طويلة جداً (الحد الأقصى 128 حرفاً)")
    return p


class OwnerMixin:
    """دوال وضع المالك الرئيسي وإدارة أمان الهيكلة."""

    def _owner_row(self, conn):
        return conn.execute("SELECT * FROM owner_auth WHERE id=1").fetchone()

    def _parse_fail_state(self, raw: str | None) -> dict:
        try:
            st = json.loads(raw or "{}")
            if isinstance(st, dict):
                return {
                    "count": int(st.get("count", 0) or 0),
                    "locked_until": float(st.get("locked_until", 0.0) or 0.0),
                }
        except Exception:
            pass
        return {"count": 0, "locked_until": 0.0}

    def _check_owner_lock(self, conn, row, now_ts: float) -> dict:
        info = self._parse_fail_state(row["fail_state"])
        if info["locked_until"] > now_ts:
            remain = int(info["locked_until"] - now_ts)
            mins = max(1, (remain + 59) // 60)
            raise ApiError(f"تم تجاوز عدد محاولات المالك المسموحة. حاول بعد {mins} دقيقة [LOCKED:{remain}]")
        if info["locked_until"] and info["locked_until"] <= now_ts:
            info = {"count": 0, "locked_until": 0.0}
            conn.execute("UPDATE owner_auth SET fail_state=? WHERE id=1", (json.dumps(info),))
            conn.commit()
        return info

    def _record_owner_fail(self, conn, info: dict, now_ts: float) -> None:
        info["count"] = int(info.get("count", 0)) + 1
        if info["count"] >= OWNER_LOCK_MAX_ATTEMPTS:
            info["locked_until"] = now_ts + OWNER_LOCK_SECONDS
            info["count"] = 0
        conn.execute("UPDATE owner_auth SET fail_state=? WHERE id=1", (json.dumps(info),))
        conn.commit()
        if info.get("locked_until", 0.0) > now_ts:
            remain = int(info["locked_until"] - now_ts)
            mins = max(1, (remain + 59) // 60)
            raise ApiError(f"تم تجاوز عدد محاولات المالك المسموحة. حاول بعد {mins} دقيقة [LOCKED:{remain}]")

    def _clear_owner_fail(self, conn) -> None:
        conn.execute("UPDATE owner_auth SET fail_state=? WHERE id=1", ('{"count":0,"locked_until":0}',))

    def owner_status(self):
        """حالة إعداد ونشاط وضع المالك الرئيسي."""
        with db.connect() as conn:
            row = self._owner_row(conn)
            configured = bool(row)
            locked_until = 0.0
            if row:
                info = self._parse_fail_state(row["fail_state"])
                if info["locked_until"] > time.time():
                    locked_until = info["locked_until"]
        active = self._owner_is_active()
        seconds_left = 0
        if active and _STATE.get("owner"):
            seconds_left = max(0, int(_STATE["owner"]["until"] - time.time()))
        return {
            "configured": configured,
            "active": active,
            "seconds_left": seconds_left,
            "locked_until": locked_until,
        }

    def owner_setup(self, passphrase):
        """إعداد عبارة مرور المالك لأول مرة (متاح للمدير فقط قبل التكوين) ويعيد مفتاح الاسترداد لمرة واحدة."""
        self._admin()
        p = _validate_passphrase(passphrase)
        with db.connect() as conn:
            if self._owner_row(conn):
                raise ApiError("تم إعداد وضع المالك مسبقاً")
            raw_recovery = _generate_recovery_key()
            norm_recovery = _normalize_recovery_key(raw_recovery)
            pass_salt = os.urandom(16)
            rec_salt = os.urandom(16)
            ts = db.now()
            conn.execute(
                """INSERT INTO owner_auth
                   (id, pass_hash, pass_salt, recovery_hash, recovery_salt, fail_state, created_at, updated_at)
                   VALUES(1, ?, ?, ?, ?, '{"count":0,"locked_until":0}', ?, ?)""",
                (
                    db.hash_secret(p, pass_salt),
                    pass_salt,
                    db.hash_secret(norm_recovery, rec_salt),
                    rec_salt,
                    ts,
                    ts,
                ),
            )
            self._audit(conn, "owner_setup", "owner_auth")
            conn.commit()
        _STATE["owner"] = {"until": time.time() + OWNER_SESSION_TTL, "backed_up": False}
        return {
            "configured": True,
            "active": True,
            "seconds_left": OWNER_SESSION_TTL,
            "recovery_key": raw_recovery,
        }

    def owner_login(self, passphrase):
        """بدء جلسة المالك الرئيسي باستخدام عبارة المرور."""
        p = str(passphrase or "").strip()
        if not p:
            raise ApiError("يرجى إدخال عبارة مرور المالك")
        now_ts = time.time()
        with db.connect() as conn:
            row = self._owner_row(conn)
            if not row:
                raise ApiError("لم يتم إعداد وضع المالك بعد")
            info = self._check_owner_lock(conn, row, now_ts)
            if not hmac.compare_digest(db.hash_secret(p, row["pass_salt"]), row["pass_hash"]):
                self._record_owner_fail(conn, info, now_ts)
                raise ApiError("عبارة مرور المالك غير صحيحة")
            self._clear_owner_fail(conn)
            self._audit(conn, "owner_login", "owner_auth")
            conn.commit()
        _STATE["owner"] = {"until": now_ts + OWNER_SESSION_TTL, "backed_up": False}
        return self.owner_status()

    def owner_logout(self):
        """إنهاء جلسة المالك الرئيسي فوراً."""
        _STATE["owner"] = None
        return True

    def owner_change_passphrase(self, old_passphrase, new_passphrase):
        """تغيير عبارة مرور المالك بعد التحقق من العبارة الحالية."""
        self._owner()
        old_p = str(old_passphrase or "").strip()
        new_p = _validate_passphrase(new_passphrase)
        with db.connect() as conn:
            row = self._owner_row(conn)
            if not row:
                raise ApiError("لم يتم إعداد وضع المالك بعد")
            if not hmac.compare_digest(db.hash_secret(old_p, row["pass_salt"]), row["pass_hash"]):
                raise ApiError("عبارة المرور الحالية غير صحيحة")
            new_salt = os.urandom(16)
            conn.execute(
                "UPDATE owner_auth SET pass_hash=?, pass_salt=?, updated_at=? WHERE id=1",
                (db.hash_secret(new_p, new_salt), new_salt, db.now()),
            )
            self._audit(conn, "owner_change_passphrase", "owner_auth")
            conn.commit()
        return True

    def owner_recover(self, recovery_key, new_passphrase):
        """استعادة وتعيين عبارة مرور جديدة عبر مفتاح الاسترداد مع تدوير المفتاح وإصدار مفتاح جديد لمرة واحدة."""
        norm_key = _normalize_recovery_key(recovery_key)
        if not norm_key:
            raise ApiError("يرجى إدخال مفتاح الاسترداد")
        new_p = _validate_passphrase(new_passphrase)
        now_ts = time.time()
        with db.connect() as conn:
            row = self._owner_row(conn)
            if not row:
                raise ApiError("لم يتم إعداد وضع المالك بعد")
            info = self._check_owner_lock(conn, row, now_ts)
            if not hmac.compare_digest(db.hash_secret(norm_key, row["recovery_salt"]), row["recovery_hash"]):
                self._record_owner_fail(conn, info, now_ts)
                raise ApiError("مفتاح الاسترداد غير صحيح")
            new_recovery = _generate_recovery_key()
            new_norm_rec = _normalize_recovery_key(new_recovery)
            pass_salt = os.urandom(16)
            rec_salt = os.urandom(16)
            conn.execute(
                """UPDATE owner_auth
                   SET pass_hash=?, pass_salt=?, recovery_hash=?, recovery_salt=?, fail_state='{"count":0,"locked_until":0}', updated_at=?
                   WHERE id=1""",
                (
                    db.hash_secret(new_p, pass_salt),
                    pass_salt,
                    db.hash_secret(new_norm_rec, rec_salt),
                    rec_salt,
                    db.now(),
                ),
            )
            self._audit(conn, "owner_recover", "owner_auth")
            conn.commit()
        _STATE["owner"] = {"until": now_ts + OWNER_SESSION_TTL, "backed_up": False}
        return {"ok": True, "recovery_key": new_recovery}

    def owner_reset_admin_pin(self, secret, new_pin, user_id=None):
        """إعادة تعيين رمز المدير باستخدام عبارة مرور المالك أو مفتاح الاسترداد."""
        raw_secret = str(secret or "").strip()
        if not raw_secret:
            raise ApiError("يرجى إدخال عبارة مرور المالك أو مفتاح الاسترداد")
        np = str(new_pin or "").strip()
        if len(np) < 4 or len(np) > 24:
            raise ApiError("الرمز السري الجديد يجب أن يتكون من 4 خانات على الأقل (حتى 24 خانة)")
        if np in _WEAK_PINS:
            raise ApiError("يرجى اختيار رمز سري قوي غير بسيط أو افتراضي")

        now_ts = time.time()
        with db.connect() as conn:
            row = self._owner_row(conn)
            if not row:
                raise ApiError("لم يتم إعداد وضع المالك بعد")
            info = self._check_owner_lock(conn, row, now_ts)
            norm_secret = _normalize_recovery_key(raw_secret)
            match_pass = hmac.compare_digest(db.hash_secret(raw_secret, row["pass_salt"]), row["pass_hash"])
            match_rec = bool(norm_secret) and hmac.compare_digest(
                db.hash_secret(norm_secret, row["recovery_salt"]), row["recovery_hash"]
            )
            if not (match_pass or match_rec):
                self._record_owner_fail(conn, info, now_ts)
                raise ApiError("عبارة مرور المالك أو مفتاح الاسترداد غير صحيح")

            self._clear_owner_fail(conn)
            if user_id is not None:
                target = conn.execute("SELECT * FROM users WHERE id=? AND role='admin'", (_int(user_id),)).fetchone()
            else:
                target = conn.execute("SELECT * FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
            if not target:
                raise ApiError("لم يتم العثور على حساب مدير النظام")

            for other in conn.execute("SELECT id, pin_salt, pin_hash FROM users WHERE id!=?", (target["id"],)).fetchall():
                if hmac.compare_digest(db.hash_pin(np, other["pin_salt"]), other["pin_hash"]):
                    raise ApiError("الرمز السري مستخدم بالفعل لموظف آخر — يرجى اختيار رمز فريد")

            salt = os.urandom(16)
            conn.execute(
                "UPDATE users SET pin_salt=?, pin_hash=? WHERE id=?",
                (salt, db.hash_pin(np, salt), target["id"]),
            )
            self._audit(
                conn,
                "owner_reset_admin_pin",
                str(target["id"]),
                {"username": target["username"], "via": "passphrase" if match_pass else "recovery_key"},
            )
            conn.commit()
            return {"id": target["id"], "username": target["username"], "name": target["name"]}

    def owner_audit_list(self, limit=100):
        """استعراض سجل تدقيق تغييرات المالك الرئيسي."""
        self._owner()
        lim = max(1, min(500, _int(limit, 100)))
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id, ts, action, target, details FROM owner_audit_log ORDER BY id DESC LIMIT ?",
                (lim,),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["details"] = json.loads(d.get("details") or "{}")
                except Exception:
                    d["details"] = {}
                out.append(d)
            return out

    # ---------------------------------------------------------- سجل الأقسام (Phase 2)
    def _serialize_module(self, m: dict) -> dict:
        perms = m.get("perm_keys") or []
        perm_val = None if not perms else (perms[0] if len(perms) == 1 else list(perms))
        params = (m.get("params") or "").strip()
        url = m["url"]
        full_url = f"{url}?{params}" if params else url
        return {
            "id": m["key"],
            "key": m["key"],
            "title": m["title"],
            "icon": m["icon"],
            "color": m["color"],
            "url": url,
            "params": params,
            "full_url": full_url,
            "perm": perm_val,
            "perm_keys": list(perms),
            "sort_order": int(m.get("sort_order", 0) or 0),
            "enabled": bool(m.get("enabled", True)),
            "is_core": bool(m.get("is_core", False)),
            "is_builtin": bool(m.get("is_builtin", True)),
            "clone_of": m.get("clone_of"),
        }

    def ui_config(self):
        """إعدادات الواجهة والأقسام المفعلة والمسميات للتحميل عند التشغيل."""
        with db.connect() as conn:
            st = self._settings(conn)
            rows = self._modules_rows(conn)
            enabled = [self._serialize_module(m) for m in rows if m["enabled"]]
            lbls = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM ui_labels")}
            return {
                "modules": enabled,
                "labels": lbls,
                "default_labels": dict(DEFAULT_LABELS),
                "profile": st.get("business_profile") or "retail_electronics",
                "images_base_url": db.images_dir().resolve().as_uri(),
            }

    def modules_all(self):
        """عرض كافة الأقسام (المفعلة والمعطلة) في لوحة تحكم المالك."""
        self._owner()
        with db.connect() as conn:
            self._modules_cache = None
            return [self._serialize_module(m) for m in self._modules_rows(conn)]

    def module_toggle(self, key, enabled):
        """تفعيل أو تعطيل قسم مع حماية الأقسام الأساسية وفحص التبعيات."""
        self._owner()
        key = str(key or "").strip()
        en = bool(enabled)
        with db.connect() as conn:
            self._modules_cache = None
            rows = self._modules_rows(conn)
            by_key = {m["key"]: m for m in rows}
            target = by_key.get(key)
            if not target:
                raise ApiError("القسم غير موجود")
            if not en and target["is_core"]:
                raise ApiError("لا يمكن تعطيل قسم أساسي من النظام")
            if not en and target["is_builtin"]:
                dependents = [
                    m["title"]
                    for m in rows
                    if m["enabled"] and m["is_builtin"] and m["key"] != key and key in MODULE_REQUIRES.get(m["key"], [])
                ]
                if dependents:
                    raise ApiError(f"لا يمكن تعطيل «{target['title']}» لأن الأقسام التالية تعتمد عليه: {'، '.join(dependents)}")
            if en and target["is_builtin"]:
                missing_deps = [
                    by_key[d]["title"]
                    for d in MODULE_REQUIRES.get(key, [])
                    if d in by_key and not by_key[d]["enabled"]
                ]
                if missing_deps:
                    raise ApiError(f"يجب تفعيل الأقسام المطلوبة أولاً: {'، '.join(missing_deps)}")

            self._owner_backup_once()
            conn.execute(
                "UPDATE modules SET enabled=?, updated_at=? WHERE key=?",
                (1 if en else 0, db.now(), key),
            )
            self._audit(conn, "module_toggle", key, {"enabled": en})
            conn.commit()
            self._modules_cache = None
            return self._serialize_module(next(m for m in self._modules_rows(conn) if m["key"] == key))

    def module_reorder(self, keys):
        """إعادة ترتيب ظهور الأقسام حسب المصفوفة الممررة."""
        self._owner()
        if not isinstance(keys, list):
            raise ApiError("صيغة الترتيب غير صالحة")
        clean_keys = [str(k).strip() for k in keys if str(k).strip()]
        with db.connect() as conn:
            self._modules_cache = None
            existing = [m["key"] for m in self._modules_rows(conn)]
            existing_set = set(existing)
            ordered = [k for k in clean_keys if k in existing_set]
            seen = set(ordered)
            for k in existing:
                if k not in seen:
                    ordered.append(k)
            self._owner_backup_once()
            ts = db.now()
            for idx, k in enumerate(ordered, start=1):
                conn.execute("UPDATE modules SET sort_order=?, updated_at=? WHERE key=?", (idx * 10, ts, k))
            self._audit(conn, "module_reorder", None, {"order": ordered})
            conn.commit()
            self._modules_cache = None
            return [self._serialize_module(m) for m in self._modules_rows(conn)]

    def modules_reset_defaults(self, purge_custom=False):
        """استعادة الأقسام الافتراضية الـ 13 لحالتها الأصلية."""
        self._owner()
        self._owner_backup_once()
        ts = db.now()
        with db.connect() as conn:
            for key, title, icon, color, url, perms, order, is_core in db.DEFAULT_MODULES:
                conn.execute(
                    """INSERT INTO modules
                       (key, title, icon, color, url, params, perm_keys, sort_order, enabled, is_core, is_builtin, clone_of, created_at, updated_at)
                       VALUES(?,?,?,?,?,?,?,?,1,?,1,NULL,?,?)
                       ON CONFLICT(key) DO UPDATE SET
                         title=excluded.title, icon=excluded.icon, color=excluded.color,
                         url=excluded.url, params=excluded.params, perm_keys=excluded.perm_keys,
                         sort_order=excluded.sort_order, enabled=1, is_core=excluded.is_core,
                         is_builtin=1, clone_of=NULL, updated_at=excluded.updated_at""",
                    (key, title, icon, color, url, "", json.dumps(perms, ensure_ascii=False), order, is_core, ts, ts),
                )
            if purge_custom:
                conn.execute("DELETE FROM modules WHERE is_builtin=0")
            self._audit(conn, "modules_reset_defaults", None, {"purge_custom": bool(purge_custom)})
            conn.commit()
            self._modules_cache = None
            return [self._serialize_module(m) for m in self._modules_rows(conn)]

    # ---------------------------------------------------------- تعديل / نسخ / حذف الأقسام (Phase 3)
    def module_save(self, key, title, icon=None, color=None, params=None, perm_keys=None):
        """تعديل بيانات القسم (الاسم، الأيقونة، اللون، المعاملات للنسخ المخصصة، أو الصلاحيات)."""
        self._owner()
        key = str(key or "").strip()
        if not key:
            raise ApiError("مفتاح القسم مطلوب")
        with db.connect() as conn:
            self._modules_cache = None
            cur = next((m for m in self._modules_rows(conn) if m["key"] == key), None)
            if not cur:
                raise ApiError("القسم غير موجود")
            next_icon = cur["icon"] if icon is None else icon
            next_color = cur["color"] if color is None else color
            next_params = cur["params"] if (params is None or cur["is_builtin"]) else params
            next_perms = cur["perm_keys"] if perm_keys is None else perm_keys
            t, ic, col, par, perms = _validate_module_fields(title, next_icon, next_color, next_params, next_perms)
            self._owner_backup_once()
            conn.execute(
                "UPDATE modules SET title=?, icon=?, color=?, params=?, perm_keys=?, updated_at=? WHERE key=?",
                (t, ic, col, par, json.dumps(perms or [], ensure_ascii=False), db.now(), key),
            )
            self._audit(conn, "module_save", key, {"title": t, "icon": ic})
            conn.commit()
            self._modules_cache = None
            return self._serialize_module(next(m for m in self._modules_rows(conn) if m["key"] == key))

    def module_clone(self, source_key, title, icon=None, color=None, params="", perm_keys=None):
        """إنشاء قسم مخصص جديد كنسخة من قالب قسم حالي (يفتح نفس الصفحة ويشارك نفس البيانات)."""
        self._owner()
        src_key = str(source_key or "").strip()
        with db.connect() as conn:
            self._modules_cache = None
            rows = self._modules_rows(conn)
            src = next((m for m in rows if m["key"] == src_key), None)
            if not src:
                raise ApiError("القسم المصدري غير موجود")
            base_source = src.get("clone_of") or src["key"]
            next_icon = src["icon"] if not icon else icon
            next_color = src["color"] if not color else color
            next_perms = src["perm_keys"] if perm_keys is None else perm_keys
            t, ic, col, par, perms = _validate_module_fields(title, next_icon, next_color, params, next_perms)

            slug_src = re.sub(r"[^a-z0-9]+", "_", base_source.lower()).strip("_") or "mod"
            existing_keys = {m["key"] for m in rows}
            idx = 2
            new_key = f"c_{slug_src}_{idx}"
            while new_key in existing_keys:
                idx += 1
                new_key = f"c_{slug_src}_{idx}"

            max_order = max((int(m.get("sort_order", 0) or 0) for m in rows), default=0)
            ts = db.now()
            self._owner_backup_once()
            conn.execute(
                """INSERT INTO modules
                   (key, title, icon, color, url, params, perm_keys, sort_order, enabled, is_core, is_builtin, clone_of, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,1,0,0,?,?,?)""",
                (new_key, t, ic, col, src["url"], par, json.dumps(perms or [], ensure_ascii=False), max_order + 10, base_source, ts, ts),
            )
            self._audit(conn, "module_clone", new_key, {"source": src_key, "title": t, "params": par})
            conn.commit()
            self._modules_cache = None
            return self._serialize_module(next(m for m in self._modules_rows(conn) if m["key"] == new_key))

    def module_delete(self, key):
        """حذف قسم مخصص فقط؛ الأقسام المبنية في النظام تُعطّل ولا تُحذف."""
        self._owner()
        key = str(key or "").strip()
        with db.connect() as conn:
            self._modules_cache = None
            cur = next((m for m in self._modules_rows(conn) if m["key"] == key), None)
            if not cur:
                raise ApiError("القسم غير موجود")
            if cur["is_builtin"] or cur["is_core"]:
                raise ApiError("لا يمكن حذف قسم أساسي أو مبني في النظام — استخدم زر التعطيل بدلاً من ذلك")
            self._owner_backup_once()
            conn.execute("DELETE FROM modules WHERE key=? AND is_builtin=0", (key,))
            self._audit(conn, "module_delete", key, {"title": cur["title"]})
            conn.commit()
            self._modules_cache = None
            return True

    # ---------------------------------------------------------- ملفات النشاط والمسميات (Phase 4+)
    def _serialize_profile(self, r, cur_profile: str) -> dict:
        d = dict(r)
        for jf, default in (("modules_enabled", []), ("module_titles", {}), ("labels", {}), ("demo_catalog", [])):
            try:
                val = json.loads(d.get(jf) or json.dumps(default))
                d[jf] = val if isinstance(val, type(default)) else default
            except Exception:
                d[jf] = default
        d["is_builtin"] = bool(d.get("is_builtin", 1))
        d["is_current"] = d["key"] == cur_profile
        d["demo_count"] = len(d["demo_catalog"])
        return d

    def profiles_list(self):
        """عرض قوالب الأنشطة التجارية المحفوظة في قاعدة البيانات مع حالة النشاط الحالي."""
        self._owner()
        with db.connect() as conn:
            cur = self._settings(conn).get("business_profile") or "retail_electronics"
            rows = conn.execute("SELECT * FROM business_profiles ORDER BY sort_order ASC, key ASC").fetchall()
            return [self._serialize_profile(r, cur) for r in rows]

    def owner_profile_save(
        self,
        key=None,
        label="",
        description="",
        modules_enabled=None,
        module_titles=None,
        labels=None,
        demo_catalog=None,
        default_start_page="pos",
        price_unit="le",
    ):
        """إنشاء قالب نشاط تجاري جديد أو تعديل قالب موجود (الأقسام، العناوين، المسميات، والبيانات التجريبية)."""
        self._owner()
        lbl = str(label or "").strip()
        if not lbl or len(lbl) > 80:
            raise ApiError("اسم قالب النشاط مطلوب (بحد أقصى 80 حرفاً)")
        desc = str(description or "").strip()
        if len(desc) > 300:
            raise ApiError("وصف القالب طويل جداً (الحد الأقصى 300 حرف)")

        builtin_keys = {r[0] for r in db.DEFAULT_MODULES}
        core_keys = {r[0] for r in db.DEFAULT_MODULES if r[7]}
        titles_map = {r[0]: r[1] for r in db.DEFAULT_MODULES}

        if modules_enabled is None:
            mods_en = [r[0] for r in db.DEFAULT_MODULES]
        elif isinstance(modules_enabled, list):
            mods_en = [str(x).strip() for x in modules_enabled if str(x).strip() in builtin_keys]
            for ck in core_keys:
                if ck not in mods_en:
                    mods_en.append(ck)
        else:
            raise ApiError("قائمة الأقسام المفعلة غير صالحة")

        mods_set = set(mods_en)
        for mk in mods_en:
            missing_deps = [titles_map.get(dep, dep) for dep in MODULE_REQUIRES.get(mk, []) if dep not in mods_set]
            if missing_deps:
                raise ApiError(f"القسم «{titles_map.get(mk, mk)}» يتطلب تفعيل: {'، '.join(missing_deps)}")

        clean_mod_titles = {}
        if isinstance(module_titles, dict):
            for mk, mv in module_titles.items():
                smk = str(mk or "").strip()
                smv = str(mv or "").strip()
                if smk in builtin_keys and smv:
                    if len(smv) > 60:
                        raise ApiError("عنوان القسم المخصص يجب ألا يتجاوز 60 حرفاً")
                    clean_mod_titles[smk] = smv

        clean_labels = {}
        if isinstance(labels, dict):
            for lk, lv in labels.items():
                slk = str(lk or "").strip()
                slv = str(lv or "").strip()
                if slk not in LABEL_KEYS:
                    raise ApiError(f"مفتاح مسمى غير مسموح: {slk}")
                if slv:
                    if len(slv) > 40:
                        raise ApiError("طول المسمى يجب ألا يتجاوز 40 حرفاً")
                    clean_labels[slk] = slv

        dsp = str(default_start_page or "pos").strip()
        if dsp != "desktop" and dsp not in mods_set:
            dsp = mods_en[0] if mods_en else "desktop"

        clean_catalog = []
        seen_skus = set()
        if demo_catalog is not None:
            if not isinstance(demo_catalog, list):
                raise ApiError("صيغة قائمة البيانات التجريبية غير صالحة")
            if len(demo_catalog) > 200:
                raise ApiError("الحد الأقصى للبيانات التجريبية في القالب الواحد 200 صنف")
            for idx, it in enumerate(demo_catalog, start=1):
                if not isinstance(it, dict):
                    raise ApiError("عنصر بيانات تجريبية غير صالح")
                sku = str(it.get("sku") or "").strip()
                name = str(it.get("name") or "").strip()
                cat = str(it.get("category") or "").strip()
                if not sku or len(sku) > 40:
                    raise ApiError(f"كود الصنف (SKU) غير صالح في السطر {idx}")
                if sku in seen_skus:
                    raise ApiError(f"تكرار كود الصنف (SKU) «{sku}» غير مسموح داخل نفس القالب")
                seen_skus.add(sku)
                if not name or len(name) > 120:
                    raise ApiError(f"اسم الصنف غير صالح في السطر {idx}")
                if not cat or len(cat) > 60:
                    raise ApiError(f"اسم الفئة غير صالح في السطر {idx}")
                price_q = _int(it.get("price"), 0) if price_unit == "minor" else _money(it.get("price"), 0)
                cost_q = _int(it.get("cost"), 0) if price_unit == "minor" else _money(it.get("cost"), 0)
                qty = max(0, _int(it.get("qty"), 0))
                min_qty = max(0, _int(it.get("min_qty"), 5))
                if price_q < 0 or cost_q < 0:
                    raise ApiError(f"الأسعار يجب أن تكون قيماً غير سالبة في السطر {idx}")
                clean_catalog.append({
                    "sku": sku,
                    "name": name,
                    "category": cat,
                    "price": price_q,
                    "cost": cost_q,
                    "qty": qty,
                    "min_qty": min_qty,
                })

        raw_key = str(key or "").strip().lower()
        with db.connect() as conn:
            self._owner_backup_once()
            ts = db.now()
            cur_prof = self._settings(conn).get("business_profile") or "retail_electronics"
            if raw_key:
                if not _PROFILE_KEY_RE.match(raw_key):
                    raise ApiError("مفتاح القالب يجب أن يتكون من أحرف إنجليزية صغيرة وأرقام و _ فقط (2 إلى 40 محرفاً)")
                existing = conn.execute("SELECT * FROM business_profiles WHERE key=?", (raw_key,)).fetchone()
                if existing:
                    final_catalog = clean_catalog if demo_catalog is not None else json.loads(existing["demo_catalog"] or "[]")
                    conn.execute(
                        """UPDATE business_profiles
                           SET label=?, description=?, modules_enabled=?, module_titles=?, labels=?, demo_catalog=?, default_start_page=?, updated_at=?
                           WHERE key=?""",
                        (
                            lbl,
                            desc,
                            json.dumps(mods_en, ensure_ascii=False),
                            json.dumps(clean_mod_titles, ensure_ascii=False),
                            json.dumps(clean_labels, ensure_ascii=False),
                            json.dumps(final_catalog, ensure_ascii=False),
                            dsp,
                            ts,
                            raw_key,
                        ),
                    )
                    final_key = raw_key
                else:
                    max_ord = conn.execute("SELECT COALESCE(MAX(sort_order), 0) m FROM business_profiles").fetchone()["m"]
                    conn.execute(
                        """INSERT INTO business_profiles
                           (key, label, description, modules_enabled, module_titles, labels, demo_catalog, default_start_page, sort_order, is_builtin, created_at, updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,0,?,?)""",
                        (
                            raw_key,
                            lbl,
                            desc,
                            json.dumps(mods_en, ensure_ascii=False),
                            json.dumps(clean_mod_titles, ensure_ascii=False),
                            json.dumps(clean_labels, ensure_ascii=False),
                            json.dumps(clean_catalog, ensure_ascii=False),
                            dsp,
                            int(max_ord) + 10,
                            ts,
                            ts,
                        ),
                    )
                    final_key = raw_key
            else:
                slug = re.sub(r"[^a-z0-9]+", "_", lbl.lower()).strip("_") or "profile"
                existing_keys = {r["key"] for r in conn.execute("SELECT key FROM business_profiles")}
                idx = 1
                final_key = f"p_{slug[:24]}"
                while final_key in existing_keys or not _PROFILE_KEY_RE.match(final_key):
                    idx += 1
                    final_key = f"p_{slug[:20]}_{idx}"
                max_ord = conn.execute("SELECT COALESCE(MAX(sort_order), 0) m FROM business_profiles").fetchone()["m"]
                conn.execute(
                    """INSERT INTO business_profiles
                       (key, label, description, modules_enabled, module_titles, labels, demo_catalog, default_start_page, sort_order, is_builtin, created_at, updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,0,?,?)""",
                    (
                        final_key,
                        lbl,
                        desc,
                        json.dumps(mods_en, ensure_ascii=False),
                        json.dumps(clean_mod_titles, ensure_ascii=False),
                        json.dumps(clean_labels, ensure_ascii=False),
                        json.dumps(clean_catalog, ensure_ascii=False),
                        dsp,
                        int(max_ord) + 10,
                        ts,
                        ts,
                    ),
                )
            self._audit(conn, "profile_save", final_key, {"label": lbl, "demo_items": len(clean_catalog)})
            conn.commit()
            row = conn.execute("SELECT * FROM business_profiles WHERE key=?", (final_key,)).fetchone()
            return self._serialize_profile(row, cur_prof)

    def owner_profile_delete(self, key):
        """حذف قالب نشاط غير نشط مع منع حذف القالب المفعّل حالياً أو آخر قالب بالنظام."""
        self._owner()
        key = str(key or "").strip()
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM business_profiles WHERE key=?", (key,)).fetchone()
            if not row:
                raise ApiError("قالب النشاط غير موجود")
            cur_prof = self._settings(conn).get("business_profile") or "retail_electronics"
            if key == cur_prof:
                raise ApiError("لا يمكن حذف قالب النشاط المفعّل حالياً — فعّل قالباً آخر أولاً")
            cnt = conn.execute("SELECT COUNT(*) c FROM business_profiles").fetchone()["c"]
            if cnt <= 1:
                raise ApiError("يجب الإبقاء على قالب نشاط واحد على الأقل في النظام")
            self._owner_backup_once()
            conn.execute("DELETE FROM business_profiles WHERE key=?", (key,))
            self._audit(conn, "profile_delete", key, {"label": row["label"]})
            conn.commit()
            return True

    def owner_profiles_reset_defaults(self):
        """استعادة قوالب النشاط الافتراضية الأربعة (مع الإبقاء على القوالب المخصصة)."""
        self._owner()
        self._owner_backup_once()
        ts = db.now()
        with db.connect() as conn:
            cur_prof = self._settings(conn).get("business_profile") or "retail_electronics"
            for k, v in DEFAULT_BUSINESS_PROFILES.items():
                conn.execute(
                    """INSERT INTO business_profiles
                       (key, label, description, modules_enabled, module_titles, labels, demo_catalog, default_start_page, sort_order, is_builtin, created_at, updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,1,?,?)
                       ON CONFLICT(key) DO UPDATE SET
                         label=excluded.label,
                         description=excluded.description,
                         modules_enabled=excluded.modules_enabled,
                         module_titles=excluded.module_titles,
                         labels=excluded.labels,
                         demo_catalog=excluded.demo_catalog,
                         default_start_page=excluded.default_start_page,
                         sort_order=excluded.sort_order,
                         is_builtin=1,
                         updated_at=excluded.updated_at""",
                    (
                        k,
                        v["label"],
                        v.get("description", ""),
                        json.dumps(v.get("modules_enabled", []), ensure_ascii=False),
                        json.dumps(v.get("module_titles", {}), ensure_ascii=False),
                        json.dumps(v.get("labels", {}), ensure_ascii=False),
                        json.dumps(v.get("demo_catalog", []), ensure_ascii=False),
                        v.get("default_start_page", "pos"),
                        int(v.get("sort_order", 10)),
                        ts,
                        ts,
                    ),
                )
            self._audit(conn, "profiles_reset_defaults", None, {})
            conn.commit()
            rows = conn.execute("SELECT * FROM business_profiles ORDER BY sort_order ASC, key ASC").fetchall()
            return [self._serialize_profile(r, cur_prof) for r in rows]

    def _apply_profile_demo_catalog(self, conn, profile_key: str, demo_catalog: list, exclusive_demo: bool = False) -> int:
        """تفعيل البيانات التجريبية لقالب النشاط وإخفاء بيانات القوالب التجريبية الأخرى بأمان (active=0)."""
        if DEFAULT_RETAIL_SKUS:
            ph = ",".join("?" for _ in DEFAULT_RETAIL_SKUS)
            conn.execute(
                f"UPDATE products SET demo_profile='retail_electronics' WHERE demo_profile IS NULL AND sku IN ({ph})",
                DEFAULT_RETAIL_SKUS,
            )
        if DEFAULT_RETAIL_CATS:
            ph_c = ",".join("?" for _ in DEFAULT_RETAIL_CATS)
            conn.execute(
                f"UPDATE categories SET demo_profile='retail_electronics' WHERE demo_profile IS NULL AND name IN ({ph_c})",
                DEFAULT_RETAIL_CATS,
            )

        if exclusive_demo:
            conn.execute("UPDATE products SET active=0 WHERE demo_profile IS NULL OR demo_profile != ?", (profile_key,))
        else:
            conn.execute("UPDATE products SET active=0 WHERE demo_profile IS NOT NULL AND demo_profile != ?", (profile_key,))

        ts = db.now()
        applied_count = 0
        for item in demo_catalog:
            cat_name = str(item.get("category") or "").strip()
            sku = str(item.get("sku") or "").strip()
            name = str(item.get("name") or "").strip()
            if not (cat_name and sku and name):
                continue
            cat_row = conn.execute("SELECT id FROM categories WHERE name=?", (cat_name,)).fetchone()
            if cat_row:
                cat_id = cat_row["id"]
            else:
                cur_c = conn.execute("INSERT INTO categories(name, demo_profile) VALUES(?, ?)", (cat_name, profile_key))
                cat_id = cur_c.lastrowid

            price_q = max(0, _int(item.get("price"), 0))
            cost_q = max(0, _int(item.get("cost"), 0))
            qty = max(0, _int(item.get("qty"), 0))
            min_qty = max(0, _int(item.get("min_qty"), 5))

            prod_row = conn.execute("SELECT id FROM products WHERE sku=?", (sku,)).fetchone()
            if prod_row:
                conn.execute(
                    """UPDATE products
                       SET name=?, category_id=?, price=?, cost=?, qty=?, min_qty=?, active=1, demo_profile=?
                       WHERE id=?""",
                    (name, cat_id, price_q, cost_q, qty, min_qty, profile_key, prod_row["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO products
                       (sku, name, category_id, price, cost, qty, min_qty, tracked, active, demo_profile, created_at)
                       VALUES(?,?,?,?,?,?,?,0,1,?,?)""",
                    (sku, name, cat_id, price_q, cost_q, qty, min_qty, profile_key, ts),
                )
            applied_count += 1
        return applied_count

    def profile_apply(
        self,
        key,
        dry_run=True,
        apply_demo=True,
        exclusive_demo=False,
        fresh_db=False,
        carry_over=None,
        reset_store_info=False,
    ):
        """معاينة أو تطبيق ملف نشاط تجاري (على القاعدة الحالية أو بإنشاء قاعدة جديدة نظيفة مع حفظ نسخة احتياطية)."""
        self._owner()
        key = str(key or "").strip()
        with db.connect() as conn:
            cur_prof = self._settings(conn).get("business_profile") or "retail_electronics"
            prof_row = conn.execute("SELECT * FROM business_profiles WHERE key=?", (key,)).fetchone()
            if not prof_row:
                raise ApiError("ملف النشاط التجاري غير معروف")
            prof = self._serialize_profile(prof_row, cur_prof)

            target_set = set(prof["modules_enabled"])
            prof_titles = prof.get("module_titles") or {}
            default_titles = {row[0]: row[1] for row in db.DEFAULT_MODULES}
            demo_catalog = prof.get("demo_catalog") or []
            demo_cats = sorted({str(x.get("category") or "").strip() for x in demo_catalog if str(x.get("category") or "").strip()})

            self._modules_cache = None
            rows = self._modules_rows(conn)
            to_enable = []
            to_disable = []
            title_changes = []
            for m in rows:
                if not m["is_builtin"]:
                    continue
                next_en = (m["key"] in target_set) or bool(m["is_core"])
                next_title = prof_titles.get(m["key"], default_titles.get(m["key"], m["title"]))
                if next_en and not m["enabled"]:
                    to_enable.append({"key": m["key"], "title": next_title})
                elif not next_en and m["enabled"]:
                    to_disable.append({"key": m["key"], "title": m["title"]})
                if next_title != m["title"]:
                    title_changes.append({"key": m["key"], "from": m["title"], "to": next_title})

            if dry_run:
                return {
                    "dry_run": True,
                    "applied": False,
                    "profile": key,
                    "label": prof["label"],
                    "to_enable": to_enable,
                    "to_disable": to_disable,
                    "title_changes": title_changes,
                    "labels": dict(prof.get("labels") or {}),
                    "demo_count": len(demo_catalog),
                    "demo_categories": len(demo_cats),
                    "apply_demo": bool(apply_demo),
                    "exclusive_demo": bool(exclusive_demo),
                    "fresh_db": bool(fresh_db),
                }

            if not fresh_db:
                self._owner_backup_once()
                ts = db.now()
                for m in rows:
                    if not m["is_builtin"]:
                        continue
                    next_en = 1 if ((m["key"] in target_set) or bool(m["is_core"])) else 0
                    next_title = prof_titles.get(m["key"], default_titles.get(m["key"], m["title"]))
                    conn.execute(
                        "UPDATE modules SET enabled=?, title=?, updated_at=? WHERE key=?",
                        (next_en, next_title, ts, m["key"]),
                    )

                conn.execute("DELETE FROM ui_labels")
                for lk, lv in (prof.get("labels") or {}).items():
                    if lk in LABEL_KEYS and str(lv).strip():
                        conn.execute("INSERT INTO ui_labels(key, value) VALUES(?,?)", (lk, str(lv).strip()[:40]))

                demo_seeded = 0
                if apply_demo:
                    demo_seeded = self._apply_profile_demo_catalog(conn, key, demo_catalog, exclusive_demo=bool(exclusive_demo))

                conn.execute(
                    "INSERT INTO settings(key, value) VALUES('hide_empty_categories', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ("1" if (apply_demo and exclusive_demo) else "0",),
                )

                st = self._settings(conn)
                ver = _int(st.get("structure_version", "1"), 1) + 1
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES('business_profile', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key,),
                )
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES('structure_version', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(ver),),
                )
                cur_sp = st.get("default_start_page") or "pos"
                if cur_sp != "desktop" and cur_sp not in target_set:
                    conn.execute(
                        "INSERT INTO settings(key, value) VALUES('default_start_page', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (prof.get("default_start_page") or "pos",),
                    )

                self._audit(
                    conn,
                    "profile_apply",
                    key,
                    {"enabled": len(target_set), "disabled": len(to_disable), "demo_seeded": demo_seeded, "exclusive_demo": bool(exclusive_demo)},
                )
                conn.commit()
                self._modules_cache = None
                self._settings_cache = None
                return {
                    "dry_run": False,
                    "applied": True,
                    "fresh_db": False,
                    "profile": key,
                    "label": prof["label"],
                    "to_enable": to_enable,
                    "to_disable": to_disable,
                    "title_changes": title_changes,
                    "labels": dict(prof.get("labels") or {}),
                    "demo_seeded": demo_seeded,
                }

        # إغلاق اتصال القراءة ثم بناء القاعدة الجديدة النظيفة واستبدالها بأمان
        fresh_res = fresh_db_mod.build_fresh_profile_db(
            profile=prof,
            apply_demo_fn=self._apply_profile_demo_catalog,
            apply_demo=bool(apply_demo),
            carry_over=carry_over,
            reset_store_info=bool(reset_store_info),
        )
        self._modules_cache = None
        self._settings_cache = None
        if _STATE.get("owner"):
            _STATE["owner"]["backed_up"] = True
        return {
            "dry_run": False,
            "applied": True,
            "fresh_db": True,
            "backup_file": fresh_res.get("backup_file"),
            "carried": fresh_res.get("carried"),
            "profile": key,
            "label": prof["label"],
            "to_enable": to_enable,
            "to_disable": to_disable,
            "title_changes": title_changes,
            "labels": dict(prof.get("labels") or {}),
            "demo_seeded": fresh_res.get("demo_seeded", 0),
        }

    def labels_save(self, labels):
        """حفظ مسميات الواجهة المخصصة مع التحقق من المفاتيح المسموحة والطول."""
        self._owner()
        if not isinstance(labels, dict):
            raise ApiError("صيغة المسميات غير صالحة")
        cleaned = {}
        for k, v in labels.items():
            sk = str(k or "").strip()
            if sk not in LABEL_KEYS:
                raise ApiError(f"مفتاح مسمى غير مسموح: {sk}")
            sv = "" if v is None else str(v).strip()
            if len(sv) > 40:
                raise ApiError("طول المسمى يجب ألا يتجاوز 40 حرفاً")
            cleaned[sk] = sv

        with db.connect() as conn:
            self._owner_backup_once()
            for sk, sv in cleaned.items():
                if sv == "":
                    conn.execute("DELETE FROM ui_labels WHERE key=?", (sk,))
                else:
                    conn.execute(
                        "INSERT INTO ui_labels(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (sk, sv),
                    )
            self._audit(conn, "labels_save", None, {"keys": sorted(cleaned.keys())})
            conn.commit()
            return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM ui_labels")}
