"""不连罐头的测试:找日期 / 员工 / 视频、认封面、裁剪框算多远、记录、挪文件夹、界面能打开、绝不点发布。
    PYTHONIOENCODING=utf-8 python tests/test_basic.py
"""
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QE_DATA_DIR", tempfile.mkdtemp(prefix="qe_data_"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

fails = []


def check(c, m):
    print(("  OK   " if c else "  FAIL ") + m)
    if not c:
        fails.append(m)


def _img(path, w, h):
    from PIL import Image
    Image.new("RGB", (w, h), (200, 200, 200)).save(path)


def test_folders(tmp: Path):
    print("[素材文件夹]")
    from qe import folders as F
    from qe.config import Settings
    st = Settings(tmp / "s.json")
    root = tmp / "小学生教育"
    st["material_root"] = str(root)
    st["archive_root"] = str(tmp / "内容查看" / "{month}月发布视频" / "企鹅号" / "教育")
    for p in ("10.15/研习空间/31条", "10.15/研习空间/51", "10.15/小天地/51", "10.14/研习社/卓13", "10.15/不认识/甲", "9.30/小天地/乙"):
        (root / p).mkdir(parents=True)
    e = root / "10.15/研习空间/31条"
    for n in ("b.第二条", "a.第一条"):
        for ext in (".mp4", ".png", ".jpg"):
            (e / f"{n}{ext}").write_bytes(b"x")
    (e / "只有视频.mp4").write_bytes(b"x")
    (e / "多余的图.png").write_bytes(b"x")
    check(F.list_dates(str(root)) == ["9.30", "10.14", "10.15"], f"日期按日子排 -> {F.list_dates(str(root))}")
    ad = F.account_dirs(str(root), "10.15", st)
    check([os.path.basename(x) for x in ad["家长研习空间"]] == ["研习空间"] and [os.path.basename(x) for x in ad["家长小天地"]] == ["小天地"], "缩写认号")
    check([os.path.basename(x) for x in F.account_dirs(str(root), "10.14", st)["家长研习空间"]] == ["研习社"], "10.14 叫研习社也认")
    check(F.unknown_dirs(str(root), "10.15", st) == ["不认识"], "不认识的缩写挑出来提醒")
    vs = F.videos_in(str(e), "家长研习空间", "10.15")
    check([v.title for v in vs] == ["a.第一条", "b.第二条", "只有视频"], f"视频按文件名排,图片不算视频 -> {[v.title for v in vs]}")
    check(vs[0].png.endswith("a.第一条.png") and vs[0].jpg.endswith("a.第一条.jpg") and not vs[2].png, "同名的横 / 竖封面配上")
    check(vs[0].employee == "31条" and vs[0].date == "10.15", "员工 = 员工文件夹名")
    dst = F.archive_target(st, "10.15")
    check(dst.endswith(os.path.join("10月发布视频", "企鹅号", "教育", "10.15")), f"挪到 10月发布视频 -> {dst}")
    F.move_date(st, "10.15")
    check(not (root / "10.15").exists() and (Path(dst) / "研习空间" / "31条" / "a.第一条.mp4").is_file(), "整天剪切过去")
    (root / "10.15/研习空间/31条").mkdir(parents=True)
    (root / "10.15/研习空间/31条/a.第一条.mp4").write_bytes(b"y")
    try:
        F.move_date(st, "10.15")
        check(False, "那边已经有了要先问")
    except FileExistsError:
        check(True, "那边已经有同名日期:先问人(抛 FileExistsError)")
    F.move_date(st, "10.15", merge=True)
    check((Path(dst) / "研习空间/31条/a.第一条 (2).mp4").is_file() and not (root / "10.15").exists(), "合并:同名不覆盖,改名 (2)")


def test_cover(tmp: Path):
    print("[封面]")
    from qe import cover as C
    from qe.folders import Video
    # 实测:画布 (393,167,677,342),图 2848×1600,3:4 框默认在 603~860
    cv = {"left": 393, "top": 167, "width": 677, "height": 342}
    x0, y0, x1, y1 = C.box_drag(cv, 2848, 1600, 0.75, {})
    check(abs(x0 - 731.6) < 2 and x0 == x1, f"不用拖:起点 = 框中间 -> {x0:.1f}")
    x0, y0, x1, y1 = C.box_drag(cv, 2848, 1600, 0.75, {"cx": 0.684, "cy": 0.4})
    want = 427.1 + 0.684 * 608.8 - 128.25 - 603.3
    check(abs((x1 - x0) - want) < 2 and abs(y1 - y0) < 1, f"3:4 往右拖到人中间 -> {x1 - x0:.1f}(应 {want:.1f})")
    x0, y0, x1, y1 = C.box_drag(cv, 2848, 1600, 9 / 16, {"cx": 0.98, "cy": 0.4})
    check(abs(x1 - (427.1 + 608.8 - 96.2)) < 2, f"人在最边上:框只拖到图边为止 -> {x1:.1f}")
    x0, y0, x1, y1 = C.box_drag(cv, 2848, 1600, 2.35, {"cx": 0.5, "cy": 0.2})
    check(abs(x1 - x0) < 1 and y1 < y0, "2.35:1 框和图一样宽:只上下挪")
    check(C.ratio_of("3:4") == 0.75 and C.ratio_of("2.35:1") == 2.35 and C.ratio_of("") == 1.0, "比例字样认得")
    real = r"X:\知乎视频\小学生教育\10.15\研习空间\31条"
    if os.path.isdir(real):
        def mk(stem):
            return Video(path=os.path.join(real, stem + ".mp4"), title=stem, account="家长研习空间", employee="31条", date="10.15",
                         png=os.path.join(real, stem + ".png"), jpg=os.path.join(real, stem + ".jpg"))
        v = mk("七条同学交往准则，帮助小学生建立良好校园人际关系")
        C.decide(v)
        check(v.cover_kind == "横" and 0.6 < v.plan.get("cx", 0) < 0.75 and not v.warn, f"一个人在右边:横封面,框对准他 -> {v.cover_why} {v.plan.get('cx')}")
        v = mk("三款每日十分钟亲子小游戏，帮助提升儿童注意力水平")
        C.decide(v)
        check(v.cover.endswith(".png") and v.warn and "脸最大" in v.cover_why, f"三个小孩分得开:还是用 png(jpg 有字),框对准脸最大的,标黄 -> {v.cover_why}")
        v = mk("十种添加剂含量较高零食，建议家长减少给孩子食用")
        C.decide(v)
        check(v.cover_kind == "横" and not v.warn and 0.45 < v.plan.get("cx", 0) < 0.7, f"没人(零食):横封面,框对准零食堆 -> {v.cover_why} {v.plan}")
        g = mk("五款辅助写作业工具，帮助改善孩子写作业专注力问题")
        C.decide(g)
        check(g.plan.get("cx", 0) > 0.58, f"背影写作业的小孩(认不出脸):框对准小孩那边 -> {g.plan.get('cx')}")
    else:
        print("  (网络盘上没有真封面,跳过)")
    v = Video(path="x.mp4", title="x", account="a", employee="e", date="d")
    C.decide(v)
    check(v.warn and not v.cover, "一张封面都没有:标黄")
    v = Video(path="x.mp4", title="x", account="a", employee="e", date="d", jpg="x.jpg")
    C.decide(v)
    check(v.warn and not v.cover and "jpg 有字" in v.cover_why, f"只有 jpg:不用(有字),标黄 -> {v.cover_why}")


def test_records(tmp: Path):
    print("[记录]")
    import openpyxl
    from qe.folders import Video
    from qe.records import Records
    r = Records(tmp / "r.sqlite")
    a = Video(path="p1", title="一", account="家长研习空间", employee="31条", date="10.15", cover_kind="横")
    b = Video(path="p2", title="二", account="家长研习空间", employee="31条", date="10.15", cover_kind="竖")
    c = Video(path="p3", title="三", account="家长研习空间", employee="51", date="10.15")
    r.prepared(a, "B1")
    r.prepared(b, "B1")
    r.failed(c, "B1", "封面没设上")
    check(r.status_of("p1") == "摆好" and r.status_of("p3") == "", "摆好 / 没摆成(没摆成的下次还摆)")
    check(r.open_batches()[0]["n"] == 2, "有一批等确认")
    check(r.mark_batch_published("B1") == 2 and r.status_of("p2") == "已发", "这批发好了:记已发")
    check(all(x["published_at"].startswith("20") for x in r.rows("10.15")), "记了发布时间")
    s = r.summary("10.15")
    check(len(s) == 1 and s[0]["employee"] == "31条" and s[0]["sent"] == 2, f"按员工数 -> {s}")
    r.prepared(c, "B2")
    check(r.drop_batch("B2") == 1 and r.status_of("p3") == "", "这批不要了:作废,下次还摆")
    out = tmp / "记录.xlsx"
    r.export_xlsx(str(out))
    wb = openpyxl.load_workbook(out)
    check(wb.sheetnames == ["明细", "按员工汇总"] and wb["明细"].max_row == 3, "导出 Excel")


def test_bj_time():
    print("[北京时间]")
    import datetime as dt
    from qe.config import bj_now
    check(bj_now().utcoffset() == dt.timedelta(hours=8), "记录时间按北京时间(不管电脑时区)")


def test_guard():
    print("[不点发布]")
    from qe.prepare import PrepError, _guard
    for t in ("发布", "定时发布", "存草稿", "全部发布", "单条发布"):
        try:
            _guard(t)
            check(False, f"「{t}」应该拒绝")
        except PrepError:
            pass
    check(True, "发布 / 定时发布 / 存草稿 / 全部发布 / 单条发布 一律不点")
    for t in ("下一步", "完成", "确认", "本地上传", "添加内容自主声明"):
        _guard(t)
    check(True, "下一步 / 完成 / 确认 这些能点")
    src = (Path(__file__).resolve().parent.parent / "qe" / "prepare.py").read_text("utf-8")
    hits = [m for m in re.findall(r"click_text\(\"([^\"]+)\"", src) if re.search("发布|定时|存草稿", m)]
    check(not hits, f"代码里没有去点发布的地方 -> {hits}")


def test_window(tmp: Path):
    print("[界面]")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from gui.window import MainWindow
    from qe.config import Settings
    from qe.records import Records
    app = QApplication.instance() or QApplication([])
    root = tmp / "素材"
    e = root / "10.16" / "研习空间" / "张三"
    e.mkdir(parents=True)
    (root / "10.17").mkdir()
    for i in range(12):
        (e / f"{i:02d}.第{i}条视频标题够长.mp4").write_bytes(b"x")
        _img(e / f"{i:02d}.第{i}条视频标题够长.png", 640, 360)
        _img(e / f"{i:02d}.第{i}条视频标题够长.jpg", 270, 480)
    st = Settings(tmp / "sw.json")
    st["material_root"] = str(root)
    w = MainWindow(st, Records(tmp / "rw.sqlite"))
    check(w.c_date.currentData() == "" and w.c_date.count() == 3, "打开时不自动选日期,要人选")
    w.c_date.setCurrentIndex(w.c_date.findData("10.16"))
    top = w.tree.topLevelItem(0)
    check(top.text(0) == "家长研习空间" and top.childCount() == 1 and top.child(0).text(1) == "12 条", "左边:号下面员工,写着几条")
    top.child(0).setCheckState(0, Qt.CheckState.Checked)
    t0 = time.time()
    while (w.cover_worker and w.cover_worker.isRunning()) and time.time() - t0 < 30:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    check(w.table.rowCount() == 12, "勾上员工:中间列出 12 条")
    check(all(v.cover_kind for v in w.videos), "每条都定了封面")
    acc, vids = w.next_batch()
    check(acc == "家长研习空间" and len(vids) == 10, f"一批最多 10 条 -> {len(vids)}")
    w.rec.prepared(vids[0], "X")
    w.rec.mark_batch_published("X")
    acc, vids2 = w.next_batch()
    check(vids2[0].title != vids[0].title and len(vids2) == 10, "发过的下一批不再拿")
    w.close()


def test_title_zone(tmp: Path):
    print("[2.35:1 标题区不挡脸]")
    from qe import cover as C
    # 一张 1600×900 的图,2.35:1 框高 = 1600/2.35 ≈ 681,能上下挪 219
    small = {"cx": 0.5, "cy": 0.4, "faces": [[0.45, 0.25, 0.1, 0.18]]}        # 小脸在中间偏上
    ok, ty = C.title_fit(1600, 900, small)
    x, y, w, h = C.crop_rect(1600, 900, 2.35, small)
    check(ok and y == ty and (0.25 + 0.18 * 1.03) * 900 <= y + h * C.TITLE_SAFE, "小脸:挪框就能让脸在标题区上面")
    low = {"cx": 0.5, "cy": 0.7, "faces": [[0.45, 0.55, 0.1, 0.15]]}          # 脸偏下:框挪到底
    ok, ty = C.title_fit(1600, 900, low)
    check(ok and abs(ty - (900 - 1600 / 2.35)) < 1, f"脸偏下:框挪到最底下 -> {ty:.0f}")
    # 大头照(像今天 16 号):挪框躲不开 → 切掉一点头顶(办法一)
    big = {"cx": 0.5, "cy": 0.6, "faces": [[0.38, 0.15, 0.26, 0.63, 0.40]]}
    mode, ty = C.wide_mode(1600, 900, big)
    check(mode == "crop" and ty > 0, f"大头照:切掉一点头顶 -> {mode}")
    x, y, w, h = C.crop_rect(1600, 900, 2.35, big)
    chin = (0.15 + 0.63 * 1.03) * 900
    check(y + h * C.TITLE_TEXT >= chin - 1 and y <= (0.40 - 0.63 * 0.22) * 900, "切完:下巴不碰标题字,眼睛眉毛都在")
    # 脸在图最下面:切头顶也躲不开 → AI 扩图(办法三)
    low2 = {"cx": 0.5, "cy": 0.9, "faces": [[0.4, 0.7, 0.12, 0.25, 0.8]]}
    check(C.wide_mode(1600, 900, low2)[0] == "ai" and C.needs_wide(1600, 900, low2), "脸贴着图片底下:要 AI 扩图")
    check(C.wide_mode(1600, 900, dict(low2, no_ai=True))[0] == "crop", "人点了「不用 AI」:改成切头顶")
    check(C.wide_mode(1600, 900, dict(big, ai235=True))[0] == "ai", "人点了「用 AI 扩」:就用 AI")
    check(C.wide_mode(1600, 900, dict(big, manual={C.rkey(2.35): [0.5, 0.5]}))[0] == "manual", "人手动拖过 2.35:1:按人的来")
    check(C.wide_mode(1600, 900, {"cx": 0.5, "cy": 0.5})[0] == "none", "没人:不管标题区")
    # AI 画布:脸落在标题区上面,原图该往上推就往上推
    import numpy as np
    img = np.zeros((900, 1600, 3), np.uint8)
    canvas, (left, up, w2, h2, src0) = C.ai_canvas(img, low2)
    H2, W2 = canvas.shape[:2]
    check(abs(W2 / H2 - 2.35) < 0.01, f"AI 画布就是 2.35:1 -> {W2}×{H2}")
    check(up == 0 and src0 > 0 and h2 < 900 * 1424 / 1600, "脸在最底下:原图往上推(上面切掉一块),下面空出来给 AI 补")
    old_key = C.AI_KEY
    C.AI_KEY = ""
    _img(tmp / "big.png", 1600, 900)
    try:
        C.wide_cover(str(tmp / "big.png"), low2)
        check(False, "没填 Key 要说清楚")
    except RuntimeError as e:
        check("Key" in str(e), f"没填阿里百炼 Key:说清楚 -> {e}")
    C.AI_KEY = old_key


def test_preview(tmp: Path):
    print("[封面预览 / 手动拖框]")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from gui.cover_dialog import CoverDialog
    from qe import cover as C
    from qe.adjust import Adjustments
    from qe.folders import Video
    app = QApplication.instance() or QApplication([])
    d = tmp / "pv"
    d.mkdir()
    _img(d / "a.png", 1600, 900)
    _img(d / "a.jpg", 720, 1280)
    (d / "a.mp4").write_bytes(b"x")
    # crop_rect:手动的 > 自动的 > 正中
    check(C.crop_rect(1600, 900, 0.75, {}) == (462.5, 0.0, 675.0, 900.0), "3:4 框:图那么高,放正中")
    x, y, w, h = C.crop_rect(1600, 900, 0.75, {"cx": 0.9, "cy": 0.5, "manual": {C.rkey(0.75): [0.25, 0.5]}})
    check(abs((x + w / 2) / 1600 - 0.25) < 1e-6, "手动拖过的位置优先")
    x, y, w, h = C.crop_rect(1600, 900, 0.75, {"cx": 0.05, "cy": 0.5})
    check(x == 0.0, "拖到头就停在图边上")
    adj = Adjustments(tmp / "adj.json")
    v = Video(path=str(d / "a.mp4"), title="a", account="号", employee="员", date="1.1", png=str(d / "a.png"), jpg=str(d / "a.jpg"))
    C.decide(v)
    adj.apply(v)
    dlg = CoverDialog([v], 0, adj)
    dlg.resize(1100, 680)
    dlg.show()
    app.processEvents()
    cv = dlg.canvas
    before = cv.rect_img
    s, ox, oy = cv._geom()
    cx, cy = ox + (before[0] + before[2] / 2) * s, oy + (before[1] + before[3] / 2) * s
    for typ, pos in ((QMouseEvent.Type.MouseButtonPress, (cx, cy)), (QMouseEvent.Type.MouseMove, (cx + 120, cy)),
                     (QMouseEvent.Type.MouseButtonRelease, (cx + 120, cy))):
        ev = QMouseEvent(typ, QPointF(*pos), QPointF(*pos), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        {QMouseEvent.Type.MouseButtonPress: cv.mousePressEvent, QMouseEvent.Type.MouseMove: cv.mouseMoveEvent,
         QMouseEvent.Type.MouseButtonRelease: cv.mouseReleaseEvent}[typ](ev)
    app.processEvents()
    check(cv.rect_img[0] > before[0] + 50, f"在大图上拖框:框往右挪了 -> {before[0]:.0f} → {cv.rect_img[0]:.0f}")
    man = Adjustments(tmp / "adj.json").manual(v.path, v.cover)
    check(C.rkey(0.75) in man and man[C.rkey(0.75)][0] > 0.5, f"拖的位置记住了(关了软件再开还在)-> {man}")
    sx, sy, ex, ey = C.box_drag({"left": 0, "top": 0, "width": 1600, "height": 900}, 1600, 900, 0.75, v.plan)
    check(abs(ex - (man[C.rkey(0.75)][0] * 1600)) < 1, "摆的时候按拖过的位置去拖(和预览一样)")
    v2 = Video(path=v.path, title="a", account="号", employee="员", date="1.1", png=v.png, jpg=v.jpg)
    C.decide(v2)
    Adjustments(tmp / "adj.json").apply(v2)
    check(C.rkey(0.75) in v2.plan.get("manual", {}), "重新打开:拖过的位置还在")
    check(v.cover.endswith(".png") and not hasattr(dlg, "b_v"), "预览里只有 png,没有「换竖封面」")
    dlg.reset()
    check(not Adjustments(tmp / "adj.json").manual(v.path, v.cover) and "manual" not in v.plan, "恢复自动")
    dlg.close()


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="qe_test_"))
    test_folders(tmp)
    test_cover(tmp)
    test_records(tmp)
    test_bj_time()
    test_guard()
    test_window(tmp)
    test_preview(tmp)
    test_title_zone(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项:\n  - " + "\n  - ".join(fails)))
    sys.exit(1 if fails else 0)
