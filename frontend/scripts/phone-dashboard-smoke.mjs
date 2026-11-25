import {chromium, expect} from '@playwright/test';
const browser=await chromium.launch();
try {
 const page=await browser.newPage();
 let responses=0;
 page.on('response',r=>{if(r.url().includes('/api/v1/overview?')&&r.status()===200)responses++;});
 await page.goto('https://localhost:5173/overview');
 const heart=page.locator('.overviewMetrics .metric').filter({has:page.getByText('Heart rate',{exact:true})});
 await expect(heart.locator('.value')).toContainText(/\d/, {timeout:20000});
 const phone=page.locator('section.card').filter({has:page.getByRole('heading',{name:'Phone readings',exact:true})});
 await expect(phone.locator('.metric').first()).toBeVisible();
 await expect.poll(()=>responses,{timeout:25000}).toBeGreaterThan(1);
 console.log('Overview: heart rate and phone metric cards populated; automatic refresh verified.');
 await page.goto('https://localhost:5173/sleep-activity');
 const observations=page.locator('section.card').filter({has:page.getByRole('heading',{name:'Recorded observations',exact:true})});
 await expect(observations).toBeVisible();
 await expect(observations.getByText('Latest recorded reading',{exact:true}).first()).toBeVisible();
 console.log('Sleep/activity: actual latest readings displayed where no daily aggregate exists.');
} finally {await browser.close();}
