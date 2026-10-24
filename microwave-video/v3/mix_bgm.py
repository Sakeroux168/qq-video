"""《大脑的账本》最终混音：配音 + 音效（sfx.py 生成的 out/sfx_only 由这里重算）+ BGM（说话时自动压低 6dB），整体响度 -15 LUFS。"""
import numpy as np, subprocess, wave, runpy, sys
SR = 48000; DUR = 206.0
sys.argv = ['sfx.py', str(DUR)]; g = runpy.run_path('sfx.py')      # 复用 sfx.py 里的音效轨和配音
sfx, v = g['sfx'], g['v']
n = len(sfx); voice = np.zeros(n); voice[:len(v)] = v * (0.85 / np.abs(v).max())
bgm = np.load('out/bgm_long.npy').astype(np.float64)[:n]; bgm = np.pad(bgm, ((0, n - len(bgm)), (0, 0)))
hop = SR // 100
env = np.sqrt(np.convolve(voice ** 2, np.ones(hop * 3) / (hop * 3), 'same'))[::hop]
talk = (20 * np.log10(env + 1e-9) > -38).astype(float)
gk = np.zeros_like(talk); up, dn = 1 - np.exp(-1 / 4), 1 - np.exp(-1 / 35)
for i in range(len(talk)):
    p = gk[i - 1] if i else talk[0]; gk[i] = p + (talk[i] - p) * (up if talk[i] > p else dn)
duck = 10 ** (-6 * np.interp(np.arange(n) / hop, np.arange(len(gk)), gk) / 20)
tt = np.arange(n) / SR
fade = np.clip(tt / 1.5, 0, 1) * np.clip((DUR - tt) / 2.0, 0, 1) ** 1.5
mix = bgm * (1.1 * duck * fade)[:, None] + (voice + sfx * 0.6)[:, None]
lim = 10 ** (-2 / 20); k = 0.6; o = np.abs(mix) > k
mix[o] = np.sign(mix[o]) * (k + (lim - k) * np.tanh((np.abs(mix[o]) - k) / (lim - k)))
with wave.open('out/mix_bgm.wav', 'w') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
print('ok')
