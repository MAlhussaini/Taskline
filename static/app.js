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
const monthDialog = document.querySelector('#month-dialog');
const monthDialogTitle = document.querySelector('#month-dialog-title');
const monthWeekdays = document.querySelector('#month-weekdays');
const monthGrid = document.querySelector('#month-grid');
const todayButton = document.querySelector('#today-button');
const weekStrip = document.querySelector('#week-strip');
const overdueSection = document.querySelector('#overdue-section');
const overdueList = document.querySelector('#overdue-list');
const overdueCount = document.querySelector('#overdue-count');
const navToday = document.querySelector('#nav-today');
const navInbox = document.querySelector('#nav-inbox');
const navRoutines = document.querySelector('#nav-routines');
const navLists = document.querySelector('#nav-lists');
const labelDialog = document.querySelector('#label-dialog');
const labelForm = document.querySelector('#label-form');
const labelName = document.querySelector('#label-name');
const labelSuggestions = document.querySelector('#label-suggestions');
const labelFilter = document.querySelector('#label-filter');
const languageToggle = document.querySelector('#language-toggle');
const workspaceToggle = document.querySelector('#workspace-toggle');
const workspaceIndicator = document.querySelector('#workspace-indicator');
const brandTitle = document.querySelector('#brand-title');
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
const routineForm = document.querySelector('#routine-form');
const routineId = document.querySelector('#routine-id');
const routineTitle = document.querySelector('#routine-title');
const routineStart = document.querySelector('#routine-start');
const routineFrequency = document.querySelector('#routine-frequency');
const routineInterval = document.querySelector('#routine-interval');
const routineWeekdays = document.querySelector('#routine-weekdays');
const routineMonthDay = document.querySelector('#routine-month-day');
const routineYearMonth = document.querySelector('#routine-year-month');
const routineYearDay = document.querySelector('#routine-year-day');
const routineEndMode = document.querySelector('#routine-end-mode');
const routineEndValue = document.querySelector('#routine-end-value');
const routineFollow = document.querySelector('#routine-follow');
const routineSteps = document.querySelector('#routine-steps');
const routineList = document.querySelector('#routine-list');
const routineCancel = document.querySelector('#routine-cancel');
const routineStats = document.querySelector('#routine-stats');
const routineStatsToggle = document.querySelector('#routine-stats-toggle');
const routineStatsPeriod = document.querySelector('#routine-stats-period');
const routineStatsMetric = document.querySelector('#routine-stats-metric');
const routineStatsFilter = document.querySelector('#routine-stats-filter');
const routineChart = document.querySelector('#routine-chart');
const listForm = document.querySelector('#list-form');
const listTitle = document.querySelector('#list-title');
const listsList = document.querySelector('#lists-list');
const listsSection = document.querySelector('#lists-section');
const listsEditToggle = document.querySelector('#lists-edit-toggle');
const installApp = document.querySelector('#install-app');
const installDialog = document.querySelector('#install-dialog');
const installDialogTitle = document.querySelector('#install-dialog-title');
const installDialogMessage = document.querySelector('#install-dialog-message');

let tasks = [];
let draggedId = null;
let swipeStart = null;
let activeDays = new Set();
let completedDays = new Set();
let currentView = 'day';
let labelingTask = null;
let editingTask = null;
let currentDream = null;
let inboxSubView = 'inbox';
let activeLabel = '';
let language = localStorage.getItem('taskline-language') || 'en';
let workspace = localStorage.getItem('taskline-workspace') === 'work' ? 'work' : 'personal';
// These defaults are centralized so they can move into the Settings screen later.
const workspaceDayStartHours = { personal: 3, work: 0 };
let dreams = [];
let routines = [];
let checklists = [];
let listsEditing = false;
let deferredInstallPrompt = null;
let calendarCursor = null;
let editingRoutine = null;
let savedLabels = [];
const copy = {
  en: { today:'Today', inbox:'Inbox', dreams:'Dreams', planned:'Planned', settings:'Settings', list:'Your list', add:'Add a task…', later:'Add something for later…', intro:'Write it down, then get it done.', inboxIntro:'A place for tasks you want to do later.', allLabels:'All labels', tasksLeft:'tasks left', taskLeft:'task left', overdue:'Overdue', language:'العربية', addButton:'Add', clear:'Your list is clear.', first:'Add your first task above.', drag:'Hold and drag a task to reorder it.', planFor:'Plan for', dreamTitle:'Dreams', dreamDesc:'Capture a dream now; add details only when you want.', dreamPlaceholder:'A dream…', addDream:'Add dream', plannedDesc:'See everything planned for the selected period.', done:'Done ✅', editTask:'Edit task', taskDetails:'Task details', task:'Task', date:'Date', saveChanges:'Save changes', addLabel:'Add a label', labelName:'Label name', color:'Color', removeLabel:'Remove label', saveLabel:'Save label', dreamDetails:'Dream details', description:'Add a description or vision', image:'Add an image', innerTasks:'Inner tasks', smallStep:'Add a small step…', saveDetails:'Save details', thisWeek:'This week', thisMonth:'This month', thisQuarter:'This quarter', thisTertial:'This tertial', thisYear:'This year' },
  ar: { today:'اليوم', inbox:'الحافظة', dreams:'الأحلام', planned:'المخطط', settings:'الإعدادات', list:'قائمتك', add:'أضف مهمة…', later:'أضف مهمة للمستقبل…', intro:'دوّنها، ثم أنجزها.', inboxIntro:'مكان للمهام التي تريد إنجازها لاحقًا.', allLabels:'كل الوسوم', tasksLeft:'مهام متبقية', taskLeft:'مهمة متبقية', overdue:'متأخرة', language:'English', addButton:'إضافة', clear:'قائمتك فارغة.', first:'أضف مهمتك الأولى أعلاه.', drag:'اضغط واسحب المهمة لإعادة ترتيبها.', planFor:'خطط لها', dreamTitle:'الأحلام', dreamDesc:'سجّل حلمًا الآن، وأضف التفاصيل عندما ترغب.', dreamPlaceholder:'حلم جديد…', addDream:'إضافة حلم', plannedDesc:'اعرض كل المهام المخطط لها في الفترة المختارة.', done:'مكتمل ✔️', editTask:'تعديل المهمة', taskDetails:'تفاصيل المهمة', task:'المهمة', date:'التاريخ', saveChanges:'حفظ التغييرات', addLabel:'إضافة وسم', labelName:'اسم الوسم', color:'اللون', removeLabel:'إزالة الوسم', saveLabel:'حفظ الوسم', dreamDetails:'تفاصيل الحلم', description:'إضافة شرح أو تصور', image:'إضافة صورة', innerTasks:'المهام الداخلية', smallStep:'أضف خطوة صغيرة…', saveDetails:'حفظ التفاصيل', thisWeek:'هذا الأسبوع', thisMonth:'هذا الشهر', thisQuarter:'هذا الربع', thisTertial:'هذا الثلث', thisYear:'هذه السنة' },
};
const t = key => copy[language][key];
const routineCopy = {
  en: { routines:'Routines', routineIntro:'Repeat what matters without losing yesterday’s history.', routineDesc:'Create repeating tasks and keep their history.', statistics:'Statistics', routine:'Routine', starts:'Starts', repeats:'Repeats', every:'Every', daily:'Daily', weekly:'Weekly', monthly:'Monthly', yearly:'Yearly', days:'Days of the week', dayOfMonth:'Day of month', month:'Month', day:'Day', ends:'Ends', never:'Never', onDate:'On a date', afterCount:'After occurrences', endDate:'End date', occurrences:'Number of occurrences', follow:'Follow until complete', followHelp:'Show unfinished occurrences in Overdue so they can be moved.', steps:'Subtasks (one per line)', create:'Create routine', update:'Update routine', cancel:'Cancel', allRoutines:'All routines', sevenDays:'7 days', thirtyDays:'30 days', oneYear:'1 year', percentage:'Completion percentage', completedCount:'Completed count', paused:'Paused', active:'Active', noRoutines:'No routines yet.', carried:'Carried from', routineBadge:'Routine', followBadge:'Follow-up', moveToday:'Move to today', toInbox:'To Inbox', ignore:'Ignore', editFollow:'Follow until complete', editFollowHelp:'Show this task in Overdue until you finish it.' },
  ar: { routines:'الروتين', routineIntro:'كرّر ما يهمك مع الاحتفاظ بسجل الأيام السابقة.', routineDesc:'أنشئ مهام متكررة واحتفظ بسجلها.', statistics:'الإحصاءات', routine:'اسم الروتين', starts:'يبدأ في', repeats:'يتكرر', every:'كل', daily:'يومي', weekly:'أسبوعي', monthly:'شهري', yearly:'سنوي', days:'أيام الأسبوع', dayOfMonth:'يوم الشهر', month:'الشهر', day:'اليوم', ends:'ينتهي', never:'دون نهاية', onDate:'في تاريخ', afterCount:'بعد عدد من المرات', endDate:'تاريخ النهاية', occurrences:'عدد المرات', follow:'متابعة حتى الاكتمال', followHelp:'أظهر الموعد غير المنجز في قسم المتأخرة حتى يمكن نقله.', steps:'المهام الفرعية (مهمة في كل سطر)', create:'إنشاء روتين', update:'تحديث الروتين', cancel:'إلغاء', allRoutines:'كل الروتينات', sevenDays:'7 أيام', thirtyDays:'30 يومًا', oneYear:'سنة', percentage:'نسبة الإنجاز', completedCount:'عدد المهام المكتملة', paused:'متوقف مؤقتًا', active:'نشط', noRoutines:'لا توجد روتينات بعد.', carried:'مرحّلة من', routineBadge:'روتين', followBadge:'متابعة', moveToday:'نقل إلى اليوم', toInbox:'إلى الحافظة', ignore:'تجاهل', editFollow:'متابعة حتى الاكتمال', editFollowHelp:'أظهر هذه المهمة في قسم المتأخرة حتى تنجزها.' },
};
routineCopy.en.missed = 'Missed';
routineCopy.ar.missed = 'فائتة';
const rt = key => routineCopy[language][key];
const listCopy = {
  en: { lists:'Lists', intro:'Keep groceries and any reusable checklist in one place.', name:'List name', namePlaceholder:'Groceries', create:'Create list', editLists:'Edit', doneEditing:'Done', noLists:'No lists yet. Create one above.', empty:'No items yet.', itemPlaceholder:'Add an item…', addItem:'Add', rename:'Rename list', editItem:'Edit item', expand:'Expand list', collapse:'Collapse list', moveUp:'Move list up', moveDown:'Move list down', remove:'Delete list', removeItem:'Delete item', completed:'completed', renamePrompt:'New list name', itemPrompt:'Edit item', confirmRemove:'Delete this list and all its items?' },
  ar: { lists:'القوائم', intro:'احتفظ بالمقاضي وأي قائمة أخرى تحتاجها في مكان واحد.', name:'اسم القائمة', namePlaceholder:'المقاضي', create:'إنشاء قائمة', editLists:'تحرير', doneEditing:'تم', noLists:'لا توجد قوائم بعد. أنشئ قائمتك الأولى أعلاه.', empty:'لا توجد عناصر بعد.', itemPlaceholder:'أضف عنصرًا…', addItem:'إضافة', rename:'تعديل اسم القائمة', editItem:'تعديل العنصر', expand:'فتح القائمة', collapse:'طي القائمة', moveUp:'نقل القائمة إلى أعلى', moveDown:'نقل القائمة إلى أسفل', remove:'حذف القائمة', removeItem:'حذف العنصر', completed:'مكتمل', renamePrompt:'اسم القائمة الجديد', itemPrompt:'تعديل العنصر', confirmRemove:'حذف هذه القائمة وجميع عناصرها؟' },
};
const lt = key => listCopy[language][key];
const pwaCopy = {
  en: { install:'Install Taskline', kicker:'Install app', title:'Add Taskline to your phone', iosHelp:'Tap the Share button, then choose Add to Home Screen.', browserHelp:'Open your browser menu, then choose Install app or Add to Home Screen.', close:'Got it' },
  ar: { install:'تثبيت Taskline', kicker:'تثبيت التطبيق', title:'أضف Taskline إلى جوالك', iosHelp:'اضغط زر المشاركة، ثم اختر «إضافة إلى الشاشة الرئيسية».', browserHelp:'افتح قائمة المتصفح، ثم اختر «تثبيت التطبيق» أو «إضافة إلى الشاشة الرئيسية».', close:'حسنًا' },
};
const pt = key => pwaCopy[language][key];
const calendarCopy = {
  en: { open:'Open full month', kicker:'Full month', previous:'Previous month', next:'Next month', choose:'Choose a day', legend:'Day status legend', incomplete:'Needs attention', complete:'All complete', noTasks:'No tasks', close:'Close', today:'Today' },
  ar: { open:'فتح الشهر كاملًا', kicker:'الشهر كاملًا', previous:'الشهر السابق', next:'الشهر التالي', choose:'اختر يومًا', legend:'دليل حالة الأيام', incomplete:'يحتاج إلى إنجاز', complete:'مكتمل بالكامل', noTasks:'لا توجد مهام', close:'إغلاق', today:'اليوم' },
};
const ct = key => calendarCopy[language][key];

function isIosDevice() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function isStandaloneApp() {
  return window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
}

function refreshInstallButton() {
  installApp.hidden = isStandaloneApp() || (!deferredInstallPrompt && !isIosDevice());
}

function setupPwa() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
        .then(registration => registration.update())
        .catch(() => {});
    });
  }

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    deferredInstallPrompt = event;
    refreshInstallButton();
  });

  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    installApp.hidden = true;
    announcer.textContent = language === 'ar' ? 'تم تثبيت Taskline.' : 'Taskline installed.';
  });

  installApp.addEventListener('click', async () => {
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt = null;
      refreshInstallButton();
      return;
    }
    installDialogMessage.textContent = isIosDevice() ? pt('iosHelp') : pt('browserHelp');
    installDialog.showModal();
  });

  refreshInstallButton();
}

function applyWorkspace() {
  const arabic = language === 'ar';
  const isWork = workspace === 'work';
  const currentName = isWork ? (arabic ? 'مساحة العمل' : 'Work space') : (arabic ? 'المساحة الشخصية' : 'Personal space');
  const destinationName = isWork ? (arabic ? 'المساحة الشخصية' : 'Personal space') : (arabic ? 'مساحة العمل' : 'Work space');
  workspaceIndicator.textContent = isWork ? '💼' : '🏡';
  workspaceIndicator.setAttribute('aria-label', currentName);
  workspaceIndicator.title = currentName;
  workspaceToggle.textContent = isWork ? '🏡' : '💼';
  workspaceToggle.setAttribute('aria-label', `${arabic ? 'انتقل إلى' : 'Switch to'} ${destinationName}`);
  workspaceToggle.title = `${arabic ? 'انتقل إلى' : 'Switch to'} ${destinationName}`;
  brandTitle.textContent = isWork ? (arabic ? 'Taskline عمل' : 'Taskline Work') : 'Taskline';
  document.title = isWork ? `Taskline — ${arabic ? 'العمل' : 'Work'}` : 'Taskline';
  document.body.classList.toggle('work-workspace', isWork);
}

function applyLanguage() {
  const arabic = language === 'ar';
  const locale = arabic ? 'ar' : 'en';
  document.documentElement.lang = arabic ? 'ar' : 'en';
  document.documentElement.dir = arabic ? 'rtl' : 'ltr';
  languageToggle.textContent = t('language');
  languageToggle.setAttribute('aria-label', arabic ? 'تغيير اللغة' : 'Change language');
  monthPicker.setAttribute('aria-label', ct('open'));
  document.querySelector('#month-dialog-kicker').textContent = ct('kicker');
  document.querySelector('#month-dialog-previous').setAttribute('aria-label', ct('previous'));
  document.querySelector('#month-dialog-next').setAttribute('aria-label', ct('next'));
  document.querySelector('#month-dialog-previous').textContent = arabic ? '›' : '‹';
  document.querySelector('#month-dialog-next').textContent = arabic ? '‹' : '›';
  monthGrid.setAttribute('aria-label', ct('choose'));
  document.querySelector('.month-legend').setAttribute('aria-label', ct('legend'));
  document.querySelector('#month-legend-incomplete').textContent = ct('incomplete');
  document.querySelector('#month-legend-complete').textContent = ct('complete');
  document.querySelector('#month-dialog-close').textContent = ct('close');
  document.querySelector('#month-dialog-today').textContent = ct('today');
  installApp.setAttribute('aria-label', pt('install'));
  installApp.title = pt('install');
  document.querySelector('#install-dialog-kicker').textContent = pt('kicker');
  installDialogTitle.textContent = pt('title');
  installDialogMessage.textContent = isIosDevice() ? pt('iosHelp') : pt('browserHelp');
  document.querySelector('#install-dialog .dialog-close').setAttribute('aria-label', arabic ? 'إغلاق' : 'Close');
  document.querySelector('#install-dialog-close').textContent = pt('close');
  applyWorkspace();
  document.querySelector('label[for="task-input"]').textContent = arabic ? 'ماذا تريد أن تنجز؟' : 'What needs doing?';
  form.querySelector('.add-button').setAttribute('aria-label', arabic ? 'إضافة مهمة' : 'Add task');
  document.querySelector('.bottom-nav').setAttribute('aria-label', arabic ? 'التنقل الرئيسي' : 'Main navigation');
  document.querySelector('.inbox-advanced-nav').setAttribute('aria-label', arabic ? 'أقسام الحافظة' : 'Inbox sections');
  planningYear.setAttribute('aria-label', arabic ? 'السنة' : 'Year'); planningQuarter.setAttribute('aria-label', arabic ? 'الربع' : 'Quarter'); planningMonth.setAttribute('aria-label', arabic ? 'الشهر' : 'Month');
  editPlanYear.setAttribute('aria-label', arabic ? 'السنة المخططة' : 'Planned year'); editPlanQuarter.setAttribute('aria-label', arabic ? 'الربع المخطط' : 'Planned quarter'); editPlanMonth.setAttribute('aria-label', arabic ? 'الشهر المخطط' : 'Planned month');
  labelFilter.setAttribute('aria-label', arabic ? 'تصفية حسب الوسم' : 'Filter by label');
  document.querySelector('.week-nav').setAttribute('aria-label', arabic ? 'اختر يومًا' : 'Choose a day');
  document.querySelector('#previous-day').setAttribute('aria-label', arabic ? 'اليوم السابق' : 'Previous day');
  document.querySelector('#next-day').setAttribute('aria-label', arabic ? 'اليوم التالي' : 'Next day');
  document.querySelector('#dream-year').setAttribute('aria-label', arabic ? 'السنة المتوقعة' : 'Expected year');
  navToday.lastChild.textContent = t('today');
  navInbox.lastChild.textContent = t('inbox');
  navRoutines.lastChild.textContent = rt('routines');
  navLists.lastChild.textContent = lt('lists');
  document.querySelector('#nav-settings').lastChild.textContent = t('settings');
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
  document.querySelector('label[for="label-name"]').textContent = arabic ? 'اختر وسمًا محفوظًا أو أنشئ وسمًا جديدًا' : 'Choose a saved label or create a new one';
  labelName.placeholder = arabic ? 'اكتب فقط لإنشاء وسم جديد…' : 'Type only to create a new label…';
  labelSuggestions.setAttribute('aria-label', arabic ? 'الوسوم المحفوظة' : 'Saved labels');
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
  document.querySelector('#routine-heading').textContent = rt('routines');
  document.querySelector('#routine-description').textContent = rt('routineDesc');
  routineStatsToggle.querySelector('span').textContent = rt('statistics');
  document.querySelector('#routine-title-label').textContent = rt('routine');
  routineTitle.placeholder = arabic ? 'مثال: إخراج القمامة' : 'For example: Take out the trash';
  document.querySelector('#routine-start-label').textContent = rt('starts');
  document.querySelector('#routine-frequency-label').textContent = rt('repeats');
  document.querySelector('#routine-interval-label').textContent = rt('every');
  [...routineFrequency.options].forEach((option, index) => option.textContent = [rt('daily'), rt('weekly'), rt('monthly'), rt('yearly')][index]);
  routineWeekdays.querySelector('legend').textContent = rt('days');
  const weekdayNames = arabic ? ['أحد','اثن','ثلا','أرب','خمي','جمع','سبت'] : ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  routineWeekdays.querySelectorAll('label span').forEach((span, index) => { span.textContent = weekdayNames[index]; });
  document.querySelector('#routine-monthly>span').textContent = rt('dayOfMonth');
  document.querySelector('#routine-yearly label:first-child>span').textContent = rt('month');
  document.querySelector('#routine-yearly label:last-child>span').textContent = rt('day');
  document.querySelector('#routine-end-label').textContent = rt('ends');
  [...routineEndMode.options].forEach((option, index) => option.textContent = [rt('never'), rt('onDate'), rt('afterCount')][index]);
  document.querySelector('#routine-follow-title').textContent = rt('follow');
  document.querySelector('#routine-follow-help').textContent = rt('followHelp');
  document.querySelector('#routine-steps-label').textContent = rt('steps');
  routineSteps.placeholder = arabic ? 'المهمة الفرعية الأولى\nالمهمة الفرعية الثانية' : 'First subtask\nSecond subtask';
  routineCancel.textContent = rt('cancel');
  document.querySelector('#routine-save').textContent = editingRoutine ? rt('update') : rt('create');
  [...routineStatsPeriod.options].forEach((option, index) => option.textContent = [rt('sevenDays'), rt('thirtyDays'), rt('oneYear')][index]);
  [...routineStatsMetric.options].forEach((option, index) => option.textContent = [rt('percentage'), rt('completedCount')][index]);
  routineStatsPeriod.setAttribute('aria-label', arabic ? 'فترة الإحصاءات' : 'Statistics period');
  routineStatsMetric.setAttribute('aria-label', arabic ? 'مقياس الإحصاءات' : 'Statistics metric');
  routineStatsFilter.setAttribute('aria-label', arabic ? 'تصفية حسب الروتين' : 'Routine filter');
  document.querySelector('#lists-heading').textContent = lt('lists');
  document.querySelector('#lists-description').textContent = lt('intro');
  document.querySelector('label[for="list-title"]').textContent = lt('name');
  listTitle.placeholder = lt('namePlaceholder');
  document.querySelector('#list-create').textContent = lt('create');
  listsEditToggle.textContent = lt(listsEditing ? 'doneEditing' : 'editLists');
  [...routineYearMonth.options].forEach((option, index) => { option.textContent = new Intl.DateTimeFormat(locale, { month: 'long' }).format(new Date(2026, index, 1)); });
  routineMonthDay.options[routineMonthDay.options.length - 1].textContent = arabic ? 'آخر يوم' : 'Last day';
  [planningMonth, editPlanMonth].forEach(select => [...select.options].slice(1).forEach((option, index) => { option.textContent = new Intl.DateTimeFormat(locale, { month: 'short' }).format(new Date(2026, index, 1)); }));
  renderCalendar(); render(); renderLabelSuggestions(); loadOverdue();
  if (currentView === 'routines') { renderRoutines(); if (!routineStats.hidden) loadRoutineStats(); }
  if (currentView === 'lists') renderLists();
  if (inboxSubView === 'dreams') loadDreams();
  if (inboxSubView === 'history') loadHistory();
}
let today = effectiveToday();
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

function renderMonthCalendar() {
  if (!calendarCursor) calendarCursor = TasklineCalendar.monthStart(currentDate);
  const locale = language === 'ar' ? 'ar' : 'en';
  const cursor = fromISO(calendarCursor);
  const cursorMonth = calendarCursor.slice(0, 7);
  monthDialogTitle.textContent = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(cursor);
  monthWeekdays.innerHTML = '';
  const firstSunday = new Date(2026, 7, 2);
  for (let index = 0; index < 7; index += 1) {
    const label = document.createElement('span');
    const weekday = new Date(firstSunday.getFullYear(), firstSunday.getMonth(), firstSunday.getDate() + index);
    label.textContent = new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(weekday);
    monthWeekdays.appendChild(label);
  }

  monthGrid.innerHTML = '';
  const fragment = document.createDocumentFragment();
  TasklineCalendar.monthGrid(calendarCursor).forEach(iso => {
    const value = fromISO(iso);
    const hasTasks = activeDays.has(iso);
    const allComplete = completedDays.has(iso);
    const statusText = hasTasks ? ct(allComplete ? 'complete' : 'incomplete') : ct('noTasks');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `month-day${iso.slice(0, 7) === cursorMonth ? '' : ' outside-month'}${iso === today ? ' today' : ''}${iso === currentDate ? ' selected' : ''}${hasTasks ? ' has-tasks' : ''}${allComplete ? ' all-complete' : ''}`;
    button.dataset.date = iso;
    button.setAttribute('role', 'gridcell');
    button.setAttribute('aria-selected', String(iso === currentDate));
    if (iso === today) button.setAttribute('aria-current', 'date');
    button.setAttribute('aria-label', `${new Intl.DateTimeFormat(locale, { dateStyle: 'full' }).format(value)} — ${statusText}`);
    button.innerHTML = `<span>${new Intl.DateTimeFormat(locale, { day: 'numeric' }).format(value)}</span><i aria-hidden="true"></i>`;
    fragment.appendChild(button);
  });
  monthGrid.appendChild(fragment);
}

async function openMonthCalendar() {
  calendarCursor = TasklineCalendar.monthStart(currentDate);
  renderMonthCalendar();
  monthPicker.setAttribute('aria-expanded', 'true');
  monthDialog.showModal();
  await loadActiveDays(TasklineCalendar.monthEnd(calendarCursor));
}

async function moveCalendarMonth(amount) {
  const cursor = fromISO(calendarCursor);
  cursor.setMonth(cursor.getMonth() + amount, 1);
  calendarCursor = TasklineCalendar.monthStart(toISO(cursor));
  renderMonthCalendar();
  await loadActiveDays(TasklineCalendar.monthEnd(calendarCursor));
}

function effectiveToday(now = new Date(), targetWorkspace = workspace) {
  const adjusted = new Date(now.getTime());
  adjusted.setHours(adjusted.getHours() - workspaceDayStartHours[targetWorkspace]);
  return toISO(adjusted);
}

function syncLocalToday(now = new Date()) {
  const nextToday = effectiveToday(now);
  if (nextToday === today) return false;
  const wasShowingToday = currentDate === today;
  today = nextToday;
  if (wasShowingToday) currentDate = today;
  return true;
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
  if (currentView === 'routines') {
    dayTitle.textContent = rt('routines');
    document.querySelector('.intro').textContent = rt('routineIntro');
    return;
  }
  if (currentView === 'inbox') {
    dayTitle.textContent = t('inbox');
    document.querySelector('.intro').textContent = workspace === 'work'
      ? (language === 'ar' ? 'حافظة مستقلة لأفكار ومهام العمل القادمة.' : 'A separate inbox for future work tasks and ideas.')
      : t('inboxIntro');
    return;
  }
  document.querySelector('.intro').textContent = workspace === 'work'
    ? (language === 'ar' ? 'مساحة هادئة ومركزة للعمل فقط.' : 'A calm, focused space for work only.')
    : t('intro');
  const selected = fromISO(currentDate);
  monthLabel.textContent = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(selected);
  dayTitle.textContent = currentDate === today ? t('today') : new Intl.DateTimeFormat(locale, { weekday: 'long', month: 'short', day: 'numeric' }).format(selected);
  todayButton.hidden = currentDate === today;
  weekStrip.innerHTML = '';
  for (let offset = -3; offset <= 3; offset += 1) {
    const iso = shifted(currentDate, offset);
    const value = fromISO(iso);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `day-chip${iso === currentDate ? ' selected' : ''}${activeDays.has(iso) ? ' has-tasks' : ''}${completedDays.has(iso) ? ' all-complete' : ''}`;
    button.dataset.date = iso;
    button.setAttribute('aria-label', new Intl.DateTimeFormat(locale, { dateStyle: 'full' }).format(value));
    button.innerHTML = `<span>${new Intl.DateTimeFormat(locale, { weekday: 'narrow' }).format(value)}</span><strong>${value.getDate()}</strong><i></i>`;
    weekStrip.appendChild(button);
  }
  if (monthDialog.open) renderMonthCalendar();
}

async function api(path, options = {}) {
  const separator = path.includes('?') ? '&' : '?';
  const scopedPath = path.startsWith('/api/') ? `${path}${separator}workspace=${encodeURIComponent(workspace)}` : path;
  const response = await fetch(scopedPath, { headers: { 'Content-Type': 'application/json' }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Something went wrong');
  return payload;
}

const escapeHtml = value => value.replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const grip = () => `<span class="grip" aria-label="${language === 'ar' ? 'اسحب لإعادة الترتيب' : 'Drag to reorder'}">${'<i></i>'.repeat(6)}</span>`;

function taskDisplayGroup(task) {
  if (task.completed) return 2;
  return task.starred ? 0 : 1;
}

function orderTasksForDisplay(source) {
  return source
    .map((task, savedIndex) => ({ task, savedIndex }))
    .sort((left, right) => taskDisplayGroup(left.task) - taskDisplayGroup(right.task) || left.savedIndex - right.savedIndex)
    .map(entry => entry.task);
}

function render() {
  syncLocalToday();
  list.innerHTML = '';
  const labels = [...new Set(tasks.map(task => task.label).filter(Boolean))].sort();
  labelFilter.hidden = currentView !== 'inbox' || labels.length === 0;
  if (currentView === 'inbox') {
    const selected = activeLabel;
    labelFilter.innerHTML = `<option value="">${t('allLabels')}</option>${labels.map(label => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`).join('')}`;
    labelFilter.value = labels.includes(selected) ? selected : '';
    activeLabel = labelFilter.value;
  }
  const filteredTasks = activeLabel && currentView === 'inbox' ? tasks.filter(task => task.label === activeLabel) : tasks;
  const visibleTasks = orderTasksForDisplay(filteredTasks);
  visibleTasks.forEach((task, index) => {
    const item = document.createElement('li');
    item.className = `task${task.completed ? ' completed' : ''}${task.parent_id ? ' child-task' : ''}${task.routine_occurrence_id ? ' routine-task' : ''}`;
    item.dataset.id = task.id;
    item.draggable = true;
    const label = task.label ? `<span class="task-label ${task.label_color || 'gray'}"><i></i>${escapeHtml(task.label)}</span>` : '';
    const plan = task.location === 'inbox' && task.planning_kind !== 'none' ? `<span class="planning-badge">${escapeHtml(task.planning_value || task.planning_kind)}</span>` : '';
    const routineBadge = task.routine_occurrence_id ? `<span class="routine-badge">🔁 ${rt('routineBadge')}</span>` : '';
    const carriedBadge = task.carried_from_date && task.carried_from_date !== task.task_date ? `<span class="carried-badge">${rt('carried')} ${escapeHtml(task.carried_from_date)}</span>` : '';
    const followBadge = task.routine_occurrence_id && task.follow_until_complete && !task.parent_id ? `<span class="follow-badge">◎ ${rt('followBadge')}</span>` : '';
    const missedBadge = task.routine_occurrence_id && !task.completed && !task.parent_id && task.task_date < today ? `<span class="missed-badge">○ ${rt('missed')}</span>` : '';
    const transferIcon = currentView === 'inbox' ? '📤' : '📥';
    const transferText = currentView === 'inbox' ? (language === 'ar' ? 'نقل إلى اليوم' : 'Move to today') : (language === 'ar' ? 'نقل إلى الحافظة' : 'Move to inbox');
    item.innerHTML = `<button type="button" class="check-button" data-check aria-label="${language === 'ar' ? (task.completed ? 'جعل المهمة غير مكتملة' : 'إكمال المهمة') : `Mark ${escapeHtml(task.title)} ${task.completed ? 'incomplete' : 'complete'}`}" aria-pressed="${Boolean(task.completed)}"><span aria-hidden="true">✓</span></button>
      <span class="task-copy"><span class="task-title"></span><span class="task-meta">${label}${plan}${routineBadge}${carriedBadge}${followBadge}${missedBadge}</span></span>
      <span class="task-actions">
        <button type="button" class="edit-button" data-edit aria-label="${language === 'ar' ? 'تعديل المهمة' : `Edit ${escapeHtml(task.title)}`} "><span aria-hidden="true">✏️</span></button>
        <button type="button" class="subtask-button" data-add-subtask aria-label="${task.parent_id ? (language === 'ar' ? 'المهام الفرعية بمستوى واحد فقط' : 'Subtasks are limited to one level') : (language === 'ar' ? 'إضافة مهمة فرعية' : 'Add subtask')}" ${task.parent_id ? 'disabled' : ''}><span aria-hidden="true">➕</span></button>
        ${!task.parent_id && !task.routine_occurrence_id ? `<button type="button" class="routine-button" data-make-routine aria-label="${language === 'ar' ? 'تحويل إلى روتين' : 'Make recurring'}"><span aria-hidden="true">🔁</span></button>` : ''}
        <button type="button" class="label-button" data-label aria-label="${language === 'ar' ? 'وسم المهمة' : `Label ${escapeHtml(task.title)}`} "><span aria-hidden="true">🏷️</span></button>
        ${task.routine_occurrence_id ? '' : `<button type="button" class="transfer-button" data-transfer aria-label="${transferText}: ${escapeHtml(task.title)}"><span aria-hidden="true">${transferIcon}</span></button>`}
        <button type="button" class="delete-button" data-delete aria-label="${language === 'ar' ? 'حذف المهمة' : `Delete ${escapeHtml(task.title)}`} "><span aria-hidden="true">🗑️</span></button>
      </span>
      <button type="button" class="star-button${task.starred ? ' starred' : ''}" data-star aria-label="${language === 'ar' ? (task.starred ? 'إزالة النجمة' : 'تمييز بنجمة') : `${task.starred ? 'Remove star from' : 'Star'} ${escapeHtml(task.title)}`}" aria-pressed="${Boolean(task.starred)}"><span aria-hidden="true">★</span></button>
      ${grip()}
      <span class="hierarchy-actions">
        <button type="button" data-enlist aria-label="${language === 'ar' ? 'جعلها تابعة للمهمة السابقة' : 'Make task a child of the previous task'}" ${index === 0 || activeLabel || task.parent_id ? 'disabled' : ''}>📨</button>
        <button type="button" data-outlist aria-label="${language === 'ar' ? 'جعل المهمة مستقلة' : 'Make task independent'}" ${task.parent_id ? '' : 'disabled'}>✉️</button>
      </span>
      <span class="order-controls">
        <button type="button" data-move="up" aria-label="Move ${escapeHtml(task.title)} up" ${index === 0 || taskDisplayGroup(visibleTasks[index - 1]) !== taskDisplayGroup(task) ? 'disabled' : ''}>↑</button>
        <button type="button" data-move="down" aria-label="Move ${escapeHtml(task.title)} down" ${index === visibleTasks.length - 1 || taskDisplayGroup(visibleTasks[index + 1]) !== taskDisplayGroup(task) ? 'disabled' : ''}>↓</button>
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
  const visibleIds = new Set(order);
  const byId = new Map(tasks.map(task => [task.id, task]));
  const reordered = [...tasks];
  for (let group = 0; group <= 2; group += 1) {
    const slots = tasks.map((task, index) => ({ task, index }))
      .filter(entry => visibleIds.has(entry.task.id) && taskDisplayGroup(entry.task) === group)
      .map(entry => entry.index);
    const groupTasks = order.map(id => byId.get(id)).filter(task => task && taskDisplayGroup(task) === group);
    slots.forEach((slot, index) => { reordered[slot] = groupTasks[index]; });
  }
  tasks = reordered;
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

async function loadActiveDays(through = TasklineCalendar.statusThrough(currentDate)) {
  try {
    const days = await api(`/api/task-days?through=${through}`);
    activeDays = new Set(days.map(day => day.task_date));
    completedDays = new Set(days.filter(day => Number(day.task_count) > 0 && Number(day.incomplete_count) === 0).map(day => day.task_date));
    renderCalendar();
  } catch { renderCalendar(); }
}

async function loadOverdue() {
  syncLocalToday();
  if (currentView === 'inbox' || currentDate !== today) { overdueSection.hidden = true; return; }
  try {
    const overdue = await api(`/api/tasks/overdue?before=${today}`);
    overdueSection.hidden = overdue.length === 0;
    overdueCount.textContent = language === 'ar' ? `${overdue.length} ${overdue.length === 1 ? 'مهمة' : 'مهام'}` : `${overdue.length} ${overdue.length === 1 ? 'task' : 'tasks'}`;
    overdueList.innerHTML = '';
    overdue.forEach(task => {
      const item = document.createElement('li');
      const inboxAction = task.routine_occurrence_id ? '' : `<button type="button" class="overdue-icon" data-overdue-action="inbox" data-task-id="${task.id}" aria-label="${rt('toInbox')}" title="${rt('toInbox')}">📥</button>`;
      item.innerHTML = `<span><strong></strong><small></small></span><span class="overdue-actions${task.routine_occurrence_id ? ' routine-overdue' : ''}"><button type="button" class="overdue-primary" data-overdue-action="today" data-task-id="${task.id}">${rt('moveToday')}</button>${inboxAction}<button type="button" class="overdue-icon" data-overdue-action="ignore" data-task-id="${task.id}" aria-label="${rt('ignore')}" title="${rt('ignore')}">🚫</button></span>`;
      item.querySelector('strong').textContent = task.title;
      item.querySelector('small').textContent = `${new Intl.DateTimeFormat(language === 'ar' ? 'ar' : 'en', { month: 'short', day: 'numeric' }).format(fromISO(task.task_date))}${task.routine_occurrence_id ? ` · ${rt('routineBadge')}` : ''}`;
      overdueList.appendChild(item);
    });
  } catch { overdueSection.hidden = true; }
}

async function selectDate(value) {
  currentDate = value;
  renderCalendar();
  await Promise.all([loadTasks(), loadOverdue(), loadActiveDays(TasklineCalendar.statusThrough(value))]);
}

async function toggleTask(task) {
  const previous = Boolean(task.completed);
  task.completed = !previous;
  render();
  try {
    const updated = await api(`/api/tasks/${task.id}`, { method: 'PUT', body: JSON.stringify({ completed: Boolean(task.completed) }) });
    task.completed = Boolean(updated.completed);
    await Promise.all([loadTasks(), loadActiveDays()]);
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

async function addSubtask(task) {
  const promptText = language === 'ar' ? `أضف مهمة فرعية إلى «${task.title}»` : `Add a subtask to “${task.title}”`;
  const title = window.prompt(promptText);
  if (title === null || !title.trim()) return;
  try {
    await api('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({ title: title.trim(), parent_id: task.id, task_date: task.task_date, location: task.location }),
    });
    await loadTasks();
    announcer.textContent = language === 'ar' ? 'تمت إضافة المهمة الفرعية.' : 'Subtask added.';
  } catch (err) { error.textContent = err.message; }
}

async function transferTask(task) {
  const toInbox = currentView !== 'inbox';
  try {
    await api(`/api/tasks/${task.id}`, {
      method: 'PUT',
      body: JSON.stringify(toInbox ? { location: 'inbox', parent_id: null, starred: false } : { location: 'day', task_date: today, parent_id: null, starred: false }),
    });
    await loadTasks();
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

function renderLabelSuggestions() {
  const selected = labelName.value.trim().toLocaleLowerCase();
  labelSuggestions.innerHTML = savedLabels.map(label => `<button type="button" class="label-suggestion ${label.color || 'gray'}${label.name.toLocaleLowerCase() === selected ? ' selected' : ''}" data-saved-label="${escapeHtml(label.name)}" data-saved-color="${escapeHtml(label.color || 'gray')}"><i></i><span>${escapeHtml(label.name)}</span></button>`).join('');
}

async function loadSavedLabels() {
  try {
    savedLabels = await api('/api/labels');
    renderLabelSuggestions();
  } catch { savedLabels = []; renderLabelSuggestions(); }
}

async function openLabelDialog(task) {
  labelingTask = task;
  labelName.value = task.label || '';
  const color = task.label_color || 'green';
  const option = labelForm.querySelector(`[name="label-color"][value="${color}"]`);
  if (option) option.checked = true;
  labelDialog.showModal();
  await loadSavedLabels();
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
    await loadSavedLabels();
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
  const subtask = event.target.closest('[data-add-subtask]');
  if (subtask) { addSubtask(tasks.find(task => task.id === Number(subtask.closest('.task').dataset.id))); return; }
  const makeRoutine = event.target.closest('[data-make-routine]');
  if (makeRoutine) { prepareRoutineFromTask(tasks.find(task => task.id === Number(makeRoutine.closest('.task').dataset.id))); return; }
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
    if (index > 0) {
      const previous = tasks[index - 1];
      changeHierarchy(task, previous.parent_id || previous.id);
    }
    return;
  }
  const outlist = event.target.closest('[data-outlist]');
  if (outlist && !outlist.disabled) { changeHierarchy(tasks.find(task => task.id === Number(outlist.closest('.task').dataset.id)), null); return; }
  const remove = event.target.closest('[data-delete]');
  if (remove) { deleteTask(tasks.find(task => task.id === Number(remove.closest('.task').dataset.id))); return; }
  const button = event.target.closest('[data-move]');
  if (!button) return;
  const item = button.closest('.task');
  const sibling = button.dataset.move === 'up' ? item.previousElementSibling : item.nextElementSibling;
  if (!sibling) return;
  const task = tasks.find(entry => entry.id === Number(item.dataset.id));
  const siblingTask = tasks.find(entry => entry.id === Number(sibling.dataset.id));
  if (taskDisplayGroup(task) !== taskDisplayGroup(siblingTask)) return;
  if (button.dataset.move === 'up') list.insertBefore(item, sibling);
  else list.insertBefore(sibling, item);
  syncTasksFromDom();
  render();
  saveOrder(`${task.title} moved.`);
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
monthPicker.addEventListener('click', openMonthCalendar);
document.querySelector('#month-dialog-previous').addEventListener('click', () => moveCalendarMonth(-1));
document.querySelector('#month-dialog-next').addEventListener('click', () => moveCalendarMonth(1));
document.querySelector('#month-dialog-close').addEventListener('click', () => monthDialog.close());
document.querySelector('#month-dialog-today').addEventListener('click', () => { monthDialog.close(); selectDate(today); });
monthGrid.addEventListener('click', event => {
  const day = event.target.closest('[data-date]');
  if (!day) return;
  monthDialog.close();
  selectDate(day.dataset.date);
});
monthDialog.addEventListener('close', () => monthPicker.setAttribute('aria-expanded', 'false'));

let weekSwipeX = null;
weekStrip.addEventListener('pointerdown', event => { weekSwipeX = event.clientX; });
weekStrip.addEventListener('pointerup', event => {
  if (weekSwipeX === null) return;
  const distance = event.clientX - weekSwipeX;
  if (Math.abs(distance) > 55) selectDate(shifted(currentDate, distance < 0 ? 1 : -1));
  weekSwipeX = null;
});

overdueList.addEventListener('click', async event => {
  const button = event.target.closest('[data-overdue-action]');
  if (!button) return;
  try {
    syncLocalToday();
    await api(`/api/tasks/${button.dataset.taskId}/overdue-action`, { method: 'POST', body: JSON.stringify({ action: button.dataset.overdueAction, target_date: today }) });
    await Promise.all([loadTasks(), loadActiveDays(), loadOverdue()]);
    announcer.textContent = language === 'ar' ? 'تم تحديث المهمة المتأخرة.' : 'Overdue task updated.';
  } catch (err) { error.textContent = err.message; }
});

async function setView(view) {
  currentView = view;
  activeLabel = '';
  if (view !== 'lists') setListsEditing(false);
  document.body.classList.toggle('inbox-view', view === 'inbox');
  document.body.classList.toggle('routines-view', view === 'routines');
  document.body.classList.toggle('lists-view', view === 'lists');
  if (view !== 'inbox') document.body.classList.remove('dreams-view', 'history-view');
  navToday.classList.toggle('active', view === 'day');
  navInbox.classList.toggle('active', view === 'inbox');
  navRoutines.classList.toggle('active', view === 'routines');
  navLists.classList.toggle('active', view === 'lists');
  [navToday, navInbox, navRoutines, navLists].forEach(button => button.removeAttribute('aria-current'));
  ({ day: navToday, inbox: navInbox, routines: navRoutines, lists: navLists })[view].setAttribute('aria-current', 'page');
  input.placeholder = view === 'inbox' ? t('later') : t('add');
  renderCalendar();
  if (view === 'routines') {
    overdueSection.hidden = true;
    await loadRoutines();
    return;
  }
  if (view === 'lists') {
    overdueSection.hidden = true;
    await loadLists();
    return;
  }
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

function updateRoutineScheduleFields() {
  const frequency = routineFrequency.value;
  routineWeekdays.hidden = frequency !== 'weekly';
  document.querySelector('#routine-monthly').hidden = frequency !== 'monthly';
  document.querySelector('#routine-yearly').hidden = frequency !== 'yearly';
  const units = language === 'ar'
    ? { daily:'يوم', weekly:'أسبوع', monthly:'شهر', yearly:'سنة' }
    : { daily:'day(s)', weekly:'week(s)', monthly:'month(s)', yearly:'year(s)' };
  document.querySelector('#routine-interval-unit').textContent = units[frequency];
  const endWrap = document.querySelector('#routine-end-value-wrap');
  endWrap.hidden = routineEndMode.value === 'never';
  routineEndValue.type = routineEndMode.value === 'date' ? 'date' : 'number';
  routineEndValue.min = routineEndMode.value === 'date' ? routineStart.value : '1';
  routineEndValue.max = routineEndMode.value === 'count' ? '10000' : '';
  document.querySelector('#routine-end-value-label').textContent = routineEndMode.value === 'date' ? rt('endDate') : rt('occurrences');
}

function resetRoutineForm() {
  editingRoutine = null;
  routineId.value = '';
  routineForm.reset();
  routineStart.value = today;
  routineInterval.value = '1';
  routineFrequency.value = 'daily';
  routineEndMode.value = 'never';
  routineFollow.checked = false;
  routineWeekdays.querySelectorAll('input').forEach(input => { input.checked = Number(input.value) === fromISO(today).getDay() - 1 || (fromISO(today).getDay() === 0 && Number(input.value) === 6); });
  routineCancel.hidden = true;
  document.querySelector('#routine-save').textContent = rt('create');
  updateRoutineScheduleFields();
}

function routineFormPayload() {
  const steps = routineSteps.value.split('\n').map(value => value.trim()).filter(Boolean);
  return {
    title: routineTitle.value.trim(),
    start_date: routineStart.value,
    frequency: routineFrequency.value,
    interval_value: Number(routineInterval.value),
    weekdays: [...routineWeekdays.querySelectorAll('input:checked')].map(input => Number(input.value)),
    month_day: routineFrequency.value === 'monthly' ? Number(routineMonthDay.value) : null,
    year_month: routineFrequency.value === 'yearly' ? Number(routineYearMonth.value) : null,
    year_day: routineFrequency.value === 'yearly' ? Number(routineYearDay.value) : null,
    end_mode: routineEndMode.value,
    end_value: routineEndMode.value === 'never' ? null : routineEndValue.value,
    follow_until_complete: routineFollow.checked,
    steps,
  };
}

function routineSummary(routine) {
  const weekdays = language === 'ar' ? ['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد'] : ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  let schedule = rt(routine.frequency);
  if (routine.interval_value > 1) schedule += language === 'ar' ? ` · كل ${routine.interval_value}` : ` · every ${routine.interval_value}`;
  if (routine.frequency === 'weekly') schedule += ` · ${routine.weekdays.map(day => weekdays[day]).join('، ')}`;
  if (routine.frequency === 'monthly') schedule += ` · ${routine.month_day === -1 ? (language === 'ar' ? 'آخر يوم' : 'last day') : routine.month_day}`;
  if (routine.frequency === 'yearly') schedule += ` · ${routine.year_month}/${routine.year_day}`;
  schedule += ` · ${routine.start_date}`;
  if (routine.follow_until_complete) schedule += ` · ${rt('follow')}`;
  if (routine.steps.length) schedule += ` · ${routine.steps.length} ${language === 'ar' ? 'مهام فرعية' : 'subtasks'}`;
  return schedule;
}

function renderRoutines() {
  routineList.innerHTML = '';
  if (!routines.length) routineList.innerHTML = `<p class="history-range">${rt('noRoutines')}</p>`;
  routines.forEach(routine => {
    const card = document.createElement('article');
    card.className = `routine-card${routine.active ? '' : ' paused'}`;
    card.innerHTML = `<div><h3></h3><p></p></div><span class="routine-card-actions"><button type="button" data-routine-edit aria-label="${language === 'ar' ? 'تعديل الروتين' : 'Edit routine'}">✏️</button><button type="button" data-routine-toggle aria-label="${routine.active ? (language === 'ar' ? 'إيقاف مؤقت' : 'Pause') : (language === 'ar' ? 'استئناف' : 'Resume')}">${routine.active ? '⏸️' : '▶️'}</button><button type="button" class="routine-delete" data-routine-delete aria-label="${language === 'ar' ? 'إيقاف الروتين نهائيًا' : 'Stop routine'}">🗑️</button></span>`;
    card.querySelector('h3').textContent = `${routine.title} · ${routine.active ? rt('active') : rt('paused')}`;
    card.querySelector('p').textContent = routineSummary(routine);
    card.querySelector('[data-routine-edit]').addEventListener('click', () => editRoutine(routine));
    card.querySelector('[data-routine-toggle]').addEventListener('click', () => toggleRoutine(routine));
    card.querySelector('[data-routine-delete]').addEventListener('click', () => deleteRoutine(routine));
    routineList.appendChild(card);
  });
  const selected = routineStatsFilter.value;
  routineStatsFilter.innerHTML = `<option value="">${rt('allRoutines')}</option>${routines.map(routine => `<option value="${routine.id}">${escapeHtml(routine.title)}</option>`).join('')}`;
  routineStatsFilter.value = routines.some(routine => String(routine.id) === selected) ? selected : '';
}

async function loadRoutines() {
  try {
    routines = await api('/api/routines');
    renderRoutines();
    if (!routineStats.hidden) await loadRoutineStats();
  } catch (err) { error.textContent = err.message; }
}

function checklistOrderKey() {
  return `taskline-list-order-${workspace}`;
}

function setListsEditing(editing) {
  listsEditing = Boolean(editing);
  listsSection.classList.toggle('editing', listsEditing);
  listsEditToggle.setAttribute('aria-pressed', String(listsEditing));
  listsEditToggle.textContent = lt(listsEditing ? 'doneEditing' : 'editLists');
}

function orderChecklistsForDisplay(source) {
  let savedIds = [];
  try {
    const saved = JSON.parse(localStorage.getItem(checklistOrderKey()) || '[]');
    if (Array.isArray(saved)) savedIds = saved.map(Number);
  } catch { savedIds = []; }
  const byId = new Map(source.map(checklist => [checklist.id, checklist]));
  const ordered = [];
  savedIds.forEach(id => {
    const checklist = byId.get(id);
    if (checklist && !ordered.includes(checklist)) ordered.push(checklist);
  });
  source.forEach(checklist => { if (!ordered.includes(checklist)) ordered.push(checklist); });
  return ordered;
}

function saveChecklistOrder() {
  localStorage.setItem(checklistOrderKey(), JSON.stringify(checklists.map(checklist => checklist.id)));
}

function moveChecklist(index, offset) {
  const target = index + offset;
  if (target < 0 || target >= checklists.length) return;
  [checklists[index], checklists[target]] = [checklists[target], checklists[index]];
  saveChecklistOrder();
  renderLists();
}

function renderLists() {
  listsList.innerHTML = '';
  if (!checklists.length) {
    const message = document.createElement('p');
    message.className = 'history-range lists-empty';
    message.textContent = lt('noLists');
    listsList.appendChild(message);
    return;
  }
  checklists = orderChecklistsForDisplay(checklists);
  checklists.forEach((checklist, index) => {
    const card = document.createElement('article');
    const collapsedKey = `taskline-list-collapsed-${workspace}-${checklist.id}`;
    const collapsed = localStorage.getItem(collapsedKey) === '1';
    card.className = `checklist-card${collapsed ? ' collapsed' : ''}`;
    const completed = checklist.items.filter(item => item.completed).length;
    card.innerHTML = `<header class="checklist-heading"><div><h3></h3><p></p></div><span class="checklist-actions"><button type="button" class="checklist-collapse" data-list-collapse aria-expanded="${!collapsed}" aria-label="${lt(collapsed ? 'expand' : 'collapse')}">${collapsed ? '▸' : '▾'}</button><button type="button" class="list-management-action" data-list-move="up" aria-label="${lt('moveUp')}" ${index === 0 ? 'disabled' : ''}>↑</button><button type="button" class="list-management-action" data-list-move="down" aria-label="${lt('moveDown')}" ${index === checklists.length - 1 ? 'disabled' : ''}>↓</button><button type="button" class="list-management-action" data-list-rename aria-label="${lt('rename')}">✏️</button><button type="button" class="checklist-delete list-management-action" data-list-delete aria-label="${lt('remove')}">🗑️</button></span></header><ul class="checklist-items"></ul><p class="checklist-empty" hidden></p><form class="checklist-item-form"><label class="sr-only">${lt('itemPlaceholder')}</label><input maxlength="280" placeholder="${lt('itemPlaceholder')}" required><button type="submit">${lt('addItem')}</button></form>`;
    card.querySelector('h3').textContent = checklist.title;
    card.querySelector('.checklist-heading p').textContent = `${completed}/${checklist.items.length} ${lt('completed')}`;
    const itemList = card.querySelector('.checklist-items');
    const emptyMessage = card.querySelector('.checklist-empty');
    emptyMessage.textContent = lt('empty');
    emptyMessage.hidden = checklist.items.length !== 0;
    checklist.items.forEach(item => {
      const row = document.createElement('li');
      row.className = item.completed ? 'completed' : '';
      row.innerHTML = `<label><input type="checkbox"><span></span></label><span class="checklist-item-actions"><button type="button" data-item-edit aria-label="${lt('editItem')}">✏️</button><button type="button" data-item-delete aria-label="${lt('removeItem')}">×</button></span>`;
      const checkbox = row.querySelector('input');
      checkbox.checked = Boolean(item.completed);
      row.querySelector('span').textContent = item.title;
      checkbox.addEventListener('change', async () => {
        try {
          await api(`/api/list-items/${item.id}`, { method: 'PUT', body: JSON.stringify({ completed: checkbox.checked }) });
          item.completed = Number(checkbox.checked);
          renderLists();
        } catch (err) { checkbox.checked = !checkbox.checked; error.textContent = err.message; }
      });
      row.querySelector('[data-item-edit]').addEventListener('click', async () => {
        const title = window.prompt(lt('itemPrompt'), item.title)?.trim();
        if (!title || title === item.title) return;
        try {
          await api(`/api/list-items/${item.id}`, { method: 'PUT', body: JSON.stringify({ title }) });
          item.title = title;
          renderLists();
        } catch (err) { error.textContent = err.message; }
      });
      row.querySelector('[data-item-delete]').addEventListener('click', async () => {
        try {
          await api(`/api/list-items/${item.id}`, { method: 'DELETE' });
          await loadLists();
        } catch (err) { error.textContent = err.message; }
      });
      itemList.appendChild(row);
    });
    card.querySelector('[data-list-collapse]').addEventListener('click', event => {
      const isCollapsed = card.classList.toggle('collapsed');
      localStorage.setItem(collapsedKey, isCollapsed ? '1' : '0');
      event.currentTarget.textContent = isCollapsed ? '▸' : '▾';
      event.currentTarget.setAttribute('aria-expanded', String(!isCollapsed));
      event.currentTarget.setAttribute('aria-label', lt(isCollapsed ? 'expand' : 'collapse'));
    });
    card.querySelector('[data-list-move="up"]').addEventListener('click', () => moveChecklist(index, -1));
    card.querySelector('[data-list-move="down"]').addEventListener('click', () => moveChecklist(index, 1));
    card.querySelector('[data-list-rename]').addEventListener('click', async () => {
      const title = window.prompt(lt('renamePrompt'), checklist.title)?.trim();
      if (!title || title === checklist.title) return;
      try {
        await api(`/api/lists/${checklist.id}`, { method: 'PUT', body: JSON.stringify({ title }) });
        await loadLists();
      } catch (err) { error.textContent = err.message; }
    });
    card.querySelector('[data-list-delete]').addEventListener('click', async () => {
      if (!window.confirm(lt('confirmRemove'))) return;
      try {
        await api(`/api/lists/${checklist.id}`, { method: 'DELETE' });
        localStorage.removeItem(collapsedKey);
        checklists = checklists.filter(entry => entry.id !== checklist.id);
        saveChecklistOrder();
        await loadLists();
      } catch (err) { error.textContent = err.message; }
    });
    card.querySelector('.checklist-item-form').addEventListener('submit', async event => {
      event.preventDefault();
      const field = event.currentTarget.querySelector('input');
      if (!field.value.trim()) return;
      try {
        await api(`/api/lists/${checklist.id}/items`, { method: 'POST', body: JSON.stringify({ title: field.value }) });
        await loadLists();
      } catch (err) { error.textContent = err.message; }
    });
    listsList.appendChild(card);
  });
}

async function loadLists() {
  try {
    checklists = await api('/api/lists');
    renderLists();
  } catch (err) { error.textContent = err.message; }
}

function editRoutine(routine) {
  editingRoutine = routine;
  routineId.value = routine.id;
  routineTitle.value = routine.title;
  routineStart.value = routine.start_date;
  routineFrequency.value = routine.frequency;
  routineInterval.value = routine.interval_value;
  routineWeekdays.querySelectorAll('input').forEach(input => { input.checked = routine.weekdays.includes(Number(input.value)); });
  routineMonthDay.value = String(routine.month_day ?? 1);
  routineYearMonth.value = String(routine.year_month ?? 1);
  routineYearDay.value = String(routine.year_day ?? 1);
  routineEndMode.value = routine.end_mode;
  routineEndValue.value = routine.end_value || '';
  routineFollow.checked = Boolean(routine.follow_until_complete);
  routineSteps.value = routine.steps.join('\n');
  routineCancel.hidden = false;
  document.querySelector('#routine-save').textContent = rt('update');
  updateRoutineScheduleFields();
  routineForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
  routineTitle.focus();
}

async function toggleRoutine(routine) {
  try {
    await api(`/api/routines/${routine.id}`, { method: 'PUT', body: JSON.stringify({ active: !Boolean(routine.active) }) });
    await Promise.all([loadRoutines(), loadTasks(), loadActiveDays(), loadOverdue()]);
  } catch (err) { error.textContent = err.message; }
}

async function deleteRoutine(routine) {
  const message = language === 'ar' ? `إيقاف «${routine.title}» وحذف مواعيده القادمة؟ سيبقى السجل السابق.` : `Stop “${routine.title}” and remove upcoming occurrences? Past history will remain.`;
  if (!window.confirm(message)) return;
  try {
    await api(`/api/routines/${routine.id}`, { method: 'DELETE' });
    await Promise.all([loadRoutines(), loadActiveDays(), loadOverdue()]);
  } catch (err) { error.textContent = err.message; }
}

async function prepareRoutineFromTask(task) {
  const sourceTasks = [...tasks];
  await setView('routines');
  resetRoutineForm();
  routineTitle.value = task.title;
  routineStart.value = task.task_date < today ? today : task.task_date;
  routineSteps.value = sourceTasks.filter(entry => entry.parent_id === task.id).map(entry => entry.title).join('\n');
  routineFollow.checked = false;
  routineTitle.focus();
}

let routineChartState = null;

function drawRoutineChart(result) {
  const metric = routineStatsMetric.value;
  const container = routineChart.parentElement;
  const width = Math.max(280, container.clientWidth);
  const height = 220;
  const scale = window.devicePixelRatio || 1;
  routineChart.width = width * scale;
  routineChart.height = height * scale;
  const context = routineChart.getContext('2d');
  context.scale(scale, scale);
  context.clearRect(0, 0, width, height);
  const padding = { left: 34, right: 12, top: 18, bottom: 28 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const values = result.points.map(point => metric === 'percentage' ? point.percentage : point.completed);
  const drawable = result.points.map((point, index) => ({ point, index, value: values[index] })).filter(item => item.value !== null);
  const maxValue = metric === 'percentage' ? 100 : Math.max(1, ...values.filter(value => value !== null));
  context.strokeStyle = '#dcddd6'; context.lineWidth = 1; context.fillStyle = '#718078'; context.font = '10px DM Sans, sans-serif';
  [0, .5, 1].forEach(ratio => {
    const y = padding.top + chartHeight * (1 - ratio);
    context.beginPath(); context.moveTo(padding.left, y); context.lineTo(width - padding.right, y); context.stroke();
    context.fillText(String(Math.round(maxValue * ratio)), 3, y + 3);
  });
  const xFor = index => padding.left + (result.points.length === 1 ? chartWidth / 2 : chartWidth * index / (result.points.length - 1));
  const yFor = value => padding.top + chartHeight * (1 - value / maxValue);
  context.strokeStyle = '#28553f'; context.lineWidth = 2.5; context.lineJoin = 'round'; context.lineCap = 'round';
  context.beginPath();
  drawable.forEach((item, index) => { const x = xFor(item.index); const y = yFor(item.value); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y); });
  context.stroke();
  if (drawable.length <= 31) {
    context.fillStyle = '#ee7049';
    drawable.forEach(item => { context.beginPath(); context.arc(xFor(item.index), yFor(item.value), 3.5, 0, Math.PI * 2); context.fill(); });
  }
  context.fillStyle = '#718078';
  context.fillText(result.start, padding.left, height - 7);
  const endWidth = context.measureText(result.end).width;
  context.fillText(result.end, width - padding.right - endWidth, height - 7);
  routineChartState = { result, xFor, width };
  const totals = result.points.reduce((sum, point) => ({ completed: sum.completed + point.completed, scheduled: sum.scheduled + point.scheduled }), { completed: 0, scheduled: 0 });
  const percentage = totals.scheduled ? Math.round(totals.completed * 100 / totals.scheduled) : 0;
  document.querySelector('#routine-chart-summary').textContent = language === 'ar' ? `${totals.completed} من ${totals.scheduled} مكتملة · ${percentage}%` : `${totals.completed} of ${totals.scheduled} completed · ${percentage}%`;
  routineChart.setAttribute('aria-label', document.querySelector('#routine-chart-summary').textContent);
}

async function loadRoutineStats() {
  try {
    const filter = routineStatsFilter.value ? `&routine_id=${routineStatsFilter.value}` : '';
    const result = await api(`/api/routines/stats?days=${routineStatsPeriod.value}${filter}`);
    drawRoutineChart(result);
  } catch (err) { error.textContent = err.message; }
}

navToday.addEventListener('click', () => { currentDate = today; setView('day'); });
navInbox.addEventListener('click', async () => { await setView('inbox'); setInboxSubView('inbox'); });
navRoutines.addEventListener('click', () => setView('routines'));
navLists.addEventListener('click', () => setView('lists'));
listsEditToggle.addEventListener('click', () => setListsEditing(!listsEditing));
listForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!listTitle.value.trim()) return;
  try {
    await api('/api/lists', { method: 'POST', body: JSON.stringify({ title: listTitle.value }) });
    listTitle.value = '';
    await loadLists();
    announcer.textContent = language === 'ar' ? 'تم إنشاء القائمة.' : 'List created.';
  } catch (err) { error.textContent = err.message; }
});
labelForm.addEventListener('submit', event => {
  event.preventDefault();
  const color = labelForm.querySelector('[name="label-color"]:checked').value;
  saveLabel(labelName.value.trim(), color);
});
labelSuggestions.addEventListener('click', event => {
  const choice = event.target.closest('[data-saved-label]');
  if (!choice) return;
  labelName.value = choice.dataset.savedLabel;
  const color = labelForm.querySelector(`[name="label-color"][value="${choice.dataset.savedColor}"]`);
  if (color) color.checked = true;
  renderLabelSuggestions();
});
labelName.addEventListener('input', renderLabelSuggestions);
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
workspaceToggle.addEventListener('click', async () => {
  workspace = workspace === 'personal' ? 'work' : 'personal';
  localStorage.setItem('taskline-workspace', workspace);
  today = effectiveToday();
  currentDate = today;
  activeLabel = '';
  savedLabels = [];
  applyWorkspace();
  await setView('day');
  await Promise.all([loadActiveDays(), loadSavedLabels()]);
  announcer.textContent = workspace === 'work'
    ? (language === 'ar' ? 'تم فتح مساحة العمل.' : 'Work space opened.')
    : (language === 'ar' ? 'تم فتح المساحة الشخصية.' : 'Personal space opened.');
});
const monthCodes = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
for (let year = fromISO(today).getFullYear(); year <= fromISO(today).getFullYear() + 30; year += 1) {
  [planningYear, editPlanYear, document.querySelector('#dream-year')].forEach(select => select.add(new Option(String(year), String(year))));
}
monthCodes.forEach((month, index) => {
  planningMonth.add(new Option(month, month)); editPlanMonth.add(new Option(month, month));
});
for (let day = 1; day <= 31; day += 1) {
  routineMonthDay.add(new Option(String(day), String(day)));
  routineYearDay.add(new Option(String(day), String(day)));
}
routineMonthDay.add(new Option('Last day', '-1'));
for (let month = 1; month <= 12; month += 1) routineYearMonth.add(new Option(String(month), String(month)));
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
routineFrequency.addEventListener('change', updateRoutineScheduleFields);
routineEndMode.addEventListener('change', updateRoutineScheduleFields);
routineStart.addEventListener('change', updateRoutineScheduleFields);
routineCancel.addEventListener('click', resetRoutineForm);
routineForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!routineTitle.value.trim() || !routineStart.value) return;
  try {
    const target = editingRoutine ? `/api/routines/${editingRoutine.id}` : '/api/routines';
    const method = editingRoutine ? 'PUT' : 'POST';
    await api(target, { method, body: JSON.stringify(routineFormPayload()) });
    resetRoutineForm();
    await Promise.all([loadRoutines(), loadTasks(), loadActiveDays(), loadOverdue()]);
    announcer.textContent = language === 'ar' ? 'تم حفظ الروتين.' : 'Routine saved.';
  } catch (err) { error.textContent = err.message; }
});
routineStatsMetric.value = localStorage.getItem('taskline-routine-chart-metric') || 'percentage';
routineStatsPeriod.value = localStorage.getItem('taskline-routine-chart-period') || '30';
routineStatsToggle.addEventListener('click', async () => {
  routineStats.hidden = !routineStats.hidden;
  routineStatsToggle.setAttribute('aria-expanded', String(!routineStats.hidden));
  if (!routineStats.hidden) await loadRoutineStats();
});
routineStatsMetric.addEventListener('change', () => { localStorage.setItem('taskline-routine-chart-metric', routineStatsMetric.value); loadRoutineStats(); });
routineStatsPeriod.addEventListener('change', () => { localStorage.setItem('taskline-routine-chart-period', routineStatsPeriod.value); loadRoutineStats(); });
routineStatsFilter.addEventListener('change', loadRoutineStats);
routineChart.addEventListener('click', event => {
  if (!routineChartState) return;
  const rect = routineChart.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const points = routineChartState.result.points;
  let nearest = 0;
  let distance = Infinity;
  points.forEach((point, index) => { const nextDistance = Math.abs(routineChartState.xFor(index) - x); if (nextDistance < distance) { distance = nextDistance; nearest = index; } });
  const point = points[nearest];
  document.querySelector('#routine-chart-summary').textContent = language === 'ar'
    ? `${point.date}: ${point.completed} من ${point.scheduled} · ${point.percentage === null ? '—' : `${point.percentage}%`}`
    : `${point.date}: ${point.completed} of ${point.scheduled} · ${point.percentage === null ? '—' : `${point.percentage}%`}`;
});
window.addEventListener('resize', () => { if (currentView === 'routines' && !routineStats.hidden) loadRoutineStats(); });
document.addEventListener('visibilitychange', async () => {
  if (!document.hidden && syncLocalToday()) {
    renderCalendar();
    await Promise.all([loadTasks(), loadActiveDays(), loadOverdue()]);
  }
});
setInterval(async () => {
  if (syncLocalToday()) {
    renderCalendar();
    await Promise.all([loadTasks(), loadActiveDays(), loadOverdue()]);
  }
}, 60_000);

resetRoutineForm();
renderCalendar();
setupPwa();
applyLanguage();
Promise.all([loadTasks(), loadActiveDays(), loadOverdue()]);
