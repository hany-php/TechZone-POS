"""نقطة تشغيل التطبيق: نافذة pywebview واحدة تعرض web/index.html."""
import pathlib

import webview

from api import Api

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
