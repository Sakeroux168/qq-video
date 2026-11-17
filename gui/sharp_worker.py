"""后台查清晰度(qe/sharp.py)、字幕被裁(qe/cropcheck.py)和结尾求关注(qe/outrocheck.py):两个发布页共用。
查过、文件没变的不再查;读不出来的跳过,下次再查。
force = 人点「重新检查」的那些路径:不管查没查过都再查一遍(页面和这里共用同一个 set,查完一条划掉一条;中途被别的活打断,剩下的接着查)。"""
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Signal

from qe import aierr, cropcheck, outrocheck, sharp, vertical, wmstore


class SharpWorker(QThread):
    one = Signal(int)

    def __init__(self, videos, rows, parent=None, want_sharp: bool = True, crop_key: str = "", need_crop=None, asker=None,
                 force=None, can_crop=None, outro_key="", need_outro=None, outro_asker=None, outro_shot_dir: str = "", skip=None):
        """crop_key / outro_key = AI(空 = 不查);need_crop / need_outro(v) = 这条要不要查;can_crop(v) = 这种号查不查(重新检查时看);
        asker / outro_asker:测试里换掉,绝不真问 AI;skip(v):这会儿这个号正忙别的事,先跳过它。"""
        super().__init__(parent)
        self.videos, self.rows = videos, rows
        self.want_sharp, self.crop_key, self.need_crop, self.asker = want_sharp, crop_key, need_crop or (lambda v: False), asker
        self.outro_key, self.need_outro, self.outro_asker = outro_key, need_outro or (lambda v: False), outro_asker
        self.outro_shot_dir = outro_shot_dir
        self.force = force if force is not None else set()
        self.can_crop = can_crop or (lambda v: True)
        self.skip = skip or (lambda _v: False)
        self.left = {videos[i].path for i in rows}       # 还没查完的(表格写「查中」)
        self.stop = False
        self.n_bad = 0
        self.n_crop = 0
        self.n_outro = 0
        self.errors: list[str] = []
        self.outro_errors: list[str] = []

    def _dur(self, v, ff: str) -> float:
        d = (getattr(v, "checks", None) or {}).get("dur")
        return float(d or vertical.probe(v.path, ff).get("dur") or 0) or 1

    def _sharp(self, v, ff: str, force: bool) -> bool:
        got = None if force else sharp.STORE.get(v.path)
        if got is None:
            try:
                got = sharp.STORE.put(v.path, sharp.check(v.path, ff, self._dur(v, ff), stop=lambda: self.stop))
            except Exception:
                v.sharp_err = not self.stop              # 被打断的不算没查成
                return False
        v.sharp, v.sharp_err = got, False
        self.n_bad += sharp.flagged(got)
        return True

    def _crop(self, v, ff: str, force: bool) -> bool:
        got = None if force else wmstore.CROP.get(v.path)
        if got is None:
            try:
                got = wmstore.CROP.put(v.path, cropcheck.check(v.path, ff, self._dur(v, ff), self.crop_key, stop=lambda: self.stop, asker=self.asker))
            except RuntimeError as e:
                self.errors.append(str(e))
                v.crop_err = True
                if aierr.hard(e):                        # 欠费 / Key 不对:再问也没用,这一轮不再问 AI
                    self.crop_key = ""
                    self.outro_key = ""
                return False
            except Exception:
                v.crop_err = not self.stop
                return False
        v.crop, v.crop_err = got, False
        if getattr(v, "checks", None) is not None:
            v.checks["crop"] = got
        self.n_crop += wmstore.blocks(got)
        return True

    def _outro(self, v, ff: str, force: bool) -> bool:
        got = None if force else wmstore.OUTRO.get(v.path)
        if got is None:
            try:
                res = outrocheck.check(v.path, ff, self._dur(v, ff), self.outro_key, stop=lambda: self.stop,
                                       asker=self.outro_asker, shot_dir=self.outro_shot_dir)
                got = wmstore.OUTRO.put(v.path, res)
            except RuntimeError as e:
                self.outro_errors.append(str(e))
                v.outro_err = True
                if aierr.hard(e):
                    self.crop_key = ""
                    self.outro_key = ""
                return False
            except Exception:
                v.outro_err = not self.stop
                return False
        v.outro, v.outro_err = got, False
        if getattr(v, "checks", None) is not None:
            v.checks["outro"] = got
        self.n_outro += wmstore.blocks(got)
        return True

    def run(self):
        ff = vertical.ffmpeg_path()

        def one(i):
            if self.stop:
                return
            v = self.videos[i]
            if self.skip(v):
                self.left.discard(v.path)
                return
            force = v.path in self.force
            if self.want_sharp:
                self._sharp(v, ff, force)
            if self.crop_key and not self.stop and ((force and self.can_crop(v)) or self.need_crop(v)):
                self._crop(v, ff, force)
            if self.outro_key and not self.stop and (force or self.need_outro(v)):
                self._outro(v, ff, force)
            if not self.stop:                            # 被打断的留着:页面接着查
                self.force.discard(v.path)
                self.left.discard(v.path)
                self.one.emit(i)
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(one, self.rows))
