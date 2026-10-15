"""企鹅号发布助手:教育号在创作罐头里把视频一批批摆好(人点发布);16 个游戏 / 动漫号用官方接口发。"""
import sys
import traceback


def main():
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv)
    app.setApplicationName("企鹅号发布助手")
    app.setStyleSheet("QWidget{font-family:'Microsoft YaHei';font-size:13px} QPushButton{padding:5px 12px}")
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
        if not lock.tryLock(100):
            QMessageBox.information(None, "企鹅号发布助手", "企鹅号发布助手已经开着了(看看任务栏)。\n\n只能开一个,免得两边互相冲掉设置、重复发视频。")
            return 0
        st = Settings()
        w = MainWindow(st)
        w.show()
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
