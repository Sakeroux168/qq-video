"""黑封面 + 模糊封面(用户 2026-11-06 查黑封面;2026-11-17 加查模糊封面):
- 发之前:员工放的同名 .jpg 是黑的或太模糊的就不用,换成软件自己从视频里挑的一帧清晰画面(api_tab 发布那里);
- 发之后:读平台上实际用的封面(文章列表的 article_imgurl,只读),黑的、模糊的列出来让人去后台改(接口改不了封面)。

判断标准:
1. 黑封面:亮度超过 40 的像素不到 3%(纯黑、只有一小行字幕都算;有一块正常画面、黑底大字的不算)。
2. 模糊封面:去掉四边黑边后缩到短边 360,切成 6×6 小块算拉普拉斯边缘方差,取 80% 分位 < 25。
   这样就算底下露了半行清楚字幕、但画面主体糊成一团(11-16 实测《新版本水上飞机》p80=6.3),也照样抓得出;正常封面都在 95 以上。
"""
import io
import json
import os
import re
import time

from .config import data_dir

BRIGHT, LIMIT = 40, 0.03
BLUR_LIMIT = 25.0


def _store_path():
    return data_dir() / "黑封面.json"


def is_black_img(im) -> bool:
    """im = 一张 PIL 图。"""
    import numpy as np
    a = np.asarray(im.convert("L").resize((160, 160)))
    return float((a > BRIGHT).mean()) < LIMIT


def block_sharpness(im) -> float:
    """去掉黑边后按 6×6 分块算清晰度(80% 分位):避免单行字幕把整张模糊图的分数拉高。纯色图给 999(不算模糊照片)。"""
    import cv2
    import numpy as np
    from . import sharp
    g = np.asarray(im.convert("L"))
    act = sharp.active(g)
    if act is None:
        return 999.0
    h, w = act.shape
    k = 360 / min(h, w)
    g2 = cv2.resize(act, (max(1, int(w * k)), max(1, int(h * k))),
                    interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
    gh, gw = g2.shape
    bh, bw = max(16, gh // 6), max(16, gw // 6)
    vals = [float(cv2.Laplacian(g2[y:y + bh, x:x + bw], cv2.CV_64F).var())
            for y in range(0, gh - bh + 1, bh) for x in range(0, gw - bw + 1, bw)]
    if not vals:
        return float(cv2.Laplacian(g2, cv2.CV_64F).var())
    return float(np.percentile(vals, 80))


def is_blurry_img(im) -> bool:
    """im = 一张 PIL 图:不是黑封面,但画面主体糊成一团。"""
    if is_black_img(im):
        return False
    return block_sharpness(im) < BLUR_LIMIT


def bad_kind_img(im) -> str:
    """这张封面有什么问题:"黑封面" / "模糊封面" / ""(没问题)。"""
    if is_black_img(im):
        return "黑封面"
    if block_sharpness(im) < BLUR_LIMIT:
        return "模糊封面"
    return ""


def is_black(path: str) -> bool:
    """本地这张图是黑的吗;读不出来算不是(不因为这个换封面)。"""
    from PIL import Image
    try:
        with Image.open(path) as im:
            return is_black_img(im)
    except Exception:
        return False


def is_blurry(path: str) -> bool:
    """本地这张图是不是太模糊;读不出来算不是。"""
    from PIL import Image
    try:
        with Image.open(path) as im:
            return is_blurry_img(im)
    except Exception:
        return False


def _fetch(url: str) -> bytes:
    import requests
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def accounts() -> list[dict]:
    """取过钥匙的号:接口发的 + 只查的(教育 / 影视)。"""
    from . import apiacc
    out = [a for a in apiacc.load() if a.get("client_id") and a.get("secret")]
    have = {a.get("nick") for a in out}
    return out + [a for a in apiacc.qload() if a.get("nick") not in have]


def scan_one(a: dict, start: str, end: str, stopped=None, make_client=None, fetch=None) -> tuple[list[dict], int]:
    """查一个号 start~end(「2026-11-06」)发的:返回 ([黑封面 / 模糊封面], 读不出来的几张)。删掉的不算。"""
    from PIL import Image
    from . import apiacc, omapi, verify
    cl = (make_client or (lambda x: omapi.Client(x["client_id"], apiacc.unseal(x["secret"]))))(a)
    found, bad = [], 0
    for p in verify.platform_between(cl, start, end, stopped=stopped):
        if stopped and stopped():
            break
        if p.get("deleted"):
            continue
        if not p.get("img"):
            bad += 1
            continue
        try:
            with Image.open(io.BytesIO((fetch or _fetch)(p["img"]))) as im:
                kind = bad_kind_img(im)
                if kind:
                    found.append({"nick": a.get("nick") or "", "title": p.get("title") or "", "time": p.get("time") or "",
                                  "url": p.get("url") or "", "aid": p.get("aid") or "", "kind": kind})
        except Exception:
            bad += 1
    return found, bad


def summary_text(items: list[dict]) -> str:
    """「2 条黑封面、5 条模糊封面」;空的给 ""。"""
    if not items:
        return ""
    n_blk = sum(1 for x in items if (x.get("kind") or "黑封面") == "黑封面")
    n_blr = sum(1 for x in items if x.get("kind") == "模糊封面")
    parts = [f"{n_blk} 条黑封面" if n_blk else "", f"{n_blr} 条模糊封面" if n_blr else ""]
    return "、".join(p for p in parts if p) or f"{len(items)} 条问题封面"


def save(day: str, items: list[dict]) -> None:
    p = _store_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"day": day, "items": items}, ensure_ascii=False), "utf-8")
    tmp.replace(p)


def load(day: str) -> list[dict]:
    """这天查到的黑封面(软件重开还在);别的天的不算。"""
    try:
        d = json.loads(_store_path().read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return list(d.get("items") or []) if isinstance(d, dict) and d.get("day") == day else []


# ---------------- 自动从原视频挑清晰封面放到指定文件夹 ----------------
ARTICLE_MANAGE_URL = "https://om.qq.com/main/management/articleManage"


def safe_cover_path(out_dir: str, title: str, aid: str = "") -> str:
    """用视频标题起文件名,去掉 Windows 不认的符号,落成 <目录>\\<标题>.jpg。"""
    stem = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (title or "").strip()).strip(" .")[:80]
    if not stem:
        stem = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (aid or "").strip()) or "封面"
    return os.path.join(out_dir, f"{stem}.jpg")


def find_video(st, rec, nick: str, title: str, aid: str = "") -> str:
    """去发布记录里找这条视频对应的本地 / 归档视频文件,找得到就返回路径。"""
    if rec is None:
        return ""
    from . import redo
    for row in rec.find_for_cover(nick, title, aid):
        loc = redo.locate(st, row)
        if loc and os.path.isfile(loc):
            return loc
    return ""


def export_cover(item: dict, st, rec=None, ffmpeg: str = "", pick_fn=None) -> str:
    """给单条黑封面 / 模糊封面从原视频截一帧清晰图存到设置里的封面文件夹。开着选项才截。"""
    if not st or not st.get("bad_cover_auto", True):
        return ""
    out_dir = str(st.get("bad_cover_dir") or r"E:\图片\企鹅号").strip()
    if not out_dir:
        return ""
    dest = safe_cover_path(out_dir, item.get("title") or "", item.get("aid") or "")
    try:
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            return dest
    except OSError:
        pass
    video = find_video(st, rec, item.get("nick") or "", item.get("title") or "", item.get("aid") or "")
    if not video:
        return ""
    from . import autocover
    tmp = (pick_fn or autocover.pick)(video, ffmpeg=ffmpeg)
    if not tmp or not os.path.isfile(tmp):
        return ""
    os.makedirs(out_dir, exist_ok=True)
    tmp_out = f"{dest}.{os.getpid()}.tmp"
    with open(tmp, "rb") as src, open(tmp_out, "wb") as dst:
        dst.write(src.read())
    os.replace(tmp_out, dest)
    return dest


def export_covers(items: list[dict], st, rec=None, stopped=None, step=None, ffmpeg: str = "", pick_fn=None) -> int:
    """批量给查到的黑 / 模糊封面截清晰图到指定文件夹;返回手里已经有清晰封面的条数。"""
    if not items or not st or not st.get("bad_cover_auto", True):
        return 0
    own_rec = rec is None
    if own_rec:
        from . import records
        rec = records.Records()
    ready = 0
    try:
        for i, it in enumerate(items):
            if stopped and stopped():
                break
            if step:
                step(f"正在从视频挑清晰封面({i + 1} / {len(items)})…")
            try:
                p = export_cover(it, st, rec, ffmpeg=ffmpeg, pick_fn=pick_fn)
            except Exception:
                p = ""
            it["cover_file"] = p
            if p:
                ready += 1
    finally:
        if own_rec and getattr(rec, "conn", None):
            try:
                rec.conn.close()
            except Exception:
                pass
    return ready


# ---------------- 双击去创作罐头「作品管理」里搜出这条视频 ----------------
def _name_match(got: str, want: str) -> int:
    """0=不匹配, 2=完全一样, 1=前面一样(如 游研社 ↔ 游研社M)。"""
    g, w = (got or "").strip(), (want or "").strip()
    if not g or not w:
        return 0
    if g == w:
        return 2
    if g.startswith(w) or w.startswith(g):
        return 1
    return 0


def _find_om_targets(port: int, nick: str, targets_fn, page_cls) -> list[tuple[int, dict, bool]]:
    """找罐头里已经开着的这个号的 om.qq.com/main 页面:返回 [(优先级, target, 是否可见), ...]。"""
    from .cdp import CdpError
    found = []
    for t in targets_fn(port):
        u = t.get("url") or ""
        if "om.qq.com" not in u or "page.om.qq.com" in u or "/userAuth" in u:
            continue
        pg = None
        try:
            pg = page_cls(t, timeout=8)
            who, w, href = pg.ev("[(document.querySelector('[class*=usernameText]')||{}).innerText||'', innerWidth, location.href]") or ["", 0, u]
        except CdpError:
            continue
        finally:
            if pg:
                pg.close()
        m = _name_match(who, nick)
        if not m:
            continue
        score = (m * 100
                 + (20 if "/main/management/articleManage" in (href or u) else 0)
                 + (10 if "/main" in (href or u) and "/creation/video" not in (href or u) else 0)
                 + (2 if w and w > 0 else 0))
        found.append((score, t, bool(w and w > 0)))
    found.sort(key=lambda x: x[0], reverse=True)
    return found


def _home_click_account(home, nick: str, sleep_fn) -> str:
    """在罐头首页点开这个企鹅号(先看已开页签,再看企鹅号卡片;首页搜着别的号时先清空搜索框)。"""
    js_open = r"""((w) => {
        const eq = (a, b) => a === b;
        const st = (a, b) => a.startsWith(b) || b.startsWith(a);
        const tabs = [...document.querySelectorAll('.title-name')];
        for (const fn of [eq, st]) {
            const t = tabs.find(e => fn((e.textContent || '').trim(), w));
            if (t) { (t.closest('.chrome-tab-content-wrapper') || t.parentElement).click(); t.click(); return 'tab'; }
        }
        const cards = [...document.querySelectorAll('div.name-UlOtte')].map(e => {
            const c = e.closest('.account-Q5JloA') || e.parentElement.parentElement;
            const qe = c ? [...c.querySelectorAll('img')].some(i => (i.src || '').includes('%E4%BC%81%E9%B9%85%E5%8F%B7')) : false;
            return {e, name: (e.textContent || '').trim(), qe};
        });
        for (const preferQe of [true, false]) {
            for (const fn of [eq, st]) {
                const hit = cards.find(x => (!preferQe || x.qe) && fn(x.name, w));
                if (hit) { hit.e.click(); return 'ok'; }
            }
        }
        return 'notfound';
    })""" + f"({json.dumps(nick, ensure_ascii=False)})"
    r = home.ev(js_open)
    if r == "notfound":
        box = home.ev("""(() => { const i = document.querySelector("input[placeholder='账号、手机号等']"); if (!i || !i.value) return null;
            const b = i.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()""")
        if box:
            home.click_xy(box[0], box[1])
            home.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
            home.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
            home.key("Backspace", 8)
            home.key("Enter", 13)
            sleep_fn(2.0)
            r = home.ev(js_open)
    return r


def _activate_target_tab(port: int, target_id: str, nick: str, targets_fn, page_cls, sleep_fn) -> dict | None:
    """把已经开着的背景页签点成前台看得见的(可能有重名页签,依次试到目标页签变宽为止)。"""
    from .cdp import CdpError
    home_t = next((t for t in targets_fn(port) if "czgts.cn" in (t.get("url") or "") and t.get("type") == "page"), None)
    if not home_t:
        return None
    home = page_cls(home_t, timeout=8)
    try:
        nj = json.dumps(nick, ensure_ascii=False)
        n_tabs = home.ev("""((w) => [...document.querySelectorAll('.title-name')].filter(e => {
            const t = (e.textContent || '').trim(); return t === w || t.startsWith(w) || w.startsWith(t);
        }).length)""" + f"({nj})") or 0
        for idx in range(int(n_tabs)):
            home.ev("""((w, i) => {
                const hits = [...document.querySelectorAll('.title-name')].filter(e => {
                    const t = (e.textContent || '').trim(); return t === w || t.startsWith(w) || w.startsWith(t);
                });
                const t = hits[i];
                if (t) { (t.closest('.chrome-tab-content-wrapper') || t.parentElement).click(); t.click(); }
            })""" + f"({nj}, {idx})")
            sleep_fn(0.4)
            t = next((x for x in targets_fn(port) if x.get("id") == target_id), None)
            if not t:
                continue
            pg = None
            try:
                pg = page_cls(t, timeout=6)
                if (pg.ev("innerWidth") or 0) > 0:
                    return t
            except CdpError:
                pass
            finally:
                if pg:
                    pg.close()
    finally:
        home.close()
    return None


def search_keyword(title: str) -> str:
    """搜视频标题时去掉末尾 #话题(用户:话题不用搜)。"""
    from . import topic
    s = (title or "").strip()
    body = (topic.split_topics(s)["body"] or "").strip()
    return body or s


def _filter_article_date(pg, day: str, sleep_fn) -> None:
    """在作品管理页筛选「开始日期 — 结束日期」为 day (YYYY-MM-DD)。找不到控件就跳过不影响搜标题。"""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", (day or "").strip())
    if not m:
        return
    yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    box = pg.ev("""(() => {
        const d = document.querySelector('[class*=dates-cls]') || document.querySelector('[class*=filterBar__date]');
        if (!d || d.offsetParent === null) return null;
        const r = d.getBoundingClientRect();
        return r.width > 0 ? {x: r.left + r.width / 2, y: r.top + r.height / 2} : null;
    })()""")
    if not box:
        return
    pg.click_xy(box["x"], box["y"])
    sleep_fn(0.35)
    for _ in range(14):
        state = pg.ev("""((yy, mm, dd) => {
            const p = document.querySelector('[class*=panel-cls]');
            if (!p) return {status: 'nopanel'};
            const cols = [...p.querySelectorAll('[class*=calMonths] > div')];
            const parsed = [];
            for (const c of cols) {
                const t = (c.querySelector('[class*=calNavTitle]')||{}).innerText || '';
                const km = t.match(/(\\d+)\\s*年\\s*(\\d+)\\s*月/);
                if (km) parsed.push({c, y: +km[1], m: +km[2]});
            }
            const hit = parsed.find(x => x.y === yy && x.m === mm);
            if (hit) {
                const dayEl = [...hit.c.querySelectorAll('[class*=days-cls] [class*=day-cls]')].find(
                    e => (e.innerText||'').trim() === String(dd) && !e.className.includes('outside') && !e.className.includes('disabled'));
                if (!dayEl) return {status: 'noday'};
                const r = dayEl.getBoundingClientRect();
                return {status: 'found', x: r.left + r.width / 2, y: r.top + r.height / 2};
            }
            if (!parsed.length) return {status: 'nocols'};
            const want = yy * 12 + mm, first = parsed[0].y * 12 + parsed[0].m;
            const nav = [...p.querySelectorAll('[class*=calNavBtn]')].find(
                b => !b.className.includes('hidden') && (b.innerText||'').trim() === (want < first ? '‹' : '›'));
            if (!nav) return {status: 'nonav'};
            const r = nav.getBoundingClientRect();
            return {status: 'nav', x: r.left + r.width / 2, y: r.top + r.height / 2};
        })""" + f"({yy}, {mm}, {dd})")
        st_s = (state or {}).get("status")
        if st_s == "nav":
            pg.click_xy(state["x"], state["y"])
            sleep_fn(0.2)
            continue
        if st_s == "found":
            pg.click_xy(state["x"], state["y"])
            sleep_fn(0.15)
            pg.click_xy(state["x"], state["y"])
            sleep_fn(0.15)
            ok = pg.ev("""(() => {
                const p = document.querySelector('[class*=panel-cls]');
                if (!p) return null;
                const b = [...p.querySelectorAll('[class*=panelFooter] button, button')].find(x => (x.innerText||'').trim() === '确定');
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return r.width > 0 ? {x: r.left + r.width / 2, y: r.top + r.height / 2} : null;
            })()""")
            if ok:
                pg.click_xy(ok["x"], ok["y"])
                sleep_fn(0.25)
            break
        break


def open_in_czgt(nick: str, title: str, day: str = "", find_ports_fn=None, targets_fn=None, page_cls=None, bring_fn=None, sleep_fn=None) -> str:
    """去创作罐头切到这个号的「作品管理」,按要查的日期筛选并把正文标题(不带话题)填进搜索框搜出来。"""
    from . import cdp, winfix
    find_ports_fn = find_ports_fn or cdp.find_ports
    targets_fn = targets_fn or cdp.targets
    page_cls = page_cls or cdp.Page
    bring_fn = bring_fn or winfix.bring_to_front
    sleep_fn = sleep_fn or time.sleep

    ports = find_ports_fn()
    if not ports:
        raise RuntimeError("没找到开着的创作罐头,先把创作罐头打开")
    port = ports[0]
    bring_fn()

    # 先看罐头顶部页签有没有开着这个号:有就直接点激活;没有才从首页卡片点开(不碰 w=0 的预加载隐藏页)
    home_t = next((t for t in targets_fn(port) if "czgts.cn" in (t.get("url") or "") and t.get("type") == "page"), None)
    if home_t:
        home = page_cls(home_t, timeout=10)
        try:
            r = _home_click_account(home, nick, sleep_fn)
        finally:
            home.close()
        if r not in ("ok", "tab"):
            raise RuntimeError(f"罐头里找不到「{nick}」这个号")
        sleep_fn(0.4 if r == "tab" else 0.8)

    target = None
    end = time.time() + 25
    while time.time() < end:
        matches = _find_om_targets(port, nick, targets_fn, page_cls)
        vis_hits = [m for m in matches if m[2]]
        if vis_hits:
            target = vis_hits[0][1]
            break
        sleep_fn(0.8)
    if not target:
        raise RuntimeError(f"罐头里点了「{nick}」,但没看到它的企鹅号页面(是不是掉登录了?)")

    pg = page_cls(target, timeout=15)
    try:
        try:
            pg.cmd("Page.bringToFront", timeout=5)
        except Exception:
            pass
        href = pg.ev("location.href") or ""
        if "/main/management/articleManage" not in href:
            pg.ev(f"location.href = {ARTICLE_MANAGE_URL!r}")
        end = time.time() + 18
        rect = None
        while time.time() < end:
            try:
                rect = pg.ev("""(() => {
                    const i = document.querySelector("input[placeholder='输入标题关键词搜索内容']");
                    if (!i || i.offsetParent === null) return null;
                    const r = i.getBoundingClientRect();
                    return r.width > 0 ? {x: r.left + Math.min(40, r.width / 3), y: r.top + r.height / 2} : null;
                })()""")
            except Exception:
                rect = None
            if rect:
                break
            sleep_fn(0.5)
        if not rect:
            raise RuntimeError(f"「{nick}」的作品管理页面打不开(搜索框没出来)")
        sleep_fn(0.35)

        if day:
            _filter_article_date(pg, day, sleep_fn)
            end_w = time.time() + 4.0
            sleep_fn(0.8)
            while time.time() < end_w:
                loading = pg.ev("[...document.querySelectorAll('.omui-loading,[class*=spin],[class*=loading]')].some(e => e.offsetParent !== null && e.getBoundingClientRect().width > 0)")
                if not loading:
                    break
                sleep_fn(0.2)

        rect = pg.ev("""(() => {
            const i = document.querySelector("input[placeholder='输入标题关键词搜索内容']");
            if (!i || i.offsetParent === null) return null;
            const r = i.getBoundingClientRect();
            return r.width > 0 ? {x: r.left + Math.min(40, r.width / 3), y: r.top + r.height / 2} : null;
        })()""") or rect
        q = search_keyword(title)
        pg.click_xy(rect["x"], rect["y"])
        pg.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
        pg.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
        pg.key("Backspace", 8)
        sleep_fn(0.1)
        if q:
            pg.cmd("Input.insertText", {"text": q})
            sleep_fn(0.3)
        sbtn = pg.ev("""(() => {
            const b = document.querySelector('.omui-input__search-btn') || document.querySelector('.omui-input--search .omui-icon-search');
            if (!b || b.offsetParent === null) return null;
            const r = b.getBoundingClientRect();
            return r.width > 0 ? {x: r.left + r.width / 2, y: r.top + r.height / 2} : null;
        })()""")
        if sbtn:
            pg.click_xy(sbtn["x"], sbtn["y"])
        else:
            pg.key("Enter", 13)
        bring_fn()
    finally:
        pg.close()
    return f"已在创作罐头「{nick}」里筛选 {day or '全部'} 并搜索「{q[:24]}」"
