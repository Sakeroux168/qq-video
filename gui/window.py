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
RED = QBrush(QColor("#FFE1E1"))


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
    finished_batch = Signal(object, str, str)      # (结果列表 or None, 出错说明, 自动发布:""没发 / "ok"发了 / 其它 = 为什么没发)

    def __init__(self, account, videos, shot_dir, parent=None, auto_publish: bool = False):
        super().__init__(parent)
        self.account, self.videos, self.shot_dir = account, videos, shot_dir
        self.auto_publish = auto_publish
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from qe.prepare import PrepError, Runner, Stop
        r = None
        try:
            r = Runner(log=self.log.emit, stopped=lambda: self._stop, shot_dir=self.shot_dir)
            res = r.prepare_batch(self.account, self.videos, on_one=lambda v, ok, why: self.one.emit(v, ok, why))
            pub = ""
            if self.auto_publish:
                bad = [v for v, ok, _w in res if not ok]
                yellow = [v for v, ok, _w in res if ok and v.warn]
                if bad:
                    pub = f"有 {len(bad)} 条没摆好,没自动发布"
                elif yellow:
                    pub = f"有 {len(yellow)} 条封面标黄(要人看一眼),没自动发布"
                else:
                    try:
                        pub = r.publish_all([v.title for v in self.videos])
                    except PrepError as e:
                        pub = f"自动发布停下了:{e}"
            self.finished_batch.emit(res, "", pub)
        except Stop:
            self.finished_batch.emit(None, "停下了", "")
        except PrepError as e:
            self.finished_batch.emit(None, str(e), "")
        except Exception as e:
            self.finished_batch.emit(None, f"{type(e).__name__}: {e}", "")
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
        from gui.widgets import StatCards, shell
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 16, 20, 12)
        v.setSpacing(10)
        title = QLabel("教育号 · 在创作罐头里摆好,人点发布")
        title.setObjectName("pageTitle")
        v.addWidget(title)
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
        self.lab_root.setStyleSheet("color:#8a8b91")
        from PySide6.QtWidgets import QSizePolicy
        self.lab_root.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)   # 路径太长就截,不撑宽窗口
        top.addWidget(self.lab_root, 1)
        self._top = top
        v.addLayout(top)
        self.cards = StatCards([("all", "勾上的视频"), ("sent", "已发"), ("ready", "摆好没发"), ("todo", "还没发")])
        v.addWidget(self.cards)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.hint.hide()
        v.addWidget(self.hint)
        self.row_note: dict[str, str] = {}            # 这一批里每条的临时状态:排队中 / 没摆成:原因

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
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        for i, wd in ((1, 96), (2, 70), (3, 200), (4, 80)):
            self.table.setColumnWidth(i, wd)
        rv.addWidget(self.table, 1)
        sp.addWidget(right)
        sp.setSizes([300, 900])
        sp.setStretchFactor(0, 1)
        sp.setStretchFactor(1, 3)
        v.addWidget(sp, 1)

        bar = QHBoxLayout()
        self.b_go = QPushButton("摆下一批")
        self.b_go.setObjectName("primary")
        self.b_go.setMinimumHeight(34)
        self.b_go.setToolTip("在罐头里打开这个号的发布页,传视频、传封面并裁好、选自主声明、补 AI 声明,停在发布前。发布你自己点。")
        self.b_go.clicked.connect(self.start_batch)
        self.b_stop = QPushButton("停")
        self.b_stop.clicked.connect(self.stop_batch)
        self.b_sent = QPushButton("这批发好了")
        self.b_sent.setToolTip("你在罐头里点完「发布 → 全部发布」以后点这个:记下发布时间。")
        self.b_sent.clicked.connect(self.batch_sent)
        from PySide6.QtWidgets import QCheckBox
        self.k_auto = QCheckBox("摆好后自动点发布")
        self.k_auto.setToolTip("勾上:整批都摆好、没有标黄的,软件自己在罐头里点「发布 → 全部发布」,记下发布时间,再摆下一批,直到勾上的都发完。\n"
                               "有一条没摆好、或者有标黄的,就停下来叫你。点完发布弹出没见过的框也停下来。")
        self.k_auto.setChecked(bool(self.st.get("auto_publish", False)))
        self.k_auto.toggled.connect(self._auto_toggled)
        self.b_drop = QPushButton("这批不要了")
        self.b_drop.setToolTip("这批没发(在罐头里删了):记录作废,下次还会再摆这些视频。")
        self.b_drop.clicked.connect(self.batch_dropped)
        self.b_manual = QPushButton("标成已发")
        self.b_manual.setToolTip("你在罐头里自己手动发了的(软件没摆成 / 没摆):选中点这个,记成已发,下次就不会再摆它")
        self.b_manual.clicked.connect(self.mark_manual)
        self.b_open = QPushButton("打开文件夹")
        self.b_open.setToolTip("在资源管理器里打开选中这条视频所在的文件夹,并选中它(右键列表 / 左边员工也有)")
        self.b_open.clicked.connect(lambda: self.open_selected("video"))
        self.b_preview = QPushButton("预览封面…")
        self.b_preview.setToolTip("看每个比例的裁剪框在哪;不满意就拖框(双击列表里一条也行)")
        self.b_preview.clicked.connect(lambda: self.preview_cover())
        self.b_move = QPushButton("这天发完,挪走…")
        self.b_move.clicked.connect(self.move_day)
        for b in (self.b_go, self.b_stop, self.b_sent, self.b_drop):
            bar.addWidget(b)
        bar.addWidget(self.k_auto)
        bar.addStretch(1)
        for b in (self.b_open, self.b_move):          # 次要的放上面一行右边;「标成已发」「预览封面」在列表右键里
            self._top.addWidget(b)
        self.b_manual.hide()
        self.b_preview.hide()
        v.addLayout(bar)
        self.logbox = QPlainTextEdit()
        self.logbox.setObjectName("log")
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        self.logbox.setMaximumHeight(110)
        v.addWidget(self.logbox)
        from gui.api_tab import ApiTab
        self.api_tab = ApiTab(self.st, self.rec, self.say, self)

        # 记录页
        r = QWidget()
        rv2 = QVBoxLayout(r)
        rv2.setContentsMargins(20, 16, 20, 12)
        title = QLabel("数据记录 · 每条哪天、哪个号、什么时候发的")
        title.setObjectName("pageTitle")
        rv2.addWidget(title)
        self.rec_cards = StatCards([("sent", "已发"), ("fail", "没发成"), ("unsure", "不确定发没发"), ("ready", "摆好没发")])
        rv2.addWidget(self.rec_cards)
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
        self.t_sum = QTableWidget(0, 9)
        self.t_sum.setHorizontalHeaderLabels(["日期", "号", "员工", "已发", "摆好没发", "没发成", "结果不明", "第一条发布", "最后一条发布"])
        self.t_sum.verticalHeader().setVisible(False)
        self.t_sum.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t_sum.setMaximumHeight(220)
        rv2.addWidget(self.t_sum)
        rv2.addWidget(QLabel("每一条:"))
        self.t_rec = QTableWidget(0, 8)
        self.t_rec.setHorizontalHeaderLabels(["日期", "号", "员工", "标题", "状态", "摆好 / 开始发", "发布时间", "备注(没发成的原因)"])
        self.t_rec.verticalHeader().setVisible(False)
        self.t_rec.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t_rec.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        rv2.addWidget(self.t_rec, 1)
        # 外壳:左边导航(教育号 / 16 个号 / 数据记录 / 设置),右边一页一页换(用户选的「抖音创作者中心」那种)
        from gui.daily_tab import DailyTab
        self.daily = DailyTab(self.st, self.rec, self)
        root, self.nav, self.stack = shell([("", "教育号", w), ("", "16 个号", self.api_tab), ("", "每日汇总", self.daily),
                                            ("", "数据记录", r)],
                                           self.edit_settings, f"第 {APP_VERSION} 版")
        self.setCentralWidget(root)
        self.stack.currentChanged.connect(lambda i: self.daily.refresh() if i == 2 else (i == 3 and self.refresh_records()))

    def say(self, m: str):
        self.logbox.appendPlainText(f"[{bj_str()[11:]}] {m}")

    # ---------------- 日期 / 员工 / 视频 ----------------
    def _load_dates(self):
        root = self.st["material_root"]
        self.lab_root.setText(f"素材在 {root}")
        self.lab_root.setToolTip(root)
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
        if self.st.get("last_date") != date:          # 真换了日期才存(审查:原来一打开就存一次,会冲掉别处改的设置)
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
                        it = QTreeWidgetItem([emp, f"{len(vids)} 条" + (f",发了 {sent}" if sent else "")])
                        it.setToolTip(0, f"{emp}({os.path.basename(d)})")
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
        note = "" if stt else self.row_note.get(v.path, "")
        cov = v.cover_why if (v.cover_kind or v.warn) else "认人中…"
        for c, t in enumerate([v.title, v.account, v.employee, cov, stt or note or "没发"]):
            it = QTableWidgetItem(t)
            if c == 4 and note:
                it.setToolTip(note)
            if stt == "已发":
                it.setBackground(GREEN)
            elif stt == "摆好":
                it.setBackground(GREY)
            elif note.startswith("没摆成"):
                it.setBackground(RED)
            elif v.warn and c == 3:
                it.setBackground(YELLOW)
            if c == 0 and len(v.title) > 64:
                it.setToolTip("标题超过 64 个字,企鹅号放不下")
            self.table.setItem(i, c, it)

    def _update_sum(self):
        n = len(self.videos)
        st = [self.rec.status_of(v.path) for v in self.videos]
        self.lab_sum.setText("" if n else "左边勾上要发的员工")
        self.lab_sum.setVisible(not n)
        self.cards.set(all=n, sent=(st.count("已发"), "good" if n and st.count("已发") == n else ""),
                       ready=(st.count("摆好"), "warn" if st.count("摆好") else ""), todo=st.count(""))

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
        if not self._ask("标成已发", f"这 {len(vids)} 条你已经在罐头里手动发了?\n\n"
                         + "\n".join(f"· {v.title[:30]}" for v in vids[:8]), "标成已发", "先不"):
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
        waiting = bool(self.batch_id) and not running
        for b, main in ((self.b_go, not waiting), (self.b_sent, waiting)):
            if (b.objectName() == "primary") != main:
                b.setObjectName("primary" if main else "")
                b.style().unpolish(b)
                b.style().polish(b)
        if running:
            self.hint.setText("正在摆…摆的时候别在罐头里切到别的号。要停就点「停」。")
            self.hint.show()
        elif waiting:
            n = self.rec.ready_in_batch(self.batch_id)
            acc = self.batch_videos[0].account if self.batch_videos else ""
            self.hint.setText(f"「{acc}」这批 {n} 条摆好了 → 去罐头里检查,点「发布 → 全部发布」→ 回来点「这批发好了」"
                              "(不要了就在罐头里删掉,点「这批不要了」)")
            self.hint.show()
        else:
            self.hint.hide()
        self.b_go.setEnabled(not running and not self.batch_id)
        self.b_stop.setEnabled(running)
        self.b_sent.setEnabled(not running and bool(self.batch_id))
        self.b_drop.setEnabled(not running and bool(self.batch_id))
        self.b_move.setEnabled(not running and bool(self.c_date.currentData()))
        self.c_date.setEnabled(not running)
        self.tree.setEnabled(not running)

    def next_batch(self) -> tuple[str, list]:
        """下一批:勾上的里面还没发 / 没摆的,同一个号的前 10 条(一批只能是一个号)。"""
        todo = [v for v in self.videos if not self.rec.status_of(v.path) and (v.cover_kind or v.cover_why) and v.cover]
        if not todo:
            return "", []
        acc = todo[0].account
        n = max(1, min(10, int(self.st.get("batch_size", 10) or 10)))
        return acc, [v for v in todo if v.account == acc][:n]

    def _ask(self, title: str, text: str, yes: str, no: str, default_no: bool = False) -> bool:
        import gui.api_tab as A                       # 中文动词按钮的确认框(和接口页同一个)
        return A.ask(self, title, text, yes, no, default_no=default_no)

    def _nothing_left(self) -> str:
        """没有能摆的了:说清楚是真发完了,还是剩下的缺无字封面(png)。"""
        nocover = [v for v in self.videos if not self.rec.status_of(v.path) and (v.cover_kind or v.cover_why) and not v.cover]
        if nocover:
            return (f"能摆的都摆完了,但还有 {len(nocover)} 条没有无字封面(png),没摆,比如「{nocover[0].title[:24]}」。\n\n"
                    "让员工补上 png 以后点「刷新」再摆。")
        return "勾上的员工都发完了(或者都摆好了等你确认)。"

    def _auto_toggled(self, on: bool):
        self.st["auto_publish"] = bool(on)
        self.st.save()
        if on:
            self.say("已勾上:摆好后软件自己点「全部发布」,接着摆下一批(有问题会停下来叫你)")

    def start_batch(self, chained: bool = False):
        if self.cover_worker and self.cover_worker.isRunning():
            QMessageBox.information(self, "企鹅号发布助手", "封面还在认人,等几秒再点。")
            return
        acc, vids = self.next_batch()
        if not vids:
            QMessageBox.information(self, "企鹅号发布助手", self._nothing_left())
            return
        warn = [v for v in vids if v.warn]
        # 没有无字封面(png)的不摆,跳过(审查:原来一条没 png 就挡住这个号后面所有的)
        nocover = [v for v in self.videos if not self.rec.status_of(v.path) and (v.cover_kind or v.cover_why) and not v.cover]
        msg = f"在罐头里给「{acc}」摆 {len(vids)} 条:\n\n" + "\n".join(f"· {v.title[:30]}" for v in vids)
        if nocover:
            msg += (f"\n\n另有 {len(nocover)} 条没有无字封面(png)先跳过,比如「{nocover[0].title[:24]}」"
                    "(jpg 有字不能用,让员工补上 png)。")
        if warn:
            msg += f"\n\n其中 {len(warn)} 条封面标黄,建议先点「预览封面」看一眼。"
        auto = self.k_auto.isChecked()
        msg += ("\n\n摆好后软件自己点「全部发布」,接着摆下一批(有标黄 / 没摆好的会停下来叫你)。" if auto else
                "\n\n软件只摆好,不点发布。") + "摆的时候别在罐头里切到别的号。开始吗?"
        if not chained and not self._ask("摆下一批", msg, "开始摆", "先不"):
            return
        if chained:
            if (self.c_date.currentData(), sorted(self.checked_dirs())) != getattr(self, "_chain_key", None):
                QMessageBox.information(self, "自动发布停下了", "摆的时候换了日期 / 改了勾选的员工,自动连发先停下。\n\n"
                                                              "要接着发,确认一下日期和员工,再点「摆下一批」。")
                return
        else:
            self._chain_key = (self.c_date.currentData(), sorted(self.checked_dirs()))
        self.batch_id = f"{acc}-{bj_str().replace(' ', '_').replace(':', '')}"
        self.batch_videos = vids
        shots = str(data_dir() / "截图" / bj_str()[:10])
        self.worker = BatchWorker(acc, vids, shots, self, auto_publish=self.k_auto.isChecked())
        self.worker.log.connect(self.say)
        self.worker.one.connect(self._one_done)
        self.worker.finished_batch.connect(self._batch_done)
        self.worker.start()
        for v in vids:                                # 这批的行先写「排队中」,摆到哪条一眼看得出
            self.row_note[v.path] = "排队中"
            if v in self.videos:
                self._fill_row(self.videos.index(v))
        self.say(f"开始给「{acc}」摆 {len(vids)} 条…")
        self._refresh_buttons()

    def stop_batch(self):
        self._chain_stop = True                         # 自动接着摆的那 3 秒里点了停:不再接着摆
        if self.worker:
            self.worker.stop()
            self.say("正在停…")

    def _one_done(self, v, ok, why):
        if ok:
            self.rec.prepared(v, self.batch_id)
            self.row_note.pop(v.path, None)
        else:
            self.rec.failed(v, self.batch_id, why)
            self.row_note[v.path] = f"没摆成:{why}"
        if v in self.videos:
            self._fill_row(self.videos.index(v))
        self._update_sum()

    def _batch_done(self, res, err, pub=""):
        for v in self.batch_videos:                   # 没轮到摆的(停了 / 出错)不再写「排队中」
            if self.row_note.get(v.path) == "排队中":
                self.row_note.pop(v.path, None)
                if v in self.videos:
                    self._fill_row(self.videos.index(v))
        ok = [x for x in (res or []) if x[1]]
        bad = [x for x in (res or []) if not x[1]]
        ready = self.rec.ready_in_batch(self.batch_id) if self.batch_id else 0
        if not ok and not ready:
            self.batch_id = ""                         # 一条都没摆上:不用等人确认
        if pub == "ok":
            n = self.rec.mark_batch_published(self.batch_id)
            self.say(f"软件点了「全部发布」:这批 {n} 条发出去了({bj_str()})")
            self.batch_id = ""
            self._after_batch()
            if self.k_auto.isChecked() and self.next_batch()[1]:
                self.say("3 秒后摆下一批…(点「停」不再继续)")
                self._chain_stop = False
                from PySide6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: None if getattr(self, "_chain_stop", False) or not self.k_auto.isChecked()
                                  else self.start_batch(chained=True))
            elif self.k_auto.isChecked():
                QMessageBox.information(self, "发完了", self._nothing_left())
            return
        if pub:
            self.say(f"⚠ {pub}")
        if err:
            n_ok = max(len(ok), ready)
            self.say(f"没摆完:{err}" + (f"(已经摆好 {n_ok} 条,在罐头里看看)" if n_ok else ""))
            box = (lambda *a: None) if err == "停下了" and not n_ok else \
                QMessageBox.information if err == "停下了" else QMessageBox.warning
            box(self, "摆下一批", ("你点了「停」,停下来了。" if err == "停下了" else f"没摆完:{err}") + (
                f"\n\n已经摆好 {n_ok} 条,在罐头里看看:要发就点「发布 → 全部发布」再回来点「这批发好了」;"
                "不要就在罐头里删掉,回来点「这批不要了」。" if n_ok else ""))
        elif ok:
            text = f"「{self.batch_videos[0].account}」摆好 {len(ok)} 条。\n\n去罐头里检查,没问题就点「发布 → 全部发布」,再回来点「这批发好了」。"
            if bad:
                text += f"\n\n有 {len(bad)} 条没摆成(在罐头里也把它们的小页签关掉,或者手动弄好):\n" + "\n".join(
                    f"· {v.title[:24]}:{why}" for v, _o, why in bad[:6])
            self.say(f"摆好 {len(ok)} 条,等你在罐头里点发布")
            if pub:
                text = f"{pub}。\n\n" + text
            QMessageBox.information(self, "摆好了", text)
        self._refresh_buttons()
        self._update_sum()

    def batch_sent(self):
        if not self.batch_id:
            return
        n_ready = self.rec.ready_in_batch(self.batch_id)
        acc = self.batch_videos[0].account if self.batch_videos else ""
        if not self._ask("这批发好了", f"「{acc}」这批 {n_ready} 条,你已经在罐头里点了「发布 → 全部发布」,都发出去了?",
                         "都发了,记下", "还没"):
            return
        n = self.rec.mark_batch_published(self.batch_id)
        self.say(f"记下:这批 {n} 条发了({bj_str()})")
        bad = self.rec.failed_in_batch(self.batch_id)
        if bad and self._ask("这批发好了", f"这批里还有 {len(bad)} 条软件没摆成(比如「{bad[0]['title'][:20]}」)。\n\n"
                                         "你在罐头里手动补好、一起发出去了吗?", "补好一起发了", "没有"):
            m = self.rec.mark_failed_published(self.batch_id)
            self.say(f"记下:没摆成的 {m} 条也是你手动补好一起发的")
        self.batch_id = ""
        self._after_batch()

    def batch_dropped(self):
        if not self.batch_id:
            return
        if not self._ask("这批不要了", "这批没发(在罐头里删掉了)?记录作废,下次这些视频还会再摆。", "不要了", "先留着"):
            return
        n = self.rec.drop_batch(self.batch_id)
        self.say(f"这批 {n} 条作废了")
        self.batch_id = ""
        self._after_batch()

    def _after_batch(self):
        for v in self.batch_videos:                   # 这批确认完了:临时状态清掉(没摆成的原因在记录里)
            self.row_note.pop(v.path, None)
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
        msg = f"把整个「{date}」文件夹挪到:\n{dst}\n"
        if left:
            per = {}
            for v in left:
                per[f"{v.account} · {v.employee}"] = per.get(f"{v.account} · {v.employee}", 0) + 1
            msg += f"\n注意:里面还有 {len(left)} 条软件没记成「已发」:\n" + "\n".join(f"  · {k}:{n} 条" for k, n in per.items())
            msg += "\n(手动发了的可以先选中点「标成已发」)"
        if not self._ask("这天发完了,挪走", msg + "\n\n挪吗?", "挪走", "先不", default_no=bool(left)):
            return
        from qe.fsops import MoveError
        try:
            self._bg(f"正在把「{date}」挪走…(网络盘上可能要一会儿)", lambda: F.move_date(self.st, date))
        except FileExistsError:
            # 先留的口子(用户:「先留个功能接口 后面我搞清楚在做」):目标已有同名日期文件夹,问人要不要合并
            if QMessageBox.question(self, "已经有了", f"那边已经有「{date}」文件夹了:\n{dst}\n\n把这边的东西合并进去吗?(同名的文件不覆盖,改名加 (2))"
                                    ) != QMessageBox.StandardButton.Yes:
                return
            try:
                self._bg(f"正在把「{date}」合并过去…", lambda: F.move_date(self.st, date, merge=True))
            except MoveError as e:
                QMessageBox.warning(self, "挪走", str(e))
                self._load_dates()
                return
            except OSError as e:
                QMessageBox.warning(self, "挪走", f"合并时出错:{e.strerror or e}")
                return
        except MoveError as e:
            QMessageBox.warning(self, "挪走", str(e))
            self._load_dates()
            return
        except OSError as e:
            QMessageBox.warning(self, "挪走", f"挪不动:{e.strerror or e}\n\n(有文件开着?关掉再试)")
            return
        self.say(f"「{date}」挪到了 {dst}")
        self._load_dates()

    def _bg(self, title: str, fn):
        """fn 放到后台线程跑(挪网络盘上几个 G 的文件夹,窗口不卡成「未响应」),期间转个圈。返回 fn 的结果,出错照样抛出来。"""
        from PySide6.QtCore import QEventLoop, QThread
        from PySide6.QtWidgets import QProgressDialog
        res = {}

        class T(QThread):
            def run(self_):
                try:
                    res["v"] = fn()
                except BaseException as e:            # 交回界面线程再抛
                    res["e"] = e
        t = T(self)
        loop = QEventLoop()
        t.finished.connect(loop.quit)
        dlg = QProgressDialog(title, None, 0, 0, self)
        dlg.setWindowTitle("请稍等")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)                               # Qt6 要先 setValue 才会按时弹出来(审查)
        dlg.show()
        self.setEnabled(False)
        try:
            t.start()
            if t.isRunning():
                loop.exec()
            t.wait()
        finally:
            dlg.close()
            self.setEnabled(True)
        if "e" in res:
            raise res["e"]
        return res.get("v")

    # ---------------- 记录 ----------------
    def refresh_records(self):
        cur = self.c_rec_date.currentData()
        def _dk(d):
            try:
                return tuple(int(x) for x in str(d).split(".")[:2])
            except ValueError:
                return (99, 99)
        dates = sorted({r["date"] for r in self.rec.rows()}, key=_dk)
        self.c_rec_date.blockSignals(True)
        self.c_rec_date.clear()
        self.c_rec_date.addItem("全部", "")
        for d in dates:
            self.c_rec_date.addItem(d, d)
        i = self.c_rec_date.findData(cur) if cur is not None else -1
        self.c_rec_date.setCurrentIndex(i if i >= 0 else (self.c_rec_date.count() - 1 if dates else 0))   # 默认最新的一天
        self.c_rec_date.blockSignals(False)
        date = self.c_rec_date.currentData() or ""
        s = self.rec.summary(date)
        tot = {k: sum(int(x[k] or 0) for x in s) for k in ("sent", "failed", "unsure", "ready")}
        self.rec_cards.set(sent=(tot["sent"], "good" if tot["sent"] else ""), fail=(tot["failed"], "warn" if tot["failed"] else ""),
                           unsure=(tot["unsure"], "warn" if tot["unsure"] else ""), ready=tot["ready"],
                           sent_sub="" if date else "全部日期")
        self.t_sum.setRowCount(len(s))
        def short(t):                              # 「2026-10-15 18:42:45」→「10-15 18:42:45」(审查:时分秒被截掉了)
            return str(t or "")[5:] if str(t or "")[:2] == "20" else str(t or "")
        for i, x in enumerate(s):
            for c, k in enumerate(["date", "account", "employee", "sent", "ready", "failed", "unsure", "first_at", "last_at"]):
                val = x[k] if x[k] is not None else ""
                self.t_sum.setItem(i, c, QTableWidgetItem(short(val) if k.endswith("_at") else str(val)))
        rows = self.rec.rows(date)
        self.t_rec.setRowCount(len(rows))
        for i, x in enumerate(rows):
            for c, k in enumerate(["date", "account", "employee", "title", "status", "prepared_at", "published_at", "note"]):
                val = short(x[k]) if k.endswith("_at") else str(x[k] or "")
                if k == "employee" and val == "接口":
                    val = "16 个号"                       # 接口发的,员工一栏写人话
                if k == "note" and val.startswith("article_id="):
                    val = ""                              # 发成了的编号放鼠标悬停,不占地方
                it = QTableWidgetItem(val)
                it.setToolTip(str(x[k] or ""))
                self.t_rec.setItem(i, c, it)
            if x["status"] in ("没发成", "结果不明", "发布中"):
                for c in range(self.t_rec.columnCount()):
                    item = self.t_rec.item(i, c)
                    if item:
                        item.setBackground(QBrush(QColor("#ffe7eb" if x["status"] == "没发成" else "#ffeedd")))
        for c in (0, 1, 2, 4, 5, 6):
            self.t_rec.resizeColumnToContents(c)
        self.t_sum.resizeColumnsToContents()
        self.t_sum.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(self.t_sum.rowCount()):
            it = self.t_sum.item(i, 2)
            if it and it.text() == "接口":
                it.setText("16 个号")

    def export_records(self):
        date = self.c_rec_date.currentData() or ""
        p, _ = QFileDialog.getSaveFileName(self, "导出发布记录", f"企鹅号发布记录_{date or '全部'}.xlsx", "Excel (*.xlsx)")
        if not p:
            return
        try:
            self.rec.export_xlsx(p, date)
            QMessageBox.information(self, "导出", f"导出到了:\n{p}")
        except PermissionError:
            QMessageBox.warning(self, "导出", "导不出来:这个文件在 Excel 里开着,关掉再导(或者换个文件名)。")
        except Exception as e:
            QMessageBox.warning(self, "导出", f"导不出来:{e}")

    # ---------------- 设置 ----------------
    def edit_settings(self):
        from PySide6.QtWidgets import QCheckBox, QGroupBox
        d = QDialog(self)
        d.setWindowTitle("设置")
        from PySide6.QtWidgets import QScrollArea
        d.resize(780, 640)
        avail = self.screen().availableGeometry().height() if self.screen() else 900
        d.setMaximumHeight(max(480, avail - 60))
        dv = QVBoxLayout(d)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        outer = QVBoxLayout(inner)
        sa.setWidget(inner)
        dv.addWidget(sa, 1)

        def path_row(text: str) -> tuple[QWidget, QLineEdit]:
            """路径框 + 「选…」按钮(审查:路径框太短看不全,也没法点选文件夹)。{month} 这种模板就只取前面那截当起点。"""
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            e = QLineEdit(text)
            e.setMinimumWidth(460)
            b = QPushButton("选…")

            def pick():
                start = e.text().split("{")[0] or ""
                p = QFileDialog.getExistingDirectory(d, "选文件夹", start)
                if p:
                    e.setText(os.path.normpath(p))
            b.clicked.connect(pick)
            h.addWidget(e, 1)
            h.addWidget(b)
            return w, e

        g1 = QGroupBox("教育号(在创作罐头里摆,人点发布)")
        f = QFormLayout(g1)
        w_root, e_root = path_row(self.st["material_root"])
        w_arc, e_arc = path_row(self.st["archive_root"])
        e_acc = QPlainTextEdit("\n".join(f"{a['name']}={'、'.join(a.get('aliases') or [])}" for a in self.st["accounts"]))
        e_acc.setToolTip("一行一个号:罐头里的号名=日期文件夹下面的缩写(几个用顿号隔开)")
        e_acc.setMaximumHeight(70)
        sp = QSpinBox()
        sp.setRange(1, 10)
        sp.setValue(int(self.st.get("batch_size", 10)))
        f.addRow("素材文件夹", w_root)
        f.addRow("一天发完挪到", w_arc)
        prev = QLabel("")
        prev.setStyleSheet("color:#8a8b91")
        prev.setWordWrap(True)

        def show_prev():
            prev.setText("比如 10.15 那天的会挪到:" + os.path.join(e_arc.text().replace("{month}", "10"), "10.15"))
        e_arc.textChanged.connect(lambda _t: show_prev())
        show_prev()
        f.addRow("", prev)
        f.addRow("号和缩写", e_acc)
        f.addRow("一批几条", sp)
        outer.addWidget(g1)

        g2 = QGroupBox("接口发(16 个游戏 / 动漫号)")
        f2 = QFormLayout(g2)
        sp_thr = QSpinBox()
        sp_thr.setRange(1, 5)
        from gui.api_tab import _num
        sp_thr.setValue(_num(self.st.get("api_threads"), 1))
        sp_gap = QSpinBox()
        sp_gap.setRange(0, 600)
        sp_gap.setSuffix(" 秒")
        sp_gap.setValue(_num(self.st.get("api_interval"), 5))
        w_api, e_api_arc = path_row(self.st.get("api_archive", ""))
        k_game = QCheckBox("按游戏放进子文件夹(CSGO、DNF、光与夜之恋 …)")
        k_game.setChecked(bool(self.st.get("api_archive_by_game", True)))
        f2.addRow("发成了挪到", w_api)
        f2.addRow("", k_game)
        f2.addRow("几个号一起发", sp_thr)
        f2.addRow("每条间隔", sp_gap)
        f2.addRow("", QLabel("1 = 一个号一个号地发,最稳;间隔 = 上一条发完歇几秒再发下一条"))
        b_mig = QPushButton("从旧软件搬账号…")
        b_mig.setToolTip("从旧软件「企鹅号批量发布」的数据库(qepm.db)把 16 个号搬过来。密钥加密存在这台电脑上,不显示。")
        b_mig.clicked.connect(self.api_tab.migrate)
        b_mig.setEnabled(not self.api_tab.busy())
        b_login = QPushButton("登录取钥匙…")
        b_login.setToolTip("某个号发布报「号的密钥不对」时用:开一个浏览器,扫码登录这个号的企鹅号,软件自己读出新钥匙换上。\n"
                           "不用再开旧软件。")
        b_login.clicked.connect(lambda: self.api_tab.relogin_key(d))
        b_login.setEnabled(not self.api_tab.busy())
        hk = QWidget()
        hkl = QHBoxLayout(hk)
        hkl.setContentsMargins(0, 0, 0, 0)
        hkl.addWidget(b_mig)
        hkl.addWidget(b_login)
        f2.addRow("16 个号的账号", hk)
        outer.addWidget(g2)

        from gui import theme as TH
        g4 = QGroupBox("界面")
        f4 = QFormLayout(g4)
        c_theme = QComboBox()
        c_theme.addItem("原来的样子", "")
        for n, t in TH.THEMES.items():
            c_theme.addItem(f"{n} —— {t['desc']}", n)
        c_theme.setCurrentIndex(max(0, c_theme.findData(self.st.get("theme", ""))))
        f4.addRow("界面风格", c_theme)
        f4.addRow("", QLabel("换了以后关掉软件再打开就是新的样子"))
        outer.addWidget(g4)
        g3 = QGroupBox("AI(两边共用)")
        f3 = QFormLayout(g3)
        e_key = QLineEdit(self.st.get("ai_key", ""))
        e_key.setEchoMode(QLineEdit.EchoMode.Password)
        e_key.setPlaceholderText("空着就用百家号发布助手里填的" + ("(找到了)" if self.st.ai_key() else "(没找到)"))
        f3.addRow("阿里百炼 Key", e_key)
        f3.addRow("", QLabel("教育:大头照的 2.35:1 封面 AI 扩图;接口:「整理话题」里挂好几个话题的让 AI 挑一个"))
        outer.addWidget(g3)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        dv.addWidget(bb)
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
        self.st.update(material_root=e_root.text().strip() or self.st["material_root"],
                       archive_root=e_arc.text().strip() or self.st["archive_root"], accounts=accs or self.st["accounts"],
                       batch_size=sp.value(), ai_key=e_key.text().strip(),
                       api_threads=sp_thr.value(), api_interval=sp_gap.value(),
                       api_archive=e_api_arc.text().strip() or self.st.get("api_archive", ""),
                       api_archive_by_game=k_game.isChecked(), theme=c_theme.currentData() or "")
        C.AI_KEY = self.st.ai_key()
        self.st.save()
        self._load_dates()

    def closeEvent(self, e):
        if self.cover_worker and self.cover_worker.isRunning():
            self.cover_worker.stop = True
            self.cover_worker.wait(10000)
        if self.worker and self.worker.isRunning():
            if QMessageBox.question(self, "企鹅号发布助手", "还在摆,要停下来关掉吗?") != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.worker.stop()
            from PySide6.QtWidgets import QApplication, QProgressDialog
            dlg = QProgressDialog("正在停:手上这条摆完就关…", None, 0, 0, self)
            dlg.setWindowTitle("请稍等")
            dlg.setMinimumDuration(0)
            dlg.setValue(0)
            dlg.show()
            while not self.worker.wait(200):
                QApplication.processEvents()
            QApplication.processEvents()              # 让摆好的那几条记进记录
            dlg.close()
        j = getattr(getattr(self, "api_tab", None), "job", None)
        if j and j.isRunning():
            if QMessageBox.question(self, "企鹅号发布助手", "接口那边还在做(发布 / 转竖屏 / 改话题),要停下来关掉吗?") \
                    != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            j.stop()
            from PySide6.QtWidgets import QApplication, QProgressDialog
            dlg = QProgressDialog("正在停:手上这条做完就关(上传大文件可能要一会儿)…", None, 0, 0, self)
            dlg.setWindowTitle("请稍等")
            dlg.setMinimumDuration(0)
            dlg.setValue(0)
            dlg.show()
            while not j.wait(200):
                QApplication.processEvents()
            dlg.close()
        super().closeEvent(e)
