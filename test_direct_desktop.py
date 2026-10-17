import sys
import os
import pathlib
import time
import threading

sys.path.insert(0, os.path.abspath('app'))
import webview
from api import Api

api_inst = Api()
user = api_inst.login(pin="1234")

def test_flow(window):
    time.sleep(2)
    diag = window.evaluate_js('''
        ({
            url: location.href,
            userName: document.getElementById("os-user-name") ? document.getElementById("os-user-name").textContent : "NO_EL",
            storeName: document.getElementById("os-store-name") ? document.getElementById("os-store-name").textContent : "NO_EL",
            toasts: Array.from(document.querySelectorAll(".tz-toast, #tz-bridge-err")).map(el => el.innerText || el.textContent)
        })
    ''')
    print('DIRECT DESKTOP DIAGNOSTIC:', diag, flush=True)
    window.destroy()

ROOT = pathlib.Path('.').resolve()
WEB = ROOT / 'web'

w = webview.create_window('Test Desktop', url=str(WEB / 'desktop.html'), js_api=api_inst, hidden=True)
threading.Thread(target=test_flow, args=(w,), daemon=True).start()
webview.start()
