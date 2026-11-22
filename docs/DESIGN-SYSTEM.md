# Design System & UI Specifications — TechZone OS

## 1. Design Concept & Philosophy

**TechZone OS** represents a hybrid desktop operating system environment blending the productivity of **Windows 11** (Start Menu, taskbar, system notifications, snapping, clean window borders) with the fluidity of **macOS** (floating dock, subtle translucent glassmorphism, rounded corners, responsive micro-animations).

The user interface is designed natively for **Arabic (Right-to-Left - RTL)** desktop environments, optimized for point-of-sale efficiency, touch terminals, and conventional mouse/keyboard setups in retail shops.


> ⚠️ **Mandatory Rule for All AI Models & Developers (`Modular Plug-and-Play — Zero-Overhead Isolation` & Full Documentation):**
> 1. **Modular Plug-and-Play Isolation**: Any creation, modification, addition, or deletion of a module now or in the future MUST strictly follow the isolated Plug-and-Play architecture (`DEFAULT_MODULES` in `app/db.py`, `API_MODULE_MAP` in `app/modules_map.py`, and `erp_hooks.is_module_active` runtime guards so disabled modules incur zero SQL/CPU overhead).
> 2. **Mandatory Documentation Sync**: Every code, schema, setting, or UI change MUST be documented in the same turn/commit across `AGENTS.md`, `CLAUDE.md`, `README.md`, and `docs/*.md`.

---

## 2. Color Tokens & Theme Architecture

The system supports synchronized dual-theme modes (Light / Dark) across the parent desktop shell and all child window `iframes`.

### 2.1 Base Neutrals & Surfaces

| Token | Light Theme | Dark Theme | Purpose |
|---|---|---|---|
| `bg-main` | `#f8fafc` (Slate 50) | `#0f172a` (Slate 900) | Application wallpaper / base desktop canvas |
| `surface-primary` | `#ffffff` (Pure White) | `#1e293b` (Slate 800) | Window interiors, modals, cards, sidebars |
| `surface-secondary` | `#f1f5f9` (Slate 100) | `#334155` (Slate 700) | Form fields, active list rows, nested panels |
| `border-subtle` | `#e2e8f0` (Slate 200) | `#334155` (Slate 700) | Dividers, window frame edges, card borders |
| `text-primary` | `#0f172a` (Slate 900) | `#f8fafc` (Slate 50) | Primary titles, price numbers, table headers |
| `text-muted` | `#64748b` (Slate 500) | `#94a3b8` (Slate 400) | Captions, secondary labels, helper descriptions |

### 2.2 Semantic Colors

| State | Color Code | Tailwind Class | Application |
|---|---|---|---|
| **Success** | `#16a34a` (Green 600) | `text-emerald-600` / `bg-emerald-500` | Completed sales, paid invoices, in-stock badges |
| **Warning** | `#d97706` (Amber 600) | `text-amber-600` / `bg-amber-500` | Low inventory warnings, pending repair approvals |
| **Danger / Alert** | `#dc2626` (Red 600) | `text-rose-600` / `bg-rose-500` | Out of stock, canceled quotes, returns, overdue debt |
| **Information** | `#0284c7` (Sky 600) | `text-sky-600` / `bg-sky-500` | Info callouts, customer search, repair review |

### 2.3 User-Configurable Accent Palette (8 Tones)

Users can customize their personal operating system accent color in `profile.html`. The selected accent propagates to active tab indicators, primary action buttons, window focus rings, and widget highlights:
1. **Blue (Default):** `#2563eb`
2. **Emerald Green:** `#059669`
3. **Indigo:** `#4f46e5`
4. **Violet Purple:** `#7c3aed`
5. **Rose Pink:** `#e11d48`
6. **Orange Amber:** `#ea580c`
7. **Teal:** `#0d9488`
8. **Slate Dark:** `#475569`

---

## 3. Typography Scale & Fonts

The application relies strictly on **100% locally hosted web fonts** stored in `web/fonts/` (23 `.woff2` files) to guarantee zero network latency and complete offline reliability.

### 3.1 Font Families
- **Primary Interface Font:** `Cairo` (Weights: 400, 600, 700, 800) — highly legible modern Arabic typography for all headings, POS tables, button labels, and system navigation.
- **Secondary / Body Font:** `IBM Plex Sans Arabic` (Weights: 400, 500, 600) — clean monospace-leaning clarity for financial reports, numbers, receipts, and invoices.
- **Iconography Font:** `Material Icons` local ligature set for all icons across toolbars, docks, and buttons.

### 3.2 Typographic Hierarchy
- **Desktop Widgets & Huge Totals:** `2.25rem (36px)` / `font-bold` / `tracking-tight`
- **Page Titles (H1):** `1.5rem (24px)` / `font-extrabold`
- **Card Titles & Modal Headers (H2):** `1.125rem (18px)` / `font-bold`
- **Body & Table Cells:** `0.875rem (14px)` / `font-normal`
- **Badges, Timestamps, Mini Details:** `0.75rem (12px)` / `font-medium`

---

## 4. Layout & Spacing Rules

- **Base Unit:** 4px grid (`p-1` = 4px, `p-2` = 8px, `p-4` = 16px, `p-6` = 24px).
- **Directionality:** Explicit `dir="rtl"` is applied globally to `<html>` and mirrored across all components.
- **Icon Mirroring:** Directional navigation arrows, chevron forward/back, and progress bars are mirrored appropriately for right-to-left scanning.
- **Border Radius:**
  - Badges & Pills: `rounded-full` (9999px)
  - Buttons & Inputs: `rounded-xl` (12px)
  - Cards & Modal Panels: `rounded-2xl` (16px)
  - Application Windows: `rounded-3xl` (24px) for window frames with top control handle bars

---

## 5. Desktop OS Components

1. **Top System Bar:** Pinned status bar featuring Store Name, Active Shift duration counter, Quick Theme toggle, Accent Selector, and Employee Profile shortcut.
2. **Desktop Dashboard Canvas:** Host for draggable desktop icons, live statistical widgets (Today Sales, Open Repairs, Low Stock count), and floating windows.
3. **Floating Window Manager (`iframe`):**
   - Draggable header bar with Arabic title and app icon.
   - Standard window controls: Minimize (`_`), Maximize / Restore (`□`), Close (`✕`).
   - Active window elevation using dynamic z-index stacking.
4. **Dock & Taskbar:** Dock situated at the screen bottom showing running application badges, launcher shortcuts, and Start Menu launcher button.
5. **Start Menu:** Sliding popup menu categorized by operations (Sales, Customers, Inventory, Maintenance, Management, System Settings).

---

## 6. Invoice Studio & Document Print Formatting

Documents generated by the system (A4 Invoices, Thermal 80mm Cashier Receipts, Maintenance Tickets, Payment Vouchers) adhere to standard printing rules:
- **Zero Margins in Print Mode:** `@page { size: auto; margin: 0; }` ensures print engines (WebView2 / Win32 Spooler) do not clip numeric columns or force unnecessary second sheets.
- **Thermal Widths:** Supported for 80mm standard retail printers and 58mm portable printers.
- **Color Accuracy:** High-contrast monochrome and two-tone palettes ensure optimal clarity on thermal heads and laser printers alike.


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
- **إصلاح تموضع قائمة ابدأ في وضع `LTR` وأزرار اللغة في شاشة الدخول وتوسيع قاموس الترجمة (`web/desktop.html`, `web/index.html`, `web/i18n.js`):** عكس موضع `#os-start-menu` إلى اليسار (`left: 16px`) و`#os-widgets` إلى اليمين وتحديث تنسيق الساعة (`en-US`) في الوضع الإنجليزي، تفعيل أزرار اللغة في شاشة الدخول (`EXPLICIT_LOGIN_LANG`)، وتوسيع قاموس `web/i18n.js` ليشمل قائمة ابدأ وشريط المهام وجميع الشاشات.
- **قسم إدارة الترجمة وقاموس النظام (`translations`, `translations_scan_project`, `translations_save`, `translations_map`) وعكس أيقونات سطح المكتب (`LTR`/`RTL`):** تبويب «الترجمة واللغات» في `web/settings.html` يضم جدولاً مركزياً لكل كلمات المشروع مع إمكانية التعديل والإضافة والفحص الآلي وتطبيق الترجمات المخصصة فوراً عبر `web/i18n.js`، مع قلب اتجاه أيقونات سطح المكتب تلقائياً إلى اليسار في الإنجليزية وإلى اليمين في العربية.
