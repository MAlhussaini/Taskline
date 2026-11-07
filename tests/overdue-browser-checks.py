"""Real overdue controls and responsive layout; called by the isolated UI suite."""
import json


def check_overdue(dev, evaluate_async, click, fits, screenshot, wait_for, app, viewports):
    for space in ('personal', 'work'):
        dev.evaluate(f"workspace = '{space}'; today = effectiveToday(); currentDate = today; applyWorkspace()")
        evaluate_async("setView('day')")
        old_day = dev.evaluate('shifted(today, -2)')
        parent = evaluate_async(f"api('/api/tasks', {{method:'POST', body:JSON.stringify({{title:'مهمة تم إنجازها في موعدها ولكن نسيت تسجيل الإنجاز في التطبيق', task_date:'{old_day}'}})}})")
        child = evaluate_async(f"api('/api/tasks', {{method:'POST', body:JSON.stringify({{title:'خطوة فرعية', parent_id:{parent['id']}, task_date:'{old_day}'}})}})")
        routine = evaluate_async(f"api('/api/routines', {{method:'POST', body:JSON.stringify({{title:'روتين متأخر مع اسم طويل لاختبار وضوح أدوات الإنجاز والنقل والتجاهل', frequency:'daily', start_date:'{old_day}', follow_until_complete:true}})}})")
        evaluate_async('loadOverdue()')
        with app.connect() as db:
            routine_task = db.execute('SELECT task_id FROM routine_occurrences WHERE routine_id = ? AND scheduled_date = ?', (routine['id'], old_day)).fetchone()[0]
        for lang in ('ar', 'en'):
            dev.evaluate(f"language = '{lang}'; applyLanguage()")
            evaluate_async('loadOverdue()')
            for theme in ('light', 'dark'):
                dev.evaluate(f"TasklineTheme.setPreference('{theme}')")
                for width, height in viewports:
                    dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width <= 600})
                    fits(('overdue completion', space, lang, theme, width))
                    assert dev.evaluate("[...overdueList.querySelectorAll('button')].every(el => el.getBoundingClientRect().height >= 44)")
                    assert dev.evaluate("overdueList.querySelector('.routine-overdue') === null")
                    if width == 390:
                        dev.evaluate("overdueSection.scrollIntoView({block:'start'}); window.scrollBy(0, -70)")
                        screenshot(f'overdue-{space}-{lang}-{theme}', scroll_top=False)
                # Hidden Inbox also fits with three actions for ordinary tasks.
                dev.evaluate("document.documentElement.classList.add('without-inbox')")
                dev.call('Emulation.setDeviceMetricsOverride', {'width': 320, 'height': 568, 'deviceScaleFactor': 1, 'mobile': True})
                fits('overdue with Inbox hidden')
                dev.evaluate("document.documentElement.classList.remove('without-inbox')")

        dev.call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        selector = f'[data-overdue-action="complete"][data-task-id="{parent["id"]}"]'
        # A failed write is recoverable and must not mark the task complete locally.
        dev.evaluate("window.overdueFetch = fetch; window.fetch = (url, options) => String(url).includes('overdue-action') ? Promise.reject(new Error('Test completion failure')) : overdueFetch(url, options)")
        click(selector)
        wait_for(lambda: dev.evaluate("error.textContent.includes('Test completion failure')"))
        assert dev.evaluate(f"!document.querySelector({json.dumps(selector)}).disabled")
        with app.connect() as db:
            assert db.execute('SELECT completed FROM tasks WHERE id = ?', (parent['id'],)).fetchone()[0] == 0
        dev.evaluate('window.fetch = window.overdueFetch')
        click(selector + ' span')
        wait_for(lambda: dev.evaluate(f"!overdueList.querySelector({json.dumps(selector)}) && document.querySelector('#task-notice').textContent.includes('{old_day}')"))
        with app.connect() as db:
            for task_id in (parent['id'], child['id']):
                row = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
                assert row['completed'] == 1 and row['task_date'] == old_day
                assert app.completion_day(row['completed_at'], space, 'Asia/Riyadh') == old_day

        # Missed routines now live as completed X entries in their original day.
        evaluate_async(f"selectDate('{old_day}')")
        routine_row = f'[data-id="{routine_task}"]'
        routine_selector = routine_row + ' [data-cancel-task]'
        for lang in ('ar', 'en'):
            dev.evaluate(f"language = '{lang}'; applyLanguage()")
            for theme in ('light', 'dark'):
                dev.evaluate(f"TasklineTheme.setPreference('{theme}')")
                assert dev.evaluate(f"document.querySelector('{routine_row} [data-check]').textContent.includes('❌') && document.querySelector('{routine_row}').classList.contains('completed')")
                assert dev.evaluate(f"document.querySelector('{routine_row} .missed-badge').textContent.trim()") == ('○ فائتة' if lang == 'ar' else '○ Missed')
                for width, height in viewports:
                    dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width <= 600})
                    fits(('missed routine badge', space, lang, theme, width))
                    if width == 390:
                        dev.evaluate(f"document.querySelector('{routine_row}').scrollIntoView({{block:'center'}})")
                        screenshot(f'missed-routine-{space}-{lang}-{theme}', scroll_top=False)
        click(routine_row + ' [data-task-more]')
        dev.evaluate("""window.overdueRequests = 0; window.fetch = (url, options) => {
          if (options?.method !== 'PUT') return overdueFetch(url, options);
          overdueRequests++;
          return new Promise(resolve => { window.releaseOverdue = () => resolve(overdueFetch(url, options)); });
        };""")
        click(routine_selector)
        assert dev.evaluate(f"document.querySelector({json.dumps(routine_selector)}).disabled")
        dev.evaluate(f"document.querySelector({json.dumps(routine_selector)}).click()")
        assert dev.evaluate('overdueRequests') == 1
        dev.evaluate('releaseOverdue(); window.fetch = window.overdueFetch')
        wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {routine_task})?.routine_missed === 0 && !document.querySelector('{routine_row} .missed-badge') && completedDays.has('{old_day}')"))
        assert dev.evaluate(f"document.querySelector('{routine_row} [data-check]').textContent.trim() === '✓'")
        evaluate_async('loadTasks()')
        assert dev.evaluate(f"!document.querySelector('{routine_row} .missed-badge')")
        assert dev.evaluate('window.uiErrors') == [], dev.evaluate('window.uiErrors')
        print(f'PASS overdue {space}: original-day completion, family, calendar, retries, pending controls, both themes/languages and five sizes')
