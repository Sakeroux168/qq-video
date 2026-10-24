"""人在「封面预览」里手动拖过的框放哪。存在数据目录的 封面调整.json,关了软件再开还在。

{视频路径: {"manual": {封面图路径: {"0.750": [框中心 x 占图几成, y], ...}}}}
(以前还记「用横还是竖」,组长说 jpg 有字不能用以后只用 png,横竖不再记)
"""
import json
import os
import re
import threading

from .config import data_dir

_LOCK = threading.RLock()


class Adjustments:
    def __init__(self, path=None):
        self.path = str(path or (data_dir() / "封面调整.json"))
        try:
            with open(self.path, encoding="utf-8") as f:
                self.d = json.load(f)
        except (OSError, ValueError):
            self.d = {}

    def _save(self):
        with _LOCK:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)

    # 用户 2026-10-24:「本来调好位置了,结果挪到 10.25 又要重新调整」—— 原来只按 视频路径 + 封面路径 记,
    # 挪了文件夹 / 去黑边换了封面路径就认不出。现在路径对不上时按 视频标题 + 封面图名字 找回来,改的时候搬到新路径下
    def _vkey(self, video: str, title: str = "") -> str:
        if video in self.d or not title:
            return video
        from .folders import norm_name
        n = norm_name(title)
        # 只认「原来那个文件已经不在了」的(真挪走了);原处还在的是另一条同名视频,不串
        hits = [k for k in self.d if norm_name(os.path.splitext(os.path.basename(k))[0]) == n and not os.path.exists(k)]
        return hits[-1] if hits else video

    @staticmethod
    def _base(p: str) -> str:
        """封面图的名字(去黑边的副本还原成原名:「横屏16x9_<哈希>_<时间>_<大小>.png」→「横屏16x9.png」)。"""
        try:
            from .cover import orig_of
            p = orig_of(p)
        except Exception:
            pass
        b = os.path.basename(p or "")
        return re.sub(r"_[0-9a-f]{10}(?:_\d+_\d+)?(?=\.\w+$)", "", b).lower()

    def _ckey(self, m: dict, cover: str):
        if cover in m:
            return cover
        b = self._base(cover)
        hits = [k for k in m if self._base(k) == b]
        return hits[0] if len(hits) == 1 else None

    def _move(self, video: str, title: str):
        """改之前:旧路径下的记录搬到新路径(其它比例调过的框不丢)。"""
        old = self._vkey(video, title)
        if old != video and video not in self.d and old in self.d:
            self.d[video] = json.loads(json.dumps(self.d[old]))

    def manual(self, video: str, cover: str, title: str = "") -> dict:
        m = (self.d.get(self._vkey(video, title)) or {}).get("manual") or {}
        k = self._ckey(m, cover)
        return dict(m.get(k) or {}) if k else {}

    def set_box(self, video: str, cover: str, rkey: str, cx: float, cy: float, title: str = ""):
        self._move(video, title)
        m = self.d.setdefault(video, {}).setdefault("manual", {})
        k = self._ckey(m, cover)
        if k and k != cover:                              # 同一张图换了路径:框搬过去
            m[cover] = m.pop(k)
        m.setdefault(cover, {})[rkey] = [round(cx, 4), round(cy, 4)]
        self._save()

    def ai235(self, video: str, title: str = ""):
        """None = 按软件自己判断;True = 人点了用 AI 扩;False = 人点了不用 AI(切头顶)。"""
        return (self.d.get(self._vkey(video, title)) or {}).get("ai235")

    def set_ai235(self, video: str, on, title: str = ""):
        self._move(video, title)
        self.d.setdefault(video, {})["ai235"] = on
        self._save()

    def own_cover(self, video: str) -> str:
        """人在「封面预览」里自己换的封面(用户 2026-10-16:配错了「我自己去添加」);没换过给 ""。"""
        return str((self.d.get(video) or {}).get("own_cover") or "")

    def set_own_cover(self, video: str, path: str):
        """换成人选的图;path 空 = 用回软件自动配的。手动拖过的框跟着作废(图换了)。"""
        e = self.d.setdefault(video, {})
        e.pop("manual", None)
        if path:
            e["own_cover"] = path
        else:
            e.pop("own_cover", None)
        self._save()

    def use_own(self, v) -> bool:
        """自动配封面之前:人换过封面、那张图还在 → 用人选的(只有这一张,竖的比例也从它裁)。"""
        if not hasattr(v, "auto_png"):                # 记下自动配的(「用回自动配的」用)
            v.auto_png, v.auto_vpng = v.png, v.vpng
        p = self.own_cover(v.path)
        if p and os.path.isfile(p):
            v.png, v.vpng = p, ""
            return True
        v.png, v.vpng = v.auto_png, v.auto_vpng
        return False

    def reset(self, video: str):
        """恢复自动:手动拖过的框都不要了(人自己换的封面留着,要换回去点「用回自动配的」)。"""
        if video in self.d:
            own = self.d[video].get("own_cover")
            del self.d[video]
            if own:
                self.d[video] = {"own_cover": own}
            self._save()

    def set_ok(self, video: str, cover: str, title: str = ""):
        """人点了「封面都看过了」:这张封面现在这样就行,不再标黄(换了封面图就不算了,又会标黄)。"""
        self._move(video, title)
        self.d.setdefault(video, {})["ok"] = cover
        self._save()

    def is_ok(self, video: str, cover: str, title: str = "") -> bool:
        ok = (self.d.get(self._vkey(video, title)) or {}).get("ok")
        return bool(cover) and bool(ok) and (ok == cover or self._base(ok) == self._base(cover))

    def apply(self, v) -> None:
        """自动定完封面以后,把人调过的套上去。"""
        if v.warn and self.is_ok(v.path, v.cover, v.title):
            v.warn = False
            if "人看过" not in v.cover_why:
                v.cover_why += "(人看过了)"
        ai = self.ai235(v.path, v.title)
        if ai is not None and v.plan is not None:
            v.plan = dict(v.plan, ai235=bool(ai), no_ai=not ai)
        if getattr(v, "vcover", ""):
            vm = self.manual(v.path, v.vcover, v.title)
            if vm:
                v.vplan = dict(v.vplan or {}, manual=vm)
        man = self.manual(v.path, v.cover, v.title) if v.cover else {}
        if man:
            v.plan = dict(v.plan or {}, manual=man)
            v.warn = False
            if "手动" not in v.cover_why:
                v.cover_why += "(框手动调过)"

    def touched(self, v) -> bool:
        return bool(self.manual(v.path, v.cover, v.title))
