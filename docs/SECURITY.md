# Security Policy and Controls — TechZone POS

## 1. Overview & Threat Model

TechZone POS is an **offline desktop system** designed for retail and repair electronics shops in Egypt. It operates within a single `pywebview` window powered by Microsoft Edge WebView2 on Windows 10/11.

Because the system is **100% offline** and binds to no public network interfaces, conventional web threats (remote brute force, DDoS, SSRF, cross-origin network sniffing) are not applicable in production. However, because it manages confidential retail, customer, financial, and repair data, strict physical, local, and privilege boundaries are required.

### Key Protected Assets
1. **Financial Records:** Cashier daily sales, net profits, price margins, drawer cash counting, customer ledger statements, debt settlements.
2. **Customer Personal Data:** Names, phone numbers, national identification numbers (mandatory for buying used electronic equipment).
3. **Inventory & Cost Secrets:** Supplier purchase costs, wholesale equipment cost bases, serial tracking.
4. **Administrative Credentials:** PIN hashes, manager role permissions, user role profiles.

### Primary Threat Vectors
- **Unauthorized Physical Access:** Unattended cashier station being used by unauthorized staff or customers.
- **Cashier Privilege Escalation:** Cashier attempting to view manager-level reports, cost prices, profit margins, or manipulate closed invoices.
- **PIN Brute-Force Guessing:** Rapid repeated PIN attempts on the login screen.
- **Malicious Local File Manipulation / Path Traversal:** Crafted invoice numbers or report paths attempting directory traversal.
- **Database File Theft:** Direct exfiltration of `data/shop.db` via USB thumb drives.


> ⚠️ **Mandatory Rule for All AI Models & Developers (`Modular Plug-and-Play — Zero-Overhead Isolation` & Full Documentation):**
> 1. **Modular Plug-and-Play Isolation**: Any creation, modification, addition, or deletion of a module now or in the future MUST strictly follow the isolated Plug-and-Play architecture (`DEFAULT_MODULES` in `app/db.py`, `API_MODULE_MAP` in `app/modules_map.py`, and `erp_hooks.is_module_active` runtime guards so disabled modules incur zero SQL/CPU overhead).
> 2. **Mandatory Documentation Sync**: Every code, schema, setting, or UI change MUST be documented in the same turn/commit across `AGENTS.md`, `CLAUDE.md`, `README.md`, and `docs/*.md`.

---

## 2. Implemented Security Controls

### 2.1 Authentication & Credential Storage
- **Cryptographic Hashing:** User PINs and passwords are protected using `hashlib.pbkdf2_hmac` with `SHA-256`, utilizing a unique 16-byte random salt per user and **200,000 iterations**.
- **No Plaintext Storage:** PINs are never persisted in plaintext, logs, or error responses.
- **Smart PIN-Only Login:** The system securely resolves identity and authorization level from the salted PIN hash without requiring pre-selection of role.

### 2.2 Brute-Force & Guessing Protections
- **Login Lockout Policy:** Configurable login lock mechanism (`login_max_attempts` default: 5, `login_lockout_minutes` default: 10 minutes).
- **Persistent Lockout State:** Failed attempt state and countdown timers are tracked in `settings` (`login_fail_state`) to prevent bypassing lockouts via application restarts.
- **Active Countdown & Input Freeze:** The UI disables inputs and shows remaining lockout seconds.
- **Mandatory Default PIN Protection:** On first run or whenever the administrative account uses default credentials (`1234`), a blocking modal (`#modal-force-pin`) prevents access to the system until a secure 4-8 digit PIN is configured and confirmed. Weak patterns (`1234`, `0000`, `1111`) are rejected.

### 2.3 Automated Backup & Disaster Recovery
- **ACID Zero-Lock Snapshots:** Automated SQLite Online Backup API (`src_conn.backup(dest_conn)`) guarantees consistent point-in-time snapshots without locking the database or interrupting POS sales.
- **Trigger Points:** Automatic backup on application startup (`daily_startup_backup`) and upon every cashier shift closure (`shift_close`).
- **Retention & Rotation:** Automatically maintains the latest 30 snapshots in `data/backups/`, pruning older files.
- **Safe In-App Database Restore (`db_restore`):** Managers can restore any snapshot directly from `settings.html`. Before overwriting, a safety snapshot (`shop_YYYYMMDD_HHMMSS_before_restore.db`) is generated, ensuring zero data loss even if an incorrect backup is selected. Integrity is verified with `PRAGMA quick_check` prior to restore.

### 2.4 Server-Side Authorization (`_perm`)
- **Backend-Enforced Authorization:** Authorization is verified strictly in Python (`app/api_*.py`) via `_perm(key)`, `_perm_any(*keys)`, `_perm_all(*keys)`, and ownership scope guards (`_scope_check`). Frontend checks in JavaScript (`hasPerm()`) are strictly for UI visibility and do not govern execution.
- **49 Granular Permissions in 10 Groups:** Non-admin staff operate under least-privilege defaults (`cashier_strict`: only `pos_sell`, `shift_manage`, `receipt_view`, `customers_quick_pick`) with zero debt/history/cost/report leaks, Blind Close support (`shift_summary_view=False`), account activation toggles (`users.is_active`), and RBAC change auditing (`perm_audit_log`).
- **Database Backup & Restore Isolation:** Endpoints `db_backup`, `backups_list`, and `db_restore` require `backups_manage` authorization; unauthorized users are strictly blocked.
- **Immutable Historical Invoices:** Sales invoices (`sales`) cannot be deleted once committed. Adjustments must follow structured return procedures (`sale_returns`) with full audit traceability.

### 2.5 Injection and Input Defense
- **SQL Parameterization:** 100% of database queries in `app/api.py` and `app/db.py` use parameterized queries (`?`). String interpolation is strictly prohibited.
- **Safe Output Escaping:** Dynamic text inserted into invoice and receipt previews is sanitized via `esc()` to prevent injection.
- **Upload Validation & Magic Bytes:** Image uploads (logos, avatars, product pictures) are validated for Base64 integrity, size limits, and cryptographic magic bytes (rejecting HTML, SVG, and binary executables disguised as images).
- **Safe Filesystem Naming:** PDF invoice and report generation routines enforce strict character allowlisting (`safe_name`) to prevent directory traversal (`../`).

---

## 3. Regulatory & Privacy Considerations (Egyptian PDPL)

Under Egyptian Law No. 151 of 2020 (Personal Data Protection Law - PDPL):
- **Customer Phone & National ID:** Collected during used device trade-ins (`used_device_purchases`) and installment customer records. These are classified as personal data.
- **Data Minimization:** Only fields necessary for warranty service, invoice tracking, and anti-theft compliance are recorded.
- **Data Retention & Disposal:** Customer records should not be deleted arbitrarily if attached to active debt ledgers, but personal notes can be cleared upon customer request.

---

## 4. Security Action Plan (from Quality Audit)

The following items are scheduled for hardening in **Phase 2** of the project roadmap:

1. ✅ **Forced Default Credential Change (Implemented):** Mandatory PIN update on first run (`#modal-force-pin`) for default `admin` (`1234`) account, plus Owner PIN reset support.
2. ✅ **Read-Endpoint Authorization & Zero-Leak Overhaul (Implemented 2026-11-17):** All read queries (`sale`, `quotation`, `repairs`, `customer`, `customers_list`, `shift`, `shift_summary`, `history_suggestions`, `sales_stats`, `used_stats`, `stock_stats`, `report_low`) enforce strict 49-key permissions, ownership scoping, name/phone-only POS customer quick-pick redaction, and Blind Close drawer redaction.
3. **Database at Rest Encryption:** Provide an optional transparent encryption wrapper (e.g., SQLCipher) or BitLocker storage guidance for `data/shop.db`.
4. **Session Idle Timeout:** Add an automatic desktop lock screen after configurable inactivity periods (e.g., 15 minutes of idle time).

---

## 5. Owner Mode & Structure Protection (Added 2026-11-16)

To separate software structural control from day-to-day shop administration (`admin`):
- **Independent Owner Secret:** `owner_auth` stores a PBKDF2-HMAC-SHA256 (200,000 iterations, 16-byte salt) hash of an owner passphrase (≥ 8 chars) and a one-time 20-char recovery key (`XXXXX-XXXXX-XXXXX-XXXXX`). Hashes and salts are never returned in any API response.
- **First-Run Claim Guard:** `owner_setup` requires an authenticated `admin` session and only succeeds once when `owner_auth` is unconfigured.
- **Persistent Lockout & Idle Expiry:** 5 failed attempts on `owner_login`, `owner_recover`, or `owner_reset_admin_pin` trigger a 15-minute lockout persisted in `owner_auth.fail_state`. Active owner sessions expire after 10 minutes of inactivity (`OWNER_SESSION_TTL = 600`) and are cleared on `logout()`, `owner_logout()`, and native window close.
- **Recovery Model:** The one-time recovery key rotates itself on use (`owner_recover`). Either the passphrase or recovery key can reset a forgotten shop `admin` PIN (`owner_reset_admin_pin`) with PIN strength and uniqueness enforcement.
- **Server-Side Module Guard:** `Api.call()` enforces `API_MODULE_MAP` before dispatching any method, blocking disabled modules even for `admin`.
- **Automatic Pre-Change Snapshot & Audit Trail:** Structural mutations create a `before_structure_change` SQLite backup once per owner session and log every action to `owner_audit_log`.
- **Honest Security Boundary:** Because the system runs offline on the client machine, Owner Mode prevents tampering **through the UI and `Api.call` bridge**. It cannot prevent direct modification of `data/shop.db` or Python source files by someone with local OS file access; production deployments should distribute the compiled `TechZone.exe` binary.


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
- **محرك الاستيراد والتصدير الشامل لملفات Excel (`app/api_excel.py`: `excel_entities_list`, `excel_template`, `excel_export`, `excel_import`):** وحدة معزولة (`Modular Plug-and-Play`) بدون مكتبات خارجية لتصدير واستيراد `.xlsx`/`.csv` للمنتجات والتصنيفات والعملاء والموردين وشجرة الحسابات وقاموس الترجمة وتصدير المبيعات والمصروفات والصيانة والأقساط، متاحة في تبويب «استيراد وتصدير Excel» في `web/settings.html` ومباشرة داخل `web/inventory.html` و`web/customers.html` و`web/purchases.html`.
