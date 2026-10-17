"""查水印评测(可以反复跑):读 tests/watermark_cases.json,一条条跑 watermark.detect,算准确率 / 位置 / 用时。

    cd E:\\软件\\百家号发布软件\\企鹅号发布助手
    PYTHONIOENCODING=utf-8 python -u tests/eval_watermark.py                 # 全部
    PYTHONIOENCODING=utf-8 python -u tests/eval_watermark.py --only 游戏      # 路径 / 说明里带「游戏」的
    PYTHONIOENCODING=utf-8 python -u tests/eval_watermark.py --cache D:\\tmp  # 先复制到本地再测(网络盘慢,只看算法用时)
    PYTHONIOENCODING=utf-8 python -u tests/eval_watermark.py --no-synth      # 不跑合成的

清单格式(watermark_cases.json):
  {"cases": [
    {"path": 视频, "wm": true/false, "label": "B站"(有水印时哪家), "boxes": [[x, y, w, h], ...](画布上的位置:
     竖视频 720×1280 / 横的 1280×720,等比缩放 + 补黑边以后), "spans": [[开始秒, 结束秒]](可不填), "note": 说明},
    {"synth": {"base": 干净的视频, "src": ["音符", "抖音字"](qe/assets/logos/_合成源 里的形状,横着拼)
               或 "text": "抖音号：12345678"(用微软雅黑写一行字), "h": 画布上多高, "pos": "tl/tr/bl/br/ml/mr" 或 [x, y],
               "alpha": 0.85, "t0": 0, "t1": 20(只在这几秒有;不填 = 整条), "len": 40(只截前几秒来测)},
     "wm": true, "label": "抖音", "note": ...}
  ]}
  合成的:按真实水印的样子(白色、半透明、带一点阴影、缩小)用 ffmpeg 叠到干净的视频上(临时文件),位置是准的。
算法:
  没水印的:报了任何东西 = 误报。
  有水印的:报了这家(label 对)= 认出来;框盖住真实位置一半以上(交集 / 真实框面积 ≥ 50%)= 位置对;
            报了别家 / 框离真实位置很远 = 记「多报」(会白糊一块)。
只读视频,不改任何素材;合成的视频和 detect 写的截图都放临时目录。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="qe_wmeval_"))
os.environ.setdefault("QE_DATA_DIR", str(TMP / "data"))
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from qe import vertical, watermark as W  # noqa: E402

SRC_DIR = W.ASSET_DIR / "_合成源"
FONT = r"C:\Windows\Fonts\msyh.ttc"


def cover(hit_box, gt) -> float:
    """真实框有多少被报的框盖住(0~1)。"""
    x0, y0 = max(hit_box[0], gt[0]), max(hit_box[1], gt[1])
    x1, y1 = min(hit_box[0] + hit_box[2], gt[0] + gt[2]), min(hit_box[1] + hit_box[3], gt[1] + gt[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0) / float(max(1, gt[2] * gt[3]))


def _mask(sy: dict, hpx: int) -> np.ndarray:
    """要叠的形状(白 = 有),高 hpx 像素(原视频像素)。"""
    if sy.get("text"):
        from PIL import Image, ImageDraw, ImageFont
        f = ImageFont.truetype(FONT, max(8, int(hpx * 0.95)))
        l, t, r, b = f.getbbox(sy["text"])
        im = Image.new("L", (r - l + 4, b - t + 4), 0)
        ImageDraw.Draw(im).text((2 - l, 2 - t), sy["text"], fill=255, font=f)
        m = np.array(im)
    else:
        parts = []
        for name in ([sy["src"]] if isinstance(sy["src"], str) else sy["src"]):
            g = cv2.imdecode(np.fromfile(str(SRC_DIR / f"{name}.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
            k = hpx / g.shape[0]
            parts.append(cv2.resize(g, (max(2, int(g.shape[1] * k)), hpx), interpolation=cv2.INTER_AREA))
        gap = np.zeros((hpx, max(2, hpx // 4)), np.uint8)
        m = parts[0]
        for p in parts[1:]:
            m = np.hstack([m, gap, p])
    ys, xs = np.where(m > 60)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def make_synth(c: dict, ff: str) -> tuple[str, list]:
    """把水印叠到干净视频上 → (临时视频, [画布上的真实框])。"""
    sy = c["synth"]
    base = sy["base"]
    info = vertical.probe(base, ff)
    rect = W.content_rect(info["w"], info["h"])
    k = info["w"] / rect[2]                                   # 画布像素 → 原视频像素
    hpx = max(6, int(round(sy.get("h", 30) * k)))
    m = _mask(sy, hpx).astype(np.float32) / 255.0
    a = float(sy.get("alpha", 0.85))
    h, w = m.shape
    pad = max(2, hpx // 10)
    rgba = np.zeros((h + pad * 2, w + pad * 2, 4), np.float32)
    sh = cv2.GaussianBlur(m, (0, 0), max(0.8, hpx / 30))
    rgba[pad + 1:pad + 1 + h, pad + 1:pad + 1 + w, 3] = sh * 0.35             # 阴影(黑)
    al = rgba[pad:pad + h, pad:pad + w, 3]
    na = m * a + al * (1 - m * a)
    rgba[pad:pad + h, pad:pad + w, :3] = np.where(na[..., None] > 0, (m * a / np.maximum(na, 1e-6))[..., None] * 255, 0)
    rgba[pad:pad + h, pad:pad + w, 3] = na
    png = TMP / f"ov_{hashlib.md5(json.dumps(sy, ensure_ascii=False).encode()).hexdigest()[:10]}.png"
    out = np.dstack([rgba[..., 2], rgba[..., 1], rgba[..., 0], rgba[..., 3] * 255]).clip(0, 255).astype(np.uint8)
    cv2.imencode(".png", out)[1].tofile(str(png))
    W_, H_ = info["w"], info["h"]
    mx, my = int(W_ * 0.03), int(H_ * 0.03)
    pos = sy.get("pos", "tr")
    if isinstance(pos, list):
        x, y = int(pos[0] * k), int(pos[1] * k)
    else:
        x = mx if pos[1] == "l" else W_ - mx - out.shape[1]
        y = {"t": my, "b": H_ - my - out.shape[0], "m": H_ // 2 - out.shape[0] // 2}[pos[0]]
    dst = TMP / (png.stem + ".mp4")
    en = f":enable='between(t,{sy['t0']},{sy['t1']})'" if sy.get("t1") else ""
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", base, "-i", str(png), "-t", str(sy.get("len", 40)),
           "-filter_complex", f"[0:v][1:v]overlay={x}:{y}{en}[v]", "-map", "[v]", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", str(dst)]
    subprocess.run(cmd, check=True)
    gt = [rect[0] + (x + pad) / k, rect[1] + (y + pad) / k, w / k, h / k]
    return str(dst), [[int(round(v)) for v in gt]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(ROOT / "tests" / "watermark_cases.json"))
    ap.add_argument("--only", default="", help="只跑路径 / 说明里带这个字的")
    ap.add_argument("--cache", default="", help="先复制到这个文件夹再测(网络盘太慢时)")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--no-synth", action="store_true")
    ap.add_argument("--out", default="", help="每条结果存成 json")
    a = ap.parse_args()

    cases = json.loads(Path(a.cases).read_text("utf-8"))["cases"]
    key = lambda c: c.get("path") or c["synth"]["base"]   # noqa: E731
    if a.only:
        cases = [c for c in cases if a.only in key(c) or a.only in c.get("note", "")]
    if a.no_synth:
        cases = [c for c in cases if "synth" not in c]
    ff = vertical.ffmpeg_path()
    W.load_logos()
    if not a.no_ocr:
        W.ocr_engine()
    rows = []
    for n, c in enumerate(cases, 1):
        p = key(c)
        if not os.path.isfile(p):
            print(f"[{n}/{len(cases)}] 跳过(找不到):{p}")
            continue
        src = p
        if a.cache:
            os.makedirs(a.cache, exist_ok=True)
            src = os.path.join(a.cache, hashlib.md5(p.encode("utf-8")).hexdigest()[:12] + Path(p).suffix)
            if not os.path.isfile(src):
                shutil.copyfile(p, src)
        gts = c.get("boxes") or []
        if "synth" in c:
            c = dict(c, synth=dict(c["synth"], base=src))
            try:
                src, gts = make_synth(c, ff)
            except Exception as e:  # noqa: BLE001
                print(f"[{n}/{len(cases)}] 合成失败:{e}")
                continue
        info = vertical.probe(src, ff)
        t = time.time()
        r = W.detect(src, ff, info, use_ocr=not a.no_ocr)
        sec = time.time() - t
        hits = r.get("hits") or []
        res = {"path": p, "synth": "synth" in c, "wm": c["wm"], "label": c.get("label"), "sec": round(sec, 2),
               "dur": round(info["dur"], 1), "gt": gts, "note": c.get("note", ""),
               "hits": [{k: x.get(k) for k in ("label", "kind", "score", "box", "spans", "text", "src")} for x in hits]}
        if c["wm"]:
            mine = [x for x in hits if not c.get("label") or x["label"] == c.get("label")]
            res["found"] = bool(mine)
            res["pos_ok"] = bool(mine) and (not gts or any(cover(x["box"], g) >= 0.5 for x in mine for g in gts))
            far = [x for x in mine if gts and max(cover(x["box"], g) + cover(g, x["box"]) for g in gts) == 0]
            res["extra"] = len([x for x in hits if x not in mine]) + len(far)
            tag = ("认出" if res["found"] else "漏了") + ("" if not res["found"] else ("·位置对" if res["pos_ok"] else "·位置不对"))
        else:
            res["extra"] = len(hits)
            tag = "误报!" if hits else "干净"
        rows.append(res)
        desc = "; ".join(f"{x['label']}/{x['kind']} {x['score']} {x['box']} {x.get('spans')}" +
                         (f" 「{x.get('text')}」" if x.get("text") else "") for x in hits)
        name = ("[合成 " + c.get("note", "") + "] " if res["synth"] else "") + Path(p).name[:36]
        print(f"[{n}/{len(cases)}] {tag:8} {sec:5.1f}s/{info['dur']:6.1f}s  {name}  {desc}"
              + (f"  真实框 {gts}" if c["wm"] else ""), flush=True)

    print("\n==== 汇总 ====")
    for title, sel in (("真实素材", [r for r in rows if not r["synth"]]), ("合成的", [r for r in rows if r["synth"]])):
        pos = [r for r in sel if r["wm"]]
        neg = [r for r in sel if not r["wm"]]
        if not sel:
            continue
        print(f"-- {title}")
        if pos:
            f = sum(r["found"] for r in pos)
            ok = sum(r["pos_ok"] for r in pos)
            print(f"有水印 {len(pos)} 条:认出 {f}({f / len(pos):.0%}),位置对 {ok}({ok / len(pos):.0%});"
                  f"多报别处 {sum(r['extra'] for r in pos)} 处")
            for r in pos:
                if not r["found"] or not r["pos_ok"]:
                    print("   漏 / 位置不对:", r["label"], r["note"], Path(r["path"]).name[:40])
        if neg:
            fp = [r for r in neg if r["extra"]]
            print(f"没水印 {len(neg)} 条:误报 {len(fp)} 条({len(fp) / len(neg):.1%})")
            for r in fp:
                print("   误报:", r["path"], [(x["label"], x["score"], x["box"]) for x in r["hits"]])
    real = [r for r in rows if not r["synth"]]
    if real:
        secs = [r["sec"] for r in real]
        per2 = [r["sec"] / max(r["dur"], 1) * 120 for r in real if r["dur"] >= 20]
        print(f"用时(真实素材):平均 {sum(secs) / len(secs):.1f} 秒/条,最慢 {max(secs):.1f} 秒"
              + (f";折合 2 分钟视频平均 {sum(per2) / len(per2):.1f} 秒" if per2 else ""))
    if a.out:
        Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
