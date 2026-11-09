'use strict';
// Optional local model UI. Prediction scores are shown for review, never as measured nutrition.
let localModelStatus=null,localModelLoading=false,localPrediction=null;
function resetLocalReview(){localPrediction=null;}
function localModelPanel(){
  const ready=localModelStatus?.ready,reviewed=localPrediction&&photoDraft.items.find(i=>i.recognition?.imageSha256===localPrediction.image_sha256);
  return `<section class="local-model-panel" aria-label="Local food recognition"><div class="card-heading"><strong>${uiIcon('shield',17)} Local food model</strong><span class="local-model-badge">${ready?'CONNECTED':'OPTIONAL'}</span></div><p>Recognize one main food on this computer. Confirm the food, enter its weight, and use label or recipe values for nutrition. No API key or cloud upload.</p>${localModelStatus?`<p class="notice" role="status">${esc(ready?`Model: ${localModelStatus.model_id}. ${localModelStatus.classes.length} classes. Held-out macro F1: ${Number.isFinite(localModelStatus.test_macro_f1)?localModelStatus.test_macro_f1.toFixed(3):'not reported'} (${localModelStatus.test_count??'?'} test photos). Internal subset results, not a guarantee for your photo.`:localModelStatus.message)}</p>`:'<p class="notice" role="status">Checking for a trained food model…</p>'}<div class="local-model-actions"><button class="secondary" data-local-model="predict" ${!ready||!photoDraft.image||photoWorking?'disabled':''}>${photoWorking?'Please wait…':'Recognize food locally'}</button><button class="text-button" data-local-model="refresh" ${photoWorking?'disabled':''}>Check model</button></div>${localPrediction?`<div class="local-predictions"><strong>${localPrediction.abstained?'Not sure — please identify the food.':'What food do you see?'}</strong><p>These are model scores among supported classes. Unfamiliar foods can still get a high score. A mixed plate needs additional manual items.</p>${localPrediction.candidates.map((candidate,index)=>`<button class="local-candidate" data-local-candidate="${index}" ${photoWorking||reviewed?'disabled':''}><span>${esc(candidate.label.replaceAll('_',' '))}</span><span>${(candidate.score*100).toFixed(1)}% ${uiIcon('arrow',14)}</span></button>`).join('')}<button class="text-button" data-local-model="correct" ${photoWorking||reviewed?'disabled':''}>None of these — enter the correct food</button><p class="notice">${Math.round(localPrediction.latency_ms)} ms including preprocessing; ${esc(localPrediction.model_id)}. ${reviewed?`Reviewed as ${esc(reviewed.name)}.`:'Choose a suggestion or correct it to open the ingredient form.'}</p>${reviewed?'<button class="secondary" data-local-model="export">Export reviewed training example</button><p class="notice">Optional: downloads a JSON file containing this photo and your reviewed food label. Keep it private or share deliberately. Nothing is uploaded, saved to the server, or used to retrain automatically.</p>':''}</div>`:''}</section>`;
}
function bindLocalModel(){if(!localModelStatus&&!localModelLoading)void checkLocalModel();}
async function checkLocalModel(){
  if(localModelLoading)return;localModelLoading=true;const epoch=photoEpoch;
  try{const response=await fetch(`${window.BLOOM_API_BASE}/api/ml/status`,{signal:AbortSignal.timeout(15000)});if(!response.ok)throw new Error('Restart Bloom using the updated server to connect a local model.');const status=await response.json();if(typeof status.ready!=='boolean'||status.ready&&(!Array.isArray(status.classes)||typeof status.model_id!=='string'))throw new Error('The model status could not be read.');localModelStatus=status;if(!status.ready)localModelStatus.message='Local food recognition is not connected yet. You can use online AI or add food manually.';}
  catch(error){localModelStatus={ready:false,message:error.name==='TimeoutError'?'Model check timed out. Try Check model.':error.message};}
  finally{localModelLoading=false;if(epoch===photoEpoch&&session&&page==='scan')renderScan();}
}
async function recognizeLocally(){
  if(photoWorking||!photoDraft.image||!session||!localModelStatus?.ready)return;
  if(photoDraft.items.length){toast('Review or remove the current food items before recognizing another photo.');return;}
  photoWorking=true;localPrediction=null;const epoch=photoEpoch,accountId=session.record.id;
  photoRequest=new AbortController();const controller=photoRequest,timeout=setTimeout(()=>controller.abort(),100000);renderScan();
  try{
    const response=await fetch(`${window.BLOOM_API_BASE}/api/ml/predict`,{method:'POST',headers:{'Content-Type':'application/json','X-Bloom-Request':'1'},body:JSON.stringify({image:photoDraft.image}),signal:controller.signal});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Local recognition is unavailable.');
    if(epoch!==photoEpoch||session?.record.id!==accountId)return;
    if(typeof result.model_id!=='string'||result.model_id.length>90||typeof result.abstained!=='boolean'||!Number.isFinite(result.latency_ms)||!Array.isArray(result.candidates)||result.candidates.length<1||result.candidates.length>3||!/^[a-f0-9]{64}$/.test(result.image_sha256)||!result.candidates.every(c=>typeof c.label==='string'&&c.label.length>0&&c.label.length<=90&&Number.isFinite(c.score)&&c.score>=0&&c.score<=1))throw new Error('The local prediction could not be read. Nothing was logged.');
    localPrediction=result;
  }catch(error){if(epoch===photoEpoch)toast(error.name==='AbortError'?'Recognition stopped. You can retry or enter food manually.':error.message);}
  finally{clearTimeout(timeout);if(epoch===photoEpoch){photoWorking=false;photoRequest=null;renderScan();}}
}
function reviewLocalCandidate(index){
  if(!localPrediction||photoWorking)return;
  const candidate=index==null?null:localPrediction.candidates[index];if(index!=null&&!candidate)return;
  const preset={name:candidate?candidate.label.replaceAll('_',' '):'',grams:null,per100:{},source:'Food label / manual',recognition:{modelId:localPrediction.model_id,predictedLabel:localPrediction.candidates[0].label,suggestedLabel:candidate?.label||'user correction',confidence:localPrediction.candidates[0].score,imageSha256:localPrediction.image_sha256}};
  editIngredient(null,preset);
}
async function exportReviewedExample(){
  if(!localPrediction||!photoDraft.image||photoWorking)return;
  const item=photoDraft.items.find(i=>i.recognition?.imageSha256===localPrediction.image_sha256);if(!item)return;
  const bytes=Uint8Array.from(atob(photoDraft.image.split(',')[1]),c=>c.charCodeAt(0));
  const sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
  if(sha!==localPrediction.image_sha256){toast('The photo changed. Recognize and review this photo again before exporting.');return;}
  const record={format:'bloom-reviewed-image-v1',consent:true,label:item.name,image_sha256:sha,image:photoDraft.image,recognition:item.recognition,reviewed_at:new Date().toISOString(),note:'Explicit user export; photo and food label only. No account or journal data.'};
  const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));const anchor=document.createElement('a');anchor.href=url;anchor.download=`bloom-${sha.slice(0,12)}.bloom-review.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Reviewed training example exported. It contains the photo and reviewed food label.');
}
document.addEventListener('click',async event=>{
  const target=event.target.closest('[data-local-model],[data-local-candidate]');if(!target||!session||busy||photoWorking)return;
  if(target.dataset.localCandidate!=null){reviewLocalCandidate(Number(target.dataset.localCandidate));return;}
  try{switch(target.dataset.localModel){case 'predict':await recognizeLocally();break;case 'refresh':await checkLocalModel();break;case 'correct':reviewLocalCandidate(null);break;case 'export':await exportReviewedExample();break;}}
  catch(error){toast(error.message||'This action could not be completed. Try again.');}
});
