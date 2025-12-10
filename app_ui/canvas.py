from typing import Optional
import logging
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem
from PyQt6.QtGui import QPainter, QPixmap, QImage, QPen, QColor, QCursor
from PyQt6.QtCore import Qt, QPoint
from app_ui.labelsgl import ParentLabelList
from app_ui.label_draw_manage import LabelDrawManager
from services.auto_annotation_manager import get_auto_annotation_manager
from app_ui.mouse_decorator import MouseDecoratorManager
from app_ui.choose_moon import handle_mouse_move_event, choose_your

logger = logging.getLogger(__name__)

class GraphicsCanvas(QGraphicsView):
    """图形画布视图：负责图片显示、绘制交互与模式切换。

    - 显示当前图片并维护场景对象
    - 分发鼠标事件到绘制管理器
    - 管理 MASK/OBB/BBOX 等模式与自由画笔
    """

    class LabelRectItem(QGraphicsRectItem):
        """矩形框图元，承载单个子标签的矩形框。"""

        def __init__(self, x: float, y: float, w: float, h: float, 
                     child_label=None, parent_view: Optional['GraphicsCanvas'] = None):
            super().__init__(x, y, w, h)
            self.child_label = child_label
            self.parent_view = parent_view
            self._setup_item_properties()

        def _setup_item_properties(self) -> None:
            """设置基础交互属性。"""
            self.setAcceptHoverEvents(True)

    def __init__(self, parent_label_list=None, get_image_info_func=None, parent=None):
        """初始化画布。

        Args:
            parent_label_list: 父标签列表引用
            get_image_info_func: 获取当前图片信息的函数
            parent: 主窗口引用
        """

        try:           
            super().__init__(parent)

            self.scene = QGraphicsScene(self)
            self.setScene(self.scene)
            self.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setMouseTracking(True)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

            self.parent_label_list = parent_label_list
            self.get_image_info_func = get_image_info_func
            self.main_window = parent

            self.image_item: Optional[QGraphicsPixmapItem] = None
            self.current_pixmap: Optional[QPixmap] = None

            self.drawing = False
            self.rect_start: Optional[QPoint] = None
            self.end_point: Optional[QPoint] = None  
            self.temp_rect_item: Optional[QGraphicsRectItem] = None  # BBOX 临时矩形
            
            self.ui_locked = False
            self.pan_mode = False
            self.delete_select_mode = False
            self.delete_select_start: Optional[QPoint] = None
            
            self.draw_manager = LabelDrawManager(
                canvas_view=self,
                parent_label_list=parent_label_list,
                get_image_info_func=get_image_info_func
            )
            
            self.polygon_mode = False
            self.mask_mode = False
            self.obb_mode = False
            
            self.free_mode = False
            self.free_brush_type: Optional[str] = None
            
            self.auto_annotation_manager = None
            
            self.mouse_decorator_manager = MouseDecoratorManager(self)  # 十字准星等装饰
            
        except Exception as e:
            logger.error(f"初始化GraphicsCanvas时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")

    def update_rects(self) -> None:
        """刷新并重绘当前矩形框。"""
        try:
            if hasattr(self, 'draw_manager'):
                self.draw_manager.update_rects()
        except Exception as e:
            logger.error(f"更新矩形框时发生错误: {e}")

    def wheelEvent(self, event):
        """滚轮缩放并更新装饰。"""

        try:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(factor, factor)
            
            if hasattr(self, 'mouse_decorator_manager') and self.mouse_decorator_manager:
                if self.mouse_decorator_manager.is_crosshair_enabled():
                    cursor_pos = self.mapFromGlobal(QCursor.pos())
                    scene_pos = self.mapToScene(cursor_pos)
                    self.mouse_decorator_manager.crosshair_decorator.update_crosshair(scene_pos)
        except Exception as e:
            logger.error(f"处理滚轮事件时发生错误: {e}")

    def mousePressEvent(self, event):
        """处理鼠标按下：模式优先，未处理时交给默认行为。"""

        if self.ui_locked or self.pan_mode:
            logger.debug("画布事件被跳过：UI锁定或平移模式，无法处理绘制")
            super().mousePressEvent(event)
            return

        try:
            if self.delete_select_mode:
                if event.button() == Qt.MouseButton.RightButton:
                    if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                        self.scene.removeItem(self.bbox_temp_item)
                        self.bbox_temp_item = None
                    self.delete_select_start = None
                    self.delete_select_mode = False
                    return
                if event.button() == Qt.MouseButton.LeftButton:
                    scene_pos = self.mapToScene(event.pos())
                    x, y = scene_pos.x(), scene_pos.y()
                    self.delete_select_start = (x, y)
                    
                    if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                        self.scene.removeItem(self.bbox_temp_item)
                        self.bbox_temp_item = None
                    self.bbox_temp_item = QGraphicsRectItem(x, y, 0, 0)
                    self.bbox_temp_item.setPen(QPen(QColor(255, 0, 0), 2))
                    self.scene.addItem(self.bbox_temp_item)
                    return
            if self.mask_mode:
                if self.auto_annotation_manager is None and self.main_window:
                    self.auto_annotation_manager = get_auto_annotation_manager(
                        self.main_window, self.parent_label_list, self
                    )
                if hasattr(self, 'bbox_input_mode') and self.bbox_input_mode:
                    scene_pos = self.mapToScene(event.pos())
                    x, y = scene_pos.x(), scene_pos.y()
                    self.bbox_start_point = (x, y)  # 记录BBOX起点
                    
                    if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                        self.scene.removeItem(self.bbox_temp_item)
                        self.bbox_temp_item = None
                    self.bbox_temp_item = QGraphicsRectItem(x, y, 0, 0)  # 创建临时框
                    self.bbox_temp_item.setPen(QPen(QColor(0, 255, 0), 2, Qt.PenStyle.DashLine))
                    self.scene.addItem(self.bbox_temp_item)
                    return
                if self.auto_annotation_manager:
                    handled = self.auto_annotation_manager.handle_mouse_press(event, self)
                    if handled:
                        return
            if self.obb_mode:
                if self.auto_annotation_manager is None and self.main_window:
                    self.auto_annotation_manager = get_auto_annotation_manager(
                        self.main_window, self.parent_label_list, self
                    )
                if hasattr(self, 'bbox_input_mode') and self.bbox_input_mode:
                    scene_pos = self.mapToScene(event.pos())
                    x, y = scene_pos.x(), scene_pos.y()
                    self.bbox_start_point = (x, y)
                    
                    if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                        self.scene.removeItem(self.bbox_temp_item)
                        self.bbox_temp_item = None
                    self.bbox_temp_item = QGraphicsRectItem(x, y, 0, 0)
                    self.bbox_temp_item.setPen(QPen(QColor(0, 255, 0), 2, Qt.PenStyle.DashLine))
                    self.scene.addItem(self.bbox_temp_item)
                    return
                if self.auto_annotation_manager:
                    handled = self.auto_annotation_manager.handle_mouse_press(event, self)
                    if handled:
                        return  
            if hasattr(self, 'draw_manager'):
                if self.free_mode and self.free_brush_type:
                    if self.free_brush_type == 'point':
                        handled = self.draw_manager.point_huabi('press', event)
                    elif self.free_brush_type == 'line':
                        handled = self.draw_manager.line_huabi('press', event)
                    elif self.free_brush_type == 'triangle':
                        handled = self.draw_manager.regular_polygon_huabi('press', event, 3)
                    elif self.free_brush_type == 'hexagon':
                        handled = self.draw_manager.regular_polygon_huabi('press', event, 6)
                    elif self.free_brush_type == 'octagon':
                        handled = self.draw_manager.regular_polygon_huabi('press', event, 8)
                    elif self.free_brush_type == 'circle':
                        handled = self.draw_manager.circle_huabi('press', event)
                    else:
                        handled = False
                elif self.polygon_mode:
                    handled = self.draw_manager.polygon_huabi('press', event)
                else:
                    handled = self.draw_manager.rect_huabi('press', event)
                if not handled:
                    super().mousePressEvent(event)
            else:
                super().mousePressEvent(event)
            scene_pos = self.mapToScene(event.pos())
            x, y = scene_pos.x(), scene_pos.y()
            choose_your(self, x, y)
        except Exception as e:
            logger.error(f"处理鼠标按下事件时发生错误: {e}")

    def mouseMoveEvent(self, event):
        """处理鼠标移动：更新临时BBOX或分发到绘制管理器。"""
        if self.ui_locked or self.pan_mode:
            logger.debug("画布事件被跳过：UI锁定或平移模式，无法处理绘制")
            super().mouseMoveEvent(event)
            if hasattr(self, 'mouse_decorator_manager') and self.mouse_decorator_manager:
                if self.mouse_decorator_manager.is_crosshair_enabled():
                    scene_pos = self.mapToScene(event.pos())
                    self.mouse_decorator_manager.crosshair_decorator.update_crosshair(scene_pos)
            return

        try:
            if self.delete_select_mode and self.delete_select_start:
                scene_pos = self.mapToScene(event.pos())
                x, y = scene_pos.x(), scene_pos.y()
                start_x, start_y = self.delete_select_start
                rect_x = min(start_x, x)
                rect_y = min(start_y, y)
                rect_width = abs(x - start_x)
                rect_height = abs(y - start_y)
                if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                    self.bbox_temp_item.setRect(rect_x, rect_y, rect_width, rect_height)
                return
            if (self.mask_mode or self.obb_mode) and hasattr(self, 'bbox_input_mode') and self.bbox_input_mode:
                if hasattr(self, 'bbox_start_point') and self.bbox_start_point:
                    scene_pos = self.mapToScene(event.pos())
                    x, y = scene_pos.x(), scene_pos.y()
                    start_x, start_y = self.bbox_start_point
                    rect_x = min(start_x, x)
                    rect_y = min(start_y, y)
                    rect_width = abs(x - start_x)
                    rect_height = abs(y - start_y)
                    if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                        self.bbox_temp_item.setRect(rect_x, rect_y, rect_width, rect_height)
                    return
            if hasattr(self, 'draw_manager'):
                if self.free_mode and self.free_brush_type:
                    if self.free_brush_type == 'point':
                        handled = self.draw_manager.point_huabi('move', event)
                    elif self.free_brush_type == 'line':
                        handled = self.draw_manager.line_huabi('move', event)
                    elif self.free_brush_type == 'circle':
                        handled = self.draw_manager.circle_huabi('move', event)
                    elif self.free_brush_type == 'triangle':
                        handled = self.draw_manager.regular_polygon_huabi('move', event, 3)
                    elif self.free_brush_type == 'hexagon':
                        handled = self.draw_manager.regular_polygon_huabi('move', event, 6)
                    elif self.free_brush_type == 'octagon':
                        handled = self.draw_manager.regular_polygon_huabi('move', event, 8)
                    else:
                        handled = False
                elif self.polygon_mode:
                    handled = self.draw_manager.polygon_huabi('move', event)
                else:
                    handled = self.draw_manager.rect_huabi('move', event)
                if not handled:
                    super().mouseMoveEvent(event)
            else:
                super().mouseMoveEvent(event)
            handle_mouse_move_event(self, event)
        except Exception as e:
            logger.error(f"处理鼠标移动事件时发生错误: {e}")

    def mouseReleaseEvent(self, event):
        """处理鼠标释放：提交BBOX或结束当前绘制。"""

        if self.ui_locked or self.pan_mode:
            logger.debug("画布事件被跳过：UI锁定或平移模式，无法处理绘制")
            super().mouseReleaseEvent(event)
            return

        try:
            if self.delete_select_mode and self.delete_select_start:
                scene_pos = self.mapToScene(event.pos())
                x, y = scene_pos.x(), scene_pos.y()
                start_x, start_y = self.delete_select_start
                bbox_x1 = min(start_x, x)
                bbox_y1 = min(start_y, y)
                bbox_x2 = max(start_x, x)
                bbox_y2 = max(start_y, y)
                if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                    self.scene.removeItem(self.bbox_temp_item)
                    self.bbox_temp_item = None
                self.delete_select_start = None
                self.delete_select_mode = False
                try:
                    from delet_moon import delete_child_label_by_object
                    sel_rect = (bbox_x1, bbox_y1, bbox_x2, bbox_y2)
                    for item in list(self.scene.items()):
                        if hasattr(item, 'child_label') and item.child_label:
                            br = item.mapToScene(item.boundingRect()).boundingRect()
                            ix1, iy1, ix2, iy2 = br.left(), br.top(), br.right(), br.bottom()
                            if ix1 >= sel_rect[0] and iy1 >= sel_rect[1] and ix2 <= sel_rect[2] and iy2 <= sel_rect[3]:
                                delete_child_label_by_object(self, item.child_label)
                except Exception:
                    pass
                return
            if (self.mask_mode or self.obb_mode) and hasattr(self, 'bbox_input_mode') and self.bbox_input_mode:
                if hasattr(self, 'bbox_start_point') and self.bbox_start_point:
                    scene_pos = self.mapToScene(event.pos())
                    x, y = scene_pos.x(), scene_pos.y()
                    start_x, start_y = self.bbox_start_point
                    bbox_x1 = min(start_x, x)
                    bbox_y1 = min(start_y, y)
                    bbox_x2 = max(start_x, x)
                    bbox_y2 = max(start_y, y)
                    if hasattr(self, 'auto_annotation_manager') and self.auto_annotation_manager:
                        if self.mask_mode and self.auto_annotation_manager.mask_sam_manager:
                            self.auto_annotation_manager.mask_sam_manager.add_bbox(bbox_x1, bbox_y1, bbox_x2, bbox_y2)
                        if self.obb_mode and self.auto_annotation_manager.obb_sam_manager:
                            self.auto_annotation_manager.obb_sam_manager.add_bbox(bbox_x1, bbox_y1, bbox_x2, bbox_y2)
                    if hasattr(self, 'bbox_temp_item') and self.bbox_temp_item:
                        self.scene.removeItem(self.bbox_temp_item)
                        self.bbox_temp_item = None
                    self.bbox_start_point = None
                    return
            if hasattr(self, 'draw_manager'):
                if self.free_mode and self.free_brush_type:
                    if self.free_brush_type == 'point':
                        handled = self.draw_manager.point_huabi('release', event)
                    elif self.free_brush_type == 'line':
                        handled = self.draw_manager.line_huabi('release', event)
                    elif self.free_brush_type == 'triangle':
                        handled = self.draw_manager.regular_polygon_huabi('release', event, 3)
                    elif self.free_brush_type == 'hexagon':
                        handled = self.draw_manager.regular_polygon_huabi('release', event, 6)
                    elif self.free_brush_type == 'octagon':
                        handled = self.draw_manager.regular_polygon_huabi('release', event, 8)
                    elif self.free_brush_type == 'circle':
                        handled = self.draw_manager.circle_huabi('release', event)
                    else:
                        handled = False
                elif self.polygon_mode:
                    handled = self.draw_manager.polygon_huabi('release', event)
                else:
                    handled = self.draw_manager.rect_huabi('release', event)
                if not handled:
                    super().mouseReleaseEvent(event)
            else:
                super().mouseReleaseEvent(event)
        except Exception as e:
            logger.error(f"处理鼠标释放事件时发生错误: {e}")

    def set_ui_locked(self, locked: bool) -> None:
        """设置 UI 锁定状态并同步绘制管理器。"""

        self.ui_locked = locked
        if locked and not self.pan_mode:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        elif not locked and not self.pan_mode:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        if hasattr(self, 'draw_manager'):
            self.draw_manager.set_ui_locked(locked)
    
    def set_pan_mode(self, enabled: bool) -> None:
        """开启/关闭平移模式，并调整拖动行为。"""
        self.pan_mode = enabled
        self.ui_locked = enabled
        if enabled:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            if self.ui_locked:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            else:
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        if hasattr(self, 'draw_manager'):
            self.draw_manager.set_ui_locked(enabled)
    
    def set_polygon_mode(self, enabled: bool) -> None:
        """开启/关闭多边形模式。"""
        self.polygon_mode = enabled
        if enabled:
            self.pan_mode = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_mode(self, mode: str) -> None:
        """设置绘制模式：rect/polygon/mask/obb/pan。"""
        try:
            self.polygon_mode = False
            self.mask_mode = False
            self.obb_mode = False
            self.pan_mode = False
            self.free_mode = False
            self.ui_locked = False
            if mode == 'rect':
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            elif mode == 'polygon':
                self.polygon_mode = True
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            elif mode == 'mask':
                self.mask_mode = True
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            elif mode == 'obb':
                self.obb_mode = True
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            elif mode == 'pan':
                self.pan_mode = True
                self.ui_locked = True
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            else:
                logger.warning(f"未知的模式名称: {mode}")
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        except Exception as e:
            logger.error(f"设置模式时发生错误: {e}")

    def update_rects(self) -> None:
        try:
            if hasattr(self, 'draw_manager'):
                self.draw_manager.update_rects()
        except Exception as e:
            logger.error(f"更新矩形框时发生错误: {e}")

    def load_image(self, file_path: str) -> bool:
        """加载图片到场景并重置视图。"""
        try:
            image = self.main_window.resource_manager.load_image_safe(file_path)
            if not image:
                logger.warning(f"无法加载图片: {file_path}")
                return False
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                logger.warning(f"无法从QImage创建QPixmap: {file_path}")
                return False
            if self.image_item:
                self.scene.removeItem(self.image_item)
                self.image_item = None
            self.image_item = QGraphicsPixmapItem(pixmap)
            self.image_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            self.image_item.setZValue(-1)
            self.scene.addItem(self.image_item)
            self.current_pixmap = pixmap
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            self.resetTransform()
            if hasattr(self, 'mouse_decorator_manager') and self.mouse_decorator_manager:
                if self.mouse_decorator_manager.is_crosshair_enabled():
                    cursor_pos = self.mapFromGlobal(QCursor.pos())
                    scene_pos = self.mapToScene(cursor_pos)
                    self.mouse_decorator_manager.crosshair_decorator.update_crosshair(scene_pos)
            self.update_rects()
            return True
        except Exception as e:
            logger.error(f"加载图片到画布时发生错误 {file_path}: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
            return False
