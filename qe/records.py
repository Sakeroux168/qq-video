"""发布记录:每条视频哪天的、哪个号、哪个员工、标题、什么时候摆好、什么时候发的(北京时间)。

「发的时间」= 用户在罐头里点完「全部发布」、回软件点「这批发好了」的时间(发布是人点的,软件只能这么记)。
"""
import sqlite3
import threading

from .config import bj_str, data_dir

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
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        with _LOCK:
            self.conn.executescript(_SCHEMA)
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

    def mark_batch_published(self, batch: str) -> int:
        with _LOCK:
            cur = self.conn.execute("UPDATE posts SET status='已发', published_at=? WHERE batch=? AND status='摆好'",
                                    (bj_str(), batch))
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

    def failed_in_batch(self, batch: str) -> list[dict]:
        """这批里没摆成、后来也没记已发的(人可能在罐头里手动补好一起发了)。"""
        with _LOCK:
            rows = [dict(r) for r in self.conn.execute("SELECT * FROM posts WHERE batch=? AND status='没摆成'", (batch,))]
        return [r for r in rows if self.status_of(r["path"]) != "已发"]

    def mark_failed_published(self, batch: str) -> int:
        with _LOCK:
            cur = self.conn.execute("UPDATE posts SET status='已发', published_at=?, note=note || '(人手动补好一起发的)' "
                                    "WHERE batch=? AND status='没摆成'", (bj_str(), batch))
            self.conn.commit()
            return cur.rowcount

    def drop_batch(self, batch: str) -> int:
        """这批没发(人在罐头里删了 / 不要了):摆好的记录作废,下次还能再摆。"""
        with _LOCK:
            cur = self.conn.execute("UPDATE posts SET status='作废' WHERE batch=? AND status='摆好'", (batch,))
            self.conn.commit()
            return cur.rowcount

    def status_of(self, path: str) -> str:
        """这条视频现在的状态:已发 > 摆好 > ''(没摆过 / 没摆成 / 作废都算没摆)。"""
        with _LOCK:
            rows = [r["status"] for r in self.conn.execute("SELECT status FROM posts WHERE path=?", (path,))]
        if "已发" in rows:
            return "已发"
        if "摆好" in rows:
            return "摆好"
        return ""

    def rows(self, date: str = "", account: str = "", employee: str = "") -> list[dict]:
        q, a = "SELECT * FROM posts WHERE status IN ('已发','摆好')", []
        for k, val in (("date", date), ("account", account), ("employee", employee)):
            if val:
                q += f" AND {k}=?"
                a.append(val)
        with _LOCK:
            return [dict(r) for r in self.conn.execute(q + " ORDER BY id", a)]

    def summary(self, date: str = "") -> list[dict]:
        """按 日期 / 号 / 员工 数:已发几条、摆好还没发几条。"""
        q = ("SELECT date, account, employee, SUM(status='已发') AS sent, SUM(status='摆好') AS ready, "
             "MIN(CASE WHEN status='已发' THEN published_at END) AS first_at, MAX(CASE WHEN status='已发' THEN published_at END) AS last_at "
             "FROM posts WHERE status IN ('已发','摆好')" + (" AND date=?" if date else "") +
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
        hdr = ["日期", "号", "员工", "标题", "封面", "状态", "摆好时间", "发布时间", "视频文件"]
        ws.append(hdr)
        for r in self.rows(date):
            ws.append([r["date"], r["account"], r["employee"], r["title"], r["cover_kind"], r["status"],
                       r["prepared_at"], r["published_at"], r["path"]])
        ws2 = wb.create_sheet("按员工汇总")
        ws2.append(["日期", "号", "员工", "已发", "摆好没发", "第一条发布", "最后一条发布"])
        for s in self.summary(date):
            ws2.append([s["date"], s["account"], s["employee"], s["sent"], s["ready"], s["first_at"] or "", s["last_at"] or ""])
        for w, widths in ((ws, [8, 14, 12, 50, 6, 8, 20, 20, 60]), (ws2, [8, 14, 12, 8, 10, 20, 20])):
            for i, x in enumerate(widths):
                w.column_dimensions[chr(65 + i)].width = x
        wb.save(path)
