# TechZone POS & ERP — Data Model (52 Tables & 63 Permissions)

## Overview

All TechZone data is stored in a single SQLite database at `data/shop.db` running in `WAL` mode (`synchronous=NORMAL`, `foreign_keys=ON`). The schema comprises **52 tables** managed by `app/db.py`, which handles creation, seeding, and non-destructive auto-migration on every startup.

---

## Mandatory Modular Plug-and-Play Data Isolation Rule

Every module's tables are designed for **Zero-Overhead Plug-and-Play Isolation**:
1. Core POS/Inventory tables store historical cost snapshots (`sale_items.cost_unit`, `repair_parts.cost_unit`) directly at transaction time so profit reports remain 100% accurate even if `purchases` or `accounting` is disabled.
2. When `purchases` or `accounting` is disabled via `owner.html`, no writes or queries are executed against their tables (`erp_hooks.is_module_active` returns `False` in `O(1)` time).
3. In `accounting`, sales/returns/installments/repairs create **two separate journal entries** in `journal_entries`:
   - The **Financial Invoice Entry** (`source_table='sales'`, etc.), whose `total_debit` and `total_credit` match the exact invoice `total`.
   - The **Perpetual Inventory Cost Entry** (`source_table='sales_cogs'`, etc.), which records `COGS` vs. `Inventory` separately.

---

## Core & Operational Tables (Tables 1–32)

1. `users` — System accounts, PBKDF2 PIN hashes, JSON permissions cache, `is_active`, `job_preset`, desktop preferences.
2. `categories` — Product categories (with `demo_profile` tag).
3. `products` — Product catalog (`sku`, `name`, `price`, `cost`, `qty`, `min_qty`, `tracked`, `expiry_date`, `demo_profile`).
4. `serials` — Individual serial/IMEI units (`in_stock`, `sold`, `in_repair`, plus `purchase_item_id` link).
5. `shifts` — Cash register shifts (`opening_cash`, `counted_cash`, `expected_cash`, `diff`).
6. `customers` — Customer CRM records with cached `total_purchases`, `credit_total`, `paid_total`, and `debt`.
7. `customer_ledger` — Unified chronological customer receivable ledger (`credit_sale`, `voucher`, `return_credit`, `adjustment`, `installment_charge`, `installment_payment`).
8. `sales` — POS and B2B sales headers (`invoice_no`, `subtotal`, `discount`, `tax`, `total`, `status`).
9. `sale_items` — Line items within a sale, including `cost_unit` snapshot at the moment of sale.
10. `payments` — Split payment lines (`cash`, `wallet`, `credit`, `ref_no`).
11. `customer_payments` — Customer collection vouchers (`RCV-...`).
12. `sale_returns` & 13. `sale_return_items` — Customer return headers and line items.
14. `quotations` & 15. `quotation_items` — B2B price quotations and A4 invoices.
16. `used_device_purchases` — Second-hand device buying records (`USD-...`).
17. `repairs` & 18. `repair_parts` — Maintenance tickets (`RPR-...`) and consumed spare parts (with `cost_unit`).
19. `stock_movements` — Full inventory movement audit trail.
20. `settings` — System-wide key-value settings.
21. `installment_plans`, 22. `installment_items`, 23. `installment_payments` — Scheduled installment financing contracts (`INS-...`) and receipts (`INP-...`).
24. `owner_auth`, 25. `owner_audit_log`, 26. `modules` (15 built-in modules), 27. `ui_labels`, 28. `business_profiles` (5 profiles) — Owner Control & Module Registry tables.
29. `user_permissions`, 30. `permission_roles` (7 job presets), 31. `perm_audit_log` — Granular RBAC tables.
32. `product_cost_history` — Historical log of every Weighted Average Cost (`WAC`) transition (`old_qty`, `old_cost`, `added_qty`, `unit_cost`, `landed_unit_cost`, `new_qty`, `new_wac`).

---

## Purchases & Suppliers Module Tables (`purchases` — Tables 33–41)

33. `suppliers` — Supplier directory (`code`, `name`, `company_name`, `phone`, `tax_reg_no`, `tax_card_no`, `payment_terms_days`, `credit_limit`, `opening_balance`, `total_purchases`, `paid_total`, `balance`).
34. `purchase_orders` & 35. `purchase_order_items` — Purchase orders (`PO-...`) and ordered items before receipt.
36. `purchases` & 37. `purchase_items` — Posted/draft supplier purchase bills (`PUR-...`) with `shipping_cost`, `tax` (14% VAT input), `wht_amount` (1%/3% withholding tax), `landed_unit_cost`, `expiry_date`, and `serials_json`.
38. `purchase_returns` & 39. `purchase_return_items` — Purchase return notes (`PRET-...`) reversing stock, WAC, and supplier balance.
40. `supplier_payments` — Supplier payment vouchers (`SPY-...`) paid from main safe, bank, e-wallet, or active POS drawer.
41. `supplier_ledger` — Chronological Accounts Payable (`AP`) ledger per supplier (`opening`, `purchase_bill`, `payment`, `purchase_return`, `adjustment`).

---

## Double-Entry Accounting Module Tables (`accounting` — Tables 42–52)

42. `accounts` — Hierarchical Chart of Accounts (`code`, `name`, `parent_id`, `level`, `type`, `normal_balance`, `is_group`, `is_system`, `system_role`, `debit_total`, `credit_total`, `balance`, `active`). Seeded with **38 standard Arabic accounts**. Supports full CRUD (`account_save`, `account_delete` when zero movements/children and non-system) and Drag-and-Drop reparenting (`account_move`).
43. `fiscal_years` & 44. `fiscal_periods` — Financial years and monthly periods (`open` / `closed`) with year-end closing to Retained Earnings (`3103`).
45. `journal_entries` — Immutable double-entry journal headers (`entry_no` `JE-YYYY-NNNNN`, `entry_date`, `kind` IN `auto`/`manual`/`opening`/`reversal`/`closing`, `source_module`, `source_table`, `source_id`, `ref`, `memo`, `total_debit`, `total_credit`, `status` IN `posted`/`reversed`).
46. `journal_lines` — Balanced debit/credit lines (`entry_id`, `line_no`, `account_id`, `debit`, `credit`, `cost_center_id`, `party_type`, `party_id`, `memo`).
47. `treasury_accounts` — Financial safes, POS cash drawer, e-wallets, and bank accounts linked 1-to-1 with leaf asset accounts in `accounts`.
48. `treasury_transfers` — Internal liquidity transfers (`TRF-...`) between treasuries/banks.
49. `cost_centers` — Analytical cost centers (Main Showroom, Maintenance Workshop, B2B/Online).
50. `expense_categories` — Operational expense categories mapped to `52xx` expense accounts.
51. `expenses` — Operational expense vouchers (`EXP-...`) auto-posting journal entries.
52. `accounting_posting_rules` — Configurable mapping of 22 operational event roles (`cash_main`, `sales_revenue`, `cogs_sales`, `inventory_merchandise`, `vat_output`, `vat_input`, `wht_payable`, etc.) to `accounts.id`.

---

## Access Control Matrix (63 Granular Permissions in 12 Groups)

Defined in `app/permissions.py`:
- **Groups 1–10 (49 keys):** `pos` (9), `history` (6), `quotes` (4), `customers` (6), `installments` (4), `inventory` (5), `repair` (4), `buy_used` (2), `reports` (4), `admin` (5).
- **Group 11 — Purchases & Suppliers (`purchases`, 6 keys):** `purchases_view`, `purchases_create_edit`, `purchases_return`, `suppliers_view`, `suppliers_manage`, `purchases_payment`.
- **Group 12 — Accounting & Finance (`accounting`, 8 keys):** `accounting_coa_view`, `accounting_journal_view`, `accounting_journal_manual`, `accounting_statements_view`, `treasury_view`, `treasury_transfer`, `expenses_view`, `expenses_manage`.


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
- **قسم إدارة الترجمة وقاموس النظام (`translations`, `translations_scan_project`, `translations_save`, `translations_map`) وعكس أيقونات سطح المكتب (`LTR`/`RTL`):** تبويب «الترجمة واللغات» في `web/settings.html` يضم جدولاً مركزياً لكل كلمات المشروع مع إمكانية التعديل والإضافة والفحص الآلي وتطبيق الترجمات المخصصة فوراً عبر `web/i18n.js`، مع قلب اتجاه أيقونات سطح المكتب تلقائياً إلى اليسار في الإنجليزية وإلى اليمين في العربية.
