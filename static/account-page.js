let currentUser = null;
let authMode = 'login';
let setupTokenRequired = false;
let registrationEnabled = true;
const statusBox = document.querySelector('#account-status');
const showMessage = (text, error = false) => { statusBox.textContent = text; statusBox.classList.toggle('error',error); };
const changedSession = () => { try { localStorage.setItem('taskline-session-change',String(Date.now())); } catch {} };
const savedPreference = key => { try { return localStorage.getItem(key); } catch { return null; } };
const fields = form => Object.fromEntries(new FormData(form));

async function request(path, method='GET', data) {
  const headers = {'Content-Type':'application/json'};
  if (currentUser) headers['X-Taskline-Account'] = String(currentUser.id);
  const response = await fetch(path,{method,headers,body:data === undefined ? undefined : JSON.stringify(data),cache:'no-store'});
  const result = await response.json();
  if (!response.ok) {
    if (currentUser && (response.status === 401 || response.status === 409)) location.reload();
    throw new Error(result.error || 'تعذر حفظ التغيير');
  }
  return result;
}
async function action(button, work) {
  button.disabled = true;
  showMessage('جارٍ التنفيذ…');
  try { await work(); } catch (error) { showMessage(error.message,true); }
  finally { button.disabled=false; }
}
function setAuthMode(mode) {
  authMode = mode;
  const form = document.querySelector('#auth-form');
  document.querySelector('#auth-title').textContent = mode === 'setup' ? 'تفعيل حساب المالك / Activate owner' : mode === 'register' ? 'حساب جديد / Register' : 'تسجيل الدخول / Sign in';
  form.elements.password.minLength = mode === 'login' ? 1 : 6;
  form.elements.password.autocomplete = mode === 'login' ? 'current-password' : 'new-password';
  document.querySelector('#password-help').hidden = mode === 'login';
  document.querySelector('#setup-token-label').hidden = mode !== 'setup' || !setupTokenRequired;
  form.elements.setup_token.required = mode === 'setup' && setupTokenRequired;
  document.querySelector('#auth-toggle').hidden = mode === 'setup' || !registrationEnabled;
  document.querySelector('#auth-toggle').textContent = mode === 'login' ? 'إنشاء حساب / Register' : 'لدي حساب / Sign in';
}
document.querySelector('#auth-toggle').onclick = () => setAuthMode(authMode === 'login' ? 'register' : 'login');
document.querySelector('#auth-form').onsubmit = event => {
  event.preventDefault();
  action(event.submitter || event.target.querySelector('[type=submit]'),async () => {
    await request(`/api/auth/${authMode}`,'POST',fields(event.target));
    changedSession();
    location.replace('/');
  });
};
document.querySelector('#logout').onclick = event => action(event.target,async () => {
  await request('/api/auth/logout','POST',{}); changedSession(); location.replace('/account.html');
});
document.querySelector('#profile-form').onsubmit = event => {
  event.preventDefault();
  action(event.submitter || event.target.querySelector('[type=submit]'),async () => {
    const data=fields(event.target);
    data.preferences={language:data.language,theme:data.theme};
    const result=await request('/api/auth/profile','PUT',data);
    currentUser=result.user;
    event.target.elements.current_password.value='';
    event.target.elements.new_password.value='';
    try {
      localStorage.setItem(`account:${currentUser.id}:taskline-language`,data.language);
      if (data.theme==='system') localStorage.removeItem(`account:${currentUser.id}:taskline-theme`);
      else localStorage.setItem(`account:${currentUser.id}:taskline-theme`,data.theme);
    } catch {}
    changedSession();
    showMessage('تم حفظ الملف الشخصي والإعدادات.');
    await loadSessions();
  });
};
function row(container, title, detail='') {
  const item=document.createElement('div'); item.className='row';
  const label=document.createElement('span'); label.textContent=title;
  const small=document.createElement('small'); small.textContent=detail;
  label.appendChild(small); item.appendChild(label); container.appendChild(item); return item;
}
function button(parent, title, callback) {
  const control=document.createElement('button');control.type='button';control.textContent=title;control.className='secondary';
  control.onclick=()=>action(control,callback);parent.appendChild(control);return control;
}
function restorePassword() {
  return new Promise(resolve => {
    const dialog=document.createElement('dialog');
    dialog.innerHTML='<form method="dialog"><label>كلمة مرور المالك لتأكيد الاستعادة<input type="password" autocomplete="current-password" required></label><button value="restore">استعادة</button><button value="cancel" formnovalidate class="secondary">إلغاء</button></form>';
    dialog.addEventListener('close',()=>{const value=dialog.returnValue==='restore'?dialog.querySelector('input').value:null;dialog.remove();resolve(value);},{once:true});
    document.body.appendChild(dialog);dialog.showModal();
  });
}
async function loadSessions() {
  const container=document.querySelector('#sessions');container.replaceChildren();
  for (const session of await request('/api/auth/sessions')) {
    const item=row(container,session.current?'هذا الجهاز / Current device':'جهاز مسجّل',`${session.user_agent} · ${session.last_used}`);
    button(item,'إنهاء الجلسة',async () => {
      await request(`/api/auth/sessions/${session.id}`,'DELETE');
      if (session.current) { changedSession();location.reload(); } else { await loadSessions();showMessage('تم إلغاء الجلسة.'); }
    });
  }
}
function editUser(user) {
  const form=document.querySelector('#user-form');form.reset();
  for (const key of ['id','full_name','nickname','email','role']) form.elements[key].value=user[key];
  form.elements.active.value=String(Boolean(user.active));
  form.elements.role.disabled=Boolean(user.is_owner);
  form.elements.active.disabled=Boolean(user.is_owner);
  form.closest('details').open=true;form.scrollIntoView({block:'center',behavior:'smooth'});
}
async function loadUsers() {
  const container=document.querySelector('#user-list');container.replaceChildren();
  for (const user of await request('/api/admin/users')) {
    const item=row(container,user.full_name,`${user.email} · ${user.role} · ${user.active?'نشط':'معطّل'}`);
    if (!user.is_owner || currentUser.is_owner) button(item,'تعديل',async () => { editUser(user);showMessage(''); });
  }
}
document.querySelector('#clear-user').onclick=()=>{
  const form=document.querySelector('#user-form');form.reset();form.elements.id.value='';
  form.elements.role.disabled=false;form.elements.active.disabled=false;
};
document.querySelector('#user-form').onsubmit=event=>{
  event.preventDefault();action(event.submitter || event.target.querySelector('[type=submit]'),async()=>{
    const data=fields(event.target);const id=data.id;delete data.id;
    if ('active' in data) data.active=data.active==='true';
    if (!id && !data.password) throw new Error('كلمة المرور مطلوبة للمستخدم الجديد');
    await request(id?`/api/admin/users/${id}`:'/api/admin/users',id?'PUT':'POST',data);
    document.querySelector('#clear-user').click();await loadUsers();showMessage('تم حفظ المستخدم.');
  });
};
async function loadBackups() {
  const container=document.querySelector('#backup-list');container.replaceChildren();
  for (const backup of await request('/api/admin/backups')) {
    const item=row(container,new Date(backup.created_at).toLocaleString(),backup.id);
    button(item,'فحص',async()=>{await request(`/api/admin/backups/${backup.id}/verify`,'POST',{});showMessage('النسخة سليمة: تطابقت الملفات وفحص SQLite.');});
    if(currentUser.is_owner) button(item,'استعادة',async()=>{
      if(!confirm('ستعود جميع الحسابات إلى هذه النسخة. سيتم حفظ نسخة من الوضع الحالي وإلغاء الجلسات. هل تريد المتابعة؟'))return;
      const password=await restorePassword();if(!password)return;
      const result=await request(`/api/admin/backups/${backup.id}/restore`,'POST',{password});
      showMessage('تمت الاستعادة. نسخة ما قبل الاستعادة: '+result.safety_backup);
      changedSession();location.replace('/account.html');
    });
  }
}
document.querySelector('#create-backup').onclick=event=>action(event.target,async()=>{
  await request('/api/admin/backups','POST',{});await loadBackups();showMessage('تم إنشاء نسخة محلية وفحص سلامتها.');
});
(async()=>{
  try{
    const status=await request('/api/auth/status');currentUser=status.user;
    setupTokenRequired=Boolean(status.setup_token_required);registrationEnabled=status.registration_enabled !== false;
    if(!currentUser){document.querySelector('#sign-in').hidden=false;setAuthMode(status.setup_required?'setup':'login');showMessage(status.setup_required?'أدخل بريد المالك المحدد مسبقًا واختر كلمة مرورك. يمكنك تعديل اسمك لاحقًا من الملف الشخصي.':'');return;}
    document.querySelector('#profile').hidden=false;
    document.querySelector('#account-role').textContent=`${currentUser.nickname} · ${currentUser.role}`;
    const form=document.querySelector('#profile-form');
    for(const key of ['full_name','nickname','email'])form.elements[key].value=currentUser[key];
    form.elements.language.value=currentUser.preferences.language||savedPreference(`account:${currentUser.id}:taskline-language`)||'ar';
    form.elements.theme.value=currentUser.preferences.theme||savedPreference(`account:${currentUser.id}:taskline-theme`)||'system';
    await loadSessions();
    if(currentUser.role==='Admin'){document.querySelector('#admin').hidden=false;await Promise.all([loadUsers(),loadBackups()]);}
    showMessage('');
  }catch(error){showMessage(error.message,true);}
})();
window.addEventListener('storage',event=>{if(event.key==='taskline-session-change')location.reload();});
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
