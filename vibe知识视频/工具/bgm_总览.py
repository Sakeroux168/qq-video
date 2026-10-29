import sys, numpy as np
from scipy.io import wavfile
from scipy.signal import stft
sr, x = wavfile.read(sys.argv[1]); x = x.astype(np.float32) / 32768
hop = 441  # 20ms
n = len(x) // hop
rms = np.array([np.sqrt(np.mean(x[i*hop:(i+1)*hop]**2)) for i in range(n)])
db = 20*np.log10(rms + 1e-7)
f, t, Z = stft(x, sr, nperseg=1024, noverlap=1024-hop)
mag = np.abs(Z)
flux = np.maximum(0, np.diff(mag, axis=1)).sum(0)
flux = flux / flux.max()
# 每秒响度
print('每秒响度 dB:')
for s in range(0, int(len(x)/sr)):
    seg = db[s*50:(s+1)*50]
    print(f'{s:4d}s {seg.mean():6.1f} max {seg.max():6.1f}', end=' | ' if s % 4 != 3 else '\n')
print()
# 节拍：onset 自相关
o = flux[: int(60 / 0.02)]
o = o - o.mean()
ac = np.correlate(o, o, 'full')[len(o)-1:]
lags = np.arange(len(ac)) * 0.02
mask = (lags > 0.3) & (lags < 1.5)
best = lags[mask][np.argmax(ac[mask])]
print('最强周期(s)', round(best, 3), '≈ BPM', round(60/best, 1))
# 「换气 + 重拍」：前面 0.3s 很安静，后面突然大起来
cands = []
for i in range(25, len(db) - 25):
    before = db[i-20:i].mean(); dip = db[i-8:i].min(); after = db[i:i+15].mean()
    if after - before > 6 and after > db.mean():
        cands.append((i*0.02, round(after-before,1), round(dip,1), round(after,1)))
# 合并相邻
out = []
for c in cands:
    if not out or c[0] - out[-1][0] > 1.0: out.append(c)
    elif c[1] > out[-1][1]: out[-1] = c
print('跳变候选 (秒, 涨幅dB, 前面最低dB, 后面平均dB):')
for c in out[:30]: print(c)
