// 风格 C：半写实立体物件 + 金色 HUD（上期《对折 42 次》的风格）。暖色中心光，账本是一本摊开的立体本子。
const GOLDC = '#D9B77A', INKC = '#EDE3D2', REDC = '#D8584A';
function warmBg(t) {
  ctx.fillStyle = '#0C0907'; ctx.fillRect(0, 0, W, H);
  const g = ctx.createRadialGradient(960, 520, 0, 960, 520, 1000); g.addColorStop(0, 'rgba(70,52,34,0.75)'); g.addColorStop(0.6, 'rgba(40,30,20,0.25)'); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.font = `900 520px ${SERIF}`; ctx.textAlign = 'center'; ctx.fillStyle = 'rgba(130,105,70,0.10)'; ctx.fillText('账', 960, 700); ctx.restore();
}
function hud(cx, cy, r, t) {
  ctx.save(); ctx.strokeStyle = 'rgba(217,183,122,0.28)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.ellipse(cx, cy, r, r * 0.32, 0, 0, 6.283); ctx.stroke();
  for (let i = 0; i < 96; i++) { const a = i / 96 * 6.283 + t * 0.05, L = i % 8 === 0 ? 18 : 8; ctx.strokeStyle = `rgba(217,183,122,${i % 8 === 0 ? 0.7 : 0.3})`; ctx.beginPath(); ctx.moveTo(cx + r * Math.cos(a), cy + r * 0.32 * Math.sin(a)); ctx.lineTo(cx + (r + L) * Math.cos(a), cy + (r + L) * 0.32 * Math.sin(a)); ctx.stroke(); }
  ctx.restore();
}
// 摊开的立体账本：每页先画在离屏画布上，再按横条做梯形透视（上边窄、下边宽）
const PAGE = document.createElement('canvas'); PAGE.width = 600; PAGE.height = 500; const pctx = PAGE.getContext('2d');
function warpPage(draw, tl, tr, bl, br) {   // 四个角的屏幕坐标
  const save = ctx; ctx = pctx; pctx.setTransform(1, 0, 0, 1, 0, 0); pctx.clearRect(0, 0, 600, 500); draw(); ctx = save;
  const N = 120;
  for (let i = 0; i < N; i++) {
    const v0 = i / N, v1 = (i + 1) / N;
    const xl = lerp(tl[0], bl[0], v0), xr = lerp(tr[0], br[0], v0), y0 = lerp(tl[1], bl[1], v0), y1 = lerp(tl[1], bl[1], v1);
    ctx.drawImage(PAGE, 0, v0 * 500, 600, 500 / N + 0.5, xl, y0, xr - xl, y1 - y0 + 0.8);
  }
}
window.draw = function (t) {
  warmBg(t);
  hud(960, 840, 640, t);
  // 阴影
  ctx.save(); ctx.filter = 'blur(30px)'; ctx.fillStyle = 'rgba(0,0,0,0.7)'; ctx.beginPath(); ctx.ellipse(960, 860, 620, 90, 0, 0, 6.283); ctx.fill(); ctx.restore();
  // 封皮（深红皮面）
  ctx.save(); ctx.fillStyle = '#4A1E17'; ctx.beginPath(); ctx.moveTo(405, 836); ctx.lineTo(585, 306); ctx.lineTo(1335, 306); ctx.lineTo(1515, 836); ctx.lineTo(960, 852); ctx.closePath(); ctx.fill(); ctx.restore();
  // 左页、右页（纸面 600×500 的局部坐标 → 透视）
  const pageDraw = (left) => () => {
    const g = ctx.createLinearGradient(0, 0, 600, 0);
    if (left) { g.addColorStop(0, '#E7DCC4'); g.addColorStop(1, '#C9BB9E'); } else { g.addColorStop(0, '#C6B89B'); g.addColorStop(1, '#ECE2CC'); }
    ctx.fillStyle = g; ctx.fillRect(0, 0, 600, 500);
    text(left ? '别人欠我的' : '我欠别人的', 300, 70, { size: 46, weight: 900, color: '#3A2A1A' });
    ledgerColumn(50, 170, 500, left ? LEDGER_L : LEDGER_R, '#1C140C', left ? [1, 1, 1, 1] : [0.35, 0.17, 0.06, 0], 46, 84);
    if (!left && Math.floor(t * 2) % 2 === 0) { ctx.fillStyle = REDC; ctx.fillRect(60, 380, 4, 50); }
  };
  warpPage(pageDraw(true), [600, 318], [954, 330], [430, 818], [954, 838]);
  warpPage(pageDraw(false), [966, 330], [1320, 318], [966, 838], [1490, 818]);
  // 书脊阴影 + 金描边
  ctx.save(); const sg = ctx.createLinearGradient(900, 0, 1020, 0); sg.addColorStop(0, 'rgba(0,0,0,0)'); sg.addColorStop(0.5, 'rgba(0,0,0,0.35)'); sg.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = sg; ctx.beginPath(); ctx.moveTo(920, 330); ctx.lineTo(1000, 330); ctx.lineTo(1000, 838); ctx.lineTo(920, 838); ctx.fill();
  ctx.strokeStyle = 'rgba(217,183,122,0.6)'; ctx.lineWidth = 2; ctx.shadowColor = 'rgba(217,183,122,0.8)'; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.moveTo(430, 818); ctx.lineTo(600, 318); ctx.lineTo(960, 330); ctx.lineTo(1320, 318); ctx.lineTo(1490, 818); ctx.lineTo(960, 838); ctx.closePath(); ctx.stroke(); ctx.restore();
  // HUD 标注
  ctx.save(); ctx.strokeStyle = 'rgba(217,183,122,0.7)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(560, 470); ctx.lineTo(380, 380); ctx.lineTo(240, 380); ctx.moveTo(1380, 640); ctx.lineTo(1560, 560); ctx.lineTo(1700, 560); ctx.stroke(); ctx.restore();
  text('墨迹 100%', 240, 366, { size: 34, weight: 700, color: GOLDC, align: 'left' });
  text('墨迹 6%', 1700, 546, { size: 34, weight: 700, color: REDC, align: 'right' });
  text('01', 70, 92, { size: 40, color: GOLDC, weight: 900, align: 'left' });
  text('钱 · MONEY', 128, 90, { size: 26, color: INKC, weight: 600, align: 'left', a: 0.75 });
  text('大脑的账本', W - 70, 90, { size: 28, color: INKC, weight: 700, align: 'right', a: 0.75 });
  text([['别人欠你的，', INKC], ['墨水加粗', GOLDC], ['；你欠别人的，', INKC], ['自动褪色', REDC], ['。', INKC]], W / 2, 1010, { size: 46, weight: 700, shadow: 0.8 });
  vignette(0.65); grain(t, 0.05);
};
