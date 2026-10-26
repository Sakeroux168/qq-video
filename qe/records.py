"""发布记录:每条视频哪天的、哪个号、哪个员工、标题、什么时候摆好、什么时候发的(北京时间)。

「发的时间」= 用户在罐头里点完「全部发布」、回软件点「这批发好了」的时间(发布是人点的,软件只能这么记)。
"""
import os
import sqlite3
import threading

from .config import bj_str, data_dir


def pkey(path: str) -> str:
    """路径的统一写法(大小写、斜杠、..):设置里素材文件夹换个写法(X:/ x:\\),发过的也认得出来(审查第 7 条)。"""
    return os.path.normcase(os.path.normpath(str(path or "")))

_LOCK = threading.RLock()
_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT, account TEXT, employee TEXT, title TEXT, path TEXT,
  cover_kind TEXT DEFAULT '', batch TEXT DEFAULT '',
  status TEXT DEFAULT '',          -- 摆好 / 已发 / 没摆成
  prepared_at TEXT DEFAULT '', published_at TEXT DEFAULT '', note TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS i_posts_path ON posts(path);
CREATE INDEX IF NOT EXISTS i_posts_date ON posts(date, account);
"""


class Records:
    def __init__(self, path=None):
        self.path = str(path or (data_dir() / "发布记录.sqlite"))
        self.conn = self._open()
        self.conn.row_factory = sqlite3.Row
        self.conn.create_function("nk", 1, pkey, deterministic=True)
        with _LOCK:
            self.conn.executescript(_SCHEMA)
            cols = [r[1] for r in self.conn.execute("PRAGMA table_info(posts)")]
            if "pkey" not in cols:
                self.conn.execute("ALTER TABLE posts ADD COLUMN pkey TEXT")
            if "moved_pkey" not in cols:                  # 发完挪走以后的新位置(手选文件夹选到归档里也认得出发过)
                self.conn.execute("ALTER TABLE posts ADD COLUMN moved_pkey TEXT")
            self.conn.execute("CREATE INDEX IF NOT EXISTS i_posts_moved ON posts(moved_pkey)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS i_posts_pkey ON posts(pkey)")
            self.conn.commit()
            self._fill()

    def _open(self):
        """打开记录库;库坏了(不是 sqlite 文件)就把坏的改名留着,建个新的(审查:原来直接开不起来、也没提示)。"""
        self.broken = ""
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        try:
            conn.execute("PRAGMA schema_version").fetchone()
            return conn
        except sqlite3.DatabaseError:
            conn.close()
            from .config import bj_now
            bad = f"{self.path}.坏了-{bj_now().strftime('%Y%m%d-%H%M%S')}"
            os.replace(self.path, bad)
            self.broken = bad
            return sqlite3.connect(self.path, check_same_thread=False, timeout=30)

    def _fill(self):
        """新记录(不管是哪个版本的软件写的)补上 pkey。有索引,没有要补的时候很快。"""
        with _LOCK:
            if self.conn.execute("SELECT 1 FROM posts WHERE pkey IS NULL LIMIT 1").fetchone() is None:
                return
            self.conn.execute("UPDATE posts SET pkey=nk(path) WHERE pkey IS NULL")
            self.conn.commit()

    def prepared(self, v, batch: str, note: str = "") -> int:
        with _LOCK:
            cur = self.conn.execute(
                "INSERT INTO posts(date,account,employee,title,path,cover_kind,batch,status,prepared_at,note) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (v.date, v.account, v.employee, v.title, v.path, v.cover_kind, batch, "摆好", bj_str(), note))
            self.conn.commit()
            return int(cur.lastrowid)

    def failed(self, v, batch: str, why: str) -> None:
        with _LOCK:
            self.conn.execute(
                "INSERT INTO posts(date,account,employee,title,path,cover_kind,batch,status,prepared_at,note) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (v.date, v.account, v.employee, v.title, v.path, v.cover_kind, batch, "没摆成", bj_str(), why))
            self.conn.commit()

    def mark_batch_published(self, batch: str, at: str = "") -> int:
        """at = 罐头里定时发布定的时间(北京时间「YYYY-MM-DD HH:MM」):发布时间记成那个点(每日汇总算到那天),备注写上定时。"""
        with _LOCK:
            cur = self.conn.execute("UPDATE posts SET status='已发', published_at=?, note=note || ? WHERE batch=? AND status='摆好'",
                                    (f"{at}:00" if at else bj_str(), f"(罐头定时发布 {at})" if at else "", batch))
            self.conn.commit()
            return cur.rowcount

    def manual_published(self, v, note: str = "人手动发的") -> None:
        """人在罐头里自己发了(软件没摆成 / 没摆):记成已发,发布时间 = 现在(补记)。"""
        with _LOCK:
            self.conn.execute(
                "INSERT INTO posts(date,account,employee,title,path,cover_kind,batch,status,prepared_at,published_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (v.date, v.account, v.employee, v.title, v.path, v.cover_kind, "手动", "已发", "", bj_str(), note))
            self.conn.commit()

    # ---------------- 接口发的 16 个号(员工一栏记「接口」,和教育的放一起数) ----------------
    def api_result(self, v, status: str, note: str = "") -> None:
        """status:已发 / 没发成。v.path 记原来的位置(发完挪走了也能查到是哪条)。"""
        with _LOCK:
            self.conn.execute(
                "INSERT INTO posts(date,account,employee,title,path,cover_kind,batch,status,prepared_at,published_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (v.date, v.account, "接口", v.title, v.path, "", "接口", status, "",
                 bj_str() if status == "已发" else "", note))
            self.conn.commit()

    def api_begin(self, v, note: str = "") -> int:
        """真正调发布接口之前先记一笔「发布中」:程序这时候被关 / 崩了,下次也不会自动再发(要人去后台看)。返回记录 id。"""
        with _LOCK:
            cur = self.conn.execute(
                "INSERT INTO posts(date,account,employee,title,path,cover_kind,batch,status,prepared_at,published_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (v.date, v.account, "接口", v.title, v.path, "", "接口", "发布中", bj_str(), "", note))
            self.conn.commit()
            return int(cur.lastrowid)

    def try_begin(self, v, note: str = "") -> int | None:
        """原子地「查一下 + 记发布中」:这个文件已经发过 / 正在发 / 结果不明(比如两个号手选了同一个文件夹)就返回 None,不发。"""
        with _LOCK:
            if self.status_of(v.path) in ("已发", "结果不明"):
                return None
            return self.api_begin(v, note)

    def mark_moved(self, rid: int, new_path: str) -> None:
        """发完挪走了:记下新位置(之后在归档里再看到它也认得出发过)。"""
        with _LOCK:
            self.conn.execute("UPDATE posts SET moved_pkey=? WHERE id=?", (pkey(new_path), rid))
            self.conn.commit()

    def relink(self, rid: int, new_path: str) -> bool:
        """发过的那条被人挪了 / 文件夹改了名:记下现在的位置,之后按路径也认得出发过。
        已经记过挪走位置、而且那里文件还在的不动(不把归档的位置盖掉)。返回改没改。
        审查 22:原来的文件还在 = 不是挪了,是员工又放了一份同名的 → 不改(不然那份没发的被当成已发,「挪走」时一起挪走)。"""
        with _LOCK:
            r = self.conn.execute("SELECT path, moved_pkey FROM posts WHERE id=?", (rid,)).fetchone()
            if r is None or (r["moved_pkey"] and r["moved_pkey"] != pkey(r["path"]) and os.path.exists(r["moved_pkey"])):
                return False
            if pkey(r["path"]) != pkey(new_path) and os.path.exists(r["path"]):
                return False
            self.conn.execute("UPDATE posts SET moved_pkey=? WHERE id=?", (pkey(new_path), rid))
            self.conn.commit()
            return True

    def api_finish(self, rid: int, status: str, note: str = "") -> None:
        """「发布中」那笔改成结果:已发 / 没发成 / 结果不明。"""
        with _LOCK:
            self.conn.execute("UPDATE posts SET status=?, published_at=?, note=? WHERE id=?",
                              (status, bj_str() if status == "已发" else "", note, rid))
            self.conn.commit()

    def unsure_paths(self) -> list[dict]:
        """「发布中」(程序中途被关)/「结果不明」的接口记录,要人去后台确认。"""
        with _LOCK:
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM posts WHERE employee='接口' AND status IN ('发布中','结果不明') ORDER BY id")]

    def resolve_unsure(self, path: str, sent: bool) -> int:
        """人去后台看过了:发了 → 已发;没发 → 没发成(能再发)。"""
        with _LOCK:
            self._fill()
            cur = self.conn.execute(
                "UPDATE posts SET status=?, published_at=CASE WHEN ?='已发' THEN COALESCE(NULLIF(published_at, ''), NULLIF(prepared_at, ''), ?) "
                "ELSE published_at END, "
                "note=note || '(人去后台确认过)' WHERE pkey=? AND status IN ('发布中','结果不明')",
                ("已发" if sent else "没发成", "已发" if sent else "", bj_str(), pkey(path)))
            self.conn.commit()
            return cur.rowcount

    def repath(self, rid: int, new_path: str) -> None:
        """视频被挪回素材盘重发了(找视频重发 / 拎回来):记录的位置改成现在那里,原来的位置写进备注。"""
        with _LOCK:
            r = self.conn.execute("SELECT path FROM posts WHERE id=?", (rid,)).fetchone()
            if r is None or pkey(r["path"]) == pkey(new_path):
                return
            self.conn.execute("UPDATE posts SET path=?, pkey=?, moved_pkey=NULL, note=note || ? WHERE id=?",
                              (new_path, pkey(new_path), f"(原来在 {r['path']})", rid))
            self.conn.commit()

    def mark_sent(self, rid: int) -> None:
        """数据记录页:人去后台看了,这条「没发成」的其实发出去了 → 记成已发。
        原来记着发布时间的(发出去过、被拎回来 / 改回没发的)保留原来的;没有的才记成现在(补记)。
        用户 2026-10-26:原来一律改成现在,10.24 发的标成已发就变成了今天发的,核对今天说它没发上。"""
        with _LOCK:
            self.conn.execute("UPDATE posts SET status='已发', published_at=COALESCE(NULLIF(published_at, ''), NULLIF(prepared_at, ''), ?), "
                              "note=note || '(人去后台看过,标成已发)' WHERE id=?", (bj_str(), rid))
            self.conn.commit()

    def failed_in_batch(self, batch: str) -> list[dict]:
        """这批里没摆成、后来也没记已发的(人可能在罐头里手动补好一起发了)。"""
        with _LOCK:
            rows = [dict(r) for r in self.conn.execute("SELECT * FROM posts WHERE batch=? AND status='没摆成'", (batch,))]
        return [r for r in rows if self.status_of(r["path"]) != "已发"]

    def mark_failed_published(self, batch: str) -> int:
        with _LOCK:
            self._fill()
            cur = self.conn.execute("UPDATE posts SET status='已发', published_at=?, note=note || '(人手动补好一起发的)' "
                                    "WHERE batch=? AND status='没摆成' AND pkey NOT IN (SELECT pkey FROM posts WHERE status='已发')",
                                    (bj_str(), batch))
            self.conn.commit()
            return cur.rowcount

    def ready_in_batch(self, batch: str) -> int:
        """这批里摆好了、还没确认发没发的条数(摆到一半停了 / 出错了也要人确认)。"""
        with _LOCK:
            return int(self.conn.execute("SELECT COUNT(*) FROM posts WHERE batch=? AND status='摆好'", (batch,)).fetchone()[0])

    def drop_batch(self, batch: str) -> int:
        """这批没发(人在罐头里删了 / 不要了):摆好的记录作废,下次还能再摆。"""
        with _LOCK:
            cur = self.conn.execute("UPDATE posts SET status='作废' WHERE batch=? AND status='摆好'", (batch,))
            self.conn.commit()
            return cur.rowcount

    def status_of(self, path: str) -> str:
        """这条视频现在的状态:已发 > 结果不明(接口发了一半 / 没收到回话,不能自动再发) > 摆好 > ''
        (没摆过 / 没摆成 / 没发成 / 作废都算没发)。"""
        with _LOCK:
            self._fill()
            k = pkey(path)
            rows = [r["status"] for r in self.conn.execute("SELECT status FROM posts WHERE pkey=? OR moved_pkey=?", (k, k))]
        if "已发" in rows:
            return "已发"
        if "发布中" in rows or "结果不明" in rows:
            return "结果不明"
        if "摆好" in rows:
            return "摆好"
        return ""

    def blocked(self, path: str) -> bool:
        """接口发布不能再发这条:已发,或者结果不明。"""
        return self.status_of(path) in ("已发", "结果不明")

    def rows(self, date: str = "", account: str = "", employee: str = "") -> list[dict]:
        q, a = "SELECT * FROM posts WHERE status IN ('已发','摆好','结果不明','发布中','没发成')", []
        for k, val in (("date", date), ("account", account), ("employee", employee)):
            if val:
                q += f" AND {k}=?"
                a.append(val)
        with _LOCK:
            return [dict(r) for r in self.conn.execute(q + " ORDER BY id", a)]

    def sent_on(self, day: str) -> dict[str, int]:
        """这天(发布时间的北京日期 2026-10-16)每个号发了几条:按「哪天发出去的」算,同一个视频只算一次。"""
        self._fill()
        with _LOCK:
            rows = self.conn.execute(
                "SELECT account, COUNT(DISTINCT pkey) AS n FROM posts WHERE status='已发' AND published_at LIKE ? GROUP BY account",
                (f"{day}%",)).fetchall()
        return {r["account"]: int(r["n"]) for r in rows}

    def published_on(self, day: str) -> list[dict]:
        """这天(北京日期 2026-10-18)发出去的 / 没发成的,按时间排(「今天」页画「今天发了这几批」用)。"""
        with _LOCK:
            return [dict(r) for r in self.conn.execute(
                "SELECT account, employee, status, published_at FROM posts WHERE published_at LIKE ? "
                "AND status IN ('已发','没发成') ORDER BY published_at", (f"{day}%",))]

    def sent_row(self, path: str) -> dict | None:
        """这条视频(原位置或者发完挪去的位置)的「已发」记录;没有给 None。"""
        self._fill()
        k = pkey(path)
        with _LOCK:
            r = self.conn.execute("SELECT * FROM posts WHERE status='已发' AND (pkey=? OR moved_pkey=?) ORDER BY id DESC LIMIT 1",
                                  (k, k)).fetchone()
        return dict(r) if r else None

    def mark_unsent(self, rid: int, note: str = "") -> None:
        """去企鹅号核对:记成已发、平台上其实没有的 → 改成「没发成」(能再发),挪走的位置清掉(视频挪回原处了)。"""
        with _LOCK:
            self.conn.execute("UPDATE posts SET status='没发成', moved_pkey=NULL, note=note || ? WHERE id=?", (note, rid))
            self.conn.commit()

    def problems_on(self, day: str) -> dict:
        """「今天出问题」那张卡(老板试用 2026-10-21):这天没发成的(后来发成了的不算)、
        还不确定发没发的、摆好了还没确认的(后两样不管哪天的,没处理就一直算)。day = 2026-10-21。"""
        self._fill()
        with _LOCK:
            fail = self.conn.execute(
                "SELECT COUNT(DISTINCT pkey) FROM posts WHERE status='没发成' AND (published_at LIKE ? OR prepared_at LIKE ?) "
                "AND pkey NOT IN (SELECT pkey FROM posts WHERE status='已发')", (f"{day}%", f"{day}%")).fetchone()[0]
            unsure = self.conn.execute("SELECT COUNT(DISTINCT pkey) FROM posts WHERE status IN ('结果不明','发布中')").fetchone()[0]
            ready = self.conn.execute("SELECT COUNT(DISTINCT pkey) FROM posts WHERE status='摆好'").fetchone()[0]
        return {"fail": int(fail or 0), "unsure": int(unsure or 0), "ready": int(ready or 0)}

    def summary(self, date: str = "") -> list[dict]:
        """按 日期 / 号 / 员工 数:已发几条、摆好还没发几条、没发成几条(后来发成了的不算)、结果不明几条。"""
        self._fill()
        q = ("SELECT date, account, employee, COUNT(DISTINCT CASE WHEN status='已发' THEN pkey END) AS sent, "
             "COUNT(DISTINCT CASE WHEN status='摆好' THEN pkey END) AS ready, "
             "COUNT(DISTINCT CASE WHEN status='没发成' AND pkey NOT IN (SELECT pkey FROM posts WHERE status='已发') THEN pkey END) AS failed, "
             "COUNT(DISTINCT CASE WHEN status IN ('结果不明','发布中') THEN pkey END) AS unsure, "
             "MIN(CASE WHEN status='已发' THEN published_at END) AS first_at, MAX(CASE WHEN status='已发' THEN published_at END) AS last_at "
             "FROM posts WHERE status IN ('已发','摆好','没发成','结果不明','发布中')" + (" AND date=?" if date else "") +
             " GROUP BY date, account, employee ORDER BY date, account, employee")
        with _LOCK:
            return [dict(r) for r in self.conn.execute(q, (date,) if date else ())]

    def open_batches(self) -> list[dict]:
        """摆好了还没确认发了的批次。"""
        with _LOCK:
            return [dict(r) for r in self.conn.execute(
                "SELECT batch, account, COUNT(*) AS n, MIN(prepared_at) AS at FROM posts WHERE status='摆好' GROUP BY batch ORDER BY at")]

    def export_xlsx(self, path: str, date: str = "") -> None:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "明细"
        hdr = ["日期", "号", "员工", "标题", "封面", "状态", "摆好 / 开始发", "发布时间", "备注", "视频文件"]
        ws.append(hdr)
        for r in self.rows(date):
            ws.append([r["date"], r["account"], r["employee"], r["title"], r["cover_kind"], r["status"],
                       r["prepared_at"], r["published_at"], r["note"], r["path"]])
        ws2 = wb.create_sheet("按员工汇总")
        ws2.append(["日期", "号", "员工", "已发", "摆好等发布", "没发成", "结果不明", "第一条发布", "最后一条发布"])
        for s in self.summary(date):
            ws2.append([s["date"], s["account"], s["employee"], s["sent"], s["ready"], s["failed"], s["unsure"],
                        s["first_at"] or "", s["last_at"] or ""])
        for w, widths in ((ws, [8, 14, 12, 50, 6, 8, 20, 20, 40, 60]), (ws2, [8, 14, 12, 8, 10, 8, 8, 20, 20])):
            for i, x in enumerate(widths):
                w.column_dimensions[chr(65 + i)].width = x
        wb.save(path)
