"""后台查清晰度(qe/sharp.py):两个发布页共用。查过、文件没变的不再查;读不出来的跳过,下次再查。"""
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Signal

from qe import sharp, vertical


class SharpWorker(QThread):
    one = Signal(int)

    def __init__(self, videos, rows, parent=None):
        super().__init__(parent)
        self.videos, self.rows = videos, rows
        self.stop = False
        self.n_bad = 0

    def _dur(self, v, ff: str) -> float:
        d = (getattr(v, "checks", None) or {}).get("dur")
        return float(d or vertical.probe(v.path, ff).get("dur") or 0)

    def run(self):
        ff = vertical.ffmpeg_path()

        def one(i):
            if self.stop:
                return
            v = self.videos[i]
            got = sharp.STORE.get(v.path)
            if got is None:
                try:
                    got = sharp.STORE.put(v.path, sharp.check(v.path, ff, self._dur(v, ff) or 1, stop=lambda: self.stop))
                except Exception:
                    return
            v.sharp = got
            if sharp.flagged(got):
                self.n_bad += 1
            self.one.emit(i)
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(one, self.rows))
