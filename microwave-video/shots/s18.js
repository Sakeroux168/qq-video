// 镜头 18｜当然，门坏了、关不严，就别用了，赶紧修。
// 画面：微波炉门边露出一道缝，橙色警示框闪现；标题从"门关不严"换成"别用，赶紧修"。
(() => {
  const DUR = 5;
  const { svg } = setupStage();
  const head1 = title(svg, 540, 330, [['门', C.white], ['关不严', C.orange]]);
  const head2 = title(svg, 540, 330, [['别用，', C.white], ['赶紧修', C.orange]]);

  const MX = 380, MY = 600, MS = 0.75;
  const mw = microwave(svg, { x: MX, y: MY, s: MS });
  // 门缝：门右边缘和面板之间一道黑缝，门微微错开
  const gx = MX + 604 * MS;
  const gap = el('g', {}, svg);
  el('path', { d: `M${gx},${MY + 30 * MS} L${gx + 18},${MY + 20 * MS} L${gx + 18},${MY + 500 * MS} L${gx},${MY + 490 * MS} Z`, fill: '#000' }, gap);
  el('path', { d: `M${gx},${MY + 30 * MS} L${gx},${MY + 490 * MS}`, stroke: C.orange, 'stroke-width': 4 }, gap);
  const frame = el('rect', { x: MX - 30, y: MY - 30, width: 860 * MS + 60, height: 520 * MS + 60, rx: 30, fill: 'none', stroke: C.orange, 'stroke-width': 5, 'stroke-dasharray': '18 12' }, svg);
  const warn = el('g', {}, svg);
  warnIcon(warn, MX - 10, MY - 40, 46);
  const lbGap = label(svg, { px: gx + 9, py: MY + 400 * MS, tx: 846, ty: 1110, text: '门缝', anchor: 'end' });
  // 扳手（开口扳手）
  const fix = el('g', {}, svg);
  const wr = el('g', { transform: 'translate(930 1210) rotate(-40)' }, fix);
  el('rect', { x: -14, y: 0, width: 28, height: 190, rx: 14, fill: C.g7 }, wr);
  el('circle', { cx: 0, cy: -10, r: 48, fill: C.g7 }, wr);
  el('rect', { x: -15, y: -62, width: 30, height: 52, fill: C.bg }, wr);
  el('circle', { cx: 0, cy: 175, r: 9, fill: C.g4 }, wr);

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.2, pose: 'scared' }, { t: 2.8, pose: 'point' }, { t: 4.2, pose: 'talk' }],
    marks: [{ t: 1.3, type: 'sweat', dur: 1.3 }, { t: 2.9, type: '!', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head1.update(t, 0.2);
      head1.g.setAttribute('opacity', Math.min(+head1.g.getAttribute('opacity'), 1 - prog(t, 2.6, 0.25)));
      head2.update(t, 2.85);
      mw.update(t, { on: 1, display: '1:30' });
      gap.setAttribute('opacity', prog(t, 0.6, 0.3));
      // 警示框：亮两下后常亮
      const blink = t < 1.0 ? 0 : t < 1.9 ? (Math.sin((t - 1.0) * 2 * Math.PI * 2.2) > 0 ? 1 : 0.3) : 1;
      frame.setAttribute('opacity', blink);
      warn.setAttribute('opacity', blink);
      lbGap.update(t, 1.2);
      popIn(fix, t, 3.1, 930, 1260, 0.35, 0.9);
      xx.update(t);
    },
  };
})();
