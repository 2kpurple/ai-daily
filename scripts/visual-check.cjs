#!/usr/bin/env node
// Local browser QA; run with the docs HTTP server already listening on port 8000.
const { chromium } = require('playwright-core');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const preview = path.join(root, 'preview');
const base = 'http://127.0.0.1:8000';
const issues = fs.readdirSync(path.join(root, 'content')).filter(n => /^\d{4}-\d{2}-\d{2}\.json$/.test(n)).sort();
const routes = ['/', '/archive/', ...issues.map(n => '/' + n.slice(0, -5) + '/')];

async function ready(page, route) {
  const response = await page.goto(base + route, { waitUntil: 'networkidle' });
  assert.equal(response.status(), 200);
  await page.evaluate(async () => {
    document.querySelectorAll('img').forEach(img => { img.loading = 'eager'; });
    await Promise.all([...document.images].map(img => img.decode()));
    await document.fonts.ready;
  });
}

async function measure(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const main = document.querySelector('main').getBoundingClientRect();
    const buttonFailures = [];
    for (const button of document.querySelectorAll('.read-original')) {
      button.scrollIntoView({ block: 'center' });
      const r = button.getBoundingClientRect();
      const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      if (!button.contains(hit) || r.height < 44 || !/^https?:/.test(button.href)) buttonFailures.push(button.href);
    }
    const imageFailures = [...document.images].filter(img => {
      const css = getComputedStyle(img);
      return !img.complete || !img.naturalWidth || css.objectFit !== 'contain' ||
        parseFloat(css.borderRadius) < 8 || img.getBoundingClientRect().height > (innerWidth <= 480 ? 300 : 360) + 1;
    }).map(img => img.getAttribute('src'));
    const result = {
      scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth, height: doc.scrollHeight,
      mainWidth: main.width, centered: Math.abs(main.x - (innerWidth - main.right)) < 1,
      images: document.images.length, imageFailures, primaryButtons: document.querySelectorAll('.read-original').length,
      buttonFailures, background: getComputedStyle(document.body).backgroundColor,
      colorSchemeDark: matchMedia('(prefers-color-scheme: dark)').matches,
    };
    window.scrollTo(0, 0);
    return result;
  });
}

async function screenshot(page, name, fullPage = false) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(preview, name + '.png'), fullPage });
}

(async () => {
  fs.mkdirSync(preview, { recursive: true });
  for (const name of fs.readdirSync(preview)) {
    if (/\.(png|jpe?g|webp)$/i.test(name)) fs.unlinkSync(path.join(preview, name));
  }
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const results = { browser: browser.version(), base, deviceScaleFactor: 1, measurements: [], interactions: [], resourceErrors: [], pageErrors: [] };
  try {
    for (const width of [390, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 900 }, deviceScaleFactor: 1 });
      const page = await context.newPage();
      page.on('pageerror', error => results.pageErrors.push(error.message));
      page.on('response', response => { if (response.status() >= 400) results.resourceErrors.push({ url: response.url(), status: response.status() }); });
      page.on('requestfailed', request => results.resourceErrors.push({ url: request.url(), error: request.failure()?.errorText }));
      const cdp = await context.newCDPSession(page);
      for (const mode of ['light', 'dark']) {
        await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: mode }] });
        for (const route of routes) {
          await ready(page, route);
          const closed = await measure(page);
          await page.locator('details').evaluateAll(nodes => nodes.forEach(node => { node.open = true; }));
          const expanded = await measure(page);
          await page.locator('details').evaluateAll(nodes => nodes.forEach(node => { node.open = false; }));
          const result = { route, width, mode, ...closed, expandedScrollWidth: expanded.scrollWidth,
            expandedClientWidth: expanded.clientWidth, expandedImageFailures: expanded.imageFailures };
          results.measurements.push(result);
          console.log(`${width} ${mode} ${route} ${closed.scrollWidth} <= ${closed.clientWidth}; expanded ${expanded.scrollWidth} <= ${expanded.clientWidth}`);
          assert(closed.scrollWidth <= closed.clientWidth && expanded.scrollWidth <= expanded.clientWidth);
          assert(closed.centered && closed.mainWidth <= 720);
          assert.equal(closed.colorSchemeDark, mode === 'dark');
          assert.deepEqual(closed.imageFailures, []);
          assert.deepEqual(expanded.imageFailures, []);
          assert.deepEqual(closed.buttonFailures, []);
          if (route === '/' && mode === 'light') {
            const label = width === 390 ? 'home-mobile-390' : 'home-desktop';
            await screenshot(page, label + '-firstscreen');
            await screenshot(page, label + '-full', true);
            await page.locator('.entry-card').first().screenshot({ path: path.join(preview, label + '-card.png'), style: '.topbar { visibility: hidden; }' });
          }
          if (route === '/' && width === 390 && mode === 'dark') {
            await screenshot(page, 'home-mobile-390-dark-firstscreen');
            await page.locator('.entry-card').first().screenshot({ path: path.join(preview, 'home-mobile-390-dark-card.png'), style: '.topbar { visibility: hidden; }' });
          }
          if (width === 390 && mode === 'light' && ['/archive/', '/2026-10-22/'].includes(route)) {
            await screenshot(page, route === '/archive/' ? 'archive-mobile-390-full' : 'issue-2026-10-22-mobile-390-full', true);
          }
        }
      }
      // Exercise actual local navigation and the expandable verification section.
      await ready(page, '/');
      await page.getByRole('link', { name: '往期', exact: true }).click();
      await page.waitForURL(base + '/archive/');
      await page.locator('.archive .t').first().click();
      await page.waitForURL(base + '/' + issues.at(-1).slice(0, -5) + '/');
      await page.locator('.toc a[href="#tools"]').click();
      assert.equal(new URL(page.url()).hash, '#tools');
      await page.locator('.unverified summary').click();
      assert(await page.locator('.unverified details').evaluate(node => node.open));
      results.interactions.push({ width, archiveNavigation: true, issueNavigation: true, tocAnchor: true, detailsToggle: true });
      await context.close();
    }
    assert.deepEqual(results.pageErrors, []);
    assert.deepEqual(results.resourceErrors, []);
    fs.writeFileSync(path.join(preview, 'browser-results.json'), JSON.stringify(results, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
