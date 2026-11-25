import {chromium} from '@playwright/test';import fs from 'node:fs';
const browser=await chromium.launch();const page=await browser.newPage({ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}});
await page.goto('https://localhost:5174/login');await page.getByLabel('Email',{exact:true}).fill('fixture-owner@example.invalid');await page.getByLabel('Password',{exact:true}).fill(fs.readFileSync('../.local/frontend-test-password','utf8'));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/overview');
const directory='../docs/frontend/screenshots';fs.mkdirSync(directory,{recursive:true});
for(const route of ['overview','body','breathing','sleep-activity','journal','labs','doctor-review','settings']){
 await page.goto('https://localhost:5174/'+route);await page.waitForFunction(()=>document.querySelectorAll('.card').length>=2&&!document.querySelector('.skeleton'));await page.waitForTimeout(250);
 for(const width of [1440,1024,768,390,320]){await page.setViewportSize({width,height:1000});await page.waitForTimeout(100);const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)console.log('Overflow:',route,width);if([1440,1024,390].includes(width))await page.screenshot({path:directory+'/'+route+'-'+width+'.png',fullPage:true});}
 console.log('Captured',route);
}
await browser.close();
