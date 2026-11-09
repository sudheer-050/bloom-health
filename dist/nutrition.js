(function(root){
  'use strict';
  const nutrients={calories:['Calories','kcal',10000],protein:['Protein','g',1000],carbs:['Carbs','g',1000],fat:['Fat','g',1000],fiber:['Fiber','g',1000],sugar:['Sugar','g',1000],sodium:['Sodium','mg',100000],calcium:['Calcium','mg',100000],iron:['Iron','mg',10000],potassium:['Potassium','mg',100000],vitaminA:['Vitamin A','µg RAE',100000],vitaminC:['Vitamin C','mg',10000],vitaminD:['Vitamin D','µg',10000],b12:['Vitamin B12','µg',10000]};
  // Small offline starter reference. Values vary with variety and preparation.
  // Missing micronutrients are deliberately unknown rather than assumed zero.
  const starter=[['Apple with skin',52,.3,13.8,.2,2.4],['Banana',89,1.1,22.8,.3,2.6],['Orange',47,.9,11.8,.1,2.4],['Rice, white, cooked',130,2.7,28.2,.3,.4],['Rice, brown, cooked',123,2.7,25.6,1,1.6],['Chicken breast, roasted',165,31,0,3.6,0],['Egg, hard-boiled',155,12.6,1.1,10.6,0],['Salmon, cooked',206,22,0,12,0],['Lentils, cooked',116,9,20.1,.4,7.9],['Chickpeas, cooked',164,8.9,27.4,2.6,7.6],['Tofu, firm',144,17.3,2.8,8.7,2.3],['Broccoli, steamed',35,2.4,7.2,.4,3.3],['Spinach, raw',23,2.9,3.6,.4,2.2],['Carrot, raw',41,.9,9.6,.2,2.8],['Potato, boiled',87,1.9,20.1,.1,1.8],['Avocado',160,2,8.5,14.7,6.7],['Oatmeal, cooked with water',71,2.5,12,1.5,1.7],['Bread, whole wheat',247,13,41,4.2,7],['Yogurt, plain whole milk',61,3.5,4.7,3.3,0],['Milk, whole',61,3.2,4.8,3.3,0],['Almonds',579,21.2,21.6,49.9,12.5],['Olive oil',884,0,0,100,0],['Butter',717,.9,.1,81.1,0],['Sugar, white',387,0,100,0,0]];
  const catalog=starter.map(([name,calories,protein,carbs,fat,fiber])=>({name,source:'Starter estimate',per100:{calories,protein,carbs,fat,fiber}}));
  // Vitamin C reference: FDA GRAS Notice 769, USDA SR28 oranges, 53.2 mg/100g.
  catalog.find(f=>f.name==='Orange').per100.vitaminC=53.2;
  function cleanItem(item){
    if(!item||typeof item.name!=='string'||!item.name.trim()||item.name.length>90||!Number.isFinite(item.grams)||item.grams<=0||item.grams>5000)throw new Error('Each item needs a food name and a portion between 0.1 and 5,000 grams.');
    if(!item.per100||typeof item.per100!=='object')throw new Error('Enter nutrition values per 100 grams.');
    const per100={};for(const [key,[label,,max]] of Object.entries(nutrients)){const value=item.per100[key];if(value==null){if(['calories','protein','carbs','fat'].includes(key))throw new Error(`Enter ${label.toLowerCase()} per 100 grams.`);per100[key]=null;}else if(typeof value!=='number'||!Number.isFinite(value)||value<0||value>max)throw new Error(`Check the ${label.toLowerCase()} value.`);else per100[key]=value;}
    const clean={name:item.name.trim(),grams:item.grams,source:['AI estimate','Starter estimate','Food label / manual'].includes(item.source)?item.source:'Food label / manual',per100};
    if(item.recognition!==undefined){
      const r=item.recognition;
      if(!r||typeof r!=='object'||!['modelId','predictedLabel','suggestedLabel'].every(k=>typeof r[k]==='string'&&r[k].length>0&&r[k].length<=90)||typeof r.confidence!=='number'||!Number.isFinite(r.confidence)||r.confidence<0||r.confidence>1||typeof r.imageSha256!=='string'||!/^[a-f0-9]{64}$/.test(r.imageSha256))throw new Error('Invalid food recognition provenance.');
      clean.recognition={modelId:r.modelId,predictedLabel:r.predictedLabel,suggestedLabel:r.suggestedLabel,confidence:r.confidence,imageSha256:r.imageSha256};
    }
    return clean;
  }
  function totals(items){
    if(!Array.isArray(items)||items.length>40)throw new Error('A meal can contain up to 40 items.');
    const clean=items.map(cleanItem),values={},known={};
    for(const key of Object.keys(nutrients)){const present=clean.filter(i=>i.per100[key]!=null);known[key]=present.length;values[key]=present.length?present.reduce((n,i)=>n+i.per100[key]*i.grams/100,0):null;}
    return {items:clean,values,known};
  }
  function meal(items,type,name,id){
    if(!items.length)throw new Error('Add at least one food before logging the meal.');
    const t=totals(items);const round=n=>Math.round(n*10)/10;
    const out={id,name:name.trim().slice(0,90)||'Reviewed meal',meal:type,items:t.items,nutrients:{},nutrientCoverage:t.known};
    for(const key of ['calories','protein','carbs','fat'])out[key]=round(t.values[key]);
    for(const key of Object.keys(nutrients))if(!['calories','protein','carbs','fat'].includes(key))out.nutrients[key]=t.values[key]==null?null:round(t.values[key]);
    if(out.calories>10000||out.protein>1000||out.carbs>1000||out.fat>1000)throw new Error('This meal is larger than the journal supports. Split it into smaller entries.');
    return out;
  }
  const api={nutrients,catalog,cleanItem,totals,meal};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.BloomNutrition=api;
})(typeof globalThis!=='undefined'?globalThis:this);
