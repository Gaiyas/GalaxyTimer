# --*utf-8*--
# Author：一念断星河
# Crete Data：2024/6/3
# Desc：不过是大梦一场空，不过是孤影照惊鸿。
import os
import sys
import threading
import time
import weakref
from collections import defaultdict
from typing import List, Dict

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from core import core_timer, core_save, core_input, core_voice, core_event
from core.core_define import *
from core.core_input import KeyType
from core.functor import CFunctor
from logic.munu.menu_group import Group_Menu
from logic.munu.menu_help import Help_Info
from logic.munu.menu_setting import Setting_Menu
from logic.munu.menu_timer import Timer_Menu
from logic.munu.menu_voice import Voice_Menu
from logic.timer.timer_group import GroupProxy
from widgets.menu import RoundMenu, Action, FIF, MenuAnimationType
from logic.helper.pet_res import PetRes
from logic.timer.timer_info import TimerProxy


class MainWindow(QLabel):
    def __init__(self):
        super().__init__(None)
        self.m_Uuid = 0
        self.m_UuidGroup = 0
        self.m_AllTimer: "Dict[int, TimerProxy]" = {}
        self.m_AllGroup: "Dict[int, GroupProxy]" = {}
        self.m_Pets: "List[PetRes]" = []
        self.m_CurPet: "PetRes" = None
        self.m_PetUpdateTimer = None
        self._Pixmap = None
        self._PixmapSize = 72
        self._PixmapUpdateTime = 100

        self.m_GlobalReSetKey = None
        self.m_GlobalAEJumpKey_Press = None
        self.m_GlobalAEJumpKey_Release = None
        self.m_AEJump_Flag = False
        self.m_Cache = []

        self.setup_ui()
        self.load_pet()
        self.load_timer()
        self.show()
        core_event.BindEvent("RELOAD_PET_RES", self.load_pet, self)
        core_event.BindEvent("RELOAD_TIMER", self.load_timer, self)
        core_event.BindEvent("REOPEN_MENU", self.ReOpenMenu, self)

        core_voice.Speak(f"欢迎使用星河定时器！")

    def update_pet_param(self):
        data = core_save.LoadJson(Path_Setting)
        icon_size = data.get(SettingName.PetIconSize, 72)
        self._PixmapUpdateTime = data.get(SettingName.PetIconUpdateTime, 100)
        self._PixmapSize = icon_size
        w, h = icon_size, icon_size
        icon_pos = data.get(SettingName.PetIconPos, None)

        # 最小区域
        min_point = QPoint()
        max_point = QPoint()
        screens = QGuiApplication.screens()
        for screen in screens:
            screen: "QScreen"
            rect = screen.geometry()
            if rect.x() < min_point.x():
                min_point.setX(rect.x())
            if rect.y() < min_point.y():
                min_point.setY(rect.y())

            p = rect.bottomRight()
            if p.x() > max_point.x():
                max_point.setX(p.x())
            if p.y() > max_point.y():
                max_point.setY(p.y())
        if icon_pos:
            print("存在存档位置：", icon_pos)
            print("屏幕最小位置：", min_point.toTuple())
            print("屏幕最大位置：", max_point.toTuple())
            minx, miny = min_point.toTuple()
            maxx, maxy = max_point.toTuple()
            savex, savey = icon_pos

            if savex < minx or savey < savey:
                icon_pos = None
            if savex > maxx or savey > maxy:
                icon_pos = None
        if not icon_pos:
            size = QApplication.primaryScreen().size()
            screen_w, screen_h = size.width(), size.height()
            x, y = screen_w - w * 1.5, screen_h - h * 1.5
        else:
            x, y = icon_pos
        self.setGeometry(x, y, w, h)

    def setup_ui(self):
        from widgets.common import setTheme
        from widgets.common import Theme
        setTheme(Theme.LIGHT)
        self.setWindowTitle("GalaxyTimer")

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SubWindow)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        mini_icon = QSystemTrayIcon(self)
        mini_icon.setIcon(QIcon(Path_Icon))
        quit_menu = QAction('退出', self, triggered=self.quit)
        tpMenu = QMenu(self)
        tpMenu.addAction(quit_menu)
        mini_icon.setContextMenu(tpMenu)
        mini_icon.show()

    def load_pet(self):
        self.m_Pets.clear()
        self.m_CurPet = None
        data = core_save.LoadJson(Path_Setting)
        default_pet = data.get(SettingName.DefaultPetRes, "")
        # 遍历宠物文件夹
        for sPath in os.listdir(Path_PetRoot):
            sCurPath = os.path.join(Path_PetRoot, sPath)
            if not os.path.isdir(sCurPath):
                continue
            print("加载宠物资源目录：", sPath)
            petRes = PetRes()
            petRes.LoadRes(sPath)
            if not petRes.HasRes():
                continue
            if not default_pet:
                default_pet = sPath
                data[SettingName.DefaultPetRes] = sPath
                core_save.SaveJson(Path_Setting, data)
            if default_pet == sPath:
                self.m_CurPet = petRes
            self.m_Pets.append(petRes)
        if not self.m_CurPet and self.m_Pets:
            self.m_CurPet = self.m_Pets[0]
        if self.m_CurPet:
            print("当前宠物：", self.m_CurPet)
            self.update_pet_param()
            self.refresh_cur_pet()
        else:
            self.quit()

    def refresh_cur_pet(self):
        self.update_pixmap()
        self.m_PetUpdateTimer = None
        if self.m_CurPet.IsNeedUpdate():
            self.m_PetUpdateTimer = core_timer.CreateAlwaysTimer(self._PixmapUpdateTime, self.update_pixmap)

    def load_timer(self):
        # -------------------- 分组
        self.m_AllGroup.clear()
        data = core_save.LoadJson(Path_Group)
        self.m_UuidGroup = 0

        group = {}
        for uid, timer_data in data.items():
            uid = int(uid)
            if self.m_UuidGroup <= uid:
                self.m_UuidGroup = uid + 1
            group[uid] = timer_data

        for uid, group_data in group.items():
            groupProxy = GroupProxy(uid, group_data)
            self.m_AllGroup[uid] = groupProxy

        # -------------------- 定时器
        self.m_AllTimer.clear()
        data = core_save.LoadJson(Path_Timer)
        timer = {}
        self.m_Uuid = 0

        for uid, timer_data in data.items():
            uid = int(uid)
            if self.m_Uuid <= uid:
                self.m_Uuid = uid + 1
            timer[uid] = timer_data
        # core_save.SaveJson(Path_Timer, timer)
        for uid, timer_data in timer.items():
            timeProxy = TimerProxy(uid, timer_data)
            self.m_AllTimer[uid] = timeProxy
            if timeProxy.m_groupId in self.m_AllGroup:
                self.m_AllGroup[timeProxy.m_groupId].m_lTimer.append(weakref.proxy(timeProxy))

        self.register_reset_hotkey()

    def register_reset_hotkey(self):
        # 全局重置
        data = core_save.LoadJson(Path_Setting)
        self.m_GlobalReSetKey = core_input.RegisterHotKey(data.get(SettingName.TimerReset, ["F2"]), self.reset_timer)

    def reset_timer(self):
        for timer in self.m_AllTimer.values():
            timer.Reset()
        core_voice.Speak(f"重置所有定时器！")

    def update_pixmap(self):
        self._Pixmap = QPixmap()
        self._Pixmap.load(self.m_CurPet.GetNextRes())
        self._Pixmap = self._Pixmap.scaled(QSize(self._PixmapSize, self._PixmapSize))
        self.setPixmap(self._Pixmap)

    def mousePressEvent(self, QMouseEvent):
        self.pos_first = None
        if QMouseEvent.button() == Qt.MouseButton.LeftButton:
            self.pos_first = QMouseEvent.globalPos() - self.pos()
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().mousePressEvent(QMouseEvent)

    def mouseMoveEvent(self, QMouseEvent):
        super().mouseMoveEvent(QMouseEvent)
        if not self.pos_first:
            return
        if Qt.MouseButton.LeftButton:
            self.move(QMouseEvent.globalPos() - self.pos_first)
            self.x, self.y = self.pos().toTuple()

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        if e.button() == Qt.MouseButton.RightButton:
            self.OpenMenu(e.globalPos())
            return
        if e.button() == Qt.MouseButton.LeftButton:
            if not self.pos_first:
                return
            data = core_save.LoadJson(Path_Setting)
            data[SettingName.PetIconPos] = [self.x, self.y]
            core_save.SaveJson(Path_Setting, data)

    def OpenMenu(self, pos):
        self.re_open_func = CFunctor(self.OpenMenu, pos)
        menu = RoundMenu(parent=self)
        newAction = Action(FIF.PENCIL_INK, '添加定时器')
        newAction.triggered.connect(self._on_new_timer)
        newAction.click_no_close = True
        menu.addAction(newAction)

        newAction = Action(FIF.PENCIL_INK, '添加分组')
        newAction.triggered.connect(self._on_new_group)
        newAction.click_no_close = True
        menu.addAction(newAction)

        # choose res
        submenu = RoundMenu("宠物资源", self)
        submenu.setIcon(FIF.ROBOT)
        for pet_res in self.m_Pets:
            _action = Action(pet_res.m_ResName)
            _action.triggered.connect(CFunctor(self._on_choose_pet, pet_res))
            submenu.addAction(_action)
        menu.addMenu(submenu)

        submenu = RoundMenu("语音播报", self)
        submenu.setIcon(FIF.VOLUME)
        voice_menu = Voice_Menu()
        submenu.addWidget(voice_menu)
        menu.addMenu(submenu)

        submenu = RoundMenu("其他设置", self)
        submenu.setIcon(FIF.SETTING)
        setting_menu = Setting_Menu(self)
        submenu.addWidget(setting_menu)
        menu.addMenu(submenu)

        submenu = RoundMenu("帮助信息", self)
        submenu.setIcon(FIF.INFO)
        help_info = Help_Info()
        submenu.addWidget(help_info)
        menu.addMenu(submenu)

        menu.addSeparator()

        # add actions
        for timeProxy in self.m_AllTimer.values():
            timeProxy: "TimerProxy"
            if timeProxy.m_groupId in self.m_AllGroup:
                continue
            submenu = RoundMenu(timeProxy.m_sName, self)
            submenu.setIcon(FIF.STOP_WATCH)
            timermenu = Timer_Menu(timeProxy, CFunctor(submenu.DeepClose), CFunctor(self._on_del_timer))
            submenu.addWidget(timermenu)
            menu.addMenu(submenu)
        for group in self.m_AllGroup.values():
            menu.addSeparator()
            sName = f"{group.m_sName}----{'开启' if group.m_bOpen else '关闭'}"
            groupMenu = RoundMenu(sName, self)
            # groupMenu.setIcon(FIF.FOLDER)
            menu.addMenu(groupMenu)

            groupMenu.addWidget(Group_Menu(group, CFunctor(groupMenu.DeepClose), CFunctor(self._on_del_group)))

            for timeProxy in group.m_lTimer:
                timeProxy: "TimerProxy"
                timeProxy = self.m_AllTimer[timeProxy.m_uuid]
                timerMenu = RoundMenu(timeProxy.m_sName, self)
                timerMenu.setIcon(FIF.STOP_WATCH)
                timerSetting = Timer_Menu(timeProxy, CFunctor(timerMenu.DeepClose), CFunctor(self._on_del_timer))
                timerMenu.addWidget(timerSetting)
                menu.addMenu(timerMenu)
        menu.addSeparator()
        newAction = Action(FIF.CLOSE, '关闭')
        newAction.triggered.connect(self.quit)
        menu.addAction(newAction)

        # show menu
        menu.exec(pos, ani=False)

    # region menu callback
    def _on_new_timer(self):
        self.m_Uuid += 1
        x, y = QCursor.pos().toTuple()
        timer = TimerProxy(str(self.m_Uuid), {"tPos":(x, y), "sPic":"icon.png", "bOpen":True}  )
        timer.Save()
        self.m_AllTimer[timer.m_uuid] = timer
        if self.re_open_func:
            self.re_open_func()

    def ReOpenMenu(self):
        if self.re_open_func:
            self.re_open_func()

    def _on_new_group(self):
        self.m_UuidGroup += 1
        group = GroupProxy(str(self.m_UuidGroup), {})
        group.Save()
        self.m_AllGroup[group.m_uuid] = group
        if self.re_open_func:
            self.re_open_func()

    def _on_choose_pet(self, pet):
        self.m_CurPet = pet
        self.m_CurPet.m_CurResIndex = 1
        self.refresh_cur_pet()
        data = core_save.LoadJson(Path_Setting)
        data[SettingName.DefaultPetRes] = pet.m_ResName
        core_save.SaveJson(Path_Setting, data)
        print("切换宠物：", pet)

    def _on_del_timer(self, index):
        try:
            index = str(index)
            data = core_save.LoadJson(Path_Timer)

            if index not in data:
                return
            del data[index]
            core_save.SaveJson(Path_Timer, data)
            self.load_timer()
        except IOError as e:
            print("删除定时器报错：", e)
            pass

    def _on_del_group(self, uid):
        uid = int(uid)
        try:
            key = str(uid)
            data = core_save.LoadJson(Path_Group)
            if key not in data:
                print("没有这个分组!!")
                return
            del data[key]
            core_save.SaveJson(Path_Group, data)
            delGroup = self.m_AllGroup.get(uid, None)
            print("当前分组定时器:", delGroup, self.m_AllGroup)
            if delGroup:
                data = core_save.LoadJson(Path_Timer)
                for timer in delGroup.m_lTimer:
                    print("删除组内定时器:", timer.m_uuid, timer.m_sName)
                    key = str(timer.m_uuid)
                    if key not in data:
                        continue
                    print("-----删除组内定时器:", timer.m_uuid, timer.m_sName)
                    del data[key]
                core_save.SaveJson(Path_Timer, data)
            self.load_timer()
        except IOError as e:
            print("删除定时器报错：", e)
            pass


    # endregion

    def quit(self):
        self.close()
        sys.exit()
