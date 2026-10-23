// 镜头 5｜一摸兜，巧克力化了。他不信邪，
// 画面：工作服口袋特写，雷达的微波从左边过来，兜里的巧克力慢慢软化、往下淌。标注：巧克力化了
(() => {
  const DUR = 5;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <linearGradient id="cloth" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${C.g4}"/><stop offset="1" stop-color="${C.g3}"/></linearGradient>
 <linearGradient id="choco" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#4A2F22"/><stop offset="0.5" stop-color="#6B4532"/><stop offset="1" stop-color="#3E271C"/></linearGradient>`);

  const scene = el('g', {}, svg);
  // 衣服
  el('rect', { x: 420, y: 470, width: 700, height: 980, rx: 40, fill: 'url(#cloth)' }, scene);
  el('path', { d: 'M470,470 L470,1450', stroke: C.g2, 'stroke-width': 5, opacity: 0.6 }, scene);
  for (const by of [620, 900, 1180]) { el('circle', { cx: 492, cy: by, r: 14, fill: C.g2 }, scene); el('circle', { cx: 492, cy: by, r: 6, fill: C.g4 }, scene); }
  // 巧克力（上半截露在兜外）
  const choco = el('path', { fill: 'url(#choco)' }, scene);
  const chocoLines = el('path', { fill: 'none', stroke: '#2E1D15', 'stroke-width': 4, opacity: 0.7 }, scene);
  // 口袋
  el('rect', { x: 540, y: 830, width: 380, height: 360, rx: 18, fill: C.g5 }, scene);
  el('rect', { x: 556, y: 846, width: 348, height: 328, rx: 12, fill: 'none', stroke: C.g6, 'stroke-width': 3, 'stroke-dasharray': '12 9' }, scene);
  el('rect', { x: 540, y: 826, width: 380, height: 12, rx: 6, fill: C.g6, opacity: 0.6 }, scene);
  // 往下淌的巧克力
  const drips = [[630, 1.0], [705, 0.7], [790, 0.85]].map(([x, k]) => ({ x, k, p: el('path', { fill: '#5A3A2A' }, scene) }));

  // 微波：从左边过来
  const waves = [700, 770].map((y, i) => el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 4, opacity: i ? 0.7 : 1, filter: 'url(#soft)' }, svg));
  const lb = label(svg, { px: 705, py: 925, tx: 560, ty: 1330, text: '巧克力化了', anchor: 'start' });

  const xx = xingxing(svg, {
    x: 215, y: 1440, h: 540,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.4, pose: 'surprise' }, { t: 3.2, pose: 'talk' }],
    marks: [{ t: 1.5, type: '!', dur: 1.4 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      const m = prog(t, 0.6, 2.8);            // 融化进度
      const top = 640 + 70 * m, bulge = 14 * m;
      choco.setAttribute('d', `M${590 - bulge},840 L${590 - bulge * 0.5},${top + 30} Q${600},${top - 10 * (1 - m)} ${690},${top + 18 * m} Q${780},${top - 10 * (1 - m)} ${790 + bulge * 0.5},${top + 30} L${790 + bulge},840 Z`);
      chocoLines.setAttribute('d', `M690,${top + 30} L690,830 M590,${(top + 840) / 2 + 10} L790,${(top + 840) / 2 + 10}`);
      chocoLines.setAttribute('opacity', (0.7 * (1 - m)).toFixed(2));
      drips.forEach(({ x, k, p }) => {
        const L = 150 * k * prog(t, 1.0, 3.0), w = 11 + 3 * k;
        p.setAttribute('d', `M${x - w},826 L${x - w * 0.8},${826 + L} A${w},${w} 0 0 0 ${x + w * 0.8},${826 + L} L${x + w},826 Z`);
      });
      waves.forEach((w, i) => w.setAttribute('d', sinePath(40, 520, 700 + i * 70, 16, 70, t * 4 + i)));
      lb.update(t, 2.0);
      xx.update(t);
    },
  };
})();
