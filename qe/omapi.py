"""企鹅号官方 OpenAPI 发视频(照搬旧软件「企鹅号批量发布」的做法,文档:
https://static.om.qq.com/om/om_3.0/normal/html/FdqHaHRh8sY8XlAqsUPKAsHX3FLsNiUc.html )

    换 token → 分片上传(ready / trunk)→ 查事务拿 vid → clientpubvideo → 轮询事务到「成功 / 失败」

旧软件实际怎么发的(它的数据库里 359 条都是这样):标题 = 简介 = 文件名;tags 空;分类 = 号的默认分类;
aigc_userstatement = "2"(非 AI);不传封面(平台自己截一帧)。
密钥只在这台电脑上解开用,不写日志、不显示。
"""
import hashlib
import os
import time

import requests

AUTH = "https://auth.om.qq.com/omoauth2/accesstoken"
API = "https://api.om.qq.com"
TRUNK = 100 * 1024 * 1024        # 一片 100MB(上限 500MB,小一点出错重来快)


class ApiError(Exception):
    pass


def _ok(j: dict) -> bool:
    return str(j.get("code", "")) == "0"


def file_hashes(path: str) -> tuple[int, str, str]:
    md5, sha = hashlib.md5(), hashlib.sha1()
    size = 0
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b""):
            md5.update(b)
            sha.update(b)
            size += len(b)
    return size, md5.hexdigest(), sha.hexdigest()


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
        r = self.s.post(AUTH, params={"grant_type": "clientcredentials", "client_id": self._cid,
                                      "client_secret": self._sec}, timeout=30)
        j = self._json(r)
        d = j.get("data") or {}
        if not _ok(j) or not d.get("access_token"):
            raise ApiError(f"换 token 失败:{j.get('msg') or j.get('code') or r.status_code}")
        self._tok = d["access_token"]
        self._exp = time.time() + int(d.get("expires_in") or d.get("expire_in") or 3600)
        return self._tok

    @staticmethod
    def _json(r) -> dict:
        try:
            return r.json()
        except ValueError:
            raise ApiError(f"接口没回 JSON:HTTP {r.status_code} {r.text[:100]}")

    def _call(self, method: str, path: str, what: str, **kw) -> dict:
        params = dict(kw.pop("params", {}) or {})
        params["access_token"] = self.token()
        r = self.s.request(method, API + path, params=params, timeout=kw.pop("timeout", 60), **kw)
        j = self._json(r)
        if not _ok(j):
            raise ApiError(f"{what}失败:{j.get('msg') or ''}(code {j.get('code')})")
        return j.get("data") or {}

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
                    raise ApiError("停下了")
                f.seek(off)
                chunk = f.read(TRUNK)
                d = self._call("POST", "/video/clientuploadtrunk", "上传视频", timeout=600,
                               data={"transaction_id": tid, "start_offset": str(off)},
                               # 文件名只用英文:中文名平台报 invalid_file_upload(40023);旧软件也是传临时文件「qepm-chunk-*」
                               files={"mediatrunk": (f"qepm-chunk-{off}", chunk, "application/octet-stream")})
                # end_offset 是收到的最后一个字节的位置(从 0 数,含它):6498881 字节的文件传完回 6498880。
                # 下一片从 end_offset + 1 开始;到文件大小就传完了(2026-10-15 真接口试出来的,按「= 文件大小」算会多传一次报 40023)
                nxt = int(d.get("end_offset") or 0) + 1
                if nxt <= off:
                    raise ApiError("上传视频:平台没收下这一片")
                off = min(nxt, size)
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
                raise ApiError("上传后平台处理失败")
            if stop and stop():
                raise ApiError("停下了")
            time.sleep(3)
        raise ApiError("上传完 5 分钟还没拿到 vid")

    def publish(self, vid: str, title: str, cat: int, desc: str = "", aigc: str = "2", tags: str = "",
                self_declare: int | None = 0) -> dict:
        """aigc "2" = AI 声明「非 AI 生成」;self_declare 0 = 自主声明「无需标注」(网页上选无需标注提交的就是 id 0;
        文档:ext_info 里写 self_declare=值)。旧软件值是 0 时干脆不带,后台显示「添加内容自主声明」(空的),用户要的是无需标注。"""
        body = {"title": title, "tags": tags, "vid": vid, "cat": int(cat), "desc": (desc or title)[:200],
                "aigc_userstatement": aigc}
        if self_declare is not None:
            body["ext_info"] = f"self_declare={int(self_declare)}"
        return self._call("POST", "/articlev2/clientpubvideo", "发布", json=body)

    def wait_done(self, tid: str, timeout: float = 600, stop=None) -> str:
        """轮询发布事务:返回 "成功";失败抛 ApiError;等太久返回 "处理中"(平台多半还在审,记成待查)。"""
        end = time.time() + timeout
        while time.time() < end:
            st = str(self.transaction(tid).get("transaction_status") or "")
            if "成功" in st:
                return "成功"
            if "失败" in st:
                raise ApiError("平台说发布失败")
            if stop and stop():
                return "处理中"
            time.sleep(5)
        return "处理中"

    def send(self, path: str, title: str, cat: int, on_progress=None, stop=None, log=None,
             self_declare: int | None = 0, aigc: str = "2") -> dict:
        """整条:传 → vid → 发 → 等结果。返回 {"vid","article_id","transaction_id","status"}。"""
        say = log or self.log
        say("上传中")
        tid = self.upload(path, on_progress=on_progress, stop=stop)
        vid = self.wait_vid(tid, stop=stop)
        say("发布中")
        d = self.publish(vid, title, cat, aigc=aigc, self_declare=self_declare)
        ptid = d.get("transaction_id") or ""
        st = self.wait_done(ptid, stop=stop) if ptid else "处理中"
        return {"vid": vid, "article_id": str(d.get("article_id") or ""), "transaction_id": ptid, "status": st}
