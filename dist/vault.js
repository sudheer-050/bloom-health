/* Local account storage and portable encrypted backups. No network calls. */
(function (root) {
  'use strict';
  const FORMAT='bloom-encrypted-backup', ITERATIONS=600000, MAX_BYTES=4*1024*1024;
  const encoder=new TextEncoder(), decoder=new TextDecoder();
  const fail=message=>{throw new Error(message);};
  const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
  const text=(v,max,label)=>typeof v==='string'&&v.length<=max?v:fail(`Invalid ${label}.`);
  const number=(v,min,max,label)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max?v:fail(`Invalid ${label}.`);
  function email(value){const normalized=text(value,254,'email address').trim().toLowerCase();if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized))fail('Enter a valid email address.');return normalized;}
  function blank(name=''){return {name,goals:{calories:2000,water:2000,activity:30,protein:100,carbs:250,fat:65},days:{},demo:false};}
  function journal(value){
    if(!object(value)||!object(value.goals)||!object(value.days))fail('This file does not contain a valid Bloom journal.');
    const clean=blank(text(value.name??'',40,'profile name'));
    const limits={calories:20000,water:20000,activity:1440,protein:1000,carbs:2000,fat:1000};
    for(const key of Object.keys(limits))clean.goals[key]=number(value.goals[key],1,limits[key],`${key} goal`);
    if(Object.keys(value.days).length>36600)fail('This journal has too many days.');
    for(const [date,day] of Object.entries(value.days)){
      if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(Date.parse(date+'T00:00:00Z'))||new Date(date+'T00:00:00Z').toISOString().slice(0,10)!==date||!object(day))fail('The journal contains an invalid date.');
      if(!Array.isArray(day.meals)||!Array.isArray(day.activities)||day.meals.length>1000||day.activities.length>1000)fail('Invalid journal entries.');
      const ids=new Set();
      const meals=day.meals.map(m=>{
        if(!object(m))fail('Invalid meal.');
        const id=text(m.id,100,'meal identifier');if(!id||ids.has(id))fail('Duplicate meal identifier.');ids.add(id);
        if(!['Breakfast','Lunch','Dinner','Snack'].includes(m.meal))fail('Invalid meal type.');
        const cleanMeal={id,name:text(m.name,90,'food name'),meal:m.meal,calories:number(m.calories,0,10000,'calories'),protein:number(m.protein,0,1000,'protein'),carbs:number(m.carbs,0,1000,'carbs'),fat:number(m.fat,0,1000,'fat')};
        if(m.items!==undefined){
          if(!Array.isArray(m.items)||m.items.length<1||m.items.length>40)fail('Invalid meal ingredients.');
          const model=typeof module!=='undefined'&&module.exports?require('./nutrition.js'):root.BloomNutrition;
          const calculated=model.meal(m.items,m.meal,cleanMeal.name,id);
          for(const field of ['calories','protein','carbs','fat'])if(Math.abs(calculated[field]-cleanMeal[field])>.11)fail('Meal totals do not match its ingredients.');
          cleanMeal.items=calculated.items;cleanMeal.nutrients=calculated.nutrients;cleanMeal.nutrientCoverage=calculated.nutrientCoverage;
        }
        return cleanMeal;
      });
      ids.clear();
      const activities=day.activities.map(a=>{
        if(!object(a))fail('Invalid activity.');const id=text(a.id,100,'activity identifier');if(!id||ids.has(id))fail('Duplicate activity identifier.');ids.add(id);
        return {id,type:text(a.type,50,'activity type'),minutes:number(a.minutes,1,1440,'activity duration'),note:text(a.note??'',120,'activity note')};
      });
      clean.days[date]={meals,activities,water:number(day.water,0,100000,'water amount'),weight:day.weight==null?null:number(day.weight,1,700,'weight')};
    }
    clean.demo=value.demo===true;
    if(encoder.encode(JSON.stringify(clean)).length>MAX_BYTES/2)fail('Your journal is too large for this version. Keep a backup before removing old entries.');
    return clean;
  }
  const encode=bytes=>{let s='';for(const b of new Uint8Array(bytes))s+=String.fromCharCode(b);return btoa(s);};
  function decode(value,min,max,label){if(typeof value!=='string'||value.length>max*2||!/^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value))fail(`Invalid backup ${label}.`);const bytes=Uint8Array.from(atob(value),c=>c.charCodeAt(0));if(bytes.length<min||bytes.length>max)fail(`Invalid backup ${label}.`);return bytes;}
  function envelope(value){
    if(!object(value)||value.format!==FORMAT||value.version!==1||value.iterations!==ITERATIONS)fail('Choose a supported encrypted Bloom backup (.bloom).');
    const id=text(value.id,36,'account identifier');if(!/^[a-f0-9-]{36}$/.test(id))fail('Invalid backup account identifier.');
    const address=email(value.email);decode(value.salt,16,16,'salt');decode(value.iv,12,12,'IV');decode(value.ciphertext,16,MAX_BYTES,'data');
    const savedAt=text(value.savedAt,40,'backup time');if(!Number.isFinite(Date.parse(savedAt)))fail('Invalid backup time.');
    return {format:FORMAT,version:1,id,email:address,iterations:ITERATIONS,salt:value.salt,iv:value.iv,ciphertext:value.ciphertext,savedAt};
  }
  function parse(source){if(typeof source!=='string'||source.length>MAX_BYTES)fail('Choose a Bloom backup smaller than 4 MB.');try{return envelope(JSON.parse(source));}catch(e){if(e instanceof SyntaxError)fail('This backup is not valid JSON. Choose a .bloom backup file.');throw e;}}
  const aad=record=>encoder.encode(JSON.stringify([FORMAT,1,record.id,record.email,record.iterations,record.salt,record.savedAt]));
  async function derive(password,salt){
    if(!root.crypto?.subtle)fail('Local encryption requires a recent browser. Open Bloom at http://localhost:4317.');
    if(typeof password!=='string'||password.length<12||password.length>256)fail('Use a password between 12 and 256 characters.');
    const material=await root.crypto.subtle.importKey('raw',encoder.encode(password),'PBKDF2',false,['deriveKey']);
    return root.crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',iterations:ITERATIONS,salt:decode(salt,16,16,'salt')},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
  }
  async function seal(value,key,base){const clean=journal(value);const record={format:FORMAT,version:1,id:base.id,email:email(base.email),iterations:ITERATIONS,salt:base.salt,savedAt:new Date().toISOString()};const iv=root.crypto.getRandomValues(new Uint8Array(12));record.iv=encode(iv);record.ciphertext=encode(await root.crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:aad(record)},key,encoder.encode(JSON.stringify(clean))));return record;}
  async function create(address,password,value){const base={id:root.crypto.randomUUID(),email:email(address),salt:encode(root.crypto.getRandomValues(new Uint8Array(16)))};const key=await derive(password,base.salt);return {key,record:await seal(value,key,base),data:journal(value)};}
  async function unlock(value,password){const record=envelope(value);const key=await derive(password,record.salt);let plain;try{plain=await root.crypto.subtle.decrypt({name:'AES-GCM',iv:decode(record.iv,12,12,'IV'),additionalData:aad(record)},key,decode(record.ciphertext,16,MAX_BYTES,'data'));}catch{fail('Could not unlock this account. Check the password, or choose an intact backup.');}let data;try{data=journal(JSON.parse(decoder.decode(plain)));}catch{fail('This backup contains an invalid journal. Nothing was changed.');}return {record,key,data};}
  const storageKey=address=>'bloom-account-v1:'+email(address);
  function summary(value){const days=Object.values(value.days);return `${days.length} days, ${days.reduce((n,d)=>n+d.meals.length,0)} meals, ${days.reduce((n,d)=>n+d.activities.length,0)} activities`;}
  const api={blank,journal,email,create,unlock,seal,parse,envelope,storageKey,summary,MAX_BYTES};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.BloomVault=api;
})(typeof globalThis!=='undefined'?globalThis:this);
