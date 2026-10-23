// 镜头 12｜那它咋把饭热的？饭菜里都有水，水分子就像一根根小磁针。
// 画面：放大圈里的水分子，每个分子上叠出一根小磁针（橙/白两头），方向跟分子一致。标注：水分子 ≈ 小磁针
(() => {
  const DUR = 5;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['水分子 ', C.white], ['≈', C.cyan], [' 小磁针', C.white]]);

  const LX = 660, LY = 800;
  const L = lens(svg, LX, LY, 270);
  const MOLS = [[-110, -95, 20], [115, -25, 150], [-15, 135, 260]];
  const mols = MOLS.map(([dx, dy, a]) => {
    const m = waterMol(L.inner, LX + dx, LY + dy, 1.35);
    const n = el('g', {}, L.inner);
    el('path', { d: 'M0,-20 L105,0 L0,20 Z', fill: C.orange }, n);
    el('path', { d: 'M0,-20 L-105,0 L0,20 Z', fill: C.white }, n);
    el('circle', { cx: 0, cy: 0, r: 9, fill: C.g2 }, n);
    return { m, n, x: LX + dx, y: LY + dy, a };
  });
  const lbW = label(svg, { px: LX - 115 - 30, py: LY - 85 - 40, tx: 330, ty: 560, text: '水分子', anchor: 'end' });

  const xx = xingxing(svg, {
    x: 200, y: 1440, h: 520,
    cues: [{ t: 0, pose: 'think' }, { t: 1.8, pose: 'talk' }, { t: 3.0, pose: 'point' }],
    marks: [{ t: 0.1, type: '?', dur: 1.5 }, { t: 3.1, type: 'spark', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 1.8);
      popIn(L.g, t, 0, LX, LY, 0.4, 0.95);
      L.g.setAttribute('opacity', 1);
      mols.forEach(({ m, n, x, y, a }, i) => {
        const ang = a + 6 * Math.sin(t * 1.7 + i * 2);
        m.rot(ang);
        const p = prog(t, 2.2 + i * 0.2, 0.4);
        n.setAttribute('transform', `translate(${x} ${y}) rotate(${ang.toFixed(2)}) scale(${(0.9 + 0.1 * p).toFixed(3)})`);
        n.setAttribute('opacity', (0.9 * p).toFixed(3));
      });
      lbW.update(t, 0.8);
      xx.update(t);
    },
  };
})();
