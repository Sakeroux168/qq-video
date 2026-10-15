"""人在「封面预览」里手动拖过的框放哪。存在数据目录的 封面调整.json,关了软件再开还在。

{视频路径: {"manual": {封面图路径: {"0.750": [框中心 x 占图几成, y], ...}}}}
(以前还记「用横还是竖」,组长说 jpg 有字不能用以后只用 png,横竖不再记)
"""
import json
import os
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

    def manual(self, video: str, cover: str) -> dict:
        return dict(((self.d.get(video) or {}).get("manual") or {}).get(cover) or {})

    def set_box(self, video: str, cover: str, rkey: str, cx: float, cy: float):
        self.d.setdefault(video, {}).setdefault("manual", {}).setdefault(cover, {})[rkey] = [round(cx, 4), round(cy, 4)]
        self._save()

    def ai235(self, video: str):
        """None = 按软件自己判断;True = 人点了用 AI 扩;False = 人点了不用 AI(切头顶)。"""
        return (self.d.get(video) or {}).get("ai235")

    def set_ai235(self, video: str, on):
        self.d.setdefault(video, {})["ai235"] = on
        self._save()

    def reset(self, video: str):
        """恢复自动:手动拖过的框都不要了。"""
        if video in self.d:
            del self.d[video]
            self._save()

    def apply(self, v) -> None:
        """自动定完封面以后,把人调过的套上去。"""
        ai = self.ai235(v.path)
        if ai is not None and v.plan is not None:
            v.plan = dict(v.plan, ai235=bool(ai), no_ai=not ai)
        if getattr(v, "vcover", ""):
            vm = self.manual(v.path, v.vcover)
            if vm:
                v.vplan = dict(v.vplan or {}, manual=vm)
        man = self.manual(v.path, v.cover) if v.cover else {}
        if man:
            v.plan = dict(v.plan or {}, manual=man)
            v.warn = False
            if "手动" not in v.cover_why:
                v.cover_why += "(框手动调过)"

    def touched(self, v) -> bool:
        return bool(self.manual(v.path, v.cover))
