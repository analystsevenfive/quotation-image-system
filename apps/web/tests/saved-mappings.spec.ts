import { test, expect } from '@playwright/test';
import path from 'node:path';

test('saved SKU mappings workflow (Phase 3)', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  // 1. Visit studio
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'เติมรูปสินค้าให้ใบเสนอราคา' })).toBeVisible();

  // 2. Check header button for Saved Mappings
  const mappingsBtn = page.getByRole('button', { name: 'คู่สินค้าที่จำไว้' });
  await expect(mappingsBtn).toBeVisible();

  // 3. Open Mappings dialog initially
  await mappingsBtn.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('heading', { name: /คู่สินค้าที่ระบบจำไว้/ })).toBeVisible();
  await page.getByRole('dialog').getByLabel('ปิด').click();
  await expect(page.getByRole('dialog')).not.toBeVisible();

  // 4. Upload QT_test.pdf
  await page.locator('input[accept="application/pdf,.pdf"]').setInputFiles(path.resolve('../../QT_test.pdf'));
  await expect(page.getByRole('heading', { name: 'QT_test.pdf' })).toBeVisible({ timeout: 30000 });
  await expect(page.locator('.react-pdf__Page canvas')).toBeVisible({ timeout: 30000 });

  // 5. Manual select a product for an item to trigger persistent mapping
  // Item 1 is missing, select CSHL550
  await page.getByRole('button', { name: 'เปลี่ยนสินค้า / รูป' }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('dialog').getByRole('button').filter({ hasText: 'CSHL550' }).first().click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.getByText('เลือกแล้ว', { exact: true })).toBeVisible();

  // 6. Verify mapping appears in "คู่สินค้าที่จำไว้"
  await mappingsBtn.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog').getByText('CSHL550').first()).toBeVisible();
  await page.getByRole('dialog').getByLabel('ปิด').click();
  await expect(page.getByRole('dialog')).not.toBeVisible();

  // 7. Start fresh and re-upload to verify "จำจากประวัติ" badge is automatically applied!
  await page.getByRole('button', { name: 'เริ่มเอกสารใหม่' }).click();
  await expect(page.getByRole('heading', { name: 'เติมรูปสินค้าให้ใบเสนอราคา' })).toBeVisible();

  // Upload QT_test.pdf again
  await page.locator('input[accept="application/pdf,.pdf"]').setInputFiles(path.resolve('../../QT_test.pdf'));
  await expect(page.getByRole('heading', { name: 'QT_test.pdf' })).toBeVisible({ timeout: 30000 });

  // Item 1 should now be auto-matched with "จำจากประวัติ" badge!
  await expect(page.getByText('จำจากประวัติ').first()).toBeVisible({ timeout: 15000 });

  // 8. Generate PDF and verify download works
  await page.getByRole('button', { name: 'สร้าง PDF โดยข้ามรูปที่ยังไม่มี' }).click();
  await expect(page.getByText('PDF พร้อมดาวน์โหลด', { exact: true })).toBeVisible({ timeout: 90000 });
  await expect(page.getByRole('link', { name: 'ดาวน์โหลด PDF' })).toBeVisible();

  expect(errors).toEqual([]);
});
