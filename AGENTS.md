# تك زون للإلكترونيات — مصدر الحقيقة للذكاء الاصطناعي (AGENTS.md)

> **قاعدة التحديث الإلزامية:** أي تعديل أو إضافة أو حذف في المشروع (فكرة أو ملفات) يجب تضمينه في `AGENTS.md` في نفس الـ commit — حدّث القسم المتأثر وأضف سطراً في `## سجل التغييرات` (الأحدث أولاً).

## 1. الفكرة

نظام نقاط بيع عربي (RTL) يعمل **offline بالكامل**: مخزون، مبيعات، شراء أجهزة مستعملة، صيانة، ورديات، تقارير. يعمل داخل نافذة `pywebview` واحدة `maximized`، بواجهة ليلية ومتجاوبة مع الجوال.

## 2. التقنية

- Python 3.13 + `sqlite3` قياسي + `pywebview` 6.2.1 (WebView2) + HTML/CSS مُجمَّع Tailwind + JS vanilla.
- ممنوعات: لا React/Electron/Rust/.NET، لا bundler، لا مكتبات runtime جديدة، لا شبكة عند التشغيل (كل الخطوط والأيقونات محلية في `web/fonts/`).

## 3. البنية

`app/main.py` — نقطة التشغيل: عنوان النافذة من `settings.store_name` + نافذة `maximized=True` (`1360×860`, حد أدنى `360×500`). يقرأ `web/index.html` كـ `file://`.
`app/db.py` — المخطط + الاتصال + الـ seed. `app/api.py` — كل دوال النظام + `call(name, payload)` dispatcher للواجهة (`window.pywebview.api.call`). `app/selfcheck.py` — فحص assert واحد قابل للتشغيل.
`web/app.js` — الجسر `api(name, payload)` + `pageInit` + `syncTitle` + `renderSidebar` + زر جوال `tz-menu` + ثيم ليلي + `fmt/money/esc/toast`.
`web/tailwind.css` — مصدر Tailwind + كل `@font-face` المحلية. `web/app.css` — المُجمَّع (~47KB) **محفوظ في git عمداً** (البرنامج يعمل به دون بناء).
`package.json` — سكربت `css`: `tailwindcss -i web/tailwind.css -o web/app.css --minify` ثم node يزيل تعليقات CSS. `tailwind.config.js` — `darkMode: class` + ألوان `primary/background/surface` + خطوط `arabic/sans/body/num`.
`README.md` — للإنسان المشغّل (شرح + مميزات + صور `screenshots/` المنسوخة من التصاميم المرجعية). `screenshots/` — صور README الثمان (منسوخة من `docs/stitch_login_screen_arabic/*/screen.png`). `AGENTS.md` — مصدر الحقيقة الحي للذكاء الاصطناعي. `.gitignore` — يستثني `node_modules/` و`web/fonts/` الكبيرة و`*.db*` (انظر §8).

## 4. قاعدة البيانات

- المسار: `%LOCALAPPDATA%\TechZone\shop.db` (يُنشأ تلقائياً)؛ تجاوز عبر `SHOP_DB` (يستخدمه selfcheck). `PRAGMA foreign_keys=ON` + `journal_mode=WAL`. المبالغ `INTEGER` وحدات صغرى (1 عملة = 100).
- الجداول (15): `users(id, username, name, role, pin_salt, pin_hash, created_at)` — `categories(id, name)` — `products(id, sku, name, category_id, price, cost, qty, min_qty, tracked, notes, active, created_at)` — `serials(id, product_id, serial, status[in_stock|sold|in_repair], created_at)` — `shifts(id, user_id, opened_at, closed_at, opening_cash, counted_cash, expected_cash, diff)` — `sales(id, invoice_no, shift_id, user_id, created_at, customer_name, customer_phone, subtotal, discount, tax, total, status[completed|partial_return|returned], notes)` — `sale_items(id, sale_id, product_id, serial_id, name, qty, unit_price, line_total)` — `payments(id, sale_id, method[cash|wallet|credit], amount, received, change)` — `sale_returns(id, sale_id, user_id, created_at, reason, total)` — `sale_return_items(id, return_id, sale_item_id, qty, amount)` — `used_device_purchases(id, ref, user_id, created_at, seller_*, device_type, brand, model, serial, condition, notes, buy_price, storage, resale_price, product_id)` — `repairs(id, ref, user_id, created_at, updated_at, customer_*, address, device_type, serial, problem, accessories, notes, status[6], priority, cost)` — `repair_parts(id, repair_id, product_id, name, qty, unit_price, line_total)` — `stock_movements(id, created_at, user_id, product_id, serial_id, qty_change, qty_after, reason, ref)` — `settings(key, value)`.
- مفاتيح `settings` (15): `store_name`، `store_address`، `store_phone`، `currency`، `tax_rate` (الخمسة المزروعة) + العشرة الجديدة: `store_email`، `store_cr`، `store_vat`، `receipt_thanks`، `receipt_footer`، `receipt_logo` (data:image ≤200KB)، `receipt_show_logo`، `receipt_show_barcode`، `receipt_show_tax`، `receipt_show_payments` (قيم `0`/`1`).
- Seed: مستخدم `admin/1234` (المدير) و`cashier/1111` (أحمد محمد) + 9 فئات + 14 منتجاً تجريبياً (منها متتبّع `DL-OPTI-P4` بسيريالات `DL-88231+`).

## 5. الـ API (كل دوال `Api` العامة — مقروءة من الكود)

الدور: `—` = بلا تسجيل، `user` = أي مسجّل، `admin` = مدير فقط.

| الدالة | المعاملات | الدور | السلوك |
|---|---|---|---|
| `users` | — | — | قائمة المستخدمين (username/name/role) لشاشة الدخول |
| `login` | `username, pin` | — | PIN من 4 أرقام، PBKDF2 مقارن بـ `hmac.compare_digest`، يخزن الجلسة في `_STATE` |
| `session` / `logout` | — | — | قراءة/مسح جلسة النافذة الواحدة |
| `settings` | — | user | كل مفاتيح `settings` كقاموس |
| `settings_save` | `**kv` | admin | 15 مفتاحاً مسموحاً فقط؛ القيمة الفارغة `""` تُتجاهل **إلا** أعلام العرض الأربعة (يجب `"0"`/`"1"` — و`"0"` تُحفظ وتُقرأ)؛ `receipt_logo` يجب أن يبدأ `data:image/` و≤200KB؛ مفاتيح مجهولة/`None` تُتجاهل بصمت؛ يعيد الإعدادات كاملة |
| `categories` | — | user | الفئات + عدد منتجات كل فئة |
| `categories_save` | `name` | admin | اسم غير فارغ وفريد |
| `categories_update` | `id, name` | admin | تعديل الاسم (غير فارغ + فريد + موجودة) |
| `categories_delete` | `id` | admin | مرفوض إن عليها منتجات نشطة |
| `products` | `q, category_id, stock[out\|low\|in], limit, offset` | user | بحث + فلاتر؛ `cost` مخفي (`None`) عن الكاشير + `stock_state` محسوب |
| `product` | `id` | user | منتج واحد (نفس حجب `cost`) |
| `product_save` | `id?, sku, name, category_id?, price, cost, min_qty, tracked, notes?, serials?` | admin | إضافة/تعديل؛ سيريالات جديدة تزيد الكمية وتكتب حركة `serial_add` |
| `product_delete` | `id` | admin | حذف ناعم (`active=0`) |
| `products_search` | `q?, limit, category_id?` | user | يطابق الاسم/SKU/**سيريال in_stock**؛ `category_id` اختياري؛ `q` فارغ = الأحدث بالاسم |
| `product_adjust` | `id, qty_change, reason` | admin | تعديل يدوي؛ رفض الصفر والسالب الناتج؛ يكتب `stock_movements` |
| `serials` | `product_id` | user | سيريالات منتج |
| `serial_add` | `product_id, serial` | admin | سيريال فريد + زيادة كمية + حركة |
| `shift` | — | user | الوردية المفتوحة + مبيعات اليوم + مبيعات الوردية |
| `shift_open` | `opening_cash` | user | وردية واحدة مفتوحة لكل مستخدم |
| `shift_close` | `counted_cash` | user | يحسب `expected/diff` من مدفوعات `cash` |
| `shifts` | — | admin | آخر 50 وردية + إجمالي مبيعات كل وردية |
| `sale_create` | `items[{product_id, qty, unit_price?, serial_ids?}], discount, payments[{method, amount, received?}], customer_*?, notes?` | user | وردية إلزامية؛ الكاشير لا يعدّل السعر (يُتجاهل `unit_price`)؛ المتتبّع يتطلب `serial_ids` بعدد الكمية؛ خصم ≤ المجموع؛ ضريبة `tax_rate%` تقريب نصف-لأعلى؛ مجموع الدفعات = الإجمالي تماماً؛ `received<cash.amount` مرفوض؛ فاتورة `INV-00000` ثم `INV-#####`؛ يخصم المخزون ويكتب حركات `sale` ودفعات |
| `sale` | `id` | user | فاتورة + أصناف + دفعات + `user_name` |
| `receipt_text` | `id` | user | نص إيصال حراري، كل سطر ≤80 عموداً |
| `sales` | `date?, kind[sale\|repair]?, q?, limit, offset` | user | الكاشير يرى مبيعاته فقط؛ 500 كحد داخلي |
| `sales_stats` | `date?` | user | عدّادات اليوم (مبيعات/مرتجعات/صيانة) |
| `sale_return` | `sale_id, items[{sale_item_id, qty}], reason?` | admin | إرجاع جزئي/كلي؛ يعيد المخزون والسيريال؛ مبلغ الإرجاع بأسعار الأصناف **دون الضريبة** (ponytail)؛ يحدّث `status` |
| `used_create` | `seller_name, model, serial?, ... buy_price, resale_price?, to_inventory=True` | admin | `buy_price>0` إلزامي؛ السيريال إلزامي وفريد عند الإضافة للمخزون؛ ينشئ منتج `USED-<ref>` + سيريال + حركة `used_purchase`؛ مرجع `TRX-YYYYMMDDHHMMSS` |
| `used` / `used_stats` | `q?, limit, offset` | user | سجل المشتريات المستعملة / إحصاءات اليوم + إجمالي المخزون |
| `repair_create` | `customer_name, customer_phone, device_type, problem, ...` | user | الحقول الأربعة إلزامية؛ الحالة `received`؛ مرجع `RPR-...` |
| `repairs` | `q?, status?, limit, offset` | user | بحث بالمرجع/العميل/السيريال + فلتر حالة |
| `repair` | `id` | user | تذكرة + قطعها + `transitions` المتاحة |
| `repair_set_status` | `id, status` | user | انتقال ضمن `REPAIR_FLOW` فقط وإلا `انتقال غير مسموح` |
| `repair_add_part` | `repair_id, product_id, qty` | user | مرفوض للمنتهية (`delivered/rejected`)؛ السعر = `cost` (أو `price`)؛ يخصم المخزون ويضيف للتكلفة |
| `report_daily` | `date?` | admin | إحصاء فترة (مبيعات/مرتجعات/دفعات/صيانة) |
| `report_monthly` | `year, month` | admin | نفسها لنطاق شهري |
| `report_top` | `date_from?, date_to?, limit` | admin | الأصناف الأعلى مبيعاً |
| `report_profit` | `date_from?, date_to?` | admin | ربح البضائع (`line_total - cost×qty`) + ربح الصيانة |
| `report_low` | — | user | منتجات `qty ≤ min_qty` |
| `report_movements` | `limit` | admin | أحدث حركات المخزون + أسماء المنتجات/المستخدمين |
| `stock_stats` | — | user | عدّاد/قيمة/منخفض/نافد |

## 6. الواجهة (8 صفحات)

| الصفحة | الدور |
|---|---|
| `index.html` | تسجيل الدخول بالـ PIN + اختيار المستخدم |
| `pos.html` | نقاط البيع: فلتر فئات + بحث (`products_search` مع `category_id`) + سلة + زر سلة جوال `cart-fab` + شريط وردية |
| `history.html` | سجل المبيعات والصيانة + رابط الإيصال `receipt.html?id=` |
| `receipt.html` | معاينة الإيصال وتخصيصه: `renderPaper()` تعكس الفورم (مدير) أو `SETTINGS` (كاشير)؛ لا عنصر `print-head` — الطباعة CSS فقط تخفي كل شيء عدا `#paper` بعرض `80mm`؛ بوابة مدير لنموذج التخصيص |
| `repair.html` | تذاكر الصيانة + انتقالات الحالة + إضافة قطع |
| `inventory.html` | المخزون (مدير): جدول + فلاتر + قسم إدارة الفئات (إضافة/تعديل `prompt`/حذف) |
| `buy_used.html` | شراء أجهزة مستعملة (مدير) |
| `reports.html` | التقارير والتحليلات (مدير) |

مشترك: `pageInit(name, {admin?})` — جلسة + إعدادات + شريط جانبي، تحويل لغير المسجّل إلى `index.html` وللكاشير في صفحات المدير إلى `pos.html`. `syncTitle(label)` — عنوان الصفحة/النافذة من `store_name`. الشريط الجانبي `renderSidebar` يخفي صفحات المدير عن الكاشير. زر الجوال `tz-menu` يفتح الشريط كدرج منزلق. الثيم الليلي يُطبَّق مبكراً من `localStorage.tz-theme` لتفادي الوميض. بوابات المدير داخل الصفحات: تخصيص الإيصال + تعديل الأسعار + المرتجعات + التقارير.

## 7. قواعد العمل

- مخزون غير سالب أبداً (بيع/تعديل/قطع صيانة تُرفض عند النقص). بيع بلا وردية مفتوحة مرفوض. الكاشير: لا أسعار شراء ولا أرباح، لا تعديل سعر، لا مرتجعات، لا تقارير، لا صفحات مدير.
- انتقالات الصيانة الست (`REPAIR_FLOW`): `received → in_review/rejected`، `in_review → pending_approval/repaired/rejected`، `pending_approval → in_review/repaired/rejected`، `repaired → delivered`، `rejected/delivered` نهائيتان.
- PIN بـ PBKDF2-SHA256 (200 ألف تكرار) + seed: `admin/1234`، `cashier/1111`.
- صور `docs/**` للقراءة فقط — النسخ إلى `screenshots/` مسموح والتعديل على الأصل ممنوع.

## 8. أوامر النجاح (انسخ والصق من جذر المشروع)

```powershell
python -m compileall -q app
python app\selfcheck.py
Select-String -Path web\*.html,web\app.js -Pattern 'https?://'  # يجب: بلا نتائج (offline)
(Get-ChildItem web\*.html).Count  # يجب: 8
python -c "import webview; print(webview.__version__)"  # يجب: 6.2.1
(Get-ChildItem web\fonts\*.woff2).Count  # يجب: 23
python -c "import ast,glob; [ast.parse(open(f,encoding='utf-8').read()) for f in glob.glob('app/*.py')]; print('syntax ok')"
```

## سجل التغييرات

- `2026-10-12`: إعادة تسمية `PROJECT_AI.md` → `AGENTS.md` + توسيع `README.md` بالشرح والمميزات والصور الثمان (`screenshots/`).
- `2026-10-12`: بناء أول + فلتر تصنيف POS + إدارة فئات + إيصال معاينة/تخصيص + طباعة 80mm + اسم محل شامل (`syncTitle`) + تجاوب (`tz-menu`/`cart-fab`) + نافذة `maximized` + توثيق حي (`AGENTS.md`) + مستودع git محلي أول (`main`).
