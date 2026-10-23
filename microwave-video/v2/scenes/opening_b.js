// 开头 20.47 秒样片 · B 风格（照第二个对标：暗棕舞台 + 斜射聚光 + 米白线描角色 + 底部衬线字幕，关键词暗红）
// 台词时间同 opening.js
const B = { bg0: '#0E0907', bg1: '#1C1510', beam: 'rgba(120,92,58,', ink: '#F2E6CE', fill: '#1E1712', red: '#D95F4B', paper: '#EFE4CE', amber: 'rgba(255,186,96,' };
const FLOOR = 1330;
const DING = 10.25;

function stage(t) {
  ctx.fillStyle = B.bg0; ctx.fillRect(0, 0, W, H);
  let g = ctx.createRadialGradient(540, 820, 0, 540, 820, 1100);
  g.addColorStop(0, 'rgba(46,35,25,1)'); g.addColorStop(1, 'rgba(14,9,7,1)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // 斜射聚光：从左上打到画面中下
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const sway = 10 * Math.sin(t * 0.3);
  ctx.beginPath(); ctx.moveTo(-60 + sway, -40); ctx.lineTo(260 + sway, -40); ctx.lineTo(860, FLOOR + 40); ctx.lineTo(240, FLOOR + 40); ctx.closePath();
  g = ctx.createLinearGradient(100, 0, 560, FLOOR);
  g.addColorStop(0, B.beam + '0.30)'); g.addColorStop(1, B.beam + '0.10)');
  ctx.fillStyle = g; ctx.filter = 'blur(40px)'; ctx.fill(); ctx.filter = 'none';
  ctx.restore();
  // 地面线
  ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.fillRect(0, FLOOR, W, H - FLOOR);
  ctx.strokeStyle = 'rgba(242,230,206,0.35)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, FLOOR); ctx.lineTo(W, FLOOR); ctx.stroke();
}
function floorRings(x, a = 1) {
  ctx.save(); ctx.globalAlpha = a * 0.5; ctx.strokeStyle = B.ink; ctx.lineWidth = 2;
  for (const r of [150, 230]) { ctx.beginPath(); ctx.ellipse(x, FLOOR, r, r * 0.16, 0, 0, 6.283); ctx.stroke(); }
  ctx.restore();
}
function inked(fn, { lw = 7, fill = B.fill, stroke = B.ink } = {}) {
  ctx.save(); ctx.lineWidth = lw; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.beginPath(); fn(); if (fill) { ctx.fillStyle = fill; ctx.fill(); } if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
  ctx.restore();
}

// 线描角色"爸"：脚底中心 (x, FLOOR)；dir 1 朝右 / -1 朝左；walk 0..1 迈腿相位强度；arm 'down' | 'cross' | 'bowl'
function dad(t, x, { dir = 1, walk = 0, arm = 'down', look = 0, blink = false, s = 1 } = {}) {
  ctx.save(); ctx.translate(x, FLOOR); ctx.scale(s * dir, s);
  const sw = walk * Math.sin(t * 14);
  // 腿 + 鞋
  for (const [lx, ph] of [[-34, 1], [34, -1]]) {
    const off = 26 * sw * ph;
    inked(() => { ctx.moveTo(lx, -190); ctx.lineTo(lx + off, -22); }, { lw: 30, fill: null, stroke: B.ink });
    inked(() => { ctx.moveTo(lx, -190); ctx.lineTo(lx + off, -22); }, { lw: 16, fill: null, stroke: B.fill });
    inked(() => ctx.ellipse(lx + off + 14, -16, 40, 18, 0, 0, 6.283), { lw: 5, fill: B.ink });
  }
  // 身体（长外套）
  inked(() => { ctx.moveTo(-80, -170); ctx.lineTo(-62, -470); ctx.quadraticCurveTo(0, -500, 62, -470); ctx.lineTo(80, -170); ctx.closePath(); });
  inked(() => { ctx.moveTo(0, -480); ctx.lineTo(0, -200); }, { lw: 4, fill: null, stroke: 'rgba(242,230,206,0.5)' });
  // 手臂
  if (arm === 'cross') {
    inked(() => { ctx.moveTo(-58, -440); ctx.quadraticCurveTo(-20, -350, 50, -370); }, { lw: 26, fill: null, stroke: B.ink });
    inked(() => { ctx.moveTo(-58, -440); ctx.quadraticCurveTo(-20, -350, 50, -370); }, { lw: 13, fill: null, stroke: B.fill });
  } else if (arm === 'bowl') {
    inked(() => { ctx.moveTo(50, -440); ctx.quadraticCurveTo(110, -380, 170, -380); }, { lw: 26, fill: null, stroke: B.ink });
    inked(() => { ctx.moveTo(50, -440); ctx.quadraticCurveTo(110, -380, 170, -380); }, { lw: 13, fill: null, stroke: B.fill });
  } else {
    const a = arm === 'run' ? 30 * sw : 0;
    inked(() => { ctx.moveTo(40, -450); ctx.lineTo(56 + a, -260); }, { lw: 26, fill: null, stroke: B.ink });
    inked(() => { ctx.moveTo(40, -450); ctx.lineTo(56 + a, -260); }, { lw: 13, fill: null, stroke: B.fill });
    inked(() => ctx.arc(58 + a, -252, 15, 0, 6.283), { lw: 5, fill: B.ink });
  }
  // 头
  inked(() => ctx.arc(10, -580, 92, 0, 6.283));
  inked(() => { ctx.arc(10, -580, 92, Math.PI * 1.05, Math.PI * 1.85); ctx.quadraticCurveTo(10, -615, -80, -600); }, { lw: 0.1, fill: B.ink, stroke: null });
  // 眼睛
  if (blink) inked(() => { ctx.moveTo(30 + look, -572); ctx.lineTo(62 + look, -572); }, { lw: 6, fill: null });
  else {
    inked(() => ctx.arc(46 + look, -572, 20, 0, 6.283), { lw: 5, fill: B.paper, stroke: B.ink });
    inked(() => ctx.arc(52 + look, -572, 8, 0, 6.283), { lw: 0.1, fill: B.fill, stroke: null });
  }
  inked(() => { ctx.moveTo(100, -560); ctx.lineTo(116, -548); ctx.lineTo(100, -540); }, { lw: 5, fill: null });
  inked(() => ctx.arc(30, -548, 11, 0, 6.283), { lw: 0.1, fill: 'rgba(120,70,52,0.9)', stroke: null });
  ctx.restore();
}

// 线描微波炉（左上角 x,y，宽 w）
function microwaveB(t, x, y, w, { on = 1, disp = '1:30', flash = 0 } = {}) {
  const h = w * 0.6, r = 18;
  ctx.save(); ctx.translate(x, y);
  inked(() => ctx.roundRect(0, 0, w, h, r), { lw: 7 });
  const wx = 26, wy = 26, ww = w * 0.64, wh = h - 52;
  // 炉内暖光
  const g = ctx.createRadialGradient(wx + ww / 2, wy + wh * 0.8, 10, wx + ww / 2, wy + wh * 0.7, ww * 0.7);
  g.addColorStop(0, B.amber + (0.85 * on) + ')'); g.addColorStop(1, B.amber + (0.12 * on) + ')');
  inked(() => ctx.roundRect(wx, wy, ww, wh, 10), { lw: 5, fill: B.fill });
  if (on > 0.01) { ctx.fillStyle = g; ctx.beginPath(); ctx.roundRect(wx, wy, ww, wh, 10); ctx.fill(); }
  // 碗
  const bx = wx + ww / 2, by = wy + wh - 30;
  inked(() => { ctx.moveTo(bx - 70, by - 40); ctx.quadraticCurveTo(bx, by + 30, bx + 70, by - 40); ctx.closePath(); }, { lw: 5, fill: B.paper });
  inked(() => { ctx.ellipse(bx, by - 46, 54, 26, 0, Math.PI, 0); }, { lw: 5, fill: '#FBF5EA' });
  // 波纹
  if (on > 0.01) {
    ctx.save(); ctx.globalAlpha = on; ctx.strokeStyle = '#FFE2B0'; ctx.lineWidth = 4; ctx.shadowColor = B.amber + '1)'; ctx.shadowBlur = 12;
    for (const j of [0, 1]) { ctx.beginPath(); for (let k = 0; k <= ww - 40; k += 4) { const yy = wy + 36 + j * 34 + 9 * Math.sin(k / 20 - t * 6 - j); k ? ctx.lineTo(wx + 20 + k, yy) : ctx.moveTo(wx + 20 + k, yy); } ctx.stroke(); }
    ctx.restore();
  }
  // 面板
  const px = wx + ww + 22;
  inked(() => ctx.roundRect(px, wy + 6, w - px - 22, 56, 8), { lw: 4, fill: '#120D0A' });
  ctx.fillStyle = B.red; ctx.font = `700 40px ${SERIF}`; ctx.textAlign = 'center'; ctx.fillText(disp, (px + w - 22) / 2, wy + 50);
  for (const k of [0.58, 0.82]) inked(() => ctx.arc((px + w - 22) / 2, h * k, 22, 0, 6.283), { lw: 5 });
  if (flash > 0.01) { ctx.save(); ctx.globalAlpha = flash; ctx.strokeStyle = '#FFE2B0'; ctx.lineWidth = 6; ctx.shadowColor = B.amber + '1)'; ctx.shadowBlur = 40; ctx.beginPath(); ctx.roundRect(0, 0, w, h, r); ctx.stroke(); ctx.restore(); }
  ctx.restore();
}

// 底部字幕（粗衬线，米白，关键词暗红）
function sub(t, s, e, parts) {
  const pin = clamp((t - s) / 0.2), pout = clamp((e - t) / 0.2), a = Math.min(easeOut(pin), pout);
  serifText(parts, 540, 1560, { size: 64, weight: 900, a, color: B.ink, spacing: 3 });
}
// 对话气泡
function bubble(x, y, w, h, a, tailX, tailY, draw) {
  if (a <= 0.01) return;
  ctx.save(); ctx.globalAlpha = a;
  inked(() => { ctx.roundRect(x, y, w, h, 24); }, { lw: 5, fill: 'rgba(30,23,18,0.92)' });
  inked(() => { ctx.moveTo(x + w * 0.3, y + h - 3); ctx.lineTo(tailX, tailY); ctx.lineTo(x + w * 0.42, y + h - 3); }, { lw: 5, fill: 'rgba(30,23,18,0.92)' });
  draw(); ctx.restore();
}

window.draw = function (t) {
  stage(t);
  const A = 1 - P(t, 11.95, 0.35);         // 厨房段
  const Bs = P(t, 12.0, 0.35) * (1 - P(t, 16.1, 0.3)); // 讲科学 / 丝瓜汤
  const Cs = P(t, 16.2, 0.35);              // 验牌

  // ---------- 厨房（0–12.3s）
  if (A > 0.001) {
    ctx.save(); ctx.globalAlpha = A;
    // 门框（左侧）
    inked(() => { ctx.rect(30, 640, 250, FLOOR - 640); }, { lw: 7, fill: 'rgba(10,7,5,0.9)' });
    // 灶台
    inked(() => ctx.rect(560, 1060, 560, 40), { lw: 6, fill: '#2A2019' });
    inked(() => ctx.rect(600, 1100, 480, FLOOR - 1100), { lw: 6, fill: B.fill });
    const on = 1 - P(t, DING, 0.1), flash = Math.exp(-Math.pow((t - DING - 0.05) / 0.2, 2));
    const secs = t < DING ? Math.max(1, Math.ceil(DING - t)) : 0;
    microwaveB(t, 600, 780, 460, { on, disp: `0:${String(secs).padStart(2, '0')}`, flash });
    // "爸"的走位：0–5.2 站在微波炉前；6.39 转身跑向门；7.6–10 在门后探头；10.7 回来
    let x = 470, dir = 1, walk = 0, arm = 'down';
    if (t > 6.35) { const p = P(t, 6.4, 0.85); x = lerp(470, -40, p); dir = -1; walk = p > 0 && p < 1 ? 1 : 0; arm = 'run'; }
    let peek = 0;
    if (t > 7.4 && t < 10.6) { x = 150; dir = 1; walk = 0; arm = 'down'; peek = 1; }
    if (t > 10.6) { const p = P(t, 10.7, 0.9); x = lerp(150, 470, p); dir = 1; walk = p > 0 && p < 1 ? 1 : 0; arm = 'down'; peek = 1 - clamp((t - 10.6) / 0.3); }
    floorRings(x, x > 300 ? 1 : 0);
    // 探头：被门框遮住，只露出头，前后伸缩
    if (peek > 0) {
      const k = (t - 7.6) / 2.6;
      const out = t < 10.25 ? 0.15 + 0.85 * Math.max(0, Math.sin(Math.max(0, k) * Math.PI * 3)) ** 0.7 : 1;
      ctx.save(); ctx.beginPath(); ctx.rect(280, 0, W, H); ctx.clip();
      dad(t, 160 + 150 * out, { dir: 1, look: 6, blink: false });
      ctx.restore();
    } else if (x > -100) {
      ctx.save(); if (x < 300) { ctx.beginPath(); ctx.rect(280, 0, W, H); ctx.clip(); }
      dad(t, x, { dir, walk, arm, blink: ((t + 1.1) % 3.3) < 0.12 });
      ctx.restore();
    }
    // 叮！气泡
    const da = easeOut(clamp((t - DING) / 0.2)) * (1 - P(t, 11.6, 0.3));
    bubble(720, 560, 240, 150, da, 820, 760, () => serifText('叮！', 840, 660, { size: 84, weight: 900, color: B.red }));
    ctx.restore();
  }

  // ---------- 讲科学 → 丝瓜汤（12.0–16.4s）
  if (Bs > 0.001) {
    ctx.save(); ctx.globalAlpha = Bs;
    floorRings(330);
    const bowlOn = t > 13.9;
    dad(t, 330, { dir: 1, arm: bowlOn ? 'bowl' : 'cross', blink: ((t + 0.4) % 2.7) < 0.12 });
    // 你：讲科学的气泡（右侧，从画面外伸进来）
    const sa = easeOut(clamp((t - 12.3) / 0.3)) * (1 - P(t, 13.85, 0.25));
    bubble(560, 560, 440, 280, sa, 600, 900, () => {
      ctx.strokeStyle = '#FFE2B0'; ctx.lineWidth = 5; ctx.beginPath();
      for (let k = 0; k <= 360; k += 4) { const yy = 680 + 40 * Math.sin(k / 24 - t * 4); k ? ctx.lineTo(600 + k, yy) : ctx.moveTo(600, yy); }
      ctx.stroke();
      serifText('非电离辐射', 780, 800, { size: 46, weight: 700, color: B.ink });
    });
    // 丝瓜汤：爸端出来一碗汤
    if (bowlOn) {
      const q = easeOut(clamp((t - 13.95) / 0.35));
      ctx.save(); ctx.translate(330 + 190, FLOOR - 360); ctx.scale(q, q);
      inked(() => { ctx.moveTo(-110, -10); ctx.quadraticCurveTo(0, 110, 110, -10); ctx.closePath(); }, { lw: 6, fill: B.paper });
      inked(() => ctx.ellipse(0, -10, 110, 24, 0, 0, 6.283), { lw: 6, fill: '#C9D1AE' });
      for (const [dx, r] of [[-50, 16], [0, 14], [48, 17]]) inked(() => ctx.ellipse(dx, -10, r, r * 0.45, 0, 0, 6.283), { lw: 3, fill: '#7E9268' });
      ctx.strokeStyle = 'rgba(242,230,206,0.55)'; ctx.lineWidth = 4;
      for (let i = 0; i < 3; i++) { ctx.beginPath(); for (let k = 0; k <= 50; k++) { const yy = -40 - k * 3, xx = -40 + i * 40 + 8 * Math.sin(k / 7 - t * 3 + i); k ? ctx.lineTo(xx, yy) : ctx.moveTo(xx, yy); } ctx.stroke(); }
      ctx.restore();
      serifText('丝瓜汤', 620, 820, { size: 54, weight: 900, color: B.ink, a: q });
    }
    ctx.restore();
  }

  // ---------- 验牌（16.2–20.47s）
  if (Cs > 0.001) {
    ctx.save(); ctx.globalAlpha = Cs;
    // 绿呢赌桌换成暗色桌面
    inked(() => ctx.ellipse(540, FLOOR - 40, 470, 120, 0, 0, 6.283), { lw: 6, fill: '#241B14' });
    const hit = Math.exp(-Math.pow((t - 19.4) / 0.08, 2));
    const flip = easeOut(clamp((t - 16.5) / 0.6));
    ctx.save(); ctx.translate(540 + 8 * hit * Math.sin(t * 90), 900); ctx.rotate(-0.06 * (1 - flip)); ctx.scale(0.9 + 0.1 * flip, 0.9 + 0.1 * flip);
    inked(() => ctx.roundRect(-210, -290, 420, 580, 26), { lw: 7, fill: B.paper });
    inked(() => ctx.roundRect(-180, -260, 360, 520, 16), { lw: 3, fill: null, stroke: 'rgba(30,23,18,0.5)' });
    serifText('辐射？', 0, 30, { size: 100, weight: 900, color: B.fill });
    serifText('?', -150, -200, { size: 60, weight: 900, color: B.red });
    ctx.restore();
    if (t > 19.3) {
      const q = easeOut(clamp((t - 19.37) / 0.2));
      ctx.save(); ctx.translate(540, 470); ctx.scale(1.3 - 0.3 * q, 1.3 - 0.3 * q);
      serifText('我要验牌！', 0, 0, { size: 130, weight: 900, color: B.red, a: q });
      ctx.restore();
    }
    ctx.restore();
  }

  // ---------- 顶部钩子标题（开场 0–3s 就在第一帧）
  const hook = 1 - P(t, 2.9, 0.35);
  serifText([['微波炉热的饭，', B.ink]], 540, 330, { size: 88, weight: 900, a: hook });
  serifText([['到底有没有', B.ink], ['辐射', B.red], ['？', B.ink]], 540, 450, { size: 88, weight: 900, a: hook });
  // 右上角小计时器（贯穿厨房段）
  if (A > 0.01 && t > 3.0) {
    const a = A * P(t, 3.0, 0.4);
    ctx.save(); ctx.globalAlpha = a; inked(() => ctx.roundRect(820, 150, 56, 64, 10), { lw: 5, fill: null, stroke: '#D9B77A' }); ctx.restore();
    serifText(t < DING ? '加热中' : '叮', 900, 200, { size: 44, weight: 900, color: B.ink, a, align: 'left' });
  }

  // ---------- 底部字幕
  sub(t, 0.5, 3.05, [['微波炉热的饭，到底有没有', B.ink], ['辐射', B.red], ['？', B.ink]]);
  sub(t, 3.2, 5.05, [['你家是不是也有这么一位：', B.ink]]);
  sub(t, 5.15, 7.4, [['微波炉一转，他', B.ink], ['转身就跑', B.red], ['。', B.ink]]);
  sub(t, 7.55, 9.9, [['躲在厨房门口，探头探脑，', B.ink]]);
  sub(t, 9.9, 12.0, [['非得等', B.ink], ['「叮」', B.red], ['一声才敢回来。', B.ink]]);
  sub(t, 12.25, 13.85, [['你跟他讲科学，', B.ink]]);
  sub(t, 13.95, 16.2, [['他让你喝碗', B.ink], ['丝瓜汤', B.red], ['，降降火。', B.ink]]);
  sub(t, 16.35, 19.25, [['行，今天咱就当一回赌神：', B.ink]]);
  sub(t, 19.35, 21, [['我要', B.ink], ['验牌', B.red], ['！', B.ink]]);

  finish(t);
};
