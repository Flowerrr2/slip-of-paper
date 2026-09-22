import os
import sys
from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox

from .store import Store, now
from .ui import NoteWindow, icon, STYLE
from .manager import Manager, Capture, Settings
from .platform import Hotkeys


WELCOME = '''嘿，这是一张便签。

直接写点东西，留住一闪而过的想法。

☐ 拖动顶部，换个位置
☐ 点点圆圈，换张彩纸
☐ 双击顶部，把纸片收起来

Ctrl + Alt + N
随时拿一张新纸。'''


class Controller:
    def __init__(self,app,store=None,background=False,testing=False):
        self.app=app
        self.store=store or Store()
        self.windows={}
        self.last_deleted=None
        self.hidden_batch=set()
        self.quitting=False
        self.testing=testing
        self.manager=Manager(self)
        self.capture_window=Capture(self)
        self.tray=QSystemTrayIcon(icon(),app)
        self.tray.setToolTip('小纸片 · 随手记下来')
        menu=QMenu()
        menu.addAction('＋  新建便签',lambda:self.create())
        menu.addAction('随手记',self.capture)
        menu.addAction('搜索便签',self.search)
        menu.addAction('所有便签',self.show_manager)
        menu.addSeparator()
        menu.addAction('显示全部',self.show_all)
        menu.addAction('隐藏全部',self.hide_all)
        menu.addSeparator()
        menu.addAction('偏好设置',self.show_settings)
        menu.addAction('退出小纸片',self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        # A delay distinguishes a single click from a double click on the tray.
        self.tray_click=QTimer(app)
        self.tray_click.setSingleShot(True)
        self.tray_click.setInterval(app.doubleClickInterval())
        self.tray_click.timeout.connect(self.show_manager)
        self.hotkeys=Hotkeys({'new':lambda:self.create(),'capture':self.capture,'search':self.search,
                             'hide':self.toggle_all,'paste':self.paste})
        if not testing:
            app.installNativeEventFilter(self.hotkeys)
            try:
                self.hotkeys.apply(self.store.settings['hotkeys'])
            except ValueError as error:
                message=str(error)
                QTimer.singleShot(800,lambda:self.error(message))
            self.tray.show()
        first=not self.store.get_meta('onboarded',False)
        if first:
            welcome=self.store.new(WELCOME)
            welcome['height']=430
            welcome['width']=350
            self.store.save(welcome)
            self.store.set_meta('onboarded',True)
        startup=self.store.settings['startup']
        for n in self.store.all():
            if n['deleted_at'] or n['archived']:
                continue
            if startup=='显示所有便签' or (startup=='保持上次状态' and not n['hidden']):
                self.open_note(n['id'],focus=False)
        if not background:
            self.show_manager()
        if self.store.was_unclean:
            self.toast('已从本地记录恢复纸片。上次程序未正常退出。')
        self.backup_timer=QTimer(app)
        self.backup_timer.setInterval(60*60*1000)
        self.backup_timer.timeout.connect(self.maintenance)
        self.backup_timer.start()
        app.aboutToQuit.connect(self.cleanup)

    def refresh(self):
        self.manager.schedule()

    def create(self,plain=''):
        n=self.store.new(plain)
        self.open_note(n['id'])
        self.refresh()
        return n['id']

    def open_note(self,note_id,focus=True):
        note=self.store.get(note_id)
        if not note or note['deleted_at']:
            return
        if note_id in self.windows:
            w=self.windows[note_id]
        else:
            w=NoteWindow(self,note)
            self.windows[note_id]=w
        w.note.update(hidden=False,archived=False)
        w.show()
        w.flush()
        if focus:
            if w.note['collapsed']:
                w.set_collapsed(False)
            w.raise_()
            w.activateWindow()
            w.editor.setFocus()

    def retire(self,note_id):
        w=self.windows.pop(note_id,None)
        if w:
            w.flush()
            w.timer.stop()
            w.ready=False
            w.hide()
            w.deleteLater()

    def trash(self,note_id):
        self.retire(note_id)
        note=self.store.get(note_id)
        if not note: return
        self.last_deleted=note_id
        note['deleted_at']=now()
        self.store.save(note)
        self.refresh()
        self.toast('便签已丢进废纸篓，30 天内可以捡回来。',True)

    def undo_trash(self):
        if self.last_deleted:
            self.restore(self.last_deleted)
            self.last_deleted=None
            self.manager.notice.hide()

    def restore(self,note_id):
        note=self.store.get(note_id)
        if note:
            note.update(deleted_at=None,archived=False,hidden=False)
            self.store.save(note)
            self.open_note(note_id)
            self.refresh()

    def permanent_delete(self,note_id):
        answer=QMessageBox.question(self.manager,'让这张纸片离开？','永久删除后无法从废纸篓恢复。',
                                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer==QMessageBox.Yes:
            self.store.delete_forever(note_id)
            self.refresh()

    def archive(self,note_id):
        self.retire(note_id)
        note=self.store.get(note_id)
        if note:
            note.update(archived=True,hidden=True)
            self.store.save(note)
            self.refresh()
            self.toast('已收进抽屉。需要时，在「已归档」中找到它。')

    def favorite(self,note_id):
        if note_id in self.windows:
            self.windows[note_id].favorite()
        else:
            note=self.store.get(note_id)
            note['favorite']=not note['favorite']
            self.store.save(note)
        self.refresh()

    def show_manager(self):
        self.manager.render()
        self.manager.showNormal()
        self.manager.raise_()
        self.manager.activateWindow()

    def search(self):
        self.show_manager()
        self.manager.select('所有便签')
        self.manager.search.setFocus()
        self.manager.search.selectAll()

    def show_settings(self):
        self.show_manager()
        Settings(self).exec()

    def capture(self):
        self.capture_window.show()
        self.capture_window.raise_()
        self.capture_window.activateWindow()
        self.capture_window.editor.setFocus()

    def paste(self):
        text=self.app.clipboard().text()
        if text.strip():
            self.create(text)
        else:
            self.toast('剪贴板里还没有文字。')

    def hide_all(self):
        self.hidden_batch={key for key,w in self.windows.items() if w.isVisible()}
        for key in list(self.hidden_batch):
            self.windows[key].hide_note()

    def show_all(self):
        for n in self.store.all():
            if not n['deleted_at'] and not n['archived']:
                self.open_note(n['id'],focus=False)
        self.hidden_batch.clear()

    def toggle_all(self):
        if any(w.isVisible() for w in self.windows.values()):
            self.hide_all()
        elif self.hidden_batch:
            for key in self.hidden_batch:
                self.open_note(key,focus=False)
            self.hidden_batch.clear()
        else:
            self.show_all()

    def toast(self,text,undo=False):
        self.manager.toast(text,undo)
        if not self.manager.isVisible() and not self.testing:
            self.tray.showMessage('小纸片',text,QSystemTrayIcon.Information,3000)

    def error(self,text):
        QMessageBox.warning(self.manager,'小纸片',text)

    def tray_activated(self,reason):
        if reason==QSystemTrayIcon.DoubleClick:
            self.tray_click.stop()
            self.create()
        elif reason==QSystemTrayIcon.Trigger:
            self.tray_click.start()

    def flush_all(self):
        for w in list(self.windows.values()):
            w.flush()

    def maintenance(self):
        try:
            self.store.daily_backup(force=True)
            self.store.prune_trash()
        except Exception as error:
            self.toast('自动备份未完成：'+str(error))

    def cleanup(self):
        if self.quitting: return
        self.quitting=True
        self.backup_timer.stop()
        self.flush_all()
        # Preserve an unfinished capture draft even during a normal exit.
        if self.capture_window.editor.toPlainText().strip():
            self.capture_window.capture()
        self.capture_window.draft_timer.stop()
        for w in self.windows.values():
            w.timer.stop()
            w.ready=False
            w.hide()
        self.hotkeys.clear()
        self.tray.hide()
        self.store.daily_backup(force=True)
        self.store.close()

    def quit(self):
        self.cleanup()
        self.app.quit()


def create_application():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('LittlePaper')
    app.setApplicationDisplayName('小纸片')
    app.setOrganizationName('LittlePaper')
    app.setQuitOnLastWindowClosed(False)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setWindowIcon(icon())
    return app
