"""剪掉口播广告那几段(用户 2026-10-16 同意从百家号搬「剪片段」)。

段落来自 ads.groups(语音转文字每句几秒到几秒),前后各多剪 0.3 秒;
画面和声音一起剪(select / aselect),剪完时间重新接上。原片挪进「广告原片」,出错原片放回原处(照 blur.py)。
"""
import os
import subprocess
import uuid
from pathlib import Path

from . import vertical
from .blur import _swap_into

_NOWIN = 0x08000000 | 0x00004000 if os.name == "nt" else 0
ORIG_DIR = "广告原片"
PAD = 0.3


def spans_to_cut(hits: list[dict], dur: float) -> list[tuple[float, float]]:
    """广告段 → 要剪的时间段(前后放宽、合并重叠的、不出界)。"""
    sp = sorted((max(0.0, float(h["start"]) - PAD), min(dur or 1e9, float(h["end"]) + PAD)) for h in hits or [])
    out: list[list[float]] = []
    for a, b in sp:
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 2), round(b, 2)) for a, b in out]


def _expr(spans) -> str:
    return "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in spans)


def cut(path: str, hits: list[dict], ffmpeg: str = "", stop=None) -> tuple[str, str, float]:
    """剪掉。返回 (新文件位置, 原片新位置, 剪掉了几秒)。出错抛 RuntimeError(原片还在原处)。"""
    ff = ffmpeg or vertical.ffmpeg_path()
    if not ff:
        raise RuntimeError("找不到 ffmpeg.exe")
    info = vertical.probe(path, ff)
    if not info["w"]:
        raise RuntimeError("视频读不出来")
    spans = spans_to_cut(hits, info["dur"])
    if not spans:
        raise RuntimeError("没有要剪的")
    gone = sum(b - a for a, b in spans)
    if info["dur"] and gone > info["dur"] * 0.5:
        raise RuntimeError(f"要剪掉 {gone:.0f} 秒,超过一半了,不敢自动剪,你自己看一下")
    e = _expr(spans)
    src = Path(path)
    tmp = src.with_name(f"_处理中_{os.getpid()}_{uuid.uuid4().hex[:6]}_{src.stem}.mp4")
    try:
        err = ""
        for nvenc in (True, False):
            enc = (["-c:v", "h264_nvenc", "-preset", "fast", "-b:v", "6M"] if nvenc
                   else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"])
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                   "-vf", f"select='not({e})',setpts=N/FRAME_RATE/TB",
                   "-af", f"aselect='not({e})',asetpts=N/SR/TB",
                   *enc, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(tmp)]
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=_NOWIN)
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
            except OSError as ex:
                err = str(ex)
            tmp.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"剪广告失败:{err[-200:] or '不知道为什么'}")
        new, orig = _swap_into(src, tmp, ORIG_DIR)
        return new, orig, round(gone, 1)
    except OSError as ex:
        raise RuntimeError(f"剪广告失败(文件挪不动:{ex.strerror or ex})")
    finally:
        tmp.unlink(missing_ok=True)
