/* TechZone POS & Shop OS — Bilingual Engine (Arabic RTL / English LTR)
 * Zero-overhead, lossless DOM & dynamic content translation across all 19 pages.
 */
(function () {
  const EXACT_MAP = {
    'استيراد وتصدير Excel': 'Excel Import & Export',
    'استيراد / تصدير Excel': 'Excel Import / Export',
    'استيراد Excel': 'Import Excel',
    'قالب': 'Template',
    'تحديث الأقسام': 'Refresh Modules',
    'مركز الاستيراد والتصدير الشامل لملفات Excel (.xlsx / .csv)': 'Universal Excel Import & Export Hub (.xlsx / .csv)',
    'تصدير كل المنتجات (Excel)': 'Export All Products (Excel)',
    'تصدير كل التصنيفات (Excel)': 'Export All Categories (Excel)',
    'استيراد منتجات من ملف Excel / CSV': 'Import Products from Excel / CSV',
    'استيراد تصنيفات من ملف Excel / CSV': 'Import Categories from Excel / CSV',
    'تصدير الموردين Excel': 'Export Suppliers Excel',
    'استيراد الموردين Excel': 'Import Suppliers Excel',
    // Full Login Screen Phrases
    'كلمة المرور / الرمز السري': 'Password / PIN Code',
    'دخول إلى النظام': 'Sign In to System',
    'وضع الدخول: الرمز السري المباشر': 'Login Mode: Direct PIN',
    'وضع الدخول: اختيار المستخدم + الرمز السري': 'Login Mode: Select User + PIN',
    'وضع الدخول: اسم المستخدم وكلمة المرور': 'Login Mode: Username & Password',
    'متصل بالنظام المحلي': 'Connected to Local System',
    'جميع الحقوق محفوظة © تك زون للإلكترونيات': 'All Rights Reserved © TechZone Electronics',
    'تأمين الحساب الإداري': 'Secure Admin Account',
    'أنت تستخدم الرمز الافتراضي (1234). يرجى تغييره الآن.': 'You are using the default PIN (1234). Please change it now.',
    'لحماية بيانات متجرك وأرباحك وحسابات العملاء، يجب تعيين رمز سري جديد وخاص بك قبل متابعة الدخول.': 'To protect your store data, profits, and customer accounts, please set a new private PIN before continuing.',
    'الرمز السري الجديد (4 إلى 8 أرقام):': 'New PIN (4 to 8 digits):',
    'تأكيد الرمز السري الجديد:': 'Confirm New PIN:',
    'حفظ الرمز السري والدخول للنظام': 'Save PIN & Sign In',
    'استعادة رمز مدير النظام': 'Recover Admin PIN',
    'باستخدام عبارة مرور المالك أو مفتاح الاسترداد': 'Using Owner Passphrase or Recovery Key',
    'عبارة مرور المالك أو مفتاح الاسترداد:': 'Owner Passphrase or Recovery Key:',
    'رمز المدير الجديد (4 إلى 8 أرقام):': 'New Admin PIN (4 to 8 digits):',
    'تأكيد رمز المدير الجديد:': 'Confirm New Admin PIN:',
    'تعيين رمز المدير الجديد': 'Set New Admin PIN',
    'اكتب معرف الدخول أو اسم المستخدم...': 'Enter username...',
    'إظهار / إخفاء الرمز السري': 'Show / Hide PIN',
    'أدخل عبارة مرور المالك أو مفتاح الاسترداد': 'Enter owner passphrase or recovery key',
    'الترجمة واللغات': 'Translations & Languages',
    'إدارة الترجمة وقاموس النظام (عربي / إنجليزي)': 'Translation & Dictionary Manager (Arabic / English)',

    // Screenshot & Desktop Start Menu / Taskbar / Topbar / Common UI
    'المحاسبة والمالية': 'Accounting & Finance',
    'قائمة ابدأ — جميع تطبيقات النظام': 'Start Menu — All System Apps',
    'اضغط على أي تطبيق لفتحه في نافذة مستقلة قابلة للتكبير والتصغير': 'Click any app to open it in a resizable window',
    'ابحث عن قسم (نقاط البيع، الإعدادات، المخزون، العملاء، التقارير...)': 'Search modules (POS, Settings, Inventory, Customers, Reports...)',
    'ترتيب الأيقونات تلقائياً': 'Auto-Arrange Icons',
    'تصغير كل النوافذ': 'Minimize All Windows',
    'ترتيب النوافذ جنباً إلى جنب': 'Tile Windows Side-by-Side',
    'تخصيص الخلفية والألوان': 'Customize Wallpaper & Colors',
    'المدير': 'Admin',
    'مدير النظام': 'System Admin',
    'مدير النظام — اضغط للملف الشخصي': 'System Admin — Click for Profile',
    'موظف — اضغط للملف الشخصي': 'Staff — Click for Profile',
    'كاشير': 'Cashier',
    'نظام': 'Installments',
    'سجل': 'History',
    'مركز': 'Repairs',
    'شراء': 'Used',
    'إعدادات': 'Settings',
    'تبديل الوضع الليلي / النهاري': 'Toggle Dark / Light Mode',
    'التاريخ والوقت': 'Date & Time',
    'ج.م': 'EGP',
    'الفئة': 'Category',
    'المبلغ': 'Amount',
    'العميل:': 'Customer:',
    'رقم الفاتورة': 'Invoice No.',
    'اسم العميل *': 'Customer Name *',
    'اسم العميل': 'Customer Name',
    'محفظة إلكترونية': 'E-Wallet',
    'تاريخ الاستحقاق': 'Due Date',
    'ملغى': 'Cancelled',
    'ملغاة': 'Cancelled',
    'النوع': 'Type',
    'إجراء': 'Action',
    'الصنف': 'Item',
    'التاريخ:': 'Date:',
    'رقم السند': 'Voucher No.',
    'رقم العقد': 'Contract No.',
    'اسم الصنف': 'Item Name',
    'نقدي (كاش)': 'Cash',
    'عروض الأسعار': 'Quotations',
    'إظهار الشعار': 'Show Logo',
    'المجموع الفرعي': 'Subtotal',
    'إلغاء عرض السعر': 'Cancel Quotation',
    'فواتير المبيعات (A4)': 'Sales Invoices (A4)',
    'اتباع الافتراضي المحدد من الأدمن': 'Follow Admin Default',
    'تم': 'Done',
    'الكود': 'Code',
    'مكتمل': 'Completed',
    'اليوم': 'Today',
    'تطبيق': 'Apply',
    'واتساب': 'WhatsApp',
    'المنتج': 'Product',
    'التصنيف': 'Category',
    'المقسّط': 'Financed',
    'عرض سعر': 'Quotation',
    'المحصّل': 'Collected',
    'الضامن:': 'Guarantor:',
    'كشف حساب': 'Account Statement',
    'المتبقي:': 'Remaining:',
    'الفاتورة': 'Invoice',
    'المورد *': 'Supplier *',
    'رقم القيد': 'Entry No.',
    'المرتجعات': 'Returns',
    'فاتورة A4': 'A4 Invoice',
    'كل الفئات': 'All Categories',
    'سعر البيع': 'Sell Price',
    'سعر الشراء': 'Cost Price',
    'كود الحساب': 'Account Code',
    'اسم الحساب': 'Account Name',
    'قيمة القسط': 'Installment Amount',
    'كل الأصناف': 'All Items',
    'حذف الصورة': 'Remove Image',
    'حد التنبيه': 'Min Stock Alert',
    'دفع وطباعة': 'Pay & Print',
    'مرتجع جزئي': 'Partial Return',
    'مرتجع كامل': 'Full Return',
    'رقم العملية': 'Transaction Ref',
    'نفدت الكمية': 'Out of Stock',
    'طريقة الصرف': 'Payment Method',
    'خزينة نقدية': 'Cash Treasury',
    'مدين (Debit)': 'Debit',
    'دائن (Credit)': 'Credit',
    'طريقة الدفع:': 'Payment Method:',
    'تذكير واتساب': 'WhatsApp Reminder',
    'رقم التليفون': 'Phone Number',
    'محفظة / بنكي': 'Wallet / Bank',
    'طباعة الإيصال': 'Print Receipt',
    'الرقم الضريبي': 'Tax ID (VAT)',
    'الخزنة الدافعة': 'Paying Treasury',
    'تاريخ الفاتورة': 'Invoice Date',
    'السيريال / IMEI': 'Serial / IMEI',
    'عميل جديد / مسجل': 'New / Existing Customer',
    'الفائدة / الرسوم': 'Interest / Fees',
    'إرسال PDF واتساب': 'Send PDF via WhatsApp',
    'التفاصيل والبيان': 'Details & Description',
    'نقدي (الخزنة الرئيسية)': 'Cash (Main Safe)',
    'نظام الأقساط والمتابعة': 'Installments & Tracking',
    'شراء الأجهزة المستعملة': 'Buy Used Devices',
    'المنتهي / نفدت الكمية (0)': 'Out of Stock (0)',
    'نقاط البيع السريعة (الكاشير)': 'Fast Point of Sale (POS)',
    'إضافة موظف جديد وتخصيص صلاحياته': 'Add Staff & Customize Permissions',
    'سطح المكتب فقط بدون نافذة تلقائية': 'Desktop Only (No Auto Window)',
    'تحويل عرض السعر إلى فاتورة مبيعات معتمدة': 'Convert Quotation to Approved Invoice',
    'سطح المكتب فقط (بدون فتح أي نافذة تلقائياً)': 'Desktop Only (No Auto Window)',
    'فتح كنافذة عائمة داخل سطح المكتب (TechZone OS)': 'Open as Floating Window (TechZone OS)',
    'فتح كنافذة مكبرة لملء الشاشة داخل سطح المكتب': 'Open Maximized Inside Desktop',
    'الانتقال المباشر للصفحة بملء الشاشة': 'Open Fullscreen Directly',
    '-- اختر عميلاً مسجلاً أو اكتب بياناته بالأسفل --': '-- Select existing customer or enter below --',
    'فتح': 'Open',
    'نشط': 'Active',
    'معطل': 'Disabled',
    'من:': 'From:',
    'إلى:': 'To:',
    'أخرى': 'Other',
    'تالف': 'Damaged',
    'تسجيل الدخول عبر الرمز السري': 'Sign In with PIN',
    'أدخل الرمز السري (PIN)': 'Enter PIN Code',
    'تحديث إحصائيات سطح المكتب': 'Refresh Desktop Stats',
    'جاري فحص الوردية...': 'Checking shift...',
    'تصغير النوافذ وإظهار سطح المكتب': 'Minimize windows & show desktop',

    // Core Branding & Modules
    'تك زون للإلكترونيات': 'TechZone Electronics',
    'تسجيل الدخول': 'Sign In',
    'دخول': 'Sign In',
    'خروج': 'Sign Out',
    'تسجيل الخروج': 'Sign Out',
    'سطح المكتب': 'Desktop',
    'ابدأ': 'Start',
    'قائمة ابدأ': 'Start Menu',
    'نقاط البيع (الكاشير)': 'Point of Sale (POS)',
    'نقاط البيع': 'POS',
    'المبيعات وعروض الأسعار': 'Sales & Quotations',
    'المبيعات': 'Sales',
    'العملاء والمديونيات': 'Customers & Debts',
    'العملاء': 'Customers',
    'نظام الأقساط': 'Installments',
    'الأقساط': 'Installments',
    'المخزون والمنتجات': 'Inventory & Products',
    'إدارة المخزون': 'Inventory Management',
    'المخزون': 'Inventory',
    'المشتريات والموردون': 'Purchases & Suppliers',
    'المشتريات': 'Purchases',
    'المحاسبة العامة والمالية': 'General Accounting & Finance',
    'المحاسبة': 'Accounting',
    'سجل المبيعات والمرتجعات': 'Sales History & Returns',
    'السجل': 'History',
    'مركز الصيانة': 'Repair Center',
    'الصيانة': 'Repairs',
    'شراء أجهزة مستعملة': 'Buy Used Devices',
    'المستعمل': 'Used',
    'التقارير والتحليلات': 'Reports & Analytics',
    'التقارير والتحليلات المالية': 'Financial Reports & Analytics',
    'التقارير': 'Reports',
    'الموظفون والصلاحيات': 'Staff & Permissions',
    'إدارة الموظفين والصلاحيات': 'Staff & Permissions Management',
    'الموظفون': 'Staff',
    'إعدادات النظام': 'System Settings',
    'إعدادات المتجر والنظام': 'Store & System Settings',
    'الإعدادات': 'Settings',
    'ملفي الشخصي وإعداداتي': 'My Profile & Settings',
    'ملفي الشخصي': 'My Profile',
    'ملفي': 'Profile',
    'معاينة وطباعة الإيصال': 'Receipt Preview & Print',
    'معاينة': 'Receipt',
    'لوحة المالك الرئيسي': 'Owner Control Panel',

    // Login Screen
    'أدخل الرمز السري فقط — سيتعرف النظام تلقائياً على المستخدم وصلاحياته': 'Enter your PIN only — the system automatically identifies your account and permissions',
    'النظام يعمل بكفاءة — تعرف ذكي من الرمز السري': 'System ready — smart PIN recognition',
    'الرمز السري غير صحيح': 'Invalid PIN',
    'يرجى إدخال الرمز السري أولاً': 'Please enter your PIN first',
    'اسم المستخدم': 'Username',
    'كلمة المرور': 'Password',
    'الرمز السري': 'PIN Code',
    'اختر المستخدم': 'Select User',
    'مسح': 'Clear',
    'تبديل المستخدم': 'Switch User',
    'نسيت رمز المدير؟': 'Forgot Admin PIN?',
    'تغيير الرمز السري الافتراضي': 'Change Default PIN',
    'العربية': 'العربية',
    'English': 'English',

    // Desktop OS Topbar, Taskbar & Lock Screen
    'تقسيم الشاشة (نصفين)': 'Split Screen (50/50)',
    'المظهر والخلفية': 'Appearance & Wallpaper',
    'الوضع النهاري': 'Light Mode',
    'الوضع الليلي': 'Dark Mode',
    'الوضع النهاري (Light)': 'Light Mode',
    'الوضع الليلي (Dark)': 'Dark Mode',
    'الوضع النهاري (Light Mode)': 'Light Mode',
    'الوضع الليلي (Dark Mode)': 'Dark Mode',
    'قفل': 'Lock',
    'تم قفل الشاشة لحماية النظام': 'Screen Locked for Security',
    'فك القفل والمتابعة': 'Unlock & Continue',
    'تحديث': 'Refresh',
    'مبيعات اليوم (المتجر)': "Today's Sales (Store)",
    'عدد الفواتير': 'Invoices Count',
    'نواقص المخزون': 'Low Stock',
    'صيانة قيد العمل': 'Active Repairs',
    'فتح نافذة نقاط البيع (الكاشير)': 'Open Point of Sale (POS)',
    'الوردية مغلقة — اضغط للفتح': 'Shift Closed — Click to Open',
    'الوردية مفتوحة': 'Shift Open',
    'بحث في التطبيقات...': 'Search apps...',
    'إغلاق': 'Close',
    'إلغاء': 'Cancel',
    'حفظ': 'Save',
    'حفظ التغييرات': 'Save Changes',
    'حذف': 'Delete',
    'تعديل': 'Edit',
    'إضافة': 'Add',
    'بحث': 'Search',
    'تصفية': 'Filter',
    'طباعة': 'Print',
    'طباعة A4': 'Print A4',
    'تصدير Excel': 'Export Excel',
    'تصدير PDF': 'Export PDF',
    'إرسال عبر واتساب': 'Send via WhatsApp',
    'نعم': 'Yes',
    'لا': 'No',
    'تأكيد': 'Confirm',
    'رجوع': 'Back',
    'التالي': 'Next',
    'السابق': 'Previous',
    'الكل': 'All',
    'الإجمالي': 'Total',
    'المجموع': 'Subtotal',
    'الخصم': 'Discount',
    'الضريبة': 'Tax',
    'الصافي': 'Net',
    'المدفوع': 'Paid',
    'المتبقي': 'Remaining',
    'التاريخ': 'Date',
    'الوقت': 'Time',
    'الحالة': 'Status',
    'إجراءات': 'Actions',
    'ملاحظات': 'Notes',
    'البيان': 'Description',
    'المرجع': 'Reference',
    'المستخدم': 'User',
    'الموظف': 'Employee',
    'العميل': 'Customer',
    'المورد': 'Supplier',
    'الهاتف': 'Phone',
    'رقم الهاتف': 'Phone Number',
    'العنوان': 'Address',
    'الكمية': 'Qty',
    'السعر': 'Price',
    'التكلفة': 'Cost',
    'القيمة': 'Value',
    'الربح': 'Profit',
    'المديونية': 'Debt',
    'الرصيد': 'Balance',
    'نقدي': 'Cash',
    'محفظة': 'Wallet',
    'آجل': 'Credit',
    'تحويل بنكي': 'Bank Transfer',
    'من تاريخ': 'From Date',
    'إلى تاريخ': 'To Date',

    // Profile Page
    'البيانات الشخصية والأمان': 'Personal Info & Security',
    'إعدادات التشغيل والمظهر الشخصي': 'Startup & Personal Appearance',
    'الاسم الكامل': 'Full Name',
    'معرف الدخول (Username)': 'Username',
    'تغيير كلمة السر / الرمز السري (اختياري)': 'Change Password / PIN (Optional)',
    'الرمز السري الحالي': 'Current PIN',
    'الرمز السري الجديد': 'New PIN',
    'الصفحة التي تفتح تلقائياً عند تسجيل دخولك': 'Default Start Page on Login',
    'طريقة فتح الصفحة عند الدخول': 'Startup Window Mode',
    'حجم بطاقات المنتجات في الكاشير (خاص بحسابك)': 'POS Product Card Size (Per-User)',
    'لغة واجهة البرنامج الخاصة بحسابك': 'Your Personal Interface Language',
    'العربية (من اليمين لليسار RTL)': 'Arabic (RTL)',
    'English (Left-to-Right LTR)': 'English (LTR)',
    'الوضع المفضل للمظهر (يطبق على سطح المكتب وجميع النوافذ)': 'Preferred Theme (Desktop & All Windows)',
    'لون النظام والأزرار المفضل:': 'Preferred Accent Color:',
    'خلفية سطح المكتب المفضلة:': 'Preferred Desktop Wallpaper:',
    'حفظ بيانات ملفي الشخصي وإعداداتي': 'Save My Profile & Settings',
    'التحكم في أيقونات سطح المكتب وشريط المهام (خاص بحسابي فقط)': 'Desktop & Taskbar Icons Visibility (My Account Only)',
    'إظهار الكل (سطح المكتب + شريط المهام)': 'Show All (Desktop + Taskbar)',
    'إخفاء الكل من سطح المكتب': 'Hide All from Desktop',
    'إخفاء الكل من شريط المهام': 'Hide All from Taskbar',
    'شريط المهام': 'Taskbar',

    // Settings Tabs & Controls
    'إعدادات المتجر والضريبة والإيصال والدفع': 'Store, Tax, Receipt & Payments',
    'طريقة تسجيل الدخول والفتح الافتراضي': 'Login Mode & Default Startup',
    'تصميم القوالب وجميع الفواتير': 'Invoice & Receipt Templates',
    'النسخ الاحتياطي وقاعدة البيانات': 'Backups & Database',
    'سجل رقابة العمليات (Audit Log)': 'Activity Audit Log',
    'سجل رقابة العمليات اليومية الشامل (General Audit Log)': 'General Activity Audit Log',
    'سلوك إغلاق النافذة من علامة (X) وشريط النظام بجوار الساعة': 'Close Button (X) & System Tray Behavior',
    'إغلاق البرنامج نهائياً عند الضغط على علامة (X) أعلى النافذة': 'Exit application completely when clicking (X)',
    'قفل الشاشة التلقائي عند الخمول (Auto-Lock on Idle)': 'Auto-Lock Screen on Idle',
    'التنبيهات الصوتية والمرئية وحد ائتمان العملاء في الكاشير': 'POS Audio/Visual Alerts & Customer Credit Limits',
    'تفعيل الأصوات التفاعلية في الكاشير': 'Enable POS Interactive Sounds',
    'تنبيه فوري بنواقص المخزون أثناء البيع': 'Instant Low-Stock Alert During Sale',
    'منع البيع الآجل عند تجاوز حد الائتمان': 'Block Credit Sale Over Credit Limit',
    'ترحيل الصور للقرص وضغط القاعدة (VACUUM)': 'Migrate Images to Disk & VACUUM DB',
    'إنشاء نسخة احتياطية فورية': 'Create Backup Now',
    'تحديث السجل': 'Refresh Log',
    'طباعة السجل A4': 'Print Log A4',

    // Inventory & Barcode Studio
    'إضافة منتج جديد': 'Add New Product',
    'تعديل منتج': 'Edit Product',
    'استوديو طباعة ملصقات الباركود': 'Barcode Label Studio',
    'استوديو طباعة ملصقات الباركود والأسعار (Barcode & Shelf Labels Studio)': 'Barcode & Shelf Labels Studio',
    'جرد المخزون (الموجود والمنتهي)': 'Inventory Stocktake',
    'الأرقام التسلسلية': 'Serial Numbers',
    'الفئات': 'Categories',
    'طباعة الملصقات الآن': 'Print Labels Now',
    'إجمالي الأصناف': 'Total Items',
    'الأصناف الموجودة': 'In Stock Items',
    'مخزون منخفض': 'Low Stock',
    'المنتهي (نفدت)': 'Out of Stock',
    'متوفر': 'In Stock',
    'منخفض': 'Low',
    'منتهي': 'Out',

    // POS
    'سلة المشتريات': 'Shopping Cart',
    'السلة فارغة': 'Cart is empty',
    'إتمام البيع والدفع': 'Checkout & Pay',
    'إتمام البيع': 'Complete Sale',
    'تفريغ السلة': 'Clear Cart',
    'فتح وردية': 'Open Shift',
    'إغلاق الوردية': 'Close Shift',
    'ملخص الوردية': 'Shift Summary',
    'بحث بالاسم أو الباركود أو السيريال...': 'Search by name, barcode, or serial...',

    // Customers
    'إضافة عميل جديد': 'Add New Customer',
    'تعديل بيانات العميل': 'Edit Customer',
    'كشف الحساب': 'Statement',
    'المديونون فقط': 'Indebted Only',
    'إجمالي العملاء': 'Total Customers',
    'عملاء عليهم مديونية': 'Indebted Customers',
    'إجمالي المديونيات': 'Total Receivables',
    'خالص (0.00)': 'Settled (0.00)',

    // Purchases & Accounting & Reports
    'فواتير المشتريات': 'Purchase Bills',
    'أوامر الشراء': 'Purchase Orders',
    'المرتجعات وتكلفة WAC': 'Returns & WAC Cost',
    'الموردون': 'Suppliers',
    'فاتورة مشتريات جديدة': 'New Purchase Bill',
    'أمر شراء جديد': 'New Purchase Order',
    'مورد جديد': 'New Supplier',
    'سند صرف لمورد': 'Supplier Payment Voucher',
    '1. لوحة المحاسبة السريعة': '1. Accounting Dashboard',
    '2. المصروفات التشغيلية': '2. Operating Expenses',
    '3. الخزائن والتحويلات': '3. Treasuries & Transfers',
    '4. شجرة الحسابات (COA)': '4. Chart of Accounts (COA)',
    '5. دفتر اليومية والقيود': '5. General Journal',
    '6. القوائم والتقارير المالية': '6. Financial Statements',
    'معالج الترصيد الافتتاحي': 'Opening Balance Wizard',
    '+ تسجيل مصروف': '+ Record Expense',
    '+ قيد يومية يدوي': '+ Manual Journal Entry',
    'مدين': 'Debit',
    'دائن': 'Credit',
    'مرحل': 'Posted',
    'معكوس': 'Reversed',
    'مسودة': 'Draft',
    'معتمدة': 'Posted',
    'الأرباح والخسائر': 'Profit & Loss',
    'مديونيات العملاء': 'Customer Receivables',
    'مستحقات الموردين': 'Supplier Payables',
    'التدفقات النقدية': 'Cash Flow',
    'تقييم المخزون': 'Inventory Valuation',
    'القسم غير مُفعّل': 'Module Disabled',
    'هذا القسم معطل حالياً من إعدادات المالك الرئيسي للبرنامج.': 'This module is currently disabled by the system owner.',
    'العودة لسطح المكتب': 'Back to Desktop',
  };

  const PARTIAL_PAIRS = [
    ['وردية مفتوحة', 'Shift Open'],
    ['الوردية مفتوحة', 'Shift Open'],
    ['وردية مغلقة', 'Shift Closed'],
    ['اضغط للفتح', 'Click to Open'],
    ['اضغط للملف الشخصي', 'Click for Profile'],
    ['مدير النظام', 'System Admin'],
    ['بواسطة', 'By'],
    ['قطعة', 'pcs'],
    ['فاتورة', 'Invoice'],
    ['مورد', 'Supplier'],
    ['عميل', 'Customer'],
    ['ملصق', 'Labels'],
    ['ج.م', 'EGP'],
    ['تم الحفظ بنجاح', 'Saved successfully'],
    ['تم الحذف', 'Deleted'],
    ['تم البيع بنجاح', 'Sale completed successfully'],
    ['تم فك قفل الشاشة بنجاح', 'Screen unlocked successfully'],
    ['تم حفظ بيانات ملفك الشخصي', 'Your profile & settings were saved'],
    ['تم حفظ إعدادات', 'Settings saved'],
    ['تم تحديث', 'Updated'],
    ['لا توجد نتائج', 'No results'],
    ['لا توجد بيانات', 'No data'],
    ['جاري التحميل...', 'Loading...'],
    ['فاتورة مبيعات', 'Sales Invoice'],
    ['فاتورة مشتريات', 'Purchase Bill'],
    ['سند قبض', 'Receipt Voucher'],
    ['سند صرف', 'Payment Voucher'],
    ['عرض سعر', 'Quotation'],
    ['قيد يومية', 'Journal Entry'],
    ['الوردية مغلقة', 'Shift Closed'],
    ['الوردية مفتوحة', 'Shift Open'],
    ['ممنوع:', 'Forbidden:'],
    ['تنبيه مخزون:', 'Stock Alert:'],
    ['تنبيه حد ائتمان:', 'Credit Limit Alert:'],
  ];


  function mergeCustomMap(mapObj) {
    if (!mapObj || typeof mapObj !== 'object') return;
    for (const [k, v] of Object.entries(mapObj)) {
      if (k && typeof v === 'string' && v.trim()) {
        EXACT_MAP[k.trim()] = v.trim();
      }
    }
  }

  // Load cached custom user translations immediately for zero-latency startup
  try {
    const cached = localStorage.getItem('tz-i18n-custom');
    if (cached) mergeCustomMap(JSON.parse(cached));
  } catch (e) {}

  async function reloadCustomTranslations() {
    try {
      if (typeof api !== 'function') return;
      const mapObj = await api('translations_map');
      if (mapObj && typeof mapObj === 'object') {
        try { localStorage.setItem('tz-i18n-custom', JSON.stringify(mapObj)); } catch (e) {}
        mergeCustomMap(mapObj);
        applyLanguageEverywhere(getSavedLang());
      }
    } catch (e) {}
  }

  function getSavedLang() {
    try {
      const v = (localStorage.getItem('tz-lang') || 'ar').toLowerCase();
      return v === 'en' ? 'en' : 'ar';
    } catch (e) {
      return 'ar';
    }
  }

  function translateText(arStr, lang) {
    if (!arStr || lang !== 'en') return arStr;
    const raw = String(arStr);
    const trimmed = raw.trim();
    if (!trimmed) return raw;
    if (EXACT_MAP[trimmed]) {
      return raw.replace(trimmed, EXACT_MAP[trimmed]);
    }
    // Check normalized whitespace match
    const compact = trimmed.replace(/\s+/g, ' ');
    if (EXACT_MAP[compact]) {
      return raw.replace(trimmed, EXACT_MAP[compact]);
    }
    let out = raw;
    for (const [ar, en] of PARTIAL_PAIRS) {
      if (out.includes(ar)) out = out.split(ar).join(en);
    }
    return out;
  }

  function applyDirectionToDoc(doc, lang) {
    if (!doc || !doc.documentElement) return;
    const isEn = lang === 'en';
    doc.documentElement.lang = isEn ? 'en' : 'ar';
    doc.documentElement.dir = isEn ? 'ltr' : 'rtl';
    if (doc.body) {
      doc.body.classList.toggle('tz-lang-en', isEn);
      doc.body.classList.toggle('tz-lang-ar', !isEn);
    }
    let st = doc.getElementById('tz-i18n-dir-style');
    if (!st && doc.head) {
      st = doc.createElement('style');
      st.id = 'tz-i18n-dir-style';
      doc.head.appendChild(st);
    }
    if (st) {
      st.textContent = isEn
        ? `html[dir="ltr"] .text-right { text-align: left !important; }
           html[dir="ltr"] th, html[dir="ltr"] td { text-align: left; }
           html[dir="ltr"] th.text-center, html[dir="ltr"] td.text-center { text-align: center; }`
        : '';
    }
  }

  function translateSubtree(rootNode, lang) {
    if (!rootNode) return;
    const doc = rootNode.ownerDocument || (rootNode.nodeType === 9 ? rootNode : document);
    const isEn = lang === 'en';

    // 1. Text nodes
    const walker = doc.createTreeWalker(rootNode, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const p = node.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        const tag = p.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') return NodeFilter.FILTER_REJECT;
        if (p.classList && (p.classList.contains('material-icons-round') || p.classList.contains('material-icons-outlined') || p.classList.contains('material-icons'))) {
          return NodeFilter.FILTER_REJECT;
        }
        if (p.hasAttribute && p.hasAttribute('data-no-i18n')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });

    let node;
    while ((node = walker.nextNode())) {
      const cur = node.nodeValue;
      if (!cur || !cur.trim()) continue;
      if (isEn) {
        if (node._tzOrigAr === undefined) node._tzOrigAr = cur;
        const tr = translateText(node._tzOrigAr, 'en');
        if (tr !== cur) node.nodeValue = tr;
      } else {
        if (node._tzOrigAr !== undefined && node.nodeValue !== node._tzOrigAr) {
          node.nodeValue = node._tzOrigAr;
        }
      }
    }

    // 2. Attributes (placeholder, title, aria-label)
    if (rootNode.querySelectorAll) {
      const els = rootNode.querySelectorAll('[placeholder],[title],[aria-label]');
      els.forEach((el) => {
        if (el.hasAttribute('data-no-i18n')) return;
        ['placeholder', 'title', 'aria-label'].forEach((attr) => {
          const val = el.getAttribute(attr);
          if (!val) return;
          const origKey = 'data-tz-orig-' + attr;
          if (isEn) {
            if (!el.hasAttribute(origKey)) el.setAttribute(origKey, val);
            const orig = el.getAttribute(origKey);
            const tr = translateText(orig, 'en');
            if (tr !== val) el.setAttribute(attr, tr);
          } else if (el.hasAttribute(origKey)) {
            el.setAttribute(attr, el.getAttribute(origKey));
          }
        });
      });
    }
  }

  function ensureObserver(doc, lang) {
    if (!doc || !doc.body) return;
    if (doc._tzI18nObs) {
      doc._tzI18nObs.disconnect();
      doc._tzI18nObs = null;
    }
    if (lang !== 'en') return;
    let timer = null;
    const obs = new MutationObserver(() => {
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        if (getSavedLang() === 'en' && doc.body) {
          translateSubtree(doc.body, 'en');
        }
      }, 45);
    });
    obs.observe(doc.body, { childList: true, subtree: true });
    doc._tzI18nObs = obs;
  }

  function applyLanguageToDoc(doc, lang) {
    const clean = lang === 'en' ? 'en' : 'ar';
    applyDirectionToDoc(doc, clean);
    if (doc) {
      if (clean === 'en') {
        if (doc._tzOrigTitle === undefined) doc._tzOrigTitle = doc.title;
        doc.title = translateText(doc._tzOrigTitle, 'en');
      } else if (doc._tzOrigTitle !== undefined) {
        doc.title = doc._tzOrigTitle;
      }
    }
    if (doc && doc.body) {
      translateSubtree(doc.body, clean);
      ensureObserver(doc, clean);
    }
  }

  function applyLanguageEverywhere(lang) {
    const clean = lang === 'en' ? 'en' : 'ar';
    try { localStorage.setItem('tz-lang', clean); } catch (e) {}
    applyLanguageToDoc(document, clean);
    try {
      const topWin = window.top || window;
      const topDoc = topWin.document || document;
      if (topDoc !== document) applyLanguageToDoc(topDoc, clean);
      topDoc.querySelectorAll('iframe').forEach((fr) => {
        try {
          if (fr.contentDocument) applyLanguageToDoc(fr.contentDocument, clean);
          if (fr.contentWindow && typeof fr.contentWindow.onLanguageChanged === 'function') {
            fr.contentWindow.onLanguageChanged(clean);
          }
        } catch (e) {}
      });
      if (topWin.TZOS && typeof topWin.TZOS.onLanguageChanged === 'function') {
        topWin.TZOS.onLanguageChanged(clean);
      }
    } catch (e) {}
    return clean;
  }

  // Early direction apply before body renders to avoid RTL/LTR flash
  const initialLang = getSavedLang();
  applyDirectionToDoc(document, initialLang);
  document.addEventListener('DOMContentLoaded', () => {
    const cur = getSavedLang();
    applyLanguageToDoc(document, cur);
    setTimeout(() => { reloadCustomTranslations(); }, 250);
  });

  window.TZI18N = {
    getLang: getSavedLang,
    translateText,
    applyLanguageToDoc,
    applyLanguageEverywhere,
    EXACT_MAP,
    mergeCustomMap,
    reloadCustomTranslations,
  };
  window.applyLanguageEverywhere = applyLanguageEverywhere;
})();
