import sys
import os
import pathlib
import time
import threading

sys.path.insert(0, os.path.abspath('app'))
import webview
from api import Api

api_inst = Api()

def test_flow(window):
    time.sleep(2)
    print('Submitting PIN 1234 from UI...', flush=True)
    window.evaluate_js('''
        const pinInp = document.getElementById("pin-input");
        if (pinInp) pinInp.value = "1234";
        PIN = "1234";
        submit();
    ''')

    for i in range(25):
        time.sleep(0.2)
        res = window.evaluate_js('''
            ({
                url: location.href.split("/").pop(),
                userName: document.getElementById("os-user-name") ? document.getElementById("os-user-name").textContent : null,
                storeName: document.getElementById("os-store-name") ? document.getElementById("os-store-name").textContent : null,
                toasts: Array.from(document.querySelectorAll(".tz-toast, #tz-bridge-err")).map(el => el.innerText || el.textContent)
            })
        ''')
        if res and res.get('url') == 'desktop.html':
            print(f"t={i*0.2:.1f}s on desktop.html: {res}", flush=True)
            if res.get('userName') and res.get('userName') != '...':
                print('SUCCESSFULLY LOGGED IN AND DESKTOP LOADED! User:', res['userName'], flush=True)
                break
            if res.get('toasts'):
                print('TOAST ERROR DETECTED:', res['toasts'], flush=True)
                break

    window.destroy()

ROOT = pathlib.Path('.').resolve()
WEB = ROOT / 'web'

w = webview.create_window('Test', url=str(WEB / 'index.html'), js_api=api_inst, hidden=True)
threading.Thread(target=test_flow, args=(w,), daemon=True).start()
webview.start()
