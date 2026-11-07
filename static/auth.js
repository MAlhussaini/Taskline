/* Load the existing app only after local session validation. */
(async () => {
  try {
    const response = await fetch('/api/auth/status', {cache:'no-store'});
    if (!response.ok) throw new Error('تعذر الاتصال بالخادم المحلي. أعد المحاولة.');
    const status = await response.json();
    if (!status.user) { location.replace('/account.html'); return; }
    window.TasklineAccount = status.user;
    TasklineStorage.use(status.user);
    let preferenceWrites = Promise.resolve();
    window.TasklineSavePreferences = patch => {
      TasklineAccount.preferences = {...TasklineAccount.preferences, ...patch};
      const preferences = {...TasklineAccount.preferences};
      preferenceWrites = preferenceWrites.then(async () => {
        const result = await fetch('/api/auth/profile', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...TasklineAccount, preferences})});
        if (!result.ok) throw new Error('تعذر حفظ إعدادات الحساب.');
      }).catch(error => { document.getElementById('form-error').textContent=error.message; });
    };
    TasklineTheme.reload();
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (resource, options = {}) => {
      const url = new URL(typeof resource === 'string' ? resource : resource.url, location.href);
      if (url.origin === location.origin && url.pathname.startsWith('/api/')) {
        const headers = new Headers(options.headers);
        headers.set('X-Taskline-Account', String(TasklineAccount.id));
        options = {...options, headers};
      }
      const result = await nativeFetch(resource, options);
      if (url.origin === location.origin && (result.status === 401 || result.status === 409)) location.replace('/account.html');
      return result;
    };
    const script = document.createElement('script');
    script.src = '/app.js?v=30';
    script.onload = () => document.documentElement.classList.remove('auth-pending');
    document.body.appendChild(script);
  } catch (error) {
    document.getElementById('auth-loading').textContent = error.message;
  }
})();
window.addEventListener('storage', event => { if (event.key === 'taskline-session-change') location.reload(); });
window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
