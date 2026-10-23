// 全局风格：写实信息图风。所有镜头共用，保证统一。
// 配色只用 4 色：底 #0F141A / 青 #5CC8FF / 橙 #FF9A3D / 白 #F2F4F7；物体材质用灰阶。
const NS = 'http://www.w3.org/2000/svg';
const W = 1080, H = 1920, FPS = 30;
const C = {
  bg: '#0F141A', bgHi: '#1A212B',
  cyan: '#5CC8FF', orange: '#FF9A3D', white: '#F2F4F7',
  // 材质灰阶（由底色派生）
  g1: '#11151A', g2: '#1D2127', g3: '#2A2F37', g4: '#3A414B', g5: '#4A525D', g6: '#9AA3AD', g7: '#C9D1DA',
};
const FONT = { heavy: 'NotoBlack', bold: 'NotoBold' };
const SIZE = { title: 120, label: 76 };

function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
// 缓入缓出，无回弹
const ease = x => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const prog = (t, start, dur) => ease((t - start) / dur);
const lerp = (a, b, p) => a + (b - a) * p;

// 入场：淡入 + 上移 30px，0.4s
function enter(g, t, start, dy = 30, dur = 0.4) {
  const p = prog(t, start, dur);
  g.setAttribute('opacity', p);
  g.setAttribute('transform', `translate(0 ${((1 - p) * dy).toFixed(2)})`);
  return p;
}
// 退场：淡出
function leave(g, t, start, dur = 0.4) {
  const p = prog(t, start, dur);
  g.setAttribute('opacity', 1 - p);
  return p;
}

function sinePath(x0, x1, y, amp, period, phase = 0, step = 6) {
  let d = '';
  for (let x = x0; x <= x1; x += step) {
    const yy = y + amp * Math.sin(((x - x0) / period) * 2 * Math.PI - phase);
    d += (d ? ' L' : 'M') + x.toFixed(1) + ',' + yy.toFixed(1);
  }
  return d;
}

function setupStage() {
  const svg = el('svg', { xmlns: NS, width: W, height: H, viewBox: `0 0 ${W} ${H}` });
  document.body.appendChild(svg);
  const defs = el('defs', {}, svg);
  defs.innerHTML = `
 <radialGradient id="bg" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="${C.bgHi}"/><stop offset="1" stop-color="${C.bg}"/></radialGradient>
 <linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.g5}"/><stop offset="0.5" stop-color="#2E343C"/><stop offset="1" stop-color="${C.g2}"/></linearGradient>
 <linearGradient id="metalH" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${C.g3}"/><stop offset="0.5" stop-color="${C.g5}"/><stop offset="1" stop-color="${C.g3}"/></linearGradient>
 <linearGradient id="panel" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${C.g3}"/><stop offset="1" stop-color="${C.g4}"/></linearGradient>
 <radialGradient id="cavity" cx="50%" cy="75%" r="80%"><stop offset="0" stop-color="#6B4A22"/><stop offset="0.6" stop-color="#2A2118"/><stop offset="1" stop-color="#121010"/></radialGradient>
 <radialGradient id="cavityOff" cx="50%" cy="75%" r="80%"><stop offset="0" stop-color="#1E1D1C"/><stop offset="1" stop-color="#0C0C0C"/></radialGradient>
 <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="0.35" stop-color="#FFFFFF" stop-opacity="0.02"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
 <pattern id="mesh" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="5" cy="5" r="1.8" fill="#000" opacity="0.22"/></pattern>
 <linearGradient id="bowl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${C.g6}"/><stop offset="0.45" stop-color="#F4F6F8"/><stop offset="1" stop-color="#B7BEC6"/></linearGradient>
 <radialGradient id="rice" cx="45%" cy="30%" r="70%"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#D8D2C4"/></radialGradient>
 <radialGradient id="atomO" cx="35%" cy="30%" r="70%"><stop offset="0" stop-color="#FFB27A"/><stop offset="0.55" stop-color="#E8562A"/><stop offset="1" stop-color="#7A1E0C"/></radialGradient>
 <radialGradient id="atomH" cx="35%" cy="30%" r="70%"><stop offset="0" stop-color="#FFFFFF"/><stop offset="0.6" stop-color="${C.g7}"/><stop offset="1" stop-color="#6C7681"/></radialGradient>
 <radialGradient id="lensbg" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#16202B"/><stop offset="1" stop-color="#0C1218"/></radialGradient>
 <linearGradient id="skin" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#D2B39A"/><stop offset="1" stop-color="#A88A73"/></linearGradient>
 <linearGradient id="wall" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#141A21"/><stop offset="1" stop-color="#1C232D"/></linearGradient>
 <linearGradient id="counter" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.g4}"/><stop offset="0.15" stop-color="${C.g3}"/><stop offset="1" stop-color="${C.g1}"/></linearGradient>
 <filter id="soft" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="shadow" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="24" stdDeviation="22" flood-color="#000" flood-opacity="0.6"/></filter>`;
  el('rect', { width: W, height: H, fill: 'url(#bg)' }, svg);
  return { svg, defs };
}

// 标题：思源黑体 Heavy，parts = [[文字, 颜色], ...]
function title(parent, x, y, parts, size = SIZE.title) {
  const g = el('g', {}, parent);
  const t = el('text', { x, y, 'font-family': FONT.heavy, 'font-size': size, 'text-anchor': 'middle', fill: C.white }, g);
  for (const [s, c] of parts) { const sp = el('tspan', { fill: c || C.white }, t); sp.textContent = s; }
  return { g, update(tt, start) { enter(g, tt, start); } };
}

// 关键词标注：起点圆点 → 3px 青色引线 → 8px 青色竖条 + 白字
// (px,py) 指向点；(tx,ty) 文字基线位置；anchor: start 文字在竖条右边，end 在左边
function label(parent, { px, py, tx, ty, text, size = SIZE.label, anchor = 'start', color = C.white }) {
  const g = el('g', {}, parent);
  const barX = anchor === 'start' ? tx : tx - 8;
  const barBottom = ty + size * 0.18;
  const lx = anchor === 'start' ? tx + 4 : tx - 4;
  const hasLine = px != null;
  let line, dot, len = 0;
  if (hasLine) {
    line = el('path', { d: `M${px},${py} L${lx},${barBottom}`, stroke: C.cyan, 'stroke-width': 3, fill: 'none' }, g);
    len = Math.hypot(lx - px, barBottom - py);
    line.setAttribute('stroke-dasharray', `${len} ${len}`);
    dot = el('circle', { cx: px, cy: py, r: 9, fill: C.cyan }, g);
  }
  const tg = el('g', {}, g);
  el('rect', { x: barX, y: ty - size * 0.82, width: 8, height: size, fill: C.cyan }, tg);
  const tx2 = anchor === 'start' ? tx + 26 : tx - 26;
  const te = el('text', { x: tx2, y: ty, 'font-family': FONT.bold, 'font-size': size, fill: color, 'text-anchor': anchor }, tg);
  if (Array.isArray(text)) for (const [s, c] of text) { const sp = el('tspan', { fill: c || color }, te); sp.textContent = s; }
  else te.textContent = text;
  return {
    g,
    // 引线 0.3s 画出 → 文字 0.3s 淡入
    update(t, start) {
      if (hasLine) {
        const p = prog(t, start, 0.3);
        line.setAttribute('stroke-dashoffset', (len * (1 - p)).toFixed(1));
        dot.setAttribute('opacity', clamp((t - start) / 0.1));
        const q = prog(t, start + 0.3, 0.3);
        tg.setAttribute('opacity', q);
      } else {
        enter(tg, t, start, 20, 0.3);
      }
    },
    hide(t, start) { leave(g, t, start); },
  };
}

// 微波炉（本地坐标 860×520，左上角为原点）
function microwave(parent, { x = 0, y = 0, s = 1, id = 'mw' } = {}) {
  const root = el('g', { transform: `translate(${x} ${y}) scale(${s})` }, parent);
  el('rect', { x: 0, y: 0, width: 860, height: 520, rx: 22, fill: 'url(#metal)', filter: 'url(#shadow)' }, root);
  el('rect', { x: 3, y: 3, width: 854, height: 4, rx: 2, fill: '#FFFFFF', opacity: 0.18 }, root);
  el('rect', { x: 615, y: 30, width: 215, height: 460, rx: 10, fill: 'url(#panel)' }, root);
  const clip = el('clipPath', { id: id + 'win' }, root);
  el('rect', { x: 40, y: 40, width: 560, height: 440, rx: 14 }, clip);
  const win = el('g', { 'clip-path': `url(#${id}win)` }, root);
  const cavOff = el('rect', { x: 40, y: 40, width: 560, height: 440, fill: 'url(#cavityOff)' }, win);
  const cavOn = el('rect', { x: 40, y: 40, width: 560, height: 440, fill: 'url(#cavity)' }, win);
  el('ellipse', { cx: 320, cy: 452, rx: 215, ry: 26, fill: C.g4 }, win);
  el('ellipse', { cx: 320, cy: 448, rx: 215, ry: 24, fill: '#5A6068', opacity: 0.6 }, win);
  const bx = 320, by = 380;
  const food = el('g', {}, win);
  el('ellipse', { cx: bx, cy: by - 15, rx: 118, ry: 22, fill: 'url(#rice)' }, food);
  el('path', { d: `M${bx - 115},${by - 15} Q${bx - 110},${by - 90} ${bx},${by - 95} Q${bx + 110},${by - 90} ${bx + 115},${by - 15} Z`, fill: 'url(#rice)' }, food);
  el('path', { d: `M${bx - 130},${by - 15} Q${bx - 120},${by + 70} ${bx},${by + 72} Q${bx + 120},${by + 70} ${bx + 130},${by - 15} Z`, fill: 'url(#bowl)' }, food);
  // 碗上的花纹，横向移动表示转盘在转
  const deco = el('g', {}, food);
  const decoDots = [0, 1, 2, 3].map(() => el('ellipse', { cx: 0, cy: by + 25, rx: 9, ry: 7, fill: '#7D8FA3' }, deco));
  el('ellipse', { cx: bx, cy: by - 15, rx: 130, ry: 10, fill: 'none', stroke: '#FFFFFF', 'stroke-opacity': 0.6, 'stroke-width': 3 }, food);
  const waves = el('g', {}, win);
  const w1 = el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 4, filter: 'url(#soft)' }, waves);
  const w2 = el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 4, opacity: 0.7, filter: 'url(#soft)' }, waves);
  el('rect', { x: 40, y: 40, width: 560, height: 440, fill: 'url(#mesh)' }, win);
  el('rect', { x: 40, y: 40, width: 560, height: 440, fill: 'url(#glass)' }, win);
  el('rect', { x: 40, y: 40, width: 560, height: 440, rx: 14, fill: 'none', stroke: C.g1, 'stroke-width': 8 }, root);
  el('rect', { x: 642, y: 65, width: 162, height: 70, rx: 6, fill: '#0A0C0F' }, root);
  const disp = el('text', { x: 723, y: 117, 'font-family': FONT.bold, 'font-size': 44, fill: C.orange, 'text-anchor': 'middle', 'letter-spacing': 4 }, root);
  for (const ky of [250, 390]) {
    el('circle', { cx: 723, cy: ky, r: 50, fill: '#1A1E23' }, root);
    el('circle', { cx: 723, cy: ky, r: 44, fill: 'url(#metal)' }, root);
    el('rect', { x: 720, y: ky - 38, width: 6, height: 26, rx: 3, fill: C.g7 }, root);
  }
  return {
    root,
    // on: 0..1 内灯/波纹强度；t 用于波纹流动和转盘
    update(t, { on = 1, display = '1:30' } = {}) {
      cavOn.setAttribute('opacity', on);
      waves.setAttribute('opacity', on);
      w1.setAttribute('d', sinePath(60, 580, 105, 16, 70, t * 4.0));
      w2.setAttribute('d', sinePath(60, 580, 170, 16, 70, t * 4.0 + 1.5));
      disp.textContent = display;
      // 转盘：花纹绕碗一周 6 秒
      decoDots.forEach((d, i) => {
        const a = (t / 6) * 2 * Math.PI * (on > 0 ? 1 : 0) + (i * Math.PI) / 2;
        const c = Math.cos(a), sn = Math.sin(a);
        d.setAttribute('cx', (bx + 100 * c).toFixed(1));
        d.setAttribute('opacity', sn > 0 ? (0.5 * sn).toFixed(2) : 0);
        d.setAttribute('rx', (9 * Math.max(0.2, sn)).toFixed(1));
      });
    },
  };
}

// 推近：整组从 1 缓慢放大到 1+amt（≤5%）
function pushIn(g, t, dur, amt = 0.03, cx = 540, cy = 800) {
  const s = 1 + amt * clamp(t / dur);
  g.setAttribute('transform', `translate(${cx} ${cy}) scale(${s.toFixed(5)}) translate(${-cx} ${-cy})`);
}

// ---------------------------------------------------------------- 通用组件
// 青色 ✓（安全/正确）
function checkIcon(parent, cx, cy, r = 60) {
  const g = el('g', {}, parent);
  el('circle', { cx, cy, r, fill: 'none', stroke: C.cyan, 'stroke-width': Math.max(5, r * 0.09) }, g);
  el('path', { d: `M${cx - r * 0.42},${cy + r * 0.02} L${cx - r * 0.1},${cy + r * 0.34} L${cx + r * 0.45},${cy - r * 0.3}`, fill: 'none', stroke: C.cyan, 'stroke-width': Math.max(8, r * 0.16), 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g);
  return g;
}
// 橙色 ✕（危险/错误）
function crossIcon(parent, cx, cy, r = 60) {
  const g = el('g', {}, parent);
  el('circle', { cx, cy, r, fill: 'none', stroke: C.orange, 'stroke-width': Math.max(5, r * 0.09) }, g);
  const k = r * 0.36;
  el('path', { d: `M${cx - k},${cy - k} L${cx + k},${cy + k} M${cx + k},${cy - k} L${cx - k},${cy + k}`, stroke: C.orange, 'stroke-width': Math.max(8, r * 0.16), 'stroke-linecap': 'round' }, g);
  return g;
}
// 橙色警示三角
function warnIcon(parent, cx, cy, r = 60) {
  const g = el('g', {}, parent);
  el('path', { d: `M${cx},${cy - r} L${cx + r * 1.1},${cy + r * 0.8} L${cx - r * 1.1},${cy + r * 0.8} Z`, fill: 'none', stroke: C.orange, 'stroke-width': Math.max(6, r * 0.1), 'stroke-linejoin': 'round' }, g);
  el('rect', { x: cx - r * 0.07, y: cy - r * 0.45, width: r * 0.14, height: r * 0.7, rx: r * 0.07, fill: C.orange }, g);
  el('circle', { cx, cy: cy + r * 0.5, r: r * 0.09, fill: C.orange }, g);
  return g;
}
// 立体水分子：O 在中心，两个 H 夹角 104.5°；ang 为朝向（度）
function waterMol(parent, cx, cy, s = 1) {
  const outer = el('g', { transform: `translate(${cx} ${cy})` }, parent);
  const g = el('g', {}, outer);
  for (const d of [-52, 52]) {
    const a = (d * Math.PI) / 180;
    el('circle', { cx: (54 * Math.cos(a) * s).toFixed(1), cy: (54 * Math.sin(a) * s).toFixed(1), r: 25 * s, fill: 'url(#atomH)' }, g);
  }
  el('circle', { cx: 0, cy: 0, r: 42 * s, fill: 'url(#atomO)' }, g);
  return { outer, g, rot(a) { g.setAttribute('transform', `rotate(${a.toFixed(2)})`); } };
}
// 圆弧箭头（顺时针），返回 g
function arcArrow(parent, cx, cy, r, a0, a1, color = C.cyan, w = 4, head = 14) {
  const g = el('g', {}, parent);
  const P = a => [cx + r * Math.cos((a * Math.PI) / 180), cy + r * Math.sin((a * Math.PI) / 180)];
  const [x0, y0] = P(a0), [x1, y1] = P(a1);
  const large = ((a1 - a0) % 360 + 360) % 360 > 180 ? 1 : 0;
  el('path', { d: `M${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1}`, fill: 'none', stroke: color, 'stroke-width': w, 'stroke-linecap': 'round' }, g);
  const t = (a1 * Math.PI) / 180, tx = -Math.sin(t), ty = Math.cos(t), nx = Math.cos(t), ny = Math.sin(t);
  el('path', { d: `M${x1 + tx * head * 1.1},${y1 + ty * head * 1.1} L${x1 + nx * head * 0.75},${y1 + ny * head * 0.75} L${x1 - nx * head * 0.75},${y1 - ny * head * 0.75} Z`, fill: color }, g);
  return g;
}
// 直线箭头
function arrow(parent, x0, y0, x1, y1, color = C.cyan, w = 6, head = 22) {
  const g = el('g', {}, parent);
  const a = Math.atan2(y1 - y0, x1 - x0), ux = Math.cos(a), uy = Math.sin(a);
  el('path', { d: `M${x0},${y0} L${x1 - ux * head * 0.8},${y1 - uy * head * 0.8}`, stroke: color, 'stroke-width': w, 'stroke-linecap': 'round' }, g);
  el('path', { d: `M${x1},${y1} L${x1 - ux * head - uy * head * 0.6},${y1 - uy * head + ux * head * 0.6} L${x1 - ux * head + uy * head * 0.6},${y1 - uy * head - ux * head * 0.6} Z`, fill: color }, g);
  return g;
}
// 放大圈
function lens(parent, cx, cy, r) {
  const g = el('g', {}, parent);
  el('circle', { cx, cy, r, fill: 'url(#lensbg)' }, g);
  const inner = el('g', {}, g);
  const cp = el('clipPath', { id: 'lens' + Math.round(cx) + Math.round(cy) }, g);
  el('circle', { cx, cy, r: r - 2 }, cp);
  inner.setAttribute('clip-path', `url(#lens${Math.round(cx)}${Math.round(cy)})`);
  const ring = el('circle', { cx, cy, r, fill: 'none', stroke: C.cyan, 'stroke-width': 4, filter: 'url(#soft)' }, g);
  return { g, inner, ring };
}
// 一碗米饭（侧视），(cx, cy) 为碗口中心
function riceBowl(parent, cx, cy, s = 1) {
  const g = el('g', { transform: `translate(${cx} ${cy}) scale(${s})` }, parent);
  el('ellipse', { cx: 0, cy: 0, rx: 118, ry: 22, fill: 'url(#rice)' }, g);
  el('path', { d: 'M-115,0 Q-110,-75 0,-80 Q110,-75 115,0 Z', fill: 'url(#rice)' }, g);
  el('path', { d: 'M-130,0 Q-120,85 0,87 Q120,85 130,0 Z', fill: 'url(#bowl)' }, g);
  el('ellipse', { cx: 0, cy: 0, rx: 130, ry: 10, fill: 'none', stroke: '#FFFFFF', 'stroke-opacity': 0.6, 'stroke-width': 3 }, g);
  el('ellipse', { cx: 0, cy: 92, rx: 60, ry: 8, fill: '#000', opacity: 0.35 }, g);
  return g;
}
// 热气：几条上升的淡白曲线，update(t) 让它缓慢流动
function steam(parent, xs, y0, h = 90, color = '#FFFFFF', op = 0.4) {
  const g = el('g', {}, parent);
  const ps = xs.map(() => el('path', { fill: 'none', stroke: color, 'stroke-width': 5, 'stroke-linecap': 'round', opacity: op }, g));
  return {
    g,
    update(t) {
      ps.forEach((p, i) => {
        let d = '';
        for (let k = 0; k <= h; k += 5) {
          const x = xs[i] + 9 * Math.sin(k / 22 - t * 3 + i * 1.7);
          d += (d ? ' L' : 'M') + x.toFixed(1) + ',' + (y0 - k).toFixed(1);
        }
        p.setAttribute('d', d);
      });
    },
  };
}
// 扑克牌：背面深灰 + 青色内框 + 大号字；正面浅色，内容由 front(g, w, h) 绘制（以牌中心为原点）
function playingCard(parent, { cx, cy, w = 240, h = 340, back = '', backSize = 120, front = null, id = 'c' }) {
  const outer = el('g', { transform: `translate(${cx} ${cy})` }, parent);
  const flip = el('g', {}, outer);
  el('rect', { x: -w / 2 + 6, y: -h / 2 + 14, width: w, height: h, rx: 20, fill: '#000', opacity: 0.45 }, outer).remove();
  const shadow = el('rect', { x: -w / 2 + 4, y: -h / 2 + 16, width: w, height: h, rx: 20, fill: '#000', opacity: 0.45 }, flip);
  const bk = el('g', {}, flip);
  el('rect', { x: -w / 2, y: -h / 2, width: w, height: h, rx: 20, fill: C.g2, stroke: C.g4, 'stroke-width': 3 }, bk);
  el('rect', { x: -w / 2 + 16, y: -h / 2 + 16, width: w - 32, height: h - 32, rx: 12, fill: 'none', stroke: C.cyan, 'stroke-width': 3, opacity: 0.8 }, bk);
  const bt = el('text', { x: 0, y: backSize * 0.36, 'font-family': FONT.heavy, 'font-size': backSize, fill: C.white, 'text-anchor': 'middle' }, bk);
  bt.textContent = back;
  const fr = el('g', {}, flip);
  el('rect', { x: -w / 2, y: -h / 2, width: w, height: h, rx: 20, fill: '#E9EDF1' }, fr);
  if (front) front(fr, w, h);
  const hi = el('rect', { x: -w / 2 - 6, y: -h / 2 - 6, width: w + 12, height: h + 12, rx: 24, fill: 'none', stroke: C.orange, 'stroke-width': 6, opacity: 0 }, flip);
  return {
    outer, flip, backText: bt, hi,
    // p: 0 背面 → 1 正面（绕竖轴翻转）
    setFlip(p) {
      const sx = Math.abs(Math.cos(Math.PI * clamp(p)));
      flip.setAttribute('transform', `scale(${Math.max(0.001, sx).toFixed(4)} 1)`);
      bk.setAttribute('opacity', p < 0.5 ? 1 : 0);
      fr.setAttribute('opacity', p < 0.5 ? 0 : 1);
    },
    move(x, y, s = 1, op = 1) {
      outer.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${s.toFixed(4)})`);
      outer.setAttribute('opacity', op);
    },
  };
}
// 普通文字
function text(parent, x, y, str, { size = SIZE.label, font = FONT.bold, color = C.white, anchor = 'middle' } = {}) {
  const t = el('text', { x, y, 'font-family': font, 'font-size': size, fill: color, 'text-anchor': anchor }, parent);
  if (Array.isArray(str)) for (const [s, c] of str) { const sp = el('tspan', { fill: c || color }, t); sp.textContent = s; }
  else t.textContent = str;
  return t;
}
// 缩放入场（0.92 → 1，淡入；无过冲），以 (cx,cy) 为中心
function popIn(g, t, start, cx, cy, dur = 0.4, from = 0.92) {
  const p = prog(t, start, dur);
  const s = from + (1 - from) * p;
  g.setAttribute('opacity', p);
  g.setAttribute('transform', `translate(${cx} ${cy}) scale(${s.toFixed(4)}) translate(${-cx} ${-cy})`);
  return p;
}
