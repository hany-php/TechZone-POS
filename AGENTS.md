# TechZone POS & Shop OS — AI Agent Source of Truth (AGENTS.md)

> **Mandatory Update Rule:** Any change, addition, or deletion in the project (logic, DB schema, API, or frontend) MUST be documented in `AGENTS.md` and `README.md` in the same commit — update the affected section and append an entry to `## 8. Changelog` (newest first). Historical changelog entries prior to today are archived in [`CHANGELOG_ARCHIVE.md`](CHANGELOG_ARCHIVE.md).

---

## 1. Project Overview & Mandatory Architectural Rules

**TechZone POS & ERP** is an offline-first retail, B2B sales, inventory, procurement (`purchases`), double-entry accounting (`accounting`), installment financing (`installments`), repair workshop (`repair`), and comprehensive financial analytics (`reports`) operating system tailored specifically for Egyptian technology shops, service centers, and general businesses.
- **Language & Direction:** Native Arabic UI (`dir="rtl"`), supporting both Light and Dark modes synchronized across desktop and floating windows.
- **Market Fit:** Egyptian Pound (`LE` / `ج.م`), optional 14% VAT toggle, 1%/3% Withholding Tax (`WHT` / ضريبة الخصم والإضافة) on supplier bills, localized payment methods (Cash, InstaPay, Vodafone Cash, Bank Transfer), and installment customer debt ledgers.
- **Form Factor:** Single maximized `pywebview` desktop window hosting a hybrid desktop environment (**TechZone OS — Windows 11 + macOS blend**) with multi-window floating iframes, widgets, Start menu, and dock.
- **Zero Cloud / Zero Runtime Network:** 100% offline. All fonts, icons, and assets are local (`web/fonts/`). No external runtime JS frameworks or cloud dependencies.

### ⚠️ MANDATORY CONDITION FOR ALL AI MODELS: Modular Plug-and-Play Architecture (هندسة الأقسام المعزولة)

**Every AI agent or developer working on this repository now or in the future MUST strictly enforce the Modular Plug-and-Play (Zero-Overhead Isolation) architecture whenever creating, modifying, adding, or deleting any module:**

1. **Zero-Overhead Isolation When Disabled:**
   - Every section/module (`pos`, `sales_quotes`, `inventory`, `customers`, `installments`, `purchases`, `accounting`, `history`, `repair`, `buy_used`, `reports`, `staff`, or any future module) MUST be an isolated, toggleable Plug-and-Play unit managed via `owner.html` (`modules` table).
   - Disabling any module MUST leave **zero database overhead, zero background hook queries, and zero UI errors** on POS or any other active module.
   - All cross-module hooks in `app/erp_hooks.py` MUST check `if not is_module_active(api, conn, "accounting"): return None` (using the `O(1)` in-memory cache `api._module_enabled()`) on their very first line before executing any SQL query.
2. **Mandatory Registration (`DEFAULT_MODULES` + `API_MODULE_MAP`):**
   - Any added or modified module or endpoint MUST be registered in `DEFAULT_MODULES` (`app/db.py`) and mapped in `API_MODULE_MAP` (`app/modules_map.py`). `Api.call()` blocks any call to a disabled module on the server, even for `admin`.
   - Cross-module reporting (`report_comprehensive` in `app/api_reports.py`) MUST check `erp_hooks.is_module_active(self, conn, "<module>")` before querying optional module tables so `reports` works seamlessly whether `purchases` or `accounting` is enabled or disabled.
3. **Separated Invoice Revenue vs. Perpetual Inventory COGS Journal Entries:**
   - In `app/erp_hooks.py`, operational sales (`on_sale_created`), sales returns (`on_sale_returned`), standalone installments (`on_installment_created`), and delivered repairs (`on_repair_delivered`) MUST post **two separate journal entries**:
     1. **Primary Financial Entry (`source_table='sales'`, etc.):** Records the exact invoice total (`total_debit == total_credit == sale.total`) so the General Journal displays the true invoice value.
     2. **Perpetual Inventory Cost Entry (`source_table='sales_cogs'`, etc.):** Separately records `COGS (5101) -> Merchandise Inventory (1105)` at historical weighted-average cost (`cost_unit`).

---

## 2. Documentation Map (Read Before You Code)

Detailed technical specifications are modularized in the `docs/` directory:

| Document | Purpose | Language |
|---|---|---|
| [`docs/README.md`](docs/README.md) | Documentation index and overview | Arabic |
| [`docs/PRD.md`](docs/PRD.md) | Product requirements, personas, scope, and page functional specs | Arabic |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phased roadmap, quality gates, and milestone checklists | Arabic |
| [`docs/IMPLEMENTATION-PLAN.md`](docs/IMPLEMENTATION-PLAN.md) | Step-by-step technical plan for security, shop features & refactoring | Arabic |
| [`docs/OWNER-CONTROL-PLAN.md`](docs/OWNER-CONTROL-PLAN.md) | Owner mode, module registry, business profiles & recovery key implementation plan | English |
| [`docs/OPEN-QUESTIONS.md`](docs/OPEN-QUESTIONS.md) | Pending architectural questions and design decisions | Arabic |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture, Modular Plug-and-Play rules, 10 mixins (181 methods), 19 pages | English |
| [`docs/DATA-MODEL.md`](docs/DATA-MODEL.md) | 52 tables schema, minor-unit money rules, and 63-permission matrix in 12 groups | English |
| [`docs/STACK.md`](docs/STACK.md) | Pinned runtime stack, versions, and upgrade policies | English |
| [`docs/CODING-STANDARDS.md`](docs/CODING-STANDARDS.md) | Modular Plug-and-Play coding standards, SQL guidelines, money formatting & RTL rules | English |
| [`docs/TESTING.md`](docs/TESTING.md) | Selfcheck automation (293 checks), test gates, and manual QA | English |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat model, PBKDF2 hashing, lockout rules, and Egyptian PDPL | English |
| [`docs/DESIGN-SYSTEM.md`](docs/DESIGN-SYSTEM.md) | TechZone OS color tokens, Arabic typography, layout, and invoice specs | English |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Standalone .exe compilation (PyInstaller), backup routines, and setup | English |
| [`docs/adr/`](docs/adr/) | Architectural Decision Records (ADRs) | English |

---

## 3. Technology Stack

- **Runtime:** Python 3.13.5 (64-bit)
- **Database:** Standard library `sqlite3` in `WAL` mode (schema in `app/db.py`, 52 tables, DB file in `data/shop.db`)
- **Desktop Window:** `pywebview` 6.2.1 powered by Microsoft Edge WebView2 Evergreen
- **System Integration:** Windows `ctypes.windll` for clipboard `CF_HDROP` binary file copies (direct WhatsApp desktop PDF pasting for invoices, quotes, and financial reports)
- **Native Offline Exporters:** Built-in PDF 1.4 generator (`_jpeg_to_pdf_bytes`) and native multi-sheet OpenXML `.xlsx` generator (`_build_native_xlsx_bytes` in `app/api_reports.py`) requiring zero third-party packages
- **Frontend:** Semantic HTML5 (19 pages), Vanilla ES6+ JavaScript, pre-compiled Tailwind CSS (`web/app.css` committed to Git)
- **Fonts & Icons:** Local 23 `.woff2` files in `web/fonts/` (Cairo, IBM Plex Sans Arabic, Material Icons)
- **Packaging:** PyInstaller single-file windowed binary (`build-exe.bat` → `dist/TechZone.exe`)

---

## 4. Key Commands

| Task | Command |
|---|---|
| Launch Dev Application | `python app/main.py` |
| Execute Automated Selfcheck (293 tests) | `python app/selfcheck.py` |
| Recompile Tailwind CSS | `npx tailwindcss -i web/tailwind.css -o web/app.css --minify` |
| Build Standalone EXE | Double-click `build-exe.bat` or run `.\build-exe.bat` |
| Build Windows Setup Installer | Double-click `build-installer.bat` or run `.\build-installer.bat` |
| Push Updates to GitHub | Double-click `push-github.bat` or run `.\push-github.bat` |

---

## 5. System Architecture & Directory Tree

```
project001/
├── app/
│   ├── main.py             # Entry point: pywebview window setup, branding & session cleanup on close
│   ├── api.py              # Facade Api class composing 10 domain mixins (181 public methods) + O(1) module cache
│   ├── api_common.py       # Shared state, money/format helpers, phone normalization, PDF/WhatsApp Win32 & ledger helpers
│   ├── erp_hooks.py        # Modular Plug-and-Play hooks: WAC cost engine, separated Revenue vs. COGS double-entry posting
│   ├── api_auth.py         # AuthSettingsMixin: login, users, permissions/presets/audit, profile & settings/backups
│   ├── api_owner.py        # OwnerMixin: owner auth, module registry, profiles, labels & audit log
│   ├── permissions.py      # Canonical 63-permission registry, 12 groups, 7 role presets & strict cashier baseline
│   ├── modules_map.py      # API_MODULE_MAP (181 methods), CORE_METHODS & MODULE_REQUIRES server guard map
│   ├── profiles.py         # DEFAULT_BUSINESS_PROFILES (5 profiles incl. enterprise_erp) & DEFAULT_LABELS/LABEL_KEYS
│   ├── fresh_db.py         # Clean per-profile DB builder with selective data carry-over & safety backup
│   ├── api_inventory.py    # InventoryMixin: categories, products, serials & stock adjustments
│   ├── api_customers.py    # CustomersMixin: customer CRM, debt summary, ledger history & vouchers
│   ├── api_installments.py # InstallmentsMixin: installment contracts, schedules, collections, alerts & WhatsApp reminders
│   ├── api_purchases.py    # PurchasesMixin: suppliers, POs, purchase bills (WAC + Landed Cost + VAT/WHT), returns, vouchers & AP aging
│   ├── api_accounting.py   # AccountingMixin: COA (CRUD + Drag & Drop account_move + account_delete), journal entries, treasuries, expenses, single-run opening wizard, financial statements & tax report
│   ├── api_sales.py        # SalesMixin: shifts (incl. Blind Close), POS checkout, returns, modifications & WhatsApp invoice
│   ├── api_quotes.py       # QuotesMixin: B2B quotations, A4 invoices & conversion to sales
│   ├── api_services.py     # ServicesMixin: repair workshop lifecycle & used device purchases
│   ├── api_reports.py      # ReportsMixin: daily/monthly, report_comprehensive, multi-sheet .xlsx/.csv export, A4 PDF export & WhatsApp report sharing
│   ├── db.py               # SQLite schema (52 tables), connection wrapper, seed (15 modules, 38 COA accounts), migration & backups
│   └── selfcheck.py        # Comprehensive automated regression suite (293 checks)
├── web/
│   ├── index.html          # Smart login screen (auto role/user detection by PIN, force-PIN & owner recovery)
│   ├── owner.html          # Hidden owner control panel (setup, login, recovery, modules, profiles, labels, security & audit)
│   ├── desktop.html        # TechZone OS hybrid desktop shell (dock, start menu, iframes)
│   ├── pos.html            # High-speed retail POS cashier (with global hardware barcode listener)
│   ├── sales_quotes.html   # Official B2B A4 sales invoices & price quotations
│   ├── purchases.html      # Purchases, Purchase Orders, Returns, Suppliers, Vouchers & AP Aging
│   ├── accounting.html     # Double-Entry Accounting: Overview, Expenses, Treasuries, COA (Add/Edit/Delete + Drag & Drop), Journal, Statements & universal A4 printing
│   ├── inventory.html      # Product catalog, stock tracking, serial numbers & stocktake modal
│   ├── customers.html      # Customer database, debt totals, and ledger shortcuts
│   ├── customer_details.html # Customer debt statements, installment contracts & payment vouchers
│   ├── installments.html   # Installment contracts, pre-sale calculator, collection & overdue tracking
│   ├── repair.html         # Maintenance lifecycle ticketing & spare parts
│   ├── buy_used.html       # Used device purchasing, trade-ins, and anti-theft IDs
│   ├── history.html        # Operations history, returns, and multi-filter ledger
│   ├── reports.html        # Comprehensive Financial & Operational Analytics Hub (5 tabs + .xlsx, .csv, A4 PDF, Print & WhatsApp)
│   ├── staff.html          # Employee administration, 7 job presets, perm audit log & 63-permission console
│   ├── profile.html        # Employee personal profile, PIN, and desktop theme setup
│   ├── settings.html       # Store info, tax toggle, login mode, invoice studio & database backups/restore hub
│   ├── receipt.html        # Thermal 80mm & A4 preview and WhatsApp sharing
│   ├── app.js              # Bridge api() caller, permissions, labels t(), and invoice builder
│   ├── app.css             # Pre-compiled Tailwind CSS bundle
│   └── fonts/              # 23 local WOFF2 font files
└── data/
    ├── shop.db             # Operating SQLite database (git-ignored)
    ├── backups/            # Automated & manual ACID SQLite snapshots
    ├── receipts/           # Generated PDF invoices and vouchers
    └── reports/            # Generated Excel (.xlsx) and PDF financial reports
```

---

## 6. Permissions Matrix (63 Granular Keys in 12 Groups)

Defined in `app/permissions.py`:
1. **POS & Shifts (`pos`, 9):** `pos_sell`, `shift_manage`, `shift_summary_view`, `pos_item_discount`, `pos_invoice_discount`, `pos_price`, `pos_credit_sale`, `pos_whatsapp`, `pos_categories_manage`.
2. **History, Returns & Receipts (`history`, 6):** `receipt_view`, `history_view_own`, `history_view_all`, `sales_return_own`, `sales_return`, `sales_post_discount`.
3. **B2B Sales & Quotes (`quotes`, 4):** `quotes_view`, `quotes_create_edit`, `quotes_convert`, `quotes_cancel_delete`.
4. **Customers & Debt (`customers`, 6):** `customers_quick_pick`, `customers_view`, `customers_debt_view`, `customers_edit`, `customers_payment`, `customers_delete`.
5. **Installments (`installments`, 4):** `installments_view`, `installments_collect`, `installments_create`, `installments_cancel`.
6. **Inventory & Costs (`inventory`, 5):** `inventory_view`, `inventory_edit`, `inventory_adjust`, `serials_view`, `cost_view`.
7. **Purchases & Suppliers (`purchases`, 6):** `purchases_view`, `purchases_create_edit`, `purchases_return`, `suppliers_view`, `suppliers_manage`, `purchases_payment`.
8. **Accounting & Finance (`accounting`, 8):** `accounting_coa_view`, `accounting_journal_view`, `accounting_journal_manual`, `accounting_statements_view`, `treasury_view`, `treasury_transfer`, `expenses_view`, `expenses_manage`.
9. **Repair Workshop (`repair`, 4):** `repair_view`, `repair_create`, `repair_edit`, `repair_delete`.
10. **Used Devices (`buy_used`, 2):** `used_view`, `used_manage`.
11. **Reports (`reports`, 4):** `reports_sales_view`, `reports_profit_view`, `reports_shifts_view`, `reports_movements_view`.
12. **Staff, Settings & Backups (`admin`, 5):** `staff_view`, `staff_manage`, `settings_view_edit`, `templates_manage`, `backups_manage`.

---

## 7. Non-Negotiable Engineering Rules

1. **Modular Plug-and-Play Isolation:** Every module must be self-contained, registered in `DEFAULT_MODULES` and `API_MODULE_MAP`, and guarded by `erp_hooks.is_module_active` so disabled modules incur zero runtime or SQL overhead.
2. **All Money in Minor Units:** Always store and compute currency as `INTEGER` minor units (`1 LE = 100 qirsh`). Never use floating-point types for financial transactions in the database.
3. **100% Parameterized SQL:** Never concatenate or interpolate raw user strings into SQL queries. Always use `?` placeholders.
4. **Server-Side Authorization:** Never rely on frontend JavaScript checks for access control. Always enforce `_perm(key)` inside `app/api*.py`.
5. **Offline Purity:** Never introduce external network calls, CDNs, or runtime cloud dependencies.
6. **No Bundlers / No Heavy Frameworks:** Vanilla JavaScript and pre-compiled CSS only.
7. **Selfcheck Verification:** Every change must maintain all passing tests in `python app/selfcheck.py` (currently **293 checks**).
8. **Commit Documentation:** Always update `AGENTS.md`, `README.md`, and `docs/*.md` in the same commit.

---

## 8. Changelog

### 2026-11-25 — Inventory Bulk Select & Delete for Products & Categories (`app/api_inventory.py`, `app/modules_map.py`, `web/inventory.html`, `web/app.css`)
- **Bulk Delete Backend (`app/api_inventory.py`, `app/modules_map.py`)**:
  1. Added `products_bulk_delete(ids)` (soft-deleting active products atomically with `activity_audit_log` summary while preserving historical sales/invoices) and `categories_bulk_delete(ids, detach_products=False)` (deleting empty categories by default with skipped reporting, or unlinking active products to `category_id=NULL` before deleting when `detach_products=True`), both gated by `inventory_edit` and mapped under `"inventory"` in `API_MODULE_MAP`.
- **Inventory Bulk Selection UI (`web/inventory.html`, `web/app.css`)**:
  1. Added category search (`#cat-search`), multi-select checkboxes on category chips, quick actions (`تحديد المعروض`, `تحديد الفارغة (0)`, `إلغاء التحديد`, `حذف المحدد`), and confirmation modal `#modal-bulk-confirm` with optional product detachment (`#bulk-detach-chk`).
  2. Added product table checkbox column (`#prod-sel-all`, persistent cross-page `SELECTED_PRODS`), `#prod-bulk-bar` with "Select all filtered results" (`#btn-prod-sel-filtered`) and bulk delete (`#btn-prod-bulk-del`), plus `tzImgSrc` preview fix in `openEdit()`.

### 2026-11-25 — GitHub Auto-Releases on Push to `main` & Offline-Safe In-App Auto-Updater (`app/version.py`, `app/api_updater.py`, `.github/workflows/build-installer.yml`, `web/desktop.html`, `web/settings.html`)
- **Automated GitHub Releases Pipeline (`.github/workflows/build-installer.yml`, `version.txt`, `TechZone.spec`, `build-installer-version.bat`)**:
  1. Configured GitHub Actions (`Auto Release & Build TechZone Installer`) to trigger automatically on every `push` to `main` (in addition to `v*` tags and manual `workflow_dispatch` with `patch`/`minor`/`major` or custom version override), using `concurrency` to queue sequential releases cleanly.
  2. Automatically reads the highest existing SemVer release/tag (starting from `v1.0.0` → `v1.0.1` → `v1.0.2`, with optional `[minor]` / `[major]` commit keywords), injects the resolved version into `version.txt` and `app/version.py`, runs `python app/selfcheck.py`, builds `TechZone.exe` (bundling `version.txt`), builds `TechZone-Setup-v<version>.exe`, generates `SHA256SUMS.txt`, and publishes a GitHub Release titled `TechZone V<version>` with auto-generated release notes and all 3 assets.
- **Offline-Safe Auto-Updater Backend (`app/version.py`, `app/api_updater.py`, `app/api.py`, `app/modules_map.py`, `app/main.py`, `app/db.py`, `app/api_auth.py`, `installer/TechZone.iss`)**:
  1. Added `UpdaterMixin` (`app_version_info`, `update_check`, `update_status`, `update_download`, `update_install`) registered in `CORE_METHODS` with zero impact when offline (silent 6s check, zero third-party packages).
  2. Enforces HTTPS-only GitHub download host allowlist, verifies `SHA256SUMS.txt` integrity before installing, creates an automatic pre-update SQLite backup (`db.backup_database("before_update")`), supports silent in-place Inno Setup upgrade (`/SILENT /FORCECLOSEAPPLICATIONS /DIR="..."` preserving `data/`) and portable `TechZone.exe` swap launched invisibly via `wscript.exe` `.vbs` wrapper (zero black terminal window on Windows 11), and uses `_STATE["force_exit"]` + `_STATE["shutdown_cb"]` (`request_app_shutdown()` in `app/main.py`) so the running `__main__` process exits cleanly out of System Tray before relaunching the upgraded executable.
  3. Added `auto_update_check` setting (default `'1'`) and RBAC gating (`settings_view_edit` required for download/install).
- **Arabic Upgrade Modal, Title/Topbar Version Badge & Continuous Background Update Watcher (`app/main.py`, `web/desktop.html`, `web/settings.html`)**:
  1. Added version display (`v<APP_VERSION>`) directly in the native Windows window title (`app_window_title()` in `app/main.py`), System Tray tooltip, desktop top menu bar (`#os-topbar-version` beside store logo/name), and Start menu (`#start-app-version`).
  2. Added `TZOS.checkUpdatesInBackground` in `web/desktop.html` running silently on launch (2.5s), periodically every 10 minutes while online, and immediately upon network reconnect (`window.addEventListener('online')`), automatically popping up `#update-available-modal` ("هناك إصدار جديد متاح للترقية!", pinned at `z-index: 2147483640`) with release notes, live download progress bar, one-click upgrade, and persistent `#top-update-pill` topbar badge.
  3. Added the Software Updates card in `web/settings.html` (`#st-app-version`, `#st-auto-update-check`, `#btn-check-updates-now`) and automated checks in `app/selfcheck.py`.
- **Bundled Fonts/Icons & Frozen EXE Product Images Fix (`.gitignore`, `app/api_owner.py`, `app/api_auth.py`, `web/app.js`, `web/index.html`, `.github/workflows/build-installer.yml`)**:
  1. Removed `web/fonts/` from `.gitignore` so all 23 local `.woff2` files (Material Icons + Cairo + IBM Plex Sans Arabic + Space Grotesk) are committed to Git and bundled into every GitHub Actions `TechZone.exe` release (with a CI pre-build verification guard).
  2. Exposed `images_base_url` (`db.images_dir().resolve().as_uri()`) in `ui_config()` and updated `tzImgSrc()` in `web/app.js` to resolve `data/images/...` reliably when running from PyInstaller `--onefile` (`_MEIPASS`), plus dynamic `#login-app-version` on `web/index.html`.

### 2026-11-18 — Accounting Fixes (Separated Sale/COGS Entries, Single-Run Opening Wizard, COA Drag-and-Drop, Universal Print), Comprehensive Financial Reports Hub (Excel/PDF/WhatsApp), & Mandatory Plug-and-Play Documentation (`main`)
- **Separated Financial Invoice vs. COGS Journal Entries (`app/erp_hooks.py`, `web/accounting.html`)**:
  1. Fixed the issue where auto-posted sale journal entries combined both the sale revenue lines and the perpetual inventory `COGS` lines into a single journal entry, causing the entry's displayed `total_debit`/`total_credit` to exceed the actual sale invoice total.
  2. Updated `on_sale_created`, `on_sale_returned`, `on_installment_created`, and `on_repair_delivered` in `app/erp_hooks.py` to generate two distinct journal entries: (a) the primary invoice entry (`source_table='sales'`, etc.) whose total equals the exact invoice total (`sale.total`), and (b) a separate perpetual inventory cost entry (`source_table='sales_cogs'`, etc.) for `COGS -> Inventory`.
  3. Added a source filter in `web/accounting.html` (`كل القيود`, `قيود الفواتير والسندات المالية فقط`, `قيود تكلفة البضاعة المباعة COGS فقط`, `القيود اليدوية`, `القيود الافتتاحية`) plus a `#modal-je-view` modal to inspect and print any individual journal entry on A4.
- **Single-Run Opening Balance Wizard Guard (`app/api_accounting.py`, `web/accounting.html`)**:
  1. Updated `accounting_dashboard` and `accounting_opening_preview` to detect whether a posted opening entry (`kind='opening' AND status='posted'`) already exists (`has_opening_entry`, `opening_entry`).
  2. Updated `accounting_opening_apply` to strictly reject duplicate execution if a posted opening entry exists, and updated `web/accounting.html` to show a verified badge (`تم الترصيد الافتتاحي (JE-...)`), display the existing entry details inside the wizard modal, and disable/hide the generate button so clicking it never creates duplicate entries.
- **Chart of Accounts Full CRUD + Drag-and-Drop Reparenting & Universal Printing (`app/api_accounting.py`, `app/erp_hooks.py`, `app/modules_map.py`, `web/accounting.html`)**:
  1. Added `account_delete(id)` (allowing deletion only when the account is non-system, has zero child accounts, zero journal movements, and is not linked to an active treasury/expense category/posting rule) and `account_move(account_id, new_parent_id)` (Drag-and-Drop reparenting onto any group account with circular-reference protection, subtree level/type propagation, and `rebuild_all_account_balances(conn)`).
  2. Enhanced `web/accounting.html` with `#modal-account-form` (Add/Edit account), `+ فرعي`, `كشف حساب`, `تعديل`, and conditional `حذف` buttons, HTML5 Drag-and-Drop (`draggable="true"`) on COA rows, General Ledger account selector in `pane-statements`, and `printAccountingSection()` A4 print buttons in all 6 tabs and modals.
- **Comprehensive Financial & Operational Reports Hub (`app/api_reports.py`, `app/modules_map.py`, `web/reports.html`)**:
  1. Implemented `report_comprehensive(date_from, date_to)` in `app/api_reports.py` (with `erp_hooks.is_module_active` modular checks) returning full breakdowns for: Detailed P&L + Invoice-by-Invoice Profitability + Item-by-Item Profitability + Expenses by Category (`pnl`), Customer Debt + Active/Overdue Installments + Payment Vouchers (`receivables`), Supplier Payables + Purchase Bills + Supplier Payments (`payables`), Inflows/Outflows + Treasuries + Shifts (`cashflow`), and Inventory Cost/Retail Valuation + Low Stock + Movements (`inventory`).
  2. Implemented `report_export_excel` (generating a native 5-sheet OpenXML `.xlsx` workbook via `_build_native_xlsx_bytes` with zero external dependencies + UTF-8 BOM `.csv` saved to `data/reports/`), `report_export_pdf` (generating a standard A4 PDF in `data/reports/`), and `whatsapp_send_report` (gated by admin `whatsapp_send_enabled`, copying the A4 PDF to Windows clipboard via `_win32_copy_pdf_to_clipboard` and launching WhatsApp with a full financial summary).
  3. Rebuilt `web/reports.html` into a 5-tab Financial & Operational Analytics Center with instant search filters and top action buttons for **Print A4**, **Export Excel (`.xlsx`)**, **Export CSV**, **Export PDF (`A4`)**, and **Send to WhatsApp PDF**.
- **Close Button (X) Behavior & System Tray Background Mode (`app/main.py`, `app/db.py`, `app/api_auth.py`, `web/settings.html`)**:
  1. Added `close_exit_app` setting (default `'0'`) and `#st-close-exit-app` toggle in `web/settings.html` ("إغلاق البرنامج نهائياً عند الضغط على علامة (X) أعلى النافذة").
  2. Updated `app/main.py` with Windows `.NET WinForms` `NotifyIcon` (System Tray icon next to the clock with right-click Arabic menu "فتح نافذة البرنامج" / "إغلاق البرنامج نهائياً" and click/double-click restore): when `close_exit_app='0'` (default), clicking `X` hides the window to the System Tray and keeps the app running; when `close_exit_app='1'`, clicking `X` closes and exits the application completely.
- **Per-User Desktop & Taskbar Icon Visibility Control (`web/profile.html`, `web/desktop.html`, `app/api_auth.py`)**:
  1. Added `#pf-icons-control-section` in `web/profile.html` allowing each user to show/hide individual icons on their Desktop (`_hidden_desktop`) and bottom Taskbar (`_hidden_taskbar`) with instant live sync (`TZOS.applyUserIconPrefs`) stored strictly in that user's `users.desktop_layout` JSON without affecting other users or global module state.
- **Complete ERP (`purchases` + `accounting`) Foundation & Documentation (`app/db.py`, `app/api_purchases.py`, `app/api_accounting.py`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/*.md`, `app/selfcheck.py`)**:
  1. Enshrined the **Modular Plug-and-Play (Zero-Overhead Isolation)** rule across `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DATA-MODEL.md`, and `docs/CODING-STANDARDS.md`.
  2. Added 10 new automated checks in `app/selfcheck.py` verifying separated sale/COGS entries, duplicate opening balance rejection, COA CRUD & Drag-and-Drop `account_move`/`account_delete`, and `report_comprehensive`/`report_export_excel`/`report_export_pdf`/`whatsapp_send_report` (`293/293` checks passing, `contract ok`).

### 2026-11-17 — Inventory Display Fix & Stocktake Report (`main`)
- **Inventory Blank Page Root-Cause Fix (`web/inventory.html`)**:
  1. Fixed fatal `SyntaxError: Identifier 'CAN_EDIT' has already been declared` in `web/inventory.html`.
  2. Added one-click quick stocktake filter pills (`الكل`, `الموجود (> 0)`, `مخزون منخفض`, `المنتهي (0)`) and printable A4 stocktake modal (`#modal-stocktake`).

### 2026-11-17 — Granular RBAC Overhaul (49 -> 63 Permissions, Blind Close, Zero-Leak Hardening & Staff Console) (`main`)
- **Canonical Permission Registry & Schema (`app/permissions.py`, `app/db.py`, `app/fresh_db.py`)**:
  1. Defined granular permissions across groups, `STRICT_CASHIER_PERMS`, and **7 built-in job presets** (`cashier_strict`, `senior_cashier`, `sales_b2b`, `inventory_clerk`, `technician`, `accountant`, `store_manager`).
  2. Implemented **Blind Close (الجرد الأعمى)** when `shift_summary_view=False` and name/phone-only customer quick-pick.


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
- **تنظيف رقم الإصدار في المثبّت (`MyAppVersionClean` في `installer/TechZone.iss`):** تنظيف قيمة `MyAppVersion` تلقائياً عبر ISPP (إزالة البادئة `v` واللواحق `-beta`/`+build` وعدم إضافة `.0` زائدة لإصدارات الـ 4 أجزاء) لضمان نجاح `VersionInfoVersion` على GitHub Actions والمحلي.
- **دعم اللغتين العربية والإنجليزية (`web/i18n.js`, `users.lang`, `applyLanguageEverywhere`):** محرك ترجمة ثنائي الاتجاه (`RTL`/`LTR`) معزول بدون اعتماديات خارجية، يتيح تبديل اللغة من شاشة الدخول (`index.html`) أو من إعدادات الملف الشخصي (`profile.html`) أو الشريط العلوي (`desktop.html`) مع حفظ اللغة بشكل مستقل لكل مستخدم في `users.lang`.
- **إصلاح تموضع قائمة ابدأ في وضع `LTR` وأزرار اللغة في شاشة الدخول وتوسيع قاموس الترجمة (`web/desktop.html`, `web/index.html`, `web/i18n.js`):** عكس موضع `#os-start-menu` إلى اليسار (`left: 16px`) و`#os-widgets` إلى اليمين وتحديث تنسيق الساعة (`en-US`) في الوضع الإنجليزي، تفعيل أزرار اللغة في شاشة الدخول (`EXPLICIT_LOGIN_LANG`)، وتوسيع قاموس `web/i18n.js` ليشمل قائمة ابدأ وشريط المهام وجميع الشاشات.
- **قسم إدارة الترجمة وقاموس النظام (`translations`, `translations_scan_project`, `translations_save`, `translations_map`) وعكس أيقونات سطح المكتب (`LTR`/`RTL`):** تبويب «الترجمة واللغات» في `web/settings.html` يضم جدولاً مركزياً لكل كلمات المشروع مع إمكانية التعديل والإضافة والفحص الآلي وتطبيق الترجمات المخصصة فوراً عبر `web/i18n.js`، مع قلب اتجاه أيقونات سطح المكتب تلقائياً إلى اليسار في الإنجليزية وإلى اليمين في العربية.
- **محرك الاستيراد والتصدير الشامل لملفات Excel (`app/api_excel.py`: `excel_entities_list`, `excel_template`, `excel_export`, `excel_import`):** وحدة معزولة (`Modular Plug-and-Play`) بدون مكتبات خارجية لتصدير واستيراد `.xlsx`/`.csv` للمنتجات والتصنيفات والعملاء والموردين وشجرة الحسابات وقاموس الترجمة وتصدير المبيعات والمصروفات والصيانة والأقساط، متاحة في تبويب «استيراد وتصدير Excel» في `web/settings.html` ومباشرة داخل `web/inventory.html` و`web/customers.html` و`web/purchases.html`.

### تحديث معاينة ومقارنة Excel وحوار الحفظ الأصلي (2026-11-22)
- **شاشة معاينة وتحديد قبل التصدير (`excel_export_preview`):** عند الضغط على «تصدير Excel» في أي قسم تُفتح نافذة `#tz-excel-studio-modal` لعرض البيانات والبحث وتحديد الصفوف والأعمدة المطلوب تصديرها فقط (`selected_indices`, `selected_columns`).
- **شاشة معاينة ومقارنة قبل الاستيراد (`excel_import_preview`):** تحليل ملف `.xlsx`/`.csv` دون المساس بقاعدة البيانات ومقارنة كل صف بالسجل الحالي (`جديد` / `تعديل ومقارنة: القديم ← الجديد` / `مطابق` / `خطأ`) مع إمكانية الفلترة وتحديد الصفوف المراد استيرادها فقط (`selected_indices`).
- **حوار الحفظ الأصلي في ويندوز (Save As Dialog):** حفظ مرجع نافذة `pywebview` في `_STATE["window"]` بملف `app/main.py` واستدعاء `window.create_file_dialog(SAVE)` عبر `_save_xlsx_with_dialog` عند التصدير أو تحميل القالب لاختيار مكان واسم الملف مباشرةً.
- **الاختبارات:** تحديث `app/selfcheck.py` ليصل إلى `304/304` فحصاً ناجحاً (`189` دالة في `modules_map.py` و`166` دالة في العقد).
