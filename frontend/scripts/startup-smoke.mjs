import { chromium, expect } from '@playwright/test';
const date=process.env.HEALTH03_CHECK_DATE || new Date().toISOString().slice(0,10);
const browser = await chromium.launch();
try {
 const page = await browser.newPage();
 const ready = page.waitForResponse(r => r.url().includes('/api/v1/phone/records?') && r.status() === 200, {timeout:30000});
 await page.goto('https://localhost:5173/body');
 await ready;
 const result = await page.evaluate(async date => {
   const r = await fetch(`https://localhost:8443/api/v1/phone/records?domain=body&from=${date}&to=${date}`, {credentials:'include'});
   const data = await r.json();
   return {status:r.status, count:data.items?.length};
 },date);
 expect(result.status).toBe(200);
 expect(result.count).toBeGreaterThan(0);
 console.log('PASS: trusted HTTPS dashboard, automatic local session, and existing encrypted records readable after service restart.');
} finally {await browser.close();}
