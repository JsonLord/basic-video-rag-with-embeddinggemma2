import {expect,test} from '@playwright/test';
test('dual simulated previews require explicit transfer and stop on navigation',async({page})=>{
  let frames=0;
  await page.addInitScript(()=>{
    const real=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    const requested:string[]=[];Object.assign(window,{requestedDevices:requested});
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:(c:MediaStreamConstraints)=>{if(c.video&&typeof c.video==='object')requested.push(JSON.stringify(c.video.deviceId));return real(c.video?{video:true,audio:false}:c);}});
    Object.defineProperty(navigator.mediaDevices,'enumerateDevices',{value:async()=>[
      {kind:'videoinput',deviceId:'builtin',label:'Simulated built-in camera',groupId:'g1'},
      {kind:'videoinput',deviceId:'usb',label:'Simulated USB camera',groupId:'g2'},
    ]});
  });
  await page.route('**/api/providers',r=>r.fulfill({json:{config_version:1,providers:{mock:{destination:'mock.invalid'}},features:{'live.camera1.scene':{enabled:true,providers:['mock']},'live.camera2.scene':{enabled:true,providers:['mock']}}}}));
  await page.route('**/api/live/sessions',r=>r.fulfill({json:{session_id:'mock-session',config_version:1}}));
  await page.route('**/api/live/sessions/mock-session/frames',async r=>{
    frames++;const b=r.request().postDataJSON();
    await r.fulfill({json:{...b,session_id:'mock-session',source_width:640,source_height:480,observed_at:new Date().toISOString(),detections:[{detection_id:'d',label:'hand',bbox_xyxy:[.2,.1,.6,.8],confidence:.9,source:'mock'}],decisions:[],provider_results:[{provider:'mock',status:'ok',latency_ms:1}],warnings:[]}});
  });
  await page.route('**/api/live/sessions/mock-session',r=>r.fulfill({json:{deleted:true}}));
  await page.goto('/live');
  await page.getByRole('button',{name:'Grant camera permission & list devices'}).click();
  await expect(page.getByLabel('camera1 device')).toContainText('Simulated built-in camera');
  await page.getByLabel('camera1 device').selectOption('builtin');
  await page.getByLabel('camera2 device').selectOption('usb');
  await page.getByRole('button',{name:'Start preview'}).nth(0).click();
  await page.getByRole('button',{name:'Start preview'}).nth(1).click();
  await expect.poll(()=>page.locator('video').evaluateAll(v=>v.every(e=>(e as HTMLVideoElement).videoWidth>0))).toBe(true);
  expect(frames).toBe(0);
  await page.getByRole('button',{name:'Authorize analysis session'}).click();
  await expect(page.getByLabel('camera1 device')).toHaveValue('builtin');
  await expect(page.getByLabel('camera2 device')).toHaveValue('usb');
  expect(await page.evaluate(()=>(window as unknown as {requestedDevices:string[]}).requestedDevices)).toEqual([JSON.stringify({exact:'builtin'}),JSON.stringify({exact:'usb'})]);
  expect(await page.locator('video').evaluateAll(v=>new Set(v.map(e=>((e as HTMLVideoElement).srcObject as MediaStream).id)).size)).toBe(2);
  await expect(page.getByLabel('camera1 send frames')).toBeEnabled();
  expect(frames).toBe(0);
  await page.getByLabel('camera1 send frames').check();
  await page.getByRole('button',{name:'Analyze now'}).first().click();
  await expect(page.getByLabel('camera1 detection overlay')).toBeVisible();
  const rect=page.getByLabel('camera1 detection overlay').locator('rect');
  const geometry=await rect.boundingBox();const overlay=await page.getByLabel('camera1 detection overlay').boundingBox();expect(geometry!.width/overlay!.width).toBeCloseTo(.4,2);expect((geometry!.x-overlay!.x)/overlay!.width).toBeCloseTo(.2,2);
  await page.locator('section').filter({has:page.getByRole('heading',{name:'Camera 1',exact:true})}).getByRole('checkbox',{name:'Mirror',exact:true}).check();
  const mirrored=await rect.boundingBox();expect((mirrored!.x-overlay!.x)/overlay!.width).toBeCloseTo(.4,2);
  await page.setViewportSize({width:700,height:1000});
  const resized=await rect.boundingBox(),container=await page.getByLabel('camera1 detection overlay').boundingBox();expect(resized!.width/container!.width).toBeCloseTo(.4,2);
  await page.getByLabel('camera1 send frames').uncheck();
  await expect(page.getByLabel('camera1 detection overlay')).toHaveCount(0);
  const before=frames;
  await page.getByRole('button',{name:'Stop camera'}).first().click();
  expect(await page.locator('video').first().evaluate(v=>(v as HTMLVideoElement).srcObject)).toBeNull();
  expect(await page.locator('video').nth(1).evaluate(v=>(v as HTMLVideoElement).srcObject!==null)).toBe(true);
  await page.evaluate(()=>{(window as unknown as {savedTracks:MediaStreamTrack[]}).savedTracks=Array.from(document.querySelectorAll('video')).flatMap(v=>(v.srcObject as MediaStream|null)?.getTracks()??[]);});
  await page.getByRole('link',{name:'Models & Routing',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Models & Routing'})).toBeVisible();
  expect(await page.evaluate(()=>(window as unknown as {savedTracks:MediaStreamTrack[]}).savedTracks.every(t=>t.readyState==='ended'))).toBe(true);
  expect(frames).toBe(before);
});

test('models studio validates and atomically switches a profile',async({page})=>{
  const config={yaml:'version: 1\nprofile: local-preview\nproviders: {}\nfeatures: {}',config_version:1,history:[1],writable:true};
  await page.route('**/api/config',r=>r.fulfill({json:config}));
  await page.route('**/api/config/profiles',r=>r.fulfill({json:{}}));
  await page.route('**/api/config/validate',r=>r.fulfill({json:{valid:true,changed_sections:['profile']}}));
  await page.route('**/api/config/apply',r=>{const body=r.request().postDataJSON();expect(body.expected_version).toBe(1);config.yaml=body.yaml;config.config_version=2;return r.fulfill({json:{config_version:2}});});
  await page.goto('/models');await page.getByRole('button',{name:'Load current config'}).click();
  await expect(page.getByLabel('Routing YAML')).toContainText('local-preview');
  await page.getByLabel('Routing YAML').fill('version: 1\nprofile: hybrid\nproviders: {}\nfeatures: {}');
  await page.getByRole('button',{name:'Validate & preview diff'}).click();
  await expect(page.getByRole('status')).toContainText('changed_sections');
  await page.getByRole('button',{name:'Apply profile atomically'}).click();
  await expect(page.getByRole('status')).toContainText('2');
});
