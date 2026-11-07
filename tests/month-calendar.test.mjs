import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const staticRoot = new URL("../static/", import.meta.url);

async function loadCalendarTools() {
  const source = await readFile(new URL("calendar-utils.js", staticRoot), "utf8");
  const context = vm.createContext({ globalThis: {} });
  vm.runInContext(source, context);
  return context.globalThis.TasklineCalendar;
}

test("builds a complete six-week Sunday-first month grid", async () => {
  const calendar = await loadCalendarTools();
  const dates = calendar.monthGrid("2026-09-22");

  assert.equal(dates.length, 42);
  assert.equal(dates[0], "2026-08-30");
  assert.equal(dates[41], "2026-10-10");
  assert.ok(dates.includes("2026-09-01"));
  assert.ok(dates.includes("2026-09-30"));
});

test("handles leap months and loads statuses through the visible range", async () => {
  const calendar = await loadCalendarTools();

  assert.equal(calendar.monthStart("2028-02-17"), "2028-02-01");
  assert.equal(calendar.monthEnd("2028-02-17"), "2028-02-29");
  assert.equal(calendar.statusThrough("2026-09-02"), "2026-09-30");
  assert.equal(calendar.statusThrough("2026-09-25"), "2026-10-09");
});

test("wires the full-month calendar and both completion states", async () => {
  const [html, app, css] = await Promise.all([
    readFile(new URL("index.html", staticRoot), "utf8"),
    readFile(new URL("app.js", staticRoot), "utf8"),
    readFile(new URL("styles.css", staticRoot), "utf8"),
  ]);

  assert.match(html, /id="month-dialog"/);
  assert.match(html, /id="month-grid"/);
  assert.match(app, /renderMonthCalendar/);
  assert.match(app, /monthGrid\.addEventListener\('keydown'/);
  assert.match(app, /completedDays\.has\(iso\)/);
  assert.match(css, /\.month-day\.has-tasks/);
  assert.match(css, /\.month-day\.has-tasks\.all-complete/);
});

test("routine reminders are red only on logical today, with truthful green and mixed days", async () => {
  const { dayStatus } = await loadCalendarTools();
  const today = '2026-10-28';
  assert.equal(dayStatus(undefined, today), 'noTasks');
  for (const day of ['2026-10-27', today, '2026-10-29']) {
    const summary = { task_date: day, task_count: 3, incomplete_count: 2, ordinary_incomplete_count: 0 };
    assert.equal(dayStatus(summary, today), day === today ? 'incomplete' : 'routine');
    assert.equal(dayStatus({ ...summary, ordinary_incomplete_count: 1 }, today), 'incomplete');
    assert.equal(dayStatus({ ...summary, incomplete_count: 0 }, today), 'complete');
    assert.equal(dayStatus({ ...summary, task_count: 0 }, today), 'noTasks');
  }
  const routine = { task_date: '2026-10-28', task_count: '1', incomplete_count: '1', ordinary_incomplete_count: '0' };
  assert.equal(dayStatus(routine, '2026-10-27'), 'routine');
  assert.equal(dayStatus(routine, today), 'incomplete');
  assert.equal(dayStatus(routine, '2026-10-29'), 'routine');
  assert.equal(dayStatus({ ...routine, incomplete_count: 0, missed_count: 1 }, today), 'missed');
  assert.equal(dayStatus({ ...routine, incomplete_count: 0, missed_count: 1 }, '2026-10-29'), 'missed');
  assert.equal(dayStatus({ ...routine, incomplete_count: 0, missed_count: 0 }, today), 'complete');
  // Older servers without the additive metadata keep their existing indicators.
  assert.equal(dayStatus({ task_date: '2026-10-27', task_count: 1, incomplete_count: 1 }, today), 'incomplete');
});

test("completed non-routine plans remain green despite missed or future routines", async () => {
  const { dayStatus } = await loadCalendarTools();
  const today = '2026-10-31';
  const october28 = {task_date:'2026-10-28', task_count:15, ordinary_task_count:1,
    ordinary_incomplete_count:0, incomplete_count:0, missed_count:10};
  assert.equal(dayStatus(october28, today), 'complete');
  assert.equal(dayStatus({...october28, ordinary_incomplete_count:1, incomplete_count:1}, today), 'incomplete');
  assert.equal(dayStatus({...october28, ordinary_task_count:0}, today), 'missed');
  assert.equal(dayStatus({...october28, task_count:0, ordinary_task_count:0}, today), 'noTasks');
  assert.equal(dayStatus({...october28, task_date:'2026-11-01', incomplete_count:14, missed_count:0}, today), 'complete');
  assert.equal(dayStatus({...october28, task_date:today, incomplete_count:14, missed_count:0}, today), 'incomplete');
  assert.equal(dayStatus({...october28, task_date:today}, today), 'complete');
  assert.equal(dayStatus({...october28, ordinary_task_count:'1', ordinary_incomplete_count:'0'}, today), 'complete');
});
