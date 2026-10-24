"""《大脑的账本》音效 + 配音混音。事件时间对齐 scenes/ledger.js。用法：python3 sfx.py [截到第几秒]"""
import numpy as np, subprocess, wave, sys
SR = 48000; DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 202.4
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
