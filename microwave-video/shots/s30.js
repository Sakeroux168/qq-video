// 镜头 30｜用微波炉，宁可多看一眼，也不能坏了规矩。规矩守住了，热是热得快了点，但吃了不烧心。
// 画面：一碗热透冒着热气的饭，旁边立一块小木牌"规矩"；最后大字"吃了不烧心"。星星用教鞭点木牌。
(() => {
  const DUR = 7;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8A6A4A"/><stop offset="1" stop-color="#5E4630"/></linearGradient>`);
  const head = title(svg, 540, 330, [['不能坏了', C.white], ['规矩', C.orange]]);

  const BX = 560, BY = 900;
  const bowl = riceBowl(svg, BX, BY, 1.4);
  const st = steam(svg, [BX - 70, BX, BX + 70], BY - 130, 120, '#FFFFFF', 0.4);
  // 木牌
  const sign = el('g', {}, svg);
  const SX = 870, SY = 760;
  el('rect', { x: SX - 12, y: SY + 40, width: 24, height: 230, fill: '#5E4630' }, sign);
  el('rect', { x: SX - 110, y: SY - 80, width: 220, height: 150, rx: 12, fill: 'url(#wood)' }, sign);
  el('rect', { x: SX - 98, y: SY - 68, width: 196, height: 126, rx: 8, fill: 'none', stroke: '#3E2C1C', 'stroke-width': 4 }, sign);
  text(sign, SX, SY + 30, '规矩', { size: 84, font: FONT.heavy, color: '#F6EBDD' });
  const big = el('g', {}, svg);
  text(big, 680, 1180, [['吃了', C.white], ['不烧心', C.cyan]], { size: 110, font: FONT.heavy });

  const xx = xingxing(svg, {
    x: 170, y: 1440, h: 470,
    cues: [{ t: 0, pose: 'point' }, { t: 3.4, pose: 'talk' }, { t: 4.6, pose: 'happy' }],
    marks: [{ t: 0.4, type: '!', dur: 1.3 }, { t: 4.7, type: 'heart', dur: 1.5 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.1);
      st.update(t);
      popIn(sign, t, 0.5, SX, SY + 200, 0.4, 0.9);
      sign.setAttribute('transform', sign.getAttribute('transform') + ` rotate(${(1.5 * Math.sin(t * 1.6)).toFixed(2)} ${SX} ${SY + 270})`);
      enter(big, t, 4.4);
      xx.update(t);
    },
  };
})();
