// 镜头 8｜狠角色叫电离辐射，像X光、核辐射，能量大，能把身体里的分子打坏，这种确实得躲。
// 画面：X光片、核辐射标志 → 一道橙色密集短波打中一串分子，分子链断开。标注：电离辐射 / X光 / 核辐射 / 能量大 / 要躲
(() => {
  const DUR = 7;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['电离辐射', C.orange]]);

  // X光片
  const xr = el('g', {}, svg);
  const X0 = 400, Y0 = 430;
  el('rect', { x: X0, y: Y0, width: 170, height: 200, rx: 14, fill: '#0B0E12', stroke: C.g5, 'stroke-width': 4 }, xr);
  el('path', { d: `M${X0 + 85},${Y0 + 30} L${X0 + 85},${Y0 + 175}`, stroke: C.white, 'stroke-width': 7, opacity: 0.85, 'stroke-linecap': 'round' }, xr);
  for (let i = 0; i < 4; i++) {
    const y = Y0 + 55 + i * 30;
    el('path', { d: `M${X0 + 85},${y} Q${X0 + 40},${y - 6} ${X0 + 30},${y + 22} M${X0 + 85},${y} Q${X0 + 130},${y - 6} ${X0 + 140},${y + 22}`, fill: 'none', stroke: C.white, 'stroke-width': 5, opacity: 0.75, 'stroke-linecap': 'round' }, xr);
  }
  text(xr, X0 + 85, Y0 + 280, 'X光', { size: 68 });
  // 核辐射标志
  const nu = el('g', {}, svg);
  const NX = 800, NY = 530;
  el('circle', { cx: NX, cy: NY, r: 100, fill: '#0B0E12', stroke: C.g5, 'stroke-width': 4 }, nu);
  for (let i = 0; i < 3; i++) {
    const a0 = (-90 + i * 120 - 30) * Math.PI / 180, a1 = (-90 + i * 120 + 30) * Math.PI / 180, r0 = 26, r1 = 84;
    el('path', { d: `M${NX + r0 * Math.cos(a0)},${NY + r0 * Math.sin(a0)} L${NX + r1 * Math.cos(a0)},${NY + r1 * Math.sin(a0)} A${r1},${r1} 0 0 1 ${NX + r1 * Math.cos(a1)},${NY + r1 * Math.sin(a1)} L${NX + r0 * Math.cos(a1)},${NY + r0 * Math.sin(a1)} A${r0},${r0} 0 0 0 ${NX + r0 * Math.cos(a0)},${NY + r0 * Math.sin(a0)} Z`, fill: C.orange }, nu);
  }
  el('circle', { cx: NX, cy: NY, r: 16, fill: C.orange }, nu);
  text(nu, NX, Y0 + 280, '核辐射', { size: 68 });

  // 分子链
  const CY = 830, XS = [560, 650, 740, 830, 920];
  const wave = el('path', { fill: 'none', stroke: C.orange, 'stroke-width': 6, 'stroke-linejoin': 'round' }, svg);
  const bond = el('rect', { x: 740, y: CY - 7, width: 90, height: 14, rx: 7, fill: C.g6 }, svg);
  const leftG = el('g', {}, svg), rightG = el('g', {}, svg);
  XS.forEach((x, i) => {
    const g = i < 3 ? leftG : rightG;
    if (i < XS.length - 1 && i !== 2) el('rect', { x, y: CY - 7, width: 90, height: 14, rx: 7, fill: C.g6 }, g);
    el('circle', { cx: x, cy: CY, r: 36, fill: i % 2 ? 'url(#atomO)' : 'url(#atomH)' }, g);
  });
  const crack = el('path', { d: `M785,${CY - 50} L770,${CY - 15} L795,${CY + 5} L775,${CY + 50}`, fill: 'none', stroke: C.orange, 'stroke-width': 7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
  const lbE = label(svg, { px: 330, py: 830, tx: 300, ty: 760, text: '能量大', anchor: 'end' });
  const avoid = el('g', {}, svg);
  warnIcon(avoid, 640, 1140, 52);
  text(avoid, 760, 1170, '要躲', { size: 96, font: FONT.heavy, color: C.orange, anchor: 'start' });

  const xx = xingxing(svg, {
    x: 215, y: 1440, h: 540,
    cues: [{ t: 0, pose: 'talk' }, { t: 3.5, pose: 'surprise' }, { t: 5.0, pose: 'scared' }],
    marks: [{ t: 3.6, type: '!', dur: 1.2 }, { t: 5.1, type: 'sweat', dur: 1.4 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      enter(xr, t, 0.7);
      enter(nu, t, 1.1);
      enter(leftG, t, 1.7); enter(rightG, t, 1.7);
      bond.setAttribute('opacity', prog(t, 1.7, 0.4) * (1 - prog(t, 3.5, 0.15)));
      // 波：2.4s 从左边出发，3.5s 打到分子链
      const hx = lerp(40, 600, prog(t, 2.4, 1.1));
      let d = '';
      for (let x = Math.max(40, hx - 520); x <= hx; x += 4) {
        const ph = ((x / 26 - t * 4) % 1 + 1) % 1;
        d += (d ? ' L' : 'M') + x.toFixed(1) + ',' + (CY + 36 * (Math.abs(ph * 2 - 1) * 2 - 1)).toFixed(1);
      }
      wave.setAttribute('d', d);
      wave.setAttribute('opacity', (prog(t, 2.4, 0.2) * (1 - prog(t, 3.7, 0.4))).toFixed(3));
      // 3.5s 断开
      const b = prog(t, 3.5, 0.5);
      leftG.setAttribute('transform', `translate(${-50 * b} ${(30 * (1 - prog(t, 1.7, 0.4)) + 14 * b).toFixed(1)}) rotate(${-8 * b} 650 ${CY})`);
      rightG.setAttribute('transform', `translate(${50 * b} ${(30 * (1 - prog(t, 1.7, 0.4)) - 10 * b).toFixed(1)}) rotate(${8 * b} 875 ${CY})`);
      crack.setAttribute('opacity', (prog(t, 3.5, 0.15) * (1 - prog(t, 4.4, 0.4))).toFixed(3));
      lbE.update(t, 2.7);
      enter(avoid, t, 5.0);
      xx.update(t);
    },
  };
})();
