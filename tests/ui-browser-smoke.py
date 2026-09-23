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
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[1]
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
            dev.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.uiErrors = [];
              addEventListener('error', e => uiErrors.push(e.message));
              addEventListener('unhandledrejection', e => uiErrors.push(String(e.reason)));
            """})
            dev.call("Page.navigate", {"url": origin})
            wait_for(lambda: dev.evaluate("document.readyState === 'complete' && typeof today === 'string'"))
            assert dev.evaluate("document.activeElement.id !== 'task-input'")
            date = dev.evaluate("today")

            def request(path, payload, workspace="personal"):
                req = urllib.request.Request(
                    f"{origin}{path}?workspace={workspace}",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"}, method="POST",
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

            def click(selector):
                point = evaluate_async(f"""(async () => {{
                  const el = document.querySelector({json.dumps(selector)});
                  el.scrollIntoView({{block: 'center'}});
                  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                  const r = el.getBoundingClientRect();
                  return {{x: r.x + r.width / 2 - visualViewport.offsetLeft,
                    y: r.y + r.height / 2 - visualViewport.offsetTop}};
                }})()""")
                for kind in ("mousePressed", "mouseReleased"):
                    dev.call("Input.dispatchMouseEvent", {"type": kind, **point, "button": "left", "clickCount": 1})

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

            def screenshot(name):
                if args.screenshots:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    dev.evaluate("window.scrollTo(0, 0)")
                    result = dev.call("Page.captureScreenshot", {"format": "png"})
                    (args.screenshots / f"{name}.png").write_bytes(base64.b64decode(result["data"]))

            evaluate_async("loadTasks()")
            # Normal -> starred -> normal and completed -> incomplete restore the order.
            original = dev.evaluate("tasks.map(task => task.id)")
            evaluate_async("toggleStar(tasks[1])")
            assert dev.evaluate("Number(list.firstElementChild.dataset.id)") == original[1]
            evaluate_async("toggleStar(tasks.find(task => task.id === " + str(original[1]) + "), 2)")
            assert dev.evaluate("[...list.children].map(row => Number(row.dataset.id))") == original
            evaluate_async("toggleTask(tasks[0])")
            assert dev.evaluate("Number(list.lastElementChild.dataset.id)") == original[0]
            evaluate_async("toggleTask(tasks.find(task => task.id === " + str(original[0]) + "))")
            assert dev.evaluate("[...list.children].map(row => Number(row.dataset.id))") == original

            # Two quick real clicks must persist red, not get lost during re-render.
            first_star = f'[data-id="{original[0]}"] [data-star]'
            click(first_star)
            click(first_star)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 2"))
            assert dev.evaluate("document.querySelector('.day-star-badge') !== null")
            assert dev.evaluate(f"getComputedStyle(document.querySelector({json.dumps(first_star)})).color === 'rgb(199, 53, 53)'")
            click(first_star)
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 0"))
            click(first_star)
            # Completing while the star click is still pending must flush it first.
            click(f'[data-id="{original[0]}"] [data-check]')
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).completed === 1"))
            assert dev.evaluate(f"document.querySelector({json.dumps(first_star)}).disabled && !document.querySelector({json.dumps(first_star)}).classList.contains('starred')")
            click(f'[data-id="{original[0]}"] [data-check]')
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {original[0]}).completed === 0"))
            assert dev.evaluate(f"tasks.find(task => task.id === {original[0]}).starred === 1")
            evaluate_async(f"toggleStar(tasks.find(task => task.id === {original[0]}), 2)")

            # Add consecutive subtasks without native prompts or losing input focus.
            click(".subtask-shortcut")
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
            assert dev.evaluate("document.querySelectorAll('.subtask-context').length === 2")

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
