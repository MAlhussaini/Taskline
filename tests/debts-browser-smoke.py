"""Actual finance UI, isolated server/account/database and Chrome profile."""
import base64
import json
import runpy
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
import websocket

ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT / 'tests/star-rules.test.py'))
browser_helpers = runpy.run_path(str(ROOT / 'tests/calendar-browser-smoke.py'))
DevTools, wait_for = browser_helpers['DevTools'], browser_helpers['wait_for']
fixture = helpers['StarRules']()
fixture.setUp()
try:
    with tempfile.TemporaryDirectory(prefix='taskline-debts-chrome-') as temporary:
        browser = subprocess.Popen(['/usr/bin/google-chrome', '--headless=new', '--no-sandbox', '--disable-gpu',
            '--remote-allow-origins=*', '--remote-debugging-port=0', f'--user-data-dir={temporary}', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            port_file = Path(temporary) / 'DevToolsActivePort'
            wait_for(port_file.exists)
            port = port_file.read_text().splitlines()[0]
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list') as response:
                target = next(p for p in json.load(response) if p['type'] == 'page')
            dev = DevTools(websocket.create_connection(target['webSocketDebuggerUrl'], timeout=10))
            dev.call('Runtime.enable'); dev.call('Page.enable')
            name, token = fixture.cookie.split('=', 1)
            dev.call('Network.setCookie', {'name':name, 'value':token, 'url':fixture.origin, 'secure':True,
                'httpOnly':True, 'sameSite':'Strict', 'expires':time.time()+86400})
            dev.call('Page.addScriptToEvaluateOnNewDocument', {'source':"window.uiErrors=[]; addEventListener('error',e=>uiErrors.push(e.message)); addEventListener('unhandledrejection',e=>uiErrors.push(String(e.reason)));"})
            dev.call('Page.navigate', {'url':fixture.origin})
            wait_for(lambda: dev.evaluate('window.tasklineReady === true'))

            def run(js):
                result = dev.call('Runtime.evaluate', {'expression':js, 'awaitPromise':True, 'returnByValue':True})
                assert not result.get('exceptionDetails'), result
                return result.get('result', {}).get('value')

            def click(selector):
                dev.evaluate(f'document.querySelector({json.dumps(selector)}).click()')

            def save(fields):
                for field, value in fields.items():
                    dev.evaluate(f'document.querySelector({json.dumps(field)}).value={json.dumps(value)}')
                dev.evaluate("document.querySelector('#debt-edit-form').requestSubmit()")
                wait_for(lambda: dev.evaluate("!document.querySelector('#debt-editor').open"))

            def confirm_action(selector):
                dev.call('Runtime.evaluate', {'expression':f'setTimeout(() => document.querySelector({json.dumps(selector)}).click(), 100)'})
                time.sleep(.2)
                dev.call('Page.handleJavaScriptDialog', {'accept':True})
                wait_for(lambda: dev.evaluate("document.querySelector('#debts-section .debt-status').textContent.includes('Saved')"))

            run("TasklineSettings.go('settings')")
            assert not dev.evaluate("TasklineSettings.enabled('debts')")
            assert dev.evaluate("document.querySelector('#nav-debts').hidden")
            dev.evaluate("document.querySelector('[data-group=spaces]').open=true")
            click('#feature-debts')
            wait_for(lambda: dev.evaluate("TasklineSettings.enabled('debts') && !document.querySelector('.settings-shared').disabled"))
            assert dev.evaluate("TasklineSettings.values.footer[0]") == 'debts'
            assert not dev.evaluate("document.querySelector('#settings-open').hidden")
            run("TasklineSettings.go('debts')")
            for title, amount in [('صديقي', '+100.10'), ('البقالة', '-40.25'), ('العمل', '+20')]:
                click('[data-debt-action=new-list]'); save({'#debt-title':title})
                click('[data-debt-action=new-entry]')
                save({'#debt-title':'عملية <script> & تجربة', '#debt-amount':amount, '#debt-date':'2026-11-01'})
            rows = run("api('/api/debts')")
            friend = next(l for l in rows if l['title'] == 'صديقي')
            lid = friend['id']
            card = f'[data-debt-list="{lid}"]'
            assert dev.evaluate("document.querySelectorAll('#debts-section time').length") == 0
            click(card + ' [data-debt-action=new-entry]')
            save({'#debt-title':'مبلغ لي', '#debt-amount':'-٣٠٫٢٠'})
            assert run(f"api('/api/debts/{lid}')")['balance_cents'] == 6990
            # Validation leaves the form and ledger unchanged.
            click(card + ' [data-debt-action=new-entry]')
            dev.evaluate("document.querySelector('#debt-title').value='invalid'; document.querySelector('#debt-amount').value='0.001'; document.querySelector('#debt-edit-form').requestSubmit()")
            assert dev.evaluate("document.querySelector('#debt-editor').open && !!document.querySelector('#debt-editor-error').textContent")
            click('#debt-editor [data-debt-action=close-editor]')
            click(card + ' [data-debt-action=settle]')
            assert dev.evaluate("document.querySelector('#debt-subtotal').textContent") == '69.90'
            assert dev.evaluate("document.querySelector('#debt-tax').textContent") == '10.49'
            assert dev.evaluate("document.querySelector('#debt-tax-total').textContent") == '80.39'
            assert dev.evaluate("document.activeElement.textContent") == 'Cancel'
            click('#debt-settle [data-debt-action=close-settle]')
            assert len(run(f"api('/api/debts/{lid}')")['entries']) == 2
            click(card + ' [data-debt-action=settle]')
            # A failed write keeps the amounts visible and allows retry/cancel.
            dev.evaluate("window.financeFetch=window.fetch; window.fetch=(url,options)=>String(url).includes('/settle') ? Promise.resolve(new Response(JSON.stringify({error:'Test offline failure'}),{status:503,headers:{'Content-Type':'application/json'}})) : financeFetch(url,options)")
            click('#debt-settle [data-debt-action=confirm-settle]')
            wait_for(lambda: dev.evaluate("document.querySelector('#debt-settle-error').textContent.includes('Test offline failure') && !document.querySelector('[data-debt-action=confirm-settle]').disabled"))
            assert dev.evaluate("document.querySelector('#debt-settle').open")
            dev.evaluate('window.fetch=window.financeFetch')
            click('#debt-settle [data-debt-action=confirm-settle]')
            wait_for(lambda: dev.evaluate("!document.querySelector('#debt-settle').open"))
            wait_for(lambda: dev.evaluate(f'document.querySelector(\'{card} [data-debt-action=settle]\').disabled'))
            result = run(f"api('/api/debts/{lid}')")
            assert result['balance_cents'] == 0 and len(result['entries']) == 3
            assert result['archive_count'] == 3 and result['current_count'] == 0
            assert dev.evaluate(f"document.querySelectorAll('{card} [data-debt-entry]').length") == 0
            assert dev.evaluate(f"[...document.querySelectorAll('{card} .debt-totals .debt-amount')].every(el=>el.textContent==='0.00')")
            click(card + ' [data-debt-action=archive]')
            assert dev.evaluate("document.querySelector('#debt-details [data-debt-action=show-archive]').getAttribute('aria-pressed')") == 'true'
            assert dev.evaluate("document.querySelectorAll('#debt-details [data-debt-entry]').length") == 3
            click('#debt-details [data-debt-action=show-current]')
            assert dev.evaluate("document.querySelectorAll('#debt-details [data-debt-entry]').length") == 0
            click('#debt-details [data-debt-action=close-details]')
            # A new entry, even backdated, stays outside the archive after reload.
            click(card + ' [data-debt-action=new-entry]')
            save({'#debt-title':'New after settlement', '#debt-amount':'5', '#debt-date':'2020-01-01'})
            run('TasklineDebts.load()')
            assert dev.evaluate(f"document.querySelectorAll('{card} [data-debt-entry]').length") == 1
            click(card + ' [data-debt-action=archive]')
            assert dev.evaluate("document.querySelectorAll('#debt-details [data-debt-entry]').length") == 3
            click('#debt-details [data-debt-action=show-current]')
            assert dev.evaluate("document.querySelectorAll('#debt-details [data-debt-entry]').length") == 1
            click('#debt-details [data-debt-action=close-details]')
            confirm_action(card + ' [data-debt-action=delete-entry]')
            wait_for(lambda: dev.evaluate(f"document.querySelectorAll('{card} [data-debt-entry]').length === 0"))
            assert dev.evaluate("document.querySelectorAll('#debts-section .debt-settlement').length") == 0
            click(card + ' [data-debt-action=details]')
            assert dev.evaluate("document.querySelectorAll('#debt-details time').length") == 3
            assert dev.evaluate("document.querySelectorAll('#debt-details .debt-settlement').length") == 1
            click('#debt-details .debt-settlement [data-debt-action=edit-entry]')
            save({'#debt-amount':'-60.00'})
            assert run(f"api('/api/debts/{lid}')")['balance_cents'] == 990
            assert dev.evaluate(f"document.querySelectorAll('{card} [data-debt-entry]').length") == 2
            assert dev.evaluate("document.querySelector('#debt-details [data-debt-action=show-current]').getAttribute('aria-pressed')") == 'true'
            click('#debt-details [data-debt-action=close-details]')
            negative_id = next(l['id'] for l in rows if l['title'] == 'البقالة')
            click(f'[data-debt-list="{negative_id}"] [data-debt-action=settle]')
            assert dev.evaluate("document.querySelector('#debt-subtotal').textContent") == '40.25'
            assert dev.evaluate("document.querySelector('#debt-tax').textContent") == '6.04'
            assert dev.evaluate("document.querySelector('#debt-tax-total').textContent") == '46.29'
            assert dev.evaluate("document.querySelector('.debt-settle-direction').textContent") == 'Owed to you'
            click('#debt-settle [data-debt-action=close-settle]')
            # Layout, RTL, themes and long titles on phone, landscape, tablet and desktop.
            for theme in ('light','dark'):
                for lang in ('ar','en'):
                    dev.evaluate(f"language='{lang}'; applyLanguage(); TasklineTheme.setPreference('{theme}')")
                    for width,height in ((320,568),(390,844),(568,320),(768,1024),(1440,900)):
                        dev.call('Emulation.setDeviceMetricsOverride', {'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<=600})
                        assert dev.evaluate('document.documentElement.scrollWidth <= innerWidth'), (theme,lang,width)
                        click(card + ' [data-debt-action=details]')
                        assert dev.evaluate("document.querySelector('#debt-details').scrollWidth <= document.querySelector('#debt-details').clientWidth"), (theme,lang,width,'details')
                        assert dev.evaluate("""(() => {
                          const dialog=document.querySelector('#debt-details');
                          const bounds=dialog.getBoundingClientRect();
                          const heading=dialog.querySelector('.dialog-heading').getBoundingClientRect();
                          return heading.left >= bounds.left+12 && heading.right <= bounds.right-12;
                        })()"""), (theme,lang,width,'dialog padding')
                        assert dev.evaluate("""[...document.querySelectorAll('#debt-details .debt-totals > span')].every(el => {
                          const box=el.getBoundingClientRect(), amount=el.querySelector('.debt-amount').getBoundingClientRect();
                          return Math.abs((box.left+box.right)/2-(amount.left+amount.right)/2)<2;
                        })"""), (theme,lang,width,'aligned totals')
                        click('#debt-details [data-debt-action=close-details]')
                        click(card + ' [data-debt-action=settle]')
                        assert dev.evaluate("document.querySelector('#debt-settle').scrollWidth <= document.querySelector('#debt-settle').clientWidth"), (theme,lang,width,'settlement overflow')
                        assert dev.evaluate("[...document.querySelectorAll('#debt-settle button')].every(el => el.getBoundingClientRect().height>=44)"), (theme,lang,width,'touch target')
                        click('#debt-settle [data-debt-action=close-settle]')
            dev.evaluate("language='ar'; applyLanguage(); TasklineTheme.setPreference('light')")
            dev.call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            image = dev.call('Page.captureScreenshot', {'format':'png'})
            Path('/root/taskline-debts-mobile.png').write_bytes(base64.b64decode(image['data']))
            click(card + ' [data-debt-action=details]')
            image = dev.call('Page.captureScreenshot', {'format':'png'})
            Path('/root/taskline-debts-details-mobile.png').write_bytes(base64.b64decode(image['data']))
            click('#debt-details [data-debt-action=close-details]')
            click(card + ' [data-debt-action=settle]')
            image = dev.call('Page.captureScreenshot', {'format':'png'})
            Path('/root/taskline-debts-tax-mobile.png').write_bytes(base64.b64decode(image['data']))
            click('#debt-settle [data-debt-action=close-settle]')
            dev.evaluate("language='en'; applyLanguage()")
            confirm_action(card + ' [data-debt-action=clear]')
            wait_for(lambda: len(run(f"api('/api/debts/{lid}')")['entries']) == 0)
            confirm_action(card + ' [data-debt-action=delete-list]')
            wait_for(lambda: dev.evaluate(f'document.querySelector(\'{card}\') === null'))
            run("TasklineSettings.go('settings')")
            run("TasklineSettings.save({features:{debts:false}})")
            assert dev.evaluate("document.querySelector('#nav-debts').hidden && TasklineSettings.values.footer[0] === 'settings'")
            run("TasklineSettings.save({features:{debts:true}})")
            dev.call('Page.reload')
            wait_for(lambda: dev.evaluate("window.tasklineReady === true && !document.querySelector('#nav-debts').hidden"))
            run("TasklineSettings.go('debts')")
            assert len(run("api('/api/debts')")) == 2
            assert dev.evaluate('uiErrors') == [], dev.evaluate('uiErrors')
            print('PASS finance UI: opt-in, footer, signed Arabic amounts, validation, settlement history, editing, clearing, deletion, persistence, RTL and responsive themes')
        finally:
            try:
                dev.call('Browser.close')
            except Exception:
                browser.terminate()
            browser.wait(timeout=10)
            time.sleep(.3)
finally:
    fixture.tearDown()
