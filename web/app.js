/* تك زون للإلكترونيات — جسر API + تنقّل + وضع ليلي + تنسيق (مشترك لكل الصفحات) */

/* ===== الوضع الليلي (مبكر جداً لتجنب الوميض) ===== */
if (localStorage.getItem('tz-theme') === 'dark') document.documentElement.classList.add('dark');

function toggleTheme() {
  const on = document.documentElement.classList.toggle('dark');
  localStorage.setItem('tz-theme', on ? 'dark' : 'light');
}

/* ===== جسر pywebview ===== */
const _apiWait = new Promise((resolve, reject) => {
  if (window.pywebview && window.pywebview.api) resolve();
  else {
    window.addEventListener('pywebviewready', resolve, { once: true });
    // لو الصفحة فُتحت خارج نافذة البرنامج (متصفح عادي) لا تبقى بيضاء للأبد:
    // بعد 4 ثوانٍ اعرض سبباً واضحاً بدل البياض.
    setTimeout(() => reject(new Error('bridge-timeout')), 4000);
  }
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
  let res;
  try {
    res = await window.pywebview.api.call(name, payload === undefined ? null : payload);
  } catch (e) {
    throw new Error('انقطاع الاتصال بالبرنامج الداخلي');
  }
  if (!res || !res.ok) throw new Error((res && res.error) || 'خطأ غير معروف');
  return res.data;
}

/* ===== تنسيق ===== */
let CURRENCY = 'ر.س';
let SETTINGS = {};

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

/* ===== شريط التنقل الموحد (كل الصفحات الثمانية reachable) ===== */
const NAV = [
  { page: 'pos', href: 'pos.html', icon: 'point_of_sale', label: 'نقاط البيع' },
  { page: 'history', href: 'history.html', icon: 'receipt_long', label: 'سجل المبيعات' },
  { page: 'receipt', href: 'receipt.html', icon: 'print', label: 'طباعة إيصال' },
  { page: 'repair', href: 'repair.html', icon: 'build', label: 'الصيانة' },
  { page: 'inventory', href: 'inventory.html', icon: 'inventory_2', label: 'المخزون', admin: true },
  { page: 'buy_used', href: 'buy_used.html', icon: 'phonelink_setup', label: 'شراء أجهزة مستعملة', admin: true },
  { page: 'reports', href: 'reports.html', icon: 'bar_chart', label: 'التقارير', admin: true },
  { page: 'index', href: 'index.html', icon: 'switch_account', label: 'تبديل المستخدم' },
];

function renderSidebar(current, user) {
  const host = document.getElementById('shell');
  if (!host || host.querySelector('aside.tz-nav')) return;
  const items = NAV.filter((x) => !x.admin || user.role === 'admin')
    .map((x) => {
      const active = x.page === current;
      return `<a href="${x.href}" class="flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-colors ${active
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
        <div class="w-10 h-10 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">${esc((user.name || '؟').slice(0, 1))}</div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-bold text-gray-900 dark:text-white truncate">${esc(user.name)}</p>
          <p class="text-xs text-gray-500 truncate">${user.role === 'admin' ? 'مدير' : 'كاشير'}</p>
        </div>
        <button id="tz-logout" class="text-gray-400 hover:text-red-500" title="تسجيل الخروج">
          <span class="material-icons-round">logout</span></button>
      </div>
    </div>`;
  host.prepend(aside);
  aside.querySelector('#tz-logout').addEventListener('click', async () => { await guard(() => api('logout')); location.href = 'index.html'; });
  // زر قائمة للجوال: يفتح الشريط كدرج منزلق (overlay) ويغلق عند اختيار صفحة
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

/* ===== عنوان النافذة/التبويب من اسم المحل (يتغير في كل مكان عند تعديله) ===== */
function syncTitle(pageLabel) {
  const name = (SETTINGS.store_name || 'تك زون للإلكترونيات').trim() || 'تك زون للإلكترونيات';
  document.title = pageLabel ? `${pageLabel} - ${name}` : name;
}

/* ===== حارس الصفحة: جلسة + إعدادات + شريط جانبي ===== */
async function pageInit(current, opts) {
  let sess;
  try { sess = await api('session'); } catch (e) { toast('تعذر الاتصال بالبرنامج', 'error'); return null; }
  if (!sess || !sess.user) { location.href = 'index.html'; return null; }
  const user = sess.user;
  if (opts && opts.admin && user.role !== 'admin') {
    toast('هذه الصفحة للمدير فقط', 'warn');
    location.href = 'pos.html';
    return null;
  }
  try { SETTINGS = await api('settings'); } catch (e) { SETTINGS = {}; }
  CURRENCY = SETTINGS.currency || 'ر.س';
  const nav = NAV.find((x) => x.page === current);
  syncTitle(nav ? nav.label : '');
  document.body.dataset.role = user.role;
  renderSidebar(current, user);
  return user;
}
