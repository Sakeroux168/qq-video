// 星星动作展示样片：入场 → 讲解(说话+眨眼) → 指向 → 吃惊 → 思考 → 点赞 → 害怕 → 开心
(() => {
  const DUR = 12;
  const { svg } = setupStage();
  const steps = [[0, 'talk', '讲解（嘴会动、会眨眼）'], [2.6, 'point', '指向标注'], [4.1, 'surprise', '吃惊'], [5.6, 'think', '思考'], [7.1, 'thumb', '点赞'], [8.6, 'scared', '害怕'], [10.1, 'happy', '开心']];
  const xx = xingxing(svg, {
    x: 540, y: 1420, h: 720,
    cues: steps.map(([t, pose]) => ({ t, pose })),
    enter: { t: 0.1, from: 'left' },
    marks: [{ t: 2.8, type: 'spark', dur: 1.0 }, { t: 4.2, type: '!', dur: 1.1 }, { t: 5.7, type: '?', dur: 1.1 }, { t: 7.2, type: 'spark', dur: 1.0 }, { t: 8.7, type: 'sweat', dur: 1.1 }, { t: 10.2, type: 'heart', dur: 1.4 }],
  });
  const caps = steps.map(([t, , c]) => { const g = el('g', {}, svg); text(g, 540, 420, c, { size: 80, font: FONT.heavy }); return { t, g }; });
  window.SHOT = {
    duration: DUR,
    render(t) {
      xx.update(t);
      caps.forEach(({ t: t0, g }, i) => {
        const t1 = i + 1 < caps.length ? caps[i + 1].t : 99;
        g.setAttribute('opacity', (prog(t, t0 + 0.1, 0.25) * (1 - prog(t, t1 - 0.2, 0.2))).toFixed(3));
      });
    },
  };
})();
