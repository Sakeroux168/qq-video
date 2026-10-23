// 开头 20.47 秒样片（对应配音 0:00–0:20.47）
// 台词时间来自配音的停顿检测：
//  0.56–2.74 微波炉热的饭，到底有没有辐射？  3.25–4.67 你家是不是也有这么一位
//  5.19–6.17 微波炉一转  6.39–7.29 他转身就跑  7.58–11.79 躲在厨房门口探头探脑，非得等"叮"一声才敢回来
// 12.28–13.60 你跟他讲科学  14.00–15.86 他让你喝碗丝瓜汤降降火  16.38–18.95 行，今天咱就当一回赌神
// 19.37–20.02 我要验牌！
const DING = 10.25;

// 线描微波炉（以中心 cx,cy、缩放 s 绘制）；p: 描线进度；on: 波纹强度；flash: 叮的一下高亮
function microwave(t, cx, cy, s, p, on, flash) {
  const w = 560 * s, h = 340 * s, x0 = cx - w / 2, y0 = cy - h / 2;
  const outline = [[x0 + 30 * s, y0], [x0 + w - 30 * s, y0], [x0 + w, y0 + 30 * s], [x0 + w, y0 + h - 30 * s], [x0 + w - 30 * s, y0 + h], [x0 + 30 * s, y0 + h], [x0, y0 + h - 30 * s], [x0, y0 + 30 * s], [x0 + 30 * s, y0]];
  const a = 0.85 + 0.6 * flash;
  glowStroke(() => polyPartial(outline, p), { w: 3.2, a: Math.min(1, a), blur: 22 + 40 * flash });
  const wx = x0 + 34 * s, wy = y0 + 34 * s, ww = w * 0.68, wh = h - 68 * s;
  const win = [[wx, wy], [wx + ww, wy], [wx + ww, wy + wh], [wx, wy + wh], [wx, wy]];
  glowStroke(() => polyPartial(win, clamp(p * 1.3 - 0.3)), { w: 2, a: 0.6 + 0.4 * flash, blur: 14 });
  const px = wx + ww + 40 * s;
  glowStroke(() => { ctx.moveTo(px, y0 + 20 * s); ctx.lineTo(px, y0 + h - 20 * s); }, { w: 1.6, a: 0.5 * clamp(p * 2 - 1) });
  for (const k of [0.38, 0.66]) {
    const r = 22 * s, kx = (px + x0 + w) / 2, ky = y0 + h * k;
    glowStroke(() => ctx.arc(kx, ky, r, -Math.PI / 2, -Math.PI / 2 + 6.283 * clamp(p * 1.5 - 0.5)), { w: 1.8, a: 0.7 });
  }
  // 炉内波纹（第一帧就在）
  {
    ctx.save(); ctx.beginPath(); ctx.rect(wx + 4, wy + 4, ww - 8, wh - 8); ctx.clip();
    if (on > 0.01) for (let j = 0; j < 2; j++) {
      const yy = wy + wh * (0.38 + 0.28 * j);
      glowStroke(() => {
        for (let x = wx; x <= wx + ww; x += 4) {
          const y = yy + 16 * s * on * Math.sin((x - wx) / (46 * s) - t * 6 - j * 1.7);
          x === wx ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
      }, { w: 2.6, a: 0.9 * on, color: COL.gold, blur: 18 });
    }
    // 碗（简笔）
    const bx = wx + ww / 2, by = wy + wh * 0.86;
    glowStroke(() => { ctx.ellipse(bx, by - 18 * s, 70 * s, 34 * s, 0, Math.PI, 0); }, { w: 2, a: 0.6 * on + 0.3 });
    glowStroke(() => { ctx.moveTo(bx - 82 * s, by - 18 * s); ctx.quadraticCurveTo(bx, by + 46 * s, bx + 82 * s, by - 18 * s); }, { w: 2, a: 0.8 });
    ctx.restore();
  }
  return { wx, wy, ww, wh, x0, y0, w, h };
}

window.draw = function (t) {
  // 相机：3.1s 起微波炉缩小右移
  const m = P(t, 3.1, 0.9);
  const sceneA = 1 - P(t, 11.95, 0.4);
  background(t, { cx: lerp(540, 680, m), cy: 900, glow: 1 + 0.6 * Math.exp(-Math.pow((t - DING) / 0.25, 2)) });

  // ---------------- 场景 A：厨房（0–12.3s）
  if (sceneA > 0.001) {
    ctx.save(); ctx.globalAlpha = sceneA;
    const on = 1 - P(t, DING, 0.12);
    const flash = Math.exp(-Math.pow((t - DING - 0.05) / 0.18, 2));
    const cx = lerp(540, 700, m), cy = lerp(880, 930, m), s = lerp(1.05, 0.78, m);
    microwave(t, cx, cy, s, 1, on, flash);
    // 叮：扩散光圈 + 大字
    if (t > DING - 0.05) {
      const q = clamp((t - DING) / 1.1);
      glowStroke(() => ctx.arc(cx, cy, 160 + 300 * easeOut(q), 0, 6.283), { w: 2, a: (1 - q) * 0.7, blur: 30 });
      const pin = easeOut(clamp((t - DING) / 0.25)), pout = 1 - P(t, 11.6, 0.4);
      serifText('叮', cx, cy - 240, { size: 170, weight: 900, a: pin * pout, glow: 0.9, blur: (1 - pin) * 12 });
    }
    // 门框：左侧一根竖直发光线
    const dx = 250, dp = P(t, 3.2, 0.8);
    glowStroke(() => polyPartial([[dx + 70, 560], [dx, 560], [dx, 1360]], dp), { w: 3, a: 0.9 });
    serifText('厨房门', dx - 20, 540, { size: 42, color: COL.dim, a: P(t, 3.8, 0.4), align: 'right', weight: 600 });
    // "他"：一个发光的点
    if (t > 3.4) {
      let x = 470, y = 1180;
      const run = P(t, 6.4, 0.75);                         // 转身就跑
      x = lerp(470, 150, run);
      if (t > 7.6 && t < 10.0) {                           // 探头探脑
        const k = (t - 7.6) / 2.4;
        x = 150 + 105 * Math.max(0, Math.sin(k * Math.PI * 3)) ** 0.6;
      }
      const back = P(t, 10.75, 0.9);                       // 叮之后才敢回来
      x = lerp(x, 470, back);
      const a = P(t, 3.4, 0.4);
      // 跑动拖尾
      if (run > 0 && run < 1) for (let i = 1; i <= 6; i++) node(x + i * 22, y, 6 - i * 0.7, a * (0.5 - i * 0.07));
      if (back > 0 && back < 1) for (let i = 1; i <= 6; i++) node(x - i * 22, y, 6 - i * 0.7, a * (0.5 - i * 0.07));
      // 躲在门后时变暗
      const hidden = x < dx - 30 ? 0.45 : 1;
      node(x, y, 11, a * hidden);
      serifText('他', x, y - 40, { size: 48, a: a * hidden, color: COL.text, weight: 700 });
    }
    ctx.restore();
  }

  // ---------------- 场景 B：讲科学 → 丝瓜汤（12.1–16.4s）
  const sciA = P(t, 12.1, 0.4) * (1 - P(t, 13.85, 0.35));
  if (sciA > 0.001) {
    const y = 960, x0 = 140, x1 = 940;
    glowStroke(() => { ctx.moveTo(x0, y + 120); ctx.lineTo(x1, y + 120); }, { w: 2, a: 0.55 * sciA });
    for (let i = 0; i <= 8; i++) glowStroke(() => { const x = x0 + (x1 - x0) * i / 8; ctx.moveTo(x, y + 110); ctx.lineTo(x, y + 130); }, { w: 1.6, a: 0.45 * sciA });
    glowStroke(() => {
      let ph = 0;
      for (let x = x0; x <= x1; x += 3) {
        const f = 0.012 + 0.07 * ((x - x0) / (x1 - x0)) ** 2;
        ph += f * 3; const yy = y + 70 * Math.sin(ph - t * 4);
        x === x0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
      }
    }, { w: 2.6, a: sciA, color: COL.gold });
    serifText('电磁波谱', 540, y + 200, { size: 42, color: COL.dim, a: sciA });
  }
  const soupA = P(t, 13.9, 0.45) * (1 - P(t, 16.15, 0.3));
  if (soupA > 0.001) {
    const bx = 540, by = 1010, p = P(t, 13.9, 0.9);
    glowStroke(() => ctx.ellipse(bx, by, 260, 60, 0, 0, 6.283 * p), { w: 3, a: soupA });
    glowStroke(() => { ctx.moveTo(bx - 260, by); ctx.bezierCurveTo(bx - 240, by + 230, bx + 240, by + 230, bx + 260, by); }, { w: 3, a: soupA * clamp(p * 1.6 - 0.4) });
    // 汤面上的丝瓜片
    for (const [dx, dy, r] of [[-120, 8, 26], [-20, -12, 24], [90, 6, 28], [170, -6, 20]]) glowStroke(() => ctx.ellipse(bx + dx, by + dy, r, r * 0.42, 0, 0, 6.283), { w: 1.6, a: 0.7 * soupA * P(t, 14.5, 0.5), color: COL.gold, blur: 12 });
    // 热气
    for (let i = 0; i < 3; i++) glowStroke(() => {
      for (let k = 0; k <= 60; k++) {
        const yy = by - 70 - k * 4, xx = bx - 90 + i * 90 + 14 * Math.sin(k / 9 - t * 2.4 + i * 2);
        k === 0 ? ctx.moveTo(xx, yy) : ctx.lineTo(xx, yy);
      }
    }, { w: 2, a: 0.5 * soupA * P(t, 14.6, 0.6), blur: 14 });
    serifText('丝瓜汤', bx, by + 300, { size: 44, color: COL.dim, a: soupA * P(t, 14.8, 0.4) });
  }

  // ---------------- 场景 C：赌桌验牌（16.3–20.47s）
  const cardA = P(t, 16.3, 0.4);
  if (cardA > 0.001) {
    const hit = Math.exp(-Math.pow((t - 19.4) / 0.08, 2));
    const cx = 540 + 6 * hit * Math.sin(t * 90), cy = 930, w = 380, h = 540;
    const p = P(t, 16.35, 1.1);
    const r = 28, x0 = cx - w / 2, y0 = cy - h / 2;
    const pts = [[x0 + r, y0], [x0 + w - r, y0], [x0 + w, y0 + r], [x0 + w, y0 + h - r], [x0 + w - r, y0 + h], [x0 + r, y0 + h], [x0, y0 + h - r], [x0, y0 + r], [x0 + r, y0]];
    glowStroke(() => polyPartial(pts, p), { w: 3, a: cardA });
    const ip = P(t, 17.0, 0.8);
    glowStroke(() => ctx.rect(x0 + 26, y0 + 26, w - 52, h - 52), { w: 1.4, a: 0.45 * ip, color: COL.gold, blur: 10 });
    for (const [ax, ay] of [[x0 + 60, y0 + 70], [x0 + w - 60, y0 + h - 70]]) node(ax, ay, 4, 0.6 * ip);
    serifText('辐射？', cx, cy + 30, { size: 92, weight: 900, a: ip, blur: (1 - ip) * 10, glow: 0.5 });
    // 我要验牌：暗红大字
    if (t > 19.3) {
      const q = easeOut(clamp((t - 19.37) / 0.22));
      ctx.save(); ctx.translate(540, 1420); ctx.scale(1.25 - 0.25 * q, 1.25 - 0.25 * q);
      serifText('验牌', 0, 0, { size: 200, weight: 900, color: COL.red, a: q, glow: 0.85, glowColor: COL.redGlow, blur: (1 - q) * 16 });
      ctx.restore();
    }
  }

  // ---------------- 置顶字幕（衬线）+ 开场钩子
  caption(t, -1, 3.05, '微波炉热的饭，到底有没有辐射？');
  caption(t, 3.2, 5.05, '你家是不是也有这么一位：');
  caption(t, 5.15, 7.4, '微波炉一转，他转身就跑。');
  caption(t, 7.55, 9.9, '躲在厨房门口，探头探脑，');
  caption(t, 9.9, 12.0, '非得等「叮」一声才敢回来。');
  caption(t, 12.25, 13.85, '你跟他讲科学，');
  caption(t, 13.95, 16.2, '他让你喝碗丝瓜汤，降降火。');
  caption(t, 16.35, 19.25, '行，今天咱就当一回赌神：');
  caption(t, 19.35, 21, '我要验牌！');
  // 0–3s 中下方的钩子大字：第一帧就在
  const hookA = 1 - P(t, 2.7, 0.4);
  if (hookA > 0.001) {
    ctx.save(); ctx.translate(540, 1380); const sc = 1.06 - 0.06 * easeOut(t / 1.5); ctx.scale(sc, sc);
    serifText([['有', COL.text], ['辐射', COL.red], ['？', COL.text]], 0, 0, { size: 170, weight: 900, a: hookA, glow: 0.7, glowColor: COL.redGlow });
    ctx.restore();
  }
  finish(t);
};
