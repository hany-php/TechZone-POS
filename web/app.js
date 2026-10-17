/* تك زون للإلكترونيات — جسر API + تنقّل + صلاحيات + وضع ليلي + دعم نظام التشغيل (TechZone OS) */

/* ===== الوضع الليلي (مبكر جداً لتجنب الوميض + متزامن مع جميع نوافذ النظام) ===== */
if (localStorage.getItem('tz-theme') === 'dark') document.documentElement.classList.add('dark');

function applyThemeEverywhere(isDark) {
  const darkBool = !!isDark;
  localStorage.setItem('tz-theme', darkBool ? 'dark' : 'light');
  document.documentElement.classList.toggle('dark', darkBool);
  if (document.body) document.body.classList.toggle('dark-body', darkBool);
  try {
    const topWin = (window.top) ? window.top : window;
    const topDoc = topWin.document || document;
    topDoc.documentElement.classList.toggle('dark', darkBool);
    if (topDoc.body) topDoc.body.classList.toggle('dark-body', darkBool);
    topDoc.querySelectorAll('iframe').forEach((fr) => {
      try {
        if (fr.contentDocument && fr.contentDocument.documentElement) {
          fr.contentDocument.documentElement.classList.toggle('dark', darkBool);
          if (fr.contentDocument.body) fr.contentDocument.body.classList.toggle('dark-body', darkBool);
        }
      } catch (e) {}
    });
    if (topWin.TZOS && typeof topWin.TZOS.onThemeChanged === 'function') {
      topWin.TZOS.onThemeChanged(darkBool);
    }
  } catch (e) {}
}


/* ===== تخصيص اللون الأساسي للنظام لكل مستخدم (Accent Color) ===== */
function _hexToRgb(hex) {
  const h = String(hex || '#137fec').replace('#', '').trim();
  if (h.length !== 6) return { r: 19, g: 127, b: 236 };
  const num = parseInt(h, 16);
  if (isNaN(num)) return { r: 19, g: 127, b: 236 };
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

function applyAccentToDoc(doc, hex) {
  if (!doc || !doc.head) return;
  const { r, g, b } = _hexToRgb(hex);
  const dr = Math.max(0, Math.round(r * 0.82));
  const dg = Math.max(0, Math.round(g * 0.82));
  const db = Math.max(0, Math.round(b * 0.82));
  let st = doc.getElementById('tz-accent-style');
  if (!st) {
    st = doc.createElement('style');
    st.id = 'tz-accent-style';
    doc.head.appendChild(st);
  }
  st.textContent = `
    :root { --tz-accent: rgb(${r}, ${g}, ${b}); }
    .bg-primary { background-color: rgb(${r}, ${g}, ${b}) !important; }
    .hover\:bg-primary:hover, .hover\:bg-primary-dark:hover, .hover\:bg-primary\/90:hover { background-color: rgb(${dr}, ${dg}, ${db}) !important; }
    .text-primary { color: rgb(${r}, ${g}, ${b}) !important; }
    .hover\:text-primary:hover, .dark\:hover\:text-primary:hover:is(.dark *) { color: rgb(${r}, ${g}, ${b}) !important; }
    .border-primary, .focus\:border-primary:focus, .hover\:border-primary:hover { border-color: rgb(${r}, ${g}, ${b}) !important; }
    .bg-primary\/10 { background-color: rgba(${r}, ${g}, ${b}, 0.12) !important; }
    .bg-primary\/20 { background-color: rgba(${r}, ${g}, ${b}, 0.22) !important; }
    .bg-primary\/5 { background-color: rgba(${r}, ${g}, ${b}, 0.06) !important; }
    .border-primary\/30, .hover\:border-primary\/30:hover { border-color: rgba(${r}, ${g}, ${b}, 0.35) !important; }
    .focus\:ring-primary:focus { --tw-ring-color: rgba(${r}, ${g}, ${b}, 0.55) !important; }
    .accent-blue-600 { accent-color: rgb(${r}, ${g}, ${b}) !important; }
    #os-start-btn { background: linear-gradient(135deg, rgb(${r}, ${g}, ${b}) 0%, rgb(${dr}, ${dg}, ${db}) 100%) !important; box-shadow: 0 6px 16px -2px rgba(${r}, ${g}, ${b}, 0.55) !important; }
    .tz-os-window.win-active { box-shadow: 0 30px 70px -12px rgba(0,0,0,0.6), 0 0 0 2px rgba(${r}, ${g}, ${b}, 0.72) !important; }
    .dock-item.dock-active { background: rgba(${r}, ${g}, ${b}, 0.35) !important; border-color: rgba(${r}, ${g}, ${b}, 0.75) !important; }
  `;
}

function applyAccentColorEverywhere(hex) {
  const cleanHex = hex || '#137fec';
  localStorage.setItem('tz-accent', cleanHex);
  applyAccentToDoc(document, cleanHex);
  try {
    const topDoc = (window.top && window.top.document) ? window.top.document : document;
    applyAccentToDoc(topDoc, cleanHex);
    topDoc.querySelectorAll('iframe').forEach((fr) => {
      try {
        if (fr.contentDocument) applyAccentToDoc(fr.contentDocument, cleanHex);
      } catch (e) {}
    });
  } catch (e) {}
}

function toggleTheme() {
  let curDark = document.documentElement.classList.contains('dark');
  try {
    if (window.top && window.top.document) {
      curDark = window.top.document.documentElement.classList.contains('dark');
    }
  } catch (e) {}
  const on = !curDark;
  applyThemeEverywhere(on);
  try {
    if (CURRENT_USER) {
      CURRENT_USER.theme_mode = on ? 'dark' : 'light';
      api('user_pref_save', { theme_mode: on ? 'dark' : 'light' }).catch(() => {});
    }
  } catch (e) {}
}

/* ===== جسر pywebview (يدعم النافذة الرئيسية وجميع النوافذ الفرعية داخل سطح المكتب) ===== */
function _resolvePywebview() {
  if (window.pywebview && window.pywebview.api) return window.pywebview;
  try {
    if (window.parent && window.parent !== window && window.parent.pywebview && window.parent.pywebview.api) {
      window.pywebview = window.parent.pywebview;
      return window.pywebview;
    }
    if (window.top && window.top !== window && window.top.pywebview && window.top.pywebview.api) {
      window.pywebview = window.top.pywebview;
      return window.pywebview;
    }
  } catch (e) {}
  return null;
}

const _apiWait = new Promise((resolve, reject) => {
  if (_resolvePywebview()) {
    resolve();
    return;
  }
  const poll = setInterval(() => {
    if (_resolvePywebview()) {
      clearInterval(poll);
      resolve();
    }
  }, 40);
  window.addEventListener('pywebviewready', () => {
    clearInterval(poll);
    _resolvePywebview();
    resolve();
  }, { once: true });
  setTimeout(() => {
    clearInterval(poll);
    if (_resolvePywebview()) resolve();
    else reject(new Error('bridge-timeout'));
  }, 4500);
});

function showBridgeError() {
  if (document.getElementById('tz-bridge-err')) return;
  const d = document.createElement('div');
  d.id = 'tz-bridge-err';
  d.dir = 'rtl';
  d.style.cssText = 'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:#f6f7f8;padding:24px;font-family:sans-serif';
  d.innerHTML = '<div style="max-width:480px;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;text-align:center">'
    + '<p style="font-size:20px;font-weight:bold;margin-bottom:8px">تعذر الاتصال بالبرنامج الداخلي</p>'
    + '<p style="color:#64748b;font-size:14px;margin-bottom:16px">افتح هذه الصفحة من داخل تطبيق «تك زون» (<span style="font-family:monospace">python app\\main.py</span>) وليس من المتصفح مباشرة.</p>'
    + '<button onclick="location.reload()" style="background:#137fec;color:#fff;border:0;border-radius:10px;padding:10px 28px;font-weight:bold;cursor:pointer">إعادة المحاولة</button></div>';
  document.body.appendChild(d);
}

async function api(name, payload) {
  try { await _apiWait; }
  catch (e) { showBridgeError(); throw new Error('انقطاع الاتصال بالبرنامج الداخلي'); }
  const bridge = _resolvePywebview();
  if (!bridge || !bridge.api) { showBridgeError(); throw new Error('انقطاع الاتصال بالبرنامج الداخلي'); }
  let res;
  try {
    res = await bridge.api.call(name, payload === undefined ? null : payload);
  } catch (e) {
    throw new Error('انقطاع الاتصال بالبرنامج الداخلي');
  }
  if (!res || !res.ok) throw new Error((res && res.error) || 'خطأ غير معروف');
  return res.data;
}

/* ===== تنسيق وصلاحيات ===== */
let CURRENCY = 'ج.م';
let SETTINGS = {};
function whatsappEnabled() {
  return !SETTINGS || SETTINGS.whatsapp_send_enabled !== '0';
}
function applyWhatsappVisibility() {
  const on = whatsappEnabled();
  if (document.body) document.body.classList.toggle('wa-disabled', !on);
  document.querySelectorAll('[data-wa-toggle]').forEach((el) => {
    el.style.display = on ? '' : 'none';
  });
}
let CURRENT_USER = null;

function hasPerm(key, u) {
  const target = u || CURRENT_USER;
  if (!target) return false;
  if (target.role === 'admin') return true;
  const p = target.permissions || {};
  if (Array.isArray(key)) return key.some((k) => !!p[k]);
  return !!p[key];
}

function fmt(cents) {
  return ((cents || 0) / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function money(cents) { return fmt(cents) + ' ' + CURRENCY; }
function n(v) { return (v || 0).toLocaleString('en-US'); }
function toAmount(str) { const x = parseFloat(String(str).replace(/,/g, '')); return isNaN(x) ? 0 : x; }
function fmtDT(s) { return s ? s.slice(0, 16) : ''; }
function todayISO() { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ===== Toast ===== */
function toast(msg, kind) {
  let zone = document.getElementById('toast-zone');
  if (!zone) {
    zone = document.createElement('div');
    zone.id = 'toast-zone';
    zone.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 items-center pointer-events-none';
    document.body.appendChild(zone);
  }
  const el = document.createElement('div');
  el.className = 'px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white transition-opacity ' +
    (kind === 'error' ? 'bg-red-600' : kind === 'warn' ? 'bg-amber-600' : 'bg-emerald-600');
  el.textContent = msg;
  zone.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 400); }, 3200);
}
async function guard(fn) {
  try { return await fn(); } catch (e) { toast(e.message || String(e), 'error'); return null; }
}

/* ===== شريط التنقل الموحد (يتكيف مع صلاحيات المستخدم وبيئة نظام التشغيل) ===== */
const NAV = [
  { page: 'desktop', href: 'desktop.html', icon: 'desktop_windows', label: 'سطح المكتب (النظام)' },
  { page: 'pos', href: 'pos.html', icon: 'point_of_sale', label: 'نقاط البيع' },
  { page: 'sales_quotes', href: 'sales_quotes.html', icon: 'description', label: 'المبيعات وعروض الأسعار' },
  { page: 'customers', href: 'customers.html', icon: 'people', label: 'العملاء والمديونيات', perm: ['customers_view', 'customers_edit'] },
  { page: 'history', href: 'history.html', icon: 'receipt_long', label: 'سجل المبيعات' },
  { page: 'receipt', href: 'receipt.html', icon: 'print', label: 'معاينة وطباعة الإيصال' },
  { page: 'repair', href: 'repair.html', icon: 'build', label: 'الصيانة', perm: ['repair_view', 'repair_edit'] },
  { page: 'inventory', href: 'inventory.html', icon: 'inventory_2', label: 'المخزون', perm: ['inventory_view', 'inventory_edit'] },
  { page: 'buy_used', href: 'buy_used.html', icon: 'phonelink_setup', label: 'شراء أجهزة مستعملة', perm: 'used_manage' },
  { page: 'reports', href: 'reports.html', icon: 'bar_chart', label: 'التقارير والتحليلات', perm: 'reports_view' },
  { page: 'staff', href: 'staff.html', icon: 'manage_accounts', label: 'الموظفون والصلاحيات', perm: 'settings_manage' },
  { page: 'settings', href: 'settings.html', icon: 'settings', label: 'إعدادات النظام', perm: 'settings_manage' },
  { page: 'profile', href: 'profile.html', icon: 'account_circle', label: 'ملفي الشخصي وإعداداتي' },
  { page: 'index', href: 'index.html', icon: 'switch_account', label: 'تبديل المستخدم' },
];

function _setupOsWindowInterceptors() {
  if (window._tzOsIntercepted) return;
  window._tzOsIntercepted = true;
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href]');
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
    try {
      if (window.parent && window.parent !== window && window.parent.TZOS) {
        // السماح لصفحتي العملاء وكشف حساب العميل بالتنقل داخل نفس نافذة العملاء
        if (href.startsWith('customers.html') || href.startsWith('customer_details.html')) {
          return;
        }
        e.preventDefault();
        window.parent.TZOS.openUrlInApp(href);
      }
    } catch (err) {}
  });
}

function renderSidebar(current, user) {
  // إذا كانت الصفحة مفتوحة كنافذة داخل نظام التشغيل (desktop.html)، لا نعرض الشريط الجانبي المكرر
  try {
    if (window.self !== window.top && window.parent && window.parent.TZOS) {
      _setupOsWindowInterceptors();
      return;
    }
  } catch (e) {}

  if (current === 'desktop') return;

  const host = document.getElementById('shell');
  if (!host || host.querySelector('aside.tz-nav')) return;
  const items = NAV.filter((x) => !x.perm || hasPerm(x.perm, user))
    .map((x) => {
      const active = x.page === current;
      const isOsBtn = x.page === 'desktop';
      return `<a href="${x.href}" class="flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-colors ${isOsBtn
        ? 'bg-primary text-white shadow-md shadow-primary/20 mb-2 font-bold'
        : active
          ? 'bg-primary/10 text-primary'
          : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white'}">
        <span class="material-icons-round">${x.icon}</span><span>${x.label}</span></a>`;
    }).join('');
  const aside = document.createElement('aside');
  aside.className = 'tz-nav w-64 shrink-0 bg-surface-light dark:bg-surface-dark border-l border-gray-200 dark:border-gray-800 flex-col hidden md:flex h-screen sticky top-0 z-20 shadow-sm';
  aside.id = 'tz-aside';
  aside.innerHTML = `
    <div class="h-16 flex items-center justify-center border-b border-gray-100 dark:border-gray-800 px-4">
      <div class="flex items-center gap-3 min-w-0">
        <div class="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white shrink-0">
          <span class="material-icons-round text-xl">memory</span></div>
        <h1 id="tz-store" class="font-bold text-base tracking-wide text-gray-800 dark:text-white truncate">${esc(SETTINGS.store_name || 'تك زون')}</h1>
      </div>
    </div>
    <nav class="flex-1 overflow-y-auto py-6 px-4 space-y-1">
      <div class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4 px-2">القائمة الرئيسية</div>
      ${items}
      <div class="text-xs font-semibold text-gray-400 uppercase tracking-wider mt-8 mb-4 px-2">المظهر</div>
      <button onclick="toggleTheme()" class="w-full flex items-center gap-3 px-4 py-3 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl font-medium transition-colors text-right">
        <span class="material-icons-round dark:hidden">dark_mode</span>
        <span class="material-icons-round hidden dark:inline">light_mode</span>
        <span>وضع ليلي / نهاري</span>
      </button>
    </nav>
    <div class="p-4 border-t border-gray-100 dark:border-gray-800">
      <div class="flex items-center gap-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-800/50">
        <a href="profile.html" class="flex items-center gap-3 flex-1 min-w-0 group" title="اضغط لفتح ملفك الشخصي وتغيير اسمك أو صورتك أو إعداداتك">
          <div class="w-10 h-10 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold overflow-hidden shrink-0 border border-primary/30">
            ${user.avatar ? `<img src="${esc(user.avatar)}" class="w-full h-full object-cover" alt="${esc(user.name)}"/>` : esc((user.name || '؟').slice(0, 1))}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-bold text-gray-900 dark:text-white group-hover:text-primary truncate">${esc(user.name)}</p>
            <p class="text-xs text-gray-500 truncate">${user.role === 'admin' ? 'مدير' : 'موظف / كاشير'} · إعداداتي</p>
          </div>
        </a>
        <button id="tz-logout" class="text-gray-400 hover:text-red-500" title="تسجيل الخروج">
          <span class="material-icons-round">logout</span></button>
      </div>
    </div>`;
  host.prepend(aside);
  aside.querySelector('#tz-logout').addEventListener('click', async () => { await guard(() => api('logout')); location.href = 'index.html'; });
  if (!document.getElementById('tz-menu')) {
    const btn = document.createElement('button');
    btn.id = 'tz-menu';
    btn.className = 'md:hidden fixed bottom-5 right-5 z-40 w-14 h-14 rounded-full bg-primary text-white shadow-lg shadow-primary/40 flex items-center justify-center';
    btn.innerHTML = '<span class="material-icons-round text-2xl">menu</span>';
    btn.addEventListener('click', () => {
      const a = document.getElementById('tz-aside');
      const open = a.classList.toggle('tz-open');
      a.classList.toggle('hidden', false);
      a.classList.toggle('flex', true);
      a.style.cssText = open
        ? 'position:fixed;top:0;bottom:0;right:0;z-index:50;display:flex;box-shadow:0 0 40px rgba(0,0,0,.25)'
        : '';
    });
    document.body.appendChild(btn);
    aside.querySelectorAll('nav a').forEach((l) => l.addEventListener('click', () => {
      if (window.innerWidth >= 768) return;
      aside.classList.remove('tz-open');
      aside.classList.add('hidden');
      aside.classList.remove('flex');
      aside.style.cssText = '';
    }));
  }
}

/* ===== عنوان النافذة/التبويب من اسم المحل ===== */
function syncTitle(pageLabel) {
  const name = (SETTINGS.store_name || 'تك زون للإلكترونيات').trim() || 'تك زون للإلكترونيات';
  document.title = pageLabel ? `${pageLabel} - ${name}` : name;
}

/* ===== حارس الصفحة: جلسة + صلاحيات + إعدادات + شريط جانبي ===== */
async function pageInit(current, opts) {
  let sess;
  try { sess = await api('session'); } catch (e) { toast('تعذر الاتصال بالبرنامج', 'error'); return null; }
  if (!sess || !sess.user) {
    if (window.top && window.top !== window) window.top.location.href = 'index.html';
    else location.href = 'index.html';
    return null;
  }
  const user = sess.user;
  CURRENT_USER = user;
  if (opts) {
    if (opts.perm && !hasPerm(opts.perm, user)) {
      toast('ليست لديك صلاحية لدخول هذه الصفحة', 'warn');
      if (window.self === window.top) location.href = 'desktop.html';
      return null;
    } else if (opts.admin && !opts.perm && user.role !== 'admin') {
      toast('هذه الصفحة للمدير فقط', 'warn');
      if (window.self === window.top) location.href = 'desktop.html';
      return null;
    }
  }
  try { SETTINGS = await api('settings'); } catch (e) { SETTINGS = {}; }
  CURRENCY = SETTINGS.currency || 'ج.م';
  applyWhatsappVisibility();
  const savedLocalTheme = localStorage.getItem('tz-theme');
  const prefTheme = user.theme_mode || savedLocalTheme || SETTINGS.os_default_theme || 'light';
  applyThemeEverywhere(prefTheme === 'dark');
  const activeAccent = user.accent_color || SETTINGS.os_default_accent || '#137fec';
  applyAccentColorEverywhere(activeAccent);
  const nav = NAV.find((x) => x.page === current);
  syncTitle(nav ? nav.label : '');
  document.body.dataset.role = user.role;
  renderSidebar(current, user);
  return user;
}


/* ===== توليد صورة الفاتورة عالية الدقة لتحويلها إلى ملف PDF وإرفاقها تلقائياً في واتساب ===== */
function renderInvoiceToJpeg(s) {
  const st = SETTINGS || {};
  const cur = CURRENCY || st.currency || 'ج.م';
  const showTax = (st.tax_enabled !== '0') && (st.receipt_show_tax !== '0') && (s.tax > 0);
  const showPays = st.receipt_show_payments !== '0';
  const showBarcode = st.receipt_show_barcode !== '0';
  const AR = { cash: 'نقدي', wallet: 'محفظة إلكترونية', credit: 'آجل (مديونية)' };

  const W = 720;
  const itemsCount = (s.items || []).length;
  const paysCount = showPays ? ((s.payments || []).length + 1) : 0;
  const hasAudit = (s.status && s.status !== 'completed') || !!s.modified_by_name;
  const H = 560 + (itemsCount * 46) + (paysCount * 32) + (hasAudit ? 76 : 0) + (showBarcode ? 95 : 0);

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  // خلفية الورقة البيضاء
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, W, H);
  ctx.direction = 'rtl';

  let y = 44;
  ctx.fillStyle = '#0f172a';
  ctx.textAlign = 'center';
  ctx.font = 'bold 30px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  ctx.fillText(st.store_name || 'تك زون للإلكترونيات', W / 2, y);
  y += 30;

  ctx.fillStyle = '#475569';
  ctx.font = '18px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  if (st.store_address) { ctx.fillText(st.store_address, W / 2, y); y += 26; }
  if (st.store_phone) { ctx.fillText('هاتف: ' + st.store_phone, W / 2, y); y += 26; }
  if (st.store_vat) { ctx.fillText('الرقم الضريبي: ' + st.store_vat, W / 2, y); y += 26; }

  // إشعار مرتجع / تعديل إن وجد
  if (hasAudit) {
    y += 6;
    ctx.fillStyle = '#fff7ed';
    ctx.fillRect(36, y - 22, W - 72, 60);
    ctx.strokeStyle = '#ea580c';
    ctx.lineWidth = 2;
    ctx.strokeRect(36, y - 22, W - 72, 60);
    ctx.fillStyle = '#c2410c';
    ctx.font = 'bold 18px "IBM Plex Sans Arabic", "Cairo", sans-serif';
    ctx.fillText(s.status === 'returned' ? '*** فاتورة مرتجع كلي ***' : '*** فاتورة مرتجع جزئي / معدلة ***', W / 2, y + 2);
    if (s.modified_by_name) {
      ctx.font = '15px "IBM Plex Sans Arabic", "Cairo", sans-serif';
      ctx.fillText(`بواسطة: ${s.modified_by_name} — التاريخ: ${(s.modified_at || '').slice(0, 16)}`, W / 2, y + 26);
    }
    y += 54;
  }

  // خط فاصل متقطع
  y += 8;
  ctx.strokeStyle = '#94a3b8';
  ctx.setLineDash([6, 4]);
  ctx.beginPath(); ctx.moveTo(36, y); ctx.lineTo(W - 36, y); ctx.stroke();
  ctx.setLineDash([]);
  y += 28;

  // بيانات الفاتورة والعميل
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 19px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(`فاتورة رقم: #${s.invoice_no}`, W - 36, y);
  ctx.textAlign = 'left';
  ctx.fillText(`التاريخ: ${(s.created_at || '').slice(0, 16)}`, 36, y);
  y += 28;

  ctx.font = '18px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  ctx.fillStyle = '#334155';
  ctx.textAlign = 'right';
  ctx.fillText(`الكاشير: ${s.user_name || ''}`, W - 36, y);
  if (s.customer_name) {
    ctx.textAlign = 'left';
    ctx.fillText(`العميل: ${s.customer_name}${s.customer_phone ? ' (' + s.customer_phone + ')' : ''}`, 36, y);
  }
  y += 22;

  // رأس جدول الأصناف
  ctx.fillStyle = '#f1f5f9';
  ctx.fillRect(36, y, W - 72, 38);
  ctx.strokeStyle = '#0f172a';
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(36, y); ctx.lineTo(W - 36, y); ctx.moveTo(36, y + 38); ctx.lineTo(W - 36, y + 38); ctx.stroke();

  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 18px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText('الصنف', W - 48, y + 25);
  ctx.textAlign = 'center';
  ctx.fillText('الكمية', 270, y + 25);
  ctx.textAlign = 'left';
  ctx.fillText('الإجمالي', 48, y + 25);
  y += 64;

  // سطور الأصناف
  ctx.font = 'bold 18px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  for (const it of (s.items || [])) {
    const rem = it.remaining_qty != null ? it.remaining_qty : it.qty;
    const ret = it.returned_qty || 0;
    const itemLabel = (it.name || '').slice(0, 36) + (ret > 0 ? ` (مرتجع ${ret})` : '');
    ctx.fillStyle = '#0f172a';
    ctx.textAlign = 'right';
    ctx.fillText(itemLabel, W - 48, y);
    ctx.textAlign = 'center';
    ctx.fillText(String(rem), 270, y);
    ctx.textAlign = 'left';
    ctx.fillText(fmt(rem * it.unit_price), 48, y);
    y += 42;
  }

  // خط قبل الإجماليات
  ctx.strokeStyle = '#cbd5e1';
  ctx.setLineDash([6, 4]);
  ctx.beginPath(); ctx.moveTo(36, y - 14); ctx.lineTo(W - 36, y - 14); ctx.stroke();
  ctx.setLineDash([]);
  y += 14;

  const drawRow = (label, val, bold = false, color = '#1e293b') => {
    ctx.fillStyle = color;
    ctx.font = (bold ? 'bold 24px ' : '19px ') + '"IBM Plex Sans Arabic", "Cairo", sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(label, W - 48, y);
    ctx.textAlign = 'left';
    ctx.fillText(val, 48, y);
    y += bold ? 38 : 30;
  };

  drawRow('المجموع الفرعي', `${fmt(s.subtotal)} ${cur}`);
  if (s.discount > 0) drawRow('الخصم', `-${fmt(s.discount)} ${cur}`, false, '#16a34a');
  if (showTax) drawRow('ضريبة القيمة المضافة', `${fmt(s.tax)} ${cur}`);

  // مربع الإجمالي النهائي
  ctx.fillStyle = '#f8fafc';
  ctx.fillRect(36, y - 24, W - 72, 48);
  ctx.strokeStyle = '#0f172a';
  ctx.lineWidth = 2;
  ctx.strokeRect(36, y - 24, W - 72, 48);
  drawRow('الإجمالي المطلوب', `${fmt(s.total)} ${cur}`, true, '#0f172a');
  y += 10;

  // طرق الدفع
  if (showPays && s.payments && s.payments.length) {
    for (const p of s.payments) {
      const mName = AR[p.method] || p.method;
      const refTxt = p.ref_no ? ` [مرجع: ${p.ref_no}]` : '';
      const chgTxt = p.change > 0 ? ` (الباقي: ${fmt(p.change)})` : '';
      drawRow(`الدفع (${mName}${refTxt})`, `${fmt(p.amount)} ${cur}${chgTxt}`, false, '#475569');
    }
  }

  // الباركود والتذييل
  if (showBarcode) {
    y += 6;
    ctx.fillStyle = '#0f172a';
    const barStart = (W - 260) / 2;
    for (let x = 0; x < 260; x += 6) {
      const bw = (x % 18 === 0) ? 4 : 2;
      ctx.fillRect(barStart + x, y, bw, 38);
    }
    y += 56;
    ctx.textAlign = 'center';
    ctx.font = '16px monospace';
    ctx.fillText(String(s.id).padStart(10, '0'), W / 2, y);
    y += 30;
  }

  ctx.textAlign = 'center';
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 19px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  ctx.fillText(st.receipt_thanks || 'شكراً لزيارتكم', W / 2, y);
  y += 26;
  ctx.fillStyle = '#64748b';
  ctx.font = '16px "IBM Plex Sans Arabic", "Cairo", sans-serif';
  ctx.fillText(st.receipt_footer || 'يرجى الاحتفاظ بالإيصال للاستبدال', W / 2, y);

  return { dataUrl: canvas.toDataURL('image/jpeg', 0.92), width: W, height: H };
}

async function sendInvoicePdfToWhatsapp(saleId, phoneOverride = '') {
  if (!whatsappEnabled()) { toast('إرسال WhatsApp معطّل من قبل المدير', 'warn'); return null; }
  const s = await guard(() => api('sale', { id: +saleId }));
  if (!s) return null;
  let phone = (phoneOverride || s.customer_phone || '').trim();
  if (!phone) {
    phone = prompt('أدخل رقم موبايل العميل لإرسال ملف الفاتورة (PDF) عبر واتساب (مثال: 01012345678):', '');
    if (!phone || !phone.trim()) return null;
    phone = phone.trim();
  }
  toast('جاري إنشاء ملف الفاتورة PDF وإرفاقه إلى واتساب...');
  const rendered = renderInvoiceToJpeg(s);
  const res = await guard(() => api('whatsapp_send_invoice', {
    sale_id: s.id,
    phone,
    pdf_image: rendered.dataUrl,
    img_w: rendered.width,
    img_h: rendered.height,
  }));
  if (res) {
    toast(`تم تجهيز رسالة «لديك فاتورة من ${res.store_name || 'المتجر'}» ونسخ ملف (${res.pdf_name}) لإرفاقه في المحادثة`);
  }
  return res;
}


/* ===== محرك قوالب الفواتير (قالب شركة تقنية الموجي A4 + العصري + الكلاسيكي + إيصال الكاشير الحراري) ===== */
const AR_MONTHS = [
  "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
];

function formatArabicDate(dateStr) {
  if (!dateStr) return "";
  const clean = String(dateStr).slice(0, 10);
  const parts = clean.split("-");
  if (parts.length !== 3) return dateStr;
  const y = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  const d = parseInt(parts[2], 10);
  if (!y || !m || !d || m < 1 || m > 12) return clean;
  return `${d} ${AR_MONTHS[m - 1]}، ${y}`;
}

function formatDocSeqClient(prefix, seqNum) {
  const p = String(prefix || "").trim() || "INV-";
  const n = Math.max(1, parseInt(seqNum, 10) || 1);
  if (/\d$/.test(p)) {
    return `${p}${n}`;
  }
  return `${p}${String(n).padStart(5, "0")}`;
}

function normalizeDocForA4(rawDoc, a4Cfg = {}) {
  const d = rawDoc || {};
  const isQuote = d.doc_type === "quote" && d.status !== "converted";
  const docNo = d.quote_no || d.invoice_no || formatDocSeqClient(isQuote ? (a4Cfg.quote_prefix || "ع.س/2026/") : (a4Cfg.invoice_prefix || "الفات/2026/"), d.id || 1);
  const docDate = d.doc_date || d.invoice_date || (d.created_at ? d.created_at.slice(0, 10) : todayISO());
  const dueDate = d.due_date || d.valid_until || docDate;

  const rawItems = Array.isArray(d.items) ? d.items : [];
  const items = rawItems.map((it) => {
    const qty = it.remaining_qty != null ? it.remaining_qty : (it.qty || 1);
    const unitPrice = it.unit_price != null ? it.unit_price : 0;
    const lineTotal = it.line_total != null ? it.line_total : (qty * unitPrice);
    return {
      sku: (it.sku || "").trim(),
      name: (it.name || "").trim(),
      qty,
      unit_price: unitPrice,
      tax_label: it.tax_label != null ? it.tax_label : (a4Cfg.default_tax_label || "Zero Rated 0%"),
      tax_rate: it.tax_rate || 0,
      line_total: lineTotal,
    };
  });

  const subtotal = d.subtotal != null ? d.subtotal : items.reduce((s, x) => s + x.line_total, 0);
  const discount = d.discount || 0;
  const tax = d.tax || 0;
  const total = d.total != null ? d.total : Math.max(0, subtotal - discount + tax);

  // في عرض السعر لا توجد مدفوعات إطلاقاً
  let paymentsList = [];
  if (!isQuote) {
    if (Array.isArray(d.payments_list) && d.payments_list.length) {
      paymentsList = d.payments_list.filter((p) => (p.amount || 0) > 0);
    } else if (d.payments_json) {
      try {
        const parsed = JSON.parse(d.payments_json);
        if (Array.isArray(parsed)) paymentsList = parsed.filter((p) => (p.amount || 0) > 0);
      } catch (e) {}
    }
  }

  let paidAmount = 0;
  if (!isQuote) {
    if (paymentsList.length > 0) {
      paidAmount = paymentsList.reduce((s, p) => s + (p.amount || 0), 0);
    } else if (d.paid_amount != null) {
      paidAmount = d.paid_amount;
    } else if (Array.isArray(d.payments)) {
      paidAmount = d.payments.filter((p) => p.method === "cash" || p.method === "wallet").reduce((s, p) => s + (p.amount || 0), 0);
    }
  }
  paidAmount = Math.max(0, Math.min(total, paidAmount));
  const dueAmount = isQuote ? 0 : (d.due_amount != null ? d.due_amount : Math.max(0, total - paidAmount));

  const payMethodLabel = (d.payment_method_label || "").trim()
    || (d.payment_method === "wallet" ? "محفظة إلكترونية" : "نقدي");
  const payDate = d.payment_date || docDate;
  const paymentPlanNote = (d.payment_plan_note || "").trim();

  return {
    isQuote,
    docNo,
    docDate,
    dueDate,
    customerName: (d.customer_name || "").trim(),
    customerPhone: (d.customer_phone || "").trim(),
    items,
    subtotal,
    discount,
    tax,
    total,
    paidAmount,
    dueAmount,
    payMethodLabel,
    payDate,
    paymentPlanNote,
    paymentsList,
    notes: (d.notes || "").trim(),
  };
}

function buildA4InvoiceHtml(rawDoc, a4Cfg = {}) {
  const cfg = Object.assign({
    theme: "taqnia_wave",
    primary_color: "#0e6ba8",
    accent_color: "#9e2a5b",
    company_title: "تقنية -Technology",
    company_address: "خلف المطافي\nخلف مستشفى دار الشفاء\nطهطا - سوهاج - 1405\nمصر",
    company_email: "hany_hassan2000@hotmail.com",
    company_phone: "",
    company_logo: "",
    invoice_title_label: "الفاتورة",
    quote_title_label: "عرض سعر",
    currency_symbol: "LE",
    default_tax_label: "Zero Rated 0%",
    show_waves: true,
    show_logo: true,
    show_info_box: true,
    show_sku_brackets: true,
    show_tax_col: true,
    show_payment_comm: true,
    show_payments_detail: true,
    show_footer_page: true,
    custom_terms: "",
  }, a4Cfg || {});

  const st = (typeof SETTINGS !== "undefined" && SETTINGS) ? SETTINGS : {};
  const globalTaxEnabled = st.tax_enabled !== "0";
  const showTaxCol = globalTaxEnabled && (cfg.show_tax_col !== false);
  const info = normalizeDocForA4(rawDoc, cfg);
  const cur = cfg.currency_symbol || "LE";
  const fmtCur = (cents) => `${cur} ${fmt(cents)}`;
  const primary = cfg.primary_color || "#0e6ba8";
  const accent = cfg.accent_color || "#9e2a5b";
  const pRgb = _hexToRgb(primary);
  const aRgb = _hexToRgb(accent);
  const addrLines = String(cfg.company_address || "").split(/\r?\n/).filter((x) => x.trim() !== "");
  const titleText = `${info.isQuote ? (cfg.quote_title_label || "عرض سعر") : (cfg.invoice_title_label || "الفاتورة")} ${info.docNo}`;
  const isClassic = cfg.theme === "classic_formal";
  const isModern = cfg.theme === "modern_clean";
  const showWaves = cfg.show_waves !== false && cfg.theme === "taqnia_wave";

  const topWaveSvg = showWaves ? `
    <svg viewBox="0 0 800 220" preserveAspectRatio="none" style="position:absolute;top:0;left:0;width:62%;height:175px;pointer-events:none;z-index:0">
      <path d="M0,0 L800,0 C680,145 430,210 0,205 Z" fill="rgba(${pRgb.r},${pRgb.g},${pRgb.b},0.09)"></path>
    </svg>` : (isModern ? `
    <div style="position:absolute;top:0;left:0;right:0;height:10px;background:linear-gradient(90deg,${primary},${accent});z-index:0"></div>` : "");

  const bottomWaveSvg = showWaves ? `
    <svg viewBox="0 0 1000 180" preserveAspectRatio="none" style="position:absolute;bottom:0;left:0;width:85%;height:110px;pointer-events:none;z-index:0">
      <path d="M0,180 L1000,180 C840,55 480,5 0,40 Z" fill="rgba(${aRgb.r},${aRgb.g},${aRgb.b},0.11)"></path>
    </svg>` : "";

  const logoHtml = (cfg.show_logo !== false && cfg.company_logo)
    ? `<img src="${esc(cfg.company_logo)}" alt="شعار الشركة" style="max-width:210px;max-height:115px;object-fit:contain;display:block"/>`
    : (cfg.show_logo !== false ? `<div style="padding:12px 20px;border-radius:14px;background:rgba(${pRgb.r},${pRgb.g},${pRgb.b},0.1);color:${primary};font-weight:800;font-size:20px">${esc(cfg.company_title)}</div>` : "");

  const displayItems = info.items.length ? info.items : [{ sku: "", name: "", qty: 1, unit_price: 0, tax_label: cfg.default_tax_label || "Zero Rated 0%", line_total: 0 }];
  const rowsHtml = displayItems.map((it) => {
    const hasName = !!it.name;
    const skuPart = (cfg.show_sku_brackets !== false && it.sku) ? `[${esc(it.sku)}] ` : "";
    const descHtml = hasName
      ? `${skuPart}${esc(it.name)}`
      : `<span style="color:#94a3b8;font-style:italic">${skuPart}اسم المنتج / البيان</span>`;
    return `
      <tr style="border-bottom:1px solid #e2e8f0">
        <td style="padding:10px 14px;text-align:right;font-weight:500;color:#1e293b;border-left:1px solid #e2e8f0">${descHtml}</td>
        <td style="padding:10px 10px;text-align:center;font-family:monospace,sans-serif;color:#334155;border-left:1px solid #e2e8f0">${Number(it.qty || 0).toFixed(2)}</td>
        <td style="padding:10px 10px;text-align:center;font-family:monospace,sans-serif;color:#334155;border-left:1px solid #e2e8f0">${fmt(it.unit_price)}</td>
        ${showTaxCol ? `<td style="padding:10px 10px;text-align:center;font-size:12px;color:#475569;border-left:1px solid #e2e8f0">${esc(it.tax_label || "")}</td>` : ""}
        <td style="padding:10px 14px;text-align:left;font-family:monospace,sans-serif;font-weight:700;color:#0f172a;direction:ltr">${esc(fmtCur(it.line_total))}</td>
      </tr>
    `;
  }).join("");

  const custNameHtml = info.customerName
    ? `<div style="font-size:17px;font-weight:700;color:#0f172a">${esc(info.customerName)}</div>`
    : `<div style="font-size:16px;font-weight:600;color:#94a3b8;font-style:italic">اسم العميل</div>`;
  const custPhoneHtml = info.customerPhone
    ? `<div style="font-size:12.5px;color:#64748b;font-family:monospace,sans-serif">${esc(info.customerPhone)}</div>`
    : `<div style="font-size:12px;color:#cbd5e1;font-style:italic">رقم التليفون</div>`;

  // أسطر الدفع الفعلية (تظهر فقط في فاتورة المبيعات وليس في عرض السعر، وعند وجود دفعة فعلية فقط > 0)
  let paymentRowsHtml = "";
  if (!info.isQuote && cfg.show_payments_detail !== false) {
    if (info.paymentsList && info.paymentsList.length > 0) {
      paymentRowsHtml += info.paymentsList.map((p) => `
        <tr style="border-bottom:1px solid #cbd5e1">
          <td style="padding:8px 12px;text-align:right;font-style:italic;color:#1e293b;border-left:1px solid #cbd5e1;line-height:1.45">
            ${p.label ? `<b>${esc(p.label)}</b> — ` : ""}تم الدفع في ${esc(formatArabicDate(p.date || info.payDate))}<br/>باستخدام ${esc(p.method || info.payMethodLabel)}
          </td>
          <td style="padding:8px 12px;text-align:left;font-family:monospace,sans-serif;direction:ltr;vertical-align:top">${esc(fmtCur(p.amount))}</td>
        </tr>
      `).join("");
    } else if (info.paidAmount > 0) {
      paymentRowsHtml += `
        <tr style="border-bottom:1px solid #cbd5e1">
          <td style="padding:8px 12px;text-align:right;font-style:italic;color:#1e293b;border-left:1px solid #cbd5e1;line-height:1.45">
            تم الدفع في ${esc(formatArabicDate(info.payDate))}<br/>باستخدام ${esc(info.payMethodLabel)}
          </td>
          <td style="padding:8px 12px;text-align:left;font-family:monospace,sans-serif;direction:ltr;vertical-align:top">${esc(fmtCur(info.paidAmount))}</td>
        </tr>
      `;
    }
    paymentRowsHtml += `
      <tr>
        <td style="padding:9px 12px;text-align:right;font-weight:800;color:#0f172a;border-left:1px solid #cbd5e1">المبلغ المستحق</td>
        <td style="padding:9px 12px;text-align:left;font-family:monospace,sans-serif;font-weight:800;direction:ltr;color:#0f172a">${esc(fmtCur(info.dueAmount))}</td>
      </tr>
    `;
  }

  return `
    <div class="tz-a4-sheet" dir="rtl" style="position:relative;width:100%;max-width:794px;min-height:1122px;margin:0 auto;background:#ffffff;color:#0f172a;font-family:'IBM Plex Sans Arabic','Cairo',sans-serif;padding:34px 40px 86px 40px;box-sizing:border-box;overflow:hidden;${isClassic ? "border:2px solid #0f172a;" : "box-shadow:0 10px 35px rgba(15,23,42,0.10);"}">
      ${topWaveSvg}
      <!-- ترويسة الشركة والشعار -->
      <div style="position:relative;z-index:2;display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:26px">
        <div style="order:1;min-width:160px;display:flex;justify-content:flex-start">
          ${logoHtml}
        </div>
        <div style="order:2;text-align:right;direction:rtl;font-size:13.5px;line-height:1.65;color:#1e293b;min-width:210px">
          <div style="font-weight:800;font-size:15px;color:#0f172a">${esc(cfg.company_title)}</div>
          ${addrLines.map((l) => `<div>${esc(l)}</div>`).join("")}
          ${cfg.company_phone ? `<div style="font-family:monospace,sans-serif">هاتف: ${esc(cfg.company_phone)}</div>` : ""}
        </div>
      </div>

      <!-- صف اسم العميل وعنوان الفاتورة -->
      <div style="position:relative;z-index:2;display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px;gap:16px">
        <div style="order:1;text-align:right">
          ${custNameHtml}
          ${custPhoneHtml}
        </div>
        <div style="order:2;text-align:left">
          <h1 style="margin:0;font-size:28px;font-weight:800;color:${primary};letter-spacing:0.2px">${esc(titleText)}</h1>
        </div>
      </div>

      <!-- شريط معلومات المستند (رقم الفاتورة كمرجع + تاريخ الفاتورة + تاريخ الاستحقاق فقط بدون المصدر أو رقم الإشارة) -->
      ${cfg.show_info_box !== false ? `
      <div style="position:relative;z-index:2;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding:12px 18px;margin-bottom:18px;border-radius:14px;border:1.6px solid ${accent};background:rgba(${aRgb.r},${aRgb.g},${aRgb.b},0.06)">
        <div style="text-align:right">
          <div style="font-size:12.5px;font-weight:800;color:#0f172a;margin-bottom:3px">${info.isQuote ? "رقم عرض السعر (المرجع)" : "رقم الفاتورة (المرجع)"}</div>
          <div style="font-size:13px;font-weight:700;color:${primary};font-family:monospace,sans-serif">${esc(info.docNo)}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:12.5px;font-weight:800;color:#0f172a;margin-bottom:3px">${info.isQuote ? "تاريخ عرض السعر" : "تاريخ الفاتورة"}</div>
          <div style="font-size:13px;color:#334155">${esc(formatArabicDate(info.docDate))}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:12.5px;font-weight:800;color:#0f172a;margin-bottom:3px">${info.isQuote ? "صالح حتى تاريخ" : "تاريخ الاستحقاق"}</div>
          <div style="font-size:13px;color:#334155">${esc(formatArabicDate(info.dueDate))}</div>
        </div>
      </div>` : ""}

      <!-- جدول الأصناف الرئيسي -->
      <div style="position:relative;z-index:2;border-radius:12px;overflow:hidden;border:1.2px solid #cbd5e1;margin-bottom:4px">
        <table style="width:100%;border-collapse:collapse;font-size:13.5px">
          <thead>
            <tr style="background:${primary};color:#ffffff;font-weight:700">
              <th style="padding:11px 14px;text-align:right;border-left:1px solid rgba(255,255,255,0.25)">الوصف</th>
              <th style="padding:11px 10px;text-align:center;width:76px;border-left:1px solid rgba(255,255,255,0.25)">الكمية</th>
              <th style="padding:11px 10px;text-align:center;width:105px;border-left:1px solid rgba(255,255,255,0.25)">سعر الوحدة</th>
              ${showTaxCol ? `<th style="padding:11px 10px;text-align:center;width:110px;border-left:1px solid rgba(255,255,255,0.25)">الضرائب</th>` : ""}
              <th style="padding:11px 14px;text-align:left;width:125px">المبلغ</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>

      <!-- قسم الإجماليات والملاحظات وخطة الدفع -->
      <div style="position:relative;z-index:2;display:flex;justify-content:space-between;align-items:flex-start;gap:24px;margin-top:8px">
        <div style="order:1;flex:1;padding-top:18px;text-align:right;font-size:13.5px;color:#1e293b">
          ${(!info.isQuote && cfg.show_payment_comm !== false) ? `
            <div style="margin-bottom:8px">مرجع الفاتورة للسداد: <b style="color:#0f172a">${esc(info.docNo)}</b></div>
          ` : ""}
          ${(!info.isQuote && info.paymentPlanNote) ? `
            <div style="margin-top:6px;padding:10px 12px;border-radius:10px;background:rgba(${pRgb.r},${pRgb.g},${pRgb.b},0.06);border:1px solid rgba(${pRgb.r},${pRgb.g},${pRgb.b},0.25);font-size:12.5px;color:#0f172a;white-space:pre-line"><b>نظام / خطة الدفع المتفق عليها:</b>
${esc(info.paymentPlanNote)}</div>
          ` : ""}
          ${info.notes ? `<div style="margin-top:8px;padding:10px 12px;border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0;font-size:12.5px;color:#334155;white-space:pre-line"><b>ملاحظات وشروط الدفع والتوريد:</b>
${esc(info.notes)}</div>` : ""}
          ${cfg.custom_terms ? `<div style="margin-top:8px;font-size:12px;color:#475569;white-space:pre-line">${esc(cfg.custom_terms)}</div>` : ""}
        </div>

        <!-- يسار: جدول ملخص المبالغ (في عرض السعر يظهر الخصم والإجمالي فقط بدون مدفوعات) -->
        <div style="order:2;width:320px;border:1.2px solid #cbd5e1;border-radius:6px;overflow:hidden;font-size:13.5px">
          <table style="width:100%;border-collapse:collapse">
            <tbody>
              <tr style="border-bottom:1px solid #cbd5e1">
                <td style="padding:8px 12px;text-align:right;color:#1e293b;border-left:1px solid #cbd5e1">${showTaxCol ? "المبلغ دون الضريبة" : "المجموع الفرعي"}</td>
                <td style="padding:8px 12px;text-align:left;font-family:monospace,sans-serif;direction:ltr;width:125px">${esc(fmtCur(info.subtotal))}</td>
              </tr>
              ${info.discount > 0 ? `
              <tr style="border-bottom:1px solid #cbd5e1">
                <td style="padding:8px 12px;text-align:right;color:#dc2626;border-left:1px solid #cbd5e1">الخصم</td>
                <td style="padding:8px 12px;text-align:left;font-family:monospace,sans-serif;direction:ltr;color:#dc2626">- ${esc(fmtCur(info.discount))}</td>
              </tr>` : ""}
              ${(showTaxCol && info.tax > 0) ? `
              <tr style="border-bottom:1px solid #cbd5e1">
                <td style="padding:8px 12px;text-align:right;color:#475569;border-left:1px solid #cbd5e1">الضرائب</td>
                <td style="padding:8px 12px;text-align:left;font-family:monospace,sans-serif;direction:ltr">${esc(fmtCur(info.tax))}</td>
              </tr>` : ""}
              <tr style="border-bottom:1px solid #cbd5e1;background:${primary};color:#ffffff;font-weight:800">
                <td style="padding:9px 12px;text-align:right;border-left:1px solid rgba(255,255,255,0.3)">الإجمالي</td>
                <td style="padding:9px 12px;text-align:left;font-family:monospace,sans-serif;direction:ltr">${esc(fmtCur(info.total))}</td>
              </tr>
              ${paymentRowsHtml}
            </tbody>
          </table>
        </div>
      </div>

      ${bottomWaveSvg}
      ${cfg.show_footer_page !== false ? `
      <div style="position:absolute;bottom:18px;left:0;right:0;z-index:2;text-align:center;font-size:13px;color:#334155">
        ${cfg.company_email ? `<div style="font-weight:600;margin-bottom:4px">${esc(cfg.company_email)}</div>` : ""}
        <div style="font-size:12px;color:#64748b">الصفحة 1 / 1</div>
      </div>` : ""}
    </div>
  `;
}

async function renderA4DocumentToJpeg(rawDoc, a4Cfg = {}) {
  const cfg = Object.assign({
    theme: "taqnia_wave",
    primary_color: "#0e6ba8",
    accent_color: "#9e2a5b",
    company_title: "تقنية -Technology",
    company_address: "خلف المطافي\nخلف مستشفى دار الشفاء\nطهطا - سوهاج - 1405\nمصر",
    company_email: "hany_hassan2000@hotmail.com",
    company_phone: "",
    company_logo: "",
    invoice_title_label: "الفاتورة",
    quote_title_label: "عرض سعر",
    currency_symbol: "LE",
    default_tax_label: "Zero Rated 0%",
    show_waves: true,
    show_logo: true,
    show_info_box: true,
    show_sku_brackets: true,
    show_tax_col: true,
    show_payment_comm: true,
    show_payments_detail: true,
    show_footer_page: true,
    custom_terms: "",
  }, a4Cfg || {});

  const st = (typeof SETTINGS !== "undefined" && SETTINGS) ? SETTINGS : {};
  const globalTaxEnabled = st.tax_enabled !== "0";
  const showTaxCol = globalTaxEnabled && (cfg.show_tax_col !== false);
  const info = normalizeDocForA4(rawDoc, cfg);
  const cur = cfg.currency_symbol || "LE";
  const fmtCur = (cents) => `${cur} ${fmt(cents)}`;
  const primary = cfg.primary_color || "#0e6ba8";
  const accent = cfg.accent_color || "#9e2a5b";
  const pRgb = _hexToRgb(primary);
  const aRgb = _hexToRgb(accent);

  const W = 1240;
  const H = Math.max(1754, 960 + info.items.length * 64);
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, W, H);

  if (cfg.show_waves !== false && cfg.theme === "taqnia_wave") {
    ctx.fillStyle = `rgba(${pRgb.r}, ${pRgb.g}, ${pRgb.b}, 0.09)`;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(W * 0.62, 0);
    ctx.bezierCurveTo(W * 0.50, 190, W * 0.28, 260, 0, 250);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, 0.11)`;
    ctx.beginPath();
    ctx.moveTo(0, H);
    ctx.lineTo(W * 0.85, H);
    ctx.bezierCurveTo(W * 0.70, H - 110, W * 0.38, H - 150, 0, H - 115);
    ctx.closePath();
    ctx.fill();
  }

  if (cfg.show_logo !== false && cfg.company_logo) {
    try {
      await new Promise((resolve) => {
        const im = new Image();
        im.onload = () => {
          const maxW = 310, maxH = 170;
          const r = Math.min(maxW / (im.width || 1), maxH / (im.height || 1), 1);
          const dw = (im.width || 240) * r;
          const dh = (im.height || 140) * r;
          ctx.drawImage(im, W - 64 - dw, 48, dw, dh);
          resolve();
        };
        im.onerror = () => resolve();
        im.src = cfg.company_logo;
      });
    } catch (e) {}
  }

  ctx.direction = "rtl";
  ctx.textAlign = "right";
  ctx.fillStyle = "#0f172a";
  ctx.font = "bold 23px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
  let ay = 74;
  ctx.fillText(cfg.company_title || "تقنية -Technology", 360, ay);
  ay += 32;
  ctx.font = "20px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
  ctx.fillStyle = "#1e293b";
  for (const line of String(cfg.company_address || "").split(/\r?\n/).filter((x) => x.trim())) {
    ctx.fillText(line.trim(), 360, ay);
    ay += 29;
  }

  let y = Math.max(270, ay + 36);
  ctx.fillStyle = info.customerName ? "#0f172a" : "#94a3b8";
  ctx.font = "bold 26px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(info.customerName || "اسم العميل", W - 64, y);
  if (info.customerPhone) {
    ctx.font = "19px monospace";
    ctx.fillStyle = "#64748b";
    ctx.fillText(info.customerPhone, W - 64, y + 28);
  }

  const titleText = `${info.isQuote ? (cfg.quote_title_label || "عرض سعر") : (cfg.invoice_title_label || "الفاتورة")} ${info.docNo}`;
  ctx.fillStyle = primary;
  ctx.font = "bold 40px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(titleText, 64, y);
  y += 40;

  // شريط البيانات (3 أعمدة فقط: رقم المرجع + تاريخ الفاتورة + تاريخ الاستحقاق)
  if (cfg.show_info_box !== false) {
    const bx = 64, bw = W - 128, bh = 96;
    ctx.fillStyle = `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, 0.06)`;
    ctx.strokeStyle = accent;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(bx, y, bw, bh, 20);
    else ctx.rect(bx, y, bw, bh);
    ctx.fill();
    ctx.stroke();

    const cols = [
      { lbl: info.isQuote ? "رقم عرض السعر (المرجع)" : "رقم الفاتورة (المرجع)", val: info.docNo, x: W - 92 },
      { lbl: info.isQuote ? "تاريخ عرض السعر" : "تاريخ الفاتورة", val: formatArabicDate(info.docDate), x: W - 470 },
      { lbl: info.isQuote ? "صالح حتى تاريخ" : "تاريخ الاستحقاق", val: formatArabicDate(info.dueDate), x: W - 840 },
    ];
    for (const c of cols) {
      ctx.textAlign = "right";
      ctx.fillStyle = "#0f172a";
      ctx.font = "bold 20px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
      ctx.fillText(c.lbl, c.x, y + 38);
      ctx.fillStyle = "#334155";
      ctx.font = "19px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
      ctx.fillText(c.val || "", c.x, y + 70);
    }
    y += bh + 26;
  }

  const tx = 64, tw = W - 128, th = 56;
  ctx.fillStyle = primary;
  ctx.fillRect(tx, y, tw, th);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 21px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
  ctx.textAlign = "right";
  ctx.fillText("الوصف", W - 84, y + 36);
  ctx.textAlign = "center";
  ctx.fillText("الكمية", 545, y + 36);
  ctx.fillText("سعر الوحدة", 415, y + 36);
  if (showTaxCol) ctx.fillText("الضرائب", 275, y + 36);
  ctx.textAlign = "left";
  ctx.fillText("المبلغ", 84, y + 36);
  y += th;

  const displayItems = info.items.length ? info.items : [{ sku: "", name: "اسم المنتج / البيان", qty: 1, unit_price: 0, tax_label: "", line_total: 0 }];
  for (const it of displayItems) {
    const rh = 56;
    ctx.strokeStyle = "#cbd5e1";
    ctx.lineWidth = 1.2;
    ctx.strokeRect(tx, y, tw, rh);
    const skuPart = (cfg.show_sku_brackets !== false && it.sku) ? `[${it.sku}] ` : "";
    ctx.fillStyle = "#0f172a";
    ctx.font = "20px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`${skuPart}${it.name || "اسم المنتج / البيان"}`.slice(0, 56), W - 84, y + 35);
    ctx.textAlign = "center";
    ctx.font = "20px monospace";
    ctx.fillText(Number(it.qty || 0).toFixed(2), 545, y + 35);
    ctx.fillText(fmt(it.unit_price), 415, y + 35);
    if (showTaxCol) {
      ctx.font = "17px sans-serif";
      ctx.fillText(it.tax_label || "", 275, y + 35);
    }
    ctx.textAlign = "left";
    ctx.font = "bold 20px monospace";
    ctx.fillText(fmtCur(it.line_total), 84, y + 35);
    y += rh;
  }

  y += 20;
  let rightY = y + 40;
  if (!info.isQuote && cfg.show_payment_comm !== false) {
    ctx.fillStyle = "#0f172a";
    ctx.font = "21px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`مرجع الفاتورة للسداد: ${info.docNo}`, W - 64, rightY);
    rightY += 34;
  }
  if (!info.isQuote && info.paymentPlanNote) {
    ctx.fillStyle = primary;
    ctx.font = "bold 19px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("نظام / خطة الدفع المتفق عليها:", W - 64, rightY);
    rightY += 28;
    ctx.fillStyle = "#1e293b";
    ctx.font = "18px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    for (const ln of info.paymentPlanNote.split(/\r?\n/)) {
      if (ln.trim()) { ctx.fillText(ln.trim().slice(0, 55), W - 64, rightY); rightY += 26; }
    }
    rightY += 8;
  }
  if (info.notes) {
    ctx.fillStyle = "#0f172a";
    ctx.font = "bold 19px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("ملاحظات وشروط الدفع والتوريد:", W - 64, rightY);
    rightY += 28;
    ctx.fillStyle = "#475569";
    ctx.font = "18px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    for (const ln of info.notes.split(/\r?\n/)) {
      if (ln.trim()) { ctx.fillText(ln.trim().slice(0, 55), W - 64, rightY); rightY += 26; }
    }
  }

  const sx = 64, sw = 480;
  const drawSumRow = (lbl, val, isPrimary = false, isBold = false) => {
    const sh = 50;
    if (isPrimary) {
      ctx.fillStyle = primary;
      ctx.fillRect(sx, y, sw, sh);
    }
    ctx.strokeStyle = "#cbd5e1";
    ctx.lineWidth = 1.2;
    ctx.strokeRect(sx, y, sw, sh);
    ctx.fillStyle = isPrimary ? "#ffffff" : "#0f172a";
    ctx.font = (isPrimary || isBold ? "bold " : "") + "20px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(lbl, sx + sw - 18, y + 32);
    ctx.textAlign = "left";
    ctx.font = (isPrimary || isBold ? "bold " : "") + "20px monospace";
    ctx.fillText(val, sx + 18, y + 32);
    y += sh;
  };

  drawSumRow(showTaxCol ? "المبلغ دون الضريبة" : "المجموع الفرعي", fmtCur(info.subtotal));
  if (info.discount > 0) drawSumRow("الخصم", `- ${fmtCur(info.discount)}`);
  if (showTaxCol && info.tax > 0) drawSumRow("الضرائب", fmtCur(info.tax));
  drawSumRow("الإجمالي", fmtCur(info.total), true, true);
  if (!info.isQuote && cfg.show_payments_detail !== false) {
    if (info.paymentsList && info.paymentsList.length > 0) {
      for (const p of info.paymentsList) {
        drawSumRow(`${p.label ? p.label + " - " : ""}تم الدفع (${p.method || info.payMethodLabel})`, fmtCur(p.amount));
      }
    } else if (info.paidAmount > 0) {
      drawSumRow(`تم الدفع (${info.payMethodLabel})`, fmtCur(info.paidAmount));
    }
    drawSumRow("المبلغ المستحق", fmtCur(info.dueAmount), false, true);
  }

  if (cfg.show_footer_page !== false) {
    ctx.textAlign = "center";
    ctx.fillStyle = "#1e293b";
    ctx.font = "bold 20px sans-serif";
    if (cfg.company_email) ctx.fillText(cfg.company_email, W / 2, H - 62);
    ctx.fillStyle = "#64748b";
    ctx.font = "18px 'IBM Plex Sans Arabic', 'Cairo', sans-serif";
    ctx.fillText("الصفحة 1 / 1", W / 2, H - 30);
  }

  return { dataUrl: canvas.toDataURL("image/jpeg", 0.92), width: W, height: H };
}

async function sendQuoteOrA4PdfToWhatsapp(quoteId, phoneOverride = "", a4CfgOverride = null) {
  if (!whatsappEnabled()) { toast("إرسال WhatsApp معطّل من قبل المدير", "warn"); return null; }
  const qDoc = await guard(() => api("quotation", { id: +quoteId }));
  if (!qDoc) return null;
  let phone = (phoneOverride || qDoc.customer_phone || "").trim();
  if (!phone) {
    phone = prompt("أدخل رقم موبايل العميل لإرسال ملف الـ PDF (A4) عبر واتساب (مثال: 01012345678):", "");
    if (!phone || !phone.trim()) return null;
    phone = phone.trim();
  }
  let a4Cfg = a4CfgOverride;
  if (!a4Cfg) {
    const tpls = await guard(() => api("templates_get"));
    a4Cfg = (tpls && tpls.a4) || {};
  }
  toast("جاري توليد ملف الفاتورة / عرض السعر (A4 PDF) وإرفاقه تلقائياً في واتساب...");
  const rendered = await renderA4DocumentToJpeg(qDoc, a4Cfg);
  const res = await guard(() => api("whatsapp_send_quote", {
    quote_id: qDoc.id,
    phone,
    pdf_image: rendered.dataUrl,
    img_w: rendered.width,
    img_h: rendered.height,
  }));
  if (res) {
    toast(`تم تجهيز الرسالة وإرفاق ملف (${res.pdf_name}) في محادثة واتساب`);
  }
  return res;
}


/* ===== محرك بناء إيصال الكاشير الحراري الموحد (80mm / 58mm) لجميع شاشات البرنامج ===== */
function buildPosThermalReceiptHtml(sale, posCfg = {}, stOverride = null) {
  const st = stOverride || SETTINGS || {};
  const cfg = Object.assign({
    paper_width: '80mm',
    font_scale: 'normal',
    border_style: 'dashed',
    show_logo: st.receipt_show_logo !== '0',
    show_store_address: true,
    show_store_phone: true,
    show_store_email: true,
    show_store_tax_cr: true,
    show_customer: true,
    show_cashier: true,
    show_sku: false,
    show_unit_price: true,
    show_discount: true,
    show_tax: st.receipt_show_tax !== '0',
    show_payments: st.receipt_show_payments !== '0',
    show_barcode: st.receipt_show_barcode !== '0',
    header_note: '',
    thanks_text: st.receipt_thanks || 'شكراً لزيارتكم',
    footer_text: st.receipt_footer || 'يرجى الاحتفاظ بالإيصال للاستبدال خلال 14 يوماً',
  }, posCfg || {});

  const s = sale || {};
  const cur = st.currency || CURRENCY || 'ج.م';
  const taxEnabled = st.tax_enabled !== '0';
  const fSize = cfg.font_scale === 'small' ? '11px' : cfg.font_scale === 'large' ? '14px' : '12px';
  const bStyle = cfg.border_style || 'dashed';
  const sep = `<div style="border-bottom:${bStyle === 'double' ? '3px double' : '1px ' + bStyle} #000;margin:6px 0"></div>`;
  const logoSrc = st.receipt_logo || '';
  const AR = { cash: 'نقدي', wallet: 'محفظة', credit: 'آجل' };

  const items = Array.isArray(s.items) ? s.items : [];
  const pays = Array.isArray(s.payments) ? s.payments : [];

  return `
    <div dir="rtl" style="font-family:monospace,'IBM Plex Sans Arabic',sans-serif;font-size:${fSize};color:#000;background:#fff;line-height:1.45">
      <div style="text-align:center;margin-bottom:6px">
        ${(cfg.show_logo && logoSrc) ? `<img src="${esc(logoSrc)}" style="width:56px;height:56px;object-fit:contain;margin:0 auto 4px;display:block"/>` : ''}
        <div style="font-size:16px;font-weight:800">${esc(st.store_name || 'تك زون للإلكترونيات')}</div>
        ${cfg.header_note ? `<div style="font-size:11px;font-weight:600;color:#222;margin-top:2px">${esc(cfg.header_note)}</div>` : ''}
        ${(cfg.show_store_address && st.store_address) ? `<div style="font-size:11px;color:#333">${esc(st.store_address)}</div>` : ''}
        ${(cfg.show_store_phone && st.store_phone) ? `<div style="font-size:11px;color:#333">هاتف: ${esc(st.store_phone)}</div>` : ''}
        ${(cfg.show_store_email && st.store_email) ? `<div style="font-size:10.5px;color:#333">${esc(st.store_email)}</div>` : ''}
        ${(cfg.show_store_tax_cr && st.store_cr) ? `<div style="font-size:10.5px;color:#333">سجل تجاري: ${esc(st.store_cr)}</div>` : ''}
        ${(cfg.show_store_tax_cr && st.store_vat) ? `<div style="font-size:10.5px;color:#333">الرقم الضريبي: ${esc(st.store_vat)}</div>` : ''}
      </div>
      ${sep}
      ${(s.status && s.status !== 'completed') || s.modified_by_name ? `
        <div style="border:1px solid #000;padding:4px;margin-bottom:6px;text-align:center;font-size:11px;font-weight:bold">
          <div>*** ${s.status === 'returned' ? 'إشعار فاتورة مرتجع كلي' : 'إشعار فاتورة مرتجع / معدلة'} ***</div>
          ${s.modified_by_name ? `<div style="font-size:10px;font-weight:normal">بواسطة: ${esc(s.modified_by_name)} — ${esc((s.modified_at || '').slice(0, 16))}</div>` : ''}
        </div>
      ` : ''}
      <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px">
        <div>
          <div>فاتورة: <b>#${esc(s.invoice_no || '00001')}</b></div>
          ${(cfg.show_cashier && s.user_name) ? `<div>الكاشير: ${esc(s.user_name)}</div>` : ''}
          ${(cfg.show_customer && s.customer_name) ? `<div>العميل: ${esc(s.customer_name)}${s.customer_phone ? ' (' + esc(s.customer_phone) + ')' : ''}</div>` : ''}
        </div>
        <div dir="ltr" style="text-align:left">
          <div>${esc((s.created_at || todayISO()).slice(0, 10))}</div>
          <div>${esc((s.created_at || '').slice(11, 16))}</div>
        </div>
      </div>
      <div style="border-bottom:1.5px solid #000;padding-bottom:3px;margin-bottom:4px;display:flex;justify-content:space-between;font-weight:bold;font-size:11px">
        <span style="flex:2">الصنف</span>
        <span style="flex:0.8;text-align:center">الكمية</span>
        <span style="flex:1.2;text-align:left">الإجمالي</span>
      </div>
      ${items.length ? items.map((it) => `
        <div style="display:flex;justify-content:space-between;font-size:${fSize};margin-bottom:3px">
          <span style="flex:2;font-weight:bold">
            ${(cfg.show_sku && it.sku) ? `[${esc(it.sku)}] ` : ''}${esc(it.name)}
            ${cfg.show_unit_price ? `<span style="font-weight:normal;font-size:10px;color:#444"> (${fmt(it.unit_price)})</span>` : ''}
          </span>
          <span style="flex:0.8;text-align:center">${n(it.qty)}</span>
          <span style="flex:1.2;text-align:left">${fmt(it.line_total)}</span>
        </div>
      `).join('') : '<div style="text-align:center;color:#777;padding:6px 0">— لا توجد أصناف —</div>'}
      ${sep}
      <div style="font-size:11px">
        <div style="display:flex;justify-content:space-between"><span>المجموع الفرعي</span><span>${fmt(s.subtotal || 0)}</span></div>
        ${(cfg.show_discount && s.discount) ? `<div style="display:flex;justify-content:space-between"><span>الخصم</span><span>-${fmt(s.discount)}</span></div>` : ''}
        ${(taxEnabled && cfg.show_tax && s.tax) ? `<div style="display:flex;justify-content:space-between"><span>ضريبة القيمة المضافة</span><span>${fmt(s.tax)}</span></div>` : ''}
      </div>
      <div style="border-top:1.5px solid #000;margin-top:4px;padding-top:4px;display:flex;justify-content:space-between;font-size:14px;font-weight:800">
        <span>الإجمالي</span>
        <span>${fmt(s.total || 0)} ${esc(cur)}</span>
      </div>
      ${(cfg.show_payments && pays.length) ? `
        <div style="margin-top:5px;font-size:11px">
          ${pays.map((p) => `
            <div style="display:flex;justify-content:space-between">
              <span>الدفع (${AR[p.method] || p.method}${p.ref_no ? ' - ' + esc(p.ref_no) : ''})</span>
              <span>${fmt(p.amount)}${p.change ? ' (الباقي ' + fmt(p.change) + ')' : ''}</span>
            </div>
          `).join('')}
        </div>
      ` : ''}
      ${cfg.show_barcode ? `
        <div style="text-align:center;margin-top:8px">
          <div style="height:28px;width:165px;margin:0 auto;background:repeating-linear-gradient(90deg,#000 0 2px,transparent 2px 4px,#000 4px 5px,transparent 5px 8px)"></div>
          <div style="font-size:10px;letter-spacing:2.5px">${String(s.id || 1).padStart(10, '0')}</div>
        </div>
      ` : ''}
      ${cfg.thanks_text ? `<div style="text-align:center;margin-top:7px;font-size:11.5px;font-weight:bold">${esc(cfg.thanks_text)}</div>` : ''}
      ${cfg.footer_text ? `<div style="text-align:center;font-size:10px;color:#444;margin-top:2px">${esc(cfg.footer_text)}</div>` : ''}
    </div>
  `;
}


/* ===== بناء إيصال / تذكرة صيانة قابل للطباعة في أي حالة ===== */
function buildRepairTicketPrintHtml(rep, posCfg = {}, stOverride = null) {
  const st = stOverride || SETTINGS || {};
  const cfg = Object.assign({
    paper_width: "80mm",
    show_logo: st.receipt_show_logo !== "0",
    show_store_address: true,
    show_store_phone: true,
    repair_receipt_title: "إيصال استلام وصيانة جهاز",
    repair_terms: "المحل غير مسؤول عن الأجهزة التي لا يُسأل عنها خلال 30 يوماً من تاريخ الإبلاغ.",
    thanks_text: st.receipt_thanks || "شكراً لزيارتكم",
  }, posCfg || {});
  const r = rep || {};
  const cur = st.currency || CURRENCY || "ج.م";
  const STATUS_AR = {
    received: "تم الاستلام",
    in_review: "تحت الفحص",
    pending_approval: "بانتظار موافقة العميل",
    repaired: "تم الإصلاح — جاهز للتسليم",
    delivered: "تم التسليم للعميل",
    rejected: "مرفوض / غير قابل للإصلاح",
  };
  const parts = Array.isArray(r.parts) ? r.parts : [];
  const logoSrc = st.receipt_logo || "";
  return `
    <div dir="rtl" style="font-family:'IBM Plex Sans Arabic',monospace,sans-serif;max-width:340px;margin:0 auto;padding:12px;color:#000;background:#fff;line-height:1.5;border:1px solid #cbd5e1;border-radius:10px">
      <div style="text-align:center;border-bottom:1.5px dashed #000;padding-bottom:8px;margin-bottom:8px">
        ${(cfg.show_logo && logoSrc) ? `<img src="${esc(logoSrc)}" style="width:52px;height:52px;object-fit:contain;margin:0 auto 4px;display:block"/>` : ""}
        <div style="font-size:16px;font-weight:800">${esc(st.store_name || "تك زون للإلكترونيات")}</div>
        ${(cfg.show_store_address && st.store_address) ? `<div style="font-size:11px;color:#333">${esc(st.store_address)}</div>` : ""}
        ${(cfg.show_store_phone && st.store_phone) ? `<div style="font-size:11px;color:#333">هاتف: ${esc(st.store_phone)}</div>` : ""}
        <div style="margin-top:6px;display:inline-block;padding:3px 10px;border:1.5px solid #000;border-radius:6px;font-size:12.5px;font-weight:800">
          ${esc(cfg.repair_receipt_title || "إيصال استلام وصيانة جهاز")}
        </div>
      </div>

      <div style="display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:6px">
        <div>رقم التذكرة: <b style="font-family:monospace">${esc(r.ref || "RPR-001")}</b></div>
        <div style="font-family:monospace">${esc((r.created_at || todayISO()).slice(0, 16))}</div>
      </div>

      <div style="padding:6px 8px;border:1px solid #000;border-radius:6px;margin-bottom:8px;font-size:11.5px;display:flex;justify-content:space-between;align-items:center">
        <span>حالة التذكرة الحالية:</span>
        <b>${esc(STATUS_AR[r.status] || r.status || "تم الاستلام")}</b>
      </div>

      <div style="font-size:12px;border-bottom:1px dashed #000;padding-bottom:6px;margin-bottom:6px">
        <div><b>العميل:</b> ${esc(r.customer_name || "—")}</div>
        <div><b>الهاتف:</b> <span style="font-family:monospace">${esc(r.customer_phone || "—")}</span></div>
        ${r.address ? `<div><b>العنوان:</b> ${esc(r.address)}</div>` : ""}
      </div>

      <div style="font-size:12px;border-bottom:1px dashed #000;padding-bottom:6px;margin-bottom:6px">
        <div><b>نوع وموديل الجهاز:</b> ${esc(r.device_type || "—")} ${r.priority ? "(مستعجل ★)" : ""}</div>
        ${r.serial ? `<div><b>السيريال / IMEI:</b> <span style="font-family:monospace">${esc(r.serial)}</span></div>` : ""}
        ${r.accessories ? `<div><b>الملحقات المستلمة:</b> ${esc(r.accessories)}</div>` : ""}
        <div style="margin-top:4px"><b>وصف العطل / المشكلة:</b><br/>${esc(r.problem || "—")}</div>
        ${r.notes ? `<div style="margin-top:3px"><b>ملاحظات الفحص:</b> ${esc(r.notes)}</div>` : ""}
      </div>

      ${parts.length ? `
        <div style="font-size:11.5px;border-bottom:1px dashed #000;padding-bottom:6px;margin-bottom:6px">
          <div style="font-weight:bold;margin-bottom:3px">قطع الغيار المركبة:</div>
          ${parts.map((p) => `<div style="display:flex;justify-content:space-between"><span>${esc(p.name)} × ${n(p.qty)}</span><span style="font-family:monospace">${fmt(p.line_total)}</span></div>`).join("")}
        </div>
      ` : ""}

      <div style="display:flex;justify-content:space-between;align-items:center;font-size:14px;font-weight:800;padding:4px 0;border-bottom:1.5px solid #000;margin-bottom:6px">
        <span>إجمالي تكلفة الصيانة:</span>
        <span style="font-family:monospace">${fmt(r.cost || 0)} ${esc(cur)}</span>
      </div>

      ${cfg.repair_terms ? `<div style="font-size:10px;color:#333;text-align:center;line-height:1.4;margin-bottom:6px">${esc(cfg.repair_terms)}</div>` : ""}
      ${cfg.thanks_text ? `<div style="text-align:center;font-size:11px;font-weight:bold">${esc(cfg.thanks_text)}</div>` : ""}
    </div>
  `;
}
