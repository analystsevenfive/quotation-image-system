import {test, expect} from '@playwright/test';
import path from 'node:path';
import type {Quotation} from '../src/lib/api';

test('inline Canva-style image crop directly on PDF: click crop, handles, double click, apply and revert', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');

  // 1. Upload quotation PDF
  const uploaded = page.waitForResponse(
    (r) => r.url().endsWith('/api/quotations') && r.request().method() === 'POST'
  );
  await page
    .locator('input[accept="application/pdf,.pdf"]')
    .setInputFiles(path.resolve('../../QT_test.pdf'));
  let quotation: Quotation = await (await uploaded).json();

  await expect(page.getByTestId('pdf-preview')).toHaveAttribute('data-rendered', 'true');
  const overlay0 = page.getByTestId('image-overlay-0');
  await expect(overlay0).toBeVisible();

  // 2. Click "ครอบตัด" on PDF toolbar -> enters inline Canva crop mode
  await expect(page.getByRole('button', {name: 'ครอบตัด', exact: true})).toBeEnabled();
  await page.getByRole('button', {name: 'ครอบตัด', exact: true}).click();

  // No separate modal dialog should appear
  await expect(page.getByRole('dialog')).not.toBeVisible();

  // The inline crop box and Canva corner/edge handles appear directly on the PDF
  const inlineCropBox = page.getByTestId('inline-crop-box');
  await expect(inlineCropBox).toBeVisible();
  await expect(page.getByTestId('crop-handle-nw')).toBeVisible();
  await expect(page.getByTestId('crop-handle-se')).toBeVisible();
  await expect(page.getByTestId('apply-inline-crop-pill')).toBeVisible();
  await expect(page.getByText(/โหมดครอบตัดภาพ:\s*รายการ 1/)).toBeVisible();

  // 3. Drag SE handle to adjust crop frame
  const seHandle = page.getByTestId('crop-handle-se');
  const seCorner = (await seHandle.boundingBox())!;
  await page.mouse.move(seCorner.x + seCorner.width / 2, seCorner.y + seCorner.height / 2);
  await page.mouse.down();
  await page.mouse.move(seCorner.x + seCorner.width / 2 - 15, seCorner.y + seCorner.height / 2 - 15, {steps: 6});
  await page.mouse.up();

  // 4. Click "เสร็จสิ้นการครอบตัด" in toolbar to apply
  const croppedUpload = page.waitForResponse(
    (r) => r.url().includes('/items/0/image') && r.request().method() === 'POST'
  );
  await page.getByRole('button', {name: 'เสร็จสิ้นการครอบตัด'}).click();

  const uploadRes = await croppedUpload;
  expect(uploadRes.status()).toBe(200);
  quotation = await uploadRes.json();

  // Inline crop box closes, image stays updated on PDF
  await expect(inlineCropBox).not.toBeVisible();
  expect(quotation.items[0].uploaded_image).toBe(true);

  // 5. Verify "คืนค่ารูป Catalog" button is visible for item 1
  const item1Card = page.locator('article').filter({hasText: '1. CSHL550'});
  await expect(item1Card.getByRole('button', {name: 'คืนค่ารูป Catalog'})).toBeVisible();

  // 6. Test Double-Click directly on image 2 to enter Canva crop mode
  const overlay1 = page.getByTestId('image-overlay-1');
  await expect(overlay1).toBeVisible();
  await overlay1.dblclick();

  // Inline crop box is now active for item 2
  await expect(inlineCropBox).toBeVisible();
  await expect(page.getByText(/โหมดครอบตัดภาพ:\s*รายการ 2/)).toBeVisible();

  // Press Escape to cancel
  await page.keyboard.press('Escape');
  await expect(inlineCropBox).not.toBeVisible();

  // 7. Test sidebar "ครอบตัดรูป" button for item 1
  await item1Card.getByRole('button', {name: 'ครอบตัดรูป'}).click();
  await expect(inlineCropBox).toBeVisible();
  await page.getByTestId('cancel-inline-crop-pill').click();
  await expect(inlineCropBox).not.toBeVisible();

  // 8. Revert item 1 back to catalog image
  const revertResponse = page.waitForResponse(
    (r) => r.url().includes('/items/0/select-product') && r.request().method() === 'POST'
  );
  await item1Card.getByRole('button', {name: 'คืนค่ารูป Catalog'}).click();
  const reverted = await revertResponse;
  expect(reverted.status()).toBe(200);
  quotation = await reverted.json();
  expect(quotation.items[0].uploaded_image).toBe(false);

  // 9. Generate PDF and verify clean output
  const generated = page.waitForResponse(
    (r) => r.url().endsWith('/generate') && r.request().method() === 'POST'
  );
  await page.getByRole('button', {name: 'สร้าง PDF โดยข้ามรูปที่ยังไม่มี'}).click();
  quotation = await (await generated).json();
  expect(quotation.images_inserted).toBe(18);
  await expect(page.getByText('PDF พร้อมดาวน์โหลด', {exact: true})).toBeVisible();

  expect(errors).toEqual([]);
});
