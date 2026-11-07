import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const context = vm.createContext({});
vm.runInContext(await readFile(new URL('../static/task-order.js', import.meta.url), 'utf8'), context);
const order = context.TasklineOrder;
const task = (id, values = {}) => ({ id, completed: 0, starred: 0, parent_id: null, ...values });
const ids = rows => Array.from(rows, row => row.id);

test('optional sorting never changes saved order or separates families', () => {
  const rows = [task(1, { completed: 1 }), task(2), task(3, { starred: 1 }), task(4, { parent_id: 2, starred: 2 })];
  assert.deepEqual(ids(order.order(rows, { prioritySort: false, completedLast: false })), [1, 2, 4, 3]);
  assert.deepEqual(ids(order.order(rows, { prioritySort: false })), [2, 4, 3, 1]);
  assert.deepEqual(ids(order.order(rows, { taskOfDay: false })), [2, 4, 3, 1]);
  const off = { prioritySort: false, completedLast: false };
  const moved = order.reorder(rows, [3, 1, 2, 4], off);
  assert.deepEqual(ids(order.order(moved, off)), [3, 1, 2, 4]);
  assert.deepEqual(ids(rows), [1, 2, 3, 4]);
});

test('reunites interleaved completed families without mutating saved positions', () => {
  const rows = [task(1, { completed: 1 }), task(2, { completed: 1 }), task(3, { parent_id: 1, completed: 1 }), task(4, { parent_id: 1, completed: 1 })];
  assert.deepEqual(ids(order.order(rows)), [1, 3, 4, 2]);
  assert.deepEqual(ids(rows), [1, 2, 3, 4]);
});
test('partial completion and child priority keep the family intact', () => {
  const rows = [task(1), task(2), task(3, { parent_id: 2, completed: 1 }), task(4, { parent_id: 2, starred: 2 })];
  assert.deepEqual(ids(order.order(rows)), [2, 3, 4, 1]);
  rows[3].starred = 0;
  assert.deepEqual(ids(order.order(rows)), [1, 2, 3, 4]);
  rows[1].completed = rows[3].completed = 1;
  assert.deepEqual(ids(order.order(rows)), [1, 2, 3, 4]);
});
test('family filters preserve context for matching parents or children', () => {
  const rows = [task(1), task(2, { parent_id: 1, label: 'Home' }), task(3), task(4, { label: 'Home' })];
  assert.deepEqual(ids(order.filtered(rows, 'Home')), [1, 2, 4]);
});
test('task of the day precedes yellow stars and carries all related tasks', () => {
  const rows = [task(1, { starred: 1 }), task(2), task(3, { starred: 2 }), task(4, { parent_id: 3 }), task(5, { completed: 1 })];
  assert.deepEqual(ids(order.order(rows)), [3, 4, 1, 2, 5]);
  assert.deepEqual(ids(rows), [1, 2, 3, 4, 5]);
  rows[2].starred = 0;
  rows[3].starred = 2;
  assert.deepEqual(ids(order.order(rows)), [3, 4, 1, 2, 5]);
  rows[3].completed = 1;
  assert.deepEqual(ids(order.order(rows)), [1, 2, 3, 4, 5]);
  rows[3].completed = 0;
  rows[3].starred = 0;
  assert.deepEqual(ids(order.order(rows)), [1, 2, 3, 4, 5]);
  rows[2].starred = 2;
  rows[2].completed = rows[3].completed = 1;
  assert.deepEqual(ids(order.order(rows)), [1, 2, 3, 4, 5]);
});
test('manual reorder covers all four priority groups without changing their saved slots', () => {
  const rows = [task(1, { completed: 1 }), task(2, { starred: 1 }), task(3), task(4, { starred: 2 }), task(5, { completed: 1 }), task(6), task(7, { starred: 1 })];
  const moved = order.reorder(rows, [4, 7, 2, 6, 3, 5, 1]);
  assert.deepEqual(ids(moved), [5, 7, 6, 4, 1, 3, 2]);
  assert.deepEqual(ids(order.order(moved)), [4, 7, 2, 6, 3, 5, 1]);
  moved.find(row => row.id === 4).starred = 0;
  assert.deepEqual(ids(order.order(moved)), [7, 2, 6, 4, 3, 5, 1]);
});
test('manual reorder moves families and siblings without baking priority into saved order', () => {
  const rows = [task(1), task(2, { parent_id: 1 }), task(3, { starred: 1 }), task(4), task(5, { parent_id: 4 }), task(6, { parent_id: 4 })];
  const moved = order.reorder(rows, [3, 4, 6, 5, 1, 2]);
  assert.deepEqual(ids(moved), [4, 6, 5, 3, 1, 2]);
  assert.deepEqual(ids(order.order(moved)), [3, 4, 6, 5, 1, 2]);
  moved.find(row => row.id === 3).starred = 0;
  assert.deepEqual(ids(order.order(moved)), [4, 6, 5, 3, 1, 2]);
});

test('successful completion comes before cancelled families, with stable saved order', () => {
  const rows = [task(1, { completed: 1, cancelled: 1 }), task(2, { completed: 1 }),
    task(3), task(4, { parent_id: 1, completed: 1 }), task(5, { completed: 1, cancelled: 1, routine_missed: 1 }),
    task(6, { completed: 1 }), task(7, { parent_id: 2, completed: 1, cancelled: 1 }),
    task(8, { starred: 1 }), task(9, { starred: 2 })];
  const original = JSON.stringify(rows);
  assert.deepEqual(ids(order.order(rows)), [9, 8, 3, 2, 7, 6, 1, 4, 5]);
  assert.equal(JSON.stringify(rows), original);
  rows[0].cancelled = 0;
  assert.deepEqual(ids(order.order(rows)), [9, 8, 3, 1, 4, 2, 7, 6, 5]);
  rows[0].completed = 0;
  assert.deepEqual(ids(order.order(rows)), [9, 8, 1, 4, 3, 2, 7, 6, 5]);
  const off = {prioritySort:false, completedLast:false};
  assert.deepEqual(ids(order.order(rows, off)), [1, 4, 2, 7, 3, 5, 6, 8, 9]);
});

test('cancelled families have their own reorder slots and retain them on success', () => {
  const rows = [task(1, {completed:1, cancelled:1}), task(2), task(3, {completed:1}),
    task(4, {completed:1, cancelled:1}), task(5, {parent_id:4, completed:1, cancelled:1})];
  const reordered = order.reorder(rows, [2, 3, 4, 5, 1]);
  assert.deepEqual(ids(reordered), [4, 5, 2, 3, 1]);
  assert.deepEqual(ids(order.order(reordered)), [2, 3, 4, 5, 1]);
  reordered.find(row => row.id === 4).cancelled = 0;
  assert.deepEqual(ids(order.order(reordered)), [2, 4, 5, 3, 1]);
  assert.deepEqual(ids(rows), [1, 2, 3, 4, 5]);
});
