// 旁白人物「星星」：用 GPT 出的 12 张动作图做成动态立绘。
// 动作：入场/出场滑动、呼吸起伏、轻微摇摆、说话时嘴巴开合+身体微弹、眨眼、换动作时小跳一下（无回弹）、头顶反应符号。
// 姿势：talk（讲解，嘴会动）idle（讲解，闭嘴）happy point surprise thumb shrug think scared stick wave heart
// stick / wave / heart 三张原图脚被裁掉了，只在腿被前景挡住或人物贴画面底边时使用。

const ASSETS = (window.ASSETS = window.ASSETS || []);
function preload(url) {
  ASSETS.push(new Promise(r => { const i = new Image(); i.onload = r; i.onerror = r; i.src = url; }));
  return url;
}
const XPOSES = ['base', 'blink', 'talk', 'talkblink', 'happy', 'point', 'surprise', 'thumb', 'shrug', 'think', 'scared', 'stick', 'wave', 'heart'];
const XURL = {};
for (const k of XPOSES) XURL[k] = preload(`file://${window.ROOT}/xingxing/assets/${k}.png`);
const XREF_H = 388;                         // 原图全身高度（像素）

// 伪随机：说话时嘴巴开合的节奏
const _hash = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

function xingxing(parent, { x, y, h = 480, flip = false, cues = [{ t: 0, pose: 'talk' }], enter = null, exit = null, marks = [], shadow = true } = {}) {
  const s = h / XREF_H;
  const root = el('g', {}, parent);
  const shadowEl = shadow ? el('ellipse', { cx: 0, cy: 0, rx: 0.24 * h, ry: 0.03 * h, fill: '#000', opacity: 0.45 }, root) : null;
  const sway = el('g', {}, root);
  const hop = el('g', {}, sway);
  const sc = el('g', {}, hop);
  const imgs = {};
  for (const k of XPOSES) {
    const m = window.XMETA[k];
    imgs[k] = el('image', { href: XURL[k], x: -m.ax, y: -m.ay, width: m.w, height: m.h, opacity: 0, preserveAspectRatio: 'none' }, sc);
  }
  const markG = el('g', {}, root);
  const markEls = marks.map(mk => {
    const g = el('g', {}, markG);
    const k = mk.type, sz = 0.2 * h;
    if (k === '!' || k === '?') {
      el('text', { x: 0, y: 0, 'font-family': FONT.heavy, 'font-size': sz, fill: k === '!' ? C.orange : C.cyan, 'text-anchor': 'middle' }, g).textContent = k === '!' ? '！' : '？';
    } else if (k === 'sweat') {
      el('path', { d: `M0,${-sz * 0.6} Q${sz * 0.32},${-sz * 0.1} ${sz * 0.2},${sz * 0.12} Q0,${sz * 0.3} ${-sz * 0.2},${sz * 0.12} Q${-sz * 0.32},${-sz * 0.1} 0,${-sz * 0.6} Z`, fill: C.cyan, opacity: 0.9 }, g);
    } else if (k === 'heart') {
      const r = sz * 0.28;
      el('path', { d: `M0,${r * 1.2} C${-r * 2.2},${-r * 0.2} ${-r * 0.9},${-r * 1.9} 0,${-r * 0.6} C${r * 0.9},${-r * 1.9} ${r * 2.2},${-r * 0.2} 0,${r * 1.2} Z`, fill: C.orange }, g);
    } else if (k === 'spark') {
      const star = (cx, cy, r) => el('path', { d: `M${cx},${cy - r} Q${cx},${cy} ${cx + r},${cy} Q${cx},${cy} ${cx},${cy + r} Q${cx},${cy} ${cx - r},${cy} Q${cx},${cy} ${cx},${cy - r} Z`, fill: C.cyan }, g);
      star(0, 0, sz * 0.32); star(sz * 0.42, sz * 0.32, sz * 0.18);
    }
    return { g, mk };
  });

  // 找当前姿势与上一个姿势
  function poseAt(t) {
    let cur = cues[0], prev = null;
    for (const c of cues) { if (c.t <= t) { prev = cur === c ? prev : cur; cur = c; } }
    let i = cues.indexOf(cur);
    return { cur, prev: i > 0 ? cues[i - 1] : null };
  }
  function rigFrame(t, pose, talking) {
    const blink = ((t + 1.9) % 3.4) < 0.13 || ((t + 2.3) % 7.9) < 0.11;
    if (pose === 'talk' && talking) {
      const open = _hash(Math.floor(t * 7.5)) > 0.42;
      return open ? (blink ? 'talkblink' : 'talk') : (blink ? 'blink' : 'base');
    }
    return blink ? 'blink' : 'base';
  }
  const resolve = (c, t) => (c.pose === 'talk' || c.pose === 'idle') ? rigFrame(t, c.pose, c.talk !== false && c.pose === 'talk') : c.pose;

  return {
    root,
    update(t) {
      const { cur, prev } = poseAt(t);
      const since = t - cur.t;
      // 换动作：0.12s 交叉淡化 + 0.3s 小跳（向上 14px 再落回，无回弹）
      const fade = 1;  // 换动作直接切（配合小跳），不做交叉淡化，避免出现重影
      for (const k of XPOSES) imgs[k].setAttribute('opacity', 0);
      const nk = resolve(cur, t);
      // 新姿势叠在旧姿势上面淡入，旧姿势保持不透明，避免交叉时人物变半透明
      imgs[nk].setAttribute('opacity', fade);
      if (prev && fade < 1) {
        const pk = resolve(prev, t);
        if (pk !== nk) { imgs[pk].setAttribute('opacity', 1); sc.appendChild(imgs[nk]); }
      }
      if (shadowEl) shadowEl.setAttribute('opacity', ['stick', 'wave', 'heart'].includes(nk) ? 0 : 0.45);
      const hp = prev && since < 0.3 ? Math.sin(Math.PI * since / 0.3) : 0;
      const talking = cur.pose === 'talk' && cur.talk !== false;
      const bob = talking && (nk === 'talk' || nk === 'talkblink') ? -2 : 0;
      hop.setAttribute('transform', `translate(0 ${(-14 * hp + bob).toFixed(2)})`);
      const breath = 1 + 0.008 * Math.sin((2 * Math.PI * t) / 2.2);
      const sy = breath * (1 - 0.025 * hp);
      sc.setAttribute('transform', `scale(${(flip ? -s : s).toFixed(4)} ${(s * sy).toFixed(4)})`);
      sway.setAttribute('transform', `rotate(${(0.7 * Math.sin((2 * Math.PI * t) / 4.5)).toFixed(3)})`);
      // 入场 / 出场：横向滑动 + 淡入淡出
      let dx = 0, op = 1;
      if (enter) { const p = prog(t, enter.t, 0.45); dx += (enter.from === 'right' ? 240 : -240) * (1 - p); op *= p; }
      if (exit) { const p = prog(t, exit.t, 0.4); dx += (exit.to === 'right' ? 240 : -240) * p; op *= 1 - p; }
      root.setAttribute('transform', `translate(${(x + dx).toFixed(1)} ${y})`);
      root.setAttribute('opacity', op.toFixed(3));
      // 头顶反应符号：在头部右上方淡入上浮，停留后淡出
      const m = window.XMETA[nk];
      const headX = (m.headx - m.ax) * s * (flip ? -1 : 1);
      for (const { g, mk } of markEls) {
        const d = mk.dur || 1.5;
        const pin = prog(t, mk.t, 0.25), pout = prog(t, mk.t + d, 0.25);
        const mx = headX + (flip ? -1 : 1) * 0.36 * h + (mk.dx || 0), my = -0.86 * h + (mk.dy || 0);
        g.setAttribute('transform', `translate(${mx.toFixed(1)} ${(my + 12 * (1 - pin)).toFixed(1)})`);
        g.setAttribute('opacity', (pin * (1 - pout)).toFixed(3));
      }
    },
  };
}
