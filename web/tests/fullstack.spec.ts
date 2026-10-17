import {expect,test} from '@playwright/test';
test('real same-origin sample library, search, Ask, playback and Range',async({page})=>{
 test.skip(!process.env.VM_FULLSTACK,'Start an isolated loopback backend and set VM_FULLSTACK=1; no provider calls.');
 await page.goto('/');await expect(page.getByText('Workshop safety: prepare the bench',{exact:true})).toBeVisible();
 await page.getByText('Workshop safety: prepare the bench',{exact:true}).click();
 await expect.poll(()=>page.locator('video').evaluate(v=>(v as HTMLVideoElement).readyState),{timeout:15000}).toBeGreaterThanOrEqual(1);
 await page.locator('[data-cue="1"]').click();
 await expect.poll(()=>page.locator('video').evaluate(v=>(v as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(29);
 await page.goto('/search?q=workbench');await expect(page.getByText('Clear the workbench and check equipment before starting.',{exact:true}).first()).toBeVisible();
 await page.goto('/ask');await page.getByPlaceholder('Ask anything about the videos…').fill('How should I prepare the bench?');await page.getByRole('button',{name:'Ask',exact:true}).click();
 await expect(page.getByText(/Sample evidence extract/)).toBeVisible();await page.getByRole('button',{name:'1',exact:true}).click();await expect(page.locator('video')).toBeVisible();
 const range=await page.request.get('/sample/video.mp4',{headers:{Range:'bytes=0-31'}});expect(range.status()).toBe(206);expect((await range.body()).length).toBe(32);
 expect((await page.request.get('/api/videos')).status()).toBe(401);
 await page.goto('/experiments');await expect(page.getByRole('heading',{name:'Experiments',exact:true})).toBeVisible();await expect(page.getByText(/Synthetic UI fixture/).first()).toBeVisible();
});
