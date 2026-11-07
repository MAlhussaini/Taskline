"""Exercise real mouse/touch dragging and immediate task insertion in the browser."""
import time


def check_routine_drag(dev, evaluate_async, click, fits, wait_for):
    for space in ('personal', 'work'):
        dev.evaluate(f"workspace = '{space}'; applyWorkspace()")
        evaluate_async("setView('routines')")
        evaluate_async("api('/api/routines', {method:'POST', body:JSON.stringify({title:'Drag fixture', start_date:'2030-01-01', frequency:'daily'})})")
        evaluate_async('loadRoutines()')
        for touch, width, lang in ((False, 1440, 'en'), (True, 390, 'ar')):
            dev.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 900, 'deviceScaleFactor': 1, 'mobile': touch})
            dev.evaluate(f"language = '{lang}'; applyLanguage()")
            before = dev.evaluate('routines.map(r => r.id)')
            expected = [before[1], before[0], *before[2:]]
            def drag(cancel=False):
                points = evaluate_async("""(async () => {
                  const cards = routineList.querySelectorAll('.routine-card');
                  cards[0].scrollIntoView({block:'start'}); window.scrollBy(0, -120);
                  await new Promise(resolve => requestAnimationFrame(resolve));
                  const handle = cards[0].querySelector('[data-routine-drag]').getBoundingClientRect();
                  const target = cards[1].getBoundingClientRect();
                  return {x:handle.x+handle.width/2, y:handle.y+handle.height/2, end:target.bottom-8};
                })()""")
                x, y = points['x'], points['y']
                if touch:
                    dev.call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y, 'id': 1}]})
                else:
                    dev.call('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})
                for step in range(1, 7):
                    current = y + (points['end'] - y) * step / 6
                    if touch:
                        dev.call('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': current, 'id': 1}]})
                    else:
                        dev.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': current, 'button': 'left', 'buttons': 1})
                    time.sleep(.02)
                if cancel:
                    dev.call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape'})
                if touch:
                    dev.call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                else:
                    dev.call('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': points['end'], 'button': 'left', 'clickCount': 1})
            drag(cancel=True)
            assert dev.evaluate('routines.map(r => r.id)') == before
            drag()
            wait_for(lambda: dev.evaluate('!movingRoutine && routines.map(r => r.id).join()') == ','.join(map(str, expected)))
            evaluate_async('loadRoutines()')
            assert dev.evaluate('routines.map(r => r.id)') == expected
            fits((space, lang, width, 'routine drag'))
            print(f'PASS routine drag {space}/{lang}: real {"touch" if touch else "mouse"}, cancel, save and reload')
        evaluate_async("setView('day')")
        evaluate_async("selectDate('2030-01-01')")
        dev.evaluate("input.value = 'New above routines'; form.requestSubmit()")
        wait_for(lambda: dev.evaluate("tasks.some(task => task.title === 'New above routines')"))
        assert dev.evaluate("[...list.children].findIndex(row => row.querySelector('.task-title').textContent === 'New above routines') < [...list.children].findIndex(row => row.classList.contains('routine-task'))")
        evaluate_async('loadTasks()')
        assert dev.evaluate("tasks.findIndex(task => task.title === 'New above routines') < tasks.findIndex(task => task.routine_occurrence_id)")
    assert dev.evaluate('window.uiErrors') == [], dev.evaluate('window.uiErrors')
