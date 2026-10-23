// 镜头 29｜总结一下：微波炉没辐射，放心用。真正要防的是三样：盒子、鸡蛋、热不透。
// 画面：微波炉 + 青色 ✓"没辐射"；三张牌翻开排成一排：塑料盒 / 带壳鸡蛋 / 热不透（橙框）。
(() => {
  const DUR = 7;
  const { svg } = setupStage();
  const head1 = title(svg, 540, 330, [['微波炉', C.white], ['没辐射', C.cyan]]);
  const head2 = title(svg, 540, 330, [['真正要防', C.orange], [' 三样', C.white]]);

  const top = el('g', {}, svg);
  const mw = microwave(top, { x: 380, y: 450, s: 0.55 });
  const ok = el('g', {}, top);
  checkIcon(ok, 900, 520, 50);

  const CX = [330, 600, 870];
  const names = ['塑料盒', '带壳鸡蛋', '热不透'];
  const cards = CX.map((x, i) => playingCard(svg, {
    cx: x, cy: 900, w: 250, h: 350, back: String(i + 1), backSize: 150,
    front(g) {
      text(g, 0, -70, ['①', '②', '③'][i], { size: 90, font: FONT.heavy, color: C.orange });
      text(g, 0, 60, names[i], { size: names[i].length > 3 ? 54 : 64, font: FONT.heavy, color: C.g1 });
    },
  }));

  const xx = xingxing(svg, {
    x: 160, y: 1440, h: 440,
    cues: [{ t: 0, pose: 'thumb' }, { t: 2.6, pose: 'talk' }, { t: 4.4, pose: 'point' }],
    marks: [{ t: 0.3, type: 'spark', dur: 1.4 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head1.update(t, 0.1);
      head1.g.setAttribute('opacity', Math.min(+head1.g.getAttribute('opacity'), 1 - prog(t, 2.6, 0.25)));
      head2.update(t, 2.85);
      mw.update(t, { on: 1, display: '1:30' });
      popIn(ok, t, 0.6, 900, 520, 0.35, 0.85);
      // 2.8s 后微波炉区淡一点，突出三张牌
      top.setAttribute('opacity', (1 - 0.5 * prog(t, 2.8, 0.4)).toFixed(3));
      cards.forEach((c, i) => {
        const p = prog(t, 2.9 + i * 0.15, 0.35);
        c.move(CX[i], 900 + 50 * (1 - p), 1, p);
        c.setFlip(prog(t, 3.6 + i * 0.6, 0.45));
        c.hi.setAttribute('opacity', i === 2 ? prog(t, 5.4, 0.3) : 0);
      });
      xx.update(t);
    },
  };
})();
