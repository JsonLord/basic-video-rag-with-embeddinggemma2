import { expect, test } from '@playwright/test';

test('backup administration distinguishes acceptance from verified completion', async ({page}) => {
  let requested=false;
  await page.route('**/api/admin/backup-status', route => route.fulfill({json:{configured:true,stale:false,last_success:{checkpoint:'checkpoint-verified',created_at:100},pending_uploads:2,encrypted_storage_bytes:2097152,restore_points:['checkpoint-verified','checkpoint-older'],last_recovery_test:{verified:true,checkpoint:'checkpoint-verified',tested_at:100},failure_code:null,queued:requested}}));
  await page.route('**/api/admin/backup', route => {
    expect(route.request().headers().authorization).toBe('Bearer test-admin');requested=true;
    return route.fulfill({json:{accepted:true,completed:false}});
  });
  await page.addInitScript(()=>sessionStorage.setItem('vm-admin-token','test-admin'));
  await page.goto('/backups');
  await page.getByRole('button',{name:'Refresh status'}).click();
  await expect(page.getByText('Verified complete recovery')).toBeVisible();
  await expect(page.getByText('2.00 MiB')).toBeVisible();
  await expect(page.getByText('checkpoint-older',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Back up now'}).click();
  await expect(page.getByRole('status').last()).toContainText('acceptance does not establish success');
  await expect(page.getByText(/Backup queued or running/)).toBeVisible();
});

test('backup administration handles denied access',async({page})=>{
  await page.route('**/api/admin/backup-status',route=>route.fulfill({status:401,json:{detail:'Access denied'}}));
  await page.goto('/backups');
  await expect(page.getByRole('button',{name:'Back up now'})).toBeDisabled();
  await page.getByRole('button',{name:'Refresh status'}).click();
  await expect(page.getByRole('status').last()).toContainText('Access denied');
});
