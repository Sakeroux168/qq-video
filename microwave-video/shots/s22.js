// 镜头 22｜用之前翻过来看看盒底，写了"可微波炉加热"的才行。
// 画面：盒子翻过来露出盒底，推近，盒底的"微波炉可用"标志被青框高亮。标注：看盒底 / ✓ 可微波炉加热
(() => {
  const DUR = 5;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['看', C.white], ['盒底', C.cyan]]);

  const BX = 690, BY = 880;
  const flipG = el('g', {}, svg);
  // 盒底（俯视）：圆角矩形 + 一圈加强筋
  const bottom = el('g', {}, flipG);
  el('rect', { x: BX - 260, y: BY - 190, width: 520, height: 380, rx: 46, fill: '#A9B7C4', opacity: 0.55 }, bottom);
  el('rect', { x: BX - 230, y: BY - 160, width: 460, height: 320, rx: 34, fill: 'none', stroke: '#DDE6EE', 'stroke-width': 4, opacity: 0.7 }, bottom);
  // 标志：微波炉图形 + 波浪
  const sign = el('g', {}, bottom);
  el('rect', { x: BX - 110, y: BY - 90, width: 220, height: 140, rx: 16, fill: 'none', stroke: C.white, 'stroke-width': 7 }, sign);
  el('rect', { x: BX - 92, y: BY - 72, width: 140, height: 104, rx: 8, fill: 'none', stroke: C.white, 'stroke-width': 5 }, sign);
  for (const yy of [-45, -10]) el('path', { d: sinePath(BX - 84, BX + 40, BY + yy, 7, 34, 0, 4), fill: 'none', stroke: C.white, 'stroke-width': 5 }, sign);
  el('circle', { cx: BX + 80, cy: BY - 50, r: 9, fill: C.white }, sign);
  el('circle', { cx: BX + 80, cy: BY - 15, r: 9, fill: C.white }, sign);
  const ring = el('rect', { x: BX - 145, y: BY - 125, width: 290, height: 210, rx: 22, fill: 'none', stroke: C.cyan, 'stroke-width': 6 }, svg);
  const ok = el('g', {}, svg);
  checkIcon(ok, 470, 1200, 46);
  text(ok, 540, 1228, '可微波炉加热', { size: 80, font: FONT.heavy, color: C.cyan, anchor: 'start' });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.6, pose: 'point' }, { t: 3.2, pose: 'thumb' }],
    marks: [{ t: 1.7, type: 'spark', dur: 1.2 }, { t: 3.3, type: 'spark', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.1);
      // 0~0.8s 翻转（竖直方向压扁再展开），之后慢慢推近
      const f = prog(t, 0, 0.8);
      const sy = 0.15 + 0.85 * f;
      const z = 0.9 + 0.1 * prog(t, 1.0, 1.4);
      flipG.setAttribute('transform', `translate(${BX} ${BY}) scale(${z.toFixed(4)} ${(z * sy).toFixed(4)}) translate(${-BX} ${-BY})`);
      flipG.setAttribute('opacity', f);
      ring.setAttribute('opacity', prog(t, 2.0, 0.3));
      ring.setAttribute('transform', `translate(${BX} ${BY}) scale(${z.toFixed(4)}) translate(${-BX} ${-BY})`);
      enter(ok, t, 2.6);
      xx.update(t);
    },
  };
})();
