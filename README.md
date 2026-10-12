# تك زون للإلكترونيات

نظام نقاط بيع وإدارة محل يعمل **offline بالكامل**: مخزون، مبيعات، شراء أجهزة مستعملة، صيانة، ورديات، وتقارير. الواجهة عربية (RTL) بوضع ليلي، وتعمل داخل نافذة `pywebview` واحدة (maximized).

## التثبيت

```powershell
npm install
npm run css
```

يبني `web\app.css` من `web\tailwind.css`. ملاحظة: مجلد `web\fonts\` (23 ملف woff2 ~1MB) مستثنى من git لتقليل الحجم — أعد جلبه بإحدى الطريقتين قبل البناء:

- الطريقة 1: `npm i @fontsource/ibm-plex-sans-arabic @fontsource/cairo @fontsource/space-grotesk` ثم انسخ ملفات `woff2` المطلوبة إلى `web\fonts\` بالأسماء التي يشير إليها `web\tailwind.css`.
- الطريقة 2: حمّل ملفات `woff2` من Google Fonts (عائلات IBM Plex Sans Arabic وCairo وSpace Grotesk + أيقونات Material) وضعها في `web\fonts\` بنفس الأسماء، ثم شغّل `npm run css`.

## التشغيل

```powershell
python app\main.py
```

## الفحص

```powershell
python app\selfcheck.py
```

يطبع أسطر `PASS` ويعيد `0` عند النجاح (`ALL 40 CHECKS PASSED`). يستخدم قاعدة بيانات مؤقتة عبر متغير `SHOP_DB`.

## الدخول الافتراضي (PIN من 4 أرقام)

| المستخدم | الاسم | الرمز |
|---|---|---|
| `admin` | المدير | `1234` |
| `cashier` | أحمد محمد | `1111` |

## قاعدة البيانات

المسار الافتراضي: `%LOCALAPPDATA%\TechZone\shop.db` (يُنشأ تلقائياً).
للتجاوز (فحص/اختبار): عيّن متغير البيئة `SHOP_DB` إلى مسار ملف آخر.

ملاحظات:

- المبالغ تُخزَّن `INTEGER` بوحدات صغرى (1 وحدة عملة = 100) لتفادي أخطاء التقريب.
- لا يُسمح بمخزون سالب، ولا بيع بدون وردية مفتوحة (المدير يرى الأرباح وأسعار الشراء؛ الكاشير لا).
- `settings` تشمل: `store_name`، `store_address`، `store_phone`، `currency` (ر.س)، `tax_rate` (15%)، إضافة إلى `store_email` و`store_cr` و`store_vat` وخيارات تخصيص الإيصال (`receipt_thanks` و`receipt_footer` والشعار وأعلام الإظهار).

## للمطور / للذكاء الاصطناعي

المصدر الحي للحقيقة: [PROJECT_AI.md](PROJECT_AI.md) — يغني عن قراءة الكود كاملاً. **قاعدة إلزامية:** أي تعديل/إضافة/حذف في المشروع يجب تضمينه في `PROJECT_AI.md` في نفس الـ commit (القسم المتأثر + سطر في سجل التغييرات).
