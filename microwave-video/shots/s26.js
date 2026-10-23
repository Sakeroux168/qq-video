// 镜头 26｜第三件，也是最多人中招的：热不透。外面烫嘴，里头冰凉。
// 画面：牌 ③ 翻开"热不透"（橙框高亮）；一碗饭剖面像热成像：外圈橙、中心青。标注：外面烫嘴 / 里头冰凉
(() => {
  const DUR = 6;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="thermo" cx="50%" cy="60%" r="60%"><stop offset="0" stop-color="${C.cyan}"/><stop offset="0.35" stop-color="#3A8FC0"/><stop offset="0.6" stop-color="#C77A3A"/><stop offset="1" stop-color="${C.orange}"/></radialGradient>`);
  const head = title(svg, 540, 330, [['③', C.orange], [' 热不透', C.white]]);

  const card = playingCard(svg, {
    cx: 540, cy: 900, w: 300, h: 420, back: '3', backSize: 170,
    front(g) { text(g, 0, 30, '热不透', { size: 80, font: FONT.heavy, color: C.g1 }); },
  });

  // 剖面碗：碗壁 + 热成像的饭
  const BX = 640, BY = 860;
  const bowl = el('g', {}, svg);
  const clip = el('clipPath', { id: 'riceCut' }, svg);
  el('path', { d: `M${BX - 260},${BY} Q${BX - 255},${BY - 190} ${BX},${BY - 200} Q${BX + 255},${BY - 190} ${BX + 260},${BY} Q${BX + 240},${BY + 170} ${BX},${BY + 175} Q${BX - 240},${BY + 170} ${BX - 260},${BY} Z`}, clip);
  const thermo = el('rect', { x: BX - 270, y: BY - 210, width: 540, height: 400, fill: 'url(#thermo)', 'clip-path': 'url(#riceCut)' }, bowl);
  const cold = el('rect', { x: BX - 270, y: BY - 210, width: 540, height: 400, fill: '#3A8FC0', 'clip-path': 'url(#riceCut)' }, bowl);
  el('path', { d: `M${BX - 290},${BY} Q${BX - 270},${BY + 200} ${BX},${BY + 205} Q${BX + 270},${BY + 200} ${BX + 290},${BY} L${BX + 260},${BY} Q${BX + 240},${BY + 170} ${BX},${BY + 175} Q${BX - 240},${BY + 170} ${BX - 260},${BY} Z`, fill: 'url(#bowl)' }, bowl);
  const lbHot = label(svg, { px: BX + 210, py: BY - 80, tx: 1040, ty: 560, text: [['外面', C.white], ['烫嘴', C.orange]], anchor: 'end' });
  const lbCold = label(svg, { px: BX, py: BY + 40, tx: 640, ty: 1240, text: [['里头', C.white], ['冰凉', C.cyan]], anchor: 'start' });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'point' }, { t: 1.8, pose: 'talk' }, { t: 3.4, pose: 'surprise' }, { t: 4.8, pose: 'think' }],
    marks: [{ t: 0.3, type: '!', dur: 1.2 }, { t: 3.5, type: 'sweat', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.1);
      card.setFlip(prog(t, 0.3, 0.6));
      card.hi.setAttribute('opacity', prog(t, 0.9, 0.3));
      const co = prog(t, 1.6, 0.35);
      card.move(540, 900 - 40 * co, 1 - 0.1 * co, 1 - co);
      enter(bowl, t, 1.8);
      // 热成像从全青慢慢“热”到外圈橙
      cold.setAttribute('opacity', (1 - prog(t, 2.0, 1.4)).toFixed(3));
      lbHot.update(t, 2.6);
      lbCold.update(t, 3.4);
      xx.update(t);
    },
  };
})();
