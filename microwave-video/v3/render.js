// v3 横屏渲染：1920×1080，Canvas + window.draw(t)，Playwright 逐帧截图，ffmpeg 编码。
//   node render.js scenes/x.js out.mp4 <秒数>        （可用环境变量 T0/T1 分段渲染）
//   node render.js scenes/x.js frames/ --at 0,3,10
const path = require('path'), fs = require('fs'), { spawn } = require('child_process');
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const ROOT = __dirname, FONTS = path.resolve(ROOT, '..', 'fonts');
const [scene, out, a3, a4] = process.argv.slice(2);

(async () => {
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: NotoSerif; font-weight: 600; src: url('file://${FONTS}/NotoSerifSC-SemiBold.otf'); }
@font-face { font-family: NotoSerif; font-weight: 700; src: url('file://${FONTS}/NotoSerifSC-Bold.otf'); }
@font-face { font-family: NotoSerif; font-weight: 900; src: url('file://${FONTS}/NotoSerifSC-Black.otf'); }
@font-face { font-family: NotoSans; font-weight: 500; src: url('file://${FONTS}/NotoSansSC-Medium.otf'); }
@font-face { font-family: NotoSans; font-weight: 700; src: url('file://${FONTS}/NotoSansSC-Bold.otf'); }
@font-face { font-family: Hand; src: url('file://${FONTS}/LongCang-Regular.ttf'); }
html,body{margin:0;background:#000;width:1920px;height:1080px;overflow:hidden} canvas{display:block}
</style></head><body>
${['base.js', ...fs.readdirSync(path.join(ROOT, 'lib')).filter(f => f.endsWith('.js') && f !== 'base.js').sort()].map(f => `<script src="file://${path.join(ROOT, 'lib', f)}"></script>`).join('\n')}
<script src="file://${path.resolve(scene)}"></script></body></html>`;
  const tmp = path.join(ROOT, `_page_${process.pid}.html`); fs.writeFileSync(tmp, html);
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', e => { console.error('PAGE ERROR', e); process.exit(1); });
  await page.goto('file://' + tmp);
  await page.evaluate(async () => {
    for (const w of [600, 700, 900]) await document.fonts.load(`${w} 60px NotoSerif`, '账本钱人情功劳伤害');
    for (const w of [500, 700]) await document.fonts.load(`${w} 60px NotoSans`, '转账微信');
    await document.fonts.load('60px Hand', '室友小王老张同事帮他搬家替顶班那句话表姐小李两顿饭钱我改');
    await document.fonts.ready;
  });
  if (a3 === '--at') {
    fs.mkdirSync(out, { recursive: true });
    for (const t of a4.split(',').map(Number)) {
      await page.evaluate(t => window.draw(t), t);
      await page.screenshot({ path: path.join(out, `t${t.toFixed(2)}.png`) });
    }
  } else {
    const n = Math.round(parseFloat(a3) * 30);
    const f0 = Math.round(parseFloat(process.env.T0 || '0') * 30), f1 = process.env.T1 ? Math.round(parseFloat(process.env.T1) * 30) : n;
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let i = f0; i < f1; i++) {
      await page.evaluate(t => window.draw(t), i / 30);
      const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
    console.log('wrote', out, f1 - f0);
  }
  await browser.close(); fs.unlinkSync(tmp);
})();
