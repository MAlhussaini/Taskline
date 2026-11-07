"""Local-only browser activation, profiles, registration and restart persistence."""
import importlib.util
import json
import runpy
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import websocket

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
helpers=runpy.run_path(str(ROOT/'tests/calendar-browser-smoke.py'))
DevTools,wait_for=helpers['DevTools'],helpers['wait_for']
spec=importlib.util.spec_from_file_location('auth_browser_app',ROOT/'app.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)


def main():
    with tempfile.TemporaryDirectory(prefix='taskline-auth-browser-') as temporary:
        root=Path(temporary)
        app.DB_PATH=root/'tasks.db';app.UPLOAD_DIR=root/'uploads';app.initialize_database()
        store=app.initialize_accounts('owner@example.test',root/'state',root/'backups')
        class Quiet(app.TodoHandler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Quiet)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        port=server.server_port;origin=f'http://localhost:{port}'
        browser=None;dev=None
        def boot():
            browser=subprocess.Popen(['/usr/bin/google-chrome','--headless=new','--no-sandbox','--disable-gpu','--remote-allow-origins=*','--remote-debugging-port=0',f'--user-data-dir={root}/chrome','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            port_file=root/'chrome/DevToolsActivePort'
            wait_for(port_file.exists)
            def ready():
                try:
                    debug_port=port_file.read_text().splitlines()[0]
                    with urllib.request.urlopen(f'http://127.0.0.1:{debug_port}/json/list') as response: return json.load(response)
                except Exception:return None
            wait_for(ready)
            target=next(page for page in ready() if page['type']=='page')
            dev=DevTools(websocket.create_connection(target['webSocketDebuggerUrl'],timeout=10))
            dev.call('Page.enable');dev.call('Runtime.enable');return browser,dev
        def page(path,ready):
            dev.call('Page.navigate',{'url':origin+path});wait_for(lambda:dev.evaluate(ready))
        def submit(selector,values):
            dev.evaluate(f"(()=>{{const form=document.querySelector({json.dumps(selector)});for(const [key,value] of Object.entries({json.dumps(values)})) form.elements[key].value=value; form.requestSubmit();}})()")
        def fits():
            for width,height in ((320,568),(390,844),(768,1024),(1440,900)):
                dev.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<600})
                assert dev.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
        try:
            browser,dev=boot()
            page('/',"location.pathname === '/account.html' && !document.querySelector('#sign-in').hidden")
            assert dev.evaluate("Array.from(document.querySelectorAll('#auth-form input'), input => input.name)")==['email','password','setup_token']
            assert dev.evaluate("document.querySelector('#setup-token-label').hidden")
            fits()
            submit('#auth-form',{'email':'owner@example.test','password':'browser-owner-password'})
            wait_for(lambda:dev.evaluate('window.tasklineReady === true'))
            dev.evaluate("input.value='Owner private task';form.requestSubmit()")
            wait_for(lambda:dev.evaluate('tasks.length===1'))
            page('/account.html',"!!document.querySelector('#profile') && !document.querySelector('#profile').hidden && document.querySelector('#profile-form').elements.email.value === 'owner@example.test'")
            fits()
            submit('#profile-form',{'nickname':'Updated owner','theme':'dark','language':'ar'})
            wait_for(lambda:dev.evaluate("document.querySelector('#account-status').textContent.includes('تم حفظ')"))
            submit('#user-form',{'full_name':'Managed User','nickname':'Managed','email':'managed@example.test','password':'managed-browser-password'})
            wait_for(lambda:dev.evaluate("document.querySelector('#user-list').textContent.includes('managed@example.test')"))
            dev.evaluate("document.querySelector('#logout').click()")
            wait_for(lambda:dev.evaluate("!!document.querySelector('#sign-in') && !document.querySelector('#sign-in').hidden"))
            dev.evaluate("document.querySelector('#auth-toggle').click()")
            assert dev.evaluate("document.querySelector('#setup-token-label').hidden")
            submit('#auth-form',{'email':'registered@example.test','password':'registered-browser-password'})
            wait_for(lambda:dev.evaluate('window.tasklineReady === true'))
            assert dev.evaluate('tasks.length')==0
            assert dev.evaluate('TasklineAccount.role')=='User'
            user_id=dev.evaluate('TasklineAccount.id')
            # Gracefully close Chrome, restart the HTTP server and reopen its persisted profile.
            cookies=dev.call('Network.getCookies',{'urls':[origin]})['cookies']
            assert any(not cookie['session'] and cookie['httpOnly'] and cookie['secure'] for cookie in cookies), 'Persistent cookie missing'
            dev.call('Browser.close');browser.wait(timeout=10);dev.socket.close();browser=None
            server.shutdown();server.server_close()
            app.initialize_accounts('owner@example.test',root/'state',root/'backups')
            server=ThreadingHTTPServer(('127.0.0.1',port),Quiet)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            browser,dev=boot();page('/','window.tasklineReady === true')
            assert dev.evaluate('TasklineAccount.id')==user_id
            assert dev.evaluate('tasks.length')==0
            page('/account.html',"!!document.querySelector('#profile') && !document.querySelector('#profile').hidden")
            assert dev.evaluate("document.querySelector('#admin').hidden")
            fits()
            dev.evaluate("document.querySelector('#logout').click()")
            wait_for(lambda:dev.evaluate("!!document.querySelector('#sign-in') && !document.querySelector('#sign-in').hidden"))
            submit('#auth-form',{'email':'owner@example.test','password':'browser-owner-password'})
            wait_for(lambda:dev.evaluate('window.tasklineReady === true'))
            assert dev.evaluate('tasks[0].title')=='Owner private task'
            assert dev.evaluate("document.documentElement.dataset.theme")=='dark'
            assert dev.evaluate('language')=='ar'
            print('PASS browser: owner activation, registration, admin creation, profile, isolation, logout/login, persistent cookie across browser+server restart, four responsive widths')
        except Exception:
            if dev:
                print(dev.evaluate("({path:location.pathname,status:document.querySelector('#account-status')?.textContent,loading:document.querySelector('#auth-loading')?.textContent,invalid:[...document.querySelectorAll(':invalid')].map(el=>el.name)})"))
            raise
        finally:
            if dev:
                dev.socket.close()
            if browser:
                browser.terminate();browser.wait(timeout=10)
            server.shutdown();server.server_close()


if __name__=='__main__':main()
