"""Small, font-independent line icons painted in logical coordinates."""
import math

from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QIcon
from PySide6.QtWidgets import QPushButton


def draw_symbol(p, name, rect, color='#52634F', active=False):
    p.save()
    p.translate(rect.x(), rect.y())
    p.scale(rect.width()/24, rect.height()/24)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color),1.7,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    def line(*points):
        path=QPainterPath(QPointF(*points[0]))
        for point in points[1:]: path.lineTo(*point)
        p.drawPath(path)
    def box(x,y,w,h,r=2): p.drawRoundedRect(QRectF(x,y,w,h),r,r)
    if name in ('notes','paper'):
        if name=='notes': line((4,16),(3,5),(15,3))
        box(7,6,13,15)
        line((10,11),(16,11));line((10,15),(15,15))
    elif name=='today':
        p.drawEllipse(QRectF(8,8,8,8))
        for i in range(8):
            a=i*math.pi/4
            line((12+7*math.cos(a),12+7*math.sin(a)),(12+9*math.cos(a),12+9*math.sin(a)))
    elif name=='star':
        path=QPainterPath()
        for i in range(10):
            a=-math.pi/2+i*math.pi/5
            r=9 if i%2==0 else 4.4
            pt=QPointF(12+r*math.cos(a),12+r*math.sin(a))
            if i==0:path.moveTo(pt)
            else:path.lineTo(pt)
        path.closeSubpath()
        if active:p.setBrush(QColor('#D5AF56'))
        p.drawPath(path)
    elif name=='todo':
        box(4,4,16,16,3);line((8,12),(11,15),(17,9))
    elif name=='tag':
        line((4,4),(12,4),(21,13),(13,21),(4,12),(4,4))
        p.drawEllipse(QRectF(7,7,2,2))
    elif name=='archive':
        box(3,4,18,5,1.5);line((5,9),(5,20),(19,20),(19,9));line((10,13),(14,13))
    elif name=='trash':
        line((4,6),(20,6));line((9,6),(9,3),(15,3),(15,6))
        line((6,9),(7,21),(17,21),(18,9));line((10,10),(10.5,17));line((14,10),(13.5,17))
    elif name=='settings':
        for y,x in ((6,9),(12,16),(18,7)):
            line((4,y),(20,y))
            p.setBrush(QColor('#EEEFE7'));p.drawEllipse(QRectF(x-2,y-2,4,4));p.setBrush(Qt.NoBrush)
    elif name=='open':
        line((10,5),(5,5),(5,20),(19,20),(19,14));line((13,4),(20,4),(20,11));line((11,13),(20,4))
    elif name=='plus':
        line((12,5),(12,19));line((5,12),(19,12))
    elif name=='minus': line((5,12),(19,12))
    elif name=='more':
        p.setBrush(QColor(color));p.setPen(Qt.NoPen)
        for x in (5,12,19):p.drawEllipse(QRectF(x-1.4,10.6,2.8,2.8))
    elif name=='pin':
        if active:p.setBrush(QColor('#A6BE91'))
        path=QPainterPath(QPointF(8,3));path.lineTo(17,3);path.lineTo(15,10)
        path.lineTo(19,15);path.lineTo(5,15);path.lineTo(9,10);path.closeSubpath();p.drawPath(path)
        line((12,15),(11,22))
    elif name=='palette':
        path=QPainterPath(QPointF(20,14));path.cubicTo(24,4,10,0,5,6)
        path.cubicTo(-1,13,6,23,12,21);path.cubicTo(17,19,10,17,14,15)
        path.cubicTo(16,14,19,17,20,14);p.drawPath(path)
        p.setPen(Qt.NoPen)
        for x,y,c in ((7,10,'#C99586'),(11,6,'#CAB06D'),(16,8,'#8BA3B0')):
            p.setBrush(QColor(c));p.drawEllipse(QRectF(x-1.6,y-1.6,3.2,3.2))
    elif name=='bold':
        path=QPainterPath(QPointF(7,4));path.lineTo(7,20);path.lineTo(13,20)
        path.cubicTo(21,20,21,11,13,11);path.lineTo(7,11);path.lineTo(12,11)
        path.cubicTo(19,11,19,4,12,4);path.closeSubpath();p.drawPath(path)
    elif name=='strike':
        path=QPainterPath(QPointF(18,6));path.cubicTo(11,0,4,5,8,10)
        path.moveTo(15,14);path.cubicTo(22,20,10,24,6,18);p.drawPath(path);line((3,12),(21,12))
    elif name=='highlight':
        line((6,15),(14,4),(20,8),(12,19),(6,15),(5,20),(10,20))
        p.setPen(QPen(QColor('#C5A351'),2.5,Qt.SolidLine,Qt.RoundCap));line((3,23),(19,23))
    elif name=='link':
        path=QPainterPath(QPointF(10,7));path.cubicTo(18,-2,26,6,17,14)
        path.moveTo(14,17);path.cubicTo(6,26,-2,18,7,10);p.drawPath(path);line((8,16),(16,8))
    elif name=='clear':
        line((4,5),(18,5));line((11,5),(9,19));line((16,15),(22,21));line((22,15),(16,21))
    else:
        raise ValueError(f'Unknown icon: {name}')
    p.restore()


def line_icon(name,color='#52634F',active=False):
    result=QIcon()
    for size in (20,24,32,40,48,64):
        pixmap=QPixmap(size,size);pixmap.fill(Qt.transparent)
        p=QPainter(pixmap);draw_symbol(p,name,QRectF(0,0,size,size),color,active);p.end()
        result.addPixmap(pixmap)
    return result


def brand_icon():
    result=QIcon()
    for size in (16,32,48,64,128,256):
        pixmap=QPixmap(size,size);pixmap.fill(Qt.transparent)
        p=QPainter(pixmap);p.setRenderHint(QPainter.Antialiasing);p.scale(size/64,size/64)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#DFE6D4'));p.drawRoundedRect(QRectF(1,1,62,62),17,17)
        p.translate(32,32);p.rotate(-7);p.translate(-32,-32)
        p.setBrush(QColor('#C1CDB5'));p.drawRoundedRect(QRectF(15,14,36,42),5,5)
        path=QPainterPath(QPointF(19,10));path.lineTo(46,10);path.quadTo(49,10,49,14)
        path.lineTo(49,39);path.lineTo(38,51);path.lineTo(18,51);path.quadTo(14,51,14,47)
        path.lineTo(14,15);path.quadTo(14,10,19,10)
        p.setBrush(QColor('#FAE9AE'));p.setPen(QPen(QColor('#52664B'),1.5,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawPath(path)
        fold=QPainterPath(QPointF(38,51));fold.lineTo(38,43);fold.quadTo(38,39,42,39);fold.lineTo(49,39)
        p.setBrush(QColor('#FFF5D7'));p.drawPath(fold)
        p.setPen(QPen(QColor('#738165'),2.5,Qt.SolidLine,Qt.RoundCap))
        p.drawLine(QPointF(22,24),QPointF(40,24));p.drawLine(QPointF(22,31),QPointF(35,31))
        p.setPen(Qt.NoPen);p.setBrush(QColor('#9CAD88'));p.drawRoundedRect(QRectF(25,6,14,9),2,2)
        p.end();result.addPixmap(pixmap)
    return result


class IconButton(QPushButton):
    """Stable hit target with state-aware vector artwork, independent of fonts."""
    def __init__(self,name,callback,tip,size=32,danger=False,dark=False):
        super().__init__()
        self.symbol=name;self.danger=danger;self.dark=dark
        self.setFixedSize(size,size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip);self.setAccessibleName(tip)
        self.clicked.connect(callback)
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        hovered=self.underMouse() and self.isEnabled()
        active=self.isChecked()
        bg=QColor(255,255,255,22) if self.dark else QColor(255,255,255,65)
        color='#E5EBDD' if self.dark else '#607055'
        if active:
            bg=QColor('#EBD69C') if self.symbol=='star' else QColor('#CCDBBA')
            color='#8F6D27' if self.symbol=='star' else '#40573C'
        if hovered:
            bg=QColor(255,255,255,50) if self.dark else QColor(255,255,255,150)
            if self.danger:bg=QColor('#F2DAD1');color='#AB5149'
        if self.isDown():bg=QColor('#D1DBC3') if not self.danger else QColor('#E9C4BA')
        p.setPen(QPen(QColor(100,115,90,25),1));p.setBrush(bg)
        p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),8,8)
        side=18 if self.width()<32 else 19
        draw_symbol(p,self.symbol,QRectF((self.width()-side)/2,(self.height()-side)/2,side,side),color,active)
        if self.hasFocus():
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#8FA580'),1,Qt.DotLine))
            p.drawRoundedRect(QRectF(2,2,self.width()-4,self.height()-4),6,6)
        p.end()
