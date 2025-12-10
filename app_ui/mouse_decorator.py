"""
鼠标装饰器模块
实现画布区域的十字准星光标、虚线延伸和实时坐标显示功能
"""

import logging
from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QCursor, QPixmap
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsLineItem, QGraphicsTextItem

logger = logging.getLogger(__name__)


class CrosshairDecorator:
    """十字准星装饰器类，负责在画布上绘制十字准星、虚线和坐标显示"""
    
    def __init__(self, canvas_view):
        """
        初始化十字准星装饰器
        
        Args:
            canvas_view: GraphicsCanvas实例
        """
        self.canvas_view = canvas_view
        self.scene = canvas_view.scene
        
        # 十字准星相关属性
        self.crosshair_enabled = False
        self.current_pos = QPoint(0, 0)
        
        # 十字准星图形项
        self.h_line = None  # 水平线
        self.v_line = None  # 垂直线
        self.coord_text = None  # 坐标文本
        
        # 样式配置
        self.crosshair_color = QColor(255, 0, 0, 180)  # 红色，半透明
        self.line_width = 1
        self.font_size = 10
        self.coord_offset = QPoint(15, -15)  # 坐标文本相对于鼠标的偏移
        
        # 原始光标
        self.original_cursor = None
        
        # 创建自定义十字准星光标
        self._create_crosshair_cursor()
        
    def _create_crosshair_cursor(self):
        """创建自定义的十字准星光标"""
        try:
            # 创建一个透明的像素图作为光标
            cursor_size = 32
            pixmap = QPixmap(cursor_size, cursor_size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 设置画笔
            pen = QPen(self.crosshair_color, 2)
            painter.setPen(pen)
            
            # 绘制十字准星
            center = cursor_size // 2
            # 水平线
            painter.drawLine(center - 8, center, center + 8, center)
            # 垂直线
            painter.drawLine(center, center - 8, center, center + 8)
            
            painter.end()
            
            # 创建光标，热点在中心
            self.crosshair_cursor = QCursor(pixmap, center, center)
            
        except Exception as e:
            logger.error(f"创建十字准星光标时发生错误: {e}")
            # 如果创建失败，使用系统默认的十字光标
            self.crosshair_cursor = QCursor(Qt.CursorShape.CrossCursor)
    
    def enable_crosshair(self):
        """启用十字准星装饰器"""
        try:
            if not self.crosshair_enabled:
                self.crosshair_enabled = True
                
                # 保存原始光标
                self.original_cursor = self.canvas_view.cursor()
                
                # 设置十字准星光标
                self.canvas_view.setCursor(self.crosshair_cursor)
                
                logger.debug("十字准星装饰器已启用")
                
        except Exception as e:
            logger.error(f"启用十字准星装饰器时发生错误: {e}")
    
    def disable_crosshair(self):
        """禁用十字准星装饰器"""
        try:
            if self.crosshair_enabled:
                self.crosshair_enabled = False
                
                # 恢复原始光标
                if self.original_cursor:
                    self.canvas_view.setCursor(self.original_cursor)
                else:
                    self.canvas_view.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                
                # 清除十字准星图形项
                self._clear_crosshair_items()
                
                logger.debug("十字准星装饰器已禁用")
                
        except Exception as e:
            logger.error(f"禁用十字准星装饰器时发生错误: {e}")
    
    def update_crosshair(self, scene_pos):
        """
        更新十字准星位置和坐标显示
        
        Args:
            scene_pos: 鼠标在场景中的位置 (QPointF)
        """
        try:
            if not self.crosshair_enabled:
                return
            
            # 更新当前位置
            self.current_pos = QPoint(int(scene_pos.x()), int(scene_pos.y()))
            
            # 清除之前的十字准星图形项
            self._clear_crosshair_items()
            
            # 绘制新的十字准星线条（无限长虚线）
            self._draw_infinite_crosshair_lines(scene_pos)
            
            # 绘制坐标文本
            self._draw_coordinate_text(scene_pos)
            
        except Exception as e:
            logger.error(f"更新十字准星时发生错误: {e}")
    
    def _clear_crosshair_items(self):
        """清除十字准星相关的图形项"""
        try:
            if self.h_line:
                self.scene.removeItem(self.h_line)
                self.h_line = None
            
            if self.v_line:
                self.scene.removeItem(self.v_line)
                self.v_line = None
            
            if self.coord_text:
                self.scene.removeItem(self.coord_text)
                self.coord_text = None
                
        except Exception as e:
            logger.error(f"清除十字准星图形项时发生错误: {e}")
    
    def _draw_infinite_crosshair_lines(self, scene_pos):
        """
        绘制十字准星的无限长虚线延伸
        
        Args:
            scene_pos: 鼠标在场景中的位置
        """
        try:
            # 获取当前视图的缩放因子
            transform = self.canvas_view.transform()
            scale_factor = transform.m11()  # 获取X轴缩放因子
            
            # 根据缩放因子调整线条宽度，使其在视觉上保持恒定
            adjusted_line_width = self.line_width / scale_factor
            
            # 设置虚线样式
            pen = QPen(self.crosshair_color, adjusted_line_width, Qt.PenStyle.DashLine)
            
            # 获取视图的可见区域
            view_rect = self.canvas_view.viewport().rect()
            scene_rect = self.canvas_view.mapToScene(view_rect).boundingRect()
            
            # 扩展线条范围，使其看起来无限长
            extended_margin = 10000  # 扩展边距，使线条看起来无限长
            
            # 绘制水平线（从左边缘到右边缘，扩展到视图外）
            self.h_line = QGraphicsLineItem(
                scene_rect.left() - extended_margin, scene_pos.y(),
                scene_rect.right() + extended_margin, scene_pos.y()
            )
            self.h_line.setPen(pen)
            self.h_line.setZValue(1000)  # 确保在最上层
            self.scene.addItem(self.h_line)
            
            # 绘制垂直线（从上边缘到下边缘，扩展到视图外）
            self.v_line = QGraphicsLineItem(
                scene_pos.x(), scene_rect.top() - extended_margin,
                scene_pos.x(), scene_rect.bottom() + extended_margin
            )
            self.v_line.setPen(pen)
            self.v_line.setZValue(1000)  # 确保在最上层
            self.scene.addItem(self.v_line)
            
        except Exception as e:
            logger.error(f"绘制无限长十字准星线条时发生错误: {e}")
    
    def _draw_coordinate_text(self, scene_pos):
        """
        绘制坐标文本
        
        Args:
            scene_pos: 鼠标在场景中的位置
        """
        try:
            # 创建坐标文本
            coord_str = f"({int(scene_pos.x())}, {int(scene_pos.y())})"
            
            self.coord_text = QGraphicsTextItem(coord_str)
            
            # 获取当前视图的缩放因子
            transform = self.canvas_view.transform()
            scale_factor = transform.m11()  # 获取X轴缩放因子
            
            # 设置固定字体大小，不受缩放影响
            font = QFont("Arial", self.font_size)
            font.setBold(True)  # 设置粗体以提高可见性
            self.coord_text.setFont(font)
            
            # 设置文本颜色
            self.coord_text.setDefaultTextColor(self.crosshair_color)
            
            # 应用逆变换来抵消视图缩放的影响
            inverse_transform = transform.inverted()[0]
            self.coord_text.setTransform(inverse_transform)
            
            # 计算文本位置，使用视图坐标系下的固定偏移量
            # 将偏移量转换到场景坐标系，确保在不同缩放下保持一致的视觉偏移
            view_offset_x = 15  # 视图坐标系下的偏移量
            view_offset_y = -15  # 视图坐标系下的偏移量
            
            # 将视图偏移量转换为场景偏移量
            scene_offset_x = view_offset_x / scale_factor
            scene_offset_y = view_offset_y / scale_factor
            
            text_pos = QPointF(
                scene_pos.x() + scene_offset_x,
                scene_pos.y() + scene_offset_y
            )
            
            # 获取视图的可见区域（场景坐标）
            view_rect = self.canvas_view.viewport().rect()
            scene_rect = self.canvas_view.mapToScene(view_rect).boundingRect()
            
            # 获取文本边界矩形（在视图坐标系下的大小）
            font_metrics = QFontMetrics(font)
            text_rect = font_metrics.boundingRect(coord_str)
            # 将文本尺寸转换到场景坐标系
            text_width_scene = text_rect.width() / scale_factor
            text_height_scene = text_rect.height() / scale_factor
            
            # 边界检查和位置调整（在场景坐标系下进行）
            # 如果文本会超出右边界，则放在鼠标左侧
            if text_pos.x() + text_width_scene > scene_rect.right():
                text_pos.setX(scene_pos.x() - text_width_scene - scene_offset_x)
            
            # 如果文本会超出上边界，则放在鼠标下方
            if text_pos.y() - text_height_scene < scene_rect.top():
                text_pos.setY(scene_pos.y() + text_height_scene + abs(scene_offset_y))
            
            self.coord_text.setPos(text_pos)
            self.coord_text.setZValue(1001)  # 确保在最上层
            self.scene.addItem(self.coord_text)
            
        except Exception as e:
            logger.error(f"绘制坐标文本时发生错误: {e}")
    
    def is_enabled(self):
        """返回十字准星装饰器是否启用"""
        return self.crosshair_enabled
    
    def set_crosshair_color(self, color):
        """
        设置十字准星颜色
        
        Args:
            color: QColor对象
        """
        self.crosshair_color = color
        self._create_crosshair_cursor()  # 重新创建光标
    
    def set_line_width(self, width):
        """
        设置线条宽度
        
        Args:
            width: 线条宽度
        """
        self.line_width = width
    
    def set_font_size(self, size):
        """
        设置坐标文本字体大小
        
        Args:
            size: 字体大小
        """
        self.font_size = size


class MouseDecoratorManager:
    """鼠标装饰器管理器，负责管理画布的鼠标装饰功能"""
    
    def __init__(self, canvas_view):
        """
        初始化鼠标装饰器管理器
        
        Args:
            canvas_view: GraphicsCanvas实例
        """
        self.canvas_view = canvas_view
        self.crosshair_decorator = CrosshairDecorator(canvas_view)
        
        # 连接鼠标事件
        self._setup_mouse_tracking()
    
    def _setup_mouse_tracking(self):
        """设置鼠标跟踪"""
        try:
            # 确保鼠标跟踪已启用
            self.canvas_view.setMouseTracking(True)
            
            # 保存原始的鼠标事件处理方法
            if not hasattr(self.canvas_view, '_original_mouseMoveEvent_decorator'):
                self.canvas_view._original_mouseMoveEvent_decorator = self.canvas_view.mouseMoveEvent
            
            if not hasattr(self.canvas_view, '_original_enterEvent_decorator'):
                self.canvas_view._original_enterEvent_decorator = self.canvas_view.enterEvent
            
            if not hasattr(self.canvas_view, '_original_leaveEvent_decorator'):
                self.canvas_view._original_leaveEvent_decorator = self.canvas_view.leaveEvent
            
            # 重写鼠标事件处理方法
            self.canvas_view.mouseMoveEvent = self._handle_mouse_move
            self.canvas_view.enterEvent = self._handle_enter_event
            self.canvas_view.leaveEvent = self._handle_leave_event
            
        except Exception as e:
            logger.error(f"设置鼠标跟踪时发生错误: {e}")
    
    def _handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        try:
            # 调用原始的鼠标移动事件处理
            if hasattr(self.canvas_view, '_original_mouseMoveEvent_decorator'):
                self.canvas_view._original_mouseMoveEvent_decorator(event)
            
            # 更新十字准星
            if self.crosshair_decorator.is_enabled():
                scene_pos = self.canvas_view.mapToScene(event.pos())
                self.crosshair_decorator.update_crosshair(scene_pos)
                
        except Exception as e:
            logger.error(f"处理鼠标移动事件时发生错误: {e}")
    
    def _handle_enter_event(self, event):
        """处理鼠标进入画布事件"""
        try:
            # 调用原始的进入事件处理
            if hasattr(self.canvas_view, '_original_enterEvent_decorator'):
                self.canvas_view._original_enterEvent_decorator(event)
            
            # 启用十字准星
            self.crosshair_decorator.enable_crosshair()
            
        except Exception as e:
            logger.error(f"处理鼠标进入事件时发生错误: {e}")
    
    def _handle_leave_event(self, event):
        """处理鼠标离开画布事件"""
        try:
            # 调用原始的离开事件处理
            if hasattr(self.canvas_view, '_original_leaveEvent_decorator'):
                self.canvas_view._original_leaveEvent_decorator(event)
            
            # 禁用十字准星
            self.crosshair_decorator.disable_crosshair()
            
        except Exception as e:
            logger.error(f"处理鼠标离开事件时发生错误: {e}")
    
    def enable_crosshair(self):
        """启用十字准星装饰器"""
        self.crosshair_decorator.enable_crosshair()
    
    def disable_crosshair(self):
        """禁用十字准星装饰器"""
        self.crosshair_decorator.disable_crosshair()
    
    def is_crosshair_enabled(self):
        """返回十字准星装饰器是否启用"""
        return self.crosshair_decorator.is_enabled()
    
    def set_crosshair_color(self, color):
        """设置十字准星颜色"""
        self.crosshair_decorator.set_crosshair_color(color)
    
    def set_line_width(self, width):
        """设置线条宽度"""
        self.crosshair_decorator.set_line_width(width)
    
    def set_font_size(self, size):
        """设置坐标文本字体大小"""
        self.crosshair_decorator.set_font_size(size)
