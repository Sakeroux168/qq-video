// 镜头 31｜赶紧把这条转给你家那个一用微波炉就躲出厨房的人。爱你老己，也顺便爱一下他。关注我，每天一个生活冷知识，咱们下期见。
// 画面：开头那个躲门后的家人（剪影）从门框后走出来，站到微波炉旁；"转给家人"转发箭头；"爱你老己"；最后大号「＋关注我」按钮 + 星星挥手。
(() => {
  const DUR = 9;
  const { svg } = setupStage();
  const scene = el('g', {}, svg);

  // 与镜头 1 同一个厨房
  el('rect', { x: 380, y: 1054, width: 700, height: 70, fill: 'url(#counter)' }, scene);
  const mw = microwave(scene, { x: 440, y: 700, s: 0.68 });
  // 家人剪影（全身站立）
  const person = el('g', {}, scene);
  const P = 'translate(250 640) scale(1.45) translate(-250 -800)';
  const pb = el('g', { transform: P }, person);
  el('path', { d: 'M200,885 L262,885 Q336,882 348,965 L348,1320 Q348,1350 318,1350 L200,1350 Q170,1350 170,1320 L170,965 Q182,885 200,885 Z', fill: C.g3, stroke: C.cyan, 'stroke-width': 2, 'stroke-opacity': 0.35 }, pb);
  el('rect', { x: 248, y: 846, width: 34, height: 50, fill: C.g3 }, pb);
  el('ellipse', { cx: 265, cy: 800, rx: 60, ry: 70, fill: C.g3, stroke: C.cyan, 'stroke-width': 2, 'stroke-opacity': 0.35 }, pb);
  el('path', { d: 'M203,800 Q200,712 270,708 Q332,712 328,790 Q312,750 260,748 Q222,752 203,800 Z', fill: C.g2 }, pb);
  el('path', { d: 'M248,812 Q258,822 268,812 M282,812 Q292,822 302,812', fill: 'none', stroke: C.g6, 'stroke-width': 4, 'stroke-linecap': 'round' }, pb);
  el('path', { d: 'M255,840 Q270,852 290,840', fill: 'none', stroke: C.g6, 'stroke-width': 4, 'stroke-linecap': 'round' }, pb);
  // 门框（左侧墙）
  el('rect', { x: 0, y: 0, width: 140, height: 1920, fill: 'url(#wall)' }, scene);
  el('rect', { x: 126, y: 0, width: 30, height: 1920, fill: 'url(#metalH)' }, scene);

  // 转发箭头 + 文案
  const share = el('g', {}, svg);
  el('path', { d: 'M560,560 Q620,450 760,450 L760,400 L860,480 L760,560 L760,510 Q650,510 560,560 Z', fill: C.cyan }, share);
  text(share, 540, 360, [['转给', C.white], ['家人', C.cyan]], { size: 110, font: FONT.heavy });
  const love = el('g', {}, svg);
  text(love, 540, 360, [['爱你', C.white], ['老己', C.orange], ['，也爱他', C.white]], { size: 100, font: FONT.heavy });

  // 结尾卡：关注我
  const endG = el('g', {}, svg);
  el('rect', { x: 0, y: 0, width: 1080, height: 1920, fill: C.bg, opacity: 0.88 }, endG);
  const btn = el('g', {}, endG);
  el('rect', { x: 290, y: 760, width: 500, height: 170, rx: 85, fill: C.orange }, btn);
  text(btn, 540, 878, '＋ 关注我', { size: 92, font: FONT.heavy, color: C.bg });
  text(endG, 540, 620, [['每天一个', C.white], ['生活冷知识', C.cyan]], { size: 76, font: FONT.bold });
  text(endG, 540, 1080, '下期见', { size: 84, font: FONT.heavy, color: C.white });

  const xx = xingxing(svg, {
    x: 900, y: 1440, h: 430, flip: true,
    cues: [{ t: 0, pose: 'point' }, { t: 2.6, pose: 'heart' }, { t: 4.8, pose: 'talk' }, { t: 6.6, pose: 'wave' }],
    marks: [{ t: 2.7, type: 'heart', dur: 1.6 }],
    shadow: true,
  });

  window.SHOT = {
    duration: DUR,
    render(t) {
      mw.update(t, { on: 0, display: '0:00' });
      // 家人从门框后走出来，0.3~2.3s
      const w = prog(t, 0.3, 2.0);
      const bobY = w > 0 && w < 1 ? -6 * Math.abs(Math.sin(t * 7)) : 0;
      person.setAttribute('transform', `translate(${(-220 + 300 * w).toFixed(1)} ${bobY.toFixed(1)})`);
      enter(share, t, 0.4);
      share.setAttribute('opacity', Math.min(+share.getAttribute('opacity'), 1 - prog(t, 2.5, 0.25)));
      enter(love, t, 2.75);
      love.setAttribute('opacity', Math.min(+love.getAttribute('opacity'), 1 - prog(t, 4.6, 0.3)));
      // 结尾卡 4.8s
      endG.setAttribute('opacity', prog(t, 4.8, 0.4));
      popIn(btn, t, 5.1, 540, 845, 0.4, 0.9);
      // 按钮轻微呼吸，提示可点
      if (t > 5.6) btn.setAttribute('transform', `translate(540 845) scale(${(1 + 0.03 * Math.sin((t - 5.6) * 4)).toFixed(4)}) translate(-540 -845)`);
      xx.update(t);
    },
  };
})();
