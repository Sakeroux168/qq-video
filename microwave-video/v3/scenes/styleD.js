// 风格 D：暗场光斑 + 白色棋子小人 + UI 卡片（照“知识诅咒”样片）。近黑偏蓝底，金/蓝虚化光斑，金色衬线字幕。
const INKD = '#EFE6D8', GOLDD = '#E3B871', REDD = '#E0604E';
const BOKEH = (() => { const r = rng(5); return [...Array(46)].map(() => ({ x: r() * W, y: r() * H, s: 20 + r() * 70, c: r() < 0.7 ? [230, 170, 90] : [90, 130, 200], a: 0.05 + r() * 0.12, ph: r() * 6 })); })();
function bokehBg(t) {
  ctx.fillStyle = '#07080C'; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const b of BOKEH) {
    const x = b.x + 12 * Math.sin(t * 0.2 + b.ph), g = ctx.createRadialGradient(x, b.y, b.s * 0.6, x, b.y, b.s);
    g.addColorStop(0, `rgba(${b.c},${b.a})`); g.addColorStop(1, `rgba(${b.c},0)`);
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, b.y, b.s, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}
// 棋子小人：圆头 + 钟形身体，柔光
function pawn(x, y, s, a = 1, col = '#F6EEE2') {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s); ctx.shadowColor = 'rgba(255,230,190,0.6)'; ctx.shadowBlur = 30;
    const g = ctx.createLinearGradient(0, -120, 0, 60); g.addColorStop(0, col); g.addColorStop(1, '#B9AE9E'); ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(0, -92, 30, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-60, 40); ctx.bezierCurveTo(-60, -20, -30, -54, 0, -54); ctx.bezierCurveTo(30, -54, 60, -20, 60, 40); ctx.closePath(); ctx.fill();
    ctx.restore();
  });
}
function card(x, y, w, h) {
  ctx.save(); ctx.fillStyle = 'rgba(16,14,14,0.88)'; ctx.strokeStyle = 'rgba(227,184,113,0.55)'; ctx.lineWidth = 2; ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 40;
  ctx.beginPath(); ctx.roundRect(x, y, w, h, 18); ctx.fill(); ctx.shadowBlur = 0; ctx.stroke(); ctx.restore();
}
function labelTag(x, y, str, a = 1, struck = 0) {
  withAlpha(a, () => {
    ctx.font = `600 34px ${SERIF}`; const w = ctx.measureText(str).width + 50;
    ctx.fillStyle = 'rgba(14,12,12,0.9)'; ctx.strokeStyle = 'rgba(239,230,216,0.6)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.roundRect(x - w / 2, y - 34, w, 60, 6); ctx.fill(); ctx.stroke();
    text(str, x, y + 8, { size: 34, weight: 600, color: INKD });
    if (struck > 0) { ctx.strokeStyle = REDD; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x - w / 2 - 6, y - 4); ctx.lineTo(x - w / 2 - 6 + (w + 12) * struck, y - 4); ctx.stroke(); }
  });
}
window.draw = function (t) {
  bokehBg(t);
  // 中间：账本卡片
  const X = 560, Y = 210, CW = 800, CH = 560;
  card(X, Y, CW, CH);
  text('大脑的账本', X + CW / 2, Y + 66, { size: 34, weight: 700, color: GOLDD, spacing: 8 });
  ctx.strokeStyle = 'rgba(227,184,113,0.3)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(X + CW / 2, Y + 100); ctx.lineTo(X + CW / 2, Y + CH - 40); ctx.stroke();
  text('别人欠我的', X + CW / 4, Y + 150, { size: 38, weight: 900, color: INKD });
  text('我欠别人的', X + CW * 3 / 4, Y + 150, { size: 38, weight: 900, color: INKD, a: 0.85 });
  ledgerColumn(X + 40, Y + 240, CW / 2 - 70, LEDGER_L, '#F6E9D2', [1, 1, 1, 1], 38, 76, 'rgba(227,184,113,0.25)');
  ledgerColumn(X + CW / 2 + 30, Y + 240, CW / 2 - 70, LEDGER_R, '#F6E9D2', [0.32, 0.16, 0.06, 0], 38, 76, 'rgba(227,184,113,0.25)');
  if (Math.floor(t * 2) % 2 === 0) { ctx.fillStyle = REDD; ctx.fillRect(X + CW / 2 + 40, Y + 432, 3, 42); }
  // 两边：棋子小人 + 误解标签
  pawn(330, 760, 1.25); pawn(1590, 760, 1.25, 0.55);
  labelTag(330, 540, '我记性好？', 1, 1); labelTag(1590, 540, '他人品差？', 1, 1);
  // 角标
  text('01', 70, 92, { size: 40, color: GOLDD, weight: 900, align: 'left' });
  text('钱 · MONEY', 128, 90, { size: 26, color: INKD, weight: 600, align: 'left', a: 0.75 });
  text('THE LEDGER', W - 70, 90, { size: 22, color: INKD, weight: 600, align: 'right', a: 0.5, spacing: 6 });
  text([['别人欠你的，', INKD], ['墨水加粗', GOLDD], ['；你欠别人的，', INKD], ['自动褪色', REDD], ['。', INKD]], W / 2, 1000, { size: 46, weight: 700, shadow: 0.8 });
  vignette(0.7); grain(t, 0.06);
};
