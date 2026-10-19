"""标题清理(用户 2026-10-18):
1. 「@某某 / @某平台」那段删掉再发(不是不发);
2. 莫名其妙的一长串乱码(数字、英文、符号混在一起,比如「今天三角洲打大坝#443241gfsdfq123@!#!%$#fa」)删掉;
3. 标题里有广告词 → 视频里八成也有广告,要人工剪:标出来不让发,人剪好了右键「剪好了」才能发(记在 标题广告处理过.json)。
正常的话题(#英雄联盟、#LOL、#S14)、正常的英文数字(iPhone16、AK-12)不动。
"""
import json
import os
import re
import threading

from .config import data_dir

# 一段连着的英文 / 数字 / 符号(可以带开头的 #),没有中文
_RUN = re.compile(r"[#＃]?[\x21-\x7e]{6,}")
_SYM = re.compile(r"[^A-Za-z0-9\-_.#]")
# @ 后面要真有字;@ 前面紧挨着英文数字的(邮箱 a@b.com)不算
_AT = re.compile(r"(?<![A-Za-z0-9])[@＠]\s*[^\s@＠#＃，,。！!？?、；;：:）)】」]+")

# 标题里出现就当视频里有广告(比口播判断严:标题里「评论区」「关注我」很常见,不算)
from .ads import STRONG as _STRONG               # noqa: E402
TITLE_AD_WORDS = sorted(_STRONG | {"淘宝", "拼多多", "京东", "优惠", "折扣", "私信领", "领取"}, key=len, reverse=True)


def _is_junk(s: str) -> bool:
    body = s.lstrip("#＃")
    if len(body) < 6:
        return False
    d = sum(c.isdigit() for c in body)
    a = sum(c.isalpha() for c in body)
    sym = len(_SYM.findall(body))
    return sym >= 3 or (d >= 4 and a >= 4 and len(body) >= 10)


def junk_runs(title: str) -> list[str]:
    return [m.group(0) for m in _RUN.finditer(str(title or "")) if _is_junk(m.group(0))]


def at_runs(title: str) -> list[str]:
    return [m.group(0).strip() for m in _AT.finditer(str(title or ""))]


def ad_words(title: str) -> list[str]:
    t, out = str(title or ""), []
    for w in TITLE_AD_WORDS:
        if w in t and not any(w in x for x in out):
            out.append(w)
    return out


def clean(title: str) -> str | None:
    """删掉乱码尾巴和 @ 那段;没东西可删 / 删完剩不下字 → None。删掉的部分里有广告词也返回 None(留着给人看)。"""
    t = str(title or "")
    removed = junk_runs(t)
    for r in removed:
        t = t.replace(r, " ")
    ats = at_runs(t)
    for r in ats:
        t = t.replace(r, " ")
    removed += ats
    if not removed or any(ad_words(r) for r in removed):
        return None
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([#＃])", r" \1", t).strip(" -_|·,，")
    t = re.sub(r"[#＃]+\s*$", "", t).strip()
    if len(re.sub(r"[#＃\s]", "", t)) < 2 or t == str(title or "").strip():
        return None
    return t


def dirty(title: str) -> list[str]:
    """标题里要删的:乱码、@ 段(给界面看)。"""
    return junk_runs(title) + at_runs(title)


# ---------------- 标题广告词:人剪好了 / 不是广告 ----------------
_LOCK = threading.RLock()


class AdOk:
    """人在列表里点了「剪好了 / 不是广告」的:号 + 标题(去空格标点)。视频剪过文件会变,所以不按文件认。"""

    def __init__(self, path=None):
        self.path = str(path or (data_dir() / "标题广告处理过.json"))
        try:
            with open(self.path, encoding="utf-8") as f:
                self.d = json.load(f)
        except (OSError, ValueError):
            self.d = {}

    @staticmethod
    def key(account: str, title: str) -> str:
        from .folders import norm_name
        return f"{account}|{norm_name(title) or title}"

    def ok(self, account: str, title: str) -> bool:
        return bool(self.d.get(self.key(account, title)))

    def set(self, account: str, title: str, on: bool = True):
        with _LOCK:
            k = self.key(account, title)
            if on:
                self.d[k] = True
            else:
                self.d.pop(k, None)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)


_STORE = None


def store() -> AdOk:
    global _STORE
    if _STORE is None or _STORE.path != str(data_dir() / "标题广告处理过.json"):
        _STORE = AdOk()
    return _STORE


def ad_problem(account: str, title: str) -> str:
    """标题有广告词、人还没说剪好了 → 一句话;否则 ""。"""
    ws = ad_words(title)
    if not ws or store().ok(account, title):
        return ""
    return f"标题有广告词「{'、'.join(ws[:2])}」:视频里八成也有广告,要人工剪(剪好了右键「剪好了」)"
