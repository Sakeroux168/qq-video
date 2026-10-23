// 镜头 3｜先说结论：牌没有问题，饭没有辐射，放心吃。但是，有三件事比辐射危险多了……我估计你家就中过招。
// 画面：牌翻开是青色 ✓"没有辐射" → 三张扣着的牌 1 2 3，第 3 张亮起。标注：牌没有问题 / 比辐射更危险
(() => {
  const DUR = 8;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="felt" cx="50%" cy="45%" r="60%"><stop offset="0" stop-color="#232A33"/><stop offset="1" stop-color="#12161B"/></radialGradient>`);
  el('ellipse', { cx: 640, cy: 960, rx: 620, ry: 380, fill: 'url(#felt)' }, svg);
  el('ellipse', { cx: 640, cy: 960, rx: 600, ry: 362, fill: 'none', stroke: C.cyan, 'stroke-width': 3, opacity: 0.5 }, svg);
  el('ellipse', { cx: 640, cy: 930, rx: 330, ry: 230, fill: '#FFFFFF', opacity: 0.04 }, svg);

  const big = playingCard(svg, {
    cx: 640, cy: 930, w: 380, h: 540, back: '辐射？', backSize: 100,
    front(g) {
      checkIcon(g, 0, -60, 110);
      text(g, 0, 150, '没有辐射', { size: 72, font: FONT.heavy, color: C.g1 });
    },
  });
  const eat = el('g', {}, svg);
  text(eat, 640, 1310, '放心吃', { size: 84, font: FONT.heavy, color: C.cyan });
  const head1 = title(svg, 540, 400, [['牌', C.white], ['没有问题', C.cyan]]);

  const CX = [250, 540, 830];
  const cards = CX.map((x, i) => playingCard(svg, { cx: x, cy: 700, w: 240, h: 340, back: String(i + 1), backSize: 150 }));
  const head2 = title(svg, 540, 400, [['比辐射', C.white], ['更危险', C.orange]]);

  const xx = xingxing(svg, {
    x: 215, y: 1440, h: 540,
    cues: [{ t: 0, pose: 'thumb' }, { t: 3.6, pose: 'talk' }, { t: 6.2, pose: 'surprise' }, { t: 7.4, pose: 'talk' }],
    marks: [{ t: 0.9, type: 'spark', dur: 1.6 }, { t: 6.3, type: '!', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      // 0.3s 翻牌
      big.setFlip(prog(t, 0.3, 0.7));
      head1.update(t, 0.9);
      enter(eat, t, 2.2);
      eat.setAttribute('opacity', Math.min(+eat.getAttribute('opacity'), 1 - prog(t, 3.6, 0.4)));
      // 3.6s 起换成三张牌
      const o = prog(t, 3.6, 0.4);
      big.move(640, 930 - 40 * o, 1 - 0.1 * o, 1 - o);
      head1.g.setAttribute('opacity', Math.min(+head1.g.getAttribute('opacity'), 1 - o));
      cards.forEach((c, i) => {
        const p = prog(t, 4.0 + i * 0.2, 0.4);
        const lift = i === 2 ? 26 * prog(t, 6.2, 0.4) : 0;
        c.move(CX[i], 700 + 60 * (1 - p) - lift, 1, p);
        c.setFlip(0);
      });
      cards[2].hi.setAttribute('opacity', prog(t, 6.2, 0.4));
      head2.update(t, 4.4);
      xx.update(t);
    },
  };
})();
