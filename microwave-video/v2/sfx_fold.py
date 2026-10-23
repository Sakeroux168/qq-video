"""对折 42 次 开头 15 秒音效：低音重击、提示音、上升呼啸 + 撞击、纸张翻折声。"""
import numpy as np, wave
SR = 48000; DUR = 15.0
rng = np.random.default_rng(9)
out = np.zeros(int(SR * DUR))
def place(sig, t, g):
    i = int(t * SR); j = min(len(out), i + len(sig)); out[i:j] += sig[:j - i] * g
lp = lambda x, k: np.convolve(x, np.ones(k) / k, 'same')
def boom(d=1.4, f0=62):
    n = int(d * SR); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * (f0 * tt - 18 * tt ** 2)) * np.exp(-tt / 0.4) * np.minimum(1, tt / 0.004) + lp(rng.normal(0, 1, n), 40) * np.exp(-tt / 0.05) * 0.5
def tick(f=1800):
    n = int(0.35 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.01 * tt)) * np.exp(-tt / 0.08) * np.minimum(1, tt / 0.002)
def riser(d):
    n = int(d * SR); tt = np.arange(n) / SR; x = rng.normal(0, 1, n); y = np.zeros(n); seg = n // 40
    for s in range(40):
        k = int(60 - 55 * s / 39); y[s * seg:(s + 1) * seg] = lp(x, max(2, k))[s * seg:(s + 1) * seg]
    tone = np.sin(2 * np.pi * (110 * tt + 140 * tt ** 2 / d)) * 0.25
    return (y + tone) * (tt / d) ** 1.6
def swish(d=0.9):
    n = int(d * SR); tt = np.arange(n) / n
    return lp(rng.normal(0, 1, n), 5) * np.sin(np.pi * tt) ** 1.5
# 环境低频铺底（很轻）
n = len(out); tt = np.arange(n) / SR
place((np.sin(2 * np.pi * 55 * tt) * 0.5 + lp(rng.normal(0, 1, n), 200) * 2) * np.minimum(1, tt / 1.0) * np.minimum(1, (DUR - tt) / 0.5), 0, 0.05)
place(boom(), 0.0, 0.5)
place(tick(1600), 4.0, 0.18); place(tick(2000), 5.1, 0.18)
place(riser(2.3), 6.5, 0.32); place(boom(1.8, 48), 8.8, 0.55)
place(tick(2400), 11.0, 0.12)
place(swish(1.1), 13.0, 0.35); place(boom(0.5, 120), 14.05, 0.25)
peak = np.abs(out).max(); out *= 0.89 / peak
with wave.open('sfx_fold.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())
print('ok', round(peak, 3))
