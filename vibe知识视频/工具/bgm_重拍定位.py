import sys, numpy as np
from scipy.io import wavfile
from scipy.signal import stft
sr, x = wavfile.read(sys.argv[1]); x = x.astype(np.float32) / 32768
hop = 110
f, t, Z = stft(x, sr, nperseg=512, noverlap=512-hop)
mag = np.abs(Z); flux = np.maximum(0, np.diff(mag, axis=1)).sum(0); tt = t[1:]
o = flux / flux.max()
m = (tt > 94.5) & (tt < 96.5); i = np.argmax(o[m]); print('第二次重拍', round(tt[m][i], 3))
seg = x[int(93.5*sr):int(96.5*sr)]; n = len(seg)//1102
print('93.5–96.5 每 50ms dB:', ' '.join(f'{93.5+k*0.05:.2f}:{20*np.log10(np.sqrt(np.mean(seg[k*1102:(k+1)*1102]**2))+1e-7):.0f}' for k in range(n)))
# 拟合节拍周期：17.455 起到 79s 的强起音
pk = [tt[k] for k in range(1, len(o)-1) if o[k] > 0.45 and o[k] >= o[k-1] and o[k] >= o[k+1] and 17.4 < tt[k] < 79]
best = None
for p in np.arange(0.535, 0.548, 0.0002):
    ph = (np.array(pk) - 17.455) / (p/2)  # 八分音符网格
    err = np.mean(np.abs(ph - np.round(ph)))
    if best is None or err < best[1]: best = (p, err)
print('最佳四分音符周期', round(best[0], 4), '误差', round(best[1], 3), '→ 小节', round(best[0]*4, 4))
# 第二次重拍在网格上的位置
print('第二次重拍距 17.455 的拍数', round((tt[m][i]-17.455)/best[0], 2))
