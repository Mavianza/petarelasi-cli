"""Interactive view using the exact table positions and FK routes used by exports."""
from math import ceil, floor

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from ..layout import HEADER, ROW, WIDTH, layout


INK = QColor('#203b3a')
TEAL = QColor('#087d72')


def font(size=12, bold=False, mono=False):
    result = QFont('Consolas' if mono else 'Segoe UI')
    result.setPixelSize(size)
    result.setBold(bold)
    return result


class TableItem(QGraphicsObject):
    activated = Signal(str, str)

    def __init__(self, box, foreign):
        super().__init__()
        self.box = box
        self.foreign = foreign
        self.active = False
        self.active_column = ''
        self.setPos(box.x, box.y)
        self.setZValue(2)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def boundingRect(self):
        return QRectF(-2, -2, WIDTH + 4, self.box.height + 4)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(0, 0, WIDTH, self.box.height), 7, 7)
        painter.save()
        painter.setClipPath(shape)
        painter.fillRect(QRectF(0, 0, WIDTH, self.box.height), QColor('#ffffff'))
        painter.fillRect(QRectF(0, 0, WIDTH, HEADER), INK)
        painter.setPen(QColor('#ffffff'))
        painter.setFont(font(13, True))
        title = painter.fontMetrics().elidedText(self.box.table.name, Qt.TextElideMode.ElideMiddle, WIDTH - 26)
        painter.drawText(QRectF(13, 0, WIDTH - 26, HEADER), Qt.AlignmentFlag.AlignVCenter, title)
        for index, column in enumerate(self.box.table.columns):
            y = HEADER + ROW * index
            selected = self.active and self.active_column == column.name
            painter.fillRect(QRectF(0, y, WIDTH, ROW), QColor('#e2f3ec' if selected else ('#f3f6f5' if index % 2 == 0 else '#ffffff')))
            painter.setFont(font(10, True))
            badge = ('PK' + str(column.pk)) if column.pk else ''
            if (self.box.table.name, column.name) in self.foreign:
                badge += '/FK' if badge else 'FK'
            painter.setPen(QColor('#8d5b0c') if column.pk else TEAL)
            painter.drawText(QRectF(10, y, 52, ROW), Qt.AlignmentFlag.AlignVCenter, badge)
            painter.setFont(font(12, mono=True))
            painter.setPen(INK)
            name = painter.fontMetrics().elidedText(column.name, Qt.TextElideMode.ElideRight, 125)
            painter.drawText(QRectF(63, y, 128, ROW), Qt.AlignmentFlag.AlignVCenter, name)
            painter.setFont(font(10, mono=True))
            painter.setPen(QColor('#71817a'))
            kind = painter.fontMetrics().elidedText(column.type, Qt.TextElideMode.ElideRight, 75)
            painter.drawText(QRectF(192, y, 76, ROW), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, kind)
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(TEAL if self.active else QColor('#bdcdc6'), 2.4 if self.active else 1))
        painter.drawRoundedRect(QRectF(0, 0, WIDTH, self.box.height), 7, 7)

    def column_at(self, y):
        index = floor((y - HEADER) / ROW)
        return self.box.table.columns[index].name if 0 <= index < len(self.box.table.columns) else ''

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.box.table.name, self.column_at(event.pos().y()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def hoverMoveEvent(self, event):
        column = self.column_at(event.pos().y())
        self.setToolTip(self.box.table.name + ('.' + column if column else '') + '\nKlik untuk melihat penjelasan.')
        super().hoverMoveEvent(event)


class EdgeItem(QGraphicsPathItem):
    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())


class DiagramView(QGraphicsView):
    table_selected = Signal(str, str)
    relation_selected = Signal(object)
    zoom_changed = Signal(int)
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('diagramView')
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setBackgroundBrush(QColor('#f1f5f0'))
        self.setAcceptDrops(True)
        self.tables = {}
        self.edges = []
        self.current_schema = None
        self.diagram = None

    def show_schema(self, schema):
        self.scene().clear()
        self.tables, self.edges = {}, []
        self.current_schema = schema
        self.diagram = layout(schema)
        foreign = {(ref.table, col) for ref in schema.foreign_keys for col in ref.columns}
        for wire in self.diagram.wires:
            number = int(wire.key.split('.')[0][1:]) - 1
            reference = schema.foreign_keys[number]
            path = QPainterPath(QPointF(*wire.points[0]))
            for point in wire.points[1:]:
                path.lineTo(QPointF(*point))
            edge = EdgeItem(path)
            edge.setPen(QPen(QColor(wire.color), 1.6))
            edge.setCursor(Qt.CursorShape.PointingHandCursor)
            edge.setData(0, 'relation')
            edge.setData(1, reference)
            edge.setToolTip(wire.key + ' · ' + reference.table + ' → ' + reference.references + '\nKlik untuk melihat pasangan kolom.')
            self.scene().addItem(edge)
            x, y = wire.points[-1]
            base = x + (8 if wire.target_side else -8)
            arrow = self.scene().addPolygon(QPolygonF([QPointF(x, y), QPointF(base, y - 4), QPointF(base, y + 4)]),
                                           QPen(QColor(wire.color)), QColor(wire.color))
            arrow.setData(0, 'relation')
            arrow.setData(1, reference)
            label = self.scene().addSimpleText(wire.key, font(9, True))
            label.setBrush(QColor(wire.color))
            label.setPos((wire.points[2][0] + wire.points[3][0]) / 2 - 12, wire.points[2][1] + 2)
            label.setData(0, 'relation')
            label.setData(1, reference)
            self.edges.append((edge, arrow, label, wire, reference))
        for box in self.diagram.boxes:
            item = TableItem(box, foreign)
            item.activated.connect(self.table_selected)
            self.scene().addItem(item)
            self.tables[box.table.name] = item
        self.scene().setSceneRect(0, 0, self.diagram.width, self.diagram.height)
        self.fit_diagram()

    def select(self, table='', column='', reference=None):
        for name, item in self.tables.items():
            item.active = name == table or (reference is not None and name in {reference.table, reference.references})
            item.active_column = column if name == table else ''
            item.update()
        for edge, arrow, label, wire, ref in self.edges:
            if reference is not None:
                active = ref == reference
            elif table:
                active = ((ref.table == table and (not column or column in ref.columns))
                          or (ref.references == table and (not column or column in ref.ref_columns)))
            else:
                active = True
            edge.setPen(QPen(QColor(wire.color), 3 if active and (table or reference) else 1.6))
            for item in (edge, arrow, label):
                item.setOpacity(1 if active else 0.18)

    def fit_diagram(self):
        if not self.scene().items():
            return
        self.fitInView(self.sceneRect().adjusted(-20, -20, 20, 20), Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 1.15:
            self.scale(1.15 / self.transform().m11(), 1.15 / self.transform().m11())
        self.zoom_changed.emit(round(self.transform().m11() * 100))

    def zoom(self, factor):
        current = self.transform().m11()
        target = max(0.15, min(3.0, current * factor))
        self.scale(target / current, target / current)
        self.zoom_changed.emit(round(target * 100))

    def wheelEvent(self, event):
        if event.angleDelta().y():
            self.zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(0) == 'relation':
            self.relation_selected.emit(item.data(1))
            event.accept()
            return
        super().mousePressEvent(event)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.setPen(QPen(QColor('#dbe4db'), 1))
        step = 24
        points = [QPointF(x, y) for x in range(floor(rect.left() / step) * step, ceil(rect.right()), step)
                  for y in range(floor(rect.top() / step) * step, ceil(rect.bottom()), step)]
        if points:
            painter.drawPoints(points)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            self.file_dropped.emit(event.mimeData().urls()[0].toLocalFile())
            event.acceptProposedAction()
        else:
            event.ignore()
