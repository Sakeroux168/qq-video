// 镜头 11｜这么点能量，改不了饭菜的分子结构，饭菜更不会"带上辐射"。
// 画面：青色微波穿过一碗饭，放大圈里的分子结构完好不动。标注：分子结构不变 / ✓ 不会带辐射
(() => {
  const DUR = 5;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['分子结构', C.white], ['不变', C.cyan]]);

  const BX = 700, BY = 1120;
  const lines = el('path', { d: `M${BX - 90},${BY - 70} L${BX - 170},${BY - 360} M${BX + 90},${BY - 70} L${BX + 170},${BY - 360}`, stroke: C.cyan, 'stroke-width': 2.5, 'stroke-dasharray': '10 10', opacity: 0.7 }, svg);
  const waves = [BY - 60, BY].map((y, i) => el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 4, opacity: i ? 0.6 : 0.9, filter: 'url(#soft)' }, svg));
  const bowl = riceBowl(svg, BX, BY, 1.05);
  const L = lens(svg, BX, 690, 200);
  // 六元环分子（球棍模型）
  const mol = el('g', {}, L.inner);
  const pts = [...Array(6)].map((_, i) => [BX + 95 * Math.cos(Math.PI / 3 * i - Math.PI / 2), 690 + 95 * Math.sin(Math.PI / 3 * i - Math.PI / 2)]);
  pts.forEach(([x, y], i) => { const [x2, y2] = pts[(i + 1) % 6]; el('path', { d: `M${x},${y} L${x2},${y2}`, stroke: C.g6, 'stroke-width': 12 }, mol); });
  pts.forEach(([x, y], i) => {
    const ox = x + (x - BX) * 0.55, oy = y + (y - 690) * 0.55;
    el('path', { d: `M${x},${y} L${ox},${oy}`, stroke: C.g6, 'stroke-width': 8 }, mol);
    el('circle', { cx: ox, cy: oy, r: 16, fill: 'url(#atomH)' }, mol);
  });
  pts.forEach(([x, y], i) => el('circle', { cx: x, cy: y, r: 30, fill: i % 3 ? 'url(#atomH)' : 'url(#atomO)' }, mol));
  const ok = el('g', {}, svg);
  checkIcon(ok, 520, 1345, 46);
  text(ok, 590, 1372, '不会带辐射', { size: 80, font: FONT.heavy, color: C.cyan, anchor: 'start' });

  const xx = xingxing(svg, {
    x: 200, y: 1440, h: 520,
    cues: [{ t: 0, pose: 'talk' }, { t: 2.4, pose: 'thumb' }, { t: 3.9, pose: 'talk' }],
    marks: [{ t: 2.5, type: 'spark', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      waves.forEach((w, i) => w.setAttribute('d', sinePath(420, 1050, BY - 60 + i * 60, 16, 70, t * 4 + i)));
      lines.setAttribute('opacity', 0.7 * prog(t, 0.5, 0.4));
      popIn(L.g, t, 0.6, BX, 690);
      // 分子只做轻微的热振动，结构不变
      mol.setAttribute('transform', `rotate(${(4 * Math.sin(t * 2)).toFixed(2)} ${BX} 690)`);
      enter(ok, t, 2.3);
      xx.update(t);
    },
  };
})();
