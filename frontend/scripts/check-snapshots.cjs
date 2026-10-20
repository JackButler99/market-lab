const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
require.extensions['.ts'] = (m, filename) => m._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS},
}).outputText, filename);
const {selectSnapshot, snapshotRead} = require('../app/api/snapshot.ts');
const {proxyRead} = require('../app/api/proxy.ts');
const record = {dataset:{dataset_id:'dataset',prices:[{close:1}]},prices:[{close:1}],forecasts:{'trend:7':{dataset_id:'dataset'}},fundamentals:{saved:{snapshot_id:'snapshot',has_data:true},insights:{latest:{period:'latest'},'2025-09-30':{period:'2025-09-30'}}}};
const bundle = {schema:1,generated_at:new Date().toISOString(),symbols:{AAPL:record,BTCUSD:record},dashboard:{assets:[]},automation:{mode:'scheduled_snapshot'},fundamental_automation:{mode:'scheduled_snapshot'}};
async function check() {
  const call = (route, query='') => selectSnapshot(bundle,route,new URLSearchParams(query));
  assert.equal(call('fundamentals/insights','snapshot_id=wrong').status,409);
  assert.equal(call('fundamentals/insights','symbol=BTCUSD&period=2025-09-30').status,400);
  assert.equal(call('fundamentals/insights','period=unknown').status,404);
  assert.deepEqual(await call('fundamentals/insights','period=2025-09-30').json(),{period:'2025-09-30'});
  assert.deepEqual(await call('datasets','id=dataset').json(),record.dataset);
  assert.equal((await call('datasets').json())[0].prices,undefined);
  assert.deepEqual(await call('forecast','dataset_id=dataset').json(),{dataset_id:'dataset'});
  assert.equal(await call('forecast','dataset_id=old').json(),null);
  assert.equal(call('unknown').status,404);
  const old = {...bundle,generated_at:'2020-01-01T00:00:00Z'};
  assert.equal((await selectSnapshot(old,'automation',new URLSearchParams()).json()).snapshot_stale,true);
  process.env.DEPLOYMENT_MODE='snapshot'; process.env.SNAPSHOT_REPOSITORY='owner/repo';
  const original=global.fetch;
  try {
    global.fetch=async url=>{assert.equal(url,'https://raw.githubusercontent.com/owner/repo/market-data/bundle.json'); return Response.json(bundle)};
    assert.equal((await proxyRead(new Request('https://demo/api/dashboard'),['dashboard'])).status,200);
    global.fetch=async()=>new Response('missing',{status:404});
    assert.equal((await snapshotRead(new Request('https://demo/api/dashboard'),['dashboard'])).status,503);
    process.env.SNAPSHOT_REPOSITORY='https://attacker.example';
    assert.equal((await snapshotRead(new Request('https://demo/api/dashboard'),['dashboard'])).status,503);
  } finally { global.fetch=original; delete process.env.DEPLOYMENT_MODE; delete process.env.SNAPSHOT_REPOSITORY; }
  console.log('PASS: period/snapshot isolation, dataset/forecast consistency, stale metadata, mode routing and safe fetch errors');
}
check().catch(e=>{console.error(e);process.exitCode=1});
