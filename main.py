"""企鹅号发布助手:教育号在创作罐头里把视频一批批摆好(人点发布);16 个游戏 / 动漫号用官方接口发。"""
import sys
import traceback


def main():
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv)
    app.setApplicationName("企鹅号发布助手")
    from PySide6.QtCore import QLibraryInfo, QTranslator
    tr = QTranslator(app)                     # 对话框按钮用中文(审查:原来是 Yes / No / OK / Cancel)
    if tr.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(tr)
    try:
        from gui.window import MainWindow
        from qe.config import Settings, data_dir
        # 只许开一个(审查:开两个会互相冲掉设置,接口发还可能同一条发两遍)
        lock = QLockFile(str(data_dir() / "运行中.lock"))
        lock.setStaleLockTime(0)
        # 刚关掉马上又开:上一个还在收尾(等后台活停下、存设置),等它几秒(用户 2026-10-17:「已经开着了」可我没看到)
        if not lock.tryLock(8000):
            QMessageBox.information(None, "企鹅号发布助手", "企鹅号发布助手已经开着了(看看任务栏)。\n\n只能开一个,免得两边互相冲掉设置、重复发视频。\n"
                                    "(要是刚关掉:它还在收尾,过十几秒再开)")
            return 0
        st = Settings()
        from gui import theme                     # 界面风格(设置里选;老版本存的名字认不出来就用浅色)
        theme.apply(app, st.get("theme") or theme.DEFAULT)
        w = MainWindow(st)
        w.show()
        if st.get("splash", True):                # 开场「Hi,欢迎使用本工作台」(设置里能关)
            w.play_splash()
        if st.broken:
            QMessageBox.warning(w, "设置文件坏了", f"设置文件读不出来,已经用默认设置打开。\n坏的那份留着:\n{st.broken}\n\n"
                                "去「设置…」里把素材文件夹、Key 等重新填一下。")
        if getattr(w.rec, "broken", ""):
            QMessageBox.warning(w, "发布记录坏了", f"发布记录库读不出来,已经新建了一个空的。\n坏的那份留着:\n{w.rec.broken}\n\n"
                                "注意:以前发过的软件现在认不出来了,发之前留意别重复发。")
        code = app.exec()
        lock.unlock()
        return code
    except Exception:
        # 用 pythonw 打开时没有黑窗口,出错要弹出来(审查:原来直接没反应)
        QMessageBox.critical(None, "企鹅号发布助手打不开", "出错了,把下面这段发给做软件的人:\n\n" + traceback.format_exc()[-1500:])
        return 1


if __name__ == "__main__":
    sys.exit(main())
