"""账号管理(用户 2026-11-03:新增 6 个号 —— 4 个教育、2 个游戏,又要加 4 个影视;「做一个新增账号并分组的功能」)。

一个号的东西原来散在三处,这里一起改,免得漏:
- 每天规定几条 + 分组:设置里的 daily_plan(游戏 / 教育 / 动漫 / 影视 一组一组);
- 接口发的号(游戏 / 动漫):接口账号.json(钥匙另外「登录取钥匙」扫码取,没取到钥匙的不发);
- 罐头发的号(教育 / 影视):设置里的 accounts —— 教育号 = 日期文件夹下面的缩写,影视号 = 自己的文件夹(下面是日期)。
"""
import copy

from . import apiacc
from . import plan as P

CATS = ("游戏", "动漫", "教育", "影视")
# 游戏 / 动漫号默认的视频分类(接口要):游戏 = 网络游戏,动漫 = 动漫周边
DEFAULT_CATEGORY = {"游戏": 1604, "动漫": 401}


def czgt(cat: str) -> bool:
    """这个品类在创作罐头里发(教育 / 影视)。"""
    return cat in P.CZGT_CATS


def rows(st) -> list[dict]:
    """表里一行一个号:{nick, cat, quota, folder, key}。key:接口号有没有钥匙(罐头号 None)。"""
    api = {a["nick"]: a for a in apiacc.load()}
    edu = {a["name"]: a for a in st.get("accounts") or [] if a.get("name")}
    out, seen = [], set()
    for g in P.plan(st):
        cat = g.get("cat") or ""
        for nick, q in (g.get("accounts") or {}).items():
            if nick in seen:
                continue
            seen.add(nick)
            if czgt(cat):
                a = edu.get(nick) or {}
                folder = a.get("dir") or "、".join(a.get("aliases") or [])
                key = None
            else:
                a = api.get(nick) or {}
                folder = a.get("source_name") or ""
                key = bool(a.get("client_id") and a.get("secret"))
            out.append({"nick": nick, "cat": cat, "quota": int(q or 0), "folder": folder, "key": key})
    return out


def _plan_copy(st) -> list[dict]:
    p = copy.deepcopy(P.plan(st))
    for g in p:
        g.pop("total", None)                         # 品类合计跟着各号加起来算
    return p


def _group(p: list[dict], cat: str) -> dict:
    for g in p:
        if g.get("cat") == cat:
            return g
    g = {"cat": cat, "label": f"{cat}总发布量", "accounts": {}}
    p.append(g)
    return g


def add(st, nick: str, cat: str, quota: int, folder: str = "", category: int | None = None) -> None:
    """新增一个号。folder:游戏 / 动漫 = 游戏名(素材文件夹「游戏名--号名」、发完按它分子文件夹);
    教育 = 日期文件夹下面的缩写(几个用顿号隔开);影视 = 这个号自己的文件夹(下面是日期)。出错抛 ValueError。"""
    nick = (nick or "").strip()
    if not nick:
        raise ValueError("号名没填")
    if cat not in CATS:
        raise ValueError(f"分组不对:{cat}")
    if any(r["nick"] == nick for r in rows(st)) or apiacc.find(nick) or nick in st.account_names():
        raise ValueError(f"「{nick}」已经有了")
    folder = (folder or "").strip()
    if cat == "影视" and not folder:
        raise ValueError("影视号要选它的素材文件夹(下面是 11.3 这种日期文件夹的那个)")
    p = _plan_copy(st)
    _group(p, cat)["accounts"][nick] = max(0, int(quota or 0))
    if czgt(cat):
        accs = list(st.get("accounts") or [])
        if cat == "影视":
            accs.append({"name": nick, "aliases": [], "dir": folder})
        else:
            al = [x.strip() for x in folder.replace(",", "、").replace("，", "、").split("、") if x.strip()]
            accs.append({"name": nick, "aliases": al})
        st["accounts"] = accs
    else:
        accs = apiacc.load()
        accs.append({"nick": nick, "source_name": folder, "source_id": "", "client_id": "", "secret": "",
                     "category": int(category or DEFAULT_CATEGORY[cat]), "enabled": True})
        apiacc.save(accs)
    st["daily_plan"] = p
    st.save()


def set_cat(st, nick: str, cat: str) -> None:
    """改分组。游戏 ↔ 动漫、教育 ↔ 影视 能直接改;接口发的和罐头发的不能互换(发法不一样,要去掉再新增)。"""
    if cat not in CATS:
        raise ValueError(f"分组不对:{cat}")
    p = _plan_copy(st)
    old = next((g for g in p if nick in (g.get("accounts") or {})), None)
    if old is None:
        raise ValueError(f"没有「{nick}」这个号")
    if old.get("cat") == cat:
        return
    if czgt(old.get("cat") or "") != czgt(cat):
        raise ValueError(f"「{nick}」是{'罐头' if czgt(old.get('cat') or '') else '接口'}发的,不能改成{cat}(发法不一样)。"
                         "真要改:先去掉这个号,再按新的分组新增")
    if cat == "影视" and not any(a.get("name") == nick and a.get("dir") for a in st.get("accounts") or []):
        raise ValueError("教育号的文件夹是「日期\\缩写」放法,影视号是「号文件夹\\日期」放法,不能直接改 —— 去掉再按影视新增")
    if old.get("cat") == "影视":
        raise ValueError("影视号的文件夹放法和教育号不一样,不能直接改成教育 —— 去掉再按教育新增")
    q = old["accounts"].pop(nick)
    _group(p, cat)["accounts"][nick] = q
    st["daily_plan"] = p
    st.save()


def remove(st, nick: str) -> None:
    """软件里不再管这个号:从每天规定、分组、罐头号名单里去掉;接口号的钥匙也删掉(以后要再加就重新扫码)。
    企鹅号平台上的东西、素材文件夹都不动。"""
    p = _plan_copy(st)
    for g in p:
        (g.get("accounts") or {}).pop(nick, None)
    st["daily_plan"] = p
    st["accounts"] = [a for a in st.get("accounts") or [] if a.get("name") != nick]
    accs = apiacc.load()
    if any(a.get("nick") == nick for a in accs):
        apiacc.save([a for a in accs if a.get("nick") != nick])
    st.save()
