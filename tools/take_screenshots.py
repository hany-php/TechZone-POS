"""
سكريبت التقاط لقطات شاشة لجميع صفحات نظام تك زون للإلكترونيات وحفظها في screenshots/
"""
import os
import sys
import json
import time
import subprocess
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "app"))

import api
import db

SCREENSHOTS_DIR = os.path.join(ROOT_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

api_instance = api.Api()

class TechZoneServer(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(ROOT_DIR, "web"), **kwargs)

    def do_POST(self):
        if self.path == "/api/call":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            name = data.get("name")
            payload = data.get("payload")
            res = api_instance.call(name, payload)
            out = json.dumps(res, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        # صامت لعدم ملء السجل
        pass

def run_server():
    httpd = HTTPServer(("127.0.0.1", 0), TechZoneServer)
    port = httpd.server_address[1]
    return httpd, port

PAGES = [
    ("01_login_screen.png", "index.html", 2500, (1440, 900)),
    ("02_desktop_os.png", "desktop.html", 3500, (1440, 900)),
    ("03_pos_cashier.png", "pos.html?edit_sale=10", 3000, (1440, 900)),
    ("04_sales_invoices.png", "sales_quotes.html", 3000, (1440, 900)),
    ("05_inventory_management.png", "inventory.html", 3000, (1440, 900)),
    ("06_customers_debt.png", "customers.html", 3000, (1440, 900)),
    ("07_customer_statement.png", "customer_details.html?id=1", 3000, (1440, 900)),
    ("08_maintenance_repair.png", "repair.html", 3000, (1440, 900)),
    ("09_buy_used_devices.png", "buy_used.html", 3000, (1440, 900)),
    ("10_operations_history.png", "history.html", 3000, (1440, 900)),
    ("11_financial_reports.png", "reports.html", 3000, (1440, 900)),
    ("12_staff_permissions.png", "staff.html", 3000, (1440, 900)),
    ("13_employee_profile.png", "profile.html", 3000, (1440, 900)),
    ("14_system_settings.png", "settings.html?tab=store", 3000, (1440, 900)),
    ("15_invoice_studio.png", "settings.html?tab=invoices", 3500, (1440, 900)),
    ("16_receipt_preview.png", "receipt.html?id=10", 3000, (1440, 900)),
]

def main():
    print("Starting background server on dynamic port...")
    httpd, port = run_server()
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)
    print(f"Server started on port {port}.")

    # تسجيل الدخول كمدير مسبقاً
    api_instance.login(pin="1234")
    print("Logged in as admin successfully.")

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    temp_profile = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "tz_chrome_snap")

    for filename, page_url, budget_ms, (w, h) in PAGES:
        dest_path = os.path.join(SCREENSHOTS_DIR, filename)
        url = f"http://127.0.0.1:{port}/{page_url}"
        print(f"Capturing {filename} from {page_url}...")

        args = [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            f"--window-size={w},{h}",
            f"--virtual-time-budget={budget_ms}",
            f"--user-data-dir={temp_profile}",
            f"--screenshot={dest_path}",
            url
        ]

        p = subprocess.run(args, capture_output=True, text=True, timeout=20)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            print(f" -> OK: {filename} ({os.path.getsize(dest_path)} bytes)")
        else:
            print(f" -> FAILED: {filename}. stderr: {p.stderr}")

    print("All captures completed.")

if __name__ == "__main__":
    main()
