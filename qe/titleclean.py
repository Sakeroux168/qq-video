"""标题清理(用户 2026-10-18 / 2026-11-17):
1. 「@某某 / @某平台」那段删掉再发(不是不发);
2. 莫名其妙的一长串乱码(数字、英文、符号混在一起,比如「今天三角洲打大坝#443241gfsdfq123@!#!%$#fa」)、
   转义残片(u003eu003c / u003c / u200b / &nbsp;)、换行丢失留下的孤立 n 删掉;
3. 括号 / 结尾里的联系人、残留署名标签((yc老师：) / (yc老师 ) / (wx:xxx) / (文案来源：) / yc： / 原创：)删掉;
4. 标题里有广告词 → 视频里八成也有广告,要人工剪:标出来不让发,人剪好了右键「剪好了」才能发(记在 标题广告处理过.json)。
正常的话题(#英雄联盟、#LOL、#S14)、正常的英文数字(iPhone16、AK-12)、「第n次」「n卡」「（陆沉免答）」「【沧元图逐帧解析：】」不动。
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
# 网页 / JSON 转义丢了反斜杠的残片(u003eu003c / u003c / u200b / &nbsp;)
_UESC = re.compile(r"(?<![A-Za-z0-9])(?:\\?u[0-9a-fA-F]{4})+(?![A-Za-z0-9])")
_HENT = re.compile(r"&(?:nbsp|amp|lt|gt|quot|apos|#\d{1,5}|#x[0-9a-fA-F]{1,5});", re.I)

# 联系人 / 残留署名标签
_CONTACT_KW = (r"(?:联系(?:方式|人|我|我们)?|咨询|客服|商务(?:合作)?|加微|加[vV]|\+[vV]|"
               r"微信(?:号)?|[vV]信|威信|[vwVW][xX]|QQ|qq|Q群|qq群|企鹅号?|扣扣|粉丝群|交流群|社群|公众号|邮箱|电话|手机)")
_CONTACT_COLON_KW = r"(?:合作|投稿|约稿)"
_ATTR_KW = r"(?:(?:文案|思路|图|视频|素材)?来源|出处|灵感|原创(?:借鉴)?|作者|授权|搬运|剪辑|摄影|后期|配音|cr|CR)"
_BRACKET = re.compile(r"([（(\[【])([^（）()\[\]【】]{1,45})([）)\]】])")
_UNCLOSED_CONTACT = re.compile(
    rf"[（(\[][^）)\]】#＃]{{0,30}}(?:老师|(?:文案|思路|图|视频|素材)?来源|出处|灵感|原创|作者|{_CONTACT_KW}|[A-Za-z]{{1,6}})"
    r"\s*[:：][^）)\]】#＃]*?(?=[#＃]|$)"
)
_BARE_CONTACT = re.compile(
    r"(?<![A-Za-z0-9\u4e00-\u9fff])(?:"
    r"(?:联系方式|联系人|联系我|客服|微信号?|威信|[vV]信|[vV][xX]|[wW][xX]|QQ|qq|Q群|qq群|企鹅号?|扣扣|[+＋][vV])\s*[:：]\s*[A-Za-z0-9_\-.@+]*|"
    r"(?:联系|合作|咨询|商务|投稿|约稿)\s*[:：]\s*(?:[A-Za-z0-9_\-.@+]+|(?=[#＃\s]|$)))"
)
_BARE_ATTR_EMPTY = re.compile(
    rf"(?:(?<![A-Za-z0-9\u4e00-\u9fff])|(?<=[\u4e00-\u9fff]n))"
    rf"(?:n+(?={_ATTR_KW}|[A-Za-z0-9_.\-]{{1,8}}老师))?(?:{_ATTR_KW}|[A-Za-z0-9_.\-]{{1,8}}老师|[A-Za-z]{{1,5}})\s*[:：]"
    r"(?=\s+(?:[^0-9]|$)|[#＃]|$)"
)

# 换行 \n 丢了反斜杠留下的孤立 n(避开「第n次 / 第n个 / n卡 / n个 / 英文单词」)
_ZH_Q = r"次个遍章回节季期天日周月年时分秒刻倍种样类多"
_ZH_Q_MID = _ZH_Q + r"小款项条根张片块把支辆架台部篇首句段行字号名位员家户套份场局盘战杀排连线星级阶步点选合卡版代式型重维向站几"
_N_TRAIL = re.compile(r"(?<=[\u4e00-\u9fff\"”’'。！？，、；：~～…）】」』》!?.\-])(?<!第)(?:\s*n+)+(?=\s*(?:$|[#＃]))")
_N_AFTER_PUNCT = re.compile(rf"(?<=[\"”’。！？，、；：~～…）】」』》!?])(?:\s*n+)+(?![A-Za-z0-9{_ZH_Q}])")
_N_SPACED = re.compile(rf"(?<=[\u4e00-\u9fff\"”’。！？，、；：~～…）】」』》!?])(?<!第)(?:\s+n+)+(?=\s+[^\sA-Za-z0-9{_ZH_Q}])")
_N_BEFORE_PUNCT = re.compile(r"(?<=[\u4e00-\u9fff\"”’。！？~～…）】」』》])(?<!第)n+(?=[，。！？、；：~～…）】」』》])")
_N_BETWEEN_ZH = re.compile(rf"(?<=[\u4e00-\u9fff])(?<![第这那每好])n+(?=[\u4e00-\u9fff\"“‘（(【「])(?![{_ZH_Q_MID}])")

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


def _is_contact_bracket(open_b: str, inner: str) -> bool:
    s = inner.strip()
    if not s:
        return True
    if re.search(rf"{_CONTACT_KW}\s*(?:[:：]|$|[A-Za-z0-9_@+])", s):
        return True
    if re.search(rf"{_CONTACT_COLON_KW}\s*[:：]", s):
        return True
    if re.search(r"老师\s*[:：]", s) or re.search(r"(?:联系|找|咨询|加|私信).*?老师", s):
        return True
    if re.match(r"^[A-Za-z0-9_.\-]{1,12}[\u4e00-\u9fff]{0,8}老师$", s):
        return True
    if re.search(r"[:：]\s*$", s):
        if re.search(rf"(?:老师|{_ATTR_KW}|{_CONTACT_KW}|{_CONTACT_COLON_KW})\s*[:：]\s*$", s):
            return True
        if open_b != "【" and re.match(r"^[A-Za-z0-9_.\-]{1,10}\s*[:：]\s*$", s):
            return True
    return False


def junk_runs(title: str) -> list[str]:
    return [m.group(0) for m in _RUN.finditer(str(title or "")) if _is_junk(m.group(0))]


def esc_runs(title: str) -> list[str]:
    """u003eu003c / u003c / &nbsp; 这类转义残片。"""
    s = str(title or "")
    out = [m.group(0) for m in _UESC.finditer(s) if any(c.isdigit() for c in m.group(0))]
    out += [m.group(0) for m in _HENT.finditer(s)]
    return out


# 剪辑师写在标题里的备注(用户 2026-11-21:「(1分44s；2分14)【三角洲行动】…」「(广告)10人口混战…」「(1min06s处脏话)贪吃的老叔子…」)。
# 只认两种,别的圆括号(「（暴力出弯）保姆级教学」「（3分钟学会）」「（22660分）」)是正常标题,不动:
#   ① 括号里只有时间点(1分44s；2分14 / 1:06 / 30秒),任何位置;
#   ② 标题开头的括号,里面有「广告 / 脏话 …」,而且(有时间点 或 去掉这个词只剩 ≤3 个字:「(广告)」「(有广告)」「(1min06s处脏话)」)
_PAREN = re.compile(r"([（(])([^（）()]{1,40})([）)])")
_REMARK_KW = ("广告", "脏话", "粗口", "敏感", "违规", "违禁")
_REMARK_TIME = re.compile(r"\d+\s*分\s*\d|\d+\s*(?:秒|min|MIN|Min|[sS](?![A-Za-z]))|\d+[:：]\d")
_REMARK_TIME_ONLY = re.compile(r"(?:\d+\s*(?:分|秒|min|MIN|Min|[smSM:：'′])?\s*[;；,，、/\-~～到至和与及]*\s*)+")


def _is_remark(lead: bool, inner: str) -> bool:
    s = inner.strip()
    if not s:
        return False
    if _REMARK_TIME.search(s) and _REMARK_TIME_ONLY.fullmatch(s):
        return True
    if lead:
        hit = next((k for k in _REMARK_KW if k in s), "")
        if hit:
            rest = re.sub(r"[\s,，;；、:：]", "", s.replace(hit, ""))
            return bool(_REMARK_TIME.search(s)) or len(rest) <= 3
    return False


def remark_runs(title: str) -> list[str]:
    """标题里剪辑师写的备注括号(时间点 / 开头的「广告」「脏话」)。"""
    t = str(title or "")
    lead_at = len(t) - len(t.lstrip())
    return [m.group(0) for m in _PAREN.finditer(t) if _is_remark(m.start() == lead_at, m.group(2))]


def contact_runs(title: str) -> list[str]:
    """括号或结尾里的联系人、老师署名残片、空署名冒号、剪辑备注。"""
    t = str(title or "")
    out = [m.group(0) for m in _BRACKET.finditer(t) if _is_contact_bracket(m.group(1), m.group(2))]
    out += [x for x in remark_runs(t) if x not in out]
    left = t
    for x in out:
        left = left.replace(x, " ")
    for pat in (_UNCLOSED_CONTACT, _BARE_CONTACT, _BARE_ATTR_EMPTY):
        for m in pat.finditer(left):
            s = m.group(0).strip()
            if s:
                out.append(s)
    return out


def n_runs(title: str) -> list[str]:
    """换行 \\n 丢了反斜杠留下的孤立 n。"""
    t = str(title or "")
    out = []
    for pat in (_N_TRAIL, _N_SPACED, _N_AFTER_PUNCT, _N_BEFORE_PUNCT, _N_BETWEEN_ZH):
        for m in pat.finditer(t):
            s = m.group(0).strip() or "n"
            if s not in out:
                out.append(s)
    return out


def at_runs(title: str) -> list[str]:
    return [m.group(0).strip() for m in _AT.finditer(str(title or ""))]


def ad_words(title: str) -> list[str]:
    t, out = str(title or ""), []
    for w in TITLE_AD_WORDS:
        if w in t and not any(w in x for x in out):
            out.append(w)
    return out


def _strip_n(t: str) -> tuple[str, list[str]]:
    """去掉标题里孤立的换行残片 n,返回 (改后的, 删掉的片段)。"""
    removed = []
    for _ in range(3):
        t0 = t
        for pat, rep in ((_N_TRAIL, ""), (_N_SPACED, " "),
                         (_N_AFTER_PUNCT, lambda m: " " if m.group(0)[0].isspace() else ""),
                         (_N_BEFORE_PUNCT, ""), (_N_BETWEEN_ZH, "")):
            for m in pat.finditer(t):
                removed.append(m.group(0).strip() or "n")
            t = pat.sub(rep, t)
        if t == t0:
            break
    return t, removed


def clean(title: str) -> str | None:
    """删掉乱码尾巴 / @ / 转义残片 / 联系人署名 / 孤立 n;没东西可删或删掉部分含广告词 → None。"""
    t = str(title or "")
    removed = []
    for fn in (contact_runs, at_runs, esc_runs, junk_runs):
        hits = fn(t)
        for r in hits:
            if r in t:
                t = t.replace(r, " ")
                removed.append(r)
    t, ns = _strip_n(t)
    removed += ns
    # _strip_n 清掉前面贴着的 n 之后再扫一遍裸联系人/空署名
    for pat in (_BARE_CONTACT, _BARE_ATTR_EMPTY):
        for m in list(pat.finditer(t)):
            r = m.group(0)
            t = t.replace(r, " ", 1)
            removed.append(r.strip())
    t, ns2 = _strip_n(t)
    removed += ns2
    if not removed or any(ad_words(r) for r in removed):
        return None
    t = re.sub(r"[（(\[【]\s*[）)\]】]", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([#＃])", r" \1", t).strip(" -_|·,，")
    t = re.sub(r"[#＃]+\s*$", "", t).strip()
    if len(re.sub(r"[#＃\s]", "", t)) < 2 or t == str(title or "").strip():
        return None
    return t


def dirty(title: str) -> list[str]:
    """标题里要删的(去重按顺序,给界面看)。"""
    t = str(title or "")
    seen, out = set(), []
    for fn in (contact_runs, at_runs, esc_runs, junk_runs, n_runs):
        for x in fn(t):
            k = x.strip()
            if k and k not in seen:
                seen.add(k)
                out.append(k)
    return out


# ---------------- 标题广告词:人剪好了 / 不是广告 ----------------
_LOCK = threading.RLock()


class AdOk:
    """人在列表里点了「剪好了 / 不是广告」的:号 + 标题(去空格标点)。视频剪过文件会变,所以不按文件认。"""

    def __init__(self, path=None):
        self.path = str(path or (data_dir() / "标题广告处理过.json"))
        fn = os.path.basename(self.path)
        self._kind = "titledate" if "日期" in fn else ("titleclean" if "广告" in fn else "")
        self.reload()

    def reload(self):
        with _LOCK:
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
        with _LOCK:
            return bool(self.d.get(self.key(account, title)))

    def set(self, account: str, title: str, on: bool = True):
        from . import lansync
        c = None if (not self._kind or lansync.is_reloading()) else lansync.active_client()
        if c is not None:
            c.store_op(self._kind, "set", account=account, title=title, on=on)
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
            if self._kind and c is None:
                lansync.bump(self._kind)


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
