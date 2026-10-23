// 镜头 2｜你跟他讲科学，他让你喝碗丝瓜汤降降火。行，今天咱就当一回赌神：我要验牌！
// 画面：一碗丝瓜汤推到面前 → 换成赌桌，桌上扣着一张"辐射？"牌。标注：丝瓜汤降降火 / 我要验牌！
(() => {
  const DUR = 6;
  const { svg, defs } = setupStage();
  defs.insertAdjacentHTML('beforeend', `
 <radialGradient id="soup" cx="45%" cy="40%" r="60%"><stop offset="0" stop-color="#C9D1AE"/><stop offset="1" stop-color="#9AA77F"/></radialGradient>
 <radialGradient id="felt" cx="50%" cy="45%" r="60%"><stop offset="0" stop-color="#232A33"/><stop offset="1" stop-color="#12161B"/></radialGradient>
 <linearGradient id="bigbowl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8C959F"/><stop offset="0.45" stop-color="#F2F4F6"/><stop offset="1" stop-color="#A9B1BA"/></linearGradient>`);

  // A：丝瓜汤
  const A = el('g', {}, svg);
  const soupG0 = el('g', { transform: 'translate(610 830) scale(1.1) translate(-540 -930)' }, A);
  const soupG = el('g', {}, soupG0);
  const cx = 540, cy = 930;
  el('ellipse', { cx, cy: cy + 175, rx: 230, ry: 26, fill: '#000', opacity: 0.4 }, soupG);
  el('path', { d: `M${cx - 300},${cy} Q${cx - 280},${cy + 175} ${cx},${cy + 180} Q${cx + 280},${cy + 175} ${cx + 300},${cy} Z`, fill: 'url(#bigbowl)' }, soupG);
  el('ellipse', { cx, cy, rx: 300, ry: 62, fill: '#DDE2E7' }, soupG);
  el('ellipse', { cx, cy: cy + 4, rx: 278, ry: 52, fill: 'url(#soup)' }, soupG);
  // 丝瓜片
  const slices = [[-150, -6, 1], [-40, 14, 0.9], [80, -10, 1.05], [180, 12, 0.85], [-90, -22, 0.8], [30, -26, 0.75]];
  for (const [dx, dy, s] of slices) {
    const g = el('g', { transform: `translate(${cx + dx} ${cy + dy}) scale(${s} ${s * 0.45})` }, soupG);
    el('circle', { r: 44, fill: '#7E9268' }, g);
    el('circle', { r: 34, fill: '#D3DBBC' }, g);
    el('circle', { r: 10, fill: '#B9C59C' }, g);
  }
  const st = steam(soupG, [cx - 120, cx, cx + 120], cy - 50, 150, '#FFFFFF', 0.35);
  const lbSoup = label(A, { px: 478, py: 700, tx: 150, ty: 520, text: '丝瓜汤降降火' });

  // B：赌桌 + 扣着的牌
  const B = el('g', {}, svg);
  el('ellipse', { cx: 640, cy: 960, rx: 620, ry: 380, fill: 'url(#felt)' }, B);
  el('ellipse', { cx: 640, cy: 960, rx: 600, ry: 362, fill: 'none', stroke: C.cyan, 'stroke-width': 3, opacity: 0.5 }, B);
  el('ellipse', { cx: 640, cy: 930, rx: 330, ry: 230, fill: '#FFFFFF', opacity: 0.04 }, B);
  const card = playingCard(B, { cx: 640, cy: 930, w: 380, h: 540, back: '辐射？', backSize: 100 });
  card.setFlip(0);
  const head = title(B, 540, 400, [['我要', C.white], ['验牌', C.orange], ['！', C.white]]);

  const xx = xingxing(svg, {
    x: 215, y: 1440, h: 540,
    cues: [{ t: 0, pose: 'talk' }, { t: 3.3, pose: 'point' }, { t: 5.0, pose: 'talk' }],
    marks: [{ t: 3.4, type: '!', dur: 1.4 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      st.update(t);
      // A：0~2.9s
      popIn(soupG, t, 0, cx, cy, 0.5, 0.94);
      soupG.setAttribute('opacity', 1); // 第一帧就有主体
      lbSoup.update(t, 0.6);
      const out = prog(t, 2.6, 0.35);
      A.setAttribute('opacity', 1 - out);
      // B：2.9s 起
      const inn = prog(t, 2.95, 0.4);
      B.setAttribute('opacity', inn);
      card.move(640, 930 + 30 * (1 - inn));
      head.update(t, 3.3);
      xx.update(t);
    },
  };
})();
