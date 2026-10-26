"""配音 + 马克笔拟音 + 拇指琴/马林巴小配乐 → out/mix.wav。拟音写法照 styles/whiteboard 的做法（每一笔按手速曲线发声）。"""
import sys, os, json, numpy as np, soundfile as sf, soxr
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, ROOT)
from core.audio.sfx import SR, bp, lp, add, compress, limit
ev = json.load(open(os.path.join(HERE, 'events.json'))); E = ev['ev']; DUR = ev['dur']
rng = np.random.default_rng(7); NS = int((DUR + 1) * SR)
fol, mus, vo = (np.zeros((NS, 2), np.float32) for _ in range(3))
tt = lambda d: np.arange(int(d * SR)) / SR
_band = {}
def band(n, lo, hi):
    k = (lo, hi)
    if k not in _band: _band[k] = bp(rng.standard_normal(SR * 8), lo, hi, 2).astype(np.float32)
    b = _band[k]; i = int(rng.integers(0, len(b) - n - 1)); return b[i:i + n]
def marker(dur, length, kind, pen, z=1.):
    d = max(.03, dur); n = int(d * SR); u = np.linspace(0, 1, n); v = 1 - .8 * np.cos(2 * np.pi * u)
    if kind == 'dash': v = np.ones(n) * 1.2
    a = (v / 1.8) ** .8 * np.minimum(1, u * d / .006) * np.minimum(1, (1 - u) * d / .012)
    br = {'black': 1.0, 'orange': 1.12, 'blue': .92}.get(pen, 1.)
    x = (band(n, 2200 * br, 7500 * br) * (.55 + .45 * v / 1.8) + band(n, 500 * br, 1500 * br) * .45) * a
    if kind != 'dash' and length > 140 and rng.random() < .25:
        s0 = rng.uniform(.15, .55) * d; sd = min(d - s0, rng.uniform(.06, .14))
        if sd > .03:
            m = int(sd * SR); ts = np.arange(m) / SR; f = rng.uniform(1500, 2600) * br * (1 + .03 * np.sin(2 * np.pi * 9 * ts))
            sq = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * ts / sd) ** 1.5 * .3; i0 = int(s0 * SR); x[i0:i0 + m] += sq[:len(x) - i0]
    return x * .3 * min(1.3, z ** .5)
def eraser(d):
    n = int(d * SR); t = tt(d); base = bp(rng.standard_normal(n), 250, 2600) * .6 + bp(rng.standard_normal(n), 2500, 6000) * .15
    return base * (.45 + .55 * np.abs(np.sin(np.pi * t / d * 7))) * np.minimum(1, t / .04) * np.minimum(1, (d - t) / .06) * .5
def whoosh(d=.4):
    n = int(d * SR); t = tt(d); return bp(rng.standard_normal(n), 300, 2400) * np.sin(np.pi * t / d) ** 2 * .3
def cap_on():
    x = np.zeros(int(.2 * SR))
    for k, o in enumerate([0, .045]):
        i = int(o * SR); c = bp(rng.standard_normal(int(.006 * SR)), 2500, 9000) * np.linspace(1, 0, int(.006 * SR)); x[i:i + len(c)] += c * (1 - .4 * k)
    return x * .7
def put(buf, x, t, g=1., pan=0.):
    i = int(t * SR); x = np.asarray(x, np.float32); j = min(len(buf), i + len(x))
    if i >= len(buf) or j <= i: return
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:j, 0] += x[:j - i] * g * l * 1.414; buf[i:j, 1] += x[:j - i] * g * r * 1.414
# ── 拟音
sil = [(e['t'], e['t'] + e['dur']) for e in E if e['type'] == 'silence']
for e in E:
    p = e.get('pan', 0); z = e.get('z', 1)
    if e['type'] in ('write', 'stroke', 'dash'): put(fol, marker(e['dur'], e['len'], e['type'], e['pen'], z), e['t'], .9, p)
    elif e['type'] == 'tap': put(fol, bp(rng.standard_normal(int(.03 * SR)), 1800, 6000) * np.exp(-tt(.03) / .004) * .35, e['t'], .9, p)
    elif e['type'] == 'erase': put(fol, eraser(e['dur']), e['t'], 1.0)
    elif e['type'] == 'whip': put(fol, whoosh(.4), e['t'], .8)
    elif e['type'] == 'capon': put(fol, cap_on(), e['t'], .8)
put(fol, lp(rng.standard_normal(NS), 300) * .004, 0)                 # 房间底噪
# ── 配乐：88 BPM，拇指琴 + 马林巴（合成），两处静默
BPM = 88; BT = 60 / BPM
def kalimba(f, d=1.6):
    t = tt(d); return (np.sin(2 * np.pi * f * t) + .25 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / .05)) * np.exp(-t / .55) * np.minimum(1, t / .002)
def marimba(f, d=.9):
    t = tt(d); return (np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * f * 3.9 * t) * np.exp(-t / .03)) * np.exp(-t / .22) * np.minimum(1, t / .002)
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
PAT = [64, 67, 72, 67, 69, 72, 76, 72]        # C 大调五声音阶上的小琶音
BASS = [48, 48, 45, 45, 43, 43, 48, 48]
in_sil = lambda t: any(a - .05 <= t < b for a, b in sil)
nb = int(DUR / BT)
for k in range(nb):
    t = k * BT
    if t > DUR - 1.2 or in_sil(t): continue
    sec = 0 if t < 8.2 else 1 if t < 25.1 else 2
    put(mus, kalimba(mid(PAT[k % 8])), t, .22, -.25)
    if sec >= 1 and k % 2 == 0: put(mus, marimba(mid(BASS[(k // 2) % 8] + 12)), t, .18, .3)
    if sec == 2 and k % 4 == 2: put(mus, kalimba(mid(PAT[(k + 3) % 8] + 12), 1.2), t + BT / 2, .12, .4)
for i, m in enumerate([60, 64, 67, 72]):        # 收尾和弦
    put(mus, kalimba(mid(m), 3.0), DUR - 1.4 + i * .03, .2, (i - 1.5) * .2)
gl = np.linspace(800, 1600, int(.35 * SR)); put(mus, np.sin(2 * np.pi * np.cumsum(gl) / SR) * np.sin(np.linspace(0, np.pi, len(gl))) * .25, 10.65, .5)   # 溢出那一下的上滑音
# ── 配音：压缩，约比音乐高 10 dB；音乐在说话时再压低
v, sr = sf.read(os.path.join(HERE, 'voice/vo.wav'), dtype='float32')
if v.ndim > 1: v = v.mean(1)
if sr != SR: v = soxr.resample(v, sr, SR)
v = compress(v / (np.abs(v).max() + 1e-9) * .8, thr=.2, ratio=3)
put(vo, v, 0, 1.0)
env = np.convolve(np.abs(vo[:, 0]), np.ones(int(.05 * SR)) / int(.05 * SR), 'same'); duck = 1 - .55 * np.clip(env / (env.max() * .25), 0, 1)
mix = vo + fol * .55 + mus * duck[:, None]
mix = limit(mix, .9)
os.makedirs(os.path.join(HERE, 'out'), exist_ok=True); sf.write(os.path.join(HERE, 'out/mix.wav'), mix[:int(DUR * SR)], SR)
print('mix ok', DUR)
