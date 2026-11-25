import {chromium} from '@playwright/test';
const browser=await chromium.launch();
const page=await browser.newPage({ignoreHTTPSErrors:true});
const failures=[];
page.on('pageerror',e=>failures.push(e.message));
page.on('response',r=>{if(r.status()>=400)failures.push(`${r.status()} ${new URL(r.url()).pathname}`)});
for(const route of ['overview','body','breathing','sleep-activity','journal','labs','doctor-review','settings']){
 await page.goto('https://localhost:5173/'+route);
 await page.waitForTimeout(1500);
 console.log(route,JSON.stringify({headings:await page.locator('h1').allTextContents(),alerts:await page.getByRole('alert').allTextContents(),passwords:await page.locator('input[type=password]').count(),failures:failures.splice(0)}));
}
await browser.close();
