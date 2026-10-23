// 镜头 20｜好，重点来了，比辐射危险多了的三件事。
// 画面：三张扣着的牌 1 2 3 依次落到桌上，标题"重点来了"→"比辐射更危险"。
(() => {
  const DUR = 5;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="felt" cx="50%" cy="45%" r="60%"><stop offset="0" stop-color="#232A33"/><stop offset="1" stop-color="#12161B"/></radialGradient>`);
  el('ellipse', { cx: 640, cy: 960, rx: 620, ry: 380, fill: 'url(#felt)' }, svg);
  el('ellipse', { cx: 640, cy: 960, rx: 600, ry: 362, fill: 'none', stroke: C.cyan, 'stroke-width': 3, opacity: 0.5 }, svg);
  const head1 = title(svg, 540, 330, [['重点', C.orange], ['来了', C.white]]);
  const head2 = title(svg, 540, 330, [['比辐射', C.white], ['更危险', C.orange]]);
  const CX = [250, 540, 830];
  const cards = CX.map((x, i) => playingCard(svg, { cx: x, cy: 700, w: 240, h: 340, back: String(i + 1), backSize: 150 }));

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'point' }, { t: 1.8, pose: 'surprise' }, { t: 3.4, pose: 'talk' }],
    marks: [{ t: 0.1, type: '!', dur: 1.4 }, { t: 1.9, type: 'sweat', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head1.update(t, 0.1);
      head1.g.setAttribute('opacity', Math.min(+head1.g.getAttribute('opacity'), 1 - prog(t, 1.6, 0.25)));
      head2.update(t, 1.85);
      cards.forEach((c, i) => {
        const p = prog(t, 0.4 + i * 0.25, 0.4);
        c.move(CX[i], 700 - 80 * (1 - p), 1, p);
        c.setFlip(0);
        c.hi.setAttribute('opacity', 0);
      });
      xx.update(t);
    },
  };
})();
