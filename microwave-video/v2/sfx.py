"""用代码合成音效并与配音混音：嗡鸣、嗖、叮、重击、翻牌。音量克制，峰值限制在 -1dBFS。"""
import numpy as np, subprocess, sys, wave
SR = 48000; DUR = 20.47
rng = np.random.default_rng(3)
out = np.zeros(int(SR * DUR))
def place(sig, t, gain):
    i = int(t * SR); j = min(len(out), i + len(sig)); out[i:j] += sig[:j - i] * gain
def env(n, a, d):
    e = np.ones(n); ka = max(1, int(a * SR)); e[:ka] = np.linspace(0, 1, ka)
    e *= np.exp(-np.arange(n) / (d * SR)); return e
def lowpass(x, k):  # 简单滑动平均低通
    return np.convolve(x, np.ones(k) / k, 'same')
# 开场重击：低频正弦下滑 + 短噪声
n = int(1.2 * SR); tt = np.arange(n) / SR
boom = np.sin(2 * np.pi * (70 * tt - 25 * tt ** 2)) * env(n, 0.005, 0.35) + lowpass(rng.normal(0, 1, n), 40) * env(n, 0.001, 0.05) * 0.6
place(boom, 0.0, 0.4)
# 微波炉嗡鸣（0–10.25s），低音量
n = int(10.25 * SR); tt = np.arange(n) / SR
hum = (np.sin(2 * np.pi * 100 * tt) * 0.5 + np.sin(2 * np.pi * 200 * tt) * 0.2 + lowpass(rng.normal(0, 1, n), 60) * 0.3)
fade = np.minimum(1, np.minimum(tt / 0.4, (10.25 - tt) / 0.05)); place(hum * fade, 0.0, 0.05)
# 嗖（白噪声带通扫频的近似：变宽度低通 + 包络）
def whoosh(d=0.6):
    n = int(d * SR); x = rng.normal(0, 1, n); y = np.zeros(n); k = 1
    seg = n // 24
    for s in range(24):
        k = int(30 - 26 * np.sin(np.pi * s / 23)); y[s * seg:(s + 1) * seg] = lowpass(x, k)[s * seg:(s + 1) * seg]
    tt = np.arange(n) / n; return y * np.sin(np.pi * tt) ** 2
place(whoosh(0.7), 6.3, 0.5); place(whoosh(0.5), 10.75, 0.3)
place(whoosh(0.8), 12.0, 0.35); place(whoosh(0.8), 16.2, 0.35)
# 叮：铃声（几个泛音指数衰减）
n = int(1.8 * SR); tt = np.arange(n) / SR
ding = sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt / d) for f, a, d in [(1568, 1, 0.9), (3136, 0.35, 0.5), (4704, 0.15, 0.3), (2350, 0.2, 0.6)])
ding *= np.minimum(1, tt / 0.003); place(ding, 10.25, 0.32)
# 验牌：重击 + 纸牌"啪"
place(boom, 19.37, 0.3)
n = int(0.12 * SR); snap = rng.normal(0, 1, n) * env(n, 0.001, 0.02); place(snap, 19.37, 0.25)
# 牌框画出来时的轻微"沙"声
n = int(1.0 * SR); tt = np.arange(n) / SR; place(lowpass(rng.normal(0, 1, n), 6) * np.sin(np.pi * tt) * 0.4, 16.4, 0.25)
np.save('sfx.npy', out)
# 读配音 0–20.47s
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', sys.argv[1], '-t', str(DUR), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
voice = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
mix = np.zeros_like(out); mix[:len(voice)] += voice; mix += out
peak = np.abs(mix).max(); lim = 10 ** (-1 / 20)
# 软限幅：0.75 以下原样，以上平滑压到 lim 以内（只压偶尔的峰，不把整体音量拉低）
k = 0.75; over = np.abs(mix) > k
mix[over] = np.sign(mix[over]) * (k + (lim - k) * np.tanh((np.abs(mix[over]) - k) / (lim - k)))
for name, sig in (('mix.wav', mix), ('sfx_only.wav', out / max(1e-9, np.abs(out).max()) * lim * 0.8)):
    with wave.open(name, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
print('peak before limit', round(peak, 3))
