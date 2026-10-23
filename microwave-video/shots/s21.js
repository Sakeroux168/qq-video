// 镜头 21｜第一件：装饭的盒子。不耐热的塑料盒一热就软塌，跟世界杯开幕式那个漏气的大力神杯一个样，里面的东西还可能跑进饭里。
// 画面：牌 ① 翻开"塑料盒"；塑料盒受热软塌变形，旁边一个泛化的奖杯轮廓同步漏气瘪下去；几道细箭头从盒壁指向饭。标注：一热就软塌 / 跑进饭里
(() => {
  const DUR = 9;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <linearGradient id="plastic" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7F93A6" stop-opacity="0.35"/><stop offset="0.5" stop-color="#C9D6E0" stop-opacity="0.35"/><stop offset="1" stop-color="#71879B" stop-opacity="0.35"/></linearGradient>
 <linearGradient id="trophy" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${C.g5}"/><stop offset="0.5" stop-color="${C.g7}"/><stop offset="1" stop-color="${C.g5}"/></linearGradient>`);
  const head = title(svg, 540, 330, [['①', C.orange], [' 塑料盒', C.white]]);

  // 翻牌（开场）
  const card = playingCard(svg, {
    cx: 540, cy: 900, w: 300, h: 420, back: '1', backSize: 170,
    front(g) { text(g, 0, 30, '塑料盒', { size: 76, font: FONT.heavy, color: C.g1 }); },
  });

  // 塑料盒 + 饭（变形用路径插值）
  const box = el('g', {}, svg);
  const BX = 640, BY = 1080;
  const food = el('path', { fill: 'url(#rice)' }, box);
  const veg = el('g', {}, box);
  const vegs = [[-120, '#6E9A4E'], [-50, '#C9703A'], [30, '#6E9A4E'], [100, '#C9703A'], [-10, '#8C5A3A']].map(([dx, c]) => ({ dx, e: el('ellipse', { rx: 22, ry: 12, fill: c }, veg) }));
  const body = el('path', { fill: 'url(#plastic)', stroke: '#DDE6EE', 'stroke-width': 3 }, box);
  const lid = el('path', { fill: 'url(#plastic)', stroke: '#DDE6EE', 'stroke-width': 3 }, box);
  const heatW = [0, 1].map(i => el('path', { fill: 'none', stroke: C.orange, 'stroke-width': 5, 'stroke-linecap': 'round', opacity: 0.8 }, box));
  const leaks = [-110, 0, 110].map(dx => arrow(box, BX + dx * 1.7, BY - 20, BX + dx, BY - 110, C.orange, 5, 18));
  const lbSoft = label(svg, { px: BX - 200, py: BY - 120, tx: 60, ty: 760, text: '一热就软塌', anchor: 'start' });
  const lbLeak = label(svg, { px: BX + 60, py: BY - 70, tx: 1040, ty: 1300, text: '跑进饭里', anchor: 'end' });

  // 泛化的奖杯轮廓（不画任何真实赛事标志）
  const troO = el('g', { transform: `translate(${880} ${760}) scale(1.2) translate(-880 -760)` }, svg);
  const tro = el('g', {}, troO);
  const TX = 880, TY = 760;
  const trophy = el('path', { fill: 'url(#trophy)' }, tro);
  el('rect', { x: TX - 50, y: TY - 30, width: 100, height: 30, rx: 6, fill: C.g4 }, tro);
  const troCap = text(tro, TX, TY + 75, '漏气奖杯', { size: 64, color: C.g7 });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'point' }, { t: 2.0, pose: 'talk' }, { t: 3.4, pose: 'surprise' }, { t: 5.2, pose: 'scared' }, { t: 7.0, pose: 'talk' }],
    marks: [{ t: 3.5, type: '!', dur: 1.3 }, { t: 5.3, type: 'sweat', dur: 1.4 }],
  });

  const L = (a, b, p) => a + (b - a) * p;
  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.1);
      // 0.3 翻牌，1.6 牌退场
      card.setFlip(prog(t, 0.3, 0.6));
      const co = prog(t, 1.6, 0.35);
      card.move(540, 900 - 40 * co, 1 - 0.1 * co, 1 - co);
      enter(box, t, 1.8);
      // 软塌进度 m：3.0s 起
      const m = prog(t, 3.0, 2.2);
      const w = 210, h = 190;
      // 盒身：底部变宽、上沿下陷、侧壁外鼓
      const top = BY - h + 45 * m, sag = 45 * m, bulge = 32 * m;
      body.setAttribute('d', `M${BX - w},${top} Q${BX - w - bulge},${(top + BY) / 2} ${BX - w - 10 * m},${BY} L${BX + w + 10 * m},${BY} Q${BX + w + bulge},${(top + BY) / 2} ${BX + w},${top + sag * 0.5} Q${BX},${top + sag} ${BX - w},${top} Z`);
      food.setAttribute('d', `M${BX - w + 14},${top + 6} Q${BX},${top - 70 + sag} ${BX + w - 14},${top + 6 + sag * 0.5} L${BX + w - 14},${BY - 12} L${BX - w + 14},${BY - 12} Z`);
      vegs.forEach(({ dx, e }) => { e.setAttribute('cx', BX + dx); e.setAttribute('cy', (top - 40 + sag * 0.8 + Math.abs(dx) * 0.18).toFixed(1)); });
      lid.setAttribute('d', `M${BX - w - 10},${top - 6} Q${BX},${top - 22 + sag * 1.2} ${BX + w + 10},${top - 6 + sag * 0.5} L${BX + w + 10},${top + 6 + sag * 0.5} Q${BX},${top - 10 + sag * 1.2} ${BX - w - 10},${top + 6} Z`);
      heatW.forEach((p, i) => p.setAttribute('d', sinePath(BX - 170, BX + 170, BY + 45 + i * 28, 9, 55, t * 4 + i)));
      heatW.forEach(p => p.setAttribute('opacity', (0.8 * prog(t, 2.4, 0.4)).toFixed(2)));
      leaks.forEach((a, i) => a.setAttribute('opacity', prog(t, 6.2 + i * 0.15, 0.35)));
      lbSoft.update(t, 4.2);
      lbLeak.update(t, 6.6);
      // 奖杯：和盒子同步瘪下去
      enter(tro, t, 3.6);
      const k = prog(t, 4.0, 2.0);
      trophy.setAttribute('d', `M${TX - 34},${TY - 30} L${TX - 16},${TY - 100} Q${TX - 85},${TY - 170} ${TX - 80},${TY - 260} L${TX + 80},${TY - 260} Q${TX + 85},${TY - 170} ${TX + 16},${TY - 100} L${TX + 34},${TY - 30} Z`);
      trophy.setAttribute('transform', `translate(${TX} ${TY - 30}) rotate(${(-14 * k).toFixed(2)}) scale(${(1 + 0.25 * k).toFixed(3)} ${(1 - 0.45 * k).toFixed(3)}) translate(${-TX} ${-(TY - 30)})`);
      troCap.setAttribute('opacity', Math.min(prog(t, 4.2, 0.4), 1 - prog(t, 6.2, 0.3)).toFixed(3));
      xx.update(t);
    },
  };
})();
