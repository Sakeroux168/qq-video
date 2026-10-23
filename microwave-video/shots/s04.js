// 镜头 4｜先讲个冷知识：微波炉是"意外"发明的。1945年前后，美国有个工程师在研究雷达，
// 画面：标题「冷知识：意外发明」→ 大字 1945 → 雷达天线缓慢转动、发出脉冲。标注：雷达
(() => {
  const DUR = 7;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['冷知识：', C.cyan], ['意外发明', C.white]], 110);

  const year = el('g', {}, svg);
  text(year, 380, 600, [['1945', C.white]], { size: 170, font: FONT.heavy });
  text(year, 600, 600, '年前后', { size: 64, color: C.g6, anchor: 'start' });

  // 雷达天线（本地坐标：底座中心 0,0）
  const radar = el('g', { transform: 'translate(720 1300)' }, svg);
  el('ellipse', { cx: 0, cy: 0, rx: 170, ry: 26, fill: '#000', opacity: 0.45 }, radar);
  el('path', { d: 'M-130,0 L-90,-70 L90,-70 L130,0 Z', fill: 'url(#metal)' }, radar);
  el('rect', { x: -22, y: -330, width: 44, height: 270, fill: 'url(#metalH)' }, radar);
  el('rect', { x: -60, y: -350, width: 120, height: 40, rx: 8, fill: C.g4 }, radar);
  const turn = el('g', { }, radar);
  const dish = el('g', { transform: 'translate(0 -420) rotate(28)' }, turn);
  el('ellipse', { cx: 0, cy: 0, rx: 230, ry: 82, fill: 'url(#metal)' }, dish);
  el('ellipse', { cx: 0, cy: -8, rx: 214, ry: 70, fill: C.g2 }, dish);
  for (const r of [0.33, 0.66]) el('ellipse', { cx: 0, cy: -8, rx: 214 * r, ry: 70 * r, fill: 'none', stroke: C.g4, 'stroke-width': 3 }, dish);
  el('path', { d: 'M0,-8 L0,-150', stroke: C.g6, 'stroke-width': 8 }, dish);
  el('path', { d: 'M-150,-30 L0,-150 M150,-30 L0,-150', stroke: C.g5, 'stroke-width': 4 }, dish);
  el('rect', { x: -16, y: -176, width: 32, height: 34, rx: 6, fill: C.g6 }, dish);
  // 脉冲：从天线向左上方扩散的青色弧线
  const pulses = [0, 1, 2].map(() => el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 4, 'stroke-linecap': 'round', filter: 'url(#soft)' }, svg));
  const lbRadar = label(svg, { px: 700, py: 880, tx: 560, ty: 820, text: '雷达', anchor: 'end' });

  const xx = xingxing(svg, {
    x: 215, y: 1440, h: 540,
    cues: [{ t: 0, pose: 'point' }, { t: 1.6, pose: 'talk' }, { t: 5.0, pose: 'think' }],
    marks: [{ t: 0.2, type: 'spark', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      enter(year, t, 2.3);
      // 天线绕竖轴慢慢转：横向缩放
      const k = 0.78 + 0.22 * Math.cos(t * 0.9);
      turn.setAttribute('transform', `scale(${k.toFixed(4)} 1)`);
      const ox = 720 + 150 * k, oy = 1300 - 520;
      pulses.forEach((p, i) => {
        const ph = ((t * 0.55 + i / 3) % 1);
        const r = 60 + ph * 300;
        const a0 = -65, a1 = -20;
        const P = a => [ox + r * Math.cos(a * Math.PI / 180), oy + r * Math.sin(a * Math.PI / 180)];
        const [x0, y0] = P(a0), [x1, y1] = P(a1);
        p.setAttribute('d', `M${x0.toFixed(1)},${y0.toFixed(1)} A${r.toFixed(1)},${r.toFixed(1)} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)}`);
        p.setAttribute('opacity', (Math.sin(Math.PI * ph) * prog(t, 0.6, 0.6)).toFixed(3));
      });
      lbRadar.update(t, 4.0);
      xx.update(t);
    },
  };
})();
