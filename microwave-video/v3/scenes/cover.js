// 封面（横屏 1920×1080）：左边是“他的账本”，你那一行墨迹最重；右边大字。
window.draw = function (t) {
  stage(t, { spot: 640, ring: 0.6, floorY: 920 });
  // 他的账本
  book(660, 540, 1000, () => {
    ledgerPage('别人欠我的', HIS_L, [1, 0.3, 0.25, 0], null, 0, false, 0);
    ctx.save(); ctx.globalAlpha = 0.38; ctx.fillStyle = '#C9862E'; ctx.fillRect(50, 160, 800, 100); ctx.restore();
    ctx.save(); ctx.font = `62px ${HAND}`; ctx.lineWidth = 2.5; ctx.strokeStyle = C.pen; ctx.textAlign = 'left'; ctx.strokeText('你', 72, 230); ctx.textAlign = 'right'; ctx.strokeText('¥200', 828, 230); ctx.restore();
  }, () => ledgerPage('我欠别人的', [['', ''], ['', ''], ['', ''], ['', '']], [0, 0, 0, 0], null, 0, false, 0), { cover: '#1E2A44', glowL: 0.9 });
  text('他的账本', 660, 205, { size: 46, weight: 900, color: C.gold, spacing: 8 });
  // 指向“你”那一行的金色标注
  ctx.save(); ctx.strokeStyle = C.goldA + '0.85)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(300, 395); ctx.lineTo(170, 300); ctx.lineTo(90, 300); ctx.stroke(); ctx.restore();
  text('墨迹最重', 90, 284, { size: 40, weight: 900, color: C.gold, align: 'left' });
  // 右侧文字
  ctx.save(); ctx.font = `700 40px ${SERIF}`; ctx.letterSpacing = '6px'; const tw = ctx.measureText('Vibe知识大赏').width; ctx.restore();
  ctx.save(); ctx.strokeStyle = C.goldA + '0.9)'; ctx.lineWidth = 2.5; ctx.fillStyle = 'rgba(20,14,9,0.8)'; ctx.beginPath(); ctx.roundRect(1200, 200, tw + 60, 76, 38); ctx.fill(); ctx.stroke(); ctx.restore();
  text('Vibe知识大赏', 1230, 252, { size: 40, weight: 700, color: C.gold, align: 'left', spacing: 6 });
  text('你忘掉的钱，', 1196, 450, { size: 112, weight: 900, color: C.ink, align: 'left', spacing: 4, shadow: 0.8 });
  text('他还记着。', 1196, 600, { size: 140, weight: 900, color: C.red, align: 'left', spacing: 6, glow: 0.3, glowColor: 'rgba(217,99,79,' });
  ctx.save(); ctx.strokeStyle = C.goldA + '0.5)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(1200, 668); ctx.lineTo(1780, 668); ctx.stroke(); ctx.restore();
  text([['大脑的账本', C.gold], [' · 钱 · 人情 · 功劳 · 伤害', C.ink]], 1200, 735, { size: 38, weight: 700, align: 'left', spacing: 3 });
  finishFrame(0.5);
};
