"""企鹅号官方 OpenAPI 发视频(照搬旧软件「企鹅号批量发布」的做法,文档:
https://static.om.qq.com/om/om_3.0/normal/html/FdqHaHRh8sY8XlAqsUPKAsHX3FLsNiUc.html )

    换 token → 分片上传(ready / trunk)→ 查事务拿 vid → clientpubvideo → 轮询事务到「成功 / 失败」

旧软件实际怎么发的(它的数据库里 359 条都是这样):标题 = 简介 = 文件名;tags 空;分类 = 号的默认分类;
aigc_userstatement = "2"(非 AI);不传封面(平台自己截一帧)。
我们(2026-10-16 用户要的):视频旁边有同名封面图就传上去(/video/clientvideopic,拿到 vid 之后、发布之前);
封面传不上不耽误发视频,平台自己截一帧,记一笔原因。
密钥只在这台电脑上解开用,不写日志、不显示 —— 所有报错都过一遍 redact(),网络错只给一句人话(2026-10-15 审查:
requests 的报错原文带完整 URL,client_secret / access_token 会跟着进日志)。
"""
import hashlib
import json
import os
import re
import time

import requests

AUTH = "https://auth.om.qq.com/omoauth2/accesstoken"
API = "https://api.om.qq.com"
TRUNK = 100 * 1024 * 1024        # 一片 100MB(上限 500MB,小一点出错重来快)


class ApiError(Exception):
    """接口出错。code = 平台回的错误码(网络错为 "");fatal = 这个号后面的都别发了(比如换不到 token)。"""

    def __init__(self, msg: str, code: str = "", fatal: bool = False):
        super().__init__(redact(msg))
        self.code, self.fatal = str(code or ""), fatal


class Stopped(ApiError):
    """人按了「停」:不是失败。"""


class Unknown(ApiError):
    """发布请求发出去了,但没收到平台的回话(超时 / 断网):平台可能已经发了,不能自动再发,要人去后台看。"""


_SECRET = re.compile(r"(client_secret|access_token|client_id|refresh_to(?:e)?ken)=[^&\s'\"]*", re.I)


def redact(s: str) -> str:
    return _SECRET.sub(r"\1=***", str(s or ""))


def _ok(j) -> bool:
    return isinstance(j, dict) and str(j.get("code", "")) == "0"


_TOKEN_BAD = ("40001", "40014", "42001", "41001")


def file_hashes(path: str) -> tuple[int, str, str]:
    md5, sha = hashlib.md5(), hashlib.sha1()
    size = 0
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b""):
            md5.update(b)
            sha.update(b)
            size += len(b)
    return size, md5.hexdigest(), sha.hexdigest()


def _net(fn, what: str):
    """调 requests;网络层的错误换成人话(不带 URL,URL 里有密钥)。"""
    try:
        return fn()
    except requests.Timeout:
        raise ApiError(f"{what}:等企鹅号回话太久(超时),可能是网不好")
    except requests.RequestException:
        raise ApiError(f"{what}:网络连不上企鹅号,看看网线 / 网络")


class Client:
    def __init__(self, client_id: str, client_secret: str, session=None, log=None):
        self._cid, self._sec = client_id, client_secret
        self.s = session or requests.Session()
        self.log = log or (lambda m: None)
        self._tok, self._exp = "", 0.0

    # ---------------- token ----------------
    def token(self) -> str:
        if self._tok and time.time() < self._exp - 300:
            return self._tok
        r = _net(lambda: self.s.post(AUTH, params={"grant_type": "clientcredentials", "client_id": self._cid,
                                                   "client_secret": self._sec}, timeout=30), "换 token")
        j = self._json(r)
        d = j.get("data") or {}
        if not _ok(j) or not d.get("access_token"):
            raise ApiError(f"换 token 失败(账号凭据可能失效,去旧软件 / 后台看看):{j.get('msg') or j.get('code') or r.status_code}",
                           j.get("code"), fatal=True)
        self._tok = d["access_token"]
        self._exp = time.time() + int(d.get("expires_in") or d.get("expire_in") or 3600)
        return self._tok

    @staticmethod
    def _json(r) -> dict:
        try:
            j = r.json()
        except ValueError:
            raise ApiError(f"企鹅号没按格式回话:HTTP {r.status_code}")
        if not isinstance(j, dict):                   # 回了 null / 列表:当成没回对话(发布这步会算「结果不明」)
            raise ApiError(f"企鹅号回话格式不对:HTTP {r.status_code}")
        return j

    def _call(self, method: str, path: str, what: str, **kw) -> dict:
        params = dict(kw.pop("params", {}) or {})
        timeout = kw.pop("timeout", 60)
        for k in range(2):
            params["access_token"] = self.token()
            r = _net(lambda: self.s.request(method, API + path, params=params, timeout=timeout, **kw), what)
            j = self._json(r)
            if _ok(j):
                d = j.get("data")
                return d if isinstance(d, dict) else {}
            code, msg = str(j.get("code") or ""), str(j.get("msg") or "")
            if k == 0 and (code in _TOKEN_BAD or "token" in msg.lower()):
                self._tok, self._exp = "", 0.0        # token 中途作废(别处用同一个号换了):重换一次再试;平台回错误码 = 没发,重试安全
                continue
            raise ApiError(f"{what}失败:{msg}(code {code})", code)
        return {}

    # ---------------- 发一条 ----------------
    def upload(self, path: str, on_progress=None, stop=None) -> str:
        """分片传视频,返回 transaction_id。"""
        size, md5, sha = file_hashes(path)
        d = self._call("POST", "/video/clientuploadready", "准备上传", json={"size": size, "md5": md5, "sha": sha})
        tid = d.get("transaction_id")
        if not tid:
            raise ApiError("准备上传没拿到 transaction_id")
        off = 0
        with open(path, "rb") as f:
            while off < size:
                if stop and stop():
                    raise Stopped("停下了")
                f.seek(off)
                chunk = f.read(TRUNK)
                d = self._call("POST", "/video/clientuploadtrunk", "上传视频", timeout=600,
                               data={"transaction_id": tid, "start_offset": str(off)},
                               # 文件名只用英文:中文名平台报 invalid_file_upload(40023);旧软件也是传临时文件「qepm-chunk-*」
                               files={"mediatrunk": (f"qepm-chunk-{off}", chunk, "application/octet-stream")})
                # 平台回的是「下一片」的起止位置:start_offset = 下一片从哪开始,end_offset = 下一片到哪(含)。
                # 最后一片传完回 start = end = 文件大小 - 1(6498881 字节的文件回 6498880,2026-10-15 真接口)。
                # 2026-10-16 修:以前拿 end_offset + 1 当下一片开头,单片(<100MB)碰巧对,多片会跳过一整片 → 40023。
                # 现在:我们这片传到文件末尾就算传完(不再多传);没到末尾就从平台说的 start_offset 接着传。
                sent_to = off + len(chunk)
                if sent_to >= size:
                    off = size
                else:
                    try:
                        nxt = int(d["start_offset"])
                    except (KeyError, TypeError, ValueError):
                        nxt = sent_to
                    if nxt <= off or nxt > size:
                        raise ApiError("上传视频:平台没收下这一片")
                    off = nxt
                if on_progress:
                    on_progress(off, size)
        return tid

    def transaction(self, tid: str) -> dict:
        return self._call("GET", "/transaction/infoclient", "查进度", params={"transaction_id": tid})

    def wait_vid(self, tid: str, timeout: float = 300, stop=None) -> str:
        end = time.time() + timeout
        while time.time() < end:
            d = self.transaction(tid)
            # 真接口(2026-10-15 试的):vid 在最外层 data.vid,article_info.article_video_info 是空的;文档写的是后者,两个都认
            vid = d.get("vid") or ((d.get("article_info") or {}).get("article_video_info") or {}).get("vid")
            if vid:
                return vid
            if "失败" in str(d.get("transaction_status") or ""):
                raise ApiError("上传后平台处理失败" + _why(d))
            if stop and stop():
                raise Stopped("停下了")
            time.sleep(3)
        raise ApiError(f"上传完等了 {int(timeout)} 秒还没拿到视频编号(vid)")

    def cover(self, vid: str, img: str) -> dict:
        """给这条视频传封面(每个 vid 一张;平台建议 3:4,不超过 20MB,jpg / png)。md5 是图片的 md5。"""
        with open(img, "rb") as f:
            data = f.read()
        ext = os.path.splitext(img)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        return self._call("POST", "/video/clientvideopic", "传封面", timeout=120,
                          params={"vid": vid, "md5": hashlib.md5(data).hexdigest()},
                          # 文件名只用英文(视频分片中文名会报 40023,封面也照这样)
                          files={"media": ("cover" + (ext if ext in (".jpg", ".jpeg", ".png") else ".jpg"), data, mime)})

    def publish(self, vid: str, title: str, cat: int, desc: str = "", aigc: str = "2", tags: str = "",
                self_declare: int | None = 0) -> dict:
        """aigc "2" = AI 声明「非 AI 生成」;self_declare 0 = 自主声明「无需标注」(网页上选无需标注提交的就是 id 0)。
        旧软件值是 0 时干脆不带,后台显示「添加内容自主声明」(空的),用户要的是无需标注(2026-10-15 真发验证过)。"""
        body = {"title": title, "tags": tags, "vid": vid, "cat": int(cat), "desc": (desc or title)[:200],
                "aigc_userstatement": aigc}
        if self_declare is not None:
            # ext_info 必须是 JSON(写成文档里的 "self_declare=0" 平台报 40002 must be a valid JSON encoding)
            body["ext_info"] = json.dumps({"self_declare": int(self_declare)})
        return self._call("POST", "/articlev2/clientpubvideo", "发布", json=body)

    def wait_done(self, tid: str, timeout: float = 600, stop=None) -> str:
        """轮询发布事务:返回 "成功";平台明确说失败抛 ApiError(带原因);等太久 / 停了返回 "处理中"。"""
        end = time.time() + timeout
        while time.time() < end:
            d = self.transaction(tid)
            st = str(d.get("transaction_status") or "")
            if "成功" in st:
                return "成功"
            if "失败" in st:
                raise ApiError("平台说发布失败" + _why(d))
            if stop and stop():
                return "处理中"
            time.sleep(5)
        return "处理中"

    def send(self, path: str, title: str, cat: int, on_progress=None, stop=None, log=None,
             self_declare: int | None = 0, aigc: str = "2", before_publish=None, cover: str = "") -> dict:
        """整条:传 → vid → 发 → 等结果。返回 {"vid","article_id","transaction_id","status"}。
        status:「成功」/「处理中」(平台已收下,还在处理)。
        cover:要传的封面图(空 = 不传,平台自己截);传不上不耽误发,原因放在返回的 "cover" 里。
        before_publish(vid):真正调发布接口前调一下(界面先记一笔「发布中」,程序中途关掉也不会再发)。
        发布请求发出去后没收到回话 → 抛 Unknown;平台已收下、之后查进度出错 → 不算失败,返回「处理中」。"""
        say = log or self.log
        say("上传中")
        tid = self.upload(path, on_progress=on_progress, stop=stop)
        vid = self.wait_vid(tid, stop=stop)
        if stop and stop():
            raise Stopped("停下了")
        cov = ""
        if cover:
            say("传封面")
            try:
                self.cover(vid, cover)
                cov = "传了"
            except ApiError as e:                        # 封面传不上:照样发视频,平台自己截一帧
                cov = f"没传上:{e}"
            except OSError as e:
                cov = f"没传上:图片读不出来({type(e).__name__})"
        if stop and stop():
            raise Stopped("停下了")
        self.token()                                     # 换 token 出错 = 明确没发,不算结果不明
        if before_publish:
            before_publish(vid)
        say("发布中")
        try:
            d = self.publish(vid, title, cat, aigc=aigc, self_declare=self_declare)
        except ApiError as e:
            if e.code:                                   # 平台回了错误码 = 明确没发
                raise
            raise Unknown(f"发布请求发出去了,但没收到平台回话({e}),可能已经发了,去后台看一眼")
        # 平台已经收下了:后面不管出什么错(回话缺字段、查进度出错)都算已发(处理中),绝不能记成没发成再发一遍
        try:
            ptid = str(d.get("transaction_id") or "")
            aid = str(d.get("article_id") or "")
        except Exception:
            ptid = aid = ""
        st = "处理中"
        if ptid:
            try:
                st = self.wait_done(ptid, stop=stop)
            except ApiError as e:
                if "平台说发布失败" in str(e):
                    raise
                st = "处理中"
            except Exception:
                st = "处理中"
        return {"vid": vid, "article_id": aid, "transaction_id": ptid, "status": st, "cover": cov}


def _why(d: dict) -> str:
    for k in ("msg", "reason", "fail_reason", "transaction_msg", "err_msg"):
        if d.get(k):
            return f":{d[k]}"
    return ""
