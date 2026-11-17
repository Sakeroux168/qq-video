"""字幕被裁(用户 2026-11-07):有同事把横屏硬转竖屏,两边直接裁掉,字幕只剩中间一截。「检测这种情况,然后能打回去让同事重找」。

我们自己转的是上下加黑边(1080×1920),不会裁;被裁的都是满屏没黑边的。所以只看满屏的竖屏视频:抽 7 帧,问千问字幕两头是不是被切了,
3 帧以上算被裁。11-07 拿 FPS游戏射击馆 11.6 的 69 条试:47 条有黑边不用看;满屏 22 条里 18 条 3 帧以上,4 条 0~1 帧,中间没有含糊的。
抽 4 帧不够:用户点名的「最高压的一集」只有 1 帧看得出来;开头也要抽(用户截图就是开头 1 秒)。
记在 字幕被裁.json(wmstore.CROP),文件没变不重问。人说没被裁:ok=True(和水印一样)。

打回(用户说的放法):素材盘上单独一个「打回视频」文件夹,下面按账号名分,视频连封面放进去,用户自己去跟同事说。软件不读这个文件夹。
"""
import base64
import io
import json
import os
import subprocess

from . import wmstore

MODEL = "qwen3-vl-plus"
URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
POINTS = (0.03, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9)
MIN_CUT = 3
FULL = 0.96                                          # 有画面的那块占整张几成以上算满屏
FOLDER = "打回视频"
TEXT = "字幕被裁"
PROMPT = ("这是竖屏短视频里的一帧。看画面里烧录的字幕(一行字):\n"
          "字幕的第一个字和最后一个字是完整的吗?如果字幕两头被图片左右边缘切掉、句子明显没头没尾,就是切断了。\n"
          '只回 JSON:{"subtitle": "有" 或 "没有", "cut": "切断了" 或 "没切断"}')
_NOWIN = 0x08000000 if os.name == "nt" else 0


def _frame(ff: str, path: str, t: float):
    from PIL import Image
    r = subprocess.run([ff, "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, timeout=60, creationflags=_NOWIN)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def full_screen(im) -> bool:
    """竖屏、四边没有黑边(我们转竖屏的都有上下黑边,不用看)。"""
    import numpy as np
    from .sharp import active
    if im.height <= im.width:
        return False
    g = active(np.array(im.convert("L")))
    return g is not None and g.shape[0] >= im.height * FULL and g.shape[1] >= im.width * FULL


def ask(im, key, timeout: int = 60) -> bool:
    """这一帧字幕被切了吗。AI 没回话 / 读不出来抛 RuntimeError(不当成没问题)。key:百炼 Key 或 aiconf.AI。"""
    import requests
    from .aiconf import as_ai, clean, tokens
    ai = as_ai(key, MODEL)
    if not ai.key:
        raise RuntimeError("没填阿里百炼 Key")
    k = 960 / max(im.size)
    buf = io.BytesIO()
    im.resize((int(im.width * k), int(im.height * k))).save(buf, "JPEG", quality=88)
    body = {"model": ai.model, "temperature": 0, "max_tokens": tokens(ai, 60), **ai.extra(), "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")}},
        {"type": "text", "text": PROMPT}]}]}
    try:
        r = requests.post(ai.url(), json=body, headers={"Authorization": f"Bearer {ai.key}", "Content-Type": "application/json"}, timeout=timeout)
    except (requests.RequestException, ValueError) as e:      # ValueError:Key 里有中文
        raise RuntimeError(f"连不上{ai.who}(网络?{type(e).__name__})")
    try:
        raw = clean(r.json()["choices"][0]["message"]["content"])
        return parse(raw)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        from .aierr import why
        raise RuntimeError(why(r, ai.who) or f"{ai.who}没回话(HTTP {r.status_code},{type(e).__name__})")


def parse(raw: str) -> bool:
    d = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    return str(d.get("cut") or "") == "切断了"          # 不看 subtitle:它说没字幕也常是界面文字被切,照样算


def check(path: str, ff: str, dur: float, key: str, stop=None, grab=None, asker=None) -> dict:
    """查一条:{"hits": [{"n": 几帧被切, "of": 看了几帧}]},没事 hits 空。有黑边的不问 AI。
    grab(t) / asker(图):测试里换掉,绝不真问 AI。一帧都读不出来抛 OSError(不记成没问题)。"""
    grab = grab or (lambda t: _frame(ff, path, t))
    asker = asker or (lambda im: ask(im, key))
    ims = []
    for f in POINTS:
        if stop and stop():
            raise OSError("停下了")
        im = grab(dur * f)
        if im is not None:
            ims.append(im)
    if not ims:
        raise OSError("读不出画面")
    if sum(1 for im in ims if full_screen(im)) * 2 < len(ims):       # 大半帧有黑边:正常转的
        return {"hits": []}
    n = 0
    for im in ims:
        if stop and stop():
            raise OSError("停下了")
        n += bool(asker(im))
    return {"hits": [{"n": n, "of": len(ims)}] if n >= MIN_CUT else []}


def back_dir(material_root: str, nick: str) -> str:
    """素材盘\\打回视频\\<账号名>(和 小学生教育、游戏视频 这些放一起)。"""
    return os.path.join(os.path.dirname(os.path.normpath(material_root)), FOLDER, nick)


def send_back(path: str, to: str) -> str:
    """视频连封面挪进 to:走 safe_move_file,重名加 (2),不覆盖、不删。返回视频的新位置。"""
    from .fsops import move_tree, safe_move_file, unique
    from .redo import extras
    more = extras(path)
    new = safe_move_file(path, unique(os.path.join(to, os.path.basename(path))))
    for p, _k, r in more:
        try:
            if os.path.isdir(p):
                move_tree(p, os.path.join(to, r))
            else:
                safe_move_file(p, unique(os.path.join(to, r)))
        except OSError:
            pass                                     # 封面挪不动不算失败(视频已经挪了)
    return new


def names_text(rows: list[tuple[str, str]]) -> str:
    """发给同事的名单:[(号, 标题)] → 按号分。"""
    by: dict[str, list[str]] = {}
    for nick, title in rows:
        by.setdefault(nick, []).append(title)
    out = ["这些视频字幕被裁了,麻烦重找 / 用等比例重新转:"]
    for nick, ts in by.items():
        out.append(f"【{nick}】{len(ts)} 条")
        out += [f"  {t}" for t in ts]
    return "\n".join(out)
