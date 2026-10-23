// 镜头 1｜微波炉热的饭，到底有没有辐射？你家是不是也有这么一位……才敢回来。
// 画面：微波炉在工作，屏幕倒数；左侧墙边有人探头偷看。标注：有辐射？ / 躲出厨房
(() => {
  const DUR = 8;
  const { svg } = setupStage();
  const scene = el('g', {}, svg);

  // 灶台
  el('rect', { x: 380, y: 1234, width: 700, height: 70, fill: 'url(#counter)' }, scene);
  const mw = microwave(scene, { x: 440, y: 880, s: 0.68 });

  // 人（在墙后面，探出半个头）
  const BIG = 'translate(250 760) scale(1.45) translate(-250 -800)';
  const person = el('g', {}, scene);
  const pBody = el('g', { transform: BIG }, person);
  el('rect', { x: 282, y: 846, width: 34, height: 50, fill: 'url(#skin)' }, pBody);
  el('path', { d: 'M200,885 L262,885 Q336,882 348,965 L348,1800 L200,1800 Z', fill: C.g4 }, pBody);
  el('ellipse', { cx: 305, cy: 800, rx: 60, ry: 70, fill: 'url(#skin)' }, pBody);
  el('path', { d: 'M243,800 Q240,712 310,708 Q372,712 368,790 Q352,750 300,748 Q262,752 243,800 Z', fill: C.g3 }, pBody);
  el('path', { d: 'M350,800 Q362,816 350,824', stroke: '#9A7B66', 'stroke-width': 3, fill: 'none', 'stroke-linecap': 'round' }, pBody);
  el('path', { d: 'M318,846 Q330,840 342,846', stroke: '#7A5B4A', 'stroke-width': 4, fill: 'none', 'stroke-linecap': 'round' }, pBody);
  el('path', { d: 'M312,772 Q326,764 344,774', stroke: C.g3, 'stroke-width': 6, fill: 'none', 'stroke-linecap': 'round' }, pBody);
  const eye = el('g', {}, pBody);
  el('ellipse', { cx: 329, cy: 798, rx: 13, ry: 10, fill: '#E9EDF1' }, eye);
  el('circle', { cx: 335, cy: 799, r: 6, fill: C.g1 }, eye);

  // 墙和门框
  el('rect', { x: 0, y: 0, width: 250, height: 1920, fill: 'url(#wall)' }, scene);
  el('rect', { x: 236, y: 0, width: 30, height: 1920, fill: 'url(#metalH)' }, scene);
  el('rect', { x: 266, y: 0, width: 10, height: 1920, fill: '#000', opacity: 0.25 }, scene);

  // 扒着门框的手
  const handWrap = el('g', { transform: BIG }, scene);
  const hand = el('g', {}, handWrap);
  for (let i = 0; i < 4; i++) el('rect', { x: 238, y: 905 + i * 26, width: 36, height: 23, rx: 11, fill: 'url(#skin)' }, hand);

  const lbHide = label(scene, { px: 345, py: 668, tx: 290, ty: 560, text: '躲出厨房' });
  const head = title(svg, 540, 360, [['有', C.white], ['辐射', C.orange], ['？', C.white]]);

  window.SHOT = {
    duration: DUR,
    render(t) {
      pushIn(scene, t, DUR, 0.03, 640, 1000);
      const secs = Math.max(0, 90 - Math.floor(t));
      mw.update(t, { on: 1, display: `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}` });
      head.update(t, 0.2);
      // 2.4s 起探头
      const p = prog(t, 2.4, 0.8);
      person.setAttribute('transform', `translate(${(-200 * (1 - p)).toFixed(1)} 0)`);
      hand.setAttribute('opacity', prog(t, 2.7, 0.4));
      // 5.0s 眨一下眼
      const blink = t > 5.0 && t < 5.15 ? 0.15 : 1;
      eye.setAttribute('transform', `translate(0 ${799 * (1 - blink)}) scale(1 ${blink})`);
      lbHide.update(t, 3.4);
    },
  };
})();
