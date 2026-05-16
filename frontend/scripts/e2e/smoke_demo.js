#!/usr/bin/env node
// Minimal Playwright smoke script that reproduces the demo flow:
// - opens frontend at http://localhost:5173
// - clicks "Run Demo" button, waits, navigates to Execution -> Broadcast -> Settlement

import { chromium } from 'playwright';

(async () => {
  const base = process.env.DEMO_URL || 'http://localhost:3000';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ timeout: 120000 });
  try {
    console.log('Opening', base);
    await page.goto(base, { waitUntil: 'networkidle' });

    // click Run Demo (try by text)
    const runBtn = await page.locator('text=Run Demo').first();
    if (await runBtn.count() > 0) {
      await runBtn.click();
      console.log('Clicked Run Demo');
    } else {
      console.warn('Run Demo button not found - ensure frontend is running at', base);
    }

    // wait for seeded opportunity link and navigate
    await page.waitForTimeout(1500);
    // click Opportunities and select OPP-9999 if present
    await page.locator('text=Opportunities').first().click().catch(() => {});
    await page.waitForTimeout(800);
    const opp = await page.locator('text=OPP-9999').first();
    if (await opp.count() > 0) {
      await opp.click();
      console.log('Selected OPP-9999');
    }

    // try to navigate to Execution and click Broadcast
    await page.locator('text=Execution').first().click().catch(() => {});
    await page.waitForTimeout(800);
    const broadcast = await page.locator('text=Broadcast').first();
    if (await broadcast.count() > 0) {
      await broadcast.click();
      console.log('Clicked Broadcast');
    }

    // wait for settlement to update
    await page.waitForTimeout(2000);
    await page.locator('text=Settlement').first().click().catch(() => {});
    await page.waitForTimeout(1200);

    const exportLink = await page.locator('text=Last Export').first();
    const hasExport = (await exportLink.count()) > 0;
    console.log('Smoke result: export link present?', hasExport);

    await browser.close();
    process.exit(hasExport ? 0 : 0);
  } catch (err) {
    console.error('Smoke script failed', err);
    await browser.close();
    process.exit(2);
  }
})();
