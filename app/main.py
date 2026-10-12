"""نقطة تشغيل التطبيق: نافذة pywebview واحدة تعرض web/index.html."""
import pathlib
import sys

import webview

from api import Api

if getattr(sys, "frozen", False):
    # onedir: ملفات --add-data داخل sys._MEIPASS (dist/TechZone/_internal/web)
    _BASE = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(sys.executable).resolve().parent))
    WEB = _BASE / "web"
    if not (WEB / "index.html").exists():  # احتياطي: web/ بجانب الـ exe
        WEB = pathlib.Path(sys.executable).resolve().parent / "web"
    ROOT = pathlib.Path(sys.executable).resolve().parent  # data/ بجانب الـ exe
else:
    ROOT = pathlib.Path(__file__).resolve().parent.parent
    WEB = ROOT / "web"


import db


def store_title():
    try:
        with db.connect() as conn:
            name = conn.execute("SELECT value FROM settings WHERE key='store_name'").fetchone()
            if name and name["value"]:
                return name["value"]
    except Exception:
        pass
    return "تك زون للإلكترونيات"


def main():
    window = webview.create_window(
        title=store_title(),
        url=str(WEB / "index.html"),
        js_api=Api(),
        width=1360,
        height=860,
        min_size=(360, 500),
        maximized=True,
    )
    webview.start()  # ponytail: بدون LocalHTTP server — الملفات تُقرأ كـ file:// (كافٍ لنافذة واحدة)


if __name__ == "__main__":
    main()
