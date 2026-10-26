// 「家务百分比」· 白板讲解风格试片。一整块白板，没有手；镜头在板上走，不切。
// 配音是用户自己的 MiniMax 录音（voice/vo.wav），时间点来自《大脑的账本》的对齐结果。
import * as W from './engine/wb.js';
import { clamp, mulberry } from '/core/lib.js';
const { INK } = W;
const END = 31.0;
// 配音小句（秒）
const SUBS = [
  [0.24, 2.21, '在心里估一下：家里的家务，'], [2.41, 4.82, '或者上次的小组作业，你干了百分之几？'], [5.27, 6.13, '记住这个数。'],
  [6.37, 8.21, '经典研究就这么问过夫妻：'], [8.21, 11.28, '俩人各报各的，加起来，比一整份还多。'], [11.52, 12.52, '不是谁在撒谎。'],
  [12.80, 14.54, '是你干的每一件，你都在场；'], [14.81, 16.87, '对方干的，你很多根本没看见。'],
  [17.13, 19.42, '现在挨个想想，对方具体干了什么：'], [19.67, 22.10, '做的饭、倒的垃圾、交的水电费'],
  [22.52, 23.18, '再估一次'], [23.55, 24.92, '是不是想往下调一点了？'], [25.16, 27.12, '研究里，先想别人、再估自己，'], [27.34, 28.26, '高估就会变少。'],
];

export async function build() {
  await W.loadFont('tech', 'fonts/EMSTech.json');
  const HZ = await (await fetch('fonts/hanzi.json')).json();
  // 中文：按 Make Me a Hanzi 的笔画中线、真实笔顺一笔一笔写；数字和符号用 EMS Tech 单线字
  function hz(str, x, y, o = {}) {
    const h = o.h ?? 120, sp = o.spacing ?? 1.04, R = mulberry(o.seed ?? (x * 7 + y * 13 | 0));
    const items = [...str].map(ch => HZ[ch] ? { ch, w: h * sp } : { ch, w: (ch === ' ' ? .35 : .62) * h * sp });
    const total = items.reduce((a, b) => a + b.w, 0);
    let cx = o.align === 'center' ? x - total / 2 : o.align === 'right' ? x - total : x;
    const out = [];
    for (const it of items) {
      if (HZ[it.ch]) {
        const k = h / 1024 * (1 + (R() - .5) * .05), rot = (R() - .5) * .05, dy = (R() - .5) * h * .05, ox = cx + it.w / 2, oy = y - h / 2 + dy;
        for (const m of HZ[it.ch]) {
          const p = [];
          for (const [mx, my] of m) { const px = (mx - 512) * k, py = (900 - my - 512) * k; p.push(ox + px * Math.cos(rot) - py * Math.sin(rot), oy + px * Math.sin(rot) + py * Math.cos(rot)); }
          if (p.length === 2) p.push(p[0] + 1, p[1] + 1);
          out.push(new W.Stroke(p, { w: o.w ?? Math.max(6, h * .085), color: o.color, jitter: .3, wav: 90, kind: 'text', smooth: 1, alpha: o.alpha }));
        }
      } else if (it.ch !== ' ') out.push(...W.text(it.ch, cx + it.w / 2, y - h * .1, { h: h * .78, align: 'center', color: o.color, w: o.w ?? Math.max(6, h * .085) }));
      cx += it.w;
    }
    out.width = total; return out;
  }

  const tl = new W.Timeline();
  const K = new W.Pen('black', INK.black, { park: [2200, 1320] });
  const O = new W.Pen('orange', INK.orange, { park: [2350, 1150] });
  const B = new W.Pen('blue', INK.blue, { park: [2100, 1420] });

  // ───────── 白板上早就有的淡色旧痕：别的课留下的，和“对方干的”那三件
  const GHOST = '#a3a9b1';
  const ghosts = [];
  const ghost = (strokes, a = .1, col = GHOST) => { for (const s of strokes.flat ? strokes.flat() : [strokes]) { s.color = col; s.alpha = a; ghosts.push(s); } };
  const OTHER = [['做饭', 1100], ['倒垃圾', 1300], ['交水电费', 1500]];
  for (const [w, y] of OTHER) ghost(hz(w, 5450, y, { h: 100, seed: y }), .11);
  ghost(W.circle(1900, 2400, 160), .07, '#9fb3d1'); ghost(W.arrow(2300, 2500, 2900, 2300), .06);
  ghost(hz('先想', 5200, 2500, { h: 90, seed: 3 }), .05); ghost(W.rect(400, 2300, 700, 300), .05, '#9fb3d1');
  ghost(W.curve([[3800, 2300], [4200, 2150], [4600, 2420], [5000, 2250]]), .06);

  // ───────── R1：你的数（0–6.4）
  tl.draw(K, hz('家务', 560, 980, { h: 110 }), 0.25, { by: 1.4 });
  tl.draw(K, [W.line(470, 850, 420, 1000, { w: 8 }), W.line(400, 1000, 470, 1010, { w: 8 })], 1.45, { by: 1.75 });   // 小扫帚
  tl.draw(K, hz('小组作业', 1150, 980, { h: 110 }), 2.41, { by: 3.6 });
  tl.draw(K, hz('我干了', 520, 1420, { h: 170 }), 3.7, { by: 4.55 });
  tl.draw(K, W.line(1080, 1440, 1600, 1440, { w: 9 }), 4.55, { by: 4.8 });
  tl.draw(O, hz('70%', 1340, 1400, { h: 200, align: 'center' }), 5.27, { by: 5.95 });
  const ring70 = W.circle(1340, 1320, 190, { ry: 130, w: 9, lap: .5, a0: -2.6 });
  tl.draw(O, ring70, 5.97, { by: 6.35 });
  // 笔带镜头：从 70% 拉一条线到 R2
  tl.draw(K, W.curve([[1640, 1360], [2000, 1280], [2350, 1360]], { w: 8 }), 6.45, { by: 7.6 });
  tl.draw(K, hz('1979', 2380, 1100, { h: 80 }), 7.7, { by: 8.2 });

  // ───────── R2：夫妻自评（8.2–11.4）
  const BX = 2500, BY = 1260, BW = 1200, BH = 200;
  tl.draw(K, W.rect(BX, BY, BW, BH, { w: 9 }), 8.3, { by: 8.95 });
  tl.draw(K, hz('一整份', BX + BW / 2, BY - 50, { h: 90, align: 'center' }), 8.95, { by: 9.5 });
  const hb = BX + BW * .62;
  tl.draw(K, W.hatch([[BX + 10, BY + 15], [hb, BY + 15], [hb, BY + BH - 15], [BX + 10, BY + BH - 15]], { w: 9, spacing: 30, alpha: .7 }), 9.5, { by: 10.0 });
  tl.draw(K, hz('丈夫', (BX + hb) / 2, BY + BH + 130, { h: 80, align: 'center' }), 10.0, { by: 10.3 });
  const we = hb + BW * .58;
  tl.draw(B, W.hatch([[hb + 6, BY + 15], [we, BY + 15], [we, BY + BH - 15], [hb + 6, BY + BH - 15]], { w: 9, spacing: 30, alpha: .7 }), 10.0, { by: 10.65 });
  tl.draw(B, hz('妻子', (hb + we) / 2, BY + BH + 130, { h: 80, align: 'center' }), 10.65, { by: 10.95 });
  tl.draw(O, W.hatch([[BX + BW + 4, BY - 10], [we + 20, BY - 10], [we + 20, BY + BH + 10], [BX + BW + 4, BY + BH + 10]], { w: 10, spacing: 22, alpha: .75, angle: .7 }), 10.7, { by: 11.05 });
  tl.draw(O, hz('超出', we + 170, BY + 130, { h: 90 }), 11.05, { by: 11.35 });
  // 撒谎？（R2 上方）
  tl.draw(K, hz('撒谎？', 3100, 760, { h: 130, align: 'center' }), 11.6, { by: 12.25 });
  tl.draw(O, [W.line(2860, 600, 3330, 790, { w: 10 }), W.line(3330, 600, 2860, 790, { w: 10 })], 12.3, { by: 12.65 });

  // ───────── R3：你在场 vs 对方干的（12.8–22.2）
  tl.draw(K, hz('你在场', 4540, 830, { h: 120 }), 12.95, { by: 13.75 });
  [['洗碗', 1100], ['拖地', 1300], ['洗衣服', 1500]].forEach(([w, y], i) => tl.draw(K, hz(w, 4560, y, { h: 100 }), 13.8 + i * .32, { by: 14.08 + i * .32 }));
  tl.draw(B, hz('对方干的', 5450, 830, { h: 120 }), 14.85, { by: 15.75 });
  tl.draw(B, W.dashed([[5380, 960], [6120, 960], [6120, 1590], [5380, 1590], [5380, 960]], { w: 6 }), 15.9, { by: 16.8 });
  // 描旧痕：同样的位置、同样的笔画
  const tr = [[19.67, 20.35], [20.4, 21.15], [21.2, 22.1]];
  OTHER.forEach(([w, y], i) => tl.draw(B, hz(w, 5450, y, { h: 100, seed: y }), tr[i][0], { by: tr[i][1] }));

  // ───────── 回到 R1：擦掉 70%，写 55%（22.5–25.1）
  tl.erase(W.zigzag(1120, 1160, 470, 330, 6), 22.95, .55, { width: 150, strength: .9 });
  tl.draw(O, hz('55%', 1340, 1400, { h: 200, align: 'center' }), 23.6, { by: 24.35 });
  tl.draw(O, W.arrow(1700, 1180, 1700, 1420, { w: 9, head: 40 }), 24.4, { by: 24.85 });

  // ───────── 全板：一句话总结（25.1–31）
  tl.draw(K, hz('先想别人', 1500, 420, { h: 150, align: 'center' }), 25.4, { by: 26.3 });
  tl.draw(K, W.arrow(2220, 380, 2620, 380, { w: 10, head: 46 }), 26.32, { by: 26.6 });
  tl.draw(K, hz('再估自己', 3300, 420, { h: 150, align: 'center' }), 26.65, { by: 27.3 });
  tl.draw(K, W.arrow(4020, 380, 4420, 380, { w: 10, head: 46 }), 27.32, { by: 27.55 });
  tl.draw(O, hz('高估↓', 5000, 420, { h: 150, align: 'center' }), 27.6, { by: 28.25 });
  tl.draw(O, [W.circle(5000, 360, 300, { ry: 140, w: 10, lap: .3 }), W.circle(5010, 355, 320, { ry: 152, w: 9, a0: -2.0, lap: .1 })], 28.35, { by: 29.1 });
  tl.end();

  // ───────── 镜头（世界坐标中心 x, y, 缩放）
  const cam = new W.Camera([
    [0, 980, 1150, 1.1], [4.6, 1000, 1180, 1.16, 0, 'l'], [5.25, 1180, 1260, 1.35, 0, 'io'], [6.4, 1190, 1260, 1.35, 0, 'l'],
    [8.0, 3250, 1300, .85, 0, 'io'],                       // 骑着线到 R2
    [11.3, 3260, 1310, .86, 0, 'l'], [11.6, 3100, 800, 1.2, 0, 'io'],    // 甩到“撒谎？”
    [12.7, 3100, 800, 1.2, 0, 'l'], [13.5, 5150, 1180, .95, 0, 'io'],   // 横移到 R3
    [15.0, 5180, 1180, .95, 0, 'l'], [17.0, 5260, 1220, 1.02, 0, 'io'], [22.2, 5280, 1230, 1.05, 0, 'l'],
    [22.75, 1180, 1250, 1.35, 0, 'io'],                     // 甩回 R1
    [25.1, 1190, 1250, 1.35, 0, 'l'], [27.4, 3200, 1350, .33, 0, 'io'], [31, 3200, 1360, .32, 0, 'l'],
  ]);

  const board = new W.Board(tl, { W: 6400, H: 3000, ghosts });
  for (const P of [K, O, B]) board.objs.push({ draw: (ctx, t, c) => W.drawMarker(ctx, P, W.penPose(P, t, cam), c, t) });
  board.objs.push({ draw: (ctx, t, c) => { for (const e of tl.erasers) W.drawEraser(ctx, e, t, c); } });
  // 字幕：米白圆角标签 + 橙色短横
  const subs = SUBS.map(([t0, t1, text]) => ({ t0, t1: Math.max(t1 + .6, t0 + 1.8), text }));
  for (let i = 0; i < subs.length - 1; i++) subs[i].t1 = Math.min(subs[i].t1, subs[i + 1].t0 - .02);
  board.overlays.push({ draw: (ctx, t) => {
    const s = subs.find(s => t >= s.t0 && t < s.t1); if (!s) return;
    const a = Math.min(1, (t - s.t0) / .12, (s.t1 - t) / .12);
    ctx.font = '44px SUB'; const w = ctx.measureText(s.text).width + 72, h = 74, y0 = 1036 - h;
    ctx.globalAlpha = a * .9; ctx.fillStyle = '#fdfcf8'; ctx.shadowColor = 'rgba(30,30,40,.18)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 4;
    ctx.beginPath(); ctx.roundRect(960 - w / 2, y0, w, h, 14); ctx.fill();
    ctx.shadowColor = 'transparent'; ctx.globalAlpha = a; ctx.fillStyle = INK.orange; ctx.fillRect(960 - w / 2 + 22, y0 + h - 12, 36, 4);
    ctx.fillStyle = '#23262c'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(s.text, 960, y0 + h / 2 + 2);
  } });

  // 甩镜时的运动模糊（180° 快门，子帧间隔 ≤ 4px）
  const off = new OffscreenCanvas(1920, 1080), oc = off.getContext('2d');
  function render(ctx, t) {
    const dt = 1 / 24, a = cam.at(t), b = cam.at(Math.max(0, t - dt));
    const sp = Math.hypot((a.x - b.x) * a.z, (a.y - b.y) * a.z) + Math.abs(Math.log(a.z / b.z)) * 900;
    const N = sp > 14 ? Math.min(12, Math.ceil(sp * .5 / 4)) : 1;
    if (N === 1) { board.render(ctx, t, cam); return; }
    const ov = board.overlays; board.overlays = [];
    for (let i = 0; i < N; i++) { board.render(oc, t - dt * .5 * i / (N - 1), cam); ctx.globalAlpha = 1 / (i + 1); ctx.drawImage(off, 0, 0); }
    ctx.globalAlpha = 1; board.overlays = ov; for (const o of ov) { ctx.save(); o.draw(ctx, t); ctx.restore(); }
  }
  const ev = [...tl.ev, { t: 0, type: 'vo', file: 'voice/vo.wav' }, { t: 11.2, type: 'silence', dur: .65 }, { t: 22.3, type: 'silence', dur: .55 },
    { t: 11.35, type: 'whip' }, { t: 22.3, type: 'whip' }, { t: 29.6, type: 'capon' }].sort((a, b) => a.t - b.t);
  for (const e of ev) if (e.x != null) { const c = cam.at(e.t), [px] = W.toScreen(c, e.x, e.y); e.pan = +clamp((px - 960) / 1400, -.7, .7).toFixed(2); e.z = +c.z.toFixed(2); }
  return { dur: END, render, ev, subs };
}
