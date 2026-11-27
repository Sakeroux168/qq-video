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
os.environ.setdefault("QE_NO_WINFIX", "1")                 # 测试时别去恢复真罐头的窗口
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

fails = []

from qe import gamecheck as _gc                             # noqa: E402
AI_GAME_CALLS = []                                           # 这台电脑上有真的百炼 Key:测试里绝不真问 AI(花钱)


def _fake_ask_ai(own, titles, key, **k):
    AI_GAME_CALLS.append((own, list(titles)))
    return {t: ("PUBG" if "苟分" in t else "") for t in titles}


_gc.ask_ai = _fake_ask_ai
import gui.api_tab as _api_mod                               # noqa: E402
_api_mod.ApiTab.AUTO_UNSURE = False                          # 测试里不自动去企鹅号查结果不明(会拿假钥匙调真接口)
_api_mod.ApiTab.COVER_CHECK = False                          # 测试里不去看这台电脑上真开着的罐头登没登着
import gui.window as _win_mod                                # noqa: E402
_win_mod.MainWindow.AI_COVER = False                         # 测试里不让 AI 看封面(真 Key 会花钱)
_win_mod.MainWindow.BLACK_SCAN = False                       # 测试里不去读真号的封面
_win_mod.MainWindow.SHARP_CHECK = False                      # 测试里不在后台查清晰度
_api_mod.ApiTab.SHARP_CHECK = False
_REAL_ASK = _api_mod.ask                                     # 有的测试会换掉 ask():留一份真的


def check(c, m):
    print(("  OK   " if c else "  FAIL ") + m)
    if not c:
        fails.append(m)


def _img(path, w, h):
    from PIL import Image
    Path(path).parent.mkdir(parents=True, exist_ok=True)
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


def test_cover_dir(tmp: Path):
    print("[员工「梁」的放法:封面\标题\横屏16x9.png]")
    from qe import folders as F
    e = tmp / "梁"
    (e / "封面" / "湖南省科技馆_C_馆上新").mkdir(parents=True)
    (e / "封面" / "两个都有").mkdir(parents=True)
    (e / "封面" / "只有修改").mkdir(parents=True)
    (e / "封面" / "心理学视角：区分情绪，减少吼叫").mkdir(parents=True)
    for n in ("湖南省科技馆 C 馆上新", "两个都有", "只有修改", "心理学视角：区分情绪,减少吼叫"):
        (e / f"{n}.mp4").write_bytes(b"x")
        (e / f"{n}.jpg").write_bytes(b"x")
    _img(e / "封面" / "湖南省科技馆_C_馆上新" / "横屏16x9.png", 320, 180)
    _img(e / "封面" / "两个都有" / "横屏16x9.png", 320, 180)
    _img(e / "封面" / "两个都有" / "竖屏9x16.png", 180, 320)
    _img(e / "封面" / "两个都有" / "原图.png", 320, 180)
    _img(e / "封面" / "只有修改" / "原图.png", 320, 180)
    _img(e / "封面" / "只有修改" / "修改 (1).png", 320, 180)
    _img(e / "封面" / "心理学视角：区分情绪，减少吼叫" / "横屏16x9.png", 320, 180)
    vs = {v.title: v for v in F.videos_in(str(e), "号", "10.15")}
    check(vs["湖南省科技馆 C 馆上新"].png.endswith("横屏16x9.png"), "名字里空格 / 下划线对不齐也认")
    check(vs["心理学视角：区分情绪,减少吼叫"].png.endswith("横屏16x9.png"), "全角半角逗号对不齐也认")
    check(vs["两个都有"].png.endswith("横屏16x9.png") and vs["两个都有"].vpng.endswith("竖屏9x16.png"), "横屏、竖屏都认出来")
    check(vs["只有修改"].png.endswith("修改 (1).png"), "没有横屏:用「修改 (1).png」,不用原图")
    check(all("原图" not in v.png and not v.png.endswith(".jpg") for v in vs.values()), "原图、带字的 jpg 一律不用")


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
    import glob
    found = glob.glob(r"X:\知乎视频\小学生教育\10.15\研习空间\31条*")          # 用户发完会改名成「31条（已发）」
    real = found[0] if found else ""
    if real and os.path.isdir(real):
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
        liang = r"X:\知乎视频\小学生教育\10.15\研习空间\梁"
        if os.path.isdir(liang):
            from qe import folders as F
            lv = next((x for x in F.videos_in(liang, "家长研习空间", "10.15") if x.title.startswith("孩子遭遇同伴孤立")), None)
            if lv:
                C.decide(lv)
                check(lv.vcover.endswith("竖屏9x16.png") and lv.cover.endswith("横屏16x9.png") and not lv.warn,
                      f"两个人分得开、有无字竖屏:竖的比例用竖屏图 -> {lv.cover_why}")
                check(C.pick_for(lv, 0.75)[0] == lv.vcover and C.pick_for(lv, 2.35)[0] == lv.cover and C.pick_for(lv, 1.0)[0] == lv.cover,
                      "3:4 用竖图,2.35:1 / 1:1 用横图")
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


def test_failed_steps(tmp: Path):
    print("[封面没成也接着做声明 / 手动发的标成已发]")
    from qe import prepare as P
    from qe.folders import Video
    from qe.records import Records
    done = []

    class FakeRunner(P.Runner):
        def __init__(self):
            self.log, self.stopped, self.shot_dir, self.page = (lambda m: None), (lambda: False), "", None

        def open_account(self, name):
            pass

        def pending_videos(self):
            return []

        def go_create(self):
            pass

        def upload(self, vs):
            pass

        def ensure_visible(self):
            pass

        def select_tab(self, t):
            pass

        def wait_uploaded(self, t):
            pass

        def set_cover(self, v):
            done.append(("封面", v.title))
            if v.title == "坏封面":
                raise P.PrepError("企鹅号说封面图尺寸太小")

        def set_declaration(self):
            done.append(("自主声明",))

        def set_ai_declaration(self):
            done.append(("AI",))

        def shot(self, name):
            pass

        def _close_dialog(self):
            pass

    vs = [Video(path="a", title="坏封面", account="号", employee="员", date="1.1"),
          Video(path="b", title="好的", account="号", employee="员", date="1.1")]
    res = FakeRunner().prepare_batch("号", vs)
    check(done[:3] == [("封面", "坏封面"), ("自主声明",), ("AI",)], f"封面没成:自主声明、AI 补充照样做 -> {done[:3]}")
    check(not res[0][1] and "封面" in res[0][2] and "手动补" in res[0][2] and res[1][1], f"这条算没摆成,说清楚是封面 -> {res[0][2]}")
    r = Records(tmp / "rf.sqlite")
    r.prepared(vs[1], "B")
    r.failed(vs[0], "B", "封面")
    check([x["title"] for x in r.failed_in_batch("B")] == ["坏封面"], "这批里没摆成的认得出")
    check(r.mark_failed_published("B") == 1 and r.status_of("a") == "已发", "手动补好一起发了:也记成已发")
    c = Video(path="c", title="手动发的", account="号", employee="员", date="1.1")
    r.manual_published(c)
    check(r.status_of("c") == "已发" and r.rows("1.1")[-1]["published_at"], "「选中的标成已发」:记已发、有时间")


def test_api(tmp: Path):
    print("[接口发:找素材 / 话题留一个 / 平台名 / 转竖屏 / 账号加密 / 发布流程(假接口)]")
    from qe import apiacc, apisrc, checks, omapi, topic, vertical
    root = tmp / "api"
    g = root / "游戏视频"
    for d in ("CSGO--CSGO战神君/10.15(20)", "CSGO--CSGO战神君/不能用", "CSGO--CSGO战神君/10.14", "1疑似脏话/10.15",
              "地下城与勇士--DNF连招档案馆/10.15（20）"):
        (g / d).mkdir(parents=True)
    (root / "动漫视频" / "国漫趣谈" / "10.15（星期四）").mkdir(parents=True)
    for f in ("CSGO--CSGO战神君/10.15(20)/a #CSGO #反恐精英.mp4", "CSGO--CSGO战神君/10.15(20)/a #CSGO #反恐精英.jpg",
              "CSGO--CSGO战神君/不能用/坏.mp4", "1疑似脏话/10.15/脏.mp4", "地下城与勇士--DNF连招档案馆/10.15（20）/b.mp4"):
        (g / f).write_bytes(b"x")
    (root / "动漫视频" / "国漫趣谈" / "10.15（星期四）" / "抖音同款 #牧神记.mp4").write_bytes(b"x")
    roots = [str(g), str(root / "动漫视频")]
    check(apisrc.date_key("10.14（星期三）") == "10.14" and apisrc.date_key("10.15(20)") == "10.15" and apisrc.date_key("不能用") == "",
          "日期文件夹只认开头的「月.日」")
    known = {"CSGO战神君", "DNF连招档案馆", "国漫趣谈"}
    check(apisrc.dates(roots, known) == ["10.14", "10.15"], "有哪些日子")
    vs = apisrc.videos(roots, "10.15", known)
    check(sorted(v.account for v in vs) == ["CSGO战神君", "DNF连招档案馆", "国漫趣谈"], "「不能用」「1疑似脏话」不算")
    check(apisrc.archive_dir({}, "10.15") == r"X:\知乎视频\内容查看\10月发布视频\企鹅号\企鹅号软件发布\10.15",
          "发完挪到「企鹅号软件发布\日期」(日期 = 发出去那天)")
    check(apisrc.archive_dir({}).endswith(apisrc.pub_day()) and f"{apisrc.pub_day().split('.')[0]}月发布视频" in apisrc.archive_dir({}),
          "不给日期就按今天(北京时间)算,{month} 也是")

    p = topic.split_topics("标题 #a #B #b")
    check(p["body"] == "标题" and p["sep"] == " " and p["tags"] == ["a", "B"], "话题拆开、不分大小写去重")
    check(topic.split_topics("标题#a 中间 #b")["tags"] == ["b"], "只认结尾那一串")
    k = "狼队危险了# 2026kpl年度总决赛 # kpl十周年 # 2026kpl年度总决赛 # kpl十周年 "
    check(topic.split_topics(k)["tags"] == ["2026kpl年度总决赛", "kpl十周年"], "认「# 话题」(# 后面带空格)和重复的")
    check(topic.new_name(k, lambda b, t: t[0]) == "狼队危险了#2026kpl年度总决赛", "留下的写成「#话题」")
    check(topic.new_name("标题 # 牧神记") == "标题 #牧神记" and topic.split_topics("标题＃甲＃乙")["tags"] == ["甲", "乙"],
          "只有一个「# 话题」也改写法;全角 ＃ 也认")
    check(topic.split_topics("取胜n# 2026kpl # kpl十周年")["body"] == "取胜" and topic.split_topics("神作 ##怪化猫")["tags"] == ["怪化猫"]
          and topic.split_topics("Join#话题")["body"] == "Join", "认「##话题」「取胜n#话题」(n 是丢了的换行),英文单词的 n 不动")
    check(topic.with_topic("团战#英雄联盟手游 #lol", "#英雄 联盟") == "团战#英雄联盟" and topic.with_topic("没话题 ", "英雄联盟") == "没话题#英雄联盟"
          and topic.with_topic("a#英雄联盟", "英雄联盟") is None, "批量改话题:全换成填的那个;没话题就接上;一样的不改")
    check(topic.bad_format("标题 # 剑来") and topic.bad_format("神作 ##怪化猫") and topic.bad_format("《剑来》 #剑来 ")
          and topic.bad_format("打法。n#三角洲行动") and topic.bad_format("没话题 ") and not topic.bad_format("a #x #y")
          and not topic.bad_format("正常#三角洲行动"), "「话题写法不对」判严格(结尾空格、n# 也算)")
    check(topic.tidy("《剑来》 #剑来 ") == "《剑来》 #剑来" and topic.tidy("打法。n#三角洲行动") == "打法。#三角洲行动"
          and topic.tidy("神作 ##怪化猫") == "神作 #怪化猫" and topic.tidy("x # a # a") == "x #a" and topic.tidy("没话题 ") == "没话题",
          "整理写法:一键改好(不用 AI)")
    check("动画名" in topic.TOPIC_SYSTEM and "留下的就必须是作品名" in topic.TOPIC_SYSTEM, "作品名(游戏 / 剧 / 电影 / 动画)优先")
    check(topic.new_name("x #a #a") == "x #a" and topic.new_name("x #a") is None and topic.new_name("x") is None, "0/1 个不问 AI")
    check(topic.new_name("x #活动 #三角洲行动", lambda b, t: t[1]) == "x #三角洲行动", "2 个以上留 AI 挑的")
    check(topic.parse_order('```json\n{"理由":"x","顺序":[2,1]}\n```', 2) == [2, 1] and topic.parse_order("2", 3) == [2, 1, 3]
          and topic.parse_order("不知道", 2) == [], "AI 回话读顺序")
    m = topic.topic_messages("正文", ["a", "b"])
    check("排第一的那个会被留下" in m[0]["content"] and "1. #a\n2. #b" in m[1]["content"], "提示词和 ainame 一样")

    check(checks.platform_hits("抖音同款 #牧神记") == ["抖音"] and checks.platform_hits("everybody books") == []
          and checks.platform_hits("来自 dy 的") == ["dy"], "标题里的别的平台名(dy 只认单独的)")

    v = [x for x in vs if x.account == "CSGO战神君"][0]
    led = topic.Ledger(tmp / "led.json")
    moves = topic.rename_with_sidecars(v.path, topic.new_name(v.title, lambda b, t: t[0]))
    led.add("t1", moves)
    d = os.path.dirname(v.path)
    check(sorted(os.listdir(d)) == ["a #CSGO.jpg", "a #CSGO.mp4"], "改名:同名封面跟着改")
    check(led.undo_last() == (2, 0, 0) and sorted(os.listdir(d)) == ["a #CSGO #反恐精英.jpg", "a #CSGO #反恐精英.mp4"], "能撤销")

    check(apiacc.unseal(apiacc.seal("秘密abc")) == "秘密abc" and "秘密" not in apiacc.seal("秘密abc"), "密钥加密存")
    import sqlite3
    db = tmp / "old.db"
    con = sqlite3.connect(db)
    con.execute("create table accounts(id integer primary key, source_name, source_id, client_id, client_secret, nick, category, enabled, sort_order)")
    con.execute("insert into accounts values(1,'CSGO','1','cid','sec1','CSGO战神君',1604,1,0)")
    con.commit()
    con.close()
    check(apiacc.migrate(str(db)) == 1 and apiacc.find("CSGO战神君")["category"] == 1604, "从旧数据库搬账号")
    check("sec1" not in apiacc.store_path().read_text("utf-8"), "存下来的文件里没有明文密钥")

    class R:
        def __init__(self, j):
            self.j, self.status_code, self.text = j, 200, ""

        def json(self):
            return self.j

    class S:
        def __init__(self):
            self.calls, self.n, self.trunks = [], 0, []

        def post(self, url, **kw):
            self.calls.append(("token", kw["params"]["client_secret"]))
            return R({"code": "0", "data": {"access_token": "T", "expires_in": 7200}})

        def request(self, method, url, **kw):
            path = url.split("api.om.qq.com")[1]
            self.calls.append((path, kw.get("json")))
            assert kw["params"]["access_token"] == "T"
            if path == "/video/clientuploadready":
                self.size = kw["json"]["size"]
                return R({"code": "0", "data": {"transaction_id": "U1"}})
            if path == "/video/clientuploadtrunk":       # 和真接口一样:回下一片的起止;最后一片回 文件大小-1;文件名只能英文
                off = int(kw["data"]["start_offset"])
                name, chunk, _ct = kw["files"]["mediatrunk"]
                assert name.isascii(), "文件名得是英文"
                assert off == sum(len(c) for c in self.trunks), "多传 / 少传了"
                self.trunks.append(chunk)
                nxt = off + len(chunk)
                if nxt >= self.size:              # 最后一片:回 start = end = 文件大小 - 1(真接口)
                    return R({"code": "0", "data": {"start_offset": self.size - 1, "end_offset": self.size - 1}})
                return R({"code": "0", "data": {"start_offset": nxt, "end_offset": min(self.size, nxt + len(chunk)) - 1}})
            if path == "/articlev2/clientpubvideo":
                return R({"code": "0", "data": {"transaction_id": "P1", "article_id": "A9"}})
            if path == "/transaction/infoclient":
                if kw["params"]["transaction_id"] == "U1":
                    return R({"code": "0", "data": {"article_info": {"article_video_info": {}}, "transaction_status": "成功",
                                                    "vid": "V7"}})       # 真接口 vid 在最外层
                self.n += 1
                return R({"code": "0", "data": {"transaction_status": "处理中" if self.n < 2 else "成功"}})
            return R({"code": "-1", "msg": "?"})
    s = S()
    real_sleep = omapi.time.sleep
    omapi.time.sleep = lambda x: None
    try:
        r = omapi.Client("cid", "sec1", session=s).send(v.path, v.title, 1604)
    finally:
        omapi.time.sleep = real_sleep
    pub = [c[1] for c in s.calls if c[0] == "/articlev2/clientpubvideo"][0]
    big = tmp / "big.mp4"
    big.write_bytes(bytes(range(10)))
    s2 = S()
    real_trunk = omapi.TRUNK
    omapi.TRUNK = 3
    try:
        omapi.Client("cid", "sec1", session=s2).upload(str(big))
    finally:
        omapi.TRUNK = real_trunk
    check(b"".join(s2.trunks) == bytes(range(10)) and len(s2.trunks) == 4, "分片上传:多片按平台说的下一片位置接着传,不跳片、传完不多传")
    class Flaky(S):                              # 第二片第一次断网:原地重传这一片,接着传完
        def request(self, method, url, **kw):
            if url.endswith("clientuploadtrunk") and kw["data"]["start_offset"] == "3" and not getattr(self, "boom", False):
                self.boom = True
                import requests as _rq
                raise _rq.ConnectionError("断网")
            return S.request(self, method, url, **kw)
    s3 = Flaky()
    omapi.TRUNK = 3
    real_sleep = omapi.time.sleep
    omapi.time.sleep = lambda x: None
    try:
        omapi.Client("cid", "sec1", session=s3).upload(str(big))
    finally:
        omapi.TRUNK = real_trunk
        omapi.time.sleep = real_sleep
    check(b"".join(s3.trunks) == bytes(range(10)) and s3.boom, "上传一片断网:原地重传这一片,不用整条重来")
    check(r == {"vid": "V7", "article_id": "A9", "transaction_id": "P1", "status": "成功", "cover": ""}, "发布流程:传 → vid → 发 → 等成功")
    check(pub == {"title": v.title, "tags": "", "vid": "V7", "cat": 1604, "desc": v.title, "aigc_userstatement": "2",
                  "ext_info": "{\"self_declare\": 0}"},
          "发的内容:标题 = 简介 = 文件名,分类按号,AI 声明非 AI,自主声明无需标注(self_declare=0)")
    dst = apisrc.move_published(v.path, str(tmp / "已发布"))
    check(os.path.isfile(dst) and not os.path.exists(v.path), "发完挪走")

    ff = vertical.ffmpeg_path()
    if ff:
        src = tmp / "横.mp4"
        import subprocess
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-f", "lavfi",
                        "-i", "sine", "-t", "2", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
        check(vertical.is_landscape(vertical.probe(str(src), ff)), "认出横屏")
        new, orig = vertical.to_vertical(str(src), ff)
        info = vertical.probe(new, ff)
        check((info["w"], info["h"]) == (1080, 1920) and os.path.isfile(orig) and "横屏原片" in orig, "转成竖屏,原片挪进「横屏原片」")
    else:
        print("  (没有 ffmpeg,跳过转竖屏)")


def _settle(tab):
    """等后台(换日期 / 刷新后自动检查)做完。"""
    from PySide6.QtWidgets import QApplication
    if tab.job:
        tab.job.wait()
    QApplication.processEvents()


def test_api_tab(tmp: Path):
    print("[接口发页:手选文件夹(旧软件的「选择」)/ 一条一条发、间隔 / 发完挪走、记录]")
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, apisrc, omapi
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    root = tmp / "api2"
    (root / "游戏视频" / "CSGO--CSGO战神君" / "10.15").mkdir(parents=True)
    (root / "游戏视频" / "2电竞赛事（腾讯系相关游戏赛事）").mkdir(parents=True)
    for f in ("CSGO--CSGO战神君/10.15/c1.mp4", "CSGO--CSGO战神君/10.15/c2.mp4",
              "2电竞赛事（腾讯系相关游戏赛事）/e1.mp4", "2电竞赛事（腾讯系相关游戏赛事）/e1.jpg"):
        (root / "游戏视频" / f).write_bytes(b"x")
    esp = str(root / "游戏视频" / "2电竞赛事（腾讯系相关游戏赛事）")
    roots = [str(root / "游戏视频")]
    known = {"CSGO战神君", "电竞情报馆"}
    vs = apisrc.videos(roots, "10.15", known, {"电竞情报馆": esp})
    check(sorted((v.account, v.title) for v in vs) == [("CSGO战神君", "c1"), ("CSGO战神君", "c2"), ("电竞情报馆", "e1")],
          "手选的文件夹:电竞情报馆发「2电竞赛事」里的")
    vs = apisrc.videos(roots, "10.15", known, {"CSGO战神君": esp})
    check([v.account for v in vs] == ["CSGO战神君"] and vs[0].title == "e1", "手选了就不再自动找这个号")

    accs = [{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
            {"nick": "电竞情报馆", "source_name": "电竞赛事", "client_id": "b", "secret": apiacc.seal("s"), "category": 1605, "enabled": True}]
    apiacc.save(accs)
    st = Settings(tmp / "st_api.json")
    st["api_roots"] = roots
    st["api_archive"] = str(tmp / "发布" / "{date}已发布")
    st["api_interval"] = 1
    check(st.get("api_threads") == 1 and "api_parallel" not in st, "默认一条一条发(旧软件「线程 1」)")
    rec = Records(tmp / "rec_api.sqlite")
    logs = []
    tab = T.ApiTab(st, rec, logs.append)
    tab.c_date.setCurrentText("10.15")
    tab._set_pick("10.15", "电竞情报馆", esp)
    tab.load()
    check(len(tab.videos) == 3, "页面上:自动找的 + 手选的")
    sent = []

    class FakeClient:
        def __init__(self, cid, sec, **k):
            self.cid = cid

        def send(self, path, title, cat, before_publish=None, **k):
            if before_publish:
                before_publish("V")
            sent.append((time.time(), title, cat))
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}

    real_c, real_q = omapi.Client, QMessageBox.question
    omapi.Client = FakeClient
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        tab.run_check()
        tab.job.wait()
        QApplication.processEvents()
        for v in tab.videos:                       # 假视频 ffmpeg 读不出来:当成竖屏的好视频
            v.checks.update(bad_read=False, landscape=False, w=1080, h=1920)
        tab.run_publish()
        tab.job.wait()
        QApplication.processEvents()
    finally:
        omapi.Client, QMessageBox.question = real_c, real_q
    check(sorted((t, c) for _x, t, c in sent) == [("c1", 1604), ("c2", 1604), ("e1", 1605)], "三条都发了,分类按号")
    gaps = [b[0] - a[0] for a, b in zip(sent, sent[1:])]
    check(all(g >= 0.95 for g in gaps), f"每条之间歇够间隔 -> {[round(g, 2) for g in gaps]}")
    out = tmp / "发布" / f"{apisrc.pub_day()}已发布"          # 按发出去那天(今天)算,不是素材文件夹的 10.15
    check(sorted(os.listdir(out / "CSGO")) == ["c1.mp4", "c2.mp4"] and sorted(os.listdir(out / "电竞赛事")) == ["e1.jpg", "e1.mp4"]
          and not os.path.isfile(os.path.join(esp, "e1.jpg")), "发完挪走,按游戏分子文件夹(名字 = 旧软件「账号」),同名封面跟着挪")
    check(apisrc.archive_dir({"api_archive_by_game": False}, "10.15", accs[0]).endswith("企鹅号软件发布" + os.sep + "10.15")
          and apisrc.archive_dir({}, "10.15", accs[0]).endswith(os.path.join("企鹅号软件发布", "10.15", "CSGO")),
          "日期下面再分游戏;不勾「按游戏分」就只到日期")
    check(len([r for r in rec.rows("10.15") if r["employee"] == "接口" and r["status"] == "已发"]) == 3, "记进记录(员工 = 接口)")
    check(not (root / "游戏视频" / "CSGO--CSGO战神君" / "10.15").exists(), "这个号 10.15 发空了:文件夹自动删了")
    (root / "游戏视频" / "CSGO--CSGO战神君" / "10.15").mkdir()          # 员工又放了两条进来
    for f in ("c3.mp4", "c4.mp4"):
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.15" / f).write_bytes(b"x")
    tab.load()
    tab.run_check()
    tab.job.wait()
    QApplication.processEvents()
    for v in tab.videos:
        v.checks.update(bad_read=False, landscape=False, w=1080, h=1920)
    sent.clear()
    omapi.Client = FakeClient
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        row = [i for i, v in enumerate(tab.videos) if v.title == "c4"][0]
        tab.tree.clearSelection()
        tab.items[row].setSelected(True)
        check(tab.selected_rows() == [row], "选中一条")
        tab.run_publish(tab.selected_rows())
        tab.job.wait()
        QApplication.processEvents()
    finally:
        omapi.Client, QMessageBox.question = real_c, real_q
    check([t for _x, t, _c in sent] == ["c4"], "只发选中的:c3 没发")
    for f in ("d1.mp4", "d2.mp4"):                    # 前面发掉的都挪走了,补两条
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.15" / f).write_bytes(b"x")
    tab.load()
    _settle(tab)
    check({n for n, g in tab.groups.items() if g.childCount()} == {"CSGO战神君"} and
          all(not g.isExpanded() for g in tab.groups.values()), "按号分组,默认收起")
    check("这天已发 1 条" in tab.groups["电竞情报馆"].text(0) and tab.cards.vals["sent"].text() != "0",
          "发完挪走了的号:写「这天已发 N 条」,不是「没找到视频」;卡片「已发」算上挪走的")
    tab.expand_all(True)
    check(all(g.isExpanded() for g in tab.groups.values()), "全部展开")
    tab.expand_all(False)
    check(all(not g.isExpanded() for g in tab.groups.values()), "全部收起")
    tab.groups["CSGO战神君"].setExpanded(True)
    tab.load()
    _settle(tab)
    check(tab.groups["CSGO战神君"].isExpanded(), "刷新后展开的还展开着")
    tab.tree.clearSelection()
    tab.groups["CSGO战神君"].setSelected(True)
    check([tab.videos[i].title for i in tab.selected_rows()] == ["c3", "d1", "d2"], "选中号 = 这个号全部")
    check("3 条" in tab.groups["CSGO战神君"].text(0) and "有问题 3" in tab.groups["CSGO战神君"].text(2)
          and "没检查" not in tab.groups["CSGO战神君"].text(2), "号那一行有统计;刷新后自动检查了")
    from PySide6.QtWidgets import QInputDialog
    real_t, real_i, real_gi = QInputDialog.getText, QMessageBox.information, QInputDialog.getItem
    QInputDialog.getText = staticmethod(lambda *a, **k: ("英雄联盟", True))
    QInputDialog.getItem = staticmethod(lambda *a, **k: ("英雄联盟", True))
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        rows = [i for i, v in enumerate(tab.videos) if v.title in ("c3",)]
        tab.set_topic(rows)
        check([v.title for v in tab.videos if v.title.startswith("c3")] == ["c3#英雄联盟"] and
              os.path.isfile(os.path.join(os.path.dirname(tab.videos[rows[0]].path), "c3#英雄联盟.mp4")), "批量改话题改了文件名")
        sent_row = [i for i, v in enumerate(tab.videos) if v.title == "d1"]
        tab.state[sent_row[0]] = "已发"
        tab.set_topic(sent_row)
        check(tab.videos[sent_row[0]].title == "d1", "发过的不改")
        tab._ask_title = lambda *a, **k: ("c3 改过的标题", True)        # 改标题的框(宽的那个)
        tab.edit_title(rows[0])
        check(tab.videos[rows[0]].title == "c3 改过的标题", "右键改标题")
        check("改标题" in tab.b_undo.toolTip(), "撤销按钮上写着上一次是什么")
        tab.undo_topic()                           # 真点「撤销」(审查:原来一点就崩)
        _settle(tab)
        check(any(v.title == "c3#英雄联盟" for v in tab.videos), "撤销:只撤上一次(改标题),批量改话题还在")
        tab.undo_topic()
        _settle(tab)
        check(any(v.title == "c3" for v in tab.videos), "再撤销一次:批量改话题也撤回去")
    finally:
        QInputDialog.getText, QMessageBox.question, QMessageBox.information = real_t, real_q, real_i
        QInputDialog.getItem = real_gi
    tab.e_find.setText("c1")
    vis = [tab.videos[i].title for i, it in tab.items.items() if not it.isHidden()]
    check(vis == [], "搜标题(c1 发掉了,搜不到)")
    tab.e_find.setText("d2")
    vis = [tab.videos[i].title for i, it in tab.items.items() if not it.isHidden()]
    check(vis == ["d2"], "搜标题")
    tab.e_find.setText("")
    with open(os.path.join(esp, "e2.mp4"), "wb") as f:
        f.write(b"x")
    tab.load()
    _settle(tab)
    check("管全部" in tab.lab_scope.text(), "没选:写着「管全部」")
    tab.k_bad.setChecked(True)
    check("过滤中" in tab.lab_scope.text(), "开着「只看有问题的」:写着「过滤中:只管看得见的」,不说全部")
    tab.k_bad.setChecked(False)
    for v in tab.videos:
        v.checks = {}
    tab.tree.clearSelection()
    tab.groups["电竞情报馆"].setSelected(True)
    check("选中" in tab.lab_scope.text() and "电竞情报馆 1 条" in tab.lab_scope.text(), "选了一个号:写着「只管选中的:号 N 条」")
    tab.run_check()
    tab.job.wait()
    QApplication.processEvents()
    check([bool(v.checks) for v in tab.videos] == [v.account == "电竞情报馆" for v in tab.videos], "只检查选中的号")
    tab.tree.clearSelection()
    check("管全部" in tab.lab_scope.text(), "取消选择:回到全部")
    tab.unpick("电竞情报馆")
    check("10.15" not in (st.get("api_picked") or {}), "取消手选")


def test_audit_r1(tmp: Path):
    print("[审查第 1 轮修的:密钥不进日志 / 结果不明不重发 / 撤销不改已发的 / 转竖屏不覆盖 / 重名序号位置 / 间隔]")
    import requests
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, topic, vertical
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T

    # 1. 网络错:报错里没有密钥 / token
    class Boom:
        def post(self, *a, **k):
            raise requests.ConnectionError("Max retries exceeded with url: /x?client_secret=SEC123&access_token=TOK9")
        request = post
    try:
        omapi.Client("cid", "SEC123", session=Boom()).token()
        msg = ""
    except omapi.ApiError as e:
        msg = str(e)
    check(msg and "SEC123" not in msg and "TOK9" not in msg and "网络" in msg, f"断网报错不带密钥、说人话 -> {msg}")
    check(omapi.redact("a?client_secret=xx&access_token=yy") == "a?client_secret=***&access_token=***", "redact 去掉密钥")

    # 2. 发布请求发出去没回话 → 结果不明,不再发;发成功后查进度出错 → 算已发
    class S:
        def __init__(self, pub_err=None, poll_err=None):
            self.pub_err, self.poll_err, self.pubs = pub_err, poll_err, 0

        def post(self, url, **kw):
            class R:
                status_code = 200

                def json(self_):
                    return {"code": "0", "data": {"access_token": "T", "expires_in": 7200}}
            return R()

        def request(self, method, url, **kw):
            path = url.split("api.om.qq.com")[1]
            d = {}
            if path == "/video/clientuploadready":
                d = {"transaction_id": "U"}
            elif path == "/video/clientuploadtrunk":
                d = {"end_offset": len(kw["files"]["mediatrunk"][1]) - 1 + int(kw["data"]["start_offset"])}
            elif path == "/transaction/infoclient":
                if kw["params"]["transaction_id"] == "U":
                    d = {"vid": "V"}
                elif self.poll_err:
                    raise self.poll_err
                else:
                    d = {"transaction_status": "成功"}
            elif path == "/articlev2/clientpubvideo":
                self.pubs += 1
                if self.pub_err:
                    raise self.pub_err
                d = {"transaction_id": "P", "article_id": "A"}

            class R:
                status_code = 200

                def json(self_):
                    return {"code": "0", "data": d}
            return R()
    f = tmp / "aud.mp4"
    f.write_bytes(b"0123456789")
    try:
        omapi.Client("c", "s", session=S(pub_err=requests.ReadTimeout("t"))).send(str(f), "t", 1)
        kind = "none"
    except omapi.Unknown:
        kind = "unknown"
    check(kind == "unknown", "发布请求超时 = 结果不明(不是没发成)")
    r = omapi.Client("c", "s", session=S(poll_err=requests.ReadTimeout("t"))).send(str(f), "t", 1)
    check(r["status"] == "处理中" and r["article_id"] == "A", "发成功后查进度出错 = 已发(平台处理中)")

    rec = Records(tmp / "aud.sqlite")

    class V:
        date, account, title = "1.1", "号", "t"
        path = str(f)
    rid = rec.api_begin(V)
    check(rec.blocked(V.path) and rec.status_of(V.path) == "结果不明", "发布中(程序被关)= 不能自动再发")
    rec.api_finish(rid, "结果不明", "x")
    check(rec.blocked(V.path) and len(rec.unsure_paths()) == 1, "结果不明:不能自动再发,列出来让人看")
    rec.resolve_unsure(V.path, False)
    check(not rec.blocked(V.path), "人看过了标「没发」:能再发")

    # 3. 撤销不改已发的
    d = tmp / "aud_undo"
    d.mkdir()
    (d / "c1 #a #b.mp4").write_bytes(b"x")
    led = topic.Ledger(tmp / "aud_led.json")
    moves = topic.rename_logged(str(d / "c1 #a #b.mp4"), "c1 #a", led, "t")
    rec.api_result(type("X", (), {"date": "1.1", "account": "号", "title": "c1 #a", "path": moves[0][1]}), "已发")
    ok, bad, skipped = led.undo_last(skip=rec.blocked)
    check(skipped == 1 and (d / "c1 #a.mp4").exists(), "撤销:已经发了的不改回去(防重发)")

    # 7. 重名:序号插在话题前面,话题还在结尾
    (d / "a #x.mp4").write_bytes(b"x")
    (d / "a #x #y.mp4").write_bytes(b"x")
    mv = topic.rename_with_sidecars(str(d / "a #x #y.mp4"), "a #x")
    check(os.path.basename(mv[0][1]) == "a (2) #x.mp4" and topic.split_topics("a (2) #x")["tags"] == ["x"],
          "重名:「a (2) #x」话题还在结尾")

    # 5. 转竖屏:a.mov 转出来不覆盖已有的 a.mp4
    ff = vertical.ffmpeg_path()
    if ff:
        import subprocess
        vd = tmp / "aud_vert"
        vd.mkdir()
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-t", "1",
                        "-c:v", "libx264", str(vd / "a.mov")], check=True)
        (vd / "a.mp4").write_bytes(b"keep")
        out, orig = vertical.to_vertical(str(vd / "a.mov"), ff)
        check((vd / "a.mp4").read_bytes() == b"keep" and os.path.basename(out) == "a (2).mp4", "转竖屏:不覆盖同名的另一条")
        check(not [n for n in os.listdir(vd) if n.startswith("_处理中_")], "转竖屏:不留临时文件")
        (vd / "b.mov").write_bytes(b"x")
        (vd / "横屏原片").rename(vd / "横屏原片_d")
        (vd / "横屏原片").write_bytes(b"block")
        try:
            vertical.to_vertical(str(vd / "b.mov"), ff)
            err = ""
        except RuntimeError as e:
            err = str(e)
        check(err and (vd / "b.mov").exists() and not [n for n in os.listdir(vd) if n.startswith("_处理中_")],
              f"转竖屏失败:原片还在、不留临时文件 -> {err[:40]}")

    # 8. 间隔:上一条发完以后才开始算
    root = tmp / "aud_gap"
    (root / "号A").mkdir(parents=True)
    for n in ("g1.mp4", "g2.mp4"):
        (root / "号A" / n).write_bytes(b"x")
    apiacc.save([{"nick": "号A", "source_name": "A", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "aud_st.json")
    st["api_roots"] = [str(tmp / "nothing")]
    st["api_archive"] = str(tmp / "aud_out")
    st["api_interval"] = 1
    st["api_picked"] = {"1.1": {"号A": str(root / "号A")}}
    tab = T.ApiTab(st, Records(tmp / "aud2.sqlite"), lambda m: None)
    tab.c_date.addItem("1.1")
    tab.c_date.setCurrentText("1.1")
    tab.load()
    _settle(tab)
    for v in tab.videos:
        v.checks = {"w": 1080, "h": 1920, "tags": [], "platform": []}
    marks = []

    class Slow:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, **k):
            marks.append(("start", time.time()))
            before_publish("V")
            time.sleep(0.6)
            marks.append(("end", time.time()))
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}
    real_c, real_q = omapi.Client, QMessageBox.question
    omapi.Client = Slow
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        tab.run_publish()
        check(tab.busy() and not tab.b_pick.isEnabled(), "后台发布时「给号选文件夹」点不了")
        tab.job.wait()
        QApplication.processEvents()
    finally:
        omapi.Client, QMessageBox.question = real_c, real_q
    gap = marks[2][1] - marks[1][1] if len(marks) >= 3 else 0
    check(gap >= 0.95, f"间隔:上一条发完以后歇够了再发 -> {gap:.2f} 秒")


def test_audit_r2(tmp: Path):
    print("[审查第 1 轮(教育 / 数据安全)修的:挪文件不留两份 / 设置不互相冲 / 坏文件留底 / 路径写法 / 停了的批次 / 没 png 不挡路]")
    import json
    from qe import fsops
    from qe import folders as F
    from qe.config import Settings
    from qe.records import Records

    # 1. 挪一天:有文件被占着 → 占着的留在原处,其它挪过去,不会两边各一份;关掉再挪接着挪,没有 (2)
    root = tmp / "mv_src"
    d = root / "10.15" / "小天地" / "张三"
    d.mkdir(parents=True)
    for n in ("a", "b", "c"):
        (d / f"{n}.mp4").write_bytes(n.encode() * 10)
    st = {"material_root": str(root), "archive_root": str(tmp / "mv_dst" / "{month}月")}
    fh = open(d / "b.mp4", "rb")
    try:
        try:
            F.move_date(st, "10.15")
            err = ""
        except fsops.MoveError as e:
            err = str(e)
    finally:
        fh.close()
    dst = tmp / "mv_dst" / "10月" / "10.15" / "小天地" / "张三"
    both = [n for n in os.listdir(d) if (dst / n).exists()] if d.exists() else []
    check(err and "b.mp4" in err and not both, f"挪一天:被占着的留在原处、不留两份 -> {err[:30]}")
    F.move_date(st, "10.15", merge=True)
    check(sorted(os.listdir(dst)) == ["a.mp4", "b.mp4", "c.mp4"] and not (root / "10.15").exists(),
          "关掉再挪:接着挪完,没有 (2)")
    try:
        F.move_date({"material_root": str(root), "archive_root": ""}, "10.15")
        err = ""
    except Exception as e:
        err = str(e)
    check("发完挪到" in err, "「发完挪到」空着:说人话")

    # 4. 设置:两份各改各的,不互相冲掉
    sp = tmp / "st_merge.json"
    a = Settings(sp)
    b = Settings(sp)
    b["api_picked"] = {"10.15": {"号": "X"}}
    b.save()
    a["last_date"] = "10.16"
    a.save()
    disk = json.loads(sp.read_text("utf-8"))
    check(disk.get("api_picked") == {"10.15": {"号": "X"}} and disk.get("last_date") == "10.16" and a["api_picked"] == b["api_picked"],
          "设置:各改各的,后保存的不会冲掉先保存的")

    # 5. 设置文件坏了:原文件留底
    bad = tmp / "st_bad.json"
    bad.write_text('{"material_root": "Q:\\\\x", ', "utf-8")
    c = Settings(bad)
    check(c.broken and os.path.exists(c.broken) and c["material_root"] == r"X:\知乎视频\小学生教育", "设置坏了:原文件改名留着,用默认")
    nul = tmp / "st_null.json"
    nul.write_text("null", "utf-8")
    check(Settings(nul).broken, "设置内容是 null:不崩")

    # 7. 路径写法不同也认得出发过
    r = Records(tmp / "a2.sqlite")

    class V:
        date, account, employee, title, cover_kind = "10.15", "号", "员", "t", ""
        path = r"X:\知乎视频\小学生教育\10.15\a.mp4"
    r.manual_published(V)
    check(r.status_of("x:/知乎视频/小学生教育/10.15/a.mp4") == "已发", "素材文件夹换个写法(x:/),发过的照样认得")

    # 6. 补记没摆成:已经记过已发的不再记,汇总不多算
    class W:
        date, account, employee, title, cover_kind = "10.15", "号", "员", "w", ""
        path = r"X:\w.mp4"
    r.failed(W, "B1", "封面没成")
    r.manual_published(W)
    r.mark_failed_published("B1")
    srow = [x for x in r.summary("10.15") if x["employee"] == "员"][0]
    check(srow["sent"] == 2, f"补记没摆成:不重复算 -> 已发 {srow['sent']}")

    # 2. 摆到一半停了:已经摆好的那几条照样等人确认
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from gui.window import MainWindow
    st2 = Settings(tmp / "aw.json")
    st2["material_root"] = str(tmp / "nothing")
    st2["api_roots"] = [str(tmp / "nothing")]
    st2["ai_key"] = "test"
    rec = Records(tmp / "aw.sqlite")
    w = MainWindow(st2, rec)
    w.batch_id = "B9"
    rec.prepared(V, "B9")
    real_w = QMessageBox.warning
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    try:
        w._batch_done(None, "停下了")
    finally:
        QMessageBox.warning = real_w
    check(w.batch_id == "B9" and w.b_sent.isEnabled(), "摆到一半停了:摆好的那几条还能点「这批发好了 / 不要了」")
    w.close()


def test_ui_r1(tmp: Path):
    print("[界面审查修的:没发成说人话 / 号密钥坏了剩下的标「没轮到」/ 发完总结 / 结尾空格单独说 / 窗口能缩窄]")
    from PySide6.QtWidgets import QApplication, QPushButton
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, checks, omapi, topic
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T

    short, tip = T.friendly(omapi.ApiError("上传视频失败:invalid_file_upload(code 40023)", "40023"))
    check("平台不收" in short and "重新导出" in tip, "40023:说人话 + 下一步")
    short, tip = T.friendly(omapi.ApiError("换 token 失败", "40001", fatal=True))
    check("密钥" in short and "登录取钥匙" in tip, "换 token 失败:说密钥不对 + 去登录取钥匙")
    short, tip = T.friendly(OSError(22, "Invalid argument", r"X:\2企鹅号视频\游戏视频\a.mp4"))
    check("素材盘" in short and "双击打开素材盘" in tip, "读不了视频文件(11-03 X 盘断了):说素材盘断了 + 下一步")
    short, tip = T.friendly(FileNotFoundError(2, "No such file or directory", str(tmp / "改了名的.mp4")))
    check("改名" in short and "刷新" in tip and "素材盘" not in short, f"文件夹在、文件没了(11-09 被人改短了名字):说改名 / 挪走了 -> {short}")
    short, tip = T.friendly(FileNotFoundError(2, "No such file or directory", r"Q:\没这个盘\a.mp4"))
    check("素材盘" in short, "连文件夹都没了:还是说素材盘断了")
    import requests
    short, _tip = T.friendly(requests.ConnectionError("连不上"))
    check("素材盘" not in short, "网络错误(也是 OSError)不当成素材盘断了")

    class V:
        title = "A小到底该怎么控 "
        checks = {"w": 1080, "h": 1920, "tags": []}
    check(checks.problems(V) == [] and checks.format_kind(V.title) == "结尾多了空格",
          "只是结尾多空格:不算要处理(发的时候自己去掉,新员工试用 2026-10-21)")
    V.title = "标题 # 剑来"
    V.checks = {"w": 1080, "h": 1920, "tags": ["剑来"]}
    check(checks.problems(V) == ["话题写法不对"], "「# 话题」:说「话题写法不对」")

    root = tmp / "ui_r1"
    for nick in ("号A", "号B"):
        (root / nick).mkdir(parents=True)
        for n in ("1", "2", "3"):
            (root / nick / f"{nick}{n}.mp4").write_bytes(b"x")
    apiacc.save([{"nick": n, "source_name": n, "client_id": n, "secret": apiacc.seal("s"), "category": 1604, "enabled": True}
                 for n in ("号A", "号B")])
    st = Settings(tmp / "ui_st.json")
    st["api_roots"] = [str(tmp / "none")]
    st["api_archive"] = str(tmp / "ui_out")
    st["api_interval"] = 0
    st["api_picked"] = {"1.1": {n: str(root / n) for n in ("号A", "号B")}}
    tab = T.ApiTab(st, Records(tmp / "ui.sqlite"), lambda m: None)
    tab.c_date.addItem("1.1")
    tab.c_date.setCurrentText("1.1")
    tab.load()
    _settle(tab)
    for v in tab.videos:
        v.checks = {"w": 1080, "h": 1920, "tags": [], "platform": []}

    class C:
        def __init__(self, cid, sec, **k):
            self.cid = cid

        def send(self, path, title, cat, before_publish=None, **k):
            if self.cid == "号B":
                raise omapi.ApiError("换 token 失败", "40001", fatal=True)
            before_publish("V")
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}
    real = omapi.Client
    omapi.Client = C
    try:
        tab.run_publish()
        _settle(tab)
    finally:
        omapi.Client = real
    sts = {v.title: tab.state.get(i, "") for i, v in enumerate(tab.videos)}
    check(sts["号A1"] == "已发" and sts["号B1"].startswith("没发成:号的密钥") and sts["号B2"].startswith("没发:号的密钥坏了"),
          f"号密钥坏了:第一条没发成,剩下的标「没轮到」-> {sts['号B1']} / {sts['号B2']}")
    check("号B" in tab.groups and "能发 0" in tab.groups["号B"].text(3), "号那一行:没发成的不算「能发」")
    check(tab.logbox.toPlainText().count("发完了:成功 3 · 没发成 1") == 1 and "号的密钥坏了没发 2" in tab.logbox.toPlainText(),
          "发完总结:成功 / 没发成 / 没轮到都写")

    # 窗口能缩窄:接口页最小宽度不超过 1000
    tab.tree.clearSelection()
    tab.groups["号A"].setSelected(True)
    QApplication.processEvents()
    check(tab.minimumSizeHint().width() <= 1000, f"接口页选中号以后最小宽度 {tab.minimumSizeHint().width()} ≤ 1000 -> "
          + str([(x.text()[:14], x.minimumSizeHint().width()) for x in tab.hero.findChildren(QPushButton) if x.isVisibleTo(tab)]))


def test_squarish(tmp: Path):
    print("[偏方的(3:4 / 正方形)也转成标准竖屏]")
    from qe import checks, vertical

    class V:
        title = "a"
    for (w, h), want in (((1080, 1920), []), ((720, 1280), []), ((1080, 1440), ["偏方要转竖屏"]),
                         ((1080, 1080), ["偏方要转竖屏"]), ((1920, 1080), ["横屏"])):
        V.checks = {"w": w, "h": h, "landscape": vertical.is_landscape({"w": w, "h": h}),
                    "squarish": vertical.is_squarish({"w": w, "h": h}), "tags": []}
        check(checks.problems(V) == want and checks.needs_vertical(V.checks) == bool(want), f"{w}×{h} -> {want or '能发'}")
    ff = vertical.ffmpeg_path()
    if ff:
        import subprocess
        d = tmp / "sq"
        d.mkdir()
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=720x960:rate=25", "-t", "1",
                        "-c:v", "libx264", str(d / "方.mp4")], check=True)
        out, _orig = vertical.to_vertical(str(d / "方.mp4"), ff)
        info = vertical.probe(out, ff)
        check((info["w"], info["h"]) == (1080, 1920), f"3:4 转成 1080×1920 -> {info['w']}×{info['h']}")


def test_audit_r3(tmp: Path):
    print("[复审修的:GBK 设置不打不开 / 撤销遇到占用不出错 / 转竖屏撞名序号位置 / C# 不吃 / 话题间的 n / 挪文件不覆盖]")
    from qe import fsops, topic, vertical
    from qe.config import Settings

    gbk = tmp / "st_gbk.json"
    gbk.write_bytes("{'素材': 乱码}".encode("gbk"))
    st = Settings(gbk)
    check(st.broken and os.path.exists(st.broken), "设置文件是 GBK / 乱码:改名留着,照样打开")

    d = tmp / "r3_undo"
    d.mkdir()
    (d / "甲 #a #b.mp4").write_bytes(b"x")
    (d / "甲 #a #b.png").write_bytes(b"x")
    led = topic.Ledger(tmp / "r3_led.json")
    mv = topic.rename_logged(str(d / "甲 #a #b.mp4"), "甲 #a", led, "t¦整理话题¦1")
    fh = open(mv[0][1], "rb")
    try:
        ok, bad, skipped = led.undo_last()
    finally:
        fh.close()
    names = sorted(os.listdir(d))
    check(bad >= 1 and names == ["甲 #a.mp4", "甲 #a.png"] and led.last(), f"撤销遇到被占用:不出错、封面不乱改、留着下次撤 -> {names}")
    ok, bad, skipped = led.undo_last()
    check(sorted(os.listdir(d)) == ["甲 #a #b.mp4", "甲 #a #b.png"], "关掉占用再撤一次:改回来了")

    check(topic.tidy("学习C#") is None and topic.split_topics("打法 #王者荣耀n#英雄联盟")["tags"] == ["王者荣耀", "英雄联盟"],
          "「学习C#」不吃掉 #;两个话题中间粘的 n 去掉")

    ff = vertical.ffmpeg_path()
    if ff:
        import subprocess
        vd = tmp / "r3_vert"
        vd.mkdir()
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-t", "1",
                        "-c:v", "libx264", str(vd / "同名 #原神.mov")], check=True)
        (vd / "同名 #原神.mp4").write_bytes(b"keep")
        out, _o = vertical.to_vertical(str(vd / "同名 #原神.mov"), ff)
        check(os.path.basename(out) == "同名 (2) #原神.mp4", f"转竖屏撞名:序号在话题前面 -> {os.path.basename(out)}")

    a, b = tmp / "r3_a.txt", tmp / "r3_b.txt"
    a.write_bytes(b"A")
    b.write_bytes(b"B")
    try:
        fsops._replace(str(a), str(b))
        over = b.read_bytes() == b"A"
    except OSError:
        over = False
    check(not over and b.read_bytes() == b"B", "挪文件:目标已经有了就报错,不会盖掉")


def test_bughunt(tmp: Path):
    print("[挖 bug 修的:不重复发 / 不发错号 / 不发错日期 / 不卡死 / 不丢设置]")
    import json
    import time as _t
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, apisrc, fsops, omapi, topic
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T

    # 4. 「10.15已发」「10.15不能用」「10.150」不算 10.15
    check([apisrc.date_key(x) for x in ("10.15", "10.15(20)", "10.14（星期三）", "11.22未改比例", "11.22（20）未改比例",
                                        "11.20(20）（未改比例）", "11.19未改 比例", "10.15已发", "10.15不能用", "10.15 脏话", "10.150")]
          == ["10.15", "10.15", "10.14", "11.22", "11.22", "11.20", "11.19", "", "", "", ""], "日期文件夹:认未改比例,仍拦已发 / 不能用 / 脏话")

    # 15. 同一个号两个文件夹:都扫
    r2 = tmp / "bh_dup"
    for f in ("CSGO--号X/10.15/甲.mp4", "CS2--号X/10.15/乙.mp4"):
        (r2 / f).parent.mkdir(parents=True, exist_ok=True)
        (r2 / f).write_bytes(b"x")
    check(sorted(v.title for v in apisrc.videos([str(r2)], "10.15", {"号X"})) == ["乙", "甲"], "同一个号两个文件夹:都列出来")

    # 6. 话题正则不卡死
    t0 = _t.time()
    topic.split_topics("标题 " + " ".join(f"#t{i}" for i in range(40)) + " 来学")
    check(_t.time() - t0 < 0.2, f"40 个话题后面跟字:不卡({(_t.time() - t0) * 1000:.0f} 毫秒)")

    # 7. 设置文件带 BOM:保存不丢别的键
    sp = tmp / "bh_bom.json"
    sp.write_bytes(b"\xef\xbb\xbf" + json.dumps({"material_root": "Q:\\x", "api_interval": 9}).encode("utf-8"))
    st = Settings(sp)
    st["last_date"] = "10.16"
    st.save()
    d = json.loads(sp.read_text("utf-8-sig"))
    check(d.get("material_root") == "Q:\\x" and d.get("api_interval") == 9, "设置带 BOM:保存后别的设置还在")

    # 2. 平台回话格式怪:发布已收下就算已发,绝不记成没发成
    class R:
        def __init__(self, j):
            self.j, self.status_code = j, 200

        def json(self):
            return self.j

    class S:
        def __init__(self, pub, poll):
            self.pub, self.poll, self.pubs, self.toks = pub, poll, 0, 0

        def post(self, url, **kw):
            self.toks += 1
            return R({"code": "0", "data": {"access_token": f"T{self.toks}", "expires_in": 7200}})

        def request(self, method, url, **kw):
            path = url.split("api.om.qq.com")[1]
            if path == "/video/clientuploadready":
                return R({"code": "0", "data": {"transaction_id": "U"}})
            if path == "/video/clientuploadtrunk":
                return R({"code": "0", "data": {"end_offset": len(kw["files"]["mediatrunk"][1]) - 1}})
            if path == "/transaction/infoclient":
                if kw["params"]["transaction_id"] == "U":
                    return R({"code": "0", "data": {"vid": "V"}})
                return R(self.poll)
            if path == "/articlev2/clientpubvideo":
                self.pubs += 1
                return R(self.pub)
    f = tmp / "bh.mp4"
    f.write_bytes(b"abc")

    class FakeTime:                                  # 假时钟:查进度的「等一会儿」瞬间过去
        now = 1000.0

        @classmethod
        def time(cls):
            return cls.now

        @classmethod
        def sleep(cls, x):
            cls.now += x
    real_time = omapi.time
    omapi.time = FakeTime
    for pub, poll in (({"code": "0", "data": "weird"}, {"code": "0", "data": {}}),
                      ({"code": "0", "data": {"transaction_id": "P"}}, {"code": "0", "data": ["x"]}),
                      ({"code": "0", "data": {"transaction_id": "P"}}, None)):
        r = omapi.Client("c", "s", session=S(pub, poll)).send(str(f), "t", 1)
        check(r["status"] in ("处理中", "成功"), f"平台收下了但回话怪({str(pub)[:30]} / {str(poll)[:20]}):算已发,不记没发成")
    try:
        omapi.Client("c", "s", session=S(None, None)).send(str(f), "t", 1)
        kind = "none"
    except omapi.Unknown:
        kind = "unknown"
    except omapi.ApiError:
        kind = "apierror"
    check(kind == "unknown", f"发布回了 null:结果不明(不能自动再发)-> {kind}")

    # 12. token 中途作废:重换一次再试
    class S2(S):
        def request(self, method, url, **kw):
            if "articlev2" in url and kw["params"]["access_token"] == "T1":
                return R({"code": "40001", "msg": "access_token expired"})
            return super().request(method, url, **kw)
    s2 = S2({"code": "0", "data": {"transaction_id": "P"}}, {"code": "0", "data": {"transaction_status": "成功"}})
    r = omapi.Client("c", "s", session=s2).send(str(f), "t", 1)
    check(r["status"] == "成功" and s2.toks == 2, "token 中途作废:重换一次就发出去了")
    omapi.time = real_time

    # 1 / 3. 两个号同一个文件:记「发布中」原子地拦;发完挪走的新位置也认得出发过
    rec = Records(tmp / "bh.sqlite")

    class V:
        date, account, title = "10.15", "号A", "v1"
        path = str(tmp / "same" / "v1.mp4")
    rid = rec.try_begin(V)
    check(rid is not None and rec.try_begin(V) is None, "同一个文件:第二个号要发时拦住(不发两遍)")
    rec.api_finish(rid, "已发")
    rec.mark_moved(rid, str(tmp / "归档" / "CSGO" / "v1.mp4"))
    check(rec.blocked(str(tmp / "归档" / "CSGO" / "v1.mp4")), "发完挪走了:在归档里再看到它也认得出发过")

    # 1. 界面:两个号手选同一个文件夹 → 发布前拦住;手选文件夹不许选别的号在用的 / 归档 / 已发
    same = tmp / "bh_same"
    same.mkdir()
    for n in ("s1.mp4", "s2.mp4"):
        (same / n).write_bytes(b"x")
    apiacc.save([{"nick": n, "source_name": n, "client_id": n, "secret": apiacc.seal("s"), "category": 1604, "enabled": True}
                 for n in ("号A", "号B")])
    st = Settings(tmp / "bh_st.json")
    st["api_roots"] = [str(tmp / "none")]
    st["api_archive"] = str(tmp / "归档")
    st["api_picked"] = {"1.1": {"号A": str(same), "号B": str(same)}}
    tab = T.ApiTab(st, Records(tmp / "bh2.sqlite"), lambda m: None)
    tab.c_date.addItem("1.1")
    tab.c_date.setCurrentText("1.1")
    tab.load()
    _settle(tab)
    for v in tab.videos:
        v.checks = {"w": 1080, "h": 1920, "tags": [], "platform": []}
    sent = []

    class C:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, **k):
            before_publish("V")
            sent.append(title)
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}
    real = omapi.Client
    omapi.Client = C
    try:
        tab.run_publish()
        _settle(tab)
    finally:
        omapi.Client = real
    check(sent == [], "两个号手选同一个文件夹:发布前就拦住,一条都不发")
    check("已经给「号A」用了" in tab._bad_pick("1.1", "号B", str(same)) and "已发布" in tab._bad_pick("1.1", "号A", str(tmp / "归档" / "CSGO"))
          and "不发的" in tab._bad_pick("1.1", "号A", str(tmp / "x" / "10.15已发")), "手选文件夹:别的号在用的 / 归档 / 已发的都不让选")

    # 10. 挪一天时有文件没挪走:要报出来
    src = tmp / "bh_mv" / "a"
    src.mkdir(parents=True)
    (src / "x.mp4").write_bytes(b"x")
    (tmp / "bh_mv_dst" / "存在").mkdir(parents=True)        # 目标已经有(合并):一个文件一个文件挪
    real_safe = fsops.safe_move_file
    fsops.safe_move_file = lambda a, b: b                    # 模拟:挪的时候文件被改名,实际没挪走、也没报错
    try:
        n, errs = fsops.move_tree(str(tmp / "bh_mv"), str(tmp / "bh_mv_dst" / "存在"))
    finally:
        fsops.safe_move_file = real_safe
    check(errs, "挪一天:有文件没挪走就报出来,不说「挪到了」")

    # 11. 改名时封面被占着:视频照样改、照样进台账
    d = tmp / "bh_side"
    d.mkdir()
    (d / "标题 #a #b.mp4").write_bytes(b"x")
    (d / "标题 #a #b.jpg").write_bytes(b"x")
    led = topic.Ledger(tmp / "bh_led.json")
    fh = open(d / "标题 #a #b.jpg", "rb")
    try:
        mv = topic.rename_logged(str(d / "标题 #a #b.mp4"), "标题 #a", led, "t¦x¦1")
    finally:
        fh.close()
    check(os.path.basename(mv[0][1]) == "标题 #a.mp4" and led.last(), "改名时封面被占着:视频照样改、能撤销")

    # 17. 账号文件手改坏了:坏的那条跳过,不让软件打不开
    apiacc.store_path().write_text(json.dumps([{"client_id": "x"}, {"nick": "好的", "category": 1604}]), "utf-8")
    check([a["nick"] for a in apiacc.load()] == ["好的"], "账号文件里少 nick 的那条跳过")
    check(T._num("5秒", 1) == 5 and T._num(None, 3) == 3, "设置里数字写坏了:有兜底")


def test_daily_plan(tmp: Path):
    print("[每日规定条数 / 实际(按发出去的日期)/ 复制到企业微信表]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import plan
    from qe.config import Settings
    from qe.records import Records
    from gui.daily_tab import DailyTab
    st = Settings(tmp / "plan_st.json")
    check(plan.quota_of(st, "和平精英上分君") == 80 and plan.quota_of(st, "国漫解说馆z") == 50 and plan.quota_of(st, "家长小天地") == 54
          and plan.quota_of(st, "家长研习空间") == 102, "每个号每天规定条数(教育 2026-10-19 定了:小天地 54、研习空间 102)")
    check([plan.cat_total(g) for g in plan.plan(st)] == [380, 156, 200], "游戏 380 / 教育 156 / 动漫 200")
    rec = Records(tmp / "plan.sqlite")

    class V:
        date, employee, cover_kind = "10.15", "接口", ""

        def __init__(self, acc, title):
            self.account, self.title, self.path = acc, title, str(tmp / acc / f"{title}.mp4")
    day = plan.today()
    for k in range(3):
        rec.api_result(V("PUBG突围君", f"p{k}"), "已发")
    rec.api_result(V("国漫趣谈", "g1"), "已发")
    rec.api_result(V("国漫趣谈", "g2"), "没发成")
    rec.manual_published(type("E", (), {"date": "10.14", "account": "家长小天地", "employee": "张三", "title": "e1",
                                        "path": str(tmp / "e1.mp4"), "cover_kind": ""}))
    s1 = plan.summary(rec, st, day)
    check(s1["rows_rule"] == [380, 156, 200] and s1["total_rule"] == 736 and [r[2] for r in s1["rows"]] == [3, 1, 1]
          and s1["rows"][0][1] == 300 and s1["total"] == (656, 5),        # 电竞情报馆有多少发多少:这天要发的不算它的 80

          f"按发出去的日期数(素材文件夹 10.14 / 10.15 都算今天发的)-> {s1['rows']}")
    tsv = plan.as_tsv(s1).splitlines()
    check(tsv[0].split("\t") == [plan.short_day(day), "发布企鹅号视频", "游戏总发布量", "380", "3"] and tsv[3].split("\t")[2:] == ["总发布量", "736", "5"],
          "复制的文字:日期 / 工作内容 / 品类 / 规定 / 实际,和企业微信表一样")
    short = plan.short_list(s1)
    check(short[0][0] == "家长研习空间" and ("家长小天地", 54, 1) in short, f"没达标的号:差得多的排前面;教育也按号算 -> {short[:3]}")
    dt = DailyTab(st, rec)
    check("3 / 380" in dt.cards.vals["游戏"].text() and dt.t.rowCount() == 18, "每日汇总页:卡片和每个号的表")
    dt.copy_day()
    check(QApplication.clipboard().text().startswith(plan.short_day(day)), "点「复制」:剪贴板里就是那四行")


def test_login_key(tmp: Path):
    print("[登录取钥匙:从回话里读钥匙 / 挑对号 / 换上]")
    from qe import apiacc, omlogin
    data = {"response": {"code": 0}, "data": {"list": [
        {"mediaName": "CSGO战神君", "mediaId": "245", "clientID": "CID1", "clientSecret": "SEC1"},
        {"mediaName": "PUBG突围君", "mediaId": "246", "clientID": "CID2", "clientSecret": "SEC2"}]}}
    keys = omlogin.extract(data)
    check([(k["name"], k["client_id"], k["secret"]) for k in keys] == [("CSGO战神君", "CID1", "SEC1"), ("PUBG突围君", "CID2", "SEC2")],
          "回话里读出每个号的钥匙(字段名大小写不同也认)")
    check(omlogin.match(keys, "PUBG突围君")["client_id"] == "CID2" and omlogin.match(keys, "x", source_id="245")["client_id"] == "CID1"
          and omlogin.match(keys, "没有的号") is None, "按名字 / 号 ID 挑对号;挑不出来让人选")
    check("SEC1" not in omlogin.shape(data) and "clientSecret" in omlogin.shape(data), "读不到时日志里只写字段名,不写钥匙")
    apiacc.save([{"nick": "PUBG突围君", "client_id": "old", "secret": apiacc.seal("oldsec"), "category": 1604, "enabled": True}])
    check(apiacc.set_key("PUBG突围君", "CID2", "SEC2") and apiacc.find("PUBG突围君")["client_id"] == "CID2"
          and apiacc.unseal(apiacc.find("PUBG突围君")["secret"]) == "SEC2" and "SEC2" not in apiacc.store_path().read_text("utf-8"),
          "换上新钥匙:加密存")
    check("relogin" not in omlogin.OAUTH_LIST, "读钥匙不带 relogin=1(不让平台重发钥匙)")


def test_api_cover(tmp: Path):
    print("[接口封面:找同名封面 / 裁比例 / 原图不动]")
    from PIL import Image
    from qe import apicover
    d = tmp / "cover"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x")
    Image.new("RGB", (1280, 720), "red").save(d / "a.PNG")
    Image.new("RGB", (1280, 720), "blue").save(d / "a.jpg")
    check(apicover.find(str(d / "a.mp4")).endswith("a.jpg") and apicover.find(str(d / "b.mp4")) == "", "同名封面 jpg 优先;没有给空")
    check(apicover.crop_box(1280, 720, (3, 4)) == (370, 0, 910, 720) and apicover.crop_box(720, 1280, (16, 9)) == (0, 437, 720, 842),
          "从中间裁成 3:4 / 16:9")
    src = str(d / "a.jpg")
    check(apicover.prepare(src, "原样") == src and apicover.prepare(src, "不传") == "", "原样就传原图;不传给空")
    out = apicover.prepare(src, "3:4")
    with Image.open(out) as im:
        check(im.size == (540, 720) and out != src, "裁好的放临时文件夹")
    with Image.open(src) as im:
        check(im.size == (1280, 720), "原图没动")
    apicover.cleanup(out, src)
    check(not os.path.exists(out) and os.path.exists(src), "传完删临时的,原图还在")


def test_scan_any_layout(tmp: Path):
    print("[教育素材:每个人怎么放都认]")
    from qe import folders as F
    a = tmp / "scan" / "小天地"
    mk = lambda rel: ((a / rel).parent.mkdir(parents=True, exist_ok=True), (a / rel).write_bytes(b"x"))
    mk("卓金凤13/视频/卓的一条.mp4")                       # 卓金凤:视频\ + 封面\_标题.jpg
    mk("卓金凤13/封面/_卓的一条.jpg")
    mk("51/横/五一 的一条.mp4")                            # 51:原\ 横\(51 是人名,纯数字也算人)
    mk("51/横/五一 的一条.png")
    mk("51/原/五一 的一条.jpg")
    mk("梁/1/梁的一条.mp4")                                # 梁:梁/1/视频 + 封面/标题/横屏16x9.png
    _img(a / "梁/封面/梁的一条/横屏16x9.png", 320, 180)
    _img(a / "梁/封面/梁的一条/竖屏9x16.png", 180, 320)
    _img(a / "梁/封面/梁的一条/原图.png", 180, 320)
    mk("直接放 的一条.mp4")                                # 10.16:没有员工层,封面工具文件夹堆在旁边 / 套在封面\里
    mk("直接放 的一条.jpg")
    _img(a / "直接放_的一条/横屏16x9.png", 320, 180)
    mk("另一条.mp4")
    _img(a / "封面/另一条/横屏16x9.png", 320, 180)
    mk("31条（已发）/发过的.mp4")                          # 名字带「已发」的文件夹不碰
    mk("快捷方式 - 快捷方式.lnk")
    vs = {v.title: v for v in F.scan_account(str(a), "家长小天地", "10.16")}
    check(sorted(vs) == sorted(["卓的一条", "五一 的一条", "梁的一条", "直接放 的一条", "另一条"]), f"视频都翻出来,「已发」文件夹和快捷方式不算 -> {sorted(vs)}")
    check(vs["卓的一条"].employee == "卓金凤13" and vs["五一 的一条"].employee == "51" and vs["梁的一条"].employee == "梁"
          and vs["直接放 的一条"].employee == F.NO_EMP and vs["另一条"].employee == F.NO_EMP, "按第一层人名分人;直接放的算「没分人」")
    check(not vs["卓的一条"].png and vs["卓的一条"].jpg.endswith("_卓的一条.jpg"), "卓:只有带字 jpg(前面多个下划线也配得上),不当无字封面")
    check(vs["五一 的一条"].png.endswith("五一 的一条.png") and vs["五一 的一条"].jpg.endswith("五一 的一条.jpg"), "51:横里的 png 当无字封面")
    check(vs["梁的一条"].png.endswith("横屏16x9.png") and vs["梁的一条"].vpng.endswith("竖屏9x16.png"), "梁:封面工具的横屏 / 竖屏")
    check(vs["直接放 的一条"].png.endswith(os.path.join("直接放_的一条", "横屏16x9.png")) and vs["另一条"].png.endswith(os.path.join("另一条", "横屏16x9.png")),
          "10.16:封面工具文件夹在旁边 / 在封面里都配得上(空格变下划线也认)")
    check([g for g, _n in F.groups(list(vs.values()))][-1] == F.NO_EMP, "「没分人」排最后")


def test_scan_tricky(tmp: Path):
    print("[教育素材:漏不漏、多不多、分错人没有(刁钻放法)]")
    from qe import folders as F
    from qe.config import Settings
    a = tmp / "tricky" / "小天地"

    def mk(rel, data=b"x"):
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_bytes(data)
    mk("张/a/b/c/d/e/f/g/h/深.mp4")                         # 超深
    (a / "空的" / "更空").mkdir(parents=True)                # 空文件夹
    _img(a / "只有封面的人" / "只有封面.png", 64, 36)          # 只有封面没视频:不成为员工
    mk("张/大写.MP4")
    mk("张/._苹果垃圾.mp4")                                  # 苹果电脑留下的小文件,不是视频
    mk("张/Thumbs.db")
    mk("张/快捷 - 快捷方式.lnk")
    mk("张/零字节.mp4", b"")
    mk("张/表情😀🎉.mp4")
    mk("张/没脏话/干净的.mp4")                               # 脏话检测工具分出来的「没脏话」正是要发的
    mk("张/1疑似脏话/脏的.mp4")                              # 这个要跳过
    mk("张/31条（已发）/发过的.mp4")
    mk("张/31条（已发）/发过的2.mp4")
    mk("张/不重复/不重复的那条.mp4")
    mk("张/孩子不要玩手机，三招管住.mp4")                     # 封面工具按标题建的文件夹,标题里有「不要」
    _img(a / "张/封面/孩子不要玩手机，三招管住/横屏16x9.png", 320, 180)
    mk("张/孩子已发烧三天怎么办.mp4")                         # 标题里有「已发」(已发烧),里面是封面工具的图
    _img(a / "张/封面/孩子已发烧三天怎么办/横屏16x9.png", 320, 180)
    mk("10.16/李/嵌套日期.mp4")                              # 号文件夹里又套了一层日期:人还是「李」
    mk("一条放在自己标题文件夹里/一条放在自己标题文件夹里.mp4")  # <号>\<标题>\<标题>.mp4:不是人名
    mk("下载中.mp4.part")
    rep = []
    vs = {v.title: v for v in F.scan_account(str(a), "家长小天地", "10.16", rep)}
    want = ["深", "大写", "零字节", "表情😀🎉", "干净的", "不重复的那条", "孩子不要玩手机，三招管住", "孩子已发烧三天怎么办",
            "嵌套日期", "一条放在自己标题文件夹里"]
    check(sorted(vs) == sorted(want), f"该有的都有,._ / .lnk / Thumbs.db / .part / 疑似脏话 / 已发 的没有 -> {sorted(vs)}")
    check(vs["深"].employee == "张" and vs["大写"].employee == "张" and vs["干净的"].employee == "张", "超深 / 大写 .MP4 / 没脏话 里的都算张的")
    check(vs["嵌套日期"].employee == "李", f"号文件夹里套了日期:人是李 -> {vs['嵌套日期'].employee}")
    check(vs["一条放在自己标题文件夹里"].employee == F.NO_EMP, "放在自己标题文件夹里的不把标题当人名")
    check("只有封面的人" not in {v.employee for v in vs.values()} and "空的" not in {v.employee for v in vs.values()},
          "只有封面 / 空文件夹不成为员工")
    check(vs["零字节"].skip.startswith("0 字节") and not vs["深"].skip, "0 字节的列出来但写明不发")
    check(vs["孩子不要玩手机，三招管住"].png.endswith("横屏16x9.png") and vs["孩子已发烧三天怎么办"].png.endswith("横屏16x9.png"),
          "标题里有「不要 / 已发」的封面文件夹照样配得上")
    skipped = {os.path.basename(p): n for k, p, n in rep if k == "跳过"}
    check(skipped == {"1疑似脏话": 1, "31条（已发）": 2}, f"跳过的文件夹和条数报出来 -> {skipped}")
    # 路径太长(超过 260 字):文件夹打不开 → 报出来;文件夹打得开、文件太长 → 列出来写明不发
    P = "\\\\?\\"
    b = tmp / "tricky2" / "小天地"
    b.mkdir(parents=True)
    cur = str(b / "王")
    os.mkdir(cur)
    while len(cur) < 190:
        cur = os.path.join(cur, "长" * 40)
        os.mkdir(P + cur)
    cur = os.path.join(cur, "补" * (240 - len(cur) - 1))           # 文件夹正好 240 字:打得开,里面的文件超过 260
    os.mkdir(P + cur)
    open(P + os.path.join(cur, "文件名也很长" * 8 + ".mp4"), "wb").write(b"x")
    deep = os.path.join(cur, "再深一层" * 10)
    os.mkdir(P + deep)
    open(P + os.path.join(deep, "更深.mp4"), "wb").write(b"x")
    rep = []
    vs2 = F.scan_account(str(b), "家长小天地", "10.16", rep)
    long_ok = os.path.isdir(deep)                             # 这台电脑开了长路径就都读得到
    check(long_ok or (len(vs2) == 1 and "路径太长" in vs2[0].skip and any(k == "打不开" for k, _p, _n in rep)),
          f"路径太长:读不到的文件夹报「打不开」,文件写明不发 -> {[(v.title[:6], v.skip) for v in vs2]} {[k for k, _p, _n in rep]}")
    shutil.rmtree(P + str(tmp / "tricky2"), ignore_errors=True)
    # 同号同名只发一条(两个人各放一份);0 字节的那份不把好的挤掉;已经发了的那条优先留着
    mk2 = lambda p, t, e, s="": F.Video(path=p, title=t, account="家长小天地", employee=e, date="10.16", skip=s)
    x1, x2, x3 = mk2("z/同名.mp4", "同名", "卓金凤13"), mk2("y/同名.mp4", "同名 ", "卓金凤14"), mk2("w/同名.mp4", "同名", "51", "0 字节")
    check(F.mark_dups([x2, x1, x3]) == 1 and not x1.skip and x2.skip == "同一天有2条同名" and x3.skip == "0 字节",
          "同号同名:留卓金凤13 的,卓金凤14 的写明不发")
    y1, y2 = mk2("z/同名.mp4", "同名", "卓金凤13"), mk2("y/同名.mp4", "同名", "卓金凤14")
    F.mark_dups([y1, y2], prefer=lambda v: v is y2)
    check(not y2.skip and y1.skip, "已经发了 / 摆了的那条优先留着")
    other = F.Video(path="q/同名.mp4", title="同名", account="家长研习空间", employee="卓", date="10.16")
    check(F.mark_dups([mk2("z/同名.mp4", "同名", "卓"), other]) == 0, "不同号同名不算重复")
    # 号文件夹:套了一层同名日期、名字多了空格 / 多了字、两个号都像的、带「已发」的
    st = Settings(tmp / "s_tricky.json")
    r = tmp / "tricky_root"
    for rel in ("10.15/10.15/研习空间/梁/x.mp4", "10.16/ 家长小天地/x.mp4", "10.18/小天地 /x.mp4", "10.16/研习空间2/x.mp4",
                "10.16/研习空间和小天地/x.mp4", "10.16/小天地（已发）/x.mp4", "10.16/别的/x.mp4"):
        p = Path(P + str(r / rel))                           # 「小天地 」末尾带空格:Windows 只有加 \\?\ 才建得出来(苹果电脑能建)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    ad = F.account_dirs(str(r), "10.15", st)
    check(ad["家长研习空间"] == [str(r / "10.15" / "10.15" / "研习空间")] and not F.unknown_dirs(str(r), "10.15", st),
          f"10.15\\10.15\\研习空间:里面那层照样认 -> {ad}")
    ad = F.account_dirs(str(r), "10.16", st)
    check(ad["家长小天地"] == [str(r / "10.16" / " 家长小天地")] and ad["家长研习空间"] == [str(r / "10.16" / "研习空间2")],
          f"「 家长小天地」「研习空间2」认得出 -> {ad}")
    ad = F.account_dirs(str(r), "10.18", st)
    rep = []
    got = F.scan_account(ad["家长小天地"][0], "家长小天地", "10.18", rep) if ad["家长小天地"] else None
    check(got == [] and [k for k, _p, _n in rep] == ["打不开"] or got and len(got) == 1,
          f"「小天地 」末尾带空格:认得出是哪个号,读不了就报「打不开」(不悄悄漏) -> {ad} {rep}")
    check(sorted(F.unknown_dirs(str(r), "10.16", st)) == sorted(["研习空间和小天地", "小天地（已发）", "别的"]),
          f"两个号都像的 / 带已发的 / 不认识的不分给号,报出来 -> {F.unknown_dirs(str(r), '10.16', st)}")
    check(F.account_dirs(str(r), "9.9", st) == {}, "没有这天的文件夹:空")
    shutil.rmtree(P + str(r), ignore_errors=True)


def test_scan_cover_match(tmp: Path):
    print("[教育素材:封面配对不能配错(A 的视频配上 B 的封面)]")
    import time
    from qe import folders as F
    a = tmp / "covmatch"

    def mk(rel):
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_bytes(b"x")

    def im(rel, w=320, h=180, t=None):
        _img(a / rel, w, h)
        if t:
            os.utime(a / rel, (t, t))

    def scan(sub):
        return {os.path.relpath(v.path, a / sub): v for v in F.scan_account(str(a / sub), "号", "10.16")}
    rel = lambda p, sub: os.path.relpath(p, a / sub) if p else ""
    # ① 两个标题去掉标点后一样(「三个方法，」「三个方法。」):各配各的;只有一张时另一条不能拿
    mk("p1/人/三个方法，.mp4"); mk("p1/人/三个方法。.mp4"); im("p1/人/三个方法，.png"); im("p1/人/三个方法。.png")
    vs = scan("p1")
    check(vs[r"人\三个方法，.mp4"].png.endswith("三个方法，.png") and vs[r"人\三个方法。.mp4"].png.endswith("三个方法。.png"),
          "只差标点的两条:各配各的 png")
    mk("p2/人/三个方法，.mp4"); mk("p2/人/三个方法。.mp4"); im("p2/人/三个方法，.png")
    vs = scan("p2")
    check(vs[r"人\三个方法，.mp4"].png.endswith("三个方法，.png") and not vs[r"人\三个方法。.mp4"].png,
          f"只差标点、只有一张:另一条不给(宁可没封面) -> {rel(vs[r'人\三个方法。.mp4'].png, 'p2')}")
    mk("p3/三个方法，A.mp4"); mk("p3/三个方法。A.mp4"); im("p3/封面/三个方法，A/横屏16x9.png"); im("p3/封面/三个方法。A/横屏16x9.png")
    vs = scan("p3")
    check(rel(vs["三个方法，A.mp4"].png, "p3") == os.path.join("封面", "三个方法，A", "横屏16x9.png")
          and rel(vs["三个方法。A.mp4"].png, "p3") == os.path.join("封面", "三个方法。A", "横屏16x9.png"), "封面工具文件夹只差标点:各配各的")
    # ② 两个员工都有同名的:各用各的;乙没有封面不能拿甲的
    mk("p4/甲/视频/同一个标题.mp4"); im("p4/甲/封面/同一个标题/横屏16x9.png"); mk("p4/乙/同一个标题.mp4"); im("p4/乙/封面/同一个标题/横屏16x9.png")
    vs = scan("p4")
    check(rel(vs[r"甲\视频\同一个标题.mp4"].png, "p4").startswith("甲") and rel(vs[r"乙\同一个标题.mp4"].png, "p4").startswith("乙"),
          "甲、乙各有同名封面工具文件夹:各用各的(原来两条都配到乙的)")
    mk("p5/甲/同一个标题.mp4"); im("p5/甲/同一个标题.png"); mk("p5/乙/同一个标题.mp4")
    vs = scan("p5")
    check(vs[r"甲\同一个标题.mp4"].png and not vs[r"乙\同一个标题.mp4"].png, "乙的视频不拿甲的同名 png")
    mk("p5b/甲/视频/只此一条.mp4"); im("p5b/封面/只此一条/横屏16x9.png")
    check(scan("p5b")[r"甲\视频\只此一条.mp4"].png.endswith("横屏16x9.png"), "号\\封面\\ 里的(没分人)封面,员工的视频也能用")
    # ③ 前缀、全是表情、全角数字
    mk("p6/三个方法.mp4"); mk("p6/三个方法帮孩子.mp4"); im("p6/三个方法帮孩子.png")
    mk("p6/🔥🔥.mp4"); mk("p6/❤❤.mp4"); im("p6/❤❤.png")
    mk("p6/好习惯１２招.mp4"); im("p6/封面/好习惯12招/横屏16x9.png")
    vs = scan("p6")
    check(not vs["三个方法.mp4"].png, "一个标题是另一个的前缀:不配")
    check(not vs["🔥🔥.mp4"].png and vs["❤❤.mp4"].png.endswith("❤❤.png"), "全是表情的标题不互相配")
    check(vs["好习惯１２招.mp4"].png.endswith("横屏16x9.png"), "全角数字「１２」和「12」算一样")
    # ④ 封面工具文件夹里好几张:用最后改的;只有「修改 (1).png」没有横屏竖屏也认;带字 jpg 不当无字封面
    now = time.time()
    mk("p7/多版本.mp4")
    im("p7/封面/多版本/横屏16x9.png", t=now - 300); im("p7/封面/多版本/横屏16x9 (2).png", t=now - 200); im("p7/封面/多版本/横屏16x9 (3).png", t=now - 100)
    mk("p7/改过.mp4"); im("p7/封面/改过/横屏16x9.png", t=now - 300); im("p7/封面/改过/修改 (1).png", 400, 225, t=now - 100)
    mk("p7/只有修改.mp4"); im("p7/封面/只有修改/修改 (1).png"); im("p7/封面/只有修改/原图.png", 180, 320); mk("p7/封面/只有修改/_thumb.jpg")
    mk("p7/带字.mp4"); im("p7/封面/带字/原图.png"); im("p7/封面/带字/带字.jpg"); im("p7/封面/带字/竖屏9x16.png", 180, 320)
    mk("p7/人/修改作文的三个技巧.mp4"); im("p7/人/修改作文的三个技巧.png")
    vs = scan("p7")
    check(vs["多版本.mp4"].png.endswith("横屏16x9 (3).png"), f"横屏跑了几遍:用最新的 -> {os.path.basename(vs['多版本.mp4'].png)}")
    check(vs["改过.mp4"].png.endswith("修改 (1).png"), "他自己改的「修改 (1).png」比横屏晚:用修改的")
    check(vs["只有修改.mp4"].png.endswith("修改 (1).png"), "只有「修改 (1).png + 原图.png」(没横屏竖屏)也认(真实素材梁有 9 条)")
    check(not vs["带字.mp4"].png and vs["带字.mp4"].vpng.endswith("竖屏9x16.png"), "工具文件夹里的带字 jpg / 原图 不当无字横封面")
    check(vs[r"人\修改作文的三个技巧.mp4"].png.endswith("修改作文的三个技巧.png"), "标题以「修改」开头的同名 png 照样配")


def test_window_dups(tmp: Path):
    print("[界面:同号同名只摆一条、挪过地方的发过的不再摆]")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from gui.window import MainWindow
    from qe import folders as F
    from qe.config import Settings
    from qe.records import Records
    app = QApplication.instance() or QApplication([])
    root = tmp / "素材dup"
    a = root / "10.17" / "小天地"
    for rel in ("张/同名.mp4", "李/同名.mp4", "李/挪过的.mp4", "李/新的.mp4"):
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_bytes(b"x")
        _img(str(a / rel)[:-4] + ".png", 640, 360)
    rec = Records(tmp / "rdup.sqlite")
    rec.manual_published(F.Video(path=str(tmp / "早就挪走了" / "挪过的.mp4"), title="挪过的", account="家长小天地",
                                 employee="李", date="10.15"))
    st = Settings(tmp / "sdup.json")
    st["material_root"] = str(root)
    st["api_roots"] = [str(tmp / "api_none")]
    st["ai_key"] = "test"
    w = MainWindow(st, rec)
    w.c_date.setCurrentIndex(w.c_date.findData("10.17"))
    top = next(w.tree.topLevelItem(i) for i in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(i).text(0) == "家长小天地")
    kids = {top.child(k).data(0, Qt.ItemDataRole.UserRole + 3): top.child(k) for k in range(top.childCount())}
    check(kids["张"].text(1) == "1 条" and kids["李"].toolTip(1).startswith("3 条") and "发过同名 1,1 条不发" in kids["李"].toolTip(1)
          and kids["李"].text(1) == "3 条 · 1 不发 · 1 发过同名",
          f"树:李 3 条里 2 条不发 -> 张「{kids['张'].text(1)}」李「{kids['李'].text(1)}」/「{kids['李'].toolTip(1)}」")
    for it in kids.values():
        it.setCheckState(0, Qt.CheckState.Checked)
    t0 = time.time()
    while (w.cover_worker and w.cover_worker.isRunning()) and time.time() - t0 < 30:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    _acc, vids = w.next_batch()
    check(sorted((v.employee, v.title) for v in vids) == sorted([("张", "同名"), ("李", "新的")]),
          f"这批只摆 张的同名 + 李的新的 -> {[(v.employee, v.title) for v in vids]}")
    st4 = {w.table.item(i, 0).text() + "/" + w.table.item(i, 2).text(): w.table.item(i, 4).text() for i in range(w.table.rowCount())}
    check(st4["同名/李"] == "不发:同一天有2条同名" and st4["挪过的/李"] == "不发:发过同名" and st4["新的/李"] == "还没发",
          f"表里写清楚为什么不发 -> {st4}")
    check("另有 2 条不发" in w._nothing_left(), "没得摆时也说还有几条不发")
    # 处理重名(用户 2026-11-03):AI 想个意思相近的,人点「改」才改;封面跟着改名
    asked = []
    W_mod = sys.modules["gui.window"]
    from PySide6.QtWidgets import QMessageBox
    popped = []
    real = (W_mod.MainWindow.DUP_ASKER, W_mod.MainWindow._confirm, QMessageBox.information, QMessageBox.warning)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: popped.append(a[2]))
    W_mod.MainWindow.DUP_ASKER = staticmethod(lambda body, avoid: asked.append((body, list(avoid))) or body + "呀")
    W_mod.MainWindow._confirm = lambda self, *a: True
    try:
        w.table.clearSelection()
        w.edu_dupname()
    finally:
        W_mod.MainWindow.DUP_ASKER, W_mod.MainWindow._confirm = real[:2]
    names = sorted(os.listdir(a / "李"))
    check({"同名呀.mp4", "同名呀.png", "挪过的呀.mp4", "挪过的呀.png", "新的.mp4"} <= set(names) and "同名.mp4" not in names
          and len(asked) == 2 and os.path.isfile(a.parent / "小天地" / "张" / "同名.mp4"),
          f"李的两条重名的(同一天同名 / 发过同名)问了 AI、改了名,封面跟着改;张那条留着的不动 -> {names} 问了 {[x[0] for x in asked]}")
    # 按 Delete:挪进「重复删除」,软件不再读
    w.c_date.setCurrentIndex(w.c_date.findData("10.17"))
    top = next(w.tree.topLevelItem(i) for i in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(i).text(0) == "家长小天地")
    for k in range(top.childCount()):
        top.child(k).setCheckState(0, Qt.CheckState.Checked)
    app.processEvents()
    r = next(i for i, v in enumerate(w.videos) if v.title == "新的")
    w.table.clearSelection()
    w.table.selectRow(r)
    W_mod.MainWindow._confirm = lambda self, *a: True
    try:
        w.edu_delete()
    finally:
        W_mod.MainWindow._confirm = real[1]
        QMessageBox.information, QMessageBox.warning = real[2], real[3]
    check(os.path.isfile(a / "李" / "重复删除" / "新的.mp4") and os.path.isfile(a / "李" / "重复删除" / "新的.png")
          and not os.path.exists(a / "李" / "新的.mp4") and all(v.title != "新的" for v in w.videos),
          "Delete:视频连封面挪进「重复删除」(不真删),列表里没了")
    w.close()


def test_window_renamed(tmp: Path):
    print("[界面:日期 / 号文件夹被人改了名(10.14 → 10.14（101）),发过的照样算已发,不用再标手动发过]")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from gui.window import MainWindow
    from qe import folders as F
    from qe.config import Settings
    from qe.records import Records, pkey
    app = QApplication.instance() or QApplication([])
    check(F.day_of("10.14（101）") == "10.14" and F.day_of("10-14") == "10.14" and F.day_of("10.145") == ""
          and F.month_of("10.14（101）") == "10", "改了名的日期文件夹也认得出哪天、几月(挪走要用月)")
    root = tmp / "素材ren"
    a = root / "10.14（101）" / "小天地（33）"
    for rel in ("李/发过的.mp4", "李/没发的.mp4", "李/别天发过的.mp4", "李/归档过的.mp4"):
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_bytes(b"x")
        _img(str(a / rel)[:-4] + ".png", 640, 360)
    rec = Records(tmp / "rren.sqlite")
    old = tmp / "素材ren" / "10.14" / "小天地" / "李"
    for t, d in (("发过的", "10.14"), ("别天发过的", "10.12"), ("归档过的", "10.14")):
        rec.manual_published(F.Video(path=str(old / f"{t}.mp4"), title=t, account="家长小天地", employee="李", date=d))
    arch = tmp / "归档ren" / "归档过的.mp4"
    arch.parent.mkdir(parents=True)
    arch.write_bytes(b"x")
    rid = next(r["id"] for r in rec.rows() if r["title"] == "归档过的")
    rec.mark_moved(rid, str(arch))
    st = Settings(tmp / "sren.json")
    st["material_root"] = str(root)
    st["api_roots"] = [str(tmp / "api_none")]
    st["ai_key"] = "test"
    w = MainWindow(st, rec)
    w.c_date.setCurrentIndex(w.c_date.findData("10.14（101）"))
    top = next(w.tree.topLevelItem(i) for i in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(i).text(0) == "家长小天地")
    li = top.child(0)
    check("发了 1" in li.toolTip(1) and "发过同名 2" in li.toolTip(1) and li.text(1).startswith("发了 1/"), f"同一天改了名的算已发,别天的 / 归档过的照旧不发 -> {li.text(1)}")
    check(rec.status_of(str(a / "李" / "发过的.mp4")) == "已发", "记下了新位置,按路径就认得出")
    check(rec.status_of(str(arch)) == "已发", "已经挪到归档的那条,归档位置没被盖掉")
    li.setCheckState(0, Qt.CheckState.Checked)
    t0 = time.time()
    while (w.cover_worker and w.cover_worker.isRunning()) and time.time() - t0 < 30:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    _acc, vids = w.next_batch()
    check([v.title for v in vids] == ["没发的"], f"下一批只摆没发的 -> {[v.title for v in vids]}")
    n = sum(1 for r in rec.rows() if r["status"] == "已发")
    check(n == 3 and pkey(str(old / "发过的.mp4")) in {r["pkey"] for r in rec.rows()}, "没多记一笔(每日汇总不会多算)")
    w.close()


def test_at_titles(tmp: Path):
    print("[标题带 @某某 / @某平台 的不能发(16 个号算有问题,教育号跳过)]")
    from types import SimpleNamespace as NS
    from qe import checks
    check(checks.at_hits("好看的视频@腾讯游戏 #英雄联盟") == ["@腾讯游戏"] and checks.at_hits("联系＠小王 有惊喜") == ["＠小王"]
          and checks.at_hits("没有艾特的标题#英雄联盟") == [], "认得出半角 @ 和全角 ＠,没有的不乱报")
    v = NS(title="五杀集锦 @抖音小助手 #英雄联盟", checks={"w": 1080, "h": 1920, "tags": ["英雄联盟"], "platform": []}, account="CSGO战神君")
    check(any("@抖音小助手" in p and "整理标题" in p for p in checks.problems(v)), f"16 个号:带 @ 的算要处理,点「整理标题」删掉 -> {checks.problems(v)}")
    from qe import titleclean as TC
    for t, want in (("今天三角洲打大坝#443241gfsdfq123@!#!%$#fa", "今天三角洲打大坝"), ("五杀集锦 @抖音小助手 #英雄联盟", "五杀集锦 #英雄联盟"),
                    ("iPhone16ProMax评测 #数码", None), ("AK-12突击步枪改枪 #三角洲行动", None), ("S14总决赛 #LOL", None),
                    ("联系 a@b.com 吧", None), ("@某平台官方", None)):
        check(TC.clean(t) == want, f"整理标题:「{t}」→ {want!r}(实际 {TC.clean(t)!r})")
    for t, want in (("(1分44s；2分14)【三角洲行动】诶？这什么？滋一下 5.56燃烧弹", "【三角洲行动】诶？这什么？滋一下 5.56燃烧弹"),
                    ("(广告)10人口混战，真是一场酣畅淋漓的战斗", "10人口混战，真是一场酣畅淋漓的战斗"),
                    ("(1min06s处脏话)贪吃的老叔子 野排博弈论 #三角洲行动", "贪吃的老叔子 野排博弈论 #三角洲行动"),
                    ("（有广告）某某视频 #LOL", "某某视频 #LOL"), ("标题内容 (0:45；1:20) #CSGO", "标题内容 #CSGO"),
                    ("（暴力出弯）保姆级教学 #QQ飞车", None), ("（3分钟学会漂移）保姆级教学", None),
                    ("冰封列车阴间打法：速通流！（7分钟）#和平精英", None), ("当国一狼人（22660分）来峡谷打传说", None),
                    ("（违规操作解析）为什么会被封号", None), ("（待定）沙2 B洞防 rush火", None)):
        check(TC.clean(t) == want, f"剪辑备注:「{t}」→ {want!r}(实际 {TC.clean(t)!r})")
    check(TC.dirty("(广告)10人口混战") == ["(广告)"] and not TC.dirty("（暴力出弯）保姆级教学"), "剪辑备注:算要处理的(给「整理标题」用),正常括号不报")
    ad = NS(title="点击下方小黄车领取同款 #好物", checks={"w": 1080, "h": 1920, "tags": ["好物"], "platform": []}, account="CSGO战神君")
    check(any("广告" in p for p in checks.problems(ad)), "标题有广告词:算有问题(视频里八成也有广告,要人工剪)")
    TC.store().set("CSGO战神君", ad.title, True)
    check(not any("广告" in p for p in checks.problems(ad)), "人点了「剪好了」就能发(按 号 + 标题 记)")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from gui.window import MainWindow
    from qe.config import Settings
    from qe.records import Records
    root = tmp / "素材at"
    d = root / "10.20" / "小天地" / "张"
    d.mkdir(parents=True)
    for t in ("正常的一条视频标题", "带艾特的视频@某平台官方"):
        (d / f"{t}.mp4").write_bytes(b"x")
        _img(d / f"{t}.png", 640, 360)
    st = Settings(tmp / "s_at.json")
    st["material_root"] = str(root)
    st["api_roots"] = [str(tmp / "api_none")]
    st["ai_key"] = "test"
    w = MainWindow(st, Records(tmp / "r_at.sqlite"))
    w.c_date.setCurrentIndex(w.c_date.findData("10.20"))
    vs = [v for vv in w._scan.values() for v in vv]
    bad = next(v for v in vs if "艾特" in v.title)
    ok = next(v for v in vs if "正常" in v.title)
    check(not bad.skip and not ok.skip, f"教育号:带 @ 的不跳过(摆的时候在罐头里删掉 @ 那段)-> {bad.skip}")
    top = next(w.tree.topLevelItem(k) for k in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(k).text(0) == "家长小天地")
    from PySide6.QtCore import Qt
    top.child(0).setCheckState(0, Qt.CheckState.Checked)
    row = next(k for k, v in enumerate(w.videos) if "艾特" in v.title)
    check("→ 带艾特的视频" in w.table.item(row, 0).text(), f"表里写着摆的时候标题会改成什么 -> {w.table.item(row, 0).text()}")
    w.close()


def test_schedule(tmp: Path):
    print("[定时发布:定好 / 到点 / 软件没开着错过了 / 别让电脑睡]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from gui import schedule as S
    from qe.config import Settings
    st = Settings(tmp / "s_sched.json")
    said, fired = [], []
    s = S.Scheduler(st, "edu", said.append, fired.append)
    check(s.pending() is None and s.label() == "", "没定的时候什么都没有")
    import datetime as dt
    soon = (dt.datetime.strptime(S.now_str(), "%Y-%m-%d %H:%M") + dt.timedelta(hours=13, minutes=5)).strftime("%Y-%m-%d %H:%M")
    s.set(soon, "10.18")
    check(s.pending() == {"at": soon, "date": "10.18"} and "定时-edu" in S.awake_reasons() and "13 小时 5 分" in s.label(),
          f"定好了:存进设置、叫电脑别睡、写着还有多久 -> {s.label()}")
    check(Settings(tmp / "s_sched.json").get("schedules", {}).get("edu", {}).get("date") == "10.18", "重开软件还在(存在设置文件里)")
    s.tick()
    check(not fired, "没到点不发")
    sc = dict(st["schedules"])
    sc["edu"] = {"at": "2000-01-01 09:00", "date": "10.18"}
    st["schedules"] = sc
    s.tick()
    check(fired == ["10.18"] and s.pending() is None and "定时-edu" not in S.awake_reasons(), "到点了:开始发这天的,定时清掉")
    st["schedules"] = {"api": {"at": "2000-01-01 09:00", "date": "10.17"}}
    said.clear()
    s2 = S.Scheduler(st, "api", said.append, fired.append)
    check(s2.pending() is None and fired == ["10.18"] and any("没开着" in m for m in said), "到点时软件没开着:不补发,说一声、清掉")
    s.set(soon, "10.19")
    s.cancel()
    check(s.pending() is None and "定时-edu" not in S.awake_reasons(), "取消定时:清掉,电脑能睡了")


def test_prepare_retry(tmp: Path):
    print("[定时发布:没摆好的再试一次,还不行就算没摆好]")
    from types import SimpleNamespace as NS
    from qe.prepare import Runner
    r = object.__new__(Runner)
    r.log, r.stopped = (lambda m: None), (lambda: False)
    r.open_account = r.go_create = lambda *a: None
    r.upload = lambda vs: None
    r.pending_videos = lambda: []
    tries: dict[str, int] = {}

    def one(v):
        tries[v.title] = tries.get(v.title, 0) + 1
        ok = v.title == "好" or (v.title == "第二次好" and tries[v.title] == 2)
        return ok, "" if ok else "封面:尺寸过小"
    r._prepare_one = one
    vs = [NS(title=t) for t in ("好", "坏", "第二次好")]
    got = []
    res = r.prepare_batch("号", vs, on_one=lambda v, ok, why: got.append((v.title, ok)), retry=True)
    check(tries == {"好": 1, "坏": 2, "第二次好": 2}, f"没摆好的原地再试一次 -> {tries}")
    check([(v.title, ok) for v, ok, _w in res] == [("好", True), ("坏", False), ("第二次好", True)]
          and sorted(got) == sorted([("好", True), ("坏", False), ("第二次好", True)]), "每条只报一次最后的结果")
    tries.clear()
    r.prepare_batch("号", vs, retry=False)
    check(tries == {"好": 1, "坏": 1, "第二次好": 1}, "平时(人看着)不重试")
    from qe.prepare import FORBID
    check(not FORBID.search("放弃编辑"), "「放弃编辑」能点(不是发布)")
    import datetime as dt
    from qe.config import BJ
    from qe.prepare import sched_local
    check(sched_local("2026-10-18 09:00") == dt.datetime(2026, 10, 18, 9, 0) and BJ,
          f"定时框里直接填北京时间,不按电脑时钟换算(2026-10-17 换算错了一回,一定上就发了)-> {sched_local('2026-10-18 09:00')}")
    r2 = object.__new__(Runner)
    try:
        r2.schedule_all(["x"], dt.datetime(2000, 1, 1, 9, 0))
        check(False, "定在过去的不能定")
    except Exception as e:
        check("不定" in str(e), "定时时间已经过了 / 太近:不定(不然企鹅号会马上发)")
    try:
        r2._set_sched_time(dt.datetime(2026, 10, 18, 9, 3))
        check(False, "定时只能 5 分钟一档")
    except Exception as e:
        check("5 分钟" in str(e), "定时不是 5 分钟一档的直接拒绝(罐头只能选 00 / 05 … 55)")


def test_sched_edu(tmp: Path):
    print("[定时发布 · 教育号:到点勾上所有员工、一批一批发到完;没摆好的跳过;标黄没看过的不发;「全部调好了」]")
    from PySide6.QtCore import QObject, QTimer, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    import gui.window as GW
    from qe import folders as F
    from qe.adjust import Adjustments
    from qe.config import Settings
    from qe.records import Records
    root = tmp / "素材sched"
    d = root / "10.18" / "小天地" / "张"
    d.mkdir(parents=True)
    for t in ("好的一条视频", "好的二条视频", "坏的一条视频", "黄的一条视频", "黄的二条视频"):
        (d / f"{t}.mp4").write_bytes(b"x")
        _img(d / f"{t}.png", 640, 360)
    d2 = root / "10.19" / "小天地" / "李"
    d2.mkdir(parents=True)
    for t in ("定时的一条视频", "定时的二条视频", "定时坏的视频"):
        (d2 / f"{t}.mp4").write_bytes(b"x")
        _img(d2 / f"{t}.png", 640, 360)
    calls, ats = [], []

    class FakeBW(QObject):
        log = Signal(str)
        one = Signal(object, bool, str)
        finished_batch = Signal(object, str, str)

        def __init__(self, acc, vids, shots, parent=None, auto_publish=False, unattended=False, sched_at=""):
            super().__init__(parent)
            self.vids, self.unattended = vids, unattended
            calls.append(([v.title for v in vids], unattended))
            ats.append(sched_at)

        def isRunning(self):
            return False

        def stop(self):
            pass

        def start(self):
            def go():
                res = []
                for v in self.vids:
                    ok = "坏" not in v.title
                    self.one.emit(v, ok, "" if ok else "封面:尺寸过小")
                    res.append((v, ok, "" if ok else "封面:尺寸过小"))
                self.finished_batch.emit(res, "", "ok" if any(o for _v, o, _w in res) else "none")
            QTimer.singleShot(0, go)

    def fake_decide(v):
        v.cover, v.cover_kind, v.cover_why, v.plan = v.png, "png", "测试", {}
        v.warn = "黄" in v.title
    real = (GW.BatchWorker, GW.C.decide, GW.C.note_wide, QMessageBox.information)
    boxes = []
    GW.BatchWorker, GW.C.decide, GW.C.note_wide = FakeBW, fake_decide, (lambda v: None)
    QMessageBox.information = staticmethod(lambda _p, t, x, *a, **k: boxes.append(x))
    try:
        rec = Records(tmp / "r_sched.sqlite")
        Adjustments(tmp / "封面调整.json").set_ok(str(d / "黄的一条视频.mp4"), str(d / "黄的一条视频.png"))
        st = Settings(tmp / "s_sched_edu.json")
        st["material_root"] = str(root)
        st["api_roots"] = [str(tmp / "api_none")]
        st["ai_key"] = "test"
        st["batch_size"] = 2
        w = GW.MainWindow(st, rec)
        w._sched_fire("10.18")
        t0 = time.time()
        while (w._unattended or not boxes) and time.time() - t0 < 60:
            app.processEvents()
            time.sleep(0.05)
        sent = sorted(v.title for v in w.videos if rec.status_of(v.path) == "已发")
        check(all(u for _t, u in calls) and len(calls) >= 2, f"到点后自己一批一批摆(没人看着的模式)-> {calls}")
        check(sent == ["好的一条视频", "好的二条视频", "黄的一条视频"],
              f"能发的都发了(标黄但点过「全部调好了」的也发)-> {sent}")
        check(not any("黄的二条" in t for ts, _u in calls for t in ts), "还标黄、人没看过的不摆")
        check(sum(1 for ts, _u in calls for t in ts if "坏" in t) == 1, "没摆好的跳过,不反复摆")
        check(not w._unattended and boxes and "这次发了 3 条" in boxes[-1] and "坏的一条视频" in boxes[-1] and "黄的二条视频" in boxes[-1],
              f"发完写总结:发了几条、哪几条没发 -> {boxes[-1][:120] if boxes else ''}")
        from gui.schedule import awake_reasons
        check(not any(x.startswith("定时-edu") for x in awake_reasons()), "发完了电脑能睡了")
        y2 = next(v for v in w.videos if v.title == "黄的二条视频")
        w._ask = lambda *a, **k: True
        w.all_covers_ok()
        check(not y2.warn and Adjustments(tmp / "封面调整.json").is_ok(y2.path, y2.cover), "「全部调好了」:标黄的不再标黄,记在硬盘上")
        # 罐头自带的定时(用户 2026-10-17):现在就摆,每批「全部定时发布」到同一个北京时间
        calls.clear()
        ats.clear()
        boxes.clear()
        w._sched_fire("10.19", "2026-10-19 09:00")
        t0 = time.time()
        while (w._unattended or not boxes) and time.time() - t0 < 60:
            app.processEvents()
            time.sleep(0.05)
        rows = {r["title"]: r for r in rec.rows("10.19")}
        check(ats and all(a == "2026-10-19 09:00" for a in ats), f"每批都定时到同一个点 -> {ats}")
        check(rows["定时的一条视频"]["status"] == "已发" and rows["定时的一条视频"]["published_at"] == "2026-10-19 09:00:00"
              and "罐头定时发布" in rows["定时的一条视频"]["note"] and (rows.get("定时坏的视频") or {}).get("status") != "已发",
              "定好的记成已发,发布时间 = 定的那个点(每日汇总算到那天);没摆好的不算")
        check(boxes and "定好了 2 条" in boxes[-1] and "电脑可以关" in boxes[-1] and not w._sched_at, f"写总结:定好了几条、电脑能关 -> {boxes[-1][:80] if boxes else ''}")
        w.close()
    finally:
        GW.BatchWorker, GW.C.decide, GW.C.note_wide, QMessageBox.information = real


def test_sched_api(tmp: Path):
    print("[定时发布 · 16 个号:到点不弹框直接发;没有能发的就结束]")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    root = tmp / "api_sched"
    (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18").mkdir(parents=True)
    for f in ("s1.mp4", "s2.mp4"):
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18" / f).write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_api_sched.json")
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "发布sched" / "{date}")
    st["api_interval"] = 0
    rec = Records(tmp / "rec_api_sched.sqlite")
    logs = []
    tab = T.ApiTab(st, rec, logs.append)
    sent = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, **k):
            if before_publish:
                before_publish("V")
            sent.append(title)
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}

    def nope(*a, **k):
        raise AssertionError("定时发布不该弹框问")
    real = (omapi.Client, T.ask, QMessageBox.question, QMessageBox.information, QMessageBox.warning)
    omapi.Client, T.ask, QMessageBox.question = FakeClient, nope, staticmethod(nope)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: None)
    try:
        tab._sched_fire("10.18")                    # 假视频读不出来 → 检查有问题 → 没有能发的
        t0 = time.time()
        while tab._auto and time.time() - t0 < 60:
            app.processEvents()
            time.sleep(0.05)
        check(not tab._auto and not sent and "没有能发的" in tab.logbox.toPlainText(), "到点了:先等自动检查,没有能发的就结束")
        for v in tab.videos:
            v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
        tab.k_bad.setChecked(True)                  # 定时发布不管「只看有问题的」/ 选中
        tab._auto = "等检查"
        tab._auto_poll()
        if tab.job:
            tab.job.wait()
        app.processEvents()
        check(sorted(sent) == ["s1", "s2"] and not tab._auto, f"到点不弹框直接发全部 -> {sent}")
    finally:
        omapi.Client, T.ask, QMessageBox.question, QMessageBox.information, QMessageBox.warning = real


def test_api_wm(tmp: Path):
    print("[高级检查:查水印(记在硬盘上)/ 普通检查过的只查水印 / 右键「没水印」能发]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, checks, watermark, wmstore
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    root = tmp / "apiwm" / "游戏视频" / "CSGO--CSGO战神君" / "10.15"
    root.mkdir(parents=True)
    for f in ("w1.mp4", "w2.mp4"):
        (root / f).write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_wm.json")
    st["api_roots"] = [str(tmp / "apiwm" / "游戏视频")]
    tab = T.ApiTab(st, Records(tmp / "rec_wm.sqlite"), lambda m: None)
    tab.c_date.setCurrentText("10.15")
    tab.load()
    _settle(tab)
    for v in tab.videos:                               # 假视频:当成竖屏的好视频
        v.checks.update(bad_read=False, landscape=False, squarish=False, w=1080, h=1920)
        tab._remember_check(v)
    calls = []

    def fake_detect(path, ff, info, stop=None, **k):
        calls.append(os.path.basename(path))
        if path.endswith("w1.mp4"):
            return {"hits": [{"label": "B站", "kind": "logo", "score": 0.9, "box": [600, 40, 60, 30],
                              "ratio": [0.83, 0.03, 0.08, 0.02], "where": "右上角", "t": 1.0}], "shot": "", "frames": 10}
        return {"hits": [], "shot": "", "frames": 10}
    real_detect, real_check = watermark.detect, checks.check_one
    normal = []
    watermark.detect = fake_detect
    checks.check_one = lambda v, *a, **k: normal.append(v.title) or real_check(v, *a, **k)
    try:
        tab.run_check(deep=True)
        _settle(tab)
        check(sorted(calls) == ["w1.mp4", "w2.mp4"] and not normal, "高级检查:普通检查过的只查水印,不再过一遍普通检查")
        i1 = next(i for i, v in enumerate(tab.videos) if v.title == "w1")
        i2 = next(i for i, v in enumerate(tab.videos) if v.title == "w2")
        check("B站水印(右上角)" in checks.problems(tab.videos[i1]) and not tab._can_send(i1) and tab._can_send(i2),
              "查到水印:标「B站水印(右上角)」,不发;没水印的能发")
        calls.clear()
        tab.load()
        _settle(tab)
        tab.run_check(deep=True)
        _settle(tab)
        i1 = next(i for i, v in enumerate(tab.videos) if v.title == "w1")
        check(not calls and not tab._can_send(i1), "关了再开 / 刷新:水印结果记在硬盘上,不再查,照样拦着")
        tab.set_wm_ok(i1, True)
        check(tab._can_send(i1) and wmstore.get(tab.videos[i1].path)["ok"], "右键「没水印 / 不用管」:能发了,也记在硬盘上")
        tab.set_wm_ok(i1, False)
        check(not tab._can_send(i1), "「其实有水印」:又不发了")
    finally:
        watermark.detect, checks.check_one = real_detect, real_check
    f = str(root / "w2.mp4")
    wmstore.put(f, {"hits": [{"label": "x"}], "shot": ""})
    wmstore.set_ok(f, True)
    (root / "w2.mp4").write_bytes(b"xy")              # 文件变了(模糊过 / 换了一条):当没查过
    check(wmstore.get(f) is None, "文件变了:水印结果作废,要重查")
    from gui.widgets import MenuButton
    b = MenuButton("检查")
    b.add("普通检查", lambda: None)
    b.add("高级检查(再查水印)", lambda: None)
    check([a.text() for a in b.menu().actions()] == ["普通检查", "高级检查(再查水印)"], "检查按钮带下拉:普通 / 高级")


def test_edu_wm(tmp: Path):
    print("[教育号查水印:查到的标黄不摆、右键「没水印」能摆、查过的不再查]")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from gui.window import MainWindow
    from qe import watermark, wmstore
    from qe.config import Settings
    from qe.records import Records
    app = QApplication.instance() or QApplication([])
    a = tmp / "素材wm" / "10.16" / "小天地"
    for rel in ("有水印.mp4", "干净的.mp4"):
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_bytes(b"x")
        _img(str(a / rel)[:-4] + ".png", 640, 360)
    st = Settings(tmp / "swm.json")
    st["material_root"] = str(tmp / "素材wm")
    st["api_roots"] = [str(tmp / "api_none")]
    st["ai_key"] = "test"
    w = MainWindow(st, Records(tmp / "rwm.sqlite"))

    def wait():
        t0 = time.time()
        while ((w.cover_worker and w.cover_worker.isRunning()) or (w.wm_worker and w.wm_worker.isRunning())) and time.time() - t0 < 30:
            app.processEvents()
            time.sleep(0.05)
        app.processEvents()
    w.c_date.setCurrentIndex(w.c_date.findData("10.16"))
    top = w.tree.topLevelItem(next(i for i in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(i).text(0) == "家长小天地"))
    top.child(0).setCheckState(0, Qt.CheckState.Checked)
    wait()
    calls = []

    def fake(path, ff, info, stop=None, **k):
        calls.append(os.path.basename(path))
        hit = [{"label": "抖音", "kind": "logo", "score": 0.9, "box": [10, 10, 40, 20], "ratio": [0.01, 0.01, 0.05, 0.02],
                "where": "左上角", "t": 1.0}] if "有水印" in path else []
        return {"hits": hit, "shot": "", "frames": 5}
    real = watermark.detect
    watermark.detect = fake
    try:
        w.run_wm()
        wait()
        check(sorted(calls) == ["干净的.mp4", "有水印.mp4"], "查水印:勾上的都查")
        i = next(k for k, v in enumerate(w.videos) if v.title == "有水印")
        check("有水印" in w.table.item(i, 4).text() and "抖音" in w.table.item(i, 4).text(), "查到的:状态写「有水印:抖音水印(左上角)」")
        _acc, vids = w.next_batch()
        check([v.title for v in vids] == ["干净的"], "摆下一批:有水印的不摆")
        w.table.selectRow(i)
        w.set_wm_ok(True)
        _acc, vids = w.next_batch()
        check(sorted(v.title for v in vids) == ["干净的", "有水印"], "右键「没水印,能摆」:能摆了")
        calls.clear()
        w._load_tree()
        wait()
        top = w.tree.topLevelItem(next(i for i in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(i).text(0) == "家长小天地"))
        if top.child(0).checkState(0) != Qt.CheckState.Checked:
            top.child(0).setCheckState(0, Qt.CheckState.Checked)
            wait()
        w.run_wm()
        wait()
        check(not calls, "查过的(记在硬盘上)不再查")
    finally:
        watermark.detect = real
    w.close()


def test_blur(tmp: Path):
    print("[模糊水印:只糊出现的那几段、原片进「水印原片」、教育号不会把原片再读进来、16 个号糊完能发]")
    import subprocess
    from qe import blur, folders as F, vertical, wmstore
    ff = vertical.ffmpeg_path()
    check(blur._enable([[0, 3], [10, 12.5]]) == ":enable='between(t,0.00,3.00)+between(t,10.00,12.50)'" and blur._enable([]) == "",
          "只在水印出现的那几段糊")
    px, py, pw, ph = blur.pixel_box([0.8, 0.02, 0.15, 0.03], 1080, 1920)
    check(px % 2 == 0 and py % 2 == 0 and px + pw <= 1080 and py + ph <= 1920 and pw > 0.15 * 1080, "框放宽一点、不出界、偶数")
    if not ff:
        print("  (没有 ffmpeg,跳过真糊)")
        return
    d = tmp / "blur" / "10.16" / "小天地"
    d.mkdir(parents=True)
    src = d / "一条.mp4"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=10:duration=3",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    new, orig = blur.blur(str(src), [{"ratio": [0.6, 0.02, 0.3, 0.05], "spans": [[0, 1.5]]}], ff)
    check(os.path.normcase(new) == os.path.normcase(str(src)) and os.path.isfile(orig)
          and os.path.basename(os.path.dirname(orig)) == "水印原片" and vertical.probe(new, ff)["w"] == 360,
          "糊好的放回原名,原片进「水印原片」")
    check([v.title for v in F.scan_account(str(d), "家长小天地", "10.16")] == ["一条"], "教育号不会把「水印原片」里的原片再当成一条")
    wmstore.put(new, {"hits": [{"label": "B站", "ratio": [0.6, 0.02, 0.3, 0.05]}]}, ok=True, blurred=True)
    w = wmstore.get(new)
    check(w["blurred"] and not wmstore.blocks(w), "糊过的记下来,不再拦")


def test_ads(tmp: Path):
    print("[查口播广告 / 剪掉广告:挨着的广告句连成一段、只拦很像广告的、剪完变短、原片进「广告原片」]")
    import subprocess
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import ads, apiacc, asr, checks, cut, vertical, wmstore
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    kw = ads.split_keywords(ads.DEFAULT_KEYWORDS)
    sents = [{"start": 1, "end": 3, "text": "这把枪很好用,"}, {"start": 40, "end": 42, "text": "关注我,"},
             {"start": 42.5, "end": 45, "text": "点击下方链接领取福利。"}, {"start": 60, "end": 61, "text": "限时活动开始了"}]
    g = ads.groups(sents, kw)
    check(len(g) == 1 and g[0]["start"] == 40 and g[0]["end"] == 45, "「关注我 + 点击下方链接领取」连成一段;单独一个「限时」不算")
    check(asr.sentences(["一", "个", "，", "好", "。"], [0.1, 0.2, 0.3, 0.5, 0.6], 10) ==
          [{"start": 10.1, "end": 10.5, "text": "一个，"}, {"start": 10.5, "end": 10.8, "text": "好。"}], "每个字的时间 → 一句一句几秒到几秒")
    check(cut.spans_to_cut([{"start": 5, "end": 6}, {"start": 6.2, "end": 7}], 20) == [(4.7, 7.3)], "要剪的段:前后多 0.3 秒、挨着的并起来")
    ff = vertical.ffmpeg_path()
    if ff:
        d = tmp / "adcut"
        d.mkdir()
        src = d / "广告.mp4"
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x568:rate=10:duration=6",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-shortest", "-pix_fmt", "yuv420p", str(src)], check=True)
        new, orig, gone = cut.cut(str(src), [{"start": 2, "end": 3.4}], ff)
        dur = vertical.probe(new, ff)["dur"]
        check(abs(gone - 2.0) < 0.05 and 3.6 < dur < 4.4 and os.path.basename(os.path.dirname(orig)) == "广告原片",
              f"剪掉 2 秒:6 秒变 {dur:.1f} 秒,原片进「广告原片」")
    root = tmp / "apiad" / "游戏视频" / "CSGO--CSGO战神君" / "10.15"
    root.mkdir(parents=True)
    for f in ("a1.mp4", "a2.mp4"):
        (root / f).write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_ad.json")
    st["api_roots"] = [str(tmp / "apiad" / "游戏视频")]
    tab = T.ApiTab(st, Records(tmp / "rec_ad.sqlite"), lambda m: None)
    tab.c_date.setCurrentText("10.15")
    tab.load()
    _settle(tab)
    for v in tab.videos:
        v.checks.update(bad_read=False, landscape=False, squarish=False, w=1080, h=1920)
        tab._remember_check(v)

    class FakeT:
        n = 0

        def transcribe(self, path, stop=None):
            FakeT.n += 1
            return sents if path.endswith("a1.mp4") else [{"start": 1, "end": 2, "text": "今天打一把排位。"}]
    real_shared, real_dir = asr.shared, asr.model_dir
    asr.shared, asr.model_dir = (lambda ff: FakeT()), (lambda: "x")
    try:
        tab.run_ads()
        _settle(tab)
        i1 = next(i for i, v in enumerate(tab.videos) if v.title == "a1")
        i2 = next(i for i, v in enumerate(tab.videos) if v.title == "a2")
        check(any(p.startswith("口播广告 1 处(0:40") for p in checks.problems(tab.videos[i1])) and not tab._can_send(i1)
              and tab._can_send(i2), "查到口播广告:标「口播广告 1 处(0:40…)」不发;没广告的能发")
        FakeT.n = 0
        tab.load()
        _settle(tab)
        tab.run_ads()
        _settle(tab)
        check(FakeT.n == 0, "查过的(记在硬盘上)不再转文字")
        i1 = next(i for i, v in enumerate(tab.videos) if v.title == "a1")
        tab.set_ad_ok(i1, True)
        check(tab._can_send(i1) and wmstore.ADS.get(tab.videos[i1].path)["ok"], "右键「不是广告,能发」:能发了")
    finally:
        asr.shared, asr.model_dir = real_shared, real_dir


def test_cover_cache_unique(tmp: Path):
    print("[封面缓存按完整路径分:每条都叫「横屏16x9.png」也不会串]")
    from qe import cover as C
    a = C.cache_file("2.35专用封面", str(tmp / "甲" / "横屏16x9.png"), "_2.35_AI.jpg")
    b = C.cache_file("2.35专用封面", str(tmp / "乙" / "横屏16x9.png"), "_2.35_AI.jpg")
    check(a != b and a.name.startswith("横屏16x9_") and a.name.endswith("_2.35_AI.jpg"), "两条视频的同名封面:AI 扩图各存各的")
    check(C.cache_file("放大的封面", str(tmp / "甲" / "横屏16x9.png"), "_x.jpg") != C.cache_file("放大的封面", str(tmp / "乙" / "横屏16x9.png"), "_x.jpg"),
          "放大的封面也各存各的")


def test_cover_dialog_src(tmp: Path):
    print("[封面预览:显示封面的标题和位置、对不上标红、自己换封面 / 用回自动的]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from gui.cover_dialog import CoverDialog
    from qe import cover as C
    from qe.adjust import Adjustments
    from qe.folders import Video
    d = tmp / "cdlg"
    _img(d / "封面" / "别的视频" / "横屏16x9.png", 640, 360)
    _img(d / "我选的.png", 640, 360)
    (d / "这条视频.mp4").write_bytes(b"x")
    v = Video(path=str(d / "这条视频.mp4"), title="这条视频", account="号", employee="甲", date="10.16",
              png=str(d / "封面" / "别的视频" / "横屏16x9.png"))
    adj = Adjustments(tmp / "adj_dlg.json")
    adj.use_own(v)
    C.decide(v)
    dlg = CoverDialog([v], 0, adj)
    t = dlg.lab_src.text()
    check("别的视频" in t and "对不上" in t and "横屏16x9.png" in t, "封面标题 = 封面工具的文件夹名;和视频标题对不上标红;写位置")
    dlg.set_cover(str(d / "我选的.png"))
    check(v.cover.endswith("我选的.png") and "你自己换的" in dlg.lab_src.text() and adj.own_cover(v.path).endswith("我选的.png"),
          "更换封面:用你选的,记下来")
    v2 = Video(path=v.path, title=v.title, account="号", employee="甲", date="10.16", png=str(d / "封面" / "别的视频" / "横屏16x9.png"))
    check(Adjustments(tmp / "adj_dlg.json").use_own(v2) and v2.png.endswith("我选的.png"), "关了再开:还是用你选的")
    dlg.set_cover("")
    check(v.cover.endswith("横屏16x9.png") and not adj.own_cover(v.path), "用回自动配的")
    # 用户 2026-10-19:员工忘了处理封面 → 复制封面图 / 去豆包处理 / 打开封面文件夹
    from PySide6.QtGui import QDesktopServices
    import subprocess
    opened, ran = [], []
    real = (QDesktopServices.openUrl, subprocess.Popen)
    QDesktopServices.openUrl = staticmethod(lambda u: opened.append(u.toString()) or True)
    subprocess.Popen = lambda args, *a, **k: ran.append(args)
    try:
        QApplication.clipboard().clear()
        check(dlg.copy_cover() and QApplication.clipboard().image().width() == 640, "复制封面图:剪贴板里是这张图")
        QApplication.clipboard().clear()
        dlg.to_doubao()
        check(opened == [dlg.DOUBAO] and QApplication.clipboard().image().width() == 640 and "Ctrl+V" in dlg.lab_toast.text(),
              f"去豆包处理:先复制封面,再在浏览器里打开豆包 -> {opened}")
        dlg.open_cover_dir()
        check(ran and ran[-1][0] == "explorer" and ran[-1][-1].endswith("横屏16x9.png"), f"打开封面文件夹并选中它 -> {ran}")
        dlg._src_path = ""
        QApplication.clipboard().clear()
        check(not dlg.copy_cover() and QApplication.clipboard().image().isNull(), "没有封面:复制不了,写一句")
    finally:
        QDesktopServices.openUrl, subprocess.Popen = real
    dlg.close()


def test_api_direct(tmp: Path):
    print("[接口发直连企鹅号(不走代理,快 7 倍);直连不通才走代理]")
    import requests
    from qe import omapi

    class R:
        def __init__(self, j):
            self.j, self.status_code = j, 200

        def json(self):
            return self.j

    class S:
        trust_env = True

        def __init__(self):
            self.tries = []

        def post(self, url, **kw):
            self.tries.append(self.trust_env)
            if not self.trust_env:
                raise requests.ConnectionError("直连不通")
            return R({"code": "0", "data": {"access_token": "T", "expires_in": 7200}})
    s = S()
    c = omapi.Client("a", "b", session=s)
    check(s.trust_env is False, "默认直连(不用电脑上的代理)")
    check(c.token() == "T" and s.tries == [False, True] and s.trust_env is True, "直连不通:换 token 时改走代理再试一次")


def test_api_cover_pic(tmp: Path):
    print("[接口发带封面:先传图拿地址、发布带 cover_pic;平台不收封面就不带封面再发一次]")
    from qe import omapi

    class R:
        def __init__(self, j):
            self.j, self.status_code = j, 200

        def json(self):
            return self.j

    class S:
        def __init__(self, reject_cover=False):
            self.bodies, self.reject = [], reject_cover

        def post(self, url, **kw):
            return R({"code": "0", "data": {"access_token": "T", "expires_in": 7200}})

        def request(self, method, url, **kw):
            path = url.split("api.om.qq.com")[1]
            if path == "/video/clientuploadready":
                self.size = kw["json"]["size"]
                return R({"code": "0", "data": {"transaction_id": "U1"}})
            if path == "/video/clientuploadtrunk":
                return R({"code": "0", "data": {"start_offset": self.size - 1, "end_offset": self.size - 1}})
            if path == "/transaction/infoclient":
                return R({"code": "0", "data": {"vid": "V7", "transaction_status": "成功"}})
            if path == "/articlev2/clientpubvideo":
                self.bodies.append(kw["json"])
                if self.reject and "cover_pic" in kw["json"]:
                    return R({"code": "40002", "msg": "invalid ClientPubVideoReq.CoverPic: value must be absolute"})
                return R({"code": "0", "data": {"transaction_id": "P1", "article_id": "A9"}})
            return R({"code": "-1"})
    f = tmp / "cv.mp4"
    f.write_bytes(b"0123456789")
    real_sleep = omapi.time.sleep
    omapi.time.sleep = lambda x: None
    try:
        s1 = S()
        r = omapi.Client("a", "b", session=s1).send(str(f), "t", 1604, cover="x.jpg", cover_upload=lambda img: "https://inews.gtimg.com/om_bt/abc")
        check(s1.bodies[0].get("cover_pic") == "https://inews.gtimg.com/om_bt/abc" and r["cover"] == "传了", "发布带上 cover_pic(传图拿到的地址)")
        s2 = S(reject_cover=True)
        r = omapi.Client("a", "b", session=s2).send(str(f), "t", 1604, cover="x.jpg", cover_upload=lambda img: "https://x/y")
        check(len(s2.bodies) == 2 and "cover_pic" not in s2.bodies[1] and r["article_id"] == "A9" and r["cover"].startswith("平台不收"),
              "平台不收封面:不带封面再发一次(视频照样发出去)")
        s3 = S()

        def boom(img):
            raise RuntimeError("没登录")
        r = omapi.Client("a", "b", session=s3).send(str(f), "t", 1604, cover="x.jpg", cover_upload=boom)
        check("cover_pic" not in s3.bodies[0] and r["cover"].startswith("没传上"), "封面传不上:照样发,平台自己截")
    finally:
        omapi.time.sleep = real_sleep


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
    st["api_roots"] = [str(tmp / "api_none")]
    st["ai_key"] = "test"
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
    # 用户 2026-11-09:「我按错了 没发没发…居然还不能弄回来」→ 右键「不算已发」
    r0, r1 = w.videos.index(vids[0]), w.videos.index(vids[1])
    w.rec.manual_published(vids[1])
    day = w.rec.sent_row(vids[1].path)["published_at"][:10]
    n0 = w.rec.sent_on(day).get("家长研习空间", 0)
    w.table.clearSelection()
    w.table.selectRow(r0)
    from PySide6.QtCore import QItemSelectionModel
    w.table.selectionModel().select(w.table.model().index(r1, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    w.table.selectionModel().select(w.table.model().index(2 if 2 not in (r0, r1) else 3, 0),
                                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    check(len(w._sent_sel()) == 2, f"选中 3 条、2 条是已发:菜单写 2 条 -> {len(w._sent_sel())}")
    asked = []
    w._ask = lambda *a, **k: asked.append(a) or False
    w.unmark_sent()
    check(asked and w.rec.status_of(vids[0].path) == "已发", "点了「先不」:不改")
    w._ask = lambda *a, **k: True
    w.unmark_sent()
    check(w.rec.status_of(vids[0].path) == "" and w.rec.status_of(vids[1].path) == "", "改回还没发:这批发好了的、手动标的都改回来")
    check(w.rec.sent_on(day).get("家长研习空间", 0) == n0 - 2 and w.table.item(r0, 4).text() != "已发", "每天的已发数跟着减,行里不写已发")
    check(not [r for r in w.rec.rows() if r["status"] == "已发" and r["path"] in (vids[0].path, vids[1].path)]
          and w.rec.conn.execute("SELECT COUNT(*) FROM posts WHERE status='作废' AND note LIKE '%按错了%'").fetchone()[0] == 2,
          "记录不删,改成作废、备注写着按错了")
    acc, vids3 = w.next_batch()
    check(vids[0] in vids3, "改回来的下一批还会摆")
    w.close()


def test_window_scan(tmp: Path):
    print("[界面:号文件夹整个翻(没分人 / 有人名)、勾选三元组、缓存、刷新、发了几条]")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from gui.window import MainWindow
    from qe import folders as F
    from qe.config import Settings
    from qe.records import Records
    app = QApplication.instance() or QApplication([])
    root = tmp / "素材2"
    a = root / "10.16" / "小天地"
    for rel in ("直接放一.mp4", "直接放二.mp4", "张三/视频/张三的一.mp4"):
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_bytes(b"x")
        _img(str(a / rel)[:-4] + ".png", 640, 360)
    st = Settings(tmp / "sw2.json")
    st["material_root"] = str(root)
    st["api_roots"] = [str(tmp / "api_none")]
    st["ai_key"] = "test"
    w = MainWindow(st, Records(tmp / "rw2.sqlite"))

    def wait():
        t0 = time.time()
        while (w.cover_worker and w.cover_worker.isRunning()) and time.time() - t0 < 30:
            app.processEvents()
            time.sleep(0.05)
        app.processEvents()

    def kid(emp):
        top = next(w.tree.topLevelItem(i) for i in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(i).text(0) == "家长小天地")
        return next((top.child(k) for k in range(top.childCount()) if top.child(k).data(0, Qt.ItemDataRole.UserRole + 3) == emp), None)
    w.c_date.setCurrentIndex(w.c_date.findData("10.16"))
    zs, no = kid("张三"), kid(F.NO_EMP)
    check(zs is not None and no is not None and zs.text(1) == "1 条" and no.text(1) == "2 条", "树:张三 1 条、没分人 2 条")
    check(os.path.normcase(zs.data(0, Qt.ItemDataRole.UserRole)) == os.path.normcase(str(a / "张三"))
          and os.path.normcase(no.data(0, Qt.ItemDataRole.UserRole)) == os.path.normcase(str(a)), "打开文件夹:张三 → 张三\\,没分人 → 号文件夹")
    no.setCheckState(0, Qt.CheckState.Checked)
    wait()
    check(w.checked_dirs() == [("家长小天地", str(a), F.NO_EMP)], f"checked_dirs = (号, 号文件夹, 员工) -> {w.checked_dirs()}")
    check(w.table.rowCount() == 2 and all(v.employee == F.NO_EMP for v in w.videos), "勾没分人:只列直接放的 2 条,张三的不混进来")
    # 软件开着时员工加了一条:重新勾不重新翻(缓存),「刷新」才看得到,勾选还在
    (a / "直接放三.mp4").write_bytes(b"x")
    no.setCheckState(0, Qt.CheckState.Unchecked)
    no.setCheckState(0, Qt.CheckState.Checked)
    wait()
    check(w.table.rowCount() == 2, "重新勾:用缓存,不翻文件夹")
    w._load_dates()                                   # 「刷新」
    wait()
    no = kid(F.NO_EMP)
    check(no.checkState(0) == Qt.CheckState.Checked and w.table.rowCount() == 3 and "1 条没无字封面" in no.toolTip(1) and no.text(1) == "3 条 · 1 没封面",
          f"刷新:新加的看得到、勾着的还勾着 -> {w.table.rowCount()} 行,{no.text(1)}")
    # 标成已发:树上「发了 N」跟着变
    w.table.selectRow(0)
    w.mark_manual()
    check("发了 1" in kid(F.NO_EMP).text(1), f"标成已发后树上写「发了 1」-> {kid(F.NO_EMP).text(1)}")
    check(w.rec.rows("10.16")[0]["employee"] == F.NO_EMP, "记录里员工 = 没分人")
    # 摆之前文件被改名了(缓存里还是旧路径):挡下来,不开始摆
    import gui.window as GW
    real_bw, started = GW.BatchWorker, []
    GW.BatchWorker = lambda *a_, **k_: started.append(1) or (_ for _ in ()).throw(RuntimeError("不该开始摆"))
    try:
        acc, vids = w.next_batch()
        os.rename(vids[0].path, vids[0].path + ".bak")
        w.start_batch()
        check(not started and not w.batch_id, "这批里有文件找不到了:不开始摆,叫人刷新")
        os.rename(vids[0].path + ".bak", vids[0].path)
    finally:
        GW.BatchWorker = real_bw
    # 换日期:勾选不带过去
    w.c_date.setCurrentIndex(0)
    check(not w.checked_dirs() and w.table.rowCount() == 0, "换日期:什么都不勾")
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
    # 脸在图最下面:已移除 AI 扩图,一律本地切头顶(不再走 AI)
    low2 = {"cx": 0.5, "cy": 0.9, "faces": [[0.4, 0.7, 0.12, 0.25, 0.8]]}
    check(C.wide_mode(1600, 900, low2)[0] == "crop" and not C.needs_wide(1600, 900, low2), "已取消 AI 扩图:脸贴底下也走本地切框")
    check(C.wide_mode(1600, 900, dict(low2, no_ai=True))[0] == "crop", "no_ai=True 同样走切框")
    check(C.wide_mode(1600, 900, dict(big, ai235=True))[0] == "crop", "即使传 ai235=True 也不再走 AI 扩图")
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


def test_group(tmp: Path):
    print("[两个人挨着:框得下就框两个人中间]")
    from qe import cover as C
    # 2848×1600,小孩脸在 0.33,大人脸在 0.55(像用户截图那张)
    kid, mom = [0.30, 0.25, 0.07, 0.13, 0.30], [0.52, 0.12, 0.08, 0.15, 0.17]
    plan = dict(C.focus_of([mom]), faces=[mom], all=[kid, mom])
    for tag, r in (("3:4", 0.75), ("1:1", 1.0)):
        x, y, w, h = C.crop_rect(2848, 1600, r, plan)
        check(x <= (kid[0] - 0.02) * 2848 and x + w >= (mom[0] + mom[2] + 0.02) * 2848, f"{tag}:两个人都在框里")
    x, y, w, h = C.crop_rect(2848, 1600, 9 / 16, plan)
    check(x <= mom[0] * 2848 and x + w >= (mom[0] + mom[2]) * 2848, "9:16 太窄框不下两个人:对准脸大的那个")


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


def test_wm_detect_unit(tmp: Path):
    """查水印的算法本身(合成图,不用 X 盘):找 logo、框的位置、出现在哪几段、认字规则、比例框、一句话。"""
    print("[查水印:合成图找 logo / 认字规则 / 比例框]")
    import cv2
    import numpy as np
    from qe import watermark as W

    rng = np.random.default_rng(3)
    cw, ch = W.CANVAS_V
    rect = (0, 0, cw, ch)
    # 一个「水印」:白色细笔画拼的小图案(像 bilibili 那种字)
    mark = np.zeros((40, 110), np.uint8)
    cv2.putText(mark, "bili", (4, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 255, 3)

    def frame(with_mark: bool, x=560, y=60):
        f = cv2.resize(rng.integers(0, 140, (ch // 4, cw // 4), dtype=np.uint8), (cw, ch))   # 会动的画面
        if with_mark:
            reg = f[y:y + 40, x:x + 110].astype(np.float32)
            f[y:y + 40, x:x + 110] = np.clip(reg * (1 - mark / 255 * 0.8) + mark * 0.8, 0, 255).astype(np.uint8)
        return f

    ys, xs = np.where(mark > 0)
    gx, gy, gw, gh = 560 + xs.min(), 60 + ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1   # 真实位置
    crops = [frame(True)[60:100, 560:670] for _ in range(3)]
    lg = W.Logo("测试台", W.make_logo(crops), 0.75, "合成.png")
    # 20 秒:前 6 秒有水印(右上角),后面没有
    frames = [frame(i < 6) for i in range(20)]
    times = [float(i) for i in range(20)]
    maps = W.still_maps(frames)
    check(len(maps) == 18 and maps[0][1].shape == (ch, cw), "不动的图:窗口挪 1 帧,20 帧出 18 张")
    hits = W.match_logos(maps, [lg], times, rect)
    check(len(hits) == 1 and hits[0]["label"] == "测试台" and hits[0]["score"] >= 0.75, f"找到合成的水印:{hits[:1]}")
    if hits:
        bx, by, bw, bh = hits[0]["box"]
        check(abs(bx - gx) <= 5 and abs(by - gy) <= 5 and 0.8 < bw / gw < 1.25 and 0.8 < bh / gh < 1.25,
              f"框的位置对:{hits[0]['box']} ≈ {[int(gx), int(gy), int(gw), int(gh)]}")
        sp = W.spans_of(hits[0]["wins"], maps, times, 20.0)
        check(len(sp) == 1 and sp[0][0] <= 0.5 and 5 <= sp[0][1] <= 9, f"只在前几秒有:spans={sp}")
    clean = [frame(False) for _ in range(20)]
    check(not W.match_logos(W.still_maps(clean), [lg], times, rect), "没水印的(画面一直在动):不报")
    # 整条都有 → [[0, 时长]]
    allm = W.still_maps([frame(True) for _ in range(12)])
    h2 = W.match_logos(allm, [lg], times[:12], rect)
    check(h2 and W.spans_of(h2[0]["wins"], allm, times[:12], 12.0) == [[0.0, 12.0]], "整条都有:spans=[[0, 时长]]")
    # 认字规则:水印写法才算,夹在句子里 / 玩家名字不算
    for txt, want in (("抖音号：jiangjiangACG", "抖音"), ("抖音", "抖音"), ("快手号:12345", "快手"),
                      ("bilibili", "B站"), ("小红书号：99", "小红书"), ("得物", "得物"),
                      ("抖音熊二大王", ""), ("开局不到30秒抖音直接上线", ""), ("我们下期教学再会", ""),
                      ("快手", "快手"), ("微博视频", "微博"), ("抖音|悦策电影", "抖音"), ("三斤西瓜", ""),
                      ("直播版号：Z1904073", "")):
        check(W.text_label(txt) == want, f"认字规则:「{txt}」→「{want}」")
    # 比例框:竖画布里放横视频(上下黑边),框伸进黑边的部分切掉
    r = W.content_rect(1920, 1080)
    check(r == (0, 0, 1280, 720), f"横视频画布:{r}")
    r = (0, 437, 720, 406)
    check(W.to_ratio([360, 437, 72, 40.6], r) == [0.5, 0.0, 0.1, 0.1], "比例框:画布 → 原画面比例")
    check(W.to_ratio([700, 420, 40, 40], r)[1] == 0.0 and W.to_ratio([700, 420, 40, 40], r)[2] <= 0.0278,
          "比例框:伸到黑边 / 画外的部分切掉")
    check(W.where([600, 450, 80, 30], r) == "右上角", "位置说法:右上角")
    res = {"hits": [{"kind": "logo", "label": "B站", "where": "右上角"}, {"kind": "text", "label": "抖音", "where": "右下角"},
                    {"kind": "still", "label": "疑似水印", "where": "左边"}]}
    check(W.label_of(res) == "B站水印(右上角)、抖音字样(右下角)、疑似水印(左边)", f"一句话:{W.label_of(res)}")
    check(W.label_of({"hits": []}) == "", "没查到:空")
    # 整条 detect(合成一个小视频;要 ffmpeg)
    from qe import vertical
    ff = vertical.ffmpeg_path()
    if ff:
        p = str(tmp / "wm_synth.mp4")
        vw = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"mp4v"), 2, (cw, ch), False)
        for i in range(2 * 16):
            vw.write(frame(i < 2 * 8))                     # 16 秒,前 8 秒有
        vw.release()
        info = vertical.probe(p, ff)
        res = W.detect(p, ff, info, use_ocr=False, logos=[lg])
        hs = res["hits"]
        check(res["frames"] >= 15 and len(hs) == 1 and hs[0]["label"] == "测试台", f"整条 detect 找到:{hs}")
        if hs:
            x = hs[0]
            check(all(k in x for k in ("label", "kind", "score", "box", "ratio", "where", "t", "spans")), "返回的字段都在")
            check(x["spans"] and x["spans"][0][0] <= 0.5 and 7 <= x["spans"][-1][1] <= 11.5, f"出现的那几段:{x['spans']}")
            check(abs(x["ratio"][0] - gx / cw) < 0.02 and abs(x["ratio"][1] - gy / ch) < 0.02, f"比例框:{x['ratio']}")
            check(res["shot"] and os.path.isfile(res["shot"]), "存了截图")


def _wait(app, cond, secs=60):
    t0 = time.time()
    while not cond() and time.time() - t0 < secs:
        app.processEvents()
        time.sleep(0.05)
    return cond()


def test_ui_g(tmp: Path):
    print("[新界面(用户 2026-10-18 选的 G 一键驾驶舱):大字 + 大按钮、问题卡片、明细展开收起、能发 / 已发筛选、「今天」页]")
    from PySide6.QtWidgets import QApplication, QHBoxLayout
    app = QApplication.instance() or QApplication([])
    from qe import apiacc
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    root = tmp / "api_g"
    (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18").mkdir(parents=True)
    for f in ("g1.mp4", "g2.mp4", "g3.mp4"):
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18" / f).write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_g.json")
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "发布g" / "{date}")
    tab = T.ApiTab(st, Records(tmp / "rec_g.sqlite"), lambda m: None)
    tab.c_date.setCurrentText("10.18")
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 3)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
    tab.videos[0].checks["landscape"] = True
    tab._update_scope()
    tab._update_sum()
    check(tab.hero.big.text() == "2 条可以发了" and "1 条有点小问题" in tab.hero.sub.text(),
          f"大字写能发几条、下面写有几条小问题 -> {tab.hero.big.text()} / {tab.hero.sub.text()}")
    check(tab.card_v.title.text() == "1 条横屏 / 偏方" and tab.card_t.title.text() == "标题 / 话题都没问题",
          f"问题卡片按种类数 -> {tab.card_v.title.text()} / {tab.card_t.title.text()}")
    check(tab.b_vert in tab.card_v.buttons and tab.b_topic in tab.card_t.buttons, "卡片里就是原来的「转标准竖屏 / 整理标题」按钮")
    check(tab.b_pub.text() == "现在发布 2 条" and tab.b_pub.objectName() == "primary", "大按钮还是「现在发布 N 条」")
    bar = next(lay for lay in tab.findChildren(QHBoxLayout) if lay.indexOf(tab.b_pub) >= 0)
    check(bar.indexOf(tab.b_sched) >= 0 and bar.indexOf(tab.b_pub) - bar.indexOf(tab.b_sched) >= 3, "定时按钮还是离「现在发布」远一点")
    tab.set_detail(False, animate_=False)
    check(tab.detail.isHidden() and "看每个号的明细" in tab.b_detail.text() and tab.hero.property("open") == "false",
          "收起明细:列表藏起来、大字变大居中")
    tab.set_detail(True, animate_=False)
    check(not tab.detail.isHidden() and "收起明细" in tab.b_detail.text() and tab.hero.property("open") == "true",
          "看明细:列表出来、大字缩成一条")
    tab._seg_changed("ok")
    vis = [tab.videos[i].title for i, it in tab.items.items() if not it.isHidden()]
    check(sorted(vis) == ["g2", "g3"] and "过滤中" in tab.lab_scope.text(), f"点「能发」:只看能发的 -> {vis}")
    tab._seg_changed("bad")
    vis = [tab.videos[i].title for i, it in tab.items.items() if not it.isHidden()]
    check(vis == ["g1"] and tab.k_bad.isChecked(), f"点「要处理」= 原来的「只看有问题的」 -> {vis}")
    tab.k_bad.setChecked(False)
    check(tab.seg.key() == "all" and len([1 for it in tab.items.values() if not it.isHidden()]) == 3, "取消「只看有问题的」:回到全部")
    from gui.widgets import tone_of
    check([tone_of(x) for x in ("能发", "要处理", "没发成:平台不收", "已发", "结果不明", "")] == ["acc", "warn", "bad", "ok", "warn", ""],
          "状态胶囊的颜色:能发蓝 / 要处理橙 / 没发成红 / 已发绿")
    # 主窗口:「今天」页在最前面,下一步能跳过去
    import gui.window as GW
    st2 = Settings(tmp / "st_g2.json")
    st2["material_root"] = str(tmp / "edu_none")
    st2["api_roots"] = [str(tmp / "api_none")]
    w = GW.MainWindow(st2, Records(tmp / "rec_g2.sqlite"))
    check(w.stack.currentWidget() is w.today and w.nav.button(0).text() == "今天", "打开先看「今天」页")
    w.today.refresh(animate_=False)
    check("今天还差" in w.today.big.text() and "736" in w.today.lab_sent.text(), f"今天页写还差多少 -> {w.today.big.text()}")
    check(w.today.next_v.count() >= 1, "「下一步」至少有一条")
    w.goto("api")
    check(w.stack.currentWidget() is w.api_tab, "跳到 16 个号页")
    w.goto("edu")
    check(w.hero.big.text() == "先选要发哪天的", f"教育号页大字:先选日期 -> {w.hero.big.text()}")
    w.play_splash()
    _wait(app, lambda: False, 0.3)
    from gui.widgets import Splash
    sp = w.centralWidget().findChild(Splash)
    check(sp is not None and "欢迎使用本工作台" in sp.hi.text(), "开场动画:Hi,欢迎使用本工作台")
    sp.finish()
    w.close()


def test_pub_progress(tmp: Path):
    print("[发布进度(用户 2026-10-19 选的 B):大字写第几条、纸飞机进度条、每秒网速、正在发哪条、小字轮换、发完总结]")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    import gui.widgets as W
    root = tmp / "api_pp"
    (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18").mkdir(parents=True)
    for f in ("p1.mp4", "p2.mp4", "p3.mp4"):
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18" / f).write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_pp.json")
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "发布pp" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    tab = T.ApiTab(st, Records(tmp / "rec_pp.sqlite"), lambda m: None)
    tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 3)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
    tab._update_scope()
    seen = {}

    class Slow:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, on_progress=None, **k):
            if on_progress:
                on_progress(5 << 20, 10 << 20)
            time.sleep(0.4)
            if before_publish:
                before_publish("V")
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}
    real = (omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning)
    omapi.Client, T.ask = Slow, (lambda *a, **k: True)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: 0)
    try:
        tab.run_publish()
        _wait(app, lambda: tab._pub and tab._pub["done"] >= 1, 20)
        seen["big"] = tab.hero.big.text()
        seen["strip"] = not tab.hero._extra_w.isHidden() and not tab.b_stop.isHidden() and tab.b_pub.isHidden()
        seen["fun"] = tab.hero.sub.text()
        _wait(app, lambda: tab._pub and tab._pub.get("cur") is not None, 5)
        tab._pub_tick()
        seen["cur"] = tab.pub_strip.cur.text()
        _wait(app, lambda: not tab.busy(), 30)
        app.processEvents()
    finally:
        omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning = real
    check(seen.get("big", "").startswith("正在发布 · ") and seen["big"].endswith("/ 3"), f"发的时候大字写第几条 / 一共几条 -> {seen.get('big')}")
    check(seen.get("strip") is True, "发的时候露出进度条和「停」,灰掉的「现在发布」藏起来")
    pool = W.FUN_TIPS + W.FUN_ROAST + [f"{a}:{x}    {b}:{y}" for a, x, b, y in W.FUN_TALK]
    check(seen.get("fun") in pool, f"大字下面是小科普 / 段子 / 两个小人对话 -> {seen.get('fun')}")
    check("正在发" in seen.get("cur", "") and "CSGO战神君" in seen.get("cur", ""), f"写着正在发哪个号哪条 -> {seen.get('cur')}")
    p = tab._pub
    check(p["end"] and p["ok"] == 3 and "收工" in tab.pub_strip.cur.text() and "用时" in tab.pub_strip.eta.text(),
          f"发完:进度停下、写总结和用时 -> {tab.pub_strip.cur.text()} / {tab.pub_strip.eta.text()}")
    check(not tab.b_pub.isHidden() and tab.b_stop.isHidden(), "发完「现在发布」回来、「停」藏起来")
    lines = [W.fun_line() for _ in range(8)]
    check(len(set(lines)) == 8, "小字连着换不重复")
    tab.pub_strip.set_speed(2.345)
    check(tab.pub_strip.spd.text() == "↑ 2.3 MB/s", f"网速写成 MB/s -> {tab.pub_strip.spd.text()}")
    tab.pub_strip.set_speed(0.05)
    check(tab.pub_strip.spd.text() == "↑ 51 KB/s", f"慢的时候写 KB/s -> {tab.pub_strip.spd.text()}")


def test_cover_login(tmp: Path):
    print("[封面传不上(用户 2026-11-03):挑登着的页面传;发之前没登录就亮红,让人去登录或者这次不要封面]")
    import json
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, omcover
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T

    # ---- omcover:罐头里好几个页面,登录页的排后面;一个传不上换下一个 ----
    pages = {"a": "https://om.qq.com/userAuth/index", "b": "https://om.qq.com/main", "c": "https://om.qq.com/userAuth/index"}
    logged = {"b"}
    tried = []

    class FakePage:
        def __init__(self, t, timeout=20):
            self.t = t

        def ev(self, js, timeout=20):
            tried.append(self.t["id"])
            ok = self.t["id"] in logged
            if "marticle/article/list" in js:
                return json.dumps({"response": {"code": 0}, "data": {"articles": []}}) if ok else "<!DOCTYPE html>"
            return ('200 ' + json.dumps({"code": 0, "data": {"url": {"url": "https://inews.gtimg.com/om_bt/x"}}})) if ok \
                else "200 <!DOCTYPE html>"

        def close(self):
            pass
    real = (omcover.find_ports, omcover.targets, omcover.Page)
    omcover.find_ports = lambda: [1]
    omcover.targets = lambda port: [{"id": k, "url": u, "type": "webview"} for k, u in pages.items()]
    omcover.Page = FakePage
    img = tmp / "cov_login.jpg"
    _img(img, 720, 1280)
    try:
        check([t["id"] for t in omcover._targets()] == ["b", "a", "c"], "登着的页面(/main)排前面,停在登录页的排后面")
        check(omcover.check() == "", "有一个登着就算传得上")
        omcover._good["id"] = None
        pages = {"a": "https://om.qq.com/main", "b": "https://om.qq.com/main"}     # 两个都像登着,其实 a 掉线了
        tried.clear()
        url = omcover.upload(str(img))
        check(url.startswith("https://inews.gtimg.com") and tried == ["a", "b"], f"第一个页面传不上(掉线了),换下一个传上了 -> {tried}")
        tried.clear()
        omcover.upload(str(img))
        check(tried == ["b"], f"下一张直接用上次传成的页面 -> {tried}")
        logged = set()
        check(omcover.check() == omcover.NO_LOGIN, "都没登录 → 说「罐头里的企鹅号都没登录」")
        err = ""
        try:
            omcover.upload(str(img))
        except omcover.CoverError as e:
            err = str(e)
        check("没登录" in err, f"都没登录:传不上,说清楚 -> {err}")
        omcover.targets = lambda port: []
        check(omcover.check() == omcover.NO_CZGT, "罐头没开 → 说「没开创作罐头」")
    finally:
        omcover.find_ports, omcover.targets, omcover.Page = real
        omcover._good["id"] = None

    # ---- 界面:点「现在发布」先看罐头;没登录 → 不发、卡片亮红;点「这次不要封面,直接发」→ 发,不带封面 ----
    root = tmp / "api_covlogin"
    (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18").mkdir(parents=True)
    for f in ("k1.mp4", "k2.mp4"):
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18" / f).write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_covlogin.json")
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "发布covlogin" / "{date}")
    st["api_interval"] = 0
    st["quota_open"] = True
    logs = []
    tab = T.ApiTab(st, Records(tmp / "rec_covlogin.sqlite"), logs.append)
    tab.COVER_CHECK = True
    tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
    tab._update_scope()
    sent = []

    class Fake:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, cover="", cover_upload=None, **k):
            if before_publish:
                before_publish("V")
            sent.append((title, cover))
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功",
                    "cover": "没传上:传封面失败" if title == "k4" and cover else ""}
    from qe import autocover
    asked = []
    why = {"v": omcover.NO_LOGIN}
    real = (omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning, autocover.pick, tab._cover_check)
    omapi.Client, T.ask = Fake, (lambda *a, **k: asked.append(a[2]) or True)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: 0)
    autocover.pick = lambda p: str(img)
    tab._cover_check = lambda: why["v"]
    try:
        tab.run_publish()
        app.processEvents()
        check(not sent and not asked and not tab.busy(), "罐头没登录:先不发,也不弹「现在发布」确认框")
        check(not tab.card_cov.isHidden() and "没登录" in tab.card_cov.title.text() and tab.card_cov.property("tone") == "bad",
              f"卡片亮红,写着为什么 -> {tab.card_cov.title.text()}")
        check("登好了,接着发" in tab.logbox.toPlainText(), "日志里说去罐头登好点「登好了,接着发」")
        tab.b_cov_skip.click()
        _wait(app, lambda: not tab.busy(), 30)
        app.processEvents()
        check(sorted(sent) == [("k1", ""), ("k2", "")], f"点「这次不要封面,直接发」:发了,两条都不带封面 -> {sent}")
        check(asked and "这次不要封面" in asked[-1], "确认框写着这次不要封面")
        check(tab._nocover_once is False, "「这次不要封面」只管这一次")
        # 登好了:卡片收起,照常带封面;发的时候有一条封面没传上 → 发完卡片亮红、弹框列出来
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18").mkdir(parents=True, exist_ok=True)     # 发空了,文件夹删了
        for f in ("k3.mp4", "k4.mp4"):
            (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18" / f).write_bytes(b"x")
        tab.load()
        _wait(app, lambda: not tab.busy() and len(tab.videos) >= 2)
        for v in tab.videos:
            v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
        tab._update_scope()
        sent.clear()
        why["v"] = ""
        tab.card_cov.hide()
        tab.run_publish()
        check(tab.card_cov.isHidden(), "登着:卡片不出来")
        _wait(app, lambda: not tab.busy(), 30)
        app.processEvents()
        check(sorted(t for t, _c in sent) == ["k3", "k4"] and all(c for _t, c in sent), f"登着:带封面发 -> {sent}")
        check(not tab.card_cov.isHidden() and "1 条封面没传上" in tab.card_cov.title.text(),
              f"发的时候有一条封面没传上:发完卡片亮红 -> {tab.card_cov.title.text()}")
        check("1 条封面没传上" in tab.logbox.toPlainText(), "发完总结里写几条封面没传上")
    finally:
        omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning, autocover.pick, tab._cover_check = real


def test_accounts_manage(tmp: Path):
    print("[账号管理(用户 2026-11-03):新增号、分组、条数;影视号「号文件夹\\日期」;新游戏号单横杠文件夹也认]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import accounts as A, apiacc, apisrc, folders as F, plan as P
    from qe.config import Settings
    st = Settings(tmp / "st_accm.json")
    root = tmp / "accm_教育"
    st["material_root"] = str(root)
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    # 游戏号
    A.add(st, "FPS射击游戏馆", "游戏", 30, "腾讯系FPS射击游戏")
    r = {x["nick"]: x for x in A.rows(st)}
    check(r["FPS射击游戏馆"]["cat"] == "游戏" and r["FPS射击游戏馆"]["quota"] == 30 and r["FPS射击游戏馆"]["key"] is False,
          f"新增游戏号:进游戏组、30 条、钥匙「没有」 -> {r['FPS射击游戏馆']}")
    a = apiacc.find("FPS射击游戏馆")
    check(a and a["category"] == 1604 and not a["client_id"] and "FPS射击游戏馆" in apiacc.nicks(), "接口账号里有它(分类网络游戏、还没钥匙)")
    groot = tmp / "accm_游戏视频"
    (groot / "腾讯系FPS射击游戏-FPS射击游戏馆" / "11.3").mkdir(parents=True)
    (groot / "腾讯系FPS射击游戏-FPS射击游戏馆" / "11.3" / "f1.mp4").write_bytes(b"x")
    (groot / "CSGO--CSGO战神君").mkdir()
    fl = apisrc.account_folder_list([str(groot)], set(apiacc.nicks()))
    check(set(fl) == {"FPS射击游戏馆", "CSGO战神君"}, f"单横杠「…-FPS射击游戏馆」的文件夹也认成这个号 -> {sorted(fl)}")
    vs = apisrc.videos([str(groot)], "11.3", set(apiacc.nicks()))
    check([(v.account, v.title) for v in vs] == [("FPS射击游戏馆", "f1")], "新游戏号这天的视频读得到")
    # 教育号 + 影视号
    A.add(st, "家长成长营", "教育", 50, "成长营、成长")
    (root / "11.3" / "成长营" / "张").mkdir(parents=True)
    (root / "11.3" / "成长营" / "张" / "e1.mp4").write_bytes(b"x")
    film = tmp / "accm_高热剧集二创" / "光影叙集"
    (film / "11.3").mkdir(parents=True)
    (film / "11.4").mkdir(parents=True)
    (film / "11.3" / "电影解说一.mp4").write_bytes(b"x")
    A.add(st, "光影叙集", "影视", 40, str(film))
    check(P.quota_of(st, "光影叙集") == 40 and any(g["cat"] == "影视" and "光影叙集" in g["accounts"] for g in P.plan(st)),
          "新增影视号:每天规定里多了「影视」一组")
    check([F.day_of(d) for d in F.all_dates(st)] == ["11.3", "11.4"], f"日期下拉:教育的日期 + 影视号文件夹里的日期 -> {F.all_dates(st)}")
    ad = F.account_dirs(str(root), "11.3", st)
    check(ad.get("家长成长营") == [str(root / "11.3" / "成长营")] and ad.get("光影叙集") == [str(film / "11.3")],
          f"11.3:教育号按缩写找、影视号按自己的文件夹找 -> {ad}")
    ad4 = F.account_dirs(str(root), "11.4", st)
    check(ad4.get("光影叙集") == [str(film / "11.4")], "教育那边没有 11.4 这天:影视号的照样找得到")
    fv = F.scan_account(str(film / "11.3"), "光影叙集", "11.3")
    check([v.title for v in fv] == ["电影解说一"], "影视号的视频读得到(直接放在日期文件夹里的)")
    check("光影叙集" in st.account_names() and "光影叙集" not in apiacc.nicks(), "影视号在罐头那页,不进接口发布名单")
    # 改分组 / 去掉 / 重名
    A.set_cat(st, "FPS射击游戏馆", "动漫")
    check(any(g["cat"] == "动漫" and "FPS射击游戏馆" in g["accounts"] for g in P.plan(st)), "游戏 ↔ 动漫 直接改")
    bad = []
    for nick, cat in (("FPS射击游戏馆", "教育"), ("光影叙集", "游戏"), ("光影叙集", "教育"), ("家长成长营", "影视")):
        try:
            A.set_cat(st, nick, cat)
        except ValueError:
            bad.append(nick + cat)
    check(len(bad) == 4, f"接口发的 ↔ 罐头发的、教育 ↔ 影视(放法不一样)不能直接改 -> {bad}")
    try:
        A.add(st, "光影叙集", "影视", 1, str(film))
        dup = False
    except ValueError:
        dup = True
    check(dup, "同名的号加不了第二个")
    # 改名(用户 2026-11-03:号名打错了,双击改):文件夹里写的还是老名字 → 素材文件夹填完整文件夹名照样找得到
    st["api_picked"] = {"11.3": {"FPS射击游戏馆": "x"}}
    from qe import omlogin
    from qe.config import data_dir
    (Path(omlogin.profile_dir("FPS射击游戏馆")) / "Cookies").write_text("x")
    warn = A.rename(st, "FPS射击游戏馆", "FPS游戏射击馆")
    check(not warn and (data_dir() / "浏览器登录" / "FPS游戏射击馆" / "Cookies").is_file()
          and not (data_dir() / "浏览器登录" / "FPS射击游戏馆").exists(), "改号名:登录取钥匙的浏览器登录跟着改名(不用重新扫码)")
    r = {x["nick"]: x for x in A.rows(st)}
    check("FPS游戏射击馆" in r and "FPS射击游戏馆" not in r and apiacc.find("FPS游戏射击馆")
          and st["api_picked"]["11.3"] == {"FPS游戏射击馆": "x"}, "改号名:规定、接口账号、手选的文件夹都跟着改")
    fl = apisrc.account_folder_list([str(groot)], set(apiacc.nicks()))
    check("FPS游戏射击馆" not in fl, "号名和文件夹里写的不一样:光按名字找不到")
    A.set_folder(st, "FPS游戏射击馆", "腾讯系FPS射击游戏-FPS射击游戏馆")
    fl = apisrc.account_folder_list([str(groot)], set(apiacc.nicks()))
    check(fl.get("FPS游戏射击馆") == [str(groot / "腾讯系FPS射击游戏-FPS射击游戏馆")], f"素材文件夹填完整文件夹名:找到了 -> {fl}")
    bad = False
    try:
        A.rename(st, "FPS游戏射击馆", "光影叙集")
    except ValueError:
        bad = True
    check(bad, "改成已经有的号名:不行")
    A.remove(st, "FPS游戏射击馆")
    check(apiacc.find("FPS游戏射击馆") is None and all("FPS游戏射击馆" not in g["accounts"] for g in P.plan(st)), "去掉号:规定和钥匙都去掉")
    st2 = Settings(tmp / "st_accm.json")
    check(any(a.get("dir") == str(film) for a in st2["accounts"]), "存盘了(重开设置还在)")
    from gui.accounts_dialog import AccountsDialog
    d = AccountsDialog(st)
    check(d.t.rowCount() == len(A.rows(st)) and d.t.item(0, 0) is not None, "账号管理窗口打得开,一行一个号")
    apiacc.save([])


def test_ai_cover(tmp: Path):
    print("[AI 第二轮看封面(用户 2026-11-03):判断完不完整 / 有没有字;不完整的、没认出脸的 AI 自己挪框再看;"
          "还不行的、有字的标黄;人看过 / 调过框的不看;记下来不重复问]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import json
    from qe import aicover, cover as C, folders as F
    import gui.window as W
    img = tmp / "aic" / "a.png"
    _img(img, 1280, 720)
    mk = lambda n, **k: F.Video(path=str(tmp / "aic" / f"{n}.mp4"), title=n, account="家长小天地", employee="张", date="11.3",
                                cover=str(img), plan={"cx": 0.5, "cy": 0.4}, **k)
    r = aicover.parse('好的:[{"ratio":"3:4","whole":"完整","text":"没有"},{"ratio":"9:16","whole":"切掉一部分","text":"有"},'
                      '{"ratio":"1:1","whole":"不在","text":"没有"}]')
    check(r == {"3:4": {"whole": "完整", "text": False}, "9:16": {"whole": "切了", "text": True},
                "1:1": {"whole": "不在", "text": False}}, f"判断那回读得出来:完整 / 切了 / 不在、有没有字 -> {r}")
    bad = False
    try:
        aicover.parse("看不懂")
    except ValueError:
        bad = True
    check(bad, "AI 回的读不出来:报错,不当成没问题")
    check(aicover.parse_box('{"what":"一口锅","box":[600,200,900,800]}') == (0.6, 0.2, 0.9, 0.8), "主体的框读得出来(0~1000 → 几成)")
    cx, cy = aicover.aim(1280, 720, 9 / 16, (0.6, 0.2, 0.9, 0.8))
    x, y, w, h = C.crop_rect(1280, 720, 9 / 16, {"ai": {C.rkey(9 / 16): [cx, cy]}})
    check(abs((x + w / 2) / 1280 - 0.75) < 0.01, f"AI 挪的框:9:16 对准主体中间 -> {cx}")
    x2 = C.crop_rect(1280, 720, 9 / 16, {"ai": {C.rkey(9 / 16): [cx, cy]}, "manual": {C.rkey(9 / 16): [0.2, 0.5]}})[0]
    check(abs((x2 + w / 2) / 1280 - 0.2) < 0.01, "人拖过的框比 AI 挪的优先")
    _cx, cy2 = aicover.aim(1280, 1280, 2.35, (0.3, 0.1, 0.7, 0.3))
    _x, y3, _w, h3 = C.crop_rect(1280, 1280, 2.35, {"ai": {C.rkey(2.35): [_cx, cy2]}})
    check(y3 / 1280 < 0.2 and (y3 + h3 * C.TITLE_SAFE) / 1280 > 0.3, "2.35:1:主体放在框上面那块(下面是标题区)")
    imgs = aicover.sheet(mk("x"))
    check([t for t, _b in imgs] == ["原图", "3:4", "9:16", "2.35:1", "1:1"] and all(b[:2] == b"\xff\xd8" for _t, b in imgs),
          "给 AI 的:原图 + 4 个比例,一张一张的 JPEG")
    check([t for t, _b in aicover.sheet(mk("x"), ["9:16"])] == ["原图", "9:16"], "挪过框再看:只给挪过的那几个比例")

    calls = []
    sizes = {"要挪": 1000, "有字": 1100, "脸切了": 1200, "挪了也不行": 900}      # 原图缩到 360 高,按宽认是哪条
    for n, w in sizes.items():
        _img(tmp / "aic" / f"{n}.png", w, 720)

    def fake(imgs, prompt):
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(imgs[0][1]))
        who = next((n for n, w in sizes.items() if abs(im.width * 720 / im.height - w) < 3), "")
        tags = [t for t, _b in imgs[1:]]
        calls.append((who, "找" if prompt == aicover.LOCATE else "看", tags))
        if prompt == aicover.LOCATE:
            return '{"what":"一口锅","box":[600,200,900,800]}'
        again = len(tags) < 4
        out = []
        for t in tags:
            whole, text = "完整", "没有"
            if who == "要挪" and t == "3:4" and not again:
                whole = "切掉一部分"
            if who == "挪了也不行" and t == "9:16":
                whole = "切掉一部分"
            if who == "脸切了" and t in ("9:16", "2.35:1"):
                whole = "切掉一部分"
            if who == "有字" and t == "1:1":
                text = "有"
            out.append({"ratio": t, "whole": whole, "text": text})
        return json.dumps(out, ensure_ascii=False)

    class Adj:
        def is_ok(self, path, cover, title):
            return title == "人看过"
    vs = [mk("要挪"), mk("没问题", warn=True), mk("人看过"), mk("调过框"), mk("不摆", skip="发过同名"),
          mk("有字"), mk("脸切了"), mk("挪了也不行")]
    for v in vs:
        if v.title in sizes:
            v.cover = str(tmp / "aic" / f"{v.title}.png")
    vs[3].plan = dict(vs[3].plan, manual={"3:4": [0.5, 0.5]})
    vs[6].plan = dict(vs[6].plan, faces=[[0.4, 0.2, 0.1, 0.2]])
    for trust in (False, True):
        w = W.AiCoverWorker([F.Video(**{**v.__dict__}) for v in vs], Adj(), "k", trust, lambda v: False, asker=fake)
        w.run()
        out = {v.title: v for v in w.videos}
        if not trust:
            firsts = [c for c in calls if c[1] == "看" and len(c[2]) == 4]
            check(len(firsts) == 5, f"人看过的、调过框的、不摆的都不问 AI -> {calls}")
            m = out["要挪"]
            check(("要挪", "找", []) in calls and ("要挪", "看", ["3:4"]) in calls, f"不完整:问主体在哪,挪了再看那一个比例 -> {calls}")
            check(C.rkey(3 / 4) in (m.plan.get("ai") or {}) and "manual" not in m.plan, f"AI 挪的框记在 plan['ai'],不算人拖的 -> {m.plan}")
            check(m.warn and "AI 挪了 3:4 的框,看一眼" in m.cover_why, f"挪好了:没开「直接去黄」还黄着让人看一眼 -> {m.cover_why}")
            check(out["没问题"].warn and "AI 看过" in out["没问题"].cover_why, "软件拿不准的、AI 说没问题:没开「直接去黄」还黄着(前期人还要看)")
            check(out["有字"].warn and out["有字"].cover_why == "AI:1:1 有字,要去豆包去字", f"有字:标黄,说去豆包去字 -> {out['有字'].cover_why}")
            f = out["脸切了"]
            check(("脸切了", "找", []) not in calls and f.warn and f.cover_why == "AI:9:16 主体被切了" and "ai" not in f.plan,
                  f"认出了脸的不挪(多半是框太窄),标黄;2.35:1 躲标题区故意切的不算 -> {f.cover_why}")
            g = out["挪了也不行"]
            check(g.warn and g.cover_why == "AI:9:16 挪了框还是装不下整个主体(AI 挪过 9:16 的框)", f"挪了还不行:标黄 -> {g.cover_why}")
            n1 = len(calls)
        else:
            check(len(calls) == n1, "第二遍:框没变,用记下的结果,不再问 AI")
            check(not out["没问题"].warn and "AI 看过没问题" in out["没问题"].cover_why, "开了「AI 说没问题的直接去黄」:去黄")
            m = out["要挪"]
            check(not m.warn and C.rkey(3 / 4) in (m.plan.get("ai") or {}) and "看一眼" not in m.cover_why,
                  f"开了直接去黄:AI 挪好的也去黄,框照样套上 -> {m.cover_why}")
    v = mk("要挪")
    v.cover = str(tmp / "aic" / "要挪.png")
    aicover.reapply(v)
    check(C.rkey(3 / 4) in (v.plan.get("ai") or {}), "「恢复自动」重新配封面:AI 挪过的框从记录里套回来,不再问 AI")


def test_flat_folders(tmp: Path):
    print("[罐头发的号没有日期文件夹了(用户 2026-11-05):小学生教育\\研习社 直接是号;里面的就是今天的;发够了留着;发完只挪已发的]")
    from types import SimpleNamespace
    from qe import folders as F, redo
    from qe.config import Settings
    import gui.window as W
    today = F.today_md()
    root = tmp / "flat" / "小学生教育"
    st = Settings(tmp / "flat_st.json")
    st["material_root"] = str(root)
    st["archive_root"] = str(tmp / "flat" / "内容查看" / "{month}月发布视频" / "教育")
    film = tmp / "flat" / "高热剧集二创" / "剧讯幕后社"
    st["accounts"] = [{"name": "家长研习空间", "aliases": ["研习空间", "研习社"]}, {"name": "家长小天地", "aliases": ["小天地"]},
                      {"name": "剧讯幕后社", "aliases": [], "dir": str(film)}]
    a = root / "研习社"
    a.mkdir(parents=True)
    (root / "小天地").mkdir()
    (root / "不认识").mkdir()
    (root / "重复删除").mkdir()
    for n in ("第一条", "第二条"):
        (a / f"{n}.mp4").write_bytes(b"x")
        (a / f"{n}.jpg").write_bytes(b"x")
        (a / n).mkdir()
        _img(a / n / "横屏16x9.png", 64, 36)
        (a / n / "原图.png").write_bytes(b"x")
    (film / "幕后社").mkdir(parents=True)
    (film / "幕后社" / "今天的.mp4").write_bytes(b"x")
    (film / "1.1" / "幕后社").mkdir(parents=True)
    (film / "1.1" / "幕后社" / "老的.mp4").write_bytes(b"x")
    ds = F.all_dates(st)
    check(sorted(ds) == sorted(["1.1", today]), f"日期下拉:有今天,号文件夹和别的文件夹不混进去 -> {ds}")
    ad = F.account_dirs(str(root), today, st)
    check(ad["家长研习空间"] == [str(a)] and ad["剧讯幕后社"] == [str(film)], f"今天:号文件夹直接认 -> {ad}")
    check(F.unknown_dirs(str(root), today, st) == ["不认识"], "不认识的文件夹提醒;「重复删除」不算")
    check(not F.account_dirs(str(root), "1.1", st)["家长研习空间"], "别的天:号文件夹不算(只有今天算)")
    vs = F.scan_account(str(a), "家长研习空间", today)
    check(len(vs) == 2 and all(v.png.endswith("横屏16x9.png") for v in vs) and {v.employee for v in vs} == {F.NO_EMP},
          "视频直接在号文件夹里:读得到,封面工具的文件夹配得上")
    fv = [v.title for d in ad["剧讯幕后社"] for v in F.scan_account(d, "剧讯幕后社", today)]
    check(fv == ["今天的"], f"影视号今天不翻里面的日期文件夹 -> {fv}")
    old = [v.title for d in F.account_dirs(str(root), "1.1", st)["剧讯幕后社"] for v in F.scan_account(d, "剧讯幕后社", "1.1")]
    check(old == ["老的"], f"选那天才看日期文件夹 -> {old}")
    check(F.in_flat(vs[0].path, st) and F.in_flat(str(film / "幕后社" / "今天的.mp4"), st)
          and not F.in_flat(str(film / "1.1" / "幕后社" / "老的.mp4"), st) and not F.in_flat(str(root / "11.1" / "研习社" / "a.mp4"), st),
          "分得清号文件夹里的和日期文件夹里的")
    # 发够了:留着,不挪去明天
    said = []
    fake = SimpleNamespace(worker=None, batch_id="", st=st, videos=[vs[1]], row_note={}, rec=SimpleNamespace(status_of=lambda p: ""),
                           _edu_left=lambda acc: 0, _fill_row=lambda i: None, say=said.append, _update_scope=lambda: None)
    n = W.MainWindow._edu_spill(fake)
    check(n == 1 and vs[1].skip.startswith("这天发够") and os.path.isfile(vs[1].path) and "明天接着发" in said[0],
          f"发够规定条数:留在号文件夹,不建明天的文件夹 -> {said} {[x.name for x in root.iterdir()]}")
    vs[1].skip = ""
    # 发完挪走:只挪已发的
    dst = F.archive_target(st, today)
    moved, errs = F.move_flat(st, today, [(str(a), vs[0])])
    to = Path(dst) / "研习社"
    check(moved == 1 and not errs and (to / "第一条.mp4").is_file() and (to / "第一条.jpg").is_file() and (to / "第一条" / "横屏16x9.png").is_file(),
          f"已发的连封面挪到 归档\\日期\\号文件夹 -> {errs}")
    check((a / "第二条.mp4").is_file() and (a / "第二条").is_dir() and not (a / "第一条").exists() and not (a / "第一条.jpg").exists(),
          "没发的留着;号文件夹不动")
    row = {"date": today, "path": str(a / "第一条.mp4"), "account": "家长研习空间", "platform": ""}
    check(redo.locate(st, row) == str(to / "第一条.mp4"), f"找视频重发:归档里找得到 -> {redo.locate(st, row)}")
    check(redo.target_dir(st, row, today) == str(a), f"挪回来重发:回号文件夹,不建日期文件夹 -> {redo.target_dir(st, row, today)}")
    frow = {"date": today, "path": str(film / "幕后社" / "今天的.mp4"), "account": "剧讯幕后社", "platform": ""}
    check(redo.target_dir(st, frow, today) == str(film / "幕后社"), "影视号:挪回原来的文件夹")
    # 左边那行:发过同名的单写,不算进「不发」(用户 2026-11-07)
    mk = lambda p, skip="": SimpleNamespace(path=p, skip=skip, png="x")
    rows = [mk("a"), mk("b", "发过同名"), mk("c", "发过同名"), mk("d", "0 字节,视频是坏的")]
    fake2 = SimpleNamespace(rec=SimpleNamespace(status_of=lambda p: "已发" if p == "a" else ""))
    t = W.MainWindow._emp_text(fake2, rows)
    check(t == "4 条,发了 1,发过同名 2,1 条不发(同名 / 坏的)", f"发过同名单写 -> {t}")


def test_black_cover(tmp: Path):
    print("[黑封面(用户 2026-11-06):很小的字幕也算黑;发前换掉黑图;发完读平台封面列出来;只读]")
    import io
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
    from qe import blackcover as B

    def pic(fn):
        im = Image.new("RGB", (640, 360), "black")
        fn(ImageDraw.Draw(im))
        return im
    black = pic(lambda d: None)
    subtitle = pic(lambda d: d.rectangle([250, 300, 390, 312], fill="white"))
    big = pic(lambda d: d.rectangle([40, 120, 600, 240], fill="white"))
    normal = Image.new("RGB", (640, 360), (120, 150, 90))
    sharp_pic = Image.new("RGB", (640, 360), (40, 80, 140))
    ds = ImageDraw.Draw(sharp_pic)
    for x in range(0, 640, 40):
        for y in range(0, 360, 40):
            if ((x + y) // 40) % 2 == 0:
                ds.rectangle([x, y, x + 36, y + 36], fill=(230, 190, 70))
    blurry = sharp_pic.filter(ImageFilter.GaussianBlur(14))
    # 画面全糊、只有底下露一条清楚字幕(11-16《新版本水上飞机》那种):分块算照样抓得出是模糊封面
    blurry_sub = blurry.copy()
    ImageDraw.Draw(blurry_sub).rectangle([200, 344, 440, 356], fill=(255, 230, 0), outline=(0, 0, 0), width=2)
    check(B.is_black_img(black) and B.is_black_img(subtitle), "纯黑、只有一小行字幕:算黑")
    check(not B.is_black_img(big) and not B.is_black_img(normal), "黑底大字、正常画面:不算")
    check(B.is_blurry_img(blurry) and B.is_blurry_img(blurry_sub) and not B.is_blurry_img(sharp_pic) and not B.is_blurry_img(black),
          "模糊图(含底下露半行清楚字幕的)算模糊封面;清楚图不算;黑封面不重复算成模糊")
    d = tmp / "blk"
    d.mkdir()
    black.save(d / "黑.jpg")
    blurry_sub.save(d / "糊.jpg")
    normal.save(d / "好.jpg")
    (d / "坏.jpg").write_bytes(b"not a picture")
    check(B.is_black(str(d / "黑.jpg")) and not B.is_black(str(d / "好.jpg")) and not B.is_black(str(d / "坏.jpg")), "本地图:黑的认得出,读不出来的不算黑")
    check(B.is_blurry(str(d / "糊.jpg")) and not B.is_blurry(str(d / "好.jpg")) and not B.is_blurry(str(d / "坏.jpg")), "本地图:模糊的认得出,读不出来的不算")

    def jpg(im):
        b = io.BytesIO()
        im.save(b, "JPEG")
        return b.getvalue()
    imgs = {"u1": jpg(black), "u2": jpg(normal), "u3": jpg(subtitle), "u4": jpg(blurry_sub)}

    class Cl:
        def list_articles(self, page, limit):
            rows = [("a1", "黑的", "u1", "正常"), ("a2", "好的", "u2", "正常"), ("a3", "小字幕", "u3", "正常"), ("a4", "没图", "", "正常"),
                    ("a5", "删了的", "u1", "已删除"), ("a6", "读不出", "u9", "正常"), ("a7", "糊的", "u4", "正常")]
            return {"total": len(rows), "articles": [] if page > 1 else [
                {"article_id": i, "article_title": t, "article_imgurl": u, "article_url": "http://x/" + i, "article_del_flag": f,
                 "article_pub_time": "2026-11-06 10:00:00", "article_pub_flag": "1", "article_video_info": {"vid": "v" + i}}
                for i, t, u, f in rows]}

    def fetch(u):
        return imgs[u]
    got, bad = B.scan_one({"nick": "甲"}, "2026-11-06", "2026-11-06", make_client=lambda a: Cl(), fetch=fetch)
    check([(x["title"], x["kind"]) for x in got] == [("黑的", "黑封面"), ("小字幕", "黑封面"), ("糊的", "模糊封面")]
          and got[0]["nick"] == "甲" and got[0]["url"] == "http://x/a1",
          f"读平台封面:黑封面和模糊封面都列出来,删了的不算 -> {got}")
    check(B.summary_text(got) == "2 条黑封面、1 条模糊封面", f"汇总字样 -> {B.summary_text(got)}")
    check(bad == 2, f"没图 / 读不出来的记下几张,不当成没问题 -> {bad}")
    B.save("2026-11-06", got)
    check(B.load("2026-11-06") == got and B.load("2026-11-07") == [], "查到的记下来(软件重开还在),别的天不算")
    # 窗口
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from gui.black_dialog import BlackDialog
    dlg = BlackDialog("2026-11-06", None, items=got)
    check(dlg.t.rowCount() == 3 and dlg.t.item(0, 1).text() == "黑的" and dlg.t.item(2, 2).text() == "模糊封面"
          and "2 条黑封面、1 条模糊封面" in dlg.lab_done.text(), f"窗口列出来:号 / 标题 / 问题 / 时间 -> {dlg.lab_done.text()}")
    dlg.copy()
    check(QApplication.clipboard().text() == "甲\t黑的\n甲\t小字幕\n甲\t糊的", "复制标题")
    dlg.close()
    # 发之前:放的封面是黑的或模糊的,都换软件挑的一帧
    from PySide6.QtWidgets import QMessageBox
    from qe import apiacc, autocover, omapi
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    app = QApplication.instance()
    day = tmp / "blkpub" / "游戏视频" / "CSGO--CSGO战神君" / "10.18"
    day.mkdir(parents=True)
    for n in ("黑图", "糊图", "好图"):
        (day / f"{n}.mp4").write_bytes(b"x")
    black.save(day / "黑图.jpg")
    blurry_sub.save(day / "糊图.jpg")
    normal.save(day / "好图.jpg")
    picked = tmp / "blkpub" / "挑的.jpg"
    normal.save(picked)
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_blkpub.json")
    st["api_roots"] = [str(tmp / "blkpub" / "游戏视频")]
    st["api_archive"] = str(tmp / "blkpub" / "发布" / "{date}")
    st["api_interval"] = 0
    st["quota_open"] = True
    logs = []
    tab = T.ApiTab(st, Records(tmp / "rec_blkpub.sqlite"), logs.append)
    tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 3)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
    tab._update_scope()
    sent = {}

    class Fake:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, cover="", cover_upload=None, **k):
            if before_publish:
                before_publish("V" + title)
            sent[title] = cover
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功", "cover": "传了"}
    real = (omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning, autocover.pick)
    omapi.Client, T.ask, autocover.pick = Fake, (lambda *a, **k: True), (lambda p: str(picked))
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: 0)
    try:
        tab.run_publish()
        _wait(app, lambda: not tab.busy() and len(sent) == 3, 30)
        app.processEvents()
        check(sent.get("黑图") == str(picked) and sent.get("糊图") == str(picked), f"放的封面是黑的或模糊的:都传软件挑的一帧 -> {sent}")
        check(os.path.basename(sent.get("好图", "")) == "好图.jpg", "放的封面正常:照旧传它")
        check("封面是黑的" in tab.logbox.toPlainText() and "封面太模糊" in tab.logbox.toPlainText(), "日志里都说了一声")
    finally:
        omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning, autocover.pick = real
        apiacc.save([])


def test_sharp(tmp: Path):
    print("[发布前查清晰度(用户 2026-11-06):低清放大看 resdet 的尺寸要两帧一致;整条糊看最清楚的一帧;只提醒不拦;记下来不重查]")
    import numpy as np
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import sharp as S
    raw = "640:0.61 325:0.50\n360:0.60 111:0.70"
    check(S.sizes(raw, 1080, 608) == [(640, 360)], f"resdet 的话读得出:宽高比例一致才算 -> {S.sizes(raw, 1080, 608)}")
    check(S.sizes("810:0.7\n456:0.7", 1080, 608) == [], "0.75 倍是压缩的假信号,不算")
    check(S.sizes("720:0.7\n405:0.7", 1080, 608) == [], "720 放大到 1080(我们转竖屏就有):不算")
    check(S.sizes("640:0.50\n360:0.50", 1080, 608) == [], "分数不够:不算")
    check(S.sizes("681:0.7\n380:0.7", 720, 406) == [], "720×406 估成 681×380:几乎没放大,不算")
    check(S.sizes("坏的", 1080, 608) == [], "读不出来:不算")
    check(S.agree([[(640, 360)], [], [(641, 361)]]) == (640, 360), "两帧都出现(差一点算一样):算")
    check(S.agree([[(640, 360)], [(480, 270)], []]) is None, "每帧说的尺寸都不一样:是噪声,不算")
    rng = np.random.default_rng(1)
    sharp_f = (rng.random((608, 1080)) * 255).astype("uint8")
    yy, xx = np.mgrid[0:608, 0:1080]
    soft = (127 + 100 * np.sin(xx / 90) * np.sin(yy / 70)).astype("uint8")
    r = S.check("x", "", 10, grab=lambda t: sharp_f, detect=lambda g: "640:0.6\n360:0.6")
    check(r["hits"] == [{"kind": "low", "w": 640, "h": 360}], f"低清放大:记下估的尺寸 -> {r}")
    r = S.check("x", "", 10, grab=lambda t: soft, detect=lambda g: "")
    check([x["kind"] for x in r["hits"]] == ["blur"], f"4 帧都没有清楚的:算糊 -> {r}")
    got = []
    S.check("x", "", 10, grab=lambda t: got.append(round(t)) or sharp_f, detect=lambda g: "")
    check(got == [2, 4, 6, 8], f"抽 4 帧 -> {got}")
    bar = np.zeros((1920, 1080), dtype="uint8")
    bar[656:1264] = sharp_f
    check(S.active(bar).shape == (608, 1080), "上下黑边去掉再看")
    check(S.check("x", "", 10, grab=lambda t: sharp_f, detect=lambda g: "")["hits"] == [], "清楚的:没事")
    bad = False
    try:
        S.check("x", "", 10, grab=lambda t: None)
    except OSError:
        bad = True
    check(bad, "一帧都读不出来:报错,不记成没问题")
    real = S.resdet_path
    S.resdet_path = lambda: ""
    check(S.check("x", "", 10, grab=lambda t: sharp_f)["hits"] == [], "没放 resdet:照样跑,只看糊不糊")
    S.resdet_path = real
    check(S.text({"hits": [{"kind": "low", "w": 640, "h": 360}], "ok": False}) == "疑似低清放大(约 640×360),看一眼", "表格里的话")
    check(S.text({"hits": [{"kind": "blur"}], "ok": True}) == "" and S.text({"hits": []}) == "" and S.text(None) == "", "人说过没问题 / 没问题:不写")
    # 后台查:查过的不重查、读不出来的不记;只提醒,状态还是能发
    from types import SimpleNamespace
    from gui.sharp_worker import SharpWorker
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    d = tmp / "shp" / "游戏视频" / "CSGO--CSGO战神君" / "10.18"
    d.mkdir(parents=True)
    (d / "好.mp4").write_bytes(b"1")
    (d / "糊.mp4").write_bytes(b"22")
    (d / "坏.mp4").write_bytes(b"333")
    calls = []

    def fake(path, ff, dur, stop=None):
        calls.append(os.path.basename(path))
        if path.endswith("坏.mp4"):
            raise OSError("读不出")
        return {"hits": [{"kind": "blur", "score": 50}] if path.endswith("糊.mp4") else []}
    rc = S.check
    S.check = fake
    try:
        vs = [SimpleNamespace(path=str(d / n), checks={"dur": 10}) for n in ("好.mp4", "糊.mp4", "坏.mp4")]
        w = SharpWorker(vs, [0, 1, 2])
        w.run()
        check(sorted(calls) == ["坏.mp4", "好.mp4", "糊.mp4"] and w.n_bad == 1, f"三条都查 -> {calls}")
        check(S.flagged(vs[1].sharp) and not S.flagged(vs[0].sharp) and not hasattr(vs[2], "sharp"), "糊的记下;读不出来的不记,下次再查")
        calls.clear()
        w = SharpWorker(vs, [0, 1])
        w.run()
        check(not calls, "文件没变:不再查")
        S.STORE.set_ok(vs[1].path, True)
        check(not S.flagged(S.STORE.get(vs[1].path)), "右键「清晰度没问题」以后不再提")
        S.STORE.set_ok(vs[1].path, False)
        from qe import apiacc
        apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
        st = Settings(tmp / "st_shp.json")
        st["api_roots"] = [str(tmp / "shp" / "游戏视频")]
        tab = T.ApiTab(st, Records(tmp / "rec_shp.sqlite"), lambda m: None)
        tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
        app = QApplication.instance()
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 3)
        i = next(k for k, v in enumerate(tab.videos) if v.title == "糊")
        tab.videos[i].checks = dict(tab.videos[i].checks or {}, bad_read=False, landscape=False, squarish=False, w=1080, h=1920, platform=[], tags=[])
        tab.videos[i].sharp = S.STORE.get(tab.videos[i].path)
        tab._fill(i)
        st_, probs = tab._status_text(i)
        check("画面可能很糊" in tab.items[i].text(2) and st_.startswith("能发") and not probs, f"备注里提醒,状态还是能发 -> {tab.items[i].text(2)} / {st_}")
        # 右键菜单:视频行、号那一行都要弹得出来(11-06 写漏变量:右键一点就报错,「给号选文件夹」都没了)
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QMenu
        shown = []

        class FakeMenu(QMenu):
            def exec(self, *a):
                texts = [x.text() for x in self.actions()]
                for x in self.actions():
                    if x.menu():
                        texts += [y.text() for y in x.menu().actions()]
                shown.append(texts)
        real_menu, real_at = T.QMenu, tab.tree.itemAt
        T.QMenu = FakeMenu
        try:
            tab.tree.itemAt = lambda p: tab.items[i]
            tab._menu(QPoint(1, 1))
            group = tab.items[i].parent()
            tab.tree.itemAt = lambda p: group
            tab._menu(QPoint(1, 1))
        finally:
            T.QMenu, tab.tree.itemAt = real_menu, real_at
        check(len(shown) == 2 and "清晰度没问题" in shown[0], f"视频行右键:有「清晰度没问题」 -> {len(shown)}")
        check(len(shown) == 2 and all(any("换个文件夹" in t for t in x) for x in shown), "视频行、号那一行右键:都能给号选文件夹")
        tab.set_sharp_ok(i)
        check("很糊" not in tab.items[i].text(2), "标过没问题:提醒没了")
        # 用户 2026-11-09:刷新以后查过的不要再查(原来每条都排队「查中」)
        tab.load()
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 3)
        left = sorted(v.title for v in tab.videos if getattr(v, "sharp", None) is None)
        check(left == ["坏"], f"刷新:查过的直接挂上结果,只剩没查成的要查 -> {left}")
        apiacc.save([])
    finally:
        S.check = rc


def test_crop_back(tmp: Path):
    print("[字幕被裁(用户 2026-11-07):满屏的 AI 看 7 帧,3 帧以上算;不发;打回挪进「打回视频\\账号名」;右键能放行]")
    import numpy as np
    from PIL import Image
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication, QMenu, QMessageBox
    app = QApplication.instance() or QApplication([])
    from gui.sharp_worker import SharpWorker
    from qe import apiacc, checks, cropcheck as K, folders as F, wmstore
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    rng = np.random.default_rng(2)
    full = Image.fromarray((rng.random((1280, 720, 3)) * 255).astype("uint8"))
    bars = np.zeros((1920, 1080, 3), dtype="uint8")
    bars[656:1264] = (rng.random((608, 1080, 3)) * 255).astype("uint8")
    bars = Image.fromarray(bars)
    land = Image.fromarray((rng.random((720, 1280, 3)) * 255).astype("uint8"))
    check(K.full_screen(full) and not K.full_screen(bars) and not K.full_screen(land), "满屏竖屏才看;上下黑边、横屏不看")
    check(K.parse('好的{"subtitle":"有","cut":"切断了"}') and not K.parse('{"subtitle":"有","cut":"没切断"}'), "AI 的话读得出")
    asked = []

    def aski(ans):
        def f(im):
            asked.append(1)
            return ans.pop(0)
        return f
    r = K.check("x", "", 10, "k", grab=lambda t: full, asker=aski([True, False, True, False, True, False, False]))
    check(r["hits"] == [{"n": 3, "of": 7}] and len(asked) == 7, f"7 帧有 3 帧被切:算被裁 -> {r}")
    check(K.check("x", "", 10, "k", grab=lambda t: full, asker=aski([True, True, False, False, False, False, False]))["hits"] == [], "只有 2 帧:不算(AI 偶尔看错)")
    asked.clear()
    check(K.check("x", "", 10, "k", grab=lambda t: bars, asker=aski([]))["hits"] == [] and not asked, "有黑边的:不问 AI(省钱)")
    bad = False
    try:
        K.check("x", "", 10, "k", grab=lambda t: None, asker=aski([]))
    except OSError:
        bad = True
    check(bad, "读不出来:报错,不记成没问题")
    bad = False

    def boom(im):
        raise RuntimeError("AI 没回话")
    try:
        K.check("x", "", 10, "k", grab=lambda t: full, asker=boom)
    except RuntimeError:
        bad = True
    check(bad, "AI 没回话:报错,不记成没问题")
    # 打回去哪
    day = tmp / "crp" / "游戏视频" / "CSGO--CSGO战神君" / "10.18"
    day.mkdir(parents=True)
    mroot = tmp / "crp" / "小学生教育"
    check(K.back_dir(str(mroot), "甲") == str(tmp / "crp" / "打回视频" / "甲"), "打回去素材盘的 打回视频\\账号名")
    t = K.names_text([("甲", "一"), ("乙", "二"), ("甲", "三")])
    check("【甲】2 条\n  一\n  三" in t and "【乙】1 条" in t, f"名单按号分 -> {t}")
    for n in ("裁", "好"):
        (day / f"{n}.mp4").write_bytes(b"x")
        (day / f"{n}.jpg").write_bytes(b"y")
    (day / "裁").mkdir()
    (day / "裁" / "横屏16x9.png").write_bytes(b"z")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_crp.json")
    st["api_roots"] = [str(tmp / "crp" / "游戏视频")]
    st["material_root"] = str(mroot)
    tab = T.ApiTab(st, Records(tmp / "rec_crp.sqlite"), lambda m: None)
    tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, squarish=False, w=720, h=1280, platform=[], tags=[])
    real = K.check
    K.check = lambda path, ff, dur, key, stop=None, asker=None: {"hits": [{"n": 3, "of": 4}] if path.endswith("裁.mp4") else []}
    try:
        w = SharpWorker(tab.videos, [0, 1], want_sharp=False, crop_key="k", need_crop=tab._crop_todo)
        w.run()
    finally:
        K.check = real
    check(w.n_crop == 1, f"查出 1 条 -> {w.n_crop}")
    i = next(k for k, v in enumerate(tab.videos) if v.title == "裁")
    g = 1 - i
    check("字幕被裁" in checks.problems(tab.videos[i]) and not tab._can_send(i), "被裁的:不能发")
    check(tab._can_send(g), "没被裁的:照常能发")
    tab._fill(i)
    tab._update_scope()
    check(not tab.card_crop.isHidden() and "1 条字幕被裁" in tab.card_crop.title.text() and tab.b_crop.text() == "打回 1 条", f"卡片亮了,按钮写几条 -> {tab.b_crop.text()}")
    shown = []

    class FakeMenu(QMenu):
        def exec(self, *a):
            shown.append([x.text() for x in self.actions()])
    real_menu, real_at = T.QMenu, tab.tree.itemAt
    T.QMenu = FakeMenu
    tab.tree.itemAt = lambda p: tab.items[i]
    try:
        tab._menu(QPoint(1, 1))
    finally:
        T.QMenu, tab.tree.itemAt = real_menu, real_at
    check("没被裁,这条能发" in shown[0], "右键能放行")
    tab.set_crop_ok(i, True)
    check(tab._can_send(i) and tab.card_crop.isHidden(), "放行以后能发,卡片收起")
    tab.set_crop_ok(i, False)
    check(not tab._can_send(i), "改回来:又不能发")
    rs = (T.ask, QMessageBox.information)
    said = []
    T.ask = lambda *a, **k: said.append(a[2]) or True
    try:
        tab.tree.clearSelection()
        tab.crop_back()
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 1)
    finally:
        T.ask = rs[0]
    back = tmp / "crp" / "打回视频" / "CSGO战神君"
    check((back / "裁.mp4").is_file() and (back / "裁.jpg").is_file() and (back / "裁" / "横屏16x9.png").is_file() and not (day / "裁.mp4").exists(),
          "打回:视频、封面、封面文件夹都挪进 打回视频\\账号名,不删")
    check((day / "好.mp4").is_file() and [v.title for v in tab.videos] == ["好"], "别的不动;列表里没有它了")
    check("这些视频字幕被裁了" in QApplication.clipboard().text() and "裁" in QApplication.clipboard().text(), "名单复制好了")
    apiacc.save([])
    # 影视号(教育 / 影视页)
    from types import SimpleNamespace
    import gui.window as W
    film = tmp / "crp" / "高热剧集二创" / "剧讯幕后社"
    (film / "幕后社").mkdir(parents=True)
    for n in ("裁", "好"):
        (film / "幕后社" / f"{n}.mp4").write_bytes(b"x")
        (film / "幕后社" / f"{n}.jpg").write_bytes(b"y")
    mk = lambda n, c: SimpleNamespace(path=str(film / "幕后社" / f"{n}.mp4"), title=n, account="剧讯幕后社", date="11.7", crop=c)
    vs2 = [mk("裁", {"hits": [{"n": 3}], "ok": False}), mk("好", {"hits": [], "ok": False})]
    check(W.MainWindow._title_block(vs2[0]) == "字幕被裁" and W.MainWindow._title_block(vs2[1]) == "", "影视号被裁的:不摆,写清楚")
    st2 = {"material_root": str(mroot), "accounts": [{"name": "剧讯幕后社", "aliases": [], "dir": str(film)}]}
    selected = []
    pane = SimpleNamespace(batch_id="", worker=None, videos=vs2, st=SimpleNamespace(get=st2.get, __getitem__=st2.__getitem__),
                           rec=SimpleNamespace(status_of=lambda p: ""), table=SimpleNamespace(selectedIndexes=lambda: selected),
                           _confirm=lambda *a: True, say=lambda m: None, _load_tree=lambda: None)
    pane._crop_rows = lambda rows=None: W.MainWindow._crop_rows(pane, rows)
    pane.st = st2
    W.MainWindow.crop_back(pane)
    bk = tmp / "crp" / "打回视频" / "剧讯幕后社"
    check((bk / "裁.mp4").is_file() and (bk / "裁.jpg").is_file() and (film / "幕后社" / "好.mp4").is_file(), "影视号打回:同一个「打回视频」下按号分,别的不动")
    check("【剧讯幕后社】1 条" in QApplication.clipboard().text(), "影视号名单也复制好了")
    check(not any(v.title == "裁" for v in F.scan_account(str(film), "剧讯幕后社", F.today_md())), "打回以后软件不再读到它")


def test_title_date(tmp: Path):
    print("[标题里的日期(用户 2026-11-03):只发今天 / 昨天的,将来的、更早的都不要;「3号选手」不算日期;右键放行]")
    from datetime import date
    from qe import checks, folders as F, titledate as TD
    today = date(2026, 11, 3)
    cases = {
        "我的世界27号又开始了": ["27号"],
        "11月3日更新内容一览": [],
        "11月2号的比赛回顾": [],
        "11月5日开服预告": [],                    # 写了月份的将来日期:能发(用户后来改的)
        "11月1日上线超详细玩法": ["11月1日"],      # 前天:过期
        "1月5日新春活动": ["1月5日"],              # 11 月说 1 月:是明年的,超过一个月了
        "12月3日活动": [],                         # 正好一个月:能发
        "12月4日活动": ["12月4日"],                # 超过一个月:不发
        "5号开服": ["5号"],                        # 只写几号:分不清过去将来,只认今天昨天
        "10.27 版本前瞻": ["10.27"],
        "11.3 新皮肤上线": [],
        "3号选手残血反杀": [],
        "1号位怎么打 #王者荣耀": [],
        "三亚5日游攻略": [],
        "7日内必须完成的任务": [],
        "版本3.5 改动": [],
        "伤害提升1.5倍": [],
        "S11.2 赛季": [],
        "2号的比赛": [],
        "31号开始": ["31号"],
    }
    for t, want in cases.items():
        got = TD.bad_dates(t, today)
        check(got == want, f"「{t}」-> {got}(应该 {want})")
    check(TD.bad_dates("1号的回放", date(2026, 12, 2)) == [] and TD.bad_dates("30号的回放", date(2026, 12, 1)) == [],
          "昨天跨月(12.1 那天,30 号算昨天)也认")
    from datetime import timedelta
    from qe.config import bj_now
    old_d = (bj_now() - timedelta(days=5)).day
    v = F.Video(path="x.mp4", title=f"我的世界{old_d}号又开始了", account="CSGO战神君", employee="", date="11.3")
    v.checks = {"tags": []}
    TD.store().set(v.account, v.title, False)
    check(any("标题日期不对" in p for p in checks.problems(v)),
          "过期的:列进「要处理」(不用点检查,读进来就有)")
    TD.store().set(v.account, v.title, True)
    check(not any("标题日期不对" in p for p in checks.problems(v)), "右键「日期没问题」以后:能发")
    TD.store().set(v.account, v.title, False)


def test_awake(tmp: Path):
    print("[罐头最小化了任务不动(2026-10-19):摆的时候一直叫醒页面;最小化了悄悄恢复(测试里不动真窗口)]")
    from qe import prepare, winfix
    calls = []

    class FakePage:
        def cmd(self, method, params=None, timeout=20):
            calls.append((method, params))
            if method == "Page.setWebLifecycleState":
                raise prepare.CdpError("不支持")         # 叫不醒也不耽误
            return {}
    r = prepare.Runner.__new__(prepare.Runner)
    r.log, r.stopped, r.page, r._awake_at, r._told_min = (lambda m: None), (lambda: False), FakePage(), 0.0, False
    r.awake()
    check(("Emulation.setFocusEmulationEnabled", {"enabled": True}) in calls
          and ("Page.setWebLifecycleState", {"state": "active"}) in calls, f"叫页面别省电 -> {calls}")
    n = len(calls)
    r.awake()
    check(len(calls) == n, "3 秒内不重复叫")
    r.awake(force=True)
    check(len(calls) == n + 2, "换号的时候马上叫")
    check(winfix.unminimize() == 0, "测试里不去动真罐头的窗口")
    import threading
    r._closed = threading.Event()
    t = threading.Thread(target=r._window_guard, daemon=True)
    t.start()
    r.page = None
    r.close()
    t.join(3)
    check(not t.is_alive(), "摆完 close():看窗口的小哨兵跟着收工(平时你最小化罐头它不管)")
    check(isinstance(winfix.czgt_windows(), list), "能找罐头窗口(找不到就是空的)")


def test_yellow_manual(tmp: Path):
    print("[教育号不定时也能去掉标黄(2026-10-19):A 开始前问一次 / B 停下来能接着自动发布 / C 预览里「这张没问题」]")
    from PySide6.QtCore import QObject, QTimer, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    import gui.api_tab as A
    import gui.window as GW
    from qe.adjust import Adjustments
    from qe.config import Settings
    from qe.records import Records
    root = tmp / "素材yellow"
    for emp, ts in (("张", ("黄的一条视频", "好的一条视频")), ("李", ("黄的三条视频", "好的三条视频"))):
        d = root / "10.18" / "小天地" / emp
        d.mkdir(parents=True)
        for t in ts:
            (d / f"{t}.mp4").write_bytes(b"x")
            _img(d / f"{t}.png", 640, 360)
    calls = []

    class FakeBW(QObject):
        log = Signal(str)
        one = Signal(object, bool, str)
        finished_batch = Signal(object, str, str)

        def __init__(self, acc, vids, shots, parent=None, auto_publish=False, unattended=False, sched_at="", publish_only=False):
            super().__init__(parent)
            self.vids, self.auto, self.only = vids, auto_publish, publish_only
            calls.append(("只点发布" if publish_only else "摆", [v.title for v in vids]))

        def isRunning(self):
            return False

        def stop(self):
            pass

        def start(self):
            def go():
                if self.only:
                    self.finished_batch.emit([(v, True, "") for v in self.vids], "", "ok")
                    return
                res = []
                for v in self.vids:
                    self.one.emit(v, True, "")
                    res.append((v, True, ""))
                ylw = [v for v in self.vids if v.warn]
                pub = ("ok" if not ylw else f"有 {len(ylw)} 条封面标黄(要人看一眼),没自动发布") if self.auto else ""
                self.finished_batch.emit(res, "", pub)
            QTimer.singleShot(0, go)

    def fake_decide(v):
        v.cover, v.cover_kind, v.cover_why, v.plan = v.png, "png", "测试", {}
        v.warn = "黄" in v.title
    real = (GW.BatchWorker, GW.C.decide, GW.C.note_wide, QMessageBox.information, A.ask)
    boxes, asked = [], []
    GW.BatchWorker, GW.C.decide, GW.C.note_wide = FakeBW, fake_decide, (lambda v: None)
    QMessageBox.information = staticmethod(lambda _p, t, x, *a, **k: boxes.append(x))
    try:
        rec = Records(tmp / "r_yellow.sqlite")
        st = Settings(tmp / "s_yellow.json")
        st["material_root"] = str(root)
        st["api_roots"] = [str(tmp / "api_none")]
        st["ai_key"] = "test"
        st["batch_size"] = 2
        w = GW.MainWindow(st, rec)
        w.c_date.setCurrentIndex(w.c_date.findData("10.18"))
        from PySide6.QtCore import Qt
        top = next(w.tree.topLevelItem(k) for k in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(k).text(0) == "家长小天地")
        kids = {top.child(k).data(0, Qt.ItemDataRole.UserRole + 3): top.child(k) for k in range(top.childCount())}
        kids["张"].setCheckState(0, Qt.CheckState.Checked)
        _wait(app, lambda: not (w.cover_worker and w.cover_worker.isRunning()))
        w.k_auto.setChecked(True)
        w._ask = lambda *a, **k: True

        # A「还没看」:照旧摆,摆到有标黄的那批停下来
        def not_yet(*a, **k):
            asked.append(a[1])
            k["on_extra"]()
            return False
        A.ask = not_yet
        w.start_batch()
        _wait(app, lambda: bool(boxes), 10)
        y1 = next(v for v in w.videos if v.title == "黄的一条视频")
        check(asked and asked[0] == "摆下一批" and calls == [("摆", ["好的一条视频", "黄的一条视频"])] and y1.warn,
              f"A:勾了自动发布、有标黄 → 开始前问一次;选「还没看」照旧摆 -> {calls}")
        check(w._yellow_stop and not w.b_pubgo.isHidden() and "标黄" in w.hero.big.text()
              and "接着自动发布" in boxes[-1], f"摆好了因为标黄停下来:大字写标黄,露出「封面看过了,接着自动发布」-> {w.hero.big.text()}")
        # B:点「封面看过了,接着自动发布」→ 软件只点全部发布,记成已发,不再标黄
        A.ask = real[4]
        w.continue_publish()
        _wait(app, lambda: not w.batch_id, 10)
        st_ = {v.title: rec.status_of(v.path) for v in w.videos}
        check(calls[-1] == ("只点发布", ["好的一条视频", "黄的一条视频"]) and st_["黄的一条视频"] == "已发" and st_["好的一条视频"] == "已发"
              and not y1.warn and Adjustments(tmp / "封面调整.json").is_ok(y1.path, y1.cover) and w.b_pubgo.isHidden(),
              f"B:接着自动发布 = 只点「全部发布」、这批记成已发、封面记成看过了 -> {calls[-1]} {st_}")
        # A「都看过了」:开始前就去黄,一路发,不停
        w.k_auto.setChecked(False)
        kids["李"].setCheckState(0, Qt.CheckState.Checked)
        _wait(app, lambda: not (w.cover_worker and w.cover_worker.isRunning()))
        w.k_auto.setChecked(True)
        A.ask = lambda *a, **k: asked.append(a[1]) or True
        boxes.clear()
        w.start_batch()
        _wait(app, lambda: not w.batch_id and calls[-1][0] == "摆", 10)
        app.processEvents()
        y3 = next(v for v in w.videos if v.title == "黄的三条视频")
        check(not y3.warn and rec.status_of(y3.path) == "已发" and not w._yellow_stop,
              f"A:选「都看过了」→ 去黄、这批自动发出去,中间不停 -> {calls[-1]} {rec.status_of(y3.path)}")
        w.k_auto.setChecked(False)
        w.close()
    finally:
        GW.BatchWorker, GW.C.decide, GW.C.note_wide, QMessageBox.information, A.ask = real
    # C:预览里「这张没问题」
    from gui.cover_dialog import CoverDialog
    from qe.folders import Video
    d = tmp / "yc"
    _img(d / "这条.png", 640, 360)
    (d / "这条.mp4").write_bytes(b"x")
    v = Video(path=str(d / "这条.mp4"), title="这条", account="号", employee="甲", date="10.18", png=str(d / "这条.png"))
    v.cover, v.cover_kind, v.cover_why, v.plan, v.warn = v.png, "png", "没认出人,框放中间(看一眼)", {}, True
    adj = Adjustments(tmp / "adj_yc.json")
    dlg = CoverDialog([v], 0, adj)
    got = []
    dlg.changed.connect(got.append)
    vis0 = not dlg.b_okc.isHidden()
    dlg.mark_ok()
    check(vis0 and not v.warn and adj.is_ok(v.path, v.cover) and got == [0] and dlg.b_okc.isHidden() and "人看过" in v.cover_why,
          "C:标黄的封面在预览里点「这张没问题」→ 不再标黄、记在硬盘上")
    dlg.close()


def test_api_per_acc(tmp: Path):
    print("[同一个号一次传几条(2026-10-19):一组同时传、组间歇间隔;默认 1 = 一条一条;号的密钥坏了后面的不发]")
    import threading
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    root = tmp / "api_pa"
    apiacc.save([{"nick": n, "source_name": g, "client_id": g, "secret": apiacc.seal("s"), "category": 1604, "enabled": True}
                 for g, n in (("CSGO", "CSGO战神君"), ("PUBG", "PUBG突围君"))])
    st = Settings(tmp / "st_pa.json")
    check(st.get("api_per_acc") == 1, "默认同一个号一次传 1 条(一条一条发)")
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "发布pa" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    lock = threading.Lock()
    live = {"now": 0, "max": {}, "starts": []}

    class Slow:
        def __init__(self, cid, sec, **k):
            self.cid = cid

        def send(self, path, title, cat, before_publish=None, **k):
            if self.cid == "PUBG" and live.get("bad_pubg"):
                raise omapi.ApiError("换 token 失败", "40001", fatal=True)
            with lock:
                live["now"] += 1
                live["max"][self.cid] = max(live["max"].get(self.cid, 0), live["now"])
                live["starts"].append((time.time(), title))
            time.sleep(0.3)
            with lock:
                live["now"] -= 1
            if before_publish:
                before_publish("V")
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}
    real = (omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning)
    omapi.Client, T.ask = Slow, (lambda *a, **k: True)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: 0)
    try:
        def run(per, threads, only=None):
            st["api_per_acc"], st["api_threads"] = per, threads
            for g, n in (("CSGO", "CSGO战神君"), ("PUBG", "PUBG突围君")):    # 每轮一份新视频(发完会挪走)
                d = root / "游戏视频" / f"{g}--{n}" / "10.18"
                d.mkdir(parents=True, exist_ok=True)
                for k in range(7 if g == "CSGO" else 3):
                    (d / f"{g}{k}_{per}_{threads}.mp4").write_bytes(b"x")
                for old in d.glob("*.mp4"):
                    if not old.stem.endswith(f"_{per}_{threads}"):
                        old.unlink()
            rec = Records(tmp / f"rec_pa_{per}_{threads}_{bool(only)}.sqlite")
            tab = T.ApiTab(st, rec, lambda m: None)
            tab.set_day("10.18")
            _wait(app, lambda: not tab.busy() and len(tab.videos) == 10)
            for v in tab.videos:
                v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
            tab._update_scope()
            live["max"], live["starts"] = {}, []
            tab.run_publish(only=[i for i, v in enumerate(tab.videos) if only is None or v.account == only])
            _wait(app, lambda: not tab.busy(), 60)
            app.processEvents()
            return tab, rec
        tab, rec = run(1, 1, only="CSGO战神君")
        check(live["max"].get("CSGO") == 1 and sum(1 for v in tab.videos if rec.status_of(v.path) == "已发") == 7,
              f"一次传 1 条:一条一条发,7 条都发了 -> 同时最多 {live['max']}")
        tab, rec = run(3, 1, only="CSGO战神君")
        t = sorted(x for x, _ in live["starts"])
        groups = [len([x for x in t if t[g] <= x < t[g] + 0.2]) for g in (0, 3, 6)]
        check(live["max"].get("CSGO") == 3 and groups == [3, 3, 1] and sum(1 for v in tab.videos if rec.status_of(v.path) == "已发") == 7,
              f"一次传 3 条:3 + 3 + 1 一组组发,7 条都发了 -> 同时最多 {live['max']},每组 {groups}")
        live["bad_pubg"] = True
        tab, rec = run(5, 2)
        pubg = [i for i, v in enumerate(tab.videos) if v.account == "PUBG突围君"]
        sts = [tab.state.get(i, "") for i in pubg]
        check(all(x.startswith(("没发成", "没发:")) for x in sts) and all(not rec.status_of(tab.videos[i].path) for i in pubg)
              and sum(1 for v in tab.videos if rec.status_of(v.path) == "已发") == 7 and live["max"].get("CSGO", 0) <= 6,
              f"号的密钥坏了:这个号这组 + 后面的都不发,别的号照发 -> {sts}")
        live["bad_pubg"] = False
        tab, rec = run(5, 1)
        check(sum(1 for v in tab.videos if rec.status_of(v.path) == "已发") == 10 and len(live["starts"]) == 10,
              "一次传 5 条:全部一条不落、每条只发一次")
        tab.run_publish()
        _wait(app, lambda: not tab.busy(), 30)
        check(len(live["starts"]) == 10, "再点一次发布:发过的不再发(防重发照旧)")
    finally:
        omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning = real


def test_quick_review(tmp: Path):
    print("[快速过封面(2026-10-19):一屏铺开标黄的、回车 = 没问题跳下一张、剩下的都没问题、脸被切了标出来]")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import gui.api_tab as A
    import gui.cover_review as R
    from qe.adjust import Adjustments
    from qe.folders import Video
    d = tmp / "qr"
    vs = []
    for k, fx in enumerate((0.45, 0.5, 0.97)):
        _img(d / f"q{k}.png", 1600, 900)
        v = Video(path=str(d / f"q{k}.mp4"), title=f"q{k}", account="家长小天地", employee="甲", date="10.19", png=str(d / f"q{k}.png"))
        v.cover, v.cover_kind, v.warn, v.cover_why = v.png, "png", True, "看一眼"
        v.plan = {"cx": 0.5, "cy": 0.35, "faces": [[fx, 0.2, 0.08, 0.2]], "all": [[fx, 0.2, 0.08, 0.2]]}
        vs.append(v)
    adj = Adjustments(tmp / "adj_qr.json")
    dlg = R.QuickReview(vs, adj)
    got = []
    dlg.changed.connect(got.append)
    _wait(app, lambda: len(dlg.cards) == 3, 10)
    check(len(dlg.cards) == 3 and dlg.cur == 0 and "剩 3" in dlg.lab_n.text(), f"一屏铺开 3 张标黄的 -> {dlg.lab_n.text()}")
    check(dlg.cards[2].cut and not dlg.cards[0].cut and "脸好像被切了" in dlg.cards[2].why.text(), "脸跑到框外的标出来「脸好像被切了」")
    dlg.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    check(not vs[0].warn and adj.is_ok(vs[0].path, vs[0].cover) and dlg.cur == 1 and got == [vs[0]] and "看过 1" in dlg.lab_n.text(),
          "回车:这张没问题(去黄、记在硬盘上),跳到下一张")
    dlg.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier))
    check(dlg.cur == 2, "→:换下一张")
    real = A.ask
    A.ask = lambda *a, **k: True
    try:
        dlg.all_ok()
    finally:
        A.ask = real
    check(all(not v.warn for v in vs) and "剩 0" in dlg.lab_n.text() and "都看完了" in dlg.tip.text(), "「剩下的都没问题」:全去黄")
    dlg.close()


def test_game_guard(tmp: Path):
    print("[游戏号的标题像别的游戏(2026-10-20 和平精英传成了 PUBG):一条不发等确认;3 条以上整批先不发;关键词看不出来问 AI]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, checks, gamecheck
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    check(gamecheck.by_words("CSGO战神君", "今天和嫂子一起打和平精英") == ("和平精英", True), "CSGO 号里「和平精英」→ 像和平精英")
    check(gamecheck.by_words("CSGO战神君", "下班啦来整一把#英雄联盟#lol") == ("英雄联盟", True), "CSGO 号里「#英雄联盟#lol」→ 像英雄联盟")
    check(gamecheck.by_words("CSGO战神君", "cs2 急停教学,和平年代也要练") == ("", True), "提到了自己的游戏(cs2)就不算串")
    check(gamecheck.by_words("LOL玩家聚集地", "云顶之弈新阵容") == ("", True), "英雄联盟 / 云顶之弈算一家")
    check(gamecheck.by_words("LOLM峡谷日常", "lolm 打野") == ("", True) and gamecheck.hits("lolm 打野") == ["英雄联盟手游"],
          "英文词要单独出现:「lolm」不算「lol」")
    check(gamecheck.by_words("电竞情报馆", "和平精英决赛") == ("", True), "电竞情报馆(各种游戏)不查")
    check(gamecheck.by_words("PUBG突围君", "哈哈哈") == ("", False), "关键词看不出来的 → 要问 AI")
    root = tmp / "api_gg"
    apiacc.save([{"nick": n, "source_name": g, "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}
                 for g, n in (("CSGO", "CSGO战神君"), ("和平精英", "和平精英上分君"))])
    (root / "游戏视频" / "和平精英--和平精英上分君").mkdir(parents=True, exist_ok=True)
    st = Settings(tmp / "st_gg.json")
    st["api_roots"] = [str(root / "游戏视频")]
    st["quota_open"] = True
    st["ai_key"] = "fake"
    d = root / "游戏视频" / "CSGO--CSGO战神君" / "10.20"

    def load(names):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for nm in names:
            (d / f"{nm}.mp4").write_bytes(b"x")
        tab = T.ApiTab(st, Records(tmp / "rgg.sqlite"), lambda m: None)
        tab.set_day("10.20")
        _wait(app, lambda: not tab.busy() and len(tab.videos) == len(names))
        tab.run_check()
        _wait(app, lambda: not tab.busy())
        for v in tab.videos:
            v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
        tab._update_scope()
        tab._update_sum()
        return tab

    def idx(tab, w):
        return next(i for i, v in enumerate(tab.videos) if w in v.title)
    AI_GAME_CALLS.clear()
    tab = load(["cs2 急停教学", "今天和嫂子一起打和平精英", "G镇六个苟分点", "残局一打三", "大狙甩枪", "沙二A点",
                "经济局", "道具教学", "残局二", "残局三", "残局四", "残局五"] + [f"日常{k}" for k in range(10)])
    asked = [t for _o, ts in AI_GAME_CALLS for t in ts]
    check(AI_GAME_CALLS and AI_GAME_CALLS[0][0] == "CSGO" and "G镇六个苟分点" in asked and "cs2 急停教学" not in asked
          and "今天和嫂子一起打和平精英" not in asked,
          f"检查时只把关键词看不出来的问 AI(按号一批)-> {AI_GAME_CALLS[:1]}")
    a, b, ok = idx(tab, "和平精英"), idx(tab, "苟分"), idx(tab, "急停")
    check("标题像是《和平精英》的" in checks.problems(tab.videos[a]) and not tab._can_send(a),
          f"一条像和平精英:标「标题像是《和平精英》的」,不发 -> {checks.problems(tab.videos[a])}")
    check(not checks.problems(tab.videos[b]) and tab._can_send(b) and "AI 觉得像《PUBG》,不拦" in tab.items[b].text(2),
          f"AI 说像 PUBG 的:只提示、不拦(用户 2026-10-22:AI 误判太多)-> {tab.items[b].text(2)}")
    check(not tab._blocked and tab._can_send(ok), f"22 条里 2 条(不到一成):不算整批放错,别的照常能发 -> {tab._blocked}")
    AI_GAME_CALLS.clear()
    tab.run_check()
    _wait(app, lambda: not tab.busy())
    check(not AI_GAME_CALLS, "问过的标题记着,下次检查不再问(不重复花钱)")
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
    tab.tree.clearSelection()
    tab.set_game_ok(a, True)
    check(not checks.problems(tab.videos[a]) and tab._can_send(a),
          f"右键「是这个号的,能发」→ 能发了 -> {checks.problems(tab.videos[a])} {tab._blocked}")
    tab.set_game_ok(a, False)
    check(not tab._can_send(a), "再右键「其实不是这个号的」→ 又不发了")
    tab = load(["cs2 急停教学", "今天和嫂子一起打和平精英", "超体新皮肤", "下班啦来整一把#英雄联盟#lol", "残局一打三", "大狙甩枪",
                "沙二A点", "经济局", "道具教学", "残局二"])
    nick = "CSGO战神君"
    check(tab._blocked.get(nick) == 3 and not any(tab._can_send(i) for i in range(len(tab.videos))),
          f"一个号 3 条像别的游戏 → 整批先不发 -> {tab._blocked}")
    g = tab.groups.get(nick) if hasattr(tab, "groups") else None
    gtext = g.text(2) if g is not None else ""
    check("放错" in tab.hero.sub.text() and (g is None or "可能放错了 3" in gtext),
          f"大字下面 / 号那一行写「可能整批放错了」-> {tab.hero.sub.text()[:80]} / {gtext}")
    check(tab.b_pub.text() == "现在发布 0 条" or not tab.b_pub.isEnabled(), f"发布按钮不算这个号 -> {tab.b_pub.text()}")
    tab.set_batch_ok(nick, True)
    ok = idx(tab, "急停")
    check(not tab._blocked and tab._can_send(ok) and not tab._can_send(idx(tab, "和平精英")),
          "右键号「这批确认没放错」→ 这批能发了,像别的游戏的那几条还是不发")
    tab.set_batch_ok(nick, False)
    check(tab._blocked.get(nick) == 3, "取消确认 → 又整批不发")
    # 真放错了:右键「放错了:挪到「和平精英上分君」的 10.20」→ 视频连同名封面挪过去(新员工试用 2026-10-21)
    (d / "今天和嫂子一起打和平精英 .jpg").write_bytes(b"j")
    check(tab._game_home("和平精英") and tab._game_home("和平精英")[0] == "和平精英上分君", "找得到和平精英的号和文件夹")
    tab.tree.clearSelection()
    tab.move_to_game(idx(tab, "和平精英"))
    _wait(app, lambda: not tab.busy())
    hp = root / "游戏视频" / "和平精英--和平精英上分君" / "10.20"
    got = sorted(os.listdir(hp)) if hp.exists() else []
    check("今天和嫂子一起打和平精英.mp4" in got and "今天和嫂子一起打和平精英 .jpg" in got
          and not any("嫂子" in v.title for v in tab.videos if v.account == nick),
          f"放错了的视频和封面挪到和平精英号同一天的文件夹,列表里没了 -> {got}")
    check(tab._blocked.get(nick) == 2 or not tab._blocked.get(nick), f"挪走以后少了一条像别的游戏的 -> {tab._blocked}")
    # AI 的判断要「说得出标题里哪个词」、两遍一样才算(10-21 和平精英号「3v3无限火力」「冰河禁区」被误判)
    import json as _json
    import requests
    replies = iter([
        [{"i": 1, "game": "英雄联盟", "word": ""}, {"i": 2, "game": "暗区突围", "word": "冰河"},
         {"i": 3, "game": "王者荣耀", "word": "鲁班七号"}, {"i": 4, "game": "无畏契约", "word": "卡德尔"},
         {"i": 5, "game": "英雄联盟", "word": "亚索"}],
        [{"i": 1, "game": "英雄联盟", "word": ""}, {"i": 2, "game": "暗区突围", "word": "冰河"},
         {"i": 3, "game": "王者荣耀", "word": "鲁班七号"}, {"i": 4, "game": "看不出", "word": ""},
         {"i": 5, "game": "英雄联盟", "word": "不在标题里"}]])

    class _R:
        status_code, text = 200, ""

        def __init__(self, arr):
            self.arr = arr

        def json(self):
            return {"choices": [{"message": {"content": _json.dumps(self.arr, ensure_ascii=False)}}]}
    real_post = requests.post
    requests.post = lambda *a, **k: _R(next(replies))
    try:
        ts = ["3v3无限火力最新彩蛋密码", "不是吧冰河禁区提前进", "鲁班七号一套带走", "AMR淘汰卡德尔需要多少发子弹", "亚索快乐风男"]
        got = gamecheck._ask_once("和平精英", ts, "k", "m", "https://x", 5)
        got2 = {t: "" for t in ts}
        requests.post = lambda *a, **k: _R(next(replies))
        got2 = gamecheck._ask_once("和平精英", ts, "k", "m", "https://x", 5)
    finally:
        requests.post = real_post
    both = {t: (g if g and got2.get(t) == g else "") for t, g in got.items()}
    check(not got[ts[0]] and got[ts[2]] == "王者荣耀" and got[ts[4]] == "英雄联盟",
          f"说不出是哪个词的不算,说得出的算 -> {got}")
    check({t: g for t, g in both.items() if g} == {ts[1]: "暗区突围", ts[2]: "王者荣耀"} or
          {t: g for t, g in both.items() if g} == {ts[2]: "王者荣耀"},
          f"两遍一样才算:「卡德尔」一遍说是一遍说看不出 → 不算 -> {both}")
    check(gamecheck.AI_KEY == "ai2" and gamecheck.store().ai("任何标题") is None, "旧版 AI 答案(ai)不再用,换了新问法重新问")


def test_ux_fixes(tmp: Path):
    print("[五个人试用后改的(2026-10-21):会真发的确认框默认「先不」、选中了按钮写明白、默认选今天、卡片别假装没事、角标两位数]")
    import datetime
    import inspect
    from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc
    from qe.config import Settings, bj_now
    from qe.records import Records
    import gui.api_tab as T
    import gui.window as GW
    # A1:会真发出去的确认框:回车 = 先不,「好」那个画红
    seen = []
    real_exec = QMessageBox.exec
    QMessageBox.exec = lambda self: seen.append((self.defaultButton().text(), [b.objectName() for b in self.buttons()
                                                                               if b.text() == "开始摆,并自动发布"])) or 0
    try:
        _REAL_ASK(None, "摆下一批", "x", "开始摆,并自动发布", "先不", default_no=True, danger=True)
    finally:
        QMessageBox.exec = real_exec
    check(seen and seen[0] == ("先不", ["danger"]), f"自动点发布的确认框:默认「先不」、开始按钮红 -> {seen}")
    src = inspect.getsource(GW.MainWindow)
    check('"开始摆,并自动发布" if auto else "开始摆"' in src and "default_no=auto, danger=auto" in src,
          "教育号勾了「摆好后自动点发布」:摆下一批的确认框默认「先不」(原来回车就真发)")
    # B1:今天的文件夹在就默认选今天;昨天还剩的单独说
    today = f"{bj_now().month}.{bj_now().day}"
    y = bj_now() - datetime.timedelta(days=1)
    yday = f"{y.month}.{y.day}"
    root = tmp / "api_ux" / "游戏视频" / "CSGO--CSGO战神君"
    for dd, names in ((today, ["今天一", "今天二"]), (yday, ["昨天剩一", "昨天剩二"])):
        (root / dd).mkdir(parents=True, exist_ok=True)
        for nm in names:
            (root / dd / f"{nm}.mp4").write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"),
                  "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_ux.json")
    st["api_roots"] = [str(tmp / "api_ux" / "游戏视频")]
    st["api_last_date"] = yday
    st["quota_open"] = True
    tab = T.ApiTab(st, Records(tmp / "r_ux.sqlite"), lambda m: None)
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
    check(tab.day() == today, f"打开就选今天(上次选的是昨天也一样)-> {tab.day()}")
    check(tab._prev == (yday, 2) and tab.b_prev.isVisibleTo(tab) and "还剩 2 条" in tab.b_prev.text(),
          f"昨天还剩的单独写一行 -> {tab._prev} / {tab.b_prev.text()}")
    # A2:选中了几条:大按钮写「只发选中的」、旁边「✕ 取消选中」、大字下面写清楚
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
    tab._update_sum()
    tab._update_scope()
    check(tab.b_pub.text() == "现在发布 2 条" and not tab.b_unsel.isVisibleTo(tab), f"没选:照旧 -> {tab.b_pub.text()}")
    tab.items[0].setSelected(True)
    app.processEvents()
    check(tab.b_pub.text() == "只发选中的 1 条" and tab.b_pub.property("sel") and tab.b_unsel.isVisibleTo(tab)
          and "选中了 1 条" in tab.hero.sub.text() and tab.b_vert.text() == "转标准竖屏(选中 1 条)",
          f"选了 1 条:按钮写「只发选中的 1 条」换颜色,旁边能取消 -> {tab.b_pub.text()} / {tab.hero.sub.text()[:30]}")
    tab.b_unsel.click()
    check(not tab.selected_rows() and tab.b_pub.text() == "现在发布 2 条", "点「✕ 取消选中」回到全部")
    tab.items[0].setSelected(True)
    tab._seg_changed("ok")
    check(not tab.selected_rows(), "切「全部 / 要处理 / 能发…」自动取消选中")
    tab._seg_changed("all")
    tab.items[0].setSelected(True)
    tab._ask_title = lambda *a, **k: ("改过的标题", True)
    tab.edit_title(0)
    del tab._ask_title
    check(not tab.selected_rows(), "F2 改完标题自动取消选中")
    # 老手包:批量替换标题里的字(先预览、改完能撤销)
    from PySide6.QtWidgets import QDialog, QLineEdit as _QLE, QPlainTextEdit as _QPT
    real_dexec = QDialog.exec
    seen_pv = []

    def fake_dexec(dlg):
        eds = dlg.findChildren(_QLE)
        if len(eds) >= 2:
            eds[0].setText("今天")
            eds[1].setText("明天")
            seen_pv.append(dlg.findChild(_QPT).toPlainText())
            return QDialog.DialogCode.Accepted
        return real_dexec(dlg)
    QDialog.exec = fake_dexec
    try:
        tab.replace_titles()
    finally:
        QDialog.exec = real_dexec
    titles = sorted(v.title for v in tab.videos)
    check(seen_pv and "→ 明天" in seen_pv[0] and titles == ["改过的标题", "明天二"],
          f"批量替换:先预览,「今天」换成「明天」-> {titles}")
    real_ask = T.ask
    T.ask = lambda *a, **k: True
    try:
        tab.undo_topic()
    finally:
        T.ask = real_ask
    _settle(tab)
    check(sorted(v.title for v in tab.videos) == ["今天二", "改过的标题"], f"批量替换能撤销 -> {[v.title for v in tab.videos]}")
    tab._seg_changed("bad")
    check(tab.b_pub.text() == "点「全部」再发", f"看「要处理」时按钮说清楚为什么不能发 -> {tab.b_pub.text()}")
    tab._seg_changed("all")
    # D:没视频的日子:卡片不打绿勾;角标两位数不被切
    st2 = Settings(tmp / "st_ux2.json")
    st2["api_roots"] = [str(tmp / "api_ux_empty")]                # 别去读真的素材盘
    (tmp / "api_ux_empty").mkdir(exist_ok=True)
    empty = T.ApiTab(st2, Records(tmp / "r_ux2.sqlite"), lambda m: None)
    _wait(app, lambda: not empty.busy())
    check("还没查" in empty.card_v.title.text() and "还没查" in empty.card_t.title.text(),
          f"没视频 / 没检查:卡片写「还没查」,不打绿勾 -> {empty.card_v.title.text()}")
    from gui.widgets import set_badge, shell
    from PySide6.QtWidgets import QWidget
    root_w, grp, _stk = shell([("today", "今天", QWidget())], lambda: None)
    set_badge(grp, 0, "12")
    check(grp.badges[0].width() >= 24, f"角标两位数够宽 -> {grp.badges[0].width()}")


def test_packs(tmp: Path):
    print("[试用后的三包(2026-10-21):老板看数(出问题卡 / 多发变黄 / 两边各算各的批 / 摆好写号名)、新员工(小问号 / 没 Key 先改写法)、老手(点号全勾)]")
    from PySide6.QtWidgets import QApplication, QLabel, QTreeWidgetItem
    app = QApplication.instance() or QApplication([])
    from qe import folders as F
    from qe.config import Settings, bj_now
    from qe.records import Records
    import gui.api_tab as T
    import gui.window as GW
    (tmp / "pk_mat").mkdir(exist_ok=True)
    (tmp / "pk_api").mkdir(exist_ok=True)
    st = Settings(tmp / "st_pk.json")
    st["material_root"] = str(tmp / "pk_mat")
    st["api_roots"] = [str(tmp / "pk_api")]
    st["splash"] = False
    st["daily_plan"] = [{"cat": "教育", "label": "教育总发布量", "accounts": {"家长研习空间": 2}},
                        {"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 5}}]
    rec = Records(tmp / "r_pk.sqlite")
    md = f"{bj_now().month}.{bj_now().day}"
    for k in range(3):                                            # 教育号发了 3 条(规定 2 条 → 多发 1)
        rec.manual_published(F.Video(path=str(tmp / f"e{k}.mp4"), title=f"e{k}", account="家长研习空间", employee="梁", date=md))
        rec.api_result(F.Video(path=str(tmp / f"a{k}.mp4"), title=f"a{k}", account="CSGO战神君", employee="", date=md), "已发")
    rid = rec.api_begin(F.Video(path=str(tmp / "bad.mp4"), title="bad", account="CSGO战神君", employee="", date=md))
    rec.api_finish(rid, "没发成", "测试")
    rec.prepared(F.Video(path=str(tmp / "r1.mp4"), title="r1", account="家长小天地", employee="51", date=md), "批-1")
    p = rec.problems_on(bj_now().strftime("%Y-%m-%d"))
    check(p == {"fail": 1, "unsure": 0, "ready": 1}, f"今天出问题:没发成 1、摆好没确认 1 -> {p}")
    w = GW.MainWindow(st, rec)
    w.today.refresh(animate_=False)
    check(w.today.prob.isVisibleTo(w.today) and "出问题 2 条" in w.today.prob_t.text() and "没发成 1" in w.today.prob_s.text(),
          f"首页「今天出问题」卡 -> {w.today.prob_t.text()} / {w.today.prob_s.text()}")
    edu = w.today.rings["教育"][2].text()
    check(edu == "多发 1 条" and w.today.rings["教育"][2].property("tone") == "warn", f"多发了:写「多发 1 条」变黄,不是绿的「够了」-> {edu}")
    eta = w.today.lab_eta.text()
    check("教育号 1 批 3 条" in eta and "16 个号 1 批 3 条" in eta, f"今天发了这几批:教育号、16 个号各算各的 -> {eta}")
    w.show_problems()
    st_ = sorted(w.t_rec.item(r, 4).text() for r in range(w.t_rec.rowCount()))
    check(w.k_rec_bad.isChecked() and len(st_) == 2 and "没发成" in st_, f"点「出问题」:数据记录只看出问题的 -> {st_}")
    w.k_rec_bad.setChecked(False)
    w.daily.refresh()
    diffs = {w.daily.t.item(r, 1).text(): w.daily.t.item(r, 4).text() for r in range(w.daily.t.rowCount())}
    check(diffs.get("家长研习空间") == "多发 1" and diffs.get("CSGO战神君") == "还差 2", f"每日汇总:多发 / 还差 -> {diffs}")
    # 摆好的那批:软件重开以后也写号名
    w.batch_id, w.batch_videos, w._batch_acc = "批-1", [], "家长小天地"
    w.today._fill_next(False)
    texts = [x.text() for x in w.today.findChildren(QLabel) if "摆好了" in x.text()]
    check(any("「家长小天地」1 条摆好了" in x for x in texts), f"摆好的那批写号名和几条(原来是空的「」)-> {texts}")
    w.batch_id = ""
    # 小问号
    check(len(w.findChildren(QLabel, "helpDot")) >= 5, f"行话旁边有小问号 -> {len(w.findChildren(QLabel, 'helpDot'))}")
    # 老手:点号那一行 = 这个号的员工全勾 / 全不勾,只读一次
    loads = []
    real_load = w._load_videos
    w._load_videos = lambda: loads.append(1)
    top = QTreeWidgetItem(["家长研习空间", ""])
    for e in ("梁", "51"):
        it = QTreeWidgetItem([e, ""])
        it.setData(0, GW.Qt.ItemDataRole.UserRole + 2, "d")
        it.setCheckState(0, GW.Qt.CheckState.Unchecked)
        top.addChild(it)
    w.tree.addTopLevelItem(top)
    w._top_clicked(top)
    on = [top.child(k).checkState(0) == GW.Qt.CheckState.Checked for k in range(2)]
    w._top_clicked(top)
    off = [top.child(k).checkState(0) == GW.Qt.CheckState.Unchecked for k in range(2)]
    w._load_videos = real_load
    check(all(on) and all(off) and len(loads) == 2, f"点号那一行:全勾 / 再点全不勾,一次只读一遍 -> {on} {off} {loads}")
    # 新员工:没填 AI Key 的「整理标题」:不用 AI 的先改,要 AI 的跳过
    d = tmp / "pk_api" / "CSGO--CSGO战神君" / md
    d.mkdir(parents=True, exist_ok=True)
    for nm in ("甲 #a #b", "乙 ##c"):
        (d / f"{nm}.mp4").write_bytes(b"x")
    st2 = Settings(tmp / "st_pk2.json")
    st2["api_roots"] = [str(tmp / "pk_api")]
    st2["quota_open"] = True
    st2.ai_key = lambda: ""
    tab = T.ApiTab(st2, Records(tmp / "r_pk2.sqlite"), lambda m: None)
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
    seen = []
    real_ask = T.ask
    T.ask = lambda _p, _t, text, *a, **k: seen.append(text) or True
    try:
        tab.run_topic()
        _wait(app, lambda: not tab.busy())
    finally:
        T.ask = real_ask
    got = sorted(v.title for v in tab.videos)
    check(got == ["乙 #c", "甲 #a #b"] and seen and "还没填阿里百炼 Key" in seen[0],
          f"没 Key:写法不对的先改,挂好几个话题的跳过并说一声 -> {got}")


def test_clean_dirs(tmp: Path):
    print("[发完文件夹空了自动删(用户 2026-10-21):剩下的图挪进归档再删;手选的 10.2 发空了删 10.2,不动 10.1;没发完的不删]")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    root = tmp / "api_cl" / "游戏视频"
    acc = root / "CSGO--CSGO战神君"
    for d, names in (("10.1", ["一1", "一2"]), ("10.2", ["二1", "二2"])):
        (acc / d).mkdir(parents=True, exist_ok=True)
        for nm in names:
            (acc / d / f"{nm}.mp4").write_bytes(b"x")
            (acc / d / f"{nm}.jpg").write_bytes(b"j")
    (acc / "10.2" / "多的一张图.png").write_bytes(b"p")
    (acc / "10.2" / "Thumbs.db").write_bytes(b"t")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"),
                  "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_cl.json")
    st["api_roots"] = [str(root)]
    st["api_archive"] = str(tmp / "发布cl" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    st["quota_open"] = True
    st["api_picked"] = {"10.1": {"CSGO战神君": str(acc / "10.2")}}      # 这天手选的是 10.2

    class Fake:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, **k):
            if before_publish:
                before_publish("V")
            return {"vid": "V", "article_id": "A" + title, "transaction_id": "P", "status": "成功"}
    real = (omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning)
    omapi.Client, T.ask = Fake, (lambda *a, **k: True)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: 0)
    try:
        tab = T.ApiTab(st, Records(tmp / "r_cl.sqlite"), lambda m: None)
        tab.set_day("10.1")
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
        for v in tab.videos:
            v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
        tab._update_scope()
        # 先只发 1 条:还剩视频 → 不删
        tab.run_publish([0])
        _wait(app, lambda: not tab.busy())
        app.processEvents()
        check((acc / "10.2").is_dir(), "没发完(还剩视频):文件夹不删")
        for v in tab.videos:
            v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
        tab._update_scope()
        tab.run_publish()
        _wait(app, lambda: not tab.busy())
        _wait(app, lambda: not (acc / "10.2").exists(), 10)
        arc = sorted(os.listdir(tmp / "发布cl")) if (tmp / "发布cl").exists() else []
        moved = sorted(x for dd in arc for x in os.listdir(tmp / "发布cl" / dd / "CSGO"))
        check(not (acc / "10.2").exists() and (acc / "10.1").is_dir() and len(os.listdir(acc / "10.1")) == 4,
              f"手选的 10.2 发空了删 10.2;10.1 不动 -> 10.1 里 {sorted(os.listdir(acc / '10.1'))}")
        check("多的一张图.png" in moved and "二1.jpg" in moved and "Thumbs.db" not in moved,
              f"剩下的图挪进发布归档,Thumbs.db 删掉 -> {moved}")
        tab.load()                                        # 点「刷新」
        _wait(app, lambda: not tab.busy())
        check(not tab.videos and len(os.listdir(acc / "10.1")) == 4,
              f"手选的文件夹删了:这天这个号就没东西了,不会自己去找 10.1 列出来 -> {[v.title for v in tab.videos]}")
        check(acc.is_dir() and root.is_dir(), "号的总文件夹、素材根目录不动")
    finally:
        omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning = real


def test_edit_quota(tmp: Path):
    print("[每天规定条数自己改(用户 2026-10-22:有个号要从 10 条变成 30 条):每日汇总里双击一个号改]")
    from PySide6.QtWidgets import QApplication, QInputDialog
    app = QApplication.instance() or QApplication([])
    from qe import plan
    from qe.config import Settings
    from qe.records import Records
    from gui.daily_tab import DailyTab
    st = Settings(tmp / "st_eq.json")
    check(plan.quota_of(st, "DNF连招档案馆") == 10, "默认 DNF连招档案馆 每天 10 条")
    tab = DailyTab(st, Records(tmp / "r_eq.sqlite"))
    tab.refresh()
    row = next(r for r in range(tab.t.rowCount()) if tab.t.item(r, 1).text() == "DNF连招档案馆")
    real = QInputDialog.getInt
    QInputDialog.getInt = staticmethod(lambda *a, **k: (30, True))
    try:
        tab.edit_quota(row)
    finally:
        QInputDialog.getInt = real
    st2 = Settings(tmp / "st_eq.json")                               # 重新读一遍:存盘了
    row = next(r for r in range(tab.t.rowCount()) if tab.t.item(r, 1).text() == "DNF连招档案馆")
    check(plan.quota_of(st2, "DNF连招档案馆") == 30 and tab.t.item(row, 2).text() == "30" and tab.t.item(row, 4).text() == "还差 30",
          f"双击改成 30:存下来了,表里马上按 30 算 -> {tab.t.item(row, 2).text()} / {tab.t.item(row, 4).text()}")
    check(plan.quota_of(st2, "家长研习空间") == 102 and plan.quota_of(st2, "和平精英上分君") == 80, "别的号不变")
    check(plan.left_today(Records(tmp / "r_eq.sqlite"), st2, "DNF连招档案馆") == 30, "发够就停的闸也按新数算")


def test_extra_vert_order(tmp: Path):
    print("[今天临时多发 / 教育号转标准竖屏 / 发完的号沉底(用户 2026-10-23)]")
    import datetime
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, plan, vertical
    from qe import folders as F
    from qe.config import Settings, bj_now
    from qe.records import Records
    import gui.api_tab as T
    import gui.window as GW
    today_md = f"{bj_now().month}.{bj_now().day}"
    tmr = plan.tomorrow_folder()
    # ---- 今天临时多发:上限加 N(只管今天),明天文件夹里挪 N 条回来 ----
    root = tmp / "ev" / "游戏视频"
    for nick in ("CSGO战神君", "PUBG突围君", "DNF连招档案馆"):
        g = nick[:4]
        (root / f"{g}--{nick}" / today_md).mkdir(parents=True, exist_ok=True)
        for k in range(2):
            (root / f"{g}--{nick}" / today_md / f"{nick}{k}.mp4").write_bytes(b"x")
    (root / "CSGO--CSGO战神君" / tmr).mkdir(parents=True, exist_ok=True)
    for k in range(3):
        (root / "CSGO--CSGO战神君" / tmr / f"明天{k}.mp4").write_bytes(b"x")
        (root / "CSGO--CSGO战神君" / tmr / f"明天{k}.jpg").write_bytes(b"j")
    apiacc.save([{"nick": n, "source_name": n[:4], "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}
                 for n in ("CSGO战神君", "PUBG突围君", "DNF连招档案馆")])
    st = Settings(tmp / "st_ev.json")
    st["api_roots"] = [str(root)]
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 2, "PUBG突围君": 5, "DNF连招档案馆": 5}},
                        {"cat": "教育", "label": "教育总发布量", "accounts": {"家长小天地": 3}}]
    rec = Records(tmp / "r_ev.sqlite")
    for k in range(2):
        rec.api_result(F.Video(path=str(tmp / f"sent{k}.mp4"), title=f"s{k}", account="CSGO战神君", employee="", date=today_md), "已发")
    check(plan.left_today(rec, st, "CSGO战神君") == 0, "CSGO战神君 今天规定 2 条,发够了")
    tab = T.ApiTab(st, rec, lambda m: None)
    _wait(app, lambda: not tab.busy() and tab.videos)
    moved = tab.add_extra_today("CSGO战神君", 2)
    _wait(app, lambda: not tab.busy())
    here = sorted(os.listdir(root / "CSGO--CSGO战神君" / today_md))
    left_tmr = sorted(os.listdir(root / "CSGO--CSGO战神君" / tmr))
    # 打开页面时 CSGO 已经发够了:今天那 2 条先被挪到了明天;临时多发 2 条 → 挪回来的就是它俩(排在最前面)
    check(moved == 2 and plan.left_today(rec, st, "CSGO战神君") == 2 and here == ["CSGO战神君0.mp4", "CSGO战神君1.mp4"]
          and left_tmr == ["明天0.jpg", "明天0.mp4", "明天1.jpg", "明天1.mp4", "明天2.jpg", "明天2.mp4"],
          f"今天临时多发 2 条:今天还能发 2 条,明天文件夹挪回 2 条 -> 今天 {here} / 明天 {left_tmr}")
    tab.add_extra_today("CSGO战神君", 1)
    _wait(app, lambda: not tab.busy())
    here = sorted(os.listdir(root / "CSGO--CSGO战神君" / today_md))
    check("明天0.mp4" in here and "明天0.jpg" in here and plan.quota_on(st, "CSGO战神君") == 5,
          f"再多发 1 条:累加,封面跟着挪回来 -> {here}")
    y = (bj_now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    check(plan.quota_on(st, "CSGO战神君") == 5 and plan.quota_on(st, "CSGO战神君", y) == 2, "只管今天,明天还是原来的条数")
    s = plan.summary(rec, st, plan.today())
    check(("游戏", "CSGO战神君", 5, 2) in s["accounts"], f"每日汇总按 2+2 算 -> {s['accounts']}")
    # ---- 发完的号沉底 ----
    order = [tab.tree.topLevelItem(k).data(0, T.NICK) for k in range(tab.tree.topLevelItemCount())]
    pubg = [i for i, v in enumerate(tab.videos) if v.account == "PUBG突围君"]
    for i in pubg:
        tab.state[i] = "已发"
    tab._reorder()
    order2 = [tab.tree.topLevelItem(k).data(0, T.NICK) for k in range(tab.tree.topLevelItemCount())]
    check(order2[-1] == "PUBG突围君" and tab.groups["PUBG突围君"].text(0).endswith("· 发完了")
          and not tab.groups["PUBG突围君"].isExpanded(), f"发完的号沉到最下面、收起、写「发完了」-> {order} → {order2}")
    tab.k_undone.setChecked(True)
    check(all(tab.items[i].isHidden() for i in pubg) and not tab.groups["CSGO战神君"].isHidden(), "「只看没发完的号」:发完的藏起来")
    tab.k_undone.setChecked(False)
    # ---- 教育号:今天临时多发,从明天的文件夹挪回来(文件夹结构不变)----
    mat = tmp / "ev_mat"
    (mat / today_md / "小天地" / "51").mkdir(parents=True, exist_ok=True)
    (mat / today_md / "小天地" / "51" / "今天的.mp4").write_bytes(b"x")
    (mat / tmr / "小天地" / "51").mkdir(parents=True, exist_ok=True)
    (mat / tmr / "小天地" / "51" / "明天的.mp4").write_bytes(b"x")
    (mat / tmr / "小天地" / "51" / "明天的.png").write_bytes(b"p")
    st["material_root"] = str(mat)
    st["splash"] = False
    w = GW.MainWindow(st, rec)
    w.add_extra("家长小天地", 1)
    got = sorted(os.listdir(mat / today_md / "小天地" / "51"))
    check("明天的.mp4" in got and "明天的.png" in got and plan.quota_on(st, "家长小天地") == 1 + plan.quota_of(st, "家长小天地"),
          f"教育号今天临时多发 1 条:明天的那条连封面挪回今天(结构不变)-> {got}")
    # ---- 教育号转标准竖屏 ----
    ff = vertical.ffmpeg_path()
    if ff:
        import subprocess
        vd = tmp / "ev_vert"
        vd.mkdir(exist_ok=True)
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-t", "1",
                        "-c:v", "libx264", str(vd / "横的.mp4")], check=True)
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=25", "-t", "1",
                        "-c:v", "libx264", str(vd / "竖的.mp4")], check=True)
        vids = [F.Video(path=str(vd / "横的.mp4"), title="横的", account="家长小天地", employee="51", date=today_md),
                F.Video(path=str(vd / "竖的.mp4"), title="竖的", account="家长小天地", employee="51", date=today_md)]
        res = {}
        wk = GW.VertWorker(vids, [0, 1])
        wk.one.connect(lambda i, r: res.__setitem__(i, r))
        wk.run()
        app.processEvents()
        info0, info1 = vertical.probe(vids[0].path, ff), vertical.probe(vids[1].path, ff)
        check(res.get(0, "").startswith("转好了") and (info0["w"], info0["h"]) == (1080, 1920) and res.get(1) == ""
              and (info1["w"], info1["h"]) == (360, 640) and sorted(os.listdir(vd)) == ["横的.mp4", "竖的.mp4"],
              f"教育号转标准竖屏:横的转成 1080×1920(原片不留),竖的不动 -> {res} {info0} {sorted(os.listdir(vd))}")
    else:
        check(True, "(没有 ffmpeg,转竖屏那段跳过)")


def test_verify(tmp: Path):
    print("[去企鹅号核对(用户 2026-10-23):软件记的已发 vs 企鹅号上的;没发上的拎回来重发(挪回原文件夹、改没发成)]")
    from qe import folders as F
    from qe import verify
    from qe.config import bj_now
    from qe.records import Records
    day = bj_now().strftime("%Y-%m-%d")
    rec = Records(tmp / "r_vf.sqlite")
    src = tmp / "vf" / "游戏视频" / "CSGO--CSGO战神君" / "10.23"
    arc = tmp / "vf" / "发布" / "CSGO"
    src.mkdir(parents=True)
    arc.mkdir(parents=True)
    rows = {}
    for k, (title, aid) in enumerate((("在的", "A1"), ("审核中的", "A2"), ("被删的", "A3"), ("没上去的", "A4"), ("G镇大写", "A5"),
                                      ("后台搜得到", "A6"))):
        v = F.Video(path=str(src / f"{title}.mp4"), title=title, account="CSGO战神君", employee="", date="10.23")
        rid = rec.api_begin(v)
        rec.api_finish(rid, "已发", f"article_id={aid} vid=V{k}")
        (arc / f"{title}.mp4").write_bytes(b"x")
        (arc / f"{title}.jpg").write_bytes(b"j")
        rec.mark_moved(rid, str(arc / f"{title}.mp4"))
        rows[title] = rid
    now = bj_now().strftime("%Y-%m-%d %H:%M:%S")

    class Fake:
        def list_articles(self, page, limit):
            arts = [{"article_url": "http://kuaibao.qq.com/s/A100", "article_pub_flag": "发布成功", "article_pub_time": now,
                     "article_title": "在的", "article_video_info": {"vid": "V0"}},
                    {"article_id": "A2", "article_pub_flag": "审核中", "article_pub_time": now, "article_title": "审核中的"},
                    {"article_id": "A3", "article_pub_flag": "发布成功", "article_del_flag": "已删除", "article_pub_time": now,
                     "article_title": "被删的"},
                    {"article_id": "B9", "article_pub_flag": "发布成功", "article_pub_time": now, "article_title": "手动发的"},
                    {"article_id": "A5", "article_pub_flag": "发布成功", "article_pub_time": "2001-01-01 10:00:00", "article_title": "老的"}]
            return {"articles": arts if page == 1 else [], "total": "5"}

        def article_info(self, aid):
            return {"article_info": {"article_pub_flag": {"A4": "未发布", "A5": "发布成功", "A6": "发布成功"}.get(aid, "未发布"),
                                     "article_del_flag": "已删除" if aid == "A3" else "未删除",
                                     "article_pub_time": now if aid == "A6" else "2001-01-01 10:00:00"}}
    r = verify.check_account(Fake(), rec, "CSGO战神君", day)
    miss = {m["title"]: m["why"] for m in r["missing"]}
    sure = {m["title"]: m["sure"] for m in r["missing"]}
    check(r["ours"] == 6 and r["live"] == 4 and r["ok"] == 3 and r["review"] == 1 and set(miss) == {"被删的", "没上去的", "G镇大写"}
          and "删了" in miss["被删的"] and "未发布" in miss["没上去的"] and not sure["被删的"] and sure["没上去的"],
          f"核对:在的 / 审核中的 算对上;没上去的默认打勾,被删的列出来不打勾(多半是人自己删的)-> {r['ours']} {r['live']} {miss}")
    check(not sure["G镇大写"] and "单查是「发布成功」" in miss["G镇大写"] and "不是这天" in miss["G镇大写"],
          f"单查说发布成功、但发布时间不是这天的:列出来让人看(不默认打勾)-> {miss['G镇大写']}")
    check("后台搜得到" not in miss, "列表里没读到、单查是这天发布成功的:算对上(用户 2026-10-24:后台一搜就在,不是假发成功)")

    class Pages:
        def list_articles(self, page, limit):
            old = {"article_pub_flag": "发布成功", "article_pub_time": "2001-01-01 10:00:00", "article_title": "老"}
            pages = {1: [{"article_id": "P1", "article_pub_flag": "已发布", "article_pub_time": now, "article_title": "一"}],
                     2: [old] * 10, 3: [{"article_id": "P3", "article_pub_flag": "发布成功", "article_pub_time": now, "article_title": "三"}],
                     4: [old] * 10, 5: [old] * 10, 6: [old] * 10, 7: [{"article_id": "P7", "article_pub_time": now}]}
            return {"articles": pages.get(page, []), "total": "999"}
    got = verify.platform_on(Pages(), day)
    check([p["aid"] for p in got] == ["P1", "P3"], f"列表不严格按时间排:中间夹一页老的不停,连着 3 页老的才停 -> {[p['aid'] for p in got]}")
    check([e["title"] for e in r["extra"]] == ["手动发的"], f"企鹅号上有、软件没记的单独列 -> {[e['title'] for e in r['extra']]}")
    m = next(x for x in r["missing"] if x["title"] == "没上去的")
    check(verify.pull_back(rec, m) == "" and (src / "没上去的.mp4").is_file() and (src / "没上去的.jpg").is_file()
          and not (arc / "没上去的.mp4").exists() and rec.status_of(str(src / "没上去的.mp4")) == ""
          and rec.status_of(str(src / "在的.mp4")) == "已发",
          "拎回来重发:视频和封面挪回原来的文件夹(文件夹没了也建),记录改成没发成,能再发;别的不动")
    import shutil
    shutil.rmtree(src)
    m2 = next(x for x in r["missing"] if x["title"] == "被删的")
    check(verify.pull_back(rec, m2) == "" and (src / "被删的.mp4").is_file(), "原来的日期文件夹发空被删了:建回来再挪")
    check(len(rec.sent_on(day).items()) and rec.sent_on(day).get("CSGO战神君") == 4, "拎回来的不再算今天已发(发够就停的闸跟着让出名额)")
    # 窗口:每日汇总「去企鹅号核对」→ 表 + 没发上的打勾 →「拎回来重发」
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi
    from gui.verify_dialog import VerifyDialog
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    real = omapi.Client
    omapi.Client = lambda *a, **k: Fake()
    try:
        rid = rows["G镇大写"]
        rec.mark_unsent(rid, "")
        rec.conn.execute("UPDATE posts SET status='已发' WHERE id=?", (rid,))       # 再造一条「记成已发、平台没有」
        rec.conn.execute("UPDATE posts SET note='article_id=A9 vid=V9', moved_pkey=? WHERE id=?",
                         (os.path.normcase(str(arc / "G镇大写.mp4")), rid))
        rec.conn.commit()
        dlg = VerifyDialog(rec, day)
        _wait(app, lambda: not dlg.w.isRunning(), 20)
        app.processEvents()
        check(dlg.t.rowCount() == 1 and dlg.miss.count() == 1 and "G镇大写" in dlg.miss.item(0).text() and dlg.b_back.isEnabled()
              and dlg.t.horizontalHeaderItem(1).text() == "应发" and dlg.t.horizontalHeaderItem(3).text() == "还差",
              f"核对窗口:每个号一行(应发 / 实发 / 还差 …),假发成功的列出来打勾 -> {[dlg.miss.item(k).text() for k in range(dlg.miss.count())]}")
        dlg.pull_back()
        check((src / "G镇大写.mp4").is_file() and "拎回来 1 条" in dlg.lab_done.text(),
              f"点「拎回来重发」:挪回原文件夹,文件名大小写不变 -> {sorted(os.listdir(src))}")
        # 只查指定的号(右键一个号「去企鹅号核对…」)
        apiacc.save([{"nick": n, "source_name": n, "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}
                     for n in ("CSGO战神君", "PUBG突围君", "DNF连招档案馆")])
        dlg2 = VerifyDialog(rec, day, nicks=["PUBG突围君"])
        _wait(app, lambda: not dlg2.w.isRunning(), 20)
        app.processEvents()
        check(dlg2.t.rowCount() == 1 and dlg2.t.item(0, 0).text() == "PUBG突围君" and "PUBG突围君" in dlg2.windowTitle(),
              f"指定一个号核对:只查这一个 -> {[dlg2.t.item(k, 0).text() for k in range(dlg2.t.rowCount())]}")
        dlg3 = VerifyDialog(rec, day, nicks=["家长小天地"])
        check(dlg3.w is None and "教育号" in dlg3.lab_done.text(), "教育号指定核对:说清楚查不了")
        # 应发 / 实发 / 还差(带设置)
        from qe.config import Settings
        st = Settings(tmp / "st_vf.json")
        st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"PUBG突围君": 5, "CSGO战神君": 5}}]
        dlg4 = VerifyDialog(rec, day, nicks=["PUBG突围君"], st=st)
        _wait(app, lambda: not dlg4.w.isRunning(), 20)
        app.processEvents()
        row4 = [dlg4.t.item(0, c).text() for c in range(4)]
        check(row4 == ["PUBG突围君", "5", "3", "2"], f"应发 5、企鹅号上实发 3、还差 2 -> {row4}")
    finally:
        omapi.Client = real


def test_unsend(tmp: Path):
    print("[已发的手动改回没发(用户 2026-10-24):视频挪回原文件夹、记录改没发成;视频找不到也改记录并说清楚]")
    from qe import folders as F
    from qe import verify
    from qe.records import Records
    rec = Records(tmp / "r_us.sqlite")
    src = tmp / "us" / "src" / "10.24"
    arc = tmp / "us" / "arc"
    src.mkdir(parents=True)
    arc.mkdir(parents=True)
    v = F.Video(path=str(src / "a.mp4"), title="a", account="CSGO战神君", employee="", date="10.24")
    rid = rec.api_begin(v)
    rec.api_finish(rid, "已发", "article_id=X1 vid=Y1")
    (arc / "a.mp4").write_bytes(b"x")
    rec.mark_moved(rid, str(arc / "a.mp4"))
    row = rec.sent_row(str(arc / "a.mp4"))
    check(row and row["id"] == rid and rec.sent_row(str(src / "a.mp4"))["id"] == rid, "按原位置 / 挪去的位置都找得到这条已发记录")
    check(verify.unsend(rec, row) == "" and (src / "a.mp4").is_file() and rec.status_of(str(src / "a.mp4")) == "",
          "改回没发:视频挪回原来的文件夹,能再发")
    w = F.Video(path=str(src / "b.mp4"), title="b", account="CSGO战神君", employee="", date="10.24")
    rid2 = rec.api_begin(w)
    rec.api_finish(rid2, "已发", "article_id=X2 vid=Y2")
    rec.mark_moved(rid2, str(arc / "不见了.mp4"))
    msg = verify.unsend(rec, rec.sent_row(str(arc / "不见了.mp4")))
    check("视频没找到" in msg and rec.status_of(str(src / "b.mp4")) == "", f"视频找不到:记录照样改回没发,说清楚要自己放回去 -> {msg}")


def test_api_dups(tmp: Path):
    print("[16 个号查重(用户 2026-10-24):号 + 标题(去掉话题空格标点);发过同名的不发、同一天同名只发一条]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc
    from qe import folders as F
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    root = tmp / "dup" / "游戏视频"
    d = root / "CSGO--CSGO战神君" / "10.24"
    d.mkdir(parents=True)
    for nm in ("旧的", "同名 #CSGO", "同名", "新的"):
        (d / f"{nm}.mp4").write_bytes(b"x")
    (root / "PUBG--PUBG突围君" / "10.24").mkdir(parents=True)
    (root / "PUBG--PUBG突围君" / "10.24" / "旧的.mp4").write_bytes(b"x")
    apiacc.save([{"nick": n, "source_name": n[:4], "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}
                 for n in ("CSGO战神君", "PUBG突围君")])
    rec = Records(tmp / "r_dup.sqlite")
    rec.api_result(F.Video(path=str(tmp / "早就发了" / "旧的 #CSGO.mp4"), title="旧的 #CSGO", account="CSGO战神君", employee="",
                           date="10.20"), "已发")
    st = Settings(tmp / "st_dup.json")
    st["api_roots"] = [str(root)]
    st["quota_open"] = True
    tab = T.ApiTab(st, rec, lambda m: None)
    tab.set_day("10.24")
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 5)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920, tags=[], platform=[])
    tab._update_sum()

    def i_of(acc, title):
        return next(k for k, v in enumerate(tab.videos) if v.account == acc and v.title == title)
    old, s1, s2, new = (i_of("CSGO战神君", t) for t in ("旧的", "同名 #CSGO", "同名", "新的"))
    other = i_of("PUBG突围君", "旧的")
    check(not tab._can_send(old) and tab._dups.get(old) == "发过同名",
          f"这个号发过同名的(带话题的也认):不发,备注「发过同名」 -> {tab._dups.get(old)}")
    check(sum(1 for k in (s1, s2) if tab._can_send(k)) == 1 and (s1 in tab._dups) != (s2 in tab._dups)
          and set(tab._dups.values()) >= {"同一天有2条同名"},
          f"同一天同一个号同名的两条:只发一条,备注「同一天有2条同名」 -> {tab._dups}")
    check(tab._can_send(new) and tab._can_send(other), "不同名的、别的号的同名:照常能发")
    check(tab._status_text(old)[0] == "要处理", "重复的显示「要处理」")
    dup_i = s1 if s1 in tab._dups else s2
    tab._rename_rows([dup_i], lambda t: "改了个名", "改标题")
    check(tab._can_send(dup_i) and dup_i not in tab._dups, "让员工改个名:就能发了")
    # 处理重名(用户 2026-11-03):AI 想意思相近的,话题原样留着;想的和发过的重名就再想
    from qe import dupname
    tries = iter(["旧的", "旧事", "老的那条"])
    got = dupname.new_title("旧的 #CSGO", lambda full: full.startswith("旧事"), "k", asker=lambda b, av: next(tries))
    check(got == "老的那条 #CSGO", f"和原标题一样的、用过的都不要,再想;话题原样接上 -> {got}")
    check(dupname.new_title("一句很长很长的标题文字", lambda f: False, "k", asker=lambda b, av: "短") == "",
          "AI 回的字数差太多(风格变了):不用")
    real = (T.ask, tab.DUP_ASKER)
    T.ask = lambda *a, **k: True
    tab.DUP_ASKER = lambda b, av: b + "呀"
    try:
        tab.tree.clearSelection()
        tab.run_dupname()
    finally:
        T.ask = real[0]
        tab.DUP_ASKER = real[1]
    titles = sorted(v.title for v in tab.videos if v.account == "CSGO战神君")
    check("旧的呀" in titles and not tab._dups, f"处理重名:发过同名的那条改成新标题,就能发了 -> {titles}")
    # 按 Delete:挪进「重复删除」
    k = next(i for i, v in enumerate(tab.videos) if v.title == "新的")
    (d / "新的.jpg").write_bytes(b"x")
    tab.tree.clearSelection()
    tab.items[k].setSelected(True)
    T.ask = lambda *a, **kw: True
    try:
        tab.delete_dups()
    finally:
        T.ask = real[0]
    _wait(app, lambda: not tab.busy())
    check(os.path.isfile(d / "重复删除" / "新的.mp4") and os.path.isfile(d / "重复删除" / "新的.jpg") and not os.path.exists(d / "新的.mp4")
          and all(v.title != "新的" for v in tab.videos), "Delete:视频连封面挪进「重复删除」(不真删),列表里没了")


def test_view_tomorrow(tmp: Path):
    print("[切到明天的文件夹准备定时(用户 2026-10-24):今天发够了的号不算「发完了」,大字提示定到明天]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, plan
    from qe import folders as F
    from qe.config import Settings, bj_now
    from qe.records import Records
    import gui.api_tab as T
    tmr = plan.tomorrow_folder()
    root = tmp / "vt" / "游戏视频"
    (root / "CSGO--CSGO战神君" / tmr).mkdir(parents=True)
    for k in range(3):
        (root / "CSGO--CSGO战神君" / tmr / f"明天{k}.mp4").write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_vt.json")
    st["api_roots"] = [str(root)]
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 2}}]
    rec = Records(tmp / "r_vt.sqlite")
    for k in range(2):
        rec.api_result(F.Video(path=str(tmp / f"今天{k}.mp4"), title=f"今天{k}", account="CSGO战神君", employee="",
                               date=f"{bj_now().month}.{bj_now().day}"), "已发")
    tab = T.ApiTab(st, rec, lambda m: None)
    tab.set_day(tmr)
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 3)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920, tags=[], platform=[])
    tab._update_sum()
    tab._update_scope()
    g = tab.groups["CSGO战神君"]
    tab._fill_group("CSGO战神君")
    check(not tab._done("CSGO战神君") and "发完了" not in g.text(0) and "今天发够了" not in g.text(0),
          f"看明天的文件夹:不算发完、不沉底,也不写「今天发够了」(用户 2026-10-24:25 号都没发)-> {g.text(0)}")
    check(g.text(3).endswith(f"{tmr} 0/2"), f"号那一行的进度按这天算:{tmr} 发了 0 / 规定 2 -> {g.text(3)}")
    check(tab.hero.big.text().startswith("这天 3 条能发") and "到点自动发" in tab.hero.sub.text() and tab.b_pub.text() == "今天都发够了",
          f"大字:这天的用「到点自动发」;「现在发布」按今天算 -> {tab.hero.big.text()} / {tab.hero.sub.text()} / {tab.b_pub.text()}")
    check(tab._quota_sub() == f"{tmr}还差 2 条", f"还差几条按这天算 -> {tab._quota_sub()}")


def test_cover_move_keep(tmp: Path):
    print("[封面:「图片修改需求 (16).png」也认;挪了文件夹 / 去了黑边,调好的框还在(用户 2026-10-24)]")
    from PIL import Image
    from qe import folders as F
    from qe.adjust import Adjustments
    d = tmp / "cmk" / "10.25" / "研习社"
    sub = d / "家有儿童手表的注意啦，防止被骗要当心"
    sub.mkdir(parents=True)
    (d / "家有儿童手表的注意啦，防止被骗要当心.mp4").write_bytes(b"x")
    (d / "家有儿童手表的注意啦，防止被骗要当心.jpg").write_bytes(b"j")
    Image.new("RGB", (1280, 720), (100, 120, 140)).save(sub / "图片修改需求 (16).png")
    vs = F.scan_account(str(tmp / "cmk" / "10.25" / "研习社"), "家长研习空间", "10.25")
    check(vs and vs[0].png.endswith("图片修改需求 (16).png"), f"封面文件夹里只有「图片修改需求 (16).png」:认成无字封面 -> {[v.png for v in vs]}")
    adj = Adjustments(tmp / "adj_cmk.json")
    old_v, old_c = r"X:\素材\25\研习社\a.mp4", r"X:\素材\25\研习社\a\横屏16x9.png"
    adj.set_box(old_v, old_c, "0.750", 0.3, 0.4)
    adj.set_ok(old_v, old_c)
    new_v, new_c = r"X:\素材\10.25\研习社\a.mp4", r"X:\素材\10.25\研习社\a\横屏16x9.png"
    check(adj.manual(new_v, new_c, "a") == {"0.750": [0.3, 0.4]} and adj.is_ok(new_v, new_c, "a"),
          "视频从 25 挪到 10.25:调好的框、「这张没问题」都还在(按标题 + 封面图名字找回来)")
    cache = r"C:\数据\去黑边的封面\横屏16x9_0123456789_1792837650_12345.png"
    check(adj.manual(new_v, cache, "a") == {"0.750": [0.3, 0.4]}, "去了黑边(封面换成副本路径):框也还在")
    adj.set_box(new_v, new_c, "0.562", 0.5, 0.5, title="a")
    check(adj.manual(new_v, new_c, "a") == {"0.750": [0.3, 0.4], "0.562": [0.5, 0.5]}, "在新位置再调一个比例:原来调过的比例不丢")
    check(adj.manual(r"X:\素材\10.25\研习社\b.mp4", r"X:\素材\10.25\研习社\b\横屏16x9.png", "b") == {}, "别的标题不会串")


def test_export_and_edu_dims(tmp: Path):
    print("[核对能选日期、导出企业微信那样的表;教育号一勾员工就认出横屏 / 偏方(用户 2026-10-25)]")
    import subprocess
    import openpyxl
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import dimcache, vertical, verify
    from qe import folders as F
    from qe.config import Settings
    from qe.records import Records
    st = Settings(tmp / "st_ex.json")
    rec = Records(tmp / "r_ex.sqlite")
    day = "2026-10-25"
    rec.conn.execute("INSERT INTO posts(date,account,employee,title,path,status,published_at) VALUES('10.25','家长小天地','51','a','p1','已发','2026-10-25 09:00:00')")
    rec.conn.commit()
    results = {"PUBG突围君": {"live": 19}, "CSGO战神君": {"error": "x"}}
    p = tmp / "导出.xlsx"
    verify.export_xlsx(str(p), st, rec, day, results)
    ws = openpyxl.load_workbook(p).active
    head = [ws.cell(1, c).value for c in range(1, 5)]
    rows = {ws.cell(r, 2).value: [ws.cell(r, c).value for c in range(1, 5)] for r in range(2, ws.max_row + 1) if ws.cell(r, 2).value}
    tot = {ws.cell(r, 1).value: [ws.cell(r, 3).value, ws.cell(r, 4).value] for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value and not ws.cell(r, 2).value}
    check(head == ["品类", "账号名称", "规定视频条数", "10月25日"], f"表头和企业微信表一样 -> {head}")
    check(rows["PUBG突围君"] == ["PUBG", "PUBG突围君", 20, 19] and rows["DNF连招档案馆"][0] == "地下城与勇士"
          and rows["电竞情报馆"][0] == "亚运会电竞赛事", f"16 个号:品类写游戏名,实发用企鹅号上查到的 -> {rows['PUBG突围君']}")
    check(rows["家长小天地"][3] == 1 and rows["CSGO战神君"][3] == 0, "教育号 / 没查成的:按软件记录")
    check(tot.get("游戏总发布量") == [380, 19] and tot.get("教育总发布量", [0])[0] == 156 and tot.get("总发布量", [0])[0] == 736,
          f"小计:游戏 / 教育 / 动漫总发布量、总发布量 -> {tot}")
    check(any(str(m).startswith("A") and ":A" in str(m) for m in ws.merged_cells.ranges), f"教育、动漫的品类格子合并 -> {ws.merged_cells.ranges}")
    # 核对窗口:换日期重查
    from qe import apiacc, omapi
    from gui.verify_dialog import VerifyDialog
    apiacc.save([{"nick": "PUBG突围君", "source_name": "PUBG", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    asked = []

    class Fake:
        def list_articles(self, page, limit):
            asked.append(page)
            return {"articles": [], "total": "0"}

        def article_info(self, aid):
            return {}
    real = omapi.Client
    omapi.Client = lambda *a, **k: Fake()
    try:
        dlg = VerifyDialog(rec, "2026-10-24", st=st)
        _wait(app, lambda: not dlg.w.isRunning(), 20)
        dlg.start("2026-10-20")
        _wait(app, lambda: not dlg.w.isRunning(), 20)
        _wait(app, lambda: dlg.b_xls.isEnabled(), 5)
        check(dlg.day == "2026-10-20" and "10-20" in dlg.windowTitle() and dlg.t.rowCount() == 1 and dlg.b_xls.isEnabled(),
              f"核对窗口:能换日期重查,查完能导出 -> {dlg.windowTitle()}")
    finally:
        omapi.Client = real
    # 教育号:横屏 / 偏方认出来
    ff = vertical.ffmpeg_path()
    if not ff:
        check(True, "(没有 ffmpeg,横屏那段跳过)")
        return
    import gui.window as GW
    vd = tmp / "edu_dims"
    vd.mkdir()
    for nm, size in (("横的", "640x360"), ("方的", "480x480"), ("竖的", "360x640")):
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=25", "-t", "1", "-c:v", "libx264",
                        str(vd / f"{nm}.mp4")], check=True)
    vids = [F.Video(path=str(vd / f"{nm}.mp4"), title=nm, account="家长小天地", employee="51", date="10.25") for nm in ("横的", "方的", "竖的")]
    wk = GW.DimWorker(vids, [0, 1, 2])
    wk.run()
    check([getattr(v, "shape", "") for v in vids] == ["横屏", "偏方", ""], f"教育号读尺寸:横屏 / 偏方 / 竖的 -> {[getattr(v, 'shape', '') for v in vids]}")
    check(dimcache.get(str(vd / "横的.mp4")) == (640, 360), "读过的记着,下次不再读")


def test_black_border(tmp: Path):
    print("[封面去黑边(用户 2026-10-22):上下 / 左右的黑条去掉再裁、再传,原图不动;黑得太多的不去、标黄;暗的夜景不误伤]")
    from PIL import Image, ImageDraw
    from qe import apicover
    from qe import cover as C
    d = tmp / "bb"
    d.mkdir(exist_ok=True)
    im = Image.new("RGB", (2048, 1152), (0, 0, 0))
    ImageDraw.Draw(im).rectangle([0, 82, 2047, 1068], fill=(120, 160, 90))
    p = d / "横屏16x9.png"
    im.save(p)
    out, why = C.deborder(str(p))
    got = Image.open(out).size if out != str(p) else None
    check(why == "" and got and got[0] == 2048 and 980 <= got[1] <= 987 and C.orig_of(out) == str(p)
          and Image.open(p).size == (2048, 1152), f"上下黑条去掉,原图不动 -> {got}")
    check(C.deborder(str(p))[0] == out, "做过的副本直接用(不重复做)")
    import numpy as _np
    rng = _np.random.default_rng(1)
    sky = _np.clip(rng.normal(12, 7, (600, 800, 3)), 0, 255).astype(_np.uint8)       # 夜空:很暗,但有噪点(真照片都有)
    night = Image.fromarray(sky)
    ImageDraw.Draw(night).ellipse([300, 200, 500, 400], fill=(230, 220, 120))
    pn = d / "夜景.png"
    night.save(pn)
    check(C.deborder(str(pn)) == (str(pn), ""), "暗的夜景:不当成黑边")
    tall = Image.new("RGB", (1152, 2048), (0, 0, 0))
    ImageDraw.Draw(tall).rectangle([0, 900, 1151, 1250], fill=(200, 100, 100))
    pt = d / "竖屏9x16.png"
    tall.save(pt)
    check(C.deborder(str(pt)) == (str(pt), "too_wide"), "大半是黑的(横图塞进竖画布):不去,交给人看")
    clean = d / "干净.png"
    Image.new("RGB", (640, 360), (200, 200, 200)).save(clean)
    check(C.deborder(str(clean)) == (str(clean), ""), "没黑边:用原图")
    # 16 个号传的封面:原样模式也去黑边
    up = apicover.prepare(str(p), "原样")
    check(up != str(p) and Image.open(up).size[1] < 1000, f"16 个号的封面:有黑边的去掉再传 -> {Image.open(up).size}")
    apicover.cleanup(up, str(p))
    check(apicover.prepare(str(clean), "原样") == str(clean), "16 个号的封面:没黑边的原图照传")


def test_quota_gate(tmp: Path):
    print("[每天规定条数的闸(2026-10-20 PUBG 多发了 21 条):不能多发、没发成的补上、多的挪到明天、开闸才不管;转竖屏不留原片]")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, plan, vertical
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    tmr = plan.tomorrow_folder()
    root = tmp / "api_q"
    accs = [("CSGO", "CSGO战神君")]
    apiacc.save([{"nick": n, "source_name": g, "client_id": g, "secret": apiacc.seal("s"), "category": 1604, "enabled": True} for g, n in accs])
    st = Settings(tmp / "st_q.json")
    check(st.get("quota_open") is False, "默认闸关着(不能超过每天规定条数)")
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 3}},
                        {"cat": "教育", "label": "教育总发布量", "accounts": {"家长小天地": 2}}]
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "发布q" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    sent = []

    class Fake:
        def __init__(self, *a, **k):
            pass

        def send(self, path, title, cat, before_publish=None, **k):
            if "坏" in title:
                raise omapi.ApiError("上传视频失败:invalid_file_upload(code 40023)", "40023")
            if before_publish:
                before_publish("V")
            sent.append(title)
            return {"vid": "V", "article_id": "A" + title, "transaction_id": "P", "status": "成功"}
    real = (omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning)
    boxes = []
    omapi.Client, T.ask = Fake, (lambda *a, **k: True)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda _p, t, x, *a, **k: boxes.append(x) or 0)
    try:
        def run(names, rec_name):
            d = root / "游戏视频" / "CSGO--CSGO战神君" / "10.20"
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
            for nm in names:
                (d / f"{nm}.mp4").write_bytes(b"x")
                (d / f"{nm}.jpg").write_bytes(b"j")
            shutil.rmtree(root / "游戏视频" / "CSGO--CSGO战神君" / tmr, ignore_errors=True)
            rec = Records(tmp / rec_name)
            tab = T.ApiTab(st, rec, lambda m: None)
            tab.set_day("10.20")
            _wait(app, lambda: not tab.busy() and len(tab.videos) == len(names))
            for v in tab.videos:
                v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
            tab._update_scope()
            tab._update_sum()
            return tab, rec
        tab, rec = run(["q1", "q2", "q3", "q4", "q5"], "rq1.sqlite")
        check(tab.b_pub.text() == "现在发布 3 条" and "超过今天的规定条数" in tab.hero.sub.text(),
              f"按钮只写规定条数以内的;大字下面写多的发够以后挪到明天 -> {tab.b_pub.text()} / {tab.hero.sub.text()}")
        sent.clear()
        tab.run_publish()
        _wait(app, lambda: not tab.busy(), 30)
        app.processEvents()
        moved = sorted(os.listdir(root / "游戏视频" / "CSGO--CSGO战神君" / tmr)) if (root / "游戏视频" / "CSGO--CSGO战神君" / tmr).exists() else []
        check(sorted(sent) == ["q1", "q2", "q3"] and moved == ["q4.jpg", "q4.mp4", "q5.jpg", "q5.mp4"],
              f"规定 3 条:发 3 条就停,多的 2 条连封面挪到明天的文件夹({tmr})-> 发了 {sent},挪了 {moved}")
        tab, rec = run(["q1", "坏2", "q3", "q4", "q5"], "rq2.sqlite")
        sent.clear()
        tab.run_publish()
        _wait(app, lambda: not tab.busy(), 30)
        app.processEvents()
        moved = sorted(x for x in os.listdir(root / "游戏视频" / "CSGO--CSGO战神君" / tmr) if x.endswith(".mp4"))
        check(sorted(sent) == ["q1", "q3", "q4"] and moved == ["q5.mp4", "坏2.mp4"],
              f"中间一条没发成:拿下一条补上,还是发够 3 条(不少发);没发成的也挪到明天 -> 发了 {sent},挪了 {moved}")
        boxes.clear()
        tab, rec2 = run(["q6", "q7"], "rq2.sqlite")               # 同一个记录库:今天已经发够 3 条了
        sent.clear()
        tab.run_publish()
        app.processEvents()
        moved = sorted(x for x in os.listdir(root / "游戏视频" / "CSGO--CSGO战神君" / tmr) if x.endswith(".mp4"))
        check(not sent and (not tab.videos or (boxes and "已经发够" in boxes[-1])) and moved == ["q6.mp4", "q7.mp4"],
              f"今天已经发够的号:不发,还没发的挪到明天 -> {boxes[-1][:40] if boxes else ''} {moved}")
        # 打开 / 刷新页面时:今天已经发够的号,今天日期文件夹里没发的自动挪到明天(名字差个空格的封面也跟着)
        from qe.config import bj_now
        today_md = f"{bj_now().month}.{bj_now().day}"
        td = root / "游戏视频" / "CSGO--CSGO战神君" / today_md
        td.mkdir(parents=True, exist_ok=True)
        (td / "今天的.mp4").write_bytes(b"x")
        (td / "今天的 .jpg").write_bytes(b"j")
        st["api_picked"] = {"10.20": {"CSGO战神君": str(td)}}
        tab = T.ApiTab(st, Records(tmp / "rq2.sqlite"), lambda m: None)   # 这个记录库里 CSGO 今天已经发够 3 条
        tab.set_day("10.20")
        _wait(app, lambda: not tab.busy(), 30)
        app.processEvents()
        moved = sorted(os.listdir(root / "游戏视频" / "CSGO--CSGO战神君" / tmr))
        check("今天的.mp4" in moved and "今天的 .jpg" in moved and not os.listdir(td) and not tab.videos,
              f"打开页面:今天发够的号,今天文件夹里没发的自动挪到明天(差个空格的封面也挪)-> {[m for m in moved if '今天' in m]}")
        st["api_picked"] = {}
        st["quota_open"] = True
        tab, rec = run(["q1", "q2", "q3", "q4", "q5"], "rq3.sqlite")
        sent.clear()
        tab.run_publish()
        _wait(app, lambda: not tab.busy(), 30)
        check(len(sent) == 5 and tab.b_pub.text() != "现在发布 3 条", f"开了闸:能发的都发 -> {sent}")
        st["quota_open"] = False
    finally:
        omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning = real
    # 教育号:最后一批只摆差的那几条;发够了还没发的挪到明天(文件夹结构不变)
    import gui.window as GW
    from qe import folders as F
    eroot = tmp / "素材q"
    d = eroot / "10.20" / "小天地" / "张"
    d.mkdir(parents=True)
    for t in ("一一一一视频", "二二二二视频", "三三三三视频"):
        (d / f"{t}.mp4").write_bytes(b"x")
        _img(d / f"{t}.png", 640, 360)
    st["material_root"] = str(eroot)
    rec = Records(tmp / "rq_edu.sqlite")
    real_dec = GW.C.decide

    def fake_decide(v):
        v.cover, v.cover_kind, v.cover_why, v.plan, v.warn = v.png, "png", "测试", {}, False
    GW.C.decide = fake_decide
    try:
        w = GW.MainWindow(st, rec)
        w.c_date.setCurrentIndex(w.c_date.findData("10.20"))
        from PySide6.QtCore import Qt
        top = next(w.tree.topLevelItem(k) for k in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(k).text(0) == "家长小天地")
        top.child(0).setCheckState(0, Qt.CheckState.Checked)
        _wait(app, lambda: not (w.cover_worker and w.cover_worker.isRunning()))
        acc, vids = w.next_batch()
        check(acc == "家长小天地" and len(vids) == 2, f"教育号规定 2 条:一批只摆 2 条 -> {len(vids)}")
        rec.manual_published(vids[0])
        acc, vids2 = w.next_batch()
        check(len(vids2) == 1, f"今天发了 1 条:下一批只摆差的 1 条 -> {len(vids2)}")
        rec.manual_published(vids2[0])
        check(w.next_batch()[1] == [] and "发够规定条数" in w._nothing_left(), "发够了:不再摆,写清楚发够了")
        n = w._edu_spill()
        left = [p.name for p in (eroot / tmr / "小天地" / "张").glob("*")] if (eroot / tmr).exists() else []
        rest = next(v.title for v in w.videos if v not in (vids[0], vids2[0]))
        check(n == 1 and sorted(left) == [f"{rest}.mp4", f"{rest}.png"],
              f"还没发的连封面挪到明天的文件夹,结构不变(小天地\\张)-> {left}")
        w.close()
    finally:
        GW.C.decide = real_dec
    # 转竖屏不留原片(16 个号页,用户 2026-10-20)
    ff = vertical.ffmpeg_path()
    if ff:
        import subprocess
        vd = tmp / "vq"
        vd.mkdir()
        subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-t", "1",
                        "-c:v", "libx264", str(vd / "横.mp4")], check=True)
        out, orig = vertical.to_vertical(str(vd / "横.mp4"), ff, keep_orig=False)
        info = vertical.probe(out, ff) if hasattr(vertical, "probe") else None
        check(orig == "" and os.path.basename(out) == "横.mp4" and not (vd / "横屏原片").exists() and sorted(os.listdir(vd)) == ["横.mp4"]
              and os.path.getsize(out) > 1024, f"转竖屏不留原片:转好的放回原名,原片删了,不建「横屏原片」-> {os.listdir(vd)}")
        del info


def test_misfire_api(tmp: Path):
    print("[防误发 · 16 个号(改进清单 A1 A2):按钮叫「现在发布 N 条」、定时挪开;确认框默认「先不发」、红字写现在马上发、能改成定时]")
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    import gui.schedule as S
    root = tmp / "api_misfire"
    (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18").mkdir(parents=True)
    for f in ("m1.mp4", "m2.mp4"):
        (root / "游戏视频" / "CSGO--CSGO战神君" / "10.18" / f).write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_misfire.json")
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "发布misfire" / "{date}")
    tab = T.ApiTab(st, Records(tmp / "rec_misfire.sqlite"), lambda m: None)
    tab.c_date.setCurrentText("10.18")
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, w=1080, h=1920)
    tab._update_scope()
    check(tab.b_pub.text() == "现在发布 2 条" and tab.b_sched.text() == "到点自动发…",
          f"按钮名字:「{tab.b_pub.text()}」「{tab.b_sched.text()}」")
    bar = next(lay for lay in tab.findChildren(QHBoxLayout) if lay.indexOf(tab.b_pub) >= 0)
    check(bar.indexOf(tab.b_sched) >= 0 and bar.indexOf(tab.b_pub) - bar.indexOf(tab.b_sched) >= 3,
          "定时按钮挪开了,不和「现在发布」挨着(中间隔着红字和空白)")
    seen, opened = [], []
    real = (T.ask, S.ask_schedule)

    def rec_ask(*a, **k):
        seen.append(k)
        if k.get("on_extra"):
            k["on_extra"]()                         # 人点了「改成定时…」
        return False
    T.ask = rec_ask
    S.ask_schedule = lambda _p, title, *a, **k: opened.append(title)
    try:
        tab.run_publish()
    finally:
        T.ask, S.ask_schedule = real
    k = seen[-1] if seen else {}
    check(k.get("default_no") is True and "现在马上发出去" in k.get("head", "") and "后台删" in k.get("head", ""),
          f"发布确认框:默认「先不发」,第一行写现在马上发、发了只能去后台删 -> {k.get('head')}")
    check(k.get("extra") == "改成定时…" and opened and "16 个号" in opened[0], "确认框里点「改成定时…」打开定时对话框")
    check(not tab.busy(), "点了「改成定时…」不会发")
    # 真的确认框:回车 = 默认按钮 =「先不发」
    clicks, hit = [], []
    real_exec = QMessageBox.exec

    def fake_exec(box):
        want = clicks.pop(0) if clicks else box.defaultButton().text()
        seen.append(("box", box.defaultButton().text(), box.text()))
        next(b for b in box.buttons() if b.text() == want).click()
        return 0
    QMessageBox.exec = fake_exec
    try:
        r1 = T._real_ask(tab, "现在发布", "发 2 条", "现在发出去", "先不发", default_no=True,
                         head="现在马上发出去(不是定时),发了只能去后台删", extra="改成定时…", on_extra=lambda: hit.append(1))
        b1 = seen[-1]
        clicks.append("改成定时…")
        r2 = T._real_ask(tab, "现在发布", "发 2 条", "现在发出去", "先不发", default_no=True, extra="改成定时…",
                         on_extra=lambda: hit.append(1))
        clicks.append("现在发出去")
        r3 = T._real_ask(tab, "现在发布", "发 2 条", "现在发出去", "先不发", default_no=True)
    finally:
        QMessageBox.exec = real_exec
    from gui.theme import cur as _theme_cur              # 红字 = 主题里的「危险」红(2026-10-18 换了新界面)
    check(r1 is False and b1[1] == "先不发" and _theme_cur()["danger"] in b1[2] and "现在马上发出去" in b1[2],
          f"确认框直接回车 = 先不发,第一行红字 -> {b1[1]}")
    check(r2 is False and hit == [1] and r3 is True, "点「改成定时…」不发、去定时;点「现在发出去」才发")
    tab.deleteLater()


def test_misfire_edu(tmp: Path):
    print("[防误发 + 定时可靠性 · 教育号(改进清单 A1 A3 A4 B5~B8)]")
    from PySide6.QtCore import QObject, QTimer, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    import datetime as dt
    import gui.schedule as S
    import gui.window as GW
    from qe.config import Settings
    from qe.records import Records
    root = tmp / "素材misfire"
    d = root / "10.20" / "小天地" / "王"
    d.mkdir(parents=True)
    for k in range(5):
        (d / f"误发测试第{k}条.mp4").write_bytes(b"x")
        _img(d / f"误发测试第{k}条.png", 640, 360)
    H = {"w": None, "mode": "ok"}
    calls = []

    class FakeBW(QObject):
        log = Signal(str)
        one = Signal(object, bool, str)
        finished_batch = Signal(object, str, str)

        def __init__(self, acc, vids, shots, parent=None, auto_publish=False, unattended=False, sched_at=""):
            super().__init__(parent)
            self.vids = vids
            calls.append([v.title for v in vids])

        def isRunning(self):
            return False

        def stop(self):
            pass

        def start(self):
            def go():
                w, mode = H["w"], H["mode"]
                if mode == "fail":                  # 一条都没摆上(罐头没开)
                    self.finished_batch.emit([], "罐头没开", "")
                    return
                if mode == "stopmid":               # 摆的时候人点了「停」,但这批照样定好了
                    w._chain_stop = True
                res = []
                for v in self.vids:
                    self.one.emit(v, True, "")
                    res.append((v, True, ""))
                self.finished_batch.emit(res, "", "ok")
                if mode == "tamper":                # 摆完这批,有人改了勾选
                    w._chain_key = ("别的日期", [])
            QTimer.singleShot(0, go)

    def fake_decide(v):
        v.cover, v.cover_kind, v.cover_why, v.plan = v.png, "png", "测试", {}
        v.warn = False
    real = (GW.BatchWorker, GW.C.decide, GW.C.note_wide, QMessageBox.information, S.ask_schedule)
    boxes = []
    GW.BatchWorker, GW.C.decide, GW.C.note_wide = FakeBW, fake_decide, (lambda v: None)
    QMessageBox.information = staticmethod(lambda _p, t, x, *a, **k: boxes.append(x))
    try:
        rec = Records(tmp / "r_misfire.sqlite")
        st = Settings(tmp / "s_misfire.json")
        st["material_root"] = str(root)
        st["api_roots"] = [str(tmp / "api_none")]
        st["ai_key"] = "test"
        st["batch_size"] = 1
        st["auto_publish"] = True                   # 老版本记住过「勾着」
        st.save()
        w = GW.MainWindow(st, rec)
        H["w"] = w
        check(not w.k_auto.isChecked(), "「摆好后自动点发布」每次打开都不勾(以前记住的也不算)")
        w.k_auto.setChecked(True)
        w.k_auto.setChecked(False)
        check(Settings(tmp / "s_misfire.json").get("auto_publish") is True, "勾 / 不勾都不再存进设置")
        w.k_auto.setChecked(True)
        check(w.b_sched.text() == "摆好并定时发出…", f"教育号定时按钮叫「摆好并定时发出…」-> {w.b_sched.text()}")
        # A3:勾着时「摆下一批」确认框第一行红字
        w.c_date.setCurrentIndex(w.c_date.findData("10.20"))
        w._load_tree()
        for k in range(w.tree.topLevelItemCount()):
            top = w.tree.topLevelItem(k)
            for j in range(top.childCount()):
                top.child(j).setCheckState(0, GW.Qt.CheckState.Checked)
        w._load_videos()
        _wait(app, lambda: not (w.cover_worker and w.cover_worker.isRunning()))
        asks = []

        def rec_ask(title, text, yes, no, default_no=False, head="", danger=False):
            asks.append({"title": title, "text": text, "yes": yes, "default_no": default_no, "head": head, "danger": danger})
            return False
        w._ask = rec_ask
        w.start_batch()
        check(asks and "这次会自动点发布" in asks[-1]["head"] and not calls, f"勾着自动发布:确认框第一行红字写「这次会自动点发布」-> {asks[-1]['head'] if asks else ''}")
        check(asks[-1]["default_no"] is True and asks[-1]["danger"] and asks[-1]["yes"] == "开始摆,并自动发布",
              f"勾着自动发布:默认「先不」(回车不会真发),开始按钮红、写「并自动发布」-> {asks[-1]['yes']}")
        w.k_auto.setChecked(False)
        w.start_batch()
        check(asks[-1]["head"] == "" and asks[-1]["default_no"] is False and asks[-1]["yes"] == "开始摆", "没勾:没有那行红字,照旧")
        # A4:「这批发好了」默认「还没」
        w.batch_id = "假的一批"
        w.batch_sent()
        check(asks[-1]["title"] == "这批发好了" and asks[-1]["default_no"] is True and "不会再摆" in asks[-1]["text"]
              and w.batch_id == "假的一批", "「这批发好了」默认按钮是「还没」,写清楚点了这批不会再摆")
        w.batch_id = ""
        w._refresh_buttons()
        # B7:估时间够不够
        check(w._sched_estimate("10.20") == (5, 5), f"估算:5 条、一批 1 条 = 5 批 -> {w._sched_estimate('10.20')}")
        now = dt.datetime.strptime(S.now_str(), "%Y-%m-%d %H:%M")

        def slot(mins):
            t = now + dt.timedelta(minutes=mins)
            t += dt.timedelta(minutes=(5 - t.minute % 5) % 5)
            return t.strftime("%Y-%m-%d %H:%M")
        at_near, at_far = slot(45), slot(180)
        answers = [(at_near, "10.20"), None]
        S.ask_schedule = lambda *a, **k: answers.pop(0) if answers else None
        asks.clear()
        w.schedule_clicked()
        check(asks and asks[0]["title"] == "时间可能不够" and "5 批" in asks[0]["text"] and asks[0]["default_no"] is True
              and not w._unattended, f"5 批只给 45 分钟:先提示时间可能不够(默认「改时间」)-> {[a['title'] for a in asks]}")
        answers[:] = [(at_far, "10.20")]
        asks.clear()
        w.schedule_clicked()
        check([a["title"] for a in asks] == ["定时发布"], f"时间够:不提示 -> {[a['title'] for a in asks]}")
        # B5:摆的时候点了「停」,这批照样定好了 → 停下,不再接着摆;总结不写「电脑可以关了」
        H["mode"] = "stopmid"
        calls.clear()
        boxes.clear()
        w._sched_fire("10.20", at_far)
        _wait(app, lambda: not w._unattended, 20)
        check(not w._unattended and len(calls) == 1, f"点了「停」就停,不再接着摆(以前会被成功那批吃掉)-> {len(calls)} 批")
        check(boxes and "停在这里" in boxes[-1] and "还有 4 条没定" in boxes[-1] and "电脑可以关" not in boxes[-1],
              f"停下的总结:停在哪、还剩几条,不说电脑可以关 -> {boxes[-1][:120] if boxes else ''}")
        # B8:连发中途有人改了勾选 → 不弹「自动发布停下了」卡住,写日志收尾
        H["mode"] = "tamper"
        calls.clear()
        boxes.clear()
        w._sched_fire("10.20", at_far)
        _wait(app, lambda: not w._unattended, 20)
        check(not w._unattended and len(calls) == 1 and boxes and "换了日期" in boxes[-1] and "停在这里" in boxes[-1],
              f"没人看着时改了勾选:收尾写总结,不卡住 -> {boxes[-1][:60] if boxes else ''}")
        # B6:之前点过「停」(_chain_stop 还是 True),再开定时、第一批整批出错 → 1 分钟后照样重试,发到完
        w._chain_stop = True
        H["mode"] = "fail"
        calls.clear()
        boxes.clear()
        w._sched_fire("10.20", at_far)
        _wait(app, lambda: "1 分钟后再试" in w.logbox.toPlainText(), 10)
        check(w._unattended and not w._chain_stop and len(calls) == 1, "再开定时:以前点过的「停」清掉了,整批出错等着重试")
        H["mode"] = "ok"
        w._sched_next()                             # 当它 1 分钟到了
        _wait(app, lambda: not w._unattended, 30)
        check(not w._unattended and len(calls) == 4 and boxes and "都定好了" in boxes[-1] and "电脑可以关" in boxes[-1],
              f"重试成功,剩下的都定好了,写「电脑可以关了」-> {len(calls)} 批 {boxes[-1][:40] if boxes else ''}")
        # 重试等着的时候点了「停」:到点收尾,不会一直「正在自己发」
        w._unattended, w._chain_stop = True, True
        boxes.clear()
        w._sched_next()
        check(not w._unattended and boxes and "停" in boxes[-1], "等重试的时候点了停:收尾")
        w.close()
    finally:
        GW.BatchWorker, GW.C.decide, GW.C.note_wide, QMessageBox.information, S.ask_schedule = real


def test_sched_notice(tmp: Path):
    print("[16 个号定时没开始 / 没发成(改进清单 B9):⏰ 那行红字常驻,下次打开弹一次]")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    st = Settings(tmp / "st_notice.json")
    st["api_roots"] = [str(tmp / "api_notice_none")]
    rec = Records(tmp / "rec_notice.sqlite")
    warns = []
    real_w = QMessageBox.warning
    QMessageBox.warning = staticmethod(lambda _p, t, x, *a, **k: warns.append(x))
    try:
        tab = T.ApiTab(st, rec, lambda m: None)
        tab._sched_fire("9.99")
        note = (st.get("sched_notice") or {}).get("api") or {}
        check("没发成" in tab.lab_sched.text() and "9.99" in tab.lab_sched.toolTip() and note.get("popped") is False,
              f"到点没开始:红字常驻,鼠标放上去看为什么 -> {tab.lab_sched.text()}")
        _wait(app, lambda: False, 2)
        check(not warns, "当时不弹框(已经有红字了),等下次打开再弹")
        tab2 = T.ApiTab(Settings(tmp / "st_notice.json"), rec, lambda m: None)
        _wait(app, lambda: bool(warns), 5)
        check(len(warns) == 1 and "9.99" in warns[0], "下次打开软件弹一次框")
        tab3 = T.ApiTab(Settings(tmp / "st_notice.json"), rec, lambda m: None)
        _wait(app, lambda: len(warns) > 1, 3)
        check(len(warns) == 1 and "没发成" in tab3.lab_sched.text(), "只弹一次;红字还在(重新定时才清掉)")
        tab3._clear_notice()
        tab3._sched_changed()
        check(tab3.lab_sched.text() == "", "重新定时以后红字清掉")
        st4 = Settings(tmp / "st_notice.json")
        st4["schedules"] = {"api": {"at": "2000-01-01 09:00", "date": "10.17"}}
        st4.save()
        tab4 = T.ApiTab(st4, rec, lambda m: None)
        check("软件没开着" in ((st4.get("sched_notice") or {}).get("api") or {}).get("msg", "") and "没发成" in tab4.lab_sched.text(),
              "到点时软件没开着:也红字常驻")
        _wait(app, lambda: len(warns) > 1, 5)
        check(len(warns) == 2 and "软件没开着" in warns[-1], "到点时软件没开着:这次打开就弹一次")
        # 用户 2026-10-24:10-21 那条红字挂了好几天 → 点一下看完就清;不是今天的不再挂
        infos = []
        real_i = QMessageBox.information
        QMessageBox.information = staticmethod(lambda _p, t, x, *a, **k: infos.append(x))
        try:
            tab4._ack_notice()
        finally:
            QMessageBox.information = real_i
        check(infos and "软件没开着" in infos[0] and tab4.lab_sched.text() == "", "点一下红字:说为什么,然后清掉")
        st5 = Settings(tmp / "st_notice.json")
        st5["sched_notice"] = {"api": {"at": "2026-10-21 09:12", "msg": "旧的", "popped": True}}
        st5.save()
        tab5 = T.ApiTab(st5, rec, lambda m: None)
        check(tab5.lab_sched.text() == "" and not (st5.get("sched_notice") or {}).get("api"), "不是今天的提醒:不再挂着")
        for t in (tab, tab2, tab3, tab4, tab5):
            t.deleteLater()
    finally:
        QMessageBox.warning = real_w


def _modal(app, fn, wait: float = 0.3):
    """等一会儿,对弹出来的模态框调 fn(框)(测试里看框里写了什么 / 改了再点确定)。"""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    QTimer.singleShot(int(wait * 1000), lambda: fn(QApplication.activeModalWidget()))


def test_cd_items(tmp: Path):
    print("[改进清单 C / D(10~23):看得懂、知道下一步、小问题]")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox
    app = QApplication.instance() or QApplication([])
    import gui.schedule as S
    import gui.window as GW
    from gui.widgets import newest_first
    from qe import apiacc, apisrc
    from qe.config import Settings, bj_now
    from qe.records import Records
    today = f"{bj_now().month}.{bj_now().day}"
    root = tmp / "素材cd"
    for emp, names in (("王", ("cd第一条视频", "cd第二条视频")), ("李", ("cd第一条视频",))):
        d = root / "10.21" / "小天地" / emp
        d.mkdir(parents=True)
        for n in names:
            (d / f"{n}.mp4").write_bytes(b"x")
            _img(d / f"{n}.png", 640, 360)
    (root / "10.21" / "小天地" / "31条（已发）").mkdir(parents=True)
    (root / "10.21" / "小天地" / "31条（已发）" / "发过的那条.mp4").write_bytes(b"x")
    (root / "10.21" / "不认识").mkdir(parents=True)
    (root / "9.30" / "小天地" / "张").mkdir(parents=True)
    (root / "9.30" / "小天地" / "张" / "旧的.mp4").write_bytes(b"x")
    if today not in ("10.21", "9.30"):
        (root / today).mkdir()                      # 今天的文件夹还空着:下拉里标「今天」、灰掉
    api_root = tmp / "api_cd" / "游戏视频"
    (api_root / "CSGO--CSGO战神君" / "10.22").mkdir(parents=True)
    (api_root / "CSGO--CSGO战神君" / "10.22" / "重试的那条.mp4").write_bytes(b"x")
    accs0 = apiacc.load()

    def fake_decide(v):
        v.cover, v.cover_kind, v.cover_why, v.plan = v.png, "png", "测试", {}
        v.warn = False
    real = (GW.C.decide, GW.C.note_wide, QMessageBox.information)
    boxes = []
    GW.C.decide, GW.C.note_wide = fake_decide, (lambda v: None)
    QMessageBox.information = staticmethod(lambda _p, t, x, *a, **k: boxes.append(x))
    try:
        apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"),
                      "category": 1604, "enabled": True}])
        st = Settings(tmp / "s_cd.json")
        st["material_root"] = str(root)
        st["api_roots"] = [str(api_root)]
        st["archive_root"] = str(tmp / "教育归档" / "10.15")          # 被人改坏了的(少 {month})
        st["ai_key"] = "test"
        rec = Records(tmp / "r_cd.sqlite")
        w = GW.MainWindow(st, rec)
        # 刚打开:今天的文件夹有东西就选今天(试用 2026-10-21);没有就是空白 → 13:告诉人先选日期
        from qe import folders as F
        has_today = any(F.day_of(d) == today and w._date_has_files(str(root), d) for d in F.list_dates(str(root)))
        check(w.c_date.currentData() == (today if has_today else ""), f"刚打开:今天有素材就选今天 -> {w.c_date.currentData()}")
        w.c_date.setCurrentIndex(0)
        check(w.lab_sum.text() == GW.PICK_DAY and w.lab_scope.text() == GW.PICK_DAY, f"13 没选日期提示先选日期 -> {w.lab_sum.text()}")
        # 15:最新的在上面、今天标出来、没视频的灰掉
        ds = [w.c_date.itemData(i) for i in range(1, w.c_date.count())]
        check(ds == newest_first(ds) and ds.index("10.21") < ds.index("9.30") and w.c_date.itemText(0) == "(选一天)",
              f"15 教育号日期:最新的在上面 -> {ds}")
        check(newest_first(["9.30", "10.14（101）", "10.2", "乱七八糟"]) == ["10.14（101）", "10.2", "9.30", "乱七八糟"], "15 改过名的日期也按开头排")
        if today not in ("10.21", "9.30"):
            i = w.c_date.findData(today)
            fg = w.c_date.itemData(i, Qt.ItemDataRole.ForegroundRole)
            check("今天" in w.c_date.itemText(i) and "没视频" in w.c_date.itemText(i) and fg is not None,
                  f"15 今天标出来、空的灰掉 -> {w.c_date.itemText(i)}")
        i = w.c_date.findData("10.21")
        check(w.c_date.itemText(i) in ("10.21", "10.21(今天)") and w.c_date.itemData(i, Qt.ItemDataRole.ForegroundRole) is None,
              "15 有视频的正常显示")
        # 10:没选日期 / 没勾员工点「摆下一批」
        w.start_batch()
        check(boxes and "左上角" in boxes[-1], f"10 没选日期:提示先选日期 -> {boxes[-1:]}")
        w.c_date.setCurrentIndex(i)
        check(w.lab_sum.text() == GW.PICK_EMP, f"13 选了日期没勾员工:提示勾员工 -> {w.lab_sum.text()}")
        w.start_batch()
        check("你还没勾员工" in boxes[-1] and "发完" not in boxes[-1], f"10 没勾员工:不再说「都发完了」 -> {boxes[-1]}")
        # 11:名字带「已发」的文件夹留灰行;不认识的文件夹也列出来
        top = next(w.tree.topLevelItem(k) for k in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(k).text(0) == "家长小天地")
        kids = [top.child(k) for k in range(top.childCount())]
        grey = [x for x in kids if "已发" in x.text(0)]
        check(len(grey) == 1 and grey[0].text(1) == "1 条,不发" and not grey[0].flags() & Qt.ItemFlag.ItemIsUserCheckable
              and "已发" in grey[0].toolTip(0), f"11 带「已发」的文件夹留一行灰的 -> {[x.text(0) for x in kids]}")
        unk = [w.tree.topLevelItem(k) for k in range(w.tree.topLevelItemCount()) if w.tree.topLevelItem(k).text(0) == "没读的文件夹"]
        check(unk and unk[0].child(0).text(0) == "不认识", "11 认不出号的文件夹也列出来")
        for x in kids:
            if x.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                x.setCheckState(0, Qt.CheckState.Checked)
        grey[0].setCheckState(0, Qt.CheckState.Checked)                 # 灰行就算被勾上也不算
        check(sorted(e for _a, _d, e in w.checked_dirs()) == ["李", "王"], f"11 灰行勾不上 -> {w.checked_dirs()}")
        w._load_videos()
        _wait(app, lambda: not (w.cover_worker and w.cover_worker.isRunning()))
        w._update_scope()
        # 18:这次摆 N 条 / 跳过 N 条(为什么)
        sc = w.lab_scope.text()
        check("这次摆「家长小天地」2 条" in sc and "跳过 1 条" in sc and "同名" in sc, f"18 主按钮上面写这次摆几条、跳过几条 -> {sc}")
        # 17:用词统一
        stt = [w.table.item(r, 4).text() for r in range(w.table.rowCount())]
        check(stt.count("还没发") == 2 and not any(s == "没发" for s in stt), f"17 状态写「还没发」 -> {stt}")
        check(GW.READY == "摆好等发布" and w.t_sum.horizontalHeaderItem(4).text() == "摆好等发布", "17 「摆好没发」统一成「摆好等发布」")
        # 16:「封面都看过了」;摆好等确认时底栏只留要点的
        check(w.b_allok.text() == "封面都看过了", "16 「全部调好了」改名「封面都看过了」")
        check(not w.b_wm.isHidden() and not w.b_blur.isHidden(), "16 平时有「查水印 / 模糊水印」")
        w.batch_id = "测试批"
        w._refresh_buttons()
        check(w.b_wm.isHidden() and w.b_blur.isHidden() and w.b_allok.isHidden() and not w.b_sent.isHidden(),
              "16 摆好等确认时藏起「查水印 / 模糊水印 / 封面都看过了」")
        w.batch_id = ""
        w._refresh_buttons()
        # 12:定时框先写总览,标签「几点发出去」,两页意思写清楚
        ov = w._sched_overview("10.21")
        check("家长小天地 2 条" in ov, f"12 教育号总览:同名的只算一条 -> {ov}")
        seen = {}

        def look(dlg):
            seen["labels"] = [x.text() for x in dlg.findChildren(QLabel)] if dlg else []
            if dlg:
                dlg.reject()
        _modal(app, look)
        r = S.ask_schedule(w, "定时发布 · 教育号", ["10.21", "9.30"], "10.21", head="摆完电脑就能关", overview=w._sched_overview)
        labs = "\n".join(seen.get("labels", []))
        check(r is None and "家长小天地 2 条" in labs and "发出去" in labs and "几点发出去(北京时间):" in labs and "摆完电脑就能关" in labs,
              f"12 定时框最上面是总览、标签「几点发出去」 -> {labs[:200]}")
        api_ov = w.api_tab._sched_overview("10.22")
        check("CSGO战神君 1 条" in api_ov, f"12 16 个号总览 -> {api_ov}")
        # 15:16 个号页也是最新的在上、今天标出来
        tab = w.api_tab
        ti = tab.c_date.findData(today)
        from qe import plan as _P
        tmr = _P.tomorrow_folder()
        tmri = tab.c_date.findData(tmr)
        check(ti > 0 and "今天" in tab.c_date.itemText(ti) and tmri > 0 and "明天" in tab.c_date.itemText(tmri) and tab.c_date.itemData(1) == newest_first(
            [tab.c_date.itemData(k) for k in range(1, tab.c_date.count())])[0], "15 16 个号页:最新的在上、今天和明天都标出来")
        # 14:还没搬账号(nicks 空)时「今天达标」别写「都发够了」
        apiacc.save([])
        check(tab.set_day("10.22") and tab.videos, "16 个号页选到 10.22")
        sub = tab._quota_sub()
        check("差" in sub and "都发够了" not in sub, f"14 0/20 时不写「都发够了」 -> {sub}")
        apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"),
                      "category": 1604, "enabled": True}])
        # 20:数据记录页空表有提示
        w.refresh_records()
        check(not w.rec_empty.isHidden() and "还没有记录" in w.rec_empty.text(), f"20 空表有提示 -> {w.rec_empty.text()}")
        check(w.t_rec.horizontalHeader().sectionResizeMode(7) == GW.QHeaderView.ResizeMode.Stretch, "20 备注那列占剩下的宽度")
        # 23:没发成的直接「重试 / 标成已发」
        tab.reload_dates()
        tab.set_day("10.22")
        v = tab.videos[0]
        rec.api_result(v, "没发成", "网断了")
        w.refresh_records()
        check(w.rec_empty.isHidden(), "20 有记录了提示就藏起来")
        w.t_rec.selectRow(0)
        check(not w.b_rec_retry.isHidden() and not w.b_rec_sent.isHidden() and w.b_rec_unsent.isHidden(),
              "23 选中没发成的:有「重试」「标成已发」")
        w.stack.setCurrentIndex(3)
        w.rec_retry()
        check(w.stack.currentWidget() is tab and tab.day() == "10.22" and tab.selected_rows() == [0],
              f"23 重试 = 跳到 16 个号页、选中这条(不自己发) -> {tab.day()} {tab.selected_rows()}")
        check(rec.status_of(v.path) == "", "23 重试不会自己发")
        w._ask = lambda *a, **k: True
        w.t_rec.selectRow(0)
        w.rec_mark(True)
        check(rec.status_of(v.path) == "已发", "23 标成已发")
        p2 =api_root / "CSGO--CSGO战神君" / "10.22" / "不确定的那条.mp4"
        p2.write_bytes(b"x")
        tab.reload_dates()
        v2 = next(x for x in tab.videos if x.path == str(p2))
        rec.api_begin(v2)
        w.refresh_records()
        row = next(k for k in range(w.t_rec.rowCount()) if w.t_rec.item(k, 3).text() == "不确定的那条")
        w.t_rec.selectRow(row)
        check(w.t_rec.item(row, 4).text() == "不确定发没发" and not w.b_rec_unsent.isHidden() and w.b_rec_retry.isHidden(),
              "23 不确定发没发的:有「标成没发出去」,先不能重试")
        w.rec_mark(False)
        check(rec.status_of(str(p2)) == "", "23 标成没发出去:之后能再发")
        # 21:日期统一写 10.19
        check(w.daily.d.displayFormat() == "M.d", "21 每日汇总的日期写 10.19")
        w.refresh_records()
        pubs = [w.t_rec.item(k, 6).text() for k in range(w.t_rec.rowCount()) if w.t_rec.item(k, 6).text()]
        check(pubs and all(re.match(r"^\d{1,2}\.\d{1,2} \d\d:\d\d", x) for x in pubs), f"21 数据记录的时间写 10.19 10:30 -> {pubs}")
        # 19:设置里「发完挪到」只能改前面那段;改坏了的换回按月份
        got = {}

        def settings(dlg):
            if not dlg:
                return
            got["warn"] = [x.text() for x in dlg.findChildren(QLabel) if "没有 {month}" in x.text()]
            got["tpl"] = [x.text().split("后面自动接上:")[-1] for x in dlg.findChildren(QLabel) if x.text().startswith("后面自动接上:")]
            ed = [x for x in dlg.findChildren(QLineEdit) if x.text() == r"X:\知乎视频\内容查看"]
            got["n"] = len(ed)
            if ed:
                ed[0].setText(str(tmp / "教育归档"))
            dlg.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
        _modal(app, settings)
        w.edit_settings()
        check(got.get("warn") and r"\{month}月发布视频\企鹅号\教育" in got.get("tpl", []) and got.get("n") == 2,
              f"19 模板那半截灰字不能改;改坏了的红字说换回来了 -> {got}")
        check(st["archive_root"] == os.path.join(str(tmp / "教育归档"), r"{month}月发布视频\企鹅号\教育"),
              f"19 存的是 前半截 + 模板 -> {st['archive_root']}")
        check(st["api_archive"] == r"X:\知乎视频\内容查看\{month}月发布视频\企鹅号\企鹅号软件发布", f"19 没动的不变 -> {st['api_archive']}")
        w.close()
        w.deleteLater()
    finally:
        GW.C.decide, GW.C.note_wide, QMessageBox.information = real
        apiacc.save(accs0)
    # 22:relink 只在原来的文件已经不在了才改(同号同名的另一份不算成已发)
    from qe import folders as F
    a = tmp / "relink" / "甲" / "同名.mp4"
    b = tmp / "relink" / "乙" / "同名.mp4"
    for p in (a, b):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    r2 = Records(tmp / "r_relink.sqlite")
    v = F.Video(path=str(a), title="同名", account="家长小天地", employee="甲", date="10.21")
    r2.manual_published(v)
    rid = r2.rows()[0]["id"]
    check(not r2.relink(rid, str(b)) and r2.status_of(str(b)) == "", "22 原来那份还在:另一份同名的不算已发")
    a.unlink()
    check(r2.relink(rid, str(b)) and r2.status_of(str(b)) == "已发", "22 原来那份没了(被挪了 / 改了名):认新位置")


def _no_dialogs():
    """测试里不弹框:中文确认框(gui.api_tab.ask)一律点「是」,提示框一律关掉(不然 offscreen 下会一直等人点)。"""
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    import gui.api_tab as T
    T._real_ask = T.ask                            # test_misfire 要测真的确认框
    T.ask = lambda *a, **k: True
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)


def test_find_redo(tmp: Path):
    print("[找视频重发(用户 2026-10-25):输入标题找发过的 → 视频连封面挪回今天 / 明天的文件夹(结构照原样)、记录改没发成;16 个号能在企鹅号上删]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, redo
    from qe import folders as F
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    from gui.find_dialog import FindDialog
    base = tmp / "fr"
    root = base / "小学生教育类"
    day = root / "10.24" / "家长研习社"
    day.mkdir(parents=True)
    t = "幼小衔接必备 第3集"
    (day / f"{t}.mp4").write_bytes(b"x")
    (day / f"{t}.jpg").write_bytes(b"j")
    (day / t).mkdir()
    (day / t / "图片修改需求 (1).png").write_bytes(b"p")
    (day / "别的.mp4").write_bytes(b"x")
    st = Settings(tmp / "st_fr.json")
    st["material_root"] = str(root)
    st["archive_root"] = str(base / "内容查看" / r"{month}月发布视频\企鹅号\教育")
    rec = Records(tmp / "r_fr.sqlite")
    v = F.Video(path=str(day / f"{t}.mp4"), title=t, account="家长研习社", employee="小王", date="10.24")
    rec.manual_published(v)
    rec.manual_published(F.Video(path=str(day / "别的.mp4"), title="别的", account="家长研习社", employee="小王", date="10.24"))
    F.move_date(st, "10.24")                                  # 这天发完整天挪去归档
    arc = Path(F.archive_target(st, "10.24")) / "家长研习社"
    check((arc / f"{t}.mp4").is_file() and not (root / "10.24").exists(), "准备:教育号这天整个挪去了归档")
    rows = redo.search(rec, "衔接必备")
    check(len(rows) == 1 and rows[0]["title"] == t and redo.search(rec, "  ") == [], "标题里的几个字就找得到;空的不找")
    check(redo.locate(st, rows[0]) == str(arc / f"{t}.mp4"), f"教育号:从归档里认出视频现在在哪 -> {redo.locate(st, rows[0])}")
    check(sorted(os.path.basename(p) for p, _k, _r in redo.extras(str(arc / f"{t}.mp4"))) == sorted([f"{t}.jpg", t]),
          "跟着一起挪的:同名的图 + 封面文件夹,别的视频不带")
    (root / "10.25(星期六)").mkdir()
    check(redo.target_dir(st, rows[0], "10.25") == str(root / "10.25(星期六)" / "家长研习社"),
          "挪回去:那天的文件夹已经有了(带星期的也认)就放进去,下面照原样建「家长研习社」")
    check(redo.target_dir(st, rows[0], "10.26") == str(root / "10.26" / "家长研习社"), "没有那天的文件夹:建「10.26」")

    real_ask = T.ask
    asked = []
    T.ask = lambda *a, **k: asked.append(a) or True
    try:
        dlg = FindDialog(rec, st, after=lambda: asked.append("after"))
        dlg.e.setText("衔接")
        dlg.find()
        check(dlg.lst.count() == 1 and dlg.b_back.isEnabled() and dlg.b_copy.isEnabled() and dlg.b_del.isHidden(),
              "窗口里找得到;教育号能挪回去、能复制标题,「在企鹅号上删掉」不显示(罐头发的删不了)")
        dlg.copy()
        check(QApplication.clipboard().text() == t, "复制标题(去后台搜)")
        dlg.c_day.setCurrentIndex(1)
        md = dlg.c_day.currentData()
        dlg.pull_back()
        dst = Path(redo.target_dir(st, rows[0], md))
        check((dst / f"{t}.mp4").is_file() and (dst / f"{t}.jpg").is_file() and (dst / t / "图片修改需求 (1).png").is_file(),
              f"点「挪回去重发」:视频、封面图、封面文件夹都挪到明天的文件夹 -> {dst}")
        check(not (arc / f"{t}.mp4").exists() and (arc / "别的.mp4").is_file(), "归档里只拿走这一条,别的不动")
        check(rec.status_of(str(day / f"{t}.mp4")) == "" and rec.status_of(str(dst / f"{t}.mp4")) == "" and "after" in asked,
              "记录改成没发,新位置能再发;刷新了页面")
        check(dlg.lst.count() == 1 and "没发" in dlg.lst.item(0).text(), "窗口里那条显示「没发成」")
    finally:
        T.ask = real_ask

    # 16 个号:挪走的位置记录里有;在企鹅号上删
    aroot = base / "游戏视频"
    acc = aroot / "CSGO--CSGO战神君"
    (acc / "10.24").mkdir(parents=True)
    (acc / "10.26").mkdir()
    aarc = base / "接口归档"
    aarc.mkdir()
    st["api_roots"] = [str(aroot)]
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    w = F.Video(path=str(acc / "10.24" / "横屏的Ace.mp4"), title="横屏的Ace", account="CSGO战神君", employee="", date="10.24")
    rid = rec.api_begin(w)
    rec.api_finish(rid, "已发", "article_id=A77 vid=V77")
    (aarc / "横屏的Ace.mp4").write_bytes(b"x")
    (aarc / "横屏的Ace.jpg").write_bytes(b"j")
    rec.mark_moved(rid, str(aarc / "横屏的Ace.mp4"))
    r = redo.search(rec, "Ace")[0]
    check(redo.is_api(r) and os.path.normcase(redo.locate(st, r)) == os.path.normcase(str(aarc / "横屏的Ace.mp4")),
          "16 个号:按记下的挪去位置找到")
    check(redo.target_dir(st, r, "10.26") == str(acc / "10.26"), "挪回:号的文件夹下面那天的日期文件夹")
    deleted = []

    class C:
        def __init__(self, cid, sec, **k):
            self.sec = sec

        def delete_article(self, aid):
            deleted.append((aid, self.sec))
            return {}
    real = omapi.Client
    omapi.Client = C
    T.ask = lambda *a, **k: True
    try:
        dlg = FindDialog(rec, st)
        dlg.e.setText("Ace")
        dlg.find()
        check(not dlg.b_del.isHidden() and dlg.b_del.isEnabled(), "16 个号已发的:「在企鹅号上删掉」能点")
        dlg.delete()
        check(deleted == [("A77", "s")], f"在企鹅号上删掉:用记下的文章编号、这个号的密钥 -> {deleted}")
        check("在企鹅号上删掉了" in rec.conn.execute("SELECT note FROM posts WHERE id=?", (rid,)).fetchone()[0], "记录里写上删掉了")
        new, why = redo.pull_back(st, rec, r, "10.26")
        check(why == "" and (acc / "10.26" / "横屏的Ace.mp4").is_file() and (acc / "10.26" / "横屏的Ace.jpg").is_file()
              and rec.status_of(new) == "", f"16 个号挪回 10.26:视频连封面回去,能再发 -> {why}")
        check(redo.delete_on_platform(dict(r, note="")).startswith("软件没记下"), "没记文章编号的:删不了,说清楚去后台删")
    finally:
        omapi.Client = real
        T.ask = real_ask
    _ = app


def test_edu_verify(tmp: Path):
    print("[教育号也能核对(用户 2026-10-26):钥匙单独存、只查不发;按标题对;打回的打勾、对不上的不打勾;拎回来挪回今天的文件夹]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, verify
    from qe import folders as F
    from qe.config import Settings, bj_now
    from qe.records import Records
    from gui.verify_dialog import VerifyDialog
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    apiacc.set_qkey("家长研习空间", "ce", "se")
    check("家长研习空间" not in apiacc.nicks() and all(a["nick"] != "家长研习空间" for a in apiacc.load()),
          "教育号的钥匙不进 16 个号的名单:发布那边看不到,不可能被接口发")
    ca = {a["nick"]: a for a in apiacc.check_accounts()}
    check(ca["家长研习空间"].get("query_only") and not ca["CSGO战神君"].get("query_only") and apiacc.unseal(ca["家长研习空间"]["secret"]) == "se",
          "核对的名单:16 个号 + 教育号(标着只查不发,钥匙加密存)")
    n = bj_now()
    day, md = n.strftime("%Y-%m-%d"), f"{n.month}.{n.day}"
    root = tmp / "eduv" / "小学生教育类"
    d = root / md / "家长研习空间"
    d.mkdir(parents=True)
    st = Settings(tmp / "st_eduv.json")
    st["material_root"] = str(root)
    st["archive_root"] = str(tmp / "eduv" / "归档" / "{month}月")
    rec = Records(tmp / "r_eduv.sqlite")
    titles = {"A": "孩子写作业磨蹭怎么办 #家庭教育", "B": "幼小衔接必备:上学前一定要会的十件事,家长赶紧收藏", "C": "被打回的那条", "D": "标题对不上的那条"}
    for k, t in titles.items():
        (d / f"{t}.mp4").write_bytes(b"x")
        rec.manual_published(F.Video(path=str(d / f"{t}.mp4"), title=t, account="家长研习空间", employee="小王", date=md))
    t0 = f"{day} 10:00:00"
    arts = [{"article_title": "孩子写作业磨蹭怎么办#家庭教育", "article_pub_time": t0, "article_pub_flag": "发布成功"},
            {"article_title": "幼小衔接必备:上学前一定要会的十件事", "article_pub_time": t0, "article_pub_flag": "发布成功"},  # 平台截短了
            {"article_title": "被打回的那条", "article_pub_time": t0, "article_pub_flag": "审核不通过"},
            {"article_title": "人在后台手动发的", "article_pub_time": t0, "article_pub_flag": "发布成功"}]

    class C:
        def __init__(self, cid, sec, **k):
            self.cid = cid

        def list_articles(self, page=1, limit=10):
            return {"articles": arts if page == 1 and self.cid == "ce" else [], "total": len(arts)}

        def article_info(self, aid):
            return {}
    r = verify.check_edu(C("ce", "se"), rec, "家长研习空间", day)
    why = {m["title"]: (m["why"], m["sure"]) for m in r["missing"]}
    check(r["ours"] == 4 and r["live"] == 3 and len(r["extra"]) == 1 and set(why) == {titles["C"], titles["D"]},
          f"按标题对:去空格标点一样的、被平台截短的都算对上;后台多出来的列为软件没记的 -> {r['ours']} {r['live']} {why}")
    check("被审核打回" in why[titles["C"]][0] and why[titles["C"]][1] is False and why[titles["D"]][1] is False
          and "改了标题" in why[titles["D"]][0],
          "被打回的:列出来不打勾(再发多半还会被打回);标题找不到、这天后台又有多出来的:不打勾,提示可能改了标题")
    extra_one = arts.pop()                                     # 这天后台没有多出来的 → 找不到的就是没发上,打勾
    r2 = verify.check_edu(C("ce", "se"), rec, "家长研习空间", day)
    why2 = {m["title"]: (m["why"], m["sure"]) for m in r2["missing"]}
    check(why2[titles["D"]][1] is True and "没发上" in why2[titles["D"]][0], f"标题找不到、这天也没多出来的:打勾 -> {why2}")
    arts.append(extra_one)
    from datetime import timedelta
    from qe.config import bj_str
    yday = (n - timedelta(days=1)).strftime("%Y-%m-%d")
    rec.conn.execute("UPDATE posts SET published_at=? WHERE title=?", (f"{yday} 18:00:00", titles["D"]))   # D 改成昨天发的、昨天没发上
    rec.conn.commit()
    rec.manual_published(F.Video(path=str(d / "补发的D.mp4"), title=titles["D"], account="家长研习空间", employee="小王", date=md))  # 今天补发过了
    r3 = verify.check_edu(C("ce", "se"), rec, "家长研习空间", yday)
    m3 = {m["title"]: m for m in r3["missing"]}
    check(titles["D"] in m3 and m3[titles["D"]]["sure"] is False and "已经补发过了" in m3[titles["D"]]["why"],
          f"那天没发上、但后来已经用同样标题补发过的:不打勾,说清楚(不然拎回来会重复发) -> {m3.get(titles['D'], {}).get('why')}")
    rec.conn.execute("DELETE FROM posts WHERE path=?", (str(d / "补发的D.mp4"),))
    rec.conn.execute("UPDATE posts SET published_at=? WHERE title=?", (bj_str(), titles["D"]))
    rec.conn.commit()
    real = omapi.Client
    omapi.Client = C
    try:
        dlg = VerifyDialog(rec, day, st=st)
        _wait(app, lambda: dlg.w is None or dlg.w.isFinished())
        app.processEvents()
        check("家长研习空间" in dlg.results and dlg.results["家长研习空间"].get("edu") and "CSGO战神君" in dlg.results,
              "「去企鹅号核对」16 个号和教育号一起查")
        check(dlg.miss.count() == 2, f"假发成功列了 2 条 -> {dlg.miss.count()}")
        from PySide6.QtCore import Qt
        its = [dlg.miss.item(k) for k in range(dlg.miss.count())]
        check(all(it.checkState() == Qt.CheckState.Unchecked for it in its), "打回的、标题对不上的:默认都不打勾")
        for it in its:
            if "被打回的那条" in it.text():
                it.setCheckState(Qt.CheckState.Checked)       # 人确定要重发:自己勾上
        dlg.pull_back()
        check(rec.status_of(str(d / f"{titles['C']}.mp4")) == "" and (d / f"{titles['C']}.mp4").is_file()
              and not list(d.glob("*(2).mp4")),
              "拎回来:被打回的改成没发,视频就在今天的文件夹里的不挪(不会变成「(2)」)")
        check(rec.status_of(str(d / f"{titles['D']}.mp4")) == "已发", "没打勾的(标题对不上)不动")
        rows = verify.table_rows(st, rec, day, dlg.results)
        check(any(nick == "家长研习空间" and a == 3 for _c, nick, _q, a, _t in rows), "导出表格:教育号用企鹅号上的实发")
        dlg.close()
    finally:
        omapi.Client = real


def test_redo_room(tmp: Path):
    print("[补发不占规定条数(用户 2026-10-26):拎回来重发的是以前哪天发的 → 那天给这个号多加 1 条;当天发的不加;没规定条数的不管]")
    from datetime import timedelta
    from qe import plan
    from qe.config import Settings, bj_now
    st = Settings(tmp / "st_room.json")
    st["daily_plan"] = [{"cat": "教育", "label": "教育总发布量", "accounts": {"家长研习空间": 102}}]
    st["quota_open"] = False
    n = bj_now()
    today, yday = n.strftime("%Y-%m-%d"), (n - timedelta(days=1)).strftime("%Y-%m-%d")
    row = {"account": "家长研习空间", "published_at": f"{yday} 18:00:00"}
    check(plan.room_for_redo(st, row) == 1 and plan.quota_on(st, "家长研习空间", today) == 103,
          "昨天发的被打回、今天补发:今天这个号多加 1 条(今天找好的 102 条照样全发)")
    check(plan.room_for_redo(st, dict(row, published_at=f"{today} 09:00:00")) == 0 and plan.quota_on(st, "家长研习空间", today) == 103,
          "今天发的今天拎回来:不加(改回没发以后今天自然空出一条)")
    check(plan.room_for_redo(st, dict(row, account="没规定条数的号")) == 0, "没规定条数的号不管")
    tmr = n + timedelta(days=1)
    check(plan.md_to_day(f"{tmr.month}.{tmr.day}") == tmr.strftime("%Y-%m-%d") and plan.md_to_day("乱写") == "",
          "「10.27」认成那天的日期")
    check(plan.room_for_redo(st, row, tmr.strftime("%Y-%m-%d")) == 1 and plan.quota_on(st, "家长研习空间", tmr.strftime("%Y-%m-%d")) == 103,
          "挪回明天重发:加在明天")
    check(plan.room_for_redo(st, dict(row, status="没发成")) == 0 and plan.quota_on(st, "家长研习空间", today) == 103,
          "已经拎回来过(没发成)再挪一次:不再加(上次加过了)")
    from qe.records import Records
    s = plan.summary(Records(tmp / "r_room.sqlite"), st, today)
    tsv = plan.as_tsv(s)
    check("教育总发布量\t102\t0" in tsv and "总发布量\t102\t0" in tsv.splitlines()[-1] and s["rows"][0][1] == 103 and s["extra"] == {"家长研习空间": 1},
          f"复制到企业微信的「规定」写原本的 102(补发加的那 1 条不算;用户 2026-10-26「规定的 80」),还差几条照样按 103 算 -> {tsv!r}")
    # 16 个号拎回来:那天给这个号手选过文件夹的,就放进手选的那个(用户 2026-10-26:挪回老日期文件夹,今天的页面看不到)
    from qe import redo
    md = f"{n.month}.{n.day}"
    st["api_picked"] = {md: {"日漫漫谈社": str(tmp / "rm" / "日漫漫谈社" / "10.25（周日）")}}
    arow = {"account": "日漫漫谈社", "employee": "接口", "path": str(tmp / "rm" / "日漫漫谈社" / "10.21" / "痛.mp4")}
    check(redo.target_dir(st, arow, md) == str(tmp / "rm" / "日漫漫谈社" / "10.25（周日）"), "手选过文件夹的号:挪进今天手选的那个文件夹")
    (tmp / "rm" / "日漫漫谈社" / "10.21").mkdir(parents=True)
    check(redo.target_dir(st, dict(arow, account="日漫解说馆"), md) == str(tmp / "rm" / "日漫漫谈社" / md),
          "没手选的:号的文件夹下今天的日期文件夹")


def test_verify_range(tmp: Path):
    print("[批量查询(用户 2026-10-26):从哪天查到哪天,一个号只翻一遍;导出成企业微信那张表(每天一列)+ 没发上的视频]")
    from datetime import timedelta
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, verify
    from qe import folders as F
    from qe.config import Settings, bj_now
    from qe.records import Records
    from gui.verify_dialog import VerifyDialog
    import openpyxl
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    apiacc.set_qkey("家长研习空间", "ce", "se")
    n = bj_now()
    days = [(n - timedelta(days=k)).strftime("%Y-%m-%d") for k in (2, 1, 0)]
    st = Settings(tmp / "st_vr.json")
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 2}},
                        {"cat": "教育", "label": "教育总发布量", "accounts": {"家长研习空间": 1}}]
    rec = Records(tmp / "r_vr.sqlite")
    arts = {"c": [], "ce": []}
    for k, d in enumerate(days):
        for j in range(2):                                        # CSGO 每天记了 2 条;第一天的第 2 条企鹅号上没有
            v = F.Video(path=str(tmp / "vr" / f"{d}-{j}.mp4"), title=f"c{k}{j}", account="CSGO战神君", employee="", date=d[5:])
            rid = rec.api_begin(v)
            rec.api_finish(rid, "已发", f"article_id=A{k}{j} vid=V{k}{j}")
            rec.conn.execute("UPDATE posts SET published_at=? WHERE id=?", (f"{d} 10:0{j}:00", rid))
            if not (k == 0 and j == 1):
                arts["c"].append({"article_id": f"A{k}{j}", "article_title": f"c{k}{j}", "article_pub_time": f"{d} 10:0{j}:00",
                                  "article_pub_flag": "发布成功", "article_video_info": {"vid": f"V{k}{j}"}})
        rec.manual_published(F.Video(path=str(tmp / "vr" / f"e{d}.mp4"), title=f"教育{k}", account="家长研习空间", employee="小王", date=d[5:]))
        rec.conn.execute("UPDATE posts SET published_at=? WHERE title=?", (f"{d} 18:00:00", f"教育{k}"))
        arts["ce"].append({"article_title": f"教育{k}", "article_pub_time": f"{d} 18:00:00", "article_pub_flag": "发布成功"})
    rec.conn.commit()
    arts["c"].append({"article_id": "OLD", "article_title": "老的", "article_pub_time": "2020-01-01 00:00:00", "article_pub_flag": "发布成功"})
    pages = []

    class C:
        def __init__(self, cid, sec, **k):
            self.cid = cid

        def list_articles(self, page=1, limit=10):
            pages.append((self.cid, page))
            a = sorted(arts[self.cid], key=lambda x: x["article_pub_time"], reverse=True)
            return {"articles": a[(page - 1) * limit: page * limit], "total": len(a)}

        def article_info(self, aid):
            return {"article_info": {"article_pub_flag": "未发布", "article_del_flag": "未删除"}}
    # 用户 2026-10-26 当天核对:定时还没到点的,企鹅号状态是代号「10」—— 不能当成没发上(原来默认打勾,差点拎回来重发)
    v = F.Video(path=str(tmp / "vr" / "定时的.mp4"), title="定时的", account="CSGO战神君", employee="", date=days[-1][5:])
    rid = rec.api_begin(v)
    rec.api_finish(rid, "已发", "article_id=T1 vid=VT1")
    rec.conn.execute("UPDATE posts SET published_at=? WHERE id=?", (f"{days[-1]} 23:00:00", rid))
    rec.conn.commit()
    arts["c"].append({"article_id": "T1", "article_title": "定时的", "article_pub_time": f"{days[-1]} 23:00:00",
                      "article_pub_flag": "10", "article_video_info": {"vid": "VT1"}})
    one = verify.check_account(C("c", "s"), rec, "CSGO战神君", days[-1])
    check(not one["missing"] and one["live"] == 3 and one["review"] == 1,
          f"定时没到点(状态「10」):算在企鹅号上、等着发,不算没发上 -> missing={[m['why'] for m in one['missing']]} live={one['live']}")
    arts["c"].pop()
    rec.conn.execute("DELETE FROM posts WHERE id=?", (rid,))
    rec.conn.commit()
    pages.clear()
    per = verify.check_range(C("c", "s"), rec, "CSGO战神君", days)
    check([per[d]["live"] for d in days] == [1, 2, 2] and len(per[days[0]]["missing"]) == 1 and pages == [("c", 1)],
          f"一个号一段日子:后台只翻一遍,一天一天对出来 -> {[per[d]['live'] for d in days]} 翻了 {pages}")
    real = omapi.Client
    omapi.Client = C
    try:
        dlg = VerifyDialog(rec, days[-1], st=st)
        _wait(app, lambda: dlg.w is None or dlg.w.isFinished())
        dlg.start(days[0], days[-1])
        _wait(app, lambda: dlg.w is None or dlg.w.isFinished())
        app.processEvents()
        r = dlg.results.get("CSGO战神君") or {}
        check(r.get("live") == 5 and set(dlg.by_day) == {"CSGO战神君", "家长研习空间"} and dlg.miss.count() == 1
              and "·" in dlg.miss.item(0).text() and f"{int(days[0][5:7])}.{int(days[0][8:10])}" in dlg.miss.item(0).text(),
              f"窗口里查一段:合起来一行一个号,没发上的写清楚哪天 -> {r.get('live')} {dlg.miss.count()}")
        p = tmp / "vr.xlsx"
        verify.export_range_xlsx(str(p), st, rec, dlg.days, dlg.by_day)
        wb = openpyxl.load_workbook(p)
        ws, w2 = wb.worksheets[0], wb.worksheets[1]
        row = next(rr for rr in range(2, ws.max_row + 1) if ws.cell(rr, 2).value == "CSGO战神君")
        check([ws.cell(row, 4 + k).value for k in range(3)] == [1, 2, 2] and ws.cell(row, 4).fill.fgColor.rgb.endswith("FFC7CE")
              and ws.cell(1, 4).value == f"{int(days[0][5:7])}月{int(days[0][8:10])}日",
              "导出第一页:每个号一行、每天一列(企鹅号上核实的),比规定少的标红")
        check(w2.cell(2, 2).value == "CSGO战神君" and w2.cell(2, 3).value == "c01" and w2.cell(2, 5).value == "要补",
              "导出第二页:没发上的视频(哪天、哪个号、标题、原因、要不要补)")
        dlg.close()
    finally:
        omapi.Client = real


def test_mark_sent_keep(tmp: Path):
    print("[标成已发保留原来的发布时间;教育号同一天同标题记了两条算一条(用户 2026-10-26:核对说发上的视频没发上)]")
    from qe import folders as F
    from qe import verify
    from qe.records import Records
    rec = Records(tmp / "r_msk.sqlite")
    v = F.Video(path=str(tmp / "msk" / "a.mp4"), title="耗尽自身五行之力", account="国漫趣谈", employee="", date="10.24")
    rid = rec.api_begin(v)
    rec.api_finish(rid, "已发", "article_id=X1 vid=Y1")
    rec.conn.execute("UPDATE posts SET published_at='2026-10-24 15:32:49' WHERE id=?", (rid,))
    rec.conn.commit()
    rec.mark_unsent(rid, "(拎回来)")
    rec.mark_sent(rid)
    got = rec.conn.execute("SELECT status, published_at FROM posts WHERE id=?", (rid,)).fetchone()
    check(tuple(got) == ("已发", "2026-10-24 15:32:49"), f"拎回来以后又标成已发:还是原来那天发的(不变成今天)-> {tuple(got)}")
    w = F.Video(path=str(tmp / "msk" / "b.mp4"), title="没发过的", account="国漫趣谈", employee="", date="10.24")
    rec.failed(w, "b1", "没摆成")
    rid2 = rec.conn.execute("SELECT id FROM posts WHERE title='没发过的'").fetchone()[0]
    rec.mark_sent(rid2)
    check(rec.conn.execute("SELECT published_at FROM posts WHERE id=?", (rid2,)).fetchone()[0], "原来没有发布时间的:记成现在(补记)")
    day = "2026-10-26"
    for k, folder in enumerate(("10.24", "10.26")):              # 同一条视频记了两条(两个文件夹)
        x = F.Video(path=str(tmp / "msk" / folder / "幼小衔接.mp4"), title="幼小衔接必备 AI 工具汇总", account="家长研习空间",
                    employee="小王", date=folder)
        rec.manual_published(x)
    rec.conn.execute("UPDATE posts SET published_at=? WHERE account='家长研习空间'", (f"{day} 14:31:16",))
    rec.conn.commit()

    class C:
        def list_articles(self, page=1, limit=10):
            a = [{"article_title": "幼小衔接必备 AI 工具汇总", "article_pub_time": f"{day} 10:37:16", "article_pub_flag": "发布成功"}]
            return {"articles": a if page == 1 else [], "total": 1}
    r = verify.check_edu(C(), rec, "家长研习空间", day)
    check(r["ours"] == 1 and not r["missing"], f"教育号同一天同标题记了两条:算一条,不报没发上 -> ours={r['ours']} {[m['why'] for m in r['missing']]}")


def test_key_guards(tmp: Path):
    print("[钥匙串号的硬拦(审查 2026-10-26):扫错号不换、教育号进不了发布名单、搬账号不改回旧钥匙、选择框按位置取]")
    import sqlite3
    from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omlogin
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    apiacc.save([{"nick": "PUBG突围君", "client_id": "CID_PUBG", "secret": apiacc.seal("SP"), "category": 1604, "enabled": True},
                 {"nick": "家长研习空间", "client_id": "CID_X", "secret": apiacc.seal("SX"), "category": 1, "enabled": True}])
    apiacc.set_qkey("家长研习空间", "CID_EDU", "SE")
    check([a["nick"] for a in apiacc.load()] == ["PUBG突围君"] and "家长研习空间" not in apiacc.nicks(),
          "只查不发的号就算混进了接口账号.json,发布那边也看不到")
    for f, why in ((lambda: apiacc.set_key("PUBG突围君", "CID_EDU", "SE"), "教育号的钥匙换给 16 个号"),
                   (lambda: apiacc.set_qkey("家长小天地", "CID_PUBG", "SP"), "16 个号的钥匙存给教育号")):
        try:
            f()
            ok = False
        except ValueError:
            ok = True
        check(ok, f"{why}:拒绝")
    keys = [{"name": "国漫解说馆", "client_id": "A"}, {"name": "国漫解说馆z", "client_id": "B"}]
    check(omlogin.match(keys, "国漫解说馆z")["client_id"] == "B" and omlogin.name_ok({"name": "家长研习空间"}, "PUBG突围君") is False
          and omlogin.name_ok({"name": ""}, "PUBG突围君"), "名字完全一样的先认;名字对不上的算扫错号")
    # 搬账号:教育号不搬;已经有钥匙的号不改回旧库里的老钥匙
    db = tmp / "kg_old.db"
    con = sqlite3.connect(db)
    con.execute("create table accounts(nick, source_name, source_id, client_id, client_secret, category, enabled, sort_order, id)")
    con.executemany("insert into accounts values(?,?,?,?,?,?,?,?,?)",
                    [("PUBG突围君", "PUBG", "1", "OLD", "OLDSEC", 1604, 0, 1, 1), ("家长小天地", "家", "2", "C2", "S2", 1, 1, 2, 2),
                     ("CSGO战神君", "CSGO", "3", "C3", "S3", 1604, 1, 3, 3)])
    con.commit()
    con.close()
    apiacc.migrate(str(db), skip={"家长小天地"})
    p = apiacc.find("PUBG突围君")
    check(p["client_id"] == "CID_PUBG" and p["enabled"] is True and apiacc.find("CSGO战神君")["client_id"] == "C3"
          and apiacc.find("家长小天地") is None, "搬账号:已有的号钥匙 / 开关不动,新号照搬,教育号不搬")
    # 登录取钥匙:选 PUBG、扫的是教育号 → 不换;选教育号、扫的是 PUBG → 不存
    st = Settings(tmp / "st_kg.json")
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏", "accounts": {"PUBG突围君": 20}},
                        {"cat": "教育", "label": "教育", "accounts": {"家长研习空间": 102, "家长小天地": 54}}]
    st["api_roots"] = [str(tmp / "kg_空素材")]           # 不设就读这台电脑真的素材盘:那天有视频,页面在检查(busy),取钥匙不开(11-03 这样挂的)
    tab = T.ApiTab(st, Records(tmp / "r_kg.sqlite"), lambda m: None)
    scanned = {}

    class P:
        def terminate(self):
            pass
    real = (omlogin.launch, omlogin.wait_keys, QInputDialog.getItem, QMessageBox.warning, QMessageBox.information, T.ask)
    warned = []
    omlogin.launch = lambda nick: (P(), 1)
    omlogin.wait_keys = lambda port, stopped=None: ("读到了", [scanned["k"]], "")
    QMessageBox.warning = staticmethod(lambda *a, **k: warned.append(a[2]))
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    T.ask = lambda *a, **k: True
    try:
        scanned["k"] = {"name": "家长研习空间", "client_id": "CID_EDU2", "secret": "SE2", "media_id": "9"}
        QInputDialog.getItem = staticmethod(lambda *a, **k: ("PUBG突围君", True))
        tab.relogin_key()
        check(apiacc.find("PUBG突围君")["client_id"] == "CID_PUBG" and warned and "不是「PUBG突围君」" in warned[-1],
              f"选 PUBG、手机扫的是教育号:不换,说清楚 -> {warned[-1:] }")
        scanned["k"] = {"name": "", "client_id": "CID_EDU", "secret": "SE", "media_id": ""}
        tab.relogin_key()
        check(apiacc.find("PUBG突围君")["client_id"] == "CID_PUBG" and "教育号" in warned[-1], "回话里没名字、但钥匙是教育号的:也不换")
        scanned["k"] = {"name": "PUBG突围君", "client_id": "CID_PUBG", "secret": "SP", "media_id": "1"}
        QInputDialog.getItem = staticmethod(lambda *a, **k: ("家长小天地" + T.EDU_TAG, True))
        tab.relogin_key()
        check(apiacc.qfind("家长小天地") is None and "不是「家长小天地」" in warned[-1], "选教育号、扫成 PUBG:不存")
        scanned["k"] = {"name": "家长小天地", "client_id": "CID_XTD", "secret": "SX2", "media_id": "8"}
        tab.relogin_key()
        check(apiacc.qfind("家长小天地") and apiacc.qfind("家长小天地")["client_id"] == "CID_XTD", "扫对了:照常存")
        # 一个账号下两个没名字的号:选第二个就是第二个
        two = [{"name": "", "client_id": "CID_A1", "secret": "a", "media_id": ""}, {"name": "", "client_id": "CID_B2", "secret": "b", "media_id": ""}]
        omlogin.wait_keys = lambda port, stopped=None: ("读到了", two, "")
        answers = iter(["PUBG突围君", None])

        def pick(parent, title, text, items, *a, **k):
            v = next(answers)
            return (v, True) if v else (items[1], True)
        QInputDialog.getItem = staticmethod(pick)
        tab.relogin_key()
        check(apiacc.find("PUBG突围君")["client_id"] == "CID_B2", f"几个没名字的号:选第二个换上的就是第二个 -> {apiacc.find('PUBG突围君')['client_id']}")
    finally:
        omlogin.launch, omlogin.wait_keys, QInputDialog.getItem, QMessageBox.warning, QMessageBox.information, T.ask = real
    _ = app


def test_audit_redo(tmp: Path):
    print("[审查 2026-10-26 拎回来重发:不丢文件 / 不加(2) / 用原名 / 不进脏话文件夹 / 不确定的不挪 / 记录跟着走 / 封面跟着走 / 额度能退]")
    from qe import folders as F
    from qe import plan, redo
    from qe.config import Settings, bj_now
    from qe.records import Records
    n = bj_now()
    md, today = f"{n.month}.{n.day}", n.strftime("%Y-%m-%d")
    rec = Records(tmp / "r_ar.sqlite")
    st = Settings(tmp / "st_ar.json")
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏", "accounts": {"CSGO战神君": 20}},
                        {"cat": "教育", "label": "教育", "accounts": {"家长研习空间": 102}}]
    root = tmp / "ar" / "游戏视频"
    acc = root / "CSGO--CSGO战神君"
    (acc / "10.20").mkdir(parents=True)
    (acc / f"{md} 脏话").mkdir()
    (acc / f"{md}（星期一）").mkdir()
    st["api_roots"] = [str(root)]
    arc = tmp / "ar" / "归档"
    arc.mkdir(parents=True)

    def api_row(title, arc_name):
        v = F.Video(path=str(acc / "10.20" / f"{title}.mp4"), title=title, account="CSGO战神君", employee="", date="10.20")
        rid = rec.api_begin(v)
        rec.api_finish(rid, "已发", f"article_id=A{rid} vid=V{rid}")
        rec.conn.execute("UPDATE posts SET published_at='2026-10-20 10:00:00' WHERE id=?", (rid,))
        rec.conn.commit()
        (arc / f"{arc_name}.mp4").write_bytes(b"x")
        (arc / f"{arc_name}.jpg").write_bytes(b"j")
        rec.mark_moved(rid, str(arc / f"{arc_name}.mp4"))
        return dict(rec.conn.execute("SELECT * FROM posts WHERE id=?", (rid,)).fetchone())
    r1 = api_row("好标题", "好标题 (2)")
    check(redo.target_dir(st, r1, md) == str(acc / f"{md}（星期一）"), "认今天的文件夹和发布页一样:「脏话」那个不算")
    out = {}
    new, why = redo.pull_back(st, rec, r1, md, out)
    check(why == "" and os.path.basename(new) == "好标题.mp4" and (acc / f"{md}（星期一）" / "好标题.jpg").is_file()
          and not list((acc / f"{md}（星期一）").glob("*(2)*")), f"归档里叫「好标题 (2)」的:挪回来用原名,封面跟着改名 -> {new} {why}")
    got = rec.conn.execute("SELECT status, path, moved_pkey FROM posts WHERE id=?", (r1["id"],)).fetchone()
    check(got[0] == "没发成" and os.path.normcase(got[1]) == os.path.normcase(new) and got[2] is None and out.get("room") == 1,
          "记录改成没发成、位置改成新的;补发以前的给今天加 1 条")
    from qe.records import pkey
    check(rec.status_of(new) == "" and rec.conn.execute("SELECT count(*) FROM posts WHERE pkey=? AND status='没发成'", (pkey(new),)).fetchone()[0] == 1
          and plan.quota_on(st, "CSGO战神君", today) == 21, "新位置认得出这条、能再发(之后重发成了就不再挂着没发成)")
    check(plan.undo_room(st, r1["id"]) == 1 and plan.quota_on(st, "CSGO战神君", today) == 20 and plan.undo_room(st, r1["id"]) == 0,
          "拎回来以后又标成已发:多加的那 1 条退回去(只退一次)")
    # 目标已经有同名的:停下来,原处不动,不加 (2)
    r2 = api_row("撞名的", "撞名的")
    (acc / f"{md}（星期一）" / "撞名的.mp4").write_bytes(b"y")
    new2, why2 = redo.pull_back(st, rec, r2, md)
    check(new2 == "" and "已经有" in why2 and (arc / "撞名的.mp4").is_file()
          and rec.conn.execute("SELECT status FROM posts WHERE id=?", (r2["id"],)).fetchone()[0] == "已发",
          f"今天的文件夹里已经有同名的:不挪、不加 (2)、记录不动 -> {why2}")
    # 不确定发没发 / 摆好的:不让挪
    r3 = api_row("不确定的", "不确定的")
    rec.conn.execute("UPDATE posts SET status='结果不明' WHERE id=?", (r3["id"],))
    rec.conn.commit()
    new3, why3 = redo.pull_back(st, rec, dict(r3, status="结果不明"), md)
    check(new3 == "" and "不确定发没发" in why3 and (arc / "不确定的.mp4").is_file(), f"「不确定发没发」的不让挪 -> {why3}")
    # 同一个视频两条「已发」记录:一起改,额度只加一次
    r4 = api_row("两条记录", "两条记录")
    rid_b = rec.api_begin(F.Video(path=r4["path"], title="两条记录", account="CSGO战神君", employee="", date="10.20"))
    rec.api_finish(rid_b, "已发", "")
    rec.conn.execute("UPDATE posts SET published_at='2026-10-20 11:00:00', moved_pkey=? WHERE id=?", (r4["moved_pkey"], rid_b))
    rec.conn.commit()
    o4 = {}
    redo.pull_back(st, rec, r4, md, o4)
    o4b = {}
    redo.pull_back(st, rec, dict(rec.conn.execute("SELECT * FROM posts WHERE id=?", (rid_b,)).fetchone()), md, o4b)
    check([x[0] for x in rec.conn.execute("SELECT status FROM posts WHERE id IN (?,?)", (r4["id"], rid_b))] == ["没发成", "没发成"]
          and o4.get("room") == 1 and not o4b.get("room"), "同一个视频的两条记录一起改成没发;额度只加一次")
    # 号的视频直接放在号文件夹里(没日期文件夹、名单里也找不到):挪回原文件夹
    flat = tmp / "ar" / "别处" / "电竞赛事"
    flat.mkdir(parents=True)
    v = F.Video(path=str(flat / "赛事.mp4"), title="赛事", account="不在名单的号", employee="", date="10.20")
    rid5 = rec.api_begin(v)
    rec.api_finish(rid5, "已发", "")
    (arc / "赛事.mp4").write_bytes(b"x")
    rec.mark_moved(rid5, str(arc / "赛事.mp4"))
    check(redo.target_dir(st, dict(rec.conn.execute("SELECT * FROM posts WHERE id=?", (rid5,)).fetchone()), md) == str(flat),
          "没日期文件夹的号:挪回原来的文件夹(原来直接报找不到)")
    # 教育号:封面在「梁\\封面\\标题\\」;原来套了一层同名日期
    eroot = tmp / "ar" / "小学生教育类"
    st["material_root"] = str(eroot)
    st["archive_root"] = str(tmp / "ar" / "教育归档" / "{month}月")
    day = eroot / "10.20"
    (day / "10.20" / "家长研习空间" / "梁" / "视频").mkdir(parents=True)
    vp = day / "10.20" / "家长研习空间" / "梁" / "视频" / "孩子磨蹭.mp4"
    vp.write_bytes(b"x")
    (day / "10.20" / "家长研习空间" / "梁" / "封面" / "孩子磨蹭").mkdir(parents=True)
    (day / "10.20" / "家长研习空间" / "梁" / "封面" / "孩子磨蹭" / "横屏16x9.png").write_bytes(b"p")
    rec.manual_published(F.Video(path=str(vp), title="孩子磨蹭", account="家长研习空间", employee="梁", date="10.20"))
    F.move_date(st, "10.20")
    er = dict(rec.conn.execute("SELECT * FROM posts WHERE title='孩子磨蹭'").fetchone())
    (eroot / f"{md}不能用").mkdir(parents=True)
    tdir = redo.target_dir(st, er, md)
    check(tdir == str(eroot / md / "家长研习空间" / "梁" / "视频"), f"教育号:不进「不能用」,去掉套着的同名日期那层 -> {tdir}")
    o5 = {}
    new5, why5 = redo.pull_back(st, rec, er, md, o5)
    check(why5 == "" and (eroot / md / "家长研习空间" / "梁" / "封面" / "孩子磨蹭" / "横屏16x9.png").is_file(),
          f"教育号放在「梁\\封面\\标题\\」的封面跟着挪 -> {why5} {o5.get('warn')}")


def test_audit_verify(tmp: Path):
    print("[审查 2026-10-26 核对:只有确定没发上的才打勾(跨半夜 / 翻页重复 / 单查出错 / 删掉的重复 / 系列标题 / 空状态)]")
    from qe import folders as F
    from qe import verify
    from qe.records import Records
    rec = Records(tmp / "r_av.sqlite")
    d0 = "2026-10-20"

    def put(title, edu=False, aid="", at=f"{d0} 10:00:00", acc="CSGO战神君"):
        v = F.Video(path=str(tmp / "av" / f"{title}.mp4"), title=title, account=acc, employee="小王" if edu else "", date="10.20")
        if edu:
            rec.manual_published(v)
            rid = rec.conn.execute("SELECT max(id) FROM posts").fetchone()[0]
        else:
            rid = rec.api_begin(v)
            rec.api_finish(rid, "已发", f"article_id={aid} vid=V{aid}" if aid else "")
        rec.conn.execute("UPDATE posts SET published_at=? WHERE id=?", (at, rid))
        rec.conn.commit()

    class C:
        def __init__(self, arts, info=None, dup_first=False):
            self.arts, self.info, self.dup_first = sorted(arts, key=lambda a: a["article_pub_time"], reverse=True), info, dup_first

        def list_articles(self, page=1, limit=10):
            a = self.arts
            if self.dup_first and page == 2:                 # 翻页中间有新文章进来:整张表往下挪,第 1 页最后一条又出现
                a = [a[0]] + a
            return {"articles": a[(page - 1) * limit: page * limit], "total": len(self.arts) + 1}

        def article_info(self, aid):
            if self.info == "err":
                raise RuntimeError("查文章:网络连不上")
            return {}

    def art(t, at, flag="发布成功", aid="", dele=""):
        return {"article_id": aid, "article_title": t, "article_pub_time": at, "article_pub_flag": flag, "article_del_flag": dele}
    # 跨半夜(教育号):记录记在 20 号,企鹅号上是 21 号 00:05
    put("跨半夜的", edu=True, at=f"{d0} 23:55:00", acc="家长研习空间")
    r = verify.check_edu(C([art("跨半夜的", "2026-10-21 00:05:00")]), rec, "家长研习空间", d0)
    check(not r["missing"], f"跨半夜发的:前后一天有就算发上了 -> {[m['why'] for m in r['missing']]}")
    # 翻页重复:同一篇不算两次
    many = [art(f"t{k}", f"{d0} 0{k % 9}:00:00", aid=f"P{k}") for k in range(15)]
    got = verify.platform_between(C(many, dup_first=True), d0, d0)
    check(len(got) == len({p["aid"] for p in got}) == 15, f"翻页中间表往下挪:同一篇只算一次 -> {len(got)}")
    # 翻到上限还没翻完:报查不了,不当成读完
    try:
        verify.platform_between(C([art("x", f"{d0} 10:00:00", aid=f"Q{k}") for k in range(30)]), "2020-01-01", d0, max_pages=2)
        ok = False
    except verify.ListTooLong:
        ok = True
    check(ok, "翻满页数上限还没翻到那天以前:报「查不了」")
    # 单查出错:不打勾
    put("单查出错的", aid="E1")
    r = verify.check_account(C([], info="err"), rec, "CSGO战神君", d0)
    m = next(x for x in r["missing"] if x["title"] == "单查出错的")
    check(m["sure"] is False and "看一眼" in m["why"], f"列表里没有、单查又出错:不打勾 -> {m['why']}")
    # 删掉的是重复的那条:同标题的在线 → 不打勾
    put("发重了", aid="D1", at=f"{d0} 11:00:00")
    put("发重了", aid="D2", at=f"{d0} 11:05:00")
    r = verify.check_account(C([art("发重了", f"{d0} 11:00:00", aid="D1"), art("发重了", f"{d0} 11:05:00", aid="D2", dele="已删除")]),
                             rec, "CSGO战神君", d0)
    m = next((x for x in r["missing"] if x["title"] == "发重了"), None)
    check(m is not None and m["sure"] is False and "同标题" in m["why"], f"删掉的是发重了的那条:不打勾 -> {m and m['why']}")
    # 被打回的:列出来,不打勾
    put("被打回的", aid="R1")
    r = verify.check_account(C([art("被打回的", f"{d0} 10:00:00", flag="审核不通过", aid="R1")]), rec, "CSGO战神君", d0)
    m = next(x for x in r["missing"] if x["title"] == "被打回的")
    check(m["sure"] is False and "打回" in m["why"], "被打回的:不打勾(再发多半还会被打回)")
    # 系列标题:第12集被打回,第13集后来发了 → 不算「已经补发过了」
    put("三角洲行动高光时刻第12集", aid="S12")
    put("三角洲行动高光时刻第13集", aid="S13", at="2026-10-21 10:00:00")
    r = verify.check_account(C([art("三角洲行动高光时刻第12集", f"{d0} 10:00:00", flag="未发布", aid="S12")]), rec, "CSGO战神君", d0)
    m = next(x for x in r["missing"] if x["title"] == "三角洲行动高光时刻第12集")
    check(m["sure"] is True and not m.get("redone"), f"第12集没发上、第13集后来发了:不认成补发过,照样打勾 -> {m['why']}")
    # 状态是空的:认不出,不打勾,也不算在线
    put("状态空的", aid="N1")
    r = verify.check_account(C([art("状态空的", f"{d0} 10:00:00", flag="", aid="N1")]), rec, "CSGO战神君", d0)
    m = next((x for x in r["missing"] if x["title"] == "状态空的"), None)
    check(m is not None and m["sure"] is False and "认不出" in m["why"], f"状态是空的:列出来看一眼 -> {m and m['why']}")


def test_autocover(tmp: Path):
    print("[没放封面的自动挑一帧(用户 2026-10-26:平台拿第一帧当封面,很多是黑屏;选了全自动)]")
    import subprocess
    import cv2
    import numpy as np
    from qe import autocover
    from qe.vertical import ffmpeg_path
    ff = ffmpeg_path()
    if not ff:
        print("  (没有 ffmpeg,跳过)")
        return
    d = tmp / "ac"
    d.mkdir()
    v1, v2 = d / "开头黑屏.mp4", d / "全黑.mp4"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:d=2",
                    "-f", "lavfi", "-i", "testsrc=s=320x568:d=6", "-filter_complex", "[0][1]concat=n=2:v=1[v]", "-map", "[v]",
                    "-pix_fmt", "yuv420p", str(v1)], check=True)
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:d=5",
                    "-pix_fmt", "yuv420p", str(v2)], check=True)
    p = autocover.pick(str(v1))
    img = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_GRAYSCALE) if p else None
    check(p and img is not None and img.mean() > 40 and img.std() > 20 and os.path.dirname(p) == autocover.cache_dir(),
          f"开头黑屏的:挑的是后面清楚的一帧,放在软件自己的文件夹里(不碰素材) -> {p}")
    check(not [x for x in os.listdir(d) if x.lower().endswith(".jpg")], "素材文件夹里没多出东西")
    n = autocover.next_frame(str(v1))
    check(n and n != p and autocover.pick(str(v1)) == n, "「换一帧」换成另一张,之后发的时候就用它")
    check(autocover.pick(str(v2)) == "", "整条都是黑屏的:挑不出来,让平台自己截")
    v3 = d / "黑边竖屏.mp4"                                  # 转过竖屏的:上下黑边,中间是画面 —— 不能当成黑屏
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=540x304:d=5",
                    "-vf", "pad=540:960:0:328:black", "-pix_fmt", "yuv420p", str(v3)], check=True)
    check(autocover.pick(str(v3)) != "", "上下黑边、中间有画面的(转过竖屏的):照样挑得出封面")


def test_unsure_check(tmp: Path):
    print("[结果不明的软件自己去企鹅号查(用户 2026-10-26,选了 B):查到了记成已发;查不到只提示,不自动改]")
    from datetime import timedelta
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, unsure
    from qe import folders as F
    from qe.config import Settings, bj_now, bj_str
    from qe.records import Records, pkey
    import gui.api_tab as T
    n = bj_now()
    md = f"{n.month}.{n.day}"
    root = tmp / "uc" / "游戏视频"
    d = root / "CSGO--CSGO战神君" / md
    d.mkdir(parents=True)
    for t in ("发上了的", "没发上的"):
        (d / f"{t}.mp4").write_bytes(b"x")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    rec = Records(tmp / "r_uc.sqlite")
    ago = bj_str(n - timedelta(minutes=20))
    ids = {}
    for t, vid in (("发上了的", "VID1"), ("没发上的", "VID2")):
        v = F.Video(path=str(d / f"{t}.mp4"), title=t, account="CSGO战神君", employee="", date=md)
        rid = rec.api_begin(v)
        rec.api_finish(rid, "结果不明", f"vid={vid};发布:网络连不上企鹅号")
        rec.conn.execute("UPDATE posts SET prepared_at=? WHERE id=?", (ago, rid))
        ids[t] = rid
    rec.conn.commit()
    pub = bj_str(n - timedelta(minutes=19))
    arts = [{"article_id": "A1", "article_title": "别的", "article_pub_time": pub, "article_video_info": {"vid": "VID1"}},
            {"article_id": "A9", "article_title": "老的", "article_pub_time": bj_str(n - timedelta(days=3)), "article_video_info": {"vid": "OLD"}}]

    class C:
        def __init__(self, *a, **k):
            pass

        def list_articles(self, page=1, limit=10):
            return {"articles": arts if page == 1 else [], "total": len(arts)}
    r1 = dict(rec.conn.execute("SELECT * FROM posts WHERE id=?", (ids["发上了的"],)).fetchone())
    check(unsure.find(C(), r1)["article_id"] == "A1", "按视频编号认出来(标题被平台改了也认得)")
    r2 = dict(rec.conn.execute("SELECT * FROM posts WHERE id=?", (ids["没发上的"],)).fetchone())
    check(unsure.find(C(), r2) is None, "后台没有的:找不到")
    st = Settings(tmp / "st_uc.json")
    st["api_roots"] = [str(root)]
    real = omapi.Client
    omapi.Client = C
    try:
        tab = T.ApiTab(st, rec, lambda m: None)
        tab.set_day(md)
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
        tab.check_unsure(force=True)
        _wait(app, lambda: tab._unsure_thread is not None and not tab._unsure_thread.is_alive(), 20)
        for _ in range(20):
            app.processEvents()
        got = rec.conn.execute("SELECT status, published_at, note FROM posts WHERE id=?", (ids["发上了的"],)).fetchone()
        check(got[0] == "已发" and got[1] == pub and got[2].startswith("article_id=A1"),
              f"查到了:记成已发,发布时间 / 文章编号用企鹅号上的 -> {tuple(got)}")
        i2 = next(k for k, v in enumerate(tab.videos) if v.title == "没发上的")
        i1 = next(k for k, v in enumerate(tab.videos) if v.title == "发上了的")
        check(rec.conn.execute("SELECT status FROM posts WHERE id=?", (ids["没发上的"],)).fetchone()[0] == "结果不明"
              and "多半没发上" in tab._status_text(i2)[0] and tab.state.get(i1) == "已发",
              f"查不到、发出去 20 分钟了:不自动改,只提示「多半没发上」(用户选的 B)-> {tab._status_text(i2)[0]}")
    finally:
        omapi.Client = real


def test_spill_picked_root(tmp: Path):
    print("[发够了:手选的是号的总文件夹(没日期文件夹)的,剩下的也挪进它里面明天的日期文件夹(用户 2026-10-27)]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, plan
    from qe import folders as F
    from qe.config import Settings, bj_now
    from qe.records import Records
    import gui.api_tab as T
    n = bj_now()
    md, tmr = f"{n.month}.{n.day}", plan.tomorrow_folder()
    root = tmp / "spr" / "游戏视频"
    acc = root / "地下城与勇士--DNF连招档案馆"
    acc.mkdir(parents=True)
    for k in range(3):
        (acc / f"剩下的{k}.mp4").write_bytes(b"x")
        (acc / f"剩下的{k}.jpg").write_bytes(b"j")
    apiacc.save([{"nick": "DNF连招档案馆", "source_name": "DNF", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    rec = Records(tmp / "r_spr.sqlite")
    rec.api_result(F.Video(path=str(tmp / "spr" / "发过的.mp4"), title="发过的", account="DNF连招档案馆", employee="", date=md), "已发")
    st = Settings(tmp / "st_spr.json")
    st["api_roots"] = [str(root)]
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"DNF连招档案馆": 1}}]
    st["api_picked"] = {md: {"DNF连招档案馆": str(acc)}}
    tab = T.ApiTab(st, rec, lambda m: None)
    tab.set_day(md)
    _wait(app, lambda: not tab.busy() and not list(acc.glob("*.mp4")), 20)
    got = sorted(x.name for x in (acc / tmr).iterdir()) if (acc / tmr).is_dir() else []
    check(not list(acc.glob("*.mp4")) and got == sorted([f"剩下的{k}{e}" for k in range(3) for e in (".jpg", ".mp4")]),
          f"今天发够了:总文件夹里剩下的连封面挪进「{tmr}」(明天页面自己认得出) -> {got}")


def test_quota_free(tmp: Path):
    print("[有多少发多少的号(用户 2026-10-27:电竞情报馆规定 80,但强时效、不一定有比赛):不卡条数、少了不算没发够,规定照写]")
    from qe import plan
    from qe import folders as F
    from qe.config import Settings, bj_now
    from qe.records import Records
    st = Settings(tmp / "st_qf.json")
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"电竞情报馆": 80, "PUBG突围君": 20}}]
    rec = Records(tmp / "r_qf.sqlite")
    day = bj_now().strftime("%Y-%m-%d")
    for k in range(30):
        rec.api_result(F.Video(path=str(tmp / "qf" / f"e{k}.mp4"), title=f"e{k}", account="电竞情报馆", employee="", date="x"), "已发")
    check(plan.is_free(st, "电竞情报馆") and not plan.is_free(st, "PUBG突围君"), "默认:电竞情报馆有多少发多少,别的号照常")
    check(plan.left_today(rec, st, "电竞情报馆", day) is None and plan.left_today(rec, st, "PUBG突围君", day) == 20,
          "电竞不卡条数(不限);别的号照样按规定算还能发几条")
    s = plan.summary(rec, st, day)
    short = [n for n, _q, _a in plan.short_list(s)]
    check("电竞情报馆" not in short and "PUBG突围君" in short and s["rows"][0][1] == 30 + 20,
          "电竞发了 30 条不算没发够;还差几条只算别的号")
    tsv = plan.as_tsv(s)
    check("游戏总发布量\t100\t30" in tsv, f"复制到企业微信:规定照写 100(含电竞的 80),实际 30 -> {tsv!r}")
    plan.set_free(st, "电竞情报馆", False)
    check(plan.left_today(rec, st, "电竞情报馆", day) == 50, "关掉以后:电竞也按 80 条卡")


def test_check_status(tmp: Path):
    """用户 2026-11-07:查过 / 没查 / 没查成 要分得清,还要能自己点「重新检查」。"""
    print("\n[检查状态:每条一格、进度、重新检查]")
    import threading
    from PySide6.QtWidgets import QApplication
    from qe import apiacc, audiocheck as A, checkline as L, cropcheck as K, folders as F, outrocheck as O, sharp as S
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    import gui.window as W
    app = QApplication.instance() or QApplication([])
    # 翻成字
    check(L.state(None) == L.TODO and L.state({"hits": []}) == L.OK and L.state({"hits": [1]}) == L.BAD
          and L.state({"hits": [1], "ok": True}) == L.PASSED and L.state({"hits": [1], "blurred": True}) == L.FIXED, "没查 / 没问题 / 有问题 / 放行 / 已剪")
    check(L.state({"hits": []}, busy=True) == L.BUSY, "重新检查时旧结果不算数:查中")
    check(L.state(None, err=True) == L.FAIL and L.state(None, sent=True) == L.NA and L.state(None, need=False) == L.NA and L.state(None, on=False) == L.OFF and L.state(None, key=False) == L.NOKEY,
          "没查成 / 已发不用查 / 这种号不查 / 关了 / 没填 Key 分得清")
    check(L.cell((L.OK, L.OK)) == "清晰 ✓  字幕 ✓" and L.cell((L.BUSY, L.BUSY)) == "查中" and L.cell((L.BAD, L.NA)) == "疑似模糊  字幕 不用查" and L.cell((L.FAIL, L.OK)) == "清晰 没查成  字幕 ✓", "表格里的字")
    check(L.cell((L.OK, L.OK, L.FIXED)) == "清晰 ✓  字幕 ✓  结尾 已剪" and L.cell((L.BUSY, L.BUSY, L.BUSY)) == "查中", "三项一起显示")
    check(L.progress([(L.OK, L.NA), (L.OK, L.NA)]) == "检查查完了:清晰度 2/2  —— 没查到问题", "这种号不查字幕:进度里不写;查完没问题说一句")
    check(L.progress([(L.BAD, L.NA), (L.OK, L.BAD)]) == "检查查完了:清晰度 2/2 · 字幕 1/1  —— 查到 1 条模糊 · 1 条字幕被裁", "查完了:顶上那行也写查到几条不对的")
    check(L.progress([(L.OK, L.BUSY), (L.FAIL, L.OK)]) == "正在检查:清晰度 1/2 · 字幕 1/2 · 1 条没查成", "进度写查到哪、几条没查成")
    check(L.progress([(L.OK, L.NOKEY)]) == "检查查完了:清晰度 1/1 · 字幕没填 Key  —— 没查到问题", "没填 Key:说清楚")
    check(L.unchecked_text([(L.OK, L.OK)]) == "" and L.unchecked_text([(L.TODO, L.OK), (L.BUSY, L.TODO), (L.OK, L.NOKEY)]) == "还有 2 条没查完(清晰度 2 条、字幕被裁 1 条),现在发就不查了。", "发布前提醒一句")
    check(L.group_text([(L.OK, L.OK)]) == "查完了 · 没问题" and L.group_text([(L.OK, L.OK), (L.TODO, L.OK)]) == "查了 1/2" and L.group_text([(L.FAIL, L.OK)]) == "1 条没查成", "号那一行")
    # 用户 2026-11-10:「查完了咋不说有没有查到不对的?必须要我点进去看」
    g = L.group_text([(L.BAD, L.OK), (L.BAD, L.NA), (L.OK, L.BAD), (L.PASSED, L.OK)])
    check(g == "查完了 · 2 条模糊 · 1 条字幕被裁", f"查完了:直接写查到几条不对的(放行过的不算) -> {g}")
    g = L.group_text([(L.BAD, L.OK), (L.TODO, L.OK)])
    check(g == "查了 1/2 · 1 条模糊", f"还在查:已经查到的也写上 -> {g}")
    # 接口页
    d = tmp / "chk" / "游戏视频" / "CSGO--CSGO战神君" / "10.18"
    d.mkdir(parents=True)
    for n, b in (("好", b"1"), ("糊", b"22")):
        (d / f"{n}.mp4").write_bytes(b)
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_chk.json")
    st["api_roots"] = [str(tmp / "chk" / "游戏视频")]
    st["ai_key"] = "test"
    tab = T.ApiTab(st, Records(tmp / "rec_chk.sqlite"), lambda m: None)
    tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, squarish=False, w=720, h=1280, platform=[], tags=[], dur=10)
    i = next(k for k, v in enumerate(tab.videos) if v.title == "糊")
    g = 1 - i
    calls, boom, gate = [], [], [None]

    def fsharp(path, ff, dur, stop=None):
        calls.append("清" + os.path.basename(path))
        if gate[0]:
            gate[0].wait(20)
        if os.path.basename(path) in boom:
            raise OSError("读不出")
        return {"hits": [{"kind": "blur", "score": 50}] if path.endswith("糊.mp4") else []}

    def fcrop(path, ff, dur, key, stop=None, asker=None):
        calls.append("字" + os.path.basename(path))
        return {"hits": []}

    def foutro(path, ff, dur, key, stop=None, grab=None, asker=None, shot_dir=""):
        calls.append("尾" + os.path.basename(path))
        return {"hits": []}

    def faudio(path, ff, dur=0.0, has_audio=None, stop=None, measure=None):
        calls.append("声" + os.path.basename(path))
        return {"hits": []}

    def settle(idle):
        _wait(app, idle)
        for _ in range(5):
            app.processEvents()
            time.sleep(0.02)
        _wait(app, idle)
        app.processEvents()
    idle1 = lambda: not (tab.sharp_worker and tab.sharp_worker.isRunning())
    rs, rk, ro, ra, rask = S.check, K.check, O.check, A.check, T.ask
    S.check, K.check, O.check, A.check = fsharp, fcrop, foutro, faudio
    tab.SHARP_CHECK = True
    try:
        tab._fill(0), tab._fill(1)
        tab._check_refresh()
        check(tab.items[0].text(4) == "没查" and tab.lab_check.text() == "检查:清晰度 0/2 · 字幕 0/2 · 结尾 0/2 · 声音 0/2", f"还没查:写没查 -> {tab.items[0].text(4)} / {tab.lab_check.text()}")
        tab._sharp_start()
        settle(idle1)
        check(tab.items[g].text(4) == "清晰 ✓  字幕 ✓  结尾 ✓  声音 ✓" and tab.items[i].text(4) == "疑似模糊  字幕 ✓  结尾 ✓  声音 ✓", f"查完:每条写清楚 -> {tab.items[g].text(4)} / {tab.items[i].text(4)}")
        check(tab.lab_check.text().startswith("检查查完了:清晰度 2/2 · 字幕 2/2 · 结尾 2/2 · 声音 2/2"), f"进度 -> {tab.lab_check.text()}")
        check(tab.groups["CSGO战神君"].text(4) == "查完了 · 1 条模糊", f"号那一行写查完了、查到几条 -> {tab.groups['CSGO战神君'].text(4)}")
        check(tab.b_recheck.text() == "重新检查 2 条", f"没选管全部 -> {tab.b_recheck.text()}")
        tab.items[g].setSelected(True)
        tab._update_scope()
        check(tab.b_recheck.text() == "重新检查 1 条", f"跟着选中走 -> {tab.b_recheck.text()}")
        tab.tree.clearSelection()
        tab._update_scope()
        # 查过、文件没变:自动的不再查;人点了就真查
        calls.clear()
        tab._sharp_start()
        settle(idle1)
        check(not calls, "自动的:查过的不再查")
        tab.set_sharp_ok(i)
        tab._check_refresh()
        check(tab.items[i].text(4) == "清晰 放行  字幕 ✓  结尾 ✓  声音 ✓", f"人说没问题:写放行 -> {tab.items[i].text(4)}")
        tab.recheck()
        settle(idle1)
        check(sorted(calls) == sorted(["字好.mp4", "字糊.mp4", "尾好.mp4", "尾糊.mp4", "清好.mp4", "清糊.mp4", "声好.mp4", "声糊.mp4"]), f"点重新检查:不管查没查过都再查 -> {calls}")
        check(tab.items[i].text(4) == "清晰 放行  字幕 ✓  结尾 ✓  声音 ✓" and not tab._recheck_paths, f"你点过没问题的还算数,查完清单空了 -> {tab.items[i].text(4)}")
        # 只查选中的
        calls.clear()
        tab.items[g].setSelected(True)
        tab._update_scope()
        tab.recheck()
        settle(idle1)
        check(sorted(calls) == sorted(["字好.mp4", "尾好.mp4", "清好.mp4", "声好.mp4"]), f"选中了:只查选中的 -> {calls}")
        tab.tree.clearSelection()
        tab._update_scope()
        # 没查成
        boom.append("好.mp4")
        tab._recheck_paths.add(tab.videos[g].path)
        tab.videos[g].sharp = None
        tab._sharp_start()
        settle(idle1)
        check(tab.items[g].text(4) == "清晰 没查成  字幕 ✓  结尾 ✓  声音 ✓" and "1 条没查成" in tab.lab_check.text(), f"读不出来:写没查成 -> {tab.items[g].text(4)} / {tab.lab_check.text()}")
        check(tab.groups["CSGO战神君"].text(4) == "1 条没查成", "号那一行也写")
        boom.clear()
        # 正在查的时候点:手上这一轮停下,接着查人点的;中间写查中
        gate[0] = threading.Event()
        calls.clear()
        tab._recheck_paths.add(tab.videos[g].path)
        tab.videos[g].sharp = None
        tab._sharp_start()
        _wait(app, lambda: calls)
        tab._check_refresh()
        check(tab.items[g].text(4) == "查中" and tab.lab_check.text().startswith("正在检查"), f"查的时候写查中 -> {tab.items[g].text(4)} / {tab.lab_check.text()}")
        tab.recheck()
        check(tab.sharp_worker.stop, "手上这一轮先停")
        old = tab.sharp_worker
        gate[0].set()
        _wait(app, lambda: tab.sharp_worker is not old)
        gate[0] = None
        settle(idle1)
        check("清糊.mp4" in calls and "字糊.mp4" in calls and "尾糊.mp4" in calls and "声糊.mp4" in calls and not tab._recheck_paths, f"接着把人点的查完 -> {calls}")
        # 字幕关了:关掉的项彻底隐藏,不再显示「关了」
        st["crop_check"] = False
        tab.videos[i].crop = None
        tab.videos[i].checks.pop("crop", None)
        tab._check_refresh()
        check(tab.items[i].text(4) == "清晰 放行  结尾 ✓  声音 ✓", f"设置关了:彻底隐藏该检查项 -> {tab.items[i].text(4)}")
        st["crop_check"] = True
        # 多的时候问一声
        seen = []
        T.ask = lambda *a, **k: seen.append(a[2]) or False
        tab._recheck_rows = lambda: [0, 1] * 20
        tab.recheck()
        check(seen and "40 条" in seen[0] and not tab._recheck_paths, "条数多:先问一声,点先不就不查")
        del tab._recheck_rows
        T.ask = rask
        apiacc.save([])
        # 罐头页:字幕被裁只查影视号,结尾求关注和声音教育和影视都查
        st2 = Settings(tmp / "st_chk2.json")
        st2["ai_key"] = "test"
        film = tmp / "chk" / "高热剧集二创" / "影视号甲"
        film.mkdir(parents=True)
        (film / "片.mp4").write_bytes(b"333")
        edu = tmp / "chk" / "小学生教育"
        edu.mkdir(parents=True)
        (edu / "课.mp4").write_bytes(b"4444")
        st2["accounts"] = [{"name": "影视号甲", "aliases": [], "dir": str(film)}]
        w = W.MainWindow(st2, Records(tmp / "rec_chk2.sqlite"))
        w.AI_COVER = False
        w.SHARP_CHECK = True
        idle2 = lambda: not (w.sharp_worker and w.sharp_worker.isRunning())
        w.videos = [F.Video(str(film / "片.mp4"), "片", "影视号甲", "e", "10.18"), F.Video(str(edu / "课.mp4"), "课", "研习社", "e", "10.18")]
        w.table.setRowCount(2)
        w._fill_row(0), w._fill_row(1)
        w._check_line()
        check(w.table.columnCount() == 6 and w.table.item(0, 5).text() == "没查", f"还没查 -> {w.table.item(0, 5).text()}")
        check(w.table.item(1, 5).text() == "清晰 没查  字幕 不用查  结尾 没查  声音 没查", f"教育:字幕不用查,结尾和声音要查 -> {w.table.item(1, 5).text()}")
        check(w.lab_check.text() == "检查:清晰度 0/2 · 字幕 0/1 · 结尾 0/2 · 声音 0/2", f"进度只算要查的 -> {w.lab_check.text()}")
        calls.clear()
        w._sharp_start()
        settle(idle2)
        check(sorted(calls) == sorted(["字片.mp4", "尾片.mp4", "尾课.mp4", "清片.mp4", "清课.mp4", "声片.mp4", "声课.mp4"]), f"影视号四项都查,教育查清晰度结尾声音 -> {calls}")
        check(w.table.item(0, 5).text() == "清晰 ✓  字幕 ✓  结尾 ✓  声音 ✓" and w.table.item(1, 5).text() == "清晰 ✓  字幕 不用查  结尾 ✓  声音 ✓"
              and w.lab_check.text().startswith("检查查完了:清晰度 2/2 · 字幕 1/1 · 结尾 2/2 · 声音 2/2"),
              f"查完 -> {w.table.item(0, 5).text()} / {w.table.item(1, 5).text()} / {w.lab_check.text()}")
        check(w.b_recheck.text() == "重新检查 2 条", f"没选管全部 -> {w.b_recheck.text()}")
        w.table.selectRow(1)
        check(w.b_recheck.text() == "重新检查 1 条", f"跟着选中走 -> {w.b_recheck.text()}")
        calls.clear()
        w.recheck()
        settle(idle2)
        check(sorted(calls) == sorted(["尾课.mp4", "清课.mp4", "声课.mp4"]), f"重新检查选中的教育:不会去查字幕 -> {calls}")
        w.table.clearSelection()
        calls.clear()
        w.recheck()
        settle(idle2)
        check(sorted(calls) == sorted(["字片.mp4", "尾片.mp4", "尾课.mp4", "清片.mp4", "清课.mp4", "声片.mp4", "声课.mp4"]), f"没选:全部再查 -> {calls}")
        check(w.table.item(0, 4).text() == "还没发", f"「状态」那格不受影响 -> {w.table.item(0, 4).text()}")
        w.close()
    finally:
        S.check, K.check, O.check, A.check, T.ask = rs, rk, ro, ra, rask
        apiacc.save([])


def test_ai_errors(tmp: Path):
    """用户 2026-11-09:百炼欠费了,软件只写「AI 没回话(KeyError)」,看不出来 → 写清楚;欠费 / Key 不对的后台别一条一条接着问。"""
    print("\n[阿里百炼报错写清楚]")
    from types import SimpleNamespace
    import requests
    from PIL import Image
    from qe import aierr, cropcheck as K, dupname, gamecheck, topic
    from gui.sharp_worker import SharpWorker

    class R:
        def __init__(self, status, body):
            self.status_code, self._b, self.text = status, body, str(body)

        def json(self):
            if isinstance(self._b, Exception):
                raise self._b
            return self._b
    arrear = R(400, {"error": {"message": "Access denied, please make sure your account is in good standing.", "type": "Arrearage", "code": "Arrearage"}})
    check(aierr.why(arrear) == aierr.ARREARS and aierr.hard(aierr.why(arrear)), "欠费(兼容接口):认得出,算再问也没用")
    check(aierr.why(R(400, {"code": "Arrearage", "message": "x"})) == aierr.ARREARS, "欠费(原生接口,扩图用的):也认得出")
    check(aierr.why(R(401, {"error": {"code": "invalid_api_key"}})) == aierr.BADKEY and aierr.hard(aierr.BADKEY), "Key 不对")
    check(aierr.why(R(429, {"error": {"code": "Throttling.RateQuota"}})) == aierr.BUSY and not aierr.hard(aierr.BUSY), "太频繁:说等一会儿,下次还会再试")
    check(aierr.why(R(500, ValueError("不是 JSON"))) == "" and aierr.why(R(200, {"choices": []})) == "", "认不出来的:给空,调用的地方照旧写")
    real = requests.post
    seen = []

    def fake(*a, **k):
        seen.append(1)
        return arrear
    requests.post = fake
    try:
        msgs = []
        for f in (lambda: K.ask(Image.new("RGB", (72, 128)), "k"),
                  lambda: dupname.ask_ai("标题", [], "k"),
                  lambda: gamecheck._ask_once("和平精英", ["一个标题"], "k", "qwen-plus", "https://dashscope.aliyuncs.com/compatible-mode/v1", 60),   # ask_ai 测试里换掉了
                  lambda: topic.ask_ai("正文", ["#a", "#b"], "k")):
            try:
                f()
                msgs.append("没报错")
            except RuntimeError as e:
                msgs.append(str(e))
        check(all(m == aierr.ARREARS for m in msgs), f"字幕被裁 / 重名改标题 / 串游戏 / 挑话题:都写欠费 -> {msgs}")

        def boom(*a, **k):
            raise requests.ConnectionError("断网")
        requests.post = boom
        try:
            K.ask(Image.new("RGB", (72, 128)), "k")
            m = ""
        except RuntimeError as e:
            m = str(e)
        check(m.startswith("连不上阿里百炼"), f"断网:写连不上,不是欠费 -> {m}")
    finally:
        requests.post = real
    # 后台查字幕被裁:欠费一次就不再问后面的
    asked = []

    def fcrop(path, ff, dur, key, stop=None, asker=None):
        asked.append(path)
        raise RuntimeError(aierr.ARREARS)
    rk = K.check
    K.check = fcrop
    try:
        vs = [SimpleNamespace(path=f"x{i}.mp4", checks={"dur": 10}) for i in range(6)]
        w = SharpWorker(vs, list(range(6)), want_sharp=False, crop_key="k", need_crop=lambda v: True)
        w.run()
    finally:
        K.check = rk
    check(len(asked) <= 3 and w.errors and w.errors[0] == aierr.ARREARS, f"欠费:最多同时在问的那几条,后面的不问了 -> 问了 {len(asked)} 条")
    check(all(getattr(v, "crop", None) is None for v in vs), "没查成的不记成没问题")


def test_own_ai(tmp: Path):
    """用户 2026-11-09:试试自己部署的模型(地址 / 模型 / Key 自己填)。文字的活问它;认得图才让它看图。"""
    print("\n[自己的模型]")
    import requests
    from PIL import Image
    from qe import aiconf as A, aierr, cropcheck as K, dupname, topic
    from qe.config import Settings
    st = Settings(tmp / "st_own.json")
    st["ai_key"] = "bailian"
    check(A.text(st).base == A.DASH and A.text(st).key == "bailian" and A.vision(st).model == A.VISION_MODEL, "没填:全用阿里百炼")
    st["own_ai_url"], st["own_ai_model"] = "http://127.0.0.1:8788/v1", "deepseek-v4.1-flash"
    check(A.text(st).base == A.DASH, "没填全(缺 Key):还用阿里百炼")
    st["own_ai_key"] = "mine"
    t, v = A.text(st), A.vision(st)
    check(t.own and t.url() == "http://127.0.0.1:8788/v1/chat/completions" and t.model == "deepseek-v4.1-flash" and t.key == "mine" and t.extra() == {},
          "填全了:文字的活问自己的模型,不带百炼的参数")
    check(v.base == A.DASH and v.key == "bailian", "还没试过认不认图:看图的活还问阿里百炼")
    st["own_ai_vision"] = A.sig(t.base, t.model)
    check(A.vision(st).own, "试过、认得图:看图的活也问它")
    st["own_ai_model"] = "别的模型"
    check(not A.vision(st).own and A.text(st).model == "别的模型", "换了模型:认图要再试一下")
    st["own_ai_model"] = "deepseek-v4.1-flash"
    check(A.clean("<think>想一想\n很久</think>\n好") == "好" and A.tokens(t, 60) == 1500 and A.tokens(A.as_ai("k", "m"), 60) == 60, "先想一想的模型:去掉想的过程、多给字数")
    # 「试一下」
    def fake_post(ai, content, n, timeout):
        if isinstance(content, list):
            raise RuntimeError("你自己的模型没回话(HTTP 400)image not supported")
        return "好"
    r = A.probe(t, post=fake_post)
    check(r["text"][0] and not r["image"][0] and "不认图" in r["image"][1], f"只认文字的:文字能用、看图不认 -> {r}")
    r = A.probe(t, post=lambda ai, c, n, to: "红色的圆形" if isinstance(c, list) else "好")
    check(r["text"][0] and r["image"][0], "认得图的:都能用")
    r = A.probe(t, post=lambda ai, c, n, to: "蓝色方块" if isinstance(c, list) else "好")
    check(not r["image"][0], "看图瞎说的:当它不认图")
    # 真的发出去长什么样(假的 requests.post)
    sent = []

    class R:
        status_code = 200
        text = ""

        def __init__(self, content=None, status=200, body=None):
            self.status_code, self._b = status, body if body is not None else {"choices": [{"message": {"content": content}}]}

        def json(self):
            return self._b
    real = requests.post

    def fake(url, json=None, headers=None, timeout=None):
        sent.append((url, json, headers))
        return R("<think>嗯</think>新的说法" if "cut" not in str(json) else '{"subtitle":"有","cut":"切断了"}')
    requests.post = fake
    try:
        out = dupname.ask_ai("原来的标题", [], t)
        u, body, hd = sent[-1]
        check(out == "新的说法" and u == t.url() and body["model"] == "deepseek-v4.1-flash" and "enable_thinking" not in body
              and hd["Authorization"] == "Bearer mine" and body["max_tokens"] == 1500, "处理重名:问自己的模型,回答去掉想的过程")
        dupname.ask_ai("原来的标题", [], "bailian")
        check(sent[-1][0].startswith(A.DASH) and sent[-1][1]["enable_thinking"] is False, "传的是百炼 Key 字符串:照旧问百炼")
        check(K.ask(Image.new("RGB", (72, 128)), A.vision(st)) and sent[-1][0] == t.url(), "字幕被裁:认得图的自己模型")
        requests.post = lambda *a, **k: R(status=401, body={"error": {"message": "invalid api key", "code": 401}})
        try:
            dupname.ask_ai("x", [], t)
            m = ""
        except RuntimeError as e:
            m = str(e)
        check(m == "你自己的模型 Key 不对(去「设置」里重填)" and aierr.hard(m), f"Key 不对:说是自己模型的 Key -> {m}")

        def down(*a, **k):
            raise requests.ConnectionError("拒绝连接")
        requests.post = down
        try:
            dupname.ask_ai("x", [], t)
            m = ""
        except RuntimeError as e:
            m = str(e)
        check(m.startswith("连不上你自己的模型"), f"服务没开:说连不上自己的模型 -> {m}")
    finally:
        requests.post = real


def test_vcheck(tmp: Path):
    """用户 2026-11-09:「再来一个功能去企鹅号查 选中的视频有没有发上去」—— 罐头页右键,只读,按标题对;对不上的人自己勾了再改。"""
    print("\n[去企鹅号查选中的]")
    import time
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, omapi, verify
    from qe import folders as F
    from qe.records import Records
    import gui.vcheck_dialog as VD
    today = "2026-11-09"

    def art(t, at, flag="发布成功", dele=""):
        return {"article_id": "", "article_title": t, "article_pub_time": at, "article_pub_flag": flag, "article_del_flag": dele}

    class C:
        def __init__(self, arts):
            self.arts, self.pages = sorted(arts, key=lambda a: a["article_pub_time"], reverse=True), 0

        def list_articles(self, page=1, limit=10):
            self.pages += 1
            return {"articles": self.arts[(page - 1) * limit: page * limit], "total": len(self.arts)}
    arts = [art("家庭开支管控难养成强制储蓄习惯", "2026-11-09 10:00:00"),
            art("家长容易焦虑内耗七句心理暗示平复情绪稳定养育心态", "2026-11-09 10:05:00"),   # 企鹅号截短了
            art("被打回的那条", "2026-11-09 11:00:00", flag="审核未通过"),
            art("定时的那条", "2026-11-10 08:00:00", flag="10"),
            art("其实发了的", "2026-11-08 20:00:00"),
            art("很早以前的", "2026-10-01 20:00:00")]
    items = [{"i": 0, "title": "家庭开支管控难，养成强制储蓄习惯", "sent_day": today},
             {"i": 1, "title": "家长容易焦虑内耗，七句心理暗示，平复情绪稳定养育心态，给孩子更好的成长", "sent_day": today},
             {"i": 2, "title": "被打回的那条", "sent_day": today},
             {"i": 3, "title": "按错了标成已发的", "sent_day": today},
             {"i": 4, "title": "定时的那条", "sent_day": ""},
             {"i": 5, "title": "其实发了的", "sent_day": ""},
             {"i": 6, "title": "还没发的", "sent_day": ""},
             {"i": 7, "title": "很早以前的", "sent_day": ""}]
    cl = C(arts)
    r = {x["i"]: x for x in verify.check_videos(cl, items, today)}
    check(r[0]["kind"] == "on" and not r[0]["fix"] and "11-09 10:00" in r[0]["text"], f"已发、企鹅号上有:对上 -> {r[0]['text']}")
    check(r[1]["kind"] == "on", f"企鹅号把长标题截短了:也认得 -> {r[1]['text']}")
    check(r[2]["kind"] == "bad" and r[2]["fix"] == "unsend" and "打回" in r[2]["text"], f"被打回:能改回还没发 -> {r[2]['text']}")
    check(r[3]["kind"] == "none" and r[3]["fix"] == "unsend" and "没找到" in r[3]["text"], f"按错了标成已发的:企鹅号上没有 -> {r[3]['text']}")
    check(r[4]["kind"] == "wait" and r[4]["fix"] == "mark" and "定时没到点" in r[4]["text"] and r[4]["at"].startswith("2026-11-10"),
          f"定时没到点:算在企鹅号上,能标成已发 -> {r[4]['text']}")
    check(r[5]["kind"] == "on" and r[5]["fix"] == "mark" and r[5]["at"] == "2026-11-08 20:00:00", "软件记没发、企鹅号上其实有:能标成已发(时间用企鹅号上的)")
    check(r[6]["kind"] == "none" and not r[6]["fix"], "没发、企鹅号上也没有:对上了,不用改")
    check(r[7]["kind"] == "none" and not r[7]["fix"], f"很早以前发过同标题的:不算这次的 -> {r[7]['text']}")
    check(cl.pages == 1, f"一个号的后台列表只翻一遍 -> {cl.pages} 页")
    # 窗口:用假的钥匙 / 客户端,勾上了才改
    rec = Records(tmp / "vck.sqlite")
    d0 = tmp / "vck"
    d0.mkdir()
    vids = []
    for t in ("被打回的那条", "其实发了的", "家庭开支管控难，养成强制储蓄习惯"):
        (d0 / f"{t}.mp4").write_bytes(b"x")
        vids.append(F.Video(path=str(d0 / f"{t}.mp4"), title=t, account="家长小天地", employee="", date="11.9"))
    vids.append(F.Video(path=str(d0 / "没钥匙的.mp4"), title="没钥匙的", account="别的号", employee="", date="11.9"))
    rec.manual_published(vids[0], at=f"{today} 11:00:00")
    rec.manual_published(vids[2], at=f"{today} 10:00:00")
    its = [{"i": k, "title": v.title, "alts": [], "account": v.account, "sent_day": today if k in (0, 2) else ""} for k, v in enumerate(vids)]
    real = (apiacc.check_accounts, apiacc.unseal, omapi.Client)
    apiacc.check_accounts = lambda: [{"nick": "家长小天地", "client_id": "c", "secret": "s", "query_only": True}]
    apiacc.unseal = lambda s: s
    omapi.Client = lambda *a, **k: C(arts)
    try:
        dlg = VD.VCheckDialog(rec, vids, its, today)
        t0 = time.time()
        while dlg.w.isRunning() and time.time() - t0 < 10:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        txt = [dlg.t.item(k, 3).text() for k in range(4)]
        check("打回" in txt[0] and "企鹅号上有" in txt[1] and "企鹅号上有" in txt[2] and "没取钥匙" in txt[3], f"一条一行说结果 -> {txt}")
        check("查完了" in dlg.head.text() and "1 条软件记已发" in dlg.head.text() and "1 条查不了" in dlg.head.text(), f"上面一句大字 -> {dlg.head.text()}")
        check(not dlg.b_unsend.isEnabled() and not dlg.b_mark.isEnabled()
              and dlg.t.item(0, 0).checkState() == Qt.CheckState.Unchecked and dlg.t.item(2, 0).text() == "", "对不上的默认不勾,按钮灰着;对上的没有勾")
        dlg.t.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dlg.t.item(1, 0).setCheckState(Qt.CheckState.Checked)
        check(dlg.b_unsend.text() == "改回还没发(勾上的 1 条)" and dlg.b_mark.isEnabled(), f"勾上了按钮写几条 -> {dlg.b_unsend.text()}")
        dlg.apply("unsend")
        dlg.apply("mark")
        check(rec.status_of(vids[0].path) == "" and rec.status_of(vids[1].path) == "已发" and rec.status_of(vids[2].path) == "已发",
              "改回还没发 / 标成已发:只改勾上的")
        check(rec.sent_row(vids[1].path)["published_at"] == "2026-11-08 20:00:00" and dlg.changed, "标成已发:发布时间用企鹅号上的")
        check(dlg.t.item(0, 0).text().startswith("✓") and not dlg.b_unsend.isEnabled(), "改完那行写 ✓,按钮又灰了")
        dlg.close()
    finally:
        apiacc.check_accounts, apiacc.unseal, omapi.Client = real


def test_outro_cut(tmp: Path):
    """用户 2026-11-16:结尾有求关注头像 / 别人账号 / 二维码 → 全部号都查,剪前给人看,剪掉照样发,原片进「结尾原片」。"""
    print("\n[结尾求关注:检测、定位、预览、剪掉、放行]")
    import subprocess
    from types import SimpleNamespace
    import numpy as np
    import requests
    from PIL import Image
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication, QMenu
    from gui.outro_dialog import OutroDialog
    from gui.sharp_worker import SharpWorker
    from qe import aierr, apiacc, checkline as L, checks, folders as F, outrocheck as O, vertical, wmstore
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T
    import gui.window as W

    app = QApplication.instance() or QApplication([])
    # 1. AI 返回读得出来
    p1 = O.parse('好的{"found": true, "tiles": [3, 4], "kind": "头像求关注", "reason": "圆头像配点赞关注"}')
    p2 = O.parse('{"found": false, "tiles": [], "kind": "没有", "reason": "正常台词"}')
    check(p1["found"] and p1["tiles"] == [3, 4] and p1["kind"] == "头像求关注", f"AI 返回读得对 -> {p1}")
    check(not p2["found"] and p2["tiles"] == [], f"没找到 -> {p2}")

    # 2. ask() 出错翻译(绝不真问 AI)
    class _R:
        def __init__(self, status, body):
            self.status_code, self._b, self.text = status, body, str(body)

        def json(self):
            return self._b
    real_post = requests.post
    requests.post = lambda *a, **k: _R(400, {"error": {"code": "Arrearage"}})
    try:
        try:
            O.ask(Image.new("RGB", (64, 64)), "k")
            err = ""
        except RuntimeError as e:
            err = str(e)
        check(err == aierr.ARREARS, f"欠费说清楚 -> {err}")
    finally:
        requests.post = real_post

    # 3. 起点定位 + 截图 + 不可读 / AI 报错不放行(用内存模拟帧)
    rng = np.random.default_rng(7)
    im_main = Image.fromarray((rng.random((160, 90, 3)) * 200 + 30).astype("uint8"))
    im_card = Image.new("RGB", (90, 160), (5, 5, 5))
    im_card.paste(Image.new("RGB", (40, 40), (240, 240, 240)), (25, 60))

    def grab_fake(t):
        return im_card if t >= 8.0 else im_main
    r_hit = O.check(str(tmp / "fake_outro.mp4"), "", 10.0, "k", grab=grab_fake,
                    asker=lambda g: {"found": True, "tiles": [3, 4], "kind": "二维码", "reason": "片尾二维码"},
                    shot_dir=str(tmp / "oshot"))
    check(r_hit["hits"] and r_hit["hits"][0]["start"] >= 8.0 and os.path.isfile(r_hit["shot"]),
          f"算出从卡片出现那帧剪 + 存截图 -> {r_hit}")
    r_ok = O.check(str(tmp / "fake_ok.mp4"), "", 10.0, "k", grab=lambda t: im_main,
                   asker=lambda g: {"found": False, "tiles": [], "kind": "没有", "reason": ""})
    check(r_ok == {"hits": []}, f"正常结尾不算 -> {r_ok}")
    bad = False
    try:
        O.check("x", "", 10.0, "k", grab=lambda t: None, asker=lambda g: {})
    except OSError:
        bad = True
    check(bad, "读不出画面报错,不记成没问题")

    # 4. SharpWorker 遇到硬错误(欠费)不再继续问后面的
    asked = []
    ro = O.check

    def fake_boom(path, ff, dur, key, stop=None, grab=None, asker=None, shot_dir=""):
        asked.append(path)
        raise RuntimeError(aierr.ARREARS)
    O.check = fake_boom
    try:
        vs_err = [SimpleNamespace(path=f"o{k}.mp4", checks={"dur": 10}) for k in range(6)]
        sw = SharpWorker(vs_err, list(range(6)), want_sharp=False, outro_key="k", need_outro=lambda v: True)
        sw.run()
    finally:
        O.check = ro
    check(len(asked) <= 3 and sw.outro_errors and sw.outro_errors[0] == aierr.ARREARS, f"欠费一次就停 -> {len(asked)}")

    # 5. 真 ffmpeg 造一条 5 秒测试短片(前 3.5 秒亮灰,后 1.5 秒暗黑)→ 用 outrocheck.cut 剪掉结尾 → 原片进「结尾原片」
    ff = vertical.ffmpeg_path()
    odir = tmp / "outro_real" / "游戏视频" / "CSGO--CSGO战神君" / "10.18"
    odir.mkdir(parents=True)
    vid = odir / "测试结尾.mp4"
    r_ff = subprocess.run(
        [ff, "-v", "error", "-y",
         "-f", "lavfi", "-t", "3.5", "-i", "color=c=0x88aacc:s=160x284:r=25",
         "-f", "lavfi", "-t", "1.5", "-i", "color=c=0x050505:s=160x284:r=25",
         "-f", "lavfi", "-t", "5.0", "-i", "anullsrc=r=44100:cl=stereo",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
         "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(vid)],
        capture_output=True, timeout=60,
    )
    check(r_ff.returncode == 0 and vid.is_file(), "本地造测试短视频")
    guard_err = False
    try:
        O.cut(str(vid), 0.2, ff)
    except RuntimeError:
        guard_err = True
    check(guard_err, "剪切起点太靠前(超过六成):拦住不剪")
    new_v, orig_v, gone = O.cut(str(vid), 3.45, ff)
    ndur = vertical.probe(new_v, ff)["dur"]
    check(os.path.isfile(new_v) and os.path.basename(os.path.dirname(orig_v)) == O.ORIG_DIR and os.path.isfile(orig_v)
          and 3.2 <= ndur <= 3.7 and gone >= 1.2,
          f"剪掉结尾:新片 {ndur:.2f}s(剪掉 {gone}s),原片进「{O.ORIG_DIR}」")
    check("结尾原片" in F.ORIG_DIRS, "「结尾原片」放进跳过列表,不再扫描")

    # 6. 接口页完整流程: 查出 -> 拦发布 / 亮红卡 -> 右键放行 / 再标回 -> 预览框剪掉 -> 结尾 已剪 / 能发
    (odir / "正常.mp4").write_bytes(b"123")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_outro_api.json")
    st["api_roots"] = [str(tmp / "outro_real" / "游戏视频")]
    st["ai_key"] = "test"
    tab = T.ApiTab(st, Records(tmp / "rec_outro_api.sqlite"), lambda m: None)
    tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
    for v in tab.videos:
        v.checks = dict(v.checks or {}, bad_read=False, landscape=False, squarish=False, w=160, h=284, platform=[], tags=[], dur=3.5)
    shot_p = tmp / "shot_api.jpg"
    im_card.save(str(shot_p))
    i_bad = next(k for k, v in enumerate(tab.videos) if v.title == "测试结尾")
    i_ok = 1 - i_bad
    # 先把测试视频恢复到 5 秒带着结尾的那个文件(用 orig_v 拷一份回来模拟未剪)
    shutil.copy2(orig_v, tab.videos[i_bad].path)

    def foutro_tab(path, ff, dur, key, stop=None, grab=None, asker=None, shot_dir=""):
        if path.endswith(("测试结尾.mp4", "教育条.mp4")):
            return {"hits": [{"start": 3.45, "dur": 5.0, "cut": 1.6, "kind": "头像求关注", "reason": "圆头像配点赞关注"}], "shot": str(shot_p)}
        return {"hits": []}
    O.check = foutro_tab
    try:
        w = SharpWorker(tab.videos, [0, 1], want_sharp=False, outro_key="k", need_outro=tab._outro_todo)
        w.run()
    finally:
        O.check = ro
    tab._outro_card()
    tab._fill(i_bad), tab._fill(i_ok)
    check(w.n_outro == 1 and O.TEXT in checks.problems(tab.videos[i_bad]) and not tab._can_send(i_bad) and tab._can_send(i_ok),
          "查到结尾求关注:拦住不发,正常的照常能发")
    check(not tab.card_outro.isHidden() and "1 条结尾有求关注" in tab.card_outro.title.text() and tab.b_outro.text() == "剪掉结尾 1 条",
          f"红卡片亮了,按钮写几条 -> {tab.b_outro.text()}")

    shown = []

    class _FakeMenu(QMenu):
        def exec(self, *a):
            shown.append([x.text() for x in self.actions()])
    rm, ra = T.QMenu, tab.tree.itemAt
    T.QMenu, tab.tree.itemAt = _FakeMenu, (lambda p: tab.items[i_bad])
    try:
        tab._menu(QPoint(1, 1))
    finally:
        T.QMenu, tab.tree.itemAt = rm, ra
    check("看结尾截图" in shown[0] and "结尾没问题,这条能发" in shown[0], f"右键有截图和放行 -> {shown[0]}")
    tab.set_outro_ok(i_bad, True)
    check(tab._can_send(i_bad) and tab.card_outro.isHidden(), "标成没问题:能发,红卡片收起")
    tab.set_outro_ok(i_bad, False)
    check(not tab._can_send(i_bad) and not tab.card_outro.isHidden(), "改回来:又拦住")

    # OutroDialog 本身微调 & 放行按钮测试
    rel = []
    dlg = OutroDialog([{"row": i_bad, "title": "测试结尾", "account": "CSGO战神君", "path": tab.videos[i_bad].path,
                        "start": 3.45, "dur": 5.0, "kind": "头像求关注", "reason": "圆头像配点赞关注", "shot": str(shot_p)}],
                      on_ok=lambda r: rel.append(r), grab_fn=lambda p, t: im_main if t < 3.45 else im_card)
    _wait(app, lambda: not dlg._cards[0]["p_left"].pixmap().isNull())
    dlg._cards[0]["sp"].setValue(3.2)
    check("剪掉 1.8 秒" in dlg._cards[0]["lab_cut"].text() and dlg.chosen() == [(i_bad, 3.2)],
          f"预览框微调秒数 -> {dlg._cards[0]['lab_cut'].text()} / {dlg.chosen()}")
    dlg._cards[0]["b_ok"].click()
    check(rel == [i_bad] and dlg.chosen() == [] and not dlg.b_go.isEnabled(), "框里点放行:立即触发且不再剪")
    dlg.reject()

    # 真正通过 ApiTab.cut_outro 剪掉
    tab.OUTRO_DIALOG = lambda items, parent: [(items[0]["row"], items[0]["start"])]
    try:
        tab.cut_outro()
        _wait(app, lambda: not tab.busy())
        for _ in range(5):
            app.processEvents()
            time.sleep(0.02)
    finally:
        tab.OUTRO_DIALOG = None
    check(tab._can_send(i_bad) and tab.card_outro.isHidden() and "结尾 已剪" in tab.items[i_bad].text(4),
          f"剪完以后:能发、卡片收起、状态写结尾 已剪 -> {tab.items[i_bad].text(4)}")
    apiacc.save([])

    # 7. 教育 / 影视页(罐头页):教育号也查结尾、拦摆、剪完能摆
    edu_d = tmp / "outro_edu" / "小学生教育" / "10.18" / "研习社" / "小王"
    edu_d.mkdir(parents=True)
    evid = edu_d / "教育条.mp4"
    shutil.copy2(orig_v, evid)
    (edu_d / "教育条.png").write_bytes(b"png")
    st2 = Settings(tmp / "st_outro_edu.json")
    st2["material_root"] = str(tmp / "outro_edu" / "小学生教育")
    st2["ai_key"] = "test"
    w2 = W.MainWindow(st2, Records(tmp / "rec_outro_edu.sqlite"))
    w2.AI_COVER = False
    w2.SHARP_CHECK = False
    ev = F.Video(str(evid), "教育条", "家长研习空间", "小王", "10.18", png=str(edu_d / "教育条.png"),
                 cover=str(edu_d / "教育条.png"), cover_kind="横", cover_why="ok")
    w2.videos = [ev]
    w2.table.setRowCount(1)
    O.check = foutro_tab
    try:
        sw2 = SharpWorker(w2.videos, [0], want_sharp=False, outro_key="k", need_outro=w2._outro_todo)
        sw2.run()
    finally:
        O.check = ro
    w2._fill_row(0)
    w2._outro_button()
    check(W.MainWindow._title_block(ev) == O.TEXT and not w2._todo() and not w2.b_outro.isHidden() and w2.b_outro.text() == "剪掉结尾 1 条",
          f"教育号也查结尾:拦住不摆,按钮写 1 条 -> {w2.b_outro.text()}")
    w2.table.selectRow(0)
    w2.set_outro_ok(True)
    check(W.MainWindow._title_block(ev) == "" and len(w2._todo()) == 1 and w2.b_outro.isHidden(), "教育号右键放行:能摆、按钮收起")
    w2.set_outro_ok(False)
    check(W.MainWindow._title_block(ev) == O.TEXT and not w2.b_outro.isHidden(), "教育号改回来:又拦住")
    w2.OUTRO_DIALOG = lambda items, parent: [(items[0]["row"], items[0]["start"])]
    try:
        w2.cut_outro()
        _wait(app, lambda: not (w2.outro_worker and w2.outro_worker.isRunning()))
        for _ in range(5):
            app.processEvents()
            time.sleep(0.02)
    finally:
        w2.OUTRO_DIALOG = None
    check(W.MainWindow._title_block(ev) == "" and len(w2._todo()) == 1 and w2.b_outro.isHidden()
          and "结尾 已剪" in w2.table.item(0, 5).text(),
          f"教育号剪完:允许摆、按钮收起、写结尾 已剪 -> {w2.table.item(0, 5).text()}")
    w2.close()


def test_bad_cover_fix(tmp: Path):
    print("[黑/模糊封面自动截清晰图 + 设置开关 + 双击去创作罐头搜视频]")
    from unittest import mock
    from PIL import Image
    from PySide6.QtWidgets import QApplication
    from qe import blackcover as B
    from qe.config import DEFAULTS, Settings
    from qe.records import Records
    from qe.folders import Video

    app = QApplication.instance() or QApplication([])
    st = Settings(tmp / "st_badcov.json")
    check(st.get("bad_cover_auto") is True and st.get("bad_cover_dir") == DEFAULTS["bad_cover_dir"],
          f"默认开着自动截清晰封面、目录 {DEFAULTS['bad_cover_dir']}")

    # 造视频文件 + 记录(一条靠 aid 找回、一条靠 账号+标题 找回,即使归档挪走也找得回来)
    arc = tmp / "arc_badcov"
    vid_dir = arc / "11.16" / "平和"
    vid_dir.mkdir(parents=True)
    v1 = vid_dir / "新版本水上飞机：超级！.mp4"
    v2 = vid_dir / "超长标题测试一二三四五六七八九十甲乙丙丁戊己庚辛壬癸.mp4"
    v1.write_bytes(b"v1")
    v2.write_bytes(b"v2")

    rec = Records(tmp / "rec_badcov.sqlite")
    v_obj1 = Video(path=str(tmp / "orig" / "x1.mp4"), title="新版本水上飞机：超级！?", account="和平精英上分君",
                   employee="", date="11.16")
    v_obj2 = Video(path=str(v2), title="超长标题测试一二三四五六七八九十甲乙丙丁戊己庚辛壬癸", account="游研社",
                   employee="", date="11.16")
    rec.manual_published(v_obj1, note="article_id=AID111 vid=V1", at="2026-11-16 18:58:59")
    rec.conn.execute("UPDATE posts SET moved_pkey=? WHERE account=?", (str(v1), "和平精英上分君"))
    rec.conn.commit()
    rec.manual_published(v_obj2, note="手动发", at="2026-11-16 19:00:00")

    sample_jpg = tmp / "sample_pick.jpg"
    Image.new("RGB", (320, 180), (60, 140, 200)).save(sample_jpg)
    picked_calls = []

    def fake_pick(vp, ffmpeg=""):
        picked_calls.append(vp)
        return str(sample_jpg)

    out_dir = tmp / "out_covers"
    st["bad_cover_dir"] = str(out_dir)
    st["bad_cover_auto"] = False
    items_off = [{"nick": "和平精英上分君", "title": "新版本水上飞机：超级！?", "time": "2026-11-16 18:58:59",
                  "url": "http://x/1", "aid": "AID111", "kind": "模糊封面"}]
    check(B.export_covers(items_off, st, rec=rec, pick_fn=fake_pick) == 0 and not out_dir.exists(),
          "设置关着时不截封面、不建输出目录")

    st["bad_cover_auto"] = True
    items_on = [
        {"nick": "和平精英上分君", "title": "新版本水上飞机：超级！?", "time": "2026-11-16 18:58:59",
         "url": "http://x/1", "aid": "AID111", "kind": "模糊封面"},
        {"nick": "游研社", "title": "超长标题测试一二三四五六七八九十甲乙丙丁戊己庚辛壬癸", "time": "2026-11-16 19:00:00",
         "url": "http://x/2", "aid": "", "kind": "模糊封面"},
        {"nick": "和平精英上分君", "title": "找不到原视频的那条", "time": "2026-11-16 19:01:00",
         "url": "http://x/3", "aid": "NOPE", "kind": "黑封面"},
    ]
    got_n = B.export_covers(items_on, st, rec=rec, pick_fn=fake_pick)
    check(got_n == 2 and len(picked_calls) == 2 and os.path.isfile(items_on[0]["cover_file"])
          and os.path.isfile(items_on[1]["cover_file"]) and items_on[2]["cover_file"] == "",
          f"找到 2 个视频截好封面放进指定目录,找不到原视频的不报错 -> {got_n}, {items_on}")
    # 第二次直接复用现成文件,不再重复抽帧
    picked_calls.clear()
    got_n2 = B.export_covers(items_on, st, rec=rec, pick_fn=fake_pick)
    check(got_n2 == 2 and len(picked_calls) == 0, "目录里已有这张封面图时不重复抽帧")
    rec.conn.close()

    check(B.search_keyword("27年春节套爆料了？DNF联动仙剑奇侠传1 #DNF") == "27年春节套爆料了？DNF联动仙剑奇侠传1"
          and B.search_keyword("没有话题的标题") == "没有话题的标题",
          "搜视频标题时去掉末尾 #话题")

    # 模拟创作罐头 CDP:首页点开 → 跳作品管理 → 筛选日期 → 填不带话题的标题点搜索 + 窗口提到前面
    actions = []
    state = {"vis": False, "url": "https://om.qq.com/main"}

    class FakePage:
        def __init__(self, t, timeout=10):
            self.t = t

        def ev(self, js, timeout=20):
            u = self.t.get("url") or ""
            if "usernameText" in js:
                return ["和平精英上分君", 1700 if state["vis"] else 0, state["url"]]
            if "czgts.cn" in u:
                actions.append(("home_ev", js[:30]))
                state["vis"] = True
                return "ok"
            if js.strip() == "innerWidth":
                return 1700 if state["vis"] else 0
            if js.strip() == "location.href":
                return state["url"]
            if "location.href =" in js:
                state["url"] = B.ARTICLE_MANAGE_URL
                return None
            if "dates-cls" in js:
                return {"x": 120, "y": 140}
            if "calMonths" in js:
                return {"status": "found", "x": 220, "y": 260}
            if "panelFooter" in js:
                return {"x": 320, "y": 360}
            if "omui-loading" in js:
                return False
            if "输入标题关键词搜索内容" in js:
                return {"x": 500, "y": 140} if "articleManage" in state["url"] else None
            if "omui-input__search-btn" in js:
                return {"x": 580, "y": 140}
            return None

        def cmd(self, m, params=None, timeout=20):
            actions.append((m, params))

        def click_xy(self, x, y):
            actions.append(("click", x, y))

        def key(self, k, code):
            actions.append(("key", k))

        def close(self):
            pass

    fake_targets = [
        {"id": "h1", "type": "page", "url": "https://www.czgts.cn/v1/home"},
        {"id": "om1", "type": "webview", "url": "https://om.qq.com/main"},
    ]
    brought = []
    msg = B.open_in_czgt(
        "和平精英上分君", "新版本水上飞机 #和平精英", day="2026-11-16",
        find_ports_fn=lambda: [62176],
        targets_fn=lambda _p: fake_targets,
        page_cls=FakePage,
        bring_fn=lambda: brought.append(1) or 1,
        sleep_fn=lambda _s: None,
    )
    check(state["vis"] and state["url"] == B.ARTICLE_MANAGE_URL
          and ("click", 120, 140) in actions and actions.count(("click", 220, 260)) == 2
          and ("click", 320, 360) in actions
          and ("Input.insertText", {"text": "新版本水上飞机"}) in actions
          and ("click", 580, 140) in actions
          and len(brought) >= 2 and "和平精英上分君" in msg and "2026-11-16" in msg,
          f"双击在创作罐头进作品管理→选日期→去话题搜标题并把窗口提前 -> {msg}, actions={actions}")

    # 窗口列状态 + 双击调 open_in_czgt(带日期)
    from gui.black_dialog import BlackDialog
    dlg = BlackDialog("2026-11-16", None, items=items_on, st=st)
    check(dlg.t.columnCount() == 5 and dlg.t.item(0, 4).text() == "已放到文件夹" and dlg.t.item(2, 4).text() == "没找到原视频",
          f"窗口第5列显示新封面状态 -> {[dlg.t.item(i, 4).text() for i in range(3)]}")
    nav_calls = []
    with mock.patch.object(B, "open_in_czgt",
                           side_effect=lambda nk, tt, day="": nav_calls.append((nk, tt, day)) or f"已在创作罐头「{nk}」里搜索「{tt}」"):
        dlg.open_row(0)
        _wait(app, lambda: not (dlg._nav_w and dlg._nav_w.isRunning()))
        for _ in range(5):
            app.processEvents()
            time.sleep(0.02)
    check(nav_calls == [("和平精英上分君", "新版本水上飞机：超级！?", "2026-11-16")],
          f"双击触发去创作罐头按日期搜这条视频 -> {nav_calls}, {dlg.lab_done.text()}")
    dlg.close()


def test_per_account_concurrency(tmp: Path):
    print("[按号独立干活 + 全局最多 3 条重编码防卡死]")
    import threading
    from unittest import mock
    from PySide6.QtWidgets import QApplication, QFileDialog
    import gui.api_tab as T
    from qe import apiacc, checks, omapi, vertical
    from qe.config import Settings
    from qe.records import Records

    app = QApplication.instance() or QApplication([])
    root = tmp / "conc_root"
    for g, n in (("CSGO", "CSGO战神君"), ("PUBG", "PUBG突围君"), ("DNF", "DNF连招档案馆")):
        d = root / "游戏视频" / f"{g}--{n}" / "10.18"
        d.mkdir(parents=True)
        for k in range(4):
            (d / f"{g}{k}.mp4").write_bytes(b"v")
    alt_pubg = tmp / "alt_pubg" / "10.18"
    alt_pubg.mkdir(parents=True)
    (alt_pubg / "新选1 ##旧话题.mp4").write_bytes(b"v2")

    accs = [
        {"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
        {"nick": "PUBG突围君", "source_name": "PUBG", "client_id": "b", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
        {"nick": "DNF连招档案馆", "source_name": "DNF", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
    ]
    apiacc.save(accs)
    st = Settings(tmp / "st_conc.json")
    st["api_roots"] = [str(root / "游戏视频")]
    st["api_archive"] = str(tmp / "conc_arc" / "{date}")
    st["api_interval"] = 0
    st["quota_open"] = True
    rec = Records(tmp / "rec_conc.sqlite")
    logs = []
    tab = T.ApiTab(st, rec, logs.append)
    tab.SHARP_CHECK = False
    tab.COVER_CHECK = False
    tab.set_day("10.18")
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 12)
    for v in tab.videos:
        if v.account in ("CSGO战神君", "DNF连招档案馆"):
            v.checks = {"w": 1920, "h": 1080, "landscape": True, "tags": [], "platform": []}
        else:
            v.checks = {"w": 1080, "h": 1920, "landscape": False, "tags": [], "platform": []}
    tab._update_scope()

    stat = {"cur": 0, "peak": 0, "done_vs": [], "sent": []}
    sl = threading.Lock()
    gate = threading.Event()

    def slow_vert(p, ff, stop=None, keep_orig=False):
        with sl:
            stat["cur"] += 1
            stat["peak"] = max(stat["peak"], stat["cur"])
        gate.wait(2.5)
        with sl:
            stat["cur"] -= 1
            stat["done_vs"].append(p)
        return p, ""

    class FakeCl:
        def __init__(self, *a, **k):
            pass

        def send(self, p, title, cat, before_publish=None, **k):
            if before_publish:
                before_publish("V")
            stat["sent"].append((title, cat))
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}

    csgo_rows = [i for i, v in enumerate(tab.videos) if v.account == "CSGO战神君"]
    dnf_rows = [i for i, v in enumerate(tab.videos) if v.account == "DNF连招档案馆"]
    orig_csgo_vs = [tab.videos[i] for i in csgo_rows]

    with mock.patch.object(vertical, "to_vertical", side_effect=slow_vert), \
         mock.patch.object(checks, "check_one", side_effect=lambda v, *a, **k: v.checks.update({"w": 1080, "h": 1920, "landscape": False})), \
         mock.patch.object(omapi, "Client", FakeCl), \
         mock.patch.object(T, "ask", return_value=True), \
         mock.patch.object(QFileDialog, "getExistingDirectory", return_value=str(alt_pubg)):
        tab.run_vertical(csgo_rows)
        tab.run_vertical(dnf_rows)
        check(tab.busy("CSGO战神君") and tab.busy("DNF连招档案馆") and not tab.busy("PUBG突围君") and tab.b_pick.isEnabled(),
              "CSGO / DNF 转竖屏时:只锁这俩忙号,PUBG 照常空闲且顶部「给号选文件夹」不灰")

        # 1) CSGO 在转竖屏时,给 PUBG 换手选文件夹 → 只重读 PUBG,不影响 CSGO 的 Video 对象与行状态
        tab.pick_folder("PUBG突围君")
        _wait(app, lambda: not tab.busy("PUBG突围君") and any(v.title == "新选1 ##旧话题" for v in tab.videos))
        cur_csgo_vs = [v for v in tab.videos if v.account == "CSGO战神君"]
        check(cur_csgo_vs == orig_csgo_vs, "别的号选完文件夹重刷后,CSGO 正在转竖屏的 Video 对象原样留着")

        # 2) 同时给空闲的 PUBG 整理标题(并触发发布!)
        pubg_rows = [i for i, v in enumerate(tab.videos) if v.account == "PUBG突围君"]
        tab.run_topic(pubg_rows)
        _wait(app, lambda: not tab.busy("PUBG突围君"))
        check(any(v.title == "新选1 #旧话题" for v in tab.videos if v.account == "PUBG突围君"),
              f"CSGO 转竖屏期间,PUBG 照常整理好标题 -> {[v.title for v in tab.videos if v.account == 'PUBG突围君']}")

        pubg_rows = [i for i, v in enumerate(tab.videos) if v.account == "PUBG突围君"]
        tab.run_publish(pubg_rows)
        _wait(app, lambda: not tab.busy("PUBG突围君"), 15)
        check([t for t, _ in stat["sent"]] == ["新选1 #旧话题"],
              f"CSGO 转竖屏还没完,PUBG 已经先发完了 -> {stat['sent']}")

        # 放行 CSGO + DNF 的 8 条转竖屏(确认全局最多同时 3 条)
        gate.set()
        _wait(app, lambda: not tab.busy(), 15)
    for _ in range(5):
        app.processEvents()
        time.sleep(0.02)
    check(1 <= stat["peak"] <= 3 and len(stat["done_vs"]) == 8
          and all(v.checks.get("converted") for v in tab.videos if v.account in ("CSGO战神君", "DNF连招档案馆")),
          f"2 个号同时跑 8 条转竖屏,共用 3 工位上限不超 3 -> peak={stat['peak']}, done={len(stat['done_vs'])}")

    # 3) CSGO 正在发布期间:别的不在发的号(PUBG / DNF)照常能选文件夹、改话题、转竖屏
    pub_gate = threading.Event()
    alt_pubg2 = tmp / "alt_pubg2" / "10.18"
    alt_pubg2.mkdir(parents=True)
    (alt_pubg2 / "发布期间新选 ##话题2.mp4").write_bytes(b"v3")

    class SlowPubCl:
        def __init__(self, *a, **k):
            pass

        def send(self, p, title, cat, before_publish=None, **k):
            if before_publish:
                before_publish("V")
            pub_gate.wait(3.0)
            stat["sent"].append((title, cat))
            return {"vid": "V", "article_id": "A", "transaction_id": "P", "status": "成功"}

    csgo_rows = [i for i, v in enumerate(tab.videos) if v.account == "CSGO战神君"]
    dnf_rows = [i for i, v in enumerate(tab.videos) if v.account == "DNF连招档案馆"]
    for i in dnf_rows:
        tab.videos[i].checks["landscape"] = True
    stat["sent"].clear()
    with mock.patch.object(omapi, "Client", SlowPubCl), \
         mock.patch.object(vertical, "to_vertical", side_effect=lambda p, *a, **k: (p, "")), \
         mock.patch.object(checks, "check_one", side_effect=lambda v, *a, **k: v.checks.update({"w": 1080, "h": 1920, "landscape": False})), \
         mock.patch.object(T, "ask", return_value=True), \
         mock.patch.object(QFileDialog, "getExistingDirectory", return_value=str(alt_pubg2)):
        tab.run_publish(csgo_rows)
        check(tab.busy("CSGO战神君") and not tab.busy("PUBG突围君") and not tab.busy("DNF连招档案馆")
              and tab.b_pick.isEnabled() and tab.b_vert.isEnabled() and tab.b_topic.isEnabled(),
              "CSGO 正在发布时:只锁 CSGO 和防第二批发布,「给号选文件夹 / 转竖屏 / 整理标题」都不灰")
        tab.pick_folder("PUBG突围君")
        _wait(app, lambda: not tab.busy("PUBG突围君") and any(v.title == "发布期间新选 ##话题2" for v in tab.videos))
        pubg_rows = [i for i, v in enumerate(tab.videos) if v.account == "PUBG突围君"]
        tab.run_topic(pubg_rows)
        _wait(app, lambda: not tab.busy("PUBG突围君"))
        check(any(v.title == "发布期间新选 #话题2" for v in tab.videos if v.account == "PUBG突围君"),
              "CSGO 正在发布期间,PUBG 照常选好新文件夹并整理完话题")
        tab.run_vertical([i for i, v in enumerate(tab.videos) if v.account == "DNF连招档案馆"])
        _wait(app, lambda: not tab.busy("DNF连招档案馆"))
        check(all(not v.checks.get("landscape") for v in tab.videos if v.account == "DNF连招档案馆"),
              "CSGO 正在发布期间,DNF 照常转完竖屏")
        pub_gate.set()
        _wait(app, lambda: not tab.busy(), 15)
    check(len(stat["sent"]) == 4, f"期间做完别的事后 CSGO 也正常全发完 -> {len(stat['sent'])}")


def test_title_extra_clean(tmp: Path):
    print("[整理标题/话题:孤立 n / u003eu003c / 联系人署名一并删掉,正常标题不误伤]")
    from types import SimpleNamespace as NS
    from unittest import mock
    from PySide6.QtWidgets import QApplication
    from qe import checks, titleclean as TC, topic
    from qe.config import Settings
    from qe.records import Records
    from gui import api_tab as T
    from gui.api_tab import ApiTab

    cases = [
        ('“姐姐，男性的寿命比女性的寿命短6年，如果想同时离开，要选年下男才行”n',
         '“姐姐，男性的寿命比女性的寿命短6年，如果想同时离开，要选年下男才行”'),
        ('狠起来连自己的醋也要吃 u003eu003c', '狠起来连自己的醋也要吃'),
        ('最新封锁枪械推荐u003c便宜-好用u003e#暗区突围', '最新封锁枪械推荐 便宜-好用 #暗区突围'),
        ('7推年度结算(u003e u003c) 今年的卡面真好看n', '7推年度结算 今年的卡面真好看'),
        ('我想跟你在一起，不想再经历离散 （yc老师：）', '我想跟你在一起，不想再经历离散'),
        ('我想跟你在一起，不想再经历离散 (yc老师：） ', '我想跟你在一起，不想再经历离散'),
        ('狐大侠转场 （ib一滴小鱼泪老师）#光与夜之恋', '狐大侠转场 #光与夜之恋'),
        ('“天命都不曾拦下我” （yc老师 ）#光与夜之恋', '“天命都不曾拦下我” #光与夜之恋'),
        ('“带你180秒回顾陆沉心动历程”n这是最幸福的n n（yc：#光与夜之恋',
         '“带你180秒回顾陆沉心动历程”这是最幸福的 #光与夜之恋'),
        ('我 陆沉 请你做妻子。n nyc：#光与夜之恋', '我 陆沉 请你做妻子。 #光与夜之恋'),
        ('近似圆的东西吗n原创： n', '近似圆的东西吗'),
        ('打法。n#三角洲行动', '打法。#三角洲行动'),
        ('今天好开心n n n', '今天好开心'),
        ('好喜欢n所以还是画了n', '好喜欢所以还是画了'),
    ]
    for src, want in cases:
        got = TC.clean(src)
        check(got == want and TC.dirty(src), f"clean({src!r}) -> {got!r} (want {want!r}, dirty={TC.dirty(src)})")

    keeps = [
        '说出你最好的朋友的名字（陆沉免答）',
        '(扶额）简直是荒谬',
        '三角洲画面参数n卡滤镜分享#三角洲行动',
        '重刷第n次动漫#青春之旅',
        '熬了n个大夜写代码',
        '【沧元图第101集预告逐帧解析来了：】 孟川',
        '【本人投稿】',
        'iPhone16ProMax评测 #数码',
        'Join#话题',
    ]
    for src in keeps:
        check(TC.clean(src) is None and not TC.dirty(src), f"不误伤({src!r}) -> clean={TC.clean(src)!r}, dirty={TC.dirty(src)}")

    # checks.problems 标红且只报要删,不乱报话题写法不对
    v_n = NS(title='我想跟你在一起（yc老师：）#光与夜之恋', checks={"w": 1080, "h": 1920, "tags": ["光与夜之恋"], "platform": []}, account="PUBG突围君")
    ps = checks.problems(v_n)
    check(any("（yc老师：）" in p and "整理标题" in p for p in ps) and "话题写法不对" not in ps,
          f"problems 只提示要删联系人 -> {ps}")

    # 批量改话题 & AI 挑话题一并清理
    check(topic.with_topic('“要选年下男才行”n', '光与夜之恋') == '“要选年下男才行”#光与夜之恋'
          and topic.with_topic('狠起来连自己的醋也要吃 u003eu003c', '光与夜之恋') == '狠起来连自己的醋也要吃#光与夜之恋'
          and topic.with_topic('我想跟你在一起 （yc老师：）', '光与夜之恋') == '我想跟你在一起#光与夜之恋',
          "批量改话题一并删掉孤立 n / 转义串 / 联系人")
    check(topic.new_name('吃醋 u003eu003c #日常 #光与夜之恋', lambda b, t: t[1]) == '吃醋 #光与夜之恋',
          "AI 挑话题同时清掉转义串")

    # 界面端到端:tidy_titles(只整理写法不用 AI)都能改文件+同名封面
    app = QApplication.instance() or QApplication([])
    from qe import apiacc
    from qe.config import bj_now
    n0 = bj_now()
    md = f"{n0.month}.{n0.day}"
    r_ec = tmp / "root_ec"
    fd = r_ec / "游戏视频" / "PUBG--PUBG突围君" / md
    fd.mkdir(parents=True)
    names = [
        '狠起来连自己的醋也要吃 u003eu003c',
        '我想跟你在一起 (yc老师：）',
        '“想同时离开，要选年下男才行”n',
    ]
    for nm in names:
        (fd / f"{nm}.mp4").write_bytes(b"v")
        (fd / f"{nm}.jpg").write_bytes(b"c")
    st = Settings(tmp / "s_ec.json")
    st["api_roots"] = [str(r_ec / "游戏视频")]
    apiacc.save([{"nick": "PUBG突围君", "source_name": "PUBG", "client_id": "1", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    tab = ApiTab(st, Records(tmp / "r_ec.sqlite"), lambda *a: None)
    tab.AUTO_UNSURE = False
    tab.SHARP_CHECK = False
    tab.COVER_CHECK = False
    tab.set_day(md)
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 3)
    for v in tab.videos:
        v.checks = {"w": 1080, "h": 1920, "landscape": False, "tags": [], "platform": []}
    with mock.patch.object(T, "ask", return_value=True):
        tab.tidy_titles(list(range(len(tab.videos))))
    stems = sorted(os.path.splitext(f)[0] for f in os.listdir(fd) if f.endswith(".mp4"))
    covers = sorted(os.path.splitext(f)[0] for f in os.listdir(fd) if f.endswith(".jpg"))
    want_stems = sorted([
        '狠起来连自己的醋也要吃',
        '我想跟你在一起',
        '“想同时离开，要选年下男才行”',
    ])
    check(stems == want_stems and covers == want_stems and all(not checks.problems(v) for v in tab.videos if v.checks),
          f"整理写法一键清掉视频+同名封面 -> {stems}")
    apiacc.save([])


def test_verify_web_and_lag(tmp: Path):
    print("[去企鹅号核对:OpenAPI 延迟不误打勾 + 开着罐头直读实时列表]")
    from datetime import timedelta
    from unittest import mock
    from qe import cdp, folders as F, verify
    from qe.config import bj_now
    from qe.records import Records
    now = bj_now()
    day = now.strftime("%Y-%m-%d")
    yday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    rec = Records(tmp / "r_vlag.sqlite")
    d = tmp / "vlag_src"
    d.mkdir()
    for t in ("刚发1", "刚发2", "其实漏了"):
        p = d / f"{t}.mp4"
        p.write_bytes(b"v")
        rec.manual_published(F.Video(path=str(p), title=t, account="家长小天地", employee="小王", date=f"{now.month}.{now.day}"))

    class LagCl:
        def list_articles(self, page=1, limit=10):
            # 模拟企鹅号 OpenAPI 列表延迟:只同步到昨天,今天的还没进接口列表
            return {"articles": [{"article_title": "昨天的", "article_pub_time": f"{yday} 18:00:00",
                                  "article_pub_flag": "发布成功"}] if page == 1 else [], "total": 1}

        def article_info(self, aid):
            return {}

    r_lag = verify.check_edu(LagCl(), rec, "家长小天地", day)
    check(r_lag.get("lag") and len(r_lag["missing"]) == 3 and all(m["sure"] is False for m in r_lag["missing"]),
          f"OpenAPI 刚发不久没同步到时:绝不自动打勾(不误拎回重发) -> {r_lag}")

    # 模拟创作罐头正登着「家长小天地」,直接读 /marticle/article/list 实时结果
    class FakePg:
        def __init__(self, target, timeout=20):
            self.n = target["nick"]

        def ev(self, js, timeout=20):
            if "querySelector" in js:
                return self.n
            if "index=1" in js:
                return {"response": {"code": "0"}, "data": {"articles": [
                    {"article_id": "A1", "title": "刚发1", "status": "1", "v_status": "2", "del_flag": 0, "pub_time": f"{day} 18:10:00"},
                    {"article_id": "A2", "title": "刚发2", "status": "1", "v_status": "2", "del_flag": 0, "pub_time": f"{day} 18:10:01"},
                ]}}
            return {"response": {"code": "0"}, "data": {"articles": []}}

        def close(self):
            pass

    with mock.patch.object(verify, "_can_web", return_value=True), \
         mock.patch.object(cdp, "find_ports", return_value=[62176]), \
         mock.patch.object(cdp, "targets", return_value=[{"type": "webview", "url": "https://om.qq.com/main", "nick": "家长小天地"}]), \
         mock.patch.object(cdp, "Page", FakePg):
        r_web = verify.check_edu(LagCl(), rec, "家长小天地", day)
    check(r_web.get("source") == "web" and r_web["live"] == 2 and len(r_web["missing"]) == 1
          and r_web["missing"][0]["title"] == "其实漏了" and r_web["missing"][0]["sure"] is True,
          f"开着罐头直读实时网页列表:2 条已发对上,只勾真漏掉的 1 条 -> {r_web}")


def test_black_cover_v2(tmp: Path):
    print("[黑/模糊封面优化:底栏黄字黑屏、顶模糊+底工具栏、处理中不误算读不出]")
    import io
    from PIL import Image, ImageDraw, ImageFilter
    from qe import blackcover as B

    # 1. 上面 75%+ 全黑、只剩最底下一条亮黄色字幕块(11-17 DNF「加载中」那种) -> 算黑封面
    blk_bar = Image.new("RGB", (640, 360), "black")
    ImageDraw.Draw(blk_bar).rectangle([200, 315, 440, 355], fill=(250, 220, 40))
    check(B.is_black_img(blk_bar), "顶上全黑只剩底下黄条字幕:算黑封面")

    # 2. 上面 85% 全糊(只有暗场/糊景),仅最底一行有锐利游戏底栏文字 -> 避开最底一行后依然判成模糊封面
    base = Image.new("RGB", (640, 360), (52, 58, 76))
    db = ImageDraw.Draw(base)
    db.rectangle([40, 20, 600, 260], fill=(74, 80, 102))
    blur_hud = base.filter(ImageFilter.GaussianBlur(12))
    dh = ImageDraw.Draw(blur_hud)
    for x in range(20, 620, 28):
        dh.rectangle([x, 316, x + 16, 352], fill=(240, 210, 60), outline=(0, 0, 0), width=2)
    check(B.is_blurry_img(blur_hud) and B.bad_kind_img(blur_hud) == "模糊封面",
          f"顶80%全糊但底下一行游戏UI很锐利:依然判成模糊封面 -> {B.block_sharpness(blur_hud):.1f}")

    # 3. 平台还在「处理中」(flag=10) 没出封面图 -> 记成 pending,不算 bad(读不出来)
    class Cl:
        def list_articles(self, page, limit):
            return {"total": 2, "articles": [] if page > 1 else [
                {"article_id": "P1", "article_title": "处理中那条", "article_imgurl": "", "article_del_flag": "正常",
                 "article_pub_time": "2026-11-17 19:00:00", "article_pub_flag": "10", "article_video_info": {"vid": "v1"}},
                {"article_id": "P2", "article_title": "糊图", "article_imgurl": "u_blur", "article_del_flag": "正常",
                 "article_pub_time": "2026-11-17 19:01:00", "article_pub_flag": "发布成功", "article_video_info": {"vid": "v2"}},
            ]}

    buf = io.BytesIO()
    blur_hud.save(buf, "JPEG")
    st_info = {}
    got, bad = B.scan_one({"nick": "甲"}, "2026-11-17", "2026-11-17", make_client=lambda a: Cl(),
                          fetch=lambda u: buf.getvalue(), stats=st_info)
    check(len(got) == 1 and got[0]["title"] == "糊图" and bad == 0 and st_info.get("pending") == 1,
          f"处理中(10)没图不算读不出,记在 pending -> got={got}, bad={bad}, st_info={st_info}")


def test_portable_bundle(tmp: Path):
    print("\n[打包便携数据:优先读同目录「数据」、跨电脑账号钥匙、迁移后截图兜底]")
    from qe import apiacc, config as cfg, wmstore
    old_env = os.environ.get("QE_DATA_DIR")
    old_app = cfg.app_dir
    app_fake = tmp / "fake_app"
    app_fake.mkdir()
    port_dir = app_fake / "数据"
    try:
        # 1. data_dir: 未设 QE_DATA_DIR 时,旁边有「数据」目录就优先用它;QE_DATA_DIR 优先级更高
        os.environ.pop("QE_DATA_DIR", None)
        cfg.app_dir = lambda: app_fake
        check(cfg.data_dir() != port_dir, "旁边还没有「数据」目录时不用它")
        port_dir.mkdir()
        check(cfg.data_dir() == port_dir, "旁边有「数据」目录时直接用同目录数据")
        os.environ["QE_DATA_DIR"] = str(tmp / "override_dir")
        check(cfg.data_dir() == tmp / "override_dir", "QE_DATA_DIR 依然优先")

        # 2. PORT1 跨电脑加密与防篡改校验
        os.environ["QE_DATA_DIR"] = str(port_dir)
        dpapi_s = apiacc.seal("orig_dpapi_sec")
        check(not dpapi_s.startswith("PORT1:") and apiacc.unseal(dpapi_s) == "orig_dpapi_sec",
              "没有 .迁移钥匙 时保持原有 DPAPI 加密")
        p_sec = apiacc.seal_portable("跨电脑密钥_xyz_123")
        check(p_sec.startswith("PORT1:") and "跨电脑密钥" not in p_sec and apiacc.unseal(p_sec) == "跨电脑密钥_xyz_123",
              "seal_portable 生成 PORT1 且正常解出")
        # 已有 .迁移钥匙 后,新保存的钥匙也自动沿用便携格式
        apiacc.save([{"nick": "测试号", "client_id": "cid1", "secret": p_sec, "enabled": True}])
        check(apiacc.set_key("测试号", "cid1", "新换密钥_999")
              and apiacc.find("测试号")["secret"].startswith("PORT1:")
              and apiacc.unseal(apiacc.find("测试号")["secret"]) == "新换密钥_999",
              "有 .迁移钥匙 时 set_key 也用 PORT1 保持便携")
        # 篡改密文或丢了钥匙要明确报错
        bad_blob = bytearray(p_sec.encode("ascii"))
        bad_blob[-2] = ord("A" if bad_blob[-2] != ord("A") else "B")
        tampered_err = False
        try:
            apiacc.unseal(bytes(bad_blob).decode("ascii"))
        except OSError:
            tampered_err = True
        check(tampered_err, "密文被改后 PORT1 校验失败并报错")

        # 3. 迁移后的旧绝对路径截图(如 C:\\Users\\1\\...\\结尾截图\\x.jpg)自动改找当前 data_dir
        shot_dir = port_dir / "结尾截图"
        shot_dir.mkdir(exist_ok=True)
        (shot_dir / "abc123.jpg").write_bytes(b"jpg")
        st_o = wmstore.Store("结尾检查_test.json")
        vpath = str(tmp / "v1.mp4")
        Path(vpath).write_bytes(b"vid")
        st_o.put(vpath, {"hits": [{"start": 1.0}], "shot": r"C:\Users\old_pc\AppData\Local\企鹅号发布助手\结尾截图\abc123.jpg"})
        got_o = st_o.get(vpath)
        check(got_o and os.path.normpath(got_o["shot"]) == os.path.normpath(str(shot_dir / "abc123.jpg")),
              f"旧电脑绝对路径结尾截图自动切到新数据目录 -> {got_o}")
    finally:
        cfg.app_dir = old_app
        if old_env is None:
            os.environ.pop("QE_DATA_DIR", None)
        else:
            os.environ["QE_DATA_DIR"] = old_env


def test_lan_sync(tmp: Path):
    print("\n[两台电脑局域网互通(方案 B):记录实时同步、防重发、双机额度闸、缓存/放行互通、断主机拦阻、旧账合并]")
    from types import SimpleNamespace
    from qe import adjust, apiacc, config as cfg, dimcache, gamecheck, lansync, plan, titledate, wmstore
    from qe.records import Records
    old_env = os.environ.get("QE_DATA_DIR")
    host_dir = tmp / "lan_host"
    cli_dir = tmp / "lan_cli"
    host_dir.mkdir()
    cli_dir.mkdir()
    try:
        # 1. 初始化主机目录(端口 0 让系统分配空闲口),预先放好一条已发和设置
        os.environ["QE_DATA_DIR"] = str(host_dir)
        st_h = cfg.Settings(host_dir / "设置.json")
        st_h.update(lan_role="host", lan_port=0, lan_token="482910", theme="深色",
                    schedules=["host_only_sched"],
                    daily_plan={"CSGO战神君": 2},
                    quota_extra={"2026-11-17": {"CSGO战神君": 1}},
                    own_ai_url="http://127.0.0.1:8788/v1",
                    api_picked={"11.17": {"电竞情报馆": "X:/old_pick"}})
        st_h.save()
        apiacc.save([{"nick": "CSGO战神君", "client_id": "cidA", "secret": apiacc.seal("secA"), "category": 1604, "enabled": True}])
        adj_h = adjust.Adjustments(host_dir / "封面调整.json")
        rec_h = lansync.setup(st_h, adj=adj_h)
        h = lansync.active_host()
        check(h is not None and h.bound_port > 0, f"主机服务启起来 -> port={getattr(h, 'bound_port', 0)}")
        port = h.bound_port

        # 错误配对码被拒绝
        bad_pin = False
        try:
            lansync.test_connection(f"127.0.0.1:{port}", "000000")
        except lansync.LanError:
            bad_pin = True
        check(bad_pin, "配对码不对时主机拒绝连接")
        ping_ok = lansync.test_connection(f"127.0.0.1:{port}", "482910")
        check(ping_ok.get("ok") is True, f"正确配对码 ping 通 -> {ping_ok}")

        # 2. 主机先发一条视频 A (验证 db_rev 从 0 -> 1 也能增量同步!)
        va = SimpleNamespace(date="11.18", account="CSGO战神君", employee="接口", title="视频A", path=str(tmp / "a.mp4"), cover_kind="")
        Path(va.path).write_bytes(b"va")
        rid_a = rec_h.try_begin(va, "vid=A1")
        rec_h.api_finish(rid_a, "已发", "article_id=AA1 vid=A1")

        # 3. 初始化从机(本地旧库先带 1 条重复的 va + 1 条未并入的 vd;注意从机有自己的 PORT1 钥匙 & schedules)
        os.environ["QE_DATA_DIR"] = str(cli_dir)
        apiacc.seal_portable("init_key")
        st_c = cfg.Settings(cli_dir / "设置.json")
        st_c.update(lan_role="client", lan_host=f"127.0.0.1:{port}", lan_token="482910",
                    theme="浅色", schedules=["cli_only_sched"])
        st_c.save()
        vd = SimpleNamespace(date="11.18", account="CSGO战神君", employee="接口", title="视频D", path=str(tmp / "d.mp4"), cover_kind="")
        Path(vd.path).write_bytes(b"vd")
        old_cli_rec = Records(cli_dir / "发布记录.sqlite")
        old_cli_rec.api_result(va, "已发", "重复的旧账")
        old_cli_rec.api_result(vd, "已发", "只有新机发过的旧账")
        old_cli_rec.close()

        # 切换到从机实例(直接让 Host 保持在线程里;只换 client env 运行 RemoteRecords/LanClient)
        # 因为 _HOST 与 _BOUND_DATA 绑定的是 host_dir,测试里用 LanClient + RemoteRecords 直接模拟第二台进程
        from qe.records import RemoteRecords
        cli = lansync.LanClient(f"127.0.0.1:{port}", "482910", st_c)
        rrec = RemoteRecords(cli, cli_dir / "发布记录_主机镜像.sqlite")
        cli.rec = rrec
        # 在 cli_dir 测试过程中暂时把 lansync._CLIENT 指过去(测试结束停掉)
        with lansync._REG_LOCK:
            old_host_ref, old_cli_ref, old_bdata = lansync._HOST, lansync._CLIENT, lansync._BOUND_DATA
            lansync._CLIENT = cli
            lansync._BOUND_DATA = str(cli_dir)
        try:
            cli.sync_poll(strict=True)
            check(rrec.status_of(va.path) == "已发" and rrec.sent_on(plan.today()).get("CSGO战神君") == 1,
                  f"从机首次同步就看见主机发过的视频A与今日已发=1 -> {rrec.sent_on(plan.today())}")
            check(st_c.get("theme") == "浅色" and st_c.get("schedules") == ["cli_only_sched"]
                  and st_c.get("daily_plan") == {"CSGO战神君": 2}
                  and not st_c.get("api_picked") and not st_c.get("own_ai_url"),
                  f"从机拉回主机规定条数但保留自己的皮肤/定时,且不拉主机的盘符手选和本机模型 -> {st_c.get('daily_plan')} / {st_c.get('api_picked')} / {st_c.get('own_ai_url')}")
            # 账号密钥也通过局域网密文同步成从机 PORT1 可解
            c_accs = apiacc.load()
            check(len(c_accs) == 1 and c_accs[0]["secret"].startswith("PORT1:") and apiacc.unseal(c_accs[0]["secret"]) == "secA",
                  "账号钥匙从主机密文同步到从机并转成便携 PORT1 解出正确")

            # 防重发:从机想再发视频 A -> try_begin 返回 None
            check(rrec.try_begin(va, "vid=A_dup") is None, "主机发过的视频A,从机 try_begin 原子拦住不重发")

            # 从机发视频 B -> 主机立刻看见,今日总账 = 2
            vb = SimpleNamespace(date="11.18", account="CSGO战神君", employee="接口", title="视频B", path=str(tmp / "b.mp4"), cover_kind="")
            Path(vb.path).write_bytes(b"vb")
            rid_b = rrec.try_begin(vb, "vid=B1", day=plan.today(), cap=2)
            check(isinstance(rid_b, int) and rid_b > 0, f"从机领到视频B发送权 -> rid={rid_b}")
            rrec.api_finish(rid_b, "已发", "article_id=BB1 vid=B1")
            check(rec_h.status_of(vb.path) == "已发" and rec_h.sent_on(plan.today()).get("CSGO战神君") == 2,
                  f"从机发完视频B,主机立刻记上(总计2条) -> {rec_h.sent_on(plan.today())}")

            # 规定条数 cap=2 已满 -> 视频C(不管主机还是从机)返回 -1
            vc = SimpleNamespace(date="11.18", account="CSGO战神君", employee="接口", title="视频C", path=str(tmp / "c.mp4"), cover_kind="")
            Path(vc.path).write_bytes(b"vc")
            check(rrec.try_begin(vc, "vid=C1", day=plan.today(), cap=2) == -1, "双机合计达规定上限 2,从机拦截返回 -1")

            # 检查缓存与截图互传(outro + screenshot + gamecheck + titledate + settings api_picked merge)
            cshot = cli_dir / "结尾截图" / "shot_cli.jpg"
            cshot.parent.mkdir(parents=True, exist_ok=True)
            cshot.write_bytes(b"JPEG_SHOT_DATA")
            wmstore.OUTRO.put(vb.path, {"hits": [{"start": 2.0}], "shot": str(cshot)})
            gamecheck.store().set_ok("CSGO战神君", "视频B", True)
            titledate.store().set("CSGO战神君", "视频B", True)
            st_c["api_picked"] = {"11.18": {"电竞情报馆": "Z:/cli_1118"}}
            st_c["own_ai_url"] = "http://127.0.0.1:9999/v1"
            st_c["quota_extra"] = {"2026-11-18": {"CSGO战神君": 3}}
            st_c.save()
            check(st_h.get("quota_extra") == {"2026-11-17": {"CSGO战神君": 1}, "2026-11-18": {"CSGO战神君": 3}}
                  and st_h.get("api_picked") == {"11.17": {"电竞情报馆": "X:/old_pick"}}
                  and st_h.get("own_ai_url") == "http://127.0.0.1:8788/v1"
                  and st_h.get("schedules") == ["host_only_sched"],
                  f"从机临时加量温和合并进主机;两台盘符手选/本机模型/定时各自独立不互冲 -> {st_h.get('quota_extra')} / {st_h.get('api_picked')} / {st_h.get('own_ai_url')}")

            # 切换到主机 env 验证主机真收到了检查结果与截图文件
            os.environ["QE_DATA_DIR"] = str(host_dir)
            with lansync._REG_LOCK:
                lansync._CLIENT = None
                lansync._HOST = h
                lansync._BOUND_DATA = str(host_dir)
            wmstore.OUTRO.reload()
            got_outro = wmstore.OUTRO.get(vb.path)
            check(bool(got_outro and got_outro["hits"] and os.path.isfile(got_outro["shot"])),
                  f"从机上传的结尾截图与缓存同步进了主机 -> {got_outro}")
            check(gamecheck.store().ok("CSGO战神君", "视频B") and titledate.store().ok("CSGO战神君", "视频B"),
                  "从机点的串游戏/标题日期放行同步进主机")

            # 把从机旧库里没并入的 vd 合并进主机(a 已在前端去重过滤, 只发送 d 并入)
            os.environ["QE_DATA_DIR"] = str(cli_dir)
            with lansync._REG_LOCK:
                lansync._CLIENT = cli
                lansync._BOUND_DATA = str(cli_dir)
            unm = lansync.unmerged_local_rows(cli)
            m_cnt, s_cnt = lansync.merge_local_to_host(cli)
            check(len(unm) == 1 and (m_cnt, s_cnt) == (1, 0) and rec_h.status_of(vd.path) == "已发",
                  f"旧账去重合并:筛出 1 条未同步、并入 1 条 -> unm={len(unm)} {(m_cnt, s_cnt)}")

            # 主机离线(关停):从机所有写操作和 try_begin 必须抛 LanError 拦住,绝不悄悄写入本地
            h.stop()
            offline_blocked = False
            try:
                rrec.try_begin(vc, "vid=C_off")
            except lansync.LanError:
                offline_blocked = True
            check(offline_blocked, "主机关掉/离线时,从机 try_begin 明确报 LanError 拦住,绝不各自乱发")
        finally:
            rrec.close()
            cli.close()
            h.stop()
            rec_h.close()
            with lansync._REG_LOCK:
                lansync._HOST = old_host_ref
                lansync._CLIENT = old_cli_ref
                lansync._BOUND_DATA = old_bdata
    finally:
        lansync.stop()
        if old_env is None:
            os.environ.pop("QE_DATA_DIR", None)
        else:
            os.environ["QE_DATA_DIR"] = old_env


def test_audiocheck(tmp: Path):
    print("\n[发布前查有没有声音(用户 2026-11-21):无音轨零开销 / 静音抽3段提前退出 / 只提醒不拦 / 两页都能放行 / 局域网同步]")
    import subprocess
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from qe import apiacc, audiocheck as A, checkline as L, folders as F, lansync, vertical, wmstore
    from qe.config import Settings
    from qe.records import Records
    from gui.sharp_worker import SharpWorker
    import gui.api_tab as T
    import gui.window as W

    # 1. 单元测试:无音轨直出、第一段有声提前退出、三段全静音、中间静音但前段有声不误报、读不出抛异常
    seen = []
    r0 = A.check("x", "", dur=120, has_audio=False, measure=lambda s, w: seen.append((s, w)) or ("ok", -10.0))
    check(r0 == {"hits": [{"kind": "none"}]} and not seen, f"无音轨直出不调 ffmpeg -> {r0} / {seen}")
    check(A.flagged(r0) and A.text(r0) == "没有声音(无音轨)", f"无音轨文案 -> {A.text(r0)}")

    seen.clear()
    r1 = A.check("x", "", dur=120, has_audio=True, measure=lambda s, w: seen.append((s, w)) or ("ok", -15.0))
    check(r1 == {"hits": []} and len(seen) == 1 and seen[0][0] == 60.0, f"正常视频第一段(50%)就提前退出 -> {r1} / {seen}")

    seen.clear()
    dbs = iter([-62.0, -58.5, -91.0])
    r2 = A.check("x", "", dur=120, has_audio=True, measure=lambda s, w: seen.append((s, w)) or ("ok", next(dbs)))
    check(len(seen) == 3 and r2 == {"hits": [{"kind": "silent", "max_db": -58.5}]} and A.text(r2) == "疑似无声", f"三段全静音 -> {r2} / {seen}")

    seen.clear()
    dbs2 = iter([-80.0, -12.0, -90.0])
    r3 = A.check("x", "", dur=120, has_audio=True, measure=lambda s, w: seen.append((s, w)) or ("ok", next(dbs2)))
    check(r3 == {"hits": []} and len(seen) == 2, f"中间静音但 15% 有声音:不误报 -> {r3} / {seen}")

    seen.clear()
    A.check("x", "", dur=12, has_audio=True, measure=lambda s, w: seen.append((s, w)) or ("ok", -80.0))
    check(seen == [(0.0, A.SHORT_DUR)], f"短视频 <=24s 只量 1 段 -> {seen}")

    err = False
    try:
        A.check("x", "", dur=10, measure=lambda s, w: ("err", None))
    except OSError:
        err = True
    check(err, "读不出音频抛 OSError,不误记成没问题")

    # 2. 真实 ffmpeg 造 4 种极端文件验证 probe.has_audio + audiocheck.check
    ff = vertical.ffmpeg_path()
    if ff:
        NOWIN = 0x08000000 if os.name == "nt" else 0
        ad = tmp / "aud_real"
        ad.mkdir(parents=True)
        p_no, p_sil, p_ok, p_bad = ad / "无音轨.mp4", ad / "静音.mp4", ad / "有声.mp4", ad / "坏的.mp4"
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x160:d=2",
                        "-c:v", "libx264", "-t", "2", str(p_no)], check=True, creationflags=NOWIN)
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x160:d=2",
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-c:v", "libx264", "-c:a", "aac", "-shortest", "-t", "2", str(p_sil)],
                       check=True, creationflags=NOWIN)
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x160:d=2",
                        "-f", "lavfi", "-i", "sine=f=440:d=2", "-c:v", "libx264", "-c:a", "aac", "-shortest", "-t", "2", str(p_ok)],
                       check=True, creationflags=NOWIN)
        p_bad.write_bytes(b"123")
        check(vertical.probe(str(p_no), ff).get("has_audio") is False, "probe:无音轨 has_audio=False")
        check(vertical.probe(str(p_sil), ff).get("has_audio") is True, "probe:静音有音轨 has_audio=True")
        check(vertical.probe(str(p_ok), ff).get("has_audio") is True, "probe:正常视频 has_audio=True")
        check(vertical.probe(str(p_bad), ff).get("has_audio") is None, "probe:坏文件 has_audio=None")
        check(A.check(str(p_no), ff, dur=2)["hits"][0]["kind"] == "none", "真 ffmpeg:无音轨识别成 none")
        check(A.check(str(p_sil), ff, dur=2)["hits"][0]["kind"] == "silent", "真 ffmpeg:静音轨识别成 silent")
        check(A.check(str(p_ok), ff, dur=2)["hits"] == [], "真 ffmpeg:正常音频不误报")
        bad_err = False
        try:
            A.check(str(p_bad), ff, dur=2)
        except OSError:
            bad_err = True
        check(bad_err, "真 ffmpeg:坏文件抛 OSError")

    # 3. 局域网同步注册 + checkline 4 项
    check("audio" in lansync.STORE_FILES and "audio_check" in lansync.SHARED_SETTING_KEYS and wmstore.by_key("audio") is A.STORE,
          "音频检查仓库和开关已接入局域网同步")
    check(L.cell((L.OK, L.OK, L.OK, L.BAD)) == "清晰 ✓  字幕 ✓  结尾 ✓  无声音"
          and L.found([(L.OK, L.OK, L.OK, L.BAD)]) == "1 条无声"
          and "声音 1 条" in L.unchecked_text([(L.OK, L.OK, L.OK, L.TODO)]), "checkline 第 4 项声音展示正常")

    # 4. SharpWorker + ApiTab + MainWindow:只提醒不拦发布,右键放行生效
    d = tmp / "aud_ui" / "游戏视频" / "CSGO--CSGO战神君" / "10.18"
    d.mkdir(parents=True)
    for n, b in (("无声片", b"11"), ("有声片", b"22")):
        (d / f"{n}.mp4").write_bytes(b)
    vs = [SimpleNamespace(path=str(d / "无声片.mp4"), checks={"dur": 10, "has_audio": False}),
          SimpleNamespace(path=str(d / "有声片.mp4"), checks={"dur": 10, "has_audio": True})]
    ra = A.check
    A.check = lambda p, ff, dur=0.0, has_audio=None, stop=None, measure=None: {"hits": [{"kind": "none"}]} if has_audio is False else {"hits": []}
    try:
        w = SharpWorker(vs, [0, 1], want_sharp=False, want_audio=True)
        w.run()
        check(w.n_audio == 1 and A.flagged(vs[0].audio) and not A.flagged(vs[1].audio), "SharpWorker 查声音并缓存")
        apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
        st = Settings(tmp / "st_aud.json")
        st["api_roots"] = [str(tmp / "aud_ui" / "游戏视频")]
        tab = T.ApiTab(st, Records(tmp / "rec_aud.sqlite"), lambda m: None)
        tab.c_date.setCurrentIndex(tab.c_date.findData("10.18"))
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)
        i = next(k for k, v in enumerate(tab.videos) if v.title == "无声片")
        tab.videos[i].checks = dict(tab.videos[i].checks or {}, bad_read=False, landscape=False, squarish=False, w=1080, h=1920, platform=[], tags=[])
        tab.videos[i].audio = A.STORE.get(tab.videos[i].path)
        tab._fill(i)
        st_, probs = tab._status_text(i)
        check("没有声音(无音轨)" in tab.items[i].text(2) and st_.startswith("能发") and not probs and "无声音" in tab.items[i].text(4),
              f"16个号页:备注与检查列提醒,状态依然能发(不拦) -> {tab.items[i].text(2)} / {st_} / {tab.items[i].text(4)}")
        tab.set_audio_ok(i)
        check("没有声音" not in tab.items[i].text(2) and "声音 放行" in tab.items[i].text(4),
              f"16个号页:点「声音没问题」后放行 -> {tab.items[i].text(2)} / {tab.items[i].text(4)}")
        tab.close()

        # 教育/影视页
        A.STORE.set_ok(vs[0].path, False)
        st2 = Settings(tmp / "st_aud2.json")
        w2 = W.MainWindow(st2, Records(tmp / "rec_aud2.sqlite"))
        w2.AI_COVER = False
        w2.videos = [F.Video(vs[0].path, "无声片", "研习社", "e", "10.18")]
        w2.videos[0].audio = A.STORE.get(vs[0].path)
        w2.table.setRowCount(1)
        w2._fill_row(0)
        check("没有声音(无音轨)" in w2.table.item(0, 4).text() and not w2.videos[0].skip,
              f"罐头页:状态列提醒且不设 skip(不拦) -> {w2.table.item(0, 4).text()}")
        w2.table.selectRow(0)
        w2.set_audio_ok()
        check(w2.table.item(0, 4).text() == "还没发" and "声音 放行" in w2.table.item(0, 5).text(),
              f"罐头页:右键「声音没问题」后放行 -> {w2.table.item(0, 4).text()} / {w2.table.item(0, 5).text()}")
        w2.close()
    finally:
        A.check = ra
        apiacc.save([])


def test_cover_sync_and_no_ai(tmp: Path):
    print("[封面 9:16/3:4/1:1 同步调整 + 彻底去掉 AI 看封面/扩图]")
    from PySide6.QtWidgets import QApplication
    from gui.cover_dialog import CoverDialog
    import gui.window as W
    from qe import cover as C
    from qe.adjust import Adjustments
    from qe.config import Settings
    from qe.folders import Video
    from qe.records import Records
    app = QApplication.instance() or QApplication([])
    d = tmp / "cov_sync"
    d.mkdir()
    _img(d / "a.png", 1600, 900)
    (d / "a.mp4").write_bytes(b"x")
    adj = Adjustments(tmp / "adj_sync.json")
    v = Video(path=str(d / "a.mp4"), title="a", account="号", employee="员", date="11.26", png=str(d / "a.png"))
    C.decide(v)
    adj.apply(v)
    dlg = CoverDialog([v], 0, adj)
    check(hasattr(dlg, "k_sync") and dlg.k_sync.isChecked(), "默认勾选「同步调整 (9:16 / 3:4 / 1:1)」")
    check(not hasattr(dlg, "b_ai") and not hasattr(dlg, "b_again"), "已移除 2.35:1 AI 扩图按钮")

    def _drag_to(cx_norm: float):
        _x, y, w, h = dlg.canvas.rect_img
        pw = dlg.canvas.pm.width()
        dlg.canvas.rect_img = (max(0.0, min(pw - w, cx_norm * pw - w / 2)), y, w, h)
        dlg._dragged()

    # 切到 9:16 拖动 -> 3:4、1:1 同步更新,2.35:1 不受影响
    dlg.pick_ratio(1)
    _drag_to(0.72)
    man = v.plan.get("manual") or {}
    k916, k34, k11, k235 = C.rkey(9 / 16), C.rkey(3 / 4), C.rkey(1.0), C.rkey(2.35)
    check(abs(man.get(k916, [0])[0] - 0.72) < 0.01 and man.get(k34) == man.get(k916) and man.get(k11) == man.get(k916),
          f"调 9:16 时 3:4 和 1:1 同步更新 -> {man}")
    check(k235 not in man, f"2.35:1 保持独立不被同步 -> {man}")

    # 反向:切到 3:4 拖动 -> 9:16 和 1:1 也同步
    dlg.pick_ratio(0)
    _drag_to(0.31)
    man = v.plan.get("manual") or {}
    check(abs(man.get(k34, [0])[0] - 0.31) < 0.01 and man.get(k916) == man.get(k34) and man.get(k11) == man.get(k34),
          f"双向同步:调 3:4 时 9:16 和 1:1 也同步 -> {man}")

    # 手动关闭同步开关 -> 只改当前比例
    dlg.k_sync.setChecked(False)
    dlg.pick_ratio(3)  # 1:1
    _drag_to(0.70)
    man = v.plan.get("manual") or {}
    check(abs(man.get(k11, [0])[0] - 0.70) < 0.02 and abs(man.get(k916, [0])[0] - 0.31) < 0.01 and abs(man.get(k34, [0])[0] - 0.31) < 0.01,
          f"关闭同步后只调当前 1:1 -> {man}")
    dlg.close()

    # MainWindow 不再触发 AI 看封面
    st = Settings(tmp / "st_noai.json")
    st["ai_key"] = "fake"
    w = W.MainWindow(st, Records(tmp / "rec_noai.sqlite"))
    check(not w.AI_COVER and not st.get("ai_cover", False), "主窗口已关闭 AI 看封面")
    w._ai_covers()
    check(getattr(w, "ai_worker", None) is None, "_ai_covers 为空操作,不启动 AiCoverWorker")
    w.close()


def test_long_check_and_toggles(tmp: Path):
    print("[超过10分钟标记与放行 + 设置6项开关彻底隐藏/停用]")
    from PySide6.QtWidgets import QApplication
    import gui.api_tab as T
    import gui.window as W
    from qe import apiacc, checkline, checks, dimcache, folders as F, lansync, longcheck as LC
    from qe.config import Settings
    from qe.records import Records
    app = QApplication.instance() or QApplication([])

    # 1. longcheck 单元逻辑
    LC.ENABLED = True
    check(LC.fmt_dur(605) == "10分05秒" and LC.is_long(601) and not LC.is_long(600), "600秒以内不标,超过600秒标")
    p1 = LC.problem("CSGO战神君", "超长局", 615.0)
    check("超过10分钟(10分15秒)" in p1, f"默认拦截超10分钟 -> {p1}")
    LC.store().set("CSGO战神君", "超长局", True)
    check(LC.problem("CSGO战神君", "超长局", 615.0) == "", "放行后不再拦截")
    LC.store().set("CSGO战神君", "超长局", False)
    check(bool(LC.problem("CSGO战神君", "超长局", 615.0)), "取消放行恢复拦截")
    LC.ENABLED = False
    check(LC.problem("CSGO战神君", "超长局", 615.0) == "", "关闭总开关后不触发")
    LC.ENABLED = True

    # 2. dimcache 缓存 dur
    vp = tmp / "dc_vid.mp4"
    vp.write_bytes(b"12345")
    dimcache.put(str(vp), 1080, 1920, dur=625.5)
    check(dimcache.get(str(vp)) == (1080, 1920) and abs((dimcache.get_dur(str(vp)) or 0) - 625.5) < 0.01,
          "dimcache 持久化宽高和时长")

    # 3. 16 个号 & 教育号界面标黄放行 + game_ai_check 开关 + checkline 全关彻底隐藏
    root = tmp / "lc_root" / "游戏视频" / "CSGO--CSGO战神君" / "11.26"
    root.mkdir(parents=True)
    vfile = root / "超长测试视频.mp4"
    vfile.write_bytes(b"abc")
    apiacc.save([{"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_lc.json")
    st["api_roots"] = [str(tmp / "lc_root" / "游戏视频")]
    st["game_ai_check"] = False
    rec = Records(tmp / "rec_lc.sqlite")
    tab = T.ApiTab(st, rec, lambda _s: None)
    tab.SHARP_CHECK = False
    tab.COVER_CHECK = False
    tab.set_day("11.26")
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 1)
    tab.videos[0].checks = {"w": 1080, "h": 1920, "dur": 725.0, "landscape": False, "tags": [], "platform": []}
    tab._fill(0)
    check(tab.items[0].text(3) == "要处理" and "超过10分钟(12分05秒)" in tab.items[0].text(2),
          f"16个号状态与备注标出超10分钟 -> {tab.items[0].text(3)} / {tab.items[0].text(2)}")
    tab.set_long_ok(0, True)
    check(tab.items[0].text(3) == "能发" and not tab.items[0].text(2),
          f"右键放行后可发 -> {tab.items[0].text(3)} / {tab.items[0].text(2)}")
    tab.set_long_ok(0, False)
    check(tab.items[0].text(3) == "要处理" and "超过10分钟" in tab.items[0].text(2), "取消放行后恢复标黄")
    check(tab._ai_games_vs([tab.videos[0]], lambda _s: None, lambda: False) == 0, "game_ai_check=False 时不调 AI 查串游戏")

    # checkline 全部关闭 -> 单元格和进度栏均为空
    for k in ("sharp_check", "crop_check", "outro_check", "audio_check"):
        st[k] = False
    tab._check_refresh()
    check(tab.items[0].text(4) == "" and tab.lab_check.text() == "",
          f"四项检查全关:检查列与顶部进度均隐藏 -> {tab.items[0].text(4)!r} / {tab.lab_check.text()!r}")
    for k in ("sharp_check", "crop_check", "outro_check", "audio_check"):
        st[k] = True

    # 教育号页同样支持超10分钟标黄与放行
    st2 = Settings(tmp / "st_lc2.json")
    w = W.MainWindow(st2, Records(tmp / "rec_lc2.sqlite"))
    w.videos = [F.Video(str(vfile), "超长课", "家长研习空间", "张", "11.26", dur=650.0)]
    w.table.setRowCount(1)
    w._fill_row(0)
    check("超过10分钟(10分50秒)" in w.table.item(0, 4).text() and bool(w._title_block(w.videos[0])),
          f"教育号页超10分钟标黄拦截 -> {w.table.item(0, 4).text()}")
    w.table.selectRow(0)
    w.set_long_ok(True)
    check(w.table.item(0, 4).text() == "还没发" and not w._title_block(w.videos[0]), f"教育号页放行成功 -> {w.table.item(0, 4).text()}")
    w.set_long_ok(False)
    check("long_check" in lansync.SHARED_SETTING_KEYS and "game_ai_check" in lansync.SHARED_SETTING_KEYS
          and "longcheck" in lansync.STORE_FILES, "局域网同步已包含超长放行与新开关")
    w.close()
    apiacc.save([])


def test_quick_import_and_drop(tmp: Path):
    print("[16个号:账号行「导入 ▾」快捷菜单 + 拖拽文件夹导入]")
    from PySide6.QtWidgets import QApplication
    import gui.api_tab as T
    from qe import apiacc
    from qe.config import Settings
    from qe.records import Records
    app = QApplication.instance() or QApplication([])

    root = tmp / "imp_root" / "游戏视频"
    csgo = root / "CSGO--CSGO战神君"
    (csgo / "11.25").mkdir(parents=True)
    (csgo / "11.25" / "老片.mp4").write_bytes(b"1")
    (csgo / "11.26").mkdir(parents=True)
    (csgo / "11.26" / "今天片.mp4").write_bytes(b"2")
    (csgo / "周末存货").mkdir(parents=True)
    (csgo / "周末存货" / "存货1.mp4").write_bytes(b"3")
    (csgo / "11.26已发").mkdir(parents=True)
    (csgo / "11.26已发" / "已发片.mp4").write_bytes(b"4")
    (csgo / "横屏原片").mkdir(parents=True)
    (csgo / "横屏原片" / "原片.mp4").write_bytes(b"5")

    pubg = root / "PUBG--PUBG突围君" / "11.26"
    pubg.mkdir(parents=True)
    (pubg / "吃鸡.mp4").write_bytes(b"6")

    apiacc.save([
        {"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "a", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
        {"nick": "PUBG突围君", "source_name": "PUBG", "client_id": "b", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
    ])
    st = Settings(tmp / "st_imp.json")
    st["api_roots"] = [str(root)]
    rec = Records(tmp / "rec_imp.sqlite")
    tab = T.ApiTab(st, rec, lambda _s: None)
    tab.SHARP_CHECK = False
    tab.COVER_CHECK = False
    tab.set_day("11.26")
    _wait(app, lambda: not tab.busy() and len(tab.videos) == 2)

    # 每个账号行 col 1 都有导入按钮,重排后仍在
    check(tab.tree.itemWidget(tab.groups["CSGO战神君"], 1) is not None, "账号行第 1 列挂有「导入 ▾」按钮")
    tab._reorder()
    check(tab.tree.itemWidget(tab.groups["CSGO战神君"], 1) is not None, "_reorder 重排后按钮仍存在")

    # 候选子文件夹列表:包含日期与存货,过滤已发与横屏原片
    cands = tab._candidate_folders("CSGO战神君")
    names = [n for n, _p, _cnt in cands]
    check("11.26" in names and "11.25" in names and "周末存货" in names, f"列出候选文件夹 -> {names}")
    check("11.26已发" not in names and "横屏原片" not in names, f"过滤掉已发和原片文件夹 -> {names}")
    check(names.index("11.26") < names.index("11.25"), f"最新日期排在前面 -> {names}")

    # 通过快捷导入 / 拖拽应用文件夹
    check(tab._apply_pick("CSGO战神君", str(csgo / "周末存货")), "快捷导入「周末存货」返回 True")
    _wait(app, lambda: not tab.busy())
    csgo_titles = [v.title for v in tab.videos if v.account == "CSGO战神君"]
    check(csgo_titles == ["存货1"], f"快捷导入「周末存货」立刻切换为该目录视频 -> {csgo_titles}")

    # 拖错别家账号目录被 _bad_pick 防呆拦住
    check(not tab._apply_pick("CSGO战神君", str(pubg)), "拖错别家目录返回 False 被拦截")
    check(os.path.normcase(st.get("api_picked", {}).get("11.26", {}).get("CSGO战神君", "")) == os.path.normcase(str(csgo / "周末存货")),
          "拦住后保持原手选")
    apiacc.save([])


def test_ai_assistant(tmp: Path):
    print("[内置 AI 助手:6 个工具 + 安全红线 + 左侧页/右侧抽屉同步]")
    import json
    from PySide6.QtWidgets import QApplication
    import gui.window as W
    from qe import assistant as A, apiacc
    from qe.config import Settings
    from qe.folders import Video
    from qe.records import Records
    app = QApplication.instance() or QApplication([])

    # 准备素材与归档文件
    st = Settings(tmp / "st_ai.json")
    st["ai_key"] = "fake-key"
    api_root = tmp / "ai_root" / "游戏视频"
    csgo_day = api_root / "CSGO--CSGO战神君" / "11.26"
    csgo_day.mkdir(parents=True)
    arc_dir = tmp / "ai_arc" / "11.26" / "CSGO"
    arc_dir.mkdir(parents=True)
    st["api_roots"] = [str(api_root)]
    st["api_archive"] = str(tmp / "ai_arc" / "{date}")

    # 两条已发且归档的视频:一条确定没发上(sure=True),一条被审核打回(sure=False)
    f_miss = arc_dir / "漏发视频A.mp4"
    f_miss.write_bytes(b"video-miss")
    f_rej = arc_dir / "打回视频B.mp4"
    f_rej.write_bytes(b"video-rej")

    rec = Records(tmp / "rec_ai.sqlite")
    v_miss = Video(path=str(csgo_day / "漏发视频A.mp4"), title="漏发视频A", account="CSGO战神君", employee="接口", date="11.26")
    v_rej = Video(path=str(csgo_day / "打回视频B.mp4"), title="打回视频B", account="CSGO战神君", employee="接口", date="11.26")
    rec.manual_published(v_miss, note="article_id=A1", at="2026-11-26 10:00:00")
    rec.manual_published(v_rej, note="article_id=A2", at="2026-11-26 10:05:00")
    rec.conn.execute("UPDATE posts SET moved_pkey=? WHERE title=?", (str(f_miss), "漏发视频A"))
    rec.conn.execute("UPDATE posts SET moved_pkey=? WHERE title=?", (str(f_rej), "打回视频B"))
    rec.conn.commit()
    rows_by_title = {r["title"]: r for r in rec.rows(account="CSGO战神君")}

    # 确认没有暴露任何绕过确认的直接发布 / 删除线上作品工具
    tool_names = [t["function"]["name"] for t in A.TOOLS_SCHEMA]
    check(set(tool_names) == {
        "check_today_plan", "verify_backend", "check_black_covers",
        "find_archived_videos", "pull_back_for_republish", "open_in_czgt",
        "scan_old_folders", "clean_old_folders", "prepare_autopilot",
        "manage_watch", "read_autopilot_log",
    }, f"仅暴露 11 个受控工具,无直接发布/删除线上工具 -> {tool_names}")

    opened_czgt = []
    exported_cov = []

    def fake_check_acc(_cl, _rec, nick, day):
        return {
            "nick": nick, "ours": 2, "live": 0, "ok": 0, "review": 0,
            "missing": [
                dict(rows_by_title["漏发视频A"], why="企鹅号上是「发布失败」—— 没发上", sure=True),
                dict(rows_by_title["打回视频B"], why="被审核打回了", sure=False),
            ],
            "extra": [],
        }

    def fake_scan_one(acc, s, e, **_kw):
        return ([{"nick": acc["nick"], "title": "黑封面视频C", "time": f"{s} 11:00:00", "kind": "黑封面", "aid": "BLK1"}], 0)

    def fake_export(items, _st, **_kw):
        exported_cov.extend(items)
        return len(items)

    deps = {
        "today_fn": lambda: "2026-11-26",
        "accounts_fn": lambda: [({"nick": "CSGO战神君", "client_id": "c", "secret": "s"}, False)],
        "make_client": lambda _a: object(),
        "check_account_fn": fake_check_acc,
        "scan_one_fn": fake_scan_one,
        "export_covers_fn": fake_export,
        "open_czgt_fn": lambda acc, title, day="": opened_czgt.append((acc, title, day)) or f"已定位 {acc}《{title}》",
    }

    # 1. 离线模拟多轮工具调用:用户只问「帮我查漏发」-> 返回汇总 + 一键拎回按钮(不自动挪文件)
    turns = iter([
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "verify_backend", "arguments": "{}"}}
        ]},
        {"role": "assistant", "content": "查完了：CSGO战神君有 1 条确定没发上（漏发视频A），1 条被打回（打回视频B）。"},
    ])
    agent = A.AssistantAgent(st, rec, chat_fn=lambda _ai, _m, _t, _to: next(turns), deps=deps)
    res1 = agent.ask("去后台查一下今天有没有漏发")
    check("漏发视频A" in res1["reply"] and f_miss.exists(), "只查不挪:回复正常且归档原文件未被擅自移动")
    check(len(res1["actions"]) == 1 and res1["actions"][0]["kind"] == "pull_back"
          and len(res1["actions"][0]["payload"]["items"]) == 1,
          f"只给「确定没发上」的生成一键拎回按钮 -> {res1['actions']}")

    # 2. 安全红线:尝试批量拎回两条(含 sure=False 的打回视频B) -> 只挪漏发视频A,跳过打回视频B!
    pb = agent.tool_pull_back_for_republish([
        {"row_id": rows_by_title["漏发视频A"]["id"]},
        {"row_id": rows_by_title["打回视频B"]["id"]},
    ], confirmed_only=True)
    check(pb["moved_count"] == 1 and pb["skipped_count"] == 1, f"批量只挪确定没发上、跳过打回项 -> {pb}")
    check((csgo_day / "漏发视频A.mp4").is_file() and not f_miss.exists() and f_rej.is_file(),
          "确定没发上的已拎回今天待发目录,打回的原地不动")
    check(rec.status_by_id(rows_by_title["漏发视频A"]["id"]) == "没发成"
          and rec.status_by_id(rows_by_title["打回视频B"]["id"]) == "已发",
          "数据库仅改回已拎回那条为没发成")

    # 3. 查黑封面 + 截清晰图 + 去罐头定位
    rb = agent.run_quick("black")
    check("黑封面视频C" in rb["reply"] and any(a["kind"] == "export_covers" for a in rb["actions"])
          and any(a["kind"] == "open_czgt" for a in rb["actions"]),
          f"快捷查黑封面附带截封面与罐头定位按钮 -> {rb['actions']}")
    r_exp = agent.execute_action(next(a for a in rb["actions"] if a["kind"] == "export_covers"))
    r_cz = agent.execute_action(next(a for a in rb["actions"] if a["kind"] == "open_czgt"))
    check(len(exported_cov) == 1 and "已截取清晰封面：1 / 1" in r_exp["reply"], f"一键截清晰封面执行成功 -> {r_exp}")
    check(opened_czgt == [("CSGO战神君", "黑封面视频C", "2026-11-26")] and "已定位" in r_cz["reply"], f"去罐头定位执行成功 -> {opened_czgt}")

    # 4. 界面集成:左侧全屏 AI 助手页 + 右侧抽屉共用同一对话历史,切到全屏页时抽屉自动收起
    w = W.MainWindow(st, rec)
    w.ai_hub.agent.deps.update(deps)
    check("ai" in w.pages and w.ai_page.hub is w.ai_drawer.hub, "全屏页与右侧抽屉共用同一个 AssistantHub")
    w.toggle_ai_drawer(True)
    check(not w.ai_drawer.isHidden(), "点抽屉开关可展开右侧抽屉")
    w.ai_hub.quick("plan", "查今天发完没")
    _wait(app, lambda: not w.ai_hub.is_busy() and len(w.ai_hub.messages) >= 2)
    check(len(w.ai_page._bubbles) == len(w.ai_drawer._bubbles) and len(w.ai_page._bubbles) >= 2,
          f"全屏页与抽屉实时同步气泡数量 -> {len(w.ai_page._bubbles)} / {len(w.ai_drawer._bubbles)}")
    w.goto("ai")
    check(w.ai_drawer.isHidden(), "切到左侧全屏 AI 助手页时右侧抽屉自动收起")
    w.close()


def test_old_folders_and_no_leftovers(tmp: Path):
    print("[发完无残留(.meowload/结尾原片/带空格封面) + AI助手扫描清理过期文件夹]")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    import gui.api_tab as T
    from qe import apiacc, apicover, apisrc, assistant as A, omapi
    from qe.config import Settings
    from qe.folders import Video
    from qe.records import Records

    # 1. 带末尾空格的同名封面也能配对并随视频一起挪走
    d_cov = tmp / "cov_space"
    d_cov.mkdir()
    vp = d_cov / "怪物策划问答.mp4"
    cp = d_cov / "怪物策划问答 .jpg"
    vp.write_bytes(b"v")
    cp.write_bytes(b"j")
    check(os.path.normcase(apicover.find(str(vp))) == os.path.normcase(str(cp)), "apicover.find 匹配末尾带空格的封面")
    dst_c = tmp / "cov_space_arc"
    apisrc.move_published(str(vp), str(dst_c))
    check(not vp.exists() and not cp.exists() and (dst_c / "怪物策划问答.jpg").is_file(),
          f"move_published 一并挪走带空格封面不残留 -> {os.listdir(dst_c)}")

    # 2. _clean_empty_dirs: 发完后清掉 .meowload + 结尾原片 + Thumbs.db + 残留封面并删目录; 保留未知非空子目录
    root = tmp / "clean_root" / "游戏视频"
    acc = root / "PUBG--PUBG突围君"
    d_ok = acc / "11.25未改比例"
    (d_ok / ".meowload").mkdir(parents=True)
    (d_ok / "结尾原片").mkdir(parents=True)
    (d_ok / "结尾原片" / "旧原片.mp4").write_bytes(b"old")
    (d_ok / "吃鸡1.mp4").write_bytes(b"v1")
    (d_ok / "吃鸡1 .jpg").write_bytes(b"j1")
    (d_ok / "多余封面.jpg").write_bytes(b"j2")
    (d_ok / "Thumbs.db").write_bytes(b"t")

    d_keep_sub = acc / "11.24"
    (d_keep_sub / "别删我的子夹").mkdir(parents=True)
    (d_keep_sub / "别删我的子夹" / "说明.txt").write_bytes(b"hi")
    (d_keep_sub / "吃鸡2.mp4").write_bytes(b"v2")

    apiacc.save([{"nick": "PUBG突围君", "source_name": "PUBG", "client_id": "c", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])
    st = Settings(tmp / "st_nolef.json")
    st["api_roots"] = [str(root)]
    st["api_archive"] = str(tmp / "arc_nolef" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    st["quota_open"] = True

    class FakeCl:
        def __init__(self, *a, **k):
            pass
        def send(self, path, title, cat, before_publish=None, **k):
            if before_publish:
                before_publish("V")
            return {"vid": "V", "article_id": "A" + title, "transaction_id": "P", "status": "成功"}

    real = (omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning)
    omapi.Client, T.ask = FakeCl, (lambda *a, **k: True)
    QMessageBox.information = QMessageBox.warning = staticmethod(lambda *a, **k: 0)
    try:
        tab = T.ApiTab(st, Records(tmp / "rec_nolef.sqlite"), lambda _m: None)
        tab.SHARP_CHECK = False
        tab.COVER_CHECK = False
        tab.set_day("11.25")
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 1)
        tab.videos[0].checks = {"w": 1080, "h": 1920, "landscape": False, "bad_read": False}
        tab._update_scope()
        tab.run_publish()
        _wait(app, lambda: not tab.busy())
        _wait(app, lambda: not d_ok.exists(), 8)
        check(not d_ok.exists(), "发完后连同 .meowload / 结尾原片 / Thumbs.db / 多余封面一起清理并删空日期夹")

        tab.set_day("11.24")
        _wait(app, lambda: not tab.busy() and len(tab.videos) == 1)
        tab.videos[0].checks = {"w": 1080, "h": 1920, "landscape": False, "bad_read": False}
        tab._update_scope()
        tab.run_publish()
        _wait(app, lambda: not tab.busy())
        check(d_keep_sub.is_dir() and (d_keep_sub / "别删我的子夹" / "说明.txt").is_file(),
              "含未知非空子目录时不误删该目录")
    finally:
        omapi.Client, T.ask, QMessageBox.information, QMessageBox.warning = real

    # 3. AI 助手 scan_old_folders + clean_old_folders
    groot = tmp / "ai_old" / "游戏视频"
    fps_acc = groot / "腾讯系FPS射击游戏-FPS射击游戏馆"
    # 3a) 11.25未改比例: .meowload + Thumbs.db + 残留封面
    f1 = fps_acc / "11.25未改比例"
    (f1 / ".meowload").mkdir(parents=True)
    (f1 / "Thumbs.db").write_bytes(b"t")
    (f1 / "残留图 .jpg").write_bytes(b"j")
    # 3b) 11.24: 1条已发未归档 + 1条已发且归档已有副本
    f2 = fps_acc / "11.24"
    f2.mkdir(parents=True)
    v_sent_noarc = f2 / "已发没挪走.mp4"
    v_sent_dup = f2 / "已发重复副本.mp4"
    v_sent_noarc.write_bytes(b"s1")
    v_sent_dup.write_bytes(b"s2")
    arc_exist = tmp / "ai_old_arc" / "11.24" / "FPS"
    arc_exist.mkdir(parents=True)
    dup_in_arc = arc_exist / "已发重复副本.mp4"
    dup_in_arc.write_bytes(b"s2-arc")
    # 3c) 11.23: 1条已发 + 1条未发(绝不能删未发!)
    f3 = fps_acc / "11.23"
    f3.mkdir(parents=True)
    v_mix_sent = f3 / "混杂里的已发.mp4"
    v_mix_unsent = f3 / "混杂里的未发.mp4"
    v_mix_sent.write_bytes(b"ms")
    v_mix_unsent.write_bytes(b"mu")
    # 3d) 11.27(今天): 不在 <=11.25 范围内
    f_today = fps_acc / "11.27"
    f_today.mkdir(parents=True)
    (f_today / "今天的.mp4").write_bytes(b"td")

    st2 = Settings(tmp / "st_oldai.json")
    st2["api_roots"] = [str(groot)]
    st2["api_archive"] = str(tmp / "ai_old_arc" / "{date}")
    rec2 = Records(tmp / "rec_oldai.sqlite")
    for vp_x, t_x, moved in (
        (v_sent_noarc, "已发没挪走", ""),
        (v_sent_dup, "已发重复副本", str(dup_in_arc)),
        (v_mix_sent, "混杂里的已发", ""),
    ):
        rec2.manual_published(Video(str(vp_x), t_x, "FPS射击游戏馆", "接口", "11.24"), note="ok", at="2026-11-24 12:00:00")
        if moved:
            rec2.conn.execute("UPDATE posts SET moved_pkey=? WHERE title=?", (moved, t_x))
    rec2.conn.commit()
    apiacc.save([{"nick": "FPS射击游戏馆", "source_name": "FPS", "client_id": "x", "secret": apiacc.seal("s"), "category": 1604, "enabled": True}])

    agent = A.AssistantAgent(st2, rec2, deps={"today_fn": lambda: "2026-11-27"})
    sc = agent.tool_scan_old_folders(before_day="11.25", root_filter="游戏")
    by_name = {x["folder_name"]: x for x in sc["folders"]}
    check(set(by_name) == {"11.25未改比例", "11.24", "11.23"}, f"按 <=11.25 准确列出过期目录,不含 11.27 -> {list(by_name)}")
    check(by_name["11.25未改比例"]["status"] == "empty_or_leftover" and by_name["11.24"]["status"] == "all_sent"
          and by_name["11.23"]["status"] == "partial_sent",
          f"分类准确 -> { {k: v['status'] for k, v in by_name.items()} }")

    # 越权路径绝不被清理
    outside = tmp / "outside_important"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"k")
    cl = agent.tool_clean_old_folders(folders_list=[str(f1), str(f2), str(f3), str(outside)])
    check(outside.is_dir() and (outside / "keep.txt").is_file(), "配置目录之外的路径绝不碰")
    check(not f1.exists() and not f2.exists(), f"纯残留夹与全已发夹清理并删空 -> removed={cl['removed_dirs_count']}")
    check(cl["archived_sent_count"] == 2 and cl["deleted_dup_sent_count"] == 1,
          f"未归档的2条已发挪进归档,归档已有副本的1条删重复 -> {cl['archived_sent_count']}/{cl['deleted_dup_sent_count']}")
    check(f3.is_dir() and v_mix_unsent.is_file() and not v_mix_sent.exists() and cl["kept_unsent_count"] == 1,
          "混杂目录仅归档已发视频,未发视频与目录完整保留")
    check(f_today.is_dir() and (f_today / "今天的.mp4").is_file(), "今天目录丝毫未动")

    # 快捷入口「查过期/残留文件夹」+ 按钮执行
    f_extra = fps_acc / "11.20"
    f_extra.mkdir(parents=True)
    rq = agent.run_quick("old_folders")
    check("11.20" in rq["reply"] and any(a["kind"] == "clean_old_folders" for a in rq["actions"]),
          f"快捷按钮扫出旧空夹并附带一键清理按钮 -> {rq['actions']}")
    r_act = agent.execute_action(next(a for a in rq["actions"] if a["kind"] == "clean_old_folders"))
    check(not f_extra.exists() and "删除空/残留目录 1 个" in r_act["reply"], f"点一键清理按钮删掉 11.20 -> {r_act['reply']}")
    apiacc.save([])


def test_autopilot(tmp: Path):
    print("[16个号全链路自动驾驶:按设置开关检查 + 转竖屏/改标题 + 发布清残留 + 查漏自动补发1轮 + 黑封面 + 卡片同步]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import gui.window as W
    from gui.assistant_panel import _AutopilotConfirmCard, _AutopilotReportCard
    from qe import apiacc, autopilot as AP
    from qe.config import Settings
    from qe.folders import Video
    from qe.records import Records

    groot = tmp / "ap_root" / "游戏视频"
    csgo_d = groot / "CSGO--CSGO战神君" / "11.27未改比例"
    (csgo_d / ".meowload").mkdir(parents=True)
    (csgo_d / "Thumbs.db").write_bytes(b"t")
    # 5 条视频: 1) 正常横屏+多话题(自动转竖+改标题+发布), 2) 模糊但关了sharp_check(应放行发布),
    # 3) 无声(audio_check开->跳过), 4) 超10分钟(long_check开->跳过), 5) 普通可发(模拟首次后台漏发->自动拎回补发1轮)
    f_land = csgo_d / "横屏多话题 #CSGO #激励计划.mp4"
    f_blur = csgo_d / "略模糊但关了检查.mp4"
    f_mute = csgo_d / "无声视频.mp4"
    f_long = csgo_d / "超长视频.mp4"
    f_miss = csgo_d / "漏发要补.mp4"
    for f in (f_land, f_blur, f_mute, f_long, f_miss):
        f.write_bytes(b"vid-bytes")

    # PUBG 今日已发满(done), DNF 无今日文件夹(missing)
    (groot / "PUBG--PUBG突围君" / "11.27").mkdir(parents=True)
    (groot / "PUBG--PUBG突围君" / "11.27" / "满额片.mp4").write_bytes(b"p")
    (groot / "地下城与勇士--DNF连招档案馆").mkdir(parents=True)

    accs = [
        {"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c1", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
        {"nick": "PUBG突围君", "source_name": "PUBG", "client_id": "c2", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
        {"nick": "DNF连招档案馆", "source_name": "DNF", "client_id": "c3", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
    ]
    apiacc.save(accs)

    st = Settings(tmp / "st_ap.json")
    st["api_roots"] = [str(groot)]
    st["api_archive"] = str(tmp / "ap_arc" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    st["sharp_check"] = False        # 用户没勾「视频模糊」-> 彻底不跑也不拦!
    st["crop_check"] = False
    st["outro_check"] = False
    st["audio_check"] = True
    st["long_check"] = True
    st["game_ai_check"] = False
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 10, "PUBG突围君": 1, "DNF连招档案馆": 10}}]

    rec = Records(tmp / "rec_ap.sqlite")
    rec.manual_published(Video(str(tmp / "old_pubg.mp4"), "旧吃鸡", "PUBG突围君", "接口", "11.27"), note="ok", at="2026-11-27 08:00:00")

    sent_log = []
    vert_log = []
    sharp_calls = []
    exported_cov = []

    class FakeClient:
        def send(self, path, title, cat, stop=None, before_publish=None, cover="", cover_upload=None, **_k):
            if before_publish:
                before_publish("VID_" + title)
            sent_log.append(title)
            return {"article_id": "AID_" + title, "vid": "VID_" + title, "status": "成功"}

    def fake_check_one(v, words=None, ff=""):
        t = v.title
        return {
            "w": 1920 if "横屏" in t else 1080,
            "h": 1080 if "横屏" in t else 1920,
            "dur": 650.0 if "超长" in t else 60.0,
            "has_audio": False if "无声" in t else True,
            "landscape": "横屏" in t,
            "squarish": False,
            "tags": ["CSGO", "激励计划"] if "多话题" in t else [],
            "platform": [],
            "bad_read": False,
        }

    def fake_sharp(path, ff):
        sharp_calls.append(path)
        return {"hits": [{"t": 1.0, "score": 5.0}]}

    def fake_audio(path, ff, has_audio=None, dur=None):
        return {"hits": [{"kind": "none"}]} if has_audio is False else {"hits": []}

    def fake_to_vert(path, ff, stop=None, keep_orig=False):
        vert_log.append(os.path.basename(path))
        return path, ""

    def fake_verify(_cl, r_db, nick, day):
        rows = [r for r in r_db.rows(account=nick) if r["status"] == "已发" and r["title"] == "漏发要补"]
        miss = [dict(rows[0], why="企鹅号上是「发布失败」—— 没发上", sure=True)] if rows else []
        return {"nick": nick, "ours": len(rows), "live": 2, "ok": 2, "review": 0, "missing": miss, "extra": []}

    def fake_scan_black(acc, s, e, **_k):
        return ([{"nick": acc["nick"], "title": "略模糊但关了检查", "time": f"{s} 10:00:00", "kind": "黑封面", "aid": "B1"}], 0)

    def fake_export_cov(items, _st, **_k):
        exported_cov.extend(items)
        return len(items)

    deps = {
        "today_fn": lambda: "2026-11-27",
        "api_accounts_fn": lambda: accs,
        "accounts_fn": lambda: [(a, False) for a in accs],
        "make_client": lambda _a: FakeClient(),
        "check_one_fn": fake_check_one,
        "sharp_check_fn": fake_sharp,
        "audio_check_fn": fake_audio,
        "to_vertical_fn": fake_to_vert,
        "topic_pick_fn": lambda body, tags: tags[0],
        "check_account_fn": fake_verify,
        "scan_one_fn": fake_scan_black,
        "export_covers_fn": fake_export_cov,
        "api_interval": 0,
    }

    # 1. prepare 只读预演
    prep = AP.prepare(st, rec, deps=deps)
    check(prep["can_start"] and prep["ready_count"] == 1 and prep["total_estimated"] == 5,
          f"prepare 准确识别 1 个就绪号(5条) -> {prep['ready_count']}/{prep['total_estimated']}")
    check(prep["missing_accounts"] == ["DNF连招档案馆"] and [x["account"] for x in prep["done_accounts"]] == ["PUBG突围君"],
          f"准确分出无今日夹(DNF)和今日已发满(PUBG) -> {prep['missing_accounts']} / {prep['done_accounts']}")
    check("视频模糊" in prep["checks"]["disabled"] and "无声音检查" in prep["checks"]["enabled"] and "超过10分钟" in prep["checks"]["enabled"],
          f"确认卡片反映设置里勾选的检查项 -> {prep['checks']}")

    # 2. run 全链路执行
    rep = AP.run(st, rec, deps=deps)
    check(not sharp_calls, f"关掉视频模糊检查后彻底不调用 sharp_check -> {sharp_calls}")
    check(rep["converted_count"] == 1 and len(vert_log) == 1, f"横屏自动转竖屏 1 条 -> {vert_log}")
    check(rep["renamed_count"] == 1 and "横屏多话题 #CSGO" in sent_log, f"多话题自动整理成单话题并发布 -> {sent_log}")
    check("略模糊但关了检查" in sent_log, "未勾选模糊检查的略模糊片正常放行发布")
    check(rep["published_count"] == 3 and rep["retried_count"] == 1,
          f"首轮发 3 条 + 查出漏发自动拎回补发 1 轮(1 条) -> pub={rep['published_count']}, ret={rep['retried_count']}")
    skip_titles = {x["title"] for x in rep["skipped_items"]}
    check(skip_titles == {"无声视频", "超长视频"}, f"勾选开启的无声与超10分钟被拦入待拍板清单 -> {rep['skipped_items']}")
    check(len(rep["black_covers"]) == 1 and rep["exported_covers_count"] == 1 and len(exported_cov) == 1,
          f"发后自动扫描黑封面并导出清晰图 -> {rep['black_covers']} / {rep['exported_covers_count']}")
    # 混着 2 条被拦视频，所以日期夹里应保留这 2 条未发视频不误删
    check(f_mute.is_file() and f_long.is_file(), "被拦下的未发视频完整保留在原目录")

    # 3. 界面集成：确认卡片 + 取消同步 + 战报卡片双入口渲染
    w = W.MainWindow(st, rec)
    w.ai_hub.agent.deps.update(deps)
    w.ai_hub.quick("autopilot", "🚀 今日全自动")
    _wait(app, lambda: not w.ai_hub.is_busy() and len(w.ai_hub.messages) >= 2)
    b_page = w.ai_page._bubbles[-1]
    b_draw = w.ai_drawer._bubbles[-1]
    check(isinstance(b_page.card_widget, _AutopilotConfirmCard) and isinstance(b_draw.card_widget, _AutopilotConfirmCard),
          "左侧全屏页与右侧抽屉均渲染出全自动确认卡片")
    w.ai_hub.cancel_card(b_page.msg["card"])
    check(b_page.card_widget.lab_state.text() == "已取消" and b_draw.card_widget.lab_state.text() == "已取消",
          "取消卡片状态在全屏页与抽屉同步更新")

    # 验证战报卡片渲染
    w.ai_hub._append("assistant", rep["summary"], [], card={"kind": "autopilot_report", "report": rep})
    check(isinstance(w.ai_page._bubbles[-1].card_widget, _AutopilotReportCard)
          and isinstance(w.ai_drawer._bubbles[-1].card_widget, _AutopilotReportCard),
          "全屏页与右侧抽屉均正确渲染最终战报卡片")
    w.close()
    apiacc.save([])


def test_folder_intent_and_watch(tmp: Path):
    print("[文件夹备注理解(规则+AI缓存) + 落稳30秒 + 数量等2轮 + 无日期发现 + 全天值守 + 仅密钥失效红点 + 中途指挥]")
    import time
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import gui.window as W
    from qe import apiacc, assistant as A, autopilot as AP, folder_intent as FI
    from qe.config import Settings
    from qe.omapi import ApiError
    from qe.records import Records

    # 1. 规则层 + AI 兜底 + 缓存
    r1 = FI.interpret_folder("11.27未改比例")
    check(r1["action"] == "ready" and r1["needs_vertical_hint"] and r1["source"] == "rule", f"未改比例 -> ready: {r1}")
    r2 = FI.interpret_folder("11.27（正在处理）")
    check(r2["action"] == "wait" and r2["source"] == "rule", f"正在处理 -> wait: {r2}")
    r3 = FI.interpret_folder("11.27(15)")
    check(r3["action"] == "ready" and r3["expected_count"] == 15 and r3["source"] == "rule", f"(15) -> ready/15: {r3}")
    r4 = FI.interpret_folder("11.27不能用")
    check(r4["action"] == "ignore" and r4["source"] == "rule", f"不能用 -> ignore: {r4}")

    ai_calls = []
    def fake_remark_ai(fname, rem):
        ai_calls.append(rem)
        return {"action": "wait", "reason": "等老板过目后再发"}
    r5 = FI.interpret_folder("11.27（等老板点头）", ask_fn=fake_remark_ai)
    r5b = FI.interpret_folder("11.27（等老板点头）", ask_fn=fake_remark_ai)
    check(r5["action"] == "wait" and r5["source"] == "ai" and r5b["source"] == "cache" and len(ai_calls) == 1,
          f"新备注问一次 AI 后命中本地缓存不重复问 -> {r5} / {r5b} / calls={ai_calls}")
    # 无 Key / AI 失败 -> 保守 wait
    r6 = FI.interpret_folder("11.27（奇怪备注XYZ）", ask_fn=lambda f, r: (_ for _ in ()).throw(RuntimeError("net")))
    check(r6["action"] == "wait" and r6["source"] == "fallback", f"AI 失败保守判 wait -> {r6}")

    # 2. 文件落稳检测（30 秒 + .part 临时文件）
    d_st = tmp / "stab"
    d_st.mkdir()
    vf = d_st / "新片.mp4"
    vf.write_bytes(b"abc")
    now_t = time.time()
    os.utime(vf, (now_t - 5, now_t - 5))
    check(not FI.check_folder_stability(str(d_st), min_age_sec=30.0, now=now_t)["stable"], "5秒前刚写入 -> 未落稳")
    os.utime(vf, (now_t - 45, now_t - 45))
    check(FI.check_folder_stability(str(d_st), min_age_sec=30.0, now=now_t)["stable"], "45秒前写入 -> 已落稳")
    (d_st / "另一条.mp4.part").write_bytes(b"p")
    check(not FI.check_folder_stability(str(d_st), min_age_sec=30.0, now=now_t)["stable"], "含 .part 下载临时文件 -> 未落稳")
    (d_st / "另一条.mp4.part").unlink()

    # 3. 全天值守完整场景
    groot = tmp / "wt_root" / "游戏视频"
    csgo_root = groot / "CSGO--CSGO战神君"
    # 3a) 正在处理文件夹 -> 先不动
    d_wait = csgo_root / "11.27（正在处理）"
    d_wait.mkdir(parents=True)
    (d_wait / "处理中视频.mp4").write_bytes(b"w")
    os.utime(d_wait / "处理中视频.mp4", (now_t - 120, now_t - 120))
    # 3b) 标明 (3) 但目前只有 2 条 -> 第 1、2 轮等，第 3 轮(连续 2 次不涨)先发并记提醒
    d_cnt = csgo_root / "11.27(3)"
    d_cnt.mkdir(parents=True)
    for nm in ("数量片1.mp4", "数量片2.mp4"):
        p = d_cnt / nm
        p.write_bytes(b"v")
        os.utime(p, (now_t - 120, now_t - 120))
    # 3c) 无日期夹「周末存货」今天刚有新片 -> 不擅自发，只提示一键加入按钮
    d_und = csgo_root / "周末存货"
    d_und.mkdir(parents=True)
    p_und = d_und / "存货新片.mp4"
    p_und.write_bytes(b"u")
    os.utime(p_und, (now_t - 120, now_t - 120))

    # 3d) 另一账号模拟密钥失效 -> 触发 key_errors 强提醒
    pubg_d = groot / "PUBG--PUBG突围君" / "11.27"
    pubg_d.mkdir(parents=True)
    p_badk = pubg_d / "吃鸡钥匙坏了.mp4"
    p_badk.write_bytes(b"k")
    os.utime(p_badk, (now_t - 120, now_t - 120))

    accs = [
        {"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c1", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
        {"nick": "PUBG突围君", "source_name": "PUBG", "client_id": "c2", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
    ]
    apiacc.save(accs)
    st = Settings(tmp / "st_wt.json")
    st["api_roots"] = [str(groot)]
    st["api_archive"] = str(tmp / "wt_arc" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    for k in ("sharp_check", "crop_check", "outro_check", "audio_check", "long_check", "game_ai_check"):
        st[k] = False
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 10, "PUBG突围君": 10}}]
    rec = Records(tmp / "rec_wt.sqlite")

    sent_titles = []

    class FakeOk:
        def send(self, path, title, cat, before_publish=None, **_k):
            if before_publish:
                before_publish("V_" + title)
            sent_titles.append(title)
            return {"article_id": "A_" + title, "vid": "V_" + title, "status": "成功"}

    class FakeBadKey:
        def send(self, *a, **k):
            e = ApiError("token invalid")
            e.fatal = True
            raise e

    now_hm_box = ["10:00"]
    today_s = FI.time.strftime("%Y-%m-%d", FI.time.localtime(now_t))
    today_md = f"{int(today_s[5:7])}.{int(today_s[8:10])}"
    # 把日期文件夹重命名成真正的 today_md，让 datetime.fromtimestamp(mtime, BJ) 对齐 day_iso
    d_wait2 = csgo_root / f"{today_md}（正在处理）"
    d_cnt2 = csgo_root / f"{today_md}(3)"
    pubg_d2 = groot / "PUBG--PUBG突围君" / today_md
    os.rename(d_wait, d_wait2)
    os.rename(d_cnt, d_cnt2)
    os.rename(pubg_d, pubg_d2)

    deps = {
        "today_fn": lambda: today_s,
        "now_ts": now_t,
        "now_hm_fn": lambda: now_hm_box[0],
        "api_accounts_fn": lambda: accs,
        "accounts_fn": lambda: [(a, False) for a in accs],
        "make_client": lambda a: FakeBadKey() if a["nick"] == "PUBG突围君" else FakeOk(),
        "check_one_fn": lambda v, words=None, ff="": {"w": 1080, "h": 1920, "dur": 30.0, "has_audio": True, "landscape": False, "tags": [], "platform": [], "bad_read": False},
        "check_account_fn": lambda cl, r_db, nick, d: {"nick": nick, "ours": 0, "live": 0, "ok": 0, "review": 0, "missing": [], "extra": []},
        "scan_one_fn": lambda acc, s, e, **_k: ([], 0),
        "api_interval": 0,
    }

    agent = A.AssistantAgent(st, rec, deps=deps)
    # 启动全天值守（第 1 轮）：CSGO 的「正在处理」和「(3)目前2条」都等待，周末存货被发现但不擅自发，PUBG 报密钥失效
    r_start = agent.execute_action({
        "kind": "run_autopilot",
        "payload": {"day": today_s, "watch": True, "interval_min": 10, "cutoff_hm": "22:30"},
    })
    check(agent.watch is not None and agent.watch.active, "全天值守已启动")
    check("处理中视频" not in sent_titles and "数量片1" not in sent_titles and "存货新片" not in sent_titles,
          f"正在处理 / 数量未凑齐 / 无日期存货 均未擅自发布 -> {sent_titles}")
    check(any(e["account"] == "PUBG突围君" for e in (r_start.get("key_errors") or [])),
          f"检测到 PUBG 密钥失效并上报强提醒 -> {r_start.get('key_errors')}")
    check(any(a["kind"] == "add_watch_folder" and "周末存货" in a["label"] for a in (r_start.get("actions") or [])),
          f"发现无日期文件夹「周末存货」并附带一键加入按钮 -> {r_start.get('actions')}")

    # 中途一句话指挥：跳过 PUBG、改巡检为 5 分钟、把周末存货加入值守
    check(agent.tool_manage_watch("skip_account", account="PUBG")["ok"], "中途指令跳过 PUBG")
    check(agent.tool_manage_watch("set_interval", interval_min=5)["ok"] and agent.watch.interval_min == 5, "中途改巡检间隔为 5 分钟")
    check(agent.tool_manage_watch("add_folder", account="CSGO", folder="周末存货")["ok"], "中途把无日期「周末存货」加入今天值守")

    # 第 2 轮巡检：「周末存货」里的存货新片被发布；「(3)」第 1 次停滞仍在等；「正在处理」仍在等
    tk2 = agent.run_watch_tick_result()
    check("存货新片" in sent_titles and "数量片1" not in sent_titles and "处理中视频" not in sent_titles,
          f"第 2 轮仅发布刚加入的存货新片，(3)与正在处理继续等 -> {sent_titles}")

    # 第 3 轮巡检：「(3)」连续 2 次巡检数量未涨 -> 先行发布 2 条并带数量提示；且同事把「正在处理」删备注改名后立刻接手！
    os.rename(d_wait2, csgo_root / f"{today_md}第二批")
    tk3 = agent.run_watch_tick_result()
    check({"数量片1", "数量片2", "处理中视频"}.issubset(set(sent_titles)),
          f"第 3 轮数量等待超时先行发布 + 删掉「正在处理」后立刻自动接手 -> {sent_titles}")
    check(any("标 3 条实际 2 条" in n for n in (tk3.get("card", {}).get("report", {}).get("count_notes") or [])),
          f"战报里附带「标 3 条实际 2 条」提示 -> {tk3.get('card', {}).get('report', {}).get('count_notes')}")

    # 空轮次安静不刷屏
    tk4 = agent.run_watch_tick_result()
    check(tk4.get("quiet") is True and tk4.get("reply") == "", f"没新片时静默不发废话气泡 -> {tk4}")

    # 到 22:30 自动收工
    now_hm_box[0] = "22:30"
    tk5 = agent.run_watch_tick_result()
    check(not agent.watch.active and "自动收工" in tk5["reply"], f"到 22:30 自动收工 -> {tk5['reply']}")

    # 留痕日志落盘与过滤验证（每一步可追溯 + 只看异常 + AI 读取 + 弹窗打开）
    from qe import aplog
    from gui.assistant_panel import AutopilotLogDialog
    full_log = agent.tool_read_autopilot_log(day=today_s)
    err_log = agent.tool_read_autopilot_log(day=today_s, errors_only=True)
    check(full_log["total_lines"] >= 8 and "值守启动" in full_log["text"] and "发布成功" in full_log["text"]
          and "中途指挥" in full_log["text"] and "值守收工" in full_log["text"],
          f"全自动全流程每一步均落盘留痕 -> {full_log['total_lines']} 行")
    check(err_log["matched_lines"] >= 1 and "密钥失效" in err_log["text"] and "值守启动" not in err_log["text"],
          f"只看异常/失败/跳过精准过滤出密钥失效等异常 -> {err_log['lines'][:3]}")
    dlg_log = AutopilotLogDialog(day_iso=today_s)
    check(dlg_log.ed_log.toPlainText().strip() != "" and today_s in dlg_log.c_day.currentText(), "留痕日志查看窗口正常加载")
    dlg_log.k_err.setChecked(True)
    check("密钥失效" in dlg_log.ed_log.toPlainText(), "弹窗勾选「只看异常」实时生效")
    dlg_log.close()

    # UI 密钥失效红点测试
    w = W.MainWindow(st, rec)
    w._on_ai_key_alert("PUBG 密钥失效")
    check(w.nav.badges[5].text() == "!" and not w.nav.badges[5].isHidden(), "密钥失效亮左侧 AI 助手红点「!」")
    w.goto("ai")
    check(w.nav.badges[5].isHidden(), "点进 AI 助手页后红点自动清除")
    _wait(app, lambda: not w.api_tab.busy(), 5)
    w.close()
    apiacc.save([])


def test_autopilot_fixes_and_live(tmp: Path):
    print("[全自动回归: 真实check_one参数顺序 + 横屏转竖屏 + 自动剪头像片尾抽检组 + 实时动态卡 + 弹窗实时刷新]")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import gui.window as W
    from gui.assistant_panel import AutopilotLogDialog, _AutopilotReportCard
    from qe import apiacc, aplog, autopilot as AP, checks, outrocheck, vertical
    from qe.config import Settings
    from qe.records import Records

    # 1. outrocheck PROMPT 严格口径：覆盖头像片尾(居中/角落/无红勾点我关注) + 剪映/抖音/快手等平台片尾 + 二维码，纯文字放行
    check("头像" in outrocheck.PROMPT and "点我关注" in outrocheck.PROMPT and "右上角" in outrocheck.PROMPT
          and "剪映" in outrocheck.PROMPT and "记录美好生活" in outrocheck.PROMPT
          and "只有文字或账号名字" in outrocheck.PROMPT and "found=false" in outrocheck.PROMPT,
          "outrocheck.PROMPT 已覆盖头像片尾(居中/角落/点我关注)与剪映/抖音/快手等标准片尾，且纯文字不误杀")

    # 2. 真实 checks.check_one 回归（传入含「手/助/f/g/2」的 ffmpeg 路径，绝不能被当成平台词误拦）
    groot = tmp / "fix_root" / "游戏视频"
    csgo_d = groot / "CSGO--CSGO战神君" / "11.27"
    csgo_d.mkdir(parents=True)
    f_land = csgo_d / "让我们为中国大陆赛区加油助威！2026CFS世界总决赛SSG.mp4"
    f_outro = csgo_d / "带头像片尾 #CSGO #多余话题.mp4"
    f_land.write_bytes(b"land-video")
    f_outro.write_bytes(b"outro-video")
    shot_p = tmp / "outro_shot.jpg"
    shot_p.write_bytes(b"fake-jpg")

    accs = [
        {"nick": "CSGO战神君", "source_name": "CSGO", "client_id": "c1", "secret": apiacc.seal("s"), "category": 1604, "enabled": True},
    ]
    apiacc.save(accs)
    st = Settings(tmp / "st_fix.json")
    st["api_roots"] = [str(groot)]
    st["api_archive"] = str(tmp / "fix_arc" / "{date}")
    st["api_interval"] = 0
    st["api_cover"] = "不传"
    st["sharp_check"] = False
    st["crop_check"] = False
    st["outro_check"] = True
    st["audio_check"] = False
    st["long_check"] = False
    st["game_ai_check"] = False
    st["daily_plan"] = [{"cat": "游戏", "label": "游戏总发布量", "accounts": {"CSGO战神君": 10}}]
    rec = Records(tmp / "rec_fix.sqlite")

    sent_titles = []
    vert_called = []
    cut_called = []

    class FakeClient:
        def send(self, path, title, cat, before_publish=None, **_k):
            if before_publish:
                before_publish("VID_" + title)
            sent_titles.append(title)
            return {"article_id": "AID_" + title, "vid": "VID_" + title, "status": "成功"}

    orig_probe = vertical.probe
    def fake_probe(path, ff=""):
        if "赛区加油助威" in str(path):
            return {"w": 1280, "h": 720, "dur": 45.0, "has_audio": True}
        return {"w": 1080, "h": 1920, "dur": 28.0, "has_audio": True}

    def fake_to_vert(path, ff, stop=None, keep_orig=False):
        vert_called.append(os.path.basename(path))
        return path, ""

    def fake_outro_check(path, cfg, ff="", **_k):
        if "带头像片尾" in str(path):
            return {"hits": [{"start": 25.0, "end": 28.0, "kind": "头像片尾卡片", "reason": "居中圆形头像片尾卡片"}], "shot": str(shot_p)}
        return {"hits": []}

    def fake_outro_cut(path, start, ff="", stop=None, **_k):
        cut_called.append((os.path.basename(path), float(start)))
        return path, "", 3.0

    vertical.probe = fake_probe
    try:
        deps = {
            "today_fn": lambda: "2026-11-27",
            "api_accounts_fn": lambda: accs,
            "accounts_fn": lambda: [(a, False) for a in accs],
            "make_client": lambda _a: FakeClient(),
            "ffmpeg_path": r"E:\软件\百家号发布软件\企鹅号发布助手\ffmpeg.exe",
            "check_one_fn": checks.check_one,   # 真实 check_one！
            "to_vertical_fn": fake_to_vert,
            "outro_check_fn": fake_outro_check,
            "outro_cut_fn": fake_outro_cut,
            "topic_pick_fn": lambda body, tags: tags[0],
            "check_account_fn": lambda cl, r_db, nick, d: {"nick": nick, "ours": 2, "live": 2, "ok": 2, "review": 0, "missing": [], "extra": []},
            "scan_one_fn": lambda acc, s, e, **_k: ([], 0),
            "api_interval": 0,
        }
        rep = AP.run(st, rec, deps=deps)
    finally:
        vertical.probe = orig_probe

    check(rep["skipped_count"] == 0 and rep["published_count"] == 2,
          f"真实 check_one 不误杀含助/2/f/g的标题，且头像片尾自动剪掉后正常发布 -> pub={rep['published_count']}, skip={rep['skipped_items']}")
    check(rep["converted_count"] == 1 and len(vert_called) == 1,
          f"横屏视频成功进入阶段③转竖屏 -> {vert_called}")
    check(rep["outro_cut_count"] == 1 and len(cut_called) == 1 and abs(cut_called[0][1] - 25.0) < 0.01,
          f"头像片尾卡片自动从 25.0s 剪掉并发布 -> {cut_called}")
    oc_items = rep.get("outro_cut_items") or []
    check(len(oc_items) == 1 and oc_items[0]["title"] == "带头像片尾 #CSGO" and abs(oc_items[0]["cut_sec"] - 3.0) < 0.01,
          f"战报记录自动剪片尾条目（含改名后最终标题与剪掉秒数） -> {oc_items}")

    # 3. 战报卡片渲染「自动剪过头像片尾」抽检卡片组 + 按钮回调
    clicked_acts = []
    rc = _AutopilotReportCard({"kind": "autopilot_report", "report": rep}, compact=False, on_action=clicked_acts.append)
    check(rc.outro_group is not None and len(rc._outro_cards) == 1 and len(rc._outro_btns) == 1,
          "战报卡片正确渲染「自动剪过头像片尾」抽检卡片组与「去罐头定位」按钮")
    rc._outro_btns[0].click()
    check(len(clicked_acts) == 1 and clicked_acts[0]["kind"] == "open_czgt"
          and clicked_acts[0]["payload"]["title"] == "带头像片尾 #CSGO",
          f"点「去罐头定位」携带正确账号与最终标题 -> {clicked_acts}")

    # 4. 实时动态卡片（全屏页 + 右侧抽屉同步）与留痕弹窗实时刷新
    w = W.MainWindow(st, rec)
    w.ai_hub._live_active = True
    w.ai_hub._live_stage = 1
    w.ai_hub._live_headline = "正在启动全自动"
    w.ai_hub._live_lines = []
    aplog.add_listener(w.ai_hub._aplog_listener)
    w.ai_hub.live_changed.emit(w.ai_hub.live_info())
    app.processEvents()
    check(not w.ai_page.live_card.isHidden() and not w.ai_drawer.live_card.isHidden(),
          "启动全自动时全屏页与右侧抽屉同时展开实时动态卡片")
    aplog.write("③转竖屏", "开始转竖屏：《实时测试横屏》", level="INFO", account="CSGO战神君", day_iso="2026-11-27")
    app.processEvents()
    check(w.ai_page.live_card._stage == 3 and "实时测试横屏" in w.ai_page.live_card.lab_feed.text()
          and "实时测试横屏" in w.ai_drawer.live_card.lab_feed.text(),
          f"aplog 实时推送驱动动态卡片高亮第③步并显示正在转的视频 -> {w.ai_page.live_card.lab_feed.text()}")
    aplog.remove_listener(w.ai_hub._aplog_listener)
    w.ai_hub._live_active = False
    w.ai_hub.live_changed.emit(w.ai_hub.live_info())
    app.processEvents()
    check(w.ai_page.live_card.isHidden() and w.ai_drawer.live_card.isHidden(),
          "任务结束后实时动态卡片自动收起")

    dlg = AutopilotLogDialog(day_iso="2026-11-27")
    check(dlg.k_live.isChecked() and dlg._live_timer.isActive(), "留痕弹窗默认开启实时刷新定时器")
    aplog.write("④发布", "发布成功：《弹窗新日志测试》", level="OK", account="CSGO战神君", day_iso="2026-11-27")
    dlg.reload(force=False)
    check("弹窗新日志测试" in dlg.ed_log.toPlainText(), "留痕弹窗实时刷新自动拉取新写入的日志行")
    dlg.close()

    _wait(app, lambda: not w.api_tab.busy(), 5)
    w.close()
    apiacc.save([])


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="qe_test_"))
    _no_dialogs()
    test_folders(tmp)
    test_cover_dir(tmp)
    test_scan_any_layout(tmp)
    test_scan_tricky(tmp)
    test_scan_cover_match(tmp)
    test_window_dups(tmp)
    test_cover(tmp)
    test_records(tmp)
    test_failed_steps(tmp)
    test_bj_time()
    test_guard()
    test_window(tmp)
    test_window_scan(tmp)
    test_preview(tmp)
    test_title_zone(tmp)
    test_group(tmp)
    test_api(tmp)
    test_api_tab(tmp)
    test_audit_r1(tmp)
    test_audit_r2(tmp)
    test_ui_r1(tmp)
    test_squarish(tmp)
    test_audit_r3(tmp)
    test_bughunt(tmp)
    test_daily_plan(tmp)
    test_login_key(tmp)
    test_window_renamed(tmp)
    test_at_titles(tmp)
    test_schedule(tmp)
    test_prepare_retry(tmp)
    test_sched_edu(tmp)
    test_sched_api(tmp)
    test_ui_g(tmp)
    test_pub_progress(tmp)
    test_awake(tmp)
    test_yellow_manual(tmp)
    test_api_per_acc(tmp)
    test_quick_review(tmp)
    test_quota_gate(tmp)
    test_game_guard(tmp)
    test_ux_fixes(tmp)
    test_packs(tmp)
    test_clean_dirs(tmp)
    test_black_border(tmp)
    test_edit_quota(tmp)
    test_extra_vert_order(tmp)
    test_verify(tmp)
    test_unsend(tmp)
    test_api_dups(tmp)
    test_view_tomorrow(tmp)
    test_cover_move_keep(tmp)
    test_export_and_edu_dims(tmp)
    test_misfire_api(tmp)
    test_misfire_edu(tmp)
    test_sched_notice(tmp)
    test_cd_items(tmp)
    test_api_wm(tmp)
    test_edu_wm(tmp)
    test_blur(tmp)
    test_ads(tmp)
    test_cover_cache_unique(tmp)
    test_cover_dialog_src(tmp)
    test_api_direct(tmp)
    test_api_cover_pic(tmp)
    test_api_cover(tmp)
    test_wm_detect_unit(tmp)
    test_find_redo(tmp)
    test_edu_verify(tmp)
    test_redo_room(tmp)
    test_verify_range(tmp)
    test_mark_sent_keep(tmp)
    test_key_guards(tmp)
    test_audit_redo(tmp)
    test_audit_verify(tmp)
    test_autocover(tmp)
    test_unsure_check(tmp)
    test_spill_picked_root(tmp)
    test_quota_free(tmp)
    test_cover_login(tmp)
    test_accounts_manage(tmp)
    test_ai_cover(tmp)
    test_title_date(tmp)
    test_flat_folders(tmp)
    test_black_cover(tmp)
    test_sharp(tmp)
    test_crop_back(tmp)
    test_check_status(tmp)
    test_ai_errors(tmp)
    test_own_ai(tmp)
    test_vcheck(tmp)
    test_outro_cut(tmp)
    test_bad_cover_fix(tmp)
    test_per_account_concurrency(tmp)
    test_title_extra_clean(tmp)
    test_verify_web_and_lag(tmp)
    test_black_cover_v2(tmp)
    test_portable_bundle(tmp)
    test_lan_sync(tmp)
    test_audiocheck(tmp)
    test_cover_sync_and_no_ai(tmp)
    test_long_check_and_toggles(tmp)
    test_quick_import_and_drop(tmp)
    test_ai_assistant(tmp)
    test_old_folders_and_no_leftovers(tmp)
    test_autopilot(tmp)
    test_folder_intent_and_watch(tmp)
    test_autopilot_fixes_and_live(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项:\n  - " + "\n  - ".join(fails)))
    sys.exit(1 if fails else 0)
