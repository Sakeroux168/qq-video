"""《知识诅咒》画风版 15 秒样片的声音，时间点和 curse.html 一一对应。
铺底 + 八音盒琶音；盖章、标题闪光、纸卡滑入、每一枚金币落下都有一声。用法: python3 sound_curse.py out.wav"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
DUR = 15.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(3)
L = np.zeros(N)
R = np.zeros(N)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], 'bandpass', fs=SR, output='sos'), x)


def lp(x, f):
    return sosfilt(butter(2, f, 'lowpass', fs=SR, output='sos'), x)


def env(n, a, d):
    x = np.arange(n) / SR
    return np.minimum(1, x / max(a, 1e-4)) * np.exp(-np.maximum(0, x - a) / d)


def place(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N:
        return
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * gain * (1 - max(0, pan))
    R[i:j] += sig[: j - i] * gain * (1 + min(0, pan))


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


# 铺底：Am – F – C – G，每个和弦 3 秒，低音 + 柔和和声
chords = [[45, 57, 60, 64], [41, 53, 57, 60], [48, 55, 60, 64], [43, 55, 59, 62], [45, 57, 60, 64]]
pad = np.zeros(N)
for k, ch in enumerate(chords):
    i0, i1 = int(k * 3 * SR), min(N, int((k + 1) * 3 * SR + 0.6 * SR))
    x = np.arange(i1 - i0) / SR
    shape = np.minimum(1, x / 0.5) * np.minimum(1, np.maximum(0, (x[-1] - x)) / 0.6)
    tone = sum(np.sin(2 * np.pi * midi(m) * x) * (0.5 if m < 50 else 0.16) for m in ch)
    pad[i0:i1] += tone * shape
pad = lp(pad, 1400) * np.minimum(1, (DUR - t) / 0.5)
L += pad * 0.10
R += pad * 0.10

# 八音盒：每 0.375 秒一个音，跟着和弦走
def bell(f, length=1.4):
    n = int(length * SR)
    x = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * x) + 0.35 * np.sin(2 * np.pi * f * 2.76 * x) * np.exp(-x * 6)) * env(n, 0.002, 0.45)


arp = [0, 2, 3, 2, 1, 3, 2, 3]
step = 0.375
k = 0
while k * step < DUR - 0.6:
    at = k * step
    ch = chords[min(int(at / 3), len(chords) - 1)]
    if not (2.7 <= at < 4.5):  # 标题卡那两秒只留铺底和闪光
        place(bell(midi(ch[arp[k % len(arp)]] + 12)), at, 0.05, pan=0.25 if k % 2 else -0.25)
    k += 1

# 开场一记柔和重音
n = int(1.2 * SR)
x = np.arange(n) / SR
place(np.sin(2 * np.pi * (60 - 15 * x) * x) * env(n, 0.003, 0.35), 0.0, 0.5)


def thump():  # 盖章：木头闷响 + 纸声
    n = int(0.4 * SR)
    x = np.arange(n) / SR
    return np.sin(2 * np.pi * (110 - 40 * x) * x) * env(n, 0.001, 0.06) + bp(rng.standard_normal(n), 900, 4500) * env(n, 0.001, 0.025) * 0.5


place(thump(), 0.85, 0.75, pan=0.25)
place(thump(), 5.95, 0.6, pan=0.15)


def swoosh(length, lo, hi):
    n = int(length * SR)
    x = np.arange(n) / SR
    return bp(rng.standard_normal(n), lo, hi) * np.sin(np.pi * x / length) ** 2


place(swoosh(0.45, 500, 5000), 2.6, 0.25)
place(swoosh(0.5, 300, 2500), 4.55, 0.22, pan=-0.1)
place(swoosh(0.4, 400, 3000), 7.0, 0.15)

# 标题闪光：一串高音铃
for i, m in enumerate([84, 88, 91, 95, 96]):
    place(bell(midi(m), 2.0), 2.85 + i * 0.05, 0.05, pan=(i - 2) * 0.2)


def clink():
    n = int(0.12 * SR)
    x = np.arange(n) / SR
    f = 2600 + rng.random() * 600
    return (np.sin(2 * np.pi * f * x) + 0.6 * np.sin(2 * np.pi * f * 1.62 * x) + 0.4 * np.sin(2 * np.pi * f * 2.43 * x)) * env(n, 0.0005, 0.03)


def coin_drops(t0, dur, count, pan):  # 画面用 easeOut 累计金币：第 i 枚出现在 1-(1-i/n)^(1/3)
    for i in range(1, int(np.ceil(count)) + 1):
        p = min(1.0, i / count)
        place(clink(), t0 + dur * (1 - (1 - p) ** (1 / 3)) - 0.02, 0.07, pan=pan)


coin_drops(7.5, 0.9, 5, -0.35)
coin_drops(8.2, 0.7, 2.5, -0.15)
coin_drops(9.2, 0.9, 10, 0.15)
coin_drops(9.8, 1.3, 20, 0.35)

# 「你选哪个？」两个问句音
place(bell(midi(76), 1.0), 10.8, 0.10)
place(bell(midi(81), 1.2), 11.0, 0.10)

# 答案：低音重击 + 计数滴答（左上框 0→50%）
n = int(1.6 * SR)
x = np.arange(n) / SR
boom = np.sin(2 * np.pi * (55 - 15 * x) * x) * env(n, 0.003, 0.5) + lp(rng.standard_normal(n), 300) * env(n, 0.001, 0.05) * 0.5
place(boom, 12.8, 0.8)
for i in range(12):
    p = (i + 1) / 12
    place(clink() * 0.6, 12.8 + 0.8 * (1 - (1 - p) ** (1 / 3)), 0.05, pan=-0.6)

mix = np.stack([L, R], axis=1)
mix = np.tanh(mix * 1.3) / np.tanh(1.3)
mix *= 0.89 / max(1e-6, np.abs(mix).max())
wavfile.write(sys.argv[1], SR, (mix * 32767).astype(np.int16))
print('ok', sys.argv[1])
