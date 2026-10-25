// 封面 4:3 版：只画在中间 1440×1080 里，渲染后裁掉两边。上面大字，下面“他的账本”。
window.draw = function (t) {
  stage(t, { spot: 960, ring: 0.6, floorY: 990 });
  book(960, 690, 900, () => {
    ledgerPage('别人欠我的', HIS_L, [1, 0.3, 0.25, 0], null, 0, false, 0);
    ctx.save(); ctx.globalAlpha = 0.38; ctx.fillStyle = '#C9862E'; ctx.fillRect(50, 160, 800, 100); ctx.restore();
    ctx.save(); ctx.font = `62px ${HAND}`; ctx.lineWidth = 2.5; ctx.strokeStyle = C.pen; ctx.textAlign = 'left'; ctx.strokeText('你', 72, 230); ctx.textAlign = 'right'; ctx.strokeText('¥200', 828, 230); ctx.restore();
  }, () => ledgerPage('我欠别人的', [['', ''], ['', ''], ['', ''], ['', '']], [0, 0, 0, 0], null, 0, false, 0), { cover: '#1E2A44', glowL: 0.9 });
  ctx.save(); ctx.strokeStyle = C.goldA + '0.85)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(640, 595); ctx.lineTo(520, 520); ctx.lineTo(300, 520); ctx.stroke(); ctx.restore();
  text('墨迹最重', 300, 504, { size: 38, weight: 900, color: C.gold, align: 'left' });
  text('他的账本', 1460, 504, { size: 38, weight: 900, color: C.gold, align: 'left' });
  ctx.save(); ctx.font = `700 34px ${SERIF}`; ctx.letterSpacing = '6px'; const tw = ctx.measureText('Vibe知识大赏').width; ctx.restore();
  ctx.save(); ctx.strokeStyle = C.goldA + '0.9)'; ctx.lineWidth = 2.5; ctx.fillStyle = 'rgba(20,14,9,0.8)'; ctx.beginPath(); ctx.roundRect(960 - (tw + 56) / 2, 60, tw + 56, 66, 33); ctx.fill(); ctx.stroke(); ctx.restore();
  text('Vibe知识大赏', 960, 105, { size: 34, weight: 700, color: C.gold, spacing: 6 });
  text([['你忘掉的钱，', C.ink], ['他还记着。', C.red]], 960, 280, { size: 104, weight: 900, spacing: 4, shadow: 0.8 });
  text([['大脑的账本', C.gold], [' · 钱 · 人情 · 功劳 · 伤害', C.ink]], 960, 360, { size: 34, weight: 700, spacing: 3 });
  finishFrame(0.5);
};
