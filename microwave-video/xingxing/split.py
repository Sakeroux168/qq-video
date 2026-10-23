"""把 12 宫格动作图切成单张透明 PNG。相邻人物头发会粘连，所以用最小代价接缝（seam）来切格子。"""
import sys, numpy as np
from PIL import Image
from scipy import ndimage as nd
src, out = sys.argv[1], sys.argv[2]
a = np.asarray(Image.open(src).convert('RGBA')).astype(np.float32)
al = a[..., 3]
H, W = al.shape

def seam_v(x0, x1, y0=0, y1=None):
    """在 x0..x1 带内找一条从上到下代价最小的竖缝，返回每行的 x"""
    y1 = y1 or H
    cost = al[y0:y1, x0:x1].copy() + 1
    acc = cost.copy()
    for y in range(1, acc.shape[0]):
        p = acc[y - 1]
        left = np.r_[np.inf, p[:-1]]; right = np.r_[p[1:], np.inf]
        acc[y] += np.minimum(np.minimum(left, p), right)
    xs = np.zeros(acc.shape[0], int); xs[-1] = int(np.argmin(acc[-1]))
    for y in range(acc.shape[0] - 2, -1, -1):
        x = xs[y + 1]; lo = max(0, x - 1); hi = min(acc.shape[1], x + 2)
        xs[y] = lo + int(np.argmin(acc[y, lo:hi]))
    return xs + x0

def seam_h(y0, y1, x0, x1):
    global al
    sav = al
    al = sav.T
    ys = seam_v(y0, y1, x0, x1)
    al = sav
    return ys

vcuts = [np.zeros(H, int), seam_v(300, 390), seam_v(640, 690), np.full(H, W)]
hbands = [(330, 450), (740, 830), (1080, 1200)]
names = ['talk', 'idle', 'happy', 'point', 'surprise', 'thumb', 'shrug', 'think', 'scared', 'stick', 'wave', 'heart']
YY, XX = np.mgrid[0:H, 0:W]
for c in range(3):
    left = vcuts[c][:, None]; right = vcuts[c + 1][:, None]
    colmask = (XX >= left) & (XX < right)
    xa, xb = int(vcuts[c].min()), int(vcuts[c + 1].max())
    hcuts = [np.zeros(W, int)] + [np.pad(seam_h(b0, b1, xa, min(W, xb)), (xa, W - min(W, xb)), mode='edge') for b0, b1 in hbands] + [np.full(W, H)]
    for r in range(4):
        m = colmask & (YY >= hcuts[r][None, :]) & (YY < hcuts[r + 1][None, :])
        alpha = np.where(m, al, 0)
        alpha = np.clip((alpha - 12) * 255 / 230, 0, 255)
        # 只保留主体及其附近的小块（汗滴、爱心、教鞭）
        lab, n = nd.label(alpha > 60)
        if n > 1:
            s = nd.sum(alpha > 60, lab, range(1, n + 1))
            big = np.argmax(s) + 1
            keep = np.isin(lab, [i + 1 for i in range(n) if s[i] > 25])
            alpha = np.where(nd.binary_dilation(keep, iterations=3), alpha, 0)
        ys, xs = np.where(alpha > 0)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        rgba = a.copy(); rgba[..., 3] = alpha
        k = r * 3 + c
        Image.fromarray(rgba[y0:y1, x0:x1].astype(np.uint8), 'RGBA').save(f'{out}/{k+1:02d}_{names[k]}.png')
        print(f'{k+1:02d}_{names[k]}', 'box', (x0, y0, x1, y1), 'size', (x1 - x0, y1 - y0), 'touch_bottom', y1 >= H - 9)
