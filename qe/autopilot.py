"""16 个号（游戏 / 动漫）全链路自动驾驶引擎（用户 2026-11-27 拍板定稿）：

流程（严格受控，只在用户点「确认启动全自动」后执行）：
  ① 扫今日目录：自动识别今日标准日期夹（含 11.27未改比例 / 括号后缀 / 已手选夹），无今日夹的账号跳过并提醒；
  ② 发前检查：严格按设置里勾选的 6 项开关执行（未勾项彻底不跑也不拦），叠加防重发 / 违禁平台词 / 标题日期 / 坏片硬保护；
  ③ 自动预处理：横屏 / 偏方自动转竖屏（删原片）、标题 / 话题自动整理并记台账（可撤销）；
  ④ 自动发布：严格守住每日规定条数闸 + 原子防重发锁（支持局域网主机锁），命中勾选检查异常的视频一律跳过汇总，只发完全没问题的；
  ⑤ 发后闭环：发完立刻清理空夹与残留（.meowload / 结尾原片 / Thumbs.db / 残留封面）→ 去后台核对漏发 → 对「确定没发上(sure=True)」的自动拎回并最多自动补发 1 轮；
  ⑥ 封面收尾：扫描本次涉及账号的黑封面 / 模糊封面并自动导出清晰替代封面 → 生成简洁战报。
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from . import (
    aiconf, apiacc, apicover, apisrc, aplog, audiocheck, autocover, blackcover,
    checks, cropcheck, folder_intent as FI, folders, gamecheck, longcheck, omapi, omcover,
    outrocheck, plan, sharp, titleclean, titledate, topic, vertical, wmstore,
)
from .config import BJ, bj_now, bj_str, data_dir
from .lansync import LanError
from .records import pkey

CHECK_LABELS = [
    ("sharp_check", "视频模糊"),
    ("crop_check", "字幕被裁"),
    ("outro_check", "求关注结尾"),
    ("audio_check", "无声音检查"),
    ("long_check", "超过10分钟"),
    ("game_ai_check", "AI查串游戏"),
]


class _QuotaFull(Exception):
    pass


class _Taken(Exception):
    pass


_ACC_LOCK = threading.Lock()
_ACC_LISTENERS: list[Callable[[dict], None]] = []


def add_account_listener(fn: Callable[[dict], None]) -> None:
    """注册全自动单号实时状态监听器（用于看板每号一张卡片实时跳动）。"""
    with _ACC_LOCK:
        if fn not in _ACC_LISTENERS:
            _ACC_LISTENERS.append(fn)


def remove_account_listener(fn: Callable[[dict], None]) -> None:
    with _ACC_LOCK:
        try:
            _ACC_LISTENERS.remove(fn)
        except ValueError:
            pass


def _emit_acc(ev: dict, deps: dict | None = None) -> None:
    """向全局监听器与 deps['on_account_event'] 推送结构化单号状态事件。"""
    cb = (deps or {}).get("on_account_event")
    if cb is not None:
        try:
            cb(dict(ev))
        except Exception:
            pass
    with _ACC_LOCK:
        ls = list(_ACC_LISTENERS)
    for fn in ls:
        try:
            fn(dict(ev))
        except Exception:
            pass


def snapshot_accounts(
    st,
    rec,
    day: str = "",
    accounts: list[str] | None = None,
    watch: "WatchState | None" = None,
    deps: dict | None = None,
) -> list[dict[str, Any]]:
    """快速只读快照：返回所有已启用 16 个号今天的看板状态（平时空闲也能直接铺满 16 张卡）。"""
    deps = deps or {}
    prep = prepare(st, rec, day=day, accounts=accounts, deps=deps)
    day_iso = prep["day_iso"]
    sent_now = rec.sent_on(day_iso)
    ready_map = {x["account"]: x for x in prep.get("ready_accounts") or []}
    done_map = {x["account"]: x for x in prep.get("done_accounts") or []}
    wait_map: dict[str, list[dict]] = {}
    for wf in prep.get("waiting_folders") or []:
        wait_map.setdefault(wf["account"], []).append(wf)
    skip_set = set(watch.skip_accounts) if watch is not None else set()

    out: list[dict[str, Any]] = []
    for a in _load_enabled_api_accounts(deps):
        nick = str(a.get("nick") or "").strip()
        if not nick or not _match_nick_filter(nick, accounts):
            continue
        sent = int(sent_now.get(nick, 0))
        q = int(plan.quota_on(st, nick, day_iso) or 0)
        is_free = bool(st.get("quota_open", False) or plan.is_free(st, nick))
        if nick in skip_set:
            out.append({
                "account": nick, "status": "idle", "stage": "已跳过",
                "sent": sent, "target": (0 if is_free else q), "ready_count": 0,
                "detail": "已在本次值守中跳过", "skipped": 0, "outro_cut": 0, "failed": 0,
            })
        elif nick in done_map:
            t_val = q if q > 0 else sent
            out.append({
                "account": nick, "status": "done", "stage": "已发满",
                "sent": sent, "target": t_val, "ready_count": 0,
                "detail": f"今日已完成 {sent}/{t_val} 条", "skipped": 0, "outro_cut": 0, "failed": 0,
            })
        elif nick in ready_map:
            rinfo = ready_map[nick]
            rc = int(rinfo.get("to_send") or 0)
            t_val = (sent + rc) if (is_free or q <= 0) else q
            out.append({
                "account": nick, "status": "waiting", "stage": f"就绪 {rc} 条",
                "sent": sent, "target": max(t_val, sent + rc), "ready_count": rc,
                "detail": f"今日目录有 {rc} 条待发，随时可启动", "skipped": 0, "outro_cut": 0, "failed": 0,
            })
        elif nick in wait_map:
            wf0 = wait_map[nick][0]
            out.append({
                "account": nick, "status": "waiting", "stage": "等待素材",
                "sent": sent, "target": (0 if is_free else q), "ready_count": 0,
                "detail": f"等待「{wf0.get('folder_name', '')}」：{wf0.get('reason', '')}",
                "skipped": 0, "outro_cut": 0, "failed": 0,
            })
        else:
            out.append({
                "account": nick, "status": "idle", "stage": "无今日夹",
                "sent": sent, "target": (0 if is_free else q), "ready_count": 0,
                "detail": "今天素材文件夹还没放进来", "skipped": 0, "outro_cut": 0, "failed": 0,
            })
    return out


def check_summary(st) -> dict[str, Any]:
    """读取设置里 6 项自动检查开关状态。"""
    flags = {k: bool(st.get(k, True)) for k, _ in CHECK_LABELS}
    enabled = [lab for k, lab in CHECK_LABELS if flags[k]]
    disabled = [lab for k, lab in CHECK_LABELS if not flags[k]]
    return {"flags": flags, "enabled": enabled, "disabled": disabled}


def _match_nick_filter(nick: str, accounts_filter: list[str] | None) -> bool:
    if not accounts_filter:
        return True
    ws = [str(x or "").strip().casefold() for x in accounts_filter if str(x or "").strip()]
    if not ws:
        return True
    nl = nick.casefold()
    return any(w in nl or nl in w for w in ws)


def _day_to_md(day_iso: str) -> str:
    parts = (day_iso or "").split("-")
    if len(parts) == 3:
        try:
            return f"{int(parts[1])}.{int(parts[2])}"
        except ValueError:
            pass
    return apisrc.pub_day()


def _load_enabled_api_accounts(deps: dict | None = None) -> list[dict]:
    if deps and "api_accounts_fn" in deps:
        return list(deps["api_accounts_fn"]())
    return [a for a in apiacc.load() if a.get("enabled", True) and a.get("client_id") and a.get("secret")]


@dataclass
class WatchState:
    """全天自动值守会话状态（16 个号每 N 分钟巡检、数量等齐、指纹防重查、安静不刷屏）。"""
    day_iso: str
    md: str
    active: bool = True
    interval_min: int = 10
    cutoff_hm: str = "22:30"
    min_stable_sec: float = 30.0
    accounts_filter: list[str] = field(default_factory=list)
    skip_accounts: set[str] = field(default_factory=set)
    extra_folders: dict[str, list[str]] = field(default_factory=dict)
    count_tracker: dict[str, tuple[int, int]] = field(default_factory=dict)
    skipped_fingerprints: dict[str, tuple[int, int]] = field(default_factory=dict)
    reported_undated: set[str] = field(default_factory=set)
    key_alerted: set[str] = field(default_factory=set)
    rounds: int = 0
    last_tick_at: str = ""
    total_published: int = 0
    total_retried: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_cleaned: int = 0
    waiting_summary: list[dict[str, Any]] = field(default_factory=list)
    undated_summary: list[dict[str, Any]] = field(default_factory=list)
    recent_notes: list[str] = field(default_factory=list)

    def skip_account(self, nick: str, on: bool = True) -> None:
        if on:
            self.skip_accounts.add(nick)
        else:
            self.skip_accounts.discard(nick)

    def add_extra_folder(self, nick: str, folder_path: str) -> bool:
        norm = os.path.normpath(folder_path)
        lst = self.extra_folders.setdefault(nick, [])
        if any(os.path.normcase(x) == os.path.normcase(norm) for x in lst):
            return False
        lst.append(norm)
        return True

    def set_interval(self, minutes: int) -> int:
        self.interval_min = max(1, min(60, int(minutes)))
        return self.interval_min

    def record_note(self, text: str) -> None:
        if text:
            self.recent_notes.append(text)
            if len(self.recent_notes) > 30:
                self.recent_notes = self.recent_notes[-30:]

    def snapshot(self, st, rec) -> dict[str, Any]:
        sent = rec.sent_on(self.day_iso)
        s = plan.summary(rec, st, self.day_iso)
        api_q = sum(q for cat, n, q, _a in s["accounts"] if cat in plan.API_CATS and n not in (s.get("free") or []))
        api_a = sum(a for cat, n, _q, a in s["accounts"] if cat in plan.API_CATS and n not in (s.get("free") or []))
        return {
            "active": self.active,
            "day_iso": self.day_iso,
            "md": self.md,
            "interval_min": self.interval_min,
            "cutoff_hm": self.cutoff_hm,
            "rounds": self.rounds,
            "last_tick_at": self.last_tick_at,
            "api_sent": api_a,
            "api_quota": api_q,
            "total_published": self.total_published,
            "total_retried": self.total_retried,
            "total_skipped": self.total_skipped,
            "skip_accounts": sorted(self.skip_accounts),
            "extra_folders": {k: list(v) for k, v in self.extra_folders.items() if v},
            "waiting": list(self.waiting_summary),
            "undated": list(self.undated_summary),
            "sent_by_account": sent,
        }


def _file_fp(path: str) -> tuple[int, int] | None:
    try:
        s = os.stat(path)
        return (int(s.st_size), int(s.st_mtime))
    except OSError:
        return None


def _scan_smart_folders(
    st,
    rec,
    accs: list[dict],
    md: str,
    day_iso: str,
    watch: WatchState | None = None,
    check_stability: bool = False,
    deps: dict | None = None,
) -> dict[str, Any]:
    """结合文件夹备注理解引擎（规则+AI缓存）、落稳检测与数量标注，扫描今日所有待发/等待/无日期变动文件夹。"""
    deps = deps or {}
    roots = list(st.get("api_roots") or apisrc.DEFAULT_ROOTS)
    picked = dict((st.get("api_picked") or {}).get(md) or {})
    nicks = [str(a.get("nick") or "") for a in accs]
    known = set(nicks) if nicks else None
    acc_dirs_map = apisrc.account_folder_list(roots, known) if nicks else {}
    sent_today = rec.sent_on(day_iso)
    now_ts = deps.get("now_ts")
    min_age = watch.min_stable_sec if watch is not None else 0.0
    ask_fn = deps.get("remark_ask_fn")

    ready_videos: list[apisrc.ApiVideo] = []
    ready_by_nick: dict[str, list[apisrc.ApiVideo]] = {}
    waiting_folders: list[dict[str, Any]] = []
    undated_discovered: list[dict[str, Any]] = []
    count_notes: list[str] = []
    done_accounts: list[dict[str, Any]] = []
    missing_accounts: list[str] = []

    for a in accs:
        nick = str(a.get("nick") or "")
        if watch is not None and nick in watch.skip_accounts:
            continue
        left = plan.left_today(rec, st, nick, day=day_iso, sent=sent_today)
        if left == 0:
            done_accounts.append({"account": nick, "sent": sent_today.get(nick, 0), "quota": plan.quota_on(st, nick, day_iso)})
            continue

        # 收集这个号今天的候选文件夹：(path, is_explicit, intent_dict)
        cand_dirs: list[tuple[str, bool, dict[str, Any]]] = []
        seen_dir_keys: set[str] = set()

        def _add_dir(p: str, explicit: bool, intent: dict[str, Any]):
            if not p or not os.path.isdir(p):
                return
            k = os.path.normcase(os.path.abspath(p))
            if k in seen_dir_keys:
                return
            seen_dir_keys.add(k)
            cand_dirs.append((p, explicit, intent))

        pk = picked.get(nick)
        if pk:
            _add_dir(pk, True, {"action": "ready", "expected_count": None, "reason": "已手选文件夹", "source": "rule"})
        if watch is not None:
            for ep in watch.extra_folders.get(nick) or []:
                _add_dir(ep, True, {"action": "ready", "expected_count": None, "reason": "已加入今日值守", "source": "rule"})

        if not pk:
            try:
                is_sunday = (datetime.strptime(day_iso, "%Y-%m-%d").weekday() == 6)
            except ValueError:
                is_sunday = False
            for acc_dir in acc_dirs_map.get(nick) or []:
                for sub in sorted(apisrc._subdirs(acc_dir)):
                    sp = os.path.join(acc_dir, sub)
                    sub_md, _rem = FI.parse_date_and_remark(sub)
                    is_sun_dir, sun_rem = (False, "") if sub_md else FI.is_sunday_folder(sub)
                    if sub_md == md or (is_sun_dir and is_sunday):
                        if is_sun_dir and not sun_rem:
                            intent = {"action": "ready", "expected_count": None, "needs_vertical_hint": False,
                                      "priority": False, "reason": "星期天专用目录", "source": "rule"}
                        else:
                            intent = FI.interpret_folder(sub, st=st, ask_fn=ask_fn)
                        if intent["action"] == "ignore":
                            continue
                        if intent["action"] == "wait":
                            waiting_folders.append({
                                "account": nick, "folder_name": sub, "path": sp,
                                "reason": intent["reason"], "kind": "remark_wait",
                            })
                            continue
                        _add_dir(sp, False, intent)
                    elif is_sun_dir and not is_sunday:
                        # 工作室规矩：「周末 / 星期天 / 周日」留着星期天发，周六及平时静默跳过不误发也不打扰
                        continue
                    elif not sub_md and watch is not None:
                        # 检查不带日期的文件夹：绝不擅自发，但今天刚有新未发视频时静默提示 + 一键加入按钮
                        if apisrc.is_removable_subdir(sub) or any(w in sub for w in FI.IGNORE_WORDS):
                            continue
                        fk = os.path.normcase(os.path.abspath(sp))
                        if fk in seen_dir_keys or fk in watch.reported_undated:
                            continue
                        stab = FI.check_folder_stability(sp, min_age_sec=0.0, now=now_ts)
                        if not stab["video_paths"]:
                            continue
                        latest_day = datetime.fromtimestamp(stab["latest_mtime"], BJ).strftime("%Y-%m-%d") if stab["latest_mtime"] else ""
                        if latest_day != day_iso:
                            continue
                        unsent_cnt = 0
                        for vp in stab["video_paths"]:
                            try:
                                if not rec.blocked(vp):
                                    unsent_cnt += 1
                            except Exception:
                                unsent_cnt += 1
                        if unsent_cnt > 0:
                            undated_discovered.append({
                                "account": nick, "folder_name": sub, "path": sp, "video_count": unsent_cnt,
                            })

        # 时效性文件夹（如 11.28时效性）排最前优先发，防止超时过期
        cand_dirs.sort(key=lambda x: (0 if x[2].get("priority") else 1))

        acc_ready: list[apisrc.ApiVideo] = []
        acc_waiting = any(w["account"] == nick for w in waiting_folders)
        for d_path, is_explicit, intent in cand_dirs:
            sub_name = os.path.basename(d_path)
            stab = FI.check_folder_stability(d_path, min_age_sec=(min_age if check_stability else 0.0), now=now_ts)
            if check_stability and not stab["stable"]:
                waiting_folders.append({
                    "account": nick, "folder_name": sub_name, "path": d_path,
                    "reason": stab["reason"], "kind": "unstable",
                })
                acc_waiting = True
                continue

            # 过滤已发/阻塞的，以及值守期间已经拦过且文件没变化的异常片
            raw_vids = apisrc._videos_in(d_path, nick, md)
            pending_vids = []
            for v in raw_vids:
                try:
                    if rec.blocked(v.path):
                        continue
                except Exception:
                    pass
                if watch is not None:
                    fp_now = _file_fp(v.path)
                    if fp_now is not None and watch.skipped_fingerprints.get(pkey(v.path)) == fp_now:
                        continue
                pending_vids.append(v)

            if not pending_vids:
                continue

            # 数量标注检查（如 11.27(15)）：未凑够则继续巡检；连续 2 次巡检数量未涨则先行发布并提醒
            exp = intent.get("expected_count")
            if watch is not None and exp is not None and not is_explicit:
                actual_n = len(raw_vids)
                fk = os.path.normcase(os.path.abspath(d_path))
                if actual_n < exp:
                    prev_n, stag = watch.count_tracker.get(fk, (-1, 0))
                    if prev_n == actual_n:
                        stag += 1
                    else:
                        stag = 0
                    watch.count_tracker[fk] = (actual_n, stag)
                    if stag < 2:
                        waiting_folders.append({
                            "account": nick, "folder_name": sub_name, "path": d_path,
                            "reason": f"文件夹标明 {exp} 条，当前只有 {actual_n} 条（已等 {stag}/2 轮），继续等齐",
                            "kind": "count_wait",
                        })
                        acc_waiting = True
                        continue
                    count_notes.append(f"[{nick}] {sub_name} 标 {exp} 条实际 {actual_n} 条（连续 2 轮未涨，已先行处理）")
                    watch.count_tracker.pop(fk, None)
                else:
                    watch.count_tracker.pop(fk, None)

            acc_ready.extend(pending_vids)

        if acc_ready:
            ready_by_nick[nick] = acc_ready
            ready_videos.extend(acc_ready)
        elif not acc_waiting:
            missing_accounts.append(nick)

    return {
        "ready_videos": ready_videos,
        "ready_by_nick": ready_by_nick,
        "waiting_folders": waiting_folders,
        "undated_discovered": undated_discovered,
        "count_notes": count_notes,
        "done_accounts": done_accounts,
        "missing_accounts": missing_accounts,
        "sent_today": sent_today,
    }


def prepare(
    st,
    rec,
    day: str = "",
    accounts: list[str] | None = None,
    deps: dict | None = None,
) -> dict[str, Any]:
    """只读预演：快速扫描今天 16 个号待发情况（含备注理解，能识别「正在处理」等等待中目录），返回确认卡片数据。"""
    deps = deps or {}
    from .assistant import parse_day
    day_iso = parse_day(day, deps.get("today_fn"))
    md = _day_to_md(day_iso)

    accs = [a for a in _load_enabled_api_accounts(deps) if _match_nick_filter(str(a.get("nick") or ""), accounts)]
    scan = _scan_smart_folders(st, rec, accs, md, day_iso, watch=None, check_stability=False, deps=deps)
    sent_today = scan["sent_today"]

    ready_accounts = []
    total_estimated = 0
    for a in accs:
        nick = str(a.get("nick") or "")
        pending = scan["ready_by_nick"].get(nick) or []
        if not pending:
            continue
        left = plan.left_today(rec, st, nick, day=day_iso, sent=sent_today)
        est = min(len(pending), left) if left is not None else len(pending)
        folder_names = sorted({os.path.basename(v.folder) for v in pending if v.folder})
        ready_accounts.append({
            "account": nick,
            "folder_name": " / ".join(folder_names[:2]),
            "pending_count": len(pending),
            "quota_left": left,
            "estimated_run": est,
        })
        total_estimated += est

    chk = check_summary(st)
    # 即使此刻盘里还没到货，开启「全天值守」依然可以启动并等待同事放视频！
    has_unfilled = bool(ready_accounts or scan["waiting_folders"] or scan["missing_accounts"])
    return {
        "day_iso": day_iso,
        "md": md,
        "accounts_filter": list(accounts or []),
        "ready_accounts": ready_accounts,
        "waiting_folders": scan["waiting_folders"],
        "missing_accounts": scan["missing_accounts"],
        "done_accounts": scan["done_accounts"],
        "ready_count": len(ready_accounts),
        "total_estimated": total_estimated,
        "checks": chk,
        "can_start": bool(accs) and (total_estimated > 0 or has_unfilled),
        "can_start_once": total_estimated > 0,
        "reason_cannot_start": (
            "" if (bool(accs) and has_unfilled) else (
                "没有找到已启用的 16 个号账号。" if not accs else
                "今天所有 16 个号都已经发满规定条数啦 ✓"
            )
        ),
    }


def _clean_emptied_dirs(st, pub_dirs: dict[str, dict]) -> list[str]:
    """清理本次发布后已发空的日期 / 手选文件夹（含 .meowload / 结尾原片 / Thumbs.db / 残留封面）。"""
    roots = {os.path.normcase(os.path.abspath(r)) for r in (st.get("api_roots") or apisrc.DEFAULT_ROOTS)}
    acc_dirs = {
        os.path.normcase(os.path.abspath(p))
        for ps in apisrc.account_folder_list(st.get("api_roots") or apisrc.DEFAULT_ROOTS).values()
        for p in ps
    }
    picked = {
        os.path.normcase(os.path.abspath(p))
        for m in (st.get("api_picked") or {}).values()
        for p in (m or {}).values()
        if p
    }
    removed: list[str] = []
    for d, acc in list(pub_dirs.items()):
        key = os.path.normcase(os.path.abspath(d))
        if key in roots or key in acc_dirs or not os.path.isdir(d):
            continue
        if os.path.normcase(os.path.dirname(os.path.abspath(d))) in roots:
            continue
        if not (apisrc.date_key(os.path.basename(d)) or key in picked):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        paths = [os.path.join(d, x) for x in names]
        if any(os.path.splitext(x)[1].lower() in apisrc.VIDEO_EXTS and os.path.isfile(os.path.join(d, x)) for x in names):
            continue
        subdirs = [p for p in paths if os.path.isdir(p)]
        keep_sub = False
        for sp in subdirs:
            if apisrc.is_removable_subdir(os.path.basename(sp)):
                continue
            try:
                if os.listdir(sp):
                    keep_sub = True
                    break
            except OSError:
                keep_sub = True
                break
        if keep_sub:
            continue
        files = [p for p in paths if os.path.isfile(p)]
        rest = [p for p in files if not apisrc.is_junk_file(os.path.basename(p))]
        junk = [p for p in files if apisrc.is_junk_file(os.path.basename(p))]
        try:
            dest = apisrc.archive_dir(st, "", acc)
            for p in rest:
                plan.move_noclobber(p, dest)
            for p in junk:
                os.remove(p)
            for sp in subdirs:
                shutil.rmtree(sp)
            os.rmdir(d)
            removed.append(d)
        except OSError:
            continue
    return removed


def _check_video_issues(
    v: apisrc.ApiVideo,
    st,
    flags: dict[str, bool],
    ff: str,
    words,
    deps: dict,
    stopped: Callable[[], bool] | None,
) -> tuple[dict, list[str], bool, dict | None]:
    """对单条视频执行检查（严格按设置 6 项开关）。
    返回 (checks_dict, blocking_reasons, needs_vertical, outro_cut_plan)。
    横屏/偏方、话题格式、可安全剪切的头像片尾卡片都会走自动修复，不放进 blocking_reasons。"""
    check_one_fn = deps.get("check_one_fn", checks.check_one)
    c = check_one_fn(v, words, ff)
    v.checks = c
    reasons: list[str] = []

    if c.get("bad_read"):
        reasons.append("视频打不开/文件损坏")
        return c, reasons, False, None

    if c.get("platform"):
        reasons.append("标题含别的平台名(" + "/".join(c["platform"]) + ")")

    td = titledate.problem(v.account, v.title)
    if td:
        reasons.append(td)

    if wmstore.blocks(c.get("wm")):
        reasons.append("检测到水印")
    if wmstore.blocks(c.get("ads")):
        reasons.append("检测到口播广告")

    # 1) 超过 10 分钟（按设置 long_check）
    if flags.get("long_check", True):
        lp = longcheck.problem(v.account, v.title, c.get("dur"))
        if lp:
            reasons.append(f"超过10分钟({longcheck.fmt_dur(c.get('dur'))})")

    # 2) 视频模糊（按设置 sharp_check）
    if flags.get("sharp_check", True) and not (stopped and stopped()):
        s_res = sharp.STORE.get(v.path)
        if s_res is None:
            s_fn = deps.get("sharp_check_fn", sharp.check)
            try:
                s_res = sharp.STORE.put(v.path, s_fn(v.path, ff))
            except Exception:
                s_res = None
        if s_res and sharp.flagged(s_res):
            reasons.append("画面模糊")

    # 3) 字幕被裁（按设置 crop_check）
    if flags.get("crop_check", True) and not (stopped and stopped()):
        cr_res = wmstore.CROP.get(v.path)
        if cr_res is None and (deps.get("crop_check_fn") or aiconf.vision(st).key):
            cr_fn = deps.get("crop_check_fn", cropcheck.check)
            try:
                cr_res = wmstore.CROP.put(v.path, cr_fn(v.path, aiconf.vision(st), ff))
            except Exception:
                cr_res = None
        if cr_res and wmstore.blocks(cr_res):
            reasons.append("字幕被裁")

    # 4) 头像片尾卡片（按设置 outro_check；命中后交给阶段③自动剪掉并记录到战报抽检卡片组）
    outro_plan: dict | None = None
    if flags.get("outro_check", True) and not (stopped and stopped()):
        ou_res = wmstore.OUTRO.get(v.path)
        if ou_res is None and (deps.get("outro_check_fn") or aiconf.vision(st).key):
            ou_fn = deps.get("outro_check_fn", outrocheck.check)
            try:
                ou_res = wmstore.OUTRO.put(v.path, ou_fn(v.path, aiconf.vision(st), ff))
            except Exception:
                ou_res = None
        if ou_res and wmstore.blocks(ou_res):
            hits = list(ou_res.get("hits") or [])
            st_sec = float((hits[0] or {}).get("start") or 0) if hits else 0.0
            if st_sec >= 1.0:
                outro_plan = {
                    "start": st_sec,
                    "reason": str((hits[0] or {}).get("reason") or (hits[0] or {}).get("kind") or "头像片尾卡片"),
                    "shot": str(ou_res.get("shot") or ""),
                    "hits": hits,
                }
            else:
                reasons.append("结尾有头像片尾卡片(剪点太靠前，请人工确认)")

    # 5) 声音检查（按设置 audio_check）
    if flags.get("audio_check", True) and not (stopped and stopped()):
        au_res = audiocheck.STORE.get(v.path)
        if au_res is None:
            au_fn = deps.get("audio_check_fn", audiocheck.check)
            try:
                au_res = audiocheck.STORE.put(v.path, au_fn(v.path, ff, has_audio=c.get("has_audio"), dur=c.get("dur")))
            except Exception:
                au_res = None
        if au_res and audiocheck.flagged(au_res):
            reasons.append(audiocheck.text(au_res) or "没有声音")

    # 6) 串游戏本地关键词（标题里明明白白写了别的游戏名）
    gw = gamecheck.alien(v.account, v.title)
    if gw:
        reasons.append(f"标题像是《{gw}》的(串游戏)")

    needs_vert = bool(c.get("landscape") or c.get("squarish"))
    return c, reasons, needs_vert, outro_plan


def _publish_batch(
    st,
    rec,
    day_iso: str,
    accs_by_nick: dict[str, dict],
    videos_to_send: list[apisrc.ApiVideo],
    pub_dirs: dict[str, dict],
    on_progress: Callable[[str], None] | None,
    stopped: Callable[[], bool] | None,
    deps: dict,
    stage_prefix: str = "④/⑥ 自动发布",
    acc_state: dict[str, dict[str, Any]] | None = None,
    state_lock: threading.Lock | None = None,
) -> dict[str, Any]:
    """发一批已经通过检查与预处理的视频：
    严格按设置里的 api_threads（几个号一起发）与 api_per_acc（单号一次传几条，全局最多 6 路并发）并行发，
    并守住每日规定条数闸、原子防重发锁、单号发布间隔与致命密钥熔断。"""
    if not videos_to_send:
        return {"published": [], "failed": [], "unsure": [], "quota_skipped": [], "key_errors": []}

    gap = max(0, int(deps.get("api_interval", st.get("api_interval", 5)) or 0))
    par = max(1, int(deps.get("api_threads", st.get("api_threads", 1)) or 1))
    per_acc = max(1, int(deps.get("api_per_acc", st.get("api_per_acc", 1)) or 1))
    cmode = str(st.get("api_cover") or "原样")
    make_client = deps.get("make_client") or (lambda a: omapi.Client(a["client_id"], apiacc.unseal(a["secret"])))
    cover_upload_fn = deps.get("cover_upload_fn", omcover.upload)
    autocover_fn = deps.get("autocover_fn", autocover.pick)
    sleep_fn = deps.get("sleep_fn", time.sleep)
    stage_tag = stage_prefix.split(" ")[0] if " " in stage_prefix else "④发布"
    stage_short = "自动补发" if "补发" in stage_prefix else "发布中"

    # 按号分组保持原始顺序
    by_acc: dict[str, list[apisrc.ApiVideo]] = {}
    for v in videos_to_send:
        by_acc.setdefault(v.account, []).append(v)

    # 按号算上限（尊重 quota_open 与 quota_free）
    cap_of: dict[str, int | None] = {}
    for nick in by_acc:
        if st.get("quota_open", False) or plan.is_free(st, nick):
            cap_of[nick] = None
        else:
            q = plan.quota_on(st, nick, day_iso)
            cap_of[nick] = q if q else None

    published: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    unsure: list[dict[str, Any]] = []
    quota_skipped: list[dict[str, Any]] = []
    key_errors: list[dict[str, Any]] = []

    slock = state_lock or threading.Lock()
    upsem = threading.Semaphore(6)
    total = len(videos_to_send)
    started_cnt = [0]
    lan_broken = threading.Event()

    def _upd_acc(nick: str, **kw):
        if acc_state is None:
            return
        with slock:
            cur = acc_state.setdefault(nick, {
                "account": nick, "status": "running", "stage": stage_short,
                "sent": 0, "target": 0, "ready_count": 0, "detail": "",
                "skipped": 0, "outro_cut": 0, "failed": 0,
            })
            if "sent_delta" in kw:
                cur["sent"] = int(cur.get("sent") or 0) + int(kw.pop("sent_delta"))
            if "fail_delta" in kw:
                cur["failed"] = int(cur.get("failed") or 0) + int(kw.pop("fail_delta"))
            cur.update(kw)
            snap = dict(cur)
        _emit_acc(snap, deps)

    def _acc_job(nick: str, acc_vs: list[apisrc.ApiVideo]):
        if (stopped and stopped()) or lan_broken.is_set():
            return
        a = accs_by_nick.get(nick)
        if not a:
            with slock:
                for v in acc_vs:
                    failed.append({"account": nick, "title": v.title, "error": "找不到账号配置"})
            _upd_acc(nick, status="error", stage="配置异常", detail="找不到账号配置", fail_delta=len(acc_vs))
            return
        try:
            cat = int(a.get("category"))
        except (TypeError, ValueError):
            with slock:
                for v in acc_vs:
                    failed.append({"account": nick, "title": v.title, "error": f"账号分类无效({a.get('category')!r})"})
            _upd_acc(nick, status="error", stage="配置异常", detail="账号分类无效", fail_delta=len(acc_vs))
            return
        try:
            cl = make_client(a)
        except Exception as e:
            err_s = f"账号密钥初始化失败:{e}"
            with slock:
                for v in acc_vs:
                    failed.append({"account": nick, "title": v.title, "error": err_s})
                key_errors.append({"account": nick, "error": err_s})
            _upd_acc(nick, status="error", stage="密钥失效", detail=err_s[:50], fail_delta=len(acc_vs))
            return

        last_ts = [0.0]

        def _wait_gap() -> bool:
            if gap <= 0 or last_ts[0] <= 0:
                return True
            rem = (last_ts[0] + gap) - time.time()
            while rem > 0:
                if (stopped and stopped()) or lan_broken.is_set():
                    return False
                sleep_fn(min(0.25, rem))
                rem = (last_ts[0] + gap) - time.time()
            return not ((stopped and stopped()) or lan_broken.is_set())

        def _send_one(v: apisrc.ApiVideo) -> str:
            if (stopped and stopped()) or lan_broken.is_set():
                return "stop"
            try:
                if rec.blocked(v.path):
                    return "skip"
            except LanError as e:
                lan_broken.set()
                with slock:
                    failed.append({"account": nick, "title": v.title, "error": f"连不上局域网主机({e})"})
                _upd_acc(nick, status="error", stage="网络异常", detail=f"连不上局域网主机({e})", fail_delta=1)
                return "stop"

            left_now = plan.left_today(rec, st, nick, day=day_iso)
            if left_now == 0:
                with slock:
                    quota_skipped.append({"account": nick, "title": v.title})
                return "quota"

            with slock:
                started_cnt[0] += 1
                cur_idx = started_cnt[0]
            if on_progress:
                on_progress(f"{stage_prefix}（{cur_idx}/{total}）：[{nick}] {v.title[:22]}…")
            _upd_acc(nick, status="running", stage=stage_short, detail=f"正在上传：《{v.title[:22]}》")
            aplog.write(
                stage_tag,
                f"开始上传发布（{cur_idx}/{total}）：《{v.title}》",
                level="INFO", account=nick, day_iso=day_iso,
            )

            rid: dict[str, Any] = {}

            def begin(vid, _v=v, _rid=rid):
                got = rec.try_begin(_v, f"vid={vid}", day=day_iso, cap=cap_of.get(nick))
                if got == -1:
                    raise _QuotaFull()
                if got is None:
                    raise _Taken()
                _rid["id"] = got
                _rid["vid"] = vid

            src = apicover.find(v.path) if cmode != "不传" else ""
            if src and (blackcover.is_black(src) or blackcover.is_blurry(src)):
                src = ""
            auto_cov = False
            if not src and cmode != "不传":
                try:
                    src = autocover_fn(v.path) or ""
                    auto_cov = bool(src)
                except Exception:
                    src = ""
            try:
                cimg = apicover.prepare(src, cmode) if src else ""
            except Exception:
                cimg = ""

            try:
                def _sub_log(sub_msg: str, _nk=nick, _v=v):
                    s = str(sub_msg or "").strip()
                    if not s:
                        return
                    _upd_acc(_nk, status="running", stage=s[:8], detail=f"{s}：《{_v.title[:20]}》")

                r = cl.send(
                    v.path, v.title.strip(), cat,
                    stop=stopped, before_publish=begin, log=_sub_log,
                    cover=cimg, cover_upload=cover_upload_fn,
                )
            except omapi.Stopped:
                apicover.cleanup(cimg, src)
                return "stop"
            except _QuotaFull:
                apicover.cleanup(cimg, src)
                with slock:
                    quota_skipped.append({"account": nick, "title": v.title})
                return "quota"
            except LanError as e:
                apicover.cleanup(cimg, src)
                lan_broken.set()
                with slock:
                    failed.append({"account": nick, "title": v.title, "path": v.path, "error": f"连不上局域网主机({e})"})
                _upd_acc(nick, status="error", stage="网络异常", detail=f"连不上局域网主机({e})", fail_delta=1)
                return "stop"
            except _Taken:
                apicover.cleanup(cimg, src)
                return "skip"
            except omapi.Unknown as e:
                apicover.cleanup(cimg, src)
                keep = f"vid={rid['vid']};" if rid.get("vid") else ""
                if "id" in rid:
                    rec.api_finish(rid["id"], "结果不明", keep + str(e))
                else:
                    rec.api_result(v, "结果不明", keep + str(e))
                with slock:
                    unsure.append({"account": nick, "title": v.title, "path": v.path, "error": str(e)[:80]})
                aplog.write("④发布", f"结果不明：《{v.title}》—— {str(e)[:80]}", level="WARN", account=nick, day_iso=day_iso)
                _upd_acc(nick, detail=f"结果不明：《{v.title[:20]}》")
                return "unsure"
            except Exception as e:
                apicover.cleanup(cimg, src)
                raw = omapi.redact(str(e))
                if "id" in rid:
                    rec.api_finish(rid["id"], "没发成", raw)
                else:
                    rec.api_result(v, "没发成", raw)
                is_fatal = bool(getattr(e, "fatal", False))
                with slock:
                    failed.append({"account": nick, "title": v.title, "path": v.path, "error": raw[:80]})
                    if is_fatal:
                        key_errors.append({"account": nick, "error": raw[:100]})
                aplog.write(
                    "④发布",
                    f"{'密钥失效/' if is_fatal else ''}发布失败：《{v.title}》—— {raw[:100]}",
                    level="ERROR", account=nick, day_iso=day_iso,
                )
                if is_fatal:
                    _upd_acc(nick, status="error", stage="密钥失效", detail=f"密钥失效：{raw[:40]}", fail_delta=1)
                    return "fatal"
                _upd_acc(nick, detail=f"失败：《{v.title[:18]}》", fail_delta=1)
                return "fail"

            apicover.cleanup(cimg, src)
            note = (
                f"article_id={r.get('article_id', '')} vid={r.get('vid', '')}"
                + ("" if r.get("status") == "成功" else "(平台还在处理)")
                + (f";封面{r.get('cover')}" if r.get("cover") else "")
                + (";封面是软件自动挑的一帧" if auto_cov else "")
            )
            try:
                if "id" in rid:
                    rec.api_finish(rid["id"], "已发", note)
                else:
                    rec.api_result(v, "已发", note)
            except Exception as e:
                with slock:
                    unsure.append({"account": nick, "title": v.title, "error": f"已发但写库失败:{type(e).__name__}"})
                aplog.write("④发布", f"已发但写库失败：《{v.title}》—— {type(e).__name__}", level="ERROR", account=nick, day_iso=day_iso)
                return "unsure"

            try:
                old_dir = os.path.dirname(v.path)
                new_p = apisrc.move_published(v.path, apisrc.archive_dir(st, "", a))
                v.path = new_p
                with slock:
                    pub_dirs[old_dir] = a
                if "id" in rid:
                    rec.mark_moved(rid["id"], new_p)
            except OSError as e:
                aplog.write("④归档", f"视频已发但挪归档失败：《{v.title}》—— {e}", level="WARN", account=nick, day_iso=day_iso)

            with slock:
                published.append({"account": nick, "title": v.title, "path": v.path})
            aplog.write(
                stage_tag,
                f"发布成功：《{v.title}》（article_id={r.get('article_id', '')}）",
                level="OK", account=nick, day_iso=day_iso,
            )
            _upd_acc(nick, status="running", stage=stage_short, detail=f"已发：《{v.title[:22]}》", sent_delta=1)
            return "ok"

        def _send_sem(v: apisrc.ApiVideo) -> str:
            with upsem:
                return _send_one(v)

        pos = 0
        while pos < len(acc_vs):
            if (stopped and stopped()) or lan_broken.is_set():
                break
            left_acc = plan.left_today(rec, st, nick, day=day_iso)
            if left_acc == 0:
                with slock:
                    for rv in acc_vs[pos:]:
                        quota_skipped.append({"account": nick, "title": rv.title})
                break
            if pos > 0 and not _wait_gap():
                break
            gsize = per_acc if left_acc is None else min(per_acc, max(1, left_acc))
            grp = acc_vs[pos:pos + gsize]
            pos += len(grp)
            if len(grp) == 1:
                res_list = [_send_sem(grp[0])]
            else:
                with ThreadPoolExecutor(len(grp)) as gex:
                    res_list = list(gex.map(_send_sem, grp))
            last_ts[0] = time.time()
            if "fatal" in res_list or "stop" in res_list or "quota" in res_list:
                break

    workers = max(1, min(par, len(by_acc)))
    if workers == 1:
        for nk, avs in by_acc.items():
            _acc_job(nk, avs)
    else:
        with ThreadPoolExecutor(workers) as ex:
            futs = [ex.submit(_acc_job, nk, avs) for nk, avs in by_acc.items()]
            for f in futs:
                f.result()

    return {
        "published": published, "failed": failed, "unsure": unsure,
        "quota_skipped": quota_skipped, "key_errors": key_errors,
    }


def run(
    st,
    rec,
    day: str = "",
    accounts: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
    stopped: Callable[[], bool] | None = None,
    deps: dict | None = None,
    explicit_videos: list[apisrc.ApiVideo] | None = None,
    watch: WatchState | None = None,
    ignore_platform_words: bool = False,
) -> dict[str, Any]:
    """执行 16 个号全链路自动驾驶（6 阶段），返回结构化战报 dict。"""
    deps = deps or {}
    gamecheck.configure(st)
    longcheck.configure(st)
    chk = check_summary(st)
    flags = chk["flags"]

    if on_progress:
        on_progress("①/⑥ 正在扫描今日 16 个号目录与规定条数…")
    prep = prepare(st, rec, day=day, accounts=accounts, deps=deps)
    day_iso, md = prep["day_iso"], prep["md"]
    aplog.prune_old()
    aplog.write(
        "①扫描",
        f"开始全自动批次（{md}，已开检查：{'·'.join(chk['enabled']) or '无'}）",
        level="INFO", day_iso=day_iso,
    )

    accs_list = [a for a in _load_enabled_api_accounts(deps) if _match_nick_filter(str(a.get("nick") or ""), accounts)]
    accs_by_nick = {str(a.get("nick") or ""): a for a in accs_list}

    if explicit_videos is not None:
        cand_vs = list(explicit_videos)
        ready_nicks = {v.account for v in cand_vs}
    else:
        ready_nicks = {x["account"] for x in prep["ready_accounts"]}
        scan = _scan_smart_folders(st, rec, accs_list, md, day_iso, watch=watch, check_stability=False, deps=deps)
        cand_vs = list(scan["ready_videos"])

    # 初始化各账号实时状态表（供右栏每号一张卡片实时跳动）
    state_lock = threading.Lock()
    acc_state: dict[str, dict[str, Any]] = {}
    sent_init = rec.sent_on(day_iso)
    done_set = {x["account"] for x in prep.get("done_accounts") or []}
    wait_by_acc = {wf["account"]: wf for wf in prep.get("waiting_folders") or []}
    cand_cnt_by_acc: dict[str, int] = {}
    for v in cand_vs:
        cand_cnt_by_acc[v.account] = cand_cnt_by_acc.get(v.account, 0) + 1
    for a in accs_list:
        nk = str(a.get("nick") or "").strip()
        if not nk:
            continue
        s0 = int(sent_init.get(nk, 0))
        q0 = int(plan.quota_on(st, nk, day_iso) or 0)
        is_free = bool(st.get("quota_open", False) or plan.is_free(st, nk))
        cn = cand_cnt_by_acc.get(nk, 0)
        if cn > 0:
            t0 = (s0 + cn) if (is_free or q0 <= 0) else min(q0, s0 + cn) if q0 < s0 + cn else q0
            acc_state[nk] = {
                "account": nk, "status": "running", "stage": "排队检查",
                "sent": s0, "target": t0, "ready_count": cn,
                "detail": f"共 {cn} 条素材，等待检查", "skipped": 0, "outro_cut": 0, "failed": 0,
            }
        elif nk in done_set:
            acc_state[nk] = {
                "account": nk, "status": "done", "stage": "已发满",
                "sent": s0, "target": (q0 or s0), "ready_count": 0,
                "detail": f"今日已完成 {s0}/{q0 or s0} 条", "skipped": 0, "outro_cut": 0, "failed": 0,
            }
        elif nk in wait_by_acc:
            wf = wait_by_acc[nk]
            acc_state[nk] = {
                "account": nk, "status": "waiting", "stage": "等待素材",
                "sent": s0, "target": (0 if is_free else q0), "ready_count": 0,
                "detail": f"等待「{wf.get('folder_name', '')}」：{wf.get('reason', '')}",
                "skipped": 0, "outro_cut": 0, "failed": 0,
            }
        else:
            acc_state[nk] = {
                "account": nk, "status": "idle", "stage": "无今日夹",
                "sent": s0, "target": (0 if is_free else q0), "ready_count": 0,
                "detail": "今天素材文件夹还没放进来", "skipped": 0, "outro_cut": 0, "failed": 0,
            }
    _emit_acc({"__batch__": list(acc_state.values())}, deps)

    def _set_acc(nk: str, **kw):
        with state_lock:
            cur = acc_state.setdefault(nk, {
                "account": nk, "status": "running", "stage": "",
                "sent": 0, "target": 0, "ready_count": 0, "detail": "",
                "skipped": 0, "outro_cut": 0, "failed": 0,
            })
            if "skip_delta" in kw:
                cur["skipped"] = int(cur.get("skipped") or 0) + int(kw.pop("skip_delta"))
            if "outro_delta" in kw:
                cur["outro_cut"] = int(cur.get("outro_cut") or 0) + int(kw.pop("outro_delta"))
            if "fail_delta" in kw:
                cur["failed"] = int(cur.get("failed") or 0) + int(kw.pop("fail_delta"))
            cur.update(kw)
            snap = dict(cur)
        _emit_acc(snap, deps)

    if not cand_vs:
        return {
            "day_iso": day_iso,
            "md": md,
            "stopped": False,
            "published_count": 0,
            "retried_count": 0,
            "failed_count": 0,
            "unsure_count": 0,
            "skipped_count": 0,
            "converted_count": 0,
            "outro_cut_count": 0,
            "outro_cut_items": [],
            "renamed_count": 0,
            "cleaned_dirs_count": 0,
            "black_covers": [],
            "exported_covers_count": 0,
            "uncertain_missing": [],
            "skipped_items": [],
            "failed_items": [],
            "key_errors": [],
            "missing_accounts": prep["missing_accounts"],
            "waiting_folders": prep.get("waiting_folders") or [],
            "done_accounts": prep["done_accounts"],
            "per_account": [],
            "enabled_checks": chk["enabled"],
            "summary": prep["reason_cannot_start"] or "目前盘里暂无已落稳可发的视频。",
        }

    # 预先统计每个号历史上发过的规范标题（防同号重名）
    sent_title_keys: dict[str, set[str]] = {}
    for r in rec.rows():
        if r.get("status") == "已发":
            nt = folders.norm_name(r.get("title") or "")
            if nt:
                sent_title_keys.setdefault(str(r.get("account") or ""), set()).add(nt)

    # ②/⑥ 发前检查（严格按设置 6 项开关）
    ff = deps.get("ffmpeg_path") or vertical.ffmpeg_path()
    words = [] if ignore_platform_words else (st.get("api_platform_words") or None)
    skipped_items: list[dict[str, Any]] = []
    clean_vs: list[apisrc.ApiVideo] = []
    needs_vert_ids: set[int] = set()
    outro_plans: dict[int, dict] = {}
    seen_batch_titles: dict[str, set[str]] = {}

    for idx, v in enumerate(cand_vs, 1):
        if stopped and stopped():
            break
        if on_progress:
            on_progress(f"②/⑥ 发前检查（{idx}/{len(cand_vs)}）：[{v.account}] {v.title[:20]}…")
        _set_acc(v.account, status="running", stage="检查中", detail=f"检查：《{v.title[:20]}》")
        _c, reasons, needs_v, o_plan = _check_video_issues(v, st, flags, ff, words, deps, stopped)
        nt = folders.norm_name(v.title)
        if nt and nt in sent_title_keys.get(v.account, set()):
            reasons.append("这个号以前发过同名视频")
        elif nt and nt in seen_batch_titles.get(v.account, set()):
            reasons.append("本批里有同名重复视频")
        if reasons:
            skipped_items.append({"account": v.account, "title": v.title, "reasons": reasons, "path": v.path})
            aplog.write("②检查", f"拦截跳过：《{v.title}》—— {'、'.join(reasons)}", level="SKIP", account=v.account, day_iso=day_iso)
            _set_acc(v.account, detail=f"跳过：《{v.title[:18]}》", skip_delta=1)
        else:
            if nt:
                seen_batch_titles.setdefault(v.account, set()).add(nt)
            clean_vs.append(v)
            if needs_v:
                needs_vert_ids.add(id(v))
            if o_plan is not None:
                outro_plans[id(v)] = o_plan

    # ②b AI 查串游戏（仅在设置开启 game_ai_check 时触发）
    if flags.get("game_ai_check", True) and clean_vs and not (stopped and stopped()):
        ai_game_fn = deps.get("game_ai_fn")
        ai_cfg = aiconf.text(st, str(st.get("topic_model") or aiconf.TEXT_MODEL))
        if ai_game_fn is not None or ai_cfg.key:
            by_acc_clean: dict[str, list[apisrc.ApiVideo]] = {}
            for v in clean_vs:
                if gamecheck.account_game(v.account) and not gamecheck.store().batch_ok(v.account, md):
                    by_acc_clean.setdefault(v.account, []).append(v)
            blocked_vids: set[int] = set()
            for nick, vs_acc in by_acc_clean.items():
                if stopped and stopped():
                    break
                own_g = gamecheck.account_game(nick)
                to_ask = [v.title for v in vs_acc if gamecheck.need_ai(nick, v.title)]
                if to_ask:
                    if on_progress:
                        on_progress(f"②/⑥ AI 核对游戏是否放错：{nick}（{len(to_ask)} 条）…")
                    try:
                        got = ai_game_fn(nick, to_ask) if ai_game_fn is not None else gamecheck.ask_ai(own_g, to_ask, ai_cfg)
                        if got:
                            gamecheck.store().set_ai(got)
                    except Exception:
                        pass
                hits = [(v, gamecheck.ai_hint(nick, v.title)) for v in vs_acc]
                hits = [(v, g) for v, g in hits if g]
                if len(hits) >= 3 or (len(vs_acc) > 0 and len(hits) / len(vs_acc) >= 0.10):
                    aplog.write("②检查", f"AI 串游戏整批拦截（{len(hits)}/{len(vs_acc)} 条像别的游戏），跳过整个账号", level="WARN", account=nick, day_iso=day_iso)
                    for v in vs_acc:
                        blocked_vids.add(id(v))
                        why = f"AI 判断整批有 {len(hits)} 条像别的游戏(疑似放错文件夹)"
                        skipped_items.append({"account": nick, "title": v.title, "reasons": [why], "path": v.path})
                else:
                    for v, g in hits:
                        blocked_vids.add(id(v))
                        skipped_items.append({"account": nick, "title": v.title, "reasons": [f"AI 觉得像《{g}》"], "path": v.path})
                        aplog.write("②检查", f"AI 串游戏拦截：《{v.title}》像《{g}》", level="SKIP", account=nick, day_iso=day_iso)
            if blocked_vids:
                clean_vs = [v for v in clean_vs if id(v) not in blocked_vids]

    # 按每个号剩余规定条数截断，避免给今天超额用不上的视频做无谓的转竖屏
    trimmed_vs: list[apisrc.ApiVideo] = []
    sent_now = rec.sent_on(day_iso)
    per_acc_count: dict[str, int] = {}
    for v in clean_vs:
        left = plan.left_today(rec, st, v.account, day=day_iso, sent=sent_now)
        cur = per_acc_count.get(v.account, 0)
        if left is not None and cur >= left:
            continue
        per_acc_count[v.account] = cur + 1
        trimmed_vs.append(v)

    # ③/⑥ 自动预处理：横屏/偏方转竖屏 + 自动剪头像片尾卡片 + 整理标题/话题
    converted_count = 0
    renamed_count = 0
    outro_cut_items: list[dict[str, Any]] = []
    outro_cut_by_vid: dict[int, dict[str, Any]] = {}

    vert_targets = [v for v in trimmed_vs if id(v) in needs_vert_ids]
    if vert_targets and not (stopped and stopped()):
        to_vert_fn = deps.get("to_vertical_fn", vertical.to_vertical)
        v_lock = threading.Lock()
        v_done = [0]
        v_failed: set[int] = set()
        if on_progress:
            on_progress(f"③/⑥ 正在把 {len(vert_targets)} 条横屏/偏方视频转成竖屏（最多同时 3 条）…")

        def _conv_one(v: apisrc.ApiVideo):
            if stopped and stopped():
                return
            _set_acc(v.account, status="running", stage="转竖屏", detail=f"正在转竖屏：《{v.title[:20]}》")
            aplog.write("③转竖屏", f"开始转竖屏：《{v.title}》", level="INFO", account=v.account, day_iso=day_iso)
            try:
                new_p, _orig = to_vert_fn(v.path, ff, stop=stopped, keep_orig=False)
                v.path = new_p
                aplog.write("③转竖屏", f"转竖屏成功：《{v.title}》", level="OK", account=v.account, day_iso=day_iso)
                _set_acc(v.account, status="running", stage="转竖屏", detail=f"已转竖屏：《{v.title[:20]}》")
                with v_lock:
                    v_done[0] += 1
                    if on_progress:
                        on_progress(f"③/⑥ 自动转竖屏（{v_done[0]}/{len(vert_targets)}）：{v.title[:20]}…")
            except Exception as e:
                aplog.write("③转竖屏", f"转竖屏失败：《{v.title}》—— {str(e)[:80]}", level="ERROR", account=v.account, day_iso=day_iso)
                _set_acc(v.account, detail=f"转竖屏失败：《{v.title[:16]}》", skip_delta=1)
                with v_lock:
                    v_failed.add(id(v))
                    skipped_items.append({"account": v.account, "title": v.title, "reasons": [f"转竖屏失败:{str(e)[:40]}"], "path": v.path})

        with ThreadPoolExecutor(3) as ex:
            list(ex.map(_conv_one, vert_targets))
        converted_count = v_done[0]
        if v_failed:
            trimmed_vs = [v for v in trimmed_vs if id(v) not in v_failed]

    # ③b 自动剪掉头像片尾卡片，并记进战报「剪过片尾（建议抽检）」卡片组
    outro_targets = [v for v in trimmed_vs if id(v) in outro_plans]
    if outro_targets and not (stopped and stopped()):
        outro_cut_fn = deps.get("outro_cut_fn", outrocheck.cut)
        o_lock = threading.Lock()
        o_done = [0]
        o_failed: set[int] = set()
        if on_progress:
            on_progress(f"③/⑥ 正在自动剪掉 {len(outro_targets)} 条视频的头像片尾卡片…")

        def _cut_one(v: apisrc.ApiVideo):
            if stopped and stopped():
                return
            pl = outro_plans[id(v)]
            _set_acc(v.account, status="running", stage="剪片尾", detail=f"正在剪片尾：《{v.title[:20]}》")
            aplog.write("③剪结尾", f"开始剪片尾（从 {outrocheck.fmt_time(pl['start'])} 剪）：《{v.title}》", level="INFO", account=v.account, day_iso=day_iso)
            try:
                new_p, _orig, gone = outro_cut_fn(v.path, pl["start"], ff, stop=stopped)
                v.path = new_p
                wmstore.OUTRO.put(new_p, {"hits": pl.get("hits") or [{"start": pl["start"], "cut": gone}], "shot": pl.get("shot") or ""}, ok=True, blurred=True)
                rec_item = {
                    "account": v.account,
                    "title": v.title,
                    "start_sec": round(float(pl["start"]), 2),
                    "cut_sec": round(float(gone or 0), 2),
                    "reason": pl.get("reason") or "头像片尾卡片",
                    "shot": pl.get("shot") or "",
                    "day_iso": day_iso,
                }
                aplog.write("③剪结尾", f"剪片尾成功（剪掉末尾 {gone:.1f} 秒）：《{v.title}》", level="OK", account=v.account, day_iso=day_iso)
                _set_acc(v.account, status="running", stage="剪片尾", detail=f"已剪片尾 {gone:.1f}s：《{v.title[:18]}》", outro_delta=1)
                with o_lock:
                    o_done[0] += 1
                    outro_cut_items.append(rec_item)
                    outro_cut_by_vid[id(v)] = rec_item
                    if on_progress:
                        on_progress(f"③/⑥ 自动剪片尾（{o_done[0]}/{len(outro_targets)}）：{v.title[:20]}…")
            except Exception as e:
                aplog.write("③剪结尾", f"剪片尾失败：《{v.title}》—— {str(e)[:80]}", level="ERROR", account=v.account, day_iso=day_iso)
                _set_acc(v.account, detail=f"剪片尾失败：《{v.title[:16]}》", skip_delta=1)
                with o_lock:
                    o_failed.add(id(v))
                    skipped_items.append({"account": v.account, "title": v.title, "reasons": [f"自动剪片尾失败:{str(e)[:40]}"], "path": v.path})

        with ThreadPoolExecutor(2) as ex:
            list(ex.map(_cut_one, outro_targets))
        if o_failed:
            trimmed_vs = [v for v in trimmed_vs if id(v) not in o_failed]

    # ③c 整理标题 / 话题
    if trimmed_vs and not (stopped and stopped()):
        ledger = topic.Ledger(data_dir() / "改名记录.json")
        batch_at = f"{bj_str()}¦AI自动驾驶整理标题"
        ai_cfg = aiconf.text(st, str(st.get("topic_model") or aiconf.TEXT_MODEL))
        topic_pick_fn = deps.get("topic_pick_fn")

        def _pick(body: str, tags: list[str]) -> str:
            if topic_pick_fn is not None:
                return topic_pick_fn(body, tags)
            if ai_cfg.key:
                return topic.ask_ai(body, tags, ai_cfg)
            return tags[0]

        for idx, v in enumerate(trimmed_vs, 1):
            if stopped and stopped():
                break
            try:
                nn = topic.new_name(v.title, pick=_pick)
            except Exception:
                nn = None
            if nn and nn != v.title:
                if on_progress:
                    on_progress(f"③/⑥ 整理标题/话题（{idx}/{len(trimmed_vs)}）：{v.title[:20]}…")
                try:
                    old_title = v.title
                    moves = topic.rename_logged(v.path, nn, ledger, batch_at)
                    v.path = moves[0][1]
                    v.title = os.path.splitext(os.path.basename(v.path))[0]
                    if id(v) in outro_cut_by_vid:
                        outro_cut_by_vid[id(v)]["title"] = v.title
                    renamed_count += 1
                    aplog.write("③改标题", f"《{old_title}》 → 《{v.title}》", level="OK", account=v.account, day_iso=day_iso)
                except Exception as e:
                    aplog.write("③改标题", f"改名失败：《{v.title}》—— {e}", level="WARN", account=v.account, day_iso=day_iso)

    # ④/⑥ 自动发布（按设置 api_threads / api_per_acc 并行发布）
    pub_dirs: dict[str, dict] = {}
    batch1 = _publish_batch(
        st, rec, day_iso, accs_by_nick, trimmed_vs, pub_dirs,
        on_progress=on_progress, stopped=stopped, deps=deps,
        stage_prefix="④/⑥ 自动发布",
        acc_state=acc_state, state_lock=state_lock,
    )
    cleaned_dirs = _clean_emptied_dirs(st, pub_dirs)
    for cd in cleaned_dirs:
        aplog.write("④清理", f"已清残留并删空目录：{cd}", level="OK", day_iso=day_iso)

    # ⑤/⑥ 发后后台核对 + 对「确定没发上」自动拎回并最多自动补发 1 轮
    from .assistant import AssistantAgent
    agent = AssistantAgent(st, rec, deps=deps)
    touched_nicks = sorted({x["account"] for x in batch1["published"]})
    retried_ok: list[dict] = []
    retried_fail: list[dict] = []
    uncertain_missing: list[dict] = []

    key_errors = list(batch1.get("key_errors") or [])
    if touched_nicks and not (stopped and stopped()):
        for nk in touched_nicks:
            _set_acc(nk, status="running", stage="后台核对", detail="正在核对企鹅号后台有没有漏发…")
        if on_progress:
            on_progress(f"⑤/⑥ 正在去后台核对刚才发布的 {len(touched_nicks)} 个账号有没有漏发…")
        vres = agent.tool_verify_backend(day=day_iso, accounts=touched_nicks, on_progress=on_progress, stopped=stopped)
        uncertain_missing = list(vres.get("uncertain_missing") or [])
        conf_miss = [
            x for x in (vres.get("confirmed_missing") or [])
            if x.get("can_pull_back") and x.get("row_id") is not None
        ]
        if conf_miss and not (stopped and stopped()):
            aplog.write("⑤核对", f"发现 {len(conf_miss)} 条确定没发上，开始自动拎回并补发（最多 1 轮）", level="WARN", day_iso=day_iso)
            if on_progress:
                on_progress(f"⑤/⑥ 发现 {len(conf_miss)} 条确定没发上，正在自动拎回并补发（最多 1 轮）…")
            pb = agent.tool_pull_back_for_republish(
                [{"row_id": x["row_id"], "account": x["account"], "title": x["title"]} for x in conf_miss],
                target_day=day_iso,
                confirmed_only=True,
                on_progress=on_progress,
            )
            retry_vs = [
                apisrc.ApiVideo(
                    path=m["new_path"],
                    title=os.path.splitext(os.path.basename(m["new_path"]))[0],
                    account=m["account"],
                    date=md,
                    folder=os.path.dirname(m["new_path"]),
                )
                for m in (pb.get("moved") or [])
                if m.get("new_path") and os.path.isfile(m["new_path"])
            ]
            if retry_vs and not (stopped and stopped()):
                pub_dirs2: dict[str, dict] = {}
                batch2 = _publish_batch(
                    st, rec, day_iso, accs_by_nick, retry_vs, pub_dirs2,
                    on_progress=on_progress, stopped=stopped, deps=deps,
                    stage_prefix="⑤/⑥ 自动补发漏发",
                    acc_state=acc_state, state_lock=state_lock,
                )
                retried_ok = batch2["published"]
                retried_fail = batch2["failed"]
                key_errors += list(batch2.get("key_errors") or [])
                cleaned_dirs += _clean_emptied_dirs(st, pub_dirs2)

    # ⑥/⑥ 扫描黑封面 / 模糊封面 + 自动截清晰图
    black_items: list[dict] = []
    exported_covers = 0
    if touched_nicks and not (stopped and stopped()):
        for nk in touched_nicks:
            _set_acc(nk, status="running", stage="查封面", detail="正在扫描黑封面 / 模糊封面…")
        if on_progress:
            on_progress(f"⑥/⑥ 正在扫描本次 {len(touched_nicks)} 个账号的黑封面 / 模糊封面…")
        bres = agent.tool_check_black_covers(
            day=day_iso, accounts=touched_nicks, auto_export=True,
            on_progress=on_progress, stopped=stopped,
        )
        black_items = list(bres.get("items") or [])
        exported_covers = int(bres.get("exported_count") or 0)
        if black_items:
            aplog.write("⑥封面", f"发现问题封面 {len(black_items)} 条，已自动导出清晰封面 {exported_covers} 张", level="WARN", day_iso=day_iso)
        else:
            aplog.write("⑥封面", "封面扫描完毕，未发现黑封面/模糊封面", level="OK", day_iso=day_iso)

    # 结算每个参与账号的最终卡片状态
    sent_final = rec.sent_on(day_iso)
    key_err_nicks = {e.get("account") for e in key_errors}
    was_stopped_now = bool(stopped and stopped())
    for nk in sorted(ready_nicks):
        s_now = int(sent_final.get(nk, 0))
        q_now = int(plan.quota_on(st, nk, day_iso) or 0)
        is_free = bool(st.get("quota_open", False) or plan.is_free(st, nk))
        pub_k = sum(1 for x in batch1["published"] if x["account"] == nk)
        fail_k = sum(1 for x in batch1["failed"] + retried_fail if x["account"] == nk)
        skip_k = sum(1 for x in skipped_items if x["account"] == nk)
        if nk in key_err_nicks:
            _set_acc(nk, status="error", stage="密钥失效", sent=s_now, detail="密钥失效，请到设置重新搬账号")
        elif was_stopped_now:
            _set_acc(nk, status="waiting", stage="已停止", sent=s_now, detail=f"已手动停止（本轮已发 {pub_k} 条）")
        elif fail_k > 0:
            _set_acc(nk, status="error", stage="部分失败", sent=s_now, detail=f"本轮已发 {pub_k} 条，失败 {fail_k} 条")
        elif (not is_free) and q_now > 0 and s_now >= q_now:
            _set_acc(nk, status="done", stage="已发满", sent=s_now, target=q_now, detail=f"今日已发满 {s_now}/{q_now} 条")
        elif skip_k > 0 and pub_k == 0:
            _set_acc(nk, status="error", stage="待拍板", sent=s_now, detail=f"本轮 {skip_k} 条被检查拦下，待拍板")
        else:
            _set_acc(nk, status="done", stage="已完成", sent=s_now, detail=f"本轮已发 {pub_k} 条" + (f"，拦下 {skip_k} 条" if skip_k else ""))

    # 汇总按账号统计
    all_nicks = sorted(ready_nicks)
    per_account = []
    for nk in all_nicks:
        per_account.append({
            "account": nk,
            "published": sum(1 for x in batch1["published"] if x["account"] == nk),
            "retried": sum(1 for x in retried_ok if x["account"] == nk),
            "failed": sum(1 for x in batch1["failed"] + retried_fail if x["account"] == nk),
            "skipped": sum(1 for x in skipped_items if x["account"] == nk),
        })

    was_stopped = bool(stopped and stopped())
    pub_n = len(batch1["published"])
    ret_n = len(retried_ok)
    fail_n = len(batch1["failed"]) + len(retried_fail)
    uns_n = len(batch1["unsure"])
    skip_n = len(skipped_items)
    summary = (
        ("已手动停止。" if was_stopped else "今日 16 个号全自动运行完成。")
        + f" 共发布 {pub_n} 条"
        + (f"（含自动补发 {ret_n} 条）" if ret_n else "")
        + (f"，拦下异常 {skip_n} 条" if skip_n else "")
        + (f"，失败 {fail_n} 条" if fail_n else "")
        + (f"，发现问题封面 {len(black_items)} 条" if black_items else "，无黑封面")
        + "。"
    )
    aplog.write("批次结束", summary, level=("WARN" if (fail_n or was_stopped) else "OK"), day_iso=day_iso)

    return {
        "day_iso": day_iso,
        "md": md,
        "stopped": was_stopped,
        "published_count": pub_n,
        "retried_count": ret_n,
        "failed_count": fail_n,
        "unsure_count": uns_n,
        "skipped_count": skip_n,
        "converted_count": converted_count,
        "outro_cut_count": len(outro_cut_items),
        "outro_cut_items": outro_cut_items,
        "renamed_count": renamed_count,
        "cleaned_dirs_count": len(cleaned_dirs),
        "black_covers": black_items,
        "exported_covers_count": exported_covers,
        "uncertain_missing": uncertain_missing,
        "skipped_items": skipped_items,
        "failed_items": batch1["failed"] + retried_fail,
        "key_errors": key_errors,
        "missing_accounts": prep["missing_accounts"],
        "waiting_folders": prep.get("waiting_folders") or [],
        "done_accounts": prep["done_accounts"],
        "per_account": per_account,
        "enabled_checks": chk["enabled"],
        "summary": summary,
    }


HARD_SKIP_KEYWORDS = ("视频打不开", "文件损坏", "以前发过同名", "本批里有同名", "密钥失效")


def is_overridable_item(item: dict[str, Any]) -> bool:
    """判断一条待拍板/失败视频是否允许用户一键放行补发（硬防重发与损坏片绝不允许误放行）。"""
    path = str(item.get("path") or "").strip()
    if not path:
        return False
    reasons = list(item.get("reasons") or [])
    if item.get("error"):
        reasons.append(str(item["error"]))
    joined = " ".join(str(r) for r in reasons)
    if any(k in joined for k in HARD_SKIP_KEYWORDS):
        return False
    return True


def override_and_publish(
    st,
    rec,
    items: list[dict[str, Any]],
    *,
    day: str = "",
    watch: WatchState | None = None,
    on_progress: Callable[[str], None] | None = None,
    stopped: Callable[[], bool] | None = None,
    deps: dict | None = None,
) -> dict[str, Any]:
    """用户看过待拍板/失败视频确认没问题后，一键写入对应检查放行记录并立刻走全自动补发闭环。"""
    deps = deps or {}
    from .assistant import day_to_md, parse_day
    day_iso = parse_day(day, deps.get("today_fn"))
    md = day_to_md(day_iso)

    override_vs: list[apisrc.ApiVideo] = []
    rejected: list[dict[str, Any]] = []
    seen_p: set[str] = set()
    for it in items or []:
        nick = str(it.get("account") or "").strip()
        path = str(it.get("path") or "").strip()
        title = str(it.get("title") or (os.path.splitext(os.path.basename(path))[0] if path else "")).strip()
        if not nick or not path:
            rejected.append({"account": nick, "title": title, "why": "缺少账号或文件路径"})
            continue
        if not is_overridable_item(it):
            rejected.append({"account": nick, "title": title, "why": "属于防重发或文件损坏红线，不可直接放行"})
            continue
        if not os.path.isfile(path):
            rejected.append({"account": nick, "title": title, "why": "原视频文件已不在原目录（可能已发或被移走）"})
            continue
        pk = pkey(path)
        if pk in seen_p:
            continue
        seen_p.add(pk)

        reasons_txt = " ".join(str(r) for r in (it.get("reasons") or []))
        # 写入各类检查放行标记（仅影响这条视频，下次扫描也不再重复拦）
        try:
            gamecheck.store().set_ok(nick, title, True)
            if "整批" in reasons_txt or "放错" in reasons_txt:
                gamecheck.store().set_batch_ok(nick, md, True)
        except Exception:
            pass
        for store_obj, args in (
            (titledate.store(), (nick, title, True)),
            (longcheck.store(), (nick, title, True)),
            (titleclean.store(), (nick, title, True)),
        ):
            try:
                store_obj.set(*args)
            except Exception:
                pass
        for s_store in (audiocheck.STORE, sharp.STORE, wmstore.CROP, wmstore.OUTRO, wmstore.WM, wmstore.ADS):
            try:
                if s_store.get(path) is not None:
                    s_store.set_ok(path, True)
            except Exception:
                pass
        if watch is not None:
            watch.skipped_fingerprints.pop(pk, None)

        aplog.write("人工放行", f"用户确认没问题，放行补发：《{title}》", level="INFO", account=nick, day_iso=day_iso)
        override_vs.append(apisrc.ApiVideo(path=path, title=title, account=nick, date=md, folder=os.path.dirname(path)))

    if not override_vs:
        why_s = "；".join(f"《{r['title']}》({r['why']})" for r in rejected[:4]) or "没有可放行补发的视频"
        return {
            "day_iso": day_iso, "md": md, "stopped": False,
            "published_count": 0, "retried_count": 0, "failed_count": 0, "unsure_count": 0,
            "skipped_count": 0, "converted_count": 0, "outro_cut_count": 0, "outro_cut_items": [],
            "renamed_count": 0, "cleaned_dirs_count": 0, "black_covers": [], "exported_covers_count": 0,
            "uncertain_missing": [], "skipped_items": [], "failed_items": [], "key_errors": [],
            "missing_accounts": [], "waiting_folders": [], "done_accounts": [], "per_account": [],
            "enabled_checks": [], "rejected_overrides": rejected,
            "summary": f"未能放行补发：{why_s}。",
        }

    rep = run(
        st, rec,
        day=day_iso,
        explicit_videos=override_vs,
        watch=watch,
        on_progress=on_progress,
        stopped=stopped,
        deps=deps,
        ignore_platform_words=True,
    )
    if rejected:
        rep["rejected_overrides"] = rejected
    return rep


def _now_hm(deps: dict | None = None) -> str:
    if deps and "now_hm_fn" in deps:
        return str(deps["now_hm_fn"]())
    return bj_now().strftime("%H:%M")


def run_watch_tick(
    st,
    rec,
    watch: WatchState,
    on_progress: Callable[[str], None] | None = None,
    stopped: Callable[[], bool] | None = None,
    deps: dict | None = None,
) -> dict[str, Any]:
    """执行一次全天值守巡检（静默无打扰，只在有新片/无日期变动/密钥失效/收工时产出汇报）。"""
    deps = deps or {}
    if not watch.active:
        return {"quiet": True, "has_work": False, "ended": True, "end_reason": "值守已结束", "key_errors": [], "undated_discovered": []}

    hm = _now_hm(deps)
    if watch.cutoff_hm and hm >= watch.cutoff_hm:
        watch.active = False
        msg_end = f"已到晚上收工时间（{watch.cutoff_hm}），自动结束今日值守。"
        aplog.write("值守收工", msg_end, level="OK", day_iso=watch.day_iso)
        return {
            "quiet": False,
            "has_work": False,
            "ended": True,
            "end_reason": msg_end,
            "key_errors": [],
            "undated_discovered": [],
            "snapshot": watch.snapshot(st, rec),
        }

    accs = [a for a in _load_enabled_api_accounts(deps) if _match_nick_filter(str(a.get("nick") or ""), watch.accounts_filter)]
    active_accs = [a for a in accs if str(a.get("nick") or "") not in watch.skip_accounts]
    watch.rounds += 1
    watch.last_tick_at = hm

    # 检查是否所有有规定条数的账号都已发满
    sent_now = rec.sent_on(watch.day_iso)
    quota_accs = [a for a in active_accs if plan.quota_on(st, str(a.get("nick") or ""), watch.day_iso) > 0 and not plan.is_free(st, str(a.get("nick") or ""))]
    if quota_accs and all(plan.left_today(rec, st, str(a.get("nick") or ""), day=watch.day_iso, sent=sent_now) == 0 for a in quota_accs):
        watch.active = False
        msg_full = "今日所有有规定条数的 16 个号已全部发满，自动收工 ✓"
        aplog.write("值守收工", msg_full, level="OK", day_iso=watch.day_iso)
        return {
            "quiet": False,
            "has_work": False,
            "ended": True,
            "end_reason": msg_full,
            "key_errors": [],
            "undated_discovered": [],
            "snapshot": watch.snapshot(st, rec),
        }

    scan = _scan_smart_folders(st, rec, active_accs, watch.md, watch.day_iso, watch=watch, check_stability=True, deps=deps)
    watch.waiting_summary = list(scan["waiting_folders"])
    if scan["undated_discovered"]:
        seen_u = {os.path.normcase(os.path.abspath(x["path"])) for x in watch.undated_summary if x.get("path")}
        for u in scan["undated_discovered"]:
            fk_u = os.path.normcase(os.path.abspath(u["path"]))
            if fk_u not in seen_u:
                watch.undated_summary.append(dict(u))
                seen_u.add(fk_u)
    for wf in scan["waiting_folders"]:
        aplog.write("巡检等待", f"暂不动「{wf['folder_name']}」：{wf['reason']}", level="INFO", account=wf["account"], day_iso=watch.day_iso)
    for note in scan["count_notes"]:
        watch.record_note(note)
        aplog.write("巡检数量", note, level="WARN", day_iso=watch.day_iso)

    new_undated = []
    for u in scan["undated_discovered"]:
        fk = os.path.normcase(os.path.abspath(u["path"]))
        if fk not in watch.reported_undated:
            watch.reported_undated.add(fk)
            new_undated.append(u)
            aplog.write("无日期夹", f"发现今日新变动无日期目录「{u['folder_name']}」（{u['video_count']} 条未发，未擅自发）", level="INFO", account=u["account"], day_iso=watch.day_iso)

    ready_vs = scan["ready_videos"]
    if not ready_vs:
        aplog.write(
            "值守巡检",
            f"第 {watch.rounds} 轮巡检完成：无新落稳视频（等待中 {len(scan['waiting_folders'])} 个目录）",
            level="INFO", day_iso=watch.day_iso,
        )
        return {
            "quiet": len(new_undated) == 0,
            "has_work": False,
            "ended": False,
            "end_reason": "",
            "waiting_folders": scan["waiting_folders"],
            "undated_discovered": new_undated,
            "count_notes": scan["count_notes"],
            "key_errors": [],
            "snapshot": watch.snapshot(st, rec),
        }

    rep = run(
        st, rec,
        day=watch.day_iso,
        accounts=watch.accounts_filter,
        on_progress=on_progress,
        stopped=stopped,
        deps=deps,
        explicit_videos=ready_vs,
        watch=watch,
    )
    # 记住本轮被拦下异常片的文件指纹，下轮巡检不再重复检查/刷屏
    for sk in rep.get("skipped_items") or []:
        fp_v = _file_fp(sk.get("path") or "")
        if fp_v is not None:
            watch.skipped_fingerprints[pkey(sk["path"])] = fp_v

    watch.total_published += int(rep.get("published_count") or 0)
    watch.total_retried += int(rep.get("retried_count") or 0)
    watch.total_failed += int(rep.get("failed_count") or 0)
    watch.total_skipped += int(rep.get("skipped_count") or 0)
    watch.total_cleaned += int(rep.get("cleaned_dirs_count") or 0)

    new_key_errors = []
    for ke in rep.get("key_errors") or []:
        nk = ke.get("account") or ""
        if nk and nk not in watch.key_alerted:
            watch.key_alerted.add(nk)
            new_key_errors.append(ke)

    # 跑完这一批后再看一眼：是不是已经全部发满了？
    sent_after = rec.sent_on(watch.day_iso)
    ended = False
    end_reason = ""
    if quota_accs and all(plan.left_today(rec, st, str(a.get("nick") or ""), day=watch.day_iso, sent=sent_after) == 0 for a in quota_accs):
        watch.active = False
        ended = True
        end_reason = "今日所有有规定条数的 16 个号已全部发满，自动收工 ✓"

    if scan["count_notes"]:
        rep["count_notes"] = list(scan["count_notes"])
    return {
        "quiet": False,
        "has_work": True,
        "ended": ended,
        "end_reason": end_reason,
        "report": rep,
        "waiting_folders": scan["waiting_folders"],
        "undated_discovered": new_undated,
        "count_notes": scan["count_notes"],
        "key_errors": new_key_errors,
        "snapshot": watch.snapshot(st, rec),
    }
