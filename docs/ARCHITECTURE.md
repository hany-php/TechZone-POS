# TechZone POS & ERP — System Architecture

## Overview

TechZone is a fully offline point-of-sale, shop management, procurement (`purchases`), double-entry accounting (`accounting`), and financial analytics (`reports`) operating system purpose-built for Egyptian electronics retailers and general businesses. It runs as a single-window desktop application powered by Python 3.13, `pywebview` 6.2.1 (backed by Microsoft WebView2), and a vanilla HTML/CSS/JS frontend styled with compiled Tailwind CSS. All data lives in a local SQLite database (`data/shop.db` in WAL mode); the application requires zero network connection at runtime.

---

## ⚠️ Mandatory Architectural Principle: Modular Plug-and-Play (هندسة الأقسام المعزولة)

> **Non-Negotiable Rule for All AI Models & Developers:**
> Every module in TechZone OS is designed as an isolated **Plug-and-Play** unit. Any future addition, modification, or removal of a module MUST strictly obey this architecture:

1. **Zero-Overhead Isolation When Disabled:**
   - The system comprises **15 built-in modules** stored in the `modules` table (`pos`, `sales_quotes`, `inventory`, `customers`, `installments`, `purchases`, `accounting`, `history`, `repair`, `buy_used`, `reports`, `staff`, plus core `settings`, `profile`, `receipt`).
   - `Api._module_enabled(module_key)` caches module activation states in memory (`self._modules_cache`) for `O(1)` lookup and invalidates automatically on `module_toggle`, `profile_apply`, or `modules_reset_defaults`.
   - When `purchases` or `accounting` (or any other module) is disabled in `owner.html`, `app/erp_hooks.py` returns immediately on its first line (`if not is_module_active(api, conn, "accounting"): return None`), ensuring **zero SQL queries, zero CPU overhead, and zero side effects** on POS sales, returns, or shifts.
2. **Server-Side Dispatcher Gate (`app/modules_map.py`):**
   - All **181 public API methods** are mapped in `API_MODULE_MAP` or `CORE_METHODS` inside `app/modules_map.py`.
   - `Api.call()` enforces the module guard before method execution, blocking disabled module API calls even for `admin`.
3. **Separated Financial vs. COGS Journal Posting (`app/erp_hooks.py`):**
   - When `accounting` is active, operational events (`on_sale_created`, `on_sale_returned`, `on_installment_created`, `on_repair_delivered`) generate **two distinct, balanced journal entries**:
     1. **Primary Financial Entry (`source_table='sales'`, etc.):** Records the exact invoice total (`Dr Cash/Wallet/AR = Cr Sales Revenue + Cr VAT Output`), so the journal entry amount displayed in the General Journal matches the actual sale invoice 100%.
     2. **Perpetual Inventory Cost Entry (`source_table='sales_cogs'`, etc.):** Separately records `Dr COGS (5101) = Cr Merchandise Inventory (1105)` at historical weighted-average cost (`cost_unit`).
4. **Idempotent Opening Balance Wizard (`accounting_opening_apply`):**
   - `accounting_opening_preview` and `accounting_opening_apply` inspect `journal_entries` for any existing posted entry with `kind='opening' AND status='posted'`. If one exists, the backend blocks re-execution and the UI disables the wizard trigger and displays the existing opening entry metadata to prevent duplicate opening entries.

---

## System Diagram

```mermaid
flowchart TD
    subgraph Native["Native Python Backend Layer"]
        MAIN["app/main.py\n(Entry Point & Session Cleanup)"]
        PV["pywebview 6.2.1\nWindow (maximized)"]
        API["app/api.py (Facade)\n10 Domain Mixins (181 public methods)"]
        MODMAP["app/modules_map.py\nO(1) Module Guard & Profiles (profiles.py / fresh_db.py)"]
        HOOKS["app/erp_hooks.py\nPlug-and-Play Event Hooks (WAC + Double-Entry)"]
        DB_MOD["app/db.py\nSchema (52 Tables) · Seed · Migrations · Backups"]
        EXPORT["Native Exporters\nPDF 1.4 + Multi-Sheet OpenXML .xlsx + CSV"]
        WA["WhatsApp Integration\nctypes Win32 CF_HDROP"]
    end

    subgraph Engine["WebView2 Engine"]
        WV2["Microsoft WebView2\n(Chromium-based)"]
    end

    subgraph Frontend["Frontend (web/ — 19 Pages)"]
        INDEX["index.html\n(Smart Login & Owner Recovery)"]
        DESKTOP["desktop.html\n(TechZone OS Shell)"]
        OWNER["owner.html\n(Owner Mode & Profiles Control)"]
        PAGES["16 App Pages\n(pos, purchases, accounting, reports, etc.)"]
        APPJS["app.js\nBridge · 63 Permissions · Labels t() · Invoices"]
        APPCSS["app.css\n(Compiled Tailwind)"]
        FONTS["fonts/\n23 local .woff2 files"]
    end

    subgraph Data["Data Layer"]
        SQLITE[("data/shop.db\n52 Tables (WAL Mode)")]
        BACKUPS["data/backups/\nACID Snapshots"]
        RECEIPTS["data/receipts/ & data/reports/\nExported PDFs & Excel Workbooks"]
    end

    MAIN --> PV --> WV2 --> INDEX --> DESKTOP --> PAGES
    PAGES --> APPJS -->|"window.pywebview.api.call(name, payload)"| API
    API --> MODMAP
    API --> HOOKS
    API --> DB_MOD --> SQLITE
    API --> EXPORT --> RECEIPTS
    API --> WA
```

---

## Frontend Architecture (19 Pages)

| Page | Module Key | Role |
|------|------------|------|
| `index.html` | *(core)* | Smart login screen — PIN auto-detection, force-PIN change, and owner recovery modal |
| `owner.html` | *(core)* | Hidden Owner Control panel — module registry (toggle/reorder/edit/clone/delete), 5 business profiles (`retail_electronics`, `generic_shop`, `restaurant`, `pharmacy`, `enterprise_erp`), custom labels, fresh DB builder & audit log |
| `desktop.html` | *(core)* | TechZone OS shell — dynamic module registry, taskbar, Start menu, Dock, floating windows, desktop icons |
| `pos.html` | `pos` | High-speed retail POS cashier with hardware barcode scanner listener & in-app print preview |
| `sales_quotes.html` | `sales_quotes` | Official B2B A4 sales invoices & price quotations |
| `purchases.html` | `purchases` | Procurement & Suppliers ERP: purchase bills (with landed shipping cost & WAC calculation, 14% VAT input, 1%/3% WHT), purchase orders (`PO`), purchase returns, supplier CRM, supplier payment vouchers (`SPY-`), statements & AP Aging |
| `accounting.html` | `accounting` | Double-Entry Accounting & Finance ERP: 6 tabs (Overview, Operational Expenses, Treasuries & Transfers, Chart of Accounts with Add/Edit/Delete & HTML5 Drag-and-Drop reparenting, General Journal with separated Sale vs. COGS entries & single-entry viewer, Financial Statements + General Ledger, single-run Opening Balance Wizard, and universal A4 printing across all sections) |
| `inventory.html` | `inventory` | Product catalog, stock tracking, serial numbers, and stocktake sheet |
| `customers.html` | `customers` | Customer database, debt totals, and ledger shortcuts |
| `customer_details.html` | `customers` | Individual customer account statement, installment contracts & payment vouchers |
| `installments.html` | `installments` | Installment contracts, pre-sale calculator, payment collections, overdue alerts & WhatsApp reminders |
| `repair.html` | `repair` | Repair/service ticket management & spare parts |
| `buy_used.html` | `buy_used` | Used device purchasing & trade-ins |
| `history.html` | `history` | Unified operations history, returns, and multi-filter ledger |
| `reports.html` | `reports` | Comprehensive Financial & Operational Analytics Hub (5 detailed sub-tabs: Detailed P&L + Invoice/Item Profitability, Customer Receivables & Installments, Supplier Payables & Purchases, Cashflow/Treasuries/Shifts, Inventory Valuation & Movements; with native multi-sheet `.xlsx` export, `.csv` export, `A4 PDF` export, direct `A4` printing, and WhatsApp PDF report sharing) |
| `staff.html` | `staff` | Employee management, 7 job presets, audit log & 63-permission console across 12 groups |
| `settings.html` | `settings` *(core)* | System settings (store info, tax, login mode, invoice studio, and database backups/restore hub) |
| `profile.html` | `profile` *(core)* | Personal profile and per-user desktop preferences |
| `receipt.html` | `receipt` *(core)* | Thermal 80mm & A4 invoice preview, print, and WhatsApp sharing |

---

## Backend Architecture (10 Domain Mixins, 181 Public Methods)

`app/api.py` composes 10 specialized domain mixins:

1. `app/api_common.py` — Shared `_STATE`, money/format helpers, PDF 1.4 generator, Win32 clipboard (`CF_HDROP`), and `customer_ledger` helpers
2. `app/api_auth.py` (`AuthSettingsMixin`) — Login modes, users, 63 permissions/presets/audit, settings & backups
3. `app/api_owner.py` (`OwnerMixin`) — Owner auth, recovery key, module registry CRUD/cloning, 5 business profiles, custom labels, fresh DB builder & audit log
4. `app/api_inventory.py` (`InventoryMixin`) — Categories, products, serials, stock adjustments & cost history
5. `app/api_customers.py` (`CustomersMixin`) — Customer CRM, debt summary, ledger history & payment vouchers
6. `app/api_installments.py` (`InstallmentsMixin`) — Installment contracts, schedules, collections, alerts & WhatsApp reminders
7. `app/api_purchases.py` (`PurchasesMixin`) — Suppliers, purchase orders, purchase invoices (WAC + Landed Cost + VAT/WHT), purchase returns, supplier payments & AP aging
8. `app/api_accounting.py` (`AccountingMixin`) — Chart of Accounts (CRUD + Drag-and-Drop `account_move` + guarded `account_delete`), Journal Entries, Treasuries & Transfers, Expenses & Cost Centers, single-run Opening Balance Wizard, Fiscal Years/Periods, General Ledger, Trial Balance, Income Statement, Balance Sheet & Tax Report
9. `app/api_sales.py` (`SalesMixin`) & `app/api_quotes.py` (`QuotesMixin`) — Shifts (incl. Blind Close), POS checkout, B2B quotations, returns, modifications & WhatsApp PDF sharing
10. `app/api_services.py` (`ServicesMixin`) & `app/api_reports.py` (`ReportsMixin`) — Repairs, used device purchases, daily/monthly reports, `report_comprehensive`, `report_export_excel`, `report_export_pdf` & `whatsapp_send_report`

Supporting modules:
- `app/erp_hooks.py` — Loosely coupled Plug-and-Play hooks (`is_module_active`, `record_wac_and_cost_history`, `reverse_wac_on_purchase_return`, `post_journal_entry`, `reverse_journal_entry`, `rebuild_all_account_balances`, `on_sale_created`, `on_sale_returned`, `on_customer_payment_created`, `on_customer_payment_deleted`, `on_installment_created`, `on_installment_paid`, `on_installment_cancelled`, `on_purchase_posted`, `on_purchase_returned`, `on_supplier_payment_created`, `on_supplier_payment_deleted`, `on_repair_delivered`, `on_used_purchased`, `on_stock_adjusted`, `on_shift_closed`).
- `app/permissions.py` — Canonical **63-permission registry** across **12 groups** and **7 role presets**.
- `app/modules_map.py` — Server-side `API_MODULE_MAP` (181 methods), `CORE_METHODS`, and `MODULE_REQUIRES`.
- `app/profiles.py` — 5 built-in business profiles including `enterprise_erp`.
- `app/fresh_db.py` — Atomic per-profile clean database builder (`build_fresh_profile_db`).


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

### تحديث معاينة ومقارنة Excel وحوار الحفظ الأصلي (2026-11-22)
- **شاشة معاينة وتحديد قبل التصدير (`excel_export_preview`):** عند الضغط على «تصدير Excel» في أي قسم تُفتح نافذة `#tz-excel-studio-modal` لعرض البيانات والبحث وتحديد الصفوف والأعمدة المطلوب تصديرها فقط (`selected_indices`, `selected_columns`).
- **شاشة معاينة ومقارنة قبل الاستيراد (`excel_import_preview`):** تحليل ملف `.xlsx`/`.csv` دون المساس بقاعدة البيانات ومقارنة كل صف بالسجل الحالي (`جديد` / `تعديل ومقارنة: القديم ← الجديد` / `مطابق` / `خطأ`) مع إمكانية الفلترة وتحديد الصفوف المراد استيرادها فقط (`selected_indices`).
- **حوار الحفظ الأصلي في ويندوز (Save As Dialog):** حفظ مرجع نافذة `pywebview` في `_STATE["window"]` بملف `app/main.py` واستدعاء `window.create_file_dialog(SAVE)` عبر `_save_xlsx_with_dialog` عند التصدير أو تحميل القالب لاختيار مكان واسم الملف مباشرةً.
- **الاختبارات:** تحديث `app/selfcheck.py` ليصل إلى `304/304` فحصاً ناجحاً (`189` دالة في `modules_map.py` و`166` دالة في العقد).
