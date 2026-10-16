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
    check("密钥" in short and "搬账号" in tip, "换 token 失败:说密钥不对 + 去重新搬")

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
    test_audit_r1(tmp)
    test_audit_r2(tmp)
    test_ui_r1(tmp)
    test_squarish(tmp)
    test_audit_r3(tmp)
    test_bughunt(tmp)
    test_daily_plan(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项:\n  - " + "\n  - ".join(fails)))
    sys.exit(1 if fails else 0)
