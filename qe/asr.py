"""本地语音转文字(查口播广告用):sherpa-onnx + SenseVoice,和 ainame / 百家号发布助手用的同一个模型,
直接用它们下载好的文件(%APPDATA%\\ainame\\models\\sense-voice)。

比百家号那边准:SenseVoice 每个字都带时间(token timestamps),按标点切成一句一句,每句知道几秒到几秒
(百家号那边按 25 秒一段估,误差好几秒)→ 剪广告能剪在那句话前后。
结果按 路径 + 大小 + 修改时间 记在 数据目录\\语音转写.sqlite,同一个文件不转第二遍。
"""
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

from .config import data_dir

_NOWIN = 0x08000000 | 0x00004000 if os.name == "nt" else 0
MODEL_FILES = ("model.int8.onnx", "tokens.txt")
CHUNK_SEC = 25.0                  # SenseVoice 是在 30 秒以内的句子上训练的,长音频按 25 秒切
MAX_SEC = 900                     # 最多转前 15 分钟
_PUNCT = set("，。！？；、,.!?;…~")


def model_dir() -> str:
    for d in (data_dir() / "models" / "sense-voice",
              Path(os.environ.get("APPDATA", "")) / "ainame" / "models" / "sense-voice"):
        if all((d / f).is_file() for f in MODEL_FILES):
            return str(d)
    return ""


def _wav(ffmpeg: str, video: str, out: str) -> bool:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
           "-t", str(MAX_SEC), "-f", "wav", out]
    try:
        subprocess.run(cmd, capture_output=True, timeout=600, creationflags=_NOWIN)
    except (OSError, subprocess.SubprocessError):
        return False
    return os.path.isfile(out) and os.path.getsize(out) > 1000


def sentences(tokens: list[str], stamps: list[float], offset: float = 0.0) -> list[dict]:
    """一个字一个时间 → 按标点切成句子 [{"start","end","text"}](秒)。"""
    out, cur, t0, last = [], "", None, 0.0
    for tok, t in zip(tokens, stamps):
        if t0 is None and tok.strip() and tok not in _PUNCT:
            t0 = t
        cur += tok
        last = t
        if tok in _PUNCT and cur.strip(" " + "".join(_PUNCT)):
            out.append({"start": round(offset + (t0 or t), 2), "end": round(offset + t + 0.2, 2), "text": cur.strip()})
            cur, t0 = "", None
    if cur.strip(" " + "".join(_PUNCT)):
        out.append({"start": round(offset + (t0 if t0 is not None else last), 2), "end": round(offset + last + 0.4, 2),
                    "text": cur.strip()})
    return out


class Transcriber:
    """线程安全;第一次用时才加载模型(一两秒)。"""

    def __init__(self, ffmpeg: str, threads: int = 4):
        self.ffmpeg = ffmpeg
        self.dir = model_dir()
        self.threads = threads
        self._rec = None
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(data_dir() / "语音转写.sqlite"), check_same_thread=False, timeout=30)
        self._db.execute("CREATE TABLE IF NOT EXISTS t(key TEXT PRIMARY KEY, sents TEXT, ts REAL)")
        self._db.commit()
        self._dblock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self.dir)

    @staticmethod
    def _key(path: str) -> str:
        try:
            s = os.stat(path)
            return f"{os.path.normcase(os.path.abspath(path))}|{s.st_size}|{int(s.st_mtime)}"
        except OSError:
            return os.path.normcase(os.path.abspath(path))

    def cached(self, path: str) -> list[dict] | None:
        with self._dblock:
            r = self._db.execute("SELECT sents FROM t WHERE key=?", (self._key(path),)).fetchone()
        if r:
            try:
                return json.loads(r[0] or "[]")
            except ValueError:
                return []
        return None

    def _recognizer(self):
        if self._rec is None:
            import sherpa_onnx
            self._rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=os.path.join(self.dir, "model.int8.onnx"), tokens=os.path.join(self.dir, "tokens.txt"),
                num_threads=int(self.threads), use_itn=True, language="auto", debug=False)
        return self._rec

    def transcribe(self, path: str, stop=None) -> list[dict]:
        """一句一句:[{"start","end","text"}];没人说话给 []。模型没装抛 RuntimeError。"""
        hit = self.cached(path)
        if hit is not None:
            return hit
        if not self.available:
            raise RuntimeError("没有语音识别模型(ainame 的 sense-voice)")
        import numpy as np
        tmp = os.path.join(tempfile.gettempdir(), f"qe_asr_{os.getpid()}_{threading.get_ident()}.wav")
        try:
            if not _wav(self.ffmpeg, path, tmp):
                samples = None
            else:
                with wave.open(tmp, "rb") as w:
                    samples = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        sents: list[dict] = []
        if samples is not None and len(samples):
            step = int(CHUNK_SEC * 16000)
            with self._lock:
                rec = self._recognizer()
                for s0 in range(0, len(samples), step):
                    if stop and stop():
                        return []                      # 停了:不记(下次重转)
                    st = rec.create_stream()
                    st.accept_waveform(16000, samples[s0:s0 + step])
                    rec.decode_stream(st)
                    r = st.result
                    toks, stamps = list(getattr(r, "tokens", []) or []), list(getattr(r, "timestamps", []) or [])
                    if toks and len(toks) == len(stamps):
                        sents += sentences(toks, stamps, s0 / 16000.0)
                    elif (r.text or "").strip():         # 老版本没有每个字的时间:整段算一句
                        sents.append({"start": s0 / 16000.0, "end": min(len(samples), s0 + step) / 16000.0,
                                      "text": r.text.strip()})
        with self._dblock:
            self._db.execute("INSERT OR REPLACE INTO t(key, sents, ts) VALUES(?,?,?)",
                             (self._key(path), json.dumps(sents, ensure_ascii=False), time.time()))
            self._db.commit()
        return sents


_shared: dict = {}
_shared_lock = threading.Lock()


def shared(ffmpeg: str) -> Transcriber:
    """整个软件共用一个(模型只加载一次)。"""
    with _shared_lock:
        t = _shared.get(ffmpeg)
        if t is None:
            t = _shared[ffmpeg] = Transcriber(ffmpeg)
        return t
