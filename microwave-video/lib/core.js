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
