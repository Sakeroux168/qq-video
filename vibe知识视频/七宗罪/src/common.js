// 四个风格样图共用：种子随机数、字体加载、颗粒、暗角
window.W = 1920; window.H = 1080;

window.rng = function (seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

window.TEXT_ALL = '七宗罪嫉妒其二两个世界你选哪个别人万差不多一半的人了ABJEALOUSY0123456789.，。？：·｜受不了我酸柠檬精同事工资条明明更多却难受第二集看对面窗户灯火通明一边是另一边vibe知识大赏Vibe';

window.loadFonts = async function (specs) {
  await Promise.all(specs.map((s) => document.fonts.load(s, TEXT_ALL)));
  await document.fonts.ready;
};

window.setup = function () {
  const c = document.getElementById('c');
  c.width = W; c.height = H;
  return c.getContext('2d');
};

window.grain = function (ctx, amount, seed) {
  const img = ctx.getImageData(0, 0, W, H);
  const d = img.data, r = rng(seed || 7);
  for (let i = 0; i < d.length; i += 4) {
    const n = (r() - 0.5) * amount;
    d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  ctx.putImageData(img, 0, 0);
};

window.vignette = function (ctx, strength, color) {
  const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 1.05);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, color || `rgba(0,0,0,${strength})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
};

// 一行里不同颜色的几段字，整体居中
window.richLine = function (ctx, parts, cx, y, font) {
  ctx.font = font;
  const widths = parts.map((p) => ctx.measureText(p[0]).width);
  let x = cx - widths.reduce((a, b) => a + b, 0) / 2;
  ctx.textAlign = 'left';
  parts.forEach((p, i) => { ctx.fillStyle = p[1]; ctx.fillText(p[0], x, y); x += widths[i]; });
};
