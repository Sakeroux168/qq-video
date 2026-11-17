"""AI 报错翻成大白话(用户 2026-11-09:欠费了软件只写「AI 没回话(KeyError)」,看不出来)。

平台的错:兼容接口是 {"error": {"code": "Arrearage", ...}},原生接口是 {"code": "Arrearage", ...}。
who = 是哪边的错(阿里百炼 / 你自己的模型,qe/aiconf.py)。
欠费 / Key 不对 / 没开通 这几种再问也没用:hard() 认出来,后台检查就别一条一条接着问了。
"""


def _m(who: str) -> dict:
    return {"arrears": f"{who}欠费了(平台说账户欠费),充值以后再用",
            "badkey": f"{who} Key 不对(去「设置」里重填)",
            "noperm": f"{who}说这个 Key 用不了这个模型(看看开通了没有、模型名对不对)",
            "busy": f"{who}说问得太频繁 / 额度用满了,等一会儿再试",
            "blocked": f"{who}把这次的内容拦了(内容审核没过)"}


ARREARS, BADKEY, NOPERM, BUSY, BLOCKED = (_m("阿里百炼")[k] for k in ("arrears", "badkey", "noperm", "busy", "blocked"))
_HARD = ("欠费了(平台说账户欠费)", "Key 不对(去「设置」里重填)", "用不了这个模型")


def _code(r) -> str:
    try:
        d = r.json()
    except Exception:
        return ""
    if not isinstance(d, dict):
        return ""
    e = d.get("error")
    if isinstance(e, dict):
        return str(e.get("code") or e.get("type") or "")
    return str(d.get("code") or "")


def why(r, who: str = "阿里百炼") -> str:
    """平台回了错:翻成一句话;认不出来给 ""(调用的地方照旧写自己的)。"""
    code = _code(r).lower()
    status = getattr(r, "status_code", 0)
    m = _m(who)
    if "arrearage" in code or "overdue" in code:
        return m["arrears"]
    if "invalidapikey" in code or "invalid_api_key" in code or code == "401" or status == 401:
        return m["badkey"]
    if "accessdenied" in code or "model_not_found" in code or status == 403:
        return m["noperm"]
    if "throttling" in code or "ratelimit" in code or "quota" in code or status == 429:
        return m["busy"]
    if "datainspection" in code:
        return m["blocked"]
    return ""


def hard(msg) -> bool:
    """再问也没用的(欠费 / Key 不对 / 没开通):后台检查碰到一次就停。"""
    m = str(msg)
    return any(x in m for x in _HARD)
