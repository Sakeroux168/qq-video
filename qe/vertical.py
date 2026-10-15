"""横屏视频 → 竖屏(1080×1920):上下用同一段视频糊一下当底,中间放原画面。

快的办法(2026-10-15 在这台电脑上试过:53 秒 1080p 一条 8.7 秒,3 条一起 19 秒):
- 糊底先缩到 270×480 再糊再放大(在大图上糊很慢);缩放都用 fast_bilinear;
- 用显卡编码 h264_nvenc,声音直接拷不重编;显卡不行就退回 libx264 veryfast。
- 用百家号发布助手2 带的 ffmpeg 4.2.2(ainame 带的 ffmpeg 8 要新显卡驱动,这台用不了)。

原片不删:挪到同一个文件夹里的「横屏原片」里,转好的竖屏用原来的名字放回原处。
"""
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

ORIG_DIR = "横屏原片"
FILTER = ("[0:v]split=2[a][b];"
          "[a]scale=270:480:force_original_aspect_ratio=increase:flags=fast_bilinear,crop=270:480,"
          "boxblur=10:2,scale=1080:1920:flags=fast_bilinear,setsar=1[bg];"
          "[b]scale=1080:-2:flags=fast_bilinear[fg];[bg][fg]overlay=0:(H-h)/2")
_NOWIN = 0x08000000 if os.name == "nt" else 0


def ffmpeg_path() -> str:
    from .config import app_dir
    for p in (os.environ.get("QE_FFMPEG", ""),
              str(app_dir() / "ffmpeg.exe"),
              str(app_dir().parent / "百家号发布软件" / "百家号发布助手2" / "ffmpeg.exe"),
              r"E:\软件\百家号发布软件\百家号发布软件\百家号发布助手2\ffmpeg.exe"):
        if p and os.path.isfile(p):
            return p
    return shutil.which("ffmpeg") or ""


def probe(path: str, ffmpeg: str = "") -> dict:
    """{"w", "h", "rot", "dur"};读不出来 w=h=0。转过 90 度的(手机竖着拍、存成横的)按转过以后算。"""
    ff = ffmpeg or ffmpeg_path()
    try:
        p = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, timeout=30, creationflags=_NOWIN)
        txt = (p.stderr or b"").decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        txt = ""
    w = h = rot = 0
    dur = 0.0
    m = re.search(r"Stream #\S+.*?Video:.*?(\d{2,5})x(\d{2,5})", txt)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
    m = re.search(r"rotate\s*:\s*(-?\d+)", txt) or re.search(r"rotation of (-?[\d.]+) degrees", txt)
    if m:
        rot = int(abs(float(m.group(1)))) % 180
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", txt)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    if rot == 90:
        w, h = h, w
    return {"w": w, "h": h, "rot": rot, "dur": dur}


def is_landscape(info: dict) -> bool:
    return info.get("w", 0) > info.get("h", 0) > 0


def _cmd(ff: str, src: str, dst: str, nvenc: bool) -> list[str]:
    enc = (["-c:v", "h264_nvenc", "-preset", "fast", "-b:v", "6M"] if nvenc
           else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"])
    return [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-filter_complex", FILTER,
            *enc, "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", dst]


def to_vertical(path: str, ffmpeg: str = "", stop=None) -> tuple[str, str]:
    """转成竖屏,原片挪进「横屏原片」。返回 (竖屏的位置, 原片的新位置)。
    出错一律抛 RuntimeError,原片放回原处、临时文件删掉(2026-10-15 审查:OSError 时会留下 _处理中_ 文件)。"""
    ff = ffmpeg or ffmpeg_path()
    if not ff:
        raise RuntimeError("找不到 ffmpeg.exe")
    src = Path(path)
    # 临时文件名带进程号和随机数:同名的 a.mov / a.mp4 一起转不会抢同一个临时文件
    tmp = src.with_name(f"_处理中_{os.getpid()}_{uuid.uuid4().hex[:6]}_{src.stem}.mp4")
    try:
        return _convert(src, tmp, ff, stop)
    except RuntimeError:
        raise
    except OSError as e:
        raise RuntimeError(f"转竖屏失败(文件挪不动:{e.strerror or e})")
    finally:
        tmp.unlink(missing_ok=True)


def _convert(src: Path, tmp: Path, ff: str, stop) -> tuple[str, str]:
    err = ""
    for nvenc in (True, False):
        try:
            p = subprocess.Popen(_cmd(ff, str(src), str(tmp), nvenc), stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, creationflags=_NOWIN)
            while p.poll() is None:
                try:
                    p.wait(0.5)
                except subprocess.TimeoutExpired:
                    pass
                if stop and stop():
                    p.kill()
                    p.wait()
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError("停下了")
            err = (p.stderr.read() or b"").decode("utf-8", "replace").strip()
            if p.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 1024:
                break
        except OSError as e:
            err = str(e)
        tmp.unlink(missing_ok=True)
    else:
        raise RuntimeError(f"转竖屏失败:{err[-200:] or '不知道为什么'}")
    odir = src.parent / ORIG_DIR
    if odir.exists() and not odir.is_dir():
        raise RuntimeError(f"转竖屏失败:文件夹里有个叫「{ORIG_DIR}」的文件挡着,原片没地方放")
    odir.mkdir(exist_ok=True)
    orig = odir / src.name
    k = 2
    while orig.exists():
        orig = odir / f"{src.stem} ({k}){src.suffix}"
        k += 1
    # 转好的放回原名(.mp4);a.mov 转出来的 a.mp4 撞上同文件夹里另一条 a.mp4 → 加 (2),不覆盖
    out = src.with_suffix(".mp4")
    k = 2
    while out.exists() and os.path.normcase(str(out)) != os.path.normcase(str(src)):
        out = src.with_name(f"{src.stem} ({k}).mp4")
        k += 1
    os.replace(src, orig)
    try:
        os.replace(tmp, out)
    except OSError:
        os.replace(orig, src)                       # 新的放不回去:把原片挪回来,当没转过
        raise
    return str(out), str(orig)
