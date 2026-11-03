"""接口发布带封面(2026-10-16,旧软件 1.21 加了同样的功能,我们照着做的):
① 封面图用企鹅号网页后台自己的传图接口(image.om.qq.com/cpom_pimage/ArchacaleUploadViaFile,要登录的 Cookie)
   传上去,拿到图片地址(data.url.url,inews.gtimg.com/om_bt/...);
② 发布时把地址当 cover_pic 交给 clientpubvideo(文档没写,但平台收:坏地址报
   「ClientPubVideoReq.CoverPic: value must be absolute」,好地址过了这一关)。

为什么不用官方的 /video/clientvideopic:16 个号都报 41012 empty_upload_uin(见 omapi.cover)。
登录的页面:在已经登录企鹅号的页面里(创作罐头里开着的 om.qq.com 页面)用 fetch 传(带 Cookie);
传图接口的参数从 om.qq.com 前端代码里抄的(main.om_mixin_utility.*.js:appid / isUpOrg / endpoint / isRetImgAttr / opCode=151 / file)。
"""
import base64
import json
import os
import threading

from .cdp import CdpError, Page, find_ports, targets

UPLOAD = "https://image.om.qq.com/cpom_pimage/ArchacaleUploadViaFile"
FIELDS = {"appid": "LA6zXi1lWzAioIzdiAD6iM10aHarlHF6", "isUpOrg": 1, "endpoint": 1, "isRetImgAttr": 1, "opCode": 151}
MAX_BYTES = 10 * 1024 * 1024
_lock = threading.Lock()


class CoverError(Exception):
    pass


NO_CZGT = "没开创作罐头(或罐头里没开企鹅号)"
NO_LOGIN = "创作罐头里的企鹅号都没登录"


def _targets() -> list[dict]:
    """罐头里开着的 om.qq.com 页面。罐头里好几个号:有的登着(/main),有的停在登录页(/userAuth)——
    登录页的排到最后(2026-11-03 实查:原来只拿第一个,碰上没登录的那个就传不上,10.28 有 122 条因此没带封面)。"""
    out = []
    for port in find_ports():
        try:
            ts = targets(port)
        except Exception:
            continue
        out += [t for t in ts if "om.qq.com" in (t.get("url") or "") and t.get("type") in ("page", "webview")]
    return sorted(out, key=lambda t: "/userauth" in (t.get("url") or "").lower())


LIST_JS = ("(async () => { try { const r = await fetch('/marticle/article/list?category=&ftype=&search=&startDate=&endDate="
           "&num=1&index=1&readChannel=all&source=&dstChannel=&isPartDst=0&ignoreTotal=1', {credentials: 'include'});"
           " return await r.text(); } catch (e) { return 'ERR ' + e; } })()")


def _logged_in(p: Page) -> bool:
    """这个页面登没登着:读一条作品列表(只读),回 JSON 且 code 0 就是登着;回登录页 html 就是没登。"""
    try:
        j = json.loads(p.ev(LIST_JS, timeout=20) or "")
    except (CdpError, ValueError):
        return False
    return isinstance(j, dict) and str((j.get("response") or {}).get("code", j.get("code", ""))) == "0"


def check() -> str:
    """发之前看一眼封面传不传得上:罐头里有登录着的企鹅号页面 → 返回 "";没有 → 返回原因(NO_CZGT / NO_LOGIN)。只读。"""
    ts = _targets()
    if not ts:
        return NO_CZGT
    for t in ts:
        try:
            p = Page(t, timeout=10)
        except (CdpError, OSError):
            continue
        try:
            if _logged_in(p):
                return ""
        finally:
            p.close()
    return NO_LOGIN


def upload(img: str) -> str:
    """传一张封面图,返回图片地址。出错抛 CoverError。一个页面传不上(没登录)就换下一个页面再传。"""
    with open(img, "rb") as f:
        data = f.read()
    if len(data) > MAX_BYTES:
        raise CoverError("封面图太大(超过 10MB)")
    ext = os.path.splitext(img)[1].lower()
    mime = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
    js = """(async (b64, mime, fields, url) => {
      const bin = atob(b64); const u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const fd = new FormData(); for (const k in fields) fd.append(k, fields[k]);
      fd.append('file', new Blob([u8], {type: mime}), 'cover' + (mime === 'image/png' ? '.png' : '.jpg'));
      try { const r = await fetch(url, {method: 'POST', body: fd, credentials: 'include'}); return r.status + ' ' + await r.text(); }
      catch (e) { return 'ERR ' + e; } })(%s, %s, %s, %s)""" % (json.dumps(base64.b64encode(data).decode()), json.dumps(mime),
                                                          json.dumps(FIELDS), json.dumps(UPLOAD))
    with _lock:
        ts = _targets()
        if not ts:
            raise CoverError(f"传封面失败:{NO_CZGT}")
        ts.sort(key=lambda t: t.get("id") != _good["id"])  # 上次传成的那个页面先试
        err = CoverError(f"传封面失败:{NO_LOGIN}")
        for t in ts:
            try:
                p = Page(t, timeout=20)
            except (CdpError, OSError):
                continue
            try:
                txt = p.ev(js, timeout=120) or ""
            except CdpError as e:
                err = CoverError(f"传封面时页面出错:{e}")
                continue
            finally:
                p.close()
            try:
                url = _parse(txt)
            except CoverError as e:
                err = e
                continue                                 # 这个页面没登录 / 过期了:换下一个页面
            _good["id"] = t.get("id")
            return url
        raise err


_good = {"id": None}                                     # 上次传成功的页面


def _parse(txt: str) -> str:
    """传图接口的回话 → 图片地址;没登录 / 出错抛 CoverError。"""
    if txt.startswith("ERR"):
        raise CoverError(f"传封面失败:{txt[4:120]}")
    status, _, body = txt.partition(" ")
    try:
        j = json.loads(body)
    except ValueError:
        raise CoverError(f"传封面失败:HTTP {status}(企鹅号没登录?)")
    if not isinstance(j, dict) or str(j.get("code")) != "0":
        j = j if isinstance(j, dict) else {}
        raise CoverError(f"传封面失败:{j.get('message') or j.get('msg') or j.get('code')}(企鹅号登录过期了?)")
    u = ((j.get("data") or {}).get("url") or {})
    url = u.get("url") if isinstance(u, dict) else ""
    if not url or not str(url).startswith("http"):
        raise CoverError("传封面:企鹅号没回图片地址")
    return str(url)
