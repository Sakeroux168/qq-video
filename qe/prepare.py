"""在罐头里把一批视频(最多 10 条)摆到企鹅号发布页上,停在发布前 —— 发布由人点(「发布 → 全部发布」)。

每条走 5 步(用户 2026-10-14 定的,实机摸过):
  1. 上传视频(一次把这批全传上去,页面顶上每条一个小页签,标题自动 = 文件名)
  2. 上传封面(封面按钮 →「本地上传」→ 选图 →「下一步」)
  3. 裁剪封面(依次 3:4 / 9:16 / 2.35:1 / 公众号小图,每个框拖到人中间 →「完成」)
  4. 自主声明(「添加内容自主声明」→「无需标注」→「确认」)
  5. AI 生成声明(「进行补充>」→ 不勾 →「提交」,只提交这份声明)
分类不选。

红线:平时**绝不点 发布 / 定时发布 / 存草稿**。所有点击都过 _guard,带这些字的一律拒绝。
唯一例外:用户在界面上勾了「摆好后软件自己点全部发布」(2026-10-15 用户同意),走 publish_all —— 只在整批都摆好、
没有标黄时才点;点完弹出没见过的框就停下交给人。
"""
import os
import re
import time

from . import cover as C
from .cdp import CdpError, Page, find_ports, targets
from .config import bj_now

QE_HOST = "om.qq.com"
HOME_HOST = "czgts.cn"
CREATE_URL = "https://om.qq.com/main/creation/video"
FORBID = re.compile(r"发布|发表|定时|存草稿|投稿")


class Stop(Exception):
    pass


class PrepError(RuntimeError):
    pass


def _guard(text: str):
    if FORBID.search(text or ""):
        raise PrepError(f"软件不点「{text}」(只有人能点发布)")


# 发布页顶上每条视频一个小页签:<div class="item-xxx [active-xxx]"><div class="title-xxx">标题</div><div class="icon-xxx">…</div></div>
# (只认 item- 下面的 title-:右边「诊断助手」的 class 也带 title-)
TAB_SEL = '[class^="item-"] > [class^="title-"]'

# 页面里用的小工具:找看得见的元素、按字点按钮(带禁词检查)
_JS_LIB = r"""
window.__qe = {
  tabs: () => [...document.querySelectorAll('[class^="item-"] > [class^="title-"]')].filter(e => window.__qe.vis(e)),
  vis: e => !!(e && e.offsetParent !== null && e.getBoundingClientRect().width > 0),
  dlg: () => [...document.querySelectorAll('.omui-dialog')].filter(e => window.__qe.vis(e)).pop() || null,
  bad: t => /发布|发表|定时|存草稿|投稿/.test(t || ''),
  clickText: (root, sel, text) => {
    const els = [...(root || document).querySelectorAll(sel)].filter(e => window.__qe.vis(e) && (e.innerText || e.textContent || '').trim() === text);
    const e = els[els.length - 1];
    if (!e) return 'notfound';
    if (window.__qe.bad((e.innerText || '').trim())) return 'forbidden';
    e.scrollIntoView({block: 'center'}); e.click(); return 'ok';
  },
};
"""


class Runner:
    def __init__(self, log=lambda m: None, stopped=lambda: False, shot_dir: str = ""):
        self.log = log
        self.stopped = stopped
        self.shot_dir = shot_dir
        ports = find_ports()
        if not ports:
            raise PrepError("没找到开着的创作罐头,先把创作罐头打开")
        self.port = ports[0]
        self.page: Page | None = None
        self.account = ""

    # ---------------- 小工具 ----------------
    def _chk(self):
        if self.stopped():
            raise Stop()

    def sleep(self, s: float):
        end = time.time() + s
        while time.time() < end:
            self._chk()
            time.sleep(min(0.25, max(0.0, end - time.time())))

    def ev(self, js: str, timeout: float = 20):
        self.page.ev(_JS_LIB, timeout)
        return self.page.ev(js, timeout)

    def wait(self, js: str, timeout: float, what: str):
        end = time.time() + timeout
        while time.time() < end:
            self._chk()
            try:
                v = self.ev(js)
            except CdpError:
                v = None
            if v:
                return v
            time.sleep(0.5)
        raise PrepError(f"等不到{what}(等了 {int(timeout)} 秒)")

    def click_text(self, text: str, sel: str = "button", in_dialog: bool = False) -> None:
        _guard(text)
        r = self.ev(f"window.__qe.clickText({'window.__qe.dlg()' if in_dialog else 'document'}, {sel!r}, {text!r})")
        if r == "forbidden":
            raise PrepError(f"拒绝点「{text}」")
        if r != "ok":
            raise PrepError(f"页面上找不到「{text}」")

    def shot(self, name: str):
        if self.shot_dir and self.page:
            os.makedirs(self.shot_dir, exist_ok=True)
            self.page.shot(os.path.join(self.shot_dir, f"{bj_now().strftime('%H%M%S')}_{name}.png"))

    # ---------------- 找号、进发布页 ----------------
    def _home(self) -> Page:
        t = next((t for t in targets(self.port) if HOME_HOST in (t.get("url") or "") and t["type"] == "page"), None)
        if not t:
            raise PrepError("罐头首页没找到")
        return Page(t)

    def _account_pages(self, name: str, visible_only: bool = True) -> list[dict]:
        out = []
        for t in targets(self.port):
            if QE_HOST not in (t.get("url") or ""):
                continue
            p = None
            try:
                p = Page(t, timeout=8)
                who, w = p.ev("[(document.querySelector('[class*=usernameText]')||{}).innerText||'', innerWidth]") or ["", 0]
            except CdpError:
                continue
            finally:
                if p:
                    p.close()
            if who.strip() == name and (w > 0 or not visible_only):
                out.append(t)
        return out

    def open_account(self, name: str) -> None:
        """在罐头里点开这个号(已经开着就切过去),拿到它那个看得见的企鹅号页面。"""
        self._chk()
        home = self._home()
        try:
            # 先看顶上已经开着的页签(用户在首页搜了别的号时,列表里就没有它了)
            r = home.ev("""((w) => { const t = [...document.querySelectorAll('.title-name')].find(e => (e.textContent||'').trim() === w);
                if (t) { (t.closest('.chrome-tab-content-wrapper') || t.parentElement).click(); t.click(); return 'tab'; }
                const e = [...document.querySelectorAll('div.name-UlOtte')].find(x => (x.textContent||'').trim() === w);
                if (!e) return 'notfound'; e.click(); return 'ok'; })(%r)""" % name)
            if r == "notfound":
                # 首页搜索框里有字(用户在搜别的号):清空了再找(真键盘删,罐头的搜索框认不了直接改值)
                box = home.ev("""(() => { const i = document.querySelector("input[placeholder='账号、手机号等']"); if (!i || !i.value) return null;
                    const b = i.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2, i.value]; })()""")
                if box:
                    self.log(f"罐头首页搜索框里是「{box[2]}」,清空了再找「{name}」")
                    home.click_xy(box[0], box[1])
                    home.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
                    home.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
                    home.key("Backspace", 8)
                    home.key("Enter", 13)
                    time.sleep(2.5)
                    r = home.ev("""((w) => { const e = [...document.querySelectorAll('div.name-UlOtte')].find(x => (x.textContent||'').trim() === w);
                        if (!e) return 'notfound'; e.click(); return 'ok'; })(%r)""" % name)
        finally:
            home.close()
        if r not in ("ok", "tab"):
            raise PrepError(f"罐头里找不到「{name}」这个号")
        end = time.time() + 30
        while time.time() < end:
            self.sleep(1)
            ts = self._account_pages(name)
            if len(ts) == 1:
                if self.page:
                    self.page.close()
                self.page = Page(ts[0])
                self.account = name
                self.log(f"罐头里打开了「{name}」")
                return
            if len(ts) > 1:
                raise PrepError(f"罐头里「{name}」开着好几个页面,关掉多的再来")
        raise PrepError(f"罐头里点了「{name}」,但没看到它的企鹅号页面(是不是掉登录了?)")

    def ensure_visible(self):
        """罐头切到别的页签,这个号的页面就变成 0×0,鼠标拖不动 —— 切回来。"""
        try:
            w = self.page.ev("innerWidth")
        except CdpError:
            w = 0
        if not w:
            self.log("罐头切到别的页签了,切回来…")
            self.open_account(self.account)

    def pending_videos(self) -> list[str]:
        """发布页上还挂着的视频(上一批没发 / 人自己传的)。"""
        if "/main/creation/video" not in (self.page.ev("location.pathname") or ""):
            return []
        return self.ev("window.__qe.tabs().map(e => e.innerText.trim())") or []

    def go_create(self):
        pend = self.pending_videos()
        if pend:
            raise PrepError(f"「{self.account}」的发布页上还有 {len(pend)} 条没发的视频(比如「{pend[0][:20]}」)。"
                            "先在罐头里发掉或者关掉它们,再来")
        self.page.ev(f"location.href = {CREATE_URL!r}")
        self.page.close()
        self.page = None
        end = time.time() + 40
        while time.time() < end:
            self.sleep(1.5)
            ts = self._account_pages(self.account)
            if ts:
                self.page = Page(ts[0])
                try:
                    if self.ev("location.pathname.includes('/creation/video') && !!document.querySelector('input[type=file]')"):
                        return
                except CdpError:
                    pass
                self.page.close()
                self.page = None
        raise PrepError("发布页打不开")

    # ---------------- 1. 上传视频 ----------------
    def upload(self, videos) -> None:
        self.page.set_files("input[type=file]", [v.path for v in videos])
        want = [v.title for v in videos]
        self.log(f"传 {len(videos)} 条视频…")
        self.wait("(() => { const w = %s; const have = window.__qe.tabs().map(e => (e.innerText||'').trim());"
                  " return w.every(t => have.includes(t)); })()" % _js_list(want), 120, "每条视频的小页签出来")

    def select_tab(self, title: str):
        r = self.ev("""((w) => { const e = window.__qe.tabs().find(e => (e.innerText||'').trim() === w); if (!e) return false; e.click(); return true; })(%r)""" % title)
        if not r:
            raise PrepError("顶上找不到这条的小页签")
        self.wait("((w) => { const t = [...document.querySelectorAll('.omui-inputautogrowing__inner')].find(e => window.__qe.vis(e)); return t && t.innerText.trim() === w; })(%r)" % title,
                  15, "切到这条")

    def wait_uploaded(self, title: str):
        """当前这条传完(「视频添加成功」)。大文件可能要好几分钟。"""
        end = time.time() + 30 * 60
        last = 0
        while time.time() < end:
            self._chk()
            st = self.ev("""(() => { const f = [...document.querySelectorAll('.omui-inputautogrowing__inner')].find(e => window.__qe.vis(e));
                const box = f && f.closest('.omui-panel');
                const t = (box || document.body).innerText || '';
                return t.includes('视频添加成功') ? 'ok' : (t.includes('上传失败') || t.includes('添加失败') ? 'fail' : 'wait'); })()""")
            if st == "ok":
                return
            if st == "fail":
                raise PrepError("视频上传失败")
            if time.time() - last > 30:
                self.log(f"  「{title[:16]}」还在传…")
                last = time.time()
            time.sleep(2)
        raise PrepError("视频传了 30 分钟还没传完")

    # ---------------- 2+3. 封面 ----------------
    def set_cover(self, v):
        if not C.exists(v.cover):
            raise PrepError("没有封面图")
        if self._cover_done():
            self.log("  封面已经设好了,跳过")
            return
        upfile = C.upload_file(v.cover)
        vfile = C.upload_file(v.vcover) if getattr(v, "vcover", "") and C.exists(v.vcover) else ""
        if upfile != v.cover:
            self.log("  封面图太小,放大了再传(会有点糊,最好让员工出大一点的图)")
        first = vfile or upfile                             # 竖的比例在前(3:4 先来):有竖图就先传竖图
        r = self.ev("""(() => { const b = [...document.querySelectorAll('button[class*=commonThumb]')].find(e => window.__qe.vis(e));
            if (!b) return 'no'; b.scrollIntoView({block:'center'}); b.click(); return 'ok'; })()""")
        if r != "ok":
            raise PrepError("找不到封面按钮")
        self.wait("(() => { const d = window.__qe.dlg(); return d && d.innerText.includes('本地上传'); })()", 15, "封面弹框")
        self.click_text("本地上传", sel="*", in_dialog=True)
        self.sleep(1)
        idx = self.ev("""[...document.querySelectorAll('input[type=file]')].findIndex(i => (i.accept||'').includes('image') && i.closest('.omui-dialog') && window.__qe.vis(i.closest('.omui-dialog')))""")
        if idx is None or idx < 0:
            raise PrepError("封面弹框里找不到传图片的地方")
        small0 = self._small_count()
        self.page.set_files("input[type=file]", [first], index=int(idx))
        end = time.time() + 60
        while True:
            self.sleep(0.6)
            st = self.ev("""((n0) => { if ((document.body.innerText.match(/封面图尺寸过小/g) || []).length > n0) return 'small';
                const d = window.__qe.dlg(); return d && [...d.querySelectorAll('button')].some(b => window.__qe.vis(b) && b.innerText.trim() === '下一步') ? 'ok' : ''; })(%d)""" % small0)
            if st == "ok":
                break
            if st == "small":
                raise PrepError("企鹅号说封面图尺寸太小")
            if time.time() > end:
                raise PrepError("等不到封面图传上去(60 秒)")
        self.click_text("下一步", in_dialog=True)
        self.wait("(() => { const d = window.__qe.dlg(); return d && !!d.querySelector('ezimage-cropper'); })()", 20, "裁剪页")
        self.sleep(1.2)
        iw, ih = C.image_size(upfile)
        # 2.35:1 下面有「标题区域」:大头照挪框也躲不开 → 这一个比例「更换当前封面」换成专用图(脸在标题区上面),后面的比例再换回原图
        wide = ""
        if C.needs_wide(iw, ih, v.plan):
            try:
                wide = C.wide_cover(v.cover, v.plan, log=self.log)
            except Exception as e:                         # 没 Key / 接口不通:退回切头顶(能躲多少躲多少)
                self.log(f"  ⚠ AI 扩图没成({e}),2.35:1 改成切掉一点头顶")
                v.plan = dict(v.plan, no_ai=True, ai235=False)
        cur = first
        done = []
        for _step in range(8):
            self._chk()
            info = self.ev("""(() => { const c = window.__qe.dlg().querySelector('ezimage-cropper'); const s = c && c.shadowRoot; if (!s) return null;
                const on = s.querySelector('.preview__option-item.radio-checked'); const cv = s.querySelector('.canvas-container');
                const r = cv.getBoundingClientRect();
                return {tag: on ? ((on.querySelector('.preview__img-tag')||{}).innerText||'').trim() : '', label: on ? ((on.querySelector('label')||{}).innerText||'').trim() : '',
                        canvas: {left: r.left, top: r.top, width: r.width, height: r.height}}; })()""")
            if not info:
                raise PrepError("裁剪框读不出来")
            ratio = C.ratio_of(info["tag"])
            # 这个比例用哪张图:2.35:1 要专用图就用专用图;竖的比例有竖图用竖图;别的用横图
            if ratio >= 2 and wide:
                want, plan = wide, None
            elif ratio < 1 and vfile:
                want, plan = vfile, v.vplan
            else:
                want, plan = upfile, v.plan
            if want != cur:
                # 「更换当前封面」只换这一个比例;企鹅号会把后面的比例「优先同步最新更换的封面图」,所以 cur 跟着变
                self._replace_current(want)
                cur = want
                self.log("  2.35:1:换成 AI 扩的专用图(脸在标题区上面)" if want == wide else
                         ("  竖的比例换成竖屏图" if want == vfile else "  换回横图"))
                info["canvas"] = self.ev("""(() => { const r = window.__qe.dlg().querySelector('ezimage-cropper').shadowRoot.querySelector('.canvas-container').getBoundingClientRect();
                    return {left: r.left, top: r.top, width: r.width, height: r.height}; })()""")
            if want != wide:                                   # 专用图就是 2.35:1,框正好是整张图,不用拖
                iw, ih = C.image_size(want)
                x0, y0, x1, y1 = C.box_drag(info["canvas"], iw, ih, ratio, plan)
                if abs(x1 - x0) > 1 or abs(y1 - y0) > 1:
                    self.page.drag(x0, y0, x1, y1)
                    self.sleep(0.6)
            done.append(info["tag"] or "?")
            self.shot(f"裁剪_{info['tag'].replace(':', 'x')}_{v.title[:8]}")
            last = self.ev("(() => [...window.__qe.dlg().querySelectorAll('button')].some(b => window.__qe.vis(b) && b.innerText.trim() === '完成'))()")
            if last:
                self.click_text("完成", in_dialog=True)
                break
            self.click_text("下一步", in_dialog=True)
            self.wait("((t) => { const s = window.__qe.dlg().querySelector('ezimage-cropper').shadowRoot; const on = s.querySelector('.preview__option-item.radio-checked');"
                      " return on && ((on.querySelector('.preview__img-tag')||{}).innerText||'').trim() !== t; })(%r)" % info["tag"], 10, "下一个比例")
            self.sleep(0.8)
        else:
            raise PrepError("裁剪一直没到「完成」")
        self.wait("!window.__qe.dlg()", 90, "封面裁好(弹框关掉)")
        # 每个号裁剪的比例不一样多(测试号只有 3:4、9:16;家长研习空间还有 2.35:1、公众号小图):裁过的比例都要在封面那一栏里出现
        self.wait("((tags) => { const f = [...document.querySelectorAll('.omui-inputautogrowing__inner')].find(e => window.__qe.vis(e));"
                  " const t = ((f && f.closest('.omui-panel')) || document.body).innerText || ''; return tags.every(x => !x || t.includes(x)); })(%s)"
                  % _js_list([x for x in done if x != "?"]), 30, "封面出现在页面上")
        self.log(f"  封面:{'竖的比例用竖屏图,' if vfile else ''}{'、'.join(done)} 都对好了")

    def _replace_current(self, file: str):
        """裁剪页上「更换当前封面」:只给当前这个比例换一张图(本地上传 → 下一步 → 回到裁剪页)。
        弹出来的是另一个封面框(它和裁剪框同时开着,用「没有裁剪器、有本地上传」认它)。
        第二次换的时候「本地上传」里还留着上次那张图、没有上传框:鼠标悬停在图上点「移除」图标再传。"""
        NEST = ("[...document.querySelectorAll('.omui-dialog')].filter(e => window.__qe.vis(e) && !e.querySelector('ezimage-cropper')"
                " && (e.innerText||'').includes('本地上传')).pop()")
        r = self.ev("""(() => { const s = window.__qe.dlg().querySelector('ezimage-cropper').shadowRoot;
            const b = [...s.querySelectorAll('button')].find(b => b.innerText.trim() === '更换当前封面'); if (!b) return 'no'; b.click(); return 'ok'; })()""")
        if r != "ok":
            raise PrepError("裁剪页上找不到「更换当前封面」")
        self.wait(f"!!({NEST})", 20, "换封面的弹框")
        self.ev(f"""(() => {{ const d = {NEST}; const t = [...d.querySelectorAll('li,div,span')].find(e => e.children.length === 0 && e.textContent.trim() === '本地上传'); if (t) t.click(); }})()""")
        self.sleep(1.2)
        has_input = f"(() => {{ const d = {NEST}; return !!d && [...d.querySelectorAll('input[type=file]')].some(i => (i.accept||'').includes('image')); }})()"
        if not self.ev(has_input):
            pt = self.ev(f"""(() => {{ const d = {NEST}; const i = [...d.querySelectorAll('img')].filter(e => window.__qe.vis(e)).pop(); if (!i) return null;
                const b = i.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; }})()""")
            if pt:
                self.page.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": pt[0], "y": pt[1]})
                self.sleep(0.6)
            ic = self.ev(f"""(() => {{ const d = {NEST}; const x = [...d.querySelectorAll('.omui-icon-remove')].filter(e => window.__qe.vis(e)).pop();
                if (!x) return null; const b = x.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; }})()""")
            if not ic:
                raise PrepError("换封面时上一张图移除不掉(找不到移除图标)")
            self.page.click_xy(ic[0], ic[1])                   # 只认真鼠标点(JS 点没反应)
            self.wait(has_input, 10, "上一张图移除掉")
        idx = self.ev(f"""(() => {{ const d = {NEST}; return [...document.querySelectorAll('input[type=file]')].findIndex(i => (i.accept||'').includes('image') && d.contains(i)); }})()""")
        if idx is None or idx < 0:
            raise PrepError("换封面的弹框里找不到传图片的地方")
        small0 = self._small_count()
        self.page.set_files("input[type=file]", [file], index=int(idx))
        end = time.time() + 60
        while True:
            self.sleep(0.6)
            st = self.ev(f"""(() => {{ if ((document.body.innerText.match(/封面图尺寸过小/g) || []).length > {small0}) return 'small'; const d = {NEST};
                return d && !d.innerText.includes('上传图片') && [...d.querySelectorAll('button')].some(b => window.__qe.vis(b) && b.innerText.trim() === '下一步') ? 'ok' : ''; }})()""")
            if st == "ok":
                break
            if st == "small":
                raise PrepError("企鹅号说换的封面图尺寸太小")
            if time.time() > end:
                raise PrepError("换的封面图 60 秒没传上去")
        self.ev(f"""(() => {{ const d = {NEST}; [...d.querySelectorAll('button')].find(b => window.__qe.vis(b) && b.innerText.trim() === '下一步').click(); }})()""")
        self.wait(f"!({NEST}) && !!window.__qe.dlg() && !!window.__qe.dlg().querySelector('ezimage-cropper')", 20, "回到裁剪页")
        self.sleep(1.2)

    def _small_count(self) -> int:
        """页面上现在有几条「封面图尺寸过小」(提示会留一会儿:只认传完以后新冒出来的)。"""
        return int(self.ev("(document.body.innerText.match(/封面图尺寸过小/g) || []).length") or 0)

    def _cover_done(self) -> bool:
        """这条的封面已经设过了(封面那一栏里有带比例字样的小图,没有那个大 + 号)。"""
        return bool(self.ev("""(() => { const f = [...document.querySelectorAll('.omui-inputautogrowing__inner')].find(e => window.__qe.vis(e));
            const p = f && f.closest('.omui-panel'); if (!p) return false;
            const plus = [...p.querySelectorAll('button[class*=commonThumb]')].some(e => window.__qe.vis(e));
            return !plus && (p.innerText || '').includes('3:4'); })()"""))

    # ---------------- 4. 自主声明 ----------------
    def set_declaration(self):
        if self._form_text_has("作者声明：无需标注"):
            return
        self.click_text("添加内容自主声明")
        self.wait("(() => { const d = window.__qe.dlg(); return d && d.innerText.includes('发布内容自主声明') && d.innerText.includes('个人观点'); })()",
                  20, "自主声明弹框里的选项")        # 选项是后加载的,弹框先出来、选项转一会儿圈
        r = self.ev("""(() => { const d = window.__qe.dlg(); const l = [...d.querySelectorAll('label,span,div')].reverse().find(e => (e.innerText||'').trim() === '无需标注');
            if (!l) return 'no'; l.click(); return 'ok'; })()""")
        if r != "ok":
            raise PrepError("自主声明里找不到「无需标注」")
        self.sleep(0.4)
        self.click_text("确认", in_dialog=True)
        self.wait("!window.__qe.dlg()", 10, "自主声明弹框关掉")
        if not self._form_text_has("作者声明：无需标注"):
            raise PrepError("自主声明没设上")

    # ---------------- 5. AI 生成声明 ----------------
    def set_ai_declaration(self):
        if self._form_text_has("已完成AI生成素材声明"):
            return
        r = self.ev("""(() => { const a = [...document.querySelectorAll('a')].find(e => window.__qe.vis(e) && (e.innerText||'').trim().startsWith('进行补充'));
            if (!a) return 'no'; a.scrollIntoView({block:'center'}); a.click(); return 'ok'; })()""")
        if r != "ok":
            self.log("  (这条没有「AI生成声明」要补)")
            return
        self.wait("(() => { const d = window.__qe.dlg(); return d && d.innerText.startsWith('AI生成声明'); })()", 10, "AI生成声明弹框")
        # 弹框里的「提交」只提交这份声明(不勾 = 没有 AI 生成的素材),不是发布
        r = self.ev("""(() => { const d = window.__qe.dlg(); if (!d.innerText.startsWith('AI生成声明')) return 'wrong';
            const b = [...d.querySelectorAll('button')].find(b => window.__qe.vis(b) && b.innerText.trim() === '提交'); if (!b) return 'no'; b.click(); return 'ok'; })()""")
        if r != "ok":
            raise PrepError("AI生成声明弹框里找不到「提交」")
        self.wait("!window.__qe.dlg()", 10, "AI生成声明弹框关掉")
        self.wait("(() => document.body.innerText.includes('已完成AI生成素材声明'))()", 10, "AI生成声明完成")

    def _form_text_has(self, s: str) -> bool:
        return bool(self.ev("""((s) => [...document.querySelectorAll('*')].some(e => window.__qe.vis(e) && e.children.length === 0 && (e.innerText||'').includes(s)))(%r)""" % s))

    # ---------------- 一批 ----------------
    def prepare_batch(self, account: str, videos, on_one=lambda v, ok, why: None) -> list[tuple]:
        """把这批摆到「account」的发布页上。每条做完调 on_one(视频, 成没成, 说明)。返回 [(视频, 成没成, 说明)]。"""
        self.open_account(account)
        pend = self.pending_videos()
        if pend and sorted(pend) == sorted(v.title for v in videos):
            self.log("发布页上已经传着这一批,接着往下做(不重新传)")
        else:
            self.go_create()
            self.upload(videos)
        out = []
        for v in videos:
            self._chk()
            self.ensure_visible()
            self.log(f"「{v.title[:24]}」")
            try:
                self.select_tab(v.title)
                self.wait_uploaded(v.title)
            except Stop:
                raise
            except (PrepError, CdpError) as e:
                self.shot(f"出错_{v.title[:8]}")
                self._close_dialog()
                out.append((v, False, str(e)))
                on_one(v, False, str(e))
                self.log(f"  ✘ {e}")
                continue
            # 用户:封面没传上去时以前把后面的自主声明、AI 补充也跳过了 —— 每一步各管各的,前面不成后面照样做
            errs = []
            for what, step in (("封面", lambda: self.set_cover(v)), ("自主声明", self.set_declaration),
                               ("AI生成声明", self.set_ai_declaration)):
                try:
                    step()
                except Stop:
                    raise
                except (PrepError, CdpError) as e:
                    self.shot(f"出错_{what}_{v.title[:8]}")
                    self._close_dialog()
                    errs.append(f"{what}:{e}")
                    self.log(f"  ✘ {what}:{e}")
            if errs:
                why = ";".join(errs) + "。没弄好的那几步在罐头里手动补一下"
                out.append((v, False, why))
                on_one(v, False, why)
            else:
                out.append((v, True, ""))
                on_one(v, True, "")
                self.log("  摆好了")
        return out

    # ---------------- 软件自己点「全部发布」(用户 2026-10-15 同意,要在界面上勾选才会做) ----------------
    def publish_all(self, titles: list[str]) -> str:
        """这批都摆好了:鼠标移到「发布」上 → 弹出「全部发布 / 单条发布」→ 点「全部发布」(只有一条时没有菜单,直接点「发布」)。
        点完等发布页上这批视频的小页签都没了 = 发出去了。返回 "ok";
        弹出没见过的框 / 报错 / 等不到结果:抛 PrepError(一个字都不再点,交给人看)。"""
        self.ensure_visible()
        pend = self.pending_videos()
        if sorted(pend) != sorted(titles):
            raise PrepError(f"发布页上的视频和这批对不上(页面上 {len(pend)} 条,这批 {len(titles)} 条),不敢点发布")
        if self.ev("!!window.__qe.dlg()"):
            raise PrepError("发布页上还开着弹框,不敢点发布")
        btn = self.ev("""(() => { const b = [...document.querySelectorAll('button')].filter(e => window.__qe.vis(e) && e.innerText.trim() === '发布').pop();
            if (!b) return null; b.scrollIntoView({block: 'nearest'}); const x = b.getBoundingClientRect(); return [x.left + x.width / 2, x.top + x.height / 2]; })()""")
        if not btn:
            raise PrepError("找不到「发布」按钮")
        for dx in (-30, -10, 0):                        # 鼠标慢慢移上去,菜单才弹出来
            self.page.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": btn[0] + dx, "y": btn[1]})
            self.sleep(0.3)
        self.sleep(0.8)
        menu = self.ev("""(() => { const b = [...document.querySelectorAll('button.tool_batch_publish,button')].find(e => window.__qe.vis(e) && e.innerText.trim() === '全部发布');
            if (!b) return null; const x = b.getBoundingClientRect(); return [x.left + x.width / 2, x.top + x.height / 2]; })()""")
        if len(titles) > 1 and not menu:
            raise PrepError("鼠标移到「发布」上没弹出「全部发布」")
        n_msg0 = len(self.ev("document.body.innerText") or "")
        if menu:
            self.log(f"点「全部发布」({len(titles)} 条)")
            self.page.click_xy(menu[0], menu[1])
        else:
            self.log("只有 1 条:点「发布」")
            self.page.click_xy(btn[0], btn[1])
        end = time.time() + 180
        while time.time() < end:
            self.sleep(1.5)
            try:
                left = self.pending_videos()
                path = self.page.ev("location.pathname")
                dlg = self.ev("(() => { const d = window.__qe.dlg(); return d ? (d.innerText || '').replace(/\\s+/g, ' ').slice(0, 120) : ''; })()")
                err = self.ev("""[...document.querySelectorAll('[class*=message],[class*=toast],[class*=notice]')].filter(e => window.__qe.vis(e))
                    .map(e => (e.innerText || '').trim()).filter(t => /失败|错误|不能|未通过|请/.test(t)).slice(0, 2).join(' / ')""")
            except CdpError:
                continue                                # 页面在跳转
            if dlg:
                raise PrepError(f"点完发布弹出了一个框,软件不认识,停下来了(请你看一眼):{dlg}")
            if err:
                raise PrepError(f"点完发布页面上提示:{err}")
            if "login" in (path or "").lower() or "passport" in (path or "").lower():
                raise PrepError("点完发布页面跳到了登录页(掉登录了?),不知道发没发出去,请你去后台看一眼")
            if not left or "/creation/video" not in (path or ""):
                self.log("这批发出去了")
                return "ok"
        raise PrepError("点完发布 3 分钟还没看到发出去(发布页上视频还在),请你看一眼")

    def _close_dialog(self):
        """出错时把开着的弹框都关掉(点「取消」或右上角 ×,不点别的按钮)。换封面框和裁剪框可能同时开着,一个个关。"""
        for _ in range(4):
            try:
                left = self.ev("""(() => { const ds = [...document.querySelectorAll('.omui-dialog')].filter(e => window.__qe.vis(e)); if (!ds.length) return 0;
                    const d = ds.find(e => !e.querySelector('ezimage-cropper')) || ds[ds.length - 1];
                    const b = [...d.querySelectorAll('button')].find(b => window.__qe.vis(b) && b.innerText.trim() === '取消');
                    if (b) b.click(); else { const x = d.querySelector('.omui-dialog__close,[class*=close]'); if (x) x.click(); }
                    return ds.length; })()""")
            except Exception:
                return
            if not left:
                return
            self.sleep(0.8)

    def close(self):
        if self.page:
            self.page.close()
            self.page = None


def _js_list(items) -> str:
    import json
    return json.dumps(list(items), ensure_ascii=False)
