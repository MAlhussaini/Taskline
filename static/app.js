const form = document.querySelector('#task-form');
const input = document.querySelector('#task-input');
const list = document.querySelector('#task-list');
const count = document.querySelector('#task-count');
const empty = document.querySelector('#empty-state');
const hint = document.querySelector('#drag-hint');
const error = document.querySelector('#form-error');
const announcer = document.querySelector('#announcer');
const dayTitle = document.querySelector('#day-title');
const monthLabel = document.querySelector('#month-label');
const monthPicker = document.querySelector('#month-picker');
const datePicker = document.querySelector('#date-picker');
const todayButton = document.querySelector('#today-button');
const weekStrip = document.querySelector('#week-strip');
const overdueSection = document.querySelector('#overdue-section');
const overdueList = document.querySelector('#overdue-list');
const overdueCount = document.querySelector('#overdue-count');
const navToday = document.querySelector('#nav-today');
const navInbox = document.querySelector('#nav-inbox');
const labelDialog = document.querySelector('#label-dialog');
const labelForm = document.querySelector('#label-form');
const labelName = document.querySelector('#label-name');
const labelFilter = document.querySelector('#label-filter');
const languageToggle = document.querySelector('#language-toggle');
const editDialog = document.querySelector('#edit-dialog');
const editForm = document.querySelector('#edit-form');
const editTitle = document.querySelector('#edit-title');
const editDate = document.querySelector('#edit-date');
const editPlanYear = document.querySelector('#edit-plan-year');
const editPlanQuarter = document.querySelector('#edit-plan-quarter');
const editPlanMonth = document.querySelector('#edit-plan-month');
const planningYear = document.querySelector('#planning-year');
const planningQuarter = document.querySelector('#planning-quarter');
const planningMonth = document.querySelector('#planning-month');
const inboxTab = document.querySelector('#inbox-tab');
const dreamsTab = document.querySelector('#dreams-tab');
const historyTab = document.querySelector('#history-tab');
const dreamList = document.querySelector('#dream-list');
const dreamDialog = document.querySelector('#dream-dialog');
const dreamDescription = document.querySelector('#dream-description');
const dreamImage = document.querySelector('#dream-image');
const dreamPreview = document.querySelector('#dream-preview');
const dreamItems = document.querySelector('#dream-items');
const historyPeriod = document.querySelector('#history-period');

let tasks = [];
let draggedId = null;
let swipeStart = null;
let activeDays = new Set();
let currentView = 'day';
let labelingTask = null;
let editingTask = null;
let currentDream = null;
let inboxSubView = 'inbox';
let activeLabel = '';
let language = localStorage.getItem('taskline-language') || 'en';
let dreams = [];
const copy = {
  en: { today:'Today', inbox:'Inbox', dreams:'Dreams', planned:'Planned', settings:'Settings', list:'Your list', add:'Add a task…', later:'Add something for later…', intro:'Write it down, then get it done.', inboxIntro:'A place for tasks you want to do later.', allLabels:'All labels', tasksLeft:'tasks left', taskLeft:'task left', overdue:'Overdue', language:'العربية', addButton:'Add', clear:'Your list is clear.', first:'Add your first task above.', drag:'Hold and drag a task to reorder it.', planFor:'Plan for', dreamTitle:'Dreams', dreamDesc:'Capture a dream now; add details only when you want.', dreamPlaceholder:'A dream…', addDream:'Add dream', plannedDesc:'See everything planned for the selected period.', done:'Done ✅', editTask:'Edit task', taskDetails:'Task details', task:'Task', date:'Date', saveChanges:'Save changes', addLabel:'Add a label', labelName:'Label name', color:'Color', removeLabel:'Remove label', saveLabel:'Save label', dreamDetails:'Dream details', description:'Add a description or vision', image:'Add an image', innerTasks:'Inner tasks', smallStep:'Add a small step…', saveDetails:'Save details', thisWeek:'This week', thisMonth:'This month', thisQuarter:'This quarter', thisTertial:'This tertial', thisYear:'This year' },
  ar: { today:'اليوم', inbox:'الحافظة', dreams:'الأحلام', planned:'المخطط', settings:'الإعدادات', list:'قائمتك', add:'أضف مهمة…', later:'أضف مهمة للمستقبل…', intro:'دوّنها، ثم أنجزها.', inboxIntro:'مكان للمهام التي تريد إنجازها لاحقًا.', allLabels:'كل الوسوم', tasksLeft:'مهام متبقية', taskLeft:'مهمة متبقية', overdue:'متأخرة', language:'English', addButton:'إضافة', clear:'قائمتك فارغة.', first:'أضف مهمتك الأولى أعلاه.', drag:'اضغط واسحب المهمة لإعادة ترتيبها.', planFor:'خطط لها', dreamTitle:'الأحلام', dreamDesc:'سجّل حلمًا الآن، وأضف التفاصيل عندما ترغب.', dreamPlaceholder:'حلم جديد…', addDream:'إضافة حلم', plannedDesc:'اعرض كل المهام المخطط لها في الفترة المختارة.', done:'مكتمل ✔️', editTask:'تعديل المهمة', taskDetails:'تفاصيل المهمة', task:'المهمة', date:'التاريخ', saveChanges:'حفظ التغييرات', addLabel:'إضافة وسم', labelName:'اسم الوسم', color:'اللون', removeLabel:'إزالة الوسم', saveLabel:'حفظ الوسم', dreamDetails:'تفاصيل الحلم', description:'إضافة شرح أو تصور', image:'إضافة صورة', innerTasks:'المهام الداخلية', smallStep:'أضف خطوة صغيرة…', saveDetails:'حفظ التفاصيل', thisWeek:'هذا الأسبوع', thisMonth:'هذا الشهر', thisQuarter:'هذا الربع', thisTertial:'هذا الثلث', thisYear:'هذه السنة' },
};
const t = key => copy[language][key];

function applyLanguage() {
  const arabic = language === 'ar';
  const locale = arabic ? 'ar' : 'en';
  document.documentElement.lang = arabic ? 'ar' : 'en';
  document.documentElement.dir = arabic ? 'rtl' : 'ltr';
  languageToggle.textContent = t('language');
  languageToggle.setAttribute('aria-label', arabic ? 'تغيير اللغة' : 'Change language');
  document.querySelector('label[for="task-input"]').textContent = arabic ? 'ماذا تريد أن تنجز؟' : 'What needs doing?';
  form.querySelector('.add-button').setAttribute('aria-label', arabic ? 'إضافة مهمة' : 'Add task');
  document.querySelector('.bottom-nav').setAttribute('aria-label', arabic ? 'التنقل الرئيسي' : 'Main navigation');
  document.querySelector('.inbox-advanced-nav').setAttribute('aria-label', arabic ? 'أقسام الحافظة' : 'Inbox sections');
  planningYear.setAttribute('aria-label', arabic ? 'السنة' : 'Year'); planningQuarter.setAttribute('aria-label', arabic ? 'الربع' : 'Quarter'); planningMonth.setAttribute('aria-label', arabic ? 'الشهر' : 'Month');
  editPlanYear.setAttribute('aria-label', arabic ? 'السنة المخططة' : 'Planned year'); editPlanQuarter.setAttribute('aria-label', arabic ? 'الربع المخطط' : 'Planned quarter'); editPlanMonth.setAttribute('aria-label', arabic ? 'الشهر المخطط' : 'Planned month');
  labelFilter.setAttribute('aria-label', arabic ? 'تصفية حسب الوسم' : 'Filter by label');
  datePicker.setAttribute('aria-label', arabic ? 'اختر تاريخًا' : 'Choose a date');
  document.querySelector('.week-nav').setAttribute('aria-label', arabic ? 'اختر يومًا' : 'Choose a day');
  document.querySelector('#previous-day').setAttribute('aria-label', arabic ? 'اليوم السابق' : 'Previous day');
  document.querySelector('#next-day').setAttribute('aria-label', arabic ? 'اليوم التالي' : 'Next day');
  document.querySelector('#dream-year').setAttribute('aria-label', arabic ? 'السنة المتوقعة' : 'Expected year');
  navToday.lastChild.textContent = t('today');
  navInbox.lastChild.textContent = t('inbox');
  document.querySelector('.bottom-nav button:last-child').lastChild.textContent = t('settings');
  document.querySelector('#tasks-heading').textContent = t('list');
  document.querySelector('#overdue-heading').textContent = t('overdue');
  todayButton.textContent = t('today');
  labelFilter.options[0].textContent = t('allLabels');
  input.placeholder = currentView === 'inbox' ? t('later') : t('add');
  document.querySelector('.add-label').textContent = t('addButton');
  document.querySelector('.empty-state p').textContent = t('clear');
  document.querySelector('.empty-state>span').textContent = t('first');
  hint.textContent = t('drag');
  inboxTab.textContent = t('inbox'); dreamsTab.textContent = t('dreams'); historyTab.textContent = t('planned');
  document.querySelector('.inbox-planning>label').textContent = t('planFor');
  document.querySelector('#dreams-section h2').textContent = t('dreamTitle');
  document.querySelector('#dreams-section .advanced-composer p').textContent = t('dreamDesc');
  document.querySelector('#dream-title').placeholder = t('dreamPlaceholder');
  document.querySelector('#dream-form button').textContent = t('addDream');
  document.querySelector('#history-section h2').textContent = t('planned');
  document.querySelector('#history-section .history-heading p').textContent = t('plannedDesc');
  [...historyPeriod.options].forEach((option, index) => option.textContent = [t('thisWeek'),t('thisMonth'),t('thisQuarter'),t('thisTertial'),t('thisYear')][index]);
  document.querySelector('#done-section summary').firstChild.nodeValue = `${t('done')} `;
  document.querySelector('#label-dialog .dialog-heading h2').textContent = t('addLabel');
  document.querySelector('#label-dialog .dialog-heading small').textContent = arabic ? 'تنظيم المهمة' : 'Organize task';
  document.querySelector('label[for="label-name"]').textContent = t('labelName');
  labelName.placeholder = arabic ? 'منزل، سيارة، عمل…' : 'Home, Car, Work…';
  document.querySelector('#label-dialog legend').textContent = t('color');
  document.querySelector('#remove-label').textContent = t('removeLabel');
  document.querySelector('#label-form .save-label').textContent = t('saveLabel');
  document.querySelector('#edit-dialog .dialog-heading small').textContent = t('editTask');
  document.querySelector('#edit-dialog .dialog-heading h2').textContent = t('taskDetails');
  document.querySelector('label[for="edit-title"]').textContent = t('task');
  document.querySelector('label[for="edit-date"]').textContent = t('date');
  document.querySelector('.edit-inbox-plan>label').textContent = t('planned');
  document.querySelector('#edit-form .save-label').textContent = t('saveChanges');
  document.querySelector('#dream-dialog .dialog-heading small').textContent = t('dreamDetails');
  const dreamSummaries = document.querySelectorAll('#dream-dialog summary');
  dreamSummaries[0].textContent = t('description'); dreamSummaries[1].textContent = t('image'); dreamSummaries[2].textContent = t('innerTasks');
  document.querySelector('#dream-description').placeholder = language === 'ar' ? 'اكتب تصورك لهذا الحلم…' : 'Describe what this dream looks and feels like…';
  document.querySelector('#dream-item-title').placeholder = t('smallStep');
  document.querySelector('#add-dream-item').textContent = t('addButton');
  document.querySelector('#dream-detail-form .save-label').textContent = t('saveDetails');
  [planningMonth, editPlanMonth].forEach(select => [...select.options].slice(1).forEach((option, index) => { option.textContent = new Intl.DateTimeFormat(locale, { month: 'short' }).format(new Date(2026, index, 1)); }));
  renderCalendar(); render(); loadOverdue();
  if (inboxSubView === 'dreams') loadDreams();
  if (inboxSubView === 'history') loadHistory();
}
const today = toISO(new Date());
let currentDate = today;

function toISO(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function fromISO(value) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function shifted(value, days) {
  const result = fromISO(value);
  result.setDate(result.getDate() + days);
  return toISO(result);
}

function applyPlanningPreference() {
  planningQuarter.disabled = !planningYear.value;
  planningMonth.disabled = !planningYear.value;
  if (planningMonth.value) {
    const monthIndex = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].indexOf(planningMonth.value);
    planningQuarter.value = String(Math.floor(monthIndex / 3) + 1);
  }
  localStorage.setItem('taskline-plan-year', planningYear.value);
  localStorage.setItem('taskline-plan-quarter', planningQuarter.value);
  localStorage.setItem('taskline-plan-month', planningMonth.value);
}

function currentPlan() {
  if (!planningYear.value) return { kind: 'none', value: null };
  const base = planningYear.value;
  if (planningMonth.value) return { kind: 'month', value: `${base}-Q${planningQuarter.value}-${planningMonth.value}` };
  if (planningQuarter.value) return { kind: 'quarter', value: `${base}-Q${planningQuarter.value}` };
  return { kind: 'year', value: base };
}

function planFromWheels(year, quarter, month) {
  if (!year) return { kind: 'none', value: null };
  if (month) return { kind: 'month', value: `${year}-Q${quarter}-${month}` };
  if (quarter) return { kind: 'quarter', value: `${year}-Q${quarter}` };
  return { kind: 'year', value: year };
}

function renderCalendar() {
  const locale = language === 'ar' ? 'ar' : 'en';
  if (currentView === 'inbox') {
    dayTitle.textContent = t('inbox');
    document.querySelector('.intro').textContent = t('inboxIntro');
    return;
  }
  document.querySelector('.intro').textContent = t('intro');
  const selected = fromISO(currentDate);
  monthLabel.textContent = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(selected);
  dayTitle.textContent = currentDate === today ? t('today') : new Intl.DateTimeFormat(locale, { weekday: 'long', month: 'short', day: 'numeric' }).format(selected);
  todayButton.hidden = currentDate === today;
  datePicker.value = currentDate;
  weekStrip.innerHTML = '';
  for (let offset = -3; offset <= 3; offset += 1) {
    const iso = shifted(currentDate, offset);
    const value = fromISO(iso);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `day-chip${iso === currentDate ? ' selected' : ''}${activeDays.has(iso) ? ' has-tasks' : ''}`;
    button.dataset.date = iso;
    button.setAttribute('aria-label', new Intl.DateTimeFormat(locale, { dateStyle: 'full' }).format(value));
    button.innerHTML = `<span>${new Intl.DateTimeFormat(locale, { weekday: 'narrow' }).format(value)}</span><strong>${value.getDate()}</strong><i></i>`;
    weekStrip.appendChild(button);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Something went wrong');
  return payload;
}

const escapeHtml = value => value.replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const grip = () => `<span class="grip" aria-label="${language === 'ar' ? 'اسحب لإعادة الترتيب' : 'Drag to reorder'}">${'<i></i>'.repeat(6)}</span>`;

function render() {
  list.innerHTML = '';
  const labels = [...new Set(tasks.map(task => task.label).filter(Boolean))].sort();
  labelFilter.hidden = currentView !== 'inbox' || labels.length === 0;
  if (currentView === 'inbox') {
    const selected = activeLabel;
    labelFilter.innerHTML = `<option value="">${t('allLabels')}</option>${labels.map(label => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`).join('')}`;
    labelFilter.value = labels.includes(selected) ? selected : '';
    activeLabel = labelFilter.value;
  }
  const visibleTasks = activeLabel && currentView === 'inbox' ? tasks.filter(task => task.label === activeLabel) : tasks;
  visibleTasks.forEach((task, index) => {
    const item = document.createElement('li');
    item.className = `task${task.completed ? ' completed' : ''}${task.parent_id ? ' child-task' : ''}`;
    item.dataset.id = task.id;
    item.draggable = true;
    const label = task.label ? `<span class="task-label ${task.label_color || 'gray'}"><i></i>${escapeHtml(task.label)}</span>` : '';
    const plan = task.location === 'inbox' && task.planning_kind !== 'none' ? `<span class="planning-badge">${escapeHtml(task.planning_value || task.planning_kind)}</span>` : '';
    const transferIcon = currentView === 'inbox' ? '📤' : '📥';
    const transferText = currentView === 'inbox' ? (language === 'ar' ? 'نقل إلى اليوم' : 'Move to today') : (language === 'ar' ? 'نقل إلى الحافظة' : 'Move to inbox');
    item.innerHTML = `<button type="button" class="check-button" data-check aria-label="${language === 'ar' ? (task.completed ? 'جعل المهمة غير مكتملة' : 'إكمال المهمة') : `Mark ${escapeHtml(task.title)} ${task.completed ? 'incomplete' : 'complete'}`}" aria-pressed="${Boolean(task.completed)}"><span aria-hidden="true">✓</span></button>
      <span class="task-copy"><span class="task-title"></span><span class="task-meta">${label}${plan}</span></span>
      <span class="task-actions">
        <button type="button" class="edit-button" data-edit aria-label="${language === 'ar' ? 'تعديل المهمة' : `Edit ${escapeHtml(task.title)}`} "><span aria-hidden="true">✏️</span></button>
        <button type="button" class="label-button" data-label aria-label="${language === 'ar' ? 'وسم المهمة' : `Label ${escapeHtml(task.title)}`} "><span aria-hidden="true">🏷️</span></button>
        <button type="button" class="transfer-button" data-transfer aria-label="${transferText}: ${escapeHtml(task.title)}"><span aria-hidden="true">${transferIcon}</span></button>
        <button type="button" class="delete-button" data-delete aria-label="${language === 'ar' ? 'حذف المهمة' : `Delete ${escapeHtml(task.title)}`} "><span aria-hidden="true">🗑️</span></button>
      </span>
      <button type="button" class="star-button${task.starred ? ' starred' : ''}" data-star aria-label="${language === 'ar' ? (task.starred ? 'إزالة النجمة' : 'تمييز بنجمة') : `${task.starred ? 'Remove star from' : 'Star'} ${escapeHtml(task.title)}`}" aria-pressed="${Boolean(task.starred)}"><span aria-hidden="true">★</span></button>
      ${grip()}
      <span class="hierarchy-actions">
        <button type="button" data-enlist aria-label="${language === 'ar' ? 'جعلها تابعة للمهمة السابقة' : 'Make task a child of the previous task'}" ${index === 0 || activeLabel || task.parent_id ? 'disabled' : ''}>📨</button>
        <button type="button" data-outlist aria-label="${language === 'ar' ? 'جعل المهمة مستقلة' : 'Make task independent'}" ${task.parent_id ? '' : 'disabled'}>✉️</button>
      </span>
      <span class="order-controls">
        <button type="button" data-move="up" aria-label="Move ${escapeHtml(task.title)} up" ${index === 0 ? 'disabled' : ''}>↑</button>
        <button type="button" data-move="down" aria-label="Move ${escapeHtml(task.title)} down" ${index === tasks.length - 1 ? 'disabled' : ''}>↓</button>
      </span>`;
    item.querySelector('.task-title').textContent = task.title;
    list.appendChild(item);
  });
  const remaining = visibleTasks.filter(task => !task.completed).length;
  count.textContent = `${remaining} ${remaining === 1 ? t('taskLeft') : t('tasksLeft')}`;
  empty.hidden = visibleTasks.length > 0;
  hint.hidden = visibleTasks.length < 2 || Boolean(activeLabel);
}

function syncTasksFromDom() {
  const order = [...list.querySelectorAll('.task')].map(item => Number(item.dataset.id));
  tasks.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
}

function placeDraggedItem(target, clientY) {
  const active = list.querySelector(`[data-id="${draggedId}"]`);
  if (!active || !target || active === target) return;
  const below = clientY > target.getBoundingClientRect().top + target.offsetHeight / 2;
  list.insertBefore(active, below ? target.nextSibling : target);
}

async function saveOrder(message) {
  try {
    await api('/api/tasks/reorder', { method: 'PUT', body: JSON.stringify({ ids: tasks.map(task => task.id), task_date: currentDate, location: currentView === 'inbox' ? 'inbox' : 'day' }) });
    announcer.textContent = message;
  } catch (err) {
    error.textContent = err.message;
    await loadTasks();
  }
}

async function loadTasks() {
  try {
    const query = currentView === 'inbox' ? 'location=inbox' : `location=day&date=${currentDate}`;
    tasks = await api(`/api/tasks?${query}`); render();
  }
  catch { error.textContent = 'Could not load your tasks. Please refresh.'; }
}

async function loadActiveDays() {
  try {
    const days = await api('/api/task-days');
    activeDays = new Set(days.map(day => day.task_date));
    renderCalendar();
  } catch { renderCalendar(); }
}

async function loadOverdue() {
  if (currentView === 'inbox' || currentDate !== today) { overdueSection.hidden = true; return; }
  try {
    const overdue = await api(`/api/tasks/overdue?before=${today}`);
    overdueSection.hidden = overdue.length === 0;
    overdueCount.textContent = `${overdue.length} ${overdue.length === 1 ? 'task' : 'tasks'}`;
    overdueList.innerHTML = '';
    overdue.forEach(task => {
      const item = document.createElement('li');
      item.innerHTML = `<span><strong></strong><small></small></span><button type="button" data-move-today="${task.id}">${language === 'ar' ? 'نقل إلى اليوم' : 'Move to today'}</button>`;
      item.querySelector('strong').textContent = task.title;
      item.querySelector('small').textContent = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(fromISO(task.task_date));
      overdueList.appendChild(item);
    });
  } catch { overdueSection.hidden = true; }
}

async function selectDate(value) {
  currentDate = value;
  renderCalendar();
  await loadTasks();
  await loadOverdue();
}

async function toggleTask(task) {
  const previous = Boolean(task.completed);
  task.completed = !previous;
  render();
  try {
    const updated = await api(`/api/tasks/${task.id}`, { method: 'PUT', body: JSON.stringify({ completed: Boolean(task.completed) }) });
    task.completed = Boolean(updated.completed);
    announcer.textContent = `${task.title} marked ${task.completed ? 'complete' : 'incomplete'}.`;
    loadOverdue();
  } catch (err) {
    task.completed = previous;
    render();
    error.textContent = err.message;
  }
}

async function deleteTask(task) {
  if (!window.confirm(`Delete “${task.title}”?`)) return;
  try {
    await api(`/api/tasks/${task.id}`, { method: 'DELETE' });
    tasks = tasks.filter(entry => entry.id !== task.id);
    render();
    announcer.textContent = `${task.title} deleted.`;
    loadActiveDays(); loadOverdue();
  } catch (err) {
    error.textContent = err.message;
  }
}

async function editTask(task) {
  editingTask = task;
  editTitle.value = task.title;
  editDate.value = task.task_date || today;
  const inboxTask = task.location === 'inbox';
  document.querySelector('.edit-day-date').hidden = inboxTask;
  document.querySelector('.edit-inbox-plan').hidden = !inboxTask;
  const match = (task.planning_value || '').match(/^(\d{4})(?:-Q([1-4]))?(?:-([A-Z][a-z]{2}))?$/);
  editPlanYear.value = match?.[1] || '';
  editPlanQuarter.value = match?.[2] || '';
  editPlanMonth.value = match?.[3] || '';
  editDialog.showModal();
  editTitle.focus();
}

async function transferTask(task) {
  const toInbox = currentView !== 'inbox';
  try {
    await api(`/api/tasks/${task.id}`, {
      method: 'PUT',
      body: JSON.stringify(toInbox ? { location: 'inbox', parent_id: null, starred: false } : { location: 'day', task_date: today, parent_id: null, starred: false }),
    });
    tasks = tasks.filter(entry => entry.id !== task.id);
    render();
    await Promise.all([loadActiveDays(), loadOverdue()]);
    announcer.textContent = toInbox ? 'Task moved to inbox.' : 'Task moved to today.';
  } catch (err) { error.textContent = err.message; }
}

async function toggleStar(task) {
  try {
    const updated = await api(`/api/tasks/${task.id}`, { method: 'PUT', body: JSON.stringify({ starred: !Boolean(task.starred) }) });
    task.starred = Boolean(updated.starred);
    render();
  } catch (err) { error.textContent = language === 'ar' && err.message.includes('three') ? 'يمكن وضع نجمة على ثلاث مهام فقط في هذه القائمة.' : err.message; }
}

async function changeHierarchy(task, parentId) {
  try {
    const updated = await api(`/api/tasks/${task.id}`, { method: 'PUT', body: JSON.stringify({ parent_id: parentId }) });
    task.parent_id = updated.parent_id;
    render();
    announcer.textContent = parentId ? 'Task enlisted.' : 'Task made independent.';
  } catch (err) { error.textContent = err.message; }
}

function openLabelDialog(task) {
  labelingTask = task;
  labelName.value = task.label || '';
  const color = task.label_color || 'green';
  const option = labelForm.querySelector(`[name="label-color"][value="${color}"]`);
  if (option) option.checked = true;
  labelDialog.showModal();
  labelName.focus();
}

async function saveLabel(label, color) {
  if (!labelingTask) return;
  try {
    const updated = await api(`/api/tasks/${labelingTask.id}`, {
      method: 'PUT', body: JSON.stringify({ label, label_color: label ? color : null }),
    });
    labelingTask.label = updated.label;
    labelingTask.label_color = updated.label_color;
    render();
    labelDialog.close();
    announcer.textContent = label ? `Label ${label} added.` : 'Label removed.';
  } catch (err) { error.textContent = err.message; }
}

form.addEventListener('submit', async event => {
  event.preventDefault(); error.textContent = '';
  if (currentView === 'inbox') applyPlanningPreference();
  const plan = currentView === 'inbox' ? currentPlan() : { kind: 'date', value: currentDate };
  const button = form.querySelector('button'); button.disabled = true;
  try {
    const task = await api('/api/tasks', { method: 'POST', body: JSON.stringify({ title: input.value, task_date: currentDate, location: currentView === 'inbox' ? 'inbox' : 'day', planning_kind: plan.kind, planning_value: plan.value }) });
    tasks.push(task); input.value = ''; render(); input.focus(); announcer.textContent = `${task.title} added.`;
    loadActiveDays();
  } catch (err) { error.textContent = err.message; }
  finally { button.disabled = false; }
});

list.addEventListener('click', event => {
  const check = event.target.closest('[data-check]');
  if (check) { toggleTask(tasks.find(task => task.id === Number(check.closest('.task').dataset.id))); return; }
  const edit = event.target.closest('[data-edit]');
  if (edit) { editTask(tasks.find(task => task.id === Number(edit.closest('.task').dataset.id))); return; }
  const label = event.target.closest('[data-label]');
  if (label) { openLabelDialog(tasks.find(task => task.id === Number(label.closest('.task').dataset.id))); return; }
  const transfer = event.target.closest('[data-transfer]');
  if (transfer) { transferTask(tasks.find(task => task.id === Number(transfer.closest('.task').dataset.id))); return; }
  const star = event.target.closest('[data-star]');
  if (star) { toggleStar(tasks.find(task => task.id === Number(star.closest('.task').dataset.id))); return; }
  const enlist = event.target.closest('[data-enlist]');
  if (enlist && !enlist.disabled) {
    const task = tasks.find(entry => entry.id === Number(enlist.closest('.task').dataset.id));
    const index = tasks.indexOf(task);
    if (index > 0) changeHierarchy(task, tasks[index - 1].id);
    return;
  }
  const outlist = event.target.closest('[data-outlist]');
  if (outlist && !outlist.disabled) { changeHierarchy(tasks.find(task => task.id === Number(outlist.closest('.task').dataset.id)), null); return; }
  const remove = event.target.closest('[data-delete]');
  if (remove) { deleteTask(tasks.find(task => task.id === Number(remove.closest('.task').dataset.id))); return; }
  const button = event.target.closest('[data-move]');
  if (!button) return;
  const index = tasks.findIndex(task => task.id === Number(button.closest('.task').dataset.id));
  const next = button.dataset.move === 'up' ? index - 1 : index + 1;
  if (next < 0 || next >= tasks.length) return;
  [tasks[index], tasks[next]] = [tasks[next], tasks[index]];
  const title = tasks[next].title; render(); saveOrder(`${title} moved to position ${next + 1}.`);
});

list.addEventListener('dragstart', event => {
  if (event.target.closest('button')) { event.preventDefault(); return; }
  const item = event.target.closest('.task'); if (!item) return;
  draggedId = Number(item.dataset.id); event.dataTransfer.effectAllowed = 'move'; requestAnimationFrame(() => item.classList.add('dragging'));
});
list.addEventListener('dragover', event => { event.preventDefault(); placeDraggedItem(event.target.closest('.task'), event.clientY); });
list.addEventListener('dragend', () => {
  if (draggedId !== null) { syncTasksFromDom(); render(); saveOrder('Task order updated.'); }
  draggedId = null;
});

list.addEventListener('pointerdown', event => {
  if (event.pointerType === 'mouse' || !event.target.closest('.grip')) return;
  const item = event.target.closest('.task'); draggedId = Number(item.dataset.id); item.setPointerCapture(event.pointerId); item.classList.add('dragging');
});
list.addEventListener('pointermove', event => {
  if (draggedId === null || event.pointerType === 'mouse') return;
  event.preventDefault(); placeDraggedItem(document.elementFromPoint(event.clientX, event.clientY)?.closest('.task'), event.clientY);
});
list.addEventListener('pointerup', event => {
  if (draggedId === null || event.pointerType === 'mouse') return;
  syncTasksFromDom(); draggedId = null; render(); saveOrder('Task order updated.');
});

// On phones, reveal delete with a direction-aware horizontal swipe.
list.addEventListener('pointerdown', event => {
  if (event.pointerType === 'mouse' || event.target.closest('button, .grip')) return;
  const item = event.target.closest('.task');
  if (!item) return;
  swipeStart = { item, x: event.clientX, y: event.clientY };
});

list.addEventListener('pointermove', event => {
  if (!swipeStart || event.pointerType === 'mouse') return;
  const dx = event.clientX - swipeStart.x;
  const dy = event.clientY - swipeStart.y;
  if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) event.preventDefault();
});

list.addEventListener('pointerup', event => {
  if (!swipeStart || event.pointerType === 'mouse') return;
  const { item, x, y } = swipeStart;
  const dx = event.clientX - x;
  const dy = event.clientY - y;
  const rtl = document.documentElement.dir === 'rtl' || getComputedStyle(document.body).direction === 'rtl';
  const horizontal = Math.abs(dx) > Math.abs(dy);
  const revealActions = horizontal && (rtl ? dx < -48 : dx > 48);
  const revealHierarchy = horizontal && (rtl ? dx > 48 : dx < -48);
  list.querySelectorAll('.task.swipe-actions,.task.swipe-hierarchy').forEach(task => {
    if (task !== item || revealActions || revealHierarchy) task.classList.remove('swipe-actions', 'swipe-hierarchy');
  });
  if (revealActions) { item.classList.remove('swipe-hierarchy'); item.classList.add('swipe-actions'); }
  if (revealHierarchy) { item.classList.remove('swipe-actions'); item.classList.add('swipe-hierarchy'); }
  swipeStart = null;
});

list.addEventListener('pointercancel', () => { swipeStart = null; });

weekStrip.addEventListener('click', event => {
  const day = event.target.closest('[data-date]');
  if (day) selectDate(day.dataset.date);
});
document.querySelector('#previous-day').addEventListener('click', () => selectDate(shifted(currentDate, -1)));
document.querySelector('#next-day').addEventListener('click', () => selectDate(shifted(currentDate, 1)));
todayButton.addEventListener('click', () => selectDate(today));
monthPicker.addEventListener('click', () => {
  if (typeof datePicker.showPicker === 'function') datePicker.showPicker();
  else datePicker.click();
});
datePicker.addEventListener('change', () => { if (datePicker.value) selectDate(datePicker.value); });

let weekSwipeX = null;
weekStrip.addEventListener('pointerdown', event => { weekSwipeX = event.clientX; });
weekStrip.addEventListener('pointerup', event => {
  if (weekSwipeX === null) return;
  const distance = event.clientX - weekSwipeX;
  if (Math.abs(distance) > 55) selectDate(shifted(currentDate, distance < 0 ? 1 : -1));
  weekSwipeX = null;
});

overdueList.addEventListener('click', async event => {
  const button = event.target.closest('[data-move-today]');
  if (!button) return;
  try {
    await api(`/api/tasks/${button.dataset.moveToday}`, { method: 'PUT', body: JSON.stringify({ task_date: today }) });
    await Promise.all([loadTasks(), loadActiveDays(), loadOverdue()]);
    announcer.textContent = 'Task moved to today.';
  } catch (err) { error.textContent = err.message; }
});

async function setView(view) {
  currentView = view;
  activeLabel = '';
  document.body.classList.toggle('inbox-view', view === 'inbox');
  if (view === 'day') document.body.classList.remove('dreams-view', 'history-view');
  navToday.classList.toggle('active', view === 'day');
  navInbox.classList.toggle('active', view === 'inbox');
  if (view === 'day') { navToday.setAttribute('aria-current', 'page'); navInbox.removeAttribute('aria-current'); }
  else { navInbox.setAttribute('aria-current', 'page'); navToday.removeAttribute('aria-current'); }
  input.placeholder = view === 'inbox' ? t('later') : t('add');
  renderCalendar();
  await Promise.all([loadTasks(), loadOverdue()]);
}

async function setInboxSubView(view) {
  inboxSubView = view;
  document.body.classList.toggle('dreams-view', view === 'dreams');
  document.body.classList.toggle('history-view', view === 'history');
  [inboxTab, dreamsTab, historyTab].forEach(button => button.classList.remove('active'));
  ({ inbox: inboxTab, dreams: dreamsTab, history: historyTab })[view].classList.add('active');
  if (view === 'dreams') await loadDreams();
  if (view === 'history') await loadHistory();
}

async function loadDreams() {
  try {
    const [activeDreams, archivedDreams] = await Promise.all([api('/api/dreams'), api('/api/dreams?archived=1')]);
    dreams = [...activeDreams, ...archivedDreams];
    dreamList.innerHTML = '';
    if (!dreams.length) dreamList.innerHTML = `<p class="history-range">${language === 'ar' ? 'لا توجد أحلام بعد. أضف حلمًا عندما تهمك الفكرة.' : 'No dreams yet. Add one above when an idea matters to you.'}</p>`;
    const addCards = (items, heading) => {
      if (!items.length) return;
      const title = document.createElement('h3'); title.className = 'dream-group-title'; title.textContent = heading; dreamList.appendChild(title);
      items.forEach(dream => {
      const card = document.createElement('article');
      card.className = 'dream-card';
      card.innerHTML = `${dream.image_path ? `<img src="${dream.image_path}" alt="">` : '<div class="dream-image-placeholder">☁️</div>'}<div><h3></h3><p>${dream.expected_year || (language === 'ar' ? 'بدون سنة متوقعة' : 'No expected year')} · ${dream.items.length} ${language === 'ar' ? 'خطوات' : 'steps'}${dream.archived ? ` · ${language === 'ar' ? 'مؤرشف' : 'Archived'}` : ''}</p></div><span class="dream-card-actions"><button class="dream-open" type="button" aria-label="${language === 'ar' ? 'فتح الحلم' : 'Open dream'}">👁️</button>${dream.archived ? '' : `<button class="dream-archive" type="button" aria-label="${language === 'ar' ? 'نقل نسخة إلى الحافظة' : 'Move a copy to Inbox'}">📥</button>`}</span>`;
      card.querySelector('h3').textContent = dream.title;
      card.querySelector('.dream-open').addEventListener('click', () => openDream(dream));
      card.querySelector('.dream-archive')?.addEventListener('click', () => archiveDream(dream));
      dreamList.appendChild(card);
      });
    };
    addCards(activeDreams, language === 'ar' ? 'الأحلام النشطة' : 'Active dreams');
    addCards(archivedDreams, language === 'ar' ? 'الأحلام المؤرشفة' : 'Archived dreams');
  } catch (err) { error.textContent = err.message; }
}

function renderDreamItems() {
  dreamItems.innerHTML = '';
  currentDream.items.forEach(item => {
    const row = document.createElement('label');
    row.className = `dream-item${item.completed ? ' done' : ''}`;
    row.innerHTML = `<input type="checkbox" ${item.completed ? 'checked' : ''}><span></span>`;
    row.querySelector('span').textContent = item.title;
    row.querySelector('input').addEventListener('change', async event => {
      await api(`/api/dream-items/${item.id}`, { method: 'PUT', body: JSON.stringify({ completed: event.target.checked }) });
      item.completed = event.target.checked; renderDreamItems();
    });
    dreamItems.appendChild(row);
  });
}

function openDream(dream) {
  currentDream = dream;
  document.querySelector('#dream-dialog-title').textContent = dream.title;
  dreamDescription.value = dream.description || '';
  dreamPreview.hidden = !dream.image_path;
  if (dream.image_path) dreamPreview.src = dream.image_path;
  renderDreamItems();
  dreamDialog.showModal();
}

async function archiveDream(dream) {
  const message = language === 'ar' ? 'نقل نسخة من هذا الحلم ومهامه إلى الحافظة؟ سيبقى الحلم مؤرشفًا.' : 'Move this dream and its steps to Inbox? The dream will remain archived.';
  if (!window.confirm(message)) return;
  try {
    await api(`/api/dreams/${dream.id}/archive-to-inbox`, { method: 'POST', body: '{}' });
    await Promise.all([loadDreams(), loadTasks()]);
  } catch (err) { error.textContent = err.message; }
}

async function loadHistory() {
  try {
    const result = await api(`/api/planned?period=${historyPeriod.value}`);
    document.querySelector('#history-range').textContent = `${result.start} — ${result.end}`;
    const historyList = document.querySelector('#history-list');
    const doneList = document.querySelector('#done-list');
    const renderGroups = (container, items) => {
      const groups = items.reduce((all, task) => { const key = task.planning_value || task.task_date; (all[key] ||= []).push(task); return all; }, {});
      container.innerHTML = '';
      Object.entries(groups).forEach(([period, periodTasks]) => {
        const group = document.createElement('section'); group.className = 'history-group'; group.innerHTML = `<h3>${period}</h3>`;
        periodTasks.forEach(task => { const row = document.createElement('p'); row.className = task.completed ? 'done' : ''; row.textContent = `${task.completed ? '✓' : '○'} ${task.title}`; group.appendChild(row); });
        container.appendChild(group);
      });
      if (!items.length) container.innerHTML = `<p class="history-range">${language === 'ar' ? 'لا توجد مهام في هذه الفترة.' : 'No tasks in this period.'}</p>`;
    };
    const active = result.tasks.filter(task => !task.completed);
    const done = result.tasks.filter(task => task.completed);
    renderGroups(historyList, active); renderGroups(doneList, done);
    document.querySelector('#done-count').textContent = `(${done.length})`;
    document.querySelector('#done-section').hidden = done.length === 0;
  } catch (err) { error.textContent = err.message; }
}

navToday.addEventListener('click', () => { currentDate = today; setView('day'); });
navInbox.addEventListener('click', async () => { await setView('inbox'); setInboxSubView('inbox'); });
labelForm.addEventListener('submit', event => {
  event.preventDefault();
  const color = labelForm.querySelector('[name="label-color"]:checked').value;
  saveLabel(labelName.value.trim(), color);
});
document.querySelector('.dialog-close').addEventListener('click', () => labelDialog.close());
document.querySelector('#remove-label').addEventListener('click', () => saveLabel('', null));
editForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!editingTask || !editTitle.value.trim()) return;
  try {
    const payload = { title: editTitle.value.trim(), parent_id: null };
    if (editingTask.location === 'inbox') {
      const plan = planFromWheels(editPlanYear.value, editPlanQuarter.value, editPlanMonth.value);
      payload.planning_kind = plan.kind; payload.planning_value = plan.value;
    } else {
      if (!editDate.value) return;
      payload.task_date = editDate.value;
    }
    const updated = await api(`/api/tasks/${editingTask.id}`, {
      method: 'PUT', body: JSON.stringify(payload),
    });
    const movedOffCurrentDay = currentView === 'day' && updated.task_date !== currentDate;
    editingTask.title = updated.title;
    editingTask.task_date = updated.task_date;
    editingTask.planning_kind = updated.planning_kind;
    editingTask.planning_value = updated.planning_value;
    if (movedOffCurrentDay) tasks = tasks.filter(task => task.id !== editingTask.id);
    editDialog.close(); render(); loadActiveDays(); loadOverdue();
    announcer.textContent = 'Task updated.';
  } catch (err) { error.textContent = err.message; }
});
document.querySelector('.edit-dialog-close').addEventListener('click', () => editDialog.close());
labelFilter.addEventListener('change', () => { activeLabel = labelFilter.value; render(); });
languageToggle.addEventListener('click', () => {
  language = language === 'en' ? 'ar' : 'en';
  localStorage.setItem('taskline-language', language);
  applyLanguage();
});
const monthCodes = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
for (let year = fromISO(today).getFullYear(); year <= fromISO(today).getFullYear() + 30; year += 1) {
  [planningYear, editPlanYear, document.querySelector('#dream-year')].forEach(select => select.add(new Option(String(year), String(year))));
}
monthCodes.forEach((month, index) => {
  planningMonth.add(new Option(month, month)); editPlanMonth.add(new Option(month, month));
});
planningYear.value = localStorage.getItem('taskline-plan-year') || '';
planningQuarter.value = localStorage.getItem('taskline-plan-quarter') || '';
planningMonth.value = localStorage.getItem('taskline-plan-month') || '';
[planningYear, planningQuarter, planningMonth].forEach(select => select.addEventListener('change', applyPlanningPreference));
editPlanMonth.addEventListener('change', () => { if (editPlanMonth.value) editPlanQuarter.value = String(Math.floor(monthCodes.indexOf(editPlanMonth.value) / 3) + 1); });
applyPlanningPreference();
inboxTab.addEventListener('click', () => setInboxSubView('inbox'));
dreamsTab.addEventListener('click', () => setInboxSubView('dreams'));
historyTab.addEventListener('click', () => setInboxSubView('history'));
document.querySelector('#dream-form').addEventListener('submit', async event => {
  event.preventDefault();
  const title = document.querySelector('#dream-title');
  const year = document.querySelector('#dream-year');
  try {
    await api('/api/dreams', { method: 'POST', body: JSON.stringify({ title: title.value, expected_year: year.value || null }) });
    title.value = ''; year.value = ''; await loadDreams();
  } catch (err) { error.textContent = err.message; }
});
document.querySelector('#dream-dialog-close').addEventListener('click', () => dreamDialog.close());
document.querySelector('#add-dream-item').addEventListener('click', async () => {
  const field = document.querySelector('#dream-item-title');
  if (!currentDream || !field.value.trim()) return;
  try {
    const item = await api(`/api/dreams/${currentDream.id}/items`, { method: 'POST', body: JSON.stringify({ title: field.value }) });
    currentDream.items.push(item); field.value = ''; renderDreamItems();
  } catch (err) { error.textContent = err.message; }
});
document.querySelector('#dream-detail-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!currentDream) return;
  try {
    const payload = { description: dreamDescription.value };
    if (dreamImage.files[0]) payload.image_data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(dreamImage.files[0]); });
    const updated = await api(`/api/dreams/${currentDream.id}`, { method: 'PUT', body: JSON.stringify(payload) });
    Object.assign(currentDream, updated); dreamDialog.close(); await loadDreams();
  } catch (err) { error.textContent = err.message; }
});
historyPeriod.value = localStorage.getItem('taskline-history-period') || 'month';
historyPeriod.addEventListener('change', () => { localStorage.setItem('taskline-history-period', historyPeriod.value); loadHistory(); });

renderCalendar();
applyLanguage();
Promise.all([loadTasks(), loadActiveDays(), loadOverdue()]);
