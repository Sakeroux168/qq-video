// 道具：手机聊天、立体账本、论文卡、划掉的标签、页签卡、标题卡。
// ---------- 手机（微信风格聊天，暗色）
// msgs: [{side:'L'|'R', text, kind:'text'|'pay', amount, note, t0}]，t0 之后出现
function phone(x, y, s, t, { title = '室友小王', msgs = [], a = 1, hi = 0, date = '' } = {}) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    const w = 420, h = 820;
    ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 60; ctx.fillStyle = '#0B0B0D'; ctx.beginPath(); ctx.roundRect(-w / 2 - 14, -h / 2 - 14, w + 28, h + 28, 56); ctx.fill(); ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(243,230,211,0.35)'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#17171A'; ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 44); ctx.fill();
    ctx.save(); ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 44); ctx.clip();
    ctx.fillStyle = '#1F1F23'; ctx.fillRect(-w / 2, -h / 2, w, 112);
    ctx.fillStyle = '#000'; ctx.beginPath(); ctx.roundRect(-60, -h / 2 + 14, 120, 30, 15); ctx.fill();
    text('‹', -w / 2 + 28, -h / 2 + 92, { size: 44, weight: 600, color: '#ddd', font: SANS, align: 'left' });
    text(title, 0, -h / 2 + 90, { size: 28, weight: 700, color: '#eee', font: SANS });
    if (hi > 0) withAlpha(hi, () => { ctx.strokeStyle = C.gold; ctx.lineWidth = 3; ctx.shadowColor = C.goldA + '1)'; ctx.shadowBlur = 18; ctx.beginPath(); ctx.roundRect(-90, -h / 2 + 58, 180, 46, 10); ctx.stroke(); });
    if (date) text(date, 0, -h / 2 + 160, { size: 20, weight: 500, color: '#888', font: SANS });
    let yy = -h / 2 + 200;
    for (const m of msgs) {
      const k = easeOut((t - m.t0) / 0.3); if (k <= 0) { continue; }
      ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 20);
      const L = m.side === 'L', ax = L ? -w / 2 + 24 : w / 2 - 24;
      ctx.fillStyle = L ? '#5A6B7C' : '#C9A46A'; ctx.beginPath(); ctx.roundRect(L ? ax : ax - 52, yy, 52, 52, 8); ctx.fill();
      if (m.kind === 'pay') {
        const bw = 250, bx = L ? ax + 64 : ax - 64 - bw;
        ctx.fillStyle = m.done ? '#C98A3E' : '#F0A13A'; ctx.beginPath(); ctx.roundRect(bx, yy, bw, 118, 10); ctx.fill();
        text('¥' + m.amount, bx + 78, yy + 56, { size: 34, weight: 700, color: '#fff', font: SANS, align: 'left' });
        text(m.note, bx + 78, yy + 88, { size: 20, weight: 500, color: '#fff', font: SANS, align: 'left', a: 0.9 });
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(bx + 40, yy + 52, 20, 0, 6.283); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(bx + 32, yy + 52); ctx.lineTo(bx + 48, yy + 52); ctx.moveTo(bx + 40, yy + 44); ctx.lineTo(bx + 48, yy + 52); ctx.lineTo(bx + 40, yy + 60); ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.92)'; ctx.fillRect(bx, yy + 100, bw, 18); text('微信转账', bx + 12, yy + 115, { size: 14, weight: 500, color: '#999', font: SANS, align: 'left' });
        yy += 140;
      } else {
        ctx.font = `500 26px ${SANS}`; const tw = Math.min(260, ctx.measureText(m.text).width);
        const bw = tw + 36, bx = L ? ax + 64 : ax - 64 - bw;
        ctx.fillStyle = L ? '#2C2C31' : '#3FA35B'; ctx.beginPath(); ctx.roundRect(bx, yy, bw, 56, 10); ctx.fill();
        text(m.text, bx + 18, yy + 37, { size: 26, weight: 500, color: '#F2F2F2', font: SANS, align: 'left', spacing: 0 });
        yy += 78;
      }
      ctx.restore();
    }
    ctx.restore(); ctx.restore();
  });
}
// ---------- 立体账本：页面先画到离屏画布（900×700），再按梯形透视贴上去
const PG = document.createElement('canvas'); PG.width = 900; PG.height = 700; const pgx = PG.getContext('2d');
function drawToPage(fn) { const save = ctx; ctx = pgx; pgx.setTransform(1, 0, 0, 1, 0, 0); pgx.clearRect(0, 0, 900, 700); fn(); ctx = save; }
function warp(img, iw, ih, tl, tr, bl, br) {
  const N = 140;
  for (let i = 0; i < N; i++) {
    const v0 = i / N, v1 = (i + 1) / N, xl = lerp(tl[0], bl[0], v0), xr = lerp(tr[0], br[0], v0), y0 = lerp(tl[1], bl[1], v0), y1 = lerp(tl[1], bl[1], v1);
    ctx.drawImage(img, 0, v0 * ih, iw, ih / N + 0.6, xl, y0, xr - xl, y1 - y0 + 0.9);
  }
}
// 账本条目
const LED_L = [['室友小王', '¥200'], ['老张', '帮他搬家'], ['同事', '替他顶班 ×2'], ['他', '那句话']];
const LED_R = [['表姐', '¥500'], ['小李', '两顿饭钱'], ['同事', '帮我改 PPT'], ['', '']];
// 一页账：标题 + 条目；ink[i]=第 i 行墨水浓度，write[i]=第 i 行写出的进度(0..1)，bold=加粗程度
function ledgerPage(title, rows, ink, write, bold = 0, cursor = false, t = 0) {
  const g = ctx.createLinearGradient(0, 0, 0, 700); g.addColorStop(0, '#EDE3CD'); g.addColorStop(1, '#DCCFB2'); ctx.fillStyle = g; ctx.fillRect(0, 0, 900, 700);
  text(title, 450, 96, { size: 64, weight: 900, color: '#3A2A1A' });
  ctx.strokeStyle = 'rgba(80,60,40,0.35)'; ctx.lineWidth = 2;
  rows.forEach(([who, what], i) => {
    const y = 230 + i * 118; ctx.beginPath(); ctx.moveTo(60, y + 26); ctx.lineTo(840, y + 26); ctx.stroke();
    const k = write ? write[i] : 1, a = ink[i]; if (!who || k <= 0 || a <= 0.01) return;
    ctx.save(); ctx.beginPath(); ctx.rect(0, y - 90, 70 + 780 * k, 130); ctx.clip();
    const size = 62;
    ctx.font = `${size}px ${HAND}`; ctx.fillStyle = C.pen; ctx.globalAlpha = a; ctx.textAlign = 'left'; ctx.fillText(who, 72, y);
    ctx.textAlign = 'right'; ctx.fillText(what, 828, y);
    if (bold > 0) { ctx.lineWidth = 3 * bold; ctx.strokeStyle = C.pen; ctx.textAlign = 'left'; ctx.strokeText(who, 72, y); ctx.textAlign = 'right'; ctx.strokeText(what, 828, y); }
    ctx.restore();
  });
  if (cursor && Math.floor(t * 2.2) % 2 === 0) { const i = rows.findIndex(r => !r[0]); const y = 230 + (i < 0 ? 3 : i) * 118; ctx.fillStyle = C.red; ctx.fillRect(78, y - 58, 6, 72); }
}
// 摊开的账本：中心 (cx, cy)，宽 bw；L/R 是两页的绘制函数；open 0..1 控制翻开
function book(cx, cy, bw, L, R, { open = 1, a = 1, glowL = 0 } = {}) {
  withAlpha(a, () => {
    const ph = bw * 0.52, topW = bw * 0.39, botW = bw * 0.5, ty = cy - ph / 2, by = cy + ph / 2;
    ctx.save(); ctx.filter = 'blur(28px)'; ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.beginPath(); ctx.ellipse(cx, by + 30, bw * 0.55, 70, 0, 0, 6.283); ctx.fill(); ctx.restore();
    ctx.fillStyle = '#4A1E17'; ctx.beginPath(); ctx.moveTo(cx - botW - 22, by + 16); ctx.lineTo(cx - topW - 14, ty - 8); ctx.lineTo(cx + topW + 14, ty - 8); ctx.lineTo(cx + botW + 22, by + 16); ctx.lineTo(cx, by + 30); ctx.closePath(); ctx.fill();
    // 右页先画（翻开时左页从右边翻过来）
    drawToPage(R); warp(PG, 900, 700, [cx + 6, ty + 10], [cx + topW, ty], [cx + 6, by + 18], [cx + botW, by]);
    const k = ease(open), lx = lerp(cx + topW, cx - topW, k), lbx = lerp(cx + botW, cx - botW, k);
    drawToPage(L); if (k > 0.5) warp(PG, 900, 700, [lx, ty], [cx - 6, ty + 10], [lbx, by], [cx - 6, by + 18]);
    else { ctx.fillStyle = '#5A261D'; ctx.beginPath(); ctx.moveTo(cx, ty + 10); ctx.lineTo(lx, ty); ctx.lineTo(lbx, by); ctx.lineTo(cx, by + 18); ctx.closePath(); ctx.fill(); }
    const sg = ctx.createLinearGradient(cx - 60, 0, cx + 60, 0); sg.addColorStop(0, 'rgba(0,0,0,0)'); sg.addColorStop(0.5, 'rgba(0,0,0,0.38)'); sg.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = sg; ctx.fillRect(cx - 60, ty + 8, 120, ph + 12);
    if (glowL > 0) withAlpha(glowL, () => { ctx.strokeStyle = C.gold; ctx.lineWidth = 3; ctx.shadowColor = C.goldA + '1)'; ctx.shadowBlur = 24; ctx.beginPath(); ctx.moveTo(cx - 6, ty + 10); ctx.lineTo(cx - topW, ty); ctx.lineTo(cx - botW, by); ctx.lineTo(cx - 6, by + 18); ctx.closePath(); ctx.stroke(); });
  });
}
// ---------- 论文卡（写实纸张 + 期刊名 + 年份）
function paperCard(x, y, s, a, { year, title, authors, journal, rot = -0.04 } = {}) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s);
    ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 40; ctx.shadowOffsetY = 16; ctx.fillStyle = '#ECE4D2'; ctx.fillRect(-230, -300, 460, 600); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
    { const [jn, yr] = journal.split(' · '); text(jn, 0, -262, { size: jn.length > 36 ? 15 : 18, weight: 600, color: '#6B5A45', spacing: 0 }); text(yr || '', 0, -240, { size: 16, weight: 600, color: '#8A7658' }); }
    ctx.strokeStyle = 'rgba(80,60,40,0.4)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(-190, -224); ctx.lineTo(190, -224); ctx.stroke();
    ctx.save(); ctx.font = `700 30px ${SERIF}`; ctx.fillStyle = '#2A1E12'; ctx.textAlign = 'center';
    const words = title.split(' '); let line = '', ly = -180; for (const w of words) { const tl = line ? line + ' ' + w : w; if (ctx.measureText(tl).width > 380) { ctx.fillText(line, 0, ly); ly += 40; line = w; } else line = tl; } ctx.fillText(line, 0, ly); ctx.restore();
    text(authors, 0, ly + 64 - (-180) + -180, { size: 20, weight: 600, color: '#5A4A38' });
    ctx.fillStyle = 'rgba(80,60,40,0.18)'; for (let i = 0; i < 9; i++) ctx.fillRect(-190, ly + 110 + i * 24, i % 3 === 2 ? 260 : 380, 8);
    ctx.restore();
  });
}
// 左上角大年份（会滚动）
function yearTag(a, year) { if (a <= 0.01) return; text(String(Math.round(year)), 70, 210, { size: 96, weight: 900, color: C.gold, align: 'left', a, glow: 0.25 }); }
// ---------- 标签（可被红线划掉）
function tag(x, y, str, a = 1, struck = 0, size = 40) {
  withAlpha(a, () => {
    ctx.font = `700 ${size}px ${SERIF}`; const w = ctx.measureText(str).width + 60, h = size + 36;
    ctx.fillStyle = 'rgba(20,14,10,0.92)'; ctx.strokeStyle = 'rgba(243,230,211,0.65)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 8); ctx.fill(); ctx.stroke();
    text(str, x, y + size * 0.36, { size, weight: 700, color: C.ink });
    if (struck > 0) { ctx.strokeStyle = C.red; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x - w / 2 - 8, y + 2); ctx.lineTo(x - w / 2 - 8 + (w + 16) * ease(struck), y - 4); ctx.stroke(); }
  });
}
// ---------- 页签卡（四页账）
function pageCard(x, y, s, a, num, name, { sealed = false, rot = 0, dim = 0, back = false } = {}) {
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s);
    ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 30; ctx.fillStyle = sealed ? '#3B1A14' : '#E9DFC9'; ctx.beginPath(); ctx.roundRect(-110, -150, 220, 300, 10); ctx.fill(); ctx.shadowBlur = 0;
    if (sealed) {
      ctx.strokeStyle = C.goldA + '0.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.roundRect(-96, -136, 192, 272, 6); ctx.stroke();
      if (back) { ctx.strokeStyle = C.goldA + '0.35)'; for (let i = 0; i < 5; i++) { ctx.beginPath(); ctx.roundRect(-70 + i * 8, -100 + i * 8, 140 - i * 16, 200 - i * 16, 4); ctx.stroke(); } ctx.restore(); return; }
      ctx.fillStyle = '#A8352A'; ctx.beginPath(); for (let i = 0; i < 14; i++) { const r = i % 2 ? 46 : 54, an = i / 14 * 6.283; ctx.lineTo(r * Math.cos(an), r * Math.sin(an)); } ctx.closePath(); ctx.fill();
      text('?', 0, 22, { size: 64, weight: 900, color: '#F6D9C8' });
    } else {
      text(num, 0, -60, { size: 44, weight: 900, color: '#9C7A44' });
      text(name, 0, 50, { size: name.length > 1 ? 72 : 96, weight: 900, color: '#2A1E12' });
    }
    if (dim > 0) { ctx.fillStyle = `rgba(10,7,5,${dim})`; ctx.beginPath(); ctx.roundRect(-110, -150, 220, 300, 10); ctx.fill(); }
    ctx.restore();
  });
}
// ---------- 全屏标题卡
function titleCard(t, t0, dur) {
  const k = clamp((t - t0) / dur); if (k <= 0 || k >= 1) return;
  const a = Math.min(easeOut((t - t0) / 0.35), clamp((t0 + dur - t) / 0.35));
  withAlpha(a, () => {
    ctx.fillStyle = 'rgba(10,7,5,0.92)'; ctx.fillRect(0, 0, W, H);
    // 放射细线
    ctx.save(); ctx.translate(W / 2, H / 2 - 30); ctx.strokeStyle = C.goldA + '0.08)'; ctx.lineWidth = 1.5;
    for (let i = 0; i < 64; i++) { const an = i / 64 * 6.283 + t * 0.03; ctx.beginPath(); ctx.moveTo(140 * Math.cos(an), 140 * Math.sin(an)); ctx.lineTo(1100 * Math.cos(an), 1100 * Math.sin(an)); ctx.stroke(); }
    ctx.restore();
    const z = 1.06 - 0.06 * easeOut((t - t0) / 1.2);
    ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-W / 2, -H / 2);
    text('大脑的账本', W / 2, H / 2 + 20, { size: 168, weight: 900, color: C.gold, spacing: 20, glow: 0.45 });
    text('THE LEDGER IN YOUR HEAD', W / 2, H / 2 + 100, { size: 26, weight: 600, color: C.ink, spacing: 12, a: 0.6 });
    ctx.restore();
  });
}
