import {expect,test,Page} from '@playwright/test';

async function session(page:Page){
  await page.route('**/api/providers',r=>r.fulfill({json:{config_version:1,providers:{mock:{destination:'mock.invalid'}},features:{'live.camera1.scene':{enabled:true,providers:['mock']},'audio.transcription':{enabled:true,providers:['mock']}}}}));
  await page.route('**/api/live/sessions',r=>r.fulfill({json:{session_id:'release-session',config_version:1}}));
  await page.route('**/api/live/sessions/release-session',r=>r.fulfill({json:{deleted:true}}));
  await page.goto('/live');await page.getByRole('button',{name:'Authorize analysis session'}).click();
  await expect(page.getByRole('button',{name:'Authorize analysis session'})).toBeDisabled();
}

test('permission denial shows an error without uploading',async({page})=>{
  let uploaded=false;await page.route('**/api/live/sessions/*/frames',r=>{uploaded=true;return r.abort();});
  await page.addInitScript(()=>Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:()=>Promise.reject(new DOMException('Camera permission denied','NotAllowedError'))}));
  await page.goto('/live');await page.getByRole('button',{name:'Start preview'}).first().click();
  await expect(page.locator('main').getByRole('alert')).toContainText('permission denied');expect(uploaded).toBe(false);
});

for(const mismatch of ['frame','config','dimensions','box']){
  test(`rejects ${mismatch} mismatch and permits a later matching observation`,async({page})=>{
    let attempt=0;
    await session(page);
    await page.route('**/api/live/sessions/release-session/frames',async r=>{
      const body=r.request().postDataJSON();attempt++;
      const data={...body,session_id:'release-session',source_width:640,source_height:480,observed_at:new Date().toISOString(),detections:[{detection_id:'d',label:'hand',bbox_xyxy:[.1,.1,.5,.5],confidence:.9,source:'mock'}],decisions:[],provider_results:[{provider:'mock',status:'ok',latency_ms:1}],warnings:[]};
      if(attempt===1){
        if(mismatch==='frame')data.frame_id+=1;
        if(mismatch==='config')data.config_version+=1;
        if(mismatch==='dimensions')data.source_width+=1;
        if(mismatch==='box')data.detections[0].bbox_xyxy=[0,0,2,1];
      }
      await r.fulfill({json:data});
    });
    await page.getByRole('button',{name:'Start preview'}).first().click();
    await page.getByLabel('camera1 FPS').fill('0.1');
    await page.getByLabel('camera1 send frames').check();
    await page.getByRole('button',{name:'Analyze now'}).first().click();
    await expect.poll(()=>attempt).toBe(1);
    await expect(page.locator('main').getByRole('alert')).toContainText('Discarded');
    await expect(page.getByLabel('camera1 detection overlay')).toHaveCount(0);
    await expect(page.getByText('No frames sent.',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Analyze now'}).first().click();
    await expect(page.getByLabel('camera1 detection overlay')).toBeVisible();
  });
}

test('stopping a camera discards its delayed result',async({page})=>{
  await session(page);let received=false;let release:()=>void=()=>{};
  const held=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/live/sessions/release-session/frames',async r=>{
    received=true;const body=r.request().postDataJSON();await held;
    await r.fulfill({json:{...body,session_id:'release-session',source_width:640,source_height:480,observed_at:new Date().toISOString(),detections:[],decisions:[],provider_results:[],warnings:[]}}).catch(()=>{});
  });
  await page.getByRole('button',{name:'Start preview'}).first().click();await page.getByLabel('camera1 send frames').check();
  await page.getByRole('button',{name:'Analyze now'}).first().click();await expect.poll(()=>received).toBe(true);
  await page.getByRole('button',{name:'Stop camera'}).first().click();release();
  await expect(page.getByLabel('camera1 detection overlay')).toHaveCount(0);await expect(page.getByText('No frames sent.',{exact:true})).toBeVisible();
});

test('a pending camera permission grant after navigation stops the returned tracks',async({page})=>{
  await page.addInitScript(()=>Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:()=>new Promise<MediaStream>(resolve=>Object.assign(window,{resolveCamera:resolve}))}));
  await page.goto('/live');await page.getByRole('button',{name:'Start preview'}).first().click();
  await page.getByRole('link',{name:'Models & Routing',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Models & Routing',exact:true})).toBeVisible();
  await page.evaluate(()=>{
    const canvas=document.createElement('canvas');const s=canvas.captureStream(1);
    Object.assign(window,{lateTracks:s.getTracks()});
    (window as unknown as {resolveCamera:(stream:MediaStream)=>void}).resolveCamera(s);
  });
  await expect.poll(()=>page.evaluate(()=>(window as unknown as {lateTracks:MediaStreamTrack[]}).lateTracks.every(t=>t.readyState==='ended'))).toBe(true);
});

test('device contention is reported and track end stops the preview',async({page})=>{
  await page.addInitScript(()=>{
    const real=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);let used=false;
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:(c:MediaStreamConstraints)=>{if(used)return Promise.reject(new DOMException('Device busy','NotReadableError'));used=true;return real(c);}});
  });
  await page.goto('/live');await page.getByRole('button',{name:'Start preview'}).first().click();
  await expect.poll(()=>page.locator('video').first().evaluate(v=>(v as HTMLVideoElement).videoWidth)).toBeGreaterThan(0);
  await page.getByRole('button',{name:'Start preview'}).nth(1).click();await expect(page.locator('main').getByRole('alert')).toContainText('Device busy');
  await page.locator('video').first().evaluate(v=>((v as HTMLVideoElement).srcObject as MediaStream).getVideoTracks()[0].dispatchEvent(new Event('ended')));
  expect(await page.locator('video').first().evaluate(v=>(v as HTMLVideoElement).srcObject)).toBeNull();
});

test('hiding the page stops microphone capture without uploading audio',async({page})=>{
  let uploads=0;
  await page.addInitScript(()=>{
    const real=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async(c:MediaStreamConstraints)=>{const s=await real(c);if(c.audio)Object.assign(window,{microphoneTracks:s.getTracks()});return s;}});
  });
  await session(page);await page.route('**/api/live/sessions/release-session/transcribe',r=>{uploads++;return r.fulfill({json:{text:'synthetic speech'}});});
  await page.getByRole('button',{name:'Push to talk (send up to 15 seconds)'}).click();
  await expect(page.getByRole('button',{name:'Stop and send audio'})).toBeVisible();
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
  await expect.poll(()=>page.evaluate(()=>(window as unknown as {microphoneTracks:MediaStreamTrack[]}).microphoneTracks.every(t=>t.readyState==='ended'))).toBe(true);
  expect(uploads).toBe(0);
});

test('recorder errors release microphone tracks and discard audio',async({page})=>{
  let uploads=0;
  await page.addInitScript(()=>{
    const real=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async(c:MediaStreamConstraints)=>{const s=await real(c);if(c.audio)Object.assign(window,{microphoneTracks:s.getTracks()});return s;}});
    const start=MediaRecorder.prototype.start;
    MediaRecorder.prototype.start=function(...args:Parameters<MediaRecorder['start']>){start.apply(this,args);setTimeout(()=>this.dispatchEvent(new Event('error')),20);};
  });
  await session(page);await page.route('**/api/live/sessions/release-session/transcribe',r=>{uploads++;return r.abort();});
  await page.getByRole('button',{name:'Push to talk (send up to 15 seconds)'}).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('capture stopped');
  expect(await page.evaluate(()=>(window as unknown as {microphoneTracks:MediaStreamTrack[]}).microphoneTracks.every(t=>t.readyState==='ended'))).toBe(true);
  expect(uploads).toBe(0);
});
