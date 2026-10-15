"""话题只留一个 —— 照搬 ainame「只筛话题」(E:\\软件\\ainame-src\\src\\ai\\modes.js 的 splitTopics / joinTopic /
TOPIC_SYSTEM / topicMessages,generate.js 的 parseTopicOrder / cleanTopic),结果和用户在 ainame 里做的一致。

- 只认文件名【结尾】那一串话题;正文一字不动;正文和第一个话题之间原来是什么分隔就照抄。
- 0 个话题:不动。1 个:直接留。2 个以上:AI 按「用户最容易搜索」排,留第一名(只能从原话题里挑)。温度 0。
- 改名:只改主名,扩展名不动;重名加 (2),不覆盖;同文件夹里同名的封面图跟着改;先记台账再改,能撤销。
"""
import json
import os
import re

TOPIC_SYSTEM = """
你是短视频的话题筛选员。

一条视频的标题后面挂着好几个 #话题。你的任务是把这些话题按【用户最容易搜索】
从高到低排好顺序。排第一的那个会被留下，其余的会被删掉。

判断标准，按优先级：
1. 游戏名、电视剧名、电影名、动漫名 / 动画名、综艺名 —— 这一类永远排最前面，
   只要有一个话题是作品名，留下的就必须是作品名。
   同一个作品有好几种叫法时，排最完整、最准确指向这个作品的那个正式名称。
   例：#火影忍者手游 排在 #火影忍者、#火影 前面（视频是手游的话，手游才是用户搜的）；
       #三角洲行动 排在 #三角洲 前面；#和平精英 排在 #和平 前面。
2. 其次是具体的人名、角色名、地名、品牌名、具体玩法或内容名。
3. 平台活动类排最后：XX激励活动、XX创作大赛、XX计划、XX挑战赛、XX嘉年华、
   XX开学季、XX新赛季、真实生活分享计划之类 —— 这些是平台拉流量用的，
   过一阵就没人搜了。

只能给这些话题排序。不许编新话题，不许改话题里的任何一个字。
""".strip()

# 比 ainame 多认两种写法(2026-10-15 电竞情报馆的素材):「# 2026kpl年度总决赛」(# 后面带空格)、全角「＃」。
# 留下的那个统一写成「#话题」(不带空格),平台才认成话题。
# 还有「##话题」(多打了一个 #),和「取胜n#话题」(换行 \n 被弄丢了反斜杠剩个 n;前面是英文字母的 n 不算,免得把单词吃掉)。
# 「# 话题」(# 后面带空格)只在 # 前面不是英文字母 / 数字时才算:「学习C# 教程」「3# 打野」不是话题(2026-10-15 审查)。
# 结尾多出来的孤零零的 #(「标题 #原神#」)不算话题,但算写法不对,tidy 会去掉。
_SPACED = r"(?:(?<![A-Za-z0-9+])|(?<=(?<![A-Za-z])n))[#＃]+\s+"
_TAG = rf"(?:{_SPACED}|[#＃]+)([^#＃\s]+)"
_RUN = re.compile(rf"((?:\s*(?:(?<![A-Za-z])n)?\s*{_TAG.replace('([^#＃', '(?:[^#＃')})+)[\s#＃]*$")


def split_topics(name: str) -> dict:
    """{"body": 正文, "sep": 正文和第一个话题之间的分隔, "tags": [话题(去 #、去重)]}。"""
    s = str(name or "")
    m = _RUN.search(s)
    if not m:
        return {"body": s, "sep": "", "tags": []}
    run = m.group(1)
    seen, tags = set(), []
    for t in re.findall(_TAG, run):
        t = re.sub(r"(?<=[\u4e00-\u9fff])n$", "", t)      # 中文话题后面粘的 n(丢了反斜杠的换行)
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        tags.append(t)
    return {"body": s[:m.start()], "sep": re.match(r"^\s*", run).group(0), "tags": tags}


def join_topic(parts: dict, tag: str) -> str:
    return f"{parts['body']}{parts['sep']}#{tag}"


def tidy(stem: str) -> str | None:
    """话题写法整理(不用 AI,规矩固定):结尾空格去掉、「# 话题」「##话题」「＃话题」→「#话题」、
    话题前粘的 n(丢了反斜杠的换行)去掉、重复的话题去掉。不用改返回 None。
    挂了好几个不同话题的不在这管(那个要 AI 挑),返回 None。"""
    p = split_topics(stem)
    if len(p["tags"]) > 1:
        return None
    out = join_topic(p, p["tags"][0]) if p["tags"] else re.sub(r"(?<![A-Za-z0-9+#＃])[#＃]+$", "", stem.rstrip()).rstrip()
    out = sanitize(out)
    if not out:                                   # 整个标题都是空格 / #:改不了,交给人
        return None
    return None if out == stem else out


def bad_format(stem: str) -> bool:
    """话题写法不对(要严格:用户 2026-10-15「就是得判严格」)= tidy 会改它。"""
    return tidy(stem) is not None


def clean_tag(tag: str) -> str:
    """用户填的话题:去掉 #、空格、文件名里不能用的字。"""
    return sanitize(re.sub(r"[#＃\s]+", "", str(tag or "")))


def with_topic(stem: str, tag: str) -> str | None:
    """批量改话题:结尾的话题全换成这一个(原来没有话题就接在后面)。不用改返回 None。"""
    tag = clean_tag(tag)
    if not tag:
        return None
    p = split_topics(stem)
    out = sanitize(join_topic(p, tag) if p["tags"] else f"{re.sub(r'[\s#＃]+$', '', p['body'])}#{tag}")
    out = tidy(out) or out                        # 产出的再整理一遍写法(审查:「标题 #原神#」会产出「##」)
    return None if out == stem else out


def topic_messages(body: str, tags: list[str]) -> list[dict]:
    lst = "\n".join(f"{i + 1}. #{t}" for i, t in enumerate(tags))
    user = (f"标题正文：{body.strip() or '（无）'}\n\n"
            f"挂着的话题：\n{lst}\n\n"
            f"把这 {len(tags)} 个话题按\"用户最容易搜索\"从高到低排序。\n"
            f"只输出一个 JSON 对象，不要有任何别的文字：\n"
            "{\"理由\":\"排第一的为什么最好搜，一句话\",\"顺序\":[编号, 编号, ...]}")
    return [{"role": "system", "content": TOPIC_SYSTEM}, {"role": "user", "content": user}]


def parse_order(raw: str, n: int) -> list[int]:
    """AI 返回 → 话题编号的顺序(1..n);漏掉的按原顺序补在后面;一个都读不出返回 []。"""
    s = re.sub(r"^```(?:json|JSON)?\s*", "", str(raw or "").strip())
    s = re.sub(r"```\s*$", "", s).strip()
    order = None
    for txt in (s, (re.search(r"\{[\s\S]*\}", s) or [None])[0]):
        if not txt:
            continue
        try:
            j = json.loads(txt)
            arr = j.get("顺序") or j.get("order") or j.get("排序")
            if isinstance(arr, list):
                order = arr
                break
        except (ValueError, AttributeError):
            pass
    if order is None:
        order = re.findall(r"\d+", s)
    out = []
    for x in order:
        try:
            k = int(x)
        except (TypeError, ValueError):
            continue
        if 1 <= k <= n and k not in out:
            out.append(k)
    if not out:
        return []
    return out + [k for k in range(1, n + 1) if k not in out]


def ask_ai(body: str, tags: list[str], key: str, model: str = "qwen-plus",
           base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", timeout: int = 60) -> str:
    """问 AI 留哪个话题,返回那个话题。读不出顺序抛 RuntimeError(可以再试)。"""
    import requests
    if not key:
        raise RuntimeError("要用 AI 挑话题,先在「设置」里填阿里百炼 Key")
    body_json = {"model": model, "messages": topic_messages(body, tags), "temperature": 0, "max_tokens": 400}
    if "dashscope" in base_url:
        body_json["enable_thinking"] = False
    r = requests.post(base_url.rstrip("/") + "/chat/completions", json=body_json,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=timeout)
    try:
        raw = r.json()["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"AI 没回话:{r.status_code} {r.text[:120]}")
    order = parse_order(raw, len(tags))
    if not order:
        raise RuntimeError("AI 回的顺序读不出来,再试一次")
    return tags[order[0] - 1]


def new_name(stem: str, pick=None) -> str | None:
    """这个文件名只留一个话题以后叫什么。不用改返回 None。pick(body, tags) 负责 2 个以上时挑哪个。"""
    p = split_topics(stem)
    tags = p["tags"]
    if len(tags) == 0:
        return None
    if len(tags) == 1:
        out = join_topic(p, tags[0])
    else:
        out = join_topic(p, pick(p["body"], tags))
    out = sanitize(out)
    return None if out == stem else out


def sanitize(name: str) -> str:
    """去掉文件名里不能用的字(和 ainame 一样:<>:\"/\\|?*;emoji 不去,企鹅号标题里能用)。"""
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def _numbered(new_stem: str, k: int) -> str:
    """重名时的新名字:序号插在正文后面、话题前面(「a (2) #x」),话题还在结尾,检查照样认得出(审查:原来是「a #x (2)」)。"""
    p = split_topics(new_stem)
    if not p["tags"]:
        return f"{new_stem} ({k})"
    return f"{p['body'].rstrip()} ({k}){new_stem[len(p['body']):]}"


def rename_with_sidecars(path: str, new_stem: str) -> list[tuple[str, str]]:
    """改视频的主名;同文件夹里同名的封面图 / 文字跟着改。重名加 (2)。返回 [(旧, 新), ...](第一个是视频)。"""
    d, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    target = os.path.join(d, new_stem + ext)
    k = 2
    while os.path.exists(target) and os.path.normcase(target) != os.path.normcase(path):
        target = os.path.join(d, _numbered(new_stem, k) + ext)
        k += 1
    final_stem = os.path.splitext(os.path.basename(target))[0]
    os.rename(path, target)
    moves = [(path, target)]
    for n in os.listdir(d):
        s2, e2 = os.path.splitext(n)
        if s2 == stem and e2.lower() in (".jpg", ".jpeg", ".png", ".webp", ".txt"):
            src, dst = os.path.join(d, n), os.path.join(d, final_stem + e2)
            if not os.path.exists(dst):
                os.rename(src, dst)
                moves.append((src, dst))
    return moves


def rename_logged(path: str, new_stem: str, ledger, at: str) -> list[tuple[str, str]]:
    """改名 + 记台账;台账写不进去就把名字改回去(不留撤销不了的改名)。"""
    moves = rename_with_sidecars(path, new_stem)
    try:
        ledger.add(at, moves)
    except Exception:
        for old, new in reversed(moves):
            try:
                os.rename(new, old)
            except OSError:
                pass
        raise
    return moves


class Ledger:
    """改名台账(能整批撤销)。每一批:{"at", "groups": [[[旧, 新], ...](一条视频和它跟着改的封面), ...]}。
    老格式 {"at", "moves": [...]} 也认(每个改名自成一组)。"""

    def __init__(self, path):
        self.path = str(path)

    def _load(self) -> list:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def _save(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    @staticmethod
    def groups_of(b: dict) -> list:
        return b.get("groups") or [[m] for m in (b.get("moves") or [])]

    @staticmethod
    def label(b: dict | None) -> str:
        """给人看的这批是什么:「10-15 20:01:02 批量改成 #英雄联盟」。批次名是「时间¦做了什么¦编号」(老的只有时间)。"""
        if not b:
            return ""
        parts = str(b.get("at") or "").split("¦")
        return f"{parts[0][5:]} {parts[1]}" if len(parts) >= 2 else parts[0]

    def add(self, at: str, moves: list) -> None:
        data = self._load()
        g = [list(m) for m in moves]
        if data and data[-1].get("at") == at:
            data[-1].setdefault("groups", self.groups_of(data[-1])).append(g)
            data[-1].pop("moves", None)
        else:
            data.append({"at": at, "groups": [g]})
        self._save(data[-50:])

    def last(self) -> dict | None:
        data = self._load()
        return data[-1] if data else None

    def undo_last(self, skip=None) -> tuple[int, int, int]:
        """把最后一批改回去。skip(视频现在的路径) 为真的整组不改(已经发了的:改回去防重发就认不出了)。
        返回 (改回几个文件, 改不回几个:文件不在了 / 原名被占了, 跳过几条视频)。"""
        data = self._load()
        if not data:
            return 0, 0, 0
        b = data.pop()
        ok = bad = skipped = 0
        left = []
        for g in reversed(self.groups_of(b)):
            if not g:
                continue
            if skip and skip(g[0][1]):
                skipped += 1
                continue
            vold, vnew = g[0]
            try:
                if not os.path.exists(vnew) or os.path.exists(vold):
                    raise OSError("文件不在了 / 原名被占了")
                os.rename(vnew, vold)                 # 先改视频;改不回(被占着)就别动它的封面,免得名字对不上
                ok += 1
            except OSError:
                bad += 1
                left.append(g)
                continue
            for old, new in g[1:]:
                try:
                    if os.path.exists(new) and not os.path.exists(old):
                        os.rename(new, old)
                        ok += 1
                    else:
                        bad += 1
                except OSError:
                    bad += 1
        if left:                                      # 改不回的留着,关掉占用的程序后还能再撤一次
            data.append({"at": b.get("at", ""), "groups": list(reversed(left))})
        self._save(data)
        return ok, bad, skipped
