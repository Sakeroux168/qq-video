"""人在「封面预览」里手动调过的:用横还是竖、每个比例的框放哪。存在数据目录的 封面调整.json,关了软件再开还在。

{视频路径: {"kind": "横"/"竖", "manual": {封面图路径: {"0.750": [框中心 x 占图几成, y], ...}}}}
(框的位置跟着封面图走:横的、竖的各记各的)
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

    def kind(self, video: str) -> str:
        return (self.d.get(video) or {}).get("kind", "")

    def manual(self, video: str, cover: str) -> dict:
        return dict(((self.d.get(video) or {}).get("manual") or {}).get(cover) or {})

    def set_kind(self, video: str, kind: str):
        self.d.setdefault(video, {})["kind"] = kind
        self._save()

    def set_box(self, video: str, cover: str, rkey: str, cx: float, cy: float):
        self.d.setdefault(video, {}).setdefault("manual", {}).setdefault(cover, {})[rkey] = [round(cx, 4), round(cy, 4)]
        self._save()

    def reset(self, video: str):
        """恢复自动:横竖和框的位置都不要了。"""
        if video in self.d:
            del self.d[video]
            self._save()

    def apply(self, v) -> None:
        """自动定完封面以后,把人调过的套上去。"""
        from . import cover as C
        k = self.kind(v.path)
        if k and k != v.cover_kind:
            C.set_kind(v, k)
        if k:
            v.cover_why = f"手动选的{k}封面"
        man = self.manual(v.path, v.cover)
        if man:
            v.plan = dict(v.plan or {}, manual=man)
            v.warn = False
            if "手动" not in v.cover_why:
                v.cover_why += "(框手动调过)"

    def touched(self, v) -> bool:
        return bool(self.kind(v.path) or self.manual(v.path, v.cover))
