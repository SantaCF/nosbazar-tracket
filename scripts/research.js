// Renders nosapki pages in a real browser and saves text, HTML and every JSON/JS response,
// so upgrade rates/costs that are loaded client-side can be read.
const { chromium } = require('playwright');
const fs = require('fs');
const OUT = 'research';
const PAGES = [
  'https://nosapki.com/en/simulators/specialists_upgrade',
  'https://nosapki.com/en/simulators/equipment_upgrade',
  'https://nosapki.com/en/simulators/specialists_perfection',
  'https://nosapki.com/en/items/4772',
  'https://nosapki.com/en/items/9872',
];
fs.mkdirSync(`${OUT}/bodies`, { recursive: true });
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
  const log = []; let n = 0;
  page.on('response', async (res) => {
    const type = res.headers()['content-type'] || '';
    const e = { url: res.url(), status: res.status(), type };
    if (/json|javascript/.test(type) && res.url().includes('nosapki')) {
      try {
        const b = await res.body();
        const f = `${OUT}/bodies/${String(++n).padStart(3, '0')}${/json/.test(type) ? '.json' : '.js'}`;
        fs.writeFileSync(f, b); e.file = f; e.bytes = b.length;
      } catch (err) { e.err = String(err); }
    }
    log.push(e);
  });
  for (const [i, url] of PAGES.entries()) {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 }).catch((err) => log.push({ gotoError: url, err: String(err) }));
    await page.waitForTimeout(4000);
    const name = `${OUT}/${i + 1}-${url.split('/').slice(-1)[0]}`;
    fs.writeFileSync(`${name}.txt`, await page.evaluate(() => document.body.innerText).catch(() => ''));
    fs.writeFileSync(`${name}.html`, await page.content().catch(() => ''));
    // Simulators: pick the second option of every select to trigger rate loading.
    const sels = await page.$$('select');
    for (const [k, s] of sels.entries()) {
      const opts = await s.$$eval('option', (o) => o.map((x) => x.value + ' | ' + x.textContent.trim())).catch(() => []);
      fs.writeFileSync(`${name}-select${k}.json`, JSON.stringify(opts, null, 1));
      const vals = await s.$$eval('option', (o) => o.map((x) => x.value)).catch(() => []);
      if (vals[1]) { await s.selectOption(vals[1]).catch(() => {}); await page.waitForTimeout(1500); }
    }
    if (sels.length) fs.writeFileSync(`${name}-after.txt`, await page.evaluate(() => document.body.innerText).catch(() => ''));
  }
  fs.writeFileSync(`${OUT}/network.json`, JSON.stringify(log, null, 1));
  await browser.close();
})();
