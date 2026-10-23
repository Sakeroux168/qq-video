// v2 全局风格：照对标爆款（暗金电影感 + 发光细线）拆出来的参数。
// 背景近黑暖色、中心暖光、暗角、胶片颗粒、少量漂浮尘埃；主体是一根会发光的米金色细线；
// 字幕衬线体（思源宋体）米白色，置顶；负面/危险词用暗红；数据引用用极小灰字放底部。
const W = 1080, H = 1920;
const COL = {
  bg: '#0B0806', warm: 'rgba(58,44,30,', line: '#FCEBD4', glow: 'rgba(255,196,130,',
  text: '#F4EADC', dim: '#8A8077', red: '#D85046', redGlow: 'rgba(216,80,70,', gold: '#E8C48A',
};
const SERIF = '"NotoSerif"';

const cv = document.createElement('canvas');
cv.width = W; cv.height = H;
document.body.appendChild(cv);
const ctx = cv.getContext('2d');

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const ease = x => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const easeOut = x => 1 - Math.pow(1 - clamp(x), 3);
const P = (t, s, d) => ease((t - s) / d);
const lerp = (a, b, p) => a + (b - a) * p;
// 带种子的随机数（画面完全由 t 决定）
function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

// ---------- 背景：暖色中心光 + 暗角 + 颗粒 + 尘埃
const grainTiles = [];
(() => {
  const r = rng(7);
  for (let k = 0; k < 6; k++) {
    const c = document.createElement('canvas'); c.width = 270; c.height = 480;
    const g = c.getContext('2d'); const img = g.createImageData(270, 480);
    for (let i = 0; i < img.data.length; i += 4) { const v = r() * 255; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
    g.putImageData(img, 0, 0); grainTiles.push(c);
  }
})();
const dust = (() => { const r = rng(11); return [...Array(36)].map(() => ({ x: r() * W, y: r() * H, s: 0.6 + r() * 1.8, v: 6 + r() * 14, ph: r() * 6.28, a: 0.15 + r() * 0.35 })); })();

function background(t, { cx = 540, cy = 900, glow = 1 } = {}) {
  ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = COL.bg; ctx.fillRect(0, 0, W, H);
  let g = ctx.createRadialGradient(cx, cy, 0, cx, cy, 900);
  g.addColorStop(0, COL.warm + (0.55 * glow) + ')'); g.addColorStop(0.55, COL.warm + (0.16 * glow) + ')'); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}
function finish(t) {
  // 尘埃
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const d of dust) {
    const y = ((d.y - t * d.v) % H + H) % H, x = d.x + 14 * Math.sin(t * 0.4 + d.ph);
    ctx.fillStyle = `rgba(255,214,160,${(d.a * (0.6 + 0.4 * Math.sin(t * 1.3 + d.ph))).toFixed(3)})`;
    ctx.beginPath(); ctx.arc(x, y, d.s, 0, 6.283); ctx.fill();
  }
  ctx.restore();
  // 暗角
  const v = ctx.createRadialGradient(540, 960, 380, 540, 960, 1250);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.78)');
  ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  // 胶片颗粒（每帧换一张）
  ctx.save(); ctx.globalAlpha = 0.07; ctx.globalCompositeOperation = 'overlay';
  ctx.drawImage(grainTiles[Math.floor(t * 30) % grainTiles.length], 0, 0, W, H);
  ctx.restore();
}

// ---------- 发光线条
function glowStroke(drawPath, { w = 3, a = 1, color = COL.line, glow = COL.glow, blur = 22 } = {}) {
  ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.globalAlpha = a;
  ctx.shadowColor = glow + '0.9)'; ctx.shadowBlur = blur;
  ctx.strokeStyle = color; ctx.lineWidth = w;
  ctx.beginPath(); drawPath(); ctx.stroke();
  ctx.shadowBlur = blur * 0.4; ctx.stroke();
  ctx.restore();
}
// 按比例截取折线（p: 0..1），用于"画出来"的动画
function polyPartial(pts, p) {
  const seg = []; let L = 0;
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); L += d; }
  let rem = L * clamp(p); ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) {
    if (rem >= seg[i - 1]) { ctx.lineTo(pts[i][0], pts[i][1]); rem -= seg[i - 1]; }
    else { const k = rem / seg[i - 1]; ctx.lineTo(lerp(pts[i - 1][0], pts[i][0], k), lerp(pts[i - 1][1], pts[i][1], k)); break; }
  }
}
function node(x, y, r = 7, a = 1, color = COL.line) {
  ctx.save(); ctx.globalAlpha = a; ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createRadialGradient(x, y, 0, x, y, r * 6);
  g.addColorStop(0, COL.glow + '0.55)'); g.addColorStop(1, COL.glow + '0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 6, 0, 6.283); ctx.fill();
  ctx.restore();
  ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = color; ctx.shadowColor = COL.glow + '1)'; ctx.shadowBlur = 16;
  ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill(); ctx.restore();
}

// ---------- 文字：衬线、模糊淡入
function serifText(str, x, y, { size = 58, color = COL.text, a = 1, blur = 0, weight = 600, align = 'center', glow = 0, glowColor = COL.glow, spacing = 2 } = {}) {
  if (a <= 0.001) return;
  ctx.save();
  ctx.font = `${weight} ${size}px ${SERIF}`; ctx.textAlign = align; ctx.textBaseline = 'alphabetic';
  ctx.letterSpacing = spacing + 'px';
  ctx.globalAlpha = a; if (blur > 0.2) ctx.filter = `blur(${blur.toFixed(1)}px)`;
  if (glow) { ctx.shadowColor = glowColor + glow + ')'; ctx.shadowBlur = size * 0.45; }
  if (Array.isArray(str)) {
    // [[文字, 颜色], ...] 逐段绘制，整体按 align 对齐
    const total = str.reduce((s, [w]) => s + ctx.measureText(w).width, 0);
    let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
    ctx.textAlign = 'left';
    for (const [w, c] of str) { ctx.fillStyle = c || color; ctx.fillText(w, cx, y); cx += ctx.measureText(w).width; }
  } else { ctx.fillStyle = color; ctx.fillText(str, x, y); }
  ctx.restore();
}
// 置顶字幕：模糊 → 清晰淡入（0.35s），结束时淡出（0.25s）
function caption(t, s, e, str, y = 360, size = 62) {
  const pin = clamp((t - s) / 0.35), pout = clamp((e - t) / 0.25);
  const a = Math.min(easeOut(pin), pout);
  serifText(str, 540, y, { size, a, blur: (1 - easeOut(pin)) * 10 });
}
