import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir, stat } from 'node:fs/promises';
import { resolve, extname, join } from 'node:path';
import assert from 'node:assert/strict';
const root = resolve('doc/dist'), out = resolve('test-results/screenshots');
await mkdir(out,{recursive:true});
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.svg':'image/svg+xml','.glb':'model/gltf-binary'};
const server=createServer(async(req,res)=>{
  try {
    let file=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://local').pathname));
    if (!file.startsWith(root+'/')) throw new Error('path');
    if ((await stat(file)).isDirectory()) file=join(file,'index.html');
    res.writeHead(200,{'content-type':types[extname(file)]??'application/octet-stream'});res.end(await readFile(file));
  } catch {res.writeHead(404);res.end('Not found');}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--enable-unsafe-swiftshader']});
async function ready(page){await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('表示中'),{},{timeout:30000});}
async function shot(page,name){await page.screenshot({path:join(out,`a7-${name}.png`),fullPage:true});}
try {
 for (const mobile of [false,true]) {
  const label=mobile?'mobile':'desktop';
  const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:1000},isMobile:mobile,hasTouch:mobile,deviceScaleFactor:1});
  const page=await context.newPage(),errors=[],bad=[],models=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('response',r=>{if(r.status()>=400)bad.push(r.url());if(r.url().endsWith('.glb'))models.push(r.url());});
  await page.goto(base+'/a7-preview/');
  assert.equal(await page.locator('canvas').count(),0);assert.equal(models.length,0);
  await page.locator('#start').click();await ready(page);
  assert.equal(await page.locator('canvas').count(),1);assert.ok(models[0].endsWith('/3hp.glb'));
  assert.ok(await page.locator('#part option').count()>60);
  assert.match(await page.locator('#dimensions').innerText(),/14.9 × 128.5/);
  await shot(page,`${label}-assembled`);
  const assembled=await page.locator('canvas').screenshot();
  for(const view of ['front','side','rear','iso']) {await page.locator(`[data-view=${view}]`).click();await page.waitForTimeout(80);await shot(page,`${label}-${view}`);}
  await page.locator('#explode').check();await page.waitForTimeout(80);assert.notDeepEqual(await page.locator('canvas').screenshot(),assembled);await shot(page,`${label}-exploded`);
  await page.locator('#reset').click();await page.waitForTimeout(80);assert.deepEqual(await page.locator('canvas').screenshot(),assembled,'reset restores assembled scene');
  await page.locator('#part').selectOption('controller_pcb_A7');assert.match(await page.locator('#part-info').innerText(),/制御基板/);
  await page.locator('#isolate').click();assert.equal(await page.locator('#groups input:checked').count(),1);await shot(page,`${label}-isolated`);
  await page.locator('#fit').click();await page.locator('#show-all').click();assert.equal(await page.locator('#groups input:checked').count(),6);
  for(const input of await page.locator('#groups input').all())await input.uncheck();assert.match(await page.locator('#status').innerText(),/表示部品がありません/);await page.locator('#show-all').click();
  await page.locator('#reset').click();
  const canvas=page.locator('canvas');await canvas.scrollIntoViewIfNeeded();const box=await canvas.boundingBox();
  if (mobile) {
    const cdp=await context.newCDPSession(page);
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width/2,y:box.y+box.height/2}]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:box.x+box.width/2+40,y:box.y+box.height/2+20}]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  } else {await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+60,box.y+box.height/2+30,{steps:5});await page.mouse.up();await page.mouse.wheel(0,-100);}
  await page.waitForTimeout(100);assert.notDeepEqual(await canvas.screenshot(),assembled,'orbit/touch changes rendered geometry');
  await page.locator('#stage').focus();await page.keyboard.press('ArrowRight');await page.keyboard.press('Shift+ArrowUp');await page.keyboard.press('+');
  for(const [id,width] of [['2hp','9.8'],['3hp_pet','14.9'],['3hp','14.9']]){await page.locator('#variant').selectOption(id);await ready(page);assert.ok((await page.locator('#dimensions').innerText()).includes(width));}
  await page.locator('#close').click();assert.equal(await page.locator('canvas').count(),0);await page.locator('#start').click();await ready(page);assert.equal(await page.locator('canvas').count(),1);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);assert.deepEqual(bad,[]);
  await page.goto(base+'/docs/project/a7-preview/');
  const frame=page.frameLocator('iframe[title*="A7"]');await frame.locator('#start').click();await frame.locator('#status').filter({hasText:'表示中'}).waitFor();
  await page.locator('main a[href="/docs/project/a7/"]').last().click();await page.waitForURL(/\/docs\/project\/a7\/$/);
  await page.locator('main a[href="/docs/project/a7-preview/"]').first().click();await page.waitForURL(/\/a7-preview\/$/);
  assert.equal(await page.locator('iframe').count(),1);assert.equal(await page.frameLocator('iframe').locator('canvas').count(),0);
  await page.frameLocator('iframe').locator('#start').click();await page.frameLocator('iframe').locator('#status').filter({hasText:'表示中'}).waitFor();assert.equal(await page.frameLocator('iframe').locator('canvas').count(),1);
  await context.close();console.log(`PASS A7 ${label}: real GLB, presets, explode/reset, isolation/visible fit, input, variants, close/remount, navigation`);
 }
 for(const failure of ['missing-model','webgl']) {
  const context=await browser.newContext();const page=await context.newPage();
  if(failure==='missing-model')await page.route('**/3hp.glb',r=>r.fulfill({status:404,body:'Missing test fixture'}));
  else await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type.startsWith('webgl')?null:original.call(this,type,...args);};});
  await page.goto(base+'/a7-preview/');await page.locator('#start').click();await page.locator('#error').waitFor({state:'visible'});
  assert.equal(await page.locator('canvas').count(),0);assert.equal(await page.locator('#poster').isVisible(),true);assert.match(await page.locator('#error').innerText(),/側面図/);await shot(page,failure);await context.close();console.log(`PASS A7 ${failure} fallback`);
 }
} finally {await browser.close();await new Promise(r=>server.close(r));}
