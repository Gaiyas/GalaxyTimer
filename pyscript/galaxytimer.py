import os
import sys
import time

from PySide6.QtCore import *
from PySide6.QtWidgets import *

from logic.main_window import MainWindow


def Loop():
    try:
        global g_TimeMs, main_window
        curTimeMs = time.time() * 1000
        deltaMs = curTimeMs - g_TimeMs
        g_TimeMs = curTimeMs
        core_input.Update()
        core_timer.UpdateTimer(deltaMs)
    except KeyboardInterrupt:
        global updateTimer, main_window
        if updateTimer:
            updateTimer.stop()
            updateTimer = None
        if main_window:
            main_window.quit()
        main_window = None
        sys.exit()


if __name__ == '__main__':

    cur_path = os.getcwd()
    sys.path.append(os.path.join(cur_path, "pyscript"))
    sys.path.append(os.path.join(cur_path, "resources"))

    # 初始化输入、定时器、语音
    from core import core_input
    from core import core_timer
    from core import core_voice
    from core import core_event
    # 加载资源
    from widgets._rc import resource  # noqa

    core_input.Initialize()
    core_timer.Initialize()
    core_voice.Initialize()
    core_event.Initialize()

    # 源码热更新
    # if not sys.argv[0].endswith('.exe'):
    #     from filereload import filewatch
    #     filewatch.StartReload(os.getcwd())

    # 创建主窗口
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()

    # 时间戳
    g_TimeMs = time.time() * 1000

    # 定时器
    updateTimer = QTimer(app)
    updateTimer.timeout.connect(Loop)
    updateTimer.start(16)  # 控制在60帧

    app.exec()
