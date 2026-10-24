"""动态规划对齐：每个小句占一段连续说话区间，区间边界只能落在静音缝上。
代价 = (实际说话时长 − 字数×语速)² + 句内吞掉的长停顿惩罚 + 句号处停顿太短的惩罚。输出 timing2.json。"""
import re, json, subprocess
SRC = 'voice_final.wav'
txt = re.sub(r'\((chuckle|laughs|sighs)\)', '', open('../MiniMax粘贴版.txt').read())
units = [u.strip() for u in re.split(r'(?<=[，。？：；！])|<#[0-9.]+#>|——', txt) if u.strip()]
import sys
T_START = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
U_START = next(i for i, u in enumerate(units) if u.startswith(sys.argv[2])) if len(sys.argv) > 2 else 0
units = units[U_START:]
wt = lambda s: len(re.sub(r'[，。？：；！“”、…—\s]', '', s)) + 3 * len(re.findall(r'\d{4}', s))
Wt = [max(1, wt(u)) for u in units]
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', SRC], capture_output=True, text=True).stdout)
log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', SRC, '-af', 'silencedetect=n=-38dB:d=0.14', '-f', 'null', '-'], capture_output=True, text=True).stderr
st = [float(v) for v in re.findall(r'silence_start: ([0-9.]+)', log)]; en = [float(v) for v in re.findall(r'silence_end: ([0-9.]+)', log)]
gaps = [g for g in zip(st, en) if g[1] > T_START]
lead = T_START
if gaps and gaps[0][0] <= T_START + 0.05: lead = gaps.pop(0)[1]
if len(st) > len(en): gaps = gaps[:-1]
B = [(lead, lead)] + gaps + [(dur, dur)]          # 边界候选：B[k] = (说话结束, 下一段开始)
G = len(B)
def speech(k0, k1):   # 从 B[k0] 结束到 B[k1] 开始之间的说话时长、吞掉的停顿
    tot = B[k1][0] - B[k0][1]; inner = sum(B[m][1] - B[m][0] for m in range(k0 + 1, k1))
    big = sum(max(0, B[m][1] - B[m][0] - 0.22) for m in range(k0 + 1, k1))
    return tot - inner, big
S = sum(speech(0, G - 1)[0] for _ in [0]); rate = S / sum(Wt)
INF = 1e18; U = len(units)
# dp[i][j]：前 i 个小句恰好在边界 j 结束；每一步吃掉 1–3 个小句（它们之间可以没有停顿）
dp = [[INF] * G for _ in range(U + 1)]; bk = [[None] * G for _ in range(U + 1)]; dp[0][0] = 0
for i in range(1, U + 1):
    for g in (1, 2, 3):
        if i - g < 0: continue
        w = sum(Wt[i - g:i]); end_strong = units[i - 1][-1] in '。？！'
        for j in range(1, G):
            for k in range(max(0, j - 10), j):
                if dp[i - g][k] >= INF: continue
                sp, big = speech(k, j); exp = w * rate
                c = ((sp - exp) / (0.3 + 0.12 * exp)) ** 2 + 6 * big + 0.8 * (g - 1)
                gl = B[j][1] - B[j][0]
                if end_strong and j < G - 1 and gl < 0.22: c += 1.5
                if dp[i - g][k] + c < dp[i][j]: dp[i][j] = dp[i - g][k] + c; bk[i][j] = (k, g)
out = []; i, j = U, G - 1
while i > 0:
    k, g = bk[i][j]; a0, a1 = B[k][1], B[j][0]; ws = Wt[i - g:i]; tot = sum(ws); acc = 0
    seg = []
    for m, w in enumerate(ws):
        s0 = a0 + (a1 - a0) * acc / tot; acc += w; s1 = a0 + (a1 - a0) * acc / tot
        seg.append([round(s0, 2), round(s1, 2), units[i - g + m]])
    out = seg + out; i -= g; j = k
json.dump(out, open('timing2.json', 'w'), ensure_ascii=False, indent=0)
for a, b, u in out: print(f'{a:7.2f} {b:7.2f}  {u}')
