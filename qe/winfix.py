"""罐头窗口最小化了任务就不动(用户 2026-10-19)。

罐头是 Chrome 内核:窗口一最小化就当没人看,页面里的动画 / 计时器放慢甚至停掉,弹框、裁剪框出不来,软件就一直等。
这里:发现罐头被最小化 → 悄悄恢复成普通窗口(不抢正在用的窗口),放到所有窗口最后面。只在 Windows 上管用。"""
import ctypes
import os
import sys

EXE = "创作罐头.exe"
SW_SHOWNOACTIVATE = 4
HWND_BOTTOM = 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _exe_of(pid: int) -> str:
    k = ctypes.windll.kernel32
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.c_ulong(len(buf))
        if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value)
        return ""
    finally:
        k.CloseHandle(h)


def czgt_windows() -> list[int]:
    """罐头的主窗口(看得见、有标题的顶层窗口)。"""
    if sys.platform != "win32":
        return []
    from ctypes import wintypes
    u = ctypes.windll.user32
    out, exe = [], {}

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lp):
        if not u.IsWindowVisible(hwnd) or u.GetWindowTextLengthW(hwnd) == 0 or u.GetWindow(hwnd, 4):   # 4 = GW_OWNER:不要弹出的小窗
            return True
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in exe:
            exe[pid.value] = _exe_of(pid.value)
        if exe[pid.value].lower() == EXE.lower():
            out.append(int(hwnd))
        return True
    u.EnumWindows(cb, 0)
    return out


def unminimize() -> int:
    """罐头被最小化了:恢复成普通窗口(不抢焦点),放到最后面。返回恢复了几个窗口(没最小化 = 0)。"""
    if sys.platform != "win32" or os.environ.get("QE_NO_WINFIX"):     # 跑测试时不动真罐头的窗口
        return 0
    u = ctypes.windll.user32
    n = 0
    for hwnd in czgt_windows():
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
            u.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
            n += 1
    return n
