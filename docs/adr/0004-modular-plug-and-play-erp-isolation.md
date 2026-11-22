# ADR 0004: Mandatory Modular Plug-and-Play (Zero-Overhead Isolation) & Full Documentation Rule

- **Date:** 2026-11-18
- **Status:** Accepted & Mandatory (Non-Negotiable for all AI Models & Developers)

## Context

TechZone POS & Shop OS has expanded from a retail POS into a full modular ERP system including Procurement (`purchases`), Double-Entry Accounting (`accounting`), Installments (`installments`), Maintenance (`repair`), Used Devices (`buy_used`), and Comprehensive Financial Analytics (`reports`). Different businesses (or the same shop at different growth stages) may enable or disable any module via Owner Mode (`owner.html`). Furthermore, multiple AI models and developers may maintain or extend the codebase over time.

## Decision

1. **Mandatory Modular Plug-and-Play Architecture (هندسة الأقسام المعزولة — Zero-Overhead Isolation):**
   - Every section/module (`pos`, `sales_quotes`, `inventory`, `customers`, `installments`, `purchases`, `accounting`, `history`, `repair`, `buy_used`, `reports`, `staff`, or any future module) MUST be built and maintained as an isolated Plug-and-Play unit.
   - Every module must be registered in `DEFAULT_MODULES` (`app/db.py`), mapped in `API_MODULE_MAP` (`app/modules_map.py`), encapsulated in its own backend mixin (`app/api_<module>.py`) and standalone HTML page (`web/<module>.html`), and guarded at runtime via `Api._module_enabled()` (`O(1)` memory cache).
   - Cross-module hooks (`app/erp_hooks.py`) and cross-module reports (`app/api_reports.py`) MUST check `erp_hooks.is_module_active(api, conn, "<module_key>")` before executing any SQL query so disabled modules incur **zero database queries, zero CPU overhead, and zero errors**.
   - Auto-posted accounting journal entries for sales, returns, installments, and repairs MUST separate the **Financial Invoice Revenue Entry** (`source_table='sales'`, matching exact invoice `total`) from the **Perpetual Inventory Cost Entry** (`source_table='sales_cogs'`).
2. **Mandatory Documentation Rule (توثيق إلزامي لكل تعديل أو إضافة أو حذف):**
   - Any addition, modification, or deletion in the codebase MUST be documented in the same turn/commit across `AGENTS.md`, `CLAUDE.md`, `README.md`, and the relevant `docs/*.md` files.
   - `app/selfcheck.py` includes an automated assertion verifying that the Modular Plug-and-Play mandate and latest feature documentation remain present across all core documentation files.

## Consequences

- Any AI agent reading `AGENTS.md`, `CLAUDE.md`, `README.md`, or `docs/*.md` will immediately understand and enforce the Modular Plug-and-Play rule and the mandatory documentation rule.
- Disabling or enabling any module from `owner.html` is guaranteed safe and zero-overhead.


---

## 🔒 الشرط الأساسي الإلزامي: هندسة الأقسام المعزولة (Modular Plug-and-Play — Zero-Overhead Isolation) وسجل التحديثات الشامل

> **قاعدة معمارية صارمة لكل نموذج ذكاء اصطناعي (AI Agent) أو مطور يعمل على المشروع الآن وفيما بعد:**
> 1. **العزل التام للأقسام (`Modular Plug-and-Play / Zero-Overhead Isolation`):** أي قسم حالي أو مستقبلي (مثل `purchases`، `accounting`، `installments`، `repair`، `buy_used`، `reports` أو أي قسم جديد) يجب أن يعمل عبر خطافات معزولة (`app/erp_hooks.py` و`is_module_active(conn, 'module_key')`) بحيث إذا تم إيقاف القسم من `system_modules` أو لم يكن مفعلاً في نشاط المتجر، يعمل باقي النظام بنسبة 100% دون أي خطأ أو بطء أو اعتمادية إجبارية.
> 2. **التوثيق الإلزامي الفوري مع كل طلب:** أي تعديل أو إضافة أو حذف في الكود أو الواجهات أو قاعدة البيانات يجب توثيقه فوراً في `AGENTS.md` و`CLAUDE.md` و`README.md` وكافة ملفات `docs/*.md`، ويتم فحص ذلك آلياً في `app/selfcheck.py`.

### سجل التحديثات المعمارية والميزات الموثقة
- **فصل قيد إيراد المبيعات عن قيد تكلفة البضاعة المباعة (`sales` vs `sales_cogs`):** في `app/erp_hooks.py`، يُسجل قيد فاتورة البيع (`source_table='sales'`) بمبلغ الفاتورة الفعلي فقط، بينما يُسجل قيد الجرد المستمر لتكلفة البضاعة المباعة (`source_table='sales_cogs'`) كقيد مستقل لمنع تضخم إجمالي القيد في دفتر اليومية.
- **حماية معالج الترصيد الافتتاحي الآلي (`has_opening_entry`):** في `app/api_accounting.py` و`web/accounting.html`، يتحقق النظام من وجود قيد افتتاحي مرحّل (`kind='opening' AND status='posted'`) ويمنع تكرار التشغيل من الخلفية والواجهة.
- **إدارة شجرة الحسابات الكاملة والسحب والإفلات (`account_save`, `account_delete`, `account_move`):** إضافة وتعديل وحذف الحسابات (بشرط عدم وجود حركات أو حسابات فرعية) وتحريك الحسابات بالسحب والإفلات (Drag-and-Drop) مع إعادة بناء الأرصدة آلياً، بالإضافة إلى طباعة A4 شاملة لكل تبويبات المحاسبة وسندات القيد.
- **مركز التقارير والتحليلات المالية الشامل (`report_comprehensive`):** في `app/api_reports.py` و`web/reports.html`، استخراج تقارير الأرباح والخسائر، مديونيات العملاء وأعمار الديون، مستحقات الموردين، تقييم المخزون، وحركة الخزائن، مع التصدير إلى **Excel الأصلي (`.xlsx` متعدد الأوراق + `.csv`)** و**PDF (A4)** والطباعة المباشرة والإرسال عبر **واتساب (`whatsapp_send_report`)**.
- **تخصيص أيقونات سطح المكتب وشريط المهام لكل مستخدم (`_hidden_desktop` & `_hidden_taskbar`):** في `web/profile.html` و`web/desktop.html` و`app/api_auth.py`، حفظ تفضيلات إظهار/إخفاء الأيقونات لكل مستخدم بشكل مستقل داخل `users.desktop_layout` دون التأثير على باقي المستخدمين، مع تنسيق متجاوب كامل في `web/app.css`.
- **التحكم في سلوك زر الإغلاق (`X`) والتصغير إلى شريط النظام بجوار الساعة (`close_exit_app`):** في `app/main.py` و`web/settings.html` و`app/db.py`، خيار `close_exit_app` (الافتراضي `'0'`) يخفي النافذة عند الضغط على `X` ويبقي البرنامج يعمل في شريط النظام (System Tray / `.NET WinForms NotifyIcon`) بجوار الساعة مع قائمة سياقية عربية («إظهار نافذة البرنامج» / «إغلاق البرنامج نهائياً»)، وعند تفعيله (`'1'`) يغلق البرنامج نهائياً.


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
