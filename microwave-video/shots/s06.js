// 镜头 6｜又抓了把玉米粒放过去，噼里啪啦，全成了爆米花。得，世界上第一台微波炉，就这么"炸"出来了。
// 画面：一排玉米粒依次膨开成爆米花（平稳放大，不做爆炸）→ 第一台微波炉（大柜子）。标注：爆米花 / 第一台微波炉
(() => {
  const DUR = 7;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="kernel" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#F0D27A"/><stop offset="1" stop-color="#B98A2E"/></radialGradient>
 <radialGradient id="pop" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#DCD4C2"/></radialGradient>`);

  // A：托盘 + 玉米粒
  const A = el('g', {}, svg);
  el('ellipse', { cx: 720, cy: 975, rx: 320, ry: 50, fill: C.g3 }, A);
  el('ellipse', { cx: 720, cy: 966, rx: 300, ry: 40, fill: C.g4 }, A);
  const XS = [500, 610, 720, 830, 940];
  const corns = XS.map((x, i) => {
    const k = el('g', {}, A);
    el('path', { d: `M${x},${890} Q${x - 38},${935} ${x - 24},${965} Q${x},${984} ${x + 24},${965} Q${x + 38},${935} ${x},${890} Z`, fill: 'url(#kernel)' }, k);
    const p = el('g', {}, A);
    const blobs = [[0, -28, 42], [-36, -6, 34], [36, -8, 35], [-14, 22, 31], [20, 20, 30], [0, -62, 26]];
    for (const [dx, dy, r] of blobs) el('circle', { cx: x + dx, cy: 920 + dy, r, fill: 'url(#pop)' }, p);
    return { k, p, x, t0: 1.0 + [0, 0.5, 0.2, 0.8, 0.35][i] * 2.2 };
  });
  const waves = [800, 860].map((y, i) => el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 4, opacity: i ? 0.7 : 1, filter: 'url(#soft)' }, A));
  const lbPop = label(A, { px: 720, py: 850, tx: 640, ty: 680, text: '爆米花' });

  // B：第一台微波炉（像冰箱一样高的大柜子）
  const B = el('g', {}, svg);
  const bx = 560, by = 520, bw = 380, bh = 820;
  el('ellipse', { cx: bx + bw / 2, cy: by + bh + 6, rx: 230, ry: 24, fill: '#000', opacity: 0.45 }, B);
  el('rect', { x: bx, y: by, width: bw, height: bh, rx: 18, fill: 'url(#metal)', filter: 'url(#shadow)' }, B);
  el('rect', { x: bx + 4, y: by + 4, width: bw - 8, height: 5, rx: 2, fill: '#FFFFFF', opacity: 0.18 }, B);
  el('rect', { x: bx + 40, y: by + 60, width: bw - 80, height: 230, rx: 12, fill: '#0B0E12' }, B);
  el('rect', { x: bx + 40, y: by + 60, width: bw - 80, height: 230, rx: 12, fill: 'url(#glass)' }, B);
  el('rect', { x: bx + 40, y: by + 330, width: bw - 80, height: 90, rx: 8, fill: C.g3 }, B);
  for (let i = 0; i < 4; i++) el('circle', { cx: bx + 90 + i * 66, cy: by + 375, r: 20, fill: 'url(#metal)', stroke: C.g2, 'stroke-width': 3 }, B);
  for (let i = 0; i < 6; i++) el('rect', { x: bx + 60, y: by + 470 + i * 50, width: bw - 120, height: 10, rx: 5, fill: C.g2, opacity: 0.7 }, B);
  const headB = title(B, 540, 330, [['第一台', C.white], ['微波炉', C.orange]]);

  const xx = xingxing(svg, {
    x: 215, y: 1440, h: 540,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.2, pose: 'surprise' }, { t: 2.9, pose: 'happy' }, { t: 4.4, pose: 'point' }, { t: 5.9, pose: 'talk' }],
    marks: [{ t: 1.3, type: '!', dur: 1.3 }, { t: 3.0, type: 'heart', dur: 1.2 }, { t: 4.5, type: 'spark', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      waves.forEach((w, i) => w.setAttribute('d', sinePath(40, 420, 800 + i * 60, 14, 70, t * 4 + i)));
      corns.forEach(({ k, p, x, t0 }) => {
        const q = prog(t, t0, 0.35);
        k.setAttribute('opacity', 1 - q);
        const s = 0.4 + 0.6 * q;
        p.setAttribute('opacity', q);
        p.setAttribute('transform', `translate(${x} 940) scale(${s.toFixed(3)}) translate(${-x} -940) translate(0 ${(-10 * Math.sin(Math.PI * q)).toFixed(1)})`);
      });
      lbPop.update(t, 2.4);
      const sw = prog(t, 3.9, 0.4);
      A.setAttribute('opacity', 1 - sw);
      B.setAttribute('opacity', sw);
      headB.update(t, 4.2);
      xx.update(t);
    },
  };
})();
