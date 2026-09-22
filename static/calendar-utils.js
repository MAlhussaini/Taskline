(() => {
  function parseISO(value) {
    const [year, month, day] = value.split('-').map(Number);
    return new Date(year, month - 1, day, 12);
  }

  function toISO(value) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function addDays(value, amount) {
    const result = parseISO(value);
    result.setDate(result.getDate() + amount);
    return toISO(result);
  }

  function monthStart(value) {
    const result = parseISO(value);
    result.setDate(1);
    return toISO(result);
  }

  function monthEnd(value) {
    const result = parseISO(value);
    result.setMonth(result.getMonth() + 1, 0);
    return toISO(result);
  }

  function statusThrough(value) {
    const endOfMonth = monthEnd(value);
    const twoWeeksAhead = addDays(value, 14);
    return endOfMonth > twoWeeksAhead ? endOfMonth : twoWeeksAhead;
  }

  function monthGrid(value) {
    const firstVisible = parseISO(monthStart(value));
    firstVisible.setDate(firstVisible.getDate() - firstVisible.getDay());
    return Array.from({ length: 42 }, (_, index) => addDays(toISO(firstVisible), index));
  }

  globalThis.TasklineCalendar = Object.freeze({ addDays, monthStart, monthEnd, statusThrough, monthGrid });
})();
