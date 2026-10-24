"""收紧配音停顿：静音段按 新长度 = 0.24 + 0.4×(原长 − 0.24) 压缩，然后整体 atempo 提速。"""
import numpy as np, subprocess, re, sys, wave
SRC = 'voice_fix.wav'; SR = 44100; TEMPO = float(sys.argv[1]) if len(sys.argv) > 1 else 1.1
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', SRC, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
x = np.frombuffer(raw, np.float32).astype(np.float64)
log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', SRC, '-af', 'silencedetect=n=-40dB:d=0.2', '-f', 'null', '-'], capture_output=True, text=True).stderr
st = [float(v) for v in re.findall(r'silence_start: ([0-9.]+)', log)]
en = [float(v) for v in re.findall(r'silence_end: ([0-9.]+)', log)]
out = []; pos = 0; fade = int(0.01 * SR)
for s, e in zip(st, en):
    d = e - s
    if s < 0.05: s = 0  # 开头静音只留 0.15s
    keep = 0.15 if s == 0 else (d if d <= 0.24 else 0.24 + 0.4 * (d - 0.24))
    cut = d - keep
    if cut < 0.02: continue
    a = int((s + keep / 2) * SR); b = int((s + keep / 2 + cut) * SR)
    seg = x[pos:a].copy(); seg[-fade:] *= np.linspace(1, 0, fade)
    out.append(seg); pos = b
tail = x[pos:].copy(); out.append(tail)
for i in range(1, len(out)): out[i][:fade] *= np.linspace(0, 1, fade)
y = np.concatenate(out)
with wave.open('tight.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', 'tight.wav', '-af', f'atempo={TEMPO},loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'libmp3lame', '-b:a', '192k', 'voice_tight.mp3'], check=True)
print('原长 %.1fs → 收紧停顿 %.1fs → 提速 %.2f 后 %.1fs' % (len(x) / SR, len(y) / SR, TEMPO, len(y) / SR / TEMPO))
