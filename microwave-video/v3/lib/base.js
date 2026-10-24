// v3 横屏基础库：1920×1080。只放各风格通用的东西：数学、随机、文字、字幕、颗粒。
const W = 1920, H = 1080;
const SERIF = '"NotoSerif"', SANS = '"NotoSans"', HAND = '"Hand"';
const cv = document.createElement('canvas'); cv.width = W; cv.height = H; document.body.appendChild(cv);
let ctx = cv.getContext('2d');   // 用 let：离屏绘制时可以临时换成别的画布

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, p) => a + (b - a) * p;
const ease = x => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const easeOut = x => 1 - Math.pow(1 - clamp(x), 3);
const P = (t, s, d) => ease((t - s) / d);
// 在 [a, b] 内显示，两端 f 秒淡入淡出
const vis = (t, a, b, f = 0.3) => Math.min(easeOut((t - a) / f), clamp((b - t) / f));
function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
function withAlpha(a, fn) { if (a <= 0.003) return; ctx.save(); ctx.globalAlpha *= a; fn(); ctx.restore(); }

// 文字：str 可以是字符串，或 [[文字, 颜色], ...] 分段着色
function text(str, x, y, { size = 48, color = '#F2E8DA', a = 1, weight = 700, font = SERIF, align = 'center', spacing = 2, glow = 0, glowColor = 'rgba(255,200,130,', blur = 0, shadow = 0 } = {}) {
  if (a <= 0.003) return 0;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.font = `${weight} ${size}px ${font}`; ctx.textBaseline = 'alphabetic'; ctx.letterSpacing = spacing + 'px';
  if (blur > 0.2) ctx.filter = `blur(${blur.toFixed(1)}px)`;
  if (glow) { ctx.shadowColor = glowColor + glow + ')'; ctx.shadowBlur = size * 0.5; }
  else if (shadow) { ctx.shadowColor = `rgba(0,0,0,${shadow})`; ctx.shadowBlur = size * 0.4; }
  const parts = Array.isArray(str) ? str : [[str, color]];
  const total = parts.reduce((s, [w]) => s + ctx.measureText(w).width, 0);
  let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
  ctx.textAlign = 'left';
  for (const [w, c] of parts) { ctx.fillStyle = c || color; ctx.fillText(w, cx, y); cx += ctx.measureText(w).width; }
  ctx.restore(); return total;
}
// 胶片颗粒（每帧换一张）
const GRAIN = (() => { const r = rng(7); return [...Array(5)].map(() => { const c = document.createElement('canvas'); c.width = 480; c.height = 270; const g = c.getContext('2d'); const im = g.createImageData(480, 270); for (let i = 0; i < im.data.length; i += 4) { const v = r() * 255; im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 255; } g.putImageData(im, 0, 0); return c; }); })();
function grain(t, a = 0.06) { ctx.save(); ctx.globalAlpha = a; ctx.globalCompositeOperation = 'overlay'; ctx.drawImage(GRAIN[Math.floor(t * 30) % GRAIN.length], 0, 0, W, H); ctx.restore(); }
function vignette(a = 0.75, r0 = 520, r1 = 1150) { const v = ctx.createRadialGradient(W / 2, H / 2, r0, W / 2, H / 2, r1); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, `rgba(0,0,0,${a})`); ctx.fillStyle = v; ctx.fillRect(0, 0, W, H); }
