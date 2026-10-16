import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests', workers:1, use:{baseURL:process.env.VM_TEST_URL??'http://127.0.0.1:7860',headless:true,
    launchOptions:{executablePath:process.env.CHROMIUM_PATH??'/usr/bin/chromium',args:['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']}, permissions:['camera','microphone']},
});
