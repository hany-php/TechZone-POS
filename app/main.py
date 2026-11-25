"""نقطة تشغيل التطبيق: نافذة pywebview واحدة تعرض web/index.html مع دعم التصغير إلى شريط النظام بجوار الساعة (System Tray)."""
import pathlib
import sys

import webview

from api import Api
from api_common import _STATE

if getattr(sys, "frozen", False):
    # onedir / onefile: ملفات --add-data داخل sys._MEIPASS
    _BASE = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(sys.executable).resolve().parent))
    WEB = _BASE / "web"
    if not (WEB / "index.html").exists():  # احتياطي: web/ بجانب الـ exe
        WEB = pathlib.Path(sys.executable).resolve().parent / "web"
    ROOT = pathlib.Path(sys.executable).resolve().parent  # data/ بجانب الـ exe
else:
    ROOT = pathlib.Path(__file__).resolve().parent.parent
    WEB = ROOT / "web"


import db

_TRAY_STATE = {
    "force_exit": False,
    "notify_icon": None,
    "form": None,
    "balloon_shown": False,
}


def store_title():
    try:
        with db.connect() as conn:
            name = conn.execute("SELECT value FROM settings WHERE key='store_name'").fetchone()
            if name and name["value"]:
                return name["value"]
    except Exception:
        pass
    return "تك زون للإلكترونيات"


def is_close_exit_enabled() -> bool:
    """التحقق من إعداد (إغلاق البرنامج نهائياً عند الضغط على علامة X):
    - إذا كان مفعلاً ('1'): يُغلق البرنامج نهائياً عند الضغط على X.
    - إذا لم يكن مفعلاً ('0' — الافتراضي): تختفي النافذة ويبقى البرنامج يعمل في شريط النظام بجوار الساعة (System Tray).
    """
    try:
        with db.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='close_exit_app'").fetchone()
            if row and str(row["value"]).strip() == "1":
                return True
    except Exception:
        pass
    return False


def _dispose_tray_icon():
    ni = _TRAY_STATE.get("notify_icon")
    if ni is not None:
        try:
            ni.Visible = False
            ni.Dispose()
        except Exception:
            pass
        _TRAY_STATE["notify_icon"] = None


def request_app_shutdown():
    """إغلاق البرنامج نهائياً بنعومة (يُستخدم أثناء تثبيت التحديثات التلقائية لتجاوز وضع التصغير بجوار الساعة)."""
    _TRAY_STATE["force_exit"] = True
    _STATE["force_exit"] = True
    _dispose_tray_icon()
    form = _TRAY_STATE.get("form")
    if sys.platform == "win32" and form is not None:
        try:
            from System import Action

            def _do_close():
                try:
                    form.Close()
                except Exception:
                    pass

            if form.InvokeRequired:
                form.Invoke(Action(_do_close))
            else:
                _do_close()
            return
        except Exception:
            pass
    win = _STATE.get("window")
    if win is not None:
        try:
            win.destroy()
            return
        except Exception:
            pass
    import os
    os._exit(0)


def _restore_from_tray(window):
    """إظهار وإعادة تنشيط نافذة البرنامج من شريط النظام بجوار الساعة."""
    form = _TRAY_STATE.get("form")
    if sys.platform == "win32" and form is not None:
        try:
            from System import Action
            from System.Windows.Forms import FormWindowState

            def _do_restore():
                try:
                    form.ShowInTaskbar = True
                    form.Show()
                    if form.WindowState != FormWindowState.Maximized:
                        form.WindowState = FormWindowState.Maximized
                    form.Activate()
                    form.BringToFront()
                except Exception:
                    pass

            if form.InvokeRequired:
                form.Invoke(Action(_do_restore))
            else:
                _do_restore()
            return
        except Exception:
            pass
    try:
        window.show()
        window.restore()
    except Exception:
        pass


def _hide_to_tray(window):
    """إخفاء النافذة في شريط النظام بجوار الساعة مع إبقاء البرنامج يعمل في الخلفية."""
    title = store_title()
    form = _TRAY_STATE.get("form")
    ni = _TRAY_STATE.get("notify_icon")
    if sys.platform == "win32" and form is not None:
        try:
            from System import Action
            from System.Windows.Forms import ToolTipIcon

            def _do_hide():
                try:
                    if ni is not None:
                        ni.Text = title[:63]
                        ni.Visible = True
                        if not _TRAY_STATE.get("balloon_shown"):
                            _TRAY_STATE["balloon_shown"] = True
                            ni.ShowBalloonTip(
                                2500,
                                title[:63],
                                "ما زال البرنامج يعمل في شريط النظام بجوار الساعة — اضغط على الأيقونة لإعادة فتحه.",
                                ToolTipIcon.Info,
                            )
                    form.Hide()
                except Exception:
                    pass

            if form.InvokeRequired:
                form.Invoke(Action(_do_hide))
            else:
                _do_hide()
            return
        except Exception:
            pass
    try:
        window.hide()
    except Exception:
        pass


def is_start_in_tray_requested(argv=None) -> bool:
    """التحقق مما إذا تم تشغيل البرنامج بخيار البدء الصامت في شريط النظام بجوار الساعة (--tray)."""
    args = sys.argv[1:] if argv is None else list(argv)
    return any(str(a).strip().lower() in ("--tray", "--minimized", "--background", "/tray") for a in args)


def _setup_winforms_tray(window, icon_path, start_hidden: bool = False):
    """إنشاء أيقونة شريط النظام بجوار الساعة (System Tray NotifyIcon) على ويندوز عبر WinForms."""
    if sys.platform != "win32" or _TRAY_STATE.get("notify_icon") is not None:
        return
    try:
        from System import Action
        from System.Drawing import Icon, SystemIcons
        from System.Windows.Forms import (
            ContextMenuStrip,
            FormClosingEventHandler,
            MouseButtons,
            MouseEventHandler,
            NotifyIcon,
            RightToLeft,
        )
        from webview.platforms.winforms import BrowserView

        form = BrowserView.instances.get(window.uid)
        if not form:
            return
        _TRAY_STATE["form"] = form

        def _init_tray():
            try:
                ni = NotifyIcon()
                if icon_path and pathlib.Path(icon_path).exists():
                    try:
                        ni.Icon = Icon(str(icon_path))
                    except Exception:
                        ni.Icon = form.Icon or SystemIcons.Application
                else:
                    ni.Icon = form.Icon or SystemIcons.Application

                ni.Text = store_title()[:63]
                ni.Visible = True

                menu = ContextMenuStrip()
                try:
                    menu.RightToLeft = RightToLeft.Yes
                except Exception:
                    pass

                item_open = menu.Items.Add("فتح نافذة البرنامج")
                item_open.Click += lambda s, e: _restore_from_tray(window)

                menu.Items.Add("-")

                def _on_exit_click(s, e):
                    _TRAY_STATE["force_exit"] = True
                    _dispose_tray_icon()
                    try:
                        form.Close()
                    except Exception:
                        try:
                            window.destroy()
                        except Exception:
                            pass

                item_exit = menu.Items.Add("إغلاق البرنامج نهائياً (خروج)")
                item_exit.Click += _on_exit_click

                ni.ContextMenuStrip = menu
                ni.DoubleClick += lambda s, e: _restore_from_tray(window)

                def _on_mouse_click(s, e):
                    try:
                        if e.Button == MouseButtons.Left:
                            _restore_from_tray(window)
                    except Exception:
                        pass

                ni.MouseClick += MouseEventHandler(_on_mouse_click)
                _TRAY_STATE["notify_icon"] = ni

                def _on_form_closing(sender, e):
                    if _TRAY_STATE.get("force_exit") or _STATE.get("force_exit") or is_close_exit_enabled():
                        _dispose_tray_icon()
                        return
                    e.Cancel = True
                    _hide_to_tray(window)

                form.FormClosing += FormClosingEventHandler(_on_form_closing)
                if start_hidden:
                    try:
                        form.ShowInTaskbar = False
                        form.Hide()
                    except Exception:
                        pass
            except Exception:
                pass

        if form.InvokeRequired:
            form.Invoke(Action(_init_tray))
        else:
            _init_tray()
    except Exception:
        pass


def main():
    try:
        db.daily_startup_backup()
    except Exception:
        pass

    icon_candidates = [
        ROOT / "icon.ico",
        _BASE / "icon.ico" if getattr(sys, "frozen", False) else None,
        WEB / "favicon.ico",
        WEB / "icon.ico",
    ]
    icon_path = next((p for p in icon_candidates if p and p.exists()), None)

    start_in_tray = is_start_in_tray_requested()

    window = webview.create_window(
        title=store_title(),
        url=str(WEB / "index.html"),
        js_api=Api(),
        width=1360,
        height=860,
        min_size=(360, 500),
        maximized=not start_in_tray,
        hidden=start_in_tray,
    )
    _STATE["window"] = window
    _STATE["force_exit"] = False
    _STATE["shutdown_cb"] = request_app_shutdown

    def _on_window_shown():
        _setup_winforms_tray(window, icon_path, start_hidden=False)

    def _on_webview_started():
        import time
        # عند البدء الصامت مع ويندوز (--tray)، ننتظر لحظة تهيئة نافذة WinForms ثم ننشئ أيقونة شريط النظام فوراً دون إظهار النافذة
        for _ in range(40):
            _setup_winforms_tray(window, icon_path, start_hidden=start_in_tray)
            if _TRAY_STATE.get("notify_icon") is not None:
                break
            time.sleep(0.1)

    def _on_window_closing():
        if _TRAY_STATE.get("force_exit") or _STATE.get("force_exit") or is_close_exit_enabled():
            _dispose_tray_icon()
            return True
        _setup_winforms_tray(window, icon_path)
        _hide_to_tray(window)
        return False

    def _on_window_closed():
        _dispose_tray_icon()
        _STATE["owner"] = None
        _STATE["user"] = None
        _STATE["window"] = None

    window.events.shown += _on_window_shown
    window.events.closing += _on_window_closing
    window.events.closed += _on_window_closed
    webview.start(func=_on_webview_started, icon=str(icon_path) if icon_path else None)


if __name__ == "__main__":
    main()
