"""剪 BGM：去掉一整段 16 拍（61.59→77.32 秒，前后两段几乎一样），让最后一个重音落在片尾 73.8 秒；
整体延后 0.4 秒，让 47–49 秒的渐强落在“没人能”盖章上。输出 ../bgm/bgm_edit.npy 给 mix_bgm.py 用。"""
import numpy as np, subprocess
SR = 48000
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', '../bgm/bgm.mp3', '-af', 'equalizer=f=2500:t=q:w=1.2:g=-3', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
a, b = 61.59, 77.32
xf = int(0.08 * SR); pre = int(0.04 * SR)
ia, ib = int(a * SR) - pre, int(b * SR) - pre
A = x[:ia + xf]; B = x[ib:]
w = np.linspace(0, 1, xf)[:, None]
cross = A[-xf:] * np.sqrt(1 - w) + B[:xf] * np.sqrt(w)
y = np.concatenate([np.zeros((int(0.4 * SR), 2)), A[:-xf], cross, B[xf:]])
np.save('../bgm/bgm_edit.npy', y.astype(np.float32))
