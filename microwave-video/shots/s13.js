// 镜头 13｜微波一来，小磁针就跟着疯狂转圈，一秒钟转几十亿下，你挤我、我挤你，一摩擦，就热了。
// 画面：上方小微波炉在工作，放大圈里水分子跟着微波疯狂转圈，圈内从冷色慢慢变暖。标注：疯狂转圈 → 发热 / 每秒几十亿次 / 摩擦发热
(() => {
  const DUR = 7;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="warm" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#6B3A16"/><stop offset="1" stop-color="#2A1608"/></radialGradient>`);
  const head = title(svg, 540, 330, [['疯狂转圈 → ', C.white], ['发热', C.orange]]);

  const mw = microwave(svg, { x: 470, y: 430, s: 0.6 });
  const LX = 690, LY = 1040, LR = 240;
  // 碗口 → 放大圈的连线
  el('path', { d: `M${470 + 320 * 0.6 - 60},${430 + 380 * 0.6 + 30} L${LX - LR + 30},${LY - 120} M${470 + 320 * 0.6 + 60},${430 + 380 * 0.6 + 30} L${LX + LR - 30},${LY - 120}`, stroke: C.cyan, 'stroke-width': 2.5, 'stroke-dasharray': '10 10', opacity: 0.7 }, svg);
  const L = lens(svg, LX, LY, LR);
  const warm = el('circle', { cx: LX, cy: LY, r: LR, fill: 'url(#warm)', opacity: 0 }, L.inner);
  const MOLS = [[-100, -80, 20], [105, -20, 150], [-10, 120, 260]];
  const mols = MOLS.map(([dx, dy, a], i) => {
    const m = waterMol(L.inner, LX + dx, LY + dy, 1.05);
    const arc = arcArrow(L.inner, LX + dx, LY + dy, 88, 0, 150, C.cyan, 5, 14);
    return { m, arc, x: LX + dx, y: LY + dy, a, dir: i % 2 ? -1 : 1 };
  });
  const lbFast = label(svg, { px: LX - 100, py: LY - 80 - 60, tx: 60, ty: 830, text: '每秒几十亿次', anchor: 'start' });
  const heat = el('g', {}, svg);
  text(heat, LX, LY + LR + 105, [['摩擦', C.white], ['发热', C.orange]], { size: 96, font: FONT.heavy });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'talk' }, { t: 2.0, pose: 'surprise' }, { t: 3.6, pose: 'talk' }, { t: 5.0, pose: 'happy' }],
    marks: [{ t: 2.1, type: '!', dur: 1.3 }, { t: 5.1, type: 'spark', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      mw.update(t, { on: 1, display: '1:30' });
      // 转速随时间加快
      const spin = t < 0.6 ? 0 : 120 * (t - 0.6) + 260 * Math.max(0, t - 1.6) ** 1.4;
      mols.forEach(({ m, arc, x, y, a, dir }) => {
        m.rot(a + dir * spin);
        arc.setAttribute('transform', `rotate(${(a + dir * spin * 0.5).toFixed(1)} ${x} ${y})${dir < 0 ? ` translate(${2 * x} 0) scale(-1 1)` : ''}`);
        arc.setAttribute('opacity', prog(t, 0.8, 0.4));
        // 转得快时轻微抖动，表示互相挤
        m.outer.setAttribute('transform', `translate(${(x + 4 * Math.sin(t * 37 + x) * prog(t, 3.0, 1)).toFixed(1)} ${(y + 4 * Math.cos(t * 41 + y) * prog(t, 3.0, 1)).toFixed(1)})`);
      });
      warm.setAttribute('opacity', (0.85 * prog(t, 3.2, 2.0)).toFixed(3));
      L.ring.setAttribute('stroke', t > 4.2 ? C.orange : C.cyan);
      lbFast.update(t, 1.8);
      enter(heat, t, 4.4);
      xx.update(t);
    },
  };
})();
