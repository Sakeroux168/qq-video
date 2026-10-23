// 镜头 17｜小孔只有几毫米，微波的"个头"有十几厘米，好比大象想钻猫洞，根本出不来，只能在炉子里来回弹。
// 画面：炉门剖面——左边炉内、右边炉外；一段长长的微波撞到金属网就弹回去。尺寸标注：约 12 厘米 / 孔：几毫米。小插图：大象对猫洞。
(() => {
  const DUR = 7;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <linearGradient id="inside" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2A2118"/><stop offset="1" stop-color="#3A2A18"/></linearGradient>`);
  const head = title(svg, 540, 330, [['微波', C.cyan], ['钻不出来', C.white]]);

  const T = 480, B = 1000, WX = 860;   // 剖面上下边、金属网位置
  const sec = el('g', {}, svg);
  el('rect', { x: 420, y: T, width: WX - 420, height: B - T, rx: 16, fill: 'url(#inside)' }, sec);
  text(sec, 450, T + 60, '炉内', { size: 64, color: C.g6, anchor: 'start' });
  text(sec, 970, T + 60, '炉外', { size: 64, color: C.g6 });
  // 金属网：一段段金属，中间留小缝
  for (let y = T; y < B; y += 64) el('rect', { x: WX, y, width: 22, height: 54, rx: 3, fill: C.g6 }, sec);
  const clip = el('clipPath', { id: 'inner' }, svg);
  el('rect', { x: 420, y: T, width: WX - 420, height: B - T }, clip);
  const waveG = el('g', { 'clip-path': 'url(#inner)' }, svg);
  const wave = el('path', { fill: 'none', stroke: C.cyan, 'stroke-width': 6, filter: 'url(#soft)' }, waveG);
  const bounce = arrow(svg, 800, 860, 620, 860, C.cyan, 5, 20);
  // 波长尺寸线
  const WL = 280;
  const dim = el('g', {}, svg);
  el('path', { d: `M470,690 L${470 + WL},690 M470,672 L470,708 M${470 + WL},672 L${470 + WL},708`, stroke: C.white, 'stroke-width': 3 }, dim);
  text(dim, 470 + WL / 2, 662, '约12厘米', { size: 64, font: FONT.heavy, color: C.cyan });
  const lbHole = label(svg, { px: WX + 11, py: T + 59 + 64 * 6, tx: 1040, ty: 1100, text: '孔：几毫米', anchor: 'end' });

  // 小插图：大象和猫洞
  const ins = el('g', {}, svg);
  const EY = 1330;
  el('path', { d: `M1000,1170 L1000,${EY} M1000,${EY} L470,${EY}`, stroke: C.g5, 'stroke-width': 6 }, ins);
  el('rect', { x: 990, y: 1170, width: 50, height: EY - 1170, fill: C.g4 }, ins);
  el('path', { d: `M990,${EY} L990,${EY - 26} A16,16 0 0 1 1022,${EY - 26} L1022,${EY} Z`, fill: '#000' }, ins);
  const ele = el('g', { transform: 'translate(700 0)' }, ins);
  el('ellipse', { cx: 0, cy: 1255, rx: 120, ry: 70, fill: C.g6 }, ele);
  for (const lx of [-80, -35, 40, 85]) el('rect', { x: lx - 16, y: 1280, width: 32, height: 50, rx: 10, fill: C.g6 }, ele);
  el('circle', { cx: 120, cy: 1210, r: 58, fill: C.g6 }, ele);
  el('ellipse', { cx: 95, cy: 1210, rx: 38, ry: 52, fill: C.g5 }, ele);
  el('path', { d: 'M168,1222 Q205,1260 190,1300', fill: 'none', stroke: C.g6, 'stroke-width': 22, 'stroke-linecap': 'round' }, ele);
  el('circle', { cx: 138, cy: 1196, r: 6, fill: C.g1 }, ele);
  text(ins, 700, 1420, '大象钻猫洞', { size: 64, color: C.g7 });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'talk' }, { t: 1.0, pose: 'point' }, { t: 4.0, pose: 'happy' }, { t: 5.6, pose: 'talk' }],
    marks: [{ t: 1.1, type: 'spark', dur: 1.2 }, { t: 4.1, type: 'heart', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      enter(sec, t, 0.3);
      // 波包在炉内左右来回弹：中心位置是三角波
      const ph = (t * 0.32) % 1, cx = 520 + 280 * (ph < 0.5 ? ph * 2 : 2 - ph * 2);
      const dir = ph < 0.5 ? 1 : -1;
      let d = '';
      for (let x = 430; x <= WX; x += 5) {
        const env = Math.exp(-(((x - cx) / 170) ** 2));
        const y = 830 + 85 * env * Math.sin((2 * Math.PI * (x - cx)) / WL - dir * t * 6);
        d += (d ? ' L' : 'M') + x + ',' + y.toFixed(1);
      }
      wave.setAttribute('d', d);
      waveG.setAttribute('opacity', prog(t, 0.5, 0.4));
      bounce.setAttribute('opacity', (prog(t, 3.0, 0.3) * (dir < 0 ? 1 : 0.25)).toFixed(3));
      enter(dim, t, 1.2);
      lbHole.update(t, 2.2);
      enter(ins, t, 3.8);
      xx.update(t);
    },
  };
})();
