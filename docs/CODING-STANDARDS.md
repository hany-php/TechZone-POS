# TechZone Coding Standards & Modular Plug-and-Play Rules

Rules and conventions for all code in the TechZone POS & ERP system.

---

## 1. Mandatory Modular Plug-and-Play Architecture (هندسة الأقسام المعزولة)

Every AI model and developer working on TechZone POS MUST adhere to the **Modular Plug-and-Play (Zero-Overhead Isolation)** architecture whenever creating, modifying, adding, or deleting any module:

1. **Self-Contained Domain Mixins & Pages:**
   - Each functional section (`pos`, `sales_quotes`, `inventory`, `customers`, `installments`, `purchases`, `accounting`, `history`, `repair`, `buy_used`, `reports`, `staff`) must encapsulate its backend endpoints in `app/api_<module>.py` and its UI in `web/<module>.html`.
2. **Server-Side Module Guard (`app/modules_map.py` & `app/api.py`):**
   - Every non-core public `Api` method must be mapped to its module key in `API_MODULE_MAP` (`app/modules_map.py`).
   - `Api.call()` checks `self._module_enabled(mod)` from the in-memory `self._modules_cache` (`O(1)`) before executing any method. If a module is disabled in `owner.html`, all its API methods are blocked server-side even for `admin`.
3. **Zero-Overhead Cross-Module Hooks (`app/erp_hooks.py`):**
   - Core operational modules (`pos`, `inventory`, `customers`, `repair`, `buy_used`, `installments`) must never hard-depend on optional ERP modules (`purchases`, `accounting`).
   - Any cross-module hook in `app/erp_hooks.py` MUST check `if not is_module_active(api, conn, "accounting"): return None` on its first line so disabled modules add **0 ms and 0 SQL queries** to POS checkout or other operations.
   - Cross-module analytics (such as `report_comprehensive` in `app/api_reports.py`) must check `erp_hooks.is_module_active(self, conn, "<module>")` before querying optional module tables.
4. **Separation of Invoice Revenue vs. Perpetual Inventory COGS Entries:**
   - When `accounting` is active, auto-posted journal entries for sales (`on_sale_created`), sales returns (`on_sale_returned`), standalone installments (`on_installment_created`), and delivered repairs (`on_repair_delivered`) MUST separate the **Financial Invoice/Revenue entry** (`source_table='sales'`, whose debit/credit total equals the exact invoice total) from the **Perpetual Inventory Cost (COGS) entry** (`source_table='sales_cogs'`). Never merge revenue and COGS into a single journal entry header, as that inflates the displayed journal entry total above the actual sale price.

---

## 2. Python (`app/*.py`)

### General

- All SQL queries use **parameterized placeholders** (`?`) — never string interpolation.
- Money values are stored as **INTEGER minor units** (1 LE = 100 qirsh). Display conversion happens in the JS frontend or formatted export helpers.
- HTML output from Python (PDF templates, dynamic snippets) must use escaping helpers to prevent injection.
- Imports: standard library first, then pywebview, then project modules.

### File & Function Naming

- Filenames: `lowercase_with_underscores.py` (e.g., `api_purchases.py`, `api_accounting.py`, `erp_hooks.py`, `selfcheck.py`).
- Functions: `snake_case` (e.g., `purchase_save`, `accounting_opening_apply`, `report_comprehensive`).
- The API dispatcher `call(name, payload)` maps JS calls to Python functions — every public API function must be classified in `app/modules_map.py`.

### Database

- Schema lives in `app/db.py` (52 tables) with non-destructive auto-migration logic (`_ensure_schema_columns`) that adds new tables/columns without data loss.
- Always use `INTEGER` for monetary amounts and `TEXT` for ISO-8601 timestamps.
- Default seed data is Egyptian-market specific (`ج.م` currency, 14% VAT rate, 1%/3% WHT withholding tax support, Arabic UI defaults, 38-account standard Arabic Chart of Accounts).

---

## 3. JavaScript (`web/app.js`, inline `<script>` blocks)

### General

- **Vanilla JS only** — no frameworks, no npm runtime dependencies, no TypeScript.
- DOM manipulation via `getElementById`, `querySelector`, and `innerHTML` templating using `esc()` on all dynamic strings.
- The bridge function `api(name, payload)` wraps `window.pywebview.api.call()` and transparently supports iframe sub-windows.

### Permission & Module Checks

- Every module page calls `await pageInit('<module_key>')` at startup to verify authentication, module activation, and user permissions.
- Use `hasPerm(key)` before showing or enabling UI elements that require a specific permission (63 granular permission keys across 12 groups in `app/permissions.py`).

### Theme & Accent

- `applyThemeEverywhere()` synchronizes dark/light mode across the desktop shell and all open sub-windows.
- `applyAccentColorEverywhere()` applies the user's chosen accent color globally.

---

## 4. CSS (`web/tailwind.css` → `web/app.css`)

- Source file: `web/tailwind.css` (Tailwind directives + `@font-face` declarations).
- Compiled output: `web/app.css` — **checked into git intentionally** so the app runs without Node.js at runtime.
- All 23 font files (Cairo, IBM Plex Sans Arabic, Material Icons) are local `.woff2` in `web/fonts/`.

---

## 5. RTL, Printing & Localization

- The entire UI is **Arabic, right-to-left** (`dir="rtl"`).
- Currency symbol: `ج.م` (or `LE` in English contexts).
- Every financial and accounting screen must support clean **A4 printing (`@media print`)** and, where applicable, export to **Excel (`.xlsx` / `.csv`)**, **PDF (`A4`)**, and **WhatsApp PDF sharing** (respecting the admin `whatsapp_send_enabled` setting).

---

## 6. Prohibited Patterns

1. **No violation of Modular Plug-and-Play isolation** — never hardwire cross-module calls without `erp_hooks.is_module_active` guards and `modules_map.py` registration.
2. **No external network calls** at runtime — not even for fonts, analytics, or error reporting.
3. **No new Python runtime dependencies** beyond stdlib + pywebview without explicit approval (even `.xlsx` and `.pdf` exports are built natively using Python's standard library).
4. **No npm packages** that ship to production.
5. **No raw SQL string concatenation** — always use parameterized queries.
6. **No `eval()`** in Python or JavaScript.
7. **No undocumented changes** — every addition, modification, or deletion must be recorded in `AGENTS.md`, `README.md`, and `docs/*.md`.


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
- **آلية تسليم التحديثات بالملفات المعدّلة فقط (`Delta-Only Patch Delivery`):** عند أي تعديل أو إضافة أو حذف مستقبلاً، يتم اختبار النسخة الكاملة عبر `app/selfcheck.py` ثم تسليم حزمة `.zip` خفيفة تحتوي على **الملفات المعدّلة والمضافة فقط** بنفس هيكل المجلدات (`techzone-pos/...`) مع ذكر قائمة أي ملفات محذوفة صراحةً، وذلك لتقليل حجم التحميل والرفع (ما لم يطلب المستخدم النسخة الكاملة).
- **بدء التشغيل الصامت مع ويندوز في شريط النظام بجوار الساعة (`--tray`, `is_start_in_tray_requested`, `installer/TechZone.iss`):** عند تفعيل خيار التشغيل التلقائي مع ويندوز في المثبت، يُمرر المعامل `--tray` ليبدأ البرنامج مخفياً تماماً (`hidden=True`, `ShowInTaskbar=False`) في شريط النظام بجوار الساعة دون فتح نافذة على سطح المكتب، مع إمكانية فتحه بالضغط على الأيقونة أو إغلاقه نهائياً بكليك يمين.
- **دعم اللغتين العربية والإنجليزية (`web/i18n.js`, `users.lang`, `applyLanguageEverywhere`):** محرك ترجمة ثنائي الاتجاه (`RTL`/`LTR`) معزول بدون اعتماديات خارجية، يتيح تبديل اللغة من شاشة الدخول (`index.html`) أو من إعدادات الملف الشخصي (`profile.html`) أو الشريط العلوي (`desktop.html`) مع حفظ اللغة بشكل مستقل لكل مستخدم في `users.lang`.
- **محرك الاستيراد والتصدير الشامل لملفات Excel (`app/api_excel.py`: `excel_entities_list`, `excel_template`, `excel_export`, `excel_import`):** وحدة معزولة (`Modular Plug-and-Play`) بدون مكتبات خارجية لتصدير واستيراد `.xlsx`/`.csv` للمنتجات والتصنيفات والعملاء والموردين وشجرة الحسابات وقاموس الترجمة وتصدير المبيعات والمصروفات والصيانة والأقساط، متاحة في تبويب «استيراد وتصدير Excel» في `web/settings.html` ومباشرة داخل `web/inventory.html` و`web/customers.html` و`web/purchases.html`.
