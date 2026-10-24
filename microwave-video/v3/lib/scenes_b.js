// 《大脑的账本》37.6s 以后的场景。时间都来自 timing_rest.json（配音对齐结果）。
const CHAT = [{ side: 'L', text: '兄弟，借我200应个急', t0: -9 }, { side: 'L', text: '下个月生活费到了就还', t0: -9 },
  { side: 'R', kind: 'pay', amount: '200.00', note: '借你的', t0: -9 }, { side: 'L', text: '收到！谢啦', t0: -9 }];
function notePage(x, y, a, title, lines, inkFn, { rot = 0, pencil = false } = {}) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
    ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 36; ctx.fillStyle = C.paper; ctx.fillRect(-210, -250, 420, 500); ctx.shadowBlur = 0;
    text(title, 0, -186, { size: 40, weight: 900, color: '#3A2A1A' });
    ctx.strokeStyle = 'rgba(80,60,40,0.3)'; ctx.lineWidth = 1.5;
    lines.forEach((ln, i) => {
      const yy = -90 + i * 110; ctx.beginPath(); ctx.moveTo(-170, yy + 22); ctx.lineTo(170, yy + 22); ctx.stroke();
      const k = inkFn(i); if (k <= 0) return;
      ctx.save(); ctx.beginPath(); ctx.rect(-180, yy - 70, 360 * clamp(k * 1.6), 100); ctx.clip();
      ctx.font = `58px ${HAND}`; ctx.textAlign = 'center'; ctx.fillStyle = pencil ? 'rgba(60,50,40,0.45)' : C.pen; ctx.fillText(ln, 0, yy);
      if (!pencil) { ctx.lineWidth = 2.5; ctx.strokeStyle = C.pen; ctx.strokeText(ln, 0, yy); }
      ctx.restore();
    });
    ctx.restore();
  });
}
function pageFlipCard(t, t0, num, name) {   // 换页：大页签从中间翻出来再飞走
  const k = clamp((t - t0) / 1.0); if (k <= 0 || k >= 1) return;
  const inn = easeOut(k / 0.35), out = ease((k - 0.7) / 0.3);
  ctx.save(); ctx.translate(960, 520 - 300 * out); ctx.scale(Math.max(0.02, Math.min(1, inn)) * 1.6 * (1 - 0.5 * out), 1.6 * (1 - 0.5 * out)); ctx.translate(-960, -520);
  pageCard(960, 520, 1, 1 - out, num, name); ctx.restore();
}
// ============ 第一页后半：室友的两百块（37.6–57.6）
function sceneRoommate(t) {
  const a = vis(t, 37.55, 57.5, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    const cal = t < 40.83 ? ['2025年9月', '3', ''] : t < 43.76 ? ['2025年10月', '3', '下个月'] : ['2026年9月', '3', '一年后'];
    const flip = Math.min(Math.abs(t - 40.83), Math.abs(t - 43.76)), sx = flip < 0.2 ? Math.max(0.05, flip / 0.2) : 1;
    ctx.save(); ctx.translate(1700, 270); ctx.scale(1, sx); ctx.translate(-1700, -270); calendar(1700, 270, vis(t, 37.7, 46.6, 0.3), ...cal); ctx.restore();
    const out = ease((t - 43.6) / 0.5), back = ease((t - 53.9) / 0.5);
    const px = t < 50 ? lerp(1180, 2400, out) : lerp(2400, 1180, back);
    phone(px, 520, 0.95, t, { title: '室友小王', date: '2025年9月3日 21:14', msgs: CHAT, hi: 0 });
    phoneInput(px, 520, 0.95, t < 50 ? vis(t, 41.3, 43.6, 0.2) : 0, typing(t, '那个…上次那200…', 41.6, 42.5, 42.75, 43.3), t);
    // 转账气泡上的金色高光（转账记录）
    withAlpha(vis(t, 54.2, 57.5, 0.3) * (1 - clamp((t - 55.62) / 0.5) * 0.6), () => {
      ctx.save(); ctx.translate(px, 520); ctx.scale(0.95, 0.95); ctx.strokeStyle = C.gold; ctx.lineWidth = 5; ctx.shadowColor = C.goldA + '1)'; ctx.shadowBlur = 24;
      ctx.beginPath(); ctx.roundRect(-210 + 420 - 24 - 64 - 250 - 6, -410 + 200 + 78 * 2 - 6, 262, 130, 12); ctx.stroke(); ctx.restore();
    });
    const youX = lerp(560, 520, out);
    const pose = poseAt(t, [[37.6, 'phone'], [41.3, 'phone'], [43.76, 'think'], [46.8, 'stand'], [50.7, 'hips'], [54.0, 'point']]);
    const face = faceAt(t, [[37.6, 'neutral'], [41.6, 'confused'], [43.0, 'sad'], [43.76, 'neutral'], [45.48, 'smug'], [49.06, 'shock'], [50.7, 'neutral']]);
    figure(youX, 905, 1.25, t, { pose, face, prop: t < 43.76 ? 'phone' : null, hair: 0, seed: 1, a: 1 - 0.5 * vis(t, 54.0, 57.6, 0.3) });
    bubble(youX + 300, 300, 520, 200, vis(t, 44.0, 49.0, 0.3), () => {
      ctx.font = `68px ${HAND}`; ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.fillText('¥200', 0, -14); ctx.lineWidth = 2.5; ctx.strokeStyle = C.ink; ctx.strokeText('¥200', 0, -14);
      ctx.font = `44px ${HAND}`; ctx.globalAlpha *= clamp((t - 45.5) / 0.4); ctx.fillText('宿舍楼下 · 周三晚上', 0, 56);
    }, -0.4);
    // 室友登场
    const ra = vis(t, 46.8, 53.95, 0.35);
    figure(1360, 905, 1.25, t, { pose: poseAt(t, [[46.8, 'stand'], [47.81, 'scratch'], [50.7, 'shrug']]), face: faceAt(t, [[46.8, 'neutral'], [47.81, 'confused']]), hair: 1, seed: 4, flip: true, a: ra });
    mark(1330, 430, '?', vis(t, 47.9, 50.5, 0.2), t);
    bubble(1180, 300, 380, 170, vis(t, 49.0, 53.95, 0.3), () => {
      ctx.font = `80px ${HAND}`; ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.globalAlpha *= lerp(0.55, 0.04, ease((t - 52.54) / 1.0)); ctx.fillText('¥200 ?', 0, 28);
    }, 0.35);
    tag(1360, 160, '赖账？', vis(t, 50.7, 52.5, 0.2), (t - 51.1) / 0.35, 44);
    // 没有记录的账
    withAlpha(vis(t, 55.62, 57.5, 0.3), () => { text('没有记录的账', 1600, 500, { size: 52, weight: 900, color: C.ink }); text('偏得更厉害', 1600, 580, { size: 52, weight: 900, color: C.red }); });
  });
  pageFlipCard(t, 56.9, '02', '人情');
}
// ============ 第二页：人情（57.6–80.6）
function sceneFavors(t) {
  const a = vis(t, 57.6, 80.5, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    const gs = ease((t - 60.34) / 0.6);
    giftBook(lerp(960, 430, gs), lerp(470, 380, gs), lerp(1, 0.55, gs), vis(t, 57.7, 62.0, 0.3), t - 58.2);
    // 帮忙搬家：两人抬一个箱子
    const ma = vis(t, 60.4, 62.0, 0.3);
    figure(1215, 905, 1.1, t, { pose: 'hold', face: 'smile', hair: 0, seed: 1, a: ma });
    figure(1495, 905, 1.1, t, { pose: 'hold', face: 'happy', hair: 1, seed: 4, flip: true, a: ma });
    icon('box', 1355, 650, 1.35, ma);
    text('帮忙搬家', 1355, 300, { size: 46, weight: 900, color: C.ink, a: ma });
    tag(1355, 400, '记录：无', vis(t, 61.3, 62.0, 0.2), 0, 38);
    paperCard(960, 520, 0.95, vis(t, 62.04, 63.2, 0.25), { journal: 'Organizational Behavior and Human Decision Processes · 2003', title: 'What have you done for me lately? Temporal adjustments to favor evaluations', authors: 'Flynn' });
    yearTag(vis(t, 62.04, 66.2, 0.25), 2003);
    // 气球：帮忙的人 vs 受助的人
    const fa = vis(t, 63.0, 80.5, 0.3);
    const rH = t < 67.61 ? 62 : lerp(62, 150, easeOut((t - 67.61) / 1.4));
    const rR = t < 63.4 ? 0 : t < 69.86 ? 115 * easeOut((t - 63.2) / 0.5) : lerp(115, 34, easeOut((t - 69.86) / 1.4));
    const sp = vis(t, 76.6, 80.5, 0.3);
    figure(560, 905, 1.2, t, { pose: poseAt(t, [[63, 'stand'], [67.61, 'hips'], [72.32, 'point'], [76.7, 'stand']]), face: faceAt(t, [[63, 'neutral'], [67.61, 'smug']]), hair: 0, seed: 1, a: fa * (1 - 0.6 * clamp((t - 78.3) / 0.5)) });
    figure(1360, 905, 1.2, t, { pose: poseAt(t, [[63, 'stand'], [69.86, 'shrug']]), face: faceAt(t, [[63, 'happy'], [65.45, 'neutral'], [74.3, 'confused']]), hair: 1, seed: 4, flip: true, a: fa * (1 - 0.6 * clamp((t - 78.3) / 0.5)) });
    favorBalloon(600, 330 - (rH - 62) * 0.3, rH, fa * (1 - sp));
    favorBalloon(1320, 330, Math.max(4, rR), fa * (1 - sp));
    text('帮忙的人', 560, 980, { size: 0.1, a: 0 });
    // 时间条
    withAlpha(vis(t, 65.45, 72.3, 0.3), () => {
      const k = ease((t - 65.6) / 1.4); ctx.strokeStyle = 'rgba(243,230,211,0.3)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(760, 140); ctx.lineTo(1160, 140); ctx.stroke();
      ctx.strokeStyle = C.gold; ctx.beginPath(); ctx.moveTo(760, 140); ctx.lineTo(760 + 400 * k, 140); ctx.stroke();
      text('刚帮完', 760, 120, { size: 30, weight: 700, color: C.ink, align: 'center' }); text(k > 0.95 ? '很久以后' : '', 1160, 120, { size: 30, weight: 700, color: C.gold });
    });
    speech(700, 170, '我当初可帮过你！', vis(t, 72.32, 75.0, 0.25), { size: 46, tx: 610, ty: 260 });
    tag(1320, 220, '缩水', vis(t, 74.97, 76.6, 0.25), 0, 40);
    // 一个给、一个收
    withAlpha(sp * (1 - clamp((t - 78.3) / 0.5)), () => {
      ctx.strokeStyle = C.gold; ctx.lineWidth = 5; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(720, 470); ctx.lineTo(1200, 470); ctx.lineTo(1170, 450); ctx.moveTo(1200, 470); ctx.lineTo(1170, 490); ctx.stroke();
      text('给', 960, 450, { size: 48, weight: 900, color: C.gold }); text('收', 1360, 300, { size: 48, weight: 900, color: C.ink });
    });
  });
  pageFlipCard(t, 78.4, '03', '功劳');
}
// ============ 第三页：功劳（80.6–115）
function sceneCredit(t) {
  const a = vis(t, 80.6, 115.2, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    // 表盘：先估一次，再估一次
    const g1 = vis(t, 80.9, 87.0, 0.3), g2 = vis(t, 103.1, 105.8, 0.3);
    const v1 = t < 84.6 ? 0.5 + 0.25 * Math.sin((t - 81) * 3) * (1 - clamp((t - 83.5) / 1.2)) : 0.7;
    gauge(960, 600, 280, Math.max(g1, g2), g2 > 0 ? lerp(0.7, 0.55, ease((t - 104.25) / 1.0)) : v1, '你干了百分之几？');
    icon('mop', 470, 560, 1.4, vis(t, 82.08, 87.0, 0.25)); icon('dish', 470, 720, 1.3, vis(t, 82.3, 87.0, 0.25));
    text('家务', 470, 840, { size: 40, weight: 700, color: C.ink, a: vis(t, 82.08, 87.0, 0.25) });
    icon('ppt', 1450, 620, 1.6, vis(t, 83.11, 87.0, 0.25)); text('小组作业', 1450, 760, { size: 40, weight: 700, color: C.ink, a: vis(t, 83.11, 87.0, 0.25) });
    sticky(1660, 270, vis(t, 85.97, 106.0, 0.3), '我：70%', -0.06, (t - 104.4) / 0.4);
    sticky(1680, 440, vis(t, 104.9, 106.0, 0.3), '我：55%', 0.04);
    // 夫妻实验
    paperCard(470, 540, 0.85, vis(t, 87.07, 92.1, 0.3), { journal: 'Journal of Personality and Social Psychology · 1979', title: 'Egocentric biases in availability and attribution', authors: 'Ross & Sicoly' });
    yearTag(vis(t, 87.07, 92.1, 0.3), 1979);
    withAlpha(vis(t, 88.9, 93.3, 0.3), () => {
      const X0 = 900, BW = 720, k1 = easeOut((t - 89.0) / 0.5), k2 = easeOut((t - 90.14) / 0.6);
      ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.setLineDash([12, 8]); ctx.strokeRect(X0, 470, BW, 110); ctx.setLineDash([]);
      text('一整份', X0 + BW / 2, 450, { size: 36, weight: 700, color: C.ink });
      ctx.fillStyle = C.gold; ctx.fillRect(X0, 485, BW * 0.62 * k1, 80);
      const wy = lerp(640, 485, k2), wx = X0 + BW * 0.62 * k2;
      ctx.fillStyle = 'rgba(243,230,211,0.75)'; ctx.fillRect(wx, wy, BW * 0.58 * k1, 80);
      text('丈夫自评', X0 + 110, 610 + 150 * k2, { size: 32, weight: 700, color: C.gold, a: k1 * (k2 > 0 ? 1 : 0) + k1 * (k2 > 0 ? 0 : 0) });
      text('丈夫自评', X0 - 24, 538, { size: 32, weight: 700, color: C.gold, a: k1 * (1 - k2), align: 'right' });
      text('妻子自评', X0 - 24, 694, { size: 32, weight: 700, color: C.ink, a: k1 * (1 - k2), align: 'right' });
      text('妻子自评', wx + BW * 0.29, 760, { size: 32, weight: 700, color: C.ink, a: k1 * k2 });
      const ov = clamp((t - 90.91) / 0.4);
      withAlpha(ov, () => { ctx.fillStyle = C.redA + '0.85)'; ctx.fillRect(X0 + BW, 485, BW * 0.2 * k2, 80); text('超出', X0 + BW + 74, 450, { size: 40, weight: 900, color: C.red }); });
    });
    tag(960, 320, '撒谎？', vis(t, 92.22, 93.3, 0.2), (t - 92.6) / 0.35, 50);
    // 聚光灯：你干的 vs 对方干的
    const sa = vis(t, 93.5, 103.0, 0.3);
    withAlpha(sa, () => {
      const sx = t < 97.83 ? 600 : lerp(600, 1320, ease((t - 97.83) / 0.8));
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; const g = ctx.createRadialGradient(sx, 600, 40, sx, 600, 420); g.addColorStop(0, 'rgba(255,214,150,0.22)'); g.addColorStop(1, 'rgba(255,214,150,0)'); ctx.fillStyle = g; ctx.fillRect(0, 100, W, 900); ctx.restore();
      text('你干的', 600, 330, { size: 46, weight: 900, color: C.gold }); text('对方干的', 1320, 330, { size: 46, weight: 900, color: C.ink, a: t < 97.83 ? 0.3 : 1 });
      [['dish', '洗碗'], ['mop', '拖地'], ['laundry', '洗衣服']].forEach(([k, s], i) => { icon(k, 420 + i * 180, 560, 1.2, 1); text(s, 420 + i * 180, 680, { size: 32, weight: 700, color: C.ink }); });
      [['bowl', '做饭', 100.37], ['trash', '倒垃圾', 101.2], ['bill', '交水电费', 102.0]].forEach(([k, s, tt], i) => {
        const lit = clamp((t - tt) / 0.3), al = 0.1 + 0.9 * lit; icon(k, 1140 + i * 180, 560, 1.2, al, lit > 0.5 ? C.gold : C.ink); text(s, 1140 + i * 180, 680, { size: 32, weight: 700, color: C.ink, a: al });
      });
    });
    // 研究：先想别人，再估自己
    paperCard(470, 540, 0.85, vis(t, 105.86, 109.1, 0.3), { journal: 'Journal of Personality and Social Psychology · 2006', title: 'The costs and benefits of undoing egocentric responsibility assessments in groups', authors: 'Caruso, Epley & Bazerman' });
    yearTag(vis(t, 105.86, 109.1, 0.3), 2006);
    withAlpha(vis(t, 106.2, 109.1, 0.3), () => {
      const steps = [['先想别人', 106.4], ['再估自己', 107.1], ['高估 ↓', 108.04]];
      steps.forEach(([s, tt], i) => { const k = easeOut((t - tt) / 0.3); tag(1000 + i * 290, 540, s, k, 0, 40); if (i) withAlpha(k, () => text('→', 855 + i * 290, 556, { size: 48, weight: 900, color: C.gold })); });
    });
    // 三页都有个数，第四页没有
    const ca = vis(t, 109.19, 115.2, 0.3);
    [['01', '钱', '¥'], ['02', '人情', '忙'], ['03', '功劳', '%']].forEach(([n, s, v], i) => {
      const k = easeOut((t - 109.19 - i * 0.25) / 0.3); pageCard(420 + i * 260, 500, 0.9, ca * k, n, s, { dim: 0.25 * clamp((t - 111.83) / 0.4) });
      text(v, 420 + i * 260, 720, { size: 60, weight: 900, color: C.gold, a: ca * k * (0.4 + 0.6 * clamp((t - 110.28) / 0.3)) });
    });
    const k4 = easeOut((t - 111.83) / 0.4);
    pageCard(1400, 480, 1.25, ca * k4, '04', '伤害', { rot: 0.03 });
    text('？', 1400, 740, { size: 70, weight: 900, color: C.red, a: ca * clamp((t - 114.01) / 0.3) });
  });
}
// ============ 第四页：伤害（115.2–152.8）
function sceneHurt(t) {
  const a = vis(t, 115.3, 152.9, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    paperCard(400, 520, 0.85, vis(t, 115.48, 130.9, 0.3), { journal: 'Journal of Personality and Social Psychology · 1990', title: 'Victim and perpetrator accounts of interpersonal conflict: Autobiographical narratives about anger', authors: 'Baumeister, Stillwell & Wotman', rot: -0.05 });
    yearTag(vis(t, 115.48, 121.0, 0.3), 1990);
    const nA = vis(t, 117.76, 130.9, 0.3), nB = vis(t, 119.37, 130.9, 0.3);
    notePage(1030, 500, nA, '我受伤的那次', ['他莫名其妙', '到现在还膈应', '不是第一次了'], i => clamp((t - [122.83, 123.86, 124.99][i]) / 0.5), { rot: -0.02 });
    notePage(1530, 500, nB, '我伤人的那次', ['我是有原因的', '就这一回', '早过去了'], i => clamp((t - [128.30, 129.33, 130.23][i]) / 0.5), { rot: 0.03, pencil: true });
    // 吵架
    const qa = vis(t, 130.98, 139.1, 0.3);
    figure(640, 905, 1.25, t, { pose: poseAt(t, [[131, 'stand'], [133.06, 'shrug']]), face: faceAt(t, [[131, 'neutral'], [133.06, 'smug']]), hair: 0, seed: 1, a: qa });
    figure(1300, 905, 1.25, t, { pose: poseAt(t, [[131, 'stand'], [134.98, 'cross']]), face: faceAt(t, [[131, 'sad'], [134.98, 'angry']]), hair: 2, seed: 5, flip: true, a: qa });
    speech(720, 200, '你至于吗？就这点事。', vis(t, 133.06, 137.0, 0.2), { size: 46, tx: 660, ty: 300 });
    speech(1260, 200, '我忍你很久了。', vis(t, 135.82, 139.0, 0.2), { size: 50, col: C.red, tx: 1300, ty: 300, border: C.red });
    withAlpha(vis(t, 136.81, 139.1, 0.25), () => { text('这一笔', 640, 330, { size: 34, weight: 700, color: C.ink }); tally(640, 400, 1, 1); });
    withAlpha(vis(t, 137.94, 139.1, 0.25), () => { text('总账', 1300, 330, { size: 34, weight: 700, color: C.red }); tally(1300, 400, 12, 1, C.red); });
    // 亏心事
    tag(960, 480, '亏心事', vis(t, 139.74, 141.0, 0.25), 0, 70);
    paperCard(960, 520, 0.95, vis(t, 140.88, 144.2, 0.3), { journal: 'PNAS · 2016', title: 'Memories of unethical actions become obfuscated over time', authors: 'Kouchaki & Gino' });
    yearTag(vis(t, 140.88, 144.2, 0.3), 2016);
    tag(560, 420, '9 个实验', vis(t, 141.68, 144.2, 0.25), 0, 44); tag(1360, 420, '2100+ 人', vis(t, 142.3, 144.2, 0.25), 0, 44);
    // 两张“记忆照片”
    const ph = vis(t, 144.24, 152.9, 0.3);
    const scene1 = () => { ctx.fillStyle = 'rgba(255,214,150,0.15)'; ctx.fillRect(0, 0, 480, 360); figure(170, 330, 0.75, t, { pose: 'point', face: 'smug', hair: 0, seed: 1 }); icon('box', 360, 280, 0.9, 1, C.gold); text('骰子 6!', 360, 150, { size: 40, weight: 900, color: C.gold }); };
    const scene2 = () => { ctx.fillStyle = 'rgba(255,214,150,0.15)'; ctx.fillRect(0, 0, 480, 360); figure(300, 330, 0.75, t, { pose: 'hips', face: 'smug', hair: 1, seed: 4, flip: true }); text('插队', 130, 150, { size: 44, weight: 900, color: C.red }); };
    const blurK = clamp((t - 145.61) / 1.2), pixK = clamp((t - 150.39) / 0.4);
    photo(640, 500, 1, ph, scene1, { blur: 9 * blurK * (1 - pixK), pix: pixK > 0 ? 6 + 26 * pixK : 0, label: pixK > 0.5 ? '我的 · 已打码' : '我的', rot: -0.04 });
    photo(1300, 500, 1, ph * vis(t, 147.06, 153, 0.3), scene2, { label: t > 151.67 ? '别人的 · 原图' : '别人的', rot: 0.04 });
    withAlpha(vis(t, 151.9, 152.9, 0.2), () => { ctx.save(); ctx.translate(1440, 360); ctx.rotate(-0.2); ctx.strokeStyle = C.red; ctx.lineWidth = 5; ctx.strokeRect(-90, -36, 180, 72); text('原图保存', 0, 14, { size: 36, weight: 900, color: C.red }); ctx.restore(); });
  });
}
// ============ 封底：他的账本（152.9–192.4）
const HIS_L = [['你', '¥200'], ['阿杰', '¥80'], ['表弟', '¥300'], ['', '']];
function sceneHis(t) {
  const a = vis(t, 153.0, 193.1, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    // 四页收回你的账本
    const ya = vis(t, 153.1, 157.2, 0.3);
    book(960, 520, 1000, () => ledgerPage('别人欠我的', LED_L, [1, 1, 1, 1], null, 1, false, t), () => ledgerPage('我欠别人的', LED_R, [0.32, 0.15, 0.05, 0], null, 0, false, t), { a: ya });
    text('你的账本', 960, 200, { size: 50, weight: 900, color: C.gold, a: ya });
    // 封蜡第五页
    const sk = vis(t, 155.5, 158.1, 0.25), brk = clamp((t - 157.13) / 0.4);
    pageCard(960, 520, 1.3 * (1 + 0.2 * brk), sk * (1 - brk), '', '', { sealed: true });
    withAlpha(sk * brk * (1 - brk), () => { for (let i = 0; i < 12; i++) { const an = i / 12 * 6.283, r = 80 + 200 * brk; ctx.fillStyle = '#A8352A'; ctx.beginPath(); ctx.arc(960 + r * Math.cos(an), 520 + r * Math.sin(an), 14 * (1 - brk), 0, 6.283); ctx.fill(); } });
    paperCard(1320, 520, 0.85, vis(t, 158.1, 160.1, 0.3), { journal: 'Organizational Behavior and Human Decision Processes · 2022', title: 'Misaligned mindsets between borrowers and lenders of small interpersonal loans', authors: 'Morvinski & Shani' });
    yearTag(vis(t, 158.1, 160.1, 0.3), 2022);
    // 他：想催又删掉（和开头你的样子一模一样）
    const fa = vis(t, 160.1, 164.0, 0.3);
    figure(620, 905, 1.25, t, { pose: 'phone', prop: 'phone', face: faceAt(t, [[160, 'neutral'], [161.56, 'confused'], [162.7, 'sad']]), hair: 1, seed: 4, a: fa });
    phone(1250, 520, 0.95, t, { title: '你', date: '2025年11月', msgs: [{ side: 'R', kind: 'pay', amount: '200.00', note: '先拿去用', t0: -9 }, { side: 'L', text: '谢了兄弟！', t0: -9 }], a: fa });
    phoneInput(1250, 520, 0.95, fa, typing(t, '那个…上次的钱…', 160.6, 161.6, 162.4, 163.2), t);
    // 交易 vs 交情
    const ja = vis(t, 164.0, 172.0, 0.3);
    figure(520, 905, 1.2, t, { pose: 'stand', face: 'neutral', hair: 0, seed: 1, a: ja });
    figure(1400, 905, 1.2, t, { pose: 'stand', face: faceAt(t, [[164, 'smile'], [170.23, 'shock']]), hair: 1, seed: 4, flip: true, a: ja });
    tag(520, 300, '交易', vis(t, 164.92, 172.0, 0.25), 0, 60); text('借的人', 520, 200, { size: 34, weight: 700, color: C.ink, a: vis(t, 164.07, 172, 0.25) });
    tag(1400, 300, '交情', vis(t, 167.65, 172.0, 0.25), 0, 60); text('借出的人', 1400, 200, { size: 34, weight: 700, color: C.ink, a: vis(t, 166.41, 172, 0.25) });
    balance(960, 440, vis(t, 169.19, 172.0, 0.3), t < 170.23 ? 0 : -0.22 * easeOut((t - 170.23) / 0.6), '钱', '感情');
    // 他不说
    const sa = vis(t, 172.0, 176.0, 0.3);
    figure(960, 905, 1.3, t, { pose: 'stand', face: 'sad', hair: 1, seed: 4, a: sa });
    mark(1000, 440, '...', vis(t, 172.3, 176.0, 0.2), t);
    text('不代表没事', 960, 260, { size: 56, weight: 900, color: C.red, a: vis(t, 174.75, 176.0, 0.25) });
    paperCard(960, 520, 0.95, vis(t, 175.93, 177.8, 0.3), { journal: 'Journal of Economic Psychology · 2012', title: "Lenders' blind trust and borrowers' blind spots: A descriptive investigation of personal loans", authors: 'Dezső & Loewenstein' });
    yearTag(vis(t, 175.93, 177.8, 0.3), 2012);
    // 越走越远
    const da = vis(t, 177.75, 186.4, 0.3), sep = ease((t - 178.9) / 2.2);
    const yx = lerp(780, 520, sep), hx = lerp(1140, 1420, sep);
    figure(yx, 905, 1.2, t, { pose: t > 183.6 ? 'phone' : 'stand', prop: t > 183.6 ? 'phone' : null, face: t > 183.6 ? 'happy' : 'neutral', hair: 0, seed: 1, a: da });
    figure(hx, 905, 1.2, t, { pose: 'stand', face: t > 179 ? 'sad' : 'neutral', hair: 1, seed: 4, flip: true, a: da });
    withAlpha(da * sep, () => { ctx.strokeStyle = C.goldA + '0.6)'; ctx.setLineDash([10, 10]); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(yx + 80, 760); ctx.lineTo(hx - 80, 760); ctx.stroke(); ctx.setLineDash([]); text('越来越远', (yx + hx) / 2, 740, { size: 34, weight: 700, color: C.gold }); });
    bubble(hx - 160, 300, 380, 150, vis(t, 181.79, 186.4, 0.25), () => { ctx.font = `60px ${HAND}`; ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.fillText('他在躲我？', 0, 20); }, 0.35);
    text('察觉不到', yx, 330, { size: 40, weight: 700, color: C.ink, a: vis(t, 184.0, 186.4, 0.25) });
    // 他的账本：你那一行墨迹最重
    const ha = vis(t, 186.22, 193.1, 0.35), z = 1 + 0.12 * ease((t - 188.62) / 3);
    ctx.save(); ctx.translate(960, 520); ctx.scale(z, z); ctx.translate(-960, -520);
    book(960, 520, 1080, () => {
      ledgerPage('别人欠我的', HIS_L, [1, 0.35, 0.3, 0], null, 0, false, t);
      const b = clamp((t - 191.56) / 0.4);
      ctx.save(); ctx.font = `62px ${HAND}`; ctx.fillStyle = C.pen; ctx.lineWidth = 2 + 5 * b; ctx.strokeStyle = C.pen; ctx.textAlign = 'left'; ctx.strokeText('你', 72, 230); ctx.textAlign = 'right'; ctx.strokeText('¥200', 828, 230); ctx.restore();
      if (b > 0) { ctx.save(); ctx.globalAlpha = b * 0.35; ctx.fillStyle = '#C9862E'; ctx.fillRect(50, 160, 800, 100); ctx.restore(); }
    }, () => ledgerPage('我欠别人的', [['', ''], ['', ''], ['', ''], ['', '']], [0, 0, 0, 0], null, 0, false, t), { a: ha, cover: '#1E2A44', glowL: clamp((t - 191.56) / 0.4) });
    ctx.restore();
    text('他的账本', 960, 180, { size: 50, weight: 900, color: C.gold, a: ha });
  });
}
// ============ 结尾（192.4–205.5）
function sceneEnd(t) {
  const a = vis(t, 192.95, 205.6, 0.35); if (a <= 0.01) return;
  withAlpha(a, () => {
    const ba = vis(t, 193.0, 195.6, 0.3);
    book(560, 520, 700, () => ledgerPage('别人欠我的', LED_L, [1, 1, 1, 1], null, 1, false, t), () => ledgerPage('我欠别人的', LED_R, [0.3, 0.15, 0.05, 0], null, 0, false, t), { a: ba });
    book(1360, 520, 700, () => ledgerPage('别人欠我的', HIS_L, [1, 0.35, 0.3, 0], null, 1, false, t), () => ledgerPage('我欠别人的', [['', ''], ['', ''], ['', ''], ['', '']], [0, 0, 0, 0], null, 0, false, t), { a: ba, cover: '#1E2A44' });
    text('你的', 560, 270, { size: 44, weight: 900, color: C.gold, a: ba }); text('他的', 1360, 270, { size: 44, weight: 900, color: C.gold, a: ba });
    tag(960, 160, '偏心', vis(t, 194.57, 195.6, 0.2), 0, 54);
    const pa = vis(t, 195.57, 202.5, 0.3);
    billList(960, 520, 0.95, pa, [['小王', '借你的', '-200.00', false], ['表姐', '转账给你', '+500.00', true], ['小李', '饭钱', '+86.00', true], ['房东', '房租', '-1800.00', false], ['美团', '外卖', '-32.50', false]], 1, clamp((t - 197.07) / 0.4));
    figure(420, 905, 1.25, t, { pose: poseAt(t, [[195.5, 'phone'], [198.4, 'think'], [200.64, 'point']]), prop: t < 198.4 ? 'phone' : null, face: faceAt(t, [[195.5, 'neutral'], [197.07, 'shock'], [198.4, 'confused'], [200.64, 'smug']]), hair: 0, seed: 1, a: pa });
    text('先看你自己那一页', 1500, 300, { size: 44, weight: 900, color: C.gold, a: vis(t, 197.07, 202.5, 0.3) });
    // 转发按钮
    withAlpha(vis(t, 200.64, 202.6, 0.25), () => {
      const press = 1 - 0.08 * Math.max(0, 1 - Math.abs(t - 201.7) / 0.15);
      ctx.save(); ctx.translate(1500, 760); ctx.scale(press, press); ctx.fillStyle = '#3FA35B'; ctx.beginPath(); ctx.roundRect(-170, -50, 340, 100, 50); ctx.fill();
      text('转发给他', 0, 16, { size: 44, weight: 700, color: '#fff', font: SANS }); ctx.restore();
    });
  });
  // 片尾卡
  const e = vis(t, 202.6, 999, 0.5);
  withAlpha(e, () => {
    ctx.fillStyle = 'rgba(10,7,5,0.94)'; ctx.fillRect(0, 0, W, H);
    text('大脑的账本', W / 2, 420, { size: 140, weight: 900, color: C.gold, spacing: 18, glow: 0.4 });
    text([['你忘掉的那笔钱，', C.ink], ['他一直记着。', C.red]], W / 2, 540, { size: 52, weight: 700 });
    const refs = ['Morvinski & Shani (2022) Organizational Behavior and Human Decision Processes', 'Dezső & Loewenstein (2012) Journal of Economic Psychology', 'Flynn (2003) Organizational Behavior and Human Decision Processes',
      'Ross & Sicoly (1979) Journal of Personality and Social Psychology', 'Caruso, Epley & Bazerman (2006) Journal of Personality and Social Psychology',
      'Baumeister, Stillwell & Wotman (1990) Journal of Personality and Social Psychology', 'Kouchaki & Gino (2016) PNAS'];
    text('参考研究', W / 2, 680, { size: 26, weight: 700, color: C.gold, a: 0.8 });
    refs.forEach((r, i) => text(r, W / 2, 724 + i * 36, { size: 22, weight: 600, color: C.dim, spacing: 0 }));
  });
}
