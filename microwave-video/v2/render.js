// v2 渲染：Canvas + window.draw(t)，Playwright 逐帧截图，ffmpeg 编码。
//   node render.js scenes/opening.js out.mp4 <秒数>
//   node render.js scenes/opening.js frames/ --at 0,3,10
const path = require('path'), fs = require('fs'), { spawn } = require('child_process');
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const ROOT = __dirname, FONTS = path.resolve(ROOT, '..', 'fonts');
const [scene, out, a3, a4] = process.argv.slice(2);

(async () => {
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: NotoSerif; font-weight: 600; src: url('file://${FONTS}/NotoSerifSC-SemiBold.otf'); }
@font-face { font-family: NotoSerif; font-weight: 700; src: url('file://${FONTS}/NotoSerifSC-Bold.otf'); }
@font-face { font-family: NotoSerif; font-weight: 900; src: url('file://${FONTS}/NotoSerifSC-Black.otf'); }
html,body{margin:0;background:#000;width:1080px;height:1920px;overflow:hidden} canvas{display:block}
</style></head><body>
<script src="file://${path.join(ROOT, 'lib', 'style.js')}"></script>
<script src="file://${path.resolve(scene)}"></script></body></html>`;
  const tmp = path.join(ROOT, `_page_${process.pid}.html`); fs.writeFileSync(tmp, html);
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', e => { console.error('PAGE ERROR', e); process.exit(1); });
  await page.goto('file://' + tmp);
  await page.evaluate(async () => {
    for (const w of [600, 700, 900]) await document.fonts.load(`${w} 60px NotoSerif`, '微波炉辐射验牌');
    await document.fonts.ready;
  });
  console.log(await page.evaluate(() => [...document.fonts].map(f => f.family + f.weight + ':' + f.status).join(' ')));
  if (a3 === '--at') {
    fs.mkdirSync(out, { recursive: true });
    for (const t of a4.split(',').map(Number)) {
      await page.evaluate(t => window.draw(t), t);
      await page.screenshot({ path: path.join(out, `t${t.toFixed(2)}.png`) });
    }
  } else {
    const n = Math.round(parseFloat(a3) * 30);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let i = 0; i < n; i++) {
      await page.evaluate(t => window.draw(t), i / 30);
      const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
    console.log('wrote', out, n);
  }
  await browser.close(); fs.unlinkSync(tmp);
})();
