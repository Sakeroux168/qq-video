"""设置和数据放哪。

数据(设置、发布记录)放在 %LOCALAPPDATA%\\企鹅号发布助手;测试时用环境变量 QE_DATA_DIR 指到临时目录。
时间一律按北京时间算(这台电脑的 Windows 时区会自己跳成美国时间,不能信本地时间)。
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_NAME = "企鹅号发布助手"
APP_VERSION = 1
BJ = timezone(timedelta(hours=8))


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    d = os.environ.get("QE_DATA_DIR", "").strip()
    p = Path(d) if d else Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def bj_now() -> datetime:
    return datetime.now(BJ)


def bj_str(dt: datetime | None = None) -> str:
    return (dt or bj_now()).strftime("%Y-%m-%d %H:%M:%S")


def model_file() -> str:
    for p in (app_dir() / "models" / "face_detection_yunet_2023mar.onnx",
              app_dir() / "_internal" / "models" / "face_detection_yunet_2023mar.onnx"):
        if p.is_file():
            return str(p)
    return ""


DEFAULTS = {
    "material_root": r"X:\知乎视频\小学生教育",
    # 一天发完挪到哪:{month} = 日期文件夹的月份(10.15 → 10)
    "archive_root": r"X:\知乎视频\内容查看\{month}月发布视频\企鹅号\教育",
    # 号 → 日期文件夹下面的缩写(10.14 叫「研习社」,10.15 叫「研习空间」)
    "accounts": [
        {"name": "家长研习空间", "aliases": ["研习空间", "研习社"]},
        {"name": "家长小天地", "aliases": ["小天地"]},
    ],
    "batch_size": 10,          # 企鹅号一次最多传 10 条
    "ai_key": "",              # 阿里百炼 Key(2.35:1 AI 扩图用);空着就用百家号发布助手里填的
    "last_date": "",
}


class Settings(dict):
    def __init__(self, path: Path | None = None):
        super().__init__()
        self.path = Path(path) if path else data_dir() / "设置.json"
        self.update(json.loads(json.dumps(DEFAULTS)))
        try:
            self.update(json.loads(self.path.read_text("utf-8")))
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(dict(self), ensure_ascii=False, indent=1), "utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def ai_key(self) -> str:
        k = str(self.get("ai_key") or "").strip()
        if k:
            return k
        try:                                   # 百家号发布助手的设置(这台电脑上用户填过阿里百炼 Key)
            ptr = Path(os.environ.get("APPDATA") or "") / "百家号发布助手2" / "location.json"
            root = json.loads(ptr.read_text("utf-8")).get("data_root") or ""
            d = json.loads((Path(root) / "data" / "settings.json").read_text("utf-8"))
            return str(d.get("bailian_api_key") or "").strip()
        except Exception:
            return ""

    def account_names(self) -> list[str]:
        return [a["name"] for a in self.get("accounts") or [] if a.get("name")]

    def aliases_of(self, name: str) -> list[str]:
        for a in self.get("accounts") or []:
            if a.get("name") == name:
                return [name] + [x for x in a.get("aliases") or [] if x]
        return [name]
