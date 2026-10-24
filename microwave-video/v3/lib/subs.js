// 底部字幕：衬线，数字和关键词金色，少数词红色。list: [[开始, 结束, 文字]]
const SUB_GOLD = /(\d[\d,.]*\s*(?:年|块|元|次|%)?|¥\d+|墨水加粗|钱|人情|功劳|伤害|记得更牢|交情|墨迹最重|原图保存|一整份|两百)/g;
const SUB_RED = /(自动褪色|更容易忘|卡住了吧|对不上|打了码|不好意思催|交易|褪色了)/g;
function subParts(s) {
  const marks = [];
  for (const [re, col] of [[SUB_RED, C.red], [SUB_GOLD, C.gold]]) { re.lastIndex = 0; let m; while ((m = re.exec(s))) marks.push([m.index, m.index + m[0].length, col]); }
  marks.sort((a, b) => a[0] - b[0]);
  const out = []; let i = 0;
  for (const [a, b, col] of marks) { if (a < i) continue; if (a > i) out.push([s.slice(i, a), C.ink]); out.push([s.slice(a, b), col]); i = b; }
  if (i < s.length) out.push([s.slice(i), C.ink]);
  return out;
}
function subtitles(t, list) {
  for (const [a, b, s] of list) {
    if (t < a - 0.05 || t > b + 0.12) continue;
    const k = Math.min(clamp((t - a + 0.05) / 0.12), clamp((b + 0.12 - t) / 0.12));
    const g = ctx.createLinearGradient(0, H - 190, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${0.55 * k})`); ctx.fillStyle = g; ctx.fillRect(0, H - 190, W, 190);
    text(subParts(s), W / 2, H - 70, { size: 50, weight: 700, a: k, shadow: 0.9, spacing: 3 });
  }
}
