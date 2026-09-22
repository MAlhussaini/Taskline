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
  assert.match(app, /completedDays\.has\(iso\)/);
  assert.match(css, /\.month-day\.has-tasks/);
  assert.match(css, /\.month-day\.has-tasks\.all-complete/);
});
