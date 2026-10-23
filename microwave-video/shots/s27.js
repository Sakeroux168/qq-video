// 镜头 27｜因为微波在炉子里分布不均匀，有的地方热、有的地方冷，所以里面才要装个转盘。
// 画面：俯视炉膛，冷热斑块（橙=热点，青=冷点）固定不动；转盘带着饭碗转，依次经过热点。标注：冷热不均 / 转盘
(() => {
  const DUR = 7;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="hot" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="${C.orange}" stop-opacity="0.75"/><stop offset="1" stop-color="${C.orange}" stop-opacity="0"/></radialGradient>
 <radialGradient id="cold" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="${C.cyan}" stop-opacity="0.55"/><stop offset="1" stop-color="${C.cyan}" stop-opacity="0"/></radialGradient>`);
  const head = title(svg, 540, 330, [['微波', C.cyan], ['分布不均', C.white]]);

  const CX = 690, CY = 820;
  // 炉膛（俯视）
  el('rect', { x: CX - 350, y: CY - 300, width: 700, height: 600, rx: 30, fill: '#1E1A16', stroke: C.g4, 'stroke-width': 10 }, svg);
  const cav = el('clipPath', { id: 'cav' }, svg);
  el('rect', { x: CX - 345, y: CY - 295, width: 690, height: 590, rx: 26 }, cav);
  const spotsC = el('g', { 'clip-path': 'url(#cav)' }, svg);
  const spots = el('g', {}, spotsC);
  [[-220, -190, 'hot', 150], [210, -150, 'cold', 150], [-200, 190, 'cold', 140], [230, 200, 'hot', 150], [0, 0, 'hot', 110], [-40, -260, 'cold', 110]].forEach(([dx, dy, k, r]) =>
    el('circle', { cx: CX + dx, cy: CY + dy, r, fill: `url(#${k})` }, spots));
  // 转盘 + 饭碗（俯视）
  const plate = el('g', {}, svg);
  el('circle', { cx: CX, cy: CY, r: 250, fill: '#FFFFFF', opacity: 0.1 }, plate);
  el('circle', { cx: CX, cy: CY, r: 250, fill: 'none', stroke: C.g6, 'stroke-width': 5 }, plate);
  const rot = el('g', {}, plate);
  // 饭碗放在转盘偏外的位置，转起来就会经过不同斑块
  el('circle', { cx: CX + 140, cy: CY, r: 92, fill: 'url(#bowl)' }, rot);
  el('circle', { cx: CX + 140, cy: CY, r: 74, fill: 'url(#rice)' }, rot);
  el('path', { d: `M${CX - 200},${CY} A200,200 0 0 1 ${CX - 140},${CY - 141}`, fill: 'none', stroke: C.g6, 'stroke-width': 4 }, rot);
  const turnArrow = arcArrow(svg, CX, CY, 290, 200, 290, C.cyan, 6, 22);
  const lbSpot = label(svg, { px: CX - 220, py: CY - 190, tx: 60, ty: 500, text: '冷热不均', anchor: 'start' });
  const lbPlate = label(svg, { px: CX + 177, py: CY + 177, tx: 1040, ty: 1250, text: '转盘', anchor: 'end' });

  const xx = xingxing(svg, {
    x: 170, y: 1440, h: 470,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.6, pose: 'think' }, { t: 3.4, pose: 'point' }, { t: 5.2, pose: 'thumb' }],
    marks: [{ t: 1.7, type: '?', dur: 1.4 }, { t: 3.5, type: 'spark', dur: 1.2 }, { t: 5.3, type: 'spark', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.1);
      spots.setAttribute('opacity', prog(t, 0.4, 0.6));
      // 斑块轻微呼吸
      spots.setAttribute('transform', `translate(${CX} ${CY}) scale(${(1 + 0.02 * Math.sin(t * 2)).toFixed(4)}) translate(${-CX} ${-CY})`);
      lbSpot.update(t, 1.2);
      const ang = 50 * Math.max(0, t - 2.6);
      rot.setAttribute('transform', `rotate(${ang.toFixed(2)} ${CX} ${CY})`);
      turnArrow.setAttribute('opacity', prog(t, 2.6, 0.4));
      lbPlate.update(t, 3.2);
      xx.update(t);
    },
  };
})();
