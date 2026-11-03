"""重名的视频(用户 2026-11-03):
① 「处理重名」:AI 照原标题改一个意思相近的标题 —— 「记住意思必须相近,不能有其他风格」;结尾的话题原样留着;
   新标题不能再和这个号发过的 / 这天别的重名;
② 确实重复的:选中按 Delete 删掉 —— 素材在网络盘(X:),Windows 回收站管不到网络盘(删了就真没了),
   所以挪进视频旁边的「重复删除」文件夹(软件不再读它,删错了去那里拿回来)。
"""
import os
import re

from . import topic
from .fsops import safe_move_file, unique

TRASH = "重复删除"
PROMPT = ("把下面这个短视频标题换一种说法。要求:\n"
          "1. 意思必须和原标题相近,说的是同一件事,只换用词和语序;\n"
          "2. 风格和原标题一样:不加表情、不加感叹号问号、不加「震惊」「必看」这类夸张的词,不加原标题没有的内容;\n"
          "3. 字数和原标题差不多;\n"
          "4. 不能和原标题一样,也不能和下面「不要用」里的任何一个一样。\n"
          "只回新标题这一行,不要别的字,不要引号。\n\n"
          "原标题:{body}\n{avoid}")


def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", str(s or "")).lower()


def ask_ai(body: str, avoid: list[str], key: str, model: str = "qwen-plus", timeout: int = 60) -> str:
    """问 AI 一个意思相近的说法(只给正文,不给话题)。出错抛 RuntimeError。"""
    import requests
    if not key:
        raise RuntimeError("要 AI 改标题,先在「设置」里填阿里百炼 Key")
    av = ("不要用:\n" + "\n".join(avoid[:20])) if avoid else ""
    msg = PROMPT.format(body=body, avoid=av)
    try:
        r = requests.post("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                          json={"model": model, "messages": [{"role": "user", "content": msg}], "temperature": 0.7,
                                "max_tokens": 200, "enable_thinking": False},
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=timeout)
        return str(r.json()["choices"][0]["message"]["content"])
    except Exception:
        raise RuntimeError("AI 没回话(网络 / Key?)")


def new_title(title: str, taken, key: str, asker=None, tries: int = 3) -> str:
    """给一条重名的视频想个新标题(正文让 AI 换说法,结尾话题原样接上)。taken(新标题) → 这个号用过没有。
    想不出来(AI 回的不像样 / 一直重名)返回 ""。"""
    p = topic.split_topics(title)
    body = p["body"].strip()
    tail = title[len(p["body"]):]                       # 话题那段(带前面的空格)原样留着
    ask = asker or (lambda b, av: ask_ai(b, av, key))
    avoid: list[str] = []
    for _ in range(tries):
        raw = ask(body, avoid)
        cand = topic.sanitize(raw.strip().splitlines()[0] if raw.strip() else "").strip("「」\"'“”")
        cand = re.sub(r"\s*#\S+", "", cand).strip()     # AI 自己加了话题的去掉(话题用原来的)
        if not cand or _norm(cand) == _norm(body) or abs(len(cand) - len(body)) > max(4, len(body) * 0.5):   # 字数差太多 = 风格变了
            avoid.append(cand) if cand else None
            continue
        full = cand + tail
        if taken(full):
            avoid.append(cand)
            continue
        return full
    return ""


def trash(path: str, covers=()) -> list[str]:
    """把一条视频连同名封面挪进旁边的「重复删除」文件夹(不真删)。covers = 别处配上的这条的封面(教育号按名字配的),
    也一起挪(和视频同名的才挪,免得挪走别的视频共用的图)。返回挪过去的新位置。出错抛 OSError。"""
    d, base = os.path.split(path)
    stem = os.path.splitext(base)[0]
    dst_dir = os.path.join(d, TRASH)
    os.makedirs(dst_dir, exist_ok=True)
    out = [safe_move_file(path, unique(os.path.join(dst_dir, base)))]
    side = [os.path.join(d, n) for n in os.listdir(d)]
    for p in dict.fromkeys(side + [c for c in covers if c]):
        s2, e2 = os.path.splitext(os.path.basename(p))
        if s2.strip() == stem.strip() and e2.lower() in (".jpg", ".jpeg", ".png", ".webp", ".txt") and os.path.isfile(p):
            try:
                out.append(safe_move_file(p, unique(os.path.join(dst_dir, os.path.basename(p)))))
            except OSError:
                pass                                     # 封面挪不动:视频已经挪了
    return out
