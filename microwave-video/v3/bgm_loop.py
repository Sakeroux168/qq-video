"""把那首 BGM 拉长到全片：从原曲 28.2s 处起播（让 48.9s 的渐强落在标题卡上），
播到 77.32s 后回跳 9 次一整段 16 拍（61.59→77.32，前后几乎一样），最后接原曲结尾，让最后一个重音落在按下“转发给他”的 201.7s。"""
import numpy as np, subprocess
SR = 48000
x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', '../bgm/bgm.mp3', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout, np.float32).reshape(-1, 2).astype(np.float64)
S = lambda t: int(t * SR)
segs = [x[S(28.2):S(77.32)]] + [x[S(61.59):S(77.32)] for _ in range(9)] + [x[S(77.32):]]
xf = int(0.08 * SR); w = np.linspace(0, 1, xf)[:, None]
out = segs[0]
for s in segs[1:]:
    out = np.concatenate([out[:-xf], out[-xf:] * np.sqrt(1 - w) + s[:xf] * np.sqrt(w), s[xf:]])
np.save('out/bgm_long.npy', out.astype(np.float32))
print('len', len(out) / SR, '最后重音在', (77.32 - 28.2) + 9 * 15.73 + (89.13 - 77.32) - 10 * 0.08)
