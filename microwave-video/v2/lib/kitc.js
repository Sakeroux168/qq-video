// 风格 C 组件库：半写实物件 + 金色 HUD + 大号衬线字幕
const G = { gold: '#D9B77A', goldA: 'rgba(217,183,122,', ink: '#EDE3D2', red: '#D8584A', redA: 'rgba(216,88,74,', paperTop: [246, 238, 222], paperBack: [214, 203, 182] };

// 可见度：在 [a, b] 区间内显示，两端 0.3s 淡入淡出
const vis = (t, a, b, f = 0.3) => Math.min(easeOut(clamp((t - a) / f)), clamp((b - t) / f));
function withAlpha(a, fn) { if (a <= 0.003) return; ctx.save(); ctx.globalAlpha *= a; fn(); ctx.restore(); }
// 以 (cx,cy) 为中心缩放
function zoom(cx, cy, s, fn) { ctx.save(); ctx.translate(cx, cy); ctx.scale(s, s); ctx.translate(-cx, -cy); fn(); ctx.restore(); }

// ---------- 3D 纸
function makeCam(cx, cy, yaw, pitch, scale = 1, dist = 1800) {
  const cyw = Math.cos(yaw), syw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  return ([x, y, z]) => {
    const X = x * cyw - z * syw; let Z = x * syw + z * cyw;
    const Y = y * cp - Z * sp; Z = y * sp + Z * cp;
    const f = dist / (dist + Z) * scale;
    return [cx + X * f, cy - Y * f, Z];
  };
}
const shade = (rgb, k) => `rgb(${rgb.map(v => Math.round(Math.min(255, v * k))).join(',')})`;
function quad(cam, pts, rgb, light) {
  const p = pts.map(cam);
  ctx.beginPath(); p.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath();
  const g = ctx.createLinearGradient(p[0][0], p[0][1], p[2][0], p[2][1]);
  g.addColorStop(0, shade(rgb, light + 0.08)); g.addColorStop(1, shade(rgb, light * 0.9));
  ctx.fillStyle = g; ctx.fill();
  ctx.strokeStyle = G.goldA + '0.55)'; ctx.lineWidth = 1.6; ctx.stroke();
}
function paper3d(cam, a, b, theta) {
  const c0 = cam([0, -40, 0]);
  ctx.save(); ctx.filter = 'blur(24px)'; ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.beginPath(); ctx.ellipse(c0[0], c0[1] + 180, a * 0.9 * (1 - 0.45 * theta / Math.PI), 40, 0, 0, 6.283); ctx.fill(); ctx.restore();
  quad(cam, [[-a, 0, -b], [0, 0, -b], [0, 0, b], [-a, 0, b]], G.paperTop, 0.95);
  const c = Math.cos(theta), s = Math.sin(theta), eps = 3 * (theta / Math.PI);
  const pts = [[0, -b], [a, -b], [a, b], [0, b]].map(([x, z]) => [x * c, x * s + eps, z]);
  quad(cam, pts, c >= 0 ? G.paperTop : G.paperBack, theta < 0.01 ? 0.95 : 0.7 + 0.3 * Math.abs(c));
  const f0 = cam([0, 1, -b]), f1 = cam([0, 1, b]);
  ctx.save(); ctx.strokeStyle = `rgba(255,236,200,${0.25 + 0.5 * Math.sin(theta)})`; ctx.lineWidth = 2.5; ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.moveTo(f0[0], f0[1]); ctx.lineTo(f1[0], f1[1]); ctx.stroke(); ctx.restore();
}
// 2D 透视纸堆：底边中心 (cx, by)
function paperStack(cx, by, w, d, h, layers = 12) {
  const dx = d * 0.62, dy = d * 0.36, x0 = cx - (w + dx) / 2, x1 = x0 + w, top = by - h;
  ctx.save(); ctx.filter = 'blur(18px)'; ctx.fillStyle = 'rgba(0,0,0,0.6)';
  ctx.beginPath(); ctx.ellipse(cx, by + 8, (w + dx) * 0.6, 30, 0, 0, 6.283); ctx.fill(); ctx.restore();
  let g = ctx.createLinearGradient(0, top, 0, by); g.addColorStop(0, '#CFC2A8'); g.addColorStop(1, '#8F8370');
  ctx.fillStyle = g; ctx.fillRect(x0, top, w, h);
  g = ctx.createLinearGradient(x1, 0, x1 + dx, 0); g.addColorStop(0, '#A89A80'); g.addColorStop(1, '#6E6452');
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x1, top); ctx.lineTo(x1 + dx, top - dy); ctx.lineTo(x1 + dx, by - dy); ctx.lineTo(x1, by); ctx.closePath(); ctx.fill();
  g = ctx.createLinearGradient(x0, top - dy, x1, top); g.addColorStop(0, '#FFF8EA'); g.addColorStop(1, '#F3EAD8');
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x0, top); ctx.lineTo(x0 + dx, top - dy); ctx.lineTo(x1 + dx, top - dy); ctx.lineTo(x1, top); ctx.closePath(); ctx.fill();
  ctx.save(); ctx.strokeStyle = 'rgba(60,50,38,0.35)'; ctx.lineWidth = 1.1;
  const n = Math.min(layers, Math.floor(h / 4));
  for (let i = 1; i < n; i++) { const y = top + h * i / n; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.lineTo(x1 + dx, y - dy); ctx.stroke(); }
  ctx.restore();
  ctx.save(); ctx.strokeStyle = G.goldA + '0.55)'; ctx.lineWidth = 2; ctx.shadowColor = G.goldA + '0.8)'; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.moveTo(x0, by); ctx.lineTo(x0, top); ctx.lineTo(x0 + dx, top - dy); ctx.lineTo(x1 + dx, top - dy); ctx.lineTo(x1 + dx, by - dy); ctx.lineTo(x1, by); ctx.closePath();
  ctx.moveTo(x0, top); ctx.lineTo(x1, top); ctx.lineTo(x1 + dx, top - dy); ctx.moveTo(x1, top); ctx.lineTo(x1, by); ctx.stroke(); ctx.restore();
  return { top: top - dy, x0, x1: x1 + dx };
}
// 竖直纸柱（发光）
function column(x, yTop, yBot, w = 28) {
  const g = ctx.createLinearGradient(x - w / 2, 0, x + w / 2, 0);
  g.addColorStop(0, '#A89A80'); g.addColorStop(0.5, '#F3EAD8'); g.addColorStop(1, '#A89A80');
  ctx.save(); ctx.fillStyle = g; ctx.shadowColor = G.goldA + '0.9)'; ctx.shadowBlur = 34; ctx.fillRect(x - w / 2, yTop, w, yBot - yTop); ctx.restore();
  node(x, yTop, 8, 1, '#FFF2D6');
}

// ---------- 天体
function earth(cx, cy, r) {
  let g = ctx.createRadialGradient(cx - r * 0.25, cy - r * 0.6, r * 0.05, cx, cy, r * 1.05);
  g.addColorStop(0, '#6F8BA0'); g.addColorStop(0.6, '#2C3A47'); g.addColorStop(1, '#0E1218');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.fill();
  ctx.save(); ctx.strokeStyle = 'rgba(140,190,230,0.35)'; ctx.lineWidth = 6; ctx.shadowColor = 'rgba(140,190,230,0.8)'; ctx.shadowBlur = 30;
  ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, 6.283); ctx.stroke(); ctx.restore();
}
function moon(cx, cy, r, a = 1) {
  const g = ctx.createRadialGradient(cx - r * 0.35, cy - r * 0.35, r * 0.1, cx, cy, r * 1.1);
  g.addColorStop(0, '#F4EEE2'); g.addColorStop(0.7, '#A9A293'); g.addColorStop(1, '#4A463E');
  ctx.save(); ctx.globalAlpha *= a; ctx.shadowColor = 'rgba(255,240,210,0.7)'; ctx.shadowBlur = r * 0.6; ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.fill();
  ctx.shadowBlur = 0;
  for (const [x, y, rr] of [[-0.27, -0.18, 0.16], [0.32, 0.23, 0.11], [0.09, 0.45, 0.08], [-0.45, 0.36, 0.06]]) { ctx.fillStyle = 'rgba(80,74,64,0.35)'; ctx.beginPath(); ctx.arc(cx + x * r, cy + y * r, rr * r, 0, 6.283); ctx.fill(); }
  ctx.restore();
}
function sun(cx, cy, r, t) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  let g = ctx.createRadialGradient(cx, cy, r * 0.2, cx, cy, r * 2.4);
  g.addColorStop(0, 'rgba(255,214,140,0.9)'); g.addColorStop(0.4, 'rgba(255,170,80,0.35)'); g.addColorStop(1, 'rgba(255,140,60,0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r * 2.4, 0, 6.283); ctx.fill();
  ctx.restore();
  g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
  g.addColorStop(0, '#FFF6DC'); g.addColorStop(0.7, '#FFC36E'); g.addColorStop(1, '#E88A3A');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.fill();
  // 表面细微流动
  ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, r, 0, 6.283); ctx.clip(); ctx.globalAlpha = 0.15; ctx.strokeStyle = '#FFF3D0'; ctx.lineWidth = 3;
  for (let i = 0; i < 9; i++) { ctx.beginPath(); for (let k = 0; k <= 40; k++) { const a = k / 40 * 6.283; const rr = r * (0.3 + i * 0.08) + 6 * Math.sin(a * 5 + t * 0.8 + i); const x = cx + rr * Math.cos(a), y = cy + rr * Math.sin(a); k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
  ctx.restore();
}

// ---------- HUD
function tickRing(cx, cy, r, t, a) {
  withAlpha(a, () => {
    ctx.strokeStyle = G.goldA + '0.3)'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(cx, cy, r + 60, 0, 6.283); ctx.stroke();
    ctx.setLineDash([8, 10]); ctx.beginPath(); ctx.moveTo(70, cy); ctx.lineTo(W - 70, cy); ctx.moveTo(cx, cy - r - 150); ctx.lineTo(cx, cy + r + 120); ctx.stroke(); ctx.setLineDash([]);
    for (let i = 0; i < 72; i++) {
      const ang = i / 72 * 6.283 + t * 0.06, L = i % 6 === 0 ? 22 : 10;
      ctx.strokeStyle = G.goldA + (i % 6 === 0 ? '0.75)' : '0.35)');
      ctx.beginPath(); ctx.moveTo(cx + r * Math.cos(ang), cy + r * Math.sin(ang)); ctx.lineTo(cx + (r + L) * Math.cos(ang), cy + (r + L) * Math.sin(ang)); ctx.stroke();
    }
    ctx.shadowColor = G.goldA + '1)'; ctx.shadowBlur = 16; ctx.strokeStyle = G.gold; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(cx, cy, r - 14, -1.25 + t * 0.2, 0.9 + t * 0.2); ctx.stroke();
  });
}
function tag(x, y, big, small, a, color = G.ink, w = 260) {
  withAlpha(a, () => {
    ctx.strokeStyle = G.goldA + '0.7)'; ctx.lineWidth = 2; ctx.fillStyle = 'rgba(18,13,9,0.85)';
    ctx.beginPath(); ctx.roundRect(x - w / 2, y - 52, w, 104, 12); ctx.fill(); ctx.stroke();
  });
  serifText(big, x, y + 4, { size: 52, weight: 900, color, a });
  if (small) serifText(small, x, y + 40, { size: 26, weight: 600, color: G.goldA + '0.9)', a });
}
// 左上章节：大号金色数字 + 细线 + 小字
function chapter(a, big, unit, line2, lineP = 1) {
  if (a <= 0.01) return;
  serifText([[big, G.gold], [unit, G.ink]], 70, 230, { size: 112, weight: 700, a, align: 'left', spacing: 4 });
  withAlpha(a, () => { ctx.strokeStyle = G.goldA + '0.45)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(70, 262); ctx.lineTo(70 + 380 * lineP, 262); ctx.stroke(); });
  serifText(line2, 72, 316, { size: 40, weight: 600, a, align: 'left', spacing: 4 });
}
function bgWord(str, y, size, a) {
  withAlpha(a, () => { ctx.font = `900 ${size}px ${SERIF}`; ctx.textAlign = 'center'; ctx.letterSpacing = '20px'; ctx.fillStyle = 'rgba(120,100,70,0.14)'; ctx.fillText(str, 540, y); });
}
function bokeh(t) {
  const r = rng(21);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 14; i++) {
    const x = r() * W, y = r() * H * 0.8, s = 6 + r() * 16, a = 0.05 + r() * 0.12;
    const g = ctx.createRadialGradient(x, y, 0, x, y, s);
    g.addColorStop(0, `rgba(255,220,170,${a})`); g.addColorStop(1, 'rgba(255,220,170,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x + 10 * Math.sin(t * 0.3 + i), y, s, 0, 6.283); ctx.fill();
  }
  ctx.restore();
}
function floorLine(a, y = 1430) {
  withAlpha(a, () => {
    const g = ctx.createLinearGradient(0, y, 0, H); g.addColorStop(0, 'rgba(40,30,20,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0.9)');
    ctx.fillStyle = g; ctx.fillRect(0, y, W, H - y);
    ctx.strokeStyle = G.goldA + '0.18)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    ctx.strokeStyle = G.goldA + '0.22)'; ctx.beginPath(); ctx.ellipse(540, y + 10, 330, 46, 0, 0, 6.283); ctx.stroke();
  });
}
// 里程碑刻度：柱子在 x，向右写说明，向左写"第 N 次"
function milestone(x, y, right, left, a) {
  withAlpha(a, () => {
    ctx.strokeStyle = G.goldA + '0.7)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x + 20, y); ctx.lineTo(x + 100, y); ctx.stroke();
    ctx.fillStyle = G.gold; ctx.beginPath(); ctx.arc(x + 20, y, 6, 0, 6.283); ctx.fill();
  });
  serifText(right, x + 120, y + 15, { size: 46, weight: 700, color: G.ink, align: 'left', a });
  if (left) serifText(left, x - 30, y + 15, { size: 42, weight: 600, color: G.gold, align: 'right', a });
}
// 印章（红色方块 + 字）
function stamp(x, y, str, a, rot = -0.12, size = 92) {
  withAlpha(a, () => {
    ctx.translate(x, y); ctx.rotate(rot);
    const w = str.length * size + 60, h = size + 50;
    ctx.fillStyle = 'rgba(160,52,40,0.92)'; ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 20;
    ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 10); ctx.fill();
    ctx.shadowBlur = 0; ctx.strokeStyle = 'rgba(255,210,190,0.5)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.roundRect(-w / 2 + 10, -h / 2 + 10, w - 20, h - 20, 6); ctx.stroke();
    ctx.font = `900 ${size}px ${SERIF}`; ctx.textAlign = 'center'; ctx.fillStyle = '#FBE9DF'; ctx.fillText(str, 0, size * 0.36);
  });
}

// ---------- 字幕：底部大号衬线，数字和关键词自动标金，少数词标红
const GOLD_RE = /([0-9][0-9.,]*\s*(?:次|毫米|厘米|公里|米|年|万公里)?|月亮|太阳|翻一倍|太空的边界|后半段|42 次)/g;
const RED_WORDS = ['没人能', '折不动', '想放弃'];
function richParts(str) {
  for (const w of RED_WORDS) if (str.includes(w)) { const [a, b] = str.split(w); return [[a, G.ink], [w, G.red], [b, G.ink]]; }
  const parts = []; let last = 0; let m; GOLD_RE.lastIndex = 0;
  while ((m = GOLD_RE.exec(str))) { if (m.index > last) parts.push([str.slice(last, m.index), G.ink]); parts.push([m[0], G.gold]); last = m.index + m[0].length; }
  if (last < str.length) parts.push([str.slice(last), G.ink]);
  return parts;
}
function subtitles(t, list) {
  const g = ctx.createLinearGradient(0, 1520, 0, 1800); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.5, 'rgba(0,0,0,0.55)'); g.addColorStop(1, 'rgba(0,0,0,0.3)');
  ctx.fillStyle = g; ctx.fillRect(0, 1520, W, 280);
  for (const [a, b, s] of list) {
    if (t < a - 0.01 || t > b + 0.01) continue;
    const pin = clamp((t - a) / 0.22), pout = clamp((b - t) / 0.15), al = Math.min(easeOut(pin), pout);
    ctx.save(); ctx.font = `900 62px ${SERIF}`; const w = ctx.measureText(s).width; ctx.restore();
    const size = w > 960 ? Math.floor(62 * 960 / w) : 62;
    serifText(richParts(s), 540, 1660, { size, weight: 900, color: G.ink, a: al, blur: (1 - easeOut(pin)) * 8, spacing: 0 });
  }
}
