// 《Vibe知识大赏｜一张纸对折 42 次，厚度能碰到月亮》全片 · 风格 C
// 时间轴全部按用户配音（75.7s）的停顿检测结果对齐。
const DUR = 77.0;
const SUBS = [
  [-0.5, 3.78, '一张纸，对折 42 次，能有多厚？'],
  [3.72, 5.1, '先猜一个数。'], [5.1, 5.95, '一米？'], [5.95, 6.97, '一栋楼？'],
  [6.91, 9.08, '答案是：它能一直顶到月亮。'],
  [9.02, 11.66, '一张普通的纸，大约 0.1 毫米。'],
  [11.6, 13.5, '对折 1 次，0.2 毫米。'],
  [13.5, 15.2, '折 7 次，1 厘米多，'], [15.2, 16.45, '像一本小本子。'],
  [16.46, 18.25, '折 10 次，10 厘米，一个手掌宽。'],
  [18.25, 21.05, '到这儿，你还觉得没什么。'],
  [20.99, 23.97, '折 20 次，100 米，三十多层楼。'],
  [23.91, 26.05, '折 30 次，107 公里，'], [25.99, 28.11, '已经越过了太空的边界。'],
  [28.05, 30.24, '折 42 次，44 万公里，'], [30.18, 31.86, '比地球到月亮还远。'],
  [31.8, 34.33, '再多折 9 次，它能碰到太阳。'],
  [34.27, 35.53, '为什么会这样？'],
  [35.47, 36.75, '因为每折一次，'], [36.75, 37.72, '不是加一层，'], [37.66, 38.77, '是翻一倍。'],
  [38.71, 40.45, '前面的翻倍，只是从 0.1 毫米'], [40.45, 42.31, '变成 0.2 毫米，'],
  [42.25, 43.85, '你根本看不出来；'],
  [43.79, 46.66, '后面的翻倍，一下就是几十万公里。'],
  [46.6, 48.99, '那现实里，谁能折到 42 次？'], [48.93, 49.98, '没人能。'],
  [49.92, 52.4, '2002 年，美国一个高中生，'], [52.34, 54.41, '用一卷一公里多长的卫生纸，'],
  [54.35, 56.17, '也才折到第 12 次。'],
  [56.11, 58.56, '纸越折越厚、越折越短，'], [58.5, 60.14, '到后面根本折不动。'],
  [60.08, 62.79, '可这件事真正想说的，不是纸。'],
  [62.73, 63.95, '是那些一开始看起来'], [63.95, 65.31, '"没什么变化"的事。'],
  [65.25, 67.0, '攒钱、学一门手艺，'],
  [66.94, 69.33, '前面好几年都像那 0.1 毫米，'], [69.27, 70.84, '慢得让人想放弃。'],
  [70.78, 71.8, '翻倍的力量，'], [71.74, 73.87, '都藏在你看不见的后半段。'],
  [73.81, 77.0, '你现在，折到第几次了？'],
];
// 数字滚动显示
const fmtTicker = (v, dec = 0) => v.toFixed(dec);

// ================= 场景：一张纸（开场 0–7.0 / 近景对折 9.05–13.45 / 结尾 73.8–77）
function sceneSheet(t) {
  const a = vis(t, -1, 7.0) + vis(t, 9.05, 13.45) + vis(t, 73.75, 80);
  if (a <= 0.01) return;
  withAlpha(Math.min(1, a), () => {
    floorLine(1);
    const close = P(t, 9.05, 1.0) * (1 - P(t, 73.75, 0.01));
    const yaw = -0.5 + 0.12 * Math.sin(t * 0.35) + 0.25 * close;
    const pitch = lerp(0.42, 0.62, close);
    const cy = lerp(960, 930, close) + 10 * Math.sin(t * 1.2) * (1 - close);
    const endPush = 1 + 0.06 * P(t, 73.8, 3.0);
    const cam = makeCam(540, cy, yaw, pitch, lerp(1.0, 1.25, close) * endPush);
    const theta = t < 20 ? Math.PI * ease(clamp((t - 11.72) / 1.0)) : 0;
    tickRing(540, cy, 330, t, vis(t, 3.8, 6.95) + (t < 20 ? 0.8 * vis(t, 11.7, 13.45) : 0) + 0.6 * vis(t, 73.9, 80));
    paper3d(cam, 260, 190, theta);
    // 悬浮碎光
    if (close < 0.99) {
      const r = rng(5);
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 26; i++) { const ph = r() * 6.28, dx = (r() - 0.5) * 180, dy = r() * 26; ctx.fillStyle = `rgba(255,225,170,${((1 - close) * (0.25 + 0.5 * (0.5 + 0.5 * Math.sin(t * 3 + ph)))).toFixed(3)})`; ctx.beginPath(); ctx.arc(540 + dx, 1415 + dy - 6 * Math.sin(t * 1.5 + ph), 2 + r() * 4, 0, 6.283); ctx.fill(); }
      ctx.restore();
    }
    tag(830, 700, '1 米？', '第一个猜测', easeOut(clamp((t - 5.15) / 0.25)) * (1 - P(t, 6.8, 0.25)));
    tag(250, 1180, '一栋楼？', '第二个猜测', easeOut(clamp((t - 5.98) / 0.25)) * (1 - P(t, 6.8, 0.25)));
    // 卡尺 0.1 → 0.2 mm
    const calA = vis(t, 9.4, 13.45);
    if (calA > 0.01) {
      const e0 = cam([-260, 0, 190]); const x = e0[0] - 40, y = e0[1];
      withAlpha(calA, () => {
        ctx.strokeStyle = G.gold; ctx.fillStyle = G.gold; ctx.lineWidth = 2.5; ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 10;
        ctx.beginPath(); ctx.moveTo(x - 80, y - 14); ctx.lineTo(x, y - 14); ctx.moveTo(x - 80, y + 14); ctx.lineTo(x, y + 14); ctx.moveTo(x - 40, y - 60); ctx.lineTo(x - 40, y - 14); ctx.moveTo(x - 40, y + 60); ctx.lineTo(x - 40, y + 14); ctx.stroke();
        for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(x - 40, y + 14 * s); ctx.lineTo(x - 48, y + 28 * s); ctx.lineTo(x - 32, y + 28 * s); ctx.closePath(); ctx.fill(); }
      });
      const d = t > 12.75;
      serifText(d ? '0.2 mm' : '0.1 mm', x - 40, y + 120, { size: 52, weight: 900, color: d ? G.gold : G.ink, a: calA });
    }
  });
  chapter(vis(t, -0.5, 3.75), '42', ' 次', '对折 · 能有多厚', 1);
  chapter(vis(t, 11.75, 13.45), '第 1', ' 次', '0.1 mm × 2', easeOut((t - 11.75) / 0.6));
  chapter(vis(t, 73.9, 80), '第 ?', ' 次', '你，折到哪儿了', easeOut((t - 73.9) / 0.6));
}

// ================= 场景：冲向月亮（7.0–9.05）与 42 次（28.0–31.8）共用
function sceneMoon(t, s, e, quick) {
  const a = vis(t, s, e);
  if (a <= 0.01) return;
  withAlpha(a, () => {
    const lt = t - s, growDur = quick ? 1.55 : 2.0;
    const p = clamp((lt - 0.1) / growDur), grow = 1 - Math.pow(1 - p, 2.2);
    const shake = p > 0 && p < 1 ? 3 * Math.sin(t * 70) * (1 - p) : 0;
    ctx.translate(shake, 0);
    zoom(540, 960, 1.06 - 0.06 * easeOut(lt / 0.8), () => {
      earth(540, 1720, 400);
      moon(540, 300, 110, easeOut(clamp((p - 0.35) / 0.4)));
      const yTop = lerp(1310, 420, grow);
      column(540, yTop, 1316);
      const marks = [[1180, '珠峰', '第 27 次'], [1010, '太空边界', '第 30 次'], [780, '空间站', '第 32 次']];
      for (const [y, r, l] of marks) milestone(540, y, r, l, easeOut(clamp((y - yTop + 2) / 70)));
      milestone(540, 440, '月球 38 万公里', '第 42 次', easeOut(clamp((lt - growDur - 0.05) / 0.3)));
    });
  });
}

// ================= 场景：纸堆长高（13.45–21.0）
function sceneStack(t) {
  const a = vis(t, 13.45, 21.0);
  if (a <= 0.01) return;
  withAlpha(a, () => {
    floorLine(1);
    // 7 次 → 10 次
    const k = P(t, 16.5, 0.9);
    const hPx = lerp(42, 330, k);
    zoom(540, 1300, 1 + 0.04 * P(t, 18.3, 2.6), () => {
      paperStack(560, 1400, 280, 240, hPx, Math.round(lerp(14, 40, k)));
      // 左侧刻度尺（cm）
      const rx = 330, base = 1400, pxPerCm = 33;
      withAlpha(0.9, () => {
        ctx.strokeStyle = G.goldA + '0.7)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(rx, base); ctx.lineTo(rx, base - 11 * pxPerCm); ctx.stroke();
        for (let c = 0; c <= 11; c++) { const y = base - c * pxPerCm; ctx.beginPath(); ctx.moveTo(rx, y); ctx.lineTo(rx - (c % 5 === 0 ? 26 : 14), y); ctx.stroke(); }
      });
      for (const c of [0, 5, 10]) serifText(`${c} cm`, rx - 36, base - c * pxPerCm + 12, { size: 30, weight: 600, color: G.ink, align: 'right' });
      // 参照物：小本子（15.2）、手掌（17.4）
      withAlpha(vis(t, 15.25, 16.5), () => {
        ctx.save(); ctx.translate(920, 1330); ctx.rotate(-0.08);
        ctx.fillStyle = 'rgba(30,22,15,0.9)'; ctx.strokeStyle = G.gold; ctx.lineWidth = 3; ctx.beginPath(); ctx.roundRect(-70, -95, 140, 190, 8); ctx.fill(); ctx.stroke();
        ctx.strokeStyle = G.goldA + '0.6)'; for (let i = -1; i <= 1; i++) { ctx.beginPath(); ctx.moveTo(-40, i * 40); ctx.lineTo(40, i * 40); ctx.stroke(); }
        ctx.restore();
        serifText('小本子', 920, 1480, { size: 34, weight: 600, color: G.ink });
      });
      withAlpha(vis(t, 17.4, 21.0), () => {
        // 手掌轮廓：掌心 + 四指 + 拇指（立起来，与纸堆比高）
        ctx.save(); ctx.translate(930, 1400); ctx.strokeStyle = G.gold; ctx.lineWidth = 3; ctx.fillStyle = 'rgba(30,22,15,0.85)'; ctx.shadowColor = G.goldA + '0.8)'; ctx.shadowBlur = 10;
        ctx.beginPath(); ctx.roundRect(-62, -180, 124, 180, 26); ctx.fill(); ctx.stroke();
        for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.roundRect(-58 + i * 30, -310 + Math.abs(i - 1.5) * 16, 26, 150, 13); ctx.fill(); ctx.stroke(); }
        ctx.beginPath(); ctx.ellipse(-82, -110, 18, 56, -0.5, 0, 6.283); ctx.fill(); ctx.stroke();
        ctx.restore();
        serifText('手掌宽', 930, 1480, { size: 34, weight: 600, color: G.ink });
      });
    });
  });
  const n = t < 16.5 ? 7 : 10, val = n === 7 ? '1.28' : '10.24';
  chapter(vis(t, 13.55, 21.0), `第 ${n}`, ' 次', `${val} 厘米`, easeOut((t - 13.55) / 0.6));
}

// ================= 场景：越升越高（楼 21.0–23.95 / 太空 23.95–28.05 / 月亮 28.0–31.8 / 太阳 31.8–34.3）
function sceneBuilding(t) {
  const a = vis(t, 21.0, 23.95);
  if (a <= 0.01) return;
  withAlpha(a, () => zoom(540, 1400, 1.08 - 0.08 * easeOut((t - 21.0) / 0.9), () => {
    floorLine(1);
    // 楼：金色线描 + 窗格
    const bx = 560, bw = 300, top = 560, base = 1430;
    ctx.fillStyle = 'rgba(24,18,12,0.92)'; ctx.fillRect(bx, top, bw, base - top);
    ctx.strokeStyle = G.goldA + '0.8)'; ctx.lineWidth = 3; ctx.strokeRect(bx, top, bw, base - top);
    ctx.strokeStyle = G.goldA + '0.18)'; ctx.lineWidth = 1.5;
    for (let y = top + 28; y < base; y += 28) { ctx.beginPath(); ctx.moveTo(bx + 14, y); ctx.lineTo(bx + bw - 14, y); ctx.stroke(); }
    for (let x = bx + 50; x < bx + bw; x += 50) { ctx.beginPath(); ctx.moveTo(x, top + 10); ctx.lineTo(x, base); ctx.stroke(); }
    const p = 1 - Math.pow(1 - clamp((t - 21.15) / 1.4), 2.2);
    column(400, lerp(base - 10, top, p), base);
    serifText([['100 米', G.gold], [' · 三十多层楼', G.ink]], 540, 480, { size: 56, weight: 900, a: easeOut(clamp((t - 22.6) / 0.3)) });
    withAlpha(easeOut(clamp((t - 22.6) / 0.3)), () => { ctx.setLineDash([8, 8]); ctx.strokeStyle = G.goldA + '0.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(380, top); ctx.lineTo(880, top); ctx.stroke(); ctx.setLineDash([]); });
  }));
  chapter(vis(t, 21.05, 23.95), '第 20', ' 次', '约 105 米', easeOut((t - 21.05) / 0.6));
}
function sceneSpace(t) {
  const a = vis(t, 23.95, 28.05);
  if (a <= 0.01) return;
  withAlpha(a, () => zoom(540, 1300, 1.08 - 0.08 * easeOut((t - 23.95) / 0.9), () => {
    // 大地弧线 + 大气层
    const R = 2600, cy = 1500 + R;
    const g = ctx.createRadialGradient(540, cy, R - 10, 540, cy, R + 260);
    g.addColorStop(0, 'rgba(120,170,220,0.35)'); g.addColorStop(1, 'rgba(120,170,220,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(540, cy, R + 260, 0, 6.283); ctx.fill();
    earth(540, cy, R);
    // 卡门线
    const ky = 820;
    ctx.save(); ctx.setLineDash([14, 12]); ctx.strokeStyle = 'rgba(160,200,235,0.6)'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.moveTo(60, ky); ctx.lineTo(1020, ky); ctx.stroke(); ctx.restore();
    serifText('太空边界 · 100 公里', 1020, ky - 22, { size: 40, weight: 700, color: 'rgba(200,225,245,0.9)', align: 'right' });
    const p = 1 - Math.pow(1 - clamp((t - 24.05) / 1.8), 2.2);
    column(540, lerp(1495, 640, p), 1500);
    // 穿过时的光圈
    const hit = clamp((t - 24.05 - 1.25) / 0.7);
    if (hit > 0 && hit < 1) { ctx.save(); ctx.strokeStyle = `rgba(200,225,245,${(1 - hit) * 0.8})`; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(540, ky, 40 + 260 * hit, 10 + 40 * hit, 0, 0, 6.283); ctx.stroke(); ctx.restore(); }
  }));
  bgWord('107 km', 700, 200, a * 0.8);
  chapter(vis(t, 24.0, 28.05), '第 30', ' 次', '约 107 公里', easeOut((t - 24.0) / 0.6));
}
function sceneSun(t) {
  const a = vis(t, 31.8, 34.35);
  if (a <= 0.01) return;
  withAlpha(a, () => zoom(540, 960, 1.1 - 0.1 * easeOut((t - 31.8) / 1.2), () => {
    sun(840, 60, 280, t);
    earth(700, 1560, 16);
    moon(760, 1500, 7);
    const p = 1 - Math.pow(1 - clamp((t - 31.95) / 1.5), 2.2);
    column(700, lerp(1540, 360, p), 1545, 12);
    milestone(700, 1490, '月球', '第 42 次', 0.8);
    const sa = easeOut(clamp((t - 33.3) / 0.3));
    milestone(700, 380, '太阳', '第 51 次', sa);
    serifText([['日地距离 ', G.ink], ['1.5 亿公里', G.gold]], 420, 760, { size: 50, weight: 900, a: sa });
  }));
  chapter(vis(t, 31.85, 34.35), '第 51', ' 次', '约 2.25 亿公里', easeOut((t - 31.85) / 0.6));
}

// ================= 场景：为什么？加一层 vs 翻一倍（34.3–38.75），指数曲线（38.7–46.65）
function sceneWhy(t) {
  const a = vis(t, 34.3, 38.75);
  if (a <= 0.01) return;
  withAlpha(a, () => {
    bgWord('?', 900, 700, vis(t, 34.3, 36.7));
    const q = easeOut(clamp((t - 35.5) / 0.35));
    if (t < 36.7) zoom(540, 860, 0.8 + 0.2 * q, () => serifText('×2', 540, 930, { size: 260, weight: 900, color: G.gold, a: q * (1 - P(t, 36.5, 0.2)), glow: 0.7 }));
    // 两张对比卡
    const cards = [[60, '加一层', '+0.1 mm', 36.75, false], [560, '翻一倍', '× 2', 37.7, true]];
    for (const [x, name, op, s, dbl] of cards) {
      const ca = easeOut(clamp((t - s) / 0.35));
      if (ca <= 0.01) continue;
      withAlpha(ca, () => {
        ctx.fillStyle = 'rgba(20,15,10,0.85)'; ctx.strokeStyle = dbl ? G.gold : G.goldA + '0.45)'; ctx.lineWidth = dbl ? 3 : 2;
        if (dbl) { ctx.shadowColor = G.goldA + '0.6)'; ctx.shadowBlur = 24; }
        ctx.beginPath(); ctx.roundRect(x, 470, 460, 760, 18); ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0;
        // 柱状：8 根
        for (let i = 0; i < 8; i++) {
          const v = dbl ? Math.pow(2, i) / 128 : (i + 1) / 8 * 0.06 + 0.01;
          const hb = 560 * v * easeOut(clamp((t - s - 0.05 - i * 0.035) / 0.25));
          ctx.fillStyle = dbl ? (i === 7 ? G.gold : G.goldA + '0.7)') : 'rgba(237,227,210,0.55)';
          ctx.fillRect(x + 40 + i * 50, 1150 - hb, 34, hb);
        }
      });
      serifText(name, x + 230, 560, { size: 64, weight: 900, color: dbl ? G.gold : G.ink, a: ca });
      serifText(op, x + 230, 630, { size: 40, weight: 600, color: G.ink, a: ca });
    }
  });
}
function sceneCurve(t) {
  const a = vis(t, 38.7, 46.65);
  if (a <= 0.01) return;
  const shake = t > 44.6 && t < 45.4 ? 4 * Math.sin(t * 80) * (1 - (t - 44.6) / 0.8) : 0;
  withAlpha(a, () => {
    ctx.translate(shake, 0);
    const x0 = 140, x1 = 960, y0 = 1350, yTop = 520;
    // 坐标轴
    ctx.strokeStyle = G.goldA + '0.5)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x0, yTop - 40); ctx.lineTo(x0, y0); ctx.lineTo(x1 + 20, y0); ctx.stroke();
    for (let n = 0; n <= 42; n += 6) { const x = lerp(x0, x1, n / 42); ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y0 + 12); ctx.stroke(); serifText(String(n), x, y0 + 52, { size: 30, weight: 600, color: G.ink }); }
    serifText('对折次数', x1, y0 + 100, { size: 34, weight: 600, color: G.goldA + '0.9)', align: 'right' });
    serifText('厚度', x0 + 14, yTop - 50, { size: 34, weight: 600, color: G.goldA + '0.9)', align: 'left' });
    // 指数曲线：画到 reveal 处；43.8 之后最后一段冲出画面顶部
    const reveal = 0.2 + 0.68 * easeOut(clamp((t - 38.9) / 4.6)) + 0.12 * easeOut(clamp((t - 43.85) / 1.0));
    const yOf = n => y0 - (y0 - yTop) * Math.pow(2, n - 42) * 1.7;
    glowStroke(() => {
      for (let i = 0; i <= 420; i++) {
        const n = i / 10; if (n / 42 > reveal) break;
        const x = lerp(x0, x1, n / 42), y = Math.max(-200, yOf(n));
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
    }, { w: 4, color: G.gold, blur: 20 });
    // 放大镜：前段几乎贴着地面
    const ma = vis(t, 39.3, 43.9);
    withAlpha(ma, () => {
      ctx.strokeStyle = G.gold; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(330, y0 - 6, 120, 0, 6.283); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(330 + 85, y0 - 6 - 85); ctx.lineTo(330 + 150, y0 - 6 - 150); ctx.lineWidth = 8; ctx.stroke();
    });
    serifText('0.1 → 0.2 mm', 330, y0 - 260, { size: 46, weight: 900, color: G.ink, a: ma });
    serifText('看不出来', 330, y0 - 200, { size: 36, weight: 600, color: G.goldA + '0.9)', a: vis(t, 42.25, 43.9) });
    // 末端冲顶
    const ea = easeOut(clamp((t - 44.4) / 0.35));
    serifText('几十万公里', 760, 500, { size: 72, weight: 900, color: G.gold, a: ea, glow: 0.6 });
    if (ea > 0) node(lerp(x0, x1, 41.4 / 42), Math.max(380, yOf(41.4)), 10, ea);
  });
  chapter(vis(t, 38.75, 46.65), '2⁴²', '', '每一次，都翻一倍', easeOut((t - 38.75) / 0.6));
}

// ================= 场景：现实里谁能折 42 次（46.6–60.1）
function sceneReal(t) {
  const a1 = vis(t, 46.6, 49.95);
  withAlpha(a1, () => {
    bgWord('42', 1000, 620, 1);
    zoom(540, 900, 0.9 + 0.1 * easeOut((t - 46.6) / 0.6), () => serifText('42 次？', 540, 960, { size: 180, weight: 900, color: G.ink, glow: 0.4 }));
    const sa = easeOut(clamp((t - 48.95) / 0.18));
    zoom(700, 1200, 1.4 - 0.4 * sa, () => stamp(700, 1200, '没人能', sa));
  });
  const a2 = vis(t, 49.95, 56.15);
  withAlpha(a2, () => {
    // 长长的一卷纸：从左下延伸到右上，飘出画面
    const p = easeOut(clamp((t - 52.35) / 1.4));
    const pts = []; for (let i = 0; i <= 60; i++) { const k = i / 60; pts.push([lerp(-80, 1180, k), 1250 - 520 * k + 60 * Math.sin(k * 6 + t * 0.6)]); }
    ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.lineWidth = 60; ctx.beginPath(); polyPartial(pts.map(([x, y]) => [x + 10, y + 30]), p); ctx.stroke();
    const g = ctx.createLinearGradient(0, 700, 0, 1300); g.addColorStop(0, '#F3EAD8'); g.addColorStop(1, '#BFB29A');
    ctx.strokeStyle = g; ctx.lineWidth = 46; ctx.beginPath(); polyPartial(pts, p); ctx.stroke();
    ctx.strokeStyle = 'rgba(120,105,85,0.5)'; ctx.lineWidth = 2; ctx.setLineDash([3, 14]); ctx.beginPath(); polyPartial(pts, p); ctx.stroke();
    ctx.restore();
    serifText([['约 ', G.ink], ['1.2 公里', G.gold], [' 长', G.ink]], 360, 1340, { size: 54, weight: 900, a: easeOut(clamp((t - 53.4) / 0.3)) });
    // 12 次
    const ca = easeOut(clamp((t - 54.4) / 0.3));
    zoom(700, 600, 1.25 - 0.25 * ca, () => serifText([['12', G.gold], [' 次', G.ink]], 700, 640, { size: 170, weight: 900, a: ca, glow: 0.5 }));
  });
  chapter(vis(t, 49.95, 56.15), '2002', '', '美国 · 高中生 布兰妮·加利文', easeOut((t - 49.95) / 0.6));
  const a3 = vis(t, 56.1, 60.12);
  withAlpha(a3, () => {
    floorLine(1);
    // 越折越厚、越折越短：k 从 1 到 12
    const k = 1 + 11 * easeOut(clamp((t - 56.2) / 2.6));
    const w = 900 / Math.pow(2, (k - 1) * 0.38), h = 20 * Math.pow(2, (k - 1) * 0.38);
    const st = paperStack(540, 1400, w, 120, Math.min(h, 700), Math.round(k * 3));
    serifText(`第 ${Math.round(k)} 次`, 540, 560, { size: 64, weight: 900, color: G.gold });
    serifText('越厚 ↑', st.x1 + 40, st.top + 40, { size: 50, weight: 900, color: G.gold, a: P(t, 56.4, 0.3), align: 'left' });
    serifText('越短 ←→', 540, 1480, { size: 50, weight: 900, color: G.gold, a: P(t, 57.3, 0.3) });
    const sa = easeOut(clamp((t - 58.55) / 0.18));
    zoom(540, 760, 1.4 - 0.4 * sa, () => stamp(540, 760, '折不动', sa, 0.08, 80));
  });
}

// ================= 场景：结尾（60.1–73.9）
function sceneEnd(t) {
  // 60.1–62.8：一张纸慢慢淡去
  const a0 = vis(t, 60.08, 62.9);
  withAlpha(a0, () => {
    floorLine(1);
    const cam = makeCam(540, 960 + 8 * Math.sin(t), -0.5 + 0.1 * Math.sin(t * 0.4), 0.42, 1);
    withAlpha(1 - P(t, 61.9, 0.9), () => paper3d(cam, 260, 190, 0));
    serifText('不是纸', 540, 600, { size: 90, weight: 900, color: G.ink, a: easeOut(clamp((t - 61.85) / 0.3)) });
  });
  // 62.7–73.9：一条"人生曲线"——前段几乎平，后段陡升
  const a = vis(t, 62.75, 73.95);
  withAlpha(a, () => {
    const x0 = 120, x1 = 960, y0 = 1280;
    const yOf = k => y0 - 820 * Math.pow(k, 7);
    ctx.strokeStyle = G.goldA + '0.3)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1 + 30, y0); ctx.stroke();
    const flat = 0.15 + 0.6 * easeOut(clamp((t - 62.9) / 7.8));
    const rise = easeOut(clamp((t - 70.8) / 2.0));
    const reveal = flat + 0.25 * rise;
    glowStroke(() => { for (let i = 0; i <= 200; i++) { const k = i / 200; if (k > reveal) break; const x = lerp(x0, x1, k), y = yOf(k); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } }, { w: 4, color: G.gold, blur: rise > 0 ? 26 : 12 });
    // 光点在曲线上慢慢走
    const kk = reveal; node(lerp(x0, x1, kk), yOf(kk), 9, 1);
    // 年份刻度
    for (let i = 1; i <= 8; i++) { const x = lerp(x0, x1, i / 9); serifText(`第 ${i} 年`, x, y0 + 50, { size: 26, weight: 600, color: G.ink, a: 0.6 * easeOut(clamp((t - 63.2 - i * 0.2) / 0.3)) }); }
    // 攒钱 / 手艺 图标
    const ia = vis(t, 65.3, 70.8);
    withAlpha(ia, () => {
      ctx.strokeStyle = G.gold; ctx.lineWidth = 3; ctx.fillStyle = 'rgba(30,22,15,0.9)';
      for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.ellipse(300, 860 - i * 22, 60, 16, 0, 0, 6.283); ctx.fill(); ctx.stroke(); }
      ctx.save(); ctx.translate(760, 820); ctx.rotate(-0.6);
      ctx.beginPath(); ctx.roundRect(-10, -20, 20, 140, 8); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.roundRect(-55, -60, 110, 44, 8); ctx.fill(); ctx.stroke(); ctx.restore();
    });
    serifText('攒钱', 300, 960, { size: 40, weight: 700, color: G.ink, a: ia });
    serifText('学手艺', 760, 960, { size: 40, weight: 700, color: G.ink, a: ia });
    serifText('0.1 毫米', lerp(x0, x1, 0.35), y0 - 60, { size: 46, weight: 900, color: G.gold, a: vis(t, 67.0, 70.8) });
    // 后半段括号
    const ba = easeOut(clamp((t - 71.8) / 0.4));
    withAlpha(ba, () => {
      ctx.strokeStyle = G.gold; ctx.lineWidth = 3; ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 14;
      ctx.beginPath(); ctx.moveTo(lerp(x0, x1, 0.72), y0 + 100); ctx.lineTo(lerp(x0, x1, 0.72), y0 + 120); ctx.lineTo(x1, y0 + 120); ctx.lineTo(x1, y0 + 100); ctx.stroke();
    });
    serifText('后半段', lerp(x0, x1, 0.86), y0 + 180, { size: 52, weight: 900, color: G.gold, a: ba, glow: 0.5 });
  });
}

window.draw = function (t) {
  background(t, { cx: 540, cy: 900, glow: 0.95 });
  bokeh(t);
  bgWord('42', 640, 520, vis(t, -1, 3.75));
  bgWord('?', 640, 520, vis(t, 3.8, 6.95));
  bgWord('0.1 mm', 640, 230, vis(t, 9.1, 12.75));
  bgWord('0.2 mm', 640, 230, vis(t, 12.75, 13.45));
  sceneSheet(t);
  sceneMoon(t, 6.95, 9.1, true);
  sceneStack(t);
  sceneBuilding(t);
  sceneSpace(t);
  sceneMoon(t, 28.0, 31.85, false);
  if (t > 28.0 && t < 31.85) chapter(vis(t, 28.05, 31.85), '第 42', ' 次', '约 44 万公里', easeOut((t - 28.05) / 0.6));
  sceneSun(t);
  sceneWhy(t);
  sceneCurve(t);
  sceneReal(t);
  sceneEnd(t);
  subtitles(t, SUBS);
  // 片尾 0.6s 淡出
  const out = P(t, DUR - 0.6, 0.6);
  if (out > 0) { ctx.fillStyle = `rgba(0,0,0,${out})`; ctx.fillRect(0, 0, W, H); }
  finish(t);
};
