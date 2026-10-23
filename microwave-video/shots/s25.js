// 镜头 25｜有的拿出来剥的时候才炸，烫一脸。所以要么打散了再热，要么用牙签在蛋黄上戳几个小洞，给蒸汽留条路。
// 画面：前半——刚拿出来的鸡蛋 + 警示"剥的时候也会炸"；后半——两种正确做法并排：打散 ✓ / 戳小洞 ✓
(() => {
  const DUR = 8;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="shell" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#FFF6EA"/><stop offset="1" stop-color="#D9C6AE"/></radialGradient>
 <radialGradient id="yolk" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#FFD27A"/><stop offset="1" stop-color="#E39A2E"/></radialGradient>
 <linearGradient id="cup" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${C.g6}"/><stop offset="0.45" stop-color="#F4F6F8"/><stop offset="1" stop-color="#B7BEC6"/></linearGradient>`);

  // A：剥的时候也会炸
  const A = el('g', {}, svg);
  const headA = title(A, 540, 330, [['剥的时候', C.white], ['也会炸', C.orange]]);
  const EX = 640, EY = 900;
  const egg = el('g', {}, A);
  el('ellipse', { cx: EX, cy: EY, rx: 150, ry: 190, fill: 'url(#shell)' }, egg);
  const st = steam(A, [EX - 50, EX + 10, EX + 60], EY - 200, 90, '#FFFFFF', 0.35);
  const warnA = el('g', {}, A);
  warnIcon(warnA, EX + 210, EY - 170, 54);
  const lbHot = label(A, { px: EX + 130, py: EY - 60, tx: 1040, ty: 1240, text: '烫一脸', anchor: 'end' });

  // B：两种正确做法
  const B = el('g', {}, svg);
  const headB = title(B, 540, 330, [['这样热才', C.white], ['安全', C.cyan]]);
  // 左：打散的蛋液（碗）
  const L = el('g', {}, B);
  const LX = 420, LY = 860;
  el('path', { d: `M${LX - 150},${LY} Q${LX - 140},${LY + 120} ${LX},${LY + 124} Q${LX + 140},${LY + 120} ${LX + 150},${LY} Z`, fill: 'url(#cup)' }, L);
  el('ellipse', { cx: LX, cy: LY, rx: 150, ry: 26, fill: '#E9EDF1' }, L);
  el('ellipse', { cx: LX, cy: LY + 2, rx: 132, ry: 20, fill: '#F2C15A' }, L);
  const whisk = el('path', { d: `M${LX + 40},${LY - 10} Q${LX + 90},${LY - 120} ${LX + 150},${LY - 180}`, stroke: C.g6, 'stroke-width': 10, 'stroke-linecap': 'round', fill: 'none' }, L);
  const swirl = el('path', { fill: 'none', stroke: '#FFE3A0', 'stroke-width': 5, 'stroke-linecap': 'round' }, L);
  checkIcon(L, LX, LY + 230, 44);
  text(L, LX, LY + 350, '打散', { size: 80, font: FONT.heavy, color: C.cyan });
  // 右：蛋黄上戳洞（荷包蛋俯视）
  const R = el('g', {}, B);
  const RX = 820, RY = 860;
  el('ellipse', { cx: RX, cy: RY + 10, rx: 160, ry: 120, fill: '#F6F2EA' }, R);
  el('circle', { cx: RX, cy: RY, r: 62, fill: 'url(#yolk)' }, R);
  const holes = [[-22, -18], [18, -10], [-6, 22]].map(([dx, dy]) => el('circle', { cx: RX + dx, cy: RY + dy, r: 7, fill: '#8A5A1A', opacity: 0 }, R));
  const pick = el('path', { stroke: '#D8B98A', 'stroke-width': 8, 'stroke-linecap': 'round' }, R);
  checkIcon(R, RX, RY + 230, 44);
  text(R, RX, RY + 350, '戳小洞', { size: 80, font: FONT.heavy, color: C.cyan });

  const xx = xingxing(svg, {
    x: 170, y: 1440, h: 480,
    cues: [{ t: 0, pose: 'scared' }, { t: 2.6, pose: 'talk' }, { t: 4.0, pose: 'point' }, { t: 5.8, pose: 'thumb' }],
    marks: [{ t: 0.2, type: 'sweat', dur: 1.8 }, { t: 5.9, type: 'spark', dur: 1.3 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      st.update(t);
      headA.update(t, 0.1);
      const wobble = t < 2.4 ? 3 * Math.sin(t * 40) * prog(t, 0.6, 0.4) : 0;
      egg.setAttribute('transform', `rotate(${wobble.toFixed(2)} ${EX} ${EY + 190})`);
      warnA.setAttribute('opacity', prog(t, 0.6, 0.3));
      lbHot.update(t, 1.2);
      const sw = prog(t, 2.7, 0.35);
      A.setAttribute('opacity', 1 - sw);
      B.setAttribute('opacity', sw);
      headB.update(t, 2.8);
      enter(L, t, 3.0);
      enter(R, t, 3.6);
      // 打散：蛋液里的漩涡转起来
      let d = '';
      for (let a = 0; a < 6.5; a += 0.15) {
        const r = 10 + a * 13, ang = a + t * 5;
        d += (d ? ' L' : 'M') + (LX + r * Math.cos(ang)).toFixed(1) + ',' + (LY + 2 + r * 0.15 * Math.sin(ang)).toFixed(1);
      }
      swirl.setAttribute('d', d);
      whisk.setAttribute('transform', `rotate(${(8 * Math.sin(t * 6)).toFixed(2)} ${LX + 40} ${LY - 10})`);
      // 戳洞：牙签点三下
      holes.forEach((h, i) => h.setAttribute('opacity', t > 4.3 + i * 0.5 ? 1 : 0));
      const hi = Math.min(2, Math.max(0, Math.floor((t - 4.0) / 0.5)));
      const [hx, hy] = [[-22, -18], [18, -10], [-6, 22]][hi];
      const down = (t > 4.0 && t < 5.6) ? Math.abs(Math.sin(((t - 4.0) / 0.5) * Math.PI)) : 0;
      const px = RX + hx, py = RY + hy;
      pick.setAttribute('d', `M${px + 60},${py - 120 + 30 * down} L${px + 6 - 6 * down},${py - 10 + 10 * down}`);
      pick.setAttribute('opacity', prog(t, 3.8, 0.3) * (1 - prog(t, 5.8, 0.3)));
      xx.update(t);
    },
  };
})();
