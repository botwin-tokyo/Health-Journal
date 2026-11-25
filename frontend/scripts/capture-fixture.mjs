// Explicit synthetic server only; never point this at the owner's journal.
import {chromium} from '@playwright/test';import fs from 'node:fs';
const browser=await chromium.launch();const page=await browser.newPage({ignoreHTTPSErrors:true});
await page.goto('https://localhost:5174/login');await page.getByLabel('Email',{exact:true}).fill('fixture-owner@example.invalid');await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/overview');
const fixture=await page.evaluate(async()=>{
 const base='https://localhost:8444';const get=async(path)=>{const response=await fetch(base+path,{credentials:'include',cache:'no-store'});if(!response.ok)throw Error('Fixture endpoint failed: '+path);return response.json();};
 const session=await get('/api/v1/session');if(session.sample_data!==true)throw Error('Synthetic session required');
 const data={};for(const route of ['overview','body','breathing','sleep-activity','journal/entries','journal/questions','journal/medication-events','labs/reports','labs/trends','settings','security/status','sharing/grants','devices','sync/status','baselines'])data['/api/v1/'+route]=await get('/api/v1/'+route+'?date=2026-11-07&from=2026-10-11&to=2026-11-07&weight_unit=lb');
 data['/api/v1/security/sessions']={items:[]};
 data['/api/v1/session']={...session,csrf_token:'synthetic-only',permission_epoch:'synthetic-epoch',auth_actions:[]};return data;
});fs.writeFileSync('../contracts/fixtures/health03-v1/responses.json',JSON.stringify(fixture,null,2)+'\n');await browser.close();console.log('Captured synthetic API fixture only.');
