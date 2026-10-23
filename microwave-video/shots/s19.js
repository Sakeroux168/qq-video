// 镜头 19｜还有人说，微波炉热饭没营养。恰恰相反。它热得快，基本不用加水，像维生素C这种又怕热又怕水的营养，反而比水煮留得多。论保营养，微波炉直接夯爆了。
// 画面："没营养？"被划掉 → 水煮锅 vs 微波炉，两根维生素C柱子（只比高低不标数）→ "夯"排名条，微波炉排第一。
(() => {
  const DUR = 10;
  const { svg } = setupStage();
  const headA = title(svg, 540, 330, [['热饭', C.white], ['没营养？', C.orange]]);
  const A = el('g', {}, svg);
  const amw = microwave(A, { x: 420, y: 620, s: 0.68 });
  const strike = el('path', { d: 'M425,295 L830,295', stroke: C.white, 'stroke-width': 14, 'stroke-linecap': 'round' }, svg);
  const headB = title(svg, 540, 330, [['维生素C', C.cyan], ['留得多', C.white]]);
  const headC = title(svg, 540, 330, [['保营养：', C.white], ['夯爆了', C.orange]]);

  // B：对比柱（柱子在上，设备图标在下当横轴标签）
  const B = el('g', {}, svg);
  const BASE = 1080, X1 = 600, X2 = 860;
  el('path', { d: `M470,${BASE} L1000,${BASE}`, stroke: C.g6, 'stroke-width': 4 }, B);
  const pot = el('g', { transform: `translate(${X1} ${BASE + 40})` }, B);
  el('path', { d: 'M-80,0 L80,0 L70,80 Q66,92 54,92 L-54,92 Q-66,92 -70,80 Z', fill: 'url(#metal)' }, pot);
  el('rect', { x: -98, y: -10, width: 196, height: 16, rx: 8, fill: C.g5 }, pot);
  el('ellipse', { cx: 0, cy: 4, rx: 72, ry: 10, fill: C.cyan, opacity: 0.5 }, pot);
  text(B, X1, BASE + 200, '水煮', { size: 72 });
  const mw = microwave(B, { x: X2 - 95, y: BASE + 30, s: 0.22 });
  text(B, X2, BASE + 200, '微波', { size: 72 });
  const barL = el('rect', { x: X1 - 60, width: 120, rx: 10, fill: C.g5 }, B);
  const barR = el('rect', { x: X2 - 60, width: 120, rx: 10, fill: C.cyan }, B);
  const BAR0 = BASE - 4;
  const capC = el('g', {}, B);
  text(capC, 735, 520, '维生素C 保留', { size: 64, color: C.g7 });

  // C：夯 → 拉 排名条
  const Cg = el('g', {}, svg);
  const tiers = [['夯', C.orange], ['顶级', C.g5], ['人上人', C.g4], ['NPC', C.g3], ['拉完了', C.g2]];
  tiers.forEach(([name, col], i) => {
    const y = 470 + i * 150;
    el('rect', { x: 420, y, width: 220, height: 130, rx: 12, fill: col }, Cg);
    text(Cg, 530, y + 88, name, { size: name.length > 2 ? 56 : 72, font: FONT.heavy, color: i === 0 ? C.bg : C.white });
    el('rect', { x: 650, y, width: 380, height: 130, rx: 12, fill: C.bgHi, stroke: C.g3, 'stroke-width': 2 }, Cg);
  });
  const champ = el('g', {}, Cg);
  const cmw = microwave(champ, { x: 700, y: 488, s: 0.17 });
  text(champ, 1000, 560, '微波炉', { size: 52, font: FONT.bold, anchor: 'end' });

  const xx = xingxing(svg, {
    x: 190, y: 1440, h: 500,
    cues: [{ t: 0, pose: 'think' }, { t: 1.6, pose: 'shrug' }, { t: 3.0, pose: 'talk' }, { t: 5.2, pose: 'point' }, { t: 7.0, pose: 'thumb' }, { t: 8.6, pose: 'happy' }],
    marks: [{ t: 0.2, type: '?', dur: 1.3 }, { t: 5.3, type: 'spark', dur: 1.2 }, { t: 7.1, type: '!', dur: 1.2 }, { t: 8.7, type: 'heart', dur: 1.2 }],
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      // A：0~2.8s
      headA.update(t, 0.1);
      const SL = 410;
      strike.setAttribute('stroke-dasharray', `${SL} ${SL}`);
      strike.setAttribute('stroke-dashoffset', (SL * (1 - prog(t, 1.6, 0.3))).toFixed(1));
      const outA = 1 - prog(t, 2.7, 0.3);
      headA.g.setAttribute('opacity', Math.min(+headA.g.getAttribute('opacity'), outA));
      strike.setAttribute('opacity', outA);
      A.setAttribute('opacity', outA);
      amw.update(t, { on: 1, display: '1:30' });
      // B：3.0~6.6s
      headB.update(t, 3.0);
      const outB = 1 - prog(t, 6.6, 0.3);
      headB.g.setAttribute('opacity', Math.min(+headB.g.getAttribute('opacity'), outB));
      enter(B, t, 3.0);
      B.setAttribute('opacity', Math.min(+B.getAttribute('opacity'), outB));
      mw.update(t, { on: 1, display: '1:30' });
      const hL = 200 * prog(t, 4.0, 1.0), hR = 450 * prog(t, 4.0, 1.4);
      barL.setAttribute('y', BAR0 - hL); barL.setAttribute('height', Math.max(0.1, hL));
      barR.setAttribute('y', BAR0 - hR); barR.setAttribute('height', Math.max(0.1, hR));
      capC.setAttribute('opacity', prog(t, 4.2, 0.4));
      // C：6.9s~
      headC.update(t, 6.9);
      enter(Cg, t, 6.9);
      cmw.update(t, { on: 1, display: '' });
      popIn(champ, t, 7.6, 850, 535, 0.35, 0.9);
      xx.update(t);
    },
  };
})();
