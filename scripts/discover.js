// Opens nosbazar.com in a headless browser and records every network request,
// so we can find the JSON endpoints that carry bazaar prices.
const { chromium } = require('playwright');
const fs = require('fs');

const OUT = 'discovery';
fs.mkdirSync(`${OUT}/bodies`, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ locale: 'it-IT', viewport: { width: 1366, height: 900 } });
  const log = [];
  let n = 0;

  page.on('response', async (res) => {
    const req = res.request();
    const type = res.headers()['content-type'] || '';
    const entry = { url: res.url(), method: req.method(), status: res.status(), type, resourceType: req.resourceType(), postData: req.postData() || null };
    if (/json|text\/plain|grpc|protobuf|octet/.test(type) || ['xhr', 'fetch', 'websocket'].includes(req.resourceType())) {
      try {
        const body = await res.body();
        const file = `${OUT}/bodies/${String(++n).padStart(3, '0')}.txt`;
        fs.writeFileSync(file, body.slice(0, 200000));
        entry.bodyFile = file;
        entry.bodyBytes = body.length;
      } catch (e) { entry.bodyError = String(e); }
    }
    log.push(entry);
  });
  page.on('websocket', (ws) => {
    const frames = [];
    log.push({ websocket: ws.url(), frames });
    ws.on('framereceived', (f) => frames.length < 50 && frames.push(String(f.payload).slice(0, 2000)));
    ws.on('framesent', (f) => frames.length < 50 && frames.push('SENT ' + String(f.payload).slice(0, 2000)));
  });

  const step = async (name) => {
    await page.waitForTimeout(6000);
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
    fs.writeFileSync(`${OUT}/${name}.txt`, await page.evaluate(() => document.body.innerText).catch(() => ''));
  };

  await page.goto('https://nosbazar.com/', { waitUntil: 'networkidle', timeout: 90000 }).catch((e) => log.push({ gotoError: String(e) }));
  await step('01-home');

  const links = await page.$$eval('a[href]', (as) => as.map((a) => ({ text: a.innerText.trim().slice(0, 80), href: a.href }))).catch(() => []);
  fs.writeFileSync(`${OUT}/links.json`, JSON.stringify(links, null, 2));

  // Try a search for one item the user tracks.
  const input = await page.$('input[type=search], input[type=text], input:not([type])');
  if (input) {
    await input.fill('Gillion');
    await input.press('Enter').catch(() => {});
    await step('02-search');
    const first = await page.$('text=/gillion/i');
    if (first) { await first.click().catch(() => {}); await step('03-item'); }
  }

  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } })).catch(() => ({}));
  fs.writeFileSync(`${OUT}/storage.json`, JSON.stringify(storage, null, 2).slice(0, 200000));
  fs.writeFileSync(`${OUT}/network.json`, JSON.stringify(log, null, 2));
  await browser.close();
})();
