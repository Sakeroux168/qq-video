// 镜头 24｜第二件：带壳的鸡蛋。蛋里的水一热变成蒸汽，壳又封得死死的，越憋越大，"砰"一下就炸了。
// 画面：牌 ② 翻开"带壳鸡蛋"；鸡蛋剖面，蒸汽箭头往外顶，压力表指针升高，蛋壳出现裂纹，"砰！"。标注：蒸汽 / 压力↑ / 砰！
(() => {
  const DUR = 7;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="shell" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#FFF6EA"/><stop offset="1" stop-color="#D9C6AE"/></radialGradient>
 <radialGradient id="yolk" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#FFD27A"/><stop offset="1" stop-color="#E39A2E"/></radialGradient>`);
  const head = title(svg, 540, 330, [['②', C.orange], [' 带壳鸡蛋', C.white]]);

  const card = playingCard(svg, {
    cx: 540, cy: 900, w: 300, h: 420, back: '2', backSize: 170,
    front(g) { text(g, 0, 30, '带壳鸡蛋', { size: 66, font: FONT.heavy, color: C.g1 }); },
  });

  const EX = 600, EY = 930;
  const egg = el('g', {}, svg);
  const eggIn = el('g', {}, egg);
  el('path', { d: `M${EX},${EY - 230} C${EX + 125},${EY - 230} ${EX + 172},${EY + 0} ${EX + 172},${EY + 80} C${EX + 166},${EY + 180} ${EX + 85},${EY + 210} ${EX},${EY + 210} C${EX - 85},${EY + 210} ${EX - 166},${EY + 180} ${EX - 172},${EY + 80} C${EX - 172},${EY + 0} ${EX - 125},${EY - 230} ${EX},${EY - 230} Z`, fill: 'url(#shell)' }, eggIn);
  el('path', { d: `M${EX},${EY - 200} C${EX + 109},${EY - 200} ${EX + 150},${EY + 0} ${EX + 150},${EY + 70} C${EX + 144},${EY + 157} ${EX + 74},${EY + 183} ${EX},${EY + 183} C${EX - 74},${EY + 183} ${EX - 144},${EY + 157} ${EX - 150},${EY + 70} C${EX - 150},${EY + 0} ${EX - 109},${EY - 200} ${EX},${EY - 200} Z`, fill: '#F6F2EA' }, eggIn);
  el('circle', { cx: EX, cy: EY + 40, r: 82, fill: 'url(#yolk)' }, eggIn);
  // 蒸汽箭头（向外顶）
  const arrows = [-50, 0, 50, 100, 150, 210, 260].map(a => {
    const r0 = 92, r1 = 140, rad = (a - 90) * Math.PI / 180;
    return arrow(eggIn, EX + r0 * Math.cos(rad), EY + 20 + r0 * 1.1 * Math.sin(rad), EX + r1 * Math.cos(rad), EY + 20 + r1 * 1.1 * Math.sin(rad), C.orange, 6, 20);
  });
  const crack = el('path', { d: `M${EX - 30},${EY - 222} L${EX - 8},${EY - 170} L${EX - 40},${EY - 130} L${EX - 5},${EY - 80} M${EX - 8},${EY - 170} L${EX + 30},${EY - 150}`, fill: 'none', stroke: C.g1, 'stroke-width': 6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, egg);
  const lbSteam = label(svg, { px: EX + 130, py: EY - 60, tx: 1040, ty: 640, text: '蒸汽', anchor: 'end' });

  // 压力表
  const gauge = el('g', {}, svg);
  const GX = 920, GY = 1170;
  el('circle', { cx: GX, cy: GY, r: 100, fill: C.g2, stroke: C.g5, 'stroke-width': 6 }, gauge);
  el('path', { d: `M${GX - 70},${GY + 40} A80,80 0 1 1 ${GX + 70},${GY + 40}`, fill: 'none', stroke: C.g5, 'stroke-width': 10 }, gauge);
  el('path', { d: `M${GX + 46},${GY - 62} A80,80 0 0 1 ${GX + 70},${GY + 40}`, fill: 'none', stroke: C.orange, 'stroke-width': 10 }, gauge);
  const needle = el('path', { d: `M${GX},${GY} L${GX},${GY - 70}`, stroke: C.white, 'stroke-width': 7, 'stroke-linecap': 'round' }, gauge);
  el('circle', { cx: GX, cy: GY, r: 12, fill: C.white }, gauge);
  text(gauge, GX, GY + 160, '压力↑', { size: 64, font: FONT.heavy, color: C.orange });
  const boom = el('g', {}, svg);
  text(boom, EX - 40, EY - 300, '砰！', { size: 150, font: FONT.heavy, color: C.orange });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'point' }, { t: 2.0, pose: 'talk' }, { t: 4.6, pose: 'scared' }],
    marks: [{ t: 4.7, type: '!', dur: 1.5 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.1);
      card.setFlip(prog(t, 0.3, 0.6));
      const co = prog(t, 1.6, 0.35);
      card.move(540, 900 - 40 * co, 1 - 0.1 * co, 1 - co);
      enter(egg, t, 1.8);
      // 蒸汽箭头逐渐变长变多
      const ps = prog(t, 2.5, 1.8);
      arrows.forEach((a, i) => a.setAttribute('opacity', prog(t, 2.5 + i * 0.12, 0.3)));
      // 鸡蛋随压力微微胀大、抖动
      const sw = 1 + 0.05 * ps, jit = t > 3.8 && t < 4.6 ? 3 * Math.sin(t * 60) : 0;
      eggIn.setAttribute('transform', `translate(${EX + jit} ${EY}) scale(${sw.toFixed(4)}) translate(${-EX} ${-EY})`);
      lbSteam.update(t, 2.6);
      enter(gauge, t, 2.4);
      const ang = -130 + 220 * prog(t, 2.6, 2.0);
      needle.setAttribute('transform', `rotate(${ang.toFixed(1)} ${GX} ${GY})`);
      crack.setAttribute('opacity', prog(t, 4.4, 0.1));
      popIn(boom, t, 4.5, EX, EY - 340, 0.2, 0.85);
      xx.update(t);
    },
  };
})();
