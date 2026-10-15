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
    check(apisrc.archive_dir({}, "10.15") == r"X:\知乎视频\内容查看\10月发布视频\企鹅号\企鹅号软件发布", "发完挪到「企鹅号软件发布」")

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
    check(led.undo_last() == (2, 0) and sorted(os.listdir(d)) == ["a #CSGO #反恐精英.jpg", "a #CSGO #反恐精英.mp4"], "能撤销")

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
                return R({"code": "0", "data": {"transaction_id": "U1"}})
            if path == "/video/clientuploadtrunk":       # 和真接口一样:end_offset = 收到的最后一个字节(含),文件名只能英文
                off = int(kw["data"]["start_offset"])
                name, chunk, _ct = kw["files"]["mediatrunk"]
                assert name.isascii(), "文件名得是英文"
                assert off == sum(len(c) for c in self.trunks), "多传 / 少传了"
                self.trunks.append(chunk)
                return R({"code": "0", "data": {"start_offset": off + len(chunk) - 1, "end_offset": off + len(chunk) - 1}})
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
    check(b"".join(s2.trunks) == bytes(range(10)) and len(s2.trunks) == 4, "分片上传:一片接一片,传完不多传(end_offset 含最后一个字节)")
    check(r == {"vid": "V7", "article_id": "A9", "transaction_id": "P1", "status": "成功"}, "发布流程:传 → vid → 发 → 等成功")
    check(pub == {"title": v.title, "tags": "", "vid": "V7", "cat": 1604, "desc": v.title, "aigc_userstatement": "2",
                  "ext_info": "self_declare=0"},
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

        def send(self, path, title, cat, **k):
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
    out = tmp / "发布" / "10.15已发布"
    check(sorted(os.listdir(out / "CSGO")) == ["c1.mp4", "c2.mp4"] and os.listdir(out / "电竞赛事") == ["e1.mp4"]
          and os.path.isfile(os.path.join(esp, "e1.jpg")), "发完挪走,按游戏分子文件夹(名字 = 旧软件「账号」),只挪视频")
    check(apisrc.archive_dir({"api_archive_by_game": False}, "10.15", accs[0]).endswith("企鹅号软件发布")
          and apisrc.archive_dir({}, "10.15", accs[0]).endswith("企鹅号软件发布" + os.sep + "CSGO"), "不勾「按游戏分」就平铺")
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
    check(set(tab.groups) == {"CSGO战神君"} and all(not g.isExpanded() for g in tab.groups.values()),
          "按号分组,默认收起")
    tab.expand_all(True)
    check(all(g.isExpanded() for g in tab.groups.values()), "全部展开")
    tab.expand_all(False)
    check(all(not g.isExpanded() for g in tab.groups.values()), "全部收起")
    tab.groups["CSGO战神君"].setExpanded(True)
    tab.load()
    check(tab.groups["CSGO战神君"].isExpanded(), "刷新后展开的还展开着")
    tab.tree.clearSelection()
    tab.groups["CSGO战神君"].setSelected(True)
    check([tab.videos[i].title for i in tab.selected_rows()] == ["c3", "d1", "d2"], "选中号 = 这个号全部")
    check("3 条" in tab.groups["CSGO战神君"].text(0) and "没检查" in tab.groups["CSGO战神君"].text(2), "号那一行有统计")
    from PySide6.QtWidgets import QInputDialog
    real_t, real_i = QInputDialog.getText, QMessageBox.information
    QInputDialog.getText = staticmethod(lambda *a, **k: ("英雄联盟", True))
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
        tab.ledger.undo_last()
        tab.ledger.undo_last()
        tab.load()
        check(any(v.title == "c3" for v in tab.videos), "撤销改名")
    finally:
        QInputDialog.getText, QMessageBox.question, QMessageBox.information = real_t, real_q, real_i
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
    check("全部" in tab.b_check.text() and "全部" in tab.b_pub.text(), "没选:按钮写着「全部」")
    tab.tree.clearSelection()
    tab.groups["电竞情报馆"].setSelected(True)
    check("选中 1 条" in tab.b_check.text() and "电竞情报馆" in tab.lab_scope.text(), "选了一个号:按钮写着「选中 N 条」")
    tab.run_check()
    tab.job.wait()
    QApplication.processEvents()
    check([bool(v.checks) for v in tab.videos] == [v.account == "电竞情报馆" for v in tab.videos], "只检查选中的号")
    tab.tree.clearSelection()
    check("全部" in tab.b_check.text(), "取消选择:回到全部")
    tab.unpick("电竞情报馆")
    check("10.15" not in (st.get("api_picked") or {}), "取消手选")


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


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="qe_test_"))
    test_folders(tmp)
    test_cover_dir(tmp)
    test_cover(tmp)
    test_records(tmp)
    test_failed_steps(tmp)
    test_bj_time()
    test_guard()
    test_window(tmp)
    test_preview(tmp)
    test_title_zone(tmp)
    test_group(tmp)
    test_api(tmp)
    test_api_tab(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项:\n  - " + "\n  - ".join(fails)))
    sys.exit(1 if fails else 0)
