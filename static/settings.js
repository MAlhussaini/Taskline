/* Shared feature preferences; appearance/language remain device preferences. */
window.TasklineSettings = (() => {
  let values = { features: {}, dayStart: { personal: 180, work: 0 }, footer: ['settings', 'inbox', 'day', 'routines', 'lists'] };
  let catalog = [];
  let loaded = false;
  let busy = false;
  let message = '';
  let failed = false;
  let generation = 0;
  const icons = { day: '☑', inbox: '📥', routines: '🔁', lists: '📋', settings: '⚙', dreams: '✨', planned: '🗓' };
  const words = (ar, en) => language === 'ar' ? ar : en;
  const names = key => ({ day: t('today'), inbox: t('inbox'), settings: t('settings'), routines: rt('routines'), lists: lt('lists'), dreams: t('dreams'), planned: t('planned'), none: words('فارغة', 'Empty') })[key];
  const enabled = id => {
    const feature = catalog.find(item => item.id === id);
    return values.features[id] !== false && (!feature?.requires || enabled(feature.requires));
  };
  const available = id => Object.hasOwn(icons, id) && (id === 'day' || id === 'settings' || enabled(id));
  const navId = id => id === 'day' ? 'nav-today' : `nav-${id}`;

  function renderFooter() {
    const nav = document.querySelector('.bottom-nav');
    Object.keys(icons).forEach(id => {
      const button = document.getElementById(navId(id));
      button.hidden = true;
      button.classList.remove('active');
      button.removeAttribute('aria-current');
      button.lastChild.textContent = names(id);
    });
    values.footer.forEach((id, index) => {
      if (!available(id)) return;
      const button = document.getElementById(navId(id));
      button.hidden = false;
      button.style.gridArea = 'auto';
      button.style.gridColumn = String(index + 1);
      button.style.gridRow = '1';
      nav.appendChild(button); // Keyboard order follows the visual left-to-right slots.
      const active = currentView === id && !(id === 'inbox' && inboxSubView !== 'inbox')
        || currentView === 'inbox' && (id === 'dreams' && inboxSubView === 'dreams' || id === 'planned' && inboxSubView === 'history');
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
    });
    document.querySelector('#settings-open').title = t('settings');
    document.querySelector('#settings-open').setAttribute('aria-label', t('settings'));
  }

  function renderSettings() {
    const section = document.querySelector('#settings-section');
    const focus = section.contains(document.activeElement) ? document.activeElement.id : '';
    const openGroups = new Set([...section.querySelectorAll('details[open]')].map(el => el.dataset.group));
    const field = (id, title, control, help = '') => `<label class="setting-field" for="${id}"><span>${title}</span>${control}${help ? `<small>${help}</small>` : ''}</label>`;
    const groups = { spaces: words('المساحات والصفحات', 'Spaces and pages'), tasks: words('أدوات المهام', 'Task tools'), planning: words('التخطيط والروتين', 'Planning and routines'), display: words('العرض والاختصارات', 'Display and shortcuts') };
    const status = busy ? words('جارٍ الحفظ…', 'Saving…') : message;
    section.innerHTML = `
      <section class="settings-card"><h2>${words('الحساب', 'Account')}</h2><a href="/account.html">${words('الملف الشخصي، الجلسات وتسجيل الخروج', 'Profile, sessions and sign out')}</a></section>
      <p class="settings-note">${words('الميزات والفوتر وبداية اليوم محفوظة على الخادم ومشتركة بين أجهزتك والمساحتين. الإيقاف يبسط الواجهة ولا يحذف بياناتك. إضافة المهام وتعديلها وإنجازها وحذفها وحفظها تبقى متاحة دائمًا.', 'Features, footer and day boundaries are saved on the server, shared across devices and spaces. Turning features off simplifies the interface without deleting data. Creating, editing, completing, deleting and saving tasks always remain available.')}</p>
      <p id="settings-status" class="settings-status ${failed ? 'error' : ''}" role="${failed ? 'alert' : 'status'}">${escapeHtml(status)}</p>
      ${!loaded ? `<button type="button" id="settings-retry">${words('إعادة تحميل الإعدادات', 'Reload settings')}</button>` : ''}
      <section class="settings-card"><h2>${words('المظهر واللغة', 'Appearance and language')}</h2><p>${words('اختيارات خاصة بهذا المتصفح أو التطبيق المثبت.', 'Preferences for this browser or installed app.')}</p><div class="settings-fields">
        ${field('settings-theme', words('المظهر', 'Appearance'), `<select id="settings-theme"><option value="system">${words('حسب الجهاز', 'System')}</option><option value="light">${words('فاتح', 'Light')}</option><option value="dark">${words('داكن', 'Dark')}</option></select>`)}
        ${field('settings-language', words('اللغة', 'Language'), '<select id="settings-language"><option value="ar">العربية</option><option value="en">English</option></select>')}
      </div></section>
      <fieldset class="settings-shared" ${busy || !loaded ? 'disabled' : ''}><legend class="sr-only">${words('الإعدادات المشتركة', 'Shared settings')}</legend>
      <section class="settings-card"><h2>${words('بداية اليوم', 'Day boundaries')}</h2><p>${words('بداية ونهاية كل يوم بتوقيت جهازك. يسري على «اليوم» والأرشفة التالية، دون نقل المهام أو الأرشيف السابق.', 'Each day starts and ends at this local time. Applies to Today and future archive actions; existing task dates and archives are not moved.')}</p><div class="settings-fields">
        ${['personal', 'work'].map(space => field(`settings-day-${space}`, space === 'personal' ? words('المنزل', 'Personal') : words('العمل', 'Work'), `<input id="settings-day-${space}" type="time" step="60" required data-day-start="${space}" value="${String(Math.floor(values.dayStart[space] / 60)).padStart(2, '0')}:${String(values.dayStart[space] % 60).padStart(2, '0')}">`)).join('')}
      </div></section>
      <section class="settings-card"><h2>${words('الميزات الاختيارية', 'Optional features')}</h2><p>${words('الخيارات التابعة تتوقف مع ميزتها الأساسية، وتعود لاختيارك السابق عند تشغيلها مجددًا.', 'Dependent options pause with their parent feature and remember your previous choice when re-enabled.')}</p>
        ${Object.entries(groups).map(([group, title]) => `<details class="settings-group" data-group="${group}" ${openGroups.has(group) ? 'open' : ''}><summary>${title}<span>${catalog.filter(f => f.group === group && enabled(f.id)).length}/${catalog.filter(f => f.group === group).length}</span></summary>${catalog.filter(f => f.group === group).map(f => {
          const blocked = f.requires && !enabled(f.requires);
          const parent = catalog.find(item => item.id === f.requires);
          return `<label class="setting-switch ${blocked ? 'setting-dependent' : ''}" for="feature-${f.id}"><span><strong>${escapeHtml(f.name[language])}</strong><small>${escapeHtml(f.help[language])}${blocked ? `<br>${words('يتطلب تفعيل: ', 'Requires: ')}${escapeHtml(parent.name[language])}` : ''}</small></span><input id="feature-${f.id}" data-feature="${f.id}" type="checkbox" role="switch" ${enabled(f.id) ? 'checked' : ''} ${blocked ? 'disabled' : ''}></label>`;
        }).join('')}</details>`).join('')}
      </section>
      <section class="settings-card"><h2>${words('شريط التنقل السفلي', 'Bottom navigation')}</h2><p>${words('اختر محتوى الخانات الأربع من اليسار إلى اليمين. «اليوم» ثابت في الوسط. اختيار صفحة مستخدمة يبدّل مكانها مع الخانة الحالية، و«فارغة» يخفي الخانة. الميزة المتوقفة تُخفى دون نسيان مكانها.', 'Choose the four slots from left to right. Today is fixed in the center. Selecting an existing destination swaps slots; Empty hides a slot. Disabled features are hidden without forgetting their position.')}</p>
        <div class="footer-preview" aria-label="${words('معاينة الفوتر', 'Footer preview')}">${values.footer.map(id => `<span ${id === 'day' ? 'class="fixed-today"' : ''}>${available(id) ? `${icons[id]}<small>${names(id)}</small>` : '—'}</span>`).join('')}</div>
        <div class="settings-fields">${[0, 1, 3, 4].map((slot, index) => field(`footer-slot-${slot}`, [words('أقصى اليسار', 'Far left'), words('يسار اليوم', 'Left of Today'), words('يمين اليوم', 'Right of Today'), words('أقصى اليمين', 'Far right')][index], `<select id="footer-slot-${slot}" data-footer-slot="${slot}">${['none', 'settings', 'inbox', 'routines', 'lists', 'dreams', 'planned'].map(id => `<option value="${id}" ${values.footer[slot] === id ? 'selected' : ''} ${id !== 'none' && !available(id) ? 'disabled' : ''}>${names(id)}${id !== 'none' && !available(id) ? words(' (متوقفة)', ' (disabled)') : ''}</option>`).join('')}</select>`)).join('')}</div>
      </section></fieldset>
      <section class="settings-card"><h2>${words('انتقال سريع', 'Quick navigation')}</h2><p>${words('كل الصفحات المفعّلة متاحة هنا، حتى إن لم تضعها في الفوتر. زر ⚙ أعلى الشاشة يفتح الإعدادات دائمًا.', 'Every enabled page is available here, even if removed from the footer. The header ⚙ always opens Settings.')}</p><div class="settings-links">${['day', 'inbox', 'routines', 'lists', 'dreams', 'planned'].filter(available).map(id => `<button type="button" data-settings-go="${id}">${icons[id]} ${names(id)}</button>`).join('')}</div></section>
      <section class="settings-card settings-future"><h2>${words('التحفيز والألعاب — لاحقًا', 'Gamification — later')}</h2><p>${words('EXP وإنجازات وفتح الميزات تدريجيًا: مرحلة لاحقة اختيارية من الإعدادات. غير مفعّلة حاليًا، ولا تقفل أي ميزة لديك.', 'XP, achievements and gradual feature unlocks will be an optional later stage in Settings. Not active now; none of your features are locked.')}</p><label class="setting-switch"><span>${words('التحفيز (غير متاح بعد)', 'Gamification (not yet available)')}</span><input type="checkbox" role="switch" disabled></label></section>`;
    document.querySelector('#settings-theme').value = TasklineTheme.preference();
    document.querySelector('#settings-language').value = language;
    if (focus) document.getElementById(focus)?.focus({ preventScroll: true });
  }

  // Only presentation settings are cached; account data still requires a live session.
  function restorePresentation() {
    try {
      const cached = JSON.parse(TasklineStorage.getItem('taskline-shell-settings'));
      if (!cached?.settings?.features || !cached.settings.dayStart || !Array.isArray(cached.settings.footer) || !Array.isArray(cached.catalog)) return;
      values = cached.settings;
      catalog = cached.catalog;
    } catch { /* Corrupt or unavailable storage uses the default shell. */ }
  }
  function cachePresentation() {
    TasklineStorage.setItem('taskline-shell-settings', JSON.stringify({settings: values, catalog}));
  }
  restorePresentation();

  async function load({ initial = false } = {}) {
    if (busy) return;
    const request = ++generation;
    try {
      const payload = await api('/api/settings');
      if (request !== generation) return;
      const changed = JSON.stringify(values) !== JSON.stringify(payload.settings);
      values = payload.settings;
      catalog = payload.catalog;
      loaded = true;
      cachePresentation();
      if (failed) message = '';
      failed = false;
      if (changed && !initial) await applyFeatureSettings();
    } catch {
      if (request !== generation) return;
      failed = true;
      message = words('تعذر تحميل الإعدادات. تحقق من الاتصال ثم أعد المحاولة.', 'Could not load settings. Check your connection and retry.');
      if (initial) throw new Error(message);
    }
    if (currentView === 'settings') renderSettings();
  }

  async function save(patch) {
    if (busy || !loaded) return;
    ++generation;
    const focus = document.activeElement.id;
    busy = true;
    failed = false;
    renderSettings();
    try {
      const payload = await api('/api/settings', { method: 'PUT', body: JSON.stringify(patch) });
      values = payload.settings;
      catalog = payload.catalog;
      cachePresentation();
      await applyFeatureSettings();
      message = words('تم حفظ الإعدادات.', 'Settings saved.');
    } catch {
      failed = true;
      message = words('لم يتم الحفظ. بقيت إعداداتك السابقة؛ تحقق من الاتصال وحاول مجددًا.', 'Not saved. Your previous settings remain; check your connection and try again.');
    } finally {
      busy = false;
      renderSettings();
      if (currentView === 'settings') document.getElementById(focus)?.focus({ preventScroll: true });
    }
  }

  async function go(destination) {
    if (!available(destination)) return;
    if (destination === 'dreams' || destination === 'planned') {
      await setView('inbox');
      await setInboxSubView(destination === 'planned' ? 'history' : 'dreams');
    } else {
      if (destination === 'day') currentDate = today;
      await setView(destination);
      if (destination === 'inbox') await setInboxSubView('inbox');
    }
    window.scrollTo(0, 0);
  }

  function init() {
    document.querySelector('#settings-open').addEventListener('click', () => go('settings'));
    document.querySelector('#nav-settings').addEventListener('click', () => go('settings'));
    ['dreams', 'planned'].forEach(id => document.getElementById(navId(id)).addEventListener('click', () => go(id)));
    document.querySelector('#settings-section').addEventListener('click', event => {
      const target = event.target.closest('[data-settings-go]');
      if (target) go(target.dataset.settingsGo);
      if (event.target.closest('#settings-retry')) load();
    });
    document.querySelector('#settings-section').addEventListener('change', event => {
      const target = event.target;
      if (target.dataset.feature) save({ features: { [target.dataset.feature]: target.checked } });
      if (target.dataset.dayStart) {
        if (!target.value || !target.validity.valid) { renderSettings(); return; }
        const [hour, minute] = target.value.split(':').map(Number);
        save({ dayStart: { [target.dataset.dayStart]: hour * 60 + minute } });
      }
      if (target.dataset.footerSlot) {
        const footer = [...values.footer];
        const slot = Number(target.dataset.footerSlot);
        const previousSlot = footer.indexOf(target.value);
        if (target.value !== 'none' && previousSlot !== -1) footer[previousSlot] = footer[slot];
        footer[slot] = target.value;
        save({ footer });
      }
      if (target.id === 'settings-theme') TasklineTheme.setPreference(target.value);
      if (target.id === 'settings-language') {
        language = target.value;
        TasklineStorage.setItem('taskline-language', language);
        applyLanguage();
      }
    });
    window.addEventListener('taskline-theme-change', () => {
      const selector = document.querySelector('#settings-theme');
      if (selector) selector.value = TasklineTheme.preference();
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
    window.addEventListener('focus', () => load());
  }
  return { enabled, available, renderFooter, render: renderSettings, load, save, init, go,
    get values() { return values; }, get catalog() { return catalog; } };
})();
