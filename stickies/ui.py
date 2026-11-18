from __future__ import annotations

import random
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QPointF, QRectF, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (QColor, QPainter, QPen, QFont, QIcon, QPixmap, QTextCursor,
                           QTextCharFormat, QTextListFormat, QKeySequence, QShortcut,
                           QDesktopServices, QFontMetricsF)
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QToolButton, QVBoxLayout,
    QHBoxLayout, QTextEdit, QLineEdit, QMenu, QSizeGrip, QInputDialog, QFileDialog,
    QDialog, QListWidget, QDialogButtonBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy)

from .store import COLORS, title, now
from .icons import IconButton, brand_icon

STYLE = '''
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #283044; }
QDialog, QMainWindow { background: #F8F8FB; }
QLabel { background: transparent; }
QPushButton, QToolButton { background: transparent; border: none; border-radius: 7px; padding: 7px 10px; }
QPushButton:hover, QToolButton:hover { background: #E4E7F0; }
QPushButton:checked { background: #DDE3FA; color: #283C86; }
QPushButton#primary { background: #4557A5; color: white; padding: 11px 19px; border-radius: 9px; }
QPushButton#primary:hover { background: #354788; }
QPushButton#danger { color: #AC4E42; }
QLineEdit, QDateTimeEdit, QSpinBox, QComboBox, QKeySequenceEdit { background: #FFFFFF; border: 1px solid #D3D7E1; border-radius: 7px; padding: 8px; }
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus, QPushButton:focus { border:1px solid #6376BB; }
QPushButton:pressed { background:#CDD4EA; }
QTextEdit#captureEditor { background:white; border:1px solid #D3D7E1; border-radius:12px; padding:12px; }
QTextEdit { border: none; background: transparent; selection-background-color: #BFCBF4; }
QMenu { background: #FAF9F4; border: 1px solid #DADDD2; padding: 6px; }
QMenu::item { padding: 8px 24px; border-radius: 4px; }
QMenu::item:selected { background: #E5EBDC; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; }
QScrollBar::handle:vertical { background: #CBCFC4; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTabWidget::pane { border: none; padding-top: 16px; }
QTabBar::tab { padding: 10px 17px; background: transparent; }
QTabBar::tab:selected { color: #4557A5; border-bottom: 2px solid #4557A5; }
QListWidget { border: 1px solid #D3D7E1; border-radius: 8px; background: white; padding: 8px; }
QListWidget::item { padding: 10px; }
QListWidget::item:selected { background: #DDE3FA; color: #283044; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked { background: #FFFFFF; border: 1px solid #A5B09A; border-radius: 4px; }
QCheckBox::indicator:checked { background: #4557A5; border: 3px solid #B7C7AB; border-radius: 4px; }
QToolTip { background: #283044; color: white; border: none; padding: 5px; }
'''


def label(text, size=13, color='#283044', bold=False):
    w = QLabel(text)
    w.setTextFormat(Qt.PlainText)
    w.setStyleSheet(f'font-size:{size}px; color:{color}; font-weight:{600 if bold else 400};')
    return w


def button(text, callback, tip='', primary=False):
    w = QPushButton(text)
    w.setCursor(Qt.PointingHandCursor)
    if primary:
        w.setObjectName('primary')
    w.clicked.connect(callback)
    w.setToolTip(tip)
    return w


def icon():
    return brand_icon()


class Paper(QFrame):
    def __init__(self, color='奶油黄', skin='横线纸', parent=None):
        super().__init__(parent)
        self.color = color
        self.skin = skin
        self.doodle = False
        self.editor_rules = False
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dark = self.color == '夜色'
        p.setPen(QPen(QColor('#57615A') if dark else QColor(105,110,83,45),1))
        p.setBrush(QColor(COLORS[self.color]))
        p.drawRoundedRect(QRectF(1,1,self.width()-2,self.height()-2),11,11)
        if not self.editor_rules and self.skin in ('横线纸','方格纸'):
            p.setPen(QPen(QColor(255,255,255,12) if dark else QColor(110,103,74,20),1))
            for y in range(66,self.height()-20,28):
                p.drawLine(16,y,self.width()-16,y)
            if self.skin == '方格纸':
                for x in range(18,self.width()-10,28):
                    p.drawLine(x,46,x,self.height()-18)
        # Small folded corner, drawn as part of the paper rather than a bitmap.
        p.setPen(QPen(QColor(255,255,255,110),1))
        p.drawLine(self.width()-24,self.height()-2,self.width()-2,self.height()-24)
        if self.doodle and self.height()>160:
            p.setPen(QPen(QColor(210,222,190,85) if dark else QColor(110,120,81,75),1.3))
            x,y=self.width()-33,self.height()-55
            for dx,dy,r in [(0,0,9),(-19,8,4)]:
                p.drawLine(x+dx-r,y+dy,x+dx+r,y+dy+1)
                p.drawLine(x+dx,y+dy-r,x+dx-1,y+dy+r)


class Editor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setTabChangesFocus(False)
        self.setPlaceholderText(random.choice(['想到什么了？','写下来，免得忘。','灵感跑得很快。','先记着，等会再想。']))
        self.document().setDocumentMargin(3)
        self.ruled_skin = '经典'
        self.dark_paper = False

    def rule_positions(self):
        """Place each rule below the actual laid-out text baseline, including wraps."""
        document = self.document()
        document.documentLayout().documentSize()  # Ensure wrapping/font changes are laid out.
        scroll = self.verticalScrollBar().value()
        positions = []
        block = self.cursorForPosition(QPoint(0, 0)).block()
        last = None
        spacing = QFontMetricsF(document.defaultFont()).height()
        while block.isValid():
            top = document.documentLayout().blockBoundingRect(block).top() - scroll
            layout = block.layout()
            if top > self.viewport().height():
                break
            for i in range(layout.lineCount()):
                line = layout.lineAt(i)
                baseline = top + line.y() + line.ascent() + 2
                if 0 <= baseline <= self.viewport().height():
                    positions.append(baseline)
                last = baseline
            block = block.next()
        # Continue the notebook through the unused writing area.
        if not block.isValid() and last is not None:
            y = last + spacing
            while y < self.viewport().height():
                if y >= 0:
                    positions.append(y)
                y += spacing
        return positions

    def paintEvent(self, event):
        if self.ruled_skin in ('横线纸', '方格纸'):
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor(255,255,255,18) if self.dark_paper else QColor(110,103,74,28), 1))
            for y in self.rule_positions():
                painter.drawLine(QPointF(0,y), QPointF(self.viewport().width(),y))
            if self.ruled_skin == '方格纸':
                spacing = QFontMetricsF(self.document().defaultFont()).height()
                x = self.document().documentMargin() - self.horizontalScrollBar().value() % spacing
                while x < self.viewport().width():
                    painter.drawLine(QPointF(x,0), QPointF(x,self.viewport().height()))
                    x += spacing
            painter.end()
        super().paintEvent(event)

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.viewport().update()

    def toggle_todo(self, checked=False):
        cur = self.textCursor()
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.StartOfBlock)
        cur.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
        text = cur.selectedText()
        if text.startswith(('☐ ', '☑ ')):
            done = text.startswith('☐ ') if checked else False
            text = text[2:]
        else:
            done = False
            for prefix in ('[] ', '[ ] ', '- '):
                if text.startswith(prefix):
                    text = text[len(prefix):]
                    break
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(done)
        if done:
            fmt.setForeground(QColor('#7B867A'))
        cur.insertText(('☑ ' if done else '☐ ') + text, fmt)
        cur.endEditBlock()
        self.setTextCursor(cur)

    def mousePressEvent(self, event):
        cur = self.cursorForPosition(event.position().toPoint())
        if event.button() == Qt.LeftButton and cur.block().text().startswith(('☐ ', '☑ ')) and cur.positionInBlock() <= 2:
            self.setTextCursor(cur)
            self.toggle_todo(True)
            return
        if event.modifiers() & Qt.ControlModifier:
            anchor = self.anchorAt(event.position().toPoint())
            if anchor.startswith(('https://', 'http://', 'mailto:')):
                QDesktopServices.openUrl(QUrl(anchor))
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        cur = self.textCursor()
        text = cur.block().text()
        if event.key() == Qt.Key_Space and text in ('[]','[ ]','#','-') and cur.positionInBlock() == len(text):
            cur.movePosition(QTextCursor.StartOfBlock)
            cur.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
            cur.removeSelectedText()
            if text in ('[]','[ ]'):
                cur.insertText('☐ ')
            elif text == '#':
                fmt = cur.blockFormat()
                fmt.setHeadingLevel(2)
                cur.setBlockFormat(fmt)
                char = QTextCharFormat()
                char.setFontWeight(QFont.Bold)
                char.setFontPointSize(18)
                cur.setCharFormat(char)
            else:
                fmt = QTextListFormat()
                fmt.setStyle(QTextListFormat.ListDisc)
                cur.createList(fmt)
            self.setTextCursor(cur)
            return
        if event.key() in (Qt.Key_Return,Qt.Key_Enter) and not (event.modifiers() & Qt.ControlModifier):
            if text.startswith(('☐ ','☑ ')):
                if not text[2:].strip():
                    cur.movePosition(QTextCursor.StartOfBlock)
                    cur.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
                    cur.removeSelectedText()
                else:
                    cur.insertBlock()
                    cur.setCharFormat(QTextCharFormat())
                    cur.insertText('☐ ')
                self.setTextCursor(cur)
                return
            if text == '---':
                cur.movePosition(QTextCursor.StartOfBlock)
                cur.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
                cur.insertHtml('<hr><p></p>')
                self.setTextCursor(cur)
                return
            if cur.blockFormat().headingLevel():
                cur.insertBlock()
                block = cur.blockFormat()
                block.setHeadingLevel(0)
                cur.setBlockFormat(block)
                cur.setCharFormat(QTextCharFormat())
                self.setTextCursor(cur)
                return
        super().keyPressEvent(event)


class DragBar(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.origin = None
        self.setCursor(Qt.SizeAllCursor)

    def mousePressEvent(self,event):
        if event.button() == Qt.LeftButton:
            self.origin = event.globalPosition().toPoint() - self.window.pos()

    def mouseMoveEvent(self,event):
        if self.origin is not None and event.buttons() & Qt.LeftButton:
            point = event.globalPosition().toPoint() - self.origin
            self.window.move(self.window.snapped(point))

    def mouseReleaseEvent(self,event):
        self.origin = None
        self.window.schedule()

    def mouseDoubleClickEvent(self,event):
        self.window.collapse()


class NoteWindow(QWidget):
    def __init__(self, controller, note):
        super().__init__()
        self.controller, self.note = controller, note
        self.ready = False
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowIcon(icon())
        self.setMinimumSize(220,120)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.flush)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8,8,8,10)
        self.paper = Paper(note['color'],controller.store.settings['skin'])
        self.paper.editor_rules = True
        # Paint the shadow directly: nested graphics effects can suppress the
        # toolbar's opacity effect when Qt renders the parent paper.
        outer.addWidget(self.paper)
        layout = QVBoxLayout(self.paper)
        layout.setContentsMargins(16,7,16,8)
        layout.setSpacing(3)
        self.bar = DragBar(self)
        self.bar.setFixedHeight(29)
        top = QHBoxLayout(self.bar)
        top.setContentsMargins(0,0,0,0)
        top.setSpacing(0)
        self.caption = label('小纸片',11,'#78806A')
        self.caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        top.addWidget(self.caption,1)
        self.tools = QWidget()
        row = QHBoxLayout(self.tools)
        row.setContentsMargins(0,0,0,0)
        row.setSpacing(3)
        self.pin_button = IconButton('pin', self.pin, '置顶 / 取消置顶 · Ctrl+Shift+P',29)
        self.pin_button.setCheckable(True)
        for w in (self.pin_button, IconButton('palette', self.color_menu,'纸张颜色',29),
                  IconButton('minus', self.collapse,'收起 / 双击标题恢复',29), IconButton('more', self.menu,'更多操作',29)):
            w.setFixedSize(29,29)
            row.addWidget(w)
        top.addWidget(self.tools)
        self.tools_opacity = QGraphicsOpacityEffect(self.tools)
        self.tools.setGraphicsEffect(self.tools_opacity)
        self.tools_animation = QPropertyAnimation(self.tools_opacity, b'opacity', self)
        self.tools_animation.setDuration(150)
        self.tools_animation.setEasingCurve(QEasingCurve.InOutQuad)
        layout.addWidget(self.bar)
        self.format_bar = QWidget()
        formats = QHBoxLayout(self.format_bar)
        formats.setContentsMargins(0,0,0,0)
        formats.setSpacing(0)
        for text, callback, tip in [('bold',lambda:self.format_text('bold'),'粗体'),
                                    ('strike',lambda:self.format_text('strike'),'删除线'),
                                    ('highlight',lambda:self.format_text('highlight'),'高亮'),
                                    ('todo',lambda:self.editor.toggle_todo(),'转待办'),
                                    ('link',self.add_link,'添加链接'),
                                    ('clear',lambda:self.format_text('clear'),'清除格式')]:
            formats.addWidget(IconButton(text,callback,tip,28))
        layout.addWidget(self.format_bar)
        self.format_bar.hide()
        self.editor = Editor()
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.menu)
        self.editor.setFont(QFont('Microsoft YaHei UI',note['font_size']))
        if note['content']:
            self.editor.setHtml(note['content'])
        else:
            self.editor.setPlainText(note['plain'])
        self.editor.textChanged.connect(self.changed)
        self.editor.selectionChanged.connect(lambda: self.format_bar.setVisible(self.editor.textCursor().hasSelection()))
        layout.addWidget(self.editor,1)
        self.footer = QWidget()
        bottom = QHBoxLayout(self.footer)
        bottom.setContentsMargins(0,0,0,0)
        self.status = label('已放好',10,'#78806A')
        self.status.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        bottom.addWidget(self.status,1)
        bottom.addWidget(IconButton('archive', lambda:controller.archive(self.note['id']), '放回抽屉（归档）',28))
        bottom.addWidget(IconButton('notes', controller.show_manager, '打开便签抽屉',28))
        bottom.addWidget(IconButton('plus', lambda:controller.create(), '新建便签 · Ctrl+N',28))
        grip = QSizeGrip(self)
        grip.setFixedSize(13,13)
        bottom.addWidget(grip)
        layout.addWidget(self.footer)
        self.shortcuts = []
        for key, callback in {'Ctrl+N':lambda:controller.create(), 'Ctrl+Shift+Return':self.editor.toggle_todo,
                              'Ctrl+Shift+P':self.pin, 'Ctrl+Shift+Delete':self.trash,
                              'Escape':self.hide_note,'Ctrl+F':self.find_text,
                              'Ctrl++':lambda:self.font_size(1),'Ctrl+=':lambda:self.font_size(1),
                              'Ctrl+-':lambda:self.font_size(-1), 'Ctrl+Shift+Z':self.editor.redo}.items():
            shortcut = QShortcut(QKeySequence(key),self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.menu)
        self.restore_geometry()
        self.apply_appearance()
        self._wheel_angle = 0
        self._wheel_pixels = 0
        for widget in [self, *self.findChildren(QWidget)]:
            widget.installEventFilter(self)
        self.ready = True
        if note['collapsed']:
            self.set_collapsed(True)

    def restore_geometry(self):
        app = self.controller.app
        screens = app.screens()
        screen = next((s for s in screens if s.name() == self.note['screen_id']),app.primaryScreen())
        area = screen.availableGeometry()
        width = min(self.note['width'],area.width())
        height = min(self.note['height'],area.height())
        x = self.note['x']
        y = self.note['y']
        if x is None or y is None:
            offset = (len(self.controller.windows) % 5) * 26
            x = area.center().x() - width//2 + offset
            y = area.center().y() - height//2 + offset
        x = max(area.left(),min(x,area.right()-width+1))
        y = max(area.top(),min(y,area.bottom()-height+1))
        self.setGeometry(x,y,width,height)

    def paintEvent(self, event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        for inset in range(1,8):
            painter.setBrush(QColor(40,45,35,2+inset//3))
            painter.drawRoundedRect(QRectF(inset,inset+2,self.width()-2*inset,self.height()-2*inset-2),14,14)
        painter.end()

    def apply_appearance(self):
        n = self.note
        self.paper.color = n['color']
        self.paper.skin = self.controller.store.settings['skin']
        self.paper.doodle = self.controller.store.settings['doodle']
        self.paper.update()
        self.editor.ruled_skin = self.paper.skin
        self.editor.dark_paper = n['color'] == '夜色'
        foreground='#F5F3E9' if n['color']=='夜色' else '#283044'
        self.editor.setStyleSheet(f'color:{foreground}; font-size:{n["font_size"]}pt;')
        self.editor.document().setDefaultFont(QFont('Microsoft YaHei UI',n['font_size']))
        self.editor.viewport().update()
        self.setWindowOpacity(n['opacity']/100)
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint,n['pinned'])
        self.pin_button.setChecked(n['pinned'])
        for action_button in self.findChildren(IconButton):
            action_button.dark = n['color'] == '夜色'
            action_button.update()
        if visible:
            self.show()
        self.set_tools_visible(not self.controller.store.settings['hover_toolbar'] or self.underMouse() or n['collapsed'], animate=False)

    def set_tools_visible(self, visible, animate=True):
        # Keep both toolbar and drag bar in the layout even at opacity zero.
        self.tools_animation.stop()
        self.tools.setEnabled(visible)
        self.tools.setAttribute(Qt.WA_TransparentForMouseEvents, not visible)
        target = 1.0 if visible else 0.0
        if animate:
            self.tools_animation.setStartValue(self.tools_opacity.opacity())
            self.tools_animation.setEndValue(target)
            self.tools_animation.start()
        else:
            self.tools_opacity.setOpacity(target)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Wheel and event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self._wheel_angle += delta
                steps = int(self._wheel_angle / 120)
                self._wheel_angle -= steps * 120
            else:
                self._wheel_pixels += event.pixelDelta().y()
                steps = int(self._wheel_pixels / 40)
                self._wheel_pixels -= steps * 40
            if steps:
                self.font_size(steps)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def enterEvent(self,event):
        self.set_tools_visible(True)
        super().enterEvent(event)

    def leaveEvent(self,event):
        if self.controller.store.settings['hover_toolbar'] and not self.note['collapsed']:
            self.set_tools_visible(False)
        super().leaveEvent(event)

    def changed(self):
        self.note['updated_at'] = now()
        self.schedule()

    def schedule(self):
        if self.ready:
            self.timer.start()

    def flush(self):
        if not self.ready:
            return
        self.timer.stop()
        n = self.note
        n.update(content=self.editor.toHtml(),plain=self.editor.toPlainText(),x=self.x(),y=self.y(),width=self.width())
        if not n['collapsed']:
            n['height'] = self.height()
        if self.screen():
            n['screen_id'] = self.screen().name()
        self.controller.store.save(n)
        self.caption.setText(title(n)[:14] if n['collapsed'] else ('已置顶' if n['pinned'] else '小纸片'))
        self.setWindowTitle(title(n) + ' · 小纸片')
        self.status.setText(datetime.fromisoformat(n['updated_at']).strftime('%H:%M') + '  ·  已放好')
        self.controller.refresh()

    def resizeEvent(self,event):
        self.schedule()
        super().resizeEvent(event)

    def moveEvent(self,event):
        self.schedule()
        super().moveEvent(event)

    def snapped(self,point):
        if not self.controller.store.settings['snap']:
            return point
        screen = self.controller.app.screenAt(point + QPoint(self.width()//2,20)) or self.screen()
        rect = screen.availableGeometry()
        xs = [rect.left(),rect.right()-self.width()+1]
        ys = [rect.top(),rect.bottom()-self.height()+1]
        for w in self.controller.windows.values():
            if w != self and w.isVisible():
                if abs(point.y()-w.y()) < max(w.height(),self.height()):
                    xs += [w.x()+w.width(),w.x()-self.width()]
                if abs(point.x()-w.x()) < max(w.width(),self.width()):
                    ys += [w.y()+w.height(),w.y()-self.height()]
        x,y = point.x(),point.y()
        for target in xs:
            if abs(target-x) < 10:
                x=target
                break
        for target in ys:
            if abs(target-y) < 10:
                y=target
                break
        return QPoint(x,y)

    def pin(self):
        self.note['pinned'] = not self.note['pinned']
        self.apply_appearance()
        self.flush()

    def color_menu(self):
        menu = QMenu(self)
        for name in COLORS:
            menu.addAction(('✓  ' if name==self.note['color'] else '    ')+name,lambda n=name:self.set_color(n))
        menu.addSeparator()
        menu.addAction('随便一张',lambda:self.set_color(random.choice(list(COLORS))))
        menu.exec(self.mapToGlobal(QPoint(60,42)))

    def set_color(self,color):
        self.note['color'] = color
        self.apply_appearance()
        self.flush()

    def collapse(self):
        self.flush()
        self.set_collapsed(not self.note['collapsed'])
        self.flush()

    def set_collapsed(self,value):
        self.note['collapsed']=value
        self.editor.setVisible(not value)
        self.footer.setVisible(not value)
        self.format_bar.hide()
        if value:
            self.setMinimumHeight(52)
            self.setMaximumHeight(52)
            self.resize(self.width(),52)
        else:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(120)
            self.resize(self.width(),self.note['height'])
        self.set_tools_visible(True, animate=False)
        self.caption.setText(title(self.note)[:14] if value else '小纸片')

    def hide_note(self):
        self.note['hidden']=True
        self.flush()
        self.hide()

    def closeEvent(self,event):
        self.hide_note()
        event.ignore()

    def trash(self):
        self.flush()
        self.controller.trash(self.note['id'])

    def menu(self,*args):
        menu=QMenu(self)
        text_menu=self.editor.createStandardContextMenu()
        text_menu.setTitle('文本编辑')
        menu.addMenu(text_menu)
        menu.addAction('取消置顶' if self.note['pinned'] else '置顶',self.pin)
        menu.addAction('复制全部',lambda:self.controller.app.clipboard().setText(self.editor.toPlainText()))
        menu.addAction('修改标题…',self.rename)
        menu.addAction('标签…',self.tags)
        reminder_label = '修改提醒…' if self.note.get('reminder_at') else '设置提醒…'
        menu.addAction(reminder_label, lambda: self.controller.edit_reminder(self.note['id'], self))
        menu.addSeparator()
        menu.addAction('更换颜色…',self.color_menu)
        size_menu=menu.addMenu(f'字号 · {self.note["font_size"]} pt')
        size_menu.addAction('增大字号    Ctrl + 滚轮向上',lambda:self.font_size(1))
        size_menu.addAction('减小字号    Ctrl + 滚轮向下',lambda:self.font_size(-1))
        opacity=menu.addMenu('透明度')
        for value in (100,90,80,70,60):
            opacity.addAction(f'{value}%',lambda v=value:self.set_opacity(v))
        menu.addAction('取消收藏' if self.note['favorite'] else '收藏',self.favorite)
        menu.addAction('收进抽屉',lambda:self.controller.archive(self.note['id']))
        menu.addSeparator()
        menu.addAction('导出…',self.export)
        menu.addAction('历史版本…',self.history)
        menu.addSeparator()
        menu.addAction('丢进废纸篓',self.trash)
        menu.exec(self.cursor().pos())
        text_menu.deleteLater()

    def rename(self):
        value,ok=QInputDialog.getText(self,'纸片标题','留空时，自动使用正文第一行：',text=self.note['title'])
        if ok:
            self.note['title']=value.strip()[:100]
            self.flush()

    def tags(self):
        value,ok=QInputDialog.getText(self,'轻轻分个类','用空格分隔标签，例如：工作 灵感',text=' '.join(self.note['tags']))
        if ok:
            self.note['tags']=list(dict.fromkeys(t.lstrip('#')[:30] for t in value.split() if t.lstrip('#')))[:20]
            self.flush()

    def favorite(self):
        self.note['favorite']=not self.note['favorite']
        self.flush()

    def set_opacity(self,value):
        self.note['opacity']=value
        self.apply_appearance()
        self.flush()

    def font_size(self,delta):
        size=max(10,min(32,self.note['font_size']+delta))
        if size == self.note['font_size']:
            return
        self.note['font_size']=size
        self.editor.setFont(QFont('Microsoft YaHei UI',self.note['font_size']))
        cursor=self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        fmt=QTextCharFormat()
        fmt.setFontPointSize(self.note['font_size'])
        cursor.mergeCharFormat(fmt)
        cursor.endEditBlock()
        self.apply_appearance()
        self.flush()

    def format_text(self,kind):
        fmt=QTextCharFormat()
        current=self.editor.currentCharFormat()
        if kind=='bold':
            fmt.setFontWeight(QFont.Normal if current.fontWeight()==QFont.Bold else QFont.Bold)
        elif kind=='strike':
            fmt.setFontStrikeOut(not current.fontStrikeOut())
        elif kind=='highlight':
            fmt.setBackground(QColor('#E7C464'))
        elif kind=='clear':
            self.editor.textCursor().setCharFormat(fmt)
            return
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def add_link(self):
        value,ok=QInputDialog.getText(self,'添加链接','网址（https://…）：')
        if ok and value.startswith(('https://','http://')):
            fmt=QTextCharFormat()
            fmt.setAnchor(True)
            fmt.setAnchorHref(value)
            fmt.setFontUnderline(True)
            fmt.setForeground(QColor('#426E72'))
            self.editor.mergeCurrentCharFormat(fmt)

    def find_text(self):
        value,ok=QInputDialog.getText(self,'在这张纸上找找','查找：')
        if ok and value:
            if not self.editor.find(value):
                cur=self.editor.textCursor()
                cur.movePosition(QTextCursor.Start)
                self.editor.setTextCursor(cur)
                if not self.editor.find(value):
                    self.controller.toast('这张纸上没有找到这段文字。')

    def export(self):
        self.flush()
        path,_=QFileDialog.getSaveFileName(self,'导出便签',title(self.note).replace('/','_').replace('\\','_')+'.txt',
                                         '纯文本 (*.txt);;Markdown (*.md);;JSON (*.json)')
        if path:
            from pathlib import Path
            import json
            if path.endswith('.json'):
                content=json.dumps(self.note,ensure_ascii=False,indent=2)
            elif path.endswith('.md'):
                content=self.editor.document().toMarkdown()
            else:
                content=self.editor.toPlainText()
            try:
                Path(path).write_text(content,encoding='utf-8')
            except OSError as error:
                self.controller.error(str(error))

    def history(self):
        versions=self.controller.store.history(self.note['id'])
        dialog=QDialog(self)
        dialog.setWindowTitle('之前写过的 · 最近 30 个版本')
        dialog.resize(530,440)
        layout=QVBoxLayout(dialog)
        listing=QListWidget()
        preview=QTextEdit()
        preview.setReadOnly(True)
        for version in versions:
            listing.addItem(version['saved_at'].replace('T','  '))
        listing.currentRowChanged.connect(lambda row:preview.setPlainText(versions[row]['plain']) if row>=0 else None)
        layout.addWidget(listing,1)
        layout.addWidget(preview,2)
        layout.addWidget(label('恢复前会先备份当前内容。' if versions else '还没有历史版本，继续记录吧。',11,'#7A8378'))
        def restore():
            row=listing.currentRow()
            if row>=0:
                self.flush()
                self.controller.store.backup()
                self.editor.setHtml(versions[row]['content'])
                self.flush()
                dialog.accept()
        layout.addWidget(button('恢复这个版本',restore,primary=True))
        listing.setCurrentRow(0)
        dialog.exec()
