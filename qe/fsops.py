"""挪文件一律走这里,不用 shutil.move(2026-10-15 审查:shutil.move 跨盘时先整份复制再删,删到一半被占着就两边各一份,
重试合并后归档里一堆「(2)」;百家号发布助手2 第56版吃过同一个亏)。

- 同一个盘:os.replace,一步到位,要么挪了要么没挪。
- 跨盘(X: → Z: 这种不同共享):逐个文件 复制 → 核对大小 → 删原文件;原文件删不掉就把刚复制的删掉,当没挪。
- 被占着(别的程序开着):等 2 秒再试一次,还不行报「某某文件被占着,关掉再挪」。
"""
import errno
import os
import shutil
import time


class MoveError(OSError):
    """挪不动:消息是给人看的大白话。"""


def _busy_name(path: str) -> str:
    return os.path.basename(path) or path


def _replace(src: str, dst: str):
    for k in range(2):
        try:
            os.rename(src, dst)                       # 不用 os.replace:检查完到挪之间目标被建出来也不会被盖掉
            return
        except PermissionError:
            if k:
                raise MoveError(f"「{_busy_name(src)}」被别的程序占着(播放器 / 资源管理器预览 / 别的软件?),关掉再挪")
            time.sleep(2)


def _cross_device(e: OSError) -> bool:
    return e.errno == errno.EXDEV or getattr(e, "winerror", None) == 17


def safe_move_file(src: str, dst: str) -> str:
    """挪一个文件到 dst(dst 已存在就报错,不覆盖)。返回 dst。"""
    if os.path.exists(dst):
        raise MoveError(f"目标已经有「{_busy_name(dst)}」了,不覆盖")
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    try:
        _replace(src, dst)
        return dst
    except FileExistsError:
        raise MoveError(f"目标已经有「{_busy_name(dst)}」了,不覆盖")
    except MoveError:
        raise
    except OSError as e:
        if not _cross_device(e):
            raise MoveError(f"「{_busy_name(src)}」挪不动:{e.strerror or e}")
    # 跨盘:复制 → 核对 → 删原文件
    try:
        shutil.copy2(src, dst)
        if os.path.getsize(src) != os.path.getsize(dst):
            raise MoveError(f"「{_busy_name(src)}」复制过去大小不对,没挪")
    except Exception:
        try:
            os.remove(dst)
        except OSError:
            pass
        raise
    for k in range(2):
        try:
            os.remove(src)
            return dst
        except PermissionError:
            if k:
                os.remove(dst)                     # 原文件删不掉:把复制的删掉,当没挪(不留两份)
                raise MoveError(f"「{_busy_name(src)}」被别的程序占着,关掉再挪(这条没挪)")
            time.sleep(2)
    return dst


def unique(path: str) -> str:
    """path 已存在就加 (2)(3)…"""
    if not os.path.exists(path):
        return path
    d, n = os.path.split(path)
    stem, ext = os.path.splitext(n)
    k = 2
    while True:
        p = os.path.join(d, f"{stem} ({k}){ext}")
        if not os.path.exists(p):
            return p
        k += 1


def move_tree(src: str, dst: str, on_file=None) -> tuple[int, list[str]]:
    """把文件夹 src 里的东西挪进 dst(dst 可以已存在:同名文件不覆盖,改名加 (2))。
    一个文件一个文件挪,挪不动的留在原处并记下来,不会两边各一份。挪空的文件夹删掉。
    返回 (挪了几个文件, 挪不动的原因列表)。"""
    moved, errs = 0, []
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return 0, []
    # 同一个盘、目标还不存在:整个文件夹一步改路径
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        try:
            os.replace(src, dst)
            return sum(len(f) for _r, _d, f in os.walk(dst)), []
        except OSError:
            pass                                   # 跨盘 / 被占着:下面逐个文件挪
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tdir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(tdir, exist_ok=True)
        for n in files:
            s = os.path.join(root, n)
            try:
                safe_move_file(s, unique(os.path.join(tdir, n)))
                moved += 1
                if on_file:
                    on_file(moved)
            except OSError as e:
                errs.append(str(e))
    for root, _dirs, _files in os.walk(src, topdown=False):  # 挪空了的文件夹删掉
        try:
            os.rmdir(root)
        except OSError:
            pass
    return moved, errs
