#!/usr/bin/env python3
"""Exercise the real UI/API with a temporary database; never touch live tasks.db.

Requires google-chrome and Python websocket-client. Optional: --screenshots DIR.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import runpy
import subprocess
import tempfile
import threading
import time
import urllib.request
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from accounts import COOKIE, password_hash
helpers = runpy.run_path(str(ROOT / "tests/calendar-browser-smoke.py"))
DevTools, wait_for = helpers["DevTools"], helpers["wait_for"]
VIEWPORTS = ((320, 568), (390, 844), (568, 320), (768, 1024), (1440, 900))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("taskline_ui_test", ROOT / "app.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)

    with tempfile.TemporaryDirectory(prefix="taskline-ui-test-") as temporary:
        app.DB_PATH = Path(temporary) / "isolated.db"
        app.UPLOAD_DIR = Path(temporary) / "uploads"
        app.initialize_database()
        store = app.initialize_accounts('owner@example.test', Path(temporary) / 'state', Path(temporary) / 'backups')
        with store.connect() as db:
            db.execute('UPDATE auth_users SET password_hash=? WHERE is_owner=1', (password_hash('fixture-browser-password'),))
        session_token = store.issue_session(1, 'UI regression tests')

        class QuietHandler(app.TodoHandler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        browser = subprocess.Popen([
            "/usr/bin/google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu",
            "--remote-allow-origins=*", "--remote-debugging-port=0",
            f"--user-data-dir={temporary}/chrome", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            port_file = Path(temporary) / "chrome/DevToolsActivePort"
            wait_for(port_file.exists)
            port = port_file.read_text().splitlines()[0]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as response:
                target = next(page for page in json.load(response) if page["type"] == "page")
            socket = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10)
            dev = DevTools(socket)
            dev.call("Runtime.enable")
            dev.call("Page.enable")
            dev.call('Network.setCookie', {'name':COOKIE, 'value':session_token, 'url':origin, 'secure':True, 'httpOnly':True, 'sameSite':'Strict', 'expires':time.time()+86400})
            dev.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.uiErrors = [];
              addEventListener('error', e => uiErrors.push(e.message));
              addEventListener('unhandledrejection', e => uiErrors.push(String(e.reason)));
            """})
            dev.call("Page.navigate", {"url": origin})
            wait_for(lambda: dev.evaluate("document.readyState === 'complete' && window.tasklineReady === true"))
            assert dev.evaluate("document.activeElement.id !== 'task-input'")
            date = dev.evaluate("today")

            def request(path, payload, workspace="personal"):
                req = urllib.request.Request(
                    f"{origin}{path}?workspace={workspace}",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json", "Cookie":COOKIE+'='+session_token}, method="POST",
                )
                with urllib.request.urlopen(req) as response:
                    return json.load(response)

            for workspace in ("personal", "work"):
                for title in ("Plan the next small step", "مراجعة الملاحظات وتجهيز قائمة المقاضي للأسبوع القادم", "LongTitle" * 20):
                    request("/api/tasks", {"title": title, "task_date": date}, workspace)
                for title in ("مقاضي الأسبوع واحتياجات المنزل الأساسية", "A very long reusable shopping checklist for the whole family"):
                    checklist = request("/api/lists", {"title": title}, workspace)
                    request(f"/api/lists/{checklist['id']}/items", {"title": "حليب وخبز وفواكه وخضار طازجة للعائلة"}, workspace)
                request("/api/tasks", {"title": "An idea for later", "location": "inbox"}, workspace)
                request("/api/dreams", {"title": "Learn a new language — تعلم لغة جديدة"}, workspace)
                request("/api/routines", {"title": "A long weekly routine — مراجعة مهام الأسبوع والاستعداد للأسبوع القادم", "start_date": "2030-01-01", "frequency": "daily"}, workspace)

            def evaluate_async(expression):
                result = dev.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
                assert not result.get("exceptionDetails"), result
                return result.get("result", {}).get("value")

            def click(selector, hold=False, touch=False, cancel=False, move=False):
                point = evaluate_async(f"""(async () => {{
                  const el = document.querySelector({json.dumps(selector)});
                  el.scrollIntoView({{block: 'center'}});
                  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                  const r = el.getBoundingClientRect();
                  return {{x: r.x + r.width / 2 - visualViewport.offsetLeft,
                    y: r.y + r.height / 2 - visualViewport.offsetTop}};
                }})()""")
                if touch:
                    dev.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**point, "id": 1}]})
                    if hold:
                        time.sleep(.65)
                    if move:
                        dev.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{**point, "x": point["x"] + 25, "id": 1}]})
                    dev.call("Input.dispatchTouchEvent", {"type": "touchCancel" if cancel else "touchEnd", "touchPoints": []})
                else:
                    dev.call("Input.dispatchMouseEvent", {"type": "mousePressed", **point, "button": "left", "clickCount": 1})
                    if hold:
                        time.sleep(.65)
                    dev.call("Input.dispatchMouseEvent", {"type": "mouseReleased", **point, "button": "left", "clickCount": 1})

            def fits(context):
                result = dev.evaluate("""(() => ({
                  fits: document.documentElement.scrollWidth <= innerWidth,
                  overflow: [...document.querySelectorAll('main *, .app-header *')].filter(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 1 && r.height > 1 && (r.right > innerWidth + 1 || r.left < -1)
                      && !el.classList.contains('sr-only');
                  }).map(el => el.id || el.className || el.tagName)
                }))()""")
                assert result["fits"] and not result["overflow"], (context, result)

            def screenshot(name, scroll_top=True):
                if args.screenshots:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    if scroll_top:
                        dev.evaluate("window.scrollTo(0, 0)")
                    result = dev.call("Page.captureScreenshot", {"format": "png"})
                    (args.screenshots / f"{name}.png").write_bytes(base64.b64decode(result["data"]))

            evaluate_async("loadTasks()")
            # Normal -> starred -> normal and completed -> incomplete restore the order.
            original = dev.evaluate("tasks.map(task => task.id)")
            # A later red task must outrank an earlier yellow task, including after reload.
            evaluate_async("toggleStar(tasks[0])")
            evaluate_async(f"toggleStar(tasks.find(task => task.id === {original[2]}), 2)")
            assert dev.evaluate("Number(list.firstElementChild.dataset.id)") == original[2]
            evaluate_async("loadTasks()")
            assert dev.evaluate("Number(list.firstElementChild.dataset.id)") == original[2]
            evaluate_async(f"toggleStar(tasks.find(task => task.id === {original[2]}))")
            evaluate_async(f"toggleStar(tasks.find(task => task.id === {original[0]}))")
            evaluate_async("toggleStar(tasks[1])")
            assert dev.evaluate("Number(list.firstElementChild.dataset.id)") == original[1]
            evaluate_async("toggleStar(tasks.find(task => task.id === " + str(original[1]) + "))")
            assert dev.evaluate("[...list.children].map(row => Number(row.dataset.id))") == original
            evaluate_async("toggleTask(tasks[0])")
            assert dev.evaluate("Number(list.lastElementChild.dataset.id)") == original[0]
            evaluate_async("toggleTask(tasks.find(task => task.id === " + str(original[0]) + "))")
            assert dev.evaluate("[...list.children].map(row => Number(row.dataset.id))") == original

            # A hold creates red; yellow and red each clear with one ordinary click.
            first_star = f'[data-id="{original[0]}"] [data-star]'
            click(first_star, hold=True)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 2"))
            assert dev.evaluate("document.querySelector('.day-star-badge') !== null")
            assert dev.evaluate(f"getComputedStyle(document.querySelector({json.dumps(first_star)})).color === 'rgb(199, 53, 53)'")
            second_star = f'[data-id="{original[1]}"] [data-star]'
            click(second_star)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[1]}).starred === 1"))
            click(second_star, hold=True)
            wait_for(lambda: dev.evaluate("error.textContent.includes('one task of the day')"))
            assert dev.evaluate(f"tasks.find(task => task.id === {original[1]}).starred === 1")
            click(second_star)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[1]}).starred === 0"))
            assert dev.evaluate("error.textContent === ''")
            click(first_star)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 0"))
            click(first_star)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 1"))
            # Completing still releases the star and restores yellow on reopening.
            click(f'[data-id="{original[0]}"] [data-check]')
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).completed === 1"))
            assert dev.evaluate(f"document.querySelector({json.dumps(first_star)}).disabled && !document.querySelector({json.dumps(first_star)}).classList.contains('starred')")
            click(f'[data-id="{original[0]}"] [data-check]')
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).completed === 0"))
            assert dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 1")
            evaluate_async(f"toggleStar(tasks.find(task => task.id === {original[0]}))")

            dev.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            dev.call("Emulation.setTouchEmulationEnabled", {"enabled": True})
            click(first_star, hold=True, touch=True, cancel=True)
            assert dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 0")
            click(first_star, hold=True, touch=True, move=True)
            assert dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 0")
            click(first_star, hold=True, touch=True)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 2"))
            click(first_star, touch=True)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 0"))

            # Add consecutive subtasks without native prompts or losing input focus.
            assert dev.evaluate("document.querySelectorAll('.subtask-shortcut').length === 0")
            click("[data-task-more]")
            click(".task-tools:not([hidden]) [data-add-subtask]")
            wait_for(lambda: dev.evaluate("subtaskDialog.open"))
            for title in ("First small step", "خطوة فرعية ثانية واضحة"):
                dev.evaluate(f"subtaskInput.value = {json.dumps(title)}")
                click("#subtask-save")
                try:
                    wait_for(lambda: dev.evaluate("!subtaskSaving && subtaskInput.value === ''"))
                except TimeoutError:
                    screenshot("subtask-save-failure")
                    raise AssertionError(dev.evaluate("({saving:subtaskSaving, error:subtaskError.textContent, open:subtaskDialog.open, errors:uiErrors, value:subtaskInput.value})"))
                assert dev.evaluate("subtaskDialog.open && document.activeElement === subtaskInput")
            assert dev.evaluate("document.querySelectorAll('#subtask-preview li').length === 2")
            dev.evaluate("window.savedFetch = window.fetch; window.fetch = () => Promise.reject(new Error('Test subtask save failure')); subtaskInput.value = 'Keep this draft'")
            click("#subtask-save")
            wait_for(lambda: dev.evaluate("subtaskError.textContent.includes('Test subtask save failure')"))
            assert dev.evaluate("subtaskInput.value === 'Keep this draft' && subtaskError.getBoundingClientRect().height > 0")
            dev.evaluate("window.fetch = window.savedFetch")
            click("#subtask-done")
            wait_for(lambda: dev.evaluate("document.activeElement.classList.contains('subtask-shortcut')"))
            assert dev.evaluate("document.querySelectorAll('.subtask-shortcut').length === 1")
            children = dev.evaluate(f"tasks.filter(task => task.parent_id === {original[0]}).map(task => task.id)")

            def family_is_together():
                return dev.evaluate(f"""(() => {{
                  const ids = [...list.children].map(row => Number(row.dataset.id));
                  const parentIndex = ids.indexOf({original[0]});
                  return JSON.stringify(ids.slice(parentIndex + 1, parentIndex + 3)) === JSON.stringify({json.dumps(children)});
                }})()""")

            # Complete/uncomplete parent and child; unrelated completed tasks cannot split them.
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {original[1]}))")
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {original[0]}))")
            assert family_is_together()
            evaluate_async("loadTasks()")
            assert family_is_together()
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {children[0]}))")
            assert family_is_together()
            evaluate_async(f"toggleStar(tasks.find(task => task.id === {children[0]}))")
            assert family_is_together()
            evaluate_async(f"toggleStar(tasks.find(task => task.id === {children[0]}))")
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {original[1]}))")
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {original[0]}))")
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {original[0]}))")
            assert family_is_together()
            # Reorder the parent as a block, persist it, then restore its saved position.
            for direction in ('down', 'up'):
                click(f'[data-id="{original[0]}"] [data-task-more]')
                click(f'[data-id="{original[0]}"] [data-move="{direction}"]')
                assert family_is_together()
                evaluate_async("saveOrder('Browser family test')")
                evaluate_async("loadTasks()")
                assert family_is_together()
            # The same drag path moves whole families and keeps child moves local.
            dev.evaluate(f"""draggedId = {original[0]};
              placeDraggedItem(list.querySelector('[data-id="{original[1]}"]'), Infinity);
              syncTasksFromDom(); draggedId = null; render();""")
            assert family_is_together()
            evaluate_async("saveOrder('Browser family drag test')")
            evaluate_async("loadTasks()")
            assert family_is_together()
            dev.evaluate(f"""draggedId = {original[0]};
              placeDraggedItem(list.querySelector('[data-id="{original[1]}"]'), -Infinity);
              syncTasksFromDom(); draggedId = null; render();""")
            evaluate_async("saveOrder('Restore browser family order')")

            for lang in ("en", "ar"):
                dev.evaluate(f"language = '{lang}'; applyLanguage()")
                for width, height in VIEWPORTS:
                    dev.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 600})
                    evaluate_async("setView('day')")
                    fits((lang, width, "day"))
                    click(".subtask-shortcut")
                    wait_for(lambda: dev.evaluate("subtaskDialog.open"))
                    assert dev.evaluate("document.activeElement === subtaskInput")
                    fits((lang, width, "subtask dialog"))
                    if width == 390:
                        screenshot(f"{lang}-subtask-dialog")
                    click("#subtask-done")
                    assert dev.evaluate("document.querySelector('.task-tools').getClientRects().length === 0")
                    click("[data-task-more]")
                    assert dev.evaluate("document.querySelector('[data-task-more]').getAttribute('aria-expanded') === 'true'"), dev.evaluate("(() => { const r = document.querySelector('[data-task-more]').getBoundingClientRect(); return {rect:r.toJSON(), hit:document.elementFromPoint(r.x+r.width/2, r.y+r.height/2)?.outerHTML}; })()")
                    assert dev.evaluate("[...document.querySelectorAll('.task-tools:not([hidden]) button')].every(el => el.getBoundingClientRect().height >= 44)")
                    fits((lang, width, "task tools"))
                    assert dev.evaluate("[...document.querySelectorAll('.task-tools:not([hidden]) button')].map(button => Object.keys(button.dataset)[0])") == [
                        'addSubtask', 'dayStar', 'edit', 'cancelTask', 'delete',
                        'label', 'makeRoutine', 'archive', 'transfer', 'outlist', 'enlist', 'move', 'move',
                    ]
                    if width == 390:
                        screenshot(f"{lang}-tasks")
                    click(".task:nth-child(2) [data-task-more]")
                    assert dev.evaluate("document.querySelectorAll('.task-tools:not([hidden])').length === 1 && document.querySelector('.task-tools').hidden")
                    click("[data-task-more]")
                    click(".task-tools:not([hidden]) [data-edit]")
                    wait_for(lambda: dev.evaluate("editDialog.open"))
                    fits((lang, width, "edit dialog"))
                    dev.evaluate("editDialog.close()")
                    dev.evaluate("document.querySelector('[data-task-more]').focus()")
                    dev.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape"})
                    assert dev.evaluate("document.querySelector('.task-tools').hidden")

                    evaluate_async("setView('lists')")
                    assert dev.evaluate("dayTitle.textContent === lt('lists')")
                    click("#lists-edit-toggle")
                    fits((lang, width, "lists editing"))
                    assert dev.evaluate("[...document.querySelectorAll('.checklist-items input')].every(el => el.getBoundingClientRect().height === 20)")
                    if width == 390:
                        screenshot(f"{lang}-lists")

                    evaluate_async("setView('routines')")
                    for frequency in ("daily", "weekly", "monthly", "yearly"):
                        dev.evaluate(f"routineFrequency.value = '{frequency}'; updateRoutineScheduleFields()")
                        fits((lang, width, frequency))
                        assert dev.evaluate("[...routineForm.querySelectorAll('[hidden]')].every(el => el.getClientRects().length === 0)")
                    evaluate_async("routineStats.hidden = false; loadRoutineStats()")
                    fits((lang, width, "routine statistics"))
                    dev.evaluate("routineStats.hidden = true")
                    if width == 390:
                        screenshot(f"{lang}-routines")
                    evaluate_async("setView('inbox')")
                    fits((lang, width, "inbox"))
                    for view in ("dreams", "history"):
                        evaluate_async(f"setInboxSubView('{view}')")
                        fits((lang, width, view))
                    evaluate_async("setView('day')")
                    click("#month-picker")
                    wait_for(lambda: dev.evaluate("monthDialog.open && !monthGrid.classList.contains('loading')"))
                    fits((lang, width, "month"))
                    dev.evaluate("monthDialog.close()")
                    print(f"PASS {lang} {width}x{height}: all pages, task tools, routine fields, calendar")

            dev.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            evaluate_async("setView('day')")
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {original[0]}))")
            assert family_is_together()
            dev.evaluate(f"window.scrollTo(0, list.querySelector('[data-id=\"{original[0]}\"]').getBoundingClientRect().top + scrollY - 70)")
            screenshot("ar-completed-family", scroll_top=False)

            # Archive a completed inbox task via the actual menu and verify the stored day.
            evaluate_async("setView('inbox')")
            archive_id = dev.evaluate("tasks[0].id")
            evaluate_async("toggleTask(tasks[0])")
            with app.connect() as db:
                db.execute("UPDATE tasks SET completed_at = '2026-09-23 22:00:00' WHERE id = ?", (archive_id,))
            evaluate_async("loadTasks()")
            click("[data-task-more]")
            dev.call("Emulation.setTimezoneOverride", {"timezoneId": "Asia/Riyadh"})
            click("[data-archive]")
            wait_for(lambda: dev.evaluate("tasks.length === 0 && document.querySelector('#task-notice').textContent.includes('2026-09-23')"))
            with app.connect() as db:
                archived = db.execute("SELECT location, task_date, completed_at FROM tasks WHERE id = ?", (archive_id,)).fetchone()
                assert tuple(archived) == ('day', '2026-09-23', '2026-09-23 22:00:00')

            # An API failure must be visible even when the task composer is hidden.
            evaluate_async("setView('lists')")
            dev.evaluate("window.originalFetch = window.fetch; window.fetch = () => Promise.reject(new Error('Test connection failure'))")
            evaluate_async("loadLists()")
            assert dev.evaluate("error.textContent.includes('Test connection failure') && error.getBoundingClientRect().height > 0")
            dev.evaluate("window.fetch = window.originalFetch; error.textContent = ''")
            click(".checklist-items input")
            wait_for(lambda: dev.evaluate("checklists[0].items[0].completed === 1"))
            # Collapse persistence and list ordering remain independent of item order.
            click(".checklist-collapse")
            evaluate_async("loadLists()")
            assert dev.evaluate("document.querySelector('.checklist-card').classList.contains('collapsed')")
            before = dev.evaluate("checklists.map(entry => ({id: entry.id, items: entry.items.map(item => item.id)}))")
            dev.evaluate("moveChecklist(0, 1)")
            evaluate_async("loadLists()")
            assert dev.evaluate("checklists.map(entry => ({id: entry.id, items: entry.items.map(item => item.id)}))") == before[::-1]
            assert dev.evaluate("window.uiErrors") == [], dev.evaluate("window.uiErrors")
            # Work mode and visible install control must fit together on a small screen.
            dev.call("Emulation.setDeviceMetricsOverride", {"width": 320, "height": 568, "deviceScaleFactor": 1, "mobile": True})
            click("#workspace-toggle")
            wait_for(lambda: dev.evaluate("workspace === 'work'"))
            dev.evaluate("installApp.hidden = false")
            fits("work header with install button")
            # Theme behavior and surfaces use the real browser and isolated data above.
            dev.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark"}]})
            wait_for(lambda: dev.evaluate("document.documentElement.dataset.theme === 'dark'"))
            assert dev.evaluate("getComputedStyle(document.body).backgroundColor") == 'rgb(20, 27, 36)'
            # Keyboard toggle is a native accessible button, and manual choice wins over OS.
            dev.evaluate("document.querySelector('#theme-toggle').focus()")
            assert dev.evaluate('document.activeElement.id') == 'theme-toggle'
            dev.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"})
            dev.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            wait_for(lambda: dev.evaluate("TasklineStorage.getItem('taskline-theme') === 'light'"))
            click("#theme-toggle")
            dev.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]})
            assert dev.evaluate("document.documentElement.dataset.theme") == 'dark'
            dev.call("Page.reload")
            wait_for(lambda: dev.evaluate("document.readyState === 'complete' && window.tasklineReady === true && typeof TasklineTheme === 'object' && document.querySelector('#theme-toggle').getAttribute('aria-pressed') === 'true'"))
            assert dev.evaluate("document.documentElement.dataset.theme") == 'dark'

            def dark_surfaces(context):
                bright = dev.evaluate("""(() => {
                  const selectors = 'input:not([type=checkbox]):not([type=radio]), select, textarea, .task, .checklist-card, .routine-form, .routine-card, .routine-stats, .dream-card, .history-group, dialog[open], .app-header, .bottom-nav, .overdue-section, .app-error';
                  return [...document.querySelectorAll(selectors)].filter(el => {
                    if (!el.getClientRects().length) return false;
                    const channels = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g).map(Number);
                    return channels.slice(0, 3).every(value => value > 120) && channels[3] !== 0;
                  }).map(el => el.id || el.className);
                })()""")
                assert not bright, (context, 'unexpected light surfaces', bright)

            for space in ('personal', 'work'):
                dev.evaluate(f"workspace = '{space}'; TasklineStorage.setItem('taskline-workspace', workspace); applyWorkspace()")
                expected = 'rgb(17, 26, 24)' if space == 'personal' else 'rgb(20, 27, 36)'
                assert dev.evaluate("getComputedStyle(document.body).backgroundColor") == expected
                assert dev.evaluate("document.querySelector('meta[name=theme-color]').content") == ('#111a18' if space == 'personal' else '#141b24')
                for lang in ('en', 'ar'):
                    dev.evaluate(f"language = '{lang}'; applyLanguage()")
                    assert dev.evaluate("document.querySelector('#theme-toggle').getAttribute('aria-label')") == ('الوضع الداكن' if lang == 'ar' else 'Dark mode')
                    for width, height in VIEWPORTS:
                        dev.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 600})
                        dev.evaluate("installApp.hidden = false")
                        for view in ('day', 'lists', 'routines', 'inbox'):
                            evaluate_async(f"setView('{view}')")
                            if view == 'day':
                                click('[data-task-more]')
                            if view == 'routines':
                                evaluate_async("routineStats.hidden = false; loadRoutineStats()")
                                # Canvas colors refresh immediately when switching themes.
                                dark_color = dev.evaluate("routineChart.getContext('2d').strokeStyle")
                                dev.evaluate("TasklineTheme.toggle()")
                                assert dev.evaluate("routineChart.getContext('2d').strokeStyle") != dark_color
                                dev.evaluate("TasklineTheme.toggle()")
                                assert dev.evaluate("routineChart.getContext('2d').strokeStyle") == dark_color
                            context = (space, lang, width, view, 'dark')
                            fits(context)
                            dark_surfaces(context)
                            if width == 390 or (width == 1440 and view == 'day'):
                                screenshot(f'dark-{space}-{lang}-{width}-{view}')
                        for view in ('dreams', 'history'):
                            evaluate_async(f"setInboxSubView('{view}')")
                            fits((space, lang, width, view))
                            dark_surfaces((space, lang, width, view))
                        evaluate_async("setView('day')")
                        click('#month-picker')
                        wait_for(lambda: dev.evaluate("monthDialog.open && !monthGrid.classList.contains('loading')"))
                        dark_surfaces('month')
                        fits('dark month')
                        if width == 390:
                            screenshot(f'dark-{space}-{lang}-calendar')
                        dev.evaluate('monthDialog.close()')
                        if width in (320, 390):
                            for dialog_id in ('label-dialog', 'edit-dialog', 'subtask-dialog', 'dream-dialog', 'install-dialog'):
                                dev.evaluate(f"document.getElementById('{dialog_id}').showModal()")
                                dark_surfaces(dialog_id)
                                fits((space, lang, width, dialog_id))
                                if width == 390:
                                    screenshot(f'dark-{space}-{lang}-{dialog_id}')
                                dev.evaluate(f"document.getElementById('{dialog_id}').close()")
                        print(f'PASS dark {space} {lang} {width}x{height}: pages, surfaces, dialogs, chart')
            # Both workspace light palettes remain intact after toggling back.
            click('#theme-toggle')
            for space, expected in (('personal', 'rgb(245, 243, 237)'), ('work', 'rgb(242, 244, 246)')):
                dev.evaluate(f"workspace = '{space}'; applyWorkspace()")
                assert dev.evaluate('getComputedStyle(document.body).backgroundColor') == expected
            assert dev.evaluate('window.uiErrors') == [], dev.evaluate('window.uiErrors')
            runpy.run_path(str(ROOT / 'tests/settings-browser-checks.py'))['check_settings'](
                dev, evaluate_async, click, fits, screenshot, wait_for, app, VIEWPORTS)
            runpy.run_path(str(ROOT / 'tests/overdue-browser-checks.py'))['check_overdue'](
                dev, evaluate_async, click, fits, screenshot, wait_for, app, VIEWPORTS)
            runpy.run_path(str(ROOT / 'tests/calendar-routine-browser-checks.py'))['check_calendar_routines'](
                dev, evaluate_async, click, fits, screenshot, wait_for, app, VIEWPORTS)
            runpy.run_path(str(ROOT / 'tests/cancellation-browser-checks.py'))['check_cancellation'](
                dev, evaluate_async, click, fits, screenshot, wait_for, app, VIEWPORTS)
            runpy.run_path(str(ROOT / 'tests/completion-order-browser-checks.py'))['check_completion_order'](
                dev, evaluate_async, click, fits, screenshot, wait_for, app, VIEWPORTS)
            dev.evaluate("workspace = 'personal'; applyWorkspace()")
            evaluate_async("setView('routines')")
            request('/api/routines', {'title': 'Second ordering routine', 'start_date': '2030-01-01', 'frequency': 'daily'})
            evaluate_async('loadRoutines()')
            before = dev.evaluate('routines.map(r => r.id)')
            after = [before[1], before[0], *before[2:]]
            click('.routine-card:first-child [data-routine-down]')
            wait_for(lambda: dev.evaluate('routines.map(r => r.id)') == after)
            evaluate_async('loadRoutines()')
            assert dev.evaluate('routines.map(r => r.id)') == after
            assert dev.evaluate("document.querySelector('.routine-card:first-child [data-routine-up]').disabled")
            click('.routine-card:nth-child(2) [data-routine-up]')
            wait_for(lambda: dev.evaluate('routines.map(r => r.id)') == before)
            fits(('routine reordering', 320))
            print('PASS routine reorder: up, down, disabled boundaries, persisted reload')
            runpy.run_path(str(ROOT / 'tests/routine-drag-browser-checks.py'))['check_routine_drag'](
                dev, evaluate_async, click, fits, wait_for)
            socket.close()
            print("PASS: ordering, keyboard, error visibility, list persistence, work header; isolated DB only")
        finally:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=5)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
