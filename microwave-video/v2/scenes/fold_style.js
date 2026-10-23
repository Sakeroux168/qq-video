// 风格 C 静帧（照骰子/羊距骨样片）：半写实立体物件 + 金色 HUD 刻度环 + 背景超大淡字 + 底部衬线字幕（关键词金色）
const G = { gold: '#D9B77A', goldA: 'rgba(217,183,122,', paper0: '#F3EAD8', paper1: '#CFC2A8', paper2: '#A89A80', ink: '#EDE3D2' };

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
function floor(y = 1430) {
  const g = ctx.createLinearGradient(0, y, 0, H);
  g.addColorStop(0, 'rgba(40,30,20,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0.9)');
  ctx.fillStyle = g; ctx.fillRect(0, y, W, H - y);
  ctx.strokeStyle = G.goldA + '0.18)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  ctx.strokeStyle = G.goldA + '0.25)'; ctx.beginPath(); ctx.ellipse(540, y + 10, 330, 46, 0, 0, 6.283); ctx.stroke();
}
function bgWord(str, y = 430, size = 300) {
  ctx.save(); ctx.font = `900 ${size}px ${SERIF}`; ctx.textAlign = 'center'; ctx.letterSpacing = '30px';
  ctx.fillStyle = 'rgba(120,100,70,0.13)'; ctx.fillText(str, 540, y); ctx.restore();
}
function bottomSub(parts) { serifText(parts, 540, 1650, { size: 64, weight: 900, color: G.ink, spacing: 2 }); }
// 立体纸堆：底面中心 (cx, by)，宽 w，进深 d，高 h（斜 30° 透视）
function paperStack(cx, by, w, d, h, layers) {
  const dx = d * 0.62, dy = d * 0.36;
  const x0 = cx - (w + dx) / 2, x1 = x0 + w;
  const top = by - h;
  // 阴影
  ctx.save(); ctx.filter = 'blur(18px)'; ctx.fillStyle = 'rgba(0,0,0,0.6)';
  ctx.beginPath(); ctx.ellipse(cx, by + 8, (w + dx) * 0.6, 34, 0, 0, 6.283); ctx.fill(); ctx.restore();
  // 正面
  let g = ctx.createLinearGradient(0, top, 0, by); g.addColorStop(0, G.paper1); g.addColorStop(1, '#8F8370');
  ctx.fillStyle = g; ctx.fillRect(x0, top, w, h);
  // 侧面
  g = ctx.createLinearGradient(x1, 0, x1 + dx, 0); g.addColorStop(0, G.paper2); g.addColorStop(1, '#6E6452');
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x1, top); ctx.lineTo(x1 + dx, top - dy); ctx.lineTo(x1 + dx, by - dy); ctx.lineTo(x1, by); ctx.closePath(); ctx.fill();
  // 顶面
  g = ctx.createLinearGradient(x0, top - dy, x1, top); g.addColorStop(0, '#FFF8EA'); g.addColorStop(1, G.paper0);
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x0, top); ctx.lineTo(x0 + dx, top - dy); ctx.lineTo(x1 + dx, top - dy); ctx.lineTo(x1, top); ctx.closePath(); ctx.fill();
  // 纸层纹理
  ctx.save(); ctx.strokeStyle = 'rgba(60,50,38,0.35)'; ctx.lineWidth = 1.2;
  for (let i = 1; i < layers; i++) { const y = top + h * i / layers; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.lineTo(x1 + dx, y - dy); ctx.stroke(); }
  ctx.restore();
  // 金色描边
  ctx.save(); ctx.strokeStyle = G.goldA + '0.55)'; ctx.lineWidth = 2; ctx.shadowColor = G.goldA + '0.8)'; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.moveTo(x0, by); ctx.lineTo(x0, top); ctx.lineTo(x0 + dx, top - dy); ctx.lineTo(x1 + dx, top - dy); ctx.lineTo(x1 + dx, by - dy); ctx.lineTo(x1, by); ctx.closePath();
  ctx.moveTo(x0, top); ctx.lineTo(x1, top); ctx.lineTo(x1 + dx, top - dy); ctx.moveTo(x1, top); ctx.lineTo(x1, by); ctx.stroke(); ctx.restore();
  return { top, x0, x1 };
}
function hudRing(cx, cy, r, t, a = 1) {
  ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = G.goldA + '0.35)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(cx, cy, r + 70, 0, 6.283); ctx.stroke();
  ctx.setLineDash([8, 10]); ctx.beginPath(); ctx.moveTo(60, cy); ctx.lineTo(W - 60, cy); ctx.moveTo(cx, cy - r - 160); ctx.lineTo(cx, cy + r + 140); ctx.stroke(); ctx.setLineDash([]);
  for (let i = 0; i < 72; i++) {
    const ang = i / 72 * 6.283 + t * 0.05, L = i % 6 === 0 ? 22 : 10;
    ctx.strokeStyle = G.goldA + (i % 6 === 0 ? '0.8)' : '0.4)');
    ctx.beginPath(); ctx.moveTo(cx + r * Math.cos(ang), cy + r * Math.sin(ang)); ctx.lineTo(cx + (r + L) * Math.cos(ang), cy + (r + L) * Math.sin(ang)); ctx.stroke();
  }
  ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 16; ctx.strokeStyle = G.gold; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.arc(cx, cy, r - 14, -1.2, 1.3); ctx.stroke();
  ctx.restore();
}
function tag(x, y, str, sub, a = 1) {
  ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = G.goldA + '0.7)'; ctx.lineWidth = 2; ctx.fillStyle = 'rgba(20,15,10,0.85)';
  ctx.beginPath(); ctx.roundRect(x - 34, y - 34, 68, 68, 10); ctx.fill(); ctx.stroke(); ctx.restore();
  serifText(str, x, y + 12, { size: 30, weight: 700, color: G.ink, a });
  serifText(sub, x, y + 82, { size: 34, weight: 600, color: G.ink, a });
}

window.draw = function (t) {
  const scene = Math.floor(t);       // 0/1/2 三张静帧
  background(t, { cx: 540, cy: 900, glow: 0.9 });
  bokeh(t);
  if (scene === 0) {
    bgWord('0.1 mm', 470, 230);
    floor();
    // 一张纸，微微倾斜悬浮
    ctx.save(); ctx.translate(540, 980); ctx.rotate(-0.12);
    paperStack(0, 0, 520, 420, 10, 1);
    ctx.restore();
    // 悬浮下方的金色碎光
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; const r = rng(5);
    for (let i = 0; i < 26; i++) { ctx.fillStyle = `rgba(255,225,170,${0.25 + r() * 0.5})`; ctx.beginPath(); ctx.arc(480 + r() * 140, 1400 + r() * 30, 2 + r() * 5, 0, 6.283); ctx.fill(); }
    ctx.restore();
    bottomSub([['一张纸，对折 ', G.ink], ['42 次', G.gold], ['，能有多厚？', G.ink]]);
  } else if (scene === 1) {
    bgWord('2⁴²', 470, 340);
    floor();
    hudRing(540, 930, 300, t);
    paperStack(540, 1110, 330, 300, 300, 24);
    tag(860, 600, '×2', '第 1 次'); tag(200, 760, '×2', '第 2 次'); tag(900, 1180, '×2', '第 10 次'); tag(190, 1230, '×2', '第 20 次');
    bottomSub([['不是加一层，是', G.ink], ['翻一倍', G.gold], ['。', G.ink]]);
  } else {
    bgWord('384,400 km', 470, 150);
    // 地球
    const ex = 540, ey = 1500, mx = 540, my = 360;
    let g = ctx.createRadialGradient(ex - 90, ey - 120, 20, ex, ey, 380);
    g.addColorStop(0, '#6F8BA0'); g.addColorStop(0.6, '#2C3A47'); g.addColorStop(1, '#0E1218');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(ex, ey + 180, 380, Math.PI, 0); ctx.fill();
    ctx.save(); ctx.strokeStyle = 'rgba(140,190,230,0.35)'; ctx.lineWidth = 6; ctx.shadowColor = 'rgba(140,190,230,0.8)'; ctx.shadowBlur = 30; ctx.beginPath(); ctx.arc(ex, ey + 180, 384, Math.PI, 0); ctx.stroke(); ctx.restore();
    // 月亮
    g = ctx.createRadialGradient(mx - 40, my - 40, 10, mx, my, 120);
    g.addColorStop(0, '#F4EEE2'); g.addColorStop(0.7, '#A9A293'); g.addColorStop(1, '#4A463E');
    ctx.save(); ctx.shadowColor = 'rgba(255,240,210,0.6)'; ctx.shadowBlur = 60; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(mx, my, 110, 0, 6.283); ctx.fill(); ctx.restore();
    for (const [x, y, r] of [[-30, -20, 18], [35, 25, 12], [10, 50, 9], [-50, 40, 7]]) { ctx.fillStyle = 'rgba(80,74,64,0.35)'; ctx.beginPath(); ctx.arc(mx + x, my + y, r, 0, 6.283); ctx.fill(); }
    // 纸柱：从地球一直到月亮
    ctx.save(); g = ctx.createLinearGradient(520, 0, 560, 0); g.addColorStop(0, G.paper2); g.addColorStop(0.5, G.paper0); g.addColorStop(1, G.paper2);
    ctx.fillStyle = g; ctx.shadowColor = G.goldA + '0.9)'; ctx.shadowBlur = 30; ctx.fillRect(526, my + 110, 28, ey - my - 120); ctx.restore();
    // 刻度标注
    const marks = [[1250, '珠峰 8.8 公里', '第 27 次'], [1060, '太空边界 100 公里', '第 30 次'], [760, '空间站 400 公里', '第 32 次'], [470, '月球 38 万公里', '第 42 次']];
    for (const [y, a, b] of marks) {
      ctx.strokeStyle = G.goldA + '0.7)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(560, y); ctx.lineTo(640, y); ctx.stroke();
      ctx.fillStyle = G.gold; ctx.beginPath(); ctx.arc(560, y, 6, 0, 6.283); ctx.fill();
      serifText(a, 660, y + 12, { size: 40, weight: 700, color: G.ink, align: 'left' });
      serifText(b, 500, y + 12, { size: 36, weight: 600, color: G.gold, align: 'right' });
    }
    bottomSub([['折 42 次，', G.ink], ['44 万公里', G.gold], ['，', G.ink]]);
    serifText('比地球到月亮还远。', 540, 1750, { size: 64, weight: 900, color: G.ink, spacing: 2 });
  }
  finish(t);
};
