from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, QSize, QDateTime, QTime, QEvent, QRectF
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QPainter, QColor, QPen, QFontMetrics, QTextCharFormat
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QScrollArea, QFrame, QDialog, QTabWidget, QFormLayout, QComboBox,
    QSpinBox, QCheckBox, QKeySequenceEdit, QFileDialog, QMessageBox, QInputDialog,
    QDateTimeEdit, QCalendarWidget)

from . import __version__
from .store import COLORS, title, pending
from .ui import label, button, Paper, Editor, icon
from .icons import IconButton, line_icon
from .platform import HOTKEY_NAMES, autostart_enabled, set_autostart


CARDS_PER_BATCH = 24


def search_excerpt(note, query):
    tags = ' '.join(note['tags'])
    fields = [('标题', title(note)), ('正文', note['plain']), ('标签', tags)]
    combined = ' '.join(text for _, text in fields)
    if query not in combined.casefold():
        return ''
    for field, text in fields + [('内容', combined)]:
        folded = text.casefold()
        offset = folded.find(query)
        if offset < 0:
            continue
        if len(text) != len(folded):
            for index, character in enumerate(text):
                if offset < len(character.casefold()):
                    offset = index
                    break
                offset -= len(character.casefold())
        start = max(0, offset - 12)
        excerpt = ' '.join(text[start:offset + len(query) + 48].split())
        return f'{field} · ' + ('…' if start else '') + excerpt
    return ''


class Card(Paper):
    def __init__(self,controller,note,mode,match=''):
        super().__init__(note['color'],'经典')
        self.controller, self.note=controller,note
        self.selected = False
        self.setMinimumHeight(230)
        self.setMaximumHeight(260)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('双击打开这张纸片')
        layout=QVBoxLayout(self)
        layout.setContentsMargins(20,16,16,10)
        top=QHBoxLayout()
        foreground='#F5F3E9' if note['color']=='夜色' else '#283044'
        heading=label(title(note),17,foreground,True)
        heading.setWordWrap(True)
        heading.setMaximumHeight(46)
        top.addWidget(heading,1)
        if mode != '回收站':
            star=IconButton('star',lambda:controller.favorite(note['id']),'取消收藏' if note['favorite'] else '收藏',dark=note['color']=='夜色')
            star.setCheckable(True)
            star.setChecked(note['favorite'])
            top.addWidget(star)
        layout.addLayout(top)
        lines=note['plain'].splitlines()
        if lines and not note['title']:
            lines=lines[1:]
        preview=label('\n'.join(lines)[:200] or '留一点空白，等下一个想法。',13,foreground)
        preview.setTextFormat(Qt.PlainText)
        preview.setWordWrap(True)
        preview.setAlignment(Qt.AlignTop)
        preview.setMaximumHeight(96)
        layout.addWidget(preview,1)
        if match:
            self.match = label('', 11, foreground)
            self.match.setMinimumWidth(0)
            self.match.setToolTip(match)
            self.match_text = match
            layout.addWidget(self.match)
        tags='  '.join('#'+t for t in note['tags'])
        meta=label((tags[:32]+'   ' if tags else '') + (f'☐ {pending(note)} 项待办' if pending(note) else ''),10,foreground)
        layout.addWidget(meta)
        foot=QHBoxLayout()
        foot.setSpacing(6)
        foot.addWidget(label(datetime.fromisoformat(note['updated_at']).strftime('%m 月 %d 日'),10,foreground))
        foot.addStretch()
        if not note['deleted_at']:
            reminder = '修改提醒' if note.get('reminder_at') else '设置提醒'
            clock = IconButton('clock', lambda: controller.edit_reminder(note['id'], controller.manager),
                               reminder, dark=note['color']=='夜色')
            if note.get('reminder_at'):
                clock.setCheckable(True)
                clock.setChecked(True)
                when = QDateTime.fromSecsSinceEpoch(note['reminder_at']).toString('M 月 d 日 HH:mm')
                status = '待查看' if note.get('reminder_ready') else when
                layout.addWidget(label('提醒 · ' + status, 11, foreground))
                clock.setToolTip(f'{reminder} · {status}')
            foot.addWidget(clock)
        if note['deleted_at']:
            foot.addWidget(button('恢复',lambda:controller.restore(note['id'])))
            remove=button('永久删除',lambda:controller.permanent_delete(note['id']))
            remove.setObjectName('danger')
            foot.addWidget(remove)
        elif note['archived']:
            foot.addWidget(button('放回桌面',lambda:controller.open_note(note['id'])))
            foot.addWidget(IconButton('trash',lambda:controller.trash(note['id']),'丢进废纸篓',danger=True,dark=note['color']=='夜色'))
        else:
            foot.addWidget(IconButton('open',lambda:controller.open_note(note['id']),'打开便签',dark=note['color']=='夜色'))
            foot.addWidget(IconButton('archive',lambda:controller.archive(note['id']),'收进抽屉',dark=note['color']=='夜色'))
            foot.addWidget(IconButton('trash',lambda:controller.trash(note['id']),'丢进废纸篓',danger=True,dark=note['color']=='夜色'))
        layout.addLayout(foot)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'match'):
            width = self.width() - 36
            self.match.setText(QFontMetrics(self.match.font()).elidedText(
                self.match_text, Qt.ElideRight, width))

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selected:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor('#BDD4B6' if self.color == '夜色' else '#425D4D'), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 10, 10)

    def mouseDoubleClickEvent(self,event):
        if not self.note['deleted_at']:
            self.controller.open_note(self.note['id'])


class ReminderCalendar(QCalendarWidget):
    def paintCell(self, painter, rect, date):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        selected = date == self.selectedDate()
        if selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#4557A5'))
            painter.drawRoundedRect(QRectF(rect).adjusted(2, 1, -2, -1), 6, 6)
        color = '#283044'
        if date < self.minimumDate() or date > self.maximumDate():
            color = '#9198A7'
        elif date.month() != self.monthShown() or date.dayOfWeek() >= 6:
            color = '#526590'
        painter.setPen(QColor('#FFFFFF' if selected else color))
        painter.drawText(rect, Qt.AlignCenter, str(date.day()))
        painter.restore()


class ReminderTimeEdit(QDateTimeEdit):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipRect(self.width() - 28, 0, 28, self.height())
        painter.fillRect(self.rect(), QColor('#F8F8FB'))
        painter.setBrush(QColor('#FFFFFF'))
        painter.setPen(QColor('#6376BB' if self.hasFocus() else '#D3D7E1'))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 7, 7)
        painter.setPen(QPen(QColor('#566174'), 1.5, Qt.SolidLine, Qt.RoundCap))
        x, y = self.width() - 14, self.height() // 2
        painter.drawLine(x - 4, y - 2, x, y + 2)
        painter.drawLine(x, y + 2, x + 4, y - 2)


class ReminderDialog(QDialog):
    def __init__(self, note, parent):
        super().__init__(parent)
        self.setWindowTitle('便签提醒')
        self.timestamp = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        self.setMinimumWidth(345)
        heading = label(title(note), 19, bold=True)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        presets = QHBoxLayout()
        presets.addWidget(button('30 分钟后', lambda: self.when.setDateTime(
            QDateTime.currentDateTime().addSecs(30 * 60))))
        presets.addWidget(button('明天上午 9 点', lambda: self.when.setDateTime(
            QDateTime(QDateTime.currentDateTime().date().addDays(1), QTime(9, 0)))))
        layout.addLayout(presets)
        for index in range(presets.count()):
            presets.itemAt(index).widget().setStyleSheet(
                'QPushButton { background:#EBEEF7; color:#354677; }'
                'QPushButton:hover { background:#DDE3FA; }')
        self.when = ReminderTimeEdit()
        self.when.setDisplayFormat('yyyy-MM-dd HH:mm')
        self.when.setCalendarPopup(True)
        self.when.setCalendarWidget(ReminderCalendar())
        calendar = self.when.calendarWidget()
        calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        calendar.setFirstDayOfWeek(Qt.Monday)
        calendar.setMinimumWidth(300)
        weekend = QTextCharFormat()
        weekend.setForeground(QColor('#526590'))
        for day in (Qt.Saturday, Qt.Sunday):
            calendar.setWeekdayTextFormat(day, weekend)
        calendar.setStyleSheet("""
            QCalendarWidget { background:#FFFFFF; border:1px solid #D3D7E1; }
            QWidget#qt_calendar_navigationbar { background:#EDF0F8; }
            QCalendarWidget QToolButton { background:transparent; color:#283044;
                padding:4px 7px; min-height:24px; }
            QCalendarWidget QToolButton:hover { background:#DDE3FA; }
            QCalendarWidget QAbstractItemView { background:#FFFFFF;
                alternate-background-color:#F4F5F9; color:#283044; border:0;
                selection-background-color:#4557A5; selection-color:white; }
            QDateTimeEdit::drop-down { width:28px; border:0; background:transparent; }
            QDateTimeEdit::down-arrow { image:none; width:0; height:0; }
        """)
        self.when.setStyleSheet("""
            QDateTimeEdit, QDateTimeEdit QLineEdit {
                selection-background-color:#4557A5; selection-color:white; }
        """)
        current = QDateTime.currentDateTime()
        self.when.setMinimumDateTime(current.addSecs(-current.time().second()))
        initial = QDateTime.fromSecsSinceEpoch(note.get('reminder_at') or 0)
        self.when.setDateTime(initial if initial > current else current.addSecs(30 * 60))
        self.when.setAccessibleName('提醒时间')
        layout.addWidget(label('提醒时间', 12, '#566174'))
        layout.addWidget(self.when)
        layout.addWidget(label('完全退出后，逾期提醒会在下次启动时提示。', 11))
        actions = QHBoxLayout()
        if note.get('reminder_at'):
            actions.addWidget(button('移除提醒', self.accept))
        actions.addStretch()
        actions.addWidget(button('取消', self.reject))
        save = button('保存', self.save_time, primary=True)
        save.setDefault(True)
        actions.addWidget(save)
        layout.addLayout(actions)

    def save_time(self):
        chosen = self.when.dateTime()
        timestamp = chosen.toSecsSinceEpoch() - chosen.time().second()
        if timestamp <= QDateTime.currentSecsSinceEpoch():
            QMessageBox.information(self, '便签提醒', '请选择一个将来的时间。')
            return
        self.timestamp = timestamp
        self.accept()


class Manager(QMainWindow):
    def __init__(self,controller):
        super().__init__()
        self.controller=controller
        self.mode='所有便签'
        self.result_notes = []
        self.result_cards = []
        self.selected_result = -1
        self.render_key = None
        self.rendering_cards = False
        self.setWindowTitle('小纸片 · 便签抽屉')
        self.setWindowIcon(icon())
        self.resize(1100,760)
        self.setMinimumSize(800,570)
        self.refresh_timer=QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(180)
        self.refresh_timer.timeout.connect(self.render)
        root=QWidget()
        self.setCentralWidget(root)
        layout=QHBoxLayout(root)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        sidebar=QFrame()
        sidebar.setFixedWidth(206)
        sidebar.setObjectName('libraryRail')
        sidebar.setStyleSheet('QFrame#libraryRail {background:#EBEDF2; border-right:1px solid #DADDE5;}')
        side=QVBoxLayout(sidebar)
        side.setContentsMargins(18,28,16,20)
        brand=QHBoxLayout()
        stamp=label('')
        stamp.setFixedSize(42,42)
        stamp.setPixmap(icon().pixmap(QSize(42,42),self.devicePixelRatioF()))
        brand.setSpacing(10)
        brand.addWidget(stamp)
        brand.addWidget(label('小纸片',22,'#20283A',True))
        brand.addStretch()
        side.addLayout(brand)

        side.addSpacing(35)
        side.addWidget(label('资料库',12,'#576173',True))
        side.addSpacing(8)
        self.navigation={}
        for glyph, name in [('notes','所有便签'),('today','今日'),('star','收藏'),('todo','待办'),('clock','提醒'),('tag','标签'),('archive','已归档'),('trash','回收站')]:
            if name=='已归档':
                side.addSpacing(22)
            b=button('  '+name,lambda checked=False,m=name:self.select(m))
            b.setIcon(line_icon(glyph))
            b.setIconSize(QSize(20,20))
            b.setAccessibleName(name)
            b.setCheckable(True)
            b.setFixedHeight(42)
            b.setStyleSheet('text-align:left; padding-left:14px;')
            side.addWidget(b)
            self.navigation[name]=b
        side.addStretch()

        side.addSpacing(12)
        preferences=button('  偏好设置',controller.show_settings)
        preferences.setIcon(line_icon('settings'))
        preferences.setIconSize(QSize(20,20))
        preferences.setStyleSheet('text-align:left; padding-left:14px;')
        side.addWidget(preferences)

        layout.addWidget(sidebar)
        content=QWidget()
        main=QVBoxLayout(content)
        main.setContentsMargins(34,28,32,20)
        main.setSpacing(18)
        top=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText('搜索标题、正文或标签')
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(42)
        self.search.textChanged.connect(self.schedule)
        self.search.installEventFilter(self)
        top.addWidget(self.search,1)
        top.addSpacing(12)
        create_button=button(' 新建便签',lambda:controller.create(),'Ctrl+Alt+N',True)
        create_button.setIcon(line_icon('plus','#FFFFFF'))
        create_button.setIconSize(QSize(18,18))
        top.addWidget(create_button)

        heading=QHBoxLayout()
        copy=QVBoxLayout()
        self.heading=label('所有便签',32,'#20283A',True)
        self.subtitle=label('',12,'#566174')
        copy.addWidget(self.heading)
        copy.addWidget(self.subtitle)
        heading.addLayout(copy,1)
        self.count=label('',12,'#515B70')
        heading.addWidget(self.count)
        main.addLayout(heading)
        main.addLayout(top)
        self.tag_filter=QComboBox()
        self.tag_filter.currentTextChanged.connect(self.schedule)
        self.tag_filter.hide()
        main.addWidget(self.tag_filter)
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.verticalScrollBar().valueChanged.connect(self.load_near_bottom)
        main.addWidget(self.scroll,1)
        self.notice=QFrame()
        self.notice.setStyleSheet('QFrame {background:#E9EDDF; border-radius:8px;}')
        notice_layout=QHBoxLayout(self.notice)
        self.notice_text=label('',12,'#52674D')
        notice_layout.addWidget(self.notice_text,1)
        self.undo=button('撤销',controller.undo_trash)
        notice_layout.addWidget(self.undo)
        main.addWidget(self.notice)
        self.notice.hide()
        self.notice_timer=QTimer(self)
        self.notice_timer.setSingleShot(True)
        self.notice_timer.timeout.connect(self.notice.hide)
        layout.addWidget(content,1)
        self.new_shortcut=QShortcut(QKeySequence('Ctrl+N'),self)
        self.new_shortcut.activated.connect(lambda:controller.create())
        self.find_shortcut=QShortcut(QKeySequence('Ctrl+F'),self)
        self.find_shortcut.activated.connect(self.search.setFocus)
        self.render()

    def select(self,mode):
        self.mode=mode
        self.search.clear()
        if mode=='标签':
            previous=self.tag_filter.currentText()
            self.tag_filter.blockSignals(True)
            self.tag_filter.clear()
            self.tag_filter.addItems(['所有标签']+sorted({t for n in self.controller.store.all() if not n['deleted_at'] for t in n['tags']}))
            index=self.tag_filter.findText(previous)
            self.tag_filter.setCurrentIndex(max(0,index))
            self.tag_filter.blockSignals(False)
        self.tag_filter.setVisible(mode=='标签')
        self.render()

    def schedule(self,*args):
        if self.isVisible():
            self.refresh_timer.start()

    def render(self):
        self.refresh_timer.stop()
        self.heading.setText(self.mode if not self.search.text() else '搜索结果')
        hint = {'回收站': '便签保留 30 天，可在这里恢复。', '已归档': '双击便签即可放回桌面。',
                '提醒': '到期的提醒排在最前面。', '今日': '今天创建或编辑过的便签。',
                '待办': '包含未完成事项的便签。'}.get(self.mode, '')
        if self.search.text().strip() and self.mode != '回收站':
            hint = '↑ ↓ 选择便签　 Enter 打开　 Esc 清除搜索'
        self.subtitle.setText(hint)
        self.subtitle.setVisible(bool(hint))
        for name,b in self.navigation.items():
            b.setChecked(name==self.mode)
        query=self.search.text().strip().casefold()
        notes=[]
        for n in self.controller.store.all():
            if self.mode=='回收站':
                if not n['deleted_at']: continue
            else:
                if n['deleted_at']: continue
                if self.mode=='已归档':
                    if not n['archived']: continue
                elif self.mode=='提醒':
                    if not n.get('reminder_at'): continue
                elif n['archived'] and not (self.mode=='所有便签' and query): continue
                if self.mode=='收藏' and not n['favorite']: continue
                if self.mode=='待办' and not pending(n): continue
                if self.mode=='今日' and n['updated_at'][:10]!=datetime.now().date().isoformat() and n['created_at'][:10]!=datetime.now().date().isoformat(): continue
                if self.mode=='标签' and self.tag_filter.currentIndex()>0 and self.tag_filter.currentText() not in n['tags']: continue
            excerpt = search_excerpt(n, query) if query else ''
            if not query or excerpt:
                notes.append((n, excerpt))
        if self.mode == '提醒':
            notes.sort(key=lambda item: (not item[0].get('reminder_ready'), item[0]['reminder_at']))
        else:
            notes.sort(key=lambda item: (item[0]['favorite'], item[0]['updated_at']), reverse=True)
        self.count.setText(f'{len(notes)} 张纸片')
        columns = max(2, (self.width() - 290) // 270)
        key = (self.mode, query, self.tag_filter.currentIndex(), columns)
        if key == self.render_key and notes == self.result_notes:
            return

        same_filter = self.render_key is not None and key[:3] == self.render_key[:3]
        scrollbar = self.scroll.verticalScrollBar()
        scroll_position = scrollbar.value() if same_filter else 0
        loaded = max(CARDS_PER_BATCH, len(self.result_cards)) if scroll_position else CARDS_PER_BATCH
        selected_id = None
        if same_filter and self.selected_result >= 0:
            selected_id = self.result_notes[self.selected_result][0]['id']
        self.render_key = key
        self.result_notes = notes
        self.result_cards = []
        self.selected_result = -1
        self.columns = columns
        self.rendering_cards = True
        container=QWidget()
        container.setStyleSheet('background:transparent;')
        grid=QGridLayout(container)
        self.result_grid = grid
        grid.setContentsMargins(0,2,8,12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        if notes:
            grid.setAlignment(Qt.AlignTop)
            for col in range(columns):
                grid.setColumnStretch(col,1)
            self.append_cards(loaded)
        else:
            empty=QWidget()
            center=QVBoxLayout(empty)
            center.addStretch()
            art=label('')
            art.setPixmap(icon().pixmap(QSize(76,76),self.devicePixelRatioF()))
            art.setAlignment(Qt.AlignCenter)
            center.addWidget(art)
            text=label('还没有找到这张纸片' if query else '这里还有很多空白',21,'#64745C',True)
            text.setAlignment(Qt.AlignCenter)
            center.addWidget(text)
            hint=label('试试换个词，或者拿张新纸记下来。' if query else '想到什么，就随手写下来吧。',13,'#929A8C')
            hint.setAlignment(Qt.AlignCenter)
            center.addWidget(hint)
            center.addStretch()
            grid.addWidget(empty,0,0)
        old=self.scroll.takeWidget()
        self.scroll.setWidget(container)
        if old: old.deleteLater()
        scrollbar.setValue(scroll_position)
        self.rendering_cards = False
        if selected_id:
            index = next((i for i, (note, _) in enumerate(notes) if note['id'] == selected_id), -1)
            if index >= 0:
                self.select_result(index)

    def append_cards(self, count):
        first = len(self.result_cards)
        stop = min(first + count, len(self.result_notes))
        for index in range(first, stop):
            note, excerpt = self.result_notes[index]
            card = Card(self.controller, note, self.mode, excerpt)
            self.result_cards.append(card)
            self.result_grid.addWidget(card, index // self.columns, index % self.columns)

    def load_near_bottom(self, value):
        scrollbar = self.scroll.verticalScrollBar()
        if not self.rendering_cards and scrollbar.maximum() - value <= 260:
            self.rendering_cards = True
            self.append_cards(CARDS_PER_BATCH)
            self.rendering_cards = False

    def select_result(self, index):
        if self.selected_result >= 0:
            previous = self.result_cards[self.selected_result]
            previous.selected = False
            previous.update()
        if index >= len(self.result_cards):
            self.append_cards(max(CARDS_PER_BATCH, index + 1 - len(self.result_cards)))
        self.selected_result = index
        card = self.result_cards[index]
        card.selected = True
        card.update()
        self.scroll.ensureWidgetVisible(card)

    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape and self.search.text():
            self.search.clear()
            self.render()
            return True
        if (watched is self.search and event.type() == QEvent.KeyPress
                and event.modifiers() in (Qt.NoModifier, Qt.KeypadModifier)
                and self.search.text().strip() and self.mode != '回收站'):
            key = event.key()
            if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter):
                if self.refresh_timer.isActive():
                    self.render()
                if not self.result_notes:
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    note, _ = self.result_notes[max(0, self.selected_result)]
                    self.controller.open_note(note['id'])
                else:
                    step = -1 if key == Qt.Key_Up else 1
                    index = max(0, min(len(self.result_notes) - 1, self.selected_result + step))
                    self.select_result(index)
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'refresh_timer'):
            self.schedule()

    def toast(self,text,undo=False):
        self.notice_text.setText(text)
        self.undo.setVisible(undo)
        self.notice.show()
        self.notice_timer.start(8000)

    def closeEvent(self,event):
        self.hide()
        event.ignore()


class Capture(QDialog):
    def __init__(self,controller):
        super().__init__()
        self.controller=controller
        self.setWindowTitle('随手记 · 小纸片')
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.resize(480,300)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(24,18,24,16)
        layout.addWidget(label('随手记',26,'#20283A',True))
        self.editor=Editor()
        self.editor.setPlaceholderText('写下想法…')
        self.editor.setObjectName('captureEditor')
        self.editor.setHtml(controller.store.get_meta('capture_draft',''))
        self.draft_timer=QTimer(self)
        self.draft_timer.setSingleShot(True)
        self.draft_timer.setInterval(400)
        self.draft_timer.timeout.connect(self.save_draft)
        self.editor.textChanged.connect(lambda:self.draft_timer.start())
        layout.addWidget(self.editor,1)
        row=QHBoxLayout()
        row.addWidget(label('Esc 收起并保留草稿',12,'#566174'))
        row.addStretch()
        row.addWidget(button('保存  Ctrl+Enter',self.capture,'Ctrl+Enter',True))
        layout.addLayout(row)
        self.shortcut=QShortcut(QKeySequence('Ctrl+Return'),self)
        self.shortcut.activated.connect(self.capture)

    def capture(self):
        if not self.editor.toPlainText().strip():
            return
        n=self.controller.store.new(self.editor.toPlainText(),self.editor.toHtml())
        n['hidden']=True
        self.controller.store.save(n)
        self.editor.clear()
        self.save_draft()
        self.hide()
        self.controller.refresh()

    def save_draft(self):
        self.draft_timer.stop()
        self.controller.store.set_meta('capture_draft',self.editor.toHtml() if self.editor.toPlainText() else '')

    def reject(self):
        self.save_draft()
        super().reject()

    def closeEvent(self,event):
        self.save_draft()
        super().closeEvent(event)


class Settings(QDialog):
    def __init__(self,controller):
        super().__init__(controller.manager)
        self.controller=controller
        self.setWindowTitle('偏好设置 · 小纸片')
        self.resize(670,610)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(28,24,28,22)
        layout.addWidget(label('偏好设置',26,'#20283A',True))
        tabs=QTabWidget()
        layout.addWidget(tabs,1)
        self.fields={}
        settings=controller.store.settings
        def page(name):
            widget=QWidget()
            form=QFormLayout(widget)
            form.setContentsMargins(8,16,8,16)
            form.setVerticalSpacing(20)
            tabs.addTab(widget,name)
            return form
        def combo(form,key,title,values):
            w=QComboBox()
            w.addItems(values)
            w.setCurrentText(settings[key])
            self.fields[key]=w
            form.addRow(title,w)
        def spin(form,key,title,minimum,maximum,suffix=''):
            w=QSpinBox()
            w.setRange(minimum,maximum)
            w.setSuffix(suffix)
            w.setValue(settings[key])
            self.fields[key]=w
            form.addRow(title,w)
        def check(form,key,title):
            w=QCheckBox(title)
            w.setChecked(settings[key])
            self.fields[key]=w
            form.addRow(w)
        general=page('常规')
        self.autostart=QCheckBox('登录 Windows 后自动启动')
        self.autostart.setChecked(autostart_enabled())
        general.addRow(self.autostart)
        combo(general,'startup','启动时',['保持上次状态','显示所有便签','全部隐藏'])
        general.addRow(label('关闭便签抽屉后继续驻留托盘。\n在托盘菜单中选择「退出小纸片」可完全退出。',12,'#899180'))
        appearance=page('外观')
        combo(appearance,'color','新纸片颜色',list(COLORS))
        combo(appearance,'skin','纸张纹理',['经典','横线纸','方格纸'])
        spin(appearance,'font_size','默认字号',10,32,' pt')
        spin(appearance,'opacity','默认透明度',60,100,' %')
        check(appearance,'doodle','纸片角落加一点星光涂鸦')
        note=page('便签')
        spin(note,'width','默认宽度',220,1600,' px')
        spin(note,'height','默认高度',120,1200,' px')
        check(note,'snap','拖动时吸附屏幕边缘与相邻便签')
        check(note,'hover_toolbar','鼠标离开后隐藏顶部工具栏')
        note.addRow(label('输入 [] 加空格变为待办，# 加空格变为标题。\n双击纸片顶部可以收起或展开。',12,'#899180'))
        shortcuts=page('快捷键')
        self.hotkey_fields={}
        for key,name in HOTKEY_NAMES.items():
            w=QKeySequenceEdit(QKeySequence(settings['hotkeys'][key]))
            w.setMaximumSequenceLength(1)
            self.hotkey_fields[key]=w
            shortcuts.addRow(name,w)
        shortcuts.addRow(label('与其他程序冲突时会保留原有配置。',11,'#899180'))
        data=page('数据')
        total=len(controller.store.all())
        size=(controller.store.directory/'database.db').stat().st_size/1024
        data.addRow(label(f'{total} 张便签  ·  数据库约 {size:.0f} KB',16,'#425D4D',True))
        spin(data,'backup_days','每日备份保留',7,30,' 天')
        for text,callback in [('立即备份',self.backup),('导出全部数据',self.export_data),('导入数据',self.import_data),
                              ('打开数据目录',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(controller.store.directory))))]:
            data.addRow(button(text,callback))
        data.addRow(label('导入会新增纸片，不覆盖已有内容。\n回收站自动保留 30 天；版本快照最多保留 30 个。',11,'#899180'))
        about=page('关于')
        about.addRow(label(f'小纸片  {__version__}',24,'#425D4D',True))
        about.addRow(label('桌面上的一张纸。\n\n无需登录，无需联网。\n文字、窗口位置和偏好都保存在本机。\n\nPython · Qt for Python · SQLite',13,'#7B8774'))
        row=QHBoxLayout()
        row.addStretch()
        row.addWidget(button('取消',self.reject))
        row.addWidget(button('应用设置',self.save,primary=True))
        layout.addLayout(row)

    def save(self):
        values={}
        for key,w in self.fields.items():
            if isinstance(w,QComboBox): value=w.currentText()
            elif isinstance(w,QCheckBox): value=w.isChecked()
            else: value=w.value()
            values[key]=value
        values['hotkeys']={k:w.keySequence().toString(QKeySequence.PortableText) for k,w in self.hotkey_fields.items()}
        previous=dict(self.controller.store.settings['hotkeys'])
        try:
            self.controller.hotkeys.apply(values['hotkeys'])
            set_autostart(self.autostart.isChecked())
            self.controller.store.save_settings(values)
        except (ValueError,OSError) as error:
            try: self.controller.hotkeys.apply(previous)
            except ValueError: pass
            self.controller.error(str(error))
            return
        for w in self.controller.windows.values():
            w.apply_appearance()
        self.accept()

    def backup(self):
        self.controller.flush_all()
        try:
            path=self.controller.store.backup()
            QMessageBox.information(self,'纸片已备份',f'备份已保存到：\n{path}')
        except OSError as error:
            self.controller.error(str(error))

    def export_data(self):
        path,_=QFileDialog.getSaveFileName(self,'导出全部纸片','小纸片备份.stickybackup','小纸片备份 (*.stickybackup);;JSON (*.json)')
        if path:
            self.controller.flush_all()
            try:
                self.controller.store.export_all(path)
                QMessageBox.information(self,'导出完成','全部纸片已放进备份文件。')
            except OSError as error:
                self.controller.error(str(error))

    def import_data(self):
        path,_=QFileDialog.getOpenFileName(self,'导入纸片','','小纸片备份 (*.stickybackup *.json)')
        if path:
            try:
                self.controller.flush_all()
                count=self.controller.store.import_all(path)
                self.controller.refresh()
                QMessageBox.information(self,'导入完成',f'已新增 {count} 张纸片，可在抽屉中打开。')
            except (ValueError,OSError,KeyError,TypeError) as error:
                self.controller.error(str(error))
