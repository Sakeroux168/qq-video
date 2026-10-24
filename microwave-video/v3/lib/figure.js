// 线描小人（风格 B）：白描轮廓、深色填充。姿势 = 两只手臂的肩/肘角度 + 头部倾斜；表情 = 眼和嘴。
// 用法：figure(x, y, s, t, { pose: 'stand', face: 'smile', prop: 'phone', flip: false, a: 1 })
// 姿势切换用 blendPose(pA, pB, k) 做平滑过渡。
const POSES = {
  //            左臂[肩,肘]      右臂[肩,肘]      头倾斜  身体前倾
  stand:     { L: [100, 10],  R: [80, -10],  head: 0, lean: 0 },
  phone:     { L: [100, 10],  R: [60, -120], head: 0.12, lean: 0.03 },   // 右手举手机到胸前看
  think:     { L: [100, 10],  R: [40, -150], head: -0.1, lean: 0 },      // 右手托下巴
  scratch:   { L: [100, 10],  R: [-60, -110], head: 0.12, lean: 0 },     // 右手挠头
  point:     { L: [100, 10],  R: [-5, 10],   head: -0.05, lean: 0.02 },   // 右手平伸指向
  hips:      { L: [140, -100], R: [40, 100], head: -0.08, lean: -0.02 },  // 叉腰
  shrug:     { L: [150, -120], R: [30, 120], head: 0.15, lean: 0 },       // 摊手
  hold:      { L: [70, -60], R: [110, 60], head: 0.05, lean: 0.02 },     // 双手捧着东西在胸前
  cross:     { L: [60, 110], R: [120, -110], head: -0.1, lean: -0.03 },   // 抱臂（生气）
  wave:      { L: [100, 10], R: [-80, -40], head: 0, lean: 0 },
};
function blendPose(a, b, k) {
  const A = typeof a === 'string' ? POSES[a] : a, B = typeof b === 'string' ? POSES[b] : b;
  return { L: [lerp(A.L[0], B.L[0], k), lerp(A.L[1], B.L[1], k)], R: [lerp(A.R[0], B.R[0], k), lerp(A.R[1], B.R[1], k)], head: lerp(A.head, B.head, k), lean: lerp(A.lean, B.lean, k) };
}
// 根据一串 [时间, 姿势] 关键帧求当前姿势（每次切换 0.35s 过渡）
function poseAt(t, keys) {
  let cur = keys[0][1], prev = keys[0][1], ts = -9;
  for (const [k, p] of keys) if (t >= k) { prev = cur; cur = p; ts = k; }
  return blendPose(prev, cur, ease((t - ts) / 0.35));
}
const faceAt = (t, keys) => { let f = keys[0][1]; for (const [k, v] of keys) if (t >= k) f = v; return f; };
const D2R = Math.PI / 180;
function figure(x, y, s, t, { pose = 'stand', face = 'neutral', prop = null, flip = false, a = 1, hair = 0, seed = 0, color = C.ink } = {}) {
  const P = typeof pose === 'string' ? POSES[pose] : pose;
  withAlpha(a, () => {
    ctx.save(); ctx.translate(x, y); ctx.scale(flip ? -s : s, s);
    const breath = Math.sin(t * 2.2 + seed) * 2;
    ctx.strokeStyle = color; ctx.lineWidth = 4.5; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.fillStyle = '#17110C';
    // 腿（脚底在 y=0）
    ctx.beginPath(); ctx.moveTo(-24, -150); ctx.lineTo(-30, -4); ctx.lineTo(-54, 0); ctx.moveTo(24, -150); ctx.lineTo(30, -4); ctx.lineTo(54, 0); ctx.stroke();
    ctx.rotate(P.lean);
    // 身体
    ctx.beginPath(); ctx.moveTo(-34, -262 + breath); ctx.quadraticCurveTo(-60, -210, -58, -148); ctx.lineTo(58, -148); ctx.quadraticCurveTo(60, -210, 34, -262 + breath); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, -256 + breath); ctx.lineTo(0, -150); ctx.stroke();
    // 手臂：肩在 (±40, -244)，上臂 62，前臂 58
    const arm = (side, [sh, el]) => {
      const sx = side * 40, sy = -244 + breath;
      const a1 = (side > 0 ? sh : 180 - sh) * D2R, a2 = a1 + (side > 0 ? el : -el) * D2R;
      const ex = sx + 62 * Math.cos(a1), ey = sy + 62 * Math.sin(a1), hx = ex + 58 * Math.cos(a2), hy = ey + 58 * Math.sin(a2);
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.quadraticCurveTo(ex, ey, hx, hy); ctx.stroke();
      return [hx, hy, a2];
    };
    arm(-1, P.L); const [hx, hy, ha] = arm(1, P.R);
    // 手上的道具
    if (prop === 'phone') { ctx.save(); ctx.translate(hx, hy); ctx.rotate(-0.25); ctx.fillStyle = '#0E0B08'; ctx.strokeStyle = color; ctx.lineWidth = 3.5; ctx.beginPath(); ctx.roundRect(-16, -44, 34, 58, 6); ctx.fill(); ctx.stroke(); ctx.fillStyle = 'rgba(160,210,255,0.55)'; ctx.fillRect(-11, -38, 24, 44); ctx.restore(); }
    if (prop === 'pen') { ctx.save(); ctx.strokeStyle = C.gold; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(hx + 44 * Math.cos(ha - 0.6), hy + 44 * Math.sin(ha - 0.6)); ctx.stroke(); ctx.restore(); }
    // 头
    ctx.save(); ctx.translate(0, -312 + breath); ctx.rotate(P.head);
    ctx.fillStyle = '#17110C'; ctx.beginPath(); ctx.arc(0, 0, 50, 0, 6.283); ctx.fill(); ctx.stroke();
    // 头发：0 短发刘海，1 中分，2 马尾
    ctx.fillStyle = color; ctx.beginPath();
    if (hair === 0) { ctx.moveTo(-46, -18); ctx.quadraticCurveTo(-10, -66, 44, -26); ctx.quadraticCurveTo(10, -40, -46, -18); }
    else if (hair === 1) { ctx.moveTo(-48, -6); ctx.quadraticCurveTo(-40, -56, 0, -52); ctx.quadraticCurveTo(40, -56, 48, -6); ctx.quadraticCurveTo(30, -36, 0, -40); ctx.quadraticCurveTo(-30, -36, -48, -6); }
    else { ctx.moveTo(-46, -14); ctx.quadraticCurveTo(0, -70, 46, -14); ctx.quadraticCurveTo(0, -42, -46, -14); ctx.moveTo(-40, -30); ctx.quadraticCurveTo(-90, -10, -76, 40); ctx.quadraticCurveTo(-70, 0, -44, -18); }
    ctx.fill();
    // 眨眼：约 3.5 秒一次
    const blink = ((t + seed * 1.7) % 3.6) < 0.12;
    ctx.fillStyle = color; ctx.strokeStyle = color; ctx.lineWidth = 4;
    const eye = (ex) => { if (blink || face === 'happy') { ctx.beginPath(); ctx.moveTo(ex - 6, 0); ctx.quadraticCurveTo(ex, face === 'happy' ? -7 : 2, ex + 6, 0); ctx.stroke(); } else { ctx.beginPath(); ctx.arc(ex, -2, face === 'shock' ? 7 : 5, 0, 6.283); ctx.fill(); } };
    eye(10); eye(32);
    ctx.beginPath();
    if (face === 'smile' || face === 'happy') { ctx.arc(22, 16, 11, 0.25, Math.PI - 0.25); }
    else if (face === 'smug') { ctx.moveTo(10, 20); ctx.quadraticCurveTo(26, 26, 36, 12); }
    else if (face === 'sad') { ctx.arc(22, 30, 10, Math.PI + 0.4, -0.4); }
    else if (face === 'shock') { ctx.ellipse(22, 22, 6, 9, 0, 0, 6.283); }
    else if (face === 'angry') { ctx.moveTo(12, 24); ctx.lineTo(34, 22); ctx.moveTo(4, -16); ctx.lineTo(16, -10); ctx.moveTo(40, -16); ctx.lineTo(28, -10); }
    else if (face === 'confused') { ctx.moveTo(12, 22); ctx.quadraticCurveTo(20, 16, 26, 22); ctx.quadraticCurveTo(32, 28, 36, 20); }
    else { ctx.moveTo(14, 20); ctx.lineTo(32, 20); }
    ctx.stroke();
    ctx.restore();
    ctx.restore();
  });
}
// 头顶符号：问号、汗滴、感叹号、省略号
function mark(x, y, type, a, t) {
  withAlpha(a, () => {
    const bob = Math.sin(t * 4) * 4;
    if (type === '?') text('?', x, y + bob, { size: 80, weight: 900, color: C.gold });
    if (type === '!') text('!', x, y + bob, { size: 84, weight: 900, color: C.red });
    if (type === '...') text('…', x, y + bob, { size: 70, weight: 900, color: C.ink });
    if (type === 'sweat') { ctx.fillStyle = 'rgba(160,210,255,0.85)'; ctx.beginPath(); ctx.moveTo(x, y - 30 + bob); ctx.quadraticCurveTo(x + 18, y + bob, x, y + 12 + bob); ctx.quadraticCurveTo(x - 18, y + bob, x, y - 30 + bob); ctx.fill(); }
  });
}
// 想法气泡：内容由 draw() 画在气泡中心坐标系里
function bubble(x, y, w, h, a, draw, tailX = -0.3) {
  withAlpha(a, () => {
    ctx.save(); ctx.fillStyle = 'rgba(24,18,13,0.92)'; ctx.strokeStyle = C.ink; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 26); ctx.fill(); ctx.stroke();
    for (const [dx, dy, r] of [[tailX * w, h / 2 + 24, 12], [tailX * w * 1.35, h / 2 + 52, 7]]) { ctx.beginPath(); ctx.arc(x + dx, y + dy, r, 0, 6.283); ctx.fill(); ctx.stroke(); }
    ctx.translate(x, y); draw(); ctx.restore();
  });
}
