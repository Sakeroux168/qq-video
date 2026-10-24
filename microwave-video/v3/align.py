"""把配音稿按标点切成小句，按字数比例映射到“去掉静音后的说话时间轴”，再吸附到最近的静音缝。输出 timing.json。"""
import re, json, subprocess
SRC = 'voice_final.wav'
txt = open('../MiniMax粘贴版.txt').read()
txt = re.sub(r'\((chuckle|laughs|sighs)\)', '', txt)
# 切小句：标点和停顿标签都算断点，标点留在句尾
units = [u for u in re.split(r'(?<=[，。？：；！])|<#[0-9.]+#>|——', txt) if u.strip()]
def weight(s):
    s2 = re.sub(r'[，。？：；！“”、…—\s]', '', s)
    return sum(4 if c.isdigit() and False else 1 for c in s2) + 3 * len(re.findall(r'\d{4}', s2)) - 0 * 0
W = [max(1, weight(u)) for u in units]
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', SRC], capture_output=True, text=True).stdout)
log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', SRC, '-af', 'silencedetect=n=-38dB:d=0.1', '-f', 'null', '-'], capture_output=True, text=True).stderr
st = [float(v) for v in re.findall(r'silence_start: ([0-9.]+)', log)]; en = [float(v) for v in re.findall(r'silence_end: ([0-9.]+)', log)]
gaps = [(s, e) for s, e in zip(st, en)]
if len(st) > len(en): gaps.append((st[-1], dur))
# 说话区间
speech = []; t = 0
for s, e in gaps:
    if s > t: speech.append((t, s))
    t = e
if t < dur: speech.append((t, dur))
S = sum(b - a for a, b in speech)
def speech_to_real(x):
    for a, b in speech:
        if x <= b - a: return a + x
        x -= b - a
    return dur
tot = sum(W); cum = 0; bounds = []
for w in W[:-1]:
    cum += w; target = speech_to_real(cum / tot * S)
    # 吸附到最近的静音缝（±0.7s 内）
    best = min(gaps, key=lambda g: abs((g[0] + g[1]) / 2 - target))
    bounds.append(best if abs((best[0] + best[1]) / 2 - target) < 0.7 else (target, target))
out = []; start = speech[0][0]
for i, u in enumerate(units):
    end = bounds[i][0] if i < len(bounds) else speech[-1][1]
    out.append([round(start, 2), round(end, 2), u.strip()])
    if i < len(bounds): start = bounds[i][1]
json.dump(out, open('timing.json', 'w'), ensure_ascii=False, indent=0)
for a, b, u in out[:40]: print(f'{a:7.2f} {b:7.2f}  {u}')
print('...', len(out), 'units; dur', dur)
