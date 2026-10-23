"""《对折 42 次》配音 + 音效 + BGM 混音。BGM 已剪好（../bgm/bgm_edit.npy），配音时自动压低。"""
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
events = [
    (boom(), 0.0, 0.5), (tick(1600), 5.45, 0.16), (swish(0.7), 5.9, 0.15), (tick(2000), 6.5, 0.16),
    (riser(1.6), 6.95, 0.3), (boom(1.6, 50), 8.55, 0.45),
    (tick(2400), 9.4, 0.1), (swish(1.0), 11.7, 0.3), (thud(), 12.7, 0.22),
    (thud(), 13.6, 0.2), (tick(1800), 15.25, 0.1), (thud(), 16.5, 0.22), (tick(1800), 17.4, 0.1),
    (riser(1.4), 21.0, 0.25), (riser(1.8), 23.95, 0.28), (tick(2600), 25.3, 0.12),
    (riser(2.0), 28.0, 0.3), (boom(1.6, 52), 30.1, 0.4), (riser(1.5), 31.8, 0.3), (boom(2.0, 44), 33.3, 0.5),
    (tick(1500), 35.5, 0.16), (tick(1700), 36.75, 0.12), (tick(1700), 37.7, 0.12), (tick(2300), 37.85, 0.12),
    (riser(1.0), 43.85, 0.3), (boom(1.4, 56), 44.6, 0.45),
    (boom(0.8, 90), 49.08, 0.4), (swish(1.4), 52.35, 0.25), (tick(2000), 54.4, 0.15),
    (swish(0.6), 56.3, 0.15), (swish(0.6), 57.0, 0.15), (boom(0.8, 90), 59.28, 0.35),
    (swish(1.6), 61.8, 0.12), (riser(2.0), 70.8, 0.18), (boom(2.2, 46), 73.8, 0.2),
]
for sig, t0, g in events: place(sig, t0, g)
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', '../fold42/voice.mp3', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
voice = np.zeros(len(sfx)); v = np.frombuffer(raw, dtype=np.float32).astype(np.float64)[:len(sfx)]; voice[:len(v)] = v
voice *= 0.89 / np.abs(voice).max()
bgm = np.load('../bgm/bgm_edit.npy').astype(np.float64)[:len(sfx)]
bgm = np.pad(bgm, ((0, len(sfx) - len(bgm)), (0, 0)))
# 配音包络 → BGM 闪避：说话时 -6 dB，停顿处回到原位，起 40ms / 落 350ms
hop = SR // 100
env = np.sqrt(np.convolve(voice ** 2, np.ones(hop * 3) / (hop * 3), 'same'))[::hop]
talk = (20 * np.log10(env + 1e-9) > -38).astype(float)
g = np.zeros_like(talk); up, dn = 1 - np.exp(-1 / 4), 1 - np.exp(-1 / 35)
for i in range(len(talk)):
    prev = g[i - 1] if i else talk[0]; g[i] = prev + (talk[i] - prev) * (up if talk[i] > prev else dn)
duck = 10 ** (-6 * np.interp(np.arange(len(sfx)) / hop, np.arange(len(g)), g) / 20)
tt = np.arange(len(sfx)) / SR
fade = np.clip(tt / 0.3, 0, 1) * np.clip((DUR - tt) / 1.6, 0, 1) ** 1.5
BGM_GAIN = 1.2; MAKEUP = float(__import__("os").environ.get("MAKEUP", "1.3"))
mus = bgm * (BGM_GAIN * duck * fade)[:, None]
mix = (mus + (voice + sfx * 0.55)[:, None]) * MAKEUP
lim = 10 ** (-2 / 20); k = 0.6; over = np.abs(mix) > k
mix[over] = np.sign(mix[over]) * (k + (lim - k) * np.tanh((np.abs(mix[over]) - k) / (lim - k)))
with wave.open('full/mix_bgm.wav', 'w') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
print('mix peak', round(float(np.abs(mix).max()), 3))
