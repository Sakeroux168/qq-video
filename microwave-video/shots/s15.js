// 镜头 15｜就像关了灯，屋里不会还剩着光。
// 画面：吊灯亮着，暖光照到地上；墙上开关一按，灯当即熄灭，屋里马上变暗。标注：关灯，不留光
(() => {
  const DUR = 5;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <linearGradient id="cone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.orange}" stop-opacity="0.45"/><stop offset="1" stop-color="${C.orange}" stop-opacity="0.04"/></linearGradient>
 <radialGradient id="pool" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="${C.orange}" stop-opacity="0.35"/><stop offset="1" stop-color="${C.orange}" stop-opacity="0"/></radialGradient>
 <radialGradient id="bulbOn" cx="50%" cy="40%" r="60%"><stop offset="0" stop-color="#FFFFFF"/><stop offset="0.5" stop-color="#FFD9A8"/><stop offset="1" stop-color="${C.orange}"/></radialGradient>`);

  const room = el('g', {}, svg);
  const LX = 660;
  el('rect', { x: 0, y: 1250, width: 1080, height: 670, fill: '#0C1015' }, room);
  el('path', { d: 'M0,1250 L1080,1250', stroke: C.g3, 'stroke-width': 3 }, room);
  const light = el('g', {}, room);
  el('path', { d: `M${LX - 70},650 L${LX + 70},650 L${LX + 300},1250 L${LX - 300},1250 Z`, fill: 'url(#cone)' }, light);
  el('ellipse', { cx: LX, cy: 1250, rx: 320, ry: 60, fill: 'url(#pool)' }, light);
  el('path', { d: `M${LX},380 L${LX},560`, stroke: C.g5, 'stroke-width': 5 }, room);
  el('path', { d: `M${LX - 40},560 L${LX + 40},560 L${LX + 110},650 L${LX - 110},650 Z`, fill: 'url(#metal)' }, room);
  const bulb = el('circle', { cx: LX, cy: 655, r: 34, fill: 'url(#bulbOn)' }, room);
  const bulbOff = el('circle', { cx: LX, cy: 655, r: 34, fill: C.g4, opacity: 0 }, room);
  // 墙上开关
  const SX = 960, SY = 900;
  el('rect', { x: SX - 45, y: SY - 70, width: 90, height: 140, rx: 12, fill: C.g3, stroke: C.g5, 'stroke-width': 3 }, room);
  const knob = el('rect', { x: SX - 18, y: SY - 45, width: 36, height: 50, rx: 8, fill: C.g7 }, room);
  const dark = el('rect', { x: 0, y: 0, width: 1080, height: 1920, fill: '#000', opacity: 0 }, room);

  const head = title(svg, 540, 330, [['关灯，', C.white], ['不留光', C.cyan]]);

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'talk' }, { t: 2.0, pose: 'point' }, { t: 3.6, pose: 'talk' }],
    marks: [{ t: 2.1, type: 'spark', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      head.update(t, 0.2);
      const off = prog(t, 1.9, 0.12);
      light.setAttribute('opacity', 1 - off);
      bulb.setAttribute('opacity', 1 - off);
      bulbOff.setAttribute('opacity', off);
      knob.setAttribute('y', t < 1.9 ? SY - 45 : SY - 5);
      dark.setAttribute('opacity', (0.35 * off).toFixed(3));
      xx.update(t);
    },
  };
})();
