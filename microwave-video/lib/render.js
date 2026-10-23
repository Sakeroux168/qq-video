// 用法：
//   node render.js shots/s01.js out/s01.mp4             渲染整段
//   node render.js shots/s01.js frames/s01 --at 0,3.5,7  只截关键帧 PNG
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { chromium } = require('/opt/node22/lib/node_modules/playwright');

const ROOT = path.resolve(__dirname, '..');
const [shotArg, outArg, flag, atArg] = process.argv.slice(2);
const shot = path.resolve(shotArg);

function pageHtml() {
  const f = n => 'file://' + path.join(ROOT, 'fonts', n);
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: NotoBlack; src: url('${f('NotoSansSC-Black.otf')}'); }
@font-face { font-family: NotoBold; src: url('${f('NotoSansSC-Bold.otf')}'); }
html,body { margin:0; padding:0; width:1080px; height:1920px; overflow:hidden; background:#0F141A; }
svg { display:block; }
</style></head><body>
<script>window.ROOT = ${JSON.stringify(ROOT)}; window.XMETA = ${fs.readFileSync(path.join(ROOT, 'xingxing', 'assets', 'meta.json'), 'utf8')};</script>
<script src="file://${path.join(ROOT, 'lib', 'core.js')}"></script>
<script src="file://${path.join(ROOT, "lib", "characters.js")}"></script>
<script src="file://${shot}"></script>
</body></html>`;
}

(async () => {
  const tmp = path.join(ROOT, 'frames', '_page_' + path.basename(shot, '.js') + '_' + process.pid + '.html');
  fs.writeFileSync(tmp, pageHtml());
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => { console.error('PAGE ERROR', e); process.exit(1); });
  await page.goto('file://' + tmp);
  await page.evaluate(async () => {
    await document.fonts.load('120px NotoBlack', '测');
    await document.fonts.load('76px NotoBold', '测');
    await document.fonts.ready;
    await Promise.all(window.ASSETS || []);
  });
  const fonts = await page.evaluate(() => [...document.fonts].map(f => f.family + ':' + f.status).join(' '));
  console.log('fonts:', fonts);
  const dur = await page.evaluate(() => window.SHOT.duration);

  if (flag === '--at') {
    fs.mkdirSync(outArg, { recursive: true });
    for (const t of atArg.split(',').map(Number)) {
      await page.evaluate(t => window.SHOT.render(t), t);
      const f = path.join(outArg, `t${t.toFixed(2)}.png`);
      await page.screenshot({ path: f });
      console.log(f);
    }
  } else {
    const n = Math.round(dur * 30);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', '30', '-an', '-movflags', '+faststart', outArg],
      { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let i = 0; i < n; i++) {
      await page.evaluate(t => window.SHOT.render(t), i / 30);
      const buf = await page.screenshot({ type: 'png' });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 60 === 0) console.log(`frame ${i}/${n}`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('wrote', outArg, n, 'frames');
  }
  await browser.close();
})();
