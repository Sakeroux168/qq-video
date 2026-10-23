// 镜头 7｜一听"辐射"就腿软？其实辐射分两种：一个是狠角色，一个是老好人。
// 画面："辐射"大字 → 上移成标题，下面分成两栏：电离辐射=狠角色（橙，密集短波）/ 非电离辐射=老好人（青，舒缓长波）
(() => {
  const DUR = 6;
  const { svg } = setupStage();

  const big = el('g', {}, svg);
  const bigT = text(big, 0, 0, [['辐射', C.white], ['？', C.orange]], { size: 220, font: FONT.heavy });
  const qMark = bigT.lastChild;

  function panel(x, w, color, name, nick, wavePath) {
    const g = el('g', {}, svg);
    el('rect', { x, y: 460, width: w, height: 420, rx: 22, fill: C.bgHi, stroke: C.g3, 'stroke-width': 2 }, g);
    el('rect', { x, y: 460, width: w, height: 10, rx: 5, fill: color }, g);
    text(g, x + w / 2, 560, name, { size: 72, font: FONT.bold });
    const wave = el('path', { fill: 'none', stroke: color, 'stroke-width': 6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g);
    text(g, x + w / 2, 835, nick, { size: 96, font: FONT.heavy, color });
    return { g, wave, x, w };
  }
  const L = panel(70, 450, C.orange, '电离辐射', '狠角色');
  const R = panel(560, 450, C.cyan, '非电离辐射', '老好人');

  const xx = xingxing(svg, {
    x: 215, y: 1440, h: 540,
    cues: [{ t: 0, pose: 'scared' }, { t: 1.8, pose: 'talk' }, { t: 3.4, pose: 'point' }, { t: 4.7, pose: 'happy' }],
    marks: [{ t: 0.3, type: 'sweat', dur: 1.3 }, { t: 4.8, type: 'heart', dur: 1.0 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      // "辐射"：先在中间放大，1.8s 起缩到顶部当标题
      const p = prog(t, 1.8, 0.5);
      const s = lerp(1, 0.55, p), cx = 540, cy = lerp(780, 330, p);
      big.setAttribute("transform", `translate(${cx + 110 * s * p} ${cy}) scale(${s})`);
      big.setAttribute('opacity', prog(t, 0, 0.3));
      qMark.setAttribute('fill-opacity', (prog(t, 0.4, 0.3) * (1 - p)).toFixed(3));
      // 两栏依次出现
      enter(L.g, t, 2.1);
      enter(R.g, t, 2.3);
      // 左：密集锯齿短波；右：舒缓长波
      let d = '';
      for (let x = L.x + 40; x <= L.x + L.w - 40; x += 4) {
        const ph = ((x - L.x) / 28 - t * 3) % 1;
        const y = 690 + 45 * (Math.abs(((ph + 1) % 1) * 2 - 1) * 2 - 1);
        d += (d ? ' L' : 'M') + x + ',' + y.toFixed(1);
      }
      L.wave.setAttribute('d', d);
      R.wave.setAttribute('d', sinePath(R.x + 40, R.x + R.w - 40, 690, 38, 190, t * 1.5, 5));
      xx.update(t);
    },
  };
})();
