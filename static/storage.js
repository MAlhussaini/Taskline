/* Device preferences are namespaced per account; no session tokens are stored here. */
window.TasklineStorage = (() => {
  const memory = new Map();
  const read = key => { try { return localStorage.getItem(key); } catch { return memory.get(key) ?? null; } };
  const write = (key,value) => { memory.set(key,String(value)); try { localStorage.setItem(key,value); } catch {} };
  const remove = key => { memory.delete(key); try { localStorage.removeItem(key); } catch {} };
  let account = read('taskline-active-account') || 'guest';
  const prefix = () => `account:${account}:`;
  return {
    getItem(key) { return read(prefix() + key); },
    setItem(key, value) { write(prefix() + key, value); if (key === 'taskline-language') window.TasklineSavePreferences?.({language:value}); if (key === 'taskline-theme') window.TasklineSavePreferences?.({theme:value}); },
    removeItem(key) { remove(prefix() + key); if (key === 'taskline-theme') window.TasklineSavePreferences?.({theme:'system'}); },
    use(user) {
      account = String(user.id);
      write('taskline-active-account', account);
      if (user.is_owner && !read(prefix() + 'migrated')) {
        try { Object.keys(localStorage).filter(key => key.startsWith('taskline-') && !['taskline-active-account','taskline-session-change'].includes(key))
          .forEach(key => { if (read(prefix() + key) === null) write(prefix() + key, read(key)); }); } catch {}
        write(prefix() + 'migrated','1');
      }
      if (user.preferences.language) this.setItem('taskline-language', user.preferences.language);
      if (user.preferences.theme) {
        if (user.preferences.theme === 'system') this.removeItem('taskline-theme');
        else this.setItem('taskline-theme', user.preferences.theme);
      }
    },
  };
})();
