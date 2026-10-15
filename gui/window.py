"""企鹅号发布助手的窗口。

上面:选日期(人自己选,不自动挑最新 —— 员工会提前建好以后的日期)。
左边:每个号下面的员工文件夹(勾要发的),写着几条、发了几条。
中间:勾上的员工的视频,一条一行:标题、员工、封面横 / 竖(和为什么,能改)、状态。
下面:「摆下一批」「这批发好了」「这批不要了」「这天发完了,挪走」;日志。
「记录」页签:每条什么时候发的,按员工汇总,能导出 Excel。
"""
import os
import time

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QMenu, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QSpinBox, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from qe import cover as C
from qe import folders as F
from qe.config import APP_VERSION, bj_str, data_dir
from qe.adjust import Adjustments
from qe.records import Records

YELLOW = QBrush(QColor("#FFF3C4"))
GREEN = QBrush(QColor("#DDF3E2"))
GREY = QBrush(QColor("#EEEEEE"))


class CoverWorker(QThread):
    """后台认封面上的人(一条几十毫秒,31 条也就几秒;放后台免得界面卡)。"""
    one = Signal(int)
    done = Signal()

    def __init__(self, videos, adj, parent=None):
        super().__init__(parent)
        self.videos, self.adj = videos, adj
        self.stop = False

    def run(self):
        for i, v in enumerate(self.videos):
            if self.stop:
                break
            if not v.cover_kind:
                C.decide(v)
                self.adj.apply(v)          # 人在「封面预览」里调过的套上去
                C.note_wide(v)             # 2.35:1 怎么躲标题区(切头顶 / AI 扩图)
            self.one.emit(i)
        self.done.emit()


class BatchWorker(QThread):
    log = Signal(str)
    one = Signal(object, bool, str)
    finished_batch = Signal(object, str)      # (结果列表 or None, 出错说明)

    def __init__(self, account, videos, shot_dir, parent=None):
        super().__init__(parent)
        self.account, self.videos, self.shot_dir = account, videos, shot_dir
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from qe.prepare import PrepError, Runner, Stop
        r = None
        try:
            r = Runner(log=self.log.emit, stopped=lambda: self._stop, shot_dir=self.shot_dir)
            res = r.prepare_batch(self.account, self.videos, on_one=lambda v, ok, why: self.one.emit(v, ok, why))
            self.finished_batch.emit(res, "")
        except Stop:
            self.finished_batch.emit(None, "停下了")
        except PrepError as e:
            self.finished_batch.emit(None, str(e))
        except Exception as e:
            self.finished_batch.emit(None, f"{type(e).__name__}: {e}")
        finally:
            if r:
                r.close()


class MainWindow(QMainWindow):
    def __init__(self, st, records: Records | None = None):
        super().__init__()
        self.st = st
        self.rec = records or Records()
        self.adj = Adjustments(os.path.join(os.path.dirname(self.rec.path), "封面调整.json") if records else None)
        self.videos: list = []            # 中间表里的
        self.batch_id = ""                # 摆好了、等人点发布的那一批
        self.batch_videos: list = []
        self.worker: BatchWorker | None = None
        self.cover_worker: CoverWorker | None = None
        C.AI_KEY = st.ai_key() if hasattr(st, "ai_key") else ""
        self.setWindowTitle(f"企鹅号发布助手(第{APP_VERSION}版)")
        self.resize(1280, 820)
        self._build()
        self._load_dates()
        ob = self.rec.open_batches()
        if ob:
            b = ob[-1]
            self.batch_id = b["batch"]
            self.say(f"上次摆好的一批还没确认:「{b['account']}」{b['n']} 条({b['at']})。在罐头里发了就点「这批发好了」,不要了就点「这批不要了」。")
        self._refresh_buttons()

    # ---------------- 界面 ----------------
    def _build(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 8, 10, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("要发哪天的:"))
        self.c_date = QComboBox()
        self.c_date.setMinimumWidth(120)
        self.c_date.currentIndexChanged.connect(self._load_tree)
        top.addWidget(self.c_date)
        b = QPushButton("刷新")
        b.clicked.connect(self._load_dates)
        top.addWidget(b)
        top.addSpacing(16)
        self.lab_root = QLabel("")
        self.lab_root.setStyleSheet("color:#777")
        top.addWidget(self.lab_root, 1)
        b = QPushButton("设置…")
        b.clicked.connect(self.edit_settings)
        top.addWidget(b)
        v.addLayout(top)

        sp = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["号 / 员工", "条数"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemChanged.connect(self._tree_changed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        sp.addWidget(self.tree)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.lab_sum = QLabel("左边勾上要发的员工")
        rv.addWidget(self.lab_sum)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["标题(= 文件名)", "号", "员工", "封面", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setToolTip("双击一条:预览封面、拖裁剪框")
        self.table.cellDoubleClicked.connect(lambda r, _c: self.preview_cover(r))
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, wd in ((1, 100), (2, 90), (3, 260), (4, 150)):
            self.table.setColumnWidth(i, wd)
        rv.addWidget(self.table, 1)
        sp.addWidget(right)
        sp.setSizes([280, 1000])
        v.addWidget(sp, 1)

        bar = QHBoxLayout()
        self.b_go = QPushButton("摆下一批(最多 10 条)")
        self.b_go.setMinimumHeight(34)
        self.b_go.setToolTip("在罐头里打开这个号的发布页,传视频、传封面并裁好、选自主声明、补 AI 声明,停在发布前。发布你自己点。")
        self.b_go.clicked.connect(self.start_batch)
        self.b_stop = QPushButton("停")
        self.b_stop.clicked.connect(self.stop_batch)
        self.b_sent = QPushButton("这批发好了")
        self.b_sent.setToolTip("你在罐头里点完「发布 → 全部发布」以后点这个:记下发布时间。")
        self.b_sent.clicked.connect(self.batch_sent)
        self.b_drop = QPushButton("这批不要了")
        self.b_drop.setToolTip("这批没发(在罐头里删了):记录作废,下次还会再摆这些视频。")
        self.b_drop.clicked.connect(self.batch_dropped)
        self.b_manual = QPushButton("选中的标成已发")
        self.b_manual.setToolTip("你在罐头里自己手动发了的(软件没摆成 / 没摆):选中点这个,记成已发,下次就不会再摆它")
        self.b_manual.clicked.connect(self.mark_manual)
        self.b_open = QPushButton("打开所在文件夹")
        self.b_open.setToolTip("在资源管理器里打开选中这条视频所在的文件夹,并选中它(右键列表 / 左边员工也有)")
        self.b_open.clicked.connect(lambda: self.open_selected("video"))
        self.b_preview = QPushButton("预览 / 调封面…")
        self.b_preview.setToolTip("看每个比例的裁剪框在哪;不满意就拖框(双击列表里一条也行)")
        self.b_preview.clicked.connect(lambda: self.preview_cover())
        self.b_move = QPushButton("这天发完了,挪走…")
        self.b_move.clicked.connect(self.move_day)
        for b in (self.b_go, self.b_stop, self.b_sent, self.b_drop):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.b_open)
        bar.addWidget(self.b_manual)
        bar.addWidget(self.b_preview)
        bar.addWidget(self.b_move)
        v.addLayout(bar)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        self.logbox.setMaximumHeight(170)
        v.addWidget(self.logbox)
        tabs.addTab(w, "发视频")

        # 记录页
        r = QWidget()
        rv2 = QVBoxLayout(r)
        rh = QHBoxLayout()
        rh.addWidget(QLabel("日期:"))
        self.c_rec_date = QComboBox()
        self.c_rec_date.currentIndexChanged.connect(self.refresh_records)
        rh.addWidget(self.c_rec_date)
        rh.addStretch(1)
        b = QPushButton("刷新")
        b.clicked.connect(self.refresh_records)
        rh.addWidget(b)
        b = QPushButton("导出 Excel…")
        b.clicked.connect(self.export_records)
        rh.addWidget(b)
        rv2.addLayout(rh)
        rv2.addWidget(QLabel("每个员工发了多少:"))
        self.t_sum = QTableWidget(0, 7)
        self.t_sum.setHorizontalHeaderLabels(["日期", "号", "员工", "已发", "摆好没发", "第一条发布", "最后一条发布"])
        self.t_sum.verticalHeader().setVisible(False)
        self.t_sum.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t_sum.setMaximumHeight(220)
        rv2.addWidget(self.t_sum)
        rv2.addWidget(QLabel("每一条:"))
        self.t_rec = QTableWidget(0, 7)
        self.t_rec.setHorizontalHeaderLabels(["日期", "号", "员工", "标题", "状态", "摆好时间", "发布时间"])
        self.t_rec.verticalHeader().setVisible(False)
        self.t_rec.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t_rec.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        rv2.addWidget(self.t_rec, 1)
        tabs.addTab(r, "记录")
        tabs.currentChanged.connect(lambda i: i == 1 and self.refresh_records())

    def say(self, m: str):
        self.logbox.appendPlainText(f"[{bj_str()[11:]}] {m}")

    # ---------------- 日期 / 员工 / 视频 ----------------
    def _load_dates(self):
        root = self.st["material_root"]
        self.lab_root.setText(f"素材在 {root}")
        dates = F.list_dates(root)
        cur = self.c_date.currentText() or self.st.get("last_date", "")
        self.c_date.blockSignals(True)
        self.c_date.clear()
        self.c_date.addItem("(选一天)", "")
        for d in dates:
            self.c_date.addItem(d, d)
        i = self.c_date.findData(cur)
        self.c_date.setCurrentIndex(i if i > 0 else 0)
        self.c_date.blockSignals(False)
        if not dates:
            self.say(f"素材文件夹里没有日期文件夹:{root}(网络盘连上了吗?)")
        self._load_tree()

    def _load_tree(self):
        date = self.c_date.currentData() or ""
        self.st["last_date"] = date
        self.st.save()
        self.tree.blockSignals(True)
        self.tree.clear()
        if date:
            root = self.st["material_root"]
            for acc, dirs in F.account_dirs(root, date, self.st).items():
                top = QTreeWidgetItem([acc, ""])
                top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                n_all = 0
                for d in dirs:
                    for emp in F.employees(d):
                        vids = F.videos_in(os.path.join(d, emp), acc, date)
                        sent = sum(1 for x in vids if self.rec.status_of(x.path) == "已发")
                        it = QTreeWidgetItem([f"{emp}   ({os.path.basename(d)})", f"{len(vids)} 条" + (f",发了 {sent}" if sent else "")])
                        it.setData(0, Qt.ItemDataRole.UserRole, os.path.join(d, emp))
                        it.setData(0, Qt.ItemDataRole.UserRole + 1, acc)
                        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        it.setCheckState(0, Qt.CheckState.Unchecked)
                        if not vids:
                            it.setDisabled(True)
                        top.addChild(it)
                        n_all += len(vids)
                top.setText(1, f"{n_all} 条" if dirs else "这天没有它的文件夹")
                self.tree.addTopLevelItem(top)
                top.setExpanded(True)
            unk = F.unknown_dirs(root, date, self.st)
            if unk:
                self.say(f"{date} 里这些文件夹不认识是哪个号的:{'、'.join(unk)}(在「设置」里给号加上这个缩写)")
        self.tree.blockSignals(False)
        self._load_videos()

    def _tree_changed(self, *_a):
        self._load_videos()

    def checked_dirs(self) -> list[tuple[str, str]]:
        out = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for k in range(top.childCount()):
                it = top.child(k)
                if it.checkState(0) == Qt.CheckState.Checked:
                    out.append((it.data(0, Qt.ItemDataRole.UserRole + 1), it.data(0, Qt.ItemDataRole.UserRole)))
        return out

    def _load_videos(self):
        date = self.c_date.currentData() or ""
        self.videos = []
        for acc, d in self.checked_dirs():
            self.videos += F.videos_in(d, acc, date)
        self.table.setRowCount(len(self.videos))
        for i, v in enumerate(self.videos):
            self._fill_row(i)
        self._update_sum()
        if self.cover_worker and self.cover_worker.isRunning():
            self.cover_worker.stop = True
            self.cover_worker.wait(3000)
        todo = [v for v in self.videos if not self.rec.status_of(v.path)]
        if todo:
            self.cover_worker = CoverWorker(self.videos, self.adj, self)
            self.cover_worker.one.connect(self._fill_row)
            self.cover_worker.start()
        self._refresh_buttons()

    def _fill_row(self, i: int):
        if i >= len(self.videos) or i >= self.table.rowCount():
            return
        v = self.videos[i]
        stt = self.rec.status_of(v.path)
        cov = v.cover_why if (v.cover_kind or v.warn) else "认人中…"
        for c, t in enumerate([v.title, v.account, v.employee, cov, stt or "没发"]):
            it = QTableWidgetItem(t)
            if stt == "已发":
                it.setBackground(GREEN)
            elif stt == "摆好":
                it.setBackground(GREY)
            elif v.warn and c == 3:
                it.setBackground(YELLOW)
            if c == 0 and len(v.title) > 64:
                it.setToolTip("标题超过 64 个字,企鹅号放不下")
            self.table.setItem(i, c, it)

    def _update_sum(self):
        n = len(self.videos)
        st = [self.rec.status_of(v.path) for v in self.videos]
        self.lab_sum.setText(f"勾上的一共 {n} 条:已发 {st.count('已发')},摆好没发 {st.count('摆好')},还没发 {st.count('')}"
                             if n else "左边勾上要发的员工")

    # ---------- 打开文件所在位置 ----------
    @staticmethod
    def reveal(path: str) -> bool:
        """在资源管理器里打开 path 所在的文件夹并选中它(path 是文件夹就直接打开)。"""
        import subprocess
        if not path or not os.path.exists(path):
            return False
        if os.path.isdir(path):
            os.startfile(path)
        else:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        return True

    def open_selected(self, what: str = "video"):
        rows = sorted({ix.row() for ix in self.table.selectedIndexes()})
        if not rows:
            d = self._cur_dir()
            if d and self.reveal(d):
                return
            QMessageBox.information(self, "打开所在文件夹", "先在列表里选中一条视频(或者左边点一个员工)。")
            return
        v = self.videos[rows[0]]
        path = v.cover if what == "cover" else v.path
        if not self.reveal(path):
            QMessageBox.information(self, "打开所在文件夹", f"找不到这个文件了(被挪走了?):{path}")

    def _cur_dir(self) -> str:
        it = self.tree.currentItem()
        if it is None:
            return ""
        d = it.data(0, Qt.ItemDataRole.UserRole)
        if d:
            return d
        date = self.c_date.currentData() or ""
        return os.path.join(self.st["material_root"], date) if date else self.st["material_root"]

    def _table_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        if not self.table.item(row, 0) or not self.table.item(row, 0).isSelected():
            self.table.selectRow(row)
        m = QMenu(self)
        m.addAction("打开视频所在文件夹", lambda: self.open_selected("video"))
        m.addAction("打开封面所在文件夹", lambda: self.open_selected("cover"))
        m.addSeparator()
        m.addAction("预览 / 调封面…", lambda: self.preview_cover(row))
        m.addAction("标成已发(我手动发了)", self.mark_manual)
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _tree_menu(self, pos):
        it = self.tree.itemAt(pos)
        if it is None:
            return
        self.tree.setCurrentItem(it)
        m = QMenu(self)
        m.addAction("打开这个文件夹", lambda: self.reveal(self._cur_dir()))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def mark_manual(self):
        rows = sorted({ix.row() for ix in self.table.selectedIndexes()})
        vids = [self.videos[r] for r in rows if self.rec.status_of(self.videos[r].path) != "已发"]
        if not vids:
            QMessageBox.information(self, "标成已发", "先在列表里选中你手动发了的那几条(已经是「已发」的不用选)。")
            return
        if QMessageBox.question(self, "标成已发", f"这 {len(vids)} 条你已经在罐头里手动发了?\n\n"
                                + "\n".join(f"· {v.title[:30]}" for v in vids[:8])) != QMessageBox.StandardButton.Yes:
            return
        for v in vids:
            self.rec.manual_published(v)
        self.say(f"记下:{len(vids)} 条是你手动发的")
        for r in rows:
            self._fill_row(r)
        self._update_sum()

    def preview_cover(self, row: int | None = None):
        """封面预览:看软件选的、拖框改。"""
        if self.cover_worker and self.cover_worker.isRunning():
            QMessageBox.information(self, "封面预览", "封面还在认人,等几秒再看。")
            return
        if not self.videos:
            QMessageBox.information(self, "封面预览", "先在左边勾上员工。")
            return
        if row is None:
            sel = sorted({ix.row() for ix in self.table.selectedIndexes()})
            row = sel[0] if sel else 0
        from gui.cover_dialog import CoverDialog
        d = CoverDialog(self.videos, row, self.adj, self)
        d.changed.connect(self._fill_row)
        d.exec()

    # ---------------- 一批 ----------------
    def _refresh_buttons(self):
        running = bool(self.worker and self.worker.isRunning())
        self.b_go.setEnabled(not running and not self.batch_id)
        self.b_stop.setEnabled(running)
        self.b_sent.setEnabled(not running and bool(self.batch_id))
        self.b_drop.setEnabled(not running and bool(self.batch_id))
        self.b_move.setEnabled(not running and bool(self.c_date.currentData()))

    def next_batch(self) -> tuple[str, list]:
        """下一批:勾上的里面还没发 / 没摆的,同一个号的前 10 条(一批只能是一个号)。"""
        todo = [v for v in self.videos if not self.rec.status_of(v.path) and (v.cover_kind or v.cover_why)]
        if not todo:
            return "", []
        acc = todo[0].account
        n = max(1, min(10, int(self.st.get("batch_size", 10) or 10)))
        return acc, [v for v in todo if v.account == acc][:n]

    def start_batch(self):
        if self.cover_worker and self.cover_worker.isRunning():
            QMessageBox.information(self, "企鹅号发布助手", "封面还在认人,等几秒再点。")
            return
        acc, vids = self.next_batch()
        if not vids:
            QMessageBox.information(self, "企鹅号发布助手", "勾上的员工里没有要发的了(都发过 / 摆好了)。")
            return
        warn = [v for v in vids if v.warn]
        nocover = [v for v in vids if not v.cover]
        if nocover:
            QMessageBox.warning(self, "摆下一批", f"这批里有 {len(nocover)} 条没有无字封面(png),比如「{nocover[0].title[:24]}」。\n\n"
                                "jpg 有字不能用,让员工补上 png 再摆。")
            return
        msg = f"在罐头里给「{acc}」摆 {len(vids)} 条:\n\n" + "\n".join(f"· {v.title[:30]}" for v in vids)
        if warn:
            msg += f"\n\n其中 {len(warn)} 条封面标黄,建议先点「预览 / 调封面」看一眼。"
        msg += "\n\n软件只摆好,不点发布。摆的时候别在罐头里切到别的号。开始吗?"
        if QMessageBox.question(self, "摆下一批", msg) != QMessageBox.StandardButton.Yes:
            return
        self.batch_id = f"{acc}-{bj_str().replace(' ', '_').replace(':', '')}"
        self.batch_videos = vids
        shots = str(data_dir() / "截图" / bj_str()[:10])
        self.worker = BatchWorker(acc, vids, shots, self)
        self.worker.log.connect(self.say)
        self.worker.one.connect(self._one_done)
        self.worker.finished_batch.connect(self._batch_done)
        self.worker.start()
        self.say(f"开始给「{acc}」摆 {len(vids)} 条…")
        self._refresh_buttons()

    def stop_batch(self):
        if self.worker:
            self.worker.stop()
            self.say("正在停…")

    def _one_done(self, v, ok, why):
        if ok:
            self.rec.prepared(v, self.batch_id)
        else:
            self.rec.failed(v, self.batch_id, why)
        if v in self.videos:
            self._fill_row(self.videos.index(v))
        self._update_sum()

    def _batch_done(self, res, err):
        ok = [x for x in (res or []) if x[1]]
        bad = [x for x in (res or []) if not x[1]]
        if not ok:
            self.batch_id = ""                         # 一条都没摆上:不用等人确认
        if err:
            self.say(f"✘ 没摆完:{err}")
            QMessageBox.warning(self, "摆下一批", f"没摆完:{err}" + (f"\n\n已经摆好 {len(ok)} 条,在罐头里看看。" if ok else ""))
        elif ok:
            text = f"「{self.batch_videos[0].account}」摆好 {len(ok)} 条。\n\n去罐头里检查,没问题就点「发布 → 全部发布」,再回来点「这批发好了」。"
            if bad:
                text += f"\n\n有 {len(bad)} 条没摆成(在罐头里也把它们的小页签关掉,或者手动弄好):\n" + "\n".join(
                    f"· {v.title[:24]}:{why}" for v, _o, why in bad[:6])
            self.say(f"摆好 {len(ok)} 条,等你在罐头里点发布")
            QMessageBox.information(self, "摆好了", text)
        self._refresh_buttons()
        self._update_sum()

    def batch_sent(self):
        if not self.batch_id:
            return
        if QMessageBox.question(self, "这批发好了", "你已经在罐头里点了「发布 → 全部发布」,这批都发出去了吗?") != QMessageBox.StandardButton.Yes:
            return
        n = self.rec.mark_batch_published(self.batch_id)
        self.say(f"记下:这批 {n} 条发了({bj_str()})")
        bad = self.rec.failed_in_batch(self.batch_id)
        if bad and QMessageBox.question(self, "这批发好了", f"这批里还有 {len(bad)} 条软件没摆成(比如「{bad[0]['title'][:20]}」)。\n\n"
                                        "你在罐头里手动补好、一起发出去了吗?") == QMessageBox.StandardButton.Yes:
            m = self.rec.mark_failed_published(self.batch_id)
            self.say(f"记下:没摆成的 {m} 条也是你手动补好一起发的")
        self.batch_id = ""
        self._after_batch()

    def batch_dropped(self):
        if not self.batch_id:
            return
        if QMessageBox.question(self, "这批不要了", "这批没发(在罐头里删掉了)?记录作废,下次这些视频还会再摆。") != QMessageBox.StandardButton.Yes:
            return
        n = self.rec.drop_batch(self.batch_id)
        self.say(f"这批 {n} 条作废了")
        self.batch_id = ""
        self._after_batch()

    def _after_batch(self):
        for i in range(len(self.videos)):
            self._fill_row(i)
        self._update_sum()
        self._refresh_buttons()

    # ---------------- 挪走一整天 ----------------
    def move_day(self):
        date = self.c_date.currentData() or ""
        if not date:
            return
        if self.batch_id:
            QMessageBox.information(self, "挪走", "还有一批摆好了没确认,先点「这批发好了」或「这批不要了」。")
            return
        dst = F.archive_target(self.st, date)
        src = os.path.join(self.st["material_root"], date)
        left = []
        for acc, dirs in F.account_dirs(self.st["material_root"], date, self.st).items():
            for d in dirs:
                for emp in F.employees(d):
                    left += [v for v in F.videos_in(os.path.join(d, emp), acc, date) if self.rec.status_of(v.path) != "已发"]
        msg = f"把整个「{date}」文件夹剪切到:\n{dst}\n"
        if left:
            msg += f"\n注意:里面还有 {len(left)} 条软件没记成「已发」(比如「{left[0].title[:20]}」)。"
        if QMessageBox.question(self, "这天发完了,挪走", msg + "\n挪吗?") != QMessageBox.StandardButton.Yes:
            return
        try:
            F.move_date(self.st, date)
        except FileExistsError:
            # 先留的口子(用户:「先留个功能接口 后面我搞清楚在做」):目标已有同名日期文件夹,问人要不要合并
            if QMessageBox.question(self, "已经有了", f"那边已经有「{date}」文件夹了:\n{dst}\n\n把这边的东西合并进去吗?(同名的文件不覆盖,改名加 (2))"
                                    ) != QMessageBox.StandardButton.Yes:
                return
            try:
                F.move_date(self.st, date, merge=True)
            except OSError as e:
                QMessageBox.warning(self, "挪走", f"合并时出错:{e}")
                return
        except OSError as e:
            QMessageBox.warning(self, "挪走", f"挪不动:{e}\n\n(有文件开着?关掉再试)")
            return
        self.say(f"「{date}」挪到了 {dst}")
        self._load_dates()

    # ---------------- 记录 ----------------
    def refresh_records(self):
        cur = self.c_rec_date.currentData()
        dates = sorted({r["date"] for r in self.rec.rows()})
        self.c_rec_date.blockSignals(True)
        self.c_rec_date.clear()
        self.c_rec_date.addItem("全部", "")
        for d in dates:
            self.c_rec_date.addItem(d, d)
        i = self.c_rec_date.findData(cur)
        self.c_rec_date.setCurrentIndex(max(0, i))
        self.c_rec_date.blockSignals(False)
        date = self.c_rec_date.currentData() or ""
        s = self.rec.summary(date)
        self.t_sum.setRowCount(len(s))
        for i, x in enumerate(s):
            for c, k in enumerate(["date", "account", "employee", "sent", "ready", "first_at", "last_at"]):
                self.t_sum.setItem(i, c, QTableWidgetItem(str(x[k] if x[k] is not None else "")))
        rows = self.rec.rows(date)
        self.t_rec.setRowCount(len(rows))
        for i, x in enumerate(rows):
            for c, k in enumerate(["date", "account", "employee", "title", "status", "prepared_at", "published_at"]):
                self.t_rec.setItem(i, c, QTableWidgetItem(str(x[k] or "")))

    def export_records(self):
        date = self.c_rec_date.currentData() or ""
        p, _ = QFileDialog.getSaveFileName(self, "导出发布记录", f"企鹅号发布记录_{date or '全部'}.xlsx", "Excel (*.xlsx)")
        if not p:
            return
        try:
            self.rec.export_xlsx(p, date)
            QMessageBox.information(self, "导出", f"导出到了:\n{p}")
        except Exception as e:
            QMessageBox.warning(self, "导出", f"导不出来:{e}")

    # ---------------- 设置 ----------------
    def edit_settings(self):
        d = QDialog(self)
        d.setWindowTitle("设置")
        d.resize(640, 320)
        f = QFormLayout(d)
        e_root = QLineEdit(self.st["material_root"])
        e_arc = QLineEdit(self.st["archive_root"])
        e_acc = QPlainTextEdit("\n".join(f"{a['name']}={'、'.join(a.get('aliases') or [])}" for a in self.st["accounts"]))
        e_acc.setToolTip("一行一个号:罐头里的号名=日期文件夹下面的缩写(几个用顿号隔开)")
        sp = QSpinBox()
        sp.setRange(1, 10)
        sp.setValue(int(self.st.get("batch_size", 10)))
        e_key = QLineEdit(self.st.get("ai_key", ""))
        e_key.setEchoMode(QLineEdit.EchoMode.Password)
        e_key.setPlaceholderText("空着就用百家号发布助手里填的" + ("(找到了)" if self.st.ai_key() else "(没找到)"))
        f.addRow("素材文件夹", e_root)
        f.addRow("发完挪到", e_arc)
        f.addRow("", QLabel("{month} 会换成日期的月份,比如 10.15 → 10"))
        f.addRow("号和缩写", e_acc)
        f.addRow("一批几条", sp)
        f.addRow("阿里百炼 Key", e_key)
        f.addRow("", QLabel("大头照的 2.35:1 封面要 AI 扩图时用(一张几毛钱)"))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        f.addRow(bb)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        accs = []
        for line in e_acc.toPlainText().splitlines():
            if "=" in line:
                n, a = line.split("=", 1)
                if n.strip():
                    accs.append({"name": n.strip(), "aliases": [x.strip() for x in a.replace(",", "、").replace("，", "、").split("、") if x.strip()]})
            elif line.strip():
                accs.append({"name": line.strip(), "aliases": []})
        self.st.update(material_root=e_root.text().strip(), archive_root=e_arc.text().strip(), accounts=accs or self.st["accounts"],
                       batch_size=sp.value(), ai_key=e_key.text().strip())
        C.AI_KEY = self.st.ai_key()
        self.st.save()
        self._load_dates()

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            if QMessageBox.question(self, "企鹅号发布助手", "还在摆,要停下来关掉吗?") != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.worker.stop()
            self.worker.wait(20000)
        super().closeEvent(e)
