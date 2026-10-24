// 第二批道具：日历、对比条、礼簿、“忙”气球、百分比表盘、便利贴、线描图标、计数、相框（可打码）、天平、手机输入框/账单。
function calendar(x, y, a, top, big, sub = '') {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 30; ctx.fillStyle = C.paper; ctx.fillRect(-110, -120, 220, 240); ctx.shadowBlur = 0;
    ctx.fillStyle = '#A8352A'; ctx.fillRect(-110, -120, 220, 60);
    text(top, 0, -78, { size: 28, weight: 700, color: '#F6E9D8' });
    text(big, 0, 40, { size: 96, weight: 900, color: '#2A1E12' });
    if (sub) text(sub, 0, 92, { size: 22, weight: 600, color: '#6B5A45' });
    ctx.restore();
  });
}
// 横条对比：rows=[[标签, 比例, 颜色]]
function bars(x, y, w, a, rows, k = 1) {
  withAlpha(a, () => {
    rows.forEach(([lab, v, col], i) => {
      const yy = y + i * 90;
      text(lab, x - 24, yy + 16, { size: 34, weight: 700, color: C.ink, align: 'right' });
      ctx.fillStyle = 'rgba(243,230,211,0.12)'; ctx.fillRect(x, yy - 22, w, 44);
      ctx.fillStyle = col; ctx.fillRect(x, yy - 22, w * v * ease(k), 44);
    });
  });
}
// 礼簿：红封皮，竖排人名和金额
function giftBook(x, y, s, a, t) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 40; ctx.fillStyle = '#8E2A20'; ctx.fillRect(-330, -230, 660, 460); ctx.shadowBlur = 0;
    ctx.fillStyle = '#EFE3C8'; ctx.fillRect(-310, -210, 620, 420);
    ctx.strokeStyle = 'rgba(160,40,30,0.55)'; ctx.lineWidth = 2;
    const rows = [['张建国', '贰佰'], ['李秀兰', '伍佰'], ['王师傅', '叁佰'], ['刘家', '陆佰'], ['陈姐', '贰佰'], ['小赵', '叁佰']];
    rows.forEach(([n, m], i) => {
      const cx = 250 - i * 100; ctx.beginPath(); ctx.moveTo(cx + 50, -190); ctx.lineTo(cx + 50, 190); ctx.stroke();
      const k = clamp((t - i * 0.12) / 0.3);
      ctx.save(); ctx.globalAlpha *= k; ctx.font = `46px ${HAND}`; ctx.fillStyle = C.pen; ctx.textAlign = 'center';
      [...n].forEach((ch, j) => ctx.fillText(ch, cx, -140 + j * 52));
      ctx.fillStyle = '#9B2A1E'; [...m].forEach((ch, j) => ctx.fillText(ch, cx, 70 + j * 52)); ctx.restore();
    });
    ctx.restore();
  });
}
// “忙”气球：半径 r
function favorBalloon(x, y, r, a, label = '忙') {
  withAlpha(a, () => {
    ctx.save(); const g = ctx.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r); g.addColorStop(0, '#F5D9A0'); g.addColorStop(1, '#B8843E');
    ctx.shadowColor = C.goldA + '0.7)'; ctx.shadowBlur = r * 0.5; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill(); ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(243,230,211,0.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, y + r); ctx.quadraticCurveTo(x + 12, y + r + 40, x, y + r + 90); ctx.stroke();
    text(label, x, y + r * 0.34, { size: r, weight: 900, color: '#4A2E12' });
    ctx.restore();
  });
}
// 半圆表盘：v 0..1
function gauge(x, y, r, a, v, label = '') {
  withAlpha(a, () => {
    ctx.save(); ctx.lineCap = 'round';
    ctx.strokeStyle = 'rgba(243,230,211,0.18)'; ctx.lineWidth = 26; ctx.beginPath(); ctx.arc(x, y, r, Math.PI, 2 * Math.PI); ctx.stroke();
    ctx.strokeStyle = C.gold; ctx.shadowColor = C.goldA + '0.8)'; ctx.shadowBlur = 16; ctx.beginPath(); ctx.arc(x, y, r, Math.PI, Math.PI * (1 + v)); ctx.stroke(); ctx.shadowBlur = 0;
    for (let i = 0; i <= 10; i++) { const an = Math.PI * (1 + i / 10); ctx.strokeStyle = 'rgba(243,230,211,0.5)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x + (r - 40) * Math.cos(an), y + (r - 40) * Math.sin(an)); ctx.lineTo(x + (r - 24) * Math.cos(an), y + (r - 24) * Math.sin(an)); ctx.stroke(); }
    const an = Math.PI * (1 + v); ctx.strokeStyle = C.ink; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + (r - 50) * Math.cos(an), y + (r - 50) * Math.sin(an)); ctx.stroke();
    ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(x, y, 12, 0, 6.283); ctx.fill();
    ctx.restore();
    text(Math.round(v * 100) + '%', x, y + 90, { size: 72, weight: 900, color: C.gold });
    if (label) text(label, x, y - r - 40, { size: 36, weight: 700, color: C.ink });
  });
}
function sticky(x, y, a, str, rot = -0.06, struck = 0) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 20; ctx.fillStyle = '#E8C66A'; ctx.fillRect(-120, -80, 240, 160); ctx.shadowBlur = 0;
    ctx.font = `60px ${HAND}`; ctx.fillStyle = C.pen; ctx.textAlign = 'center'; ctx.fillText(str, 0, 22);
    if (struck > 0) { ctx.strokeStyle = C.red; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(-90, 4); ctx.lineTo(-90 + 180 * ease(struck), 0); ctx.stroke(); }
    ctx.restore();
  });
}
// 线描小图标（白描，尺寸约 100）
function icon(kind, x, y, s = 1, a = 1, col = C.ink) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    if (kind === 'bowl') { ctx.moveTo(-46, -6); ctx.lineTo(46, -6); ctx.quadraticCurveTo(40, 40, 0, 42); ctx.quadraticCurveTo(-40, 40, -46, -6); ctx.moveTo(-20, -18); ctx.quadraticCurveTo(-10, -36, -20, -50); ctx.moveTo(10, -18); ctx.quadraticCurveTo(20, -36, 10, -50); }
    if (kind === 'mop') { ctx.moveTo(30, -60); ctx.lineTo(-6, 26); ctx.moveTo(-40, 30); ctx.lineTo(30, 30); ctx.lineTo(24, 50); ctx.lineTo(-46, 50); ctx.closePath(); }
    if (kind === 'trash') { ctx.moveTo(-34, -30); ctx.lineTo(34, -30); ctx.moveTo(-28, -30); ctx.lineTo(-22, 46); ctx.lineTo(22, 46); ctx.lineTo(28, -30); ctx.moveTo(-10, -30); ctx.lineTo(-8, -42); ctx.lineTo(8, -42); ctx.lineTo(10, -30); ctx.moveTo(-8, -14); ctx.lineTo(-6, 34); ctx.moveTo(8, -14); ctx.lineTo(6, 34); }
    if (kind === 'bill') { ctx.rect(-34, -46, 68, 92); ctx.moveTo(-20, -24); ctx.lineTo(20, -24); ctx.moveTo(-20, -4); ctx.lineTo(20, -4); ctx.moveTo(-20, 16); ctx.lineTo(6, 16); }
    if (kind === 'dish') { ctx.ellipse(0, 10, 50, 16, 0, 0, 6.283); ctx.moveTo(-30, 0); ctx.quadraticCurveTo(0, -30, 30, 0); }
    if (kind === 'laundry') { ctx.rect(-40, -46, 80, 92); ctx.moveTo(0, 14); ctx.arc(0, 8, 24, 0, 6.283); ctx.moveTo(-28, -32); ctx.lineTo(-14, -32); }
    if (kind === 'ppt') { ctx.rect(-50, -36, 100, 66); ctx.moveTo(0, 30); ctx.lineTo(0, 48); ctx.moveTo(-24, 48); ctx.lineTo(24, 48); ctx.moveTo(-30, 10); ctx.lineTo(-30, -6); ctx.moveTo(-12, 10); ctx.lineTo(-12, -16); ctx.moveTo(6, 10); ctx.lineTo(6, -2); ctx.moveTo(24, 10); ctx.lineTo(24, -22); }
    if (kind === 'box') { ctx.rect(-46, -30, 92, 70); ctx.moveTo(-46, -30); ctx.lineTo(-30, -48); ctx.lineTo(62, -48); ctx.lineTo(46, -30); ctx.moveTo(62, -48); ctx.lineTo(62, 22); ctx.lineTo(46, 40); }
    ctx.stroke(); ctx.restore();
  });
}
// 计数：正字
function tally(x, y, n, a, col = C.ink, size = 70) {
  withAlpha(a, () => { const full = Math.floor(n / 5), rest = n % 5; let s = '正'.repeat(full); text(s + (rest ? '丨'.repeat(rest) : ''), x, y, { size, weight: 900, color: col, spacing: 6 }); });
}
// 相框（里面画一个小场景），pix>0 时打马赛克，blur>0 时虚化
const PH = document.createElement('canvas'); PH.width = 480; PH.height = 360; const phx = PH.getContext('2d');
const PHS = document.createElement('canvas'); const phs = PHS.getContext('2d');
function photo(x, y, s, a, drawFn, { pix = 0, blur = 0, label = '', labelCol = C.ink, rot = 0 } = {}) {
  withAlpha(a, () => {
    const save = ctx; ctx = phx; phx.setTransform(1, 0, 0, 1, 0, 0); phx.fillStyle = '#2B2219'; phx.fillRect(0, 0, 480, 360); drawFn(); ctx = save;
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s);
    ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 40; ctx.fillStyle = '#EFE7D6'; ctx.fillRect(-264, -210, 528, 460); ctx.shadowBlur = 0;
    if (pix > 1) { const w = Math.max(4, Math.round(480 / pix)), h = Math.max(3, Math.round(360 / pix)); PHS.width = w; PHS.height = h; phs.drawImage(PH, 0, 0, w, h); ctx.imageSmoothingEnabled = false; ctx.drawImage(PHS, -240, -186, 480, 360); ctx.imageSmoothingEnabled = true; }
    else { if (blur > 0.3) ctx.filter = `blur(${blur}px)`; ctx.drawImage(PH, -240, -186, 480, 360); ctx.filter = 'none'; }
    if (label) text(label, 0, 226, { size: 34, weight: 900, color: '#3A2A1A' });
    ctx.restore();
  });
}
// 天平：tilt 正数向右倾
function balance(x, y, a, tilt, Ltxt, Rtxt) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.strokeStyle = C.ink; ctx.lineWidth = 5; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 260); ctx.moveTo(-80, 260); ctx.lineTo(80, 260); ctx.stroke();
    ctx.rotate(tilt); ctx.beginPath(); ctx.moveTo(-300, 0); ctx.lineTo(300, 0); ctx.stroke();
    for (const [sx, str] of [[-300, Ltxt], [300, Rtxt]]) {
      ctx.save(); ctx.translate(sx, 0); ctx.rotate(-tilt);
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-70, 110); ctx.moveTo(0, 0); ctx.lineTo(70, 110); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(-90, 110); ctx.quadraticCurveTo(0, 150, 90, 110); ctx.stroke();
      text(str, 0, 92, { size: 46, weight: 900, color: C.gold });
      ctx.restore();
    }
    ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(0, 0, 10, 0, 6.283); ctx.fill(); ctx.restore();
  });
}
// 手机：输入框打字/删除（typed 是当前显示的文字）
function phoneInput(x, y, s, a, typed, t) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    ctx.fillStyle = '#26262A'; ctx.beginPath(); ctx.roundRect(-190, 330, 380, 64, 12); ctx.fill();
    text(typed, -170, 372, { size: 26, weight: 500, color: '#eee', font: SANS, align: 'left', spacing: 0 });
    ctx.font = `500 26px ${SANS}`; const w = ctx.measureText(typed).width;
    if (Math.floor(t * 2.4) % 2 === 0) { ctx.fillStyle = '#5DBB72'; ctx.fillRect(-168 + w, 346, 3, 32); }
    ctx.restore();
  });
}
// 打字机：在 [t0, t1] 打出 str，[t2, t3] 删掉
function typing(t, str, t0, t1, t2 = 1e9, t3 = 1e9) {
  const n = str.length; let k = Math.floor(n * clamp((t - t0) / (t1 - t0)));
  if (t > t2) k = Math.floor(n * (1 - clamp((t - t2) / (t3 - t2))));
  return str.slice(0, k);
}
// 微信账单列表
function billList(x, y, s, a, rows, hiIdx = -1, hi = 0) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 60; ctx.fillStyle = '#0B0B0D'; ctx.beginPath(); ctx.roundRect(-224, -424, 448, 848, 56); ctx.fill(); ctx.shadowBlur = 0;
    ctx.fillStyle = '#17171A'; ctx.beginPath(); ctx.roundRect(-210, -410, 420, 820, 44); ctx.fill();
    text('账单', 0, -320, { size: 30, weight: 700, color: '#eee', font: SANS });
    rows.forEach(([who, note, amt, inc], i) => {
      const yy = -250 + i * 110;
      if (i === hiIdx && hi > 0) withAlpha(hi, () => { ctx.fillStyle = 'rgba(226,182,110,0.18)'; ctx.fillRect(-200, yy - 46, 400, 100); ctx.strokeStyle = C.gold; ctx.lineWidth = 3; ctx.strokeRect(-200, yy - 46, 400, 100); });
      ctx.fillStyle = inc ? '#C9A46A' : '#5A6B7C'; ctx.beginPath(); ctx.arc(-160, yy, 26, 0, 6.283); ctx.fill();
      text(who, -118, yy - 4, { size: 26, weight: 700, color: '#eee', font: SANS, align: 'left', spacing: 0 });
      text(note, -118, yy + 30, { size: 18, weight: 500, color: '#999', font: SANS, align: 'left', spacing: 0 });
      text(amt, 186, yy + 8, { size: 28, weight: 700, color: inc ? '#E6B86A' : '#eee', font: SANS, align: 'right', spacing: 0 });
      ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(-200, yy + 54); ctx.lineTo(200, yy + 54); ctx.stroke();
    });
    ctx.restore();
  });
}
// 话语气泡（对话用）：尾巴指向 (tx, ty)
function speech(x, y, str, a, { size = 44, col = C.ink, bg = 'rgba(24,18,13,0.94)', tx = null, ty = null, border = C.ink } = {}) {
  withAlpha(a, () => {
    ctx.save(); ctx.font = `700 ${size}px ${SERIF}`; const w = ctx.measureText(str).width + 70, h = size + 50;
    ctx.fillStyle = bg; ctx.strokeStyle = border; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 20); ctx.fill(); ctx.stroke();
    if (tx !== null) { ctx.beginPath(); ctx.moveTo(x - 20, y + h / 2 - 2); ctx.lineTo(tx, ty); ctx.lineTo(x + 20, y + h / 2 - 2); ctx.fill(); ctx.stroke(); ctx.fillRect(x - 18, y + h / 2 - 6, 36, 6); }
    ctx.restore();
    text(str, x, y + size * 0.36, { size, weight: 700, color: col });
  });
}
