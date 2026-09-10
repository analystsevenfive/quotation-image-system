import {test, expect} from '@playwright/test';
import path from 'path';

test('spacebar pan and hand tool: toggle button, spacebar keydown indicator, and drag to scroll viewport', async ({page}) => {
  page.on('console', msg => console.log('BROWSER:', msg.text()));
  await page.goto('/');

  // 1. Upload sample PDF
  const fixture = path.resolve('../../QT_test.pdf');
  const uploaded = page.waitForResponse(
    (r) => r.url().endsWith('/api/quotations') && r.request().method() === 'POST'
  );
  await page.locator('input[accept="application/pdf,.pdf"]').setInputFiles(fixture);
  await uploaded;

  await expect(page.getByTestId('pdf-preview')).toHaveAttribute('data-rendered', 'true');
  const viewport = page.getByTestId('pdf-viewport');
  await expect(viewport).toBeVisible();

  // 2. Zoom in to 150% so viewport has scrollable overflow
  const zoomInBtn = page.getByRole('button', {name: 'ซูมเข้า'});
  await zoomInBtn.click(); // 125%
  await zoomInBtn.click(); // 150%

  // 3. Test Hand Tool toggle button in the header
  const handToolBtn = page.getByRole('button', {name: 'เครื่องมือเลื่อนมุมมอง (Spacebar)'});
  await expect(handToolBtn).toBeVisible();

  const panIndicator = page.getByTestId('pan-mode-indicator');
  await expect(panIndicator).not.toBeVisible();

  // Click Hand tool button to activate
  await handToolBtn.click();
  await expect(panIndicator).toBeVisible();
  await expect(panIndicator).toContainText('กด Spacebar ค้างแล้วลากเพื่อเลื่อนดูเอกสาร');

  // Click again to deactivate
  await handToolBtn.click();
  await expect(panIndicator).not.toBeVisible();

  // 4. Test Holding Spacebar to Pan
  await viewport.scrollIntoViewIfNeeded();
  const overlay = page.getByTestId('image-overlay-0');
  const initialOverlayBox = (await overlay.boundingBox())!;

  await page.keyboard.down('Space');
  await expect(panIndicator).toBeVisible();

  // Drag mouse over overlay while holding Space (tests that it pans rather than moving the image)
  const startX = initialOverlayBox.x + initialOverlayBox.width / 2;
  const startY = initialOverlayBox.y + initialOverlayBox.height / 2;

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX - 120, startY - 100, {steps: 10});
  await page.mouse.up();

  // Check that viewport scrolled
  const scrolled = await viewport.evaluate((el) => ({left: el.scrollLeft, top: el.scrollTop}));
  expect(scrolled.left).toBeGreaterThan(0);
  expect(scrolled.top).toBeGreaterThan(0);

  // Release Spacebar
  await page.keyboard.up('Space');
  await expect(panIndicator).not.toBeVisible();
});
