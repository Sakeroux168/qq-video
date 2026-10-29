"""七宗罪·嫉妒 15 秒样片的声音：低音铺底 + 心跳一样的钟摆 + 开灯、升台、翻纸、荧光笔、写字、重音。
时间点和 sample.html 的画面一一对应。用法: python3 sound.py out.wav"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
DUR = 15.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)
L = np.zeros(N)
R = np.zeros(N)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], 'bandpass', fs=SR, output='sos'), x)


def lp(x, f):
    return sosfilt(butter(2, f, 'lowpass', fs=SR, output='sos'), x)


def place(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * gain * (1 - max(0, pan))
    R[i:j] += sig[: j - i] * gain * (1 + min(0, pan))


def env(n, a, d):
    """a 秒起音、之后按 d 秒衰减"""
    x = np.arange(n) / SR
    return np.minimum(1, x / max(a, 1e-4)) * np.exp(-np.maximum(0, x - a) / d)


# 铺底：A 小调低音和弦，剧场段暗、纸面段稍亮
drone = (np.sin(2 * np.pi * 55 * t) * 0.5 + np.sin(2 * np.pi * 82.41 * t) * 0.3
         + np.sin(2 * np.pi * 110 * t) * 0.22 + np.sin(2 * np.pi * 130.81 * t) * 0.12)
drone *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.13 * t)
drone_env = np.where(t < 10.5, 1.0, np.interp(t, [10.5, 11.0, 15], [1.0, 0.55, 0.55]))
drone *= drone_env * np.minimum(1, t / 0.05) * np.minimum(1, (DUR - t) / 0.4)
L += drone * 0.11
R += drone * 0.11

# 钟摆：每 0.75 秒一下（80 BPM），B 的「别人」往上冲时变快变响
tick = bp(rng.standard_normal(int(0.04 * SR)), 1800, 4200) * env(int(0.04 * SR), 0.001, 0.008)
beat = 0.0
while beat < 10.4:
    fast = 7.6 <= beat < 10.3
    place(tick, beat, 0.10 if not fast else 0.16, pan=0.3 if int(beat / 0.75) % 2 else -0.3)
    beat += 0.375 if fast else 0.75


def clunk():  # 舞台灯「啪」：低频一锤 + 金属噪声
    n = int(0.5 * SR)
    x = np.arange(n) / SR
    body = np.sin(2 * np.pi * (70 - 25 * x) * x) * env(n, 0.002, 0.09)
    click = bp(rng.standard_normal(n), 800, 5000) * env(n, 0.0005, 0.015)
    return body * 0.9 + click * 0.5


place(clunk(), 0.12, 0.8, pan=-0.35)
place(clunk(), 0.42, 0.8, pan=0.35)


def riser(length, f0, f1):  # 台座升起：越来越高的气声
    n = int(length * SR)
    x = np.arange(n) / SR
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    seg = 2048
    for k in range(0, n, seg):
        f = f0 + (f1 - f0) * (k / n)
        out[k:k + seg] = bp(noise[k:k + seg], f * 0.7, f * 1.4)
    tone = np.sin(2 * np.pi * np.cumsum(np.linspace(f0 / 8, f1 / 8, n)) / SR) * 0.4
    shape = np.sin(np.pi * np.clip(x / length, 0, 1)) ** 0.7
    return (out * 0.6 + tone) * shape


def ding(f):
    n = int(1.2 * SR)
    x = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * x) + 0.3 * np.sin(2 * np.pi * f * 2.01 * x)) * env(n, 0.003, 0.35)


# A：你 2.8–3.9s，别人 3.6–4.6s；B：你 6.8–8.0s，别人 7.6–9.3s
place(riser(1.1, 300, 900), 2.8, 0.22, pan=-0.4)
place(ding(660), 3.9, 0.12, pan=-0.4)
place(riser(1.0, 250, 600), 3.6, 0.16, pan=-0.2)
place(ding(587), 4.6, 0.10, pan=-0.2)
place(riser(1.2, 300, 1000), 6.8, 0.22, pan=0.2)
place(ding(660), 8.0, 0.12, pan=0.2)
place(riser(1.7, 300, 1800), 7.6, 0.30, pan=0.45)

# 别人超过你、光变绿：一个不和谐的低音慢慢涌上来（小二度）
n = int(1.8 * SR)
x = np.arange(n) / SR
sour = (np.sin(2 * np.pi * 98 * x) + np.sin(2 * np.pi * 103.8 * x) + 0.4 * np.sin(2 * np.pi * 196 * x))
sour *= np.minimum(1, x / 0.9) * np.minimum(1, (1.8 - x) / 0.5)
place(sour, 8.9, 0.10)

# 翻到纸面：一声「哗」
n = int(0.5 * SR)
x = np.arange(n) / SR
swoosh = bp(rng.standard_normal(n), 600, 6000) * np.sin(np.pi * x / 0.5) ** 2
place(swoosh, 10.45, 0.35, pan=0.2)

# 荧光笔划过（11.8–12.5s）：带颤动的高频摩擦
n = int(0.7 * SR)
x = np.arange(n) / SR
squeak = bp(rng.standard_normal(n), 2500, 7000) * (0.6 + 0.4 * np.sin(2 * np.pi * 38 * x)) * np.sin(np.pi * x / 0.7)
place(squeak, 11.8, 0.18, pan=-0.2)

# 手写批注（13.05–13.95s）：一串细碎的笔尖声
for k in range(9):
    m = int((0.05 + rng.random() * 0.06) * SR)
    stroke = bp(rng.standard_normal(m), 1500, 5000) * np.sin(np.pi * np.arange(m) / m)
    place(stroke, 13.05 + k * 0.1, 0.10, pan=0.4)

# 「差不多一半的人，选了 A」：低音重击
n = int(1.6 * SR)
x = np.arange(n) / SR
boom = np.sin(2 * np.pi * (52 - 14 * x) * x) * env(n, 0.003, 0.45)
boom += lp(rng.standard_normal(n), 300) * env(n, 0.001, 0.05) * 0.6
place(boom, 13.0, 0.75)

mix = np.stack([L, R], axis=1)
mix = np.tanh(mix * 1.3) / np.tanh(1.3)  # 软限幅，防爆音
mix *= 0.89 / max(1e-6, np.abs(mix).max())  # 峰值约 -1 dBFS
wavfile.write(sys.argv[1], SR, (mix * 32767).astype(np.int16))
print('ok', sys.argv[1])
