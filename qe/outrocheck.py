"""结尾求关注 / 别人账号 / 二维码(用户 2026-11-16):
视频最后几秒如果带着别人账号的「点赞关注」「抖音号」「二维码」等片尾，不能直接发（跟我们的账号头像、名字对不上）。

做法：
1. 查：在最后约 11 秒抽帧（一次 ffmpeg 读出），取结尾 4 帧拼成 2×2 图问看图 AI（与字幕被裁共用同一个 AI 设置）。
   明确排除正片里主角口头禅字幕（如「期待各位入股」）、普通「感谢观看」结束语、衣服工作牌等，只抓真正的引流片尾 / 别人账号 / 二维码。
2. 定位起点：从 AI 认出片尾的那一帧往前比对画面，再在跳变那 0.35 秒里按高帧率细找一帧，算出片尾从第几秒开始（精确到约 0.04 秒，含渐入/短黑屏）。
3. 剪：用户预览保留帧与剪掉帧并确认后，用 ffmpeg 保留 [0, start) 并重编成新文件，原片挪进旁边的「结尾原片」文件夹留底。
"""
import base64
import hashlib
import io
import json
import os
import subprocess
import uuid
from pathlib import Path

from . import blur, vertical
from .config import data_dir

MODEL = "qwen3-vl-plus"
WINDOW = 11.0
FPS = 4.0
ORIG_DIR = "结尾原片"
TEXT = "结尾求关注"
_NOWIN = (0x08000000 | 0x00004000) if os.name == "nt" else 0

PROMPT = (
    "这是同一条短视频结尾几秒的 4 张按时间先后排列的截图（编号 1 到 4，4 是最末尾）。\n"
    "判断视频结尾是不是出现了需要剪掉的片尾/关注引导。只有最后几帧（通常是 3 或 4）明确出现下面三种情况之一才算「有」：\n"
    "1. 带账号头像的片尾卡片或关注贴纸（不限位置，不管在画面中央还是叠在右上角/边角，不管带不带红勾）：\n"
    "   - 画面中央（黑底或半透明叠层）出现独立的圆形/方形「账号头像框」，配着红「+」或「✓」关注图标，或下方/周围写着「点我关注 / 感谢观看 / Thanks for watching / 我们下期再见 / 记得点赞关注」或账号名；\n"
    "   - 叠在视频画面边角（如右上角）的独立圆形/方形账号头像框，且底部明确带着红色「+」或「✓」关注徽标；\n"
    "2. 平台官方片尾或剪辑软件默认片尾：\n"
    "   - 剪映 / CapCut 默认片尾（黑底/深色底 + 剪刀折纸 Logo + 「剪映」或「CapCut」）；\n"
    "   - 快影 / 必剪 / 度咔等剪辑软件默认片尾（纯色/黑底 + 软件 Logo 与名称）；\n"
    "   - 抖音（黑底 + 音符 Logo + 「抖音 / 记录美好生活 / 抖音号」）、快手（双圆摄像机 Logo + 「快手 / 拥抱每一种生活 / 快手号」）、小红书（「小红书 / 你的生活指南」）、B站（小电视 Logo + 「哔哩哔哩 / 干杯」）、西瓜视频（「西瓜视频 / 点亮对生活的好奇心」）、微信视频号 / 微视等平台标准片尾画面；\n"
    "3. 明确的扫码二维码。\n\n"
    "【严格排除，以下情况全部算「没有」（found=false）】：\n"
    "- 画面里只有文字或账号名字（哪怕出现「@某某」「作者名」「感谢观看」「下期再见」「记得点赞关注」等文字，但没有独立账号头像框、没有上述平台/剪辑软件 Logo、也没有二维码），一律不算；\n"
    "- 游戏 / 赛事 / 动漫正片画面里的角色血条头像、英雄技能图标、战队名、选手名、主播名、角落小字、字幕台词、普通游戏 UI，一律不算；\n"
    "- 人物衣服上的工作牌 / 医院标志 / 科普免责声明，不算。\n\n"
    '只回 JSON：{"found": true 或 false, "tiles": [出现的那几张编号, 没有写[]], "kind": "头像片尾" 或 "平台/剪辑片尾" 或 "二维码" 或 "没有", "reason": "不超过15字的简短原因"}'
)


def fmt_time(sec: float) -> str:
    s = max(0.0, float(sec or 0))
    m, r = int(s) // 60, s - int(s) // 60 * 60
    return f"{m}:{r:04.1f}"


def _font(size: int = 26):
    from PIL import ImageFont
    for p in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def grab_frame(ff: str, path: str, t: float):
    """取 t 秒那一帧 RGB Image（超出视频尾时退用 -sseof）；读不出来给 None。"""
    from PIL import Image
    cmd = [ff, "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", path, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=_NOWIN)
    if not r.stdout:
        r = subprocess.run([ff, "-v", "error", "-sseof", "-0.15", "-i", path, "-frames:v", "1",
                            "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True, timeout=60, creationflags=_NOWIN)
    if not r.stdout:
        return None
    try:
        return Image.open(io.BytesIO(r.stdout)).convert("RGB")
    except Exception:
        return None


def _decode_slice(path: str, ff: str, start: float, tw: int, th: int, fps: float, span: float = 0.0):
    import numpy as np
    cmd = [ff, "-v", "error", "-ss", f"{max(0.0, start):.2f}"]
    if span > 0:
        cmd += ["-t", f"{span:.2f}"]
    cmd += ["-i", path, "-vf", f"fps={fps},scale={tw}:{th}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=_NOWIN)
    raw = r.stdout or b""
    step = tw * th * 3
    n = len(raw) // step if step else 0
    if not n:
        return [], np.empty((0, th, tw, 3), dtype="uint8")
    arr = np.frombuffer(raw[:n * step], dtype="uint8").reshape(n, th, tw, 3)
    ts = [round(max(0.0, start) + i / fps, 3) for i in range(n)]
    return ts, arr


def tail_points(dur: float) -> list[float]:
    if dur <= 6.0:
        return [round(max(0.05, dur * f), 2) for f in (0.25, 0.55, 0.78, 0.94)]
    return [round(max(0.05, dur + off), 2) for off in (-5.0, -3.0, -1.3, -0.35)]


def pick_4(ts: list[float]) -> list[int]:
    if len(ts) <= 4:
        return list(range(len(ts)))
    end_t = ts[-1]
    span = end_t - ts[0]
    if span <= 6.0:
        targets = [ts[0] + span * f for f in (0.25, 0.55, 0.78, 0.96)]
    else:
        targets = [end_t - 5.0, end_t - 3.0, end_t - 1.3, end_t - 0.25]
    idx = [min(range(len(ts)), key=lambda i: abs(ts[i] - t)) for t in targets]
    for k in range(1, len(idx)):
        if idx[k] <= idx[k - 1] and idx[k - 1] + 1 < len(ts):
            idx[k] = idx[k - 1] + 1
    return idx


def make_grid(arr, idx: list[int]):
    """把选出来的最多 4 帧拼成带黄底编号(1~4)的 2×2 图。"""
    from PIL import Image, ImageDraw
    font = _font(26)
    _, th, tw, _ = arr.shape
    grid = Image.new("RGB", (tw * 2 + 8, th * 2 + 8), (30, 30, 30))
    for k, i in enumerate(idx[:4]):
        t = Image.fromarray(arr[i])
        d = ImageDraw.Draw(t)
        d.rectangle((6, 6, 42, 42), fill=(255, 220, 0))
        d.text((24, 24), str(k + 1), fill=(0, 0, 0), font=font, anchor="mm")
        grid.paste(t, ((k % 2) * (tw + 8), (k // 2) * (th + 8)))
    return grid


def parse(raw: str) -> dict:
    d = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    tiles = []
    for t in d.get("tiles") or []:
        try:
            n = int(t)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 4 and n not in tiles:
            tiles.append(n)
    return {
        "found": bool(d.get("found")),
        "tiles": sorted(tiles),
        "kind": str(d.get("kind") or "").strip(),
        "reason": str(d.get("reason") or "").strip(),
    }


def ask(grid, key, timeout: int = 60) -> dict:
    """把 4 格拼图交给看图 AI。出错抛 RuntimeError(不当成没问题)。"""
    import requests
    from .aiconf import as_ai, clean, tokens
    ai = as_ai(key, MODEL)
    if not ai.key:
        raise RuntimeError("没填阿里百炼 Key")
    buf = io.BytesIO()
    grid.save(buf, "JPEG", quality=88)
    body = {"model": ai.model, "temperature": 0, "max_tokens": tokens(ai, 180), **ai.extra(),
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")}},
                {"type": "text", "text": PROMPT}]}]}
    try:
        r = requests.post(ai.url(), json=body, headers={"Authorization": f"Bearer {ai.key}", "Content-Type": "application/json"}, timeout=timeout)
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"连不上{ai.who}(网络?{type(e).__name__})")
    try:
        raw = clean(r.json()["choices"][0]["message"]["content"])
        return parse(raw)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        from .aierr import why
        raise RuntimeError(why(r, ai.who) or f"{ai.who}没回话(HTTP {r.status_code},{type(e).__name__})")


def _walk_back(arr, ref, start_idx: int) -> int:
    """从 start_idx 往前走到画面不再像 ref（含紧挨着的短黑屏或半透明渐入）的位置。"""
    import numpy as np
    f = arr.astype(np.float32)
    dist = np.abs(f - ref).mean(axis=(1, 2, 3))
    s_ref = ref - ref.mean()
    n_ref = float(np.sqrt((s_ref * s_ref).sum())) + 1e-6
    corr = []
    for k in range(len(f)):
        sk = f[k] - f[k].mean()
        nk = float(np.sqrt((sk * sk).sum())) + 1e-6
        corr.append(float((sk * s_ref).sum() / (nk * n_ref)))
    k = start_idx
    while k > 0 and ((dist[k - 1] <= 14.0 and corr[k - 1] >= 0.45) or dist[k - 1] <= 7.0 or corr[k - 1] >= 0.72):
        k -= 1
    while k > 0 and ((f[k - 1].mean() < 6 and f[k - 1].std() < 6) or corr[k - 1] >= 0.48):
        k -= 1
    return k


def find_start_idx(ts: list[float], arr, card_idx: int, early_idx: int | None = None) -> int:
    """从末尾片尾帧往回找卡片起点下标;如果有动态变化导致更早一格也含片尾,继续往回走。"""
    if len(ts) < 2:
        return 0
    f = arr.astype("float32")
    idx = min(max(0, card_idx), len(ts) - 1)
    while idx > 0 and f[idx].mean() < 3 and f[idx].std() < 3:
        idx -= 1
    k = _walk_back(arr, f[idx], idx)
    if early_idx is not None and 0 <= early_idx < k:
        k2 = _walk_back(arr, f[early_idx], early_idx)
        k = min(k, k2)
    return k


def _save_shot(arr, k: int, card_idx: int, path: str, shot_dir: str) -> str:
    """保存一张预览图(左边保留前帧,右边片尾帧)供表格悬停看。"""
    from PIL import Image, ImageDraw
    d = Path(shot_dir) if shot_dir else (data_dir() / "结尾截图")
    d.mkdir(parents=True, exist_ok=True)
    right = Image.fromarray(arr[card_idx])
    rw = 200
    rh = max(40, int(right.height * rw / max(right.width, 1)))
    right = right.resize((rw, rh), Image.LANCZOS)
    if k > 0:
        left = Image.fromarray(arr[k - 1]).resize((rw, rh), Image.LANCZOS)
        out = Image.new("RGB", (rw * 2 + 6, rh), (36, 36, 36))
        out.paste(left, (0, 0))
        out.paste(right, (rw + 6, 0))
        dr = ImageDraw.Draw(out)
        dr.rectangle((0, 0, rw - 1, rh - 1), outline=(40, 180, 90), width=3)
        dr.rectangle((rw + 6, 0, rw * 2 + 5, rh - 1), outline=(230, 60, 50), width=3)
    else:
        out = right
    key = hashlib.md5(os.path.normcase(os.path.abspath(path)).encode("utf-8", "ignore")).hexdigest()[:12]
    dst = d / f"{key}.jpg"
    out.save(str(dst), "JPEG", quality=84)
    return str(dst)


def check(path: str, ff: str, dur: float, key, stop=None, grab=None, asker=None, shot_dir: str = "") -> dict:
    """查一条:有求关注片尾返回 {"hits": [{"start", "dur", "cut", "kind", "reason"}], "shot": "..."};
    没事返回 {"hits": []}。grab(t) / asker(grid):测试里换掉,绝不真问 AI。读不出来抛 OSError。"""
    import numpy as np
    asker = asker or (lambda im: ask(im, key))
    if grab is not None:
        pts = tail_points(dur)
        ims = []
        ts = []
        for t in pts:
            if stop and stop():
                raise OSError("停下了")
            im = grab(t)
            if im is not None:
                ims.append(im)
                ts.append(t)
        if not ims:
            raise OSError("读不出画面")
        w0, h0 = ims[0].size
        tw = 360 if h0 >= w0 else 480
        th = max(60, int(round(h0 * tw / max(w0, 1))) // 2 * 2)
        arr = np.stack([np.array(im.convert("RGB").resize((tw, th))) for im in ims])
    else:
        info = vertical.probe(path, ff)
        if not info["w"]:
            raise OSError("读不出画面")
        d0 = float(dur or info["dur"] or 0)
        if d0 <= 0:
            raise OSError("读不出画面")
        dur = d0
        tw = 360 if info["h"] >= info["w"] else 480
        th = max(60, int(round(info["h"] * tw / max(info["w"], 1))) // 2 * 2)
        if stop and stop():
            raise OSError("停下了")
        ts, arr = _decode_slice(path, ff, max(0.0, dur - WINDOW), tw, th, FPS)
        if not len(ts):
            raise OSError("读不出画面")

    idx4 = pick_4(ts)
    grid = make_grid(arr, idx4)
    if stop and stop():
        raise OSError("停下了")
    res = asker(grid)
    if not res.get("found"):
        return {"hits": []}

    tiles = [t for t in (res.get("tiles") or []) if isinstance(t, int) and 1 <= t <= len(idx4)]
    cidx = idx4[tiles[-1] - 1] if tiles else idx4[-1]
    eidx = idx4[tiles[0] - 1] if len(tiles) >= 2 else None
    k = find_start_idx(ts, arr, cidx, eidx)
    start = ts[k]

    # 片尾超过 11 秒(一直顶到窗口最左端):再往前看一截
    if grab is None and k == 0 and ts[0] > 0.5:
        ts_e, arr_e = _decode_slice(path, ff, max(0.0, ts[0] - 12.0), tw, th, FPS, span=12.5)
        if len(ts_e) >= 2:
            ke = _walk_back(arr_e, arr[cidx].astype("float32"), len(ts_e) - 1)
            start = ts_e[ke]
            if ke > 0:
                ts, arr, k = ts_e, arr_e, ke

    # 粗定位之后在跳变那 0.5 秒里用 25fps 细找一帧，让剪切点几乎零误差
    if grab is None and k > 0 and start > 0.35:
        ts_f, arr_f = _decode_slice(path, ff, max(0.0, start - 0.35), tw, th, 25.0, span=0.55)
        if len(ts_f) >= 2:
            kf = _walk_back(arr_f, arr[cidx].astype("float32"), len(ts_f) - 1)
            start = max(0.0, ts_f[kf] - 0.02)

    start = round(max(0.0, start), 2)
    shot = _save_shot(arr, k, cidx, path, shot_dir)
    return {
        "hits": [{
            "start": start,
            "dur": round(float(dur), 2),
            "cut": round(max(0.0, float(dur) - start), 1),
            "kind": res.get("kind") or "求关注",
            "reason": res.get("reason") or "",
        }],
        "shot": shot,
    }


def hit_info(res: dict | None) -> dict | None:
    hits = (res or {}).get("hits") or []
    return hits[0] if hits and isinstance(hits[0], dict) else None


def label(res: dict | None) -> str:
    h = hit_info(res)
    if not h:
        return TEXT
    return f"{TEXT}(剪掉最后 {h.get('cut', 0):.1f} 秒)" if h.get("cut") else TEXT


def cut(path: str, start: float, ffmpeg: str = "", stop=None) -> tuple[str, str, float]:
    """保留 [0, start) 并把原片挪进同级「结尾原片」文件夹。返回 (新文件位置, 原片新位置, 剪掉秒数)。"""
    ff = ffmpeg or vertical.ffmpeg_path()
    if not ff:
        raise RuntimeError("找不到 ffmpeg.exe")
    info = vertical.probe(path, ff)
    if not info["w"] or not info["dur"]:
        raise RuntimeError("视频读不出来")
    dur = float(info["dur"])
    start = round(float(start), 2)
    if start <= 0.3 or start >= dur - 0.1:
        raise RuntimeError("剪切时间不对,先点开看一眼再剪")
    gone = dur - start
    if gone > dur * 0.6:
        raise RuntimeError(f"要从 {fmt_time(start)} 剪到最后(剪掉 {gone:.1f} 秒,超过六成了),不敢自动剪,你自己看一下")
    src = Path(path)
    tmp = src.with_name(f"_处理中_{os.getpid()}_{uuid.uuid4().hex[:8]}.mp4")
    try:
        err = ""
        for nvenc in (True, False):
            enc = (["-c:v", "h264_nvenc", "-preset", "fast", "-b:v", "6M"] if nvenc
                   else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"])
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-t", f"{start:.3f}",
                   "-map", "0:v:0", "-map", "0:a?", *enc, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                   "-movflags", "+faststart", str(tmp)]
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
            raise RuntimeError(f"剪结尾失败:{err[-200:] or '不知道为什么'}")
        new, orig = blur._swap_into(src, tmp, ORIG_DIR)
        return new, orig, round(gone, 1)
    except OSError as ex:
        raise RuntimeError(f"剪结尾失败(文件挪不动:{ex.strerror or ex})")
    finally:
        tmp.unlink(missing_ok=True)
