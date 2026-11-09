'use strict';
let session=null, busy=false, authMode='login', pendingRestore=null, pendingImport=null;
const vault=BloomVault;
function legacyAvailable(){try{return !session?.guest&&Boolean(localStorage.getItem(KEY));}catch{return false;}}
function storageRead(key){try{return localStorage.getItem(key);}catch{throw new Error('Browser storage is unavailable. Allow local storage for Bloom, then try again.');}}
function storageWrite(key,value){try{localStorage.setItem(key,value);}catch{throw new Error('Could not save to this browser. Storage may be full or disabled. Download a backup to keep your journal.');}}
async function writeLock(email,operation){if(!navigator.locks)throw new Error('Use a recent Chrome, Edge, Firefox or Safari browser to save local accounts.');return navigator.locks.request(vault.storageKey(email),operation);}
function statusBadge(text){$('.local-badge').textContent=text;}
function setBusy(value){busy=value;$('#workspace').inert=value;$('#modal').inert=value;$('#workspace').setAttribute('aria-busy',String(value));}
function download(record){const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`bloom-backup-${today()}-${record.id.slice(0,8)}.bloom`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function saveAccount(){
  if(!session||busy)return false;
  if(session.guest)return saveGuest();
  const active=session;active.dirty=true;setBusy(true);statusBadge('Encrypting & saving…');
  try{
    await writeLock(active.record.email,async()=>{
      const key=vault.storageKey(active.record.email);
      if(storageRead(key)!==active.raw)throw new Error('This account changed in another tab. Back up your current journal, then lock and sign in again to load the other version.');
      const record=await vault.seal(state,active.key,active.record),raw=JSON.stringify(record);
      storageWrite(key,raw);active.record=record;active.raw=raw;active.dirty=false;
    });
    $('#save-warning').hidden=true;statusBadge('Saved & encrypted');return true;
  }catch(error){$('#save-warning').hidden=false;statusBadge('Changes not saved');toast(error.message);return false;}
  finally{setBusy(false);}
}
async function backupAccount(){
  if(!session||busy)return;setBusy(true);
  try{if(session.guest){const data=vault.journal(state),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`bloom-guest-journal-${today()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Guest backup downloaded. This JSON file is not password-protected.');}else{const record=await vault.seal(state,session.key,session.record);download(record);toast('Encrypted backup downloaded. Keep it with your password.');}}
  catch(error){toast(error.message);}finally{setBusy(false);}
}
function enterAccount(unlocked,raw,guest=false){
  session={...unlocked,raw,dirty:false,guest};state=unlocked.data;date=today();
  pendingRestore=null;pendingImport=null;
  document.body?.classList.remove('auth-active');document.body?.classList.remove('landing-active');$('#landing-screen').hidden=true;
  $('#auth-screen').hidden=true;$('#workspace').hidden=false;$('#auth-content').replaceChildren();
  $('#save-warning').hidden=true;updateSessionLabels();render();window.scrollTo?.({top:0,behavior:'instant'});
}
function updateSessionLabels(){
  statusBadge(session.guest?'Saved on this device':'Saved & encrypted');
  $('#lock-button').textContent=session.guest?'Exit guest':'Lock';
  $('.profile small').textContent=session.guest?'Guest · this browser':'Local account';
  $('footer span:last-child').textContent=session.guest?'Guest journal · Saved only in this browser.':'Local account · No automatic sync between devices.';
}
async function guestWriteLock(operation){return navigator.locks?navigator.locks.request(KEY,operation):operation();}
async function startGuest(){
  if(busy||session)return;busy=true;
  try{let raw,data;await guestWriteLock(()=>{raw=storageRead(KEY);data=raw?vault.journal(JSON.parse(raw)):vault.blank();if(!raw){raw=JSON.stringify(data);storageWrite(KEY,raw);}});enterAccount({record:{id:'local-guest',email:null},key:null,data},raw,true);}
  catch(error){authError(error instanceof SyntaxError?'The saved guest journal could not be read. The original data was kept.':error.message);}
  finally{busy=false;}
}
async function saveGuest(){
  if(!session?.guest||busy)return false;const active=session;active.dirty=true;setBusy(true);statusBadge('Saving on this device…');
  try{const raw=JSON.stringify(vault.journal(state));await guestWriteLock(()=>{if(storageRead(KEY)!==active.raw)throw new Error('The guest journal changed in another tab. Back up these changes, then exit and reopen guest mode to load the other version.');storageWrite(KEY,raw);});active.raw=raw;active.dirty=false;$('#save-warning').hidden=true;statusBadge('Saved on this device');return true;}
  catch(error){$('#save-warning').hidden=false;statusBadge('Changes not saved');toast(error.message);return false;}
  finally{setBusy(false);}
}
async function lockAccount(){
  if(busy)return;
  if(session?.dirty){
    $('#dialog-title').textContent='Keep your unsaved changes';
    $('#entry-form').innerHTML='<p class="form-help">Your latest changes have not been saved. Download a backup or cancel and retry saving. Discarding will load the previously saved version next time you sign in.</p><button type="button" class="primary" id="backup-before-lock">Download current journal backup</button><button type="button" class="danger" id="discard-and-lock">Discard unsaved changes and lock</button>';
    $('#backup-before-lock').onclick=backupAccount;$('#discard-and-lock').onclick=()=>{session.dirty=false;lockAccount();};if(!$('#modal').open)$('#modal').showModal();return;
  }
  const email=session?.record.email||'';
  if(typeof resetPhotoMeal==='function')resetPhotoMeal();session=null;state=vault.blank();pendingImport=null;pendingRestore=null;$('#modal').close();$('#entry-form').replaceChildren();$('#main').replaceChildren();$('#workspace').hidden=true;$('#profile-name').textContent='Your space';document.querySelectorAll('.avatar').forEach(e=>e.textContent='Y');$('#toast').classList.remove('show');authView('login',email);
}
function authError(message){const target=$('#auth-screen').hidden?$('#landing-error'):$('#auth-error');target.textContent=message;target.hidden=false;}
function authView(mode='login',address=''){
  authMode=mode;document.body?.classList.remove('landing-active');document.body?.classList.add('auth-active');$('#landing-screen').hidden=true;$('#auth-screen').dataset.mode=mode;$('#auth-screen').hidden=false;$('#workspace').hidden=true;window.scrollTo?.({top:0,behavior:'instant'});
  const restoring=mode==='restore',creating=mode==='create';
  $('#auth-content').innerHTML=`<span class="eyebrow">${creating?'A FRESH START':restoring?'BRING YOUR JOURNAL WITH YOU':'A LITTLE TIME FOR YOU'}</span><h2>${creating?'Your space to grow.':restoring?'Welcome to your next chapter.':'Welcome back.'}</h2><p class="auth-description">${creating?'A personal space for your everyday progress.':restoring?'Unlock your backup with the password you used when you made it.':'A fresh moment for you and your wellbeing.'}</p>${!restoring?`<div class="auth-tabs" role="group" aria-label="Account access"><button type="button" data-auth="login" class="${!creating?'selected':''}">Sign in</button><button type="button" data-auth="create" class="${creating?'selected':''}">Create account</button></div>`:''}<div class="auth-error" id="auth-error" role="alert" hidden></div><form id="auth-form">${creating?'<label>Your name<input name="name" autocomplete="given-name" maxlength="40" placeholder="What should we call you?" required></label>':''}<label>Email address<input id="auth-email" name="email" type="email" autocomplete="username" maxlength="254" placeholder="you@example.com" value="${esc(restoring?pendingRestore.record.email:address)}" ${restoring?'readonly':''} required></label><label>Password<div class="password-wrap"><input id="auth-password" name="password" type="password" autocomplete="${creating?'new-password':'current-password'}" minlength="12" maxlength="256" placeholder="${creating?'At least 12 characters':'Your account password'}" required><button type="button" id="show-password" aria-label="Show password" aria-pressed="false">Show</button></div></label>${creating?'<label>Confirm password<input name="confirm" type="password" autocomplete="new-password" minlength="12" maxlength="256" placeholder="Enter your password again" required></label><p class="form-help">Your email is a local account label. No verification email is sent. Keep your password safe: there is no password reset or account recovery.</p>':''}<button type="submit" class="primary auth-submit">${creating?'Create my account':restoring?'Unlock backup':'Sign in'} <span aria-hidden="true">↗</span></button></form>${!restoring?'<button type="button" class="secondary guest-continue" id="continue-guest">Continue as guest <span aria-hidden="true">&#8599;</span></button><p class="guest-login-note">No account needed. Your journal stays in this browser.</p>':''}${!creating&&!restoring?'<button class="text-button forgot-help" id="password-help">Forgot your password?</button>':''}<div class="auth-divider"><span>${restoring?'LOOKING FOR YOUR ACCOUNT?':'TAKING BLOOM TO A NEW DEVICE?'}</span></div><button class="secondary restore-button" id="choose-restore">↥ Restore an encrypted backup</button>${restoring?'<button class="text-button back-login" data-auth="login">Back to sign in</button>':''}<div class="auth-info"><span aria-hidden="true">♧</span><p>${creating?'Your journal is encrypted on this device. A backup lets you take it elsewhere.':'Local first. Your password unlocks your data here. To sign in elsewhere, restore your latest backup there first.'}</p></div>`;
  $('#auth-form').onsubmit=submitAuth;
  if($('#continue-guest'))$('#continue-guest').onclick=startGuest;
  $('#show-password').onclick=()=>{const input=$('#auth-password'),show=input.type==='password';input.type=show?'text':'password';$('#show-password').textContent=show?'Hide':'Show';$('#show-password').setAttribute('aria-label',show?'Hide password':'Show password');$('#show-password').setAttribute('aria-pressed',String(show));};
  $('#choose-restore').onclick=()=>{if(!busy)$('#restore-file').click();};
  if($('#password-help'))$('#password-help').onclick=()=>authError('There is no password reset because Bloom does not store your password. Try the password used for your latest backup. Without that password, the encrypted journal cannot be unlocked.');
}
async function submitAuth(event){
  event.preventDefault();if(busy)return;const form=event.target;if(!form.reportValidity())return;
  const values=Object.fromEntries(new FormData(form)),button=form.querySelector('[type=submit]');
  busy=true;button.disabled=true;button.textContent='Opening your space…';$('#auth-error').hidden=true;
  try{
    const email=vault.email(values.email),key=vault.storageKey(email);let unlocked,raw;
    if(authMode==='create'){
      if(!values.name.trim())throw new Error('Enter your name to create your account.');
      if(values.password!==values.confirm)throw new Error('The passwords do not match. Please enter them again.');
      if(storageRead(key))throw new Error('An account with this email already exists in this browser. Sign in instead.');
      unlocked=await vault.create(email,values.password,vault.blank(values.name.trim()));raw=JSON.stringify(unlocked.record);
      await writeLock(email,()=>{if(storageRead(key))throw new Error('This account was just created in another tab. Sign in instead.');storageWrite(key,raw);});
    }else if(authMode==='restore'){
      const loaded=await vault.unlock(pendingRestore.record,values.password);
      form.reset();showRestorePreview(loaded);return;
    }else{
      raw=storageRead(key);if(!raw)throw new Error('No account with this email is saved in this browser. Create one, or restore your .bloom backup from the other device.');
      unlocked=await vault.unlock(vault.parse(raw),values.password);
    }
    form.reset();enterAccount(unlocked,raw);
  }catch(error){authError(error.message);}
  finally{busy=false;if(button.isConnected){button.disabled=false;button.textContent=authMode==='create'?'Create my account':authMode==='restore'?'Unlock backup':'Sign in';}}
}
function showRestorePreview(unlocked){
  const key=vault.storageKey(unlocked.record.email),expected=storageRead(key);
  if(expected&&vault.parse(expected).id!==unlocked.record.id)throw new Error('A different local account already uses this email. Restore this backup in a different browser profile to keep both accounts.');
  const hasExisting=Boolean(expected);
  $('#auth-content').innerHTML=`<span class="eyebrow">BACKUP UNLOCKED</span><h2>Your journal is ready.</h2><p class="auth-description">Review before restoring to this browser.</p><div class="restore-summary"><strong>${esc(unlocked.data.name||'Your journal')}</strong><p>${esc(unlocked.record.email)}</p><p>${esc(vault.summary(unlocked.data))}</p><small>Backup saved ${esc(new Date(unlocked.record.savedAt).toLocaleString())}</small></div><p class="form-help">${hasExisting?'This replaces the journal for this account in this browser with the backup version. Newer entries here will be lost. Cancel and back up the current account first if you need to keep them.':'This creates your local account and restores the journal from the file. Other accounts in this browser stay unchanged.'}</p><div class="auth-error" id="auth-error" role="alert" hidden></div><button class="primary auth-submit" id="confirm-restore">${hasExisting?'Replace journal and sign in':'Restore journal and sign in'}</button><button class="text-button back-login" data-auth="login">Cancel restore</button>`;
  $('#confirm-restore').onclick=async()=>{
    if(busy)return;busy=true;const button=$('#confirm-restore');button.disabled=true;
    try{const raw=JSON.stringify(unlocked.record);await writeLock(unlocked.record.email,()=>{if(storageRead(key)!==expected)throw new Error('The local account changed while you were reviewing. Cancel and choose the backup again.');storageWrite(key,raw);});enterAccount(unlocked,raw);toast('Journal restored. Welcome back.');}
    catch(error){authError(error.message);}finally{busy=false;if(button.isConnected)button.disabled=false;}
  };
}
async function readBackup(file){
  if(!file)return;if(file.size>vault.MAX_BYTES)throw new Error('Choose a Bloom backup smaller than 4 MB.');
  return vault.parse(await file.text());
}
$('#restore-file').onchange=async event=>{
  const file=event.target.files[0];event.target.value='';if(!file||busy)return;
  try{const record=await readBackup(file);if(session){if(session.dirty)throw new Error('Save your latest changes or download a backup before restoring another journal.');await lockAccount();}pendingRestore={record};authView('restore');}
  catch(error){if(session)toast(error.message);else if($('#auth-error'))authError(error.message);}
};
function transferPage(){
  if(session.guest)return guestTransferPage();
  return `<div class="grid"><section class="card"><div class="card-heading"><div><span class="card-kicker">A LITTLE PEACE OF MIND</span><h2>Good progress goes with you.</h2><small>Back up here. Restore there. Keep going.</small></div><span class="card-icon">${uiIcon('backup',23)}</span></div><ol class="transfer-steps"><li><strong>Save a backup</strong><p>Download an encrypted copy of this account’s journal, profile and goals.</p></li><li><strong>Take the file to another device</strong><p>Copy the .bloom file using a USB drive or a file transfer method you choose.</p></li><li><strong>Restore and sign in</strong><p>Open Bloom there, choose Restore an encrypted backup, and enter the password you used when you made that backup.</p></li></ol><button class="primary" data-account="backup">↓ Download encrypted backup</button><button class="secondary" data-account="restore">↥ Restore backup</button><p class="notice">Each backup is a snapshot. Changes do not sync or merge automatically. Keep your newest backup, and remember which device you last edited.</p></section><div class="right-stack"><section class="card"><span class="card-kicker">YOUR OWN LITTLE CORNER</span><h2>Your local account</h2><p class="account-email">${esc(session.record.email)}</p><p class="notice">Your journal is encrypted in this browser. Your email is an account label, not an online account. Closing or refreshing Bloom locks the journal.</p><button class="secondary" data-account="lock" style="margin-top:18px">Lock &amp; sign out</button></section><section class="card"><h2>Already using the first Bloom?</h2><p class="notice">Move the original journal on this browser into this account, or import its old JSON export. Review the entries before confirming.</p><div class="transfer-actions"><button class="text-button" data-account="legacy">Move original journal</button><button class="text-button" data-account="legacy-file">Import old JSON export</button></div></section></div></div>`;
}
function guestTransferPage(){
  return `<div class="grid"><section class="card"><div class="card-heading"><div><span class="card-kicker">LOCAL. PERSONAL. YOURS.</span><h2>Your guest journal</h2><small>No email, password or account required.</small></div></div><p class="notice">Your meals, water, activity, goals and progress are saved automatically in this browser. Anyone using this browser can open this shared guest journal. Clearing browser data removes it.</p><div class="transfer-actions"><button class="primary" data-account="backup">Download guest backup</button><button class="secondary" data-account="legacy-file">Import guest JSON backup</button></div><p class="notice">Guest backups are ordinary JSON files, without a password. Import into an empty guest journal to preserve every entry. To move devices, download a backup here, open guest mode there, then import the file.</p></section><section class="card"><h2>Want your own protected space?</h2><p class="notice">You can create a password-protected local account whenever you choose. Your guest journal stays here until you explicitly move it into that account.</p><button class="secondary" data-account="create-from-guest" style="margin-top:18px">Create a local account</button><button class="text-button" data-account="lock" style="margin:18px">Exit guest mode</button></section></div>`;
}
function previewLegacy(value,originalRaw=null){
  if(session.dirty)throw new Error('Save or back up your current changes before importing a journal.');
  if(Object.keys(state.days).length)throw new Error(session.guest?'Import into an empty guest journal. Back up your current journal first, then clear its entries in My goals before importing.':'Import your original journal into an empty account to preserve every entry. Create a new local account, then move the original journal before adding new entries.');
  const clean=vault.journal(value);pendingImport={clean,originalRaw};
  $('#dialog-title').textContent='Move your existing journal';
  $('#entry-form').innerHTML=`<p class="form-help">Import ${esc(vault.summary(clean))} into ${session.guest?'your guest journal':esc(session.record.email)}?</p><p class="form-help">All entries and goals will move into this empty journal. Your current profile name stays unchanged.</p>${originalRaw?'<p class="form-help">After a successful save, the old unprotected journal in this browser will be removed. Its contents will belong to this account.</p>':'<p class="form-help">Your original JSON file stays unchanged.</p>'}<p class="form-help" id="import-error" role="alert"></p><button type="submit" class="primary">Confirm import</button>`;
  $('#entry-form').onsubmit=async event=>{
    event.preventDefault();if(busy||!pendingImport)return;const current=pendingImport;const original=state;
    const next=vault.journal(current.clean),added=Object.keys(next.days).length;
    next.name=state.name||current.clean.name;
    state=next;
    if(!await saveAccount()){state=original;session.dirty=false;$('#save-warning').hidden=true;$('#import-error').textContent='Import was not saved. Nothing was removed from the original journal. Check storage or other open tabs, then try again.';return;}
    let removed=true;
    if(current.originalRaw){try{if(storageRead(KEY)===current.originalRaw)localStorage.removeItem(KEY);else removed=false;}catch{removed=false;}}
    pendingImport=null;$('#modal').close();render();toast(`Imported ${added} new days. ${removed?'': 'The original journal is still in this browser.'}`);
  };
  $('#modal').showModal();
}
$('#legacy-file').onchange=async event=>{const file=event.target.files[0];event.target.value='';if(!file||!session||busy)return;try{if(file.size>vault.MAX_BYTES)throw new Error('Choose a JSON journal smaller than 4 MB.');previewLegacy(JSON.parse(await file.text()));}catch(error){toast(error instanceof SyntaxError?'This file is not valid JSON. Nothing was changed.':error.message);}};
document.addEventListener('click',async event=>{
  const auth=event.target.closest('[data-auth]');if(auth&&!busy){pendingRestore=null;authView(auth.dataset.auth);return;}
  const control=event.target.closest('[data-account]');if(!control||!session||busy)return;
  const action=control.dataset.account;
  if(action==='backup')await backupAccount();else if(action==='lock')await lockAccount();else if(action==='create-from-guest'){await lockAccount();if(!session)authView('create');}else if(action==='restore')$('#restore-file').click();else if(action==='legacy-file')$('#legacy-file').click();else if(action==='legacy'){
    try{const raw=storageRead(KEY);if(!raw)throw new Error('No original journal was found in this browser. Use Import old JSON export if you have a file.');previewLegacy(JSON.parse(raw),raw);}catch(error){toast(error.message);}
  }
});
$('#backup-button').onclick=$('#export').onclick=$('#rescue-backup').onclick=backupAccount;
$('#lock-button').onclick=lockAccount;
$('#retry-save').onclick=async()=>{if(await saveAccount())toast(session.guest?'Your guest journal is saved on this device.':'Your journal is saved and encrypted.');};
window.addEventListener('beforeunload',event=>{if(session?.dirty||busy){event.preventDefault();event.returnValue='';}});
window.addEventListener('storage',event=>{if(session&&event.key===(session.guest?KEY:vault.storageKey(session.record.email))&&event.newValue!==session.raw){statusBadge('Updated in another tab');toast(session.guest?'The guest journal changed in another tab. Exit and reopen guest mode before editing here.':'This account changed in another tab. Lock and sign in again before editing here.');}});
landingView();
