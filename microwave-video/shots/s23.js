// 镜头 23｜还有带金边、银边的碗，放进去会噼啪打火花，咱是热饭，不是放烟花。
// 画面：金边碗在微波炉里，碗边闪出几道短折线火花（不做粒子），旁边橙色 ✕。标注：金边 银边 ✕ / 不是放烟花
(() => {
  const DUR = 6;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <linearGradient id="gold" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9C7A2E"/><stop offset="0.5" stop-color="#F1D27A"/><stop offset="1" stop-color="#9C7A2E"/></linearGradient>`);
  const head = title(svg, 540, 330, [['金边', C.orange], [' 银边', C.white], [' 不能进', C.white]]);

  const MX = 300, MY = 520, MS = 0.9;
  const mw = microwave(svg, { x: MX, y: MY, s: MS });
  // 在微波炉门窗里盖一只金边碗（覆盖原来的饭碗）
  const bx = MX + 320 * MS, by = MY + 365 * MS;
  const bowl = el('g', {}, svg);
  el('path', { d: `M${bx - 140},${by} Q${bx - 128},${by + 92} ${bx},${by + 95} Q${bx + 128},${by + 92} ${bx + 140},${by} Z`, fill: 'url(#bowl)' }, bowl);
  el('ellipse', { cx: bx, cy: by, rx: 140, ry: 20, fill: '#E9EDF1' }, bowl);
  el('ellipse', { cx: bx, cy: by, rx: 140, ry: 20, fill: 'none', stroke: 'url(#gold)', 'stroke-width': 9 }, bowl);
  el('path', { d: `M${bx - 128},${by + 40} Q${bx},${by + 62} ${bx + 128},${by + 40}`, fill: 'none', stroke: 'url(#gold)', 'stroke-width': 6 }, bowl);
  // 火花：短折线，位置轮换
  const SP = [[-120, -6], [70, -22], [130, 8], [-40, -24], [0, 52]];
  const sparks = SP.map(() => el('path', { fill: 'none', stroke: '#FFF3C4', 'stroke-width': 8, filter: 'url(#soft)', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg));
  const lbRim = label(svg, { px: bx + 120, py: by + 10, tx: 1040, ty: 1180, text: '金边', anchor: 'end' });
  const no = el('g', {}, svg);
  crossIcon(no, 470, 1340, 52);
  text(no, 545, 1370, '不是放烟花', { size: 80, font: FONT.heavy, color: C.orange, anchor: 'start' });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.4, pose: 'scared' }, { t: 3.2, pose: 'shrug' }, { t: 4.8, pose: 'talk' }],
    marks: [{ t: 1.5, type: '!', dur: 1.2 }, { t: 3.3, type: 'sweat', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.1);
      mw.update(t, { on: 1, display: '1:30' });
      // 1.3s 起噼啪：每 0.12s 换一组随机火花
      const k = Math.floor(t / 0.12);
      sparks.forEach((p, i) => {
        const r = _hash(k * 7 + i);
        const on = t > 1.3 && r > 0.45;
        if (!on) { p.setAttribute('opacity', 0); return; }
        const [dx, dy] = SP[i];
        const x0 = bx + dx, y0 = by + dy, a = r * Math.PI * 2, L = 60 + 40 * _hash(k + i * 3);
        const ux = Math.cos(a), uy = Math.sin(a);
        p.setAttribute('d', `M${x0},${y0} L${x0 + ux * L * 0.5 - uy * 18},${y0 + uy * L * 0.5 + ux * 18} L${x0 + ux * L * 0.6 + uy * 16},${y0 + uy * L * 0.6 - ux * 16} L${x0 + ux * L},${y0 + uy * L}`);
        p.setAttribute('opacity', 1);
      });
      lbRim.update(t, 0.9);
      enter(no, t, 3.3);
      xx.update(t);
    },
  };
})();
