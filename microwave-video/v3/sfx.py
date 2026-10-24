"""《大脑的账本》音效 + 配音混音。事件时间对齐 scenes/ledger.js。用法：python3 sfx.py [截到第几秒]"""
import numpy as np, subprocess, wave, sys
SR = 48000; DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 206.0
rng = np.random.default_rng(42)
n = int(SR * DUR); sfx = np.zeros(n)
def place(sig, t, g):
    i = int(t * SR); j = min(n, i + len(sig))
    if i < n: sfx[i:j] += sig[:j - i] * g
lp = lambda x, k: np.convolve(x, np.ones(k) / k, 'same')
env = lambda m, a, d: np.minimum(1, np.arange(m) / (a * SR + 1)) * np.exp(-np.arange(m) / (d * SR))
def boom(d=1.4, f0=58):
    m = int(d * SR); tt = np.arange(m) / SR
    return np.sin(2 * np.pi * (f0 * tt - 16 * tt ** 2)) * env(m, 0.004, 0.45) + lp(rng.normal(0, 1, m), 40) * env(m, 0.001, 0.05) * 0.5
def pop(f=900):      # 消息气泡“啵”
    m = int(0.12 * SR); tt = np.arange(m) / SR
    return np.sin(2 * np.pi * (f * tt + 2500 * tt ** 2)) * env(m, 0.002, 0.03)
def tick(f=1800):
    m = int(0.3 * SR); tt = np.arange(m) / SR
    return (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.01 * tt)) * env(m, 0.002, 0.06)
def swish(d=0.6):
    m = int(d * SR); k = np.arange(m) / m
    return lp(rng.normal(0, 1, m), 6) * np.sin(np.pi * k) ** 1.5
def thud():
    return boom(0.45, 110)
def paper(d=0.5):    # 纸张摩擦
    m = int(d * SR); x = rng.normal(0, 1, m); x = x - lp(x, 30)
    return x * np.sin(np.pi * np.arange(m) / m) ** 2 * (0.6 + 0.4 * rng.random(m))
def scribble(d=0.35):   # 笔尖沙沙
    m = int(d * SR); x = rng.normal(0, 1, m); x = x - lp(x, 8)
    am = 0.5 + 0.5 * np.sin(2 * np.pi * 14 * np.arange(m) / SR) ** 2
    return x * am * np.sin(np.pi * np.arange(m) / m)
def strike():           # 红笔划掉
    return scribble(0.3) * 1.2
def clock(d=0.8):
    s = np.zeros(int(d * SR))
    for k, tt in enumerate(np.arange(0, d, 0.2)): x = tick(2400 if k % 2 else 1700) * 0.6; i = int(tt * SR); s[i:i + len(x)] += x[:len(s) - i]
    return s
def seal():
    s = boom(0.6, 90) * 0.7; x = tick(700) * 0.4; s[:len(x)] += x; return s
ev = [
    (pop(900), 0.25, 0.2), (pop(1000), 0.6, 0.2), (pop(800), 1.0, 0.22), (pop(1100), 1.45, 0.2),
    (tick(2200), 2.4, 0.18), (swish(0.5), 3.55, 0.25), (clock(0.8), 5.42, 0.25), (tick(900), 6.22, 0.15),
    (strike(), 7.45, 0.35), (thud(), 7.85, 0.3),
    *[(scribble(0.3), 9.55 + i * 0.22, 0.16) for i in range(4)], (tick(2600), 10.46, 0.12),
    *[(scribble(0.25), 11.5 + i * 0.18, 0.07) for i in range(3)],
    (swish(0.4), 13.45, 0.12), *[(paper(0.25), x - 0.1, 0.25) for x in (14.37, 14.98, 15.70, 16.30)], (seal(), 16.84, 0.35), (swish(0.6), 18.12, 0.15),
    (boom(1.8, 50), 19.85, 0.5),
    (paper(0.4), 21.85, 0.25), (tick(500), 22.95, 0.2), (paper(0.45), 24.37, 0.3), (paper(0.45), 26.72, 0.3), (tick(2000), 29.69, 0.15),
    (pop(700), 30.7, 0.18), (pop(600), 32.3, 0.15),
    # 第一页后半
    (tick(1500), 34.8, 0.12), (swish(0.5), 37.7, 0.15), (paper(0.3), 40.8, 0.25), *[(tick(3000), 41.6 + i * 0.12, 0.05) for i in range(8)], (swish(0.4), 43.6, 0.2), (paper(0.3), 43.76, 0.25),
    (pop(800), 44.0, 0.15), (thud(), 46.9, 0.15), (tick(800), 47.9, 0.12), (strike(), 51.1, 0.3), (tick(2400), 54.2, 0.15), (swish(0.8), 56.9, 0.25), (paper(0.4), 57.3, 0.3),
    # 第二页
    *[(scribble(0.25), 58.2 + i * 0.12, 0.08) for i in range(6)], (thud(), 60.4, 0.2), (tick(700), 61.3, 0.15), (paper(0.45), 62.04, 0.3),
    (pop(500), 63.3, 0.2), (swish(1.2), 65.6, 0.12), (pop(400), 67.7, 0.22), (pop(1400), 69.9, 0.15), (tick(2000), 72.4, 0.12), (tick(600), 75.0, 0.15), (swish(0.8), 78.4, 0.25), (paper(0.4), 78.8, 0.3),
    # 第三页
    *[(tick(2200 + 200 * (i % 3)), 81.2 + i * 0.25, 0.06) for i in range(14)], (pop(900), 86.0, 0.2), (paper(0.45), 87.07, 0.3), (swish(0.5), 89.0, 0.12), (swish(0.6), 90.14, 0.15), (tick(500), 90.91, 0.25),
    (strike(), 92.6, 0.3), (swish(1.0), 97.9, 0.15), (pop(900), 100.37, 0.15), (pop(1000), 101.2, 0.15), (pop(1100), 102.0, 0.15), (swish(0.8), 104.25, 0.12), (strike(), 104.4, 0.25), (pop(900), 104.9, 0.15),
    (paper(0.45), 105.86, 0.3), (tick(1800), 106.4, 0.1), (tick(1800), 107.1, 0.1), (tick(1200), 108.04, 0.15), *[(paper(0.25), 109.19 + i * 0.25, 0.2) for i in range(3)], (thud(), 111.83, 0.3), (tick(500), 114.01, 0.2),
    # 第四页
    (paper(0.45), 115.48, 0.3), (paper(0.3), 117.76, 0.2), (paper(0.3), 119.37, 0.2), *[(scribble(0.4), x, 0.14) for x in (122.83, 123.86, 124.99)], *[(scribble(0.35), x, 0.06) for x in (128.3, 129.33, 130.23)],
    (pop(600), 133.06, 0.18), (thud(), 135.82, 0.3), (tick(1500), 136.81, 0.12), *[(tick(2600), 137.94 + i * 0.05, 0.05) for i in range(12)], (swish(0.6), 139.6, 0.15),
    (paper(0.45), 140.88, 0.3), (tick(1800), 141.68, 0.1), (tick(1800), 142.3, 0.1), (swish(1.4), 145.6, 0.1), *[(tick(3200 - i * 150), 150.39 + i * 0.04, 0.05) for i in range(10)], (seal(), 151.9, 0.3),
    # 封底
    (thud(), 153.2, 0.3), (seal(), 155.5, 0.3), (boom(0.9, 80), 157.13, 0.4), (paper(0.45), 158.1, 0.3), *[(tick(3000), 160.6 + i * 0.12, 0.05) for i in range(8)],
    (tick(1400), 164.92, 0.15), (tick(1700), 167.65, 0.15), (thud(), 170.23, 0.25), (tick(600), 174.75, 0.2), (paper(0.45), 175.93, 0.3), (swish(2.0), 178.9, 0.1), (pop(500), 181.8, 0.15),
    (pop(1200), 183.7, 0.12), (swish(0.6), 186.22, 0.15), (boom(1.6, 48), 191.56, 0.45),
    # 结尾
    (thud(), 193.0, 0.2), (swish(0.5), 195.57, 0.15), (tick(2400), 197.07, 0.2), (pop(1300), 201.7, 0.3), (boom(1.8, 52), 202.6, 0.35),
]
for sig, t0, g in ev: place(sig, t0, g)
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', '../debt/audio/voice_final.wav', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
v = np.frombuffer(raw, np.float32).astype(np.float64)[:n]
mix = sfx * 0.6; mix[:len(v)] += v * (0.85 / max(1e-9, np.abs(v).max()))
lim = 10 ** (-1.5 / 20); k = 0.7; o = np.abs(mix) > k
mix[o] = np.sign(mix[o]) * (k + (lim - k) * np.tanh((np.abs(mix[o]) - k) / (lim - k)))
with wave.open('out/mix.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
print('ok', DUR)
