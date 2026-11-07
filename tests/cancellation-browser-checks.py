"""Real cancellation controls, persistence, recovery and responsive paired actions."""
def check_cancellation(dev, evaluate_async, click, fits, screenshot, wait_for, app, viewports):
    for space in ('personal', 'work'):
        dev.evaluate(f"workspace = '{space}'; today = effectiveToday(); currentDate = today; applyWorkspace()")
        evaluate_async("setView('day')")
        task = evaluate_async("api('/api/tasks', {method:'POST', body:JSON.stringify({title:'اختبار الإلغاء مع الاحتفاظ بالمهمة ضمن المكتملة', task_date:today})})")
        task_id = task['id']
        row = f'[data-id="{task_id}"]'
        more, cancel, check = row + ' [data-task-more]', row + ' [data-cancel-task]', row + ' [data-check]'
        evaluate_async('loadTasks()')
        for lang in ('ar', 'en'):
            dev.evaluate(f"language = '{lang}'; applyLanguage()")
            for theme in ('light', 'dark'):
                dev.evaluate(f"TasklineTheme.setPreference('{theme}')")
                for width, height in viewports:
                    dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width <= 600})
                    evaluate_async('loadTasks()')
                    click(more)
                    geometry = dev.evaluate(f"""(() => {{
                      const group = document.querySelector('{row} .task-disposition');
                      const buttons = [...group.querySelectorAll('button')];
                      const rects = buttons.map(button => button.getBoundingClientRect());
                      return {{count:buttons.length, touch:rects.every(r => r.width >= 44 && r.height >= 44), sameRow:rects[0].y === rects[1].y,
                        captions:buttons.every(button => getComputedStyle(button.querySelector('.action-caption')).display !== 'none'),
                        accessible:buttons.every(button => button.getAttribute('aria-label'))}};
                    }})()""")
                    assert geometry['count'] == 2 and geometry['touch'] and geometry['sameRow'] and geometry['accessible'], geometry
                    assert geometry['captions'] == (width > 600), (width, geometry)
                    rows = dev.evaluate(f"""(() => {{
                      const task = document.querySelector('{row}');
                      const rect = selector => task.querySelector(selector).getBoundingClientRect();
                      const first = rect('[data-add-subtask]'), dayStar = rect('[data-day-star]');
                      const edit = rect('[data-edit]'), cancel = rect('[data-cancel-task]'), remove = rect('[data-delete]');
                      return {{firstRow:first.y === dayStar.y, secondRow:edit.y === cancel.y && cancel.y === remove.y && edit.y > first.y,
                        order:document.documentElement.dir === 'rtl' ? edit.x > cancel.x && cancel.x > remove.x : edit.x < cancel.x && cancel.x < remove.x,
                        restBelow:rect('[data-label]').y > edit.y}};
                    }})()""")
                    assert all(rows.values()), (space, lang, width, rows)
                    fits(('paired cancel/delete', space, lang, theme, width))
                    if width == 390:
                        screenshot(f'cancel-pair-{space}-{lang}-{theme}', scroll_top=False)

        # A failed write restores the ordinary incomplete task and offers retry.
        dev.evaluate("window.cancellationFetch = fetch; window.fetch = (url, options) => options?.method === 'PUT' ? Promise.reject(new Error('Cancellation test failure')) : cancellationFetch(url, options)")
        click(cancel)
        wait_for(lambda: dev.evaluate("error.textContent.includes('Cancellation test failure')"))
        assert dev.evaluate(f"!tasks.find(task => task.id === {task_id}).completed && !tasks.find(task => task.id === {task_id}).cancelled")
        dev.evaluate('window.fetch = window.cancellationFetch')
        click(more)
        click(cancel)
        wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {task_id}).cancelled === 1"))
        assert dev.evaluate(f"document.querySelector('{check}').textContent.includes('❌') && document.querySelector('{row}').classList.contains('completed')")
        with app.connect() as db:
            stored = db.execute('SELECT completed, cancelled FROM tasks WHERE id = ?', (task_id,)).fetchone()
            assert tuple(stored) == (1, 1)
        # Persist the space before a real page reload.
        dev.evaluate("TasklineStorage.setItem('taskline-workspace', workspace)")
        dev.call('Page.reload')
        wait_for(lambda: dev.evaluate(f"window.tasklineReady === true && document.querySelector('{check}')?.textContent.includes('❌')"))
        for lang in ('ar', 'en'):
            dev.evaluate(f"language = '{lang}'; applyLanguage()")
            for theme in ('light', 'dark'):
                dev.evaluate(f"TasklineTheme.setPreference('{theme}')")
                evaluate_async('loadTasks()')
                click(more)
                assert dev.evaluate(f"!document.querySelector('{cancel}').disabled && document.querySelector('{cancel}').textContent.includes('✅')")
                assert dev.evaluate(f"document.querySelector('{cancel} .action-caption').textContent") == ('إكمال' if lang == 'ar' else 'Complete')
                assert dev.evaluate(f"getComputedStyle(document.querySelector('{cancel}')).backgroundColor === getComputedStyle(document.querySelector('{row} [data-edit]')).backgroundColor")
                fits(('cancelled-to-complete shortcut', space, lang, theme))
                dev.evaluate(f"document.querySelector('{cancel}').scrollIntoView({{block:'center'}})")
                screenshot(f'complete-shortcut-{space}-{lang}-{theme}', scroll_top=False)
        # A failed conversion preserves the cancellation; retry sends ONE PUT
        # with completed:true, without an intermediate reopen or timestamp reset.
        dev.evaluate("window.cancellationFetch = fetch; window.fetch = (url, options) => options?.method === 'PUT' ? Promise.reject(new Error('Conversion test failure')) : cancellationFetch(url, options)")
        click(cancel)
        wait_for(lambda: dev.evaluate("error.textContent.includes('Conversion test failure')"))
        assert dev.evaluate(f"tasks.find(task => task.id === {task_id}).completed && tasks.find(task => task.id === {task_id}).cancelled")
        dev.evaluate('window.fetch = window.cancellationFetch')
        with app.connect() as db:
            before_conversion = tuple(db.execute('SELECT completed, cancelled, completed_at, position, task_date FROM tasks WHERE id = ?', (task_id,)).fetchone())
        dev.evaluate("""window.conversionRequests = []; window.fetch = (url, options) => {
          if (options?.method !== 'PUT') return cancellationFetch(url, options);
          conversionRequests.push(JSON.parse(options.body));
          return new Promise(resolve => { window.releaseConversion = () => resolve(cancellationFetch(url, options)); });
        };""")
        click(more)
        click(cancel)
        wait_for(lambda: dev.evaluate('conversionRequests.length === 1'))
        assert dev.evaluate('conversionRequests') == [{'completed': True, 'cancelled': False}]
        assert dev.evaluate(f"document.querySelector('{row}').classList.contains('completed') && document.querySelector('{check}').textContent.trim() === '✓'")
        assert dev.evaluate(f"document.querySelector('{check}').disabled && document.querySelector('{cancel}').disabled")
        dev.evaluate(f"document.querySelector('{cancel}').click(); document.querySelector('{check}').click()")
        assert dev.evaluate('conversionRequests.length') == 1
        dev.evaluate('releaseConversion(); window.fetch = window.cancellationFetch')
        wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {task_id}).cancelled === 0"))
        with app.connect() as db:
            after_conversion = tuple(db.execute('SELECT completed, cancelled, completed_at, position, task_date FROM tasks WHERE id = ?', (task_id,)).fetchone())
        assert after_conversion == (1, 0, *before_conversion[2:])
        assert dev.evaluate(f"document.querySelector('{cancel}').textContent.includes('❌')")
        dev.call('Page.reload')
        wait_for(lambda: dev.evaluate(f"window.tasklineReady === true && document.querySelector('{check}')?.textContent.trim() === '✓'"))
        # Cancel again through the same action, then verify checkbox reopening.
        click(more)
        click(cancel)
        wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {task_id}).cancelled === 1"))
        click(check)
        wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {task_id}).completed === 0 && tasks.find(task => task.id === {task_id}).cancelled === 0"))
        click(check)
        wait_for(lambda: dev.evaluate(f"tasks.find(task => task.id === {task_id}).completed === 1"))
        assert dev.evaluate(f"document.querySelector('{check}').textContent.trim() === '✓'")
        # The adjacent delete button still uses its existing confirmation and DELETE.
        dev.evaluate('window.confirm = () => true')
        click(more)
        click(row + ' [data-delete]')
        wait_for(lambda: dev.evaluate(f"!document.querySelector('{row}')"))
        assert dev.evaluate('window.uiErrors') == [], dev.evaluate('window.uiErrors')
        print(f'PASS cancellation {space}: paired actions, icons/captions, completion, reload, reopen, failure recovery, delete; two languages/themes and five sizes')
