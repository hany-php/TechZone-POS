/* تك زون للإلكترونيات — جسر API + تنقّل + صلاحيات + وضع ليلي + دعم نظام التشغيل (TechZone OS) */

/* ===== الوضع الليلي (مبكر جداً لتجنب الوميض + متزامن مع جميع نوافذ النظام) ===== */
if (localStorage.getItem('tz-theme') === 'dark') document.documentElement.classList.add('dark');

function applyThemeEverywhere(isDark) {
  try {
    const topDoc = (window.top && window.top.document) ? window.top.document : document;
    topDoc.documentElement.classList.toggle('dark', isDark);
    topDoc.querySelectorAll('iframe').forEach((fr) => {
      try {
        if (fr.contentDocument && fr.contentDocument.documentElement) {
          fr.contentDocument.documentElement.classList.toggle('dark', isDark);
        }
      } catch (e) {}
    });
  } catch (e) {}
  document.documentElement.classList.toggle('dark', isDark);
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
  const on = !document.documentElement.classList.contains('dark');
  localStorage.setItem('tz-theme', on ? 'dark' : 'light');
  applyThemeEverywhere(on);
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
  { page: 'customers', href: 'customers.html', icon: 'people', label: 'العملاء والمديونيات', perm: ['customers_view', 'customers_edit'] },
  { page: 'history', href: 'history.html', icon: 'receipt_long', label: 'سجل المبيعات' },
  { page: 'receipt', href: 'receipt.html', icon: 'print', label: 'الإيصال والإعدادات' },
  { page: 'repair', href: 'repair.html', icon: 'build', label: 'الصيانة', perm: ['repair_view', 'repair_edit'] },
  { page: 'inventory', href: 'inventory.html', icon: 'inventory_2', label: 'المخزون', perm: ['inventory_view', 'inventory_edit'] },
  { page: 'buy_used', href: 'buy_used.html', icon: 'phonelink_setup', label: 'شراء أجهزة مستعملة', perm: 'used_manage' },
  { page: 'reports', href: 'reports.html', icon: 'bar_chart', label: 'التقارير والموظفون', perm: ['reports_view', 'settings_manage'] },
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
        <div class="w-10 h-10 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">${esc((user.name || '؟').slice(0, 1))}</div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-bold text-gray-900 dark:text-white truncate">${esc(user.name)}</p>
          <p class="text-xs text-gray-500 truncate">${user.role === 'admin' ? 'مدير' : 'موظف / كاشير'}</p>
        </div>
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
