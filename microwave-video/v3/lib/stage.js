// 舞台（风格 B 底）：暖棕暗场 + 一束可移动的顶光 + 地面光圈。颜色常量全片共用。
const C = { ink: '#F3E6D3', gold: '#E2B66E', goldA: 'rgba(226,182,110,', red: '#D9634F', redA: 'rgba(217,99,79,', bg: '#120D09', paper: '#E9DFC9', pen: '#1C140C', dim: '#9C8E7C' };
// spot: 光束落点 x；spotA：亮度；floorY：地面线
function stage(t, { spot = 960, spotA = 1, floorY = 905, ring = 1 } = {}) {
  ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(spot, 560, 60, spot, 560, 1100); glow.addColorStop(0, 'rgba(70,52,34,0.55)'); glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = spotA;
  const g = ctx.createLinearGradient(spot - 300, 0, spot + 200, 900); g.addColorStop(0, 'rgba(255,214,150,0.18)'); g.addColorStop(1, 'rgba(255,214,150,0)');
  ctx.fillStyle = g; ctx.filter = 'blur(46px)'; ctx.beginPath(); ctx.moveTo(spot - 380, -40); ctx.lineTo(spot - 120, -40); ctx.lineTo(spot + 520, floorY + 60); ctx.lineTo(spot - 420, floorY + 60); ctx.closePath(); ctx.fill();
  ctx.restore();
  const fl = ctx.createRadialGradient(spot, floorY, 30, spot, floorY, 760); fl.addColorStop(0, 'rgba(120,90,55,0.5)'); fl.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = fl; ctx.fillRect(0, floorY - 200, W, H - floorY + 200);
  if (ring > 0) withAlpha(ring, () => { ctx.strokeStyle = 'rgba(230,190,130,0.22)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(spot, floorY, 560, 62, 0, 0, 6.283); ctx.stroke(); });
}
// 漂浮尘埃（光束里）
const DUST = (() => { const r = rng(3); return [...Array(40)].map(() => ({ x: r() * W, y: r() * H, s: 0.8 + r() * 2, v: 5 + r() * 12, ph: r() * 6.3, a: 0.15 + r() * 0.35 })); })();
function dust(t) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const d of DUST) { const y = ((d.y - t * d.v) % H + H) % H, x = d.x + 16 * Math.sin(t * 0.4 + d.ph); ctx.fillStyle = `rgba(255,214,160,${(d.a * (0.6 + 0.4 * Math.sin(t * 1.3 + d.ph))).toFixed(3)})`; ctx.beginPath(); ctx.arc(x, y, d.s, 0, 6.283); ctx.fill(); }
  ctx.restore();
}
function finishFrame(t) { dust(t); vignette(0.62); grain(t, 0.05); }
// 角标：左上章节，右上片名
function hud(a, num, name, en) {
  if (a <= 0.01) return;
  text(num, 70, 92, { size: 40, color: C.gold, weight: 900, align: 'left', a });
  text(`${name} · ${en}`, 70 + (num.length > 2 ? 90 : 60), 90, { size: 26, color: C.ink, weight: 600, align: 'left', a: a * 0.8, spacing: 3 });
}
function hudRight(a) { text('大脑的账本', W - 70, 90, { size: 28, color: C.ink, weight: 700, align: 'right', a: a * 0.75, spacing: 4 }); }
