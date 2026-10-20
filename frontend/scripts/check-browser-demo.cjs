// Offline browser service checks and numerical parity with actual Python-generated outputs.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), ts = require('typescript');
require.extensions['.ts'] = (m, filename) => m._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {
  compilerOptions: {target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},
}).outputText, filename);
const engine = require('../app/browser-experiments.ts');
const {browserDemoRequest:request} = require('../app/browser-demo.ts');
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/browser-parity.json'),'utf8'));
function equal(actual, expected, at='') {
  if (typeof expected === 'number') assert.ok(Math.abs(actual-expected)<=1e-10*Math.max(1,Math.abs(expected)),`${at}: ${actual} != ${expected}`);
  else if (Array.isArray(expected)) { assert.equal(actual.length,expected.length,at); expected.forEach((v,i)=>equal(actual[i],v,at+'['+i+']')); }
  else if (expected && typeof expected === 'object') Object.keys(expected).forEach(k=>equal(actual[k],expected[k],at+'.'+k));
  else assert.equal(actual,expected,at);
}
async function main() {
  let count=0;
  for (const fixture of fixtures.cases) for (const expected of fixture.expected) {
    const actual=engine.runBrowserExperiment(fixture.dataset,expected.model,expected.horizon,fixture.dates);
    for(const key of ['symbol','source','model','horizon','model_version','dataset_id','mae','baseline_mae','samples','train_end','backtest','forecast','band_note']) equal(actual[key],expected[key],key);
    for(const key of ['window','validation','evaluation_start_index','calendar']) equal(actual.config[key],expected.config[key],key);
    count++;
  }
  const rows=fixtures.cases[1].dataset.prices;
  const csv='\uFEFFdate,close,notes\r\n'+rows.map(r=>`${r.date},${r.close},"quoted, field"`).join('\r\n');
  assert.deepEqual(engine.parseCSV(csv),rows);
  assert.equal(engine.parseCSV(csv+`\r\n${rows[0].date},123,"duplicate"`)[0].close,123);
  assert.throws(()=>engine.parseCSV('date,close\n2025-02-30,12'));
  assert.throws(()=>engine.parseCSV(csv+'\n2025-01-01,NaN'));
  assert.throws(()=>engine.parseCSV('date,close\n"unterminated'));
  assert.throws(()=>engine.runBrowserExperiment(fixtures.cases[0].dataset,'trend',7));
  assert.throws(()=>engine.runBrowserExperiment(fixtures.cases[1].dataset,'invalid',7));
  const constant=fixtures.cases[0].expected.find(r=>r.model==='naive'&&r.horizon===7);
  assert.equal(constant.mae,0); assert.equal(constant.baseline_mae,0);
  // Browser facade: every fetch must be a GET. All mutations are local only.
  global.window={location:{origin:'https://demo.example'}};
  const memory=new Map(); let full=false;
  global.localStorage={getItem:k=>memory.get(k)??null,setItem:(k,v)=>{if(full)throw Error('quota');memory.set(k,v)},removeItem:k=>memory.delete(k)};
  const original=global.fetch;
  const published=fixtures.cases[0].dataset;
  const remoteAssets=[{...published,symbol:'AAPL',name:'Apple',kind:'Equity',price:100,change:0,as_of:published.end_date}];
  let unavailable=false;
  global.fetch=async (url,options)=>{
    assert.ok(!options?.method || options.method==='GET','No browser writes may reach the public API');
    if(unavailable) return Response.json({error:'offline'},{status:503});
    const u=new URL(url,'https://demo.example');
    if(u.pathname==='/api/dashboard')return Response.json({assets:remoteAssets,runs:[],pipeline:{}});
    if(u.pathname==='/api/datasets')return Response.json(published);
    if(u.pathname==='/api/prices')return Response.json(published.prices);
    if(u.pathname==='/api/forecast')return Response.json({forecast:fixtures.cases[0].dates.map(date=>({date}))});
    throw Error('Unexpected fetch '+url);
  };
  try {
    const computed=await request('/api/experiments',{symbol:'AAPL',model:'trend',horizon:7});
    assert.equal(computed.execution,'browser'); assert.equal(computed.dataset_id,published.dataset_id);
    let dashboard=await request('/api/dashboard');assert.equal(dashboard.runs.length,1);
    // Replay retains the exact exchange dates even after the published snapshot is unavailable.
    unavailable=true;
    const replay=await request('/api/experiments',{symbol:'AAPL',dataset_id:computed.dataset_id,model:'trend',horizon:7});
    assert.deepEqual(replay.forecast,computed.forecast); unavailable=false;
    const imported=await request('/api/import',{symbol:'AAPL',csv});
    dashboard=await request('/api/dashboard');assert.equal(dashboard.assets[0].dataset_id,imported.dataset_id);
    assert.deepEqual(await request('/api/prices?symbol=AAPL'),rows);
    await request('/api/experiments',{symbol:'AAPL',model:'naive',horizon:30});
    const before=[...memory.values()][0]; full=true;
    await assert.rejects(request('/api/import',{symbol:'MSFT',csv}),/storage unavailable or full/);full=false;
    assert.equal([...memory.values()][0],before,'Quota failure preserves previous saved data');
    await assert.rejects(request('/api/import',{symbol:'AAPL',csv:'date,close\ninvalid,0'}));
    assert.equal((await request('/api/dashboard')).assets[0].dataset_id,imported.dataset_id);
    unavailable=true;assert.equal((await request('/api/dashboard')).assets[0].dataset_id,imported.dataset_id);unavailable=false;
    for(let i=0;i<23;i++) await request('/api/experiments',{symbol:'AAPL',model:'naive',horizon:1});
    assert.equal((await request('/api/dashboard')).runs.length,20,'History is bounded to 20 local runs');
    await request('/api/demo/restore',{symbol:'AAPL'});
    assert.equal((await request('/api/dashboard')).assets[0].dataset_id,published.dataset_id);
    assert.equal((await request('/api/dashboard')).runs.length,20);
    await assert.rejects(request('/api/sync',{symbol:'AAPL'}),/administrator/);
    memory.set('signal-browser-demo-v1','bad json');
    await assert.rejects(request('/api/dashboard'),/Saved demo data is invalid/);
    await request('/api/demo/clear',{symbol:'AAPL'});
    assert.equal((await request('/api/dashboard')).runs.length,0);
  } finally {global.fetch=original;delete global.window;delete global.localStorage}
  console.log(`PASS: ${count} Python parity cases, CSV validation, private imports, exact-dataset replay, storage recovery and no HTTP writes`);
}
main().catch(e=>{console.error(e);process.exitCode=1});
