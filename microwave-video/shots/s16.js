// 镜头 16｜那开着的时候站旁边呢？你凑近看看炉门，上面有层带小孔的金属网。
// 画面：微波炉在工作，放大圈推近炉门，看到满是小孔的金属网，孔里透出炉内的暖光。标注：炉门金属网 / 小孔
(() => {
  const DUR = 6;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="hole" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#C08040"/><stop offset="1" stop-color="#3A2614"/></radialGradient>
 <linearGradient id="plate" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${C.g5}"/><stop offset="1" stop-color="${C.g3}"/></linearGradient>`);
  const head = title(svg, 540, 330, [['炉门', C.white], ['金属网', C.cyan]]);

  const MX = 380, MY = 470, MS = 0.75;
  const mw = microwave(svg, { x: MX, y: MY, s: MS });
  const PX = MX + 200 * MS, PY = MY + 160 * MS;   // 门上被放大的位置
  const focus = el('circle', { cx: PX, cy: PY, r: 34, fill: 'none', stroke: C.cyan, 'stroke-width': 4 }, svg);
  const LX = 720, LY = 1150, LR = 230;
  const lines = el('path', { d: `M${PX - 30},${PY + 15} L${LX - LR + 10},${LY - 60} M${PX + 30},${PY + 15} L${LX + LR - 40},${LY - 120}`, stroke: C.cyan, 'stroke-width': 2.5, 'stroke-dasharray': '10 10', opacity: 0.7 }, svg);
  const L = lens(svg, LX, LY, LR);
  const meshG = el('g', {}, L.inner);
  el('rect', { x: LX - LR, y: LY - LR, width: LR * 2, height: LR * 2, fill: 'url(#plate)' }, meshG);
  for (let r = -6; r <= 6; r++) for (let c = -6; c <= 6; c++) {
    const x = LX + c * 46 + (r % 2 ? 23 : 0), y = LY + r * 40;
    el('circle', { cx: x, cy: y, r: 15, fill: 'url(#hole)' }, meshG);
  }
  const lbHole = label(svg, { px: LX + 23, py: LY + 40, tx: 470, ty: 1440, text: '小孔', anchor: 'start' });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'think' }, { t: 1.9, pose: 'point' }, { t: 3.6, pose: 'talk' }],
    marks: [{ t: 0.2, type: '?', dur: 1.5 }, { t: 2.0, type: 'spark', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 2.2);
      mw.update(t, { on: 1, display: '1:30' });
      focus.setAttribute('opacity', prog(t, 1.2, 0.3));
      lines.setAttribute('opacity', (0.7 * prog(t, 1.4, 0.3)).toFixed(3));
      popIn(L.g, t, 1.5, LX, LY, 0.45, 0.85);
      meshG.setAttribute('transform', `translate(${LX} ${LY}) scale(${(1 + 0.05 * prog(t, 1.5, 4)).toFixed(4)}) translate(${-LX} ${-LY})`);
      lbHole.update(t, 3.4);
      xx.update(t);
    },
  };
})();
