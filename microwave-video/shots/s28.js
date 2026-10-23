// 镜头 28｜中间没热透，细菌可能还活着。热到一半，拿出来翻一翻、搅一搅，再接着热。
// 画面：剩菜剖面中心是冷区（青），里面有几个简笔细菌；勺子搅一搅，整碗变匀变暖，细菌消失。标注：细菌 / 热到一半 翻一翻
(() => {
  const DUR = 7;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="thermo" cx="50%" cy="60%" r="60%"><stop offset="0" stop-color="${C.cyan}"/><stop offset="0.35" stop-color="#3A8FC0"/><stop offset="0.6" stop-color="#C77A3A"/><stop offset="1" stop-color="${C.orange}"/></radialGradient>`);
  const headA = title(svg, 540, 330, [['中间', C.white], ['有细菌', C.orange]]);
  const headB = title(svg, 540, 330, [['热到一半 ', C.white], ['翻一翻', C.cyan]]);

  const BX = 660, BY = 860;
  const bowl = el('g', {}, svg);
  const clip = el('clipPath', { id: 'riceCut' }, svg);
  el('path', { d: `M${BX - 260},${BY} Q${BX - 255},${BY - 190} ${BX},${BY - 200} Q${BX + 255},${BY - 190} ${BX + 260},${BY} Q${BX + 240},${BY + 170} ${BX},${BY + 175} Q${BX - 240},${BY + 170} ${BX - 260},${BY} Z` }, clip);
  el('rect', { x: BX - 270, y: BY - 210, width: 540, height: 400, fill: 'url(#thermo)', 'clip-path': 'url(#riceCut)' }, bowl);
  const even = el('rect', { x: BX - 270, y: BY - 210, width: 540, height: 400, fill: C.orange, 'clip-path': 'url(#riceCut)', opacity: 0 }, bowl);
  el('path', { d: `M${BX - 290},${BY} Q${BX - 270},${BY + 200} ${BX},${BY + 205} Q${BX + 270},${BY + 200} ${BX + 290},${BY} L${BX + 260},${BY} Q${BX + 240},${BY + 170} ${BX},${BY + 175} Q${BX - 240},${BY + 170} ${BX - 260},${BY} Z`, fill: 'url(#bowl)' }, bowl);
  // 简笔细菌：圆角胶囊 + 小鞭毛
  const bugs = [[-60, 20, 20], [50, 50, -30], [10, -40, 60], [-20, 100, -10]].map(([dx, dy, a], i) => {
    const g = el('g', {}, svg);
    const b = el('g', {}, g);
    el('rect', { x: -26, y: -13, width: 52, height: 26, rx: 13, fill: '#E9EDF1', stroke: C.g1, 'stroke-width': 3 }, b);
    el('path', { d: 'M26,0 Q38,-8 46,2 Q52,10 60,4', fill: 'none', stroke: '#E9EDF1', 'stroke-width': 4, 'stroke-linecap': 'round' }, b);
    el('circle', { cx: -8, cy: -2, r: 3, fill: C.g1 }, b);
    el('circle', { cx: 6, cy: -2, r: 3, fill: C.g1 }, b);
    return { g, b, x: BX + dx, y: BY + dy, a, i };
  });
  const lbBug = label(svg, { px: BX - 60, py: BY + 5, tx: 60, ty: 560, text: '细菌', anchor: 'start' });
  // 勺子
  const spoon = el('g', {}, svg);
  el('path', { d: 'M0,0 L0,-300', stroke: C.g7, 'stroke-width': 18, 'stroke-linecap': 'round' }, spoon);
  el('ellipse', { cx: 0, cy: 20, rx: 36, ry: 50, fill: C.g7 }, spoon);
  const swirl = el('path', { fill: 'none', stroke: C.white, 'stroke-width': 5, 'stroke-linecap': 'round', opacity: 0 }, svg);
  const ok = el('g', {}, svg);
  checkIcon(ok, 520, 1200, 44);
  text(ok, 590, 1227, '再接着热', { size: 76, font: FONT.heavy, color: C.cyan, anchor: 'start' });

  const xx = xingxing(svg, {
    x: 170, y: 1440, h: 470,
    cues: [{ t: 0, pose: 'scared' }, { t: 2.2, pose: 'talk' }, { t: 3.0, pose: 'point' }, { t: 5.2, pose: 'thumb' }],
    marks: [{ t: 0.3, type: 'sweat', dur: 1.6 }, { t: 5.3, type: 'spark', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      headA.update(t, 0.1);
      headA.g.setAttribute('opacity', Math.min(+headA.g.getAttribute('opacity'), 1 - prog(t, 2.6, 0.25)));
      headB.update(t, 2.85);
      // 搅拌：3.0~4.8s
      const stir = prog(t, 3.0, 1.8, 0);
      const mix = prog(t, 3.2, 1.6);
      even.setAttribute('opacity', (0.85 * mix).toFixed(3));
      const sa = (t - 3.0) * 7;
      const sx = BX + 120 * Math.cos(sa), sy = BY + 30 + 40 * Math.sin(sa);
      spoon.setAttribute('transform', `translate(${(t < 3.0 ? BX + 200 : sx).toFixed(1)} ${(t < 3.0 ? BY - 120 : sy).toFixed(1)}) rotate(${(t < 3.0 ? 25 : 15 * Math.cos(sa)).toFixed(1)})`);
      spoon.setAttribute('opacity', (prog(t, 2.7, 0.3) * (1 - prog(t, 5.0, 0.3))).toFixed(3));
      let d = '';
      for (let a = 0; a < 5.5; a += 0.15) { const r = 30 + a * 30; d += (d ? ' L' : 'M') + (BX + r * Math.cos(a + t * 6)).toFixed(1) + ',' + (BY + 30 + r * 0.32 * Math.sin(a + t * 6)).toFixed(1); }
      swirl.setAttribute('d', d);
      swirl.setAttribute('opacity', (0.6 * (t > 3.0 && t < 4.9 ? 1 : 0)).toFixed(2));
      bugs.forEach(({ g, b, x, y, a, i }) => {
        const wig = 4 * Math.sin(t * 5 + i);
        const gone = prog(t, 3.6 + i * 0.2, 0.4);
        g.setAttribute('transform', `translate(${x} ${y + wig}) scale(${(1 - 0.6 * gone).toFixed(3)})`);
        b.setAttribute('transform', `rotate(${a + 10 * Math.sin(t * 3 + i)})`);
        g.setAttribute('opacity', (prog(t, 0.3 + i * 0.15, 0.3) * (1 - gone)).toFixed(3));
      });
      lbBug.update(t, 0.9);
      lbBug.g.setAttribute('opacity', 1 - prog(t, 2.6, 0.3));
      enter(ok, t, 5.0);
      xx.update(t);
    },
  };
})();
