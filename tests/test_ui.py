import ctypes
import tempfile
import unittest
from pathlib import Path
from time import time

from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QTextCursor, QWheelEvent
from PySide6.QtTest import QTest

from stickies.app import Controller,create_application
from stickies.manager import CARDS_PER_BATCH, Card, ReminderDialog, Settings
from stickies.platform import Hotkeys,parse_hotkey
from stickies.store import Store


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=create_application()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name)
        self.store.set_meta('onboarded',True)
        self.c=Controller(self.app,self.store,testing=True)
        self.app.processEvents()

    def tearDown(self):
        self.c.cleanup()
        self.c.manager.refresh_timer.stop()
        self.c.manager.hide()
        self.c.manager.deleteLater()
        self.c.capture_window.hide()
        self.c.capture_window.deleteLater()
        for w in self.c.windows.values():
            w.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def test_edit_debounce_and_close_flush(self):
        ident=self.c.create()
        w=self.c.windows[ident]
        w.editor.setPlainText('灵感 📝\n按时交付')
        QTest.qWait(500)
        self.assertEqual(self.store.get(ident)['plain'],'灵感 📝\n按时交付')
        w.editor.insertPlainText('最后一笔')
        w.hide_note()
        self.assertIn('最后一笔',self.store.get(ident)['plain'])
        self.assertTrue(self.store.get(ident)['hidden'])

    def test_todo_input_toggle_and_enter(self):
        ident=self.c.create()
        e=self.c.windows[ident].editor
        QTest.keyClicks(e,'[] ')
        QTest.keyClicks(e,'coffee')
        self.assertEqual(e.toPlainText(),'☐ coffee')
        e.toggle_todo(True)
        self.assertEqual(e.toPlainText(),'☑ coffee')
        QTest.keyClick(e,Qt.Key_Return)
        self.assertEqual(e.toPlainText(),'☑ coffee\n☐ ')
        QTest.keyClick(e,Qt.Key_Return)
        self.assertEqual(e.toPlainText(),'☑ coffee\n')

    def test_heading_and_plain_next_line(self):
        ident=self.c.create()
        e=self.c.windows[ident].editor
        QTest.keyClicks(e,'# Idea')
        self.assertEqual(e.textCursor().blockFormat().headingLevel(),2)
        QTest.keyClick(e,Qt.Key_Return)
        QTest.keyClicks(e,'body')
        self.assertEqual(e.textCursor().blockFormat().headingLevel(),0)
        self.assertEqual(e.toPlainText(),'Idea\nbody')

    def test_collapse_geometry_and_colors(self):
        ident=self.c.create('纸片')
        w=self.c.windows[ident]
        w.resize(380,360)
        w.flush()
        w.collapse()
        self.assertEqual(w.height(),52)
        self.assertEqual(self.store.get(ident)['height'],360)
        w.collapse()
        self.assertEqual(w.height(),360)
        w.set_color('夜色')
        w.pin()
        self.assertTrue(self.store.get(ident)['pinned'])
        self.assertEqual(self.store.get(ident)['color'],'夜色')

    def test_delete_restore_and_archive_last_edit(self):
        ident=self.c.create('初稿')
        self.c.windows[ident].editor.setPlainText('最后修改')
        self.c.trash(ident)
        self.assertEqual(self.store.get(ident)['plain'],'最后修改')
        self.assertIsNotNone(self.store.get(ident)['deleted_at'])
        self.c.undo_trash()
        self.assertIsNone(self.store.get(ident)['deleted_at'])
        self.assertTrue(self.c.windows[ident].isVisible())
        self.c.archive(ident)
        self.assertTrue(self.store.get(ident)['archived'])
        self.c.open_note(ident)
        self.assertFalse(self.store.get(ident)['archived'])

    def test_search_filters_and_favorite_sync(self):
        first=self.c.create('咖啡豆\n☐ buy coffee')
        second=self.c.create('项目灵感\n翻转动画')
        self.c.favorite(second)
        self.assertTrue(self.c.windows[second].note['favorite'])
        self.c.manager.search.setText('COFFEE')
        self.c.manager.render()
        cards=self.c.manager.scroll.widget().findChildren(Card)
        self.assertEqual(len(cards),1)
        self.assertEqual(cards[0].note['id'],first)
        self.c.manager.select('收藏')
        self.assertEqual(len(self.c.manager.scroll.widget().findChildren(Card)),1)

    def test_search_excerpt_and_keyboard_navigation_use_current_results(self):
        first = self.c.create('第一张\n会议准备 coffee')
        second = self.c.create('第二张\ncoffee 采购')
        self.c.favorite(first)
        self.c.windows[first].hide_note()
        self.c.archive(second)
        manager = self.c.manager
        manager.search.setText('COFFEE')
        QTest.keyClick(manager.search, Qt.Key_Down)
        self.assertTrue(manager.result_cards[0].selected)
        self.assertEqual(manager.result_cards[0].note['id'], first)
        self.assertIn('会议准备 coffee', manager.result_cards[0].match_text)
        QTest.keyClick(manager.search, Qt.Key_Down)
        QTest.keyClick(manager.search, Qt.Key_Return)
        self.assertTrue(self.c.windows[second].isVisible())
        self.assertFalse(self.store.get(second)['archived'])
        self.assertFalse(self.c.windows[first].isVisible())

    def test_drawer_loads_more_cards_when_scrolling(self):
        for i in range(CARDS_PER_BATCH + 5):
            self.store.new(f'纸片 {i}')
        manager = self.c.manager
        manager.render()
        self.app.processEvents()
        self.assertEqual(len(manager.result_cards), CARDS_PER_BATCH)
        scrollbar = manager.scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.assertEqual(len(manager.result_cards), CARDS_PER_BATCH + 5)

    def test_reminder_updates_open_editor_and_opens_note_on_notification(self):
        ident = self.c.create('提醒')
        window = self.c.windows[ident]
        window.editor.setPlainText('未保存的文字')
        self.c.set_reminder(ident, int(time()) - 1)
        self.c.check_reminders()
        self.assertTrue(window.note['reminder_ready'])
        window.editor.insertPlainText('还在编辑')
        window.hide_note()
        self.assertTrue(self.store.get(ident)['reminder_ready'])
        self.c.open_reminder_notification()
        self.assertTrue(window.isVisible())
        self.assertNotIn('reminder_at', self.store.get(ident))
        self.assertIn('还在编辑', self.store.get(ident)['plain'])

    def test_archived_and_trashed_reminders(self):
        first = self.c.create('归档一')
        second = self.c.create('归档二')
        trashed = self.c.create('删除')
        for ident in (first, second, trashed):
            self.c.set_reminder(ident, int(time()) - 1)
        self.c.archive(first)
        self.c.archive(second)
        self.c.trash(trashed)
        self.c.undo_trash()
        self.c.check_reminders()
        self.c.open_reminder_notification()
        self.assertEqual(self.c.manager.mode, '提醒')
        self.assertEqual({note['id'] for note, _ in self.c.manager.result_notes}, {first, second})
        self.assertNotIn('reminder_at', self.store.get(trashed))
        self.assertTrue(self.store.get(first)['archived'])
        self.c.open_note(first)
        self.assertNotIn('reminder_at', self.store.get(first))

    def test_reminder_dialog_saves_and_removes_reminder(self):
        ident = self.c.create('提醒设置')
        dialog = ReminderDialog(self.store.get(ident), self.c.manager)
        dialog.save_time()
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)
        self.assertGreater(dialog.timestamp, int(time()))
        self.c.set_reminder(ident, dialog.timestamp)
        dialog = ReminderDialog(self.store.get(ident), self.c.manager)
        self.assertEqual(dialog.when.dateTime().toSecsSinceEpoch(), self.store.get(ident)['reminder_at'])
        self.c.set_reminder(ident, None)
        self.assertNotIn('reminder_at', self.store.get(ident))

    def test_boss_key_restores_only_previously_visible_notes(self):
        a=self.c.create('A')
        b=self.c.create('B')
        self.c.windows[b].hide_note()
        self.c.toggle_all()
        self.assertFalse(self.c.windows[a].isVisible())
        self.c.toggle_all()
        self.assertTrue(self.c.windows[a].isVisible())
        self.assertFalse(self.c.windows[b].isVisible())

    def test_capture_and_settings_build(self):
        self.c.capture_window.editor.setPlainText('随手捕获')
        self.c.capture_window.capture()
        note=self.store.all()[0]
        self.assertEqual(note['plain'],'随手捕获')
        self.assertTrue(note['hidden'])
        self.assertEqual(self.c.capture_window.editor.toPlainText(),'')
        settings=Settings(self.c)
        self.assertEqual(len(settings.hotkey_fields),5)
        settings.deleteLater()

    def test_font_size_persists_for_existing_text(self):
        ident=self.c.create('existing text')
        w=self.c.windows[ident]
        w.font_size(2)
        cur=w.editor.textCursor()
        cur.movePosition(QTextCursor.Start)
        cur.movePosition(QTextCursor.Right,QTextCursor.KeepAnchor)
        self.assertEqual(cur.charFormat().fontPointSize(),16)
        self.assertEqual(self.store.get(ident)['font_size'],16)
        self.app.processEvents()
        rules=w.editor.rule_positions()
        self.c.retire(ident)
        self.c.open_note(ident)
        self.app.processEvents()
        restored=self.c.windows[ident]
        self.assertEqual(restored.editor.toPlainText(),'existing text')
        self.assertEqual(restored.editor.rule_positions(),rules)

    def test_hover_fade_does_not_move_body(self):
        ident=self.c.create('line one\nline two')
        w=self.c.windows[ident]
        self.app.processEvents()
        before=w.editor.geometry()
        rules=w.editor.rule_positions()
        for visible in (False,True,False):
            w.set_tools_visible(visible)
            QTest.qWait(200)
            self.assertEqual(w.editor.geometry(),before)
            self.assertEqual(w.editor.rule_positions(),rules)
            self.assertFalse(w.tools.isHidden())
            self.assertAlmostEqual(w.tools_opacity.opacity(),float(visible),places=2)
            self.assertEqual(w.tools.isEnabled(),visible)

    def send_wheel(self,target,angle=120,ctrl=True,pixels=0):
        point=QPointF(10,10)
        event=QWheelEvent(point,QPointF(target.mapToGlobal(QPoint(10,10))),QPoint(0,pixels),
                          QPoint(0,angle),Qt.NoButton,Qt.ControlModifier if ctrl else Qt.NoModifier,
                          Qt.NoScrollPhase,False)
        self.app.sendEvent(target,event)
        self.app.processEvents()

    def test_ctrl_wheel_over_unfocused_note_and_toolbar(self):
        ident=self.c.create('first\nsecond')
        w=self.c.windows[ident]
        self.c.create('another window has focus')
        self.send_wheel(w.editor.viewport())
        self.assertEqual(w.note['font_size'],15)
        self.send_wheel(w.bar,angle=-120)
        self.assertEqual(w.note['font_size'],14)
        self.send_wheel(w.editor.viewport(),angle=60)
        self.assertEqual(w.note['font_size'],14)
        self.send_wheel(w.editor.viewport(),angle=60)
        self.assertEqual(w.note['font_size'],15)
        self.send_wheel(w.editor.viewport(),angle=0,pixels=40)
        self.assertEqual(w.note['font_size'],16)
        self.send_wheel(w.editor.viewport(),ctrl=False)
        self.assertEqual(w.note['font_size'],16)
        self.assertEqual(self.store.get(ident)['font_size'],16)

    def test_rules_follow_font_wraps_and_scrolling(self):
        ident=self.c.create(('A long sentence that will wrap across several lines. '*3+'\n')*15)
        w=self.c.windows[ident]
        for size in (10,18,32):
            w.font_size(size-w.note['font_size'])
            self.app.processEvents()
            for scroll in (0,37,120):
                w.editor.verticalScrollBar().setValue(scroll)
                self.app.processEvents()
                actual=w.editor.rule_positions()
                self.assertGreater(len(actual),1)
                block=w.editor.document().begin()
                expected=[]
                while block.isValid():
                    top=w.editor.document().documentLayout().blockBoundingRect(block).top()
                    for i in range(block.layout().lineCount()):
                        line=block.layout().lineAt(i)
                        y=top+line.y()+line.ascent()+2-w.editor.verticalScrollBar().value()
                        if 0<=y<=w.editor.viewport().height(): expected.append(y)
                    block=block.next()
                self.assertEqual(actual,expected)
        self.assertEqual(w.note['font_size'],32)
        self.send_wheel(w.editor.viewport())
        self.assertEqual(w.note['font_size'],32)

    def test_capture_draft_saved_when_dismissed(self):
        self.c.capture_window.editor.setPlainText('未提交的想法')
        self.c.capture_window.reject()
        self.assertIn('未提交的想法',self.store.get_meta('capture_draft'))

    def test_search_includes_archived_notes(self):
        ident=self.c.create('archive keyword')
        self.c.archive(ident)
        self.c.manager.search.setText('keyword')
        self.c.manager.render()
        self.assertEqual(len(self.c.manager.scroll.widget().findChildren(Card)),1)

    def test_offscreen_geometry_is_clamped(self):
        note=self.store.new('丢失显示器')
        note.update(x=-99999,y=-99999,screen_id='disconnected',width=360,height=300)
        self.store.save(note)
        self.c.open_note(note['id'])
        w=self.c.windows[note['id']]
        self.assertTrue(w.screen().availableGeometry().contains(w.geometry()))

    def test_native_hotkey_dispatch_and_conflict(self):
        called=[]
        hotkeys=Hotkeys({'new':lambda:called.append('new')})
        self.app.installNativeEventFilter(hotkeys)
        try:
            hotkeys.apply({'new':'Ctrl+Alt+Shift+F11'})
            ident=next(iter(hotkeys.registered))
            thread=ctypes.windll.kernel32.GetCurrentThreadId()
            ctypes.windll.user32.PostThreadMessageW(thread,0x0312,ident,0)
            QTest.qWait(30)
            self.assertEqual(called,['new'])
            with self.assertRaises(ValueError):
                parse_hotkey('N')
            with self.assertRaises(ValueError):
                hotkeys.apply({'new':'Ctrl+Alt+N','hide':'Ctrl+Alt+N'})
        finally:
            hotkeys.clear()
            self.app.removeNativeEventFilter(hotkeys)


if __name__=='__main__':
    unittest.main()
