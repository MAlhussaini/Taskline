"""Settings checks invoked by ui-browser-smoke.py, using its isolated server."""
import json


def check_settings(dev, evaluate_async, click, fits, screenshot, wait_for, app, viewports):
    def centered():
        assert dev.evaluate("""(() => {
          const nav = document.querySelector('.bottom-nav').getBoundingClientRect();
          const day = document.querySelector('#nav-today').getBoundingClientRect();
          return Math.abs(day.x + day.width / 2 - nav.x - nav.width / 2) < 1;
        })()"""), 'Today must remain geometrically centered'

    def change(selector, value):
        dev.evaluate(f"""(() => {{ const el = document.querySelector({json.dumps(selector)});
          el.value = {json.dumps(value)}; el.dispatchEvent(new Event('change', {{bubbles:true}})); }})()""")
        wait_for(lambda: dev.evaluate("!document.querySelector('.settings-shared').disabled"))

    def snapshot():
        with app.connect() as db:
            return {table: [tuple(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY id')]
                    for table in ('tasks', 'routines', 'routine_steps', 'dreams', 'dream_items', 'checklists', 'checklist_items')}

    evaluate_async("TasklineSettings.go('settings')")
    assert dev.evaluate("currentView") == 'settings'
    assert dev.evaluate("document.querySelectorAll('[data-feature]').length") == 24
    defaults = dev.evaluate('JSON.parse(JSON.stringify(TasklineSettings.values))')
    for space in ('personal', 'work'):
        dev.evaluate(f"workspace = '{space}'; applyWorkspace()")
        for theme in ('light', 'dark'):
            dev.evaluate(f"TasklineTheme.setPreference('{theme}')")
            for lang in ('en', 'ar'):
                dev.evaluate(f"language = '{lang}'; applyLanguage()")
                for width, height in viewports:
                    dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width <= 600})
                    dev.evaluate("document.querySelectorAll('.settings-group').forEach(el => el.open = true); installApp.hidden = false")
                    fits(('settings', space, theme, lang, width))
                    centered()
                    assert dev.evaluate("[...document.querySelectorAll('.setting-switch input')].every(el => el.offsetWidth >= 44)")
                    if width in (390, 1440):
                        screenshot(f'settings-{space}-{theme}-{lang}-{width}')
                print(f'PASS settings {space} {theme} {lang}: five viewport sizes')

    dev.call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
    dev.evaluate("document.querySelector('.settings-group[data-group=tasks]').scrollIntoView({block:'start'})")
    screenshot('settings-task-switches', scroll_top=False)
    dev.evaluate("document.querySelector('.footer-preview').scrollIntoView({block:'center'})")
    screenshot('settings-footer-editor', scroll_top=False)
    # Every individual switch saves and restores via actual UI controls.
    before = snapshot()
    for key in defaults['features']:
        dev.evaluate("document.querySelectorAll('.settings-group').forEach(el => el.open = true)")
        click(f'#feature-{key}')
        wait_for(lambda: dev.evaluate(f"TasklineSettings.values.features.{key} === false && !document.querySelector('.settings-shared').disabled"))
        assert dev.evaluate(f"document.documentElement.classList.contains('without-{key}')")
        click(f'#feature-{key}')
        wait_for(lambda: dev.evaluate(f"TasklineSettings.values.features.{key} === true && !document.querySelector('.settings-shared').disabled"))
    assert snapshot() == before, 'Feature switches must not alter task/routine/list data'

    # Dependencies preserve independent child preferences, without silently enabling them.
    evaluate_async("TasklineSettings.save({features:{stars:false, taskOfDay:false}})")
    assert dev.evaluate("document.querySelector('#feature-taskOfDay').disabled && document.querySelector('#feature-prioritySort').disabled")
    evaluate_async("TasklineSettings.save({features:{stars:true}})")
    assert dev.evaluate("!TasklineSettings.enabled('taskOfDay') && TasklineSettings.enabled('prioritySort')")
    evaluate_async("TasklineSettings.save({features:{taskOfDay:true}})")

    # Footer swaps, empty slots and direct access to destinations outside the footer.
    change('#footer-slot-0', 'lists')
    assert dev.evaluate('TasklineSettings.values.footer') == ['lists', 'inbox', 'day', 'routines', 'settings']
    for slot in (0, 1, 3, 4):
        change(f'#footer-slot-{slot}', 'none')
        centered()
    assert dev.evaluate("[...document.querySelectorAll('.bottom-nav button')].filter(el => !el.hidden).map(el => el.id)") == ['nav-today']
    click('#nav-today')
    wait_for(lambda: dev.evaluate("currentView === 'day'"))
    click('#settings-open')
    wait_for(lambda: dev.evaluate("currentView === 'settings'"))
    click('[data-settings-go="lists"]')
    wait_for(lambda: dev.evaluate("currentView === 'lists'"))
    click('#settings-open')
    wait_for(lambda: dev.evaluate("currentView === 'settings'"))
    change('#footer-slot-0', 'dreams')
    change('#footer-slot-4', 'planned')
    click('#nav-dreams')
    wait_for(lambda: dev.evaluate("currentView === 'inbox' && inboxSubView === 'dreams'"))
    assert dev.evaluate("document.querySelector('#nav-dreams').getAttribute('aria-current')") == 'page'
    click('#nav-planned')
    wait_for(lambda: dev.evaluate("inboxSubView === 'history'"))
    centered()
    click('#settings-open')
    wait_for(lambda: dev.evaluate("currentView === 'settings'"))

    change('#settings-day-personal', '04:30')
    change('#settings-day-work', '01:00')
    assert dev.evaluate("effectiveToday(new Date(2026, 9, 11, 4, 29), 'personal')") == '2026-10-10'
    assert dev.evaluate("effectiveToday(new Date(2026, 9, 11, 4, 30), 'personal')") == '2026-10-11'
    assert dev.evaluate("effectiveToday(new Date(2026, 9, 11, 0, 59), 'work')") == '2026-10-10'
    assert dev.evaluate("effectiveToday(new Date(2026, 9, 11, 1, 0), 'work')") == '2026-10-11'

    # Persist across a reload and receive changes made by another device on focus.
    dev.call('Page.reload')
    wait_for(lambda: dev.evaluate('window.tasklineReady === true'))
    assert dev.evaluate('TasklineSettings.values.dayStart') == {'personal': 270, 'work': 60}
    assert dev.evaluate('TasklineSettings.values.footer') == ['dreams', 'none', 'day', 'none', 'planned']
    evaluate_async("api('/api/settings', {method:'PUT', body:JSON.stringify({features:{lists:false}})})")
    dev.evaluate("dispatchEvent(new Event('focus'))")
    wait_for(lambda: dev.evaluate("!TasklineSettings.enabled('lists')"))
    evaluate_async("setView('lists')")
    assert dev.evaluate('currentView') == 'day'
    evaluate_async("TasklineSettings.go('settings')")

    # Failed writes keep previous server/local state and give a visible error.
    dev.evaluate("window.settingsOriginalFetch = fetch; window.fetch = (url, options) => options?.method === 'PUT' ? Promise.reject(new Error('offline')) : settingsOriginalFetch(url, options)")
    evaluate_async("TasklineSettings.save({features:{stars:false}})")
    assert dev.evaluate("TasklineSettings.enabled('stars') && document.querySelector('#settings-status').getAttribute('role') === 'alert'")
    dev.evaluate('window.fetch = window.settingsOriginalFetch')

    # Everything optional off still leaves a useful daily task list and Settings.
    evaluate_async("TasklineSettings.save({features:Object.fromEntries(Object.keys(TasklineSettings.values.features).map(key=>[key,false]))})")
    assert dev.evaluate("workspace") == 'personal'
    evaluate_async("setView('day')")
    with app.connect() as db:
        populated_date = db.execute("SELECT task_date FROM tasks WHERE workspace = 'personal' AND location = 'day' ORDER BY id LIMIT 1").fetchone()[0]
    evaluate_async(f'selectDate({json.dumps(populated_date)})')
    assert dev.evaluate('tasks.length > 0')
    assert dev.evaluate("[...document.querySelectorAll('[data-star], .grip, [data-add-subtask]')].every(el => el.getClientRects().length === 0)")
    assert dev.evaluate("document.querySelector('#simple-date').getClientRects().length > 0")
    assert dev.evaluate("document.querySelectorAll('.day-chip.has-tasks').length === 0")
    assert dev.evaluate("list.querySelectorAll('.task').length === tasks.length")
    assert dev.evaluate("[...list.children].every(row => !row.draggable)")
    click('[data-task-more]')
    assert dev.evaluate("[...document.querySelectorAll('.task-tools:not([hidden]) button')].filter(el => el.getClientRects().length).map(el => Object.keys(el.dataset)[0])") == ['edit', 'cancelTask', 'delete']
    fits('all optional features off')
    centered()
    screenshot('settings-minimal-daily-list')
    click('#settings-open')
    wait_for(lambda: dev.evaluate("currentView === 'settings'"))
    evaluate_async(f'TasklineSettings.save({json.dumps(defaults)})')
    assert dev.evaluate("TasklineSettings.catalog.every(f => TasklineSettings.enabled(f.id))")
    assert dev.evaluate('window.uiErrors') == [], dev.evaluate('window.uiErrors')
    print('PASS settings: 24 switches, data preservation, dependencies, footer invariants, persistence, day boundaries, errors, minimal mode')
