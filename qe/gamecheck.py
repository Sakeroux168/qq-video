"""标题像不像别的游戏(用户 2026-10-20:员工把和平精英的视频传成了 PUBG,软件全发了)。

每个游戏号对一个游戏;每个游戏一张关键词表(设置里能改:game_words)。
- 一条:标题里有别的游戏的词、又没有这个号自己游戏的词 →「标题像是《和平精英》的」,不发,人右键「是这个号的,能发」才发;
- 关键词看不出的(「哈哈哈」「G镇六个苟分点」)检查时问 AI(阿里百炼)是哪个游戏,答案记在「游戏判断.json」里,不重复花钱;
- 一个号这天有 3 条以上(或超过一成)像别的游戏 → 可能整批放错了,这个号整批先不发,人点「确认没放错」才放行(界面里管,见 api_tab)。
电竞情报馆(各种游戏的赛事)和动漫号不查。英雄联盟 / 英雄联盟手游 / 云顶之弈 算一家,互相提到不算串。"""
import json
import os
import re
import threading

from .config import data_dir

GAME_WORDS = {
    "PUBG": ["pubg", "绝地求生", "绝地"],
    "和平精英": ["和平精英", "和平", "超体", "牢九门", "和平营地"],
    "CSGO": ["csgo", "cs2", "cs:go", "反恐精英"],
    "英雄联盟": ["英雄联盟", "lol", "撸啊撸"],
    "英雄联盟手游": ["英雄联盟手游", "lolm"],
    "云顶之弈": ["云顶之弈", "云顶", "金铲铲"],
    "三角洲行动": ["三角洲"],
    "暗区突围": ["暗区突围", "暗区"],
    "DNF": ["dnf", "地下城与勇士", "地下城"],
    "QQ飞车": ["qq飞车", "飞车"],
    "光与夜之恋": ["光与夜之恋", "光与夜", "光夜"],
    "王者荣耀": ["王者荣耀", "kpl"],
    "穿越火线": ["穿越火线", "cf手游"],
    "原神": ["原神"],
    "无畏契约": ["无畏契约", "瓦罗兰特", "valorant"],
    "永劫无间": ["永劫无间"],
    "第五人格": ["第五人格"],
    "蛋仔派对": ["蛋仔派对", "蛋仔"],
    "我的世界": ["我的世界", "minecraft"],
}
ACCOUNT_GAME = {"PUBG突围君": "PUBG", "和平精英上分君": "和平精英", "CSGO战神君": "CSGO", "DNF连招档案馆": "DNF",
                "QQ飞车漂移课堂": "QQ飞车", "LOLM峡谷日常": "英雄联盟手游", "LOL玩家聚集地": "英雄联盟",
                "三角洲密探君": "三角洲行动", "云顶上分情报局": "云顶之弈", "暗区突围情报局": "暗区突围",
                "光与夜心动剧场": "光与夜之恋"}
FAMILIES = [{"英雄联盟", "英雄联盟手游", "云顶之弈"}]
_WORDS = dict(GAME_WORDS)
_LOCK = threading.Lock()
_HITS: dict = {}                                  # 标题 → 提到了哪些游戏(列表每次刷新都要算,记着)


def configure(st) -> None:
    """设置里改过的关键词表(game_words:{游戏: [词, …]})盖到默认的上面。"""
    global _WORDS
    w = dict(GAME_WORDS)
    for g, ks in ((st.get("game_words") if hasattr(st, "get") else None) or {}).items():
        ks = [str(k).strip() for k in (ks or []) if str(k).strip()]
        if ks:
            w[str(g)] = ks
    _WORDS = w
    _HITS.clear()


def words() -> dict:
    return dict(_WORDS)


def account_game(nick: str) -> str:
    return ACCOUNT_GAME.get(nick, "")


def same_family(a: str, b: str) -> bool:
    return a == b or any(a in f and b in f for f in FAMILIES)


def hits(title: str) -> list[str]:
    """标题里提到了哪些游戏(按关键词;英文词要单独出现:「lol」不算「lolm」以外的词里的)。"""
    got = _HITS.get(title)
    if got is not None:
        return got
    low = str(title or "").lower()
    out = []
    for g, ks in _WORDS.items():
        for k in ks:
            k = k.lower()
            if re.fullmatch(r"[a-z0-9:]+", k):
                ok = re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", low) is not None
            else:
                ok = k in low
            if ok:
                out.append(g)
                break
    if len(_HITS) > 20000:
        _HITS.clear()
    _HITS[title] = out
    return out


def by_words(nick: str, title: str) -> tuple[str, bool]:
    """(像哪个别的游戏, 关键词看得出来吗)。不是游戏号 / 提到了自己的游戏 → ("", True)。"""
    own = account_game(nick)
    if not own:
        return "", True
    hs = hits(title)
    if not hs:
        return "", False
    if any(same_family(own, h) for h in hs):
        return "", True
    return hs[0], True


class Store:
    """AI 判断过的标题(按标题记,换号也能用)、人点过「是这个号的」(号 + 标题)、人点过「这个号这天确认没放错」(号 + 日期)。"""

    def __init__(self, path=None):
        self.path = str(path or (data_dir() / "游戏判断.json"))
        try:
            with open(self.path, encoding="utf-8") as f:
                self.d = json.load(f)
        except (OSError, ValueError):
            self.d = {}
        for k in ("ai", "ok", "batch_ok"):
            self.d.setdefault(k, {})

    @staticmethod
    def tkey(title: str) -> str:
        from .folders import norm_name
        return norm_name(title) or str(title)

    def ai(self, title: str):
        return self.d["ai"].get(self.tkey(title))

    def ok(self, nick: str, title: str) -> bool:
        return bool(self.d["ok"].get(f"{nick}|{self.tkey(title)}"))

    def batch_ok(self, nick: str, day: str) -> bool:
        return bool(self.d["batch_ok"].get(f"{nick}|{day}"))

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def set_ai(self, got: dict):
        with _LOCK:
            for t, g in got.items():
                self.d["ai"][self.tkey(t)] = g
            self._save()

    def set_ok(self, nick: str, title: str, on: bool = True):
        with _LOCK:
            k = f"{nick}|{self.tkey(title)}"
            if on:
                self.d["ok"][k] = True
            else:
                self.d["ok"].pop(k, None)
            self._save()

    def set_batch_ok(self, nick: str, day: str, on: bool = True):
        with _LOCK:
            k = f"{nick}|{day}"
            if on:
                self.d["batch_ok"][k] = True
            else:
                self.d["batch_ok"].pop(k, None)
            self._save()


_STORE = None


def store() -> Store:
    global _STORE
    d = os.environ.get("QE_DATA_DIR", "").strip()            # 不每次都 data_dir()(它会建文件夹,列表刷新时调用很多次)
    if _STORE is None or _STORE._env != d:
        _STORE = Store()
        _STORE._env = d
    return _STORE


def alien(nick: str, title: str) -> str:
    """这条标题像哪个别的游戏(没有 / 人确认过是这个号的 = "")。关键词看得出来按关键词;看不出来看 AI 记下的答案。"""
    own = account_game(nick)
    if not own:
        return ""
    s = store()
    if s.ok(nick, title):
        return ""
    g, known = by_words(nick, title)
    if known:
        return g
    a = s.ai(title) or ""
    return a if a and a in _WORDS and not same_family(own, a) else ""


def need_ai(nick: str, title: str) -> bool:
    """要不要问 AI:游戏号、关键词看不出来、还没问过。"""
    return bool(account_game(nick)) and not by_words(nick, title)[1] and store().ai(title) is None


def ask_ai(own: str, titles: list[str], key: str, model: str = "qwen-plus",
           base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", timeout: int = 60) -> dict:
    """问 AI 这些标题各是哪个游戏。返回 {标题: 游戏名};看不出来的是 ""。出错抛 RuntimeError。"""
    import requests
    if not key:
        raise RuntimeError("要用 AI 判断游戏,先在「设置」里填阿里百炼 Key")
    names = list(_WORDS)
    lines = "\n".join(f"{k + 1}. {t}" for k, t in enumerate(titles))
    prompt = (f"下面这些短视频标题,是要发到一个《{own}》游戏号上的。请判断每条标题讲的是哪个游戏。\n"
              f"只能从这些里选:{'、'.join(names)};标题里看不出是哪个游戏(比如只是「哈哈哈」)就写「看不出」。\n"
              "注意:很多游戏都有「海岛」「吃鸡」「决赛圈」这种说法;PUBG 和和平精英的枪、地图、道具大多一样(M416、AWM、三级头、"
              "G港、P城、海岛、雨林),光凭这些分不出是哪个,就写「看不出」。拿不准就写「看不出」,别乱猜。\n"
              '只回一个 JSON 数组,每项 {"i": 序号, "game": "游戏名或看不出"},不要别的字。\n\n' + lines)
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 1200}
    if "dashscope" in base_url:
        body["enable_thinking"] = False
    r = requests.post(base_url.rstrip("/") + "/chat/completions", json=body,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=timeout)
    try:
        raw = r.json()["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"AI 没回话:{r.status_code} {r.text[:120]}")
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        arr = json.loads(m.group(0)) if m else []
    except ValueError:
        arr = []
    out = {}
    for x in arr if isinstance(arr, list) else []:
        try:
            k = int(x.get("i")) - 1
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= k < len(titles):
            g = str(x.get("game") or "").strip()
            out[titles[k]] = g if g in names else ""
    if not out:
        raise RuntimeError("AI 回的读不出来,下次检查再试")
    return out
