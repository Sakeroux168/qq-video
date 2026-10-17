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


def _page() -> Page:
    """找一个已经登录企鹅号的页面(罐头里的 om.qq.com)。"""
    for port in find_ports():
        for t in targets(port):
            if "om.qq.com" in (t.get("url") or "") and t.get("type") in ("page", "webview"):
                try:
                    return Page(t, timeout=20)
                except CdpError:
                    continue
    raise CoverError("没找到登录着企鹅号的页面(把创作罐头打开、登录着企鹅号)")


def upload(img: str) -> str:
    """传一张封面图,返回图片地址。出错抛 CoverError。"""
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
        p = _page()
        try:
            txt = p.ev(js, timeout=120) or ""
        except CdpError as e:
            raise CoverError(f"传封面时页面出错:{e}")
        finally:
            p.close()
    if txt.startswith("ERR"):
        raise CoverError(f"传封面失败:{txt[4:120]}")
    status, _, body = txt.partition(" ")
    try:
        j = json.loads(body)
    except ValueError:
        raise CoverError(f"传封面失败:HTTP {status}(企鹅号没登录?)")
    if str(j.get("code")) != "0":
        raise CoverError(f"传封面失败:{j.get('message') or j.get('msg') or j.get('code')}(企鹅号登录过期了?)")
    u = ((j.get("data") or {}).get("url") or {})
    url = u.get("url") if isinstance(u, dict) else ""
    if not url or not str(url).startswith("http"):
        raise CoverError("传封面:企鹅号没回图片地址")
    return str(url)
