import {test, expect} from '@playwright/test';
import path from 'path';

test('delete image feature: toolbar button, Delete key shortcut, sidebar button, and undo/redo restoration', async ({page}) => {
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

  // 2. Select item 0
  await overlay0.click();
  const deleteToolbarBtn = page.getByRole('button', {name: 'ลบรูปภาพ (Delete)'});
  await expect(deleteToolbarBtn).toBeVisible();
  await expect(deleteToolbarBtn).toBeEnabled();

  const undoBtn = page.getByRole('button', {name: 'ย้อนกลับ (Ctrl+Z)'});
  const redoBtn = page.getByRole('button', {name: 'ทำซ้ำ (Ctrl+Y)'});
  await expect(undoBtn).toBeDisabled();

  // 3. Click toolbar "ลบรูป" button
  const delRes1 = page.waitForResponse(
    (res) => res.url().includes('/items/0/image') && res.request().method() === 'DELETE'
  );
  await deleteToolbarBtn.click();
  await delRes1;

  // Image overlay is gone, undo is enabled
  await expect(overlay0).not.toBeVisible();
  await expect(undoBtn).toBeEnabled();

  // 4. Test Undo via Ctrl+Z
  const undoRes1 = page.waitForResponse(
    (res) => res.url().includes('/undo') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Control+z');
  await undoRes1;

  // Image overlay is restored!
  await expect(overlay0).toBeVisible();
  await expect(redoBtn).toBeEnabled();

  // 5. Test Delete key keyboard shortcut
  await overlay0.click();
  const delRes2 = page.waitForResponse(
    (res) => res.url().includes('/items/0/image') && res.request().method() === 'DELETE'
  );
  await page.keyboard.press('Delete');
  await delRes2;

  await expect(overlay0).not.toBeVisible();
  await expect(undoBtn).toBeEnabled();

  // Undo again
  const undoRes2 = page.waitForResponse(
    (res) => res.url().includes('/undo') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Control+z');
  await undoRes2;
  await expect(overlay0).toBeVisible();

  // 6. Test sidebar "ลบรูป" button
  const item1Card = page.locator('article').filter({hasText: '1. CSHL550'});
  const sidebarDeleteBtn = item1Card.getByRole('button', {name: 'ลบรูป'});
  await expect(sidebarDeleteBtn).toBeVisible();

  const delRes3 = page.waitForResponse(
    (res) => res.url().includes('/items/0/image') && res.request().method() === 'DELETE'
  );
  await sidebarDeleteBtn.click();
  await delRes3;

  await expect(overlay0).not.toBeVisible();

  // 7. Verify generation continues to work with deleted image
  const genRes = page.waitForResponse(
    (res) => res.url().includes('/generate') && res.request().method() === 'POST'
  );
  await page.getByRole('button', {name: /สร้าง PDF/}).click();
  const generated = await genRes;
  expect(generated.status()).toBe(200);
  await expect(page.getByText('PDF พร้อมดาวน์โหลด')).toBeVisible();
});

test('multi-select batch delete: checkboxes, Shift+Click, batch toolbar, and atomic undo/redo', async ({page}) => {
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
  const overlay1 = page.getByTestId('image-overlay-1');
  await expect(overlay0).toBeVisible();
  await expect(overlay1).toBeVisible();

  // 2. Select All with Images button test
  const selectAllBtn = page.getByRole('button', {name: 'เลือกทั้งหมดที่มีรูป'});
  await expect(selectAllBtn).toBeVisible();
  await selectAllBtn.click();

  // Should show batch toolbar with "เลือกอยู่ X รายการ"
  await expect(page.getByText(/เลือกอยู่ \d+ รายการ/).first()).toBeVisible();

  // Deselect all
  const deselectBtn = page.getByRole('button', {name: 'ยกเลิกเลือกทั้งหมด'});
  await expect(deselectBtn).toBeVisible();
  await deselectBtn.click();
  await expect(selectAllBtn).toBeVisible();

  // 3. Multi-select via sidebar checkboxes (select item 0 and item 1)
  const checkbox0 = page.getByTestId('checkbox-item-0');
  const checkbox1 = page.getByTestId('checkbox-item-1');
  await checkbox0.check();
  await checkbox1.check();

  // Check that both overlays exist and batch delete button is visible in PDF preview toolbar
  const batchDeleteToolbarBtn = page.getByRole('button', {name: 'ลบรูปที่เลือก (2)'});
  await expect(batchDeleteToolbarBtn).toBeVisible();

  // 4. Batch delete item 0 and item 1
  const batchDelRes = page.waitForResponse(
    (res) => res.url().includes('/batch-delete-images') && res.request().method() === 'POST'
  );
  await batchDeleteToolbarBtn.click();
  const delRes = await batchDelRes;
  expect(delRes.status()).toBe(200);

  // Both overlays are gone
  await expect(overlay0).not.toBeVisible();
  await expect(overlay1).not.toBeVisible();

  // 5. Atomic undo: 1 Ctrl+Z restores BOTH deleted images
  const undoRes = page.waitForResponse(
    (res) => res.url().includes('/undo') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Control+z');
  await undoRes;

  await expect(overlay0).toBeVisible();
  await expect(overlay1).toBeVisible();

  // 6. Test Shift+Click multi-selection on canvas overlays + Delete key shortcut
  await overlay0.click();
  await overlay1.click({ modifiers: ['Shift'] });

  // Verify batch delete button appears in toolbar
  await expect(page.getByRole('button', {name: 'ลบรูปที่เลือก (2)'})).toBeVisible();

  // Press Delete key
  const batchDelRes2 = page.waitForResponse(
    (res) => res.url().includes('/batch-delete-images') && res.request().method() === 'POST'
  );
  await page.keyboard.press('Delete');
  await batchDelRes2;

  await expect(overlay0).not.toBeVisible();
  await expect(overlay1).not.toBeVisible();

  // Undo again via toolbar button
  const undoBtn = page.getByRole('button', {name: 'ย้อนกลับ (Ctrl+Z)'});
  const undoRes2 = page.waitForResponse(
    (res) => res.url().includes('/undo') && res.request().method() === 'POST'
  );
  await undoBtn.click();
  await undoRes2;

  await expect(overlay0).toBeVisible();
  await expect(overlay1).toBeVisible();
});
