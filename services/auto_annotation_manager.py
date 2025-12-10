import os
import sys
import logging
import threading
from typing import List, Dict, Tuple, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal, QPoint, QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem
import numpy as np

from sam_ops.MASKSAM import get_mask_sam_manager
from sam_ops.OBBSAM import get_sam_manager
from sam_ops.Aotu_pen import get_auto_pen_manager
from services.global_model_loader import get_global_model_loader
from algorithms.minimum_bounding_rectangle import MinimumBoundingBox

logger = logging.getLogger(__name__)


class AutoAnnotationManager(QObject):
    """自动标注管理器，负责处理AI标注的推理以及自动创建标签的功能"""
    
    # 信号定义
    annotation_started = pyqtSignal(str)  # 标注开始信号
    annotation_progress = pyqtSignal(str, int, int)  # 标注进度信号
    annotation_completed = pyqtSignal(list)  # 标注完成信号
    annotation_error = pyqtSignal(str)  # 标注错误信号
    
    def __init__(self, main_window=None, parent_label_list=None, canvas=None):
        """
        初始化自动标注管理器
        
        Args:
            main_window: 主窗口对象
            parent_label_list: 父标签列表
            canvas: 画布对象
        """
        super().__init__()
        
        self.main_window = main_window
        self.parent_label_list = parent_label_list
        self.canvas = canvas
        self._temp_items = []
        
        # 获取MASK模式SAM推理管理器
        self.mask_sam_manager = get_mask_sam_manager(main_window)
        
        # 获取OBB模式SAM推理管理器
        self.obb_sam_manager = get_sam_manager(main_window)
        
        # 获取自动绘制管理器
        self.auto_pen_manager = get_auto_pen_manager()
        if self.auto_pen_manager:
            self.auto_pen_manager.parent_label_list = parent_label_list
            self.auto_pen_manager.canvas = canvas
        
        # 连接信号
        self._connect_signals()
        
        # 当前模式状态
        self.mask_mode_enabled = False
        self.obb_mode_enabled = False
        
        logger.info("自动标注管理器初始化完成")
    
    def _connect_signals(self):
        """连接信号"""
        if self.mask_sam_manager:
            self.mask_sam_manager.inference_started.connect(self._on_mask_inference_started)
            self.mask_sam_manager.inference_completed.connect(self._on_mask_inference_completed)
            self.mask_sam_manager.inference_error.connect(self._on_mask_inference_error)
        
        if self.obb_sam_manager:
            self.obb_sam_manager.inference_started.connect(self._on_obb_inference_started)
            self.obb_sam_manager.inference_completed.connect(self._on_obb_inference_completed)
            self.obb_sam_manager.inference_error.connect(self._on_obb_inference_error)
        
        if self.auto_pen_manager:
            self.auto_pen_manager.drawing_started.connect(self.annotation_started.emit)
            self.auto_pen_manager.drawing_progress.connect(self.annotation_progress.emit)
            self.auto_pen_manager.drawing_completed.connect(self.annotation_completed.emit)
            self.auto_pen_manager.drawing_error.connect(self.annotation_error.emit)
    
    def set_mask_mode(self, enabled: bool):
        """
        设置MASK模式状态
        
        Args:
            enabled: 是否启用MASK模式
        """
        self.mask_mode_enabled = enabled
        logger.info(f"MASK模式: {'启用' if enabled else '禁用'}")
    
    def set_obb_mode(self, enabled: bool):
        """
        设置OBB模式状态
        
        Args:
            enabled: 是否启用OBB模式
        """
        self.obb_mode_enabled = enabled
        logger.info(f"OBB模式: {'启用' if enabled else '禁用'}")
    
    
    
    def handle_mouse_press(self, event, canvas):
        """
        处理鼠标按下事件
        
        Args:
            event: 鼠标事件
            canvas: 画布对象
            
        Returns:
            bool: 是否处理了事件
        """
        try:
            # 获取鼠标在场景中的坐标
            scene_pos = canvas.mapToScene(event.pos())
            point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
            
            # 检查是否有图片加载
            if not hasattr(canvas, 'image_item') or canvas.image_item is None:
                logger.debug("没有加载图片，忽略鼠标点击")
                return False
            
            # 检查是否选中了父标签
            if not self.parent_label_list or not self.parent_label_list.get_selected():
                logger.debug("没有选中父标签，忽略鼠标点击")
                return False
            
            # 处理MASK模式
            if self.mask_mode_enabled:
                return self._handle_mask_mode_click(event, point)
            
            # 处理OBB模式
            if self.obb_mode_enabled:
                return self._handle_obb_mode_click(event, point)
            
            return False
            
        except Exception as e:
            logger.error(f"处理鼠标点击事件时发生错误: {e}")
            return False
    
    def _handle_mask_mode_click(self, event, point):
        """
        处理MASK模式下的鼠标点击
        
        Args:
            event: 鼠标事件
            point: 点击点坐标
            
        Returns:
            bool: 是否处理了事件
        """
        try:
            if not self.mask_sam_manager:
                logger.warning("MASK模式SAM推理管理器未初始化")
                return False
            
            # 检查模型是否已加载，如果未加载则尝试重新加载
            if not self.mask_sam_manager.model:
                logger.warning("MASK模式SAM模型未加载，尝试重新加载")
                self.mask_sam_manager._get_model_from_global_loader()
                
                # 如果重新加载后仍然没有模型，则返回False
                if not self.mask_sam_manager.model:
                    logger.error("MASK模式SAM模型加载失败，无法处理点击")
                    return False
            
            # 检查当前是否为点输入模式
            # 通过检查主窗口中的点输入按钮状态来确定
            is_point_input_mode = True  # 默认为点输入模式
            if hasattr(self, 'main_window') and self.main_window:
                if hasattr(self.main_window, 'mask_point_input_btn'):
                    is_point_input_mode = self.main_window.mask_point_input_btn.isChecked()
            
            # 如果不是点输入模式（即BBOX模式），则不处理点击事件
            if not is_point_input_mode:
                logger.debug("MASK模式当前为BBOX输入模式，忽略点击事件")
                return False
            
            # 判断是左键还是右键
            is_positive = (event.button() == event.button().LeftButton)
            
            # 添加点击点
            self.mask_sam_manager.add_point(point, is_positive)
            try:
                if self.canvas and hasattr(self.canvas, 'scene') and self.canvas.scene:
                    r = 4
                    item = QGraphicsEllipseItem(point.x()-r, point.y()-r, r*2, r*2)
                    item.setPen(QPen(Qt.PenStyle.NoPen))
                    item.setBrush(QBrush(QColor(76,175,80) if is_positive else QColor(244,67,54)))
                    self.canvas.scene.addItem(item)
                    self._temp_items.append(item)
                    QTimer.singleShot(1000, lambda: self._remove_temp_item(item))
            except Exception:
                pass
            
            # 记录详细的点击信息
            logger.info(f"MASK模式处理点击: 坐标=({point.x()}, {point.y()}), 类型={'正点' if is_positive else '负点'}, 当前总点数={len(self.mask_sam_manager.current_points)}")
            
            return True
            
        except Exception as e:
            logger.error(f"处理MASK模式点击时发生错误: {e}")
            return False
    
    def _handle_obb_mode_click(self, event, point):
        """
        处理OBB模式下的鼠标点击
        
        Args:
            event: 鼠标事件
            point: 点击点坐标
            
        Returns:
            bool: 是否处理了事件
        """
        try:
            logger.info(f"处理OBB模式点击事件: 坐标=({point.x()}, {point.y()})")
            
            if not self.obb_sam_manager:
                logger.warning("OBB模式SAM推理管理器未初始化，尝试重新初始化")
                try:
                    # 尝试重新初始化OBB SAM管理器
                    from OBBSAM import SAMInferenceManager
                    self.obb_sam_manager = SAMInferenceManager()
                    logger.info("成功重新初始化OBB SAM管理器")
                except Exception as e:
                    logger.error(f"重新初始化OBB SAM管理器失败: {str(e)}")
                    return False
            
            # 检查模型是否已加载，如果未加载则尝试重新加载
            if not self.obb_sam_manager.model:
                logger.warning("OBB模式SAM模型未加载，尝试重新加载")
                self.obb_sam_manager._get_model_from_global_loader()
                
                # 如果重新加载后仍然没有模型，则返回False
                if not self.obb_sam_manager.model:
                    logger.error("OBB模式SAM模型加载失败，无法处理点击")
                    return False
            
            # 判断是左键还是右键
            is_positive = (event.button() == event.button().LeftButton)
            
            # 添加点击点
            logger.info(f"添加点击点: ({point.x()}, {point.y()}), 类型={'正点' if is_positive else '负点'}")
            self.obb_sam_manager.add_point(point, is_positive)
            try:
                if self.canvas and hasattr(self.canvas, 'scene') and self.canvas.scene:
                    r = 4
                    item = QGraphicsEllipseItem(point.x()-r, point.y()-r, r*2, r*2)
                    item.setPen(QPen(Qt.PenStyle.NoPen))
                    item.setBrush(QBrush(QColor(76,175,80) if is_positive else QColor(244,67,54)))
                    self.canvas.scene.addItem(item)
                    self._temp_items.append(item)
                    QTimer.singleShot(1000, lambda: self._remove_temp_item(item))
            except Exception:
                pass
            
            # 记录详细的点击信息
            logger.info(f"OBB模式点击事件处理完成，添加坐标=({point.x()}, {point.y()}), 类型={'正点' if is_positive else '负点'}, 当前总点数={len(self.obb_sam_manager.current_points)}")
            
            return True
            
        except Exception as e:
            logger.error(f"处理OBB模式点击时发生错误: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return False

    def _remove_temp_item(self, item):
        try:
            if item and self.canvas and hasattr(self.canvas, 'scene') and self.canvas.scene:
                self.canvas.scene.removeItem(item)
                try:
                    if item in self._temp_items:
                        self._temp_items.remove(item)
                except Exception:
                    pass
        except Exception:
            pass

    def _clear_temp_items(self):
        try:
            for it in list(self._temp_items):
                try:
                    self._remove_temp_item(it)
                except Exception:
                    pass
            self._temp_items.clear()
        except Exception:
            pass
    
    
    
    def _on_mask_inference_started(self):
        """MASK模式推理开始时的处理"""
        logger.info("MASK模式推理开始")
        self.annotation_started.emit("MASK模式推理开始")
    
    def _on_obb_inference_started(self):
        """OBB模式推理开始时的处理"""
        logger.info("OBB模式推理开始")
        self.annotation_started.emit("OBB模式推理开始")
    
    def _on_mask_inference_completed(self, results):
        """
        MASK模式推理完成时的处理
        
        Args:
            results: 推理结果
        """
        try:
            logger.info("MASK模式推理完成")
            
            # 获取当前图片信息
            current_image_path = None
            if self.main_window and hasattr(self.main_window, 'images') and self.main_window.images:
                current_index = self.main_window.resource_list.currentRow()
                if 0 <= current_index < len(self.main_window.images):
                    current_image_path = self.main_window.images[current_index]
            
            if not current_image_path:
                logger.warning("无法获取当前图片路径")
                self.annotation_error.emit("无法获取当前图片路径")
                return
            
            # 获取图片尺寸
            image_width, image_height = 0, 0
            if self.canvas and hasattr(self.canvas, 'image_item') and self.canvas.image_item:
                pixmap = self.canvas.image_item.pixmap()
                if pixmap:
                    image_width = pixmap.width()
                    image_height = pixmap.height()
            
            if image_width == 0 or image_height == 0:
                logger.warning("无法获取图片尺寸")
                self.annotation_error.emit("无法获取图片尺寸")
                return
            
            # 根据当前模式选择处理方式
            if self.mask_mode_enabled:
                # MASK模式：直接使用多边形
                if self.auto_pen_manager:
                    created_labels = self.auto_pen_manager.process_mask_sam_results(
                        results, current_image_path, image_width, image_height
                    )
                    
                    if created_labels:
                        logger.info(f"成功创建了 {len(created_labels)} 个标签")
                        self._clear_temp_items()
                        self.annotation_completed.emit(created_labels)
                    else:
                        logger.info("未创建任何标签")
                        self.annotation_completed.emit([])
                else:
                    logger.warning("自动绘制管理器未初始化")
                    self.annotation_error.emit("自动绘制管理器未初始化")
                
        except Exception as e:
            logger.error(f"处理推理结果时发生错误: {e}")
            self.annotation_error.emit(f"处理推理结果时发生错误: {e}")
    
    def _on_obb_inference_completed(self, results):
        """
        OBB模式推理完成时的处理
        
        Args:
            results: 推理结果
        """
        try:
            logger.info("OBB模式推理完成，开始处理结果")
            
            # 检查结果是否有效
            if not results:
                logger.warning("OBB模式推理结果为空")
                return
            
            logger.info(f"OBB模式推理结果数量: {len(results)}")
            
            # 获取当前图片信息
            current_image_path = None
            if self.main_window and hasattr(self.main_window, 'images') and self.main_window.images:
                current_index = self.main_window.resource_list.currentRow()
                logger.info(f"当前图片索引: {current_index}")
                if 0 <= current_index < len(self.main_window.images):
                    current_image_path = self.main_window.images[current_index]
                    logger.info(f"获取到当前图片路径: {current_image_path}")
            
            if not current_image_path:
                logger.warning("无法获取当前图片路径")
                self.annotation_error.emit("无法获取当前图片路径")
                return
            
            # 获取图片尺寸
            image_width, image_height = 0, 0
            if self.canvas and hasattr(self.canvas, 'image_item') and self.canvas.image_item:
                pixmap = self.canvas.image_item.pixmap()
                if pixmap:
                    image_width = pixmap.width()
                    image_height = pixmap.height()
                    logger.info(f"获取到图片尺寸: {image_width}x{image_height}")
            
            if image_width == 0 or image_height == 0:
                logger.warning("无法获取图片尺寸")
                self.annotation_error.emit("无法获取图片尺寸")
                return
            
            # 根据当前模式选择处理方式
            if self.obb_mode_enabled:
                logger.info("OBB模式已启用，开始处理推理结果")
                # OBB模式：使用最小外接矩形
                if self.auto_pen_manager:
                    logger.info("调用auto_pen_manager处理OBB推理结果")
                    created_labels = self.auto_pen_manager.process_obb_sam_results(
                        results, current_image_path, image_width, image_height
                    )
                    
                    if created_labels:
                        logger.info(f"成功创建了 {len(created_labels)} 个OBB标签")
                        self._clear_temp_items()
                        self.annotation_completed.emit(created_labels)
                    else:
                        logger.info("未创建任何OBB标签")
                        self.annotation_completed.emit([])
                else:
                    logger.warning("自动绘制管理器未初始化")
                    self.annotation_error.emit("自动绘制管理器未初始化")
            else:
                logger.warning("OBB模式未启用，跳过处理")
            
        except Exception as e:
            logger.error(f"处理OBB推理结果时发生错误: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            self.annotation_error.emit(f"处理OBB推理结果时发生错误: {e}")
    
    
    

    
    def _on_mask_inference_error(self, error_msg):
        """
        MASK模式推理错误时的处理
        
        Args:
            error_msg: 错误消息
        """
        logger.error(f"MASK模式推理错误: {error_msg}")
        self.annotation_error.emit(error_msg)
    
    def _on_obb_inference_error(self, error_msg):
        """
        OBB模式推理错误时的处理
        
        Args:
            error_msg: 错误消息
        """
        logger.error(f"OBB模式推理错误: {error_msg}")
        self.annotation_error.emit(error_msg)


# 全局实例获取函数
_auto_annotation_manager = None

def get_auto_annotation_manager(main_window=None, parent_label_list=None, canvas=None):
    """
    获取全局AutoAnnotationManager实例
    
    Args:
        main_window: 主窗口对象
        parent_label_list: 父标签列表
        canvas: 画布对象
        
    Returns:
        AutoAnnotationManager实例
    """
    global _auto_annotation_manager
    if _auto_annotation_manager is None:
        _auto_annotation_manager = AutoAnnotationManager(main_window, parent_label_list, canvas)
    else:
        # 如果实例已存在，更新引用
        _auto_annotation_manager.main_window = main_window
        _auto_annotation_manager.parent_label_list = parent_label_list
        _auto_annotation_manager.canvas = canvas
        
        # 更新子管理器的引用
        if _auto_annotation_manager.auto_pen_manager:
            _auto_annotation_manager.auto_pen_manager.parent_label_list = parent_label_list
            _auto_annotation_manager.auto_pen_manager.canvas = canvas
    
    return _auto_annotation_manager


def main():
    """测试函数"""
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    auto_annotation_manager = AutoAnnotationManager()

    auto_annotation_manager.annotation_started.connect(lambda msg: print(f"标注开始: {msg}"))
    auto_annotation_manager.annotation_progress.connect(lambda msg, curr, total: print(f"标注进度: {msg} ({curr}/{total})"))
    auto_annotation_manager.annotation_completed.connect(lambda labels: print(f"标注完成，创建了 {len(labels)} 个标签"))
    auto_annotation_manager.annotation_error.connect(lambda err: print(f"标注错误: {err}"))

    print("自动标注管理器初始化完成")


if __name__ == "__main__":
    main()
