"""企鹅号发布助手:在创作罐头里把企鹅号的视频一批批摆好(传视频、封面裁好、声明),停在发布前,人自己点发布。"""
import sys


def main():
    from PySide6.QtWidgets import QApplication
    from gui.window import MainWindow
    from qe.config import Settings
    app = QApplication(sys.argv)
    app.setApplicationName("企鹅号发布助手")
    app.setStyleSheet("QWidget{font-family:'Microsoft YaHei';font-size:13px} QPushButton{padding:5px 12px}")
    w = MainWindow(Settings())
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
