# Owner Control & Multi-Business Structure — Implementation Plan

> **Audience:** any AI coding agent (or human) executing this plan with no prior context.
> **Status:** PLAN ONLY — nothing here is implemented yet. Baseline = commit `2ee2932` (Phase D installments), selfcheck `158/158`.
> **Read first:** `AGENTS.md` (non-negotiable rules §7), `docs/ARCHITECTURE.md`, `docs/DATA-MODEL.md`, `docs/SECURITY.md`.
> **Language note:** UI strings are Arabic (RTL). Code identifiers, comments in this doc: English.

## 0. Goal (الهدف)

Let the **software owner** (a role above the shop `admin`) control the *structure* of the program from inside it, protected by a separate secret:

1. Enable / disable any section (module).
2. Add / edit / delete / reorder sections (custom sections = **copies of existing templates** only; no page builder).
3. Switch the program to another business type (retail electronics, generic shop, restaurant, pharmacy) via **profiles** (module set + UI labels).
4. Protect all of the above with an **owner passphrase**, with a simple **recovery key** so a forgotten secret / forgotten admin PIN is recoverable.
5. Keep it simple: pure-Python + SQLite, no new dependencies, no bundler, offline.

**Out of scope (do NOT build):** page builder, multi-branch/multi-DB (future), licensing/hardware binding, DB encryption, restaurant/pharmacy domain features (tables, kitchen, batches/expiry). Profiles for restaurant/pharmacy only *hide/rename* what exists today.

### Honest security boundary
The app is offline and the user owns the machine. The owner passphrase blocks tampering **through the UI and the `Api.call` bridge**. It cannot stop someone who edits `data/shop.db` or the source directly. Mitigation: ship only the PyInstaller `TechZone.exe`. Do not over-engineer beyond this (user decision).


> ⚠️ **Mandatory Rule for All AI Models & Developers (`Modular Plug-and-Play — Zero-Overhead Isolation` & Full Documentation):**
> 1. **Modular Plug-and-Play Isolation**: Any creation, modification, addition, or deletion of a module now or in the future MUST strictly follow the isolated Plug-and-Play architecture (`DEFAULT_MODULES` in `app/db.py`, `API_MODULE_MAP` in `app/modules_map.py`, and `erp_hooks.is_module_active` runtime guards so disabled modules incur zero SQL/CPU overhead).
> 2. **Mandatory Documentation Sync**: Every code, schema, setting, or UI change MUST be documented in the same turn/commit across `AGENTS.md`, `CLAUDE.md`, `README.md`, and `docs/*.md`.

---

## 1. Verified current state (audit, 2026-11-16)

| Fact | Where |
|---|---|
| Sections are hardcoded: `OS_APPS` (13 apps: pos, sales_quotes, customers, installments, inventory, history, repair, buy_used, reports, staff, settings, profile, receipt) | `web/desktop.html` ~L992 |
| Sidebar for non-OS pages is a second hardcoded list `NAV` | `web/app.js` ~L259 |
| Visible apps = `OS_APPS.filter(hasPerm)` → `PERMITTED_APPS`, used by Start menu, Dock, desktop icons, `targetApp` deep-link | `web/desktop.html` L1884-1895 |
| Valid start pages are a hardcoded set in `settings_save` | `app/api_auth.py` L491 |
| Single dispatcher: `Api.call(name, payload)`; allowed names = public (non-`_`) methods collected in `self._methods` | `app/api.py` L44-67 |
| Authorization: `_perm / _perm_any / _admin` on `_STATE["user"]`; role `admin` bypasses all | `app/api_common.py` L658-687 |
| Session is a process-global dict `_STATE = {"user": None}` | `app/api_common.py` L16 |
| PIN hashing: `db.hash_pin(pin, salt)` = PBKDF2-SHA256, 200 000 iters; compare with `hmac.compare_digest` | `app/db.py` L483 |
| Login lockout state persisted in `settings.login_fail_state` (JSON) | `app/api_auth.py` L359-437 |
| `settings_save` uses an **allowlist** of keys (new secret keys must NOT be added to it) | `app/api_auth.py` L479 |
| `db.backup_database(reason)` / `restore_database(name)` exist; schema+migration in `db.init_db` / `_migrate_once`; additive migrations only | `app/db.py` L463-660, L1111 |
| `selfcheck.py` has an API "contract" check: every `api('name')` in `web/*.html|js` must exist on `Api` | `app/selfcheck.py` ~L885 |
| Existing DB: 23 tables; ADRs in `docs/adr/` (0001, 0002) | |

**Architectural consequence:** because every backend call goes through `Api.call`, a **single server-side guard in `call()`** can enforce "module disabled" for the whole app. The frontend only *hides* things; the guard is the real control.

---

## 2. Design

### 2.1 Roles
| Level | Can do |
|---|---|
| **Owner** (new) | structure: modules, profiles, labels; reset admin PIN; view structure audit log; change owner secrets |
| `admin` (existing) | staff, settings, daily operation (unchanged) |
| `cashier` | per-permission (unchanged) |

Owner mode is **independent of the user login**: `_STATE["owner"] = {"until": <epoch>}`. Idle timeout 10 min (sliding). `logout()` also clears it.

### 2.2 Owner secrets (simple recovery model)
- **Passphrase**: ≥ 8 chars (not a 4-digit PIN). PBKDF2-SHA256 200k + 16-byte salt (reuse `db.hash_pin` style helper; add `db.hash_secret(text, salt)` if input rules differ).
- **Recovery key**: generated once at setup (e.g. 20 chars from `A-Z2-9` without ambiguous chars, shown as `XXXXX-XXXXX-XXXXX-XXXXX`), **stored only as a hash**. The owner prints/saves it offline.
- Either secret can: log in as owner **and** reset the admin PIN. Recovery key additionally resets the owner passphrase (and rotates itself — new key shown once).
- Lockout: 5 wrong attempts → 15 min lock, persisted in DB (same pattern as `login_fail_state`, separate key `owner_fail_state`).
- **First setup**: allowed only while not configured AND an `admin` is logged in (prevents a cashier from claiming ownership). After setup, structure screens require the owner secret.

### 2.3 Data model (additive migration, `db.py`)
```sql
CREATE TABLE IF NOT EXISTS owner_auth (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  pass_hash BLOB NOT NULL, pass_salt BLOB NOT NULL,
  recovery_hash BLOB NOT NULL, recovery_salt BLOB NOT NULL,
  fail_state TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS modules (
  key TEXT PRIMARY KEY,              -- 'pos', 'inventory', or custom 'c_<slug>'
  title TEXT NOT NULL,               -- display name (Arabic)
  icon TEXT NOT NULL, color TEXT NOT NULL,
  url TEXT NOT NULL,                 -- built-in page, e.g. 'inventory.html'
  params TEXT NOT NULL DEFAULT '',   -- query string for clones, e.g. 'category_id=3'
  perm_keys TEXT NOT NULL DEFAULT '[]',   -- JSON array, same semantics as OS_APPS.perm
  sort_order INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  is_core INTEGER NOT NULL DEFAULT 0,     -- cannot be disabled/deleted
  is_builtin INTEGER NOT NULL DEFAULT 1,  -- builtin: hide only; custom: deletable
  clone_of TEXT,                          -- module key this entry copies
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ui_labels (
  key TEXT PRIMARY KEY, value TEXT NOT NULL);       -- overrides of default labels

CREATE TABLE IF NOT EXISTS owner_audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, action TEXT NOT NULL,
  target TEXT, details TEXT NOT NULL DEFAULT '{}');
```
- Seed `modules` from the 13 built-ins **only if the table is empty** (idempotent; never overwrite owner edits). Core (non-disableable) = `settings`, `profile`, `receipt`. Login `index.html` and the desktop shell are never modules. `staff` is optional; because `settings` is core, an admin always keeps a reachable path.
- Settings keys (plain `settings` table, NOT in the `settings_save` allowlist): `business_profile` (default `retail_electronics`), `structure_version`.
- `modules` is a **clone-aware alias model**: a clone has its own title/icon/color/perm/params but the *same page and the same data* (shared tables). State this limitation in the UI ("نسخة من القسم — تشارك نفس البيانات"). Real data separation = future branches work.

### 2.4 Server guard (the real control)
New file `app/modules_map.py`:
```python
# Public Api method name -> module key. Methods NOT listed are CORE (always allowed).
API_MODULE_MAP = { "products_search": "inventory", "sale_create": "pos", ... }
CORE_METHODS = { "login", "logout", "session", "ui_config", "owner_status", "owner_login", ... }
```
In `Api.call()` before dispatch:
```python
mod = API_MODULE_MAP.get(name)
if mod and not self._module_enabled(mod):
    raise ApiError("هذا القسم غير مُفعّل من مدير النظام الرئيسي")
```
- `_module_enabled(key)` reads `modules` (cache invalidated on any module write, like `_settings_cache`). A module is "enabled" if its builtin row is enabled; clones don't affect API guarding (they alias a builtin).
- **Cross-module dependencies**: some features need others (`pos` → `inventory` reads, `installments` → `customers`). Define `MODULE_REQUIRES = {"installments": ["customers"], "pos": ["inventory"], ...}`; `module_toggle(off)` is refused with a clear Arabic message if an enabled module depends on it (or offers to cascade). Reads needed by a dependent module (e.g. `products_search` for POS) must map to a *shared* key or be CORE — decide per method and document in the map.
- **Contract test (mandatory):** selfcheck asserts that **every public `Api` method is either in `API_MODULE_MAP` or in `CORE_METHODS`**. This forces future AI agents to classify new methods.

### 2.5 Owner API (`app/api_owner.py`, `OwnerMixin`, register in `api.py`)
All write methods call `self._owner()` (valid unexpired owner session, refresh timer) and, for structural changes, take one `db.backup_database("before_structure_change")` per owner session and write `owner_audit_log`.

| Method | Auth | Purpose |
|---|---|---|
| `owner_status()` | public | `{configured, active, seconds_left}` |
| `owner_setup(passphrase)` | admin session, only if not configured | create secrets; **returns `recovery_key` once** |
| `owner_login(passphrase)` | public + lockout | start owner session |
| `owner_logout()` | public | end it |
| `owner_change_passphrase(old, new)` | owner session | rotate passphrase |
| `owner_recover(recovery_key, new_passphrase)` | public + lockout | reset passphrase; **returns new recovery key once** |
| `owner_reset_admin_pin(secret, new_pin, user_id=None)` | public + lockout; `secret` = passphrase or recovery key | fixes forgotten admin PIN (validates PIN strength like `profile_save`; no duplicate PIN) |
| `ui_config()` | any logged-in user (and pre-login for labels) | `{modules:[enabled only], labels:{}, profile}` — single boot call |
| `modules_all()` | owner | all rows incl. disabled |
| `module_toggle(key, enabled)` | owner | refuse core / dependency violations |
| `module_save(key?, title, icon, color, perm_keys, ...)` | owner | edit builtin metadata or create/edit custom |
| `module_clone(source_key, title, icon, color, params='')` | owner | new custom alias; key `c_<slug>` |
| `module_delete(key)` | owner | custom only; builtin → refuse (use toggle) |
| `module_reorder(keys[])` | owner | set `sort_order` |
| `modules_reset_defaults()` | owner | re-seed builtins to factory (keeps clones unless `purge_custom=True`) |
| `profiles_list()` / `profile_apply(key, dry_run=True)` | owner | preview then apply preset (modules + labels) |
| `labels_save(dict)` | owner | validate keys ∈ `LABEL_KEYS`, max 40 chars |
| `owner_audit_list(limit=100)` | owner | read log |

Never log secrets. Use `hmac.compare_digest`. Parameterized SQL only. Validate `icon` against a safe regex (`^[a-z0-9_]{1,40}$`), `color` against `^(#[0-9a-fA-F]{3,8}|linear-gradient\([#0-9a-zA-Z,.%() -]{1,120}\))$`, `params` against `^[A-Za-z0-9_=&.-]{0,120}$`, `title` ≤ 60 chars.

### 2.6 Profiles (business types) — `app/profiles.py`
Constants only (no table). Each profile = `{label, modules_enabled:[keys], labels:{key:value}, default_start_page}`.

| Profile | Enabled modules | Label overrides (examples) |
|---|---|---|
| `retail_electronics` (default = today) | all | none |
| `generic_shop` | all except `repair`, `buy_used` | — |
| `restaurant` | `pos`, `sales_quotes`, `history`, `inventory`, `reports`, `staff`, `settings`, `profile`, `receipt` | `inventory`→"الأصناف والخامات", `pos`→"نقطة البيع" |
| `pharmacy` | `pos`, `inventory`, `customers`, `history`, `reports`, `staff`, `settings`, `profile`, `receipt` | `inventory`→"الأدوية والمستلزمات" |

`profile_apply(dry_run=True)` returns the diff (modules to enable/disable, labels) for confirmation before commit. Applying never deletes data and never touches custom clones.
> Restaurant/pharmacy are *presets over the current feature set*. Missing domain features are listed in `OPEN-QUESTIONS.md` for a later phase — do not invent them here.

### 2.7 Labels (`t()`)
- `LABEL_KEYS` (Python, allowlist) and defaults (JS `DEFAULT_LABELS` in `app.js`).
- `t(key)` returns override from `ui_config().labels` or default. Apply to: module titles (via `modules.title`), sidebar `NAV`, and page `<h1>` titles marked with `data-label="key"`. **Do not** refactor every string; scope = section names + a short list (product/products, customer/customers, repair center, used devices).

### 2.8 Frontend changes
1. `app.js`: `loadUiConfig()` (cached in `window.UI_CONFIG`), `t()`, `NAV` built from `UI_CONFIG.modules` (fallback to the old constant if call fails). Keep `hasPerm` filtering.
2. `desktop.html`: `OS_APPS` becomes the **default fallback**; at boot `PERMITTED_APPS = UI_CONFIG.modules (enabled) ∩ hasPerm`. Icon layout store must tolerate missing/new ids. Deep-link `targetApp` and start page fall back to the first enabled module when the target is disabled.
3. Direct page open guard: `pageInit` checks the page's module is enabled (via `UI_CONFIG`); if not, show an "القسم غير مُفعّل" screen. (Server guard remains authoritative.)
4. `settings_save` `valid_start_pages` → validate against enabled module keys instead of a literal set.
5. New page `web/owner.html` (**not** a module, not in Start menu/Dock): 
   - Entry: **long-press (2 s) on store name/logo** on `index.html` and in the desktop Start menu header; also reachable at `owner.html`.
   - Screens: setup wizard (first run) → login → tabs: **الأقسام** (toggle/edit/clone/delete/drag-reorder) · **نوع النشاط** (profile preview/apply) · **المسميات** · **الأمان** (change passphrase, show-recovery warning) · **السجل** (audit).
   - On `index.html`: link "نسيت رمز المدير؟" → modal asking passphrase or recovery key + new admin PIN → `owner_reset_admin_pin`.
6. Reuse Tailwind classes already compiled; if new utilities are used, recompile: `npx tailwindcss -i web/tailwind.css -o web/app.css --minify`.

---

## 3. Execution phases (each ends with a gate; do not skip)

> Work on a branch (e.g. `feat/owner-control`), commit per phase. After **every** phase: `python app/selfcheck.py` must stay green, update `AGENTS.md` (affected sections + Changelog entry, newest first) in the same commit.

### Phase 1 — Owner auth & recovery (foundation)
**Files:** `app/db.py` (tables `owner_auth`, `owner_audit_log`), `app/api_owner.py` (new), `app/api.py` (register mixin), `app/api_common.py` (`_STATE["owner"]`, `_owner()`, `_audit()`), `web/owner.html` (setup/login/security/audit only), `web/index.html` (long-press entry + "نسيت رمز المدير؟").
**Tasks:** implement `owner_status/setup/login/logout/change_passphrase/recover/reset_admin_pin/owner_audit_list`; lockout; session timeout; logout clears owner state.
**Gate (selfcheck additions, ≥ 10):** cashier & admin cannot call owner-write methods; setup refused for cashier / when already configured; wrong passphrase ×5 locks and persists across reconnect; recovery key resets passphrase and the old key stops working; `owner_reset_admin_pin` works with passphrase and with recovery key and enforces PIN strength; secrets never appear in any API response besides the one-time recovery key; session expires after timeout (monkeypatch time).

### Phase 2 — Module registry + server guard
**Files:** `app/db.py` (`modules` table + idempotent seed), `app/modules_map.py` (new), `app/api.py` (guard in `call`), `app/api_owner.py` (`ui_config`, `modules_all`, `module_toggle`, `module_reorder`, `modules_reset_defaults`), `app/api_auth.py` (`valid_start_pages`), `web/app.js`, `web/desktop.html`, `web/owner.html` (الأقسام tab: toggle + reorder).
**Tasks:** classify **every** public `Api` method into `API_MODULE_MAP` / `CORE_METHODS` (list them with `dir(Api)`); dependency rules; frontend reads `ui_config`.
**Gate:** contract test (every public method classified); disabling `inventory` makes `products_search`/`product_save` fail even for admin while `login/session/settings` still work; core modules cannot be disabled; dependent-module toggle refused; disabled module disappears from Start/Dock/NAV/desktop icons and start-page validation; re-enable restores; migration on an existing DB (e.g. stress DB) keeps all data and seeds 13 modules once (run twice → no duplicates).

### Phase 3 — Edit / clone / delete sections
**Files:** `app/api_owner.py` (`module_save`, `module_clone`, `module_delete`), `web/owner.html` (edit/clone/delete UI), `web/desktop.html` (render `params`, clones opening the same page with query string).
**Tasks:** input validation regexes (§2.5); clone key generation `c_<slug>` unique; custom delete confirmation; builtin delete refused; permissions for clones (`perm_keys` inherits source by default); automatic permission-matrix exposure is **not** needed (clone uses source perms) — keep simple.
**Gate:** clone opens the source page with params; validation rejects bad icon/color/params; builtin delete refused; delete custom works; audit rows written for each change; automatic backup created before first change in a session.

### Phase 4 — Profiles + labels
**Files:** `app/profiles.py` (new), `app/api_owner.py` (`profiles_list`, `profile_apply`, `labels_save`), `web/app.js` (`t()`, `DEFAULT_LABELS`), `web/owner.html` (tabs نوع النشاط + المسميات), a few `data-label` hooks in section pages.
**Gate:** `profile_apply(dry_run=True)` changes nothing; apply → modules/labels exactly match profile; switching back to `retail_electronics` restores the original state; custom clones untouched; start page falls back correctly.

### Phase 5 — Hardening, docs, release
- Idle-timeout UI countdown in `owner.html`; clear owner state on logout/window close.
- `selfcheck` total target: **≥ 185** passing (158 now + ≥ 27 new).
- Docs: `AGENTS.md` (doc map, §4 selfcheck count, §5 tree, §7 rules, Changelog), `docs/DATA-MODEL.md` (4 tables), `docs/SECURITY.md` (owner mode, recovery, boundary), `docs/ARCHITECTURE.md` (guard + registry), `docs/ROADMAP.md`, `docs/OPEN-QUESTIONS.md` (restaurant/pharmacy domain gaps, branches), new `docs/adr/0003-owner-mode-and-module-registry.md`.
- Manual QA checklist: first-run setup as admin; cashier cannot reach `owner.html` functions; forgot admin PIN flow; forgot owner passphrase via recovery key; disable each module and verify UI + API; PyInstaller build still works (`build-exe.bat`) and `modules`/owner data persist in `data/shop.db`.

---

## 4. Rules for the executing agent
1. Obey `AGENTS.md` §7: money in minor units, parameterized SQL only, server-side authorization, offline only, no bundlers/frameworks, update `AGENTS.md` in the same commit.
2. Migrations are **additive and idempotent**; never drop/alter existing data. Test on a copy of a populated DB (`data/shop.db` copy or the stress DB), never on production data.
3. Do not add secret keys to `settings_save`'s allowlist; never return hashes/salts from any API.
4. Do not break the public API contract: existing method names/signatures unchanged.
5. Every new public `Api` method must be classified in `modules_map.py` (the contract test enforces this) and used by at least one page, or the contract/selfcheck will flag it.
6. Keep new Python files < ~400 lines; owner UI in a single `web/owner.html`.
7. If a decision is ambiguous, pick the simplest option that satisfies §0 and record it in the Changelog / `OPEN-QUESTIONS.md` instead of expanding scope.

## 5. Decisions already made by the product owner
- "Multiple places" = different **business types** (restaurant, pharmacy, shop). Branches come later.
- Custom sections = **template copies only**; no page builder.
- Forgotten admin/owner secret must be recoverable → recovery key design (§2.2).
- Simple programmatic protection only; no licensing/encryption/complexity.


---

## 2026-11-18 Updates Summary (Modular ERP, COA Drag & Drop, Reports Hub, Per-User Icons & System Tray)

- **Modular Plug-and-Play Enforcement**: All 15 built-in modules (`pos`, `sales_quotes`, `inventory`, `customers`, `installments`, `purchases`, `accounting`, `history`, `repair`, `buy_used`, `reports`, `staff`, plus core `settings`, `profile`, `receipt`) follow Zero-Overhead Isolation via `DEFAULT_MODULES`, `API_MODULE_MAP` (181 methods), and `erp_hooks.is_module_active`.
- **Accounting & Reports Enhancements**: Separated sale invoice revenue (`source_table='sales'`) vs. perpetual inventory cost (`source_table='sales_cogs'`) journal entries; single-run Opening Balance Wizard guard (`has_opening_entry`); COA Add/Edit/Delete (`account_delete`) and Drag-and-Drop reparenting (`account_move`); universal A4 printing; and 5-tab `report_comprehensive` with native multi-sheet `.xlsx`, `.csv`, `A4 PDF`, direct print, and WhatsApp report sharing (`whatsapp_send_report`).
- **Per-User Desktop & Taskbar Icon Visibility (`web/profile.html`, `web/desktop.html`)**: Each user can independently show/hide desktop icons (`_hidden_desktop`) and taskbar icons (`_hidden_taskbar`) stored strictly in their own `users.desktop_layout` JSON record.
- **Close Button (`X`) & Windows System Tray (`app/main.py`, `web/settings.html`)**: Added `close_exit_app` setting (`#st-close-exit-app`). When `'0'` (default), clicking the window `X` button hides the window to the Windows System Tray next to the clock (`.NET WinForms NotifyIcon`); when `'1'`, clicking `X` exits the application completely.


### تحديثات الميزات التشغيلية والأمنية (Barcode Label Studio, Auto-Lock on Idle, General Audit Log, POS Alerts & Credit Limits)
- **استوديو طباعة ملصقات الباركود والرفوف (`tzGenerateBarcodeSvg` & `tzBuildBarcodeLabelsPrintHtml` & `#modal-barcode-studio`):** في `web/app.js` و`web/inventory.html` و`web/purchases.html`، توليد باركود قياسي `Code-128B SVG` محلياً 100% بدون إنترنت مع طباعة ملصقات حرارية (`38×25 مم`، `50×25 مم`، `50×30 مم`) أو شبكة ملصقات `A4` من شاشة المخزون أو مباشرة لأصناف فواتير المشتريات (`printPurchaseBarcodes`).
- **قفل الشاشة التلقائي عند الخمول (`idle_lock_minutes` & `verify_lock_pin` & `#os-lock-overlay`):** في `web/desktop.html` و`web/settings.html` و`app/api_auth.py`، تتبع نشاط المستخدم في سطح المكتب والنوافذ الفرعية وقفل الشاشة تلقائياً بعد دقائق الخمول المحددة (أو يدوياً بزر «🔒 قفل») مع فك القفل برمز `PIN` الخاص بالمستخدم الحالي دون إغلاق النوافذ أو فقدان الفواتير المفتوحة.
- **سجل رقابة العمليات اليومية الشامل (`activity_audit_log` & `activity_audit_list` & `_log_activity`):** في `app/db.py` و`app/api_common.py` و`app/api_auth.py` و`web/settings.html` (تبويب «سجل رقابة العمليات Audit Log»)، تسجيل آلي معزول (`Modular Plug-and-Play`) لكافة العمليات الحساسة (إصدار وتعديل ومرتجعات المبيعات، إضافة وحذف المنتجات وتغيير الأسعار `product_price_change`، تعديل المخزون `stock_adjust`، العملاء وسندات القبض، تحديث الإعدادات، وفك قفل الشاشة) مع الفلترة والطباعة `A4`.
- **التنبيهات الصوتية والمرئية لنواقص المخزون وحد ائتمان العملاء (`tzPlayPosSound` & `pos_sound_enabled` & `pos_low_stock_alert` & `credit_limit` & `enforce_credit_limit`):** في `web/app.js` و`web/pos.html` و`web/customers.html` و`app/api_sales.py` و`app/api_customers.py`، نغمات صوتية تفاعلية عبر `WebAudio API` عند المسح والبيع والتحذير، وتنبيه فوري عند وصول رصيد الصنف للحد الأدنى أثناء البيع (`low_stock_items`)، وفحص حد الائتمان المخصص لكل عميل (`customers.credit_limit`) أو الافتراضي للمتجر (`customer_default_credit_limit`) مع خيار التنبيه أو المنع الإجباري (`enforce_credit_limit`).
- **إصلاح طبقة وحجب شاشة القفل (`#os-lock-overlay` & `tz-screen-locked`):** في `web/desktop.html`، نقل شاشة القفل خارج `#os-root` وتثبيتها بأعلى طبقة (`z-index: 2147483647`) مع تعطيل تفاعل `#os-root` بالكامل (`pointer-events: none`) وحراسة دوال `openApp` و`toggleStart` أثناء القفل (`TZOS.isLocked()`) لمنع فتح أي قسم قبل فك القفل برمز الـ `PIN`.
- **ترحيل وحفظ صور المنتجات كملفات WebP على القرص (`save_image_to_disk`, `_migrate_base64_images_to_disk`, `db_optimize_images`, `tzImgSrc`):** في `app/db.py` و`app/api_inventory.py` و`app/api_auth.py` و`web/app.js`، تحويل صور المنتجات من نصوص `Base64` داخل SQLite إلى ملفات WebP مضغوطة في `data/images/products/prod_<id>.webp` عند الإضافة/التعديل أو بدء التشغيل، مع زر ضغط القاعدة (`VACUUM`) في `web/settings.html`.
- **تحسين إرفاق ملفات PDF في الواتساب (`_win32_send_ctrl_v`, `Set-Clipboard`, `history.html`):** في `app/api_common.py` و`web/history.html`، ترقية آلية اللصق التلقائي للمرفق باستخدام `SendInput` مع انتظار تحميل محادثة واتساب (`1.35s`–`2.80s`) وفك قفل المقدمة في ويندوز، وإضافة احتياطي `PowerShell Set-Clipboard -LiteralPath` مع إصلاح استدعاء `sendInvoicePdfToWhatsapp` في `web/history.html`.
- **إصلاح حجم بنية `INPUT` في `SendInput` (`MOUSEINPUT`/`KEYBDINPUT`/`HARDWAREINPUT` = 40 بايت):** في `app/api_common.py`، تصحيح تعريف اتحاد `_INPUT_UNION` في `_win32_send_ctrl_v` ليطابق حجم Win32 64-bit الرسمي (40 بايت) مع احتياطي `keybd_event` لضمان تنفيذ لصق ملف الـ `PDF` في محادثة واتساب تلقائياً.
- **ضبط حجم `SendInput` بـ 40 بايت ثابتة وإزالة النقر العشوائي في واتساب (`_find_whatsapp_hwnd`, `_win32_send_ctrl_v`, `_win32_auto_paste_into_whatsapp`):** في `app/api_common.py`، تصفية نوافذ واتساب المساعدة الصغيرة (<300px)، عدم إلغاء التكبير (`SW_RESTORE` للمصغرة فقط)، إزالة ضغطة `Alt` والنقر أسفل النافذة حتى لا يضيع تركيز خانة الكتابة، واستخدام `ctypes.c_int32`/`c_uint32` لضمان حجم `INPUT = 40 بايت` مع تسجيل تشخيصي في `data/receipts/whatsapp_paste_debug.log`.
- **بدء التشغيل الصامت مع ويندوز في شريط النظام بجوار الساعة (`--tray`, `is_start_in_tray_requested`, `installer/TechZone.iss`):** عند تفعيل خيار التشغيل التلقائي مع ويندوز في المثبت، يُمرر المعامل `--tray` ليبدأ البرنامج مخفياً تماماً (`hidden=True`, `ShowInTaskbar=False`) في شريط النظام بجوار الساعة دون فتح نافذة على سطح المكتب، مع إمكانية فتحه بالضغط على الأيقونة أو إغلاقه نهائياً بكليك يمين.
- **دعم اللغتين العربية والإنجليزية (`web/i18n.js`, `users.lang`, `applyLanguageEverywhere`):** محرك ترجمة ثنائي الاتجاه (`RTL`/`LTR`) معزول بدون اعتماديات خارجية، يتيح تبديل اللغة من شاشة الدخول (`index.html`) أو من إعدادات الملف الشخصي (`profile.html`) أو الشريط العلوي (`desktop.html`) مع حفظ اللغة بشكل مستقل لكل مستخدم في `users.lang`.
