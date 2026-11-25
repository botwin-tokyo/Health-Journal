import {chromium, expect} from '@playwright/test';
const date=process.env.HEALTH03_CHECK_DATE || new Date().toISOString().slice(0,10);
const browser=await chromium.launch();
try {
 const page=await browser.newPage();
 const ready=page.waitForResponse(r=>r.url().includes('/api/v1/phone/records?')&&r.status()===200,{timeout:30000});
 await page.goto('https://localhost:5173/body');
 await ready;
 for(const domain of ['body','breathing','sleep']) {
  const {status, result}=await page.evaluate(async ({domain,date})=>{
   const response=await fetch(`https://localhost:8443/api/v1/phone/records?domain=${domain}&from=${date}&to=${date}`,{credentials:'include'});
   return {status:response.status,result:await response.json()};
  },{domain,date});
  expect(status, JSON.stringify(result.error || result.code || "reader")).toBe(200);
  expect(result.items.length).toBeGreaterThan(0);
  console.log(domain, 'owner reader OK;',result.items.length,'records on first page');
 }
}finally{await browser.close();}
