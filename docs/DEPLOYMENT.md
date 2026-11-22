# Deployment & Distribution Guide — TechZone POS

## 1. Target Environment & Prerequisites

TechZone POS is designed as an autonomous, self-contained desktop system requiring **no internet connectivity**, **no external database servers**, and **no runtime software dependencies** on client machines.

### Hardware & Operating System Specifications
- **Operating System:** Windows 10 (Build 1809 or later) or Windows 11 (64-bit).
- **Architecture:** x86_64 / amd64.
- **Display Resolution:** Optimized for standard 1360×860 desktop screens and touch POS monitors (min supported: 360×500 for compact windows).
- **Runtime Component:** Microsoft Edge WebView2 Evergreen Runtime (pre-installed natively on modern Windows 10/11 updates).
- **Memory & Storage:** Minimum 2 GB RAM, 250 MB free disk space for runtime and database growth.


> ⚠️ **Mandatory Rule for All AI Models & Developers (`Modular Plug-and-Play — Zero-Overhead Isolation` & Full Documentation):**
> 1. **Modular Plug-and-Play Isolation**: Any creation, modification, addition, or deletion of a module now or in the future MUST strictly follow the isolated Plug-and-Play architecture (`DEFAULT_MODULES` in `app/db.py`, `API_MODULE_MAP` in `app/modules_map.py`, and `erp_hooks.is_module_active` runtime guards so disabled modules incur zero SQL/CPU overhead).
> 2. **Mandatory Documentation Sync**: Every code, schema, setting, or UI change MUST be documented in the same turn/commit across `AGENTS.md`, `CLAUDE.md`, `README.md`, and `docs/*.md`.

---

## 2. Packaging Architecture (`PyInstaller`)

The production artifact is a single, portable executable generated via PyInstaller:

```
dist/
└── TechZone.exe     (~45 - 55 MB standalone executable)
```

### 2.1 PyInstaller Bundle Specification (`TechZone.spec`)
- **Mode:** `--onefile --windowed`
- **Icon:** Embedded `icon.ico`
- **Asset Bundling:**
  - `web/` → `sys._MEIPASS/web` (contains all HTML, compiled CSS, vanilla JS, and local WOFF2 font assets).
  - `icon.ico` → `sys._MEIPASS/icon.ico`
- **Runtime Path Resolution:**
  - When frozen (`getattr(sys, 'frozen', False)`): web assets are resolved from `sys._MEIPASS/web`.
  - Database (`data/shop.db`) and receipts (`data/receipts/`) are resolved relative to the executable's directory (`pathlib.Path(sys.executable).parent / 'data'`). This ensures user data survives executable updates without overwriting.

---

## 3. Build & Release Workflow

### 3.1 One-Click Build Script (`build-exe.bat`)
To compile a fresh production executable from the local development workspace:
1. Double-click `build-exe.bat` or execute in PowerShell:
   ```powershell
   .\build-exe.bat
   ```
2. The batch script performs:
   - Verification of Python 3.13 and PyInstaller availability.
   - Cleans previous temporary build directories (`build/TechZone`).
   - Packages all assets and writes the updated executable to `dist\TechZone.exe`.

### 3.2 Automated Git & GitHub Backup (`push-github.bat`)
To stage, commit, and push project updates safely to the remote GitHub repository:
```powershell
.\push-github.bat
```

---

## 4. Shop Installation & Deployment Steps

Installing TechZone on a new store terminal takes less than 2 minutes:

1. **Copy Files:** Copy `dist\TechZone.exe` to the shop's target folder (e.g. `C:\TechZone\`).
2. **Desktop Shortcut:** Right-click `TechZone.exe` → *Send to* → *Desktop (create shortcut)*.
3. **Launch:** Run the executable. On first launch:
   - TechZone automatically initializes the SQLite schema (`data\shop.db`) with Egyptian localized seed values.
   - Creates the receipt storage directory (`data\receipts\`).
   - Opens the smart login interface (`index.html`).
4. **Default Logins & Owner Setup (Change Immediately):**
   - **Admin:** PIN `1234` (first-run modal forces changing it to a secure PIN)
   - **Cashier:** PIN `1111`
   - **Owner Mode (Recommended for software deployers):** Long-press the store logo/name for 2 seconds on the login screen (or Start Menu header) to set up the independent Owner passphrase and store the one-time recovery key securely.
5. **Printer Configuration:** Connect the thermal printer (80mm USB / Network) and standard office printer (A4). Ensure the Windows Default Printer is assigned as desired.

---

## 5. Backup, Maintenance & Disaster Recovery

### 5.1 Built-In & Routine Database Backups
All store operations, customer ledgers, installment contracts, invoices, inventory, and settings reside in a single SQLite file:
```
data\shop.db
data\backups\    (automatic startup, shift-close, pre-restore & pre-fresh snapshots)
```
- **Automatic Rotation:** TechZone uses the ACID SQLite Online Backup API to save automatic snapshots on daily startup, cashier shift closure, and before structural/profile rebuilds (retaining the latest 30 snapshots automatically).
- **Safe In-App Restore:** Managers (`settings_manage`) can restore any snapshot from `settings.html?tab=backups` after `PRAGMA quick_check` validation and an automatic `before_restore` safety backup.
- **External Copy Routine:** Also copy `data\shop.db` / `data\backups\` to an external USB flash drive at the close of every business day.
- **Pre-Update Backup:** Before replacing `TechZone.exe` with a newer version, always take a snapshot via `settings.html` or copy `data\shop.db`.

### 5.2 Automatic Database Schema Migrations
TechZone includes non-destructive schema migrations in `app/db.py`:
- Newly introduced columns (`_ensure_schema_columns`) and structural migrations (`_migrate_customers`, `customer_ledger`, `installments`, `modules`, `business_profiles`) execute automatically on application launch.
- Existing sales, customers, and inventory data remain intact across software updates.


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
- **تنظيف رقم الإصدار في المثبّت (`MyAppVersionClean` في `installer/TechZone.iss`):** تنظيف قيمة `MyAppVersion` تلقائياً عبر ISPP (إزالة البادئة `v` واللواحق `-beta`/`+build` وعدم إضافة `.0` زائدة لإصدارات الـ 4 أجزاء) لضمان نجاح `VersionInfoVersion` على GitHub Actions والمحلي.
- **دعم اللغتين العربية والإنجليزية (`web/i18n.js`, `users.lang`, `applyLanguageEverywhere`):** محرك ترجمة ثنائي الاتجاه (`RTL`/`LTR`) معزول بدون اعتماديات خارجية، يتيح تبديل اللغة من شاشة الدخول (`index.html`) أو من إعدادات الملف الشخصي (`profile.html`) أو الشريط العلوي (`desktop.html`) مع حفظ اللغة بشكل مستقل لكل مستخدم في `users.lang`.
