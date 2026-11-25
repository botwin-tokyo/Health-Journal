import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
const routes=['overview','body','breathing','sleep-activity','journal','labs','doctor-review','settings'];
test('synthetic API routes, accessibility and memory-only storage',async({page},info)=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/login');
 await page.getByLabel('Email',{exact:true}).fill('fixture-owner@example.invalid');
 await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Overview',exact:true,level:1})).toBeVisible();
 for(const route of routes){
  await page.goto('/'+route);
  await expect(page.locator('h1')).toBeVisible();
  await page.waitForFunction(()=>document.querySelectorAll(".card").length>=2 && document.querySelectorAll(".skeleton").length===0);
  await page.waitForTimeout(500);
  expect(await page.getByRole('alert').allTextContents(),route).toEqual([]);
  const results=await new AxeBuilder({page}).analyze();
  expect.soft(results.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),route).toEqual([]);
  await page.screenshot({path:`test-results/${info.project.name}-${route}.png`,fullPage:true});
 }
 expect(errors).toEqual([]);
 expect(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}))).toEqual({local:0,session:0});
 await page.setViewportSize({width:320,height:780});await page.goto('/body');await expect(page.locator('h1')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('local desktop opens directly without login',async({page})=>{
 await page.goto('https://localhost:5173/overview');
 await expect(page.getByRole('heading',{name:'Overview',exact:true,level:1})).toBeVisible();
 await expect(page.locator('input[type=password]')).toHaveCount(0);
});

test('atomic weight and private note save through the actual Pi API',async({page})=>{
 await page.goto('/login');
 await page.getByLabel('Email',{exact:true}).fill('fixture-owner@example.invalid');
 await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.waitForURL('**/overview');await page.goto('/body');
 await page.getByLabel('Record date',{exact:true}).fill('2026-11-08');
 await expect(page.getByLabel('Weight',{exact:true})).toBeVisible();
 await page.getByLabel('Weight',{exact:true}).fill('156.125');
 await page.getByLabel('Private note (optional)').fill('Synthetic atomic note');
 const replacement=page.getByLabel('Replace the existing morning selection');if(await replacement.count())await replacement.check();
 const saved=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/body/weights'&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Save reading',exact:true}).click();
 const response=await saved;expect(response.status()).toBe(200);
 const result=await response.json();expect(result.data.value).toBe('156.125');
 await expect(page.getByRole('alert')).toHaveCount(0);
 await page.goto('/journal');
 await expect(page.getByRole('button').filter({hasText:'Synthetic atomic note'})).toHaveCount(0);
 const stored=await page.evaluate(async()=>{const r=await fetch('https://localhost:8444/api/v1/journal/entries?from=2026-11-08&to=2026-11-08',{credentials:'include',cache:'no-store'});return r.json();});
 expect(stored.items.some((r:{data:{text:string;visibility:string}})=>r.data.text==='Synthetic atomic note'&&r.data.visibility==='private')).toBe(true);
});

test('two doctor scopes exclude private journal payloads',async({page})=>{
 for(const email of ['doctor-a@example.invalid','doctor-b@example.invalid']){
  await page.context().clearCookies();await page.goto('/login');
  await page.getByLabel('Email',{exact:true}).fill(email);
  await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:/Open shared journal/}).click();
  await expect(page.getByRole('heading',{name:'Overview',exact:true,level:1})).toBeVisible();
  const result=await page.evaluate(async()=>{const get=async(path:string)=>{const response=await fetch('https://localhost:8444/api/v1/'+path,{credentials:'include',cache:'no-store'});return response.json();};return {journal:await get('journal/entries?from=2026-10-01&to=2026-11-30'),body:await get('body?date=2026-11-07'),breathing:await get('breathing?date=2026-11-07')};});
  expect(result.journal.items).toEqual([]);
  expect(JSON.stringify(result)).not.toContain('Synthetic fixture only.');
  if(email.startsWith('doctor-a')){expect(result.body.items.length).toBeGreaterThan(0);expect(result.breathing.items).toEqual([]);}else{expect(result.body.items).toEqual([]);expect(result.breathing.items.length).toBeGreaterThan(0);}
  await expect(page.getByRole('link',{name:'Settings',exact:true})).toHaveCount(0);
 }
});

test('freezes selected revisions and saves versioned preferences',async({page})=>{
 await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill('fixture-owner@example.invalid');await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/overview');
 page.on('response',r=>{if(r.status()>=400)console.log('Report test HTTP',r.status(),new URL(r.url()).pathname);});
 await page.goto('/doctor-review');await page.locator('input[type=checkbox]').first().check();
 const frozen=page.waitForResponse(r=>r.url().includes('/snapshots')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Freeze report preview',exact:true}).click();
 const response=await frozen;expect(response.status()).toBe(200);const snapshot=await response.json();expect(snapshot.data.sections.length).toBe(1);
 await expect(page.getByText('Frozen snapshot',{exact:true})).toBeVisible();
 await page.goto('/settings');await page.getByLabel('Display name',{exact:true}).fill('Fictional acceptance owner');
 const saved=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/settings'&&r.request().method()==='PATCH');await page.getByRole('button',{name:'Save changes',exact:true}).click();expect((await saved).status()).toBe(200);
 await expect(page.getByRole('alert')).toHaveCount(0);
});

test('local PDF import review and protected report download',async({page})=>{
 test.setTimeout(90000);
 await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill('fixture-owner@example.invalid');await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/overview');
 await page.goto('/labs');await page.locator('input[type=file]').setInputFiles('/tmp/health03-synthetic-lab.pdf');
 await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByLabel('Reporting laboratory',{exact:true}).fill('Fictional laboratory');await page.getByLabel('Collection date (leave blank if absent)').fill('2026-11-07');await page.getByLabel('Source report status').selectOption('final');await page.getByLabel('I confirmed this report belongs to the intended patient.').check();
 await page.getByLabel('Test name',{exact:true}).fill('Fictional analyte');await page.getByLabel('Exact original result text').fill('5.00');await page.getByLabel('Numeric value').fill('5.00');await page.getByLabel('Unit',{exact:true}).fill('mg/L');
 await page.waitForTimeout(3000);await page.getByRole('button',{name:'Save review draft',exact:true}).click();
 await page.getByRole('button',{name:'Publish reviewed results',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('button',{name:'Open original',exact:true}).click();await page.getByText('Accessible extracted page text',{exact:true}).click();await expect(page.getByText(/Fictional laboratory report/).last()).toBeVisible();
 await page.goto('/doctor-review');await page.locator('input[type=checkbox]').first().check();await page.getByRole('button',{name:'Freeze report preview',exact:true}).click();await page.getByRole('button',{name:'Prepare PDF from this snapshot'}).click();await page.getByRole('button',{name:'Prepare export',exact:true}).click();
 const downloadEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Download report',exact:true}).click({timeout:45000});const download=await downloadEvent;const path=await download.path();expect(fs.readFileSync(path!).subarray(0,5).toString()).toBe('%PDF-');
});

test('accepted deletion ends the session without further bootstrap',async({page})=>{
 test.skip(process.env.HEALTH03_DELETE_FIXTURE!=='1','Opt-in final teardown of the isolated fixture owner');
 await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill('fixture-owner@example.invalid');await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/overview');await page.goto('/settings');
 await page.getByRole('button',{name:'Delete account and records',exact:true}).click();await page.getByRole('dialog').getByRole('checkbox').check();await page.getByRole('button',{name:'Delete account and records',exact:true}).last().click();await expect(page.getByRole('heading',{name:'Journal closed',exact:true})).toBeVisible();
 const requests:string[]=[];page.on('request',r=>requests.push(new URL(r.url()).pathname));await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));await page.waitForTimeout(300);expect(requests.filter(p=>p.includes('/session')||p.includes('/bootstrap'))).toEqual([]);
});
