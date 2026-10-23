// 镜头 14｜有人担心：热完的饭会不会"残留"微波？不会。"叮"一声，微波当场下班，一秒都不加班。
// 画面：标题"残留微波？"被划掉；微波炉倒数到 0:00，"叮！"，内灯熄灭、波纹当场消失。标注：残留微波？ / 叮！ / 当场下班
(() => {
  const DUR = 6;
  const { svg } = setupStage();
  const head = title(svg, 540, 330, [['残留', C.white], ['微波', C.cyan], ['？', C.white]]);
  const strike = el('path', { d: 'M260,295 L820,295', stroke: C.orange, 'stroke-width': 14, 'stroke-linecap': 'round' }, svg);
  const SL = 560;

  const MX = 400, MY = 650, MS = 0.72;
  const mw = microwave(svg, { x: MX, y: MY, s: MS });
  const ding = el('g', {}, svg);
  text(ding, 720, 600, '叮！', { size: 150, font: FONT.heavy, color: C.orange });
  const lbOff = label(svg, { px: MX + 300 * MS, py: MY + 200 * MS, tx: 520, ty: 1120, text: '当场下班', anchor: 'start' });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'think' }, { t: 2.3, pose: 'talk' }, { t: 3.4, pose: 'happy' }, { t: 4.8, pose: 'talk' }],
    marks: [{ t: 0.3, type: '?', dur: 1.8 }, { t: 3.5, type: 'spark', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      strike.setAttribute('stroke-dasharray', `${SL} ${SL}`);
      strike.setAttribute('stroke-dashoffset', (SL * (1 - prog(t, 2.4, 0.35))).toFixed(1));
      // 倒数 0:03 → 0:00，3.0s 叮
      const secs = Math.max(0, 3 - Math.floor(t));
      const on = 1 - prog(t, 3.0, 0.15);
      mw.update(t, { on, display: `0:${String(secs).padStart(2, '0')}` });
      popIn(ding, t, 3.0, 720, 550, 0.25, 0.9);
      lbOff.update(t, 3.6);
      xx.update(t);
    },
  };
})();
