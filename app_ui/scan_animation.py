"""
扫描动画效果模块
在SAM推理开始时，在画布上显示扫描动画效果，
直到推理完成并绘制分割结果到画布上时停止动画。
"""

import sys
import math
import time
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QGraphicsLineItem
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QObject, QEvent
from PyQt6.QtGui import QPen, QColor, QPainter, QBrush, QLinearGradient, QRadialGradient, QPainterPath

import logging

logger = logging.getLogger(__name__)

class ScanAnimationOverlay(QWidget):
    """扫描动画覆盖层，用于在画布上显示扫描动画效果"""
    
    def __init__(self, parent_view: QGraphicsView):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.setFixedSize(parent_view.size())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # 扫描动画参数
        self.scan_position = 0.0  # 扫描位置 (0.0 到 1.0)
        self.scan_speed = 0.01     # 扫描速度
        self.scan_width = 0.02     # 扫描线宽度 (相对于画布高度的比例)
        self.scan_direction = 1    # 扫描方向 (1 或 -1)
        self.pulse_phase = 0.0     # 脉冲相位
        self.pulse_speed = 0.03    # 脉冲速度
        
        # 颜色参数 - 科技蓝色调
        self.scan_colors = [
            QColor(0, 149, 255, 180),     # 科技蓝
            QColor(0, 123, 255, 180),     # 深科技蓝
            QColor(64, 169, 255, 180),    # 浅科技蓝
            QColor(0, 200, 255, 180),     # 青蓝
        ]
        self.current_color_index = 0
        
        # 动画控制
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_interval = 30  # 毫秒
        self.is_animating = False
        
        # 跟随父视图大小变化
        parent_view.resizeEvent = self._wrap_resize_event(parent_view.resizeEvent)
        # 安装事件过滤器以捕获窗口状态变化
        parent_view.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        """事件过滤器，用于捕获窗口状态变化事件"""
        if obj == self.parent_view:
            if event.type() == QEvent.Type.WindowStateChange:
                # 窗口状态改变时（如切换到全屏），强制更新覆盖层大小和重绘
                self.update_overlay_size()
                if self.is_animating:
                    self.update()
            elif event.type() == QEvent.Type.Resize:
                # 窗口大小变化时也强制更新
                self.update_overlay_size()
                if self.is_animating:
                    self.update()
        return super().eventFilter(obj, event)
    
    def update_overlay_size(self):
        """更新覆盖层大小以匹配父视图"""
        if self.parent_view:
            # 获取父视图的实际大小
            view_size = self.parent_view.size()
            # 更新覆盖层大小
            self.setFixedSize(view_size)
            # 移动覆盖层到父视图的左上角
            self.move(0, 0)
            # 强制重绘，确保线条端点与画布边缘相接
            if self.is_animating:
                self.update()
    
    def _wrap_resize_event(self, original_resize_event):
        """包装父视图的resize事件，使覆盖层大小与父视图保持一致"""
        def wrapped_resize_event(event):
            original_resize_event(event)
            self.update_overlay_size()
            # 强制重绘，确保线条长度自适应
            if self.is_animating:
                self.update()
        return wrapped_resize_event
    
    def resizeEvent(self, event):
        """处理覆盖层的resize事件"""
        super().resizeEvent(event)
        # 强制重绘，确保线条长度自适应
        if self.is_animating:
            self.update()
    
    def start_animation(self):
        """开始扫描动画"""
        logger.info(f"尝试开始扫描动画，当前状态: is_animating={self.is_animating}")
        if not self.is_animating:
            self.is_animating = True
            self.scan_position = 0.0
            self.scan_direction = 1
            self.current_color_index = 0
            self.pulse_phase = 0.0
            # 确保覆盖层大小正确
            self.update_overlay_size()
            self.animation_timer.start(self.animation_interval)
            self.show()
            logger.info("扫描动画已启动")
    
    def stop_animation(self):
        """停止扫描动画"""
        logger.info(f"尝试停止扫描动画，当前状态: is_animating={self.is_animating}")
        if self.is_animating:
            self.is_animating = False
            self.animation_timer.stop()
            self.hide()
            logger.info("扫描动画已停止")
        else:
            # 即使标志位为False，也强制清理一下，防止状态不一致
            self.animation_timer.stop()
            self.hide()
            logger.info("扫描动画原本未运行，但已强制执行停止操作")
    
    def update_animation(self):
        """更新动画状态"""
        if not self.is_animating:
            return
            
        # 更新扫描位置
        self.scan_position += self.scan_speed * self.scan_direction
        
        # 更新脉冲相位
        self.pulse_phase += self.pulse_speed
        if self.pulse_phase > 1.0:
            self.pulse_phase = 0.0
        
        # 如果扫描位置超出范围，改变方向并切换颜色
        if self.scan_position >= 1.0:
            self.scan_position = 1.0
            self.scan_direction = -1
            self.current_color_index = (self.current_color_index + 1) % len(self.scan_colors)
        elif self.scan_position <= 0.0:
            self.scan_position = 0.0
            self.scan_direction = 1
            self.current_color_index = (self.current_color_index + 1) % len(self.scan_colors)
        
        # 重绘
        self.update()
    
    def paintEvent(self, event):
        """绘制扫描动画"""
        if not self.is_animating:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 获取视图的矩形区域
        view_rect = self.rect()
        
        # 计算扫描线的y坐标
        scan_y = view_rect.top() + self.scan_position * view_rect.height()
        
        # 获取当前颜色
        current_color = self.scan_colors[self.current_color_index]
        
        # 计算脉冲强度 (0.3 到 1.0)
        pulse_intensity = 0.3 + 0.7 * math.sin(self.pulse_phase * 2 * math.pi)
        
        # 绘制扫描线
        # 自适应线条宽度，根据画布高度调整
        scan_line_width = max(1, min(3, view_rect.height() / 300))
        
        # 计算线条的起点和终点 - 强制确保端点始终在画布边缘
        line_start_x = 0  # 从画布最左边缘开始
        line_end_x = view_rect.width()  # 到画布最右边缘结束
        
        # 创建扫描线渐变 - 科技风格
        gradient = QLinearGradient(line_start_x, scan_y, line_end_x, scan_y)
        gradient.setColorAt(0.0, QColor(current_color.red(), current_color.green(), 
                                        current_color.blue(), int(200 * pulse_intensity)))
        gradient.setColorAt(0.5, QColor(255, 255, 255, int(220 * pulse_intensity)))
        gradient.setColorAt(1.0, QColor(current_color.red(), current_color.green(), 
                                        current_color.blue(), int(200 * pulse_intensity)))
        
        # 绘制主扫描线
        scan_pen = QPen(QBrush(gradient), scan_line_width)
        painter.setPen(scan_pen)
        painter.drawLine(int(line_start_x), int(scan_y), int(line_end_x), int(scan_y))
        
        # 绘制扫描区域高亮
        # 在扫描线上方和下方绘制半透明区域
        highlight_height = int(view_rect.height() * 0.15)  # 高亮区域高度
        
        # 上方高亮区域
        top_gradient = QLinearGradient(0, scan_y - highlight_height, 0, scan_y)
        top_gradient.setColorAt(0.0, QColor(0, 149, 255, 0))
        top_gradient.setColorAt(1.0, QColor(0, 149, 255, int(40 * pulse_intensity)))
        painter.fillRect(0, int(scan_y - highlight_height), 
                        int(view_rect.width()), int(highlight_height), QBrush(top_gradient))
        
        # 下方高亮区域
        bottom_gradient = QLinearGradient(0, scan_y, 0, scan_y + highlight_height)
        bottom_gradient.setColorAt(0.0, QColor(0, 149, 255, int(40 * pulse_intensity)))
        bottom_gradient.setColorAt(1.0, QColor(0, 149, 255, 0))
        painter.fillRect(0, int(scan_y), 
                        int(view_rect.width()), int(highlight_height), QBrush(bottom_gradient))
        
        # 绘制端点光点 - 确保光点始终在画布边缘
        # 自适应光点大小
        point_radius = max(3, min(10, view_rect.width() / 100))  # 光点大小根据画布宽度调整
        
        # 左端光点 - 强制始终在画布最左边缘
        left_point_x = 0  # 画布最左边缘
        left_point_gradient = QRadialGradient(left_point_x, scan_y, point_radius * 3)
        left_point_gradient.setColorAt(0, QColor(255, 255, 255, int(255 * pulse_intensity)))
        left_point_gradient.setColorAt(0.5, QColor(0, 200, 255, int(200 * pulse_intensity)))
        left_point_gradient.setColorAt(1, QColor(0, 149, 255, 0))
        painter.setBrush(QBrush(left_point_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(left_point_x, scan_y), point_radius, point_radius)
        
        # 右端光点 - 强制始终在画布最右边缘
        right_point_x = view_rect.width()  # 画布最右边缘
        right_point_gradient = QRadialGradient(right_point_x, scan_y, point_radius * 3)
        right_point_gradient.setColorAt(0, QColor(255, 255, 255, int(255 * pulse_intensity)))
        right_point_gradient.setColorAt(0.5, QColor(0, 200, 255, int(200 * pulse_intensity)))
        right_point_gradient.setColorAt(1, QColor(0, 149, 255, 0))
        painter.setBrush(QBrush(right_point_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(right_point_x, scan_y), point_radius, point_radius)
        
        # 绘制额外的光晕效果，增强科技感
        halo_radius = point_radius * 2
        halo_alpha = int(100 * pulse_intensity)
        
        # 左端光晕
        left_halo_gradient = QRadialGradient(left_point_x, scan_y, halo_radius * 2)
        left_halo_gradient.setColorAt(0, QColor(0, 200, 255, halo_alpha))
        left_halo_gradient.setColorAt(1, QColor(0, 149, 255, 0))
        painter.setBrush(QBrush(left_halo_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(left_point_x, scan_y), halo_radius, halo_radius)
        
        # 右端光晕
        right_halo_gradient = QRadialGradient(right_point_x, scan_y, halo_radius * 2)
        right_halo_gradient.setColorAt(0, QColor(0, 200, 255, halo_alpha))
        right_halo_gradient.setColorAt(1, QColor(0, 149, 255, 0))
        painter.setBrush(QBrush(right_halo_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(right_point_x, scan_y), halo_radius, halo_radius)


class ScanAnimationManager(QObject):
    """扫描动画管理器，负责管理扫描动画的启动和停止"""
    
    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self.scan_overlay = None
        self.is_sam_inferring = False
        
    def initialize(self):
        """初始化扫描动画覆盖层"""
        if self.scan_overlay is None:
            self.scan_overlay = ScanAnimationOverlay(self.canvas)
            self.scan_overlay.hide()
    
    def start_scan_animation(self):
        """开始扫描动画"""
        self.initialize()
        if self.scan_overlay:
            self.scan_overlay.start_animation()
            self.is_sam_inferring = True
    
    def stop_scan_animation(self, results=None):
        """停止扫描动画
        
        Args:
            results: SAM推理结果（可选）
        """
        logger.info(f"ScanAnimationManager.stop_scan_animation called with results: {results is not None}")
        if self.scan_overlay:
            self.scan_overlay.stop_animation()
            self.is_sam_inferring = False
        else:
            logger.warning("ScanAnimationManager.stop_scan_animation: scan_overlay is None")
    
    def is_animation_running(self):
        """检查动画是否正在运行"""
        return self.is_sam_inferring


# 全局扫描动画管理器实例
scan_animation_manager = None

def get_scan_animation_manager(canvas=None):
    """获取全局扫描动画管理器实例"""
    global scan_animation_manager
    if scan_animation_manager is None and canvas is not None:
        scan_animation_manager = ScanAnimationManager(canvas)
    return scan_animation_manager


def setup_scan_animation_signals(label_draw_manager, canvas):
    """设置扫描动画的信号连接
    
    Args:
        label_draw_manager: LabelDrawManager实例
        canvas: GraphicsCanvas实例
    """
    manager = get_scan_animation_manager(canvas)
    
    # 连接SAM推理开始信号
    if hasattr(label_draw_manager, 'sam_inference_started'):
        label_draw_manager.sam_inference_started.connect(
            lambda: manager.start_scan_animation()
        )
    
    # 连接SAM推理完成信号 - 多边形模式
    if hasattr(label_draw_manager, 'sam_inference_complete'):
        label_draw_manager.sam_inference_complete.connect(
            manager.stop_scan_animation
        )
