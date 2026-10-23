"""《对折 42 次》全片音效 + 与配音混音。事件时间对齐 fold_full.js。"""
import numpy as np, subprocess, wave
SR = 48000; DUR = 77.0
rng = np.random.default_rng(42)
sfx = np.zeros(int(SR * DUR))
def place(sig, t, g):
    i = int(t * SR); j = min(len(sfx), i + len(sig)); sfx[i:j] += sig[:j - i] * g
lp = lambda x, k: np.convolve(x, np.ones(k) / k, 'same')
def boom(d=1.4, f0=62):
    n = int(d * SR); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * (f0 * tt - 18 * tt ** 2)) * np.exp(-tt / 0.4) * np.minimum(1, tt / 0.004) + lp(rng.normal(0, 1, n), 40) * np.exp(-tt / 0.05) * 0.5
def tick(f=1800):
    n = int(0.35 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.01 * tt)) * np.exp(-tt / 0.08) * np.minimum(1, tt / 0.002)
def riser(d):
    n = int(d * SR); tt = np.arange(n) / SR; x = rng.normal(0, 1, n); y = np.zeros(n); seg = max(1, n // 40)
    for s in range(40):
        k = int(60 - 55 * s / 39); y[s * seg:(s + 1) * seg] = lp(x, max(2, k))[s * seg:(s + 1) * seg]
    return (y + np.sin(2 * np.pi * (110 * tt + 140 * tt ** 2 / d)) * 0.25) * (tt / d) ** 1.6
def swish(d=0.9):
    n = int(d * SR); tt = np.arange(n) / n
    return lp(rng.normal(0, 1, n), 5) * np.sin(np.pi * tt) ** 1.5
def thud():
    return boom(0.5, 120)
# 低频铺底
n = len(sfx); tt = np.arange(n) / SR
place((np.sin(2 * np.pi * 55 * tt) * 0.5 + lp(rng.normal(0, 1, n), 200) * 2) * np.minimum(1, tt / 1.0) * np.minimum(1, (DUR - tt) / 1.0), 0, 0.05)
events = [
    (boom(), 0.0, 0.5), (tick(1600), 5.15, 0.16), (tick(2000), 5.98, 0.16),
    (riser(1.6), 7.0, 0.3), (boom(1.6, 50), 8.6, 0.45),
    (tick(2400), 9.4, 0.1), (swish(1.0), 11.7, 0.3), (thud(), 12.7, 0.22),
    (thud(), 13.6, 0.2), (tick(1800), 15.25, 0.1), (thud(), 16.5, 0.22), (tick(1800), 17.4, 0.1),
    (riser(1.4), 21.0, 0.25), (riser(1.8), 23.95, 0.28), (tick(2600), 25.3, 0.12),
    (riser(2.0), 28.0, 0.3), (boom(1.6, 52), 30.1, 0.4), (riser(1.5), 31.8, 0.3), (boom(2.0, 44), 33.3, 0.5),
    (tick(1500), 35.5, 0.16), (tick(1700), 36.75, 0.12), (tick(1700), 37.7, 0.12), (tick(2300), 37.85, 0.12),
    (riser(1.0), 43.85, 0.3), (boom(1.4, 56), 44.6, 0.45),
    (boom(0.8, 90), 48.95, 0.4), (swish(1.4), 52.35, 0.25), (tick(2000), 54.4, 0.15),
    (swish(0.6), 56.3, 0.15), (swish(0.6), 57.0, 0.15), (boom(0.8, 90), 58.55, 0.35),
    (swish(1.6), 61.8, 0.12), (riser(2.0), 70.8, 0.18), (boom(2.2, 46), 73.8, 0.3),
]
for sig, t0, g in events: place(sig, t0, g)
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', '../fold42/voice.mp3', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
voice = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
vpk = np.abs(voice).max()
mix = sfx * 0.55; mix[:len(voice)] += voice * (0.89 / vpk)
lim = 10 ** (-1 / 20); k = 0.75; over = np.abs(mix) > k
mix[over] = np.sign(mix[over]) * (k + (lim - k) * np.tanh((np.abs(mix[over]) - k) / (lim - k)))
with wave.open('full/mix.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
s2 = sfx / max(1e-9, np.abs(sfx).max()) * 0.8
with wave.open('full/sfx_only.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((s2 * 32767).astype(np.int16).tobytes())
print('voice peak', round(vpk, 3), 'mix peak', round(float(np.abs(mix).max()), 3))
