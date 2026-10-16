"""把查到的水印模糊掉(用户 2026-10-16:「查到水印模糊掉」)。和百家号那边「框水印」一样用 ffmpeg 糊一块,
不一样的是:框是查水印自己找到的(也能人手拖),**只糊水印出现的那几段**(B 站那条只有前 2 秒有,别的地方不糊)。

做法照转竖屏(vertical.py):先转出新文件,原片挪进同一个文件夹的「水印原片」,新的放回原名;
出错 / 停了:原片放回原处,临时文件删掉。
boxes = [{"ratio": [x, y, w, h](0~1,相对原画面), "spans": [[开始秒, 结束秒], ...](空 = 整条)}]
"""
import os
import subprocess
import uuid
from pathlib import Path

from . import vertical

_NOWIN = 0x08000000 | 0x00004000 if os.name == "nt" else 0
ORIG_DIR = "水印原片"
MARGIN = 0.25                     # 框往外放宽(框的宽 / 高的 25%,再加 6 像素):半透明水印边上有光晕


def pixel_box(ratio: list, w: int, h: int) -> tuple[int, int, int, int]:
    """比例框 → 原画面上的像素框(放宽一点,偶数,不出界)。"""
    x, y, bw, bh = ratio
    mx, my = bw * MARGIN + 6 / max(w, 1), bh * MARGIN + 6 / max(h, 1)
    x0, y0 = max(0.0, x - mx), max(0.0, y - my)
    x1, y1 = min(1.0, x + bw + mx), min(1.0, y + bh + my)
    px, py = int(x0 * w) // 2 * 2, int(y0 * h) // 2 * 2
    pw = max(8, int((x1 - x0) * w) // 2 * 2)
    ph = max(8, int((y1 - y0) * h) // 2 * 2)
    pw, ph = min(pw, w - px), min(ph, h - py)
    return px, py, pw, ph


def _enable(spans) -> str:
    """只在这几段糊:between(t,a,b)+…;整条就不加。"""
    sp = [s for s in (spans or []) if len(s) == 2 and s[1] > s[0]]
    if not sp:
        return ""
    return ":enable='" + "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in sp) + "'"


def filter_graph(boxes: list[dict], w: int, h: int) -> str:
    """[0:v] 拆成 1 + N 份:每份切出框那块 → 高斯模糊 → 在出现的那几段叠回去。"""
    n = len(boxes)
    parts = [f"[0:v]split={n + 1}[base]" + "".join(f"[c{i}]" for i in range(n))]
    last = "base"
    for i, b in enumerate(boxes):
        px, py, pw, ph = pixel_box(b["ratio"], w, h)
        sigma = max(6, min(pw, ph) // 3)
        parts.append(f"[c{i}]crop={pw}:{ph}:{px}:{py},gblur=sigma={sigma}:steps=2[b{i}]")
        parts.append(f"[{last}][b{i}]overlay={px}:{py}{_enable(b.get('spans'))}[v{i}]")
        last = f"v{i}"
    parts.append(f"[{last}]format=yuv420p[out]")
    return ";".join(parts)


def _cmd(ff: str, src: str, dst: str, graph: str, nvenc: bool) -> list[str]:
    enc = (["-c:v", "h264_nvenc", "-preset", "fast", "-b:v", "6M"] if nvenc
           else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"])
    return [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-filter_complex", graph, "-map", "[out]",
            "-map", "0:a?", *enc, "-c:a", "copy", "-movflags", "+faststart", dst]


def blur(path: str, boxes: list[dict], ffmpeg: str = "", stop=None) -> tuple[str, str]:
    """糊掉。返回 (新文件位置, 原片新位置)。出错抛 RuntimeError(原片还在原处)。"""
    ff = ffmpeg or vertical.ffmpeg_path()
    if not ff:
        raise RuntimeError("找不到 ffmpeg.exe")
    boxes = [b for b in boxes or [] if b.get("ratio")]
    if not boxes:
        raise RuntimeError("没有要糊的地方")
    info = vertical.probe(path, ff)
    if not info["w"]:
        raise RuntimeError("视频读不出来")
    graph = filter_graph(boxes, info["w"], info["h"])
    src = Path(path)
    tmp = src.with_name(f"_处理中_{os.getpid()}_{uuid.uuid4().hex[:6]}_{src.stem}.mp4")
    try:
        err = ""
        for nvenc in (True, False):
            try:
                p = subprocess.Popen(_cmd(ff, str(src), str(tmp), graph, nvenc), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, creationflags=_NOWIN)
                while p.poll() is None:
                    try:
                        p.wait(0.5)
                    except subprocess.TimeoutExpired:
                        pass
                    if stop and stop():
                        p.kill()
                        p.wait()
                        raise RuntimeError("停下了")
                err = (p.stderr.read() or b"").decode("utf-8", "replace").strip()
                if p.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 1024:
                    break
            except OSError as e:
                err = str(e)
            tmp.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"模糊水印失败:{err[-200:] or '不知道为什么'}")
        return _swap(src, tmp)
    except OSError as e:
        raise RuntimeError(f"模糊水印失败(文件挪不动:{e.strerror or e})")
    finally:
        tmp.unlink(missing_ok=True)


def _swap(src: Path, tmp: Path) -> tuple[str, str]:
    return _swap_into(src, tmp, ORIG_DIR)


def _swap_into(src: Path, tmp: Path, orig_dir: str) -> tuple[str, str]:
    """原片挪进 orig_dir(「水印原片」「广告原片」),新的放回原名(.mp4)。新的放不回去就把原片挪回来。"""
    odir = src.parent / orig_dir
    if odir.exists() and not odir.is_dir():
        raise RuntimeError(f"文件夹里有个叫「{orig_dir}」的文件挡着,原片没地方放")
    odir.mkdir(exist_ok=True)
    orig = odir / src.name
    k = 2
    while orig.exists():
        orig = odir / f"{src.stem} ({k}){src.suffix}"
        k += 1
    out = src.with_suffix(".mp4")
    if out.exists() and os.path.normcase(str(out)) != os.path.normcase(str(src)):
        from .topic import _numbered
        k = 2
        while out.exists():
            out = src.with_name(f"{_numbered(src.stem, k)}.mp4")
            k += 1
    os.replace(src, orig)
    try:
        os.rename(tmp, out)
    except OSError:
        os.replace(orig, src)
        raise
    return str(out), str(orig)


def boxes_of(wm: dict) -> list[dict]:
    """查水印的结果 → 要糊的框。"""
    out = []
    for x in (wm or {}).get("hits") or []:
        if x.get("ratio"):
            out.append({"ratio": x["ratio"], "spans": x.get("spans") or []})
    return out
