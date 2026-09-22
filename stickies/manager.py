from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QScrollArea, QFrame, QDialog, QTabWidget, QFormLayout, QComboBox,
    QSpinBox, QCheckBox, QKeySequenceEdit, QFileDialog, QMessageBox, QInputDialog)

from .store import COLORS, title, pending
from .ui import label, button, Paper, Editor, icon
from .icons import IconButton, line_icon
from .platform import HOTKEY_NAMES, autostart_enabled, set_autostart


class Card(Paper):
    def __init__(self,controller,note,mode):
        super().__init__(note['color'],'经典')
        self.controller, self.note=controller,note
        self.setMinimumHeight(230)
        self.setMaximumHeight(260)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('双击打开这张纸片')
        layout=QVBoxLayout(self)
        layout.setContentsMargins(20,16,16,10)
        top=QHBoxLayout()
        foreground='#F5F3E9' if note['color']=='夜色' else '#374034'
        heading=label(title(note),15,foreground,True)
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
        tags='  '.join('#'+t for t in note['tags'])
        meta=label((tags[:32]+'   ' if tags else '') + (f'☐ {pending(note)} 项待办' if pending(note) else ''),10,foreground)
        layout.addWidget(meta)
        foot=QHBoxLayout()
        foot.setSpacing(6)
        foot.addWidget(label(datetime.fromisoformat(note['updated_at']).strftime('%m 月 %d 日'),10,foreground))
        foot.addStretch()
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

    def mouseDoubleClickEvent(self,event):
        if not self.note['deleted_at']:
            self.controller.open_note(self.note['id'])


class Manager(QMainWindow):
    def __init__(self,controller):
        super().__init__()
        self.controller=controller
        self.mode='所有便签'
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
        sidebar.setStyleSheet('QFrame {background:#EEEFE7; border:none;}')
        side=QVBoxLayout(sidebar)
        side.setContentsMargins(22,32,18,24)
        brand=QHBoxLayout()
        stamp=label('')
        stamp.setFixedSize(42,42)
        stamp.setPixmap(icon().pixmap(QSize(42,42),self.devicePixelRatioF()))
        brand.setSpacing(10)
        brand.addWidget(stamp)
        brand.addWidget(label('小纸片',22,'#354B3A',True))
        brand.addStretch()
        side.addLayout(brand)
        side.addWidget(label('留住一闪而过的想法',11,'#8C9485'))
        side.addSpacing(35)
        side.addWidget(label('我的抽屉',10,'#949C8D'))
        side.addSpacing(8)
        self.navigation={}
        for glyph, name in [('notes','所有便签'),('today','今日'),('star','收藏'),('todo','待办'),('tag','标签'),('archive','已归档'),('trash','回收站')]:
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
        side.addWidget(label('一张纸，也装得下好想法。',10,'#909887'))
        side.addSpacing(12)
        preferences=button('  偏好设置',controller.show_settings)
        preferences.setIcon(line_icon('settings'))
        preferences.setIconSize(QSize(20,20))
        preferences.setStyleSheet('text-align:left; padding-left:14px;')
        side.addWidget(preferences)
        side.addWidget(label('●  只在这台电脑，安心记录',10,'#6C8265'))
        layout.addWidget(sidebar)
        content=QWidget()
        main=QVBoxLayout(content)
        main.setContentsMargins(34,28,32,20)
        main.setSpacing(18)
        top=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText('搜索纸片上的文字、标题或标签…')
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(42)
        self.search.textChanged.connect(self.schedule)
        top.addWidget(self.search,1)
        top.addSpacing(12)
        create_button=button(' 拿一张纸',lambda:controller.create(),'Ctrl+Alt+N',True)
        create_button.setIcon(line_icon('plus','#FFFFFF'))
        create_button.setIconSize(QSize(18,18))
        top.addWidget(create_button)
        main.addLayout(top)
        heading=QHBoxLayout()
        copy=QVBoxLayout()
        self.heading=label('所有便签',27,'#343E34',True)
        self.subtitle=label('不必整理得井井有条，先把想法留下。',12,'#8A9285')
        copy.addWidget(self.heading)
        copy.addWidget(self.subtitle)
        heading.addLayout(copy,1)
        self.count=label('',12,'#8A9285')
        heading.addWidget(self.count)
        main.addLayout(heading)
        self.tag_filter=QComboBox()
        self.tag_filter.currentTextChanged.connect(self.schedule)
        self.tag_filter.hide()
        main.addWidget(self.tag_filter)
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
        bottom=QHBoxLayout()
        bottom.addWidget(label('Ctrl + Alt + N  新建    /    Ctrl + Alt + Space  随手记',10,'#939A8D'))
        bottom.addStretch()
        bottom.addWidget(label('小纸片  /  1.0.3',10,'#939A8D'))
        main.addLayout(bottom)
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
        self.heading.setText(self.mode if not self.search.text() else '找到这些小纸片')
        self.subtitle.setText({'回收站':'丢掉的想法，30 天内都能捡回来。','已归档':'暂时收好，需要时再拿出来。',
                               '待办':'一件一件来，慢慢划掉。','收藏':'值得常常回看的那些小事。',
                               '今日':'今天的想法，还带着新鲜的温度。','标签':'给零散的想法，一个轻巧的记号。'}.get(self.mode,'不必整理得井井有条，先把想法留下。'))
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
                elif n['archived'] and not (self.mode=='所有便签' and query): continue
                if self.mode=='收藏' and not n['favorite']: continue
                if self.mode=='待办' and not pending(n): continue
                if self.mode=='今日' and n['updated_at'][:10]!=datetime.now().date().isoformat() and n['created_at'][:10]!=datetime.now().date().isoformat(): continue
                if self.mode=='标签' and self.tag_filter.currentIndex()>0 and self.tag_filter.currentText() not in n['tags']: continue
            if query and query not in (title(n)+' '+n['plain']+' '+' '.join(n['tags'])).casefold(): continue
            notes.append(n)
        notes.sort(key=lambda n:(n['favorite'],n['updated_at']),reverse=True)
        self.count.setText(f'{len(notes)} 张纸片')
        container=QWidget()
        container.setStyleSheet('background:transparent;')
        grid=QGridLayout(container)
        grid.setContentsMargins(0,2,8,12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        columns=max(2,(self.width()-290)//270)
        if notes:
            for i,n in enumerate(notes):
                grid.addWidget(Card(self.controller,n,self.mode),i//columns,i%columns)
            for col in range(columns):
                grid.setColumnStretch(col,1)
            grid.setRowStretch((len(notes)-1)//columns+1,1)
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
        layout.addWidget(label('记点什么。',23,'#425D4D',True))
        self.editor=Editor()
        self.editor.setPlaceholderText('灵感跑得很快，先把它留下。')
        self.editor.setHtml(controller.store.get_meta('capture_draft',''))
        self.draft_timer=QTimer(self)
        self.draft_timer.setSingleShot(True)
        self.draft_timer.setInterval(400)
        self.draft_timer.timeout.connect(self.save_draft)
        self.editor.textChanged.connect(lambda:self.draft_timer.start())
        layout.addWidget(self.editor,1)
        row=QHBoxLayout()
        row.addWidget(label('Esc 暂收起 · 内容会留在这里',11,'#91998B'))
        row.addStretch()
        row.addWidget(button('放进抽屉  ↵',self.capture,'Ctrl+Enter',True))
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
        layout.addWidget(label('让纸片合你的习惯',24,'#3E5140',True))
        layout.addWidget(label('安静地待在桌面，其他的由你决定。',12,'#8A9383'))
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
        about.addRow(label('小纸片  1.0.3',24,'#425D4D',True))
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
