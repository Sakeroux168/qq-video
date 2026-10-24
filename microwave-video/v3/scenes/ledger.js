// 《大脑的账本》横屏 1920×1080。时间轴对齐 debt/audio/voice_final.wav（已在 19.85s 处插 1.6s 给标题卡）。
const DUR = 202.4;
const SUBS = [
  [0.12, 2.15, '最近一个欠你钱的人，是谁？'], [2.33, 3.5, '一秒就想起来了吧。'],
  [3.65, 5.6, '那你最近，欠了谁的钱？'], [6.22, 6.95, '卡住了吧。'],
  [7.04, 9.3, '不是你记性差，是大脑在偷偷记账：'],
  [9.51, 11.2, '别人欠你的，墨水加粗；'], [11.44, 13.15, '你欠别人的，自动褪色。'],
  [13.26, 16.7, '这本账一共四页：钱、人情、功劳、伤害。'],
  [16.84, 18.95, '最扎心的那个发现，不在这四页里，'], [19.09, 19.85, '我放最后。'],
  [21.85, 24.2, '钱最好对账，偏偏它最先对不上。'],
  [24.37, 26.55, '2022年，有学者做了一系列实验；'], [26.72, 29.5, '更早，还有人调查过朋友之间真实的借钱。'],
  [29.69, 30.4, '结论一样：'], [30.55, 32.05, '借出去的人记得更牢，'], [32.24, 33.9, '欠钱的人更容易忘。'],
];

// ============ 开场：手机里的室友（0–7.0）
function sceneOpen(t) {
  const a = vis(t, -1, 7.1, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    const out = ease((t - 3.55) / 0.5);   // 手机滑出
    phone(lerp(1330, 2400, out), 520, 0.95, t, {
      title: '室友小王', date: '2025年9月3日 21:14', hi: vis(t, 2.35, 3.6, 0.2),
      msgs: [{ side: 'L', text: '兄弟，借我200应个急', t0: 0.25 }, { side: 'L', text: '下个月生活费到了就还', t0: 0.6 },
        { side: 'R', kind: 'pay', amount: '200.00', note: '借你的', t0: 1.0 }, { side: 'L', text: '收到！谢啦', t0: 1.45 }],
    });
    const fx = lerp(620, 860, ease((t - 3.6) / 0.6));
    const pose = poseAt(t, [[0, 'phone'], [2.33, 'point'], [3.65, 'think'], [5.45, 'scratch']]);
    const face = faceAt(t, [[0, 'neutral'], [2.33, 'smug'], [3.65, 'neutral'], [4.62, 'confused'], [6.22, 'shock']]);
    figure(fx, 905, 1.3, t, { pose, face, prop: t < 2.33 ? 'phone' : null, hair: 0, seed: 1 });
    // 想法气泡：先是“小王 ¥200”（墨迹很重），再变空白、光标闪
    const b1 = vis(t, 2.4, 3.65, 0.2), b2 = vis(t, 3.75, 7.1, 0.25);
    bubble(fx + 280, 300, 400, 160, b1, () => { ctx.font = `76px ${HAND}`; ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.fillText('小王  ¥200', 0, 26); }, -0.45);
    bubble(fx + 280, 300, 400, 160, b2, () => { if (Math.floor(t * 2.2) % 2 === 0) { ctx.fillStyle = C.red; ctx.fillRect(-4, -40, 6, 76); } }, -0.45);
    mark(fx + 60, 470, '?', vis(t, 4.62, 7.0, 0.2), t);
    mark(fx - 70, 500, 'sweat', vis(t, 5.45, 7.0, 0.2), t);
  });
}
// ============ 大脑在记账（7.0–13.3）
function sceneLedger(t) {
  const a = vis(t, 7.0, 13.6, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    tag(1000, 470, '记性差？', vis(t, 7.05, 7.95, 0.2), (t - 7.45) / 0.35, 56);
    const drop = easeOut((t - 7.8) / 0.5);
    const lw = [0, 1, 2, 3].map(i => clamp((t - 9.55 - i * 0.22) / 0.35));
    const rw = [0, 1, 2, 3].map(i => clamp((t - 11.5 - i * 0.18) / 0.3));
    const fade = clamp((t - 12.45) / 0.6), rInk = [lerp(0.6, 0.32, fade), lerp(0.55, 0.15, fade), lerp(0.5, 0.05, fade), 0];
    const bold = ease((t - 10.46) / 0.35);
    book(1000, 520 + (1 - drop) * 60 - 0 * drop, 1180 * (0.94 + 0.06 * drop),
      () => ledgerPage('别人欠我的', LED_L, [1, 1, 1, 1], lw, bold, false, t),
      () => ledgerPage('我欠别人的', LED_R, rInk, rw, 0, t > 12.6, t),
      { open: 1, a: drop, glowL: bold * 0.8 });
    // 标注线
    const la = vis(t, 10.5, 13.6, 0.25), ra = vis(t, 12.5, 13.6, 0.25);
    withAlpha(la, () => { ctx.strokeStyle = C.goldA + '0.8)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(620, 470); ctx.lineTo(420, 360); ctx.lineTo(220, 360); ctx.stroke(); });
    text('墨迹 100%', 220, 344, { size: 40, weight: 900, color: C.gold, align: 'left', a: la });
    withAlpha(ra, () => { ctx.strokeStyle = C.redA + '0.8)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(1400, 640); ctx.lineTo(1600, 560); ctx.lineTo(1760, 560); ctx.stroke(); });
    text('墨迹 6%', 1760, 544, { size: 40, weight: 900, color: C.red, align: 'right', a: ra });
  });
}
// ============ 一共四页 + 封存的第五页（13.3–19.9）
function scenePages(t) {
  const a = vis(t, 13.35, 19.95, 0.3); if (a <= 0.01) return;
  withAlpha(a, () => {
    const names = [['01', '钱'], ['02', '人情'], ['03', '功劳'], ['04', '伤害']], at = [14.37, 14.98, 15.70, 16.30];
    const shift = -110 * ease((t - 18.12) / 0.6);
    names.forEach(([n, s], i) => {
      // 先扣着出现，念到哪页翻哪页
      const k = easeOut((t - 13.45 - i * 0.08) / 0.3), f = clamp((t - at[i] + 0.12) / 0.3), sx = Math.abs(Math.cos(f * Math.PI));
      ctx.save(); const cx = 560 + i * 250 + shift, cy = 520 - (1 - k) * 50; ctx.translate(cx, cy); ctx.scale(Math.max(0.02, sx), 1); ctx.translate(-cx, -cy);
      if (f < 0.5) pageCard(cx, cy, 1, k, '', '', { sealed: true, back: true, rot: (i - 1.5) * 0.03 });
      else pageCard(cx, cy, 1, k, n, s, { rot: (i - 1.5) * 0.03 });
      ctx.restore();
    });
    const sk = easeOut((t - 16.84) / 0.35), sep = ease((t - 18.12) / 0.6), away = ease((t - 19.15) / 0.6);
    pageCard(1560 + 80 * sep + 140 * away, 520 - (1 - sk) * 50 - 40 * sep, 1 + 0.08 * sep - 0.25 * away, sk * (1 - 0.6 * away), '', '', { sealed: true, rot: 0.06 });
    withAlpha(sep * (1 - away), () => { ctx.strokeStyle = C.goldA + '0.5)'; ctx.setLineDash([10, 10]); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(1460, 330); ctx.lineTo(1460, 710); ctx.stroke(); ctx.setLineDash([]); });
  });
}
// ============ 第一页：钱（21.75–34）
function slip(x, y, str, a, ink = 1, rot = 0) {
  withAlpha(a, () => { ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 30; ctx.fillStyle = C.paper; ctx.fillRect(-200, -110, 400, 220); ctx.shadowBlur = 0;
    ctx.globalAlpha *= ink; ctx.font = `76px ${HAND}`; ctx.fillStyle = C.pen; ctx.textAlign = 'center'; ctx.fillText(str, 0, 26); ctx.restore(); });
}
function sceneMoney(t) {
  const a = vis(t, 21.7, 40, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    // 对账：两张单据，一张清楚一张糊
    const sa = vis(t, 21.85, 24.6, 0.3);
    slip(640, 470, '借出 ¥200', sa, 1, -0.05);
    slip(1280, 470, '借入 ¥?', sa, lerp(1, 0.35, ease((t - 22.9) / 0.5)), 0.04);
    text('≠', 960, 500, { size: 140, weight: 900, color: C.red, a: sa * easeOut((t - 22.95) / 0.3) });
    // 两篇研究
    const pa = vis(t, 24.37, 30.6, 0.3), pb = vis(t, 26.72, 30.6, 0.3);
    paperCard(1260, 520, 0.95, pa, { journal: 'Organizational Behavior and Human Decision Processes · 2022', title: 'Misaligned mindsets between borrowers and lenders of small interpersonal loans', authors: 'Morvinski & Shani' });
    paperCard(lerp(400, 700, easeOut((t - 26.72) / 0.5)), 540, 0.95, pb, { journal: 'Journal of Economic Psychology · 2012', title: "Lenders' blind trust and borrowers' blind spots: A descriptive investigation of personal loans", authors: 'Dezső & Loewenstein', rot: 0.05 });
    const yr = t < 26.72 ? 2022 : lerp(2022, 2012, ease((t - 26.72) / 0.6));
    yearTag(vis(t, 24.37, 30.6, 0.3), yr);
    withAlpha(vis(t, 29.69, 30.6, 0.2), () => { text('=', 980, 560, { size: 120, weight: 900, color: C.gold, glow: 0.4 }); });
    // 借出的人 vs 欠钱的人
    const fa = vis(t, 30.5, 40, 0.3);
    figure(620, 905, 1.2, t, { pose: 'hips', face: 'smug', a: fa, hair: 0, seed: 2 });
    figure(1300, 905, 1.2, t, { pose: poseAt(t, [[0, 'stand'], [32.24, 'scratch']]), face: t > 32.24 ? 'confused' : 'neutral', a: fa * easeOut((t - 30.8) / 0.3), hair: 1, seed: 3, flip: true });
    bubble(770, 290, 360, 160, vis(t, 30.7, 40, 0.25), () => { ctx.font = `80px ${HAND}`; ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.fillText('¥200', 0, 28); ctx.lineWidth = 3; ctx.strokeStyle = C.ink; ctx.strokeText('¥200', 0, 28); }, -0.4);
    bubble(1150, 290, 360, 160, vis(t, 32.3, 40, 0.25), () => { ctx.font = `80px ${HAND}`; ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.globalAlpha *= lerp(0.8, 0.12, ease((t - 32.6) / 1.0)); ctx.fillText('¥200', 0, 28); }, 0.4);
  });
}

window.draw = function (t) {
  const spot = t < 7 ? 820 : t < 13.3 ? 1000 : t < 21.7 ? 1060 : 960;
  stage(t, { spot, ring: t < 7 || t > 30.4 ? 1 : 0.4 });
  sceneOpen(t); sceneLedger(t); scenePages(t); sceneMoney(t);
  hud(vis(t, 21.8, 999, 0.4), '01', '钱', 'MONEY');
  hudRight(vis(t, 7.0, 999, 0.5));
  subtitles(t, SUBS);
  titleCard(t, 19.85, 1.95);
  finishFrame(t);
};
