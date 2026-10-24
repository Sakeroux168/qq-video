// 风格 B：舞台聚光 + 线描小人（照昨天的“goed”样片）。暖棕暗底，顶光打一束，地面一圈光斑。
const INK = '#F3E6D3', GOLDB = '#E2B66E', REDB = '#D9634F';
function stageBg() {
  ctx.fillStyle = '#120D09'; ctx.fillRect(0, 0, W, H);
  // 斜着打下来的一束顶光
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createLinearGradient(620, 0, 1000, 900); g.addColorStop(0, 'rgba(255,214,150,0.20)'); g.addColorStop(1, 'rgba(255,214,150,0.0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(560, -20); ctx.lineTo(820, -20); ctx.lineTo(1500, 980); ctx.lineTo(560, 980); ctx.closePath(); ctx.filter = 'blur(40px)'; ctx.fill();
  ctx.restore();
  const fl = ctx.createRadialGradient(980, 900, 40, 980, 900, 700); fl.addColorStop(0, 'rgba(120,90,55,0.55)'); fl.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = fl; ctx.fillRect(0, 600, W, 480);
  ctx.strokeStyle = 'rgba(230,190,130,0.25)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(980, 905, 520, 60, 0, 0, 6.283); ctx.stroke();
}
// 线描小人：站着，一手拿笔指向账本，表情得意（照样片：白描轮廓、身体是闭合形、地面一圈光）
function lineGuy(x, y, s, t) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  ctx.strokeStyle = INK; ctx.lineWidth = 4.5; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.fillStyle = '#17110C';
  // 腿
  ctx.beginPath(); ctx.moveTo(-26, 150); ctx.lineTo(-30, 300); ctx.lineTo(-52, 304); ctx.moveTo(22, 150); ctx.lineTo(28, 300); ctx.lineTo(52, 304); ctx.stroke();
  // 身体：上窄下宽的外套
  ctx.beginPath(); ctx.moveTo(-34, 40); ctx.quadraticCurveTo(-58, 90, -56, 160); ctx.lineTo(56, 160); ctx.quadraticCurveTo(58, 90, 34, 40); ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0, 46); ctx.lineTo(0, 158); ctx.stroke();
  // 左手叉腰
  ctx.beginPath(); ctx.moveTo(-40, 62); ctx.quadraticCurveTo(-86, 100, -50, 128); ctx.stroke();
  // 右手抬起拿笔指向账本
  const wob = Math.sin(t * 5) * 4;
  ctx.beginPath(); ctx.moveTo(40, 62); ctx.quadraticCurveTo(100, 70, 150, 30 + wob); ctx.stroke();
  ctx.lineWidth = 6; ctx.strokeStyle = '#E2B66E'; ctx.beginPath(); ctx.moveTo(146, 36 + wob); ctx.lineTo(190, -10 + wob); ctx.stroke();
  ctx.strokeStyle = INK; ctx.lineWidth = 4.5;
  // 头
  ctx.beginPath(); ctx.arc(0, -16, 52, 0, 6.283); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-44, -40); ctx.quadraticCurveTo(-6, -82, 44, -46); ctx.quadraticCurveTo(10, -60, -44, -40); ctx.fillStyle = INK; ctx.fill();
  ctx.fillStyle = INK; ctx.beginPath(); ctx.arc(12, -14, 5, 0, 6.283); ctx.arc(32, -14, 5, 0, 6.283); ctx.fill();
  ctx.beginPath(); ctx.moveTo(10, 10); ctx.quadraticCurveTo(24, 20, 38, 8); ctx.stroke();
  ctx.restore();
}
function ledgerB(x, y, t) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(-0.03);
  ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 40; ctx.fillStyle = '#E9DFC9'; ctx.fillRect(0, 0, 900, 520); ctx.shadowBlur = 0;
  ctx.strokeStyle = 'rgba(60,40,20,0.4)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(450, 0); ctx.lineTo(450, 520); ctx.stroke();
  text('别人欠我的', 225, 70, { size: 42, color: '#3A2A1A', font: SERIF, weight: 900 });
  text('我欠别人的', 675, 70, { size: 42, color: '#3A2A1A', font: SERIF, weight: 900 });
  ledgerColumn(40, 160, 370, LEDGER_L, '#1C140C', [1, 1, 1, 1], 40, 82);
  ledgerColumn(490, 160, 370, LEDGER_R, '#1C140C', [0.35, 0.18, 0.07, 0], 40, 82);
  if (Math.floor(t * 2) % 2 === 0) { ctx.fillStyle = REDB; ctx.fillRect(500, 360, 4, 46); }
  ctx.restore();
}
window.draw = function (t) {
  stageBg();
  ledgerB(760, 300, t);
  lineGuy(470, 540, 1.15, t);
  // 角标
  text('01', 70, 92, { size: 40, color: GOLDB, font: SERIF, weight: 900, align: 'left' });
  text('钱 · MONEY', 128, 90, { size: 26, color: INK, font: SERIF, weight: 600, align: 'left', a: 0.8 });
  text('大脑的账本', W - 70, 90, { size: 28, color: INK, font: SERIF, weight: 700, align: 'right', a: 0.8 });
  text([['别人欠你的，', INK], ['墨水加粗', GOLDB], ['；你欠别人的，', INK], ['自动褪色', REDB], ['。', INK]], W / 2, 1010, { size: 46, weight: 700, shadow: 0.8 });
  vignette(0.6); grain(t, 0.05);
};
