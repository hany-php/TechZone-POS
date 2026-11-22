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
function _hasValidBridge(target) {
  try {
    return Boolean(target && target.pywebview && target.pywebview.api && typeof target.pywebview.api.call === 'function');
  } catch (e) {
    return false;
  }
}

function _resolvePywebview() {
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.call === 'function') {
    return window.pywebview;
  }
  try {
    if (window.parent && window.parent !== window && _hasValidBridge(window.parent)) {
      window.pywebview = window.parent.pywebview;
      return window.pywebview;
    }
    if (window.top && window.top !== window && _hasValidBridge(window.top)) {
      window.pywebview = window.top.pywebview;
      return window.pywebview;
    }
  } catch (e) {}

  // إذا كنا داخل بيئة WebView2 (ويندوز) أو WebKit الأصلية لتطبيق pywebview، ننتظر حقن الجسر الأصلي ولا نفعّل الـ mock
  const isNativeWebview = Boolean(
    (typeof window !== 'undefined' && window.chrome && window.chrome.webview) ||
    (typeof window !== 'undefined' && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jsBridge)
  );

  if (!isNativeWebview && typeof window !== 'undefined' && window.location && (window.location.protocol === 'http:' || window.location.protocol === 'https:')) {
    window.pywebview = {
      api: {
        call: async (name, payload) => {
          const res = await fetch('/api/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, payload: payload === undefined ? null : payload })
          });
          return await res.json();
        }
      }
    };
    return window.pywebview;
  }
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
  if (!bridge || !bridge.api || typeof bridge.api.call !== 'function') { showBridgeError(); throw new Error('انقطاع الاتصال بالبرنامج الداخلي'); }
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
window.UI_CONFIG = null;

async function loadUiConfig(force = false) {
  if (!force && window.UI_CONFIG && Array.isArray(window.UI_CONFIG.modules)) {
    return window.UI_CONFIG;
  }
  try {
    const cfg = await api('ui_config');
    if (cfg && Array.isArray(cfg.modules)) {
      window.UI_CONFIG = cfg;
      return cfg;
    }
  } catch (e) {}
  return window.UI_CONFIG;
}

function isModuleEnabled(key) {
  if (!key || key === 'desktop' || key === 'index' || key === 'owner') return true;
  if (!window.UI_CONFIG || !Array.isArray(window.UI_CONFIG.modules)) return true;
  return window.UI_CONFIG.modules.some((m) => m.key === key || m.id === key || m.url === `${key}.html`);
}

const DEFAULT_LABELS = {
  module_pos: 'نقاط البيع (الكاشير)',
  module_inventory: 'المخزون والمنتجات',
  module_customers: 'العملاء والمديونيات',
  module_sales_quotes: 'المبيعات وعروض الأسعار',
  module_purchases: 'المشتريات والموردون',
  module_accounting: 'المحاسبة والمالية',
  module_repair: 'مركز الصيانة',
  module_buy_used: 'شراء أجهزة مستعملة',
  product_singular: 'منتج',
  products_plural: 'المنتجات',
  customer_singular: 'عميل',
  customers_plural: 'العملاء',
  repair_center: 'مركز الصيانة',
  used_devices: 'الأجهزة المستعملة',
};

function t(key, fallback = '') {
  const lbls = (window.UI_CONFIG && window.UI_CONFIG.labels) || {};
  if (lbls[key]) return lbls[key];
  if (DEFAULT_LABELS[key]) return DEFAULT_LABELS[key];
  return fallback || key;
}

function applyLabels() {
  const lbls = (window.UI_CONFIG && window.UI_CONFIG.labels) || {};
  document.querySelectorAll('[data-label]').forEach((el) => {
    const k = el.dataset.label;
    if (!el.dataset.origLabel) el.dataset.origLabel = el.textContent;
    el.textContent = lbls[k] || el.dataset.origLabel;
  });
}

const DEFAULT_NAV = [
  { page: 'desktop', href: 'desktop.html', icon: 'desktop_windows', label: 'سطح المكتب (النظام)' },
  { page: 'pos', href: 'pos.html', icon: 'point_of_sale', label: 'نقاط البيع', perm: 'pos_sell' },
  { page: 'sales_quotes', href: 'sales_quotes.html', icon: 'description', label: 'المبيعات وعروض الأسعار', perm: ['quotes_view', 'quotes_create_edit'] },
  { page: 'customers', href: 'customers.html', icon: 'people', label: 'العملاء والمديونيات', perm: ['customers_view', 'customers_debt_view', 'customers_edit', 'customers_payment'] },
  { page: 'installments', href: 'installments.html', icon: 'event_repeat', label: 'نظام الأقساط', perm: ['installments_view', 'installments_collect', 'installments_create'] },
  { page: 'history', href: 'history.html', icon: 'receipt_long', label: 'سجل المبيعات', perm: ['history_view_own', 'history_view_all', 'sales_return_own', 'sales_return', 'sales_post_discount'] },
  { page: 'receipt', href: 'receipt.html', icon: 'print', label: 'معاينة وطباعة الإيصال', perm: 'receipt_view' },
  { page: 'repair', href: 'repair.html', icon: 'build', label: 'الصيانة', perm: ['repair_view', 'repair_create', 'repair_edit'] },
  { page: 'inventory', href: 'inventory.html', icon: 'inventory_2', label: 'المخزون', perm: ['inventory_view', 'inventory_edit', 'inventory_adjust'] },
  { page: 'purchases', href: 'purchases.html', icon: 'local_shipping', label: 'المشتريات والموردون', perm: ['suppliers_view', 'suppliers_manage', 'purchases_view', 'purchases_create_post', 'purchases_return', 'purchases_payment'] },
  { page: 'accounting', href: 'accounting.html', icon: 'account_balance', label: 'المحاسبة والمالية', perm: ['expenses_view', 'expenses_manage', 'treasury_view', 'treasury_transfer', 'accounting_coa_view', 'accounting_journal_manual', 'accounting_statements_view'] },
  { page: 'buy_used', href: 'buy_used.html', icon: 'phonelink_setup', label: 'شراء أجهزة مستعملة', perm: ['used_view', 'used_manage'] },
  { page: 'reports', href: 'reports.html', icon: 'bar_chart', label: 'التقارير والتحليلات', perm: ['reports_sales_view', 'reports_profit_view', 'reports_shifts_view', 'reports_movements_view'] },
  { page: 'staff', href: 'staff.html', icon: 'manage_accounts', label: 'الموظفون والصلاحيات', perm: ['staff_view', 'staff_manage'] },
  { page: 'settings', href: 'settings.html', icon: 'settings', label: 'إعدادات النظام', perm: ['settings_view_edit', 'templates_manage', 'backups_manage'] },
  { page: 'profile', href: 'profile.html', icon: 'account_circle', label: 'ملفي الشخصي وإعداداتي' },
  { page: 'index', href: 'index.html', icon: 'switch_account', label: 'تبديل المستخدم' },
];
const NAV = DEFAULT_NAV;

function getNavItems() {
  if (window.UI_CONFIG && Array.isArray(window.UI_CONFIG.modules) && window.UI_CONFIG.modules.length) {
    return [
      { page: 'desktop', href: 'desktop.html', icon: 'desktop_windows', label: 'سطح المكتب (النظام)' },
      ...window.UI_CONFIG.modules.map((m) => ({
        page: m.key || m.id,
        href: m.full_url || m.url,
        icon: m.icon,
        label: m.title,
        perm: m.perm,
      })),
      { page: 'index', href: 'index.html', icon: 'switch_account', label: 'تبديل المستخدم' },
    ];
  }
  return DEFAULT_NAV;
}

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
  const items = getNavItems().filter((x) => !x.perm || hasPerm(x.perm, user))
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
  await loadUiConfig();
  CURRENCY = SETTINGS.currency || 'ج.م';
  applyWhatsappVisibility();
  const savedLocalTheme = localStorage.getItem('tz-theme');
  const prefTheme = user.theme_mode || savedLocalTheme || SETTINGS.os_default_theme || 'light';
  applyThemeEverywhere(prefTheme === 'dark');
  const activeAccent = user.accent_color || SETTINGS.os_default_accent || '#137fec';
  applyAccentColorEverywhere(activeAccent);
  const prefLang = user.lang || localStorage.getItem('tz-lang') || (SETTINGS && SETTINGS.app_default_lang) || 'ar';
  if (typeof applyLanguageEverywhere === 'function') applyLanguageEverywhere(prefLang);
  if (current && current !== 'desktop' && current !== 'index' && !isModuleEnabled(current)) {
    document.body.innerHTML = `
      <div class="min-h-screen w-full flex items-center justify-center p-6 bg-background-light dark:bg-background-dark text-slate-800 dark:text-slate-100">
        <div class="max-w-md w-full bg-white dark:bg-surface-dark rounded-2xl border border-slate-200 dark:border-slate-800 p-8 text-center shadow-lg">
          <div class="w-14 h-14 mx-auto rounded-2xl bg-amber-500/10 text-amber-500 flex items-center justify-center mb-4">
            <span class="material-icons-round text-3xl">block</span>
          </div>
          <h2 class="text-lg font-bold mb-2">القسم غير مُفعّل</h2>
          <p class="text-xs text-slate-500 dark:text-slate-400 mb-5">هذا القسم معطل حالياً من إعدادات المالك الرئيسي للبرنامج.</p>
          <a href="desktop.html" class="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-primary text-white text-xs font-bold">
            <span class="material-icons-round text-base">desktop_windows</span>
            <span>العودة لسطح المكتب</span>
          </a>
        </div>
      </div>`;
    return null;
  }
  const nav = getNavItems().find((x) => x.page === current);
  syncTitle(nav ? nav.label : '');
  applyLabels();
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

async function sendInvoicePdfToWhatsapp(saleId, phoneOverride = '', format = 'thermal', a4CfgOverride = null) {
  if (!whatsappEnabled()) { toast('إرسال WhatsApp معطّل من قبل المدير', 'warn'); return null; }
  const s = await guard(() => api('sale', { id: +saleId }));
  if (!s) return null;
  let phone = (phoneOverride || s.customer_phone || '').trim();
  if (!phone) {
    phone = prompt('أدخل رقم موبايل العميل لإرسال ملف الفاتورة (PDF) عبر واتساب (مثال: 01012345678):', '');
    if (!phone || !phone.trim()) return null;
    phone = phone.trim();
  }
  let rendered;
  if (format === 'a4') {
    let a4Cfg = a4CfgOverride;
    if (!a4Cfg) {
      try {
        if (SETTINGS && SETTINGS.template_a4_config) a4Cfg = JSON.parse(SETTINGS.template_a4_config) || null;
      } catch (e) {}
    }
    if (!a4Cfg) {
      try {
        const tpls = await api('templates_get');
        a4Cfg = (tpls && tpls.a4) || {};
      } catch (e) {
        a4Cfg = {};
      }
    }
    toast('جاري إنشاء ملف الفاتورة A4 (PDF) وإرفاقه إلى واتساب...');
    rendered = await renderA4DocumentToJpeg(s, a4Cfg);
  } else {
    toast('جاري إنشاء ملف الفاتورة PDF وإرفاقه إلى واتساب...');
    rendered = renderInvoiceToJpeg(s);
  }
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
    <style>
      @page { size: A4 portrait; margin: 0; }
      @media print {
        @page { size: A4 portrait; margin: 0; }
        .tz-a4-sheet {
          box-shadow: none !important;
          margin: 0 auto !important;
          page-break-inside: avoid !important;
          break-inside: avoid !important;
        }
      }
    </style>
    <div class="tz-a4-sheet" dir="rtl" style="position:relative;width:100%;max-width:794px;min-height:1122px;margin:0 auto;background:#ffffff;color:#0f172a;font-family:'IBM Plex Sans Arabic','Cairo',sans-serif;padding:32px 32px 80px 32px;box-sizing:border-box;overflow:hidden;${isClassic ? "border:2px solid #0f172a;" : "box-shadow:0 10px 35px rgba(15,23,42,0.10);"}">
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
              <th style="padding:11px 12px;text-align:right;border-left:1px solid rgba(255,255,255,0.25)">الوصف</th>
              <th style="padding:11px 8px;text-align:center;width:72px;border-left:1px solid rgba(255,255,255,0.25)">الكمية</th>
              <th style="padding:11px 8px;text-align:center;width:100px;border-left:1px solid rgba(255,255,255,0.25)">سعر الوحدة</th>
              ${showTaxCol ? `<th style="padding:11px 8px;text-align:center;width:105px;border-left:1px solid rgba(255,255,255,0.25)">الضرائب</th>` : ""}
              <th style="padding:11px 12px;text-align:left;width:120px">المبلغ</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>

      <!-- قسم الإجماليات والملاحظات وخطة الدفع -->
      <div style="position:relative;z-index:2;display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-top:8px">
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
        <div style="order:2;width:300px;border:1.2px solid #cbd5e1;border-radius:6px;overflow:hidden;font-size:13.5px">
          <table style="width:100%;border-collapse:collapse">
            <tbody>
              <tr style="border-bottom:1px solid #cbd5e1">
                <td style="padding:8px 12px;text-align:right;color:#1e293b;border-left:1px solid #cbd5e1">${showTaxCol ? "المبلغ دون الضريبة" : "المجموع الفرعي"}</td>
                <td style="padding:8px 12px;text-align:left;font-family:monospace,sans-serif;direction:ltr;width:120px">${esc(fmtCur(info.subtotal))}</td>
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

/* ===== توليد صورة الفاتورة A4 من نفس HTML المعاينة (WYSIWYG) عبر SVG foreignObject مع تضمين الخطوط المحلية ===== */
let _A4_FONT_CSS_CACHE = null;
async function _a4EmbeddedFontCss() {
  if (_A4_FONT_CSS_CACHE) return _A4_FONT_CSS_CACHE;
  const toB64 = (buf) => {
    const bytes = new Uint8Array(buf);
    let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  };
  const cache = {};
  const load = async (name) => {
    if (!cache[name]) {
      const r = await fetch(`fonts/${name}.woff2`);
      if (!r.ok) throw new Error("font " + name);
      cache[name] = toB64(await r.arrayBuffer());
    }
    return cache[name];
  };
  let css = "";
  for (const [w, fileW] of [[400, 400], [500, 500], [600, 600], [700, 700], [800, 700]]) {
    for (const sub of ["arabic", "latin"]) {
      const b64 = await load(`ibm-plex-sans-arabic-${fileW}-${sub}`);
      css += `@font-face{font-family:'IBM Plex Sans Arabic';font-style:normal;font-weight:${w};src:url(data:font/woff2;base64,${b64}) format('woff2');}`;
    }
  }
  _A4_FONT_CSS_CACHE = css;
  return css;
}

function _a4LoadSvgImage(url) {
  return new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => reject(new Error("svg render failed"));
    im.src = url;
  });
}

async function renderA4DocumentToJpeg(rawDoc, a4Cfg = {}) {
  try {
    const fontCss = await _a4EmbeddedFontCss();
    const host = document.createElement("div");
    host.style.cssText = "position:fixed;left:-10000px;top:0;width:794px;visibility:hidden;pointer-events:none";
    host.innerHTML = buildA4InvoiceHtml(rawDoc, a4Cfg);
    document.body.appendChild(host);
    const sheet = host.querySelector(".tz-a4-sheet");
    sheet.style.boxShadow = "none";
    sheet.style.margin = "0";
    sheet.style.width = "794px";
    sheet.style.maxWidth = "794px";
    const W = 794;
    const H = Math.max(1122, Math.ceil(sheet.getBoundingClientRect().height));
    const xml = new XMLSerializer().serializeToString(sheet);
    host.remove();
    const reset = "*,::before,::after{box-sizing:border-box;border-width:0;border-style:solid}table{border-collapse:collapse}";
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><foreignObject x="0" y="0" width="${W}" height="${H}"><div xmlns="http://www.w3.org/1999/xhtml" style="width:${W}px;height:${H}px;background:#fff"><style>${fontCss}${reset}</style>${xml}</div></foreignObject></svg>`;
    const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    await _a4LoadSvgImage(url);           // تسخين: تحميل الخطوط
    await new Promise((r) => setTimeout(r, 120));
    const im = await _a4LoadSvgImage(url);
    const SCALE = 2;
    const canvas = document.createElement("canvas");
    canvas.width = W * SCALE;
    canvas.height = H * SCALE;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(im, 0, 0, canvas.width, canvas.height);
    return { dataUrl: canvas.toDataURL("image/jpeg", 0.93), width: canvas.width, height: canvas.height };
  } catch (e) {
    console.warn("A4 WYSIWYG render failed, using legacy canvas renderer", e);
    return renderA4DocumentToJpegLegacy(rawDoc, a4Cfg);
  }
}
async function renderA4DocumentToJpegLegacy(rawDoc, a4Cfg = {}) {
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

/* ===== طباعة ذكية موحدة (طباعة صامتة مباشرة أو نافذة إعدادات الطابعة من الويندوز حسب الإعدادات) ===== */
async function tzPrintPage(mode = 'thermal', opts = {}) {
  const showDialog = Boolean((opts && opts.forceDialog) || (SETTINGS && SETTINGS.print_show_dialog === '1'));
  if (showDialog) {
    window.print();
    return { ok: true, mode: 'dialog' };
  }
  try {
    const res = await api('silent_print', {
      mode: mode || 'thermal',
      printer_name: (SETTINGS && SETTINGS.print_printer_name) || '',
    });
    if (res && res.ok) {
      toast('تم إرسال أمر الطباعة مباشرة للطابعة', 'success');
      return res;
    }
    if (res && res.fallback === 'dialog') {
      window.print();
      return { ok: true, mode: 'dialog', fallback: true };
    }
    toast((res && res.error) || 'تعذر إرسال أمر الطباعة المباشرة', 'error');
    return res || { ok: false };
  } catch (err) {
    toast((err && err.message) || 'تعذر إرسال أمر الطباعة', 'error');
    return { ok: false, error: err && err.message };
  }
}


/* ===== محرك التنبيهات الصوتية المحلي لنقاط البيع (100% Offline WebAudio API) ===== */
let _tzAudioCtx = null;
function tzPlayPosSound(kind = 'scan') {
  try {
    const st = (typeof SETTINGS !== 'undefined' && SETTINGS) || (window.top && window.top.SETTINGS) || {};
    if (st.pos_sound_enabled === '0') return;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!_tzAudioCtx) _tzAudioCtx = new AudioCtx();
    if (_tzAudioCtx.state === 'suspended') _tzAudioCtx.resume();
    const now = _tzAudioCtx.currentTime;
    const playTone = (freq, startOffset, duration, type = 'sine', gainVal = 0.08) => {
      const osc = _tzAudioCtx.createOscillator();
      const gain = _tzAudioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, now + startOffset);
      gain.gain.setValueAtTime(gainVal, now + startOffset);
      gain.gain.exponentialRampToValueAtTime(0.001, now + startOffset + duration);
      osc.connect(gain);
      gain.connect(_tzAudioCtx.destination);
      osc.start(now + startOffset);
      osc.stop(now + startOffset + duration);
    };
    if (kind === 'scan' || kind === 'add') {
      playTone(1350, 0, 0.065, 'sine', 0.07);
    } else if (kind === 'sale') {
      playTone(880, 0, 0.09, 'triangle', 0.09);
      playTone(1318.5, 0.09, 0.16, 'triangle', 0.1);
    } else if (kind === 'warn') {
      playTone(580, 0, 0.11, 'sawtooth', 0.06);
      playTone(440, 0.13, 0.16, 'sawtooth', 0.07);
    } else if (kind === 'error') {
      playTone(260, 0, 0.22, 'sawtooth', 0.08);
    }
  } catch (e) {}
}

/* ===== محرك توليد الباركود المحلي القياسي Code-128B بصيغة SVG بدون أي مكتبات خارجية ===== */
const _CODE128_PATTERNS = [
  "11011001100","11001101100","11001100110","10010011000","10010001100","10001001100","10011001000","10011000100",
  "10001100100","11001001000","11001000100","11000100100","10110011100","10011011100","10011001110","10111001100",
  "10011101100","10011100110","11001110010","11001011100","11001001110","11011100100","11001110100","11101101110",
  "11101001100","11100101100","11100100110","11101100100","11100110100","11100110010","11011011000","11011000110",
  "11000110110","10100011000","10001011000","10001000110","10110001000","10001101000","10001100010","11010001000",
  "11000101000","11000100010","10110111000","10110001110","10001101110","10111011000","10111000110","10001110110",
  "11101110110","11010001110","11000101110","11011101000","11011100010","11011101110","11101011000","11101000110",
  "11100010110","11101101000","11101100010","11100011010","11101111010","11001000010","11110001010","10100110000",
  "10100001100","10010110000","10010000110","10000101100","10000100110","10110010000","10110000100","10011010000",
  "10011000010","10000110100","10000110010","11000010010","11001010000","11110111010","11000010100","10001111010",
  "10100111100","10010111100","10010011110","10111100100","10011110100","10011110010","11110100100","11110010100",
  "11110010010","11011011110","11011110110","11110110110","10101111000","10100011110","10001011110","10111101000",
  "10111100010","11110101000","11110100010","10111011110","10111101110","11101011110","11110101110","11010000100",
  "11010010000","11010011100","1100011101011"
];

function tzGenerateBarcodeSvg(rawCode, opts = {}) {
  const clean = String(rawCode || 'TZ-0001').replace(/[^\x20-\x7E]/g, '').trim() || 'TZ-0001';
  const height = opts.height || 36;
  const barWidth = opts.barWidth || 1.35;
  let checksum = 104; // Start Code B
  let bits = _CODE128_PATTERNS[104];
  for (let i = 0; i < clean.length; i++) {
    const code = clean.charCodeAt(i) - 32;
    const idx = (code >= 0 && code < 95) ? code : 0;
    checksum += idx * (i + 1);
    bits += _CODE128_PATTERNS[idx];
  }
  const checkIdx = checksum % 103;
  bits += _CODE128_PATTERNS[checkIdx] + _CODE128_PATTERNS[106];

  const quiet = 8;
  const totalUnits = bits.length + quiet * 2;
  const svgW = Math.round(totalUnits * barWidth);
  let rects = '';
  let i = 0;
  while (i < bits.length) {
    if (bits[i] === '1') {
      let run = 1;
      while (i + run < bits.length && bits[i + run] === '1') run++;
      const x = ((quiet + i) * barWidth).toFixed(2);
      const w = (run * barWidth).toFixed(2);
      rects += `<rect x="${x}" y="0" width="${w}" height="${height}" fill="#000"/>`;
      i += run;
    } else {
      i++;
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgW} ${height}" width="100%" height="${height}" preserveAspectRatio="none" style="display:block;max-width:100%;margin:0 auto">${rects}</svg>`;
}

function tzBuildBarcodeLabelsPrintHtml(items, cfg = {}) {
  const size = cfg.size || '38x25'; // 38x25, 50x25, 50x30, a4_grid
  const showStore = cfg.show_store !== false;
  const showName = cfg.show_name !== false;
  const showPrice = cfg.show_price !== false;
  const showCode = cfg.show_code !== false;
  const storeName = cfg.store_name || (typeof SETTINGS !== 'undefined' && SETTINGS && SETTINGS.store_name) || 'تك زون للإلكترونيات';
  const cur = cfg.currency || (typeof CURRENCY !== 'undefined' && CURRENCY) || 'ج.م';

  const dims = {
    '38x25': { w: '38mm', h: '25mm', barH: 26, fontS: '8.5px', priceS: '10px' },
    '50x25': { w: '50mm', h: '25mm', barH: 28, fontS: '9.5px', priceS: '11px' },
    '50x30': { w: '50mm', h: '30mm', barH: 34, fontS: '10px', priceS: '11.5px' },
    'a4_grid': { w: '64mm', h: '33.9mm', barH: 32, fontS: '10px', priceS: '11.5px' },
  }[size] || { w: '38mm', h: '25mm', barH: 26, fontS: '8.5px', priceS: '10px' };

  const cards = [];
  for (const it of (items || [])) {
    const copies = Math.max(1, Math.min(200, parseInt(it.copies || 1, 10) || 1));
    const svg = tzGenerateBarcodeSvg(it.sku || String(it.id || '0001'), { height: dims.barH });
    const priceFormatted = typeof fmt === 'function' ? fmt(it.price || 0) : ((it.price || 0) / 100).toFixed(2);
    for (let c = 0; c < copies; c++) {
      cards.push(`
        <div class="bc-label">
          ${showStore ? `<div class="bc-store">${esc(storeName)}</div>` : ''}
          ${showName ? `<div class="bc-name">${esc(it.name || '')}</div>` : ''}
          <div class="bc-svg-wrap">${svg}</div>
          <div class="bc-bottom">
            ${showCode ? `<span class="bc-code">${esc(it.sku || '')}</span>` : ''}
            ${showPrice ? `<span class="bc-price">${priceFormatted} ${esc(cur)}</span>` : ''}
          </div>
        </div>
      `);
    }
  }

  const isA4 = size === 'a4_grid';
  return `<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><style>
    @page { size: ${isA4 ? 'A4 portrait' : `${dims.w} ${dims.h}`}; margin: ${isA4 ? '8mm' : '0'}; }
    * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    html, body { margin: 0; padding: 0; background: #fff; color: #000; font-family: Cairo, Tahoma, Arial, sans-serif; }
    .bc-sheet {
      display: ${isA4 ? 'grid' : 'block'};
      ${isA4 ? 'grid-template-columns: repeat(3, 1fr); gap: 3mm;' : ''}
    }
    .bc-label {
      width: ${isA4 ? '100%' : dims.w};
      height: ${dims.h};
      padding: 1.4mm 2mm;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      align-items: center;
      text-align: center;
      overflow: hidden;
      ${isA4 ? 'border: 0.5px dashed #cbd5e1; border-radius: 3px; page-break-inside: avoid;' : 'page-break-after: always; break-after: page;'}
    }
    .bc-store { font-size: 7.5px; font-weight: 700; color: #334155; line-height: 1.1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
    .bc-name { font-size: ${dims.fontS}; font-weight: 800; color: #000; line-height: 1.15; max-height: 2.3em; overflow: hidden; width: 100%; }
    .bc-svg-wrap { width: 94%; margin: 1px auto; }
    .bc-bottom { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 4px; line-height: 1.1; }
    .bc-code { font-family: monospace; font-size: 8.5px; font-weight: 700; letter-spacing: 0.3px; }
    .bc-price { font-size: ${dims.priceS}; font-weight: 900; background: #000; color: #fff; padding: 0.5px 4px; border-radius: 3px; font-family: monospace, Cairo, sans-serif; }
  </style></head><body><div class="bc-sheet">${cards.join('')}</div></body></html>`;
}

/* ===== تحويل مسار صورة المنتج المحفوظة على القرص (data/images/...) إلى مسار عرض صحيح ===== */
function tzImgSrc(val) {
  const s = String(val || '').trim();
  if (!s) return '';
  if (s.startsWith('data:image/') || s.startsWith('http://') || s.startsWith('https://') || s.startsWith('../') || s.startsWith('/')) {
    return s;
  }
  return '../data/images/' + s.replace(/^\/+/, '');
}
