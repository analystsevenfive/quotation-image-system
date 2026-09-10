import {test, expect} from '@playwright/test';
import path from 'path';

test('undo and redo: toolbar buttons, keyboard shortcuts Ctrl+Z / Ctrl+Y, placement resize and inline crop revert', async ({page}) => {
  await page.goto('/');

  // 1. Upload sample PDF
  const fixture = path.resolve('../../QT_test.pdf');
  const uploaded = page.waitForResponse(
    (r) => r.url().endsWith('/api/quotations') && r.request().method() === 'POST'
  );
  await page.locator('input[accept="application/pdf,.pdf"]').setInputFiles(fixture);
  await uploaded;

  await expect(page.getByTestId('pdf-preview')).toBeVisible();
  const overlay0 = page.getByTestId('image-overlay-0');
  await expect(overlay0).toBeVisible();

  const undoBtn = page.getByRole('button', {name: 'ย้อนกลับ (Ctrl+Z)'});
  const redoBtn = page.getByRole('button', {name: 'ทำซ้ำ (Ctrl+Y)'});
  await expect(undoBtn).toBeVisible();
  await expect(redoBtn).toBeVisible();
  await expect(undoBtn).toBeDisabled();
  await expect(redoBtn).toBeDisabled();

  // Select item 0
  await overlay0.click();
  const initialBox = await overlay0.boundingBox();
  expect(initialBox).not.toBeNull();

  // 3. Resize item 0 using "ย่อ" button
  const shrinkRes = page.waitForResponse(
    (res) => res.url().includes('/items/0/placement') && res.request().method() === 'PUT'
  );
  await page.getByRole('button', {name: 'ย่อรูป'}).click();
  await shrinkRes;

  const shrunkBox = await overlay0.boundingBox();
  expect(shrunkBox!.width).toBeLessThan(initialBox!.width);

  // Undo is now enabled, Redo is disabled
  await expect(undoBtn).toBeEnabled();
  await expect(redoBtn).toBeDisabled();

  // 4. Click "ย้อนกลับ" button
  const undoRes1 = page.waitForResponse(
    (res) => res.url().includes('/undo') && res.request().method() === 'POST'
  );
  await undoBtn.click();
  await undoRes1;
  await expect(undoBtn).toBeDisabled();
  await expect(redoBtn).toBeEnabled();

  // Box returns to initial size
  const restoredBox = await overlay0.boundingBox();
  expect(Math.abs(restoredBox!.width - initialBox!.width)).toBeLessThanOrEqual(2);

  // 5. Click "ทำซ้ำ" button
  const redoRes1 = page.waitForResponse(
    (res) => res.url().includes('/redo') && res.request().method() === 'POST'
  );
  await redoBtn.click();
  await redoRes1;
  await expect(redoBtn).toBeDisabled();
  await expect(undoBtn).toBeEnabled();

  // Box returns to shrunk size
  const redoneBox = await overlay0.boundingBox();
  expect(Math.abs(redoneBox!.width - shrunkBox!.width)).toBeLessThanOrEqual(2);

  // 6. Test Ctrl+Z keyboard shortcut
  const undoRes2 = page.waitForResponse(
    (res) => res.url().includes('/undo') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Control+z');
  await undoRes2;
  await expect(redoBtn).toBeEnabled();

  // 7. Test Ctrl+Y keyboard shortcut
  const redoRes2 = page.waitForResponse(
    (res) => res.url().includes('/redo') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Control+y');
  await redoRes2;
  await expect(undoBtn).toBeEnabled();

  // 8. Test Undo after Canva Crop
  await overlay0.click();
  await page.getByTestId('pdf-preview').getByRole('button', {name: 'ครอบตัด', exact: true}).click();
  const inlineCropBox = page.getByTestId('inline-crop-box');
  await expect(inlineCropBox).toBeVisible();

  // Resize crop handle and apply
  const seHandle = page.getByTestId('crop-handle-se');
  const seBox = await seHandle.boundingBox();
  expect(seBox).not.toBeNull();

  await page.mouse.move(seBox!.x + seBox!.width / 2, seBox!.y + seBox!.height / 2);
  await page.mouse.down();
  await page.mouse.move(seBox!.x - 20, seBox!.y - 20, {steps: 5});
  await page.mouse.up();

  const croppedUpload = page.waitForResponse(
    (res) => res.url().includes('/items/0/image') && res.request().method() === 'POST'
  );
  await page.getByRole('button', {name: 'เสร็จสิ้นการครอบตัด'}).click();
  const cropUploadRes = await croppedUpload;
  expect(cropUploadRes.status()).toBe(200);

  const item1Card = page.locator('article').filter({hasText: '1. CSHL550'});
  await expect(item1Card.getByRole('button', {name: 'คืนค่ารูป Catalog'})).toBeVisible();

  // Press Ctrl+Z to undo crop -> returns to previous uncropped state
  const undoCropRes = page.waitForResponse(
    (res) => res.url().includes('/undo') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Control+z');
  await undoCropRes;

  // Reverted: "คืนค่ารูป Catalog" button disappears
  await expect(item1Card.getByRole('button', {name: 'คืนค่ารูป Catalog'})).not.toBeVisible();
  await expect(redoBtn).toBeEnabled();

  // Press Ctrl+Y to redo crop -> custom cropped image is back
  const redoCropRes = page.waitForResponse(
    (res) => res.url().includes('/redo') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Control+y');
  await redoCropRes;

  await expect(item1Card.getByRole('button', {name: 'คืนค่ารูป Catalog'})).toBeVisible();
});
