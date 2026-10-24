// 封面 1080×1920：右侧“地球—金线—月球”上帝视角，左侧大字标题。文字都放在中间 3:4 安全区内。
const STARS = (() => { const r = rng(77); return [...Array(160)].map(() => ({ x: r() * W, y: r() * 1700, s: 0.6 + r() * 1.8, a: 0.25 + r() * 0.7 })); })();
function bigLine(parts, x, y) {   // parts: [[文字, 字号, 颜色, 字重]]，左对齐、基线对齐
  ctx.save(); ctx.textBaseline = 'alphabetic'; ctx.letterSpacing = '4px'; let cx = x;
  for (const [s, size, color, wt] of parts) {
    ctx.font = `${wt || 900} ${size}px ${SERIF}`; ctx.fillStyle = color;
    ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 24; ctx.fillText(s, cx, y);
    if (color === G.gold) { ctx.shadowColor = G.goldA + '0.55)'; ctx.shadowBlur = size * 0.35; ctx.fillText(s, cx, y); }
    cx += ctx.measureText(s).width;
  }
  ctx.restore();
}
window.draw = function (t) {
  background(t, { cx: 760, cy: 900, glow: 0.8 });
  // 星空
  for (const s of STARS) { ctx.fillStyle = `rgba(255,236,200,${(s.a * 0.75).toFixed(3)})`; ctx.beginPath(); ctx.arc(s.x, s.y, s.s, 0, 6.283); ctx.fill(); }
  const X = 800, MY = 400, MR = 100, EY = 1640, ER = 210;
  earth(X, EY, ER);
  // 太空边界虚线圈
  ctx.save(); ctx.strokeStyle = G.goldA + '0.4)'; ctx.lineWidth = 2; ctx.setLineDash([10, 10]); ctx.beginPath(); ctx.arc(X, EY, ER + 26, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); ctx.restore();
  moon(X, MY, MR, 1);
  column(X, MY + MR + 4, EY - ER, 14);
  // 金线上的刻度
  for (const [y, r, l] of [[1350, '珠峰', '27'], [1250, '太空', '30'], [1050, '地球直径', '37'], [560, '月球', '42']]) {
    ctx.save(); ctx.strokeStyle = G.goldA + '0.7)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X + 16, y); ctx.lineTo(X + 60, y); ctx.stroke();
    ctx.fillStyle = G.gold; ctx.beginPath(); ctx.arc(X + 16, y, 5, 0, 6.283); ctx.fill(); ctx.restore();
    serifText(r, X + 72, y + 12, { size: 34, weight: 700, color: G.ink, align: 'left' });
    serifText(`第 ${l} 次`, X - 22, y + 11, { size: 28, weight: 600, color: G.gold, align: 'right', a: 0.85 });
  }
  // 顶部活动标签
  ctx.save(); ctx.font = `700 46px ${SERIF}`; ctx.letterSpacing = '6px'; const tw = ctx.measureText('Vibe知识大赏').width; ctx.restore();
  ctx.save(); ctx.strokeStyle = G.goldA + '0.85)'; ctx.lineWidth = 2.5; ctx.fillStyle = 'rgba(20,14,9,0.75)';
  ctx.beginPath(); ctx.roundRect(70, 300, tw + 64, 84, 42); ctx.fill(); ctx.stroke(); ctx.restore();
  serifText('Vibe知识大赏', 102, 358, { size: 46, weight: 700, color: G.gold, align: 'left', spacing: 6 });
  // 主标题
  bigLine([['一张纸', 130, G.ink]], 70, 640);
  bigLine([['对折', 130, G.ink], ['42', 245, G.gold], ['次', 130, G.ink]], 60, 900);
  bigLine([['能碰到', 118, G.ink]], 70, 1080);
  bigLine([['月亮？', 150, G.gold]], 70, 1250);
  // 副标题
  ctx.save(); ctx.strokeStyle = G.goldA + '0.5)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(74, 1318); ctx.lineTo(560, 1318); ctx.stroke(); ctx.restore();
  serifText([['0.1 毫米', G.ink], ['  →  ', G.goldA + '0.8)'], ['44 万公里', G.gold]], 72, 1390, { size: 54, weight: 700, align: 'left' });
  finish(0.5);
};
