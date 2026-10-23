// 镜头 9｜老好人叫非电离辐射，像收音机、手机信号、你家WiFi，能量低得多。微波炉用的微波，就是这一类。
// 画面：一道舒缓的青色长波，收音机、手机、WiFi 路由器依次出现，最后微波炉加入并被圈出。标注：非电离辐射 / 能量低 / 微波炉也是
(() => {
  const DUR = 8;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['非电离辐射', C.cyan]]);
  const wave = el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 5, filter: 'url(#soft)' }, svg);
  const lbLow = label(svg, { px: 700, py: 520, tx: 720, ty: 650, text: '能量低', anchor: 'start' });

  const SHIFT = 'translate(40 0)';
  const cell = (cx, cy, cap) => { const o = el('g', { transform: SHIFT }, svg); const g = el('g', {}, o); text(g, cx, cy + 165, cap, { size: 64 }); return g; };
  // 收音机
  const radio = cell(500, 800, '收音机');
  el('path', { d: 'M440,720 L380,640', stroke: C.g6, 'stroke-width': 6, 'stroke-linecap': 'round' }, radio);
  el('rect', { x: 395, y: 715, width: 210, height: 140, rx: 22, fill: 'url(#metal)' }, radio);
  el('circle', { cx: 455, cy: 785, r: 44, fill: C.g2 }, radio);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) el('circle', { cx: 430 + i * 25, cy: 760 + j * 25, r: 5, fill: C.g5 }, radio);
  el('rect', { x: 520, y: 740, width: 62, height: 26, rx: 4, fill: '#0A0C0F' }, radio);
  el('circle', { cx: 551, cy: 815, r: 18, fill: C.g5 }, radio);
  // 手机
  const phone = cell(800, 800, '手机');
  el('rect', { x: 745, y: 700, width: 110, height: 200, rx: 20, fill: C.g2, stroke: C.g5, 'stroke-width': 4 }, phone);
  el('rect', { x: 755, y: 715, width: 90, height: 165, rx: 10, fill: '#16202B' }, phone);
  for (let i = 0; i < 4; i++) el('rect', { x: 870 + i * 16, y: 740 - i * 14, width: 10, height: 20 + i * 14, rx: 3, fill: C.cyan }, phone);
  // WiFi 路由器
  const wifi = cell(500, 1100, 'WiFi');
  el('rect', { x: 400, y: 1080, width: 200, height: 70, rx: 16, fill: 'url(#metal)' }, wifi);
  el('path', { d: 'M430,1080 L415,1000 M570,1080 L585,1000', stroke: C.g6, 'stroke-width': 8, 'stroke-linecap': 'round' }, wifi);
  for (let i = 0; i < 4; i++) el('circle', { cx: 440 + i * 25, cy: 1118, r: 5, fill: C.cyan }, wifi);
  for (const r of [24, 46, 68]) el('path', { d: `M${500 - r * 0.8},${1050 - r * 0.6} A${r},${r} 0 0 1 ${500 + r * 0.8},${1050 - r * 0.6}`, fill: 'none', stroke: C.cyan, 'stroke-width': 7, 'stroke-linecap': 'round' }, wifi);
  // 微波炉
  const mwG = cell(800, 1100, '微波炉');
  const mw = microwave(mwG, { x: 800 - 120, y: 1100 - 70, s: 0.28 });
  const ring = el('rect', { x: 695, y: 1005, width: 290, height: 300, rx: 26, fill: 'none', stroke: C.cyan, 'stroke-width': 5 }, svg);
  const lbMw = label(svg, { px: 960, py: 1305, tx: 1010, ty: 1410, text: '微波炉也是', anchor: 'end' });

  const xx = xingxing(svg, {
    x: 200, y: 1440, h: 520,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.0, pose: 'point' }, { t: 2.8, pose: 'talk' }, { t: 4.6, pose: 'thumb' }, { t: 6.2, pose: 'talk' }],
    marks: [{ t: 4.7, type: 'spark', dur: 1.4 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      wave.setAttribute('d', sinePath(40, 1040, 520, 34, 260, t * 1.6, 6));
      wave.setAttribute('opacity', prog(t, 0.3, 0.6));
      enter(radio, t, 1.0); enter(phone, t, 1.6); enter(wifi, t, 2.2);
      lbLow.update(t, 3.3);
      enter(mwG, t, 4.5);
      mw.update(t, { on: 1, display: '1:30' });
      ring.setAttribute('opacity', prog(t, 5.0, 0.4));
      lbMw.update(t, 5.2);
      xx.update(t);
    },
  };
})();
