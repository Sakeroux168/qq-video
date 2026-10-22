"""企鹅号发布助手的窗口。

上面:选日期(人自己选,不自动挑最新 —— 员工会提前建好以后的日期)。
左边:每个号下面的员工文件夹(勾要发的),写着几条、发了几条。
中间:勾上的员工的视频,一条一行:标题、员工、封面横 / 竖(和为什么,能改)、状态。
下面:「摆下一批」「这批发好了」「这批不要了」「这天发完了,挪走」;日志。
「记录」页签:每条什么时候发的,按员工汇总,能导出 Excel。
"""
import copy
import os
import time

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QMenu, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QSizePolicy, QSpinBox, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from qe import cover as C
from qe import folders as F
from qe import plan
from qe.config import APP_VERSION, bj_now, bj_str, data_dir
from qe.adjust import Adjustments
from qe.records import Records
from gui.theme import cur as _tok

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
                self.adj.use_own(v)        # 人在预览里自己换过封面的,用他选的
                C.decide(v)
                self.adj.apply(v)          # 人在「封面预览」里调过的套上去
                C.note_wide(v)             # 2.35:1 怎么躲标题区(切头顶 / AI 扩图)
            self.one.emit(i)
        self.done.emit()


class WmWorker(QThread):
    """后台查水印(教育号页的「查水印」):一条几秒,3 条一起查;查过、文件没变的不再查(记在 wmstore)。"""
    one = Signal(int)
    log = Signal(str)

    def __init__(self, videos, rows, parent=None):
        super().__init__(parent)
        self.videos, self.rows = videos, rows
        self.stop = False

    def run(self):
        from concurrent.futures import ThreadPoolExecutor
        from qe import vertical, watermark as WM, wmstore
        ff = vertical.ffmpeg_path()

        def one(i):
            if self.stop:
                return
            v = self.videos[i]
            try:
                res = WM.detect(v.path, ff, vertical.probe(v.path, ff), stop=lambda: self.stop)
            except Exception as e:
                self.log.emit(f"「{v.title}」查水印出错:{type(e).__name__} {e}")
                return
            if not self.stop:
                v.wm = wmstore.put(v.path, res)
                self.one.emit(i)
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(one, self.rows))


class BlurWorker(QThread):
    """后台把查到的水印糊掉(教育号页「模糊水印」):2 条一起做,原片挪进「水印原片」。"""
    one = Signal(int, str)            # (行, 出错说明;空 = 糊好了)

    def __init__(self, videos, rows, parent=None):
        super().__init__(parent)
        self.videos, self.rows = videos, rows
        self.stop = False

    def run(self):
        from concurrent.futures import ThreadPoolExecutor
        from qe import blur, vertical, wmstore
        ff = vertical.ffmpeg_path()

        def one(i):
            if self.stop:
                return
            v = self.videos[i]
            wm = dict(v.wm or {})
            try:
                new, _orig = blur.blur(v.path, blur.boxes_of(wm), ff, stop=lambda: self.stop)
            except Exception as e:
                self.one.emit(i, str(e))
                return
            v.path = new
            v.wm = wmstore.put(new, wm, ok=True, blurred=True)
            self.one.emit(i, "")
        with ThreadPoolExecutor(2) as ex:
            list(ex.map(one, self.rows))


WAIT_NOTE = "上传中(这批一起传,传完再一条条弄封面)"
READY = "摆好等发布"          # 记录里的「摆好」:在罐头里摆好了,还没点发布(审查 17:原来「摆好没发 / 没发 / 还没发」三个词混着用)
PICK_DAY = "先在左上角「要发哪天的」里选一天"       # 审查 13:刚打开是空白,不知道先干什么
PICK_EMP = "左边勾上要发的员工(可以勾好几个)"


class BatchWorker(QThread):
    log = Signal(str)
    one = Signal(object, bool, str)
    finished_batch = Signal(object, str, str)      # (结果列表 or None, 出错说明, 自动发布:""没发 / "ok"发了 / 其它 = 为什么没发)

    def __init__(self, account, videos, shot_dir, parent=None, auto_publish: bool = False, unattended: bool = False,
                 sched_at: str = "", publish_only: bool = False):
        super().__init__(parent)
        self.account, self.videos, self.shot_dir = account, videos, shot_dir
        self.publish_only = publish_only          # 这批已经摆好了(因为标黄停下来),人说「封面看过了」:只点「全部发布」
        self.auto_publish = auto_publish or unattended
        self.unattended = unattended              # 定时发布(没人看着):没摆好的再试一次,还不行关掉不发,其它照发
        self.sched_at = sched_at                  # 北京时间:点「全部定时发布」定到这个点(不点「全部发布」)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from qe.prepare import PrepError, Runner, Stop
        r = None
        try:
            r = Runner(log=self.log.emit, stopped=lambda: self._stop, shot_dir=self.shot_dir)
            if self.publish_only:
                r.open_account(self.account)
                try:
                    pub = r.publish_all([v.title for v in self.videos])
                except PrepError as e:
                    pub = f"自动发布停下了:{e}"
                self.finished_batch.emit([(v, True, "") for v in self.videos], "", pub)
                return
            res = r.prepare_batch(self.account, self.videos, on_one=lambda v, ok, why: self.one.emit(v, ok, why),
                                  retry=self.unattended)
            pub = ""
            if self.unattended:
                bad = [v for v, ok, _w in res if not ok]
                good = [v for v, ok, _w in res if ok]
                try:
                    if bad:
                        r.discard([v.title for v in bad])
                    if not good:
                        pub = "none"
                    elif self.sched_at:
                        from qe.prepare import sched_local
                        pub = r.schedule_all([v.title for v in good], sched_local(self.sched_at))
                    else:
                        pub = r.publish_all([v.title for v in good])
                except PrepError as e:
                    pub = f"自动发布停下了:{e}"
            elif self.auto_publish:
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
        self._unattended = False          # 定时发布正在自己发(没人看着)
        self._sched_skip: set[str] = set()  # 定时发布这一轮跳过的(没摆好 / 文件没了):不再拿来摆
        self._sched_tries = 0             # 一整批出错(罐头没开 / 掉登录 …)连着重试了几次
        self._chain_stop = False          # 人点了「停」:连发(自动发布 / 定时)手上这批做完不再接着摆
        C.AI_KEY = st.ai_key() if hasattr(st, "ai_key") else ""
        self.setWindowTitle(f"企鹅号发布助手(第{APP_VERSION}版)")
        self.resize(1280, 820)
        self._build()
        self._sched_changed()
        self._load_dates()
        ob = self.rec.open_batches()
        if ob:
            b = ob[-1]
            self.batch_id = b["batch"]
            self._batch_acc = b["account"]
            self.say(f"上次摆好的一批还没确认:「{b['account']}」{b['n']} 条({b['at']})。在罐头里发了就点「这批发好了」,不要了就点「这批不要了」。")
        self._refresh_buttons()

    # ---------------- 界面 ----------------
    def _build(self):
        """教育号页(用户 2026-10-18 选的「G 一键驾驶舱」):最上面一句大字说下一步(摆「家长小天地」2 条),
        大按钮就在旁边;摆好了大字变「这批摆好了」、主按钮变「这批发好了」。下面左边勾员工、右边看视频。"""
        from gui.widgets import Hero, PillDelegate, StatCards, shell
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 14)
        v.setSpacing(12)
        self.hero = Hero(open_=True)
        top = self.hero.meta
        top.addWidget(QLabel("要发哪天的:"))
        self.c_date = QComboBox()
        self.c_date.setMinimumWidth(130)
        self.c_date.currentIndexChanged.connect(self._load_tree)
        top.addWidget(self.c_date)
        b = self.b_refresh = QPushButton("刷新")
        b.setToolTip("重新读一遍素材文件夹(F5)。员工往文件夹里加了视频 / 补了封面 / 改了名,点这个才看得到;勾着的员工还勾着")
        b.clicked.connect(self._load_dates)
        top.addWidget(b)
        from PySide6.QtGui import QKeySequence, QShortcut
        sc = QShortcut(QKeySequence("F5"), w)              # 只在教育号这页管用(16 个号那页有它自己的 F5)
        sc.activated.connect(lambda: self.b_refresh.isEnabled() and self._load_dates())
        self.lab_root = QLabel("")
        self.lab_root.setObjectName("heroMeta")
        from PySide6.QtWidgets import QSizePolicy
        self.lab_root.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)   # 路径太长就截,不撑宽窗口
        self.lab_root.setMinimumWidth(120)
        top.addWidget(self.lab_root, 1)
        self._top = top
        v.addWidget(self.hero)
        # 用词统一(审查 17):已发 / 摆好等发布(在罐头里摆好了、还没点发布)/ 还没发(还没动过)/ 没发成(出错了)
        self.cards = StatCards([("all", "勾上的视频"), ("sent", "已发"), ("ready", READY), ("todo", "还没发")])
        self.cards.hide()                              # 数字写在大字下面那行了
        v.addWidget(self.cards)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.hint.hide()                               # 「正在摆 / 这批摆好了」改成大字写
        v.addWidget(self.hint)
        self.row_note: dict[str, str] = {}            # 这一批里每条的临时状态:排队中 / 没摆成:原因

        sp = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["号 / 员工", "条数"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemChanged.connect(self._tree_changed)
        self.tree.itemClicked.connect(self._top_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        self.tree.setIndentation(18)
        from gui.widgets import EduTableDelegate, EduTreeDelegate
        self.tree.setItemDelegate(EduTreeDelegate(self.tree))
        sp.addWidget(self.tree)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.lab_sum = QLabel(PICK_DAY)
        self.lab_sum.setObjectName("hint")
        rv.addWidget(self.lab_sum)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["标题(= 文件名)", "号", "员工", "封面", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(62)
        self.table.setItemDelegateForColumn(0, EduTableDelegate(self.table))   # 封面小图 + 标题 + 号 · 员工
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setItemDelegateForColumn(4, PillDelegate(4, self.table))
        self.table.setToolTip("双击一条:预览封面、拖裁剪框")
        self.table.cellDoubleClicked.connect(lambda r, _c: self.preview_cover(r))
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        for i, wd in ((1, 104), (2, 70), (3, 200), (4, 120)):
            self.table.setColumnWidth(i, wd)
        self.table.setColumnHidden(1, True)           # 号 / 员工写在标题下面那行小字里了(列还在)
        self.table.setColumnHidden(2, True)
        rv.addWidget(self.table, 1)
        self.lab_more = QLabel("左边再勾几个员工,视频会出现在这里")
        self.lab_more.setObjectName("muted")
        self.lab_more.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lab_more.setMinimumHeight(40)
        self.lab_more.hide()
        rv.addWidget(self.lab_more)
        sp.addWidget(right)
        sp.setSizes([330, 900])
        self.tree.setColumnWidth(1, 110)
        sp.setStretchFactor(0, 1)
        sp.setStretchFactor(1, 3)

        self.b_go = QPushButton("摆下一批")
        self.b_go.setObjectName("primary")
        self.b_go.setMinimumHeight(40)
        self.b_go.setToolTip("在罐头里打开这个号的发布页,传视频、传封面并裁好、选自主声明、补 AI 声明,停在发布前。发布你自己点。")
        self.b_go.clicked.connect(self.start_batch)
        self.b_stop = QPushButton("停")
        self.b_stop.setObjectName("danger")
        self.b_stop.setMinimumHeight(34)
        self.b_stop.clicked.connect(self.stop_batch)
        self.b_sent = QPushButton("这批发好了")
        self.b_sent.setMinimumHeight(40)
        self.b_sent.setToolTip("你在罐头里点完「发布 → 全部发布」以后点这个:记下发布时间。")
        self.b_sent.clicked.connect(self.batch_sent)
        from PySide6.QtWidgets import QCheckBox
        self.k_auto = QCheckBox("摆好后自动点发布")
        self.k_auto.setToolTip("勾上:整批都摆好、没有标黄的,软件自己在罐头里点「发布 → 全部发布」,记下发布时间,再摆下一批,直到勾上的都发完。\n"
                               "有一条没摆好、或者有标黄的,就停下来叫你。点完发布弹出没见过的框也停下来。")
        self.k_auto.setChecked(False)                  # 每次打开都不勾(审查 2026-10-18:记住了容易忘,一点「摆下一批」就真发了)
        self.k_auto.toggled.connect(self._auto_toggled)
        self.b_pubgo = QPushButton("封面看过了,接着自动发布")
        self.b_pubgo.setObjectName("primary")
        self.b_pubgo.setMinimumHeight(40)
        self.b_pubgo.setToolTip("这批因为有封面标黄停下来了:在罐头里 / 预览里看过没问题,点这个 → 软件自己点「全部发布」,接着摆下一批")
        self.b_pubgo.clicked.connect(self.continue_publish)
        self.b_pubgo.hide()
        self._yellow_stop = False
        self.b_drop = QPushButton("这批不要了")
        self.b_drop.setToolTip("这批没发(在罐头里删了):记录作废,下次还会再摆这些视频。")
        self.b_drop.clicked.connect(self.batch_dropped)
        self.b_manual = QPushButton("标成已发")
        self.b_manual.setToolTip("你在罐头里自己手动发了的(软件没摆成 / 没摆):选中点这个,记成已发,下次就不会再摆它")
        self.b_manual.clicked.connect(self.mark_manual)
        self.b_open = QPushButton("打开文件夹")
        self.b_open.setObjectName("link")
        self.b_open.setToolTip("在资源管理器里打开选中这条视频所在的文件夹,并选中它(右键列表 / 左边员工也有)")
        self.b_open.clicked.connect(lambda: self.open_selected("video"))
        self.b_preview = QPushButton("预览封面…")
        self.b_preview.setToolTip("看每个比例的裁剪框在哪;不满意就拖框(双击列表里一条也行)")
        self.b_preview.clicked.connect(lambda: self.preview_cover())
        self.b_move = QPushButton("这天发完,挪走…")
        self.b_move.setObjectName("link")
        self.b_move.clicked.connect(self.move_day)
        self.b_wm = QPushButton("查水印")
        self.b_wm.setToolTip("勾上的员工的视频,查一遍有没有别的平台的水印 / 广告图标(B站、抖音、快手、得物、转转 …)。\n"
                             "查到的标黄、不摆;鼠标放在状态上看截图,不是水印就右键「没水印,能摆」。查过的记着,不再查。")
        self.b_wm.clicked.connect(self.run_wm)
        self.wm_worker = None
        self.b_blur = QPushButton("模糊水印")
        self.b_blur.setToolTip("查到水印的(标黄的),把水印那块糊掉(只糊水印出现的那几段);原片挪进同文件夹的「水印原片」,不删。")
        self.b_blur.clicked.connect(self.run_blur)
        self.blur_worker = None
        self.b_allok = QPushButton("封面都看过了")       # 审查 16:原来叫「全部调好了」,看不出是说封面
        self.b_allok.setToolTip("标黄的封面都在「预览封面」里看过、调好了:点这个,勾上的员工里标黄的封面都算没问题,不再停下来等你。\n"
                                "(换了封面图的又会标黄;定时发布时还标黄的不发,留给你)")
        self.b_allok.clicked.connect(self.all_covers_ok)
        self.b_review = QPushButton("快速过封面")         # 用户 2026-10-19 看草图定的:一屏看完所有标黄的,回车 = 没问题
        self.b_review.setToolTip("一屏铺开勾上的员工里所有标黄的封面,每张带 4 个比例的小图。\n"
                                 "没问题按回车(去黄、跳下一张);脸被切了的点一下进去拖框;「剩下的都没问题」一下子全去黄。")
        self.b_review.clicked.connect(self.quick_review)
        self.b_sched = QPushButton("摆好并定时发出…")
        self.b_sched.setObjectName("pill")
        self.b_sched.setMinimumHeight(36)
        self.b_sched.setToolTip("选哪天的素材、几点发:软件现在就一批一批在罐头里摆好,每批点罐头的「全部定时发布」定到那个点。\n"
                                "摆完电脑能关,到点企鹅号自己发。没摆好的再试一次,还不行就关掉不发,接着摆别的。")
        self.b_sched.clicked.connect(self.schedule_clicked)
        # 审查 18:主按钮上面一行绿字写「这次摆 N 条 / 跳过 N 条(为什么)」(像 16 个号页那样)
        self.lab_scope = QLabel("")
        self.lab_scope.setObjectName("scope")
        self.lab_scope.setWordWrap(True)
        from PySide6.QtCore import QTimer
        self._scope_timer = QTimer(self)              # 一行一行刷的时候(认封面 / 查水印)攒一下再算,不每行都算一遍
        self._scope_timer.setSingleShot(True)
        self._scope_timer.setInterval(200)
        self._scope_timer.timeout.connect(self._update_scope)
        # 大按钮那一排:定时离主按钮远一点(和 16 个号页一样,免得点错)
        bar = self.hero.acts
        bar.addWidget(self.b_sched)
        self.lab_sched = QLabel("")
        self.lab_sched.setObjectName("warnText")
        bar.addWidget(self.lab_sched)
        bar.addSpacing(28)
        from gui.widgets import help_dot
        for b in (self.b_drop, self.b_sent, self.b_pubgo, self.b_go, self.b_stop):
            bar.addWidget(b)
            if b is self.b_go:
                bar.addWidget(help_dot("摆"))
        # 工具那一排:这次摆几条(绿字)+ 查水印 / 模糊水印 / 封面都看过了 / 自动点发布
        tools = QHBoxLayout()
        tools.setSpacing(8)
        tools.addWidget(self.lab_scope, 1)
        for b in (self.b_wm, self.b_blur, self.b_review, self.b_allok):
            tools.addWidget(b)
            if b is self.b_review:
                tools.addWidget(help_dot("标黄"))
        tools.addSpacing(6)
        tools.addWidget(self.k_auto)
        tools.addWidget(help_dot("自动点发布"))
        v.addLayout(tools)
        v.addWidget(sp, 1)
        for b in (self.b_open, self.b_move):          # 次要的放上面一行右边;「标成已发」「预览封面」在列表右键里
            self._top.addWidget(b)
        self.b_manual.hide()
        self.b_preview.hide()
        logrow = QHBoxLayout()
        self.lab_last = QLabel("")
        self.lab_last.setObjectName("muted")
        self.lab_last.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        logrow.addWidget(self.lab_last, 1)
        self.b_log = QPushButton("展开日志")
        self.b_log.setObjectName("link")
        self.b_log.clicked.connect(self._toggle_log)
        logrow.addWidget(self.b_log)
        v.addLayout(logrow)
        self.logbox = QPlainTextEdit()
        self.logbox.setObjectName("log")
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        self.logbox.setMaximumHeight(160)
        self.logbox.hide()                            # 平时只露最近一句,「展开日志」看全
        v.addWidget(self.logbox)
        from gui.api_tab import ApiTab
        self.api_tab = ApiTab(self.st, self.rec, self.say, self)

        # 记录页(用户 2026-10-18 看草图定的:彩色数字卡 + 表格放进白卡片 + 「每一条」合成一行)
        r = QWidget()
        rv2 = QVBoxLayout(r)
        from gui.widgets import RecDelegate
        from PySide6.QtWidgets import QFrame
        rv2.setContentsMargins(24, 18, 24, 14)
        rv2.setSpacing(12)
        title = QLabel("数据记录")
        title.setObjectName("pageTitle")
        rv2.addWidget(title)
        sub = QLabel("每条哪天、哪个号、什么时候发的")
        sub.setObjectName("heroSub")
        rv2.addWidget(sub)
        self.rec_cards = StatCards([("sent", "已发"), ("fail", "没发成"), ("unsure", "不确定发没发"), ("ready", READY)],
                                   icons={"sent": ("check", "ok"), "fail": ("error", "bad"), "unsure": ("help", "warn"),
                                          "ready": ("clock", "acc")})
        rv2.addWidget(self.rec_cards)

        def panel(title_text):
            f = QFrame()
            f.setObjectName("panel")
            pv = QVBoxLayout(f)
            pv.setContentsMargins(1, 1, 1, 1)
            pv.setSpacing(0)
            head = QHBoxLayout()
            head.setContentsMargins(16, 10, 12, 10)
            head.setSpacing(8)
            t = QLabel(title_text)
            t.setObjectName("secTitle")
            head.addWidget(t)
            pv.addLayout(head)
            return f, pv, head
        p1, pv1, rh = panel("每个员工发了多少")
        rh.addWidget(QLabel("日期:"))
        self.c_rec_date = QComboBox()
        self.c_rec_date.currentIndexChanged.connect(self.refresh_records)
        rh.addWidget(self.c_rec_date)
        from PySide6.QtWidgets import QCheckBox as _QCB2
        self.k_rec_bad = _QCB2("只看出问题的")
        self.k_rec_bad.setToolTip("下面「每一条」只列没发成、不确定发没发、摆好了还没确认的")
        self.k_rec_bad.toggled.connect(lambda _on: self.refresh_records())
        rh.addWidget(self.k_rec_bad)
        rh.addStretch(1)
        b = QPushButton("刷新")
        b.clicked.connect(self.refresh_records)
        rh.addWidget(b)
        b = QPushButton("导出 Excel…")
        b.clicked.connect(self.export_records)
        rh.addWidget(b)
        self.t_sum = QTableWidget(0, 9)
        self.t_sum.setHorizontalHeaderLabels(["日期", "号", "员工", "已发", READY, "没发成", "结果不明", "第一条发布", "最后一条发布"])
        self.t_sum.verticalHeader().setVisible(False)
        self.t_sum.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t_sum.setShowGrid(False)
        self.t_sum.verticalHeader().setDefaultSectionSize(34)
        self.t_sum.setMaximumHeight(240)
        pv1.addWidget(self.t_sum)
        rv2.addWidget(p1)
        p2, pv2, rh3 = panel("每一条")
        tip = QLabel("点一条没发成的,下面能重试 / 标成已发")
        tip.setObjectName("muted")
        rh3.addWidget(tip)
        rh3.addStretch(1)
        self.rec_empty = QLabel("")                   # 审查 20:空表没提示,不知道是没记录还是坏了
        self.rec_empty.setObjectName("hint")
        self.rec_empty.setWordWrap(True)
        self.rec_empty.hide()
        rv2.addWidget(self.rec_empty)
        self.t_rec = QTableWidget(0, 8)
        self.t_rec.setHorizontalHeaderLabels(["日期", "号", "员工", "标题", "状态", "摆好 / 开始发", "发布时间", "备注(没发成的原因)"])
        self.t_rec.verticalHeader().setVisible(False)
        self.t_rec.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t_rec.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t_rec.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.t_rec.setShowGrid(False)
        self.t_rec.verticalHeader().setDefaultSectionSize(54)
        self.t_rec.setItemDelegate(RecDelegate(self.t_rec))
        rh2 = self.t_rec.horizontalHeader()           # 标题那格占满(下面一行小字写号 · 员工 · 时间 · 备注)
        rh2.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        rh2.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 5, 6, 7):                     # 合成到标题那格里了,列还在(右键 / 导出照旧)
            self.t_rec.setColumnHidden(c, True)
        self.t_rec.setColumnWidth(0, 70)
        self.t_rec.setColumnWidth(4, 130)
        self.t_rec.itemSelectionChanged.connect(self._rec_sel)
        pv2.addWidget(self.t_rec, 1)
        rv2.addWidget(p2, 1)
        # 审查 23:点一条没发成 / 不确定发没发的,下面直接能「重试 / 标成已发」
        ra = QHBoxLayout()
        self.lab_rec_sel = QLabel("")
        self.lab_rec_sel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ra.addWidget(self.lab_rec_sel, 1)
        self.b_rec_retry = QPushButton("重试(去 16 个号页)")
        self.b_rec_retry.setToolTip("跳到「16 个号」页、选好这一天和这一条;你再点「再发一次没发成的」就发(不会自己发)")
        self.b_rec_retry.clicked.connect(self.rec_retry)
        self.b_rec_sent = QPushButton("标成已发")
        self.b_rec_sent.setToolTip("你去企鹅号后台看了,其实发出去了:记成已发,软件不会再发它")
        self.b_rec_sent.clicked.connect(lambda: self.rec_mark(True))
        self.b_rec_unsent = QPushButton("标成没发出去")
        self.b_rec_unsent.setToolTip("你去企鹅号后台看了,没发出去:记成没发成,之后能再发")
        self.b_rec_unsent.clicked.connect(lambda: self.rec_mark(False))
        for b in (self.b_rec_retry, self.b_rec_sent, self.b_rec_unsent):
            ra.addWidget(b)
        rv2.addLayout(ra)
        self._rec_sel()
        # 外壳:左边导航(教育号 / 16 个号 / 数据记录 / 设置),右边一页一页换(用户选的「抖音创作者中心」那种)
        from gui.daily_tab import DailyTab
        self.daily = DailyTab(self.st, self.rec, self)
        from gui.today_tab import TodayTab
        self.today = TodayTab(self.st, self.rec, self)
        self.pages = {"today": self.today, "edu": w, "api": self.api_tab, "daily": self.daily, "records": r}
        root, self.nav, self.stack = shell([("today", "今天", self.today), ("school", "教育号", w), ("game", "16 个号", self.api_tab),
                                            ("chart", "每日汇总", self.daily), ("table", "数据记录", r)],
                                           self.edit_settings, f"第 {APP_VERSION} 版")
        self.setCentralWidget(root)
        self.stack.currentChanged.connect(self._page_changed)
        from gui.widgets import set_badge
        self.api_tab.on_badge = lambda n: set_badge(self.nav, 2, str(n) if n else "")
        self.api_tab._update_sum()

    def goto(self, key: str):
        """跳到某一页(「今天」页的「下一步」点了用):today / edu / api / daily / records。"""
        p = self.pages.get(key)
        if p is not None:
            self.stack.setCurrentWidget(p)

    def _page_changed(self, _i: int):
        from gui.widgets import fade_in
        p = self.stack.currentWidget()
        if p is self.daily:
            self.daily.refresh()
        elif p is self.pages.get("records"):
            self.refresh_records()
        if p is not self.today:
            fade_in(p, 260)                           # 换页淡入一下(用户要活泼一点)

    def play_splash(self):
        """开场:「Hi,欢迎使用本工作台」→ 淡出,露出「今天」页(用户 2026-10-18)。设置里能关。"""
        from gui.widgets import Splash
        from qe.config import bj_now
        n = bj_now()
        s = Splash(self.centralWidget(), f"{n.month} 月 {n.day} 日 星期{'一二三四五六日'[n.weekday()]}")
        self.centralWidget().installEventFilter(s)
        s.done.connect(lambda: self.today.refresh(animate_=True))
        s.play()

    def say(self, m: str):
        self.logbox.appendPlainText(f"[{bj_str()[11:]}] {m}")
        if hasattr(self, "lab_last"):
            last = m.strip().splitlines()[0] if m.strip() else ""
            self.lab_last.setText(f"最近 {bj_str()[11:16]}:{last}")
            self.lab_last.setToolTip(m)

    def _toggle_log(self):
        big = self.logbox.isHidden()
        self.logbox.setVisible(big)
        self.b_log.setText("收起日志" if big else "展开日志")
        if big:
            self.logbox.verticalScrollBar().setValue(self.logbox.verticalScrollBar().maximum())

    # ---------------- 日期 / 员工 / 视频 ----------------
    def _load_dates(self):
        root = self.st["material_root"]
        self.lab_root.setText(f"素材在 {root}")
        self.lab_root.setToolTip(root)
        from gui.widgets import fill_dates, newest_first
        dates = newest_first(F.list_dates(root))        # 审查 15:和 16 个号页一样,最新的在上面
        empty = {d for d in dates if not self._date_has_files(root, d)}
        cur = self.c_date.currentData()
        if not cur:                                     # 刚打开:今天的文件夹有东西就选今天(试用 2026-10-21:每次都停在「选一天」)
            from qe.folders import day_of
            today = f"{bj_now().month}.{bj_now().day}"
            cur = next((d for d in dates if day_of(d) == today and d not in empty), "") or self.st.get("last_date", "")
        fill_dates(self.c_date, dates, cur, "(选一天)", empty=empty)
        if not dates:
            self.say(f"素材文件夹里没有日期文件夹:{root}(网络盘连上了吗?)")
        self._load_tree()

    def _date_has_files(self, root: str, date: str) -> bool:
        """这天有没有东西(下拉里没视频的灰掉):有认得出的号文件夹、而且里面不是空的。只看一两层,不把网络盘翻到底。"""
        try:
            for dirs in F.account_dirs(root, date, self.st).values():
                for d in dirs:
                    with os.scandir(d) as it:
                        if any(True for _e in it):
                            return True
        except OSError:
            return True                                # 打不开的不灰(说不准),点进去会说打不开
        return False

    def _load_tree(self):
        date = self.c_date.currentData() or ""
        if self.st.get("last_date") != date:          # 真换了日期才存(审查:原来一打开就存一次,会冲掉别处改的设置)
            self.st["last_date"] = date
            self.st.save()
        # 同一天点「刷新」:原来勾着的员工还勾着(勾员工用的是下面翻好的缓存,员工加了视频 / 补了封面要点刷新才看得到,
        # 刷新一下勾选全没了很烦);换了日期就都不勾
        keep = set(self.checked_dirs()) if date and date == getattr(self, "_tree_date", None) else set()
        self._tree_date = date
        self.tree.blockSignals(True)
        self.tree.clear()
        self._scan = {}                                # 号文件夹 → 翻出来的视频(勾员工时不再翻网络盘)
        if date:
            root = self.st["material_root"]
            for acc, dirs in F.account_dirs(root, date, self.st).items():
                top = QTreeWidgetItem([acc, ""])
                top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                top.setToolTip(0, f"点这一行 = 「{acc}」的员工全勾上(再点一下全不勾)")
                n_all = 0
                rep: list = []
                for d in dirs:                                 # 先把这个号的文件夹都翻完(同号同名要跨文件夹比)
                    # 每个人放法都不一样(用户:「跟他们沟通不了的」):号文件夹整个翻一遍,按人分,封面按名字配
                    self._scan[d] = F.scan_account(d, acc, date, rep)
                self._mark_skips([v for d in dirs for v in self._scan[d]])
                bad = self._say_report(acc, rep)
                for d in dirs:
                    vs_all = self._scan[d]
                    for emp, _n in F.groups(vs_all):
                        vids = [x for x in vs_all if x.employee == emp]
                        it = QTreeWidgetItem([emp, self._emp_text(vids)])
                        it.setToolTip(0, f"{emp}({os.path.basename(d)})" +
                                      ("\n视频直接放在号文件夹里,没按人分" if emp == F.NO_EMP else ""))
                        it.setData(0, Qt.ItemDataRole.UserRole, F.emp_dir(d, emp))
                        it.setData(0, Qt.ItemDataRole.UserRole + 1, acc)
                        it.setData(0, Qt.ItemDataRole.UserRole + 2, d)
                        it.setData(0, Qt.ItemDataRole.UserRole + 3, emp)
                        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        it.setCheckState(0, Qt.CheckState.Checked if (acc, d, emp) in keep else Qt.CheckState.Unchecked)
                        top.addChild(it)
                        n_all += len(vids)
                for kind, p, n in rep:                 # 审查 11:名字带「已发」的文件夹不再悄悄消失,留一行灰的说为什么不发
                    if kind == "跳过" and n:
                        top.addChild(self._grey_row(os.path.basename(p), f"{n} 条,不发", p, self._skip_why(p)))
                top.setText(1, (f"{n_all} 条" if dirs else "这天没有它的文件夹") + (f",⚠ {bad} 个文件夹打不开" if bad else ""))
                self.tree.addTopLevelItem(top)
                top.setExpanded(True)
            unk = F.unknown_dirs(root, date, self.st)
            if unk:
                self.say(f"⚠ {date} 里这些文件夹没读(认不出是哪个号 / 两个号都像 / 名字带已发):{'、'.join(unk)}"
                         "(是哪个号的,就在「设置」里给号加上这个缩写)")
                top = QTreeWidgetItem(["没读的文件夹", f"{len(unk)} 个"])
                top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                top.setToolTip(0, "这天里认不出是哪个号的文件夹,里面的视频没读")
                for u in unk:
                    top.addChild(self._grey_row(u, "没读", os.path.join(root, date, u),
                                                "认不出是哪个号的(名字带「已发 / 不要」,或者两个号都像,或者缩写没在设置里)。\n"
                                                "是哪个号的,就在左下角「设置」→「号和缩写」里给号加上这个名字,再点「刷新」。"))
                for c in range(2):
                    top.setForeground(c, QBrush(QColor(_tok()["mu"])))
                self.tree.addTopLevelItem(top)
                top.setExpanded(True)
        self.tree.blockSignals(False)
        self._load_videos()

    @staticmethod
    def _grey_row(name: str, count: str, path: str, why: str) -> QTreeWidgetItem:
        """左边不能勾的灰行:跳过的 / 没读的文件夹(右键能打开它看看)。"""
        it = QTreeWidgetItem([f"{name}(不发)" if count != "没读" else name, count])
        it.setFlags((it.flags() & ~Qt.ItemFlag.ItemIsUserCheckable) | Qt.ItemFlag.ItemIsEnabled)
        it.setData(0, Qt.ItemDataRole.UserRole, path)                 # 只有路径(右键「打开这个文件夹」用);没有号 / 员工,勾不了
        for c in range(2):
            it.setForeground(c, QBrush(QColor(_tok()["dim"])))
            it.setToolTip(c, f"{path}\n\n{why}")
        return it

    @staticmethod
    def _skip_why(p: str) -> str:
        name = os.path.basename(p).strip()
        if name in F.ORIG_DIRS:
            return f"「{name}」里是处理前的原片(转竖屏 / 糊水印 / 剪广告以前的),处理好的那份已经在外面了,不再发。"
        return ("文件夹名带「已发 / 不能用 / 不要 / 重复 / 作废 / 脏话」,软件当成不发的。\n"
                "里面的其实要发:让员工把名字里这些字去掉,再点「刷新」。")

    def _emp_text(self, vids) -> str:
        """员工那行第二列:几条、发了几条、几条没无字封面、几条不发(同名 / 发过 / 坏的)。"""
        sent = sum(1 for x in vids if self.rec.status_of(x.path) == "已发")
        nocov = sum(1 for x in vids if not x.png)
        skip = sum(1 for x in vids if x.skip and not self.rec.status_of(x.path))
        return f"{len(vids)} 条" + (f",发了 {sent}" if sent else "") + (f",{nocov} 条没无字封面" if nocov else "") + \
            (f",{skip} 条不发(同名 / 发过 / 坏的)" if skip else "")

    def _mark_skips(self, vs):
        """不摆的写上原因(Video.skip):① 同一个号里同名的只留一条(已经发了 / 摆了的那条优先);
        ② 这个号以前发过同名的 —— 发布记录是按路径认的,员工把发过的挪了地方(10.15 真有人把发过的 31 条挪进
        「31条（已发）」),路径一变就认不出来了,所以再按 号 + 标题 对一遍。
        ③ 同一天的(文件夹被改了名:10.17 有人把「10.14」改成「10.14（101）」)就是发过的那条 → 记下新位置,
        直接算「已发」(不然显示没发,人会再标一遍手动发过,每日汇总就多算了)。"""
        F.mark_dups(vs, prefer=lambda v: bool(self.rec.status_of(v.path)))
        from qe import titleclean
        for v in vs:                                  # 标题的乱码尾巴 / @ 那段:摆的时候在罐头里删掉再发(用户 2026-10-18);删完没字了的不发
            if titleclean.dirty(v.title) and not titleclean.clean(v.title) and not titleclean.ad_words(v.title)                     and not v.skip and not self.rec.status_of(v.path):
                v.skip = "标题去掉乱码 / @ 那段以后就没字了,让员工改个正常的名字"
        sent = {}
        for r in self.rec.rows():
            if r["status"] == "已发":
                sent.setdefault((r["account"], F.norm_name(r["title"]) or r["title"]), r)
        for v in vs:
            if v.skip or self.rec.status_of(v.path):
                continue
            r = sent.get(F.dup_key(v))
            if not r:
                continue
            day = F.day_of(v.date)
            if day and F.day_of(r["date"]) == day and self.rec.relink(r["id"], v.path):
                continue
            v.skip = f"这个号发过同名的({r['date']} {r['employee']}),不再发(真要发就让员工改个名)"

    def _say_report(self, acc: str, rep: list) -> int:
        """翻文件夹时跳过的 / 打不开的说给人听(不悄悄漏掉)。返回打不开的个数。"""
        bad = 0
        for kind, p, n in rep:
            if kind == "跳过":
                if n:
                    self.say(f"「{acc}」跳过了「{os.path.basename(p)}」里的 {n} 条视频(文件夹名带 已发 / 不要 / 重复…,当成不发的)")
            else:
                bad += 1
                self.say(f"⚠「{acc}」有个文件夹打不开,里面的视频没读到:{p}(路径太长 / 没权限 / 网断了?)")
        return bad

    def _update_tree_counts(self):
        """「这批发好了」「标成已发」以后,左边员工那行的「发了 N」跟着变(不重新翻文件夹,用缓存)。"""
        scan = getattr(self, "_scan", {})
        self.tree.blockSignals(True)
        try:
            for i in range(self.tree.topLevelItemCount()):
                top = self.tree.topLevelItem(i)
                for k in range(top.childCount()):
                    it = top.child(k)
                    d, emp = it.data(0, Qt.ItemDataRole.UserRole + 2), it.data(0, Qt.ItemDataRole.UserRole + 3)
                    if d in scan:
                        it.setText(1, self._emp_text([x for x in scan[d] if x.employee == emp]))
        finally:
            self.tree.blockSignals(False)

    def batch_account(self) -> str:
        """摆好的这批是哪个号的(软件重开以后 batch_videos 是空的,从记录里拿)。"""
        return self.batch_videos[0].account if self.batch_videos else getattr(self, "_batch_acc", "")

    def show_problems(self):
        """首页「今天出问题」:去数据记录,只看没发成 / 不确定 / 摆好没确认的。"""
        self.goto("records")
        self.k_rec_bad.setChecked(True)
        self.c_rec_date.setCurrentIndex(0)            # 全部日期(不确定 / 摆好没确认的可能是前几天的)
        self.refresh_records()

    def _tree_changed(self, *_a):
        self._load_videos()

    def _top_clicked(self, it, _col=0):
        """点号那一行:这个号能勾的员工全勾上;都勾着就全不勾(老手 / 新员工试用:原来要一个个勾)。只认一次封面,不是勾一个认一次。"""
        if it is None or it.parent() is not None:
            return
        kids = [it.child(k) for k in range(it.childCount()) if it.child(k).data(0, Qt.ItemDataRole.UserRole + 2)]
        if not kids:
            return
        on = not all(k.checkState(0) == Qt.CheckState.Checked for k in kids)
        self.tree.blockSignals(True)
        for k in kids:
            k.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self.tree.viewport().update()
        self._load_videos()

    def checked_dirs(self) -> list[tuple[str, str, str]]:
        """勾上的员工:[(号, 号文件夹, 员工)]。"""
        out = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for k in range(top.childCount()):
                it = top.child(k)
                if it.checkState(0) == Qt.CheckState.Checked and it.data(0, Qt.ItemDataRole.UserRole + 2):   # 灰行(不发的文件夹)不算
                    out.append((it.data(0, Qt.ItemDataRole.UserRole + 1), it.data(0, Qt.ItemDataRole.UserRole + 2),
                                it.data(0, Qt.ItemDataRole.UserRole + 3)))
        return out

    def _load_videos(self):
        date = self.c_date.currentData() or ""
        for wk in (getattr(self, "wm_worker", None), getattr(self, "blur_worker", None)):
            if wk and wk.isRunning():                   # 列表要换了:查水印 / 糊水印停下(行号会对不上)
                wk.stop = True
                wk.wait(60000)
        self.videos = []
        scan = getattr(self, "_scan", {})
        for acc, d, emp in self.checked_dirs():
            if d not in scan:
                scan[d] = F.scan_account(d, acc, date)
                self._mark_skips(scan[d])
            self.videos += [copy.deepcopy(v) for v in scan[d] if v.employee == emp]      # 拷一份:和以前每次新读一样
        from qe import wmstore
        for v in self.videos:                          # 查过水印的(记在硬盘上)
            v.wm = wmstore.get(v.path)
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
            self.cover_worker.finished.connect(self._update_scope)     # 认完了:「这次摆几条」重算
            self.cover_worker.start()
        self._refresh_buttons()

    def _fill_row(self, i: int):
        if i >= len(self.videos) or i >= self.table.rowCount():
            return
        v = self.videos[i]
        stt = self.rec.status_of(v.path)
        note = "" if stt else self.row_note.get(v.path, "")
        cov = v.cover_why if (v.cover_kind or v.warn) else "认人中…"
        skip = "" if stt or note else v.skip               # 不摆的(同号同名 / 0 字节 / 发过同名的)写清楚为什么
        from qe import checks, titleclean, wmstore
        tad = "" if stt or note or skip else titleclean.ad_problem(v.account, v.title)   # 标题有广告词:不摆
        if tad:
            skip = tad
        wmb = not (stt or note or skip) and wmstore.blocks(v.wm)       # 查到水印、人还没说没问题:不摆
        wtxt = f"有水印:{checks.wm_text(v.wm)}" if wmb else ""
        newt = "" if stt else titleclean.clean(v.title)
        stt_txt = READY if stt == "摆好" else stt
        for c, t in enumerate([v.title, v.account, v.employee, cov, stt_txt or note or (f"不发:{skip}" if skip else wtxt or "还没发")]):
            it = QTableWidgetItem(t)
            if c == 0:
                from gui.widgets import THUMB
                it.setData(THUMB, v.cover or v.png or v.vcover or v.jpg)      # 封面小图(草图 ②)
            if c == 4 and (note or skip):
                it.setToolTip(note or skip)
            if c == 4 and (skip or wmb):
                it.setBackground(YELLOW)
            if c == 4 and wmb:
                shot = (v.wm or {}).get("shot") or ""
                from PySide6.QtCore import QUrl
                it.setToolTip(f"<b>{checks.wm_text(v.wm)}</b>" + (f"<br><img src='{QUrl.fromLocalFile(shot).toString()}' width='300'>"
                              if shot and os.path.isfile(shot) else "") + "<br>不是水印:右键「没水印,能摆」")
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
            if c == 0 and newt:
                it.setToolTip(f"摆的时候标题会改成:{newt}(去掉乱码 / @ 那段;文件名不动)")
                it.setText(f"{v.title}  → {newt}")
            self.table.setItem(i, c, it)
        if hasattr(self, "_scope_timer"):
            self._scope_timer.start()

    def _update_sum(self):
        n = len(self.videos)
        st = [self.rec.status_of(v.path) for v in self.videos]
        self.lab_sum.setText("" if n else PICK_DAY if not self.c_date.currentData() else PICK_EMP)
        self.lab_sum.setVisible(not n)
        if hasattr(self, "lab_more"):
            self.lab_more.setVisible(0 < n < 6)
        self.cards.set(all=n, sent=(st.count("已发"), "good" if n and st.count("已发") == n else ""),
                       ready=(st.count("摆好"), "warn" if st.count("摆好") else ""), todo=st.count(""))
        self._update_scope()
        self._edu_hero()

    def _skip_reasons(self) -> list[tuple[str, list]]:
        """勾上的里面这次不摆的,按原因分:[(原因, [视频])](绿字那行和「摆下一批」确认框共用)。"""
        from qe import titleclean, wmstore
        left = [v for v in self.videos if not self.rec.status_of(v.path)]
        out = [("没无字封面", [v for v in left if (v.cover_kind or v.cover_why) and not v.cover and not v.skip]),
               ("同名 / 发过 / 坏文件", [v for v in left if v.skip]),
               ("有水印", [v for v in left if not v.skip and wmstore.blocks(v.wm)]),
               ("标题有广告词", [v for v in left if not v.skip and titleclean.ad_problem(v.account, v.title)])]
        return [(k, vs) for k, vs in out if vs]

    def _update_scope(self):
        """审查 18:主按钮上面写清楚「这次摆 N 条 / 跳过 N 条(为什么)」。"""
        if not hasattr(self, "lab_scope"):
            return
        if not self.c_date.currentData():
            text, tip = PICK_DAY, ""
        elif not self.videos:
            text, tip = PICK_EMP + ",这里会写这次摆几条", ""
        elif self.worker and self.worker.isRunning() or self.batch_id:
            text, tip = "", ""                         # 正在摆 / 等确认:上面横幅写着呢
        else:
            acc, vids = self.next_batch()
            todo = self._todo()
            nb = len({v.account for v in todo})
            bs = max(1, min(10, int(self.st.get("batch_size", 10) or 10)))
            import math
            nbatch = sum(math.ceil(sum(1 for v in todo if v.account == a) / bs) for a in {v.account for v in todo})
            text = (f"这次摆「{acc}」{len(vids)} 条" + (f"(能摆的一共 {len(todo)} 条,分 {nbatch} 批" +
                                                      (f",{nb} 个号" if nb > 1 else "") + ")" if len(todo) > len(vids) else "")
                    if vids else "勾上的都发了 / 都不能摆")
            if self.cover_worker and self.cover_worker.isRunning():
                text += " · 封面还在认人…"
            sk = self._skip_reasons()
            if sk:
                text += f" · 跳过 {sum(len(vs) for _k, vs in sk)} 条(" + "、".join(f"{k} {len(vs)}" for k, vs in sk) + ")"
            warn = [v for v in vids if v.warn]
            if warn:
                text += f" · 其中 {len(warn)} 条封面标黄,先看一眼"
            tip = "\n".join(f"{k}:" + "、".join(f"「{v.title[:20]}」" for v in vs[:5]) + ("…" if len(vs) > 5 else "")
                            for k, vs in sk)
        self.lab_scope.setText(text)
        self.lab_scope.setToolTip(tip + ("\n\n(鼠标放在列表的状态上看每条为什么)" if tip else ""))
        self.lab_scope.setVisible(bool(text))
        self._edu_hero()

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
        path = C.orig_of(v.cover) if what == "cover" else v.path
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
        from qe import titleclean
        v0 = self.videos[row] if row < len(self.videos) else None
        if v0 is not None and titleclean.ad_words(v0.title) and not self.rec.status_of(v0.path):
            m.addSeparator()
            if titleclean.store().ok(v0.account, v0.title):
                m.addAction("标题广告:其实还没剪(先不摆)", lambda: self.set_title_ad_ok(False))
            else:
                m.addAction("标题有广告词:视频里的广告剪好了 / 不是广告,能摆", lambda: self.set_title_ad_ok(True))
        wm = self.videos[row].wm if row < len(self.videos) else None
        if wm and wm.get("hits"):
            m.addSeparator()
            if wm.get("shot"):
                m.addAction("看水印截图", lambda: os.startfile(wm["shot"]) if os.path.isfile(wm["shot"]) else None)
            if wm.get("blurred"):
                m.addAction("水印已经糊掉了(原片在「水印原片」里)").setEnabled(False)
            elif wm.get("ok"):
                m.addAction("其实有水印(先不摆)", lambda: self.set_wm_ok(False))
            else:
                m.addAction("没水印 / 不用管,能摆", lambda: self.set_wm_ok(True))
        m.exec(self.table.viewport().mapToGlobal(pos))

    # ---------- 查水印 ----------
    def run_wm(self):
        """查勾上的员工的视频(没发的)有没有水印。查过、文件没变的直接用上次的。"""
        if self.wm_worker and self.wm_worker.isRunning():
            self.wm_worker.stop = True
            self.say("正在停查水印…(手上的几条查完就停,查完的记着)")
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "查水印", "正在摆,摆完再查。")
            return
        rows = [i for i, v in enumerate(self.videos) if not self.rec.status_of(v.path) and v.wm is None and not v.skip]
        if not self.videos:
            QMessageBox.information(self, "查水印", "先在左边勾上员工。")
            return
        if not rows:
            n = sum(1 for v in self.videos if v.wm and v.wm.get("hits") and not v.wm.get("ok"))
            QMessageBox.information(self, "查水印", "勾上的都查过了" + (f",有 {n} 条有水印(标黄的)。" if n else ",没查到水印。"))
            return
        self.wm_worker = WmWorker(self.videos, rows, self)
        self._wm_left = len(rows)
        self.wm_worker.one.connect(self._wm_one)
        self.wm_worker.log.connect(self.say)
        self.wm_worker.finished.connect(self._wm_done)
        self.b_wm.setText("停查水印")
        self.say(f"查水印:{len(rows)} 条(一条几秒,3 条一起查;再点一下按钮就停)")
        self.wm_worker.start()

    def _wm_one(self, i: int):
        self._wm_left -= 1
        self._fill_row(i)
        self.b_wm.setText(f"停查水印(还剩 {self._wm_left})")

    def _wm_done(self):
        from qe import wmstore
        self.b_wm.setText("查水印")
        n = sum(1 for v in self.videos if wmstore.blocks(v.wm))
        self.say(f"查水印完了:{n} 条有水印(标黄,不摆;鼠标放在状态上看截图,不是水印就右键「没水印,能摆」)" if n else "查水印完了:没查到水印")

    def run_blur(self):
        """把查到水印、还没处理的糊掉。"""
        from qe import blur, wmstore
        busy = [w for w in (self.wm_worker, self.blur_worker, self.worker) if w and w.isRunning()]
        if busy:
            QMessageBox.information(self, "模糊水印", "还在查水印 / 摆 / 糊,等它做完。")
            return
        rows = [i for i, v in enumerate(self.videos) if not self.rec.status_of(v.path) and wmstore.blocks(v.wm)
                and blur.boxes_of(v.wm)]
        if not rows:
            QMessageBox.information(self, "模糊水印", "勾上的里面没有查到水印的(还没查的先点「查水印」)。")
            return
        if not self._ask("模糊水印", f"把 {len(rows)} 条查到的水印糊掉(只糊水印出现的那几段)?\n\n"
                         "原片挪进同一个文件夹里的「水印原片」,不删。", "糊掉", "先不"):
            return
        self.blur_worker = BlurWorker(self.videos, rows, self)
        self._blur_left = len(rows)
        self.blur_worker.one.connect(self._blur_one)
        self.blur_worker.finished.connect(lambda: (self.b_blur.setText("模糊水印"), self.b_blur.setEnabled(True),
                                                   self.say("模糊水印做完了(原片在各自文件夹的「水印原片」里)")))
        self.b_blur.setEnabled(False)
        self.say(f"模糊水印:{len(rows)} 条(2 条一起做)")
        self.blur_worker.start()

    def _blur_one(self, i: int, err: str):
        self._blur_left -= 1
        self.b_blur.setText(f"糊水印中(还剩 {self._blur_left})")
        v = self.videos[i]
        self.say(f"「{v.title}」模糊水印失败:{err}" if err else f"「{v.title}」水印糊掉了")
        self._fill_row(i)

    def set_title_ad_ok(self, ok: bool):
        """标题有广告词的:人剪好了 / 看过不是广告 → 能摆(按 号 + 标题 记,剪完视频文件变了也认得)。"""
        from qe import titleclean
        rows = sorted({ix.row() for ix in self.table.selectedIndexes()})
        rows = [r for r in rows if r < len(self.videos) and titleclean.ad_words(self.videos[r].title)]
        for r in rows:
            v = self.videos[r]
            titleclean.store().set(v.account, v.title, ok)
            self._fill_row(r)
        if rows:
            self.say(f"{len(rows)} 条标题有广告词的标成" + ("「剪好了,能摆」" if ok else "「还没剪,先不摆」"))
        self._update_sum()

    def set_wm_ok(self, ok: bool):
        from qe import wmstore
        rows = sorted({ix.row() for ix in self.table.selectedIndexes()})
        rows = [r for r in rows if r < len(self.videos) and (self.videos[r].wm or {}).get("hits")]
        for r in rows:
            v = self.videos[r]
            wmstore.set_ok(v.path, ok)
            v.wm["ok"] = ok
            self._fill_row(r)
        if rows:
            self.say(f"{len(rows)} 条标成" + ("「没水印,能摆」" if ok else "「有水印,先不摆」"))

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
        self._update_tree_counts()

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
        yellow = waiting and getattr(self, "_yellow_stop", False)
        for b, main in ((self.b_go, not waiting), (self.b_sent, waiting and not yellow)):
            if (b.objectName() == "primary") != main:
                b.setObjectName("primary" if main else "")
                b.style().unpolish(b)
                b.style().polish(b)
        if running:
            self.hint.setText("正在摆…摆的时候别在罐头里切到别的号。要停就点「停」。")
        elif waiting:
            n = self.rec.ready_in_batch(self.batch_id)
            acc = self.batch_videos[0].account if self.batch_videos else ""
            self.hint.setText(f"「{acc}」这批 {n} 条摆好了 → 去罐头里检查,点「发布 → 全部发布」→ 回来点「这批发好了」"
                              "(不要了就在罐头里删掉,点「这批不要了」)")
        else:
            self.hint.setText("")
        # 大按钮那排只露现在该点的:平时「摆下一批」;摆好了「这批发好了 / 这批不要了」;摆的时候「停」
        self.b_go.setVisible(not waiting)
        self.b_sent.setVisible(bool(self.batch_id))
        self.b_drop.setVisible(bool(self.batch_id))
        self.b_pubgo.setVisible(yellow)
        self.b_stop.setVisible(running)
        # 审查 16:摆的时候 / 摆好等确认时底栏只留要点的,「查水印 / 模糊水印 / 封面都看过了」先藏起来
        for b in (self.b_wm, self.b_blur, self.b_allok, self.b_review):
            b.setVisible(not running and not waiting)
        self.b_go.setEnabled(not running and not self.batch_id)
        self.b_stop.setEnabled(running)
        self.b_sent.setEnabled(not running and bool(self.batch_id))
        self.b_drop.setEnabled(not running and bool(self.batch_id))
        self.b_move.setEnabled(not running and bool(self.c_date.currentData()))
        self.c_date.setEnabled(not running)
        self.b_refresh.setEnabled(not running)          # 摆的时候不许刷新(会换掉中间的列表)
        self.tree.setEnabled(not running)
        if hasattr(self, "lab_scope"):
            self._update_scope()
        self._edu_hero()

    def _edu_hero(self):
        """教育号页的大字:现在该干什么。"""
        if not hasattr(self, "hero"):
            return
        running = bool(self.worker and self.worker.isRunning())
        n = len(self.videos)
        st = [self.rec.status_of(v.path) for v in self.videos]
        counts = f"勾上 {n} 条 · 已发 {st.count('已发')} · {READY} {st.count('摆好')} · 还没发 {st.count('')}" if n else ""
        if running:
            big, sub, tone = "正在摆…", "摆的时候别在罐头里切到别的号。要停就点「停」。", ""
            if self._unattended:
                big = "正在自己摆、自己发…"
        elif self.batch_id:
            nb = self.rec.ready_in_batch(self.batch_id)
            acc = self.batch_account()
            big, tone = (f"「{acc}」这批 {nb} 条摆好了" if acc else f"这批 {nb} 条摆好了"), "good"
            sub = "去罐头里检查,点「发布 → 全部发布」→ 回来点「这批发好了」(不要了就在罐头里删掉,点「这批不要了」)"
            if getattr(self, "_yellow_stop", False):
                ny = sum(1 for v in self.batch_videos if v.warn)
                big, tone = f"「{acc}」这批摆好了,{ny} 条封面标黄" if ny else big, "warn"
                sub = "看过没问题就点「封面看过了,接着自动发布」,软件自己点发布、接着摆下一批;要改就去罐头里改好再点"
        elif not self.c_date.currentData():
            big, sub, tone = "先选要发哪天的", PICK_DAY, ""
        elif not n:
            big, sub, tone = "勾上要发的员工", PICK_EMP, ""
        else:
            acc, vids = self.next_batch()
            if vids:
                big, tone = f"下一步:摆「{acc}」{len(vids)} 条", ""
                sub = "摆好停在发布前,发布你自己点 · " + counts
                left = self._edu_left(acc)
                if left is not None:
                    sub += f" · 「{acc}」今天还能发 {left} 条"
            elif st.count("") == 0:
                big, sub, tone = "勾上的都发了 √", counts, "good"
            else:
                big, sub, tone = "勾上的都不能摆", "看列表里的状态(鼠标放上去看为什么)· " + counts, "warn"
        self.hero.set(big, sub, tone)

    def next_batch(self) -> tuple[str, list]:
        """下一批:勾上的里面还没发 / 没摆的,同一个号的前 10 条(一批只能是一个号)。
        用户 2026-10-20:每个号最多发到这天的规定条数(家长小天地 54 / 家长研习空间 102),最后一批只摆差的那几条。"""
        todo = self._todo()
        if not todo:
            return "", []
        acc = todo[0].account
        n = max(1, min(10, int(self.st.get("batch_size", 10) or 10)))
        left = self._edu_left(acc)
        if left is not None:
            n = min(n, left)
        return acc, [v for v in todo if v.account == acc][:n]

    def _quota_day(self) -> str:
        """闸按哪天算:罐头定时发到哪天就算哪天,平时算今天(北京时间)。"""
        at = getattr(self, "_sched_at", "") if self._unattended else ""
        return at[:10] if at else plan.today()

    def _edu_left(self, acc: str) -> int | None:
        """这个号这天还能发几条(已经发出去的 / 罐头定时定到这天的都算);不限 = None。"""
        return plan.left_today(self.rec, self.st, acc, self._quota_day())

    def _edu_spill(self) -> int:
        """这天发够规定条数的号:勾上的里面它还没发的视频(连同封面)挪到明天的日期文件夹,文件夹结构不变
        (小学生教育\10.20\小天地\张\a.mp4 → 小学生教育\10.21\小天地\张\a.mp4)。返回挪了几条。"""
        if self.worker and self.worker.isRunning() or self.batch_id:
            return 0
        root = os.path.normcase(os.path.normpath(self.st["material_root"]))
        tmr = plan.tomorrow_folder()
        n, accs = 0, set()
        for v in self.videos:
            if self.rec.status_of(v.path) or self.row_note.get(v.path, "").startswith("挪到明天") or not os.path.isfile(v.path):
                continue
            if self._edu_left(v.account) != 0:
                continue
            day_dir = os.path.dirname(v.path)
            while day_dir and os.path.normcase(os.path.dirname(day_dir)) != root and os.path.dirname(day_dir) != day_dir:
                day_dir = os.path.dirname(day_dir)
            if os.path.normcase(os.path.dirname(day_dir)) != root:
                continue                               # 不在素材文件夹的日期文件夹下面:不动
            dst_root = os.path.join(self.st["material_root"], tmr)
            try:
                for f in [v.path] + [p for p in (v.png, v.jpg, v.vpng) if p and os.path.isfile(p)
                                     and os.path.normcase(p).startswith(os.path.normcase(day_dir) + os.sep)]:
                    rel = os.path.relpath(f, day_dir)
                    plan.move_noclobber(f, os.path.join(dst_root, os.path.dirname(rel)))
            except OSError as e:
                self.say(f"⚠「{v.title[:24]}」挪不到明天的文件夹:{e}")
                continue
            n += 1
            accs.add(v.account)
            v.skip = f"这天发够规定条数了,挪到明天({tmr})"
            self.row_note[v.path] = f"挪到明天({tmr})"
            if v in self.videos:
                self._fill_row(self.videos.index(v))
        if n:
            self.say(f"{'、'.join(sorted(accs))} 这天发够规定条数了:还没发的 {n} 条挪到了明天的文件夹 {tmr}")
            self._update_scope()
        return n

    def _edu_short(self) -> str:
        """勾上的号里这天还没发够、又没得摆了的:「家长小天地 还差 3 条」(不能少发:素材不够要说)。"""
        out = []
        for acc in sorted({v.account for v in self.videos}):
            left = self._edu_left(acc)
            if left:
                out.append(f"{acc} 还差 {left} 条")
        return "、".join(out)

    def _todo(self) -> list:
        """勾上的里面能摆、还没发 / 没摆的。"""
        from qe import wmstore
        todo = [v for v in self.videos if not self.rec.status_of(v.path) and (v.cover_kind or v.cover_why) and v.cover
                and not v.skip                        # 同号同名 / 0 字节 / 发过同名的不摆(表里写着为什么)
                and not wmstore.blocks(v.wm)]         # 查到水印、人还没说没问题的不摆
        from qe import titleclean                     # 标题有广告词的(视频里八成有广告):人右键「剪好了」才摆
        todo = [v for v in todo if not titleclean.ad_problem(v.account, v.title)]
        if self._unattended:                          # 定时发布:还标黄的(人没看过)、这一轮跳过的不摆
            todo = [v for v in todo if not v.warn and v.path not in self._sched_skip]
        full = {a for a in {v.account for v in todo} if self._edu_left(a) == 0}     # 这天发够规定条数的号不再摆(用户 2026-10-20)
        return [v for v in todo if v.account not in full]

    def _ask(self, title: str, text: str, yes: str, no: str, default_no: bool = False, head: str = "",
             danger: bool = False) -> bool:
        import gui.api_tab as A                       # 中文动词按钮的确认框(和接口页同一个);head = 第一行红字
        return A.ask(self, title, text, yes, no, default_no=default_no, head=head, danger=danger)

    def _ask_yellow(self, n: int, how: dict) -> bool:
        """A:勾了「摆好后自动点发布」、勾上的员工里有标黄的封面 → 问一次。True = 都看过了(去黄,一路自动发);
        how["stop"] = 还没看(照旧,有标黄的那批停下来叫人);都不是 = 先不摆。"""
        import gui.api_tab as A
        return A.ask(self, "摆下一批", f"勾上的员工里有 {n} 条封面标黄(软件拿不准框得对不对)。\n\n"
                                    "都在「预览封面」里看过、没问题了吗?\n"
                                    "· 都看过了:它们不再标黄,这次一路自动发到底,中间不再停\n"
                                    "· 还没看:照旧摆,摆到有标黄的那批就停下来叫你",
                     "都看过了,一路自动发", "先不摆", extra="还没看,停下来叫我", on_extra=lambda: how.update(stop=True),
                     default_no=True, danger=True)        # 会真发出去:回车 = 先不摆(新员工试用 2026-10-21)

    def continue_publish(self):
        """B:这批因为封面标黄停下来了,人看过了 → 软件在罐头里点「全部发布」,然后接着摆下一批。"""
        if not self.batch_id or (self.worker and self.worker.isRunning()):
            return
        vids = list(self.batch_videos)
        acc = vids[0].account if vids else ""
        ylw = [v for v in vids if v.warn]
        if not self._ask("接着自动发布", f"「{acc}」这批 {len(vids)} 条已经摆好了" + (f",其中 {len(ylw)} 条封面标黄" if ylw else "") + "。\n\n"
                         "封面都看过了、没问题?点「看过了,发布」以后软件在罐头里点「全部发布」,"
                         + ("然后接着摆下一批。" if self.k_auto.isChecked() else "发完就停。"),
                         "看过了,发布", "先不", default_no=True, head="这次会自动点发布:马上发出去(不是定时)", danger=True):
            return
        self._mark_covers_ok(ylw)
        self._yellow_stop = False
        shots = str(data_dir() / "截图" / bj_str()[:10])
        self.worker = BatchWorker(acc, vids, shots, self, auto_publish=True, publish_only=True)
        self.worker.log.connect(self.say)
        self.worker.finished_batch.connect(self._batch_done)
        self.worker.start()
        self.say(f"封面看过了:软件在罐头里给「{acc}」这批点「全部发布」…")
        self._refresh_buttons()

    def _nothing_left(self) -> str:
        """没有能摆的了:前面先写发够规定条数的号 / 没发够的号(用户 2026-10-20:不能多发也不能少发),再写别的原因。"""
        full = [a for a in sorted({v.account for v in self.videos}) if self._edu_left(a) == 0]
        short = self._edu_short()
        head = ((f"这天发够规定条数的号:{'、'.join(full)}(还没发的挪到明天的文件夹)。\n\n" if full else "") +
                (f"⚠ 还没发够:{short}(素材不够 / 没摆成 / 不能摆,要补的话让员工再放一些)。\n\n" if short else ""))
        return head + self._nothing_left0()

    def _nothing_left0(self) -> str:
        """没有能摆的了:说清楚是真发完了,还是剩下的缺无字封面(png)。"""
        nocover = [v for v in self.videos if not self.rec.status_of(v.path) and (v.cover_kind or v.cover_why) and not v.cover]
        from qe import wmstore
        skip = [v for v in self.videos if not self.rec.status_of(v.path) and v.skip]
        tail = (f"\n\n另有 {len(skip)} 条不发:「{skip[0].title[:24]}」{skip[0].skip}" + ("等" if len(skip) > 1 else "")) if skip else ""
        wmv = [v for v in self.videos if not self.rec.status_of(v.path) and not v.skip and wmstore.blocks(v.wm)]
        if wmv:
            tail += f"\n\n有 {len(wmv)} 条查到水印没摆(标黄的),比如「{wmv[0].title[:24]}」;不是水印就右键「没水印,能摆」。"
        from qe import titleclean
        tad = [v for v in self.videos if not self.rec.status_of(v.path) and not v.skip and titleclean.ad_problem(v.account, v.title)]
        if tad:
            tail += f"\n\n有 {len(tad)} 条标题有广告词没摆,比如「{tad[0].title[:24]}」;剪好了就右键「…能摆」。"
        if nocover:
            return (f"能摆的都摆完了,但还有 {len(nocover)} 条没有无字封面(png),没摆,比如「{nocover[0].title[:24]}」。\n\n"
                    "让员工补上 png 以后点「刷新」再摆。" + tail)
        if tail:
            return "能摆的都摆完了,剩下的这次不摆:" + tail
        return "勾上的员工都发完了(或者都摆好了等你确认)。"

    def _auto_toggled(self, on: bool):
        if on:
            self.say("已勾上:摆好后软件自己点「全部发布」,接着摆下一批(有问题会停下来叫你)")

    def start_batch(self, chained: bool = False):
        if not self._unattended and not chained:        # 审查 10:没勾员工原来说「都发完了」,人以为发完了
            if not self.c_date.currentData():
                QMessageBox.information(self, "摆下一批", PICK_DAY + ",再勾上员工。")
                return
            if not self.checked_dirs():
                QMessageBox.information(self, "摆下一批", "你还没勾员工:先在左边勾上要发的员工(可以勾好几个),再点「摆下一批」。")
                return
        busy = ("还在查水印,查完再摆(或者点「停查水印」)。" if self.wm_worker and self.wm_worker.isRunning() else
                "还在糊水印,糊完再摆。" if getattr(self, "blur_worker", None) and self.blur_worker.isRunning() else
                "封面还在认人,等几秒再点。" if self.cover_worker and self.cover_worker.isRunning() else "")
        if busy:
            if self._unattended:                       # 定时发布:等一会儿再来,不弹框
                from PySide6.QtCore import QTimer
                QTimer.singleShot(5000, lambda: self._unattended and self.start_batch(chained=True))
            else:
                QMessageBox.information(self, "企鹅号发布助手", busy)
            return
        if not chained and not self._unattended:
            self._edu_spill()                          # 发够规定条数的号:还没发的先挪到明天
        acc, vids = self.next_batch()
        if not vids:
            if self._unattended:
                self._sched_finish()
            else:
                QMessageBox.information(self, "企鹅号发布助手", self._nothing_left())
            return
        # 列表是打开 / 刷新时翻的(缓存):员工后来改了名 / 挪走了,罐头里会传个不存在的文件 → 先挡下来叫人刷新
        gone = [v for v in vids if not os.path.isfile(v.path)]
        if gone and self._unattended:                 # 定时发布:找不到的跳过,接着摆别的
            for v in gone:
                self._sched_skip.add(v.path)
                self.say(f"⚠ 视频文件找不到了(员工改名 / 挪走了?),跳过:「{v.title[:30]}」")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._unattended and self.start_batch(chained=True))
            return
        if gone:
            QMessageBox.information(self, "企鹅号发布助手",
                                    f"这批里有 {len(gone)} 条视频文件找不到了(员工改名 / 挪走了?),比如「{gone[0].title[:24]}」。\n\n"
                                    "点「刷新」重新读一遍文件夹再摆。")
            return
        if self.k_auto.isChecked() and not chained and not self._unattended:
            # 用户 2026-10-19:不定时的时候标黄的去不掉,每批都停下来叫我手动发 → 开始前问一次(和定时那边一样)
            ylw = [v for v in self.videos if v.warn and v.cover and not self.rec.status_of(v.path) and not v.skip]
            if ylw:
                how = {}
                yes = self._ask_yellow(len(ylw), how)
                if how.get("stop"):
                    pass                                    # 还没看:照旧,有标黄的那批停下来叫人
                elif not yes:
                    return
                else:
                    self._mark_covers_ok(ylw)
        warn = [v for v in vids if v.warn]
        # 没有无字封面(png)的不摆,跳过(审查:原来一条没 png 就挡住这个号后面所有的)
        nocover = [v for v in self.videos if not self.rec.status_of(v.path) and (v.cover_kind or v.cover_why) and not v.cover]
        msg = f"在罐头里给「{acc}」摆 {len(vids)} 条:\n\n" + "\n".join(f"· {v.title[:30]}" for v in vids)
        if nocover:
            msg += (f"\n\n另有 {len(nocover)} 条没有无字封面(png)先跳过,比如「{nocover[0].title[:24]}」"
                    "(jpg 有字不能用,让员工补上 png)。")
        skip = [v for v in self.videos if not self.rec.status_of(v.path) and v.skip]
        if skip:
            msg += f"\n\n另有 {len(skip)} 条不发(同号同名 / 坏文件 / 发过同名的),比如「{skip[0].title[:24]}」:{skip[0].skip}。"
        if warn:
            msg += f"\n\n其中 {len(warn)} 条封面标黄,建议先点「预览封面」看一眼。"
        auto = self.k_auto.isChecked()
        msg += ("\n\n摆好后软件自己点「全部发布」,接着摆下一批(有标黄 / 没摆好的会停下来叫你)。" if auto else
                "\n\n软件只摆好,不点发布。") + "摆的时候别在罐头里切到别的号。开始吗?"
        if not chained and not self._ask("摆下一批", msg, "开始摆,并自动发布" if auto else "开始摆", "先不",
                                         head="这次会自动点发布:摆好就马上发出去(不是定时)" if auto else "",
                                         default_no=auto, danger=auto):   # 自动点发布 = 真发:回车 = 先不(新员工试用 2026-10-21)
            return
        if chained:
            if (self.c_date.currentData(), sorted(self.checked_dirs())) != getattr(self, "_chain_key", None):
                if self._unattended:                   # 没人看着:不弹框卡住,写日志、收尾(审查 B8)
                    self.say("⚠ 摆的时候有人换了日期 / 改了勾选的员工,定时发布先停下")
                    self._sched_finish("摆的时候换了日期 / 改了勾选的员工,定时发布先停下了")
                    return
                QMessageBox.information(self, "自动发布停下了", "摆的时候换了日期 / 改了勾选的员工,自动连发先停下。\n\n"
                                                              "要接着发,确认一下日期和员工,再点「摆下一批」。")
                return
        else:
            self._chain_key = (self.c_date.currentData(), sorted(self.checked_dirs()))
            self._chain_stop = False                   # 人自己点「摆下一批」:之前点过的「停」不算了
        self.batch_id = f"{acc}-{bj_str().replace(' ', '_').replace(':', '')}"
        self.batch_videos = vids
        self._batch_acc = acc
        shots = str(data_dir() / "截图" / bj_str()[:10])
        self.worker = BatchWorker(acc, vids, shots, self, auto_publish=self.k_auto.isChecked(), unattended=self._unattended,
                                  sched_at=getattr(self, "_sched_at", "") if self._unattended else "")
        self.worker.log.connect(self.say)
        self.worker.one.connect(self._one_done)
        self.worker.finished_batch.connect(self._batch_done)
        self.worker.start()
        for v in vids:                                # 这批的行先写「上传中」:罐头先把整批视频传完,再一条条弄封面
            self.row_note[v.path] = WAIT_NOTE            # (用户:一直「排队中」以为卡住了,其实在传)
            if v in self.videos:
                self._fill_row(self.videos.index(v))
        self.say(f"开始给「{acc}」摆 {len(vids)} 条:先把这 {len(vids)} 条视频一起传到罐头里(网慢的话要几分钟),传完再一条条弄封面…")
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
            if self.row_note.get(v.path) == WAIT_NOTE:
                self.row_note.pop(v.path, None)
                if v in self.videos:
                    self._fill_row(self.videos.index(v))
        ok = [x for x in (res or []) if x[1]]
        bad = [x for x in (res or []) if not x[1]]
        ready = self.rec.ready_in_batch(self.batch_id) if self.batch_id else 0
        if not ok and not ready:
            self.batch_id = ""                         # 一条都没摆上:不用等人确认
        if self._unattended and self._sched_batch_done(ok, bad, ready, err, pub):
            return
        if pub == "ok":
            n = self.rec.mark_batch_published(self.batch_id)
            self.say(f"软件点了「全部发布」:这批 {n} 条发出去了({bj_str()})")
            self.batch_id = ""
            self._after_batch()
            if self._chain_stop:                       # 摆的时候点了「停」,这批还是发完了:不再接着摆(审查 B5)
                self.say("你点了「停」,不再接着摆下一批")
            elif self.k_auto.isChecked() and self.next_batch()[1]:
                self.say("3 秒后摆下一批…(点「停」不再继续)")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: None if getattr(self, "_chain_stop", False) or not self.k_auto.isChecked()
                                  else self.start_batch(chained=True))
            elif self.k_auto.isChecked():
                QMessageBox.information(self, "发完了", self._nothing_left())
            return
        self._yellow_stop = bool(pub) and "标黄" in pub and not err and bool(ok) and not bad
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
            if self._yellow_stop:
                text += "\n\n封面看过了没问题的话,点上面的「封面看过了,接着自动发布」,软件自己点发布、接着摆下一批。"
            QMessageBox.information(self, "摆好了", text)
        self._refresh_buttons()
        self._update_sum()

    # ---------------- 定时发布(没人看着,发到完为止) ----------------
    def _sched_changed(self):
        at = getattr(self, "_sched_at", "")
        self.lab_sched.setText(("⏰ 正在摆,每批定时到 " + at[5:] + "(北京时间)…" if at else "⏰ 正在自己发…") if self._unattended else "")
        self.b_sched.setText("停下定时发布" if self._unattended else "摆好并定时发出…")

    def schedule_clicked(self):
        """教育号用罐头自带的「全部定时发布」(用户 2026-10-17):现在就一批一批摆好、每批定时到同一个点,
        到点企鹅号自己发,电脑能关。只能定 7 天以内、5 分钟一档。"""
        if self._unattended:
            if self._ask("定时发布", "正在一批一批摆、定时。停下来吗?(手上这批做完就停,已经定好的记着)", "停下", "接着弄"):
                self._chain_stop = True
                if self.worker and self.worker.isRunning():
                    self.worker.stop()
                    self.say("正在停…")
                else:
                    self._sched_finish("你让定时发布停下了")
            return
        if self.worker and self.worker.isRunning() or self.batch_id:
            QMessageBox.information(self, "定时发布", "上一批还在摆 / 摆好了没确认,弄完那批再定时。")
            return
        from gui.schedule import ask_schedule, now_str, short_at
        dates = [self.c_date.itemData(i) for i in range(1, self.c_date.count())]
        if not dates:
            QMessageBox.information(self, "定时发布", "素材文件夹里没有日期文件夹。")
            return
        while True:
            r = ask_schedule(self, "定时发布 · 教育号", dates, self.c_date.currentData() or "",
                             "用罐头自带的「全部定时发布」:点「定好了」软件就开始一批一批摆,每批都定时到这个点。\n"
                             "摆完电脑就能关,到点企鹅号自己发。只能定 7 天以内、分钟选 00 / 05 / 10 … 55。\n"
                             "还标黄的封面不发(先在「预览封面」里看好,点「封面都看过了」);没摆好的再试一次,还不行关掉不发。",
                             tip="这里的时间都是北京时间(企鹅号也按北京时间算)。",
                             head="教育号用罐头自带的定时:软件现在就一批批摆好定上,摆完电脑就能关,到点企鹅号自己发。",
                             overview=self._sched_overview)
            if not r:
                return
            at, date = r
            import datetime as _dt
            gap = (_dt.datetime.strptime(at, "%Y-%m-%d %H:%M") - _dt.datetime.strptime(now_str(), "%Y-%m-%d %H:%M")).total_seconds() / 60
            if int(at[-2:]) % 5:
                QMessageBox.information(self, "定时发布", "罐头的定时只能选 5 分钟一档:分钟要是 00、05、10 … 55。")
            elif gap < 30:
                QMessageBox.information(self, "定时发布", "至少定在半小时以后(摆一批要几分钟,太近了来不及)。")
            elif gap > 6 * 24 * 60:
                QMessageBox.information(self, "定时发布", "罐头只能定 7 天以内。")
            else:
                n, nb = self._sched_estimate(date)     # 审查 B7:批数多、定得近,后面的批摆好时已经不到 10 分钟,罐头不让定
                need = nb * 10 + 10                    # 每批大约 5~10 分钟,按 10 算,另留 10 分钟余量
                if gap >= need or self._ask(
                        "时间可能不够", f"{date} 还有大约 {n} 条没发,要摆 {nb} 批,每批 5~10 分钟,全部摆完大概要 "
                        f"{nb * 5}~{nb * 10} 分钟。\n\n现在离 {short_at(at)} 只有 {int(gap)} 分钟,后面几批可能来不及定"
                        "(罐头不让定在 10 分钟以内),来不及的就不定了。\n\n"
                        f"建议定在 {need} 分钟以后。", "照样开始", "改时间", default_no=True):
                    break
        if not self._ask("定时发布", f"现在开始摆 {date} 的(勾上这天所有员工),每批都在罐头里「全部定时发布」到\n"
                                     f"{short_at(at)}(北京时间)。\n\n摆的时候别动罐头;摆完电脑能关,到点企鹅号自己发。开始吗?",
                         "开始", "先不"):
            return
        self._sched_fire(date, at)

    def _sched_counts(self, date: str) -> dict[str, int]:
        """这天每个号还有几条没发(不算不发的)。"""
        per: dict[str, int] = {}
        try:
            for acc, dirs in F.account_dirs(self.st["material_root"], date, self.st).items():
                vs = [v for d in dirs for v in F.scan_account(d, acc, date)]
                F.mark_dups(vs, prefer=lambda v: bool(self.rec.status_of(v.path)))     # 同号同名只算一条
                per[acc] = sum(1 for v in vs if not v.skip and not self.rec.status_of(v.path))
        except OSError:
            pass
        return {k: n for k, n in per.items() if n}

    def _sched_estimate(self, date: str) -> tuple[int, int]:
        """定时前估一下:这天还有几条没发、要摆几批(一批只能一个号,每个号按「一批几条」分)。"""
        import math
        per = self._sched_counts(date)
        bs = max(1, min(10, int(self.st.get("batch_size", 10) or 10)))
        return sum(per.values()), sum(math.ceil(k / bs) for k in per.values())

    def _sched_overview(self, date: str) -> str:
        """定时框最上面的总览(审查 12):这天每个号要摆几条、几批。"""
        import math
        per = self._sched_counts(date)
        if not per:
            return "这天没有要发的视频(都发过了 / 还没有素材)"
        bs = max(1, min(10, int(self.st.get("batch_size", 10) or 10)))
        return (f"要摆 {sum(per.values())} 条(封面还标黄的不发):" +
                "、".join(f"{a} {n} 条({math.ceil(n / bs)} 批)" for a, n in per.items()))

    def all_covers_ok(self):
        vs = [v for v in self.videos if v.warn and v.cover and not self.rec.status_of(v.path)]
        if not vs:
            QMessageBox.information(self, "封面都看过了", "勾上的员工里现在没有标黄的封面。" if self.videos else "左边先勾上员工。")
            return
        if not self._ask("封面都看过了", f"勾上的员工里有 {len(vs)} 条封面标黄。\n\n都在「预览封面」里看过、调好了?点了以后它们不再标黄,"
                                        "自动发布 / 定时发布不会再为它们停下来。", "都看过了", "还没看完"):
            return
        self._mark_covers_ok(vs)

    def quick_review(self):
        """快速过封面:勾上的员工里还标黄的,一屏看完。"""
        vs = [v for v in self.videos if v.warn and v.cover and not self.rec.status_of(v.path) and not v.skip]
        if not vs:
            QMessageBox.information(self, "快速过封面", "勾上的员工里现在没有标黄的封面。" if self.videos else "左边先勾上员工。")
            return
        from gui.cover_review import QuickReview
        d = QuickReview(vs, self.adj, self)
        d.changed.connect(lambda v: v in self.videos and self._fill_row(self.videos.index(v)))
        d.exec()
        n = sum(1 for v in vs if not v.warn)
        if n:
            self.say(f"快速过封面:{n} 张标黄的封面看过了,不再标黄" + (f"(还有 {len(vs) - n} 张标黄)" if n < len(vs) else ""))
        self._update_scope()

    def _mark_covers_ok(self, vs):
        """这几条标黄的封面记成「人看过了」:不再标黄,自动发布 / 定时发布不会再为它们停下来。"""
        for v in vs:
            self.adj.set_ok(v.path, v.cover)
            v.warn = False
            if "人看过" not in v.cover_why:
                v.cover_why += "(人看过了)"
            if v in self.videos:
                self._fill_row(self.videos.index(v))
        if vs:
            self.say(f"{len(vs)} 条标黄的封面记成「人看过了」,不再标黄")
        self._update_scope()

    def _sched_fire(self, date: str, at: str = ""):
        """选这天、勾上所有员工、开始一批一批摆 + 自己点「全部发布」;at(北京时间)= 每批点「全部定时发布」定到这个点。"""
        if self.worker and self.worker.isRunning() or self.batch_id:
            self.say("⚠ 到点了,但上一批还在摆 / 摆好了没确认,定时发布没开始(弄完那批再点「摆下一批」)")
            return
        i = self.c_date.findData(date)
        if i < 0:
            self._load_dates()
            i = self.c_date.findData(date)
        if i < 0:
            self.say(f"⚠ 到点了,但素材里没有「{date}」这天的文件夹,定时发布没开始")
            return
        self.c_date.setCurrentIndex(i)                 # 换日期会重读;同一天也重读一遍(员工可能加了视频)
        self._load_tree()
        self.tree.blockSignals(True)
        for k in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(k)
            for j in range(top.childCount()):
                if top.child(j).data(0, Qt.ItemDataRole.UserRole + 2):     # 员工行才勾(灰的「不发」文件夹不勾)
                    top.child(j).setCheckState(0, Qt.CheckState.Checked)
        self.tree.blockSignals(False)
        self._load_videos()
        self._unattended, self._sched_skip, self._sched_tries, self._sched_at = True, set(), 0, at
        self._chain_stop = False                       # 以前点过的「停」不算(审查 B6:不清掉的话重试永远不跑、也不收尾)
        self._sched_n0 = sum(1 for v in self.videos if self.rec.status_of(v.path) == "已发")
        from gui.schedule import keep_awake
        keep_awake("定时-edu-发", True)
        self._chain_key = (self.c_date.currentData(), sorted(self.checked_dirs()))
        self._sched_changed()
        warn = [v for v in self.videos if v.warn and not self.rec.status_of(v.path)]
        self.say(f"⏰ 定时发布开始:{date},{len(self.videos)} 条" + (f"(其中 {len(warn)} 条封面还标黄,不发)" if warn else ""))
        self.start_batch(chained=True)

    def _sched_batch_done(self, ok, bad, ready, err, pub) -> bool:
        """定时发布时一批弄完:接着下一批 / 等一会儿重试 / 停下。返回 True = 这里处理完了。"""
        from PySide6.QtCore import QTimer
        for v, _o, why in bad:                        # 没摆好、已经关掉没发的:这一轮不再拿
            self._sched_skip.add(v.path)
        if pub in ("ok", "none") and not err:
            if pub == "ok":
                at = getattr(self, "_sched_at", "")
                n = self.rec.mark_batch_published(self.batch_id, at)
                self.say((f"软件点了「全部定时发布」:这批 {n} 条定好了,{at}(北京时间)企鹅号自己发" if at else
                          f"软件点了「全部发布」:这批 {n} 条发出去了({bj_str()})") + (f";{len(bad)} 条没摆好,关掉了没发" if bad else ""))
            else:
                self.say(f"这批 {len(bad)} 条都没摆好,关掉了没发,接着下一批")
            self.batch_id = ""
            self._sched_tries = 0
            self._after_batch()
            if self._chain_stop:                       # 摆的时候点了「停」但这批照样定好了:不再接着摆(审查 B5)
                self._sched_finish("你点了「停」,定时发布停下了")
                return True
            self.say("3 秒后摆下一批…(点「停」不再继续)")
            QTimer.singleShot(3000, self._sched_next)
            return True
        if err == "停下了":                            # 人点了停
            self._sched_finish(f"你点了「停」,定时发布停下了" + (f"(罐头里还摆着 {max(len(ok), ready)} 条没发,看一眼)" if ok or ready else ""))
            return True
        if err and not ok and not ready and self._sched_tries < 2:     # 一条都没摆上(罐头没开 / 网断 …):歇 1 分钟再试
            self._sched_tries += 1
            self.say(f"⚠ 这批没摆成:{err}。1 分钟后再试(第 {self._sched_tries} 次)")
            self._after_batch()
            QTimer.singleShot(60000, self._sched_next)
            return True
        self._refresh_buttons()
        self._sched_finish(f"定时发布停下了:{pub or err}" + (f"\n\n罐头里还摆着 {max(len(ok), ready)} 条没发,看一眼:要发就点「发布 → 全部发布」"
                                                             "再回来点「这批发好了」,不要就删掉点「这批不要了」。" if self.batch_id else ""))
        return True

    def _sched_next(self):
        """定时连发:等了 3 秒 / 1 分钟以后接着摆。已经收尾了就不管;等的时候点了「停」就收尾。"""
        if not self._unattended:
            return
        if self._chain_stop:
            self._sched_finish("你点了「停」,定时发布停下了")
            return
        self.start_batch(chained=True)

    def _sched_finish(self, why: str = ""):
        """定时发布结束:why 空 = 都弄完了;有 why = 中途停下了(写清楚停在哪、还剩多少,别说「电脑可以关了」)。
        写总结,恢复让电脑睡。"""
        from gui.schedule import keep_awake
        self._edu_spill()                              # 发够规定条数的号:还没发的挪到明天(按定时定到的那天算)
        rest = self._todo() if why else []             # 本来要摆、还没摆的(要在 _unattended 关掉之前算:标黄 / 跳过的不算)
        self._unattended = False
        keep_awake("定时-edu-发", False)
        self._sched_changed()
        n = sum(1 for v in self.videos if self.rec.status_of(v.path) == "已发") - getattr(self, "_sched_n0", 0)
        left = [v for v in self.videos if not self.rec.status_of(v.path)]
        skipped = [v for v in left if v.path in self._sched_skip]
        warn = [v for v in left if v.warn and v.path not in self._sched_skip]
        at = getattr(self, "_sched_at", "")
        if not why:
            text = ("定时发布都定好了" if at else "定时发布发完了") + (
                f"\n\n这次定好了 {n} 条,{at}(北京时间)企鹅号自己发,电脑可以关了。" if at else f"\n\n这次发了 {n} 条。")
        else:                                          # 中途停下(审查 B7):别说「可以关了」
            text = why + (f"\n\n停在这里:已经定好 {n} 条({at} 北京时间企鹅号自己发)" if at else f"\n\n停在这里:已经发了 {n} 条")
            if rest:
                text += (f",还有 {len(rest)} 条没{'定' if at else '发'}(比如「{rest[0].title[:24]}」),它们不会自己发。\n"
                         "要发就再点「摆好并定时发出…」(定好的不会重摆)。")
            else:
                text += "。" + ("没有剩下要定的了。" if not self.batch_id else "")
        rest_ids = {v.path for v in rest}
        if skipped:
            text += f"\n没摆好、跳过没发的 {len(skipped)} 条:" + "".join(f"\n · {v.title[:26]}" for v in skipped[:8]) + ("\n · …" if len(skipped) > 8 else "")
        if warn:
            text += f"\n封面标黄没发的 {len(warn)} 条(先在「预览封面」里看一眼):" + "".join(f"\n · {v.title[:26]}" for v in warn[:5])
        other = [v for v in left if v not in skipped and v not in warn and v.path not in rest_ids]
        if other:
            text += f"\n\n另外 {len(other)} 条本来就不发(没无字封面 / 同名 / 查到水印 …)。"
        self.say("⏰ " + text.replace("\n", " "))
        self._sched_skip, self._sched_at = set(), ""
        self._refresh_buttons()
        QMessageBox.information(self, "定时发布", text)

    def batch_sent(self):
        if not self.batch_id:
            return
        n_ready = self.rec.ready_in_batch(self.batch_id)
        acc = self.batch_videos[0].account if self.batch_videos else ""
        if not self._ask("这批发好了", f"「{acc}」这批 {n_ready} 条,你已经在罐头里点了「发布 → 全部发布」,都发出去了?\n\n"
                                       "点「都发了,记下」以后这批算发出去了,软件不会再摆这批。还没发就点「还没」。",
                         "都发了,记下", "还没", default_no=True):
            return
        n = self.rec.mark_batch_published(self.batch_id)
        self._yellow_stop = False
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
        self._yellow_stop = False
        self.say(f"这批 {n} 条作废了")
        self.batch_id = ""
        self._after_batch()

    def _after_batch(self):
        for v in self.batch_videos:                   # 这批确认完了:临时状态清掉(没摆成的原因在记录里)
            self.row_note.pop(v.path, None)
        self._edu_spill()                             # 发够规定条数的号:还没发的挪到明天
        for i in range(len(self.videos)):
            self._fill_row(i)
        self._update_sum()
        self._update_tree_counts()
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
                left += [v for v in F.scan_account(d, acc, date) if self.rec.status_of(v.path) != "已发"]
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
        dates = sorted({r["date"] for r in self.rec.rows()}, key=_dk, reverse=True)    # 和另外两页一样:最新的在上面
        self.c_rec_date.blockSignals(True)
        self.c_rec_date.clear()
        self.c_rec_date.addItem("全部", "")
        for d in dates:
            self.c_rec_date.addItem(d, d)
        i = self.c_rec_date.findData(cur) if cur is not None else -1
        self.c_rec_date.setCurrentIndex(i if i >= 0 else (1 if dates else 0))   # 默认最新的一天
        self.c_rec_date.blockSignals(False)
        date = self.c_rec_date.currentData() or ""
        s = self.rec.summary(date)
        tot = {k: sum(int(x[k] or 0) for x in s) for k in ("sent", "failed", "unsure", "ready")}
        self.rec_cards.set(sent=(tot["sent"], "good" if tot["sent"] else ""), fail=(tot["failed"], "warn" if tot["failed"] else ""),
                           unsure=(tot["unsure"], "warn" if tot["unsure"] else ""), ready=tot["ready"],
                           sent_sub="" if date else "全部日期")
        self.t_sum.setRowCount(len(s))
        def short(t):                              # 「2026-10-15 18:42:45」→「10.15 18:42:45」(审查:时分秒被截掉了;21:日期统一写 10.15)
            s = str(t or "")
            if s[:2] == "20" and len(s) >= 10 and s[4] == "-" and s[7] == "-":
                return f"{int(s[5:7])}.{int(s[8:10])}{s[10:]}"
            return s
        for i, x in enumerate(s):
            for c, k in enumerate(["date", "account", "employee", "sent", "ready", "failed", "unsure", "first_at", "last_at"]):
                val = x[k] if x[k] is not None else ""
                self.t_sum.setItem(i, c, QTableWidgetItem(short(val) if k.endswith("_at") else str(val)))
        rows = self.rec.rows(date)
        if self.k_rec_bad.isChecked():
            sent = {r.get("pkey") for r in rows if r["status"] == "已发"}
            rows = [r for r in rows if r["status"] in ("结果不明", "发布中", "摆好")
                    or (r["status"] == "没发成" and r.get("pkey") not in sent)]
        self._rec_rows = rows
        self.rec_empty.setText("" if rows else
                               ("还没有记录。在「教育号」摆好、点了「这批发好了」,或者在「16 个号」发了以后,这里会一条条记下来。"
                                if not dates else f"{date} 这天没有记录,上面换个日期看看(或者选「全部」)。"))
        self.rec_empty.setVisible(not rows)
        self.t_rec.setRowCount(len(rows))
        for i, x in enumerate(rows):
            for c, k in enumerate(["date", "account", "employee", "title", "status", "prepared_at", "published_at", "note"]):
                val = short(x[k]) if k.endswith("_at") else str(x[k] or "")
                if k == "status":
                    val = {"摆好": READY, "结果不明": "不确定发没发", "发布中": "不确定发没发"}.get(val, val)
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
                        item.setBackground(RED if x["status"] == "没发成" else YELLOW)
        for c in (0, 1, 2, 5, 6):
            self.t_rec.resizeColumnToContents(c)
        self.t_rec.setColumnWidth(0, max(64, self.t_rec.columnWidth(0)))
        self.t_rec.setColumnWidth(4, 130)                 # 状态胶囊要的宽度(按字算会太窄,画成「…」)
        self._rec_sel()
        self.t_sum.resizeColumnsToContents()
        self.t_sum.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh = self.t_sum.horizontalHeader().sizeHint().height()       # 有几行就多高,不空一大块(草图 ④)
        self.t_sum.setFixedHeight(min(240, hh + max(1, self.t_sum.rowCount()) * 34 + 4))
        for i in range(self.t_sum.rowCount()):
            it = self.t_sum.item(i, 2)
            if it and it.text() == "接口":
                it.setText("16 个号")

    def _rec_cur(self) -> dict | None:
        rows = sorted({ix.row() for ix in self.t_rec.selectedIndexes()})
        recs = getattr(self, "_rec_rows", [])
        return recs[rows[0]] if rows and rows[0] < len(recs) else None

    def _rec_sel(self):
        """审查 23:选中一条没发成 / 不确定发没发的,下面的「重试 / 标成已发」才亮。"""
        r = self._rec_cur()
        now = self.rec.status_of(r["path"]) if r else ""
        bad = bool(r) and r["status"] in ("没发成", "结果不明", "发布中") and now != "已发"
        unsure = bad and now == "结果不明"
        api = bool(r) and r["employee"] == "接口"
        if not r:
            txt = "点一条「没发成 / 不确定发没发」的(红的),这里能重试或者标成已发"
        elif r["status"] in ("没发成", "结果不明", "发布中") and now == "已发":
            txt = f"「{r['title'][:24]}」后来发成了,不用管"
        elif unsure:
            txt = f"「{r['title'][:24]}」不确定发没发:先去企鹅号后台看一眼,再点下面的"
        elif bad:
            txt = f"「{r['title'][:24]}」没发成:{(r['note'] or '')[:40]}"
        else:
            txt = ""
        self.lab_rec_sel.setText(txt)
        self.b_rec_retry.setVisible(api and bad and not unsure)
        self.b_rec_sent.setVisible(bad)
        self.b_rec_unsent.setVisible(unsure)

    def rec_mark(self, sent: bool):
        r = self._rec_cur()
        if not r:
            return
        if self.api_tab.busy() and not getattr(self.api_tab, "_quiet", False):
            QMessageBox.information(self, "数据记录", "16 个号那边正在发,发完再改。")
            return
        what = "标成已发" if sent else "标成没发出去"
        if not self._ask(what, f"「{r['title'][:40]}」\n\n" + ("你去企鹅号后台看了,这条其实发出去了?记成已发以后软件不会再发它。" if sent else
                                                         "你去企鹅号后台看了,这条没发出去?记成没发成,之后能在「16 个号」页再发。"),
                         what, "先不"):
            return
        if self.rec.status_of(r["path"]) == "结果不明":
            self.rec.resolve_unsure(r["path"], sent)
        elif sent:
            self.rec.mark_sent(r["id"])
        self.say(f"数据记录:「{r['title'][:30]}」{what}")
        if not self.api_tab.busy():
            self.api_tab.load()                       # 16 个号页的状态跟着变
        self.refresh_records()

    def rec_retry(self):
        """跳到 16 个号页、选好这天和这一条;发不发还是人点「现在发布 / 再发一次没发成的」(这里不发)。"""
        r = self._rec_cur()
        if not r:
            return
        tab = self.api_tab
        if tab.busy() and not getattr(tab, "_quiet", False):
            QMessageBox.information(self, "重试", "16 个号那边正在发 / 处理别的,弄完再重试。")
            return
        self.stack.setCurrentWidget(tab)
        if tab.day() != r["date"] and not tab.set_day(r["date"]):
            QMessageBox.information(self, "重试", f"16 个号页里没有「{r['date']}」这天了(素材挪走了?)。")
            return
        from qe.records import pkey
        k = pkey(r["path"])
        i = next((j for j, v in enumerate(tab.videos) if pkey(v.path) == k), None)
        if i is None or i not in tab.items:
            QMessageBox.information(self, "重试", f"「{r['date']}」里找不到这条了(文件被改名 / 挪走了?):\n{r['title']}")
            return
        tab.k_bad.setChecked(False)
        tab.e_find.clear()
        it = tab.items[i]
        tab.tree.clearSelection()
        if it.parent():
            it.parent().setExpanded(True)
        it.setSelected(True)
        tab.tree.setCurrentItem(it)
        tab.tree.scrollToItem(it)
        tab.say(f"从数据记录跳过来:选中了「{r['title'][:30]}」,要再发就点下面的「再发一次没发成的」")

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
        d.resize(860, 680)
        avail = self.screen().availableGeometry().height() if self.screen() else 900
        d.setMaximumHeight(max(480, avail - 60))
        dv = QVBoxLayout(d)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)   # 设计师试用:右边被切、多一条横滚动条
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
            e.setMinimumWidth(260)
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

        def tpl_row(text: str, default: str):
            """审查 19:「发完挪到」里的 {month} / {date} 容易被改坏(真填成过 …\\教育\\10.15)→ 只让改前面那段(盘 + 文件夹),
            带 {month} 的后半截灰字不能改。原来的已经坏了(没有 { })就换回默认的后半截,红字说一声。返回 (控件, 前半截框, 取完整路径)。"""
            def split(t):
                i = t.find("{")
                j = max(t.rfind("\\", 0, i), t.rfind("/", 0, i)) if i >= 0 else -1
                return (t[:j], t[j + 1:]) if j >= 0 else ("", t)
            pre, suf = split(text)
            broken = "{" not in text
            if broken:
                pre, suf = split(default)
            w0 = QWidget()
            vv = QVBoxLayout(w0)
            vv.setContentsMargins(0, 0, 0, 0)
            w1, e1 = path_row(pre)
            lab = QLabel("后面自动接上:\\" + suf)              # 放到框下面(原来夹在框和「选…」中间,把窗口撑出去了)
            lab.setObjectName("muted")
            lab.setWordWrap(True)
            lab.setToolTip("这半截是按月份 / 日期自动换的({month} = 月份,{date} = 日期),不能改")
            vv.addWidget(w1)
            vv.addWidget(lab)
            if broken:
                warn = QLabel(f"原来填的「{text}」里没有 {{month}},每个月都会挪到同一个地方 —— 已经换回按月份的,点「确定」才存")
                warn.setObjectName("warnText")
                warn.setWordWrap(True)
                vv.addWidget(warn)
            return w0, e1, lambda: (os.path.join(e1.text().strip().rstrip("\\/") + "\\", suf) if e1.text().strip() else "")

        def note(text: str) -> QLabel:
            x = QLabel(text)
            x.setObjectName("muted")
            x.setWordWrap(True)
            return x

        g1 = QGroupBox("教育号(在创作罐头里摆,人点发布)")
        f = QFormLayout(g1)
        w_root, e_root = path_row(self.st["material_root"])
        from qe.config import DEFAULTS
        w_arc, e_arc, arc_get = tpl_row(self.st["archive_root"], DEFAULTS["archive_root"])
        e_acc = QPlainTextEdit("\n".join(f"{a['name']}={'、'.join(a.get('aliases') or [])}" for a in self.st["accounts"]))
        e_acc.setToolTip("一行一个号:罐头里的号名=日期文件夹下面的缩写(几个用顿号隔开)")
        e_acc.setMaximumHeight(70)
        sp = QSpinBox()
        sp.setRange(1, 10)
        sp.setValue(int(self.st.get("batch_size", 10)))
        f.addRow("素材文件夹", w_root)
        f.addRow("一天发完挪到", w_arc)
        prev = QLabel("")
        prev.setObjectName("muted")
        prev.setWordWrap(True)

        def show_prev():
            prev.setText("比如 10.15 那天的会挪到:" + os.path.join(arc_get().replace("{month}", "10"), "10.15"))
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
        sp_per = QSpinBox()
        sp_per.setRange(1, 5)
        sp_per.setSuffix(" 条")
        sp_per.setValue(max(1, min(5, _num(self.st.get("api_per_acc"), 1))))
        sp_per.setToolTip("一个号一次同时传几条:1 = 一条一条发(原来的样子)。\n"
                          "只剩一个号在发的时候特别慢(每分钟 2 条左右),设成 3 能快一倍多;3 条以上网差不多就满了。\n"
                          "一组同时传,这组都发完歇「每条间隔」秒再下一组;所有号加起来同时最多传 6 条。\n"
                          "平台要是报「太频繁」之类的没发成,就改回 1(没发成的点「再发一次没发成的」补发)。")
        sp_gap = QSpinBox()
        sp_gap.setRange(0, 600)
        sp_gap.setSuffix(" 秒")
        sp_gap.setValue(_num(self.st.get("api_interval"), 5))
        w_api, e_api_arc, api_get = tpl_row(self.st.get("api_archive", "") or DEFAULTS["api_archive"], DEFAULTS["api_archive"])
        k_game = QCheckBox("按游戏放进子文件夹(CSGO、DNF、光与夜之恋 …)")
        k_game.setChecked(bool(self.st.get("api_archive_by_game", True)))
        f2.addRow("发成了挪到", w_api)
        f2.addRow("", k_game)
        from qe import apicover
        c_cov = QComboBox()
        for m in apicover.CHOICES:
            c_cov.addItem({"原样": "原样(文件夹里什么样就传什么样)", "不传": "不传(平台自己截一帧)"}.get(m, f"裁成 {m}"), m)
        c_cov.setCurrentIndex(max(0, c_cov.findData(self.st.get("api_cover", "原样"))))
        f2.addRow("封面(视频旁边的同名图)", c_cov)
        f2.addRow("", note("传封面要开着创作罐头(用它登录着的企鹅号传图);没有同名图的、传不上的,平台自己截一帧"))
        f2.addRow("几个号一起发", sp_thr)
        f2.addRow("同一个号一次传几条", sp_per)
        from PySide6.QtWidgets import QCheckBox as _QCB
        k_gate = _QCB("开闸:允许超过每天规定条数(教育号、16 个号都管)")
        k_gate.setChecked(bool(self.st.get("quota_open", False)))
        k_gate.setToolTip("关着(默认):每个号每天最多发到规定条数(每日汇总里那张表),发够了这个号就停,还没发的挪到明天的文件夹;\n"
                          "没发成的会拿下一条补,不会少发。\n打开:不管规定条数,能发的都发(小心发多了)。")
        f2.addRow("每天规定条数", k_gate)
        from qe import gamecheck as GC
        e_games = QPlainTextEdit("\n".join(f"{g}={'、'.join(ks)}" for g, ks in GC.words().items()))
        e_games.setMaximumHeight(110)
        e_games.setToolTip("每行一个游戏:游戏名=关键词、关键词…(英文不分大小写)。\n"
                           "游戏号的视频标题里有别的游戏的词、又没有自己游戏的词 → 标「标题像是《某游戏》的」,不发;\n"
                           "一个号这天有 3 条以上(或超过一成)这样的 → 整批先不发。关键词看不出来的检查时问 AI。")
        f2.addRow("游戏关键词", e_games)
        f2.addRow("每条间隔", sp_gap)
        f2.addRow("", note("1 = 一个号一个号地发,最稳;间隔 = 上一条发完歇几秒再发下一条"))
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
        for n, t in TH.THEMES.items():
            c_theme.addItem(f"{n} —— {t['desc']}", n)
        c_theme.setCurrentIndex(max(0, c_theme.findData(self.st.get("theme", ""))))
        f4.addRow("界面颜色", c_theme)
        from PySide6.QtWidgets import QCheckBox
        k_splash = QCheckBox("打开软件时放「Hi,欢迎使用本工作台」开场动画")
        k_splash.setChecked(bool(self.st.get("splash", True)))
        f4.addRow("", k_splash)
        outer.addWidget(g4)
        g3 = QGroupBox("AI(两边共用)")
        f3 = QFormLayout(g3)
        e_key = QLineEdit(self.st.get("ai_key", ""))
        e_key.setEchoMode(QLineEdit.EchoMode.Password)
        e_key.setPlaceholderText("空着就用百家号发布助手里填的" + ("(找到了)" if self.st.ai_key() else "(没找到)"))
        f3.addRow("阿里百炼 Key", e_key)
        f3.addRow("", note("教育:大头照的 2.35:1 封面 AI 扩图;接口:「整理话题」里挂好几个话题的让 AI 挑一个"))
        outer.addWidget(g3)
        labs = [fl.itemAt(r, QFormLayout.ItemRole.LabelRole).widget() for fl in (f, f2, f4, f3) for r in range(fl.rowCount())
                if fl.itemAt(r, QFormLayout.ItemRole.LabelRole) and fl.itemAt(r, QFormLayout.ItemRole.LabelRole).widget()]
        lw = max((x.sizeHint().width() for x in labs), default=0)
        for x in labs:                                   # 四组的左边标签一样宽:输入框左边对齐(设计师试用)
            x.setMinimumWidth(lw)
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
                       archive_root=arc_get() or self.st["archive_root"], accounts=accs or self.st["accounts"],
                       batch_size=sp.value(), ai_key=e_key.text().strip(),
                       api_threads=sp_thr.value(), api_per_acc=sp_per.value(), quota_open=k_gate.isChecked(),
                       game_words={ln.split("=", 1)[0].strip(): [x.strip() for x in ln.split("=", 1)[1].replace(",", "、").replace("，", "、").split("、") if x.strip()]
                                   for ln in e_games.toPlainText().splitlines() if "=" in ln and ln.split("=", 1)[0].strip()}, api_interval=sp_gap.value(), api_cover=c_cov.currentData() or "原样",
                       api_archive=api_get() or self.st.get("api_archive", ""),
                       api_archive_by_game=k_game.isChecked(), theme=c_theme.currentData() or TH.DEFAULT,
                       splash=k_splash.isChecked())
        C.AI_KEY = self.st.ai_key()
        self.st.save()
        from PySide6.QtWidgets import QApplication
        TH.apply(QApplication.instance(), self.st["theme"])
        from gui.widgets import retheme_shell
        retheme_shell(self)                              # 换颜色当场生效(原来要关掉重开,设计师 / 买家试用)
        if hasattr(self, "today"):
            self.today.retheme()
        from qe import gamecheck as GC2
        GC2.configure(self.st)
        self.api_tab._update_sum()
        self._load_dates()

    def closeEvent(self, e):
        pend = [s.label() for s in (self.api_tab.sched,) if s.pending()]
        if (pend or self._unattended or self.api_tab._auto) and not self._ask(
                "企鹅号发布助手", ("定着时间还没到:\n" + "\n".join(pend) if pend else "定时发布正在自己发。") +
                "\n\n关了软件就不会自己发了。真要关吗?", "关掉", "不关", default_no=True):
            e.ignore()
            return
        for wk in (self.wm_worker, self.blur_worker):
            if wk and wk.isRunning():
                wk.stop = True
                wk.wait(60000)
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
