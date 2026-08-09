"""DSTranslator 入口。"""
import sys

from PySide6.QtWidgets import QApplication

from dstl.app import Application


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DSTranslator")
    app.setQuitOnLastWindowClosed(False)  # 关窗不退出,缩到托盘
    # 必须持有 Application 引用:写成 Application(app).run() 会让临时对象在
    # run() 返回后被 GC,SearchBar 随之失引用,捕获→显示的信号连接失效
    application = Application(app)
    application.run()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
