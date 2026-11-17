"""每条视频「检查」那一格 + 顶上的进度(用户 2026-11-07:我要怎么知道他到底有没有过这道工序?)。

以前只有查出问题才显示,查过没问题 / 还没查 / 没查成都是空白,分不清。
这里只把结果翻成字,不碰界面,两个发布页共用。人看的字:清晰 ✓  字幕 ✓  结尾 ✓ / 查中 / 没查成 / 不用查。
"""
OK, BAD, PASSED, FIXED, BUSY, TODO, FAIL, OFF, NOKEY, NA = "ok", "bad", "passed", "fixed", "busy", "todo", "fail", "off", "nokey", "na"
DONE = (OK, BAD, PASSED, FIXED)
LEFT = (BUSY, TODO, FAIL)                            # 这些算「没查完」(发布确认框提醒,不拦)

_SHARP = {OK: "清晰 ✓", BAD: "疑似模糊", PASSED: "清晰 放行", FIXED: "清晰 ✓", BUSY: "清晰 查中", TODO: "清晰 没查",
          FAIL: "清晰 没查成", OFF: "清晰 关了", NOKEY: "清晰 关了", NA: "清晰 不用查"}
_CROP = {OK: "字幕 ✓", BAD: "字幕被裁", PASSED: "字幕 放行", FIXED: "字幕 ✓", BUSY: "字幕 查中", TODO: "字幕 没查",
         FAIL: "字幕 没查成", OFF: "字幕 关了", NOKEY: "字幕 没填Key", NA: "字幕 不用查"}
_OUTRO = {OK: "结尾 ✓", BAD: "结尾求关注", PASSED: "结尾 放行", FIXED: "结尾 已剪", BUSY: "结尾 查中", TODO: "结尾 没查",
          FAIL: "结尾 没查成", OFF: "结尾 关了", NOKEY: "结尾 没填Key", NA: "结尾 不用查"}
_SAME = {BUSY: "查中", TODO: "没查", FAIL: "没查成", OFF: "关了", NA: "不用查"}
_TIP = {OK: "查过了,没问题", BAD: "查过了,有问题", PASSED: "查到过问题,你说没问题", FIXED: "查到过问题,已经剪掉了",
        BUSY: "正在查", TODO: "还没查",
        FAIL: "这次没查成(文件读不出来 / AI 没回话 / 阿里百炼欠费),日志里写了原因,点「重新检查」再查",
        OFF: "设置里关了", NOKEY: "没填阿里百炼 Key,查不了",
        NA: "不用查(已经发了,或者这种号不查这项)"}


def state(res: dict | None, busy: bool = False, err: bool = False, on: bool = True, need: bool = True,
          key: bool = True, sent: bool = False) -> str:
    """一项检查现在是什么情况。res = 记下的结果(没查过 None)。busy 排最前:重新检查时旧结果不算数。"""
    if busy:
        return BUSY
    if res is not None:
        if res.get("blurred"):
            return FIXED
        return (PASSED if res.get("ok") else BAD) if res.get("hits") else OK
    if sent or not need:
        return NA
    if not on:
        return OFF
    if not key:
        return NOKEY
    return FAIL if err else TODO


def pair(v, worker, crop: dict | None, sent: bool, need_crop: bool, sharp_on: bool, crop_on: bool, has_key: bool,
         outro: dict | None = None, outro_on: bool | None = None) -> tuple:
    """(清晰度, 字幕被裁[, 结尾求关注]) 各项的情况。worker = 后台在跑的 SharpWorker(没跑 / 跑完了算没有)。"""
    sharp = getattr(v, "sharp", None)
    run = bool(worker) and worker.isRunning() and v.path in worker.left
    force = run and v.path in worker.force
    res = (state(sharp, busy=force or (run and sharp is None and worker.want_sharp), err=getattr(v, "sharp_err", False),
                 on=sharp_on, sent=sent),
           state(crop, busy=need_crop and (force or (run and crop is None and bool(worker.crop_key))),
                 err=getattr(v, "crop_err", False), on=crop_on, need=need_crop, key=has_key, sent=sent))
    if outro_on is None:
        return res
    return res + (state(outro, busy=force or (run and outro is None and bool(getattr(worker, "outro_key", ""))),
                        err=getattr(v, "outro_err", False), on=outro_on, key=has_key, sent=sent),)


def cell(p: tuple) -> str:
    """表格里那一格。各项一样(或只剩一个词)就写一个词。"""
    if len(p) >= 3:
        s, c, o = p[:3]
        if s == c == o and s in _SAME:
            return _SAME[s]
        return f"{_SHARP[s]}  {_CROP[c]}  {_OUTRO[o]}"
    s, c = p
    if s == c and s in _SAME:
        return _SAME[s]
    return f"{_SHARP[s]}  {_CROP[c]}"


def tip(p: tuple) -> str:
    lines = [f"清晰度:{_TIP[p[0]]}", f"字幕被裁:{_TIP[p[1]]}"]
    if len(p) >= 3:
        lines.append(f"结尾求关注:{_TIP[p[2]]}")
    return "\n".join(lines)


def _part(name: str, states: list[str]) -> str:
    use = [s for s in states if s != NA]
    if not use:
        return ""
    if all(s == OFF for s in use):
        return f"{name}关了"
    if all(s == NOKEY for s in use):
        return f"{name}没填 Key"
    return f"{name} {sum(s in DONE for s in use)}/{len(use)}"


def progress(pairs: list[tuple]) -> str:
    """顶上一行。pairs:这一页没发的。"""
    if not pairs:
        return ""
    flat = [s for p in pairs for s in p]
    parts = [_part("清晰度", [p[0] for p in pairs]), _part("字幕", [p[1] for p in pairs])]
    if any(len(p) >= 3 for p in pairs):
        parts.append(_part("结尾", [p[2] for p in pairs if len(p) >= 3]))
    parts = [x for x in parts if x]
    fail = sum(FAIL in p for p in pairs)
    head = "正在检查" if BUSY in flat else "检查"
    done = not any(s in LEFT for s in flat)
    if done:
        head = "检查查完了"
    bad = found(pairs)
    tail = f"  —— 查到 {bad}" if bad else ("  —— 没查到问题" if done and not fail and any(s in DONE for s in flat) else "")
    return f"{head}:" + " · ".join(parts + ([f"{fail} 条没查成"] if fail else [])) + tail


def found(pairs: list[tuple]) -> str:
    """查到的问题(用户 2026-11-10:「查完了咋不说有没有查到不对的?必须要我点进去看」):「2 条模糊 · 1 条字幕被裁」;没有给 ""。"""
    blur = sum(p[0] == BAD for p in pairs)
    crop = sum(p[1] == BAD for p in pairs)
    outro = sum(len(p) >= 3 and p[2] == BAD for p in pairs)
    return " · ".join(x for x in (f"{blur} 条模糊" if blur else "", f"{crop} 条字幕被裁" if crop else "",
                                  f"{outro} 条结尾求关注" if outro else "") if x)


def group_text(pairs: list[tuple]) -> str:
    """号那一行:这个号没发的查到哪了 + 查到了几条不对的(查完了没问题写「查完了 · 没问题」)。"""
    if not pairs:
        return ""
    left = sum(any(s in LEFT for s in p) for p in pairs)
    fail = sum(FAIL in p for p in pairs)
    bad = found(pairs)
    if fail:
        head = f"{fail} 条没查成"
    elif left:
        head = f"查了 {len(pairs) - left}/{len(pairs)}"
    else:
        head = "查完了"
    return head + (f" · {bad}" if bad else " · 没问题" if not left and not fail else "")


def unchecked_text(pairs: list[tuple]) -> str:
    """发布前确认框提醒一句(不拦)。都查完了给 ""。"""
    n = sum(any(s in LEFT for s in p) for p in pairs)
    if not n:
        return ""
    a = sum(p[0] in LEFT for p in pairs)
    b = sum(p[1] in LEFT for p in pairs)
    c = sum(len(p) >= 3 and p[2] in LEFT for p in pairs)
    what = "、".join(x for x in (f"清晰度 {a} 条" if a else "", f"字幕被裁 {b} 条" if b else "",
                                 f"结尾求关注 {c} 条" if c else "") if x)
    return f"还有 {n} 条没查完({what}),现在发就不查了。"
