window.TasklineDebts = (() => {
  let lists = [], busy = false, loading = false, generation = 0, loadedSpace = null;
  let detailId = null, detailMode = 'current', editing = null, settling = null, message = '', failed = false;
  const section = document.querySelector('#debts-section');
  const details = document.querySelector('#debt-details');
  const editor = document.querySelector('#debt-editor');
  const settlement = document.querySelector('#debt-settle');
  const w = (ar, en) => language === 'ar' ? ar : en;
  const name = () => w('العمليات المالية', 'Finances');
  const money = (cents, signed = true) => `<bdi dir="ltr" class="debt-amount ${signed && cents > 0 ? 'debt-positive' : signed && cents < 0 ? 'debt-negative' : ''}">${signed && cents > 0 ? '+' : signed && cents < 0 ? '−' : ''}${new Intl.NumberFormat(language === 'ar' ? 'ar-SA' : 'en', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(Math.abs(cents) / 100)}</bdi>`;
  const day = () => toISO(new Date());
  const button = (action, label, listId = '', entryId = '', extra = '') => `<button type="button" data-debt-action="${action}" data-list="${listId}" data-entry="${entryId}" ${extra} ${busy || loading ? 'disabled' : ''}>${label}</button>`;
  const entryTitle = e => e.kind === 'settlement' && e.title === 'Settlement' ? w('سداد القائمة', 'List settlement') : e.title;
  const direction = balance => balance > 0 ? w('عليك', 'You owe') : balance < 0 ? w('لك', 'Owed to you') : w('الرصيد صفر', 'Settled balance');

  function entries(list, full, archived = false) {
    const rows = list.entries.filter(e => Boolean(e.archived) === archived && (full || e.kind !== 'settlement'));
    return rows.length ? `<ul class="debt-entries">${rows.map(e => `<li data-debt-entry="${e.id}" class="${e.kind === 'settlement' ? 'debt-settlement' : ''}">
      <div class="debt-entry-copy"><strong>${escapeHtml(entryTitle(e))}</strong>${full ? `<small><time datetime="${e.entry_date}">${new Intl.DateTimeFormat(language === 'ar' ? 'ar-SA-u-ca-gregory' : 'en', {dateStyle: 'medium'}).format(new Date(e.entry_date + 'T12:00:00'))}</time>${e.kind === 'settlement' ? ' · ' + w('سداد', 'Settlement') : ''}</small>` : ''}</div>
      ${money(e.amount_cents)}<div class="debt-entry-actions">${button('edit-entry', w('تعديل', 'Edit'), list.id, e.id)}${button('delete-entry', w('حذف', 'Delete'), list.id, e.id)}</div>
    </li>`).join('')}</ul>` : `<p class="debt-empty">${archived ? w('لا توجد عمليات مسدّدة في الأرشيف.', 'No settled entries in the archive.') : list.archive_count ? w('لا توجد عمليات حالية. العمليات المسدّدة محفوظة في الأرشيف.', 'No current transactions. Settled entries are saved in the archive.') : w('لا توجد عمليات حالية للعرض. يمكنك إضافة عملية أو مراجعة التفاصيل.', 'No current transactions to show. Add an entry or check details.')}</p>`;
  }

  function totals(list, archived = false) {
    list = (archived ? list.archive_totals : list.current_totals) || list;
    return `<div class="debt-totals"><span>${w('مجموع الموجب', 'Positive total')}${money(list.positive_cents)}</span><span>${w('مجموع السالب', 'Negative total')}${money(list.negative_cents)}</span><span class="debt-net">${w('الصافي', 'Net balance')} · ${direction(list.balance_cents)}${money(list.balance_cents)}</span></div>`;
  }

  function renderDetails() {
    const list = lists.find(l => l.id === detailId);
    if (!list) { details.close(); detailId = null; return; }
    if (detailMode === 'archive' && !list.archive_count) detailMode = 'current';
    const archived = detailMode === 'archive';
    details.innerHTML = `<div class="dialog-heading"><div><small>${w('تفاصيل القائمة', 'List details')}</small><h2 id="debt-details-title">${escapeHtml(list.title)}</h2></div>${button('close-details', '×', '', '', `class="dialog-close" aria-label="${w('إغلاق', 'Close')}"`)}</div>
      <p class="debt-hint">${w('العمليات المسدّدة محفوظة في الأرشيف. تعديل مبلغ سابق أو حذف سداد قد يعيد العمليات غير المسدّدة إلى القائمة الحالية.', 'Settled entries are saved in the archive. Changing a previous amount or deleting a settlement may reopen unpaid entries in the current list.')}</p><div class="debt-history-tabs" aria-label="${w('عرض العمليات', 'Transaction view')}">${button('show-current', w('الحالية', 'Current') + ` (${list.current_count || 0})`, list.id, '', `aria-pressed="${!archived}"`)}${button('show-archive', w('الأرشيف', 'Archive') + ` (${list.archive_count || 0})`, list.id, '', `aria-pressed="${archived}" ${list.archive_count ? '' : 'disabled'}`)}</div><section class="debt-history-panel" aria-label="${archived ? w('أرشيف العمليات المسدّدة', 'Settled entries archive') : w('العمليات الحالية', 'Current entries')}">${totals(list, archived)}${entries(list, true, archived)}</section>
      <p class="debt-status ${failed ? 'error' : ''}" role="status">${escapeHtml(message)}</p><div class="debt-dialog-footer">${button('close-details', w('إغلاق التفاصيل', 'Close details'))}</div>`;
  }

  function render() {
    if (message && !failed) message = loading ? w('جارٍ تحميل العمليات…', 'Loading transactions…') : w('تم الحفظ.', 'Saved.');
    const owed = lists.reduce((sum, l) => sum + Math.max(0, l.balance_cents), 0);
    const due = lists.reduce((sum, l) => sum + Math.min(0, l.balance_cents), 0);
    section.innerHTML = `<div class="debt-toolbar"><p>${w('جهة واحدة، قائمة واضحة لكل ما لك وما عليك.', 'One contact, one clear record of what you owe and are owed.')}</p>${button('new-list', w('＋ إضافة جهة', '＋ Add contact'))}</div>
      <p class="debt-hint">${w('الموجب (+) دين عليك، والسالب (−) مبلغ لك. استخدم عملة واحدة لكل القوائم. العمليات المسدّدة في الأرشيف؛ المجاميع هنا للعمليات الحالية فقط.', 'Positive (+): you owe. Negative (−): owed to you. Use one currency across all lists. Settled entries are in the archive; these totals show current entries only.')}</p>
      <div class="debt-summary"><span>${w('إجمالي عليك', 'Total you owe')}${money(owed)}</span><span>${w('إجمالي لك', 'Total owed to you')}${money(due)}</span><span>${w('الصافي العام', 'Overall net')}${money(owed + due)}</span></div>
      <p class="debt-status ${failed ? 'error' : ''}" role="${failed ? 'alert' : 'status'}">${escapeHtml(message)}</p>
      ${failed ? button('reload', w('إعادة المحاولة', 'Retry')) : ''}
      <div class="debt-lists">${lists.map(list => `<article class="debt-card" data-debt-list="${list.id}"><div class="debt-card-heading"><h2>${escapeHtml(list.title)}</h2>${button('details', w('التفاصيل', 'Details'), list.id)}</div>
        ${totals(list)}${entries(list, false)}${list.archive_count ? `<div class="debt-archive-shortcut">${button('archive', w('عرض الأرشيف', 'View archive') + ` (${list.archive_count})`, list.id)}</div>` : ''}<div class="debt-actions"><div class="debt-primary-actions">${button('new-entry', w('＋ عملية', '＋ Transaction'), list.id)}${button('settle', w('سداد القائمة', 'Settle list'), list.id, '', list.balance_cents === 0 ? 'disabled' : '')}</div><div class="debt-management-actions">${button('rename', w('تعديل الجهة', 'Rename'), list.id)}${button('clear', w('حذف جميع العمليات', 'Clear all entries'), list.id, '', !list.entries.length ? 'disabled' : '')}${button('delete-list', w('حذف القائمة', 'Delete list'), list.id)}</div></div></article>`).join('') || `<div class="empty-state"><div class="empty-mark" aria-hidden="true">＄</div><p>${w('ابدأ بإضافة جهة', 'Start by adding a contact')}</p><span>${w('مثل: صديقي، العمل، البقالة.', 'For example: a friend, work, or the grocery store.')}</span></div>`}</div>`;
    if (details.open) renderDetails();
  }

  async function load() {
    if (busy) return;
    loading = true;
    const request = ++generation, space = workspace;
    if (loadedSpace !== space) { lists = []; loadedSpace = null; resetDialogs(); }
    message = w('جارٍ تحميل العمليات…', 'Loading transactions…'); failed = false; render();
    try {
      const data = await api('/api/debts');
      if (request !== generation || space !== workspace) return;
      lists = data; loadedSpace = space; message = '';
    } catch {
      if (request !== generation || space !== workspace) return;
      message = w('تعذر تحميل العمليات. تحقق من الاتصال ثم أعد المحاولة.', 'Could not load transactions. Check your connection and retry.'); failed = true;
    }
    loading = false;
    render();
  }

  function resetDialogs() { details.close(); editor.close(); settlement.close(); detailId = null; editing = null; settling = null; }
  function leave() { ++generation; loading = false; resetDialogs(); }

  function openEditor(list, entry, rename = false) {
    const isList = !list || rename;
    editing = { listId: list?.id, entryId: entry?.id, isList, space: workspace };
    editor.innerHTML = `<form id="debt-edit-form"><div class="dialog-heading"><h2 id="debt-editor-title">${isList ? w('الجهة', 'Contact') : entry ? w('تعديل العملية', 'Edit transaction') : w('إضافة عملية', 'Add transaction')}</h2>${button('close-editor', '×', '', '', `class="dialog-close" aria-label="${w('إغلاق', 'Close')}"`)}</div>
      <label for="debt-title">${isList ? w('اسم الجهة', 'Contact name') : w('العملية', 'Transaction')}</label><input id="debt-title" name="title" required maxlength="280" value="${escapeHtml(isList ? list?.title || '' : entry ? entryTitle(entry) : '')}">
      ${isList ? '' : `<label for="debt-amount">${w('المبلغ: موجب عليك، سالب لك', 'Amount: positive you owe, negative owed to you')}</label><input id="debt-amount" name="amount" type="text" inputmode="text" dir="ltr" required placeholder="+100 / -50.25" value="${entry ? (entry.amount_cents / 100).toFixed(2) : ''}"><label for="debt-date">${w('التاريخ', 'Date')}</label><input id="debt-date" name="entry_date" type="date" required value="${entry?.entry_date || day()}">`}
      <p id="debt-editor-error" class="error" role="alert"></p><div class="dialog-actions"><button class="save-label" type="submit">${w('حفظ', 'Save')}</button>${button('close-editor', w('إلغاء', 'Cancel'))}</div></form>`;
    editor.showModal();
    editor.querySelector('#debt-title').focus();
  }

  function openSettlement(list) {
    const base = Math.abs(list.balance_cents);
    // Round 15% once, to the nearest cent, with integer arithmetic.
    const tax = Math.floor((base * 15 + 50) / 100);
    settling = {listId: list.id, balance: list.balance_cents, space: workspace};
    settlement.innerHTML = `<div class="dialog-heading"><div><small>${w('سداد القائمة', 'Settle list')}</small><h2 id="debt-settle-title">${escapeHtml(list.title)}</h2></div>${button('close-settle', '×', '', '', `class="dialog-close" aria-label="${w('إغلاق', 'Close')}"`)}</div>
      <p class="debt-settle-direction">${direction(list.balance_cents)}</p>
      <dl class="debt-payment-summary"><div><dt>${w('الإجمالي قبل الضريبة', 'Total before tax')}</dt><dd id="debt-subtotal">${money(base, false)}</dd></div><div><dt>${w('الضريبة (15٪)', 'Tax (15%)')}</dt><dd id="debt-tax">${money(tax, false)}</dd></div><div class="debt-payment-total"><dt>${w('الإجمالي شامل الضريبة', 'Total including tax')}</dt><dd id="debt-tax-total">${money(base + tax, false)}</dd></div></dl>
      <p id="debt-settle-note" class="debt-hint">${w('الضريبة للعرض فقط ولا تضاف إلى الديون. التأكيد يصفّر الرصيد وينقل العمليات والسداد إلى الأرشيف.', 'Tax is a preview only and is not added to the ledger. Confirming clears the balance and moves the transactions and settlement to the archive.')}</p>
      <p id="debt-settle-error" class="error" role="alert"></p><div class="debt-primary-actions">${button('confirm-settle', w('تأكيد سداد الرصيد', 'Confirm settlement'), list.id)}${button('close-settle', w('إلغاء', 'Cancel'), '', '', 'autofocus')}</div>`;
    settlement.showModal();
    settlement.querySelector('[autofocus]').focus();
  }

  async function mutate(path, method, payload) {
    if (busy) return false;
    busy = true;
    const space = workspace;
    document.querySelectorAll('#debts-section button, #debt-details button, #debt-editor button, #debt-settle button').forEach(b => b.disabled = true);
    try {
      const result = await api(path, {method, ...(payload ? {body: JSON.stringify(payload)} : {})});
      if (space !== workspace) return true;
      ++generation;
      const id = Number(path.split('/')[3]);
      if (result.id) lists = [result, ...lists.filter(l => l.id !== result.id)].sort((a,b) => b.id-a.id);
      else lists = lists.filter(l => l.id !== id);
      message = w('تم الحفظ.', 'Saved.'); failed = false;
      return true;
    } catch (err) {
      message = w('تعذر الحفظ. أعد تحميل القائمة وتحقق من الاتصال. ', 'Could not save. Reload the list and check your connection. ') + err.message;
      failed = true;
      const target = editor.querySelector('#debt-editor-error');
      if (editor.open && target) target.textContent = message;
      if (settlement.open) settlement.querySelector('#debt-settle-error').textContent = message;
      return false;
    } finally {
      busy = false;
      [editor, settlement].forEach(dialog => dialog.querySelectorAll('button').forEach(b => b.disabled = false));
      if (space === workspace) render();
    }
  }

  async function action(event) {
    const target = event.target.closest('[data-debt-action]');
    if (!target || busy) return;
    const act = target.dataset.debtAction;
    const list = lists.find(l => l.id === Number(target.dataset.list));
    const entry = list?.entries.find(e => e.id === Number(target.dataset.entry));
    if (act === 'reload') return load();
    if (act === 'close-settle') { settlement.close(); settling = null; return; }
    if (act === 'confirm-settle') {
      if (!settling || settling.space !== workspace) return;
      const snapshot = {...settling};
      if (await mutate(`/api/debts/${snapshot.listId}/settle`, 'POST', {balance_cents: snapshot.balance, entry_date: day()})) { settlement.close(); settling = null; }
      return;
    }
    if (act === 'close-editor') { editor.close(); return; }
    if (act === 'close-details') { details.close(); return; }
    if (act === 'new-list') return openEditor();
    if (!list || loadedSpace !== workspace) return;
    if (act === 'details' || act === 'archive') { detailId = list.id; detailMode = act === 'archive' || !list.current_count && list.archive_count ? 'archive' : 'current'; renderDetails(); details.showModal(); return; }
    if (act === 'show-current' || act === 'show-archive') { detailMode = act === 'show-archive' ? 'archive' : 'current'; renderDetails(); details.querySelector(`[data-debt-action="${act}"]`)?.focus(); return; }
    if (act === 'rename') return openEditor(list, null, true);
    if (act === 'new-entry' || act === 'edit-entry') return openEditor(list, entry);
    const base = `/api/debts/${list.id}`;
    if (act === 'settle' && list.balance_cents) return openSettlement(list);
    if (act === 'clear' && confirm(w(`حذف جميع عمليات «${list.title}» بما فيها السداد والبدء من الصفر؟ لا يمكن التراجع.`, `Delete all entries including settlements in “${list.title}” and start over? This cannot be undone.`))) await mutate(base + '/entries', 'DELETE');
    if (act === 'delete-list' && confirm(w(`حذف «${list.title}» وكل عملياتها نهائيًا؟`, `Permanently delete “${list.title}” and all its entries?`))) await mutate(base, 'DELETE');
    if (act === 'delete-entry' && entry && confirm(w('حذف هذه العملية؟ سيعاد احتساب الرصيد.', 'Delete this entry? The balance will be recalculated.'))) await mutate(base + '/entries/' + entry.id, 'DELETE');
  }
  [section, details, editor, settlement].forEach(el => el.addEventListener('click', action));
  settlement.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  editor.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !editing || editing.space !== workspace) return;
    const payload = Object.fromEntries(new FormData(event.target));
    payload.title = payload.title.trim();
    if (payload.amount) payload.amount = payload.amount.trim().replace(/[٠-٩]/g, d => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).replace(/[۰-۹]/g, d => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d))).replace(/٫/g, '.').replace(/−/g, '-');
    if (!payload.title || !editing.isList && (!/^[+-]?\d+(\.\d{1,2})?$/.test(payload.amount) || Number(payload.amount) === 0 || Math.abs(Number(payload.amount)) > 1_000_000_000)) {
      editor.querySelector('#debt-editor-error').textContent = w('أدخل وصفًا ومبلغًا غير صفر، بمنزلتين عشريتين كحد أقصى. مثال: +100 أو -50.25', 'Enter a description and a non-zero amount with up to two decimal places, e.g. +100 or -50.25'); return;
    }
    const {isList, listId, entryId} = editing;
    const path = '/api/debts' + (listId ? '/' + listId : '') + (isList ? '' : '/entries' + (entryId ? '/' + entryId : ''));
    if (await mutate(path, isList ? listId ? 'PUT' : 'POST' : entryId ? 'PUT' : 'POST', payload)) editor.close();
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && currentView === 'debts' && !busy && !editor.open && !details.open && !settlement.open) load(); });
  return {name, load, render, leave};
})();
