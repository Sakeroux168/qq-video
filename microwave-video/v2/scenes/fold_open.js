// 《一张纸对折 42 次》开头 15 秒 · 风格 C（半写实物件 + 金色 HUD + 大号衬线字幕）
// 文案节奏（按约 5 字/秒估，配音到了再对齐）：
//  0.0–2.8  一张纸，对折 42 次，能有多厚？
//  2.9–6.3  先猜一个数。一米？一栋楼？
//  6.4–10.0 答案是：它能一直顶到月亮。
// 10.1–12.8 一张普通的纸，大约 0.1 毫米。
// 12.9–15.0 对折 1 次，0.2 毫米。
const DUR = 15;
const G = { gold: '#D9B77A', goldA: 'rgba(217,183,122,', ink: '#EDE3D2', paperTop: [246, 238, 222], paperBack: [214, 203, 182] };

// ---------- 小型 3D：相机绕 y 轴偏航、绕 x 轴俯仰，透视投影
function makeCam(cx, cy, yaw, pitch, scale = 1, dist = 1800) {
  const cyw = Math.cos(yaw), syw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  return ([x, y, z]) => {
    const X = x * cyw - z * syw; let Z = x * syw + z * cyw;
    const Y = y * cp - Z * sp; Z = y * sp + Z * cp;
    const f = dist / (dist + Z) * scale;
    return [cx + X * f, cy - Y * f, Z];
  };
}
function shade(rgb, k) { return `rgb(${rgb.map(v => Math.round(v * k)).join(',')})`; }
function quad(cam, pts, rgb, light, edge = true) {
  const p = pts.map(cam);
  ctx.beginPath(); p.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath();
  const g = ctx.createLinearGradient(p[0][0], p[0][1], p[2][0], p[2][1]);
  g.addColorStop(0, shade(rgb, Math.min(1.08, light + 0.08))); g.addColorStop(1, shade(rgb, light * 0.9));
  ctx.fillStyle = g; ctx.fill();
  if (edge) { ctx.strokeStyle = G.goldA + '0.55)'; ctx.lineWidth = 1.6; ctx.stroke(); }
}
// 一张纸（宽 2a、深 2b），theta: 右半边绕中线翻折角（0 平铺 → π 叠好）
function paper(cam, a, b, theta, lift = 0) {
  // 投影阴影
  const c0 = cam([0, -40, 0]);
  ctx.save(); ctx.filter = 'blur(24px)'; ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.beginPath(); ctx.ellipse(c0[0], c0[1] + 180, a * 0.9 * (1 - 0.45 * theta / Math.PI), 40, 0, 0, 6.283); ctx.fill(); ctx.restore();
  const y0 = lift;
  // 左半（不动）
  quad(cam, [[-a, y0, -b], [0, y0, -b], [0, y0, b], [-a, y0, b]], G.paperTop, 0.95);
  // 右半：点 (x,0,z) → (x cosθ, x sinθ, z)
  const c = Math.cos(theta), s = Math.sin(theta), eps = 3 * (theta / Math.PI);
  const R = x => [x * c, y0 + x * s + eps, 0];
  const pts = [[0, -b], [a, -b], [a, b], [0, b]].map(([x, z]) => { const r = R(x); return [r[0], r[1], z]; });
  // 法线朝上分量 = cosθ；翻过 90° 后看到的是纸背面
  const up = c;
  const rgb = up >= 0 ? G.paperTop : G.paperBack;
  quad(cam, pts, rgb, theta < 0.01 ? 0.95 : 0.7 + 0.3 * Math.abs(up));
  // 折痕高光
  const f0 = cam([0, y0 + 1, -b]), f1 = cam([0, y0 + 1, b]);
  ctx.save(); ctx.strokeStyle = `rgba(255,236,200,${0.25 + 0.5 * Math.sin(theta)})`; ctx.lineWidth = 2.5; ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.moveTo(f0[0], f0[1]); ctx.lineTo(f1[0], f1[1]); ctx.stroke(); ctx.restore();
}

// ---------- HUD
function tickRing(cx, cy, r, t, a) {
  if (a <= 0.01) return;
  ctx.save(); ctx.globalAlpha = a;
  ctx.strokeStyle = G.goldA + '0.3)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(cx, cy, r + 60, 0, 6.283); ctx.stroke();
  ctx.setLineDash([8, 10]); ctx.beginPath(); ctx.moveTo(70, cy); ctx.lineTo(W - 70, cy); ctx.moveTo(cx, cy - r - 150); ctx.lineTo(cx, cy + r + 120); ctx.stroke(); ctx.setLineDash([]);
  for (let i = 0; i < 72; i++) {
    const ang = i / 72 * 6.283 + t * 0.06, L = i % 6 === 0 ? 22 : 10;
    ctx.strokeStyle = G.goldA + (i % 6 === 0 ? '0.75)' : '0.35)');
    ctx.beginPath(); ctx.moveTo(cx + r * Math.cos(ang), cy + r * Math.sin(ang)); ctx.lineTo(cx + (r + L) * Math.cos(ang), cy + (r + L) * Math.sin(ang)); ctx.stroke();
  }
  ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 16; ctx.strokeStyle = G.gold; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.arc(cx, cy, r - 14, -1.25 + t * 0.2, 0.9 + t * 0.2); ctx.stroke();
  ctx.restore();
}
function tag(x, y, big, small, a, color = G.ink) {
  if (a <= 0.01) return;
  ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = G.goldA + '0.7)'; ctx.lineWidth = 2; ctx.fillStyle = 'rgba(18,13,9,0.85)';
  ctx.beginPath(); ctx.roundRect(x - 120, y - 52, 240, 104, 12); ctx.fill(); ctx.stroke(); ctx.restore();
  serifText(big, x, y + 4, { size: 54, weight: 900, color, a });
  serifText(small, x, y + 40, { size: 26, weight: 600, color: G.goldA + '0.9)', a });
}
function chapter(t, s, e, num, unit, line2) {
  const a = Math.min(easeOut(clamp((t - s) / 0.4)), clamp((e - t) / 0.3));
  if (a <= 0.01) return;
  serifText([[num, G.gold], [unit, G.ink]], 70, 230, { size: 120, weight: 700, a, align: 'left', spacing: 6 });
  ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = G.goldA + '0.45)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(70, 262); ctx.lineTo(70 + 360 * easeOut(clamp((t - s) / 0.6)), 262); ctx.stroke(); ctx.restore();
  serifText(line2, 72, 316, { size: 38, weight: 600, a, align: 'left', spacing: 4 });
}
function bgWord(str, y, size, a) {
  ctx.save(); ctx.globalAlpha = a; ctx.font = `900 ${size}px ${SERIF}`; ctx.textAlign = 'center'; ctx.letterSpacing = '24px';
  ctx.fillStyle = 'rgba(120,100,70,0.14)'; ctx.fillText(str, 540, y); ctx.restore();
}
function sub(t, s, e, parts, y = 1660) {
  const pin = clamp((t - s) / 0.3), pout = clamp((e - t) / 0.2);
  const a = Math.min(easeOut(pin), pout);
  serifText(parts, 540, y, { size: 62, weight: 900, color: G.ink, a, blur: (1 - easeOut(pin)) * 10, spacing: 0 });
}
function bokeh(t) {
  const r = rng(21);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 14; i++) {
    const x = r() * W, y = r() * H * 0.8, s = 6 + r() * 16, a = 0.05 + r() * 0.12;
    const g = ctx.createRadialGradient(x, y, 0, x, y, s);
    g.addColorStop(0, `rgba(255,220,170,${a})`); g.addColorStop(1, 'rgba(255,220,170,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x + 10 * Math.sin(t * 0.3 + i), y, s, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}
function floorLine(a) {
  const y = 1430;
  ctx.save(); ctx.globalAlpha = a;
  const g = ctx.createLinearGradient(0, y, 0, H); g.addColorStop(0, 'rgba(40,30,20,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0.9)');
  ctx.fillStyle = g; ctx.fillRect(0, y, W, H - y);
  ctx.strokeStyle = G.goldA + '0.18)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  ctx.strokeStyle = G.goldA + '0.22)'; ctx.beginPath(); ctx.ellipse(540, y + 10, 330, 46, 0, 0, 6.283); ctx.stroke();
  ctx.restore();
}
function sparkles(t, x, y, a) {
  const r = rng(5);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 26; i++) {
    const ph = r() * 6.28, dx = (r() - 0.5) * 180, dy = r() * 26;
    ctx.fillStyle = `rgba(255,225,170,${(a * (0.25 + 0.5 * (0.5 + 0.5 * Math.sin(t * 3 + ph)))).toFixed(3)})`;
    ctx.beginPath(); ctx.arc(x + dx, y + dy - 6 * Math.sin(t * 1.5 + ph), 2 + r() * 4, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}

// ---------- 月亮段：纸柱从地球冲到月亮
function moonShot(t, a) {
  if (a <= 0.01) return;
  ctx.save(); ctx.globalAlpha = a;
  const p = clamp((t - 6.6) / 2.2), grow = 1 - Math.pow(1 - p, 2.2);
  const shake = t > 6.6 && t < 8.8 ? 3 * Math.sin(t * 70) * (1 - p) : 0;
  ctx.translate(shake, 0);
  const ex = 540, ey = 1520, top = 420;
  // 地球
  let g = ctx.createRadialGradient(ex - 100, ey - 60, 20, ex, ey + 200, 420);
  g.addColorStop(0, '#6F8BA0'); g.addColorStop(0.6, '#2C3A47'); g.addColorStop(1, '#0E1218');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(ex, ey + 200, 400, Math.PI, 0); ctx.fill();
  ctx.save(); ctx.strokeStyle = 'rgba(140,190,230,0.35)'; ctx.lineWidth = 6; ctx.shadowColor = 'rgba(140,190,230,0.8)'; ctx.shadowBlur = 30;
  ctx.beginPath(); ctx.arc(ex, ey + 200, 404, Math.PI, 0); ctx.stroke(); ctx.restore();
  // 月亮（柱子到一半时亮起来）
  const ma = easeOut(clamp((p - 0.35) / 0.4));
  g = ctx.createRadialGradient(ex - 40, 260, 10, ex, 300, 120);
  g.addColorStop(0, '#F4EEE2'); g.addColorStop(0.7, '#A9A293'); g.addColorStop(1, '#4A463E');
  ctx.save(); ctx.globalAlpha = a * ma; ctx.shadowColor = 'rgba(255,240,210,0.7)'; ctx.shadowBlur = 70; ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(ex, 300, 110, 0, 6.283); ctx.fill();
  for (const [x, y, r] of [[-30, -20, 18], [35, 25, 12], [10, 50, 9], [-50, 40, 7]]) { ctx.fillStyle = 'rgba(80,74,64,0.35)'; ctx.beginPath(); ctx.arc(ex + x, 300 + y, r, 0, 6.283); ctx.fill(); }
  ctx.restore();
  // 纸柱
  const y1 = lerp(ey - 10, top, grow);
  g = ctx.createLinearGradient(520, 0, 560, 0); g.addColorStop(0, '#A89A80'); g.addColorStop(0.5, '#F3EAD8'); g.addColorStop(1, '#A89A80');
  ctx.save(); ctx.fillStyle = g; ctx.shadowColor = G.goldA + '0.9)'; ctx.shadowBlur = 34; ctx.fillRect(526, y1, 28, ey - 10 - y1); ctx.restore();
  // 柱顶光点
  node(540, y1, 8, p < 1 ? 1 : 0.6, '#FFF2D6');
  // 里程碑：柱子经过时依次出现
  const marks = [[1250, '珠峰', '第 27 次'], [1060, '太空边界', '第 30 次'], [800, '空间站', '第 32 次'], [440, '月球 38 万公里', '第 42 次']];
  for (const [y, txt, n] of marks) {
    const aa = y === 440 ? easeOut(clamp((t - 8.75) / 0.3)) : easeOut(clamp((y - y1 + 2) / 70));
    if (aa <= 0) continue;
    ctx.strokeStyle = G.goldA + (0.7 * aa) + ')'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(560, y); ctx.lineTo(640, y); ctx.stroke();
    ctx.fillStyle = G.gold; ctx.globalAlpha = a * aa; ctx.beginPath(); ctx.arc(560, y, 6, 0, 6.283); ctx.fill(); ctx.globalAlpha = a;
    serifText(txt, 660, y + 14, { size: 44, weight: 700, color: G.ink, align: 'left', a: aa });
    serifText(n, 500, y + 14, { size: 40, weight: 600, color: G.gold, align: 'right', a: aa });
  }
  ctx.restore();
}

window.draw = function (t) {
  background(t, { cx: 540, cy: 900, glow: 0.95 });
  bokeh(t);
  const sheetA = 1 - P(t, 6.3, 0.35) + P(t, 9.85, 0.4);   // 纸：0–6.4 和 10–15 出现
  const moonA = P(t, 6.35, 0.35) * (1 - P(t, 9.8, 0.4));

  // 背景大字
  bgWord('42', 640, 520, (1 - P(t, 2.7, 0.4)) * 1);
  bgWord('?', 640, 520, P(t, 2.9, 0.4) * (1 - P(t, 6.2, 0.3)));
  bgWord('384,400 km', 700, 120, moonA);
  bgWord('0.1 mm', 640, 230, P(t, 10.1, 0.5) * (1 - P(t, 13.9, 0.3)));
  bgWord('0.2 mm', 640, 230, P(t, 14.0, 0.4));

  if (sheetA > 0.01) {
    ctx.save(); ctx.globalAlpha = Math.min(1, sheetA);
    floorLine(1);
    // 相机：开场悬浮慢转；10s 后推近、俯视角更大，准备对折
    const close = P(t, 10.0, 1.2);
    const yaw = -0.5 + 0.12 * Math.sin(t * 0.35) + 0.25 * close;
    const pitch = lerp(0.42, 0.62, close);
    const cy = lerp(960, 930, close) + 10 * Math.sin(t * 1.2) * (1 - close);
    const cam = makeCam(540, cy, yaw, pitch, lerp(1.0, 1.25, close));
    const theta = Math.PI * ease(clamp((t - 13.0) / 1.1));
    tickRing(540, cy, 330, t, P(t, 3.0, 0.5) * (1 - P(t, 6.0, 0.3)) + P(t, 13.0, 0.4) * 0.8);
    paper(cam, 260, 190, theta);
    sparkles(t, 540, 1415, 1 - close);
    // 猜测：1 米 / 一栋楼
    tag(830, 700, '1 米？', '第一个猜测', easeOut(clamp((t - 4.0) / 0.3)) * (1 - P(t, 6.0, 0.3)));
    tag(250, 1180, '一栋楼？', '第二个猜测', easeOut(clamp((t - 5.1) / 0.3)) * (1 - P(t, 6.0, 0.3)));
    // 卡尺：0.1 mm → 0.2 mm
    const calA = P(t, 11.0, 0.4);
    if (calA > 0.01) {
      const e0 = cam([-260, 0, 190]);
      const x = e0[0] - 40, y = e0[1];
      ctx.save(); ctx.globalAlpha = calA; ctx.strokeStyle = G.gold; ctx.lineWidth = 2.5; ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 10;
      ctx.beginPath(); ctx.moveTo(x - 80, y - 14); ctx.lineTo(x, y - 14); ctx.moveTo(x - 80, y + 14); ctx.lineTo(x, y + 14); ctx.moveTo(x - 40, y - 60); ctx.lineTo(x - 40, y - 14); ctx.moveTo(x - 40, y + 60); ctx.lineTo(x - 40, y + 14); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x - 40, y - 14); ctx.lineTo(x - 48, y - 28); ctx.lineTo(x - 32, y - 28); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.moveTo(x - 40, y + 14); ctx.lineTo(x - 48, y + 28); ctx.lineTo(x - 32, y + 28); ctx.closePath(); ctx.fill();
      ctx.restore();
      const doubled = t > 14.05;
      serifText(doubled ? '0.2 mm' : '0.1 mm', x - 40, y + 120, { size: 52, weight: 900, color: doubled ? G.gold : G.ink, a: calA });
    }
    ctx.restore();
  }
  moonShot(t, moonA);

  // 左上章节标签
  chapter(t, 0.0, 2.75, '42', ' 次', '对折 · 能有多厚');
  chapter(t, 13.0, 16, '第 1', ' 次', '0.1 mm × 2');

  // 字幕底部压暗，保证可读
  { const g = ctx.createLinearGradient(0, 1520, 0, 1800); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.5, 'rgba(0,0,0,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0.3)'); ctx.fillStyle = g; ctx.fillRect(0, 1520, W, 280); }
  // 字幕
  sub(t, -1, 2.85, [['一张纸，对折 ', G.ink], ['42 次', G.gold], ['，能有多厚？', G.ink]]);
  sub(t, 2.95, 4.0, [['先猜一个数。', G.ink]]);
  sub(t, 4.0, 6.3, [['一米？', G.ink], ['一栋楼？', G.ink]]);
  sub(t, 6.45, 10.0, [['答案是：它能一直顶到', G.ink], ['月亮', G.gold], ['。', G.ink]]);
  sub(t, 10.1, 12.85, [['一张普通的纸，大约 ', G.ink], ['0.1 毫米', G.gold], ['。', G.ink]]);
  sub(t, 12.95, 16, [['对折 1 次，', G.ink], ['0.2 毫米', G.gold], ['。', G.ink]]);

  finish(t);
};
