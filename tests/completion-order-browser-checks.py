"""Successful tasks precede cancelled families in day, Inbox, and planned history."""
def check_completion_order(dev, evaluate_async, click, fits, screenshot, wait_for, app, viewports):
    for space in ('personal', 'work'):
        dev.evaluate(f"workspace = '{space}'; today = effectiveToday(); currentDate = today; applyWorkspace()")
        for location in ('day', 'inbox'):
            evaluate_async(f"setView('{location}')")
            def create(title, parent=None):
                return evaluate_async(f"api('/api/tasks', {{method:'POST', body:JSON.stringify({{title:'{title}', task_date:today, location:'{location}', parent_id:{parent or 'null'}, planning_kind:'date', planning_value:today}})}})")['id']
            cancelled = create('Sort cancelled parent')
            child = create('Sort completed child', cancelled)
            success = create('Sort successful parent')
            pending = create('Sort unfinished task')
            for task_id, payload in ((cancelled, '{cancelled:true}'), (child, '{completed:true}'), (success, '{completed:true}')):
                evaluate_async(f"api('/api/tasks/{task_id}', {{method:'PUT', body:JSON.stringify({payload})}})")
            evaluate_async('loadTasks()')
            tracked = [cancelled, child, success, pending]
            def displayed():
                return dev.evaluate(f"[...list.children].map(row => Number(row.dataset.id)).filter(id => {tracked}.includes(id))")
            def positions():
                with app.connect() as db:
                    return [tuple(row) for row in db.execute('SELECT id, position FROM tasks WHERE id IN (?,?,?,?) ORDER BY id', tracked)]
            original = positions()
            assert displayed() == [pending, success, cancelled, child]
            for lang in ('ar', 'en'):
                dev.evaluate(f"language = '{lang}'; applyLanguage()")
                for width, height in viewports:
                    dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width <= 600})
                    assert displayed() == [pending, success, cancelled, child]
                    fits(('completion order', space, location, lang, width))
            # Actual one-click conversion moves the family above later successes.
            click(f'[data-id="{cancelled}"] [data-task-more]')
            click(f'[data-id="{cancelled}"] [data-cancel-task]')
            wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {cancelled}).cancelled === 0"))
            assert displayed() == [pending, cancelled, child, success]
            assert positions() == original
            # Restore cancellation, reload, then confirm the same order persists.
            evaluate_async(f"toggleTask(tasks.find(task => task.id === {cancelled}), true)")
            evaluate_async('loadTasks()')
            assert displayed() == [pending, success, cancelled, child]
            assert positions() == original
            evaluate_async("setView('inbox')")
            evaluate_async("setInboxSubView('history')")
            history = dev.evaluate("[...document.querySelectorAll('#done-list .history-group p')].map(row => row.textContent)")
            success_index = next(i for i, text in enumerate(history) if text.endswith('Sort successful parent'))
            cancelled_index = next(i for i, text in enumerate(history) if text.endswith('Sort cancelled parent'))
            assert success_index < cancelled_index
            evaluate_async("setInboxSubView('inbox')")
            # Only temporary test fixtures are removed; production DB is never used.
            for task_id in (child, cancelled, success, pending):
                evaluate_async(f"api('/api/tasks/{task_id}', {{method:'DELETE'}})")
            print(f'PASS completion order {space}/{location}: pending, success, cancellation; family, conversion, saved positions, history, languages and sizes')
