"""Render our own Qt widgets to image files with isolated demonstration data."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickies.app import create_application,Controller
from stickies.store import Store
from stickies.manager import Settings

app=create_application()
temp=tempfile.TemporaryDirectory()
store=Store(temp.name)
store.set_meta('onboarded',True)
store.save_settings({'hover_toolbar':False})
c=Controller(app,store,testing=True)
examples=[
 ('今天，慢慢来。\n\n☐ 把方案的最后一页补齐\n☑ 给绿植浇水\n☐ 六点前收工，去散个步','奶油黄',['生活'],True),
 ('一些冒出来的灵感\n\n登录页可以试试卡片翻转。\n让等待也变成一个小惊喜。\n\n去找找 Lottie 的参考。','鼠尾草',['灵感','设计'],True),
 ('周末的采购清单\n\n☐ 燕麦奶 × 2\n☐ 新鲜咖啡豆\n☑ 一束随便什么花','樱花粉',['生活'],False),
 ('留给未来的自己\n\n不用一下子想明白所有事情。\n先做一点点，也很好。','雾蓝',[],False),
 ('下周的小计划\n\n☐ 整理一下桌面\n☐ 读完那篇收藏的文章\n☐ 约朋友吃顿饭','丁香紫',['计划'],False),
 ('一个好用的快捷键\n\nCtrl + Alt + Space\n\n想到什么，随手记下。\n灵感不需要排队。','白纸',['小技巧'],False),
]
for text,color,tags,favorite in examples:
    n=store.new(text)
    n.update(color=color,tags=tags,favorite=favorite)
    store.save(n)
c.manager.render()
c.manager.show()
app.processEvents()
out=Path(__file__).resolve().parents[1]/'artifacts'
out.mkdir(exist_ok=True)
c.manager.grab().save(str(out/'manager.png'))
first=store.all()[0]
c.open_note(first['id'])
w=c.windows[first['id']]
w.resize(350,390)
app.processEvents()
w.grab().save(str(out/'note.png'))
c.manager.search.setText('生活')
c.manager.render()
c.manager.select_result(0)
app.processEvents()
c.manager.grab().save(str(out/'search.png'))
c.capture()
c.capture_window.editor.setPlainText('周五讨论新方案\n\n带上两版首页草图，确认下周的交付时间。')
app.processEvents()
c.capture_window.grab().save(str(out/'capture.png'))
c.capture_window.hide()
settings=Settings(c)
settings.show()
app.processEvents()
settings.grab().save(str(out/'settings.png'))
settings.hide()
c.cleanup()
print(out)
