// 镜头 10｜说出来你可能不信：微波炉跟你家WiFi的频率差不多，是实打实的亲戚。你天天连WiFi都不怕，咋就怕上微波炉了？
// 画面：一条频率轴，WiFi 2.4GHz 和微波炉 2.45GHz 两个标记几乎挨在一起，用括号连起来写"亲戚"。
(() => {
  const DUR = 7;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['频率', C.white], ['差不多', C.cyan]]);

  const AY = 760;
  const axis = el('g', {}, svg);
  el('path', { d: `M70,${AY} L1000,${AY}`, stroke: C.g6, 'stroke-width': 5, 'stroke-linecap': 'round' }, axis);
  el('path', { d: `M1010,${AY} L985,${AY - 14} L985,${AY + 14} Z`, fill: C.g6 }, axis);
  for (let x = 120; x <= 960; x += 60) el('path', { d: `M${x},${AY - 10} L${x},${AY + 10}`, stroke: C.g5, 'stroke-width': 3 }, axis);
  text(axis, 70, AY - 30, '频率 →', { size: 64, color: C.g6, anchor: 'start' });

  // WiFi 标记（轴上方）
  const mA = el('g', {}, svg);
  el('path', { d: `M630,${AY} L630,${AY - 70}`, stroke: C.cyan, 'stroke-width': 5 }, mA);
  el('circle', { cx: 630, cy: AY, r: 12, fill: C.cyan }, mA);
  for (const r of [16, 32, 48]) el('path', { d: `M${430 - r * 0.8},${AY - 102 - r * 0.6} A${r},${r} 0 0 1 ${430 + r * 0.8},${AY - 102 - r * 0.6}`, fill: 'none', stroke: C.cyan, 'stroke-width': 7, 'stroke-linecap': 'round' }, mA);
  el('circle', { cx: 430, cy: AY - 98, r: 7, fill: C.cyan }, mA);
  text(mA, 475, AY - 85, [['WiFi ', C.white], ['2.4GHz', C.cyan]], { size: 72, anchor: 'start' });
  // 微波炉标记（轴下方）
  const mB = el('g', {}, svg);
  el('path', { d: `M660,${AY} L660,${AY + 70}`, stroke: C.orange, 'stroke-width': 5 }, mB);
  el('circle', { cx: 660, cy: AY, r: 12, fill: C.orange }, mB);
  text(mB, 430, AY + 150, [['微波炉 ', C.white], ['2.45GHz', C.orange]], { size: 72, anchor: 'start' });

  // 把两个标记框在一起，底部挂"亲戚"
  const kin = el('g', {}, svg);
  el('rect', { x: 370, y: AY - 180, width: 630, height: 410, rx: 28, fill: 'none', stroke: C.cyan, 'stroke-width': 4, 'stroke-dasharray': '16 12' }, kin);
  el('rect', { x: 550, y: AY + 170, width: 290, height: 120, rx: 60, fill: C.bg, stroke: C.cyan, 'stroke-width': 5 }, kin);
  text(kin, 695, AY + 262, '亲戚', { size: 96, font: FONT.heavy, color: C.cyan });

  const xx = xingxing(svg, {
    x: 200, y: 1440, h: 520,
    cues: [{ t: 0, pose: 'talk' }, { t: 0.8, pose: 'surprise' }, { t: 2.4, pose: 'point' }, { t: 3.8, pose: 'talk' }, { t: 4.8, pose: 'shrug' }],
    marks: [{ t: 0.9, type: '!', dur: 1.2 }, { t: 4.9, type: '?', dur: 1.8 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      enter(axis, t, 0.5);
      enter(mA, t, 1.4);
      enter(mB, t, 2.2);
      enter(kin, t, 3.2);
      xx.update(t);
    },
  };
})();
