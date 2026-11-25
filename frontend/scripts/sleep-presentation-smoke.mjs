import {chromium, expect} from '@playwright/test';
const browser=await chromium.launch();
try {
 const page=await browser.newPage();
 const date=process.env.HEALTH03_CHECK_DATE || new Date().toISOString().slice(0,10);
 const ready=page.waitForResponse(r=>r.url().includes('/api/v1/sleep-activity?')&&r.status()===200,{timeout:30000});
 await page.goto('https://localhost:5173/sleep-activity');await ready;
 await page.getByLabel('Record date',{exact:true}).fill(date);
 const data=await page.evaluate(async date=>{
  const r=await fetch(`https://localhost:8443/api/v1/sleep-activity?date=${date}`,{credentials:'include'});
  if(!r.ok)throw Error('Sleep API failed');return r.json();
 },date);
 const sessions=page.locator('section.card').filter({has:page.getByRole('heading',{name:'Sleep sessions',exact:true})});
 await expect(sessions.locator('div.card')).toHaveCount(data.sleep_sessions.length);
 for(const row of data.sleep_sessions){
  if(!row.data.complete) await expect(sessions.getByText('Partial session · direct ring',{exact:true}).first()).toBeVisible();
 }
 const workouts=page.locator('section.card').filter({has:page.getByRole('heading',{name:'Completed workout',exact:true})});
 for(const row of data.workouts)await expect(workouts.getByText(row.data.routine_snapshot?.name || row.data.activity,{exact:true})).toBeVisible();
 if(data.step_records.length) {
  expect(data.steps.value).toBe(data.step_records[0].data.value);
  await expect(page.locator('.metric').filter({has:page.getByText('Phone steps',{exact:true})}).locator('.value')).toContainText(String(data.steps.value));
 }
 if(data.workouts.length>1)expect(Number(data.workout_total_seconds)).toBeGreaterThan(0);
 console.log(JSON.stringify({verified:true,sleep_sessions:data.sleep_sessions.length,workouts:data.workouts.length,independent_step_total:data.steps.value!=null,observation_pagination:!!data.cursor}));
}finally{await browser.close()}
