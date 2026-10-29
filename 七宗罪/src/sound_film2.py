"""七宗罪·嫉妒 v3 的声音：用户给的 BGM（截到 110.7 秒，最后两小节淡出）+ 少量音效。
时间点和 film.html 一一对应（小节 = 17.455 + k × 2.1688）。
用法: python3 sound_film.py bgm.wav out.wav"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

D1, D2, BAR, END = 17.455, 95.532, 2.1688, 110.7


def B(k):
    return D1 + k * BAR


sr, bgm = wavfile.read(sys.argv[1])
bgm = bgm.astype(np.float64) / 32768
if bgm.ndim == 1:
    bgm = np.stack([bgm, bgm], axis=1)
N = int(END * sr)
bgm = bgm[:N]
t = np.arange(N) / sr
fade = np.clip((END - 0.3 - t) / (END - 0.3 - B(41)), 0, 1)  # 最后两小节淡出
bgm = bgm * (fade ** 1.5)[:, None] * 0.82
L = bgm[:, 0].copy()
R = bgm[:, 1].copy()
rng = np.random.default_rng(5)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], 'bandpass', fs=sr, output='sos'), x)


def lp(x, f):
    return sosfilt(butter(2, f, 'lowpass', fs=sr, output='sos'), x)


def env(n, a, d):
    x = np.arange(n) / sr
    return np.minimum(1, x / max(a, 1e-4)) * np.exp(-np.maximum(0, x - a) / d)


def place(sig, at, gain=1.0, pan=0.0):
    i = int(at * sr)
    if i >= N:
        return
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * gain * (1 - max(0, pan))
    R[i:j] += sig[: j - i] * gain * (1 + min(0, pan))


def tone(f, length, a=0.002, d=0.3, harm=0.3):
    n = int(length * sr)
    x = np.arange(n) / sr
    return (np.sin(2 * np.pi * f * x) + harm * np.sin(2 * np.pi * f * 2.76 * x) * np.exp(-x * 6)) * env(n, a, d)


def ding():  # 消息提示音
    return np.concatenate([tone(1318.5, 0.12, d=0.08), tone(1760, 0.6, d=0.18)])


def thud(f0=90, d=0.12):
    n = int(0.6 * sr)
    x = np.arange(n) / sr
    return np.sin(2 * np.pi * (f0 - 40 * x) * x) * env(n, 0.002, d) + lp(rng.standard_normal(n), 400) * env(n, 0.001, 0.03) * 0.4


def boom(big=1.0):  # 大重拍：低频冲击 + 一点金粉的高频
    n = int(2.2 * sr)
    x = np.arange(n) / sr
    low = np.sin(2 * np.pi * (58 - 18 * x) * x) * env(n, 0.003, 0.55)
    air = bp(rng.standard_normal(n), 3000, 9000) * env(n, 0.002, 0.35) * 0.18
    shimmer = sum(np.sin(2 * np.pi * f * x) * env(n, 0.01, 0.9) for f in (2093, 2637, 3136)) * 0.05
    return (low + air + shimmer) * big


def swoosh(length, lo, hi):
    n = int(length * sr)
    x = np.arange(n) / sr
    return bp(rng.standard_normal(n), lo, hi) * np.sin(np.pi * x / length) ** 2


# 0–1.1 三连消息，1.1 兄弟提车：解锁「嘀嘀」
place(ding(), 0.0, 0.12, pan=-0.4)
place(ding(), 0.55, 0.12, pan=-0.15)
place(ding(), 1.1, 0.12, pan=0.1)
for k in range(2):
    n = int(0.09 * sr)
    x = np.arange(n) / sr
    place(np.sign(np.sin(2 * np.pi * 2100 * x)) * 0.3 * env(n, 0.002, 0.05), 1.3 + k * 0.16, 0.10, pan=0.4)
place(ding(), B(-6) + 0.15, 0.13, pan=0.3)  # 前任
place(thud(80, 0.15), B(-6) + 1.0, 0.5, pan=-0.2)  # 你倒地
place(swoosh(0.4, 400, 3000), B(-5), 0.08)  # 爬起来
place(boom(1.0), D1, 0.75)
place(tone(1046.5, 1.2, d=0.4), B(1), 0.06, pan=-0.2)  # 乞丐
place(tone(1174.7, 1.2, d=0.4), B(2), 0.06, pan=0.2)
place(tone(1318.5, 1.4, d=0.5), B(3), 0.06, pan=0.4)  # 国王
place(swoosh(0.6, 400, 4000), B(4) - 0.4, 0.14)  # 进大脑
n = int(0.9 * sr)
x = np.arange(n) / sr
sting = (np.sin(2 * np.pi * 1800 * x) + np.sin(2 * np.pi * 1905 * x)) * (0.6 + 0.4 * np.sin(2 * np.pi * 11 * x)) * env(n, 0.02, 0.35)
place(sting, B(6), 0.035)  # 「疼」
place(boom(0.45), B(8), 0.6)  # 「爽」小爆点
place(tone(2093, 1.5, d=0.6), B(8) + 0.02, 0.05)
place(ding(), B(9) + 0.1, 0.12, pan=0.2)  # 兄弟的消息
for k in range(4):  # 打字
    m = int(0.03 * sr)
    place(bp(rng.standard_normal(m), 2000, 6000) * env(m, 0.001, 0.008), B(10) + 0.2 + k * 0.15, 0.12, pan=0.3)
place(swoosh(0.25, 1500, 7000), B(10) + 0.85, 0.08, pan=0.3)
place(thud(110, 0.06), B(13) + 0.5, 0.45, pan=0.2)  # 「坏人？」盖章
place(swoosh(0.7, 300, 3000), B(15) - 0.3, 0.14)  # 进地图
n = int(1.6 * sr)
x = np.arange(n) / sr
flutter = bp(rng.standard_normal(n), 600, 2500) * (0.5 + 0.5 * np.sin(2 * np.pi * 13 * x)) * np.sin(np.pi * x / 1.6)
place(flutter, B(17) + 0.2, 0.06, pan=0.5)  # 鸟扑翅
place(tone(1568, 1.6, d=0.5), B(22), 0.06)  # 「我也想要」
pops = np.random.default_rng(33)
for i in range(40):  # 朋友圈卡片一张张冒出来（和画面同一个种子不同，只取时间分布）
    m = int(0.025 * sr)
    place(bp(rng.standard_normal(m), 2500, 7000) * env(m, 0.001, 0.006), B(24) + pops.random() * 1.6, 0.05, pan=pops.random() * 1.2 - 0.6)
place(boom(1.15), D2, 0.8)
place(tone(1318.5, 1.2, d=0.4), B(39), 0.05)
place(tone(1760, 1.4, d=0.5), B(40), 0.05)
place(tone(1046.5, 3.0, d=1.2), B(41) + 0.1, 0.05)
# 很轻的空气底噪
air = lp(rng.standard_normal(N), 900) * 0.006
L += air
R += air * 0.9

mix = np.stack([L, R], axis=1)
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
mix *= 0.89 / max(1e-6, np.abs(mix).max())
wavfile.write(sys.argv[2], sr, (mix * 32767).astype(np.int16))
print('ok', sys.argv[2], round(N / sr, 2), 's')
