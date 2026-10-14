# تك زون للإلكترونيات — مصدر الحقيقة للذكاء الاصطناعي (AGENTS.md)

> **قاعدة التحديث الإلزامية:** أي تعديل أو إضافة أو حذف في المشروع (فكرة أو ملفات) يجب تضمينه في `AGENTS.md` في نفس الـ commit — حدّث القسم المتأثر وأضف سطراً في `## سجل التغييرات` (الأحدث أولاً).

## 1. الفكرة

نظام نقاط بيع عربي (RTL) يعمل **offline بالكامل**: مخزون (مع صور المنتجات)، مبيعات، عملاء وحسابات آجلة وسندات قبض، شراء أجهزة مستعملة، صيانة، ورديات بتقارير جرد تفصيلية، موظفون بصلاحيات مخصصة لكل فرد، وتقارير. يعمل داخل نافذة `pywebview` واحدة `maximized`، بواجهة ليلية ومتجاوبة مع الجوال، ومهيأ افتراضياً للسوق المصري (`ج.م`، ضريبة 14% قابلة للتفعيل أو الإيقاف الكامل).

## 2. التقنية

- Python 3.13 + `sqlite3` قياسي + `pywebview` 6.2.1 (WebView2) + HTML/CSS مُجمَّع Tailwind + JS vanilla.
- ممنوعات: لا React/Electron/Rust/.NET، لا bundler، لا مكتبات runtime جديدة، لا شبكة عند التشغيل (كل الخطوط والأيقونات محلية في `web/fonts/`).

## 3. البنية

`app/main.py` — نقطة التشغيل: عنوان النافذة من `settings.store_name` + نافذة `maximized=True` (`1360×860`, حد أدنى `360×500`). يقرأ `web/index.html` كـ `file://`. عند التجميد (`sys.frozen`): `web/` من `sys._MEIPASS` و`data/` بجانب الـ exe.
`build-exe.bat` — دبل كليك يعيد بناء `dist/TechZone.exe` (`--windowed --onefile --add-data "web;web"`). `push-github.bat` — دبل كليك يرفع التعديلات إلى GitHub. `TechZone.spec` محفوظ في git؛ `build/` و`dist/` مستثناة.
`app/db.py` — المخطط (17 جدولاً) + الاتصال + الـ seed المهيأ لمصر + ترحيل العملاء وترقية الأعمدة تلقائياً.
`app/api.py` — كل دوال النظام + نظام الصلاحيات المخصصة `_perm(key)` + `call(name, payload)` dispatcher للواجهة (`window.pywebview.api.call`).
`app/selfcheck.py` — فحص assert واحد قابل للتشغيل (62 فحصاً).
`web/app.js` — الجسر `api(name, payload)` + `hasPerm` + `pageInit` + `syncTitle` + `renderSidebar` + زر جوال `tz-menu` + ثيم ليلي + `fmt/money/esc/toast`.
`web/tailwind.css` — مصدر Tailwind + كل `@font-face` المحلية. `web/app.css` — المُجمَّع (~47KB) **محفوظ في git عمداً**. `web/fonts/` — 23 ملف `.woff2` محلي.

## 4. قاعدة البيانات

- المسار: `data/shop.db` بجانب جذر المشروع (وعند التجميد: `data/` بجانب الـ exe). المبالغ `INTEGER` وحدات صغرى (1 عملة = 100 قرش).
- الجداول (17): `users(id, username, name, role, pin_salt, pin_hash, permissions, card_size, created_at)` — `categories(id, name)` — `products(..., image)` — `serials(...)` — `shifts(...)` — `customers(id, name, phone, created_at)` — `sales(...)` — `sale_items(...)` — `payments(id, sale_id, method[cash|wallet|credit], amount, received, change, ref_no)` — `customer_payments(id, ref, customer_id, sale_id, user_id, shift_id, created_at, amount, method[cash|wallet], ref_no, notes)` — `sale_returns(...)` — `sale_return_items(...)` — `used_device_purchases(...)` — `repairs(...)` — `repair_parts(...)` — `stock_movements(...)` — `settings(key, value)`.
- مفاتيح `settings` (17): `store_name`، `store_address`، `store_phone`، `currency` (ج.م)، `tax_enabled` (`0`/`1`)، `tax_rate` (14)، `pos_card_size` (200) + `store_email`، `store_cr`، `store_vat`، `receipt_thanks`، `receipt_footer`، `receipt_logo`، `receipt_show_logo`، `receipt_show_barcode`، `receipt_show_tax`، `receipt_show_payments`.

## 5. الصلاحيات المخصصة لكل مستخدم (16 صلاحية)

المدير (`role='admin'`) يملك كل الصلاحيات تلقائياً. أي موظف آخر يمكن للمدير تخصيص صلاحياته الفردية عبر 16 مفتاحاً في `users.permissions`:
`pos_sell`، `pos_price`، `pos_item_discount`، `sales_return`، `sales_all`، `inventory_view`، `inventory_edit`، `cost_view`، `customers_view`، `customers_edit`، `customers_delete`، `repair_view`، `repair_edit`، `used_manage`، `reports_view`، `settings_manage`.

## 6. الواجهة (10 صفحات)

| الصفحة | الوصف |
|---|---|
| `index.html` | تسجيل الدخول بالـ PIN + اختيار المستخدم |
| `pos.html` | نقاط البيع: عرض صور المنتجات، شريط «نفدت الكمية» وتعطيل الضغط على المنتهي، سلايدر حجم البلوك لكل مستخدم مع افتراضي للأدمن، خصم على منتج معين في السلة (`%` أو مبلغ) بصلاحية، نافذة خصم `%` على الفاتورة، زر «فاتورة / مرتجع» لعرض فاتورة مدفوعة وعمل استرجاع أو خصم بصلاحية، طباعة الإيصال مباشرة عند إتمام البيع، ونافذة إغلاق وردية تفصيلية تعرض كل العمليات ومقارنة النقدي الفعلي بالمتوقع مع ملاحظة الآجل والمحفظة |
| `customers.html` | إدارة العملاء والمديونيات: عرض إجمالي الآجل والمسدد والمديونية المتبقية + فلتر «عليه مديونية فقط» |
| `customer_details.html` | كشف حساب العميل التفصيلي + إصدار وحذف سندات القبض لتسديد الدفعات الآجلة (نقدي/محفظة برقم مرجعي) |
| `history.html` | سجل المبيعات والصيانة + نافذة استرجاع تفاعلية |
| `receipt.html` | معاينة الإيصال وإعدادات المتجر (تفعيل/إيقاف الضريبة، النسبة، العملة، الشعار، وعرض مرجع المحفظة) |
| `repair.html` | تذاكر الصيانة + فتح مباشر عبر `?id=` + قائمة منسدلة لقطع الغيار + إكمال تلقائي للعملاء |
| `inventory.html` | المخزون: إضافة وضغط صور المنتجات (تلقائياً عبر Canvas)، جدول بالصور المصغرة، فلاتر، إدارة الفئات، ونافذة السيريالات |
| `buy_used.html` | شراء أجهزة مستعملة |
| `reports.html` | التقارير والتحليلات + سجل الورديات + إدارة الموظفين وتخصيص صلاحيات كل موظف (16 صلاحية) |

## سجل التغييرات

- `2026-10-14`: إضافة صور المنتجات، شريط «نفدت الكمية»، التحكم بحجم بلوك المنتج في نقاط البيع لكل مستخدم مع افتراضي للأدمن، خصم منتج في السلة (`%` أو مبلغ) بصلاحية `pos_item_discount`، نافذة خصم `%` على الفاتورة، زر «فاتورة / مرتجع» في نقاط البيع لعرض فاتورة مدفوعة واسترجاع صنف أو أكثر أو تعديل الخصم بصلاحية، الطباعة المباشرة عند إتمام الدفع دون مغادرة نقاط البيع، ونموذج إغلاق الوردية التفصيلي مع جرد النقدية الفعلي وملاحظة المحفظة والآجل (62/62 فحصاً).
- `2026-10-14`: إضافة حسابات العملاء الآجلة وسندات القبض، نظام الصلاحيات المخصصة لكل موظف، خيار تشغيل/إيقاف الضريبة وتهيئة الإعدادات لمصر (`ج.م`، 14%)، تحسين دفع نقاط البيع، وإضافة `push-github.bat`.
