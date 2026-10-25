// 账号头像三个方案，都画在中间 1080×1080 里（中心 960,540），之后裁成正方形、预览成圆形。
// ?v=A|B|C 由 t 选择：t<1 → A，t<2 → B，否则 C
function ringHud(cx, cy, r, a = 1) {
  withAlpha(a, () => {
    ctx.strokeStyle = C.goldA + '0.35)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.stroke();
    for (let i = 0; i < 72; i++) { const an = i / 72 * 6.283, L = i % 6 === 0 ? 26 : 12; ctx.strokeStyle = C.goldA + (i % 6 === 0 ? '0.8)' : '0.35)'); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(960 + (r - 8) * Math.cos(an), cy + (r - 8) * Math.sin(an)); ctx.lineTo(960 + (r - 8 - L) * Math.cos(an), cy + (r - 8 - L) * Math.sin(an)); ctx.stroke(); }
    ctx.shadowColor = C.goldA + '1)'; ctx.shadowBlur = 24; ctx.strokeStyle = C.gold; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(cx, cy, r - 50, -2.3, -0.2); ctx.stroke();
  });
}
function bgSquare() {
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.beginPath(); ctx.rect(420, 0, 1080, 1080); ctx.clip();
  ctx.fillStyle = C.bg; ctx.fillRect(420, 0, 1080, 1080);
  const g = ctx.createRadialGradient(960, 380, 40, 960, 540, 760); g.addColorStop(0, 'rgba(110,82,50,0.85)'); g.addColorStop(0.55, 'rgba(50,38,26,0.5)'); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(420, 0, 1080, 1080);
}
window.draw = function (t) {
  bgSquare();
  if (t < 1) {
    // A：系列小人的大头像，金色光圈，头顶一个灵光
    ringHud(960, 540, 500, 0.9);
    ctx.save(); ctx.translate(960, 440); ctx.scale(3.2, 3.2);
    ctx.strokeStyle = C.ink; ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.fillStyle = '#17110C';
    ctx.beginPath(); ctx.moveTo(-34, 100); ctx.quadraticCurveTo(-60, 150, -62, 200); ctx.lineTo(62, 200); ctx.quadraticCurveTo(60, 150, 34, 100); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 30, 62, 0, 6.283); ctx.fill(); ctx.stroke();
    ctx.fillStyle = C.ink; ctx.beginPath(); ctx.moveTo(-56, 6); ctx.quadraticCurveTo(-12, -54, 54, -2); ctx.quadraticCurveTo(12, -18, -56, 6); ctx.fill();
    ctx.beginPath(); ctx.arc(-18, 30, 6, 0, 6.283); ctx.arc(18, 30, 6, 0, 6.283); ctx.fill();
    ctx.beginPath(); ctx.arc(0, 50, 13, 0.25, Math.PI - 0.25); ctx.stroke();
    ctx.restore();
    // 头顶的灵光（金色小星）
    ctx.save(); ctx.translate(1210, 290); ctx.shadowColor = C.goldA + '1)'; ctx.shadowBlur = 40; ctx.fillStyle = C.gold; ctx.beginPath();
    for (let i = 0; i < 8; i++) { const r = i % 2 ? 22 : 70, an = i / 8 * 6.283 - Math.PI / 2; ctx.lineTo(r * Math.cos(an), r * Math.sin(an)); } ctx.closePath(); ctx.fill(); ctx.restore();
  } else if (t < 2) {
    // B：聚光灯下的小人仰望一个巨大的问号
    ringHud(960, 540, 500, 0.9);
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; const g = ctx.createLinearGradient(960, 100, 960, 900); g.addColorStop(0, 'rgba(255,214,150,0.28)'); g.addColorStop(1, 'rgba(255,214,150,0.02)');
    ctx.fillStyle = g; ctx.filter = 'blur(20px)'; ctx.beginPath(); ctx.moveTo(900, 120); ctx.lineTo(1020, 120); ctx.lineTo(1200, 860); ctx.lineTo(720, 860); ctx.closePath(); ctx.fill(); ctx.restore();
    ctx.strokeStyle = 'rgba(230,190,130,0.4)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(960, 860, 230, 34, 0, 0, 6.283); ctx.stroke();
    text('?', 1090, 600, { size: 380, weight: 900, color: C.gold, glow: 0.5 });
    figure(820, 880, 1.6, 0.3, { pose: 'think', face: 'smile', hair: 0, seed: 0 });
  } else {
    // C：衬线大字“知”
    ringHud(960, 540, 500, 0.9);
    text('知', 960, 680, { size: 470, weight: 900, color: C.gold, glow: 0.45 });
    text('VIBE · KNOWLEDGE', 960, 820, { size: 34, weight: 700, color: C.ink, spacing: 10, a: 0.75 });
  }
  ctx.restore();
  grain(t, 0.04);
};
