// 用法: node render.js <页面名> <秒数> [--stills t1,t2,...]
// 逐帧调 window.draw(t)，canvas 直接导出 jpg 到 frames/
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [name, secs, flag, list] = process.argv.slice(2);
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', (e) => console.error('页面报错', e.message));
  await page.goto('file://' + path.resolve(__dirname, name + '.html'));
  await page.waitForFunction('window.done === true', null, { timeout: 60000 });
  const grab = async (t, file) => {
    const url = await page.evaluate((t) => { draw(t); return document.getElementById('c').toDataURL('image/jpeg', 0.92); }, t);
    fs.writeFileSync(file, Buffer.from(url.split(',')[1], 'base64'));
  };
  if (flag === '--stills') {
    fs.mkdirSync(path.resolve(__dirname, 'stills'), { recursive: true });
    for (const t of list.split(',').map(Number)) await grab(t, path.resolve(__dirname, 'stills', `${t.toFixed(2)}.jpg`));
  } else {
    const dir = path.resolve(__dirname, 'frames'); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir);
    const n = Math.round(Number(secs) * 30);
    for (let f = 0; f < n; f++) await grab(f / 30, path.join(dir, String(f).padStart(5, '0') + '.jpg'));
    console.log('frames', n);
  }
  await browser.close();
})();
