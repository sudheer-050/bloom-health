'use strict';
// Native adaptation of 21st's Hero with Product Mockup (catalog 4710).
function landingView(){
  if(session||busy)return;
  document.body?.classList.remove('auth-active');document.body?.classList.add('landing-active');
  $('#landing-screen').hidden=false;$('#auth-screen').hidden=true;$('#workspace').hidden=true;
  $('#auth-content').replaceChildren();$('#landing-error').hidden=true;
  window.scrollTo?.({top:0,behavior:'instant'});
}
document.addEventListener('click',async event=>{
  const home=event.target.closest('[data-home]');
  if(home&&!session&&!busy){event.preventDefault();landingView();return;}
  const guest=event.target.closest('[data-start-guest]');
  if(guest&&!session&&!busy){
    document.querySelectorAll('[data-start-guest]').forEach(button=>{button.disabled=true;});
    try{await startGuest();}
    finally{document.querySelectorAll('[data-start-guest]').forEach(button=>{button.disabled=false;});}
  }
});
