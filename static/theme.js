/* Run before styles/paint so a saved dark preference never flashes light. */
(() => {
  const key = 'taskline-theme';
  const root = document.documentElement;
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const read = name => {
    try { return TasklineStorage.getItem(name); } catch { return null; }
  };
  const valid = value => value === 'dark' || value === 'light';
  let preference = read(key);
  let workspace = read('taskline-workspace') === 'work' ? 'work' : 'personal';

  function refresh() {
    const dark = valid(preference) ? preference === 'dark' : system.matches;
    root.dataset.theme = dark ? 'dark' : 'light';
    root.dataset.workspace = workspace;
    root.style.colorScheme = dark ? 'dark' : 'light';
    document.querySelector('meta[name="color-scheme"]').content = dark ? 'dark' : 'light';
    document.querySelector('meta[name="theme-color"]').content = dark
      ? (workspace === 'work' ? '#141b24' : '#111a18')
      : (workspace === 'work' ? '#355b7d' : '#28553f');
    const button = document.querySelector('#theme-toggle');
    if (button) {
      const arabic = root.lang === 'ar';
      const label = arabic ? 'الوضع الداكن' : 'Dark mode';
      button.setAttribute('aria-label', label);
      button.setAttribute('aria-pressed', String(dark));
      button.title = arabic
        ? (dark ? 'التبديل إلى الوضع الفاتح' : 'التبديل إلى الوضع الداكن')
        : (dark ? 'Switch to light mode' : 'Switch to dark mode');
    }
    window.dispatchEvent(new Event('taskline-theme-change'));
  }

  window.TasklineTheme = {
    refresh,
    reload() { preference = read(key); workspace = read('taskline-workspace') === 'work' ? 'work' : 'personal'; refresh(); },
    preference() { return valid(preference) ? preference : 'system'; },
    setPreference(value) {
      preference = valid(value) ? value : null;
      try {
        if (preference) TasklineStorage.setItem(key, preference);
        else TasklineStorage.removeItem(key);
      } catch { /* Appearance still works when storage is unavailable. */ }
      refresh();
    },
    setWorkspace(value) {
      workspace = value === 'work' ? 'work' : 'personal';
      refresh();
    },
    toggle() {
      preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { TasklineStorage.setItem(key, preference); } catch { /* Still usable without storage. */ }
      refresh();
    },
  };
  system.addEventListener('change', () => { if (!valid(preference)) refresh(); });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key?.endsWith(':' + key) || event.key === null) {
      preference = read(key);
      refresh();
    }
  });
  refresh();
})();
