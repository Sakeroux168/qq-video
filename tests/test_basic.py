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
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
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
        QInputDialog.getText = staticmethod(lambda *a, **k: ("c3 改过的标题", True))
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
    QApplication.instance() or QApplication([])
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
    QApplication.instance() or QApplication([])
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
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from qe import apiacc, checks, omapi, topic
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T

    short, tip = T.friendly(omapi.ApiError("上传视频失败:invalid_file_upload(code 40023)", "40023"))
    check("平台不收" in short and "重新导出" in tip, "40023:说人话 + 下一步")
    short, tip = T.friendly(omapi.ApiError("换 token 失败", "40001", fatal=True))
    check("密钥" in short and "登录取钥匙" in tip, "换 token 失败:说密钥不对 + 去登录取钥匙")

    class V:
        title = "A小到底该怎么控 "
        checks = {"w": 1080, "h": 1920, "tags": []}
    check(checks.problems(V) == ["结尾多了空格"], "只是结尾多空格:单独说「结尾多了空格」")
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
    check(tab.minimumSizeHint().width() <= 1000, f"接口页选中号以后最小宽度 {tab.minimumSizeHint().width()} ≤ 1000")


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
    QApplication.instance() or QApplication([])
    from qe import apiacc, apisrc, fsops, omapi, topic
    from qe.config import Settings
    from qe.records import Records
    import gui.api_tab as T

    # 4. 「10.15已发」「10.15不能用」「10.150」不算 10.15
    check([apisrc.date_key(x) for x in ("10.15", "10.15(20)", "10.14（星期三）", "10.15已发", "10.15不能用", "10.15 脏话", "10.150")]
          == ["10.15", "10.15", "10.14", "", "", "", ""], "日期文件夹:后面跟了别的字的不算(已发 / 不能用 / 脏话)")

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
    QApplication.instance() or QApplication([])
    from qe import plan
    from qe.config import Settings
    from qe.records import Records
    from gui.daily_tab import DailyTab
    st = Settings(tmp / "plan_st.json")
    check(plan.quota_of(st, "和平精英上分君") == 80 and plan.quota_of(st, "国漫解说馆z") == 50 and plan.quota_of(st, "家长小天地") == 0,
          "每个号每天规定条数(教育不分号)")
    check([plan.cat_total(g) for g in plan.plan(st)] == [380, 106, 200], "游戏 380 / 教育 106 / 动漫 200")
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
    check(s1["rows"] == [("游戏总发布量", 380, 3), ("教育总发布量", 106, 1), ("动漫总发布量", 200, 1)] and s1["total"] == (686, 5),
          f"按发出去的日期数(素材文件夹 10.14 / 10.15 都算今天发的)-> {s1['rows']}")
    tsv = plan.as_tsv(s1).splitlines()
    check(tsv[0].split("\t") == [plan.short_day(day), "发布企鹅号视频", "游戏总发布量", "380", "3"] and tsv[3].split("\t")[2:] == ["总发布量", "686", "5"],
          "复制的文字:日期 / 工作内容 / 品类 / 规定 / 实际,和企业微信表一样")
    short = plan.short_list(s1)
    check(short[0][0] == "和平精英上分君" and all(n != "家长小天地" for n, _q, _a in short), "没达标的号:差得多的排前面;教育不算")
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
    check(F.mark_dups([x2, x1, x3]) == 1 and not x1.skip and "卓金凤13" in x2.skip and x3.skip == "0 字节",
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
    check(kids["张"].text(1) == "1 条" and kids["李"].text(1).startswith("3 条") and "2 条不发" in kids["李"].text(1),
          f"树:李 3 条里 2 条不发 -> 张「{kids['张'].text(1)}」李「{kids['李'].text(1)}」")
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
    check(st4["同名/李"].startswith("不发:和「张」") and st4["挪过的/李"].startswith("不发:这个号发过同名的") and st4["新的/李"] == "没发",
          f"表里写清楚为什么不发 -> {st4}")
    check("另有 2 条不发" in w._nothing_left(), "没得摆时也说还有几条不发")
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
    check("发了 1" in li.text(1) and "2 条不发" in li.text(1), f"同一天改了名的算已发,别天的 / 归档过的照旧不发 -> {li.text(1)}")
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
    v = NS(title="五杀集锦 @抖音小助手 #英雄联盟", checks={"w": 1080, "h": 1920, "tags": ["英雄联盟"], "platform": []})
    check(any("@抖音小助手" in p for p in checks.problems(v)), f"16 个号:带 @ 的算有问题(不让发)-> {checks.problems(v)}")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
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
    check("@" in (bad.skip or "") and not ok.skip, f"教育号:带 @ 的跳过、写清楚原因 -> {bad.skip}")
    w.close()


def test_schedule(tmp: Path):
    print("[定时发布:定好 / 到点 / 软件没开着错过了 / 别让电脑睡]")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
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
    QApplication.instance() or QApplication([])
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
    QApplication.instance() or QApplication([])
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
    QApplication.instance() or QApplication([])
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
    check(no.checkState(0) == Qt.CheckState.Checked and w.table.rowCount() == 3 and "1 条没无字封面" in no.text(1),
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


def _no_dialogs():
    """测试里不弹框:中文确认框(gui.api_tab.ask)一律点「是」,提示框一律关掉(不然 offscreen 下会一直等人点)。"""
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    import gui.api_tab as T
    T.ask = lambda *a, **k: True
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)


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
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项:\n  - " + "\n  - ".join(fails)))
    sys.exit(1 if fails else 0)
