"""生成动画用素材：2 倍 Lanczos 放大 + 轻锐化；算出每个姿势的脚底锚点，写入 meta.json。"""
import json, numpy as np
from PIL import Image, ImageFilter
src = {
    'base': 'r_base.png', 'blink': 'r_blink.png', 'talk': 'r_talk.png', 'talkblink': 'r_talkblink.png',
    'happy': '03_happy.png', 'point': '04_point.png', 'surprise': '05_surprise.png', 'thumb': '06_thumb.png',
    'shrug': '07_shrug.png', 'think': '08_think.png', 'scared': '09_scared.png',
    'stick': '10_stick.png', 'wave': '11_wave.png', 'heart': '12_heart.png',
}
cut = {'stick', 'wave', 'heart'}          # 这三张原图脚被裁掉了
meta = {}
heads = []
for k, f in src.items():
    im = Image.open(f).convert('RGBA'); a = np.asarray(im)[..., 3] > 128
    h, w = a.shape
    ys, xs = np.where(a[: int(h * 0.42)])          # 头部（上 42%）
    headx = xs.mean()
    if k not in cut:
        fy, fx = np.where(a[h - 14:])               # 脚底 14 行
        footx = fx.mean()
        heads.append(footx - headx)
        meta[k] = dict(w=w, h=h, ax=float(footx), ay=float(h), headx=float(headx))
    else:
        meta[k] = dict(w=w, h=h, headx=float(headx))
    big = im.resize((w * 2, h * 2), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.6, percent=60, threshold=2))
    big.save(f'assets/{k}.png')
off = float(np.mean(heads))
full_h = float(np.mean([meta[k]['h'] for k in meta if k not in cut]))
for k in cut:                                      # 用头部位置 + 平均偏移推算虚拟脚底
    meta[k]['ax'] = meta[k]['headx'] + off
    meta[k]['ay'] = full_h
# 底图 base/blink/talk 共用 base 的锚点，避免切换时跳动
for k in ('blink', 'talk', 'talkblink'): meta[k].update(ax=meta['base']['ax'], ay=meta['base']['ay'])
json.dump(meta, open('assets/meta.json', 'w'), indent=1)
for k, v in meta.items(): print(k, v['w'], v['h'], round(v['ax'], 1), round(v['ay'], 1))
