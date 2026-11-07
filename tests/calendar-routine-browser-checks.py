"""Calendar reminder regressions; called only by the isolated UI suite."""
def check_calendar_routines(dev, evaluate_async, click, fits, screenshot, wait_for, app, viewports):
    for space in ('personal', 'work'):
        dev.evaluate(f"workspace = '{space}'; today = effectiveToday(); currentDate = today; applyWorkspace()")
        evaluate_async("setView('day')")
        old_day, current_day, future_day = dev.evaluate('[shifted(today, -1), today, shifted(today, 1)]')
        evaluate_async(f"api('/api/routines', {{method:'POST', body:JSON.stringify({{title:'Calendar reminder test', frequency:'daily', start_date:'{old_day}', steps:['Routine child']}})}})")
        evaluate_async('loadActiveDays()')

        def has_dot(selector, day):
            return dev.evaluate(f"document.querySelector('{selector}[data-date=\"{day}\"]').classList.contains('has-tasks')")

        for lang in ('ar', 'en'):
            dev.evaluate(f"language = '{lang}'; applyLanguage()")
            for width, height in viewports:
                dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width <= 600})
                evaluate_async(f"selectDate('{old_day}')")
                # Browsing yesterday must not turn it into the effective today.
                assert not has_dot('.day-chip', old_day)
                assert has_dot('.day-chip', current_day)
                assert not has_dot('.day-chip', future_day)
                click('#month-picker')
                wait_for(lambda: dev.evaluate("monthDialog.open && !monthGrid.classList.contains('loading')"))
                for day, expected in ((old_day, False), (current_day, True), (future_day, False)):
                    # Month boundaries can put tomorrow outside the selected grid.
                    dev.evaluate(f"calendarCursor = TasklineCalendar.monthStart('{day}'); renderMonthCalendar()")
                    assert has_dot('.month-day', day) == expected
                dev.evaluate(f"calendarCursor = TasklineCalendar.monthStart('{old_day}'); renderMonthCalendar()")
                label = dev.evaluate(f"document.querySelector('.month-day[data-date=\"{old_day}\"]').getAttribute('aria-label')")
                assert ('روتين فائت' if lang == 'ar' else 'Missed routines') in label
                fits(('calendar routines', space, lang, width))
                if width == 390:
                    screenshot(f'calendar-routines-{space}-{lang}')
                dev.evaluate('monthDialog.close()')

        # A completed non-routine plan is green even with missed/future routines.
        for day in (old_day, future_day):
            task = evaluate_async(f"api('/api/tasks', {{method:'POST', body:JSON.stringify({{title:'Ordinary calendar task', task_date:'{day}'}})}})")
            evaluate_async(f"selectDate('{day}')")
            assert has_dot('.day-chip', day)
            evaluate_async(f"api('/api/tasks/{task['id']}', {{method:'PUT', body:JSON.stringify({{completed:true}})}})")
            evaluate_async('loadActiveDays()')
            assert has_dot('.day-chip', day)
            assert dev.evaluate(f"document.querySelector('.day-chip[data-date=\"{day}\"]').classList.contains('all-complete')")
            for lang in ('ar', 'en'):
                dev.evaluate(f"language = '{lang}'; applyLanguage()")
                for width, height in viewports:
                    dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width <= 600})
                    click('#month-picker')
                    wait_for(lambda: dev.evaluate("monthDialog.open && !monthGrid.classList.contains('loading')"))
                    assert dev.evaluate(f"document.querySelector('.month-day[data-date=\"{day}\"]').classList.contains('all-complete')")
                    assert dev.evaluate(f"document.querySelector('.month-day[data-date=\"{day}\"]').getAttribute('aria-label').includes(ct('ordinaryComplete'))")
                    fits(('completed ordinary plan', space, lang, day, width))
                    if width == 390:
                        screenshot(f'calendar-completed-plan-{space}-{lang}-{day}')
                    dev.evaluate('monthDialog.close()')
            rows = evaluate_async(f"api('/api/tasks?date={day}')")
            routine_rows = [row for row in rows if row['routine_occurrence_id']]
            assert routine_rows
            if day == old_day:
                assert all(row['routine_missed'] and row['cancelled'] for row in routine_rows)
            else:
                assert all(not row['completed'] for row in routine_rows)
            for row in rows:
                if row['parent_id'] is None:
                    evaluate_async(f"api('/api/tasks/{row['id']}', {{method:'PUT', body:JSON.stringify({{completed:true}})}})")
            evaluate_async('loadActiveDays()')
            assert has_dot('.day-chip', day)
            assert dev.evaluate(f"document.querySelector('.day-chip[data-date=\"{day}\"]').classList.contains('all-complete')")
        assert dev.evaluate('window.uiErrors') == [], dev.evaluate('window.uiErrors')
        print(f'PASS calendar routines {space}: past/future neutral, logical today red, ordinary red, complete green; both languages and five sizes')
