import {chromium,expect} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage({forcedColors:"none",colorScheme:"light"});
 await page.goto((process.env.HEALTH03_SAMPLE_URL || 'http://127.0.0.1:5173') + '/blood-pressure');
 await expect(page.getByText('SAMPLE DATA',{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Saved measurements',exact:true})).toBeVisible();
 await expect(page.getByText('118 / 77',{exact:true})).toHaveCount(2);
 await expect(page.getByText('Measurement time unverified',{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Systolic pressure',exact:true})).toBeVisible();
 await mkdir('../.local/bp-screens',{recursive:true});
 for(const width of [1440,390]) {
  await page.setViewportSize({width,height:1000});
  await page.waitForTimeout(250);
  await page.screenshot({path:`../.local/bp-screens/${width}.png`,fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 }
 console.log('PASS: Blood pressure page renders saved pairs, uncertain date, charts and mobile layout');
}finally{await browser.close();}
