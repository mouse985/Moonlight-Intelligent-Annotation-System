from PyQt6.QtCore import Qt, QPoint, QPointF, QObject, QTimer
from PyQt6.QtGui import QPen, QColor, QBrush, QPolygonF
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsPolygonItem
import logging
from typing import Optional, Callable, List, Dict, Any
from algorithms.polygon_bounding_rectangle import calculate_bounding_rectangle
from inference.inference_moon import run_inference_with_specific_child
from app_ui.scan_animation import get_scan_animation_manager
from sam_ops.IN_Sam_rect import get_sam_manager as get_rect_sam_manager
import math



logger = logging.getLogger(__name__)





class LabelDrawManager(QObject):
    """矩形框绘制管理器，处理手动绘制矩形框的所有逻辑"""
    
    def __init__(self, canvas_view, parent_label_list=None, get_image_info_func=None):
        """
        初始化矩形框绘制管理器
        
        Args:
            canvas_view: 画布视图对象
            parent_label_list: 父标签列表对象
            get_image_info_func: 获取当前图片信息的函数
        """
        super().__init__()
        self.canvas_view = canvas_view
        self.parent_label_list = parent_label_list
        self.get_image_info_func = get_image_info_func
        
        # 绘制状态
        self.drawing = False
        self.rect_start: Optional[QPoint] = None
        self.end_point: Optional[QPoint] = None
        self.temp_rect_item: Optional[QGraphicsRectItem] = None
        # 临时图元（点、线）与状态
        self.temp_point_item: Optional[QGraphicsEllipseItem] = None
        self.drawing_line: bool = False
        self.line_start: Optional[QPoint] = None
        self.temp_line_item: Optional[QGraphicsLineItem] = None
        # 正规多边形拖拽状态
        self.drawing_regular_polygon: bool = False
        self.regular_polygon_start: Optional[QPoint] = None
        self.temp_regular_polygon_item: Optional[QGraphicsPolygonItem] = None
        
        # 圆形绘制状态
        self.drawing_circle: bool = False
        self.circle_center: Optional[QPoint] = None
        self.temp_circle_item: Optional[QGraphicsEllipseItem] = None
        
    def rect_huabi(self, event_type, event):
        """
        矩形框绘制方法，处理鼠标按下、移动和释放事件
        
        Args:
            event_type: 事件类型 ('press', 'move', 'release')
            event: 鼠标事件对象
            
        Returns:
            bool: 事件是否被处理
        """
        try:
            if event_type == 'press':
                return self._handle_mouse_press(event)
            elif event_type == 'move':
                return self._handle_mouse_move(event)
            elif event_type == 'release':
                return self._handle_mouse_release(event)
            return False
        except Exception as e:
            logger.error(f"处理矩形框绘制事件时发生错误: {e}")
            return False
    
    def _handle_mouse_press(self, event) -> bool:
        """处理鼠标按下事件"""
        if hasattr(self.canvas_view, 'ui_locked') and self.canvas_view.ui_locked:
            return False
            
        if (event.button() == Qt.MouseButton.LeftButton and 
            hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item and 
            self.parent_label_list and 
            self.parent_label_list.get_selected()):

            self.drawing = True

            scene_pos = self.canvas_view.mapToScene(event.pos())
            self.rect_start = QPoint(int(scene_pos.x()), int(scene_pos.y()))

            if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                x = min(max(self.rect_start.x(), 0), self.canvas_view.current_pixmap.width())
                y = min(max(self.rect_start.y(), 0), self.canvas_view.current_pixmap.height())
                self.rect_start = QPoint(int(x), int(y))

            if self.temp_rect_item:
                self.canvas_view.scene.removeItem(self.temp_rect_item)

            self.temp_rect_item = QGraphicsRectItem()

            parent = self.parent_label_list.get_selected()
            if parent and hasattr(parent, 'color') and parent.color:
                pen = QPen(parent.color, 2, Qt.PenStyle.DashLine)
            else:
                pen = QPen(QColor(0, 255, 0), 2, Qt.PenStyle.DashLine)

            self.temp_rect_item.setPen(pen)
            self.canvas_view.scene.addItem(self.temp_rect_item)
            
            return True
            
        return False
    
    def _handle_mouse_move(self, event) -> bool:
        """处理鼠标移动事件"""
        if hasattr(self.canvas_view, 'ui_locked') and self.canvas_view.ui_locked:
            return False
            
        if (self.drawing and 
            hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item and 
            self.temp_rect_item):
            
            scene_pos = self.canvas_view.mapToScene(event.pos())

            if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                x = min(max(scene_pos.x(), 0), self.canvas_view.current_pixmap.width())
                y = min(max(scene_pos.y(), 0), self.canvas_view.current_pixmap.height())
                scene_pos = QPoint(int(x), int(y))

            x1, y1 = int(self.rect_start.x()), int(self.rect_start.y())
            x2, y2 = int(scene_pos.x()), int(scene_pos.y())
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)

            self.temp_rect_item.setRect(x, y, w, h)
            
            return True
            
        return False
    
    def _handle_mouse_release(self, event) -> bool:
        """处理鼠标释放事件"""
        if hasattr(self.canvas_view, 'ui_locked') and self.canvas_view.ui_locked:
            return False
            
        if (self.drawing and 
            hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item):
            
            self.drawing = False
            scene_pos = self.canvas_view.mapToScene(event.pos())

            if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                x = min(max(scene_pos.x(), 0), self.canvas_view.current_pixmap.width())
                y = min(max(scene_pos.y(), 0), self.canvas_view.current_pixmap.height())
                scene_pos = QPoint(int(x), int(y))

            x1, y1 = int(self.rect_start.x()), int(self.rect_start.y())
            x2, y2 = int(scene_pos.x()), int(scene_pos.y())

            self.end_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))

            # 检查矩形大小
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 5 and h > 5:
                # 使用新的顶点坐标格式创建标签
                self._create_label_from_rect(x1, y1, x2, y2)
            
            # 移除临时矩形框
            if self.temp_rect_item:
                self.canvas_view.scene.removeItem(self.temp_rect_item)
                self.temp_rect_item = None
            
            return True
            
        return False
    
    
    
    
    
    
    
    def point_huabi(self, event_type, event) -> bool:
        """点标签绘制：在按下左键处创建一个点标签"""
        try:
            if getattr(self, 'ui_locked', False):
                return False
            if event_type == 'press':
                if event.button() == Qt.MouseButton.LeftButton and hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item:
                    # 必须选择父标签
                    if not self.parent_label_list or not self.parent_label_list.get_selected():
                        logger.info("点画笔：未选中父标签，忽略点击")
                        return False
                    # 转换坐标并限制到图像范围
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    x = int(scene_pos.x())
                    y = int(scene_pos.y())
                    logger.info(f"点画笔：scene_pos=({scene_pos.x():.2f},{scene_pos.y():.2f}) 初始像素=({x},{y})")
                    pixmap = getattr(self.canvas_view, 'current_pixmap', None)
                    if pixmap:
                        x = max(0, min(x, pixmap.width() - 1))
                        y = max(0, min(y, pixmap.height() - 1))
                        logger.info(f"点画笔：裁剪后像素=({x},{y}) 图像尺寸=({pixmap.width()}x{pixmap.height()})")
                    else:
                        logger.info("点画笔：未找到当前图像 pixmap，坐标不裁剪")
                    logger.info(f"点画笔：提交创建点子标签({x},{y})")
                    self._create_label_point(x, y)
                    return True
            return False
        except Exception as e:
            logger.error(f"点标签绘制时发生错误: {e}")
            return False

    def _create_label_point(self, x: float, y: float) -> None:
        """创建点标签"""
        try:
            logger.info(f"创建点子标签：坐标=({x},{y})")
            if not hasattr(self.canvas_view, 'current_pixmap') or not self.canvas_view.current_pixmap:
                logger.warning("创建点子标签失败：当前画布无图像")
                return
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
            parent = self.parent_label_list.get_selected() if self.parent_label_list else None
            if not parent:
                logger.warning("创建点子标签失败：未选中父标签")
                return
            child = self.parent_label_list.create_child_label(
                points=[x, y], image_info=image_info, mode='manual', shape_type='point')
            if child:
                logger.info(f"点子标签创建成功：父标签={getattr(parent,'name',None)}(ID={getattr(parent,'id',None)}), 坐标=({x},{y}), 形状=point")
                if hasattr(self.canvas_view, 'update_rects'):
                    self.canvas_view.update_rects()
                # 刷新子标签列表显示
                if hasattr(self.canvas_view, 'main_window') and hasattr(self.canvas_view.main_window, 'refresh_child_labels_for_current_image'):
                    self.canvas_view.main_window.refresh_child_labels_for_current_image()
            else:
                logger.warning("点子标签创建失败：返回对象为空")
        except Exception as e:
            logger.error(f"创建点标签时发生错误: {e}")

    def line_huabi(self, event_type, event) -> bool:
        """线标签绘制：按下确定起点，拖动预览，释放确定终点"""
        try:
            if getattr(self, 'ui_locked', False):
                return False
            if event_type == 'press':
                if event.button() == Qt.MouseButton.LeftButton and hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item:
                    if not self.parent_label_list or not self.parent_label_list.get_selected():
                        return False
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    self.line_start = QPoint(int(scene_pos.x()), int(scene_pos.y()))
                    pixmap = getattr(self.canvas_view, 'current_pixmap', None)
                    if pixmap and self.line_start:
                        self.line_start.setX(max(0, min(self.line_start.x(), pixmap.width() - 1)))
                        self.line_start.setY(max(0, min(self.line_start.y(), pixmap.height() - 1)))
                    # 移除旧的临时线
                    if self.temp_line_item and self.temp_line_item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(self.temp_line_item)
                        self.temp_line_item = None
                    # 创建新的临时线
                    if self.line_start:
                        self.temp_line_item = QGraphicsLineItem(self.line_start.x(), self.line_start.y(), self.line_start.x(), self.line_start.y())
                        pen = QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine)
                        self.temp_line_item.setPen(pen)
                        self.temp_line_item.setZValue(9)
                        self.canvas_view.scene.addItem(self.temp_line_item)
                        self.drawing_line = True
                        return True
            elif event_type == 'move':
                if self.drawing_line and self.temp_line_item and hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    x2 = int(scene_pos.x())
                    y2 = int(scene_pos.y())
                    pixmap = self.canvas_view.current_pixmap
                    x2 = max(0, min(x2, pixmap.width() - 1))
                    y2 = max(0, min(y2, pixmap.height() - 1))
                    self.temp_line_item.setLine(self.line_start.x(), self.line_start.y(), x2, y2)
                    return True
            elif event_type == 'release':
                if self.drawing_line and self.temp_line_item and hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                    # 最终终点
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    x2 = int(scene_pos.x())
                    y2 = int(scene_pos.y())
                    pixmap = self.canvas_view.current_pixmap
                    x2 = max(0, min(x2, pixmap.width() - 1))
                    y2 = max(0, min(y2, pixmap.height() - 1))
                    x1, y1 = self.line_start.x(), self.line_start.y()
                    # 有效长度阈值
                    if (abs(x2 - x1) + abs(y2 - y1)) >= 3:
                        self._create_label_from_line(x1, y1, x2, y2)
                    # 清理临时线
                    if self.temp_line_item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(self.temp_line_item)
                    self.temp_line_item = None
                    self.drawing_line = False
                    self.line_start = None
                    return True
            return False
        except Exception as e:
            logger.error(f"线标签绘制时发生错误: {e}")
            return False

    def _create_label_from_line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """创建线标签（两个端点）"""
        try:
            if not hasattr(self, 'canvas_view') or not hasattr(self.canvas_view, 'current_pixmap') or not self.canvas_view.current_pixmap:
                return
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
            child = self.parent_label_list.create_child_label(
                points=[x1, y1, x2, y2], image_info=image_info, mode='manual', shape_type='line')
            if child and hasattr(self.canvas_view, 'update_rects'):
                self.canvas_view.update_rects()
        except Exception as e:
            logger.error(f"创建线标签时发生错误: {e}")

    def _create_label_from_rect(self, x1: float, y1: float, x2: float, y2: float, rotation_angle=0) -> None:
        """根据矩形框的左上角和右下角坐标创建子标签（使用顶点坐标表示）"""
        try:
            if not hasattr(self.canvas_view, 'current_pixmap') or not self.canvas_view.current_pixmap:
                return

            # 获取当前图片信息
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return

            # 计算矩形的四个顶点坐标
            # 左上角 (x1, y1), 右上角 (x2, y1), 右下角 (x2, y2), 左下角 (x1, y2)
            points = [x1, y1, x2, y1, x2, y2, x1, y2]
            
            # 使用顶点坐标创建子标签
            child = self.parent_label_list.create_child_label(
                points=points,
                image_info=image_info,
                mode='manual',
                shape_type='rectangle',
                rotation_angle=rotation_angle
            )
            
            # 更新矩形框
            if hasattr(self.canvas_view, 'update_rects'):
                self.canvas_view.update_rects()
            
            # 检查自动标注开关状态并发送推理信号
            if child and hasattr(self.canvas_view, 'main_window') and self.canvas_view.main_window:
                auto_annotation_enabled = getattr(self.canvas_view.main_window, 'auto_annotation_enabled', False)
                if auto_annotation_enabled:
                    logger.info("自动标注开关已开启，发送推理信号")
                    try:
                        # 定义推理结果处理回调函数
                        def handle_inference_result(result):
                            """处理推理结果的回调函数"""
                            logger.info(f"推理结果: {result}")
                            # 停止扫描动画（如果在运行）
                            try:
                                scan_mgr = get_scan_animation_manager(self.canvas_view)
                                if scan_mgr:
                                    def stop_anim():
                                        try:
                                            scan_mgr.stop_scan_animation(result)
                                        except Exception as e:
                                            logger.error(f"QTimer停止扫描动画失败: {e}")
                                    QTimer.singleShot(0, stop_anim)
                            except Exception as e:
                                logger.error(f"获取扫描动画管理器失败: {e}")
                            # 在主线程中更新UI
                            if hasattr(self.canvas_view, 'main_window') and self.canvas_view.main_window:
                                # 使用QTimer在主线程中执行UI更新
                                QTimer.singleShot(0, lambda: self._update_ui_with_inference_result(result, child))
                        
                        # 调用推理方法，传入回调函数
                        inference_result = run_inference_with_specific_child(
                            get_image_info_func=self.get_image_info_func,
                            parent_label_list=self.parent_label_list,
                            child_label=child,
                            shape_type='rectangle',
                            callback=handle_inference_result,
                            main_window=self.canvas_view.main_window if hasattr(self.canvas_view, 'main_window') else None
                        )
                        logger.info(f"推理已启动: {inference_result}")
                        # 启动扫描动画（如果推理已成功以后台线程形式启动）
                        try:
                            if isinstance(inference_result, dict) and inference_result.get('status') == 'inference_started':
                                scan_mgr = get_scan_animation_manager(self.canvas_view)
                                if scan_mgr:
                                    try:
                                        scan_mgr.start_scan_animation()
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    except Exception as e:
                        logger.error(f"推理过程中发生错误: {e}")
            
            return child
        except Exception as e:
            logger.error(f"创建标签时出错: {e}")
            return None
     
    def _update_ui_with_inference_result(self, inference_result, child_label):
        """使用推理结果更新UI的辅助方法"""
        try:
            logger.info(f"使用推理结果更新UI: {inference_result}")
            
            # 检查推理结果是否有效
            if not inference_result or isinstance(inference_result, dict) and inference_result.get("status") == "inference_started":
                logger.info("推理已启动，等待结果...")
                return
                
            if isinstance(inference_result, dict) and "error" in inference_result:
                logger.error(f"推理出错: {inference_result['error']}")
                try:
                    # from scan_animation import get_scan_animation_manager
                    mgr = get_scan_animation_manager(self.canvas_view)
                    if mgr:
                        mgr.stop_scan_animation()
                except Exception as e:
                    logger.error(f"停止扫描动画失败: {e}")
                return
                
            # 统一提取 bbox 列表
            bboxes = []
            if isinstance(inference_result, list):
                for det in inference_result:
                    if isinstance(det, dict) and "bbox" in det:
                        bboxes.append(det["bbox"])
            elif isinstance(inference_result, dict):
                if "filtered_results" in inference_result and isinstance(inference_result["filtered_results"], list):
                    for det in inference_result["filtered_results"]:
                        if isinstance(det, dict) and "bbox" in det:
                            bboxes.append(det["bbox"])
                elif "yolov_result" in inference_result and isinstance(inference_result["yolov_result"], dict):
                    fr = inference_result["yolov_result"].get("filtered_results", [])
                    for det in fr:
                        if isinstance(det, dict) and "bbox" in det:
                            bboxes.append(det["bbox"])

            if not bboxes:
                try:
                    # from scan_animation import get_scan_animation_manager
                    mgr = get_scan_animation_manager(self.canvas_view)
                    if mgr:
                        mgr.stop_scan_animation()
                except Exception as e:
                    logger.error(f"停止扫描动画失败: {e}")
                return

            # 多边形流程：child 为多边形或画布处于多边形模式时，用 bbox 驱动 SAM 分割
            is_polygon_flow = (
                hasattr(child_label, 'shape_type') and child_label.shape_type == 'polygon'
            ) or (
                hasattr(self.canvas_view, 'polygon_mode') and self.canvas_view.polygon_mode
            )
            if is_polygon_flow:
                try:
                    image_info = self.get_image_info_func() if self.get_image_info_func else None
                    if not image_info:
                        return
                    selected_parent = self.parent_label_list.get_selected()
                    if not selected_parent:
                        return
                    logger.info(f"多边形流程：用 bbox 调用 SAM，bbox count={len(bboxes)}, image={image_info}")
                    # from IN_Sam_rect import get_sam_manager as get_rect_sam_manager
                    rect_sam = get_rect_sam_manager()
                    # 连接一次性处理信号到当前对象
                    def _on_polygon_detected(payload):
                        try:
                            poly_pts = payload.get('polygon_points')
                            img_info = payload.get('image_info')
                            if not poly_pts or not img_info:
                                return
                            flat_points = []
                            for x, y in poly_pts:
                                flat_points.extend([x, y])
                            new_child = self.parent_label_list.create_child_label(
                                points=flat_points,
                                image_info=img_info,
                                mode='auto',
                                shape_type='polygon',
                                polygon_points=poly_pts
                            )
                            if hasattr(self.canvas_view, 'update_rects'):
                                self.canvas_view.update_rects()
                        except Exception as _e:
                            logger.error(f"处理 polygon_detected 时发生错误: {_e}")
                    try:
                        rect_sam.polygon_detected.disconnect()
                    except Exception:
                        pass
                    rect_sam.polygon_detected.connect(_on_polygon_detected)
                    # 异步处理 bbox 列表，内部驱动 SAM 并通过信号回传 polygon
                    rect_sam.process_yolov_bboxes_for_polygon(
                        bbox_list=bboxes,
                        image_info=image_info,
                        selected_parent=selected_parent,
                        parent_label_list=self.parent_label_list,
                        canvas_view=self.canvas_view
                    )
                except Exception as e:
                    logger.error(f"通过 IN_Sam_rect 处理 bbox 时发生错误: {e}")
                return

            # 非多边形模式：保持原有矩形标签创建
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
            selected_parent = self.parent_label_list.get_selected()
            if not selected_parent:
                logger.warning("没有选中的父标签")
                return
            for bbox in bboxes:
                if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                    points = [x1, y1, x2, y1, x2, y2, x1, y2]
                    new_child = self.parent_label_list.create_child_label(
                        points=points,
                        image_info=image_info,
                        mode='auto',
                        shape_type='rectangle'
                    )
            if hasattr(self.canvas_view, 'update_rects'):
                self.canvas_view.update_rects()
            try:
                # from scan_animation import get_scan_animation_manager
                mgr = get_scan_animation_manager(self.canvas_view)
                if mgr:
                    mgr.stop_scan_animation()
            except Exception as e:
                logger.error(f"停止扫描动画失败: {e}")
            
        except Exception as e:
            logger.error(f"更新UI时发生错误: {e}")

    def update_rects(self) -> None:
        try:
            # 清除现有矩形框和多边形
            for item in list(self.canvas_view.scene.items()):
                if ((isinstance(item, QGraphicsRectItem) or isinstance(item, QGraphicsPolygonItem) or isinstance(item, QGraphicsLineItem) or isinstance(item, QGraphicsEllipseItem)) and 
                    item is not self.canvas_view.image_item and 
                    item.scene() == self.canvas_view.scene):
                    
                    # 检查是否是普通的矩形框/多边形
                    is_normal_item = hasattr(item, 'child_label') and item.child_label
                    
                    # 如果是普通的矩形框/多边形，则移除
                    if is_normal_item:
                        self.canvas_view.scene.removeItem(item)

            # 添加新的矩形框和多边形
            if (self.parent_label_list and 
                self.get_image_info_func and 
                hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap):

                image_info = self.get_image_info_func()
                if not image_info:
                    return

                for label in self.parent_label_list.labels:
                    if (hasattr(label, 'children_by_image') and 
                        image_info in label.children_by_image):

                        for child in label.children_by_image[image_info]:
                            if getattr(child, 'is_placeholder', False):
                                continue

                            # 检查是否是OBB矩形框
                            if hasattr(child, 'is_obb') and child.is_obb and hasattr(child, 'corner_points'):
                                # 创建OBB矩形框
                                polygon = QPolygonF()
                                
                                # 获取当前图像的尺寸
                                pixmap_width = self.canvas_view.current_pixmap.width()
                                pixmap_height = self.canvas_view.current_pixmap.height()
                                
                                # 获取图像在画布上的位置（不使用图像项缩放，以场景坐标为准）
                                if hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item:
                                    image_pos = self.canvas_view.image_item.pos()
                                else:
                                    image_pos = QPointF(0, 0)
                                
                                # 使用OBB的角点坐标，并转换为画布坐标
                                for pixel_x, pixel_y in child.corner_points:
                                    # 将图像坐标转换为画布坐标
                                    canvas_x = image_pos.x() + pixel_x
                                    canvas_y = image_pos.y() + pixel_y
                                    polygon.append(QPointF(canvas_x, canvas_y))
                                
                                # 创建多边形项表示OBB矩形框
                                polygon_item = QGraphicsPolygonItem(polygon)
                                
                                color = (child.color if hasattr(child, 'color') and child.color 
                                       else QColor(255, 0, 0))
                                pen = QPen(color, 2, Qt.PenStyle.SolidLine)
                                polygon_item.setPen(pen)
                                
                                fill_color = QColor(color)
                                # 根据shape_type设置不同的透明度
                                if hasattr(child, 'shape_type') and child.shape_type == 'polygon_mask':
                                    fill_color.setAlpha(120)  # 多边形MASK模式使用更低的透明度
                                else:
                                    fill_color.setAlpha(40)  # 普通多边形保持原有透明度
                                polygon_item.setBrush(QBrush(fill_color))
                                
                                polygon_item.setZValue(10)
                                polygon_item.child_label = child  # 添加子标签引用
                                self.canvas_view.scene.addItem(polygon_item)
                            
                            # 检查是否有多边形点信息
                            elif hasattr(child, 'polygon_points') and child.polygon_points:
                                # 创建多边形
                                polygon = QPolygonF()
                                
                                # 获取当前图像的尺寸
                                pixmap_width = self.canvas_view.current_pixmap.width()
                                pixmap_height = self.canvas_view.current_pixmap.height()
                                
                                # 如果有旋转角度，使用旋转后的点
                                if hasattr(child, 'rotation_angle') and child.rotation_angle != 0:
                                    rotated_points = child.get_rotated_polygon_points()
                                    for pixel_x, pixel_y in rotated_points:
                                        # 直接使用实际像素坐标
                                        polygon.append(QPointF(pixel_x, pixel_y))
                                else:
                                    # 没有旋转，使用原始点
                                    for pixel_x, pixel_y in child.polygon_points:
                                        # 直接使用实际像素坐标
                                        polygon.append(QPointF(pixel_x, pixel_y))
                                
                                # 创建多边形项
                                polygon_item = QGraphicsPolygonItem(polygon)
                                
                                color = (child.color if hasattr(child, 'color') and child.color 
                                       else QColor(255, 0, 0))
                                
                                # 根据shape_type决定是否显示轮廓线
                                if hasattr(child, 'shape_type') and child.shape_type == 'polygon_mask':
                                    # 多边形MASK模式不显示轮廓线，只显示填充
                                    pen = QPen(color, 0, Qt.PenStyle.NoPen)  # 无轮廓线
                                else:
                                    # 普通多边形显示轮廓线
                                    pen = QPen(color, 2, Qt.PenStyle.SolidLine)
                                
                                polygon_item.setPen(pen)
                                
                                fill_color = QColor(color)
                                # 根据shape_type决定填充透明度
                                if hasattr(child, 'shape_type') and child.shape_type == 'polygon_mask':
                                    fill_color.setAlpha(120)  # 多边形MASK模式使用更高的透明度(更不透明)
                                else:
                                    fill_color.setAlpha(40)   # 普通多边形使用默认透明度
                                polygon_item.setBrush(QBrush(fill_color))
                                
                                polygon_item.setZValue(10)
                                polygon_item.child_label = child  # 添加子标签引用
                                self.canvas_view.scene.addItem(polygon_item)
                            elif hasattr(child, 'shape_type') and child.shape_type == 'line' and hasattr(child, 'points') and len(child.points) >= 4:
                                # 创建线标签
                                x1, y1 = child.points[0], child.points[1]
                                x2, y2 = child.points[2], child.points[3]
                                line_item = QGraphicsLineItem(x1, y1, x2, y2)
                                color = (child.color if hasattr(child, 'color') and child.color else QColor(255, 0, 0))
                                pen = QPen(color, 2, Qt.PenStyle.SolidLine)
                                line_item.setPen(pen)
                                line_item.setZValue(10)
                                line_item.child_label = child
                                self.canvas_view.scene.addItem(line_item)
                            elif hasattr(child, 'shape_type') and child.shape_type == 'point':
                                # 创建点标签（小圆点）
                                cx = getattr(child, 'x_center', None)
                                cy = getattr(child, 'y_center', None)
                                if cx is None or cy is None:
                                    if hasattr(child, 'points') and len(child.points) >= 2:
                                        cx, cy = child.points[0], child.points[1]
                                if cx is not None and cy is not None:
                                    radius = 4
                                    ellipse_item = QGraphicsEllipseItem(cx - radius, cy - radius, radius*2, radius*2)
                                    color = (child.color if hasattr(child, 'color') and child.color else QColor(255, 0, 0))
                                    pen = QPen(color, 1, Qt.PenStyle.SolidLine)
                                    fill_color = QColor(color)
                                    fill_color.setAlpha(100)
                                    ellipse_item.setPen(pen)
                                    ellipse_item.setBrush(QBrush(fill_color))
                                    ellipse_item.setZValue(12)
                                    ellipse_item.child_label = child
                                    self.canvas_view.scene.addItem(ellipse_item)
                            elif hasattr(child, 'shape_type') and child.shape_type == 'circle':
                                # 创建圆形标签
                                if hasattr(child, 'points') and len(child.points) >= 3:
                                    center_x, center_y, radius = child.points[0], child.points[1], child.points[2]
                                elif hasattr(child, 'center_x') and hasattr(child, 'center_y') and hasattr(child, 'radius'):
                                    center_x, center_y, radius = child.center_x, child.center_y, child.radius
                                else:
                                    continue  # 跳过无效的圆形标签
                                
                                # 创建圆形图形项
                                diameter = radius * 2
                                ellipse_item = QGraphicsEllipseItem(
                                    center_x - radius, center_y - radius, diameter, diameter
                                )
                                color = (child.color if hasattr(child, 'color') and child.color else QColor(255, 0, 0))
                                pen = QPen(color, 2, Qt.PenStyle.SolidLine)
                                ellipse_item.setPen(pen)
                                
                                fill_color = QColor(color)
                                fill_color.setAlpha(40)
                                ellipse_item.setBrush(QBrush(fill_color))
                                
                                ellipse_item.setZValue(10)
                                ellipse_item.child_label = child
                                self.canvas_view.scene.addItem(ellipse_item)
                            else:
                                # 创建矩形框
                                # 如果有旋转角度，使用旋转后的角点创建多边形
                                if hasattr(child, 'rotation_angle') and child.rotation_angle != 0:
                                    polygon = QPolygonF()
                                    rotated_corners = child.get_rotated_rect_corners()
                                    
                                    # 获取当前图像的尺寸
                                    pixmap_width = self.canvas_view.current_pixmap.width()
                                    pixmap_height = self.canvas_view.current_pixmap.height()
                                    
                                    for pixel_x, pixel_y in rotated_corners:
                                        # 直接使用实际像素坐标
                                        polygon.append(QPointF(pixel_x, pixel_y))
                                    
                                    # 创建多边形项表示旋转的矩形
                                    polygon_item = QGraphicsPolygonItem(polygon)
                                    
                                    color = (child.color if hasattr(child, 'color') and child.color 
                                           else QColor(255, 0, 0))
                                    pen = QPen(color, 2, Qt.PenStyle.SolidLine)
                                    polygon_item.setPen(pen)
                                    
                                    fill_color = QColor(color)
                                    fill_color.setAlpha(40)
                                    polygon_item.setBrush(QBrush(fill_color))
                                    
                                    polygon_item.setZValue(10)
                                    polygon_item.child_label = child  # 添加子标签引用
                                    self.canvas_view.scene.addItem(polygon_item)
                                else:
                                    # 没有旋转，使用普通矩形
                                    x = child.x_center - child.width/2
                                    y = child.y_center - child.height/2
                                    w = child.width
                                    h = child.height

                                    # 使用canvas_view的LabelRectItem类，避免循环导入
                                    rect_item = self.canvas_view.LabelRectItem(x, y, w, h, 
                                                                            child_label=child, 
                                                                            parent_view=self.canvas_view)

                                    color = (child.color if hasattr(child, 'color') and child.color 
                                           else QColor(255, 0, 0))
                                    pen = QPen(color, 2, Qt.PenStyle.SolidLine)
                                    rect_item.setPen(pen)

                                    fill_color = QColor(color)
                                    fill_color.setAlpha(40)
                                    rect_item.setBrush(QBrush(fill_color))

                                    rect_item.setZValue(10)
                                    rect_item.child_label = child  # 添加子标签引用
                                    self.canvas_view.scene.addItem(rect_item)

        except Exception as e:
            logger.error(f"更新矩形框和多边形时发生错误: {e}")
    
    
    
    
    
    
    
    def set_ui_locked(self, locked: bool) -> None:
        """设置UI锁定状态"""
        if hasattr(self.canvas_view, 'ui_locked'):
            self.canvas_view.ui_locked = locked
    
    def polygon_huabi(self, event_type: str, event) -> bool:
        """
        多边形绘制方法，实现首位相接的矩形框绘制功能
        
        Args:
            event_type: 事件类型 ('press', 'move', 'release')
            event: 鼠标事件对象
            
        Returns:
            bool: 事件是否被处理
        """
        try:
            if event_type == 'press':
                return self._handle_polygon_press(event)
            elif event_type == 'move':
                return self._handle_polygon_move(event)
            elif event_type == 'release':
                return self._handle_polygon_release(event)
            return False
        except Exception as e:
            logger.error(f"处理多边形绘制事件时发生错误: {e}")
            return False
    
    def _handle_polygon_press(self, event) -> bool:
        """处理多边形绘制中的鼠标按下事件"""
        if hasattr(self.canvas_view, 'ui_locked') and self.canvas_view.ui_locked:
            return False
            
        if (hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item and 
            self.parent_label_list and 
            self.parent_label_list.get_selected()):
            
            scene_pos = self.canvas_view.mapToScene(event.pos())
            
            if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                x = min(max(scene_pos.x(), 0), self.canvas_view.current_pixmap.width())
                y = min(max(scene_pos.y(), 0), self.canvas_view.current_pixmap.height())
                scene_pos = QPoint(int(x), int(y))
            
            # 左键创建锚点
            if event.button() == Qt.MouseButton.LeftButton:
                # 添加锚点（增量绘制）
                if not hasattr(self, 'polygon_points'):
                    self.polygon_points = []
                if not hasattr(self, 'polygon_point_items'):
                    self.polygon_point_items = []
                if not hasattr(self, 'polygon_line_items'):
                    self.polygon_line_items = []

                self.polygon_points.append(scene_pos)

                parent = self.parent_label_list.get_selected()
                use_color = (parent.color if parent and hasattr(parent, 'color') and parent.color else QColor(0, 255, 0))

                ellipse_item = QGraphicsEllipseItem(scene_pos.x()-3, scene_pos.y()-3, 6, 6)
                ellipse_item.setPen(QPen(use_color, 1, Qt.PenStyle.SolidLine))
                ellipse_item.setBrush(QBrush(use_color))
                ellipse_item.setZValue(16)
                self.canvas_view.scene.addItem(ellipse_item)
                self.polygon_point_items.append(ellipse_item)

                if len(self.polygon_points) >= 2:
                    p0 = self.polygon_points[-2]
                    p1 = self.polygon_points[-1]
                    line_item = QGraphicsLineItem(p0.x(), p0.y(), p1.x(), p1.y())
                    line_item.setPen(QPen(use_color, 2, Qt.PenStyle.SolidLine))
                    line_item.setZValue(15)
                    self.canvas_view.scene.addItem(line_item)
                    self.polygon_line_items.append(line_item)
                
                # 检查是否首尾相接（至少需要3个点才能形成多边形）
                if len(self.polygon_points) >= 3:
                    first_point = self.polygon_points[0]
                    last_point = self.polygon_points[-1]
                    distance = ((first_point.x() - last_point.x())**2 + 
                               (first_point.y() - last_point.y())**2)**0.5
                    
                    # 如果首尾距离小于10像素，认为首尾相接
                    if distance < 10:
                        self._create_polygon_label()
                        return True
                
                return True
            
            # 右键撤销锚点
            elif event.button() == Qt.MouseButton.RightButton and hasattr(self, 'polygon_points') and self.polygon_points:
                self.polygon_points.pop()
                if hasattr(self, 'polygon_point_items') and self.polygon_point_items:
                    last_pt = self.polygon_point_items.pop()
                    if last_pt and last_pt.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(last_pt)
                if hasattr(self, 'polygon_line_items') and self.polygon_line_items:
                    last_ln = self.polygon_line_items.pop()
                    if last_ln and last_ln.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(last_ln)
                if hasattr(self, 'polygon_temp_line_item') and self.polygon_temp_line_item:
                    if self.polygon_temp_line_item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(self.polygon_temp_line_item)
                    self.polygon_temp_line_item = None
                
                return True
                
        return False
    
    def _handle_polygon_move(self, event) -> bool:
        """处理多边形绘制中的鼠标移动事件"""
        if hasattr(self.canvas_view, 'ui_locked') and self.canvas_view.ui_locked:
            return False
            
        if (hasattr(self, 'polygon_points') and self.polygon_points and
            hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item):
            
            scene_pos = self.canvas_view.mapToScene(event.pos())
            
            if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                x = min(max(scene_pos.x(), 0), self.canvas_view.current_pixmap.width())
                y = min(max(scene_pos.y(), 0), self.canvas_view.current_pixmap.height())
                scene_pos = QPoint(int(x), int(y))
            
            # 绘制临时线条（从最后一个锚点到当前鼠标位置）
            self._draw_polygon_temp_line(scene_pos)
            
            return True
            
        return False
    
    def _handle_polygon_release(self, event) -> bool:
        """处理多边形绘制中的鼠标释放事件"""
        # 在多边形绘制中，释放事件不需要特殊处理
        return False
    
    def polygon_mask_huabi(self, event_type: str, event) -> bool:
        """
        多边形MASK模式绘制方法，实现多边形绘制并在内部生成MASK
        
        Args:
            event_type: 事件类型 ('press', 'move', 'release')
            event: 鼠标事件对象
            
        Returns:
            bool: 事件是否被处理
        """
        try:
            if event_type == 'press':
                return self._handle_polygon_mask_press(event)
            elif event_type == 'move':
                return self._handle_polygon_mask_move(event)
            elif event_type == 'release':
                return self._handle_polygon_mask_release(event)
            return False
        except Exception as e:
            logger.error(f"处理多边形MASK模式绘制事件时发生错误: {e}")
            return False
    
    def _draw_polygon_points(self) -> None:
        """绘制多边形锚点"""
        try:
            # 清除现有多边形绘制
            self._clear_polygon_drawing()
            
            if not hasattr(self, 'polygon_points') or not self.polygon_points:
                return
                
            # 绘制锚点之间的连线
            for i in range(len(self.polygon_points) - 1):
                line_item = QGraphicsLineItem(
                    self.polygon_points[i].x(), self.polygon_points[i].y(),
                    self.polygon_points[i+1].x(), self.polygon_points[i+1].y()
                )
                
                parent = self.parent_label_list.get_selected()
                if parent and hasattr(parent, 'color') and parent.color:
                    pen = QPen(parent.color, 2, Qt.PenStyle.SolidLine)
                else:
                    pen = QPen(QColor(0, 255, 0), 2, Qt.PenStyle.SolidLine)
                
                line_item.setPen(pen)
                line_item.setZValue(15)
                self.canvas_view.scene.addItem(line_item)
                
                if not hasattr(self, 'polygon_line_items'):
                    self.polygon_line_items = []
                self.polygon_line_items.append(line_item)
            
            # 绘制锚点
            for point in self.polygon_points:
                ellipse_item = QGraphicsEllipseItem(point.x()-3, point.y()-3, 6, 6)
                
                parent = self.parent_label_list.get_selected()
                if parent and hasattr(parent, 'color') and parent.color:
                    pen = QPen(parent.color, 1, Qt.PenStyle.SolidLine)
                    brush = QBrush(parent.color)
                else:
                    pen = QPen(QColor(0, 255, 0), 1, Qt.PenStyle.SolidLine)
                    brush = QBrush(QColor(0, 255, 0))
                
                ellipse_item.setPen(pen)
                ellipse_item.setBrush(brush)
                ellipse_item.setZValue(16)
                self.canvas_view.scene.addItem(ellipse_item)
                
                if not hasattr(self, 'polygon_point_items'):
                    self.polygon_point_items = []
                self.polygon_point_items.append(ellipse_item)
                
        except Exception as e:
            logger.error(f"绘制多边形锚点时发生错误: {e}")
    
    def _draw_polygon_temp_line(self, end_point: QPoint) -> None:
        """绘制多边形临时线条（从最后一个锚点到当前鼠标位置）"""
        try:
            if hasattr(self, 'polygon_points') and self.polygon_points:
                # 绘制锚点之间的连线
                # 已有连线与锚点不重绘，改为仅更新临时线
                
                # 不重复绘制已有锚点
                
                # 绘制/更新单一临时线
                if self.polygon_points:
                    parent = self.parent_label_list.get_selected()
                    use_color = (parent.color if parent and hasattr(parent, 'color') and parent.color else QColor(0, 255, 0))
                    if hasattr(self, 'polygon_temp_line_item') and self.polygon_temp_line_item:
                        self.polygon_temp_line_item.setLine(
                            self.polygon_points[-1].x(), self.polygon_points[-1].y(), end_point.x(), end_point.y()
                        )
                        self.polygon_temp_line_item.setPen(QPen(use_color, 2, Qt.PenStyle.DashLine))
                    else:
                        self.polygon_temp_line_item = QGraphicsLineItem(
                            self.polygon_points[-1].x(), self.polygon_points[-1].y(), end_point.x(), end_point.y()
                        )
                        self.polygon_temp_line_item.setPen(QPen(use_color, 2, Qt.PenStyle.DashLine))
                        self.polygon_temp_line_item.setZValue(14)
                        self.canvas_view.scene.addItem(self.polygon_temp_line_item)

                    # 首点吸附提示
                    try:
                        first_point = self.polygon_points[0]
                        dx = first_point.x() - end_point.x()
                        dy = first_point.y() - end_point.y()
                        dist = (dx*dx + dy*dy)**0.5
                        threshold = 10
                        if dist < threshold and len(self.polygon_points) >= 2:
                            if not hasattr(self, 'polygon_snap_hint_item') or self.polygon_snap_hint_item is None:
                                hint = QGraphicsEllipseItem(first_point.x()-6, first_point.y()-6, 12, 12)
                                hint.setPen(QPen(use_color, 1, Qt.PenStyle.DashLine))
                                hint.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                                hint.setZValue(13)
                                self.canvas_view.scene.addItem(hint)
                                self.polygon_snap_hint_item = hint
                            else:
                                self.polygon_snap_hint_item.setRect(first_point.x()-6, first_point.y()-6, 12, 12)
                                self.polygon_temp_line_item.setPen(QPen(use_color, 3, Qt.PenStyle.DashLine))
                        else:
                            if hasattr(self, 'polygon_snap_hint_item') and self.polygon_snap_hint_item:
                                if self.polygon_snap_hint_item.scene() == self.canvas_view.scene:
                                    self.canvas_view.scene.removeItem(self.polygon_snap_hint_item)
                                self.polygon_snap_hint_item = None
                    except Exception:
                        pass
                
        except Exception as e:
            logger.error(f"绘制多边形临时线条时发生错误: {e}")
    
    def _clear_polygon_drawing(self) -> None:
        """清除多边形绘制相关的所有图形元素"""
        try:
            # 清除锚点
            if hasattr(self, 'polygon_point_items') and self.polygon_point_items:
                for item in self.polygon_point_items:
                    if item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(item)
                self.polygon_point_items = []
            
            # 清除连线
            if hasattr(self, 'polygon_line_items') and self.polygon_line_items:
                for item in self.polygon_line_items:
                    if item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(item)
                self.polygon_line_items = []
            
            # 清除临时线条
            if hasattr(self, 'polygon_temp_line_items') and self.polygon_temp_line_items:
                for item in self.polygon_temp_line_items:
                    if item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(item)
                self.polygon_temp_line_items = []
            
            # 清除单个临时线条（兼容旧代码）
            if hasattr(self, 'polygon_temp_line_item') and self.polygon_temp_line_item:
                if self.polygon_temp_line_item.scene() == self.canvas_view.scene:
                    self.canvas_view.scene.removeItem(self.polygon_temp_line_item)
                self.polygon_temp_line_item = None
            # 清除吸附提示
            if hasattr(self, 'polygon_snap_hint_item') and self.polygon_snap_hint_item:
                if self.polygon_snap_hint_item.scene() == self.canvas_view.scene:
                    self.canvas_view.scene.removeItem(self.polygon_snap_hint_item)
                self.polygon_snap_hint_item = None
                
        except Exception as e:
            logger.error(f"清除多边形绘制时发生错误: {e}")
    
    def _create_polygon_label(self, rotation_angle=0) -> None:
        """从多边形创建标签"""
        try:
            if not hasattr(self, 'polygon_points') or len(self.polygon_points) < 3:
                return
                
            if not hasattr(self.canvas_view, 'current_pixmap') or not self.canvas_view.current_pixmap:
                return
            
            # 计算多边形的边界框
            min_x = min(point.x() for point in self.polygon_points)
            max_x = max(point.x() for point in self.polygon_points)
            min_y = min(point.y() for point in self.polygon_points)
            max_y = max(point.y() for point in self.polygon_points)
            
            x = min_x
            y = min_y
            w = max_x - min_x
            h = max_y - min_y
            
            # 使用实际坐标
            x_center = x + w/2
            y_center = y + h/2
            
            # 获取图片信息
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
            
            # 创建多边形标签
            # 将坐标对列表转换为扁平列表，以符合ChildLabel构造函数的期望格式
            flat_points = []
            for point in self.polygon_points:
                flat_points.append(point.x())
                flat_points.append(point.y())
            
            # 使用顶点坐标创建多边形标签
            child = self.parent_label_list.create_child_label(
                points=flat_points, 
                image_info=image_info, 
                mode='manual',
                shape_type='polygon', 
                polygon_points=[(point.x(), point.y()) for point in self.polygon_points],
                rotation_angle=rotation_angle)
            
            if child:
                # 计算多边形的外接矩形（仅计算，不显示）
                polygon_coords = [(point.x(), point.y()) for point in self.polygon_points]
                bounding_rect = calculate_bounding_rectangle(polygon_coords)
                
                # 更新矩形框
                if hasattr(self.canvas_view, 'update_rects'):
                    self.canvas_view.update_rects()
                
                # 检查自动标注开关状态并发送推理信号
                if hasattr(self.canvas_view, 'main_window') and self.canvas_view.main_window:
                    auto_annotation_enabled = getattr(self.canvas_view.main_window, 'auto_annotation_enabled', False)
                    if auto_annotation_enabled:
                        logger.info("自动标注开关已开启，发送推理信号")
                        try:
                            # 定义推理回调：停止动画并在主线程更新UI
                            def handle_inference_result(result):
                                logger.info(f"推理结果: {result}")
                                try:
                                    scan_mgr = get_scan_animation_manager(self.canvas_view)
                                    if scan_mgr:
                                        def stop_anim():
                                            try:
                                                scan_mgr.stop_scan_animation(result)
                                            except Exception as e:
                                                logger.error(f"QTimer停止扫描动画失败: {e}")
                                        QTimer.singleShot(0, stop_anim)
                                except Exception as e:
                                    logger.error(f"获取扫描动画管理器失败: {e}")
                                QTimer.singleShot(0, lambda: self._update_ui_with_inference_result(result, child))

                            # 调用推理（后台线程启动）
                            inference_result = run_inference_with_specific_child(
                                get_image_info_func=self.get_image_info_func,
                                parent_label_list=self.parent_label_list,
                                child_label=child,
                                shape_type='polygon',
                                callback=handle_inference_result,
                                main_window=self.canvas_view.main_window if hasattr(self.canvas_view, 'main_window') else None
                            )
                            logger.info(f"推理已启动: {inference_result}")
                            # 若已成功启动后台推理，则启动扫描动画
                            try:
                                if isinstance(inference_result, dict) and inference_result.get('status') == 'inference_started':
                                    scan_mgr = get_scan_animation_manager(self.canvas_view)
                                    if scan_mgr:
                                        try:
                                            scan_mgr.start_scan_animation()
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        except Exception as e:
                            logger.error(f"推理过程中发生错误: {e}")
                
                # 清除多边形绘制
                self._clear_polygon_drawing()
                self.polygon_points = []
                
        except Exception as e:
            logger.error(f"创建多边形标签时发生错误: {e}")
    
    def _handle_polygon_mask_press(self, event) -> bool:
        """处理多边形MASK模式中的鼠标按下事件"""
        if hasattr(self.canvas_view, 'ui_locked') and self.canvas_view.ui_locked:
            return False
            
        if (hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item and 
            self.parent_label_list and 
            self.parent_label_list.get_selected()):
            
            scene_pos = self.canvas_view.mapToScene(event.pos())
            
            if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                x = min(max(scene_pos.x(), 0), self.canvas_view.current_pixmap.width())
                y = min(max(scene_pos.y(), 0), self.canvas_view.current_pixmap.height())
                scene_pos = QPoint(int(x), int(y))
            
            # 左键创建锚点
            if event.button() == Qt.MouseButton.LeftButton:
                # 添加锚点
                if not hasattr(self, 'polygon_mask_points'):
                    self.polygon_mask_points = []
                
                self.polygon_mask_points.append(scene_pos)
                
                # 绘制多边形预览效果
                self._draw_polygon_mask_points()
                
                # 检查是否首尾相接（至少需要3个点才能形成多边形）
                if len(self.polygon_mask_points) >= 3:
                    first_point = self.polygon_mask_points[0]
                    last_point = self.polygon_mask_points[-1]
                    distance = ((first_point.x() - last_point.x())**2 + 
                               (first_point.y() - last_point.y())**2)**0.5
                    
                    # 如果首尾距离小于10像素，认为首尾相接
                    if distance < 10:
                        self._create_polygon_mask_label()
                        return True
                
                return True
            
            # 右键撤销锚点
            elif event.button() == Qt.MouseButton.RightButton and hasattr(self, 'polygon_mask_points') and self.polygon_mask_points:
                # 移除最后一个锚点
                self.polygon_mask_points.pop()
                
                # 重新绘制多边形预览效果
                self._draw_polygon_mask_points()
                
                return True
                
        return False
    
    def _handle_polygon_mask_move(self, event) -> bool:
        """处理多边形MASK模式中的鼠标移动事件"""
        if hasattr(self.canvas_view, 'ui_locked') and self.canvas_view.ui_locked:
            return False
            
        if (hasattr(self, 'polygon_mask_points') and self.polygon_mask_points and
            hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item):
            
            scene_pos = self.canvas_view.mapToScene(event.pos())
            
            if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                x = min(max(scene_pos.x(), 0), self.canvas_view.current_pixmap.width())
                y = min(max(scene_pos.y(), 0), self.canvas_view.current_pixmap.height())
                scene_pos = QPoint(int(x), int(y))
            
            # 绘制临时线条（从最后一个锚点到当前鼠标位置）
            self._draw_polygon_mask_temp_line(scene_pos)
            
            return True
            
        return False
    
    def _handle_polygon_mask_release(self, event) -> bool:
        """处理多边形MASK模式中的鼠标释放事件"""
        # 在多边形MASK模式中，释放事件不需要特殊处理
        return False
    
    def _draw_polygon_mask_points(self) -> None:
        """绘制多边形MASK模式的锚点"""
        try:
            # 清除现有多边形MASK模式绘制
            self._clear_polygon_mask_drawing()
            
            if not hasattr(self, 'polygon_mask_points') or not self.polygon_mask_points:
                return
                
            # 绘制锚点之间的连线
            for i in range(len(self.polygon_mask_points) - 1):
                line_item = QGraphicsLineItem(
                    self.polygon_mask_points[i].x(), self.polygon_mask_points[i].y(),
                    self.polygon_mask_points[i+1].x(), self.polygon_mask_points[i+1].y()
                )
                
                parent = self.parent_label_list.get_selected()
                if parent and hasattr(parent, 'color') and parent.color:
                    pen = QPen(parent.color, 2, Qt.PenStyle.SolidLine)
                else:
                    pen = QPen(QColor(255, 0, 255), 2, Qt.PenStyle.SolidLine)  # 使用紫色区分MASK模式
                
                line_item.setPen(pen)
                line_item.setZValue(15)
                self.canvas_view.scene.addItem(line_item)
                
                if not hasattr(self, 'polygon_mask_line_items'):
                    self.polygon_mask_line_items = []
                self.polygon_mask_line_items.append(line_item)
            
            # 绘制锚点
            for point in self.polygon_mask_points:
                ellipse_item = QGraphicsEllipseItem(point.x()-3, point.y()-3, 6, 6)
                
                parent = self.parent_label_list.get_selected()
                if parent and hasattr(parent, 'color') and parent.color:
                    pen = QPen(parent.color, 1, Qt.PenStyle.SolidLine)
                    brush = QBrush(parent.color)
                else:
                    pen = QPen(QColor(255, 0, 255), 1, Qt.PenStyle.SolidLine)  # 使用紫色区分MASK模式
                    brush = QBrush(QColor(255, 0, 255))
                
                ellipse_item.setPen(pen)
                ellipse_item.setBrush(brush)
                ellipse_item.setZValue(16)
                self.canvas_view.scene.addItem(ellipse_item)
                
                if not hasattr(self, 'polygon_mask_point_items'):
                    self.polygon_mask_point_items = []
                self.polygon_mask_point_items.append(ellipse_item)
                
        except Exception as e:
            logger.error(f"绘制多边形MASK模式锚点时发生错误: {e}")
    
    def _draw_polygon_mask_temp_line(self, end_point: QPoint) -> None:
        """绘制多边形MASK模式临时线条（从最后一个锚点到当前鼠标位置）"""
        try:
            # 清除现有多边形MASK模式绘制
            self._clear_polygon_mask_drawing()
            
            # 重新绘制已有的锚点和连线
            if hasattr(self, 'polygon_mask_points') and self.polygon_mask_points:
                # 绘制锚点之间的连线
                for i in range(len(self.polygon_mask_points) - 1):
                    line_item = QGraphicsLineItem(
                        self.polygon_mask_points[i].x(), self.polygon_mask_points[i].y(),
                        self.polygon_mask_points[i+1].x(), self.polygon_mask_points[i+1].y()
                    )
                    
                    parent = self.parent_label_list.get_selected()
                    if parent and hasattr(parent, 'color') and parent.color:
                        pen = QPen(parent.color, 2, Qt.PenStyle.SolidLine)
                    else:
                        pen = QPen(QColor(255, 0, 255), 2, Qt.PenStyle.SolidLine)  # 使用紫色区分MASK模式
                    
                    line_item.setPen(pen)
                    line_item.setZValue(15)
                    self.canvas_view.scene.addItem(line_item)
                    
                    if not hasattr(self, 'polygon_mask_line_items'):
                        self.polygon_mask_line_items = []
                    self.polygon_mask_line_items.append(line_item)
                
                # 绘制锚点
                for point in self.polygon_mask_points:
                    ellipse_item = QGraphicsEllipseItem(point.x()-3, point.y()-3, 6, 6)
                    
                    parent = self.parent_label_list.get_selected()
                    if parent and hasattr(parent, 'color') and parent.color:
                        pen = QPen(parent.color, 1, Qt.PenStyle.SolidLine)
                        brush = QBrush(parent.color)
                    else:
                        pen = QPen(QColor(255, 0, 255), 1, Qt.PenStyle.SolidLine)  # 使用紫色区分MASK模式
                        brush = QBrush(QColor(255, 0, 255))
                    
                    ellipse_item.setPen(pen)
                    ellipse_item.setBrush(brush)
                    ellipse_item.setZValue(16)
                    self.canvas_view.scene.addItem(ellipse_item)
                    
                    if not hasattr(self, 'polygon_mask_point_items'):
                        self.polygon_mask_point_items = []
                    self.polygon_mask_point_items.append(ellipse_item)
                
                # 绘制从最后一个锚点到当前鼠标位置的临时线
                if self.polygon_mask_points:
                    temp_line_item = QGraphicsLineItem(
                        self.polygon_mask_points[-1].x(), self.polygon_mask_points[-1].y(),
                        end_point.x(), end_point.y()
                    )
                    
                    parent = self.parent_label_list.get_selected()
                    if parent and hasattr(parent, 'color') and parent.color:
                        pen = QPen(parent.color, 2, Qt.PenStyle.DashLine)
                    else:
                        pen = QPen(QColor(255, 0, 255), 2, Qt.PenStyle.DashLine)  # 使用紫色区分MASK模式
                    
                    temp_line_item.setPen(pen)
                    temp_line_item.setZValue(14)
                    self.canvas_view.scene.addItem(temp_line_item)
                    
                    if not hasattr(self, 'polygon_mask_temp_line_items'):
                        self.polygon_mask_temp_line_items = []
                    self.polygon_mask_temp_line_items.append(temp_line_item)
                
        except Exception as e:
            logger.error(f"绘制多边形MASK模式临时线条时发生错误: {e}")
    
    def _clear_polygon_mask_drawing(self) -> None:
        """清除多边形MASK模式绘制相关的所有图形元素"""
        try:
            # 清除锚点
            if hasattr(self, 'polygon_mask_point_items') and self.polygon_mask_point_items:
                for item in self.polygon_mask_point_items:
                    if item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(item)
                self.polygon_mask_point_items = []
            
            # 清除连线
            if hasattr(self, 'polygon_mask_line_items') and self.polygon_mask_line_items:
                for item in self.polygon_mask_line_items:
                    if item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(item)
                self.polygon_mask_line_items = []
            
            # 清除临时线条
            if hasattr(self, 'polygon_mask_temp_line_items') and self.polygon_mask_temp_line_items:
                for item in self.polygon_mask_temp_line_items:
                    if item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(item)
                self.polygon_mask_temp_line_items = []
                
        except Exception as e:
            logger.error(f"清除多边形MASK模式绘制时发生错误: {e}")
    
    def _create_polygon_mask_label(self) -> None:
        """从多边形创建MASK标签"""
        try:
            if not hasattr(self, 'polygon_mask_points') or len(self.polygon_mask_points) < 3:
                return
                
            if not hasattr(self.canvas_view, 'current_pixmap') or not self.canvas_view.current_pixmap:
                return
            
            # 计算多边形的边界框
            min_x = min(point.x() for point in self.polygon_mask_points)
            max_x = max(point.x() for point in self.polygon_mask_points)
            min_y = min(point.y() for point in self.polygon_mask_points)
            max_y = max(point.y() for point in self.polygon_mask_points)
            
            x = min_x
            y = min_y
            w = max_x - min_x
            h = max_y - min_y
            
            # 获取图片信息
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
            
            # 获取当前选中的父标签
            parent = self.parent_label_list.get_selected()
            if not parent:
                logger.warning("没有选中的父标签")
                return
            
            # 创建多边形MASK标签
            # 将坐标对列表转换为扁平列表，以符合ChildLabel构造函数的期望格式
            flat_points = []
            for point in self.polygon_mask_points:
                flat_points.append(point.x())
                flat_points.append(point.y())
            
            # 使用顶点坐标创建多边形MASK标签
            child = self.parent_label_list.create_child_label(
                points=flat_points, 
                image_info=image_info, 
                mode='manual',
                shape_type='polygon_mask',  # 使用特殊的shape_type区分MASK模式
                polygon_points=[(point.x(), point.y()) for point in self.polygon_mask_points])
            
            if child:
                # 更新矩形框
                if hasattr(self.canvas_view, 'update_rects'):
                    self.canvas_view.update_rects()
                
                # 检查自动标注开关状态并发送推理信号
                if hasattr(self.canvas_view, 'main_window') and self.canvas_view.main_window:
                    auto_annotation_enabled = getattr(self.canvas_view.main_window, 'auto_annotation_enabled', False)
                    if auto_annotation_enabled:
                        logger.info("自动标注开关已开启，发送推理信号")
                        try:
                            # 定义推理回调：停止动画并在主线程更新UI
                            def handle_inference_result(result):
                                logger.info(f"推理结果: {result}")
                                try:
                                    scan_mgr = get_scan_animation_manager(self.canvas_view)
                                    if scan_mgr:
                                        def stop_anim():
                                            try:
                                                scan_mgr.stop_scan_animation(result)
                                            except Exception as e:
                                                logger.error(f"QTimer停止扫描动画失败: {e}")
                                        QTimer.singleShot(0, stop_anim)
                                except Exception as e:
                                    logger.error(f"获取扫描动画管理器失败: {e}")
                                QTimer.singleShot(0, lambda: self._update_ui_with_inference_result(result, child))

                            # 调用推理（后台线程启动）
                            inference_result = run_inference_with_specific_child(
                                get_image_info_func=self.get_image_info_func,
                                parent_label_list=self.parent_label_list,
                                child_label=child,
                                shape_type='polygon_mask',  # 使用特殊的shape_type
                                callback=handle_inference_result,
                                main_window=self.canvas_view.main_window if hasattr(self.canvas_view, 'main_window') else None
                            )
                            logger.info(f"推理已启动: {inference_result}")
                            # 若已成功启动后台推理，则启动扫描动画
                            try:
                                if isinstance(inference_result, dict) and inference_result.get('status') == 'inference_started':
                                    scan_mgr = get_scan_animation_manager(self.canvas_view)
                                    if scan_mgr:
                                        try:
                                            scan_mgr.start_scan_animation()
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        except Exception as e:
                            logger.error(f"推理过程中发生错误: {e}")
                
                # 清除多边形MASK模式绘制
                self._clear_polygon_mask_drawing()
                self.polygon_mask_points = []
                
        except Exception as e:
            logger.error(f"创建多边形MASK标签时发生错误: {e}")
            logger.error(f"从多边形创建标签时发生错误: {e}")

    def regular_polygon_huabi(self, event_type: str, event, sides: int) -> bool:
        """正规多边形拖拽绘制：按下确定起点，拖动预览，释放创建标签
        Args:
            event_type: 'press' | 'move' | 'release'
            event: 鼠标事件
            sides: 边数（>=3）
        Returns:
            bool: 是否处理事件
        """
        try:
            if getattr(self, 'ui_locked', False):
                return False
            if not isinstance(sides, int) or sides < 3:
                return False
            if event_type == 'press':
                if event.button() == Qt.MouseButton.LeftButton and hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item:
                    if not self.parent_label_list or not self.parent_label_list.get_selected():
                        return False
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    self.regular_polygon_start = QPoint(int(scene_pos.x()), int(scene_pos.y()))
                    # 裁剪到图像边界
                    pixmap = getattr(self.canvas_view, 'current_pixmap', None)
                    if pixmap and self.regular_polygon_start:
                        self.regular_polygon_start.setX(max(0, min(self.regular_polygon_start.x(), pixmap.width() - 1)))
                        self.regular_polygon_start.setY(max(0, min(self.regular_polygon_start.y(), pixmap.height() - 1)))
                    # 清理旧的临时多边形
                    if self.temp_regular_polygon_item and self.temp_regular_polygon_item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(self.temp_regular_polygon_item)
                        self.temp_regular_polygon_item = None
                    # 创建新的临时多边形
                    self.temp_regular_polygon_item = QGraphicsPolygonItem(QPolygonF())
                    parent = self.parent_label_list.get_selected()
                    color = parent.color if parent and hasattr(parent, 'color') and parent.color else QColor(0, 255, 0)
                    pen = QPen(color, 2, Qt.PenStyle.DashLine)
                    self.temp_regular_polygon_item.setPen(pen)
                    fill_color = QColor(color)
                    fill_color.setAlpha(40)
                    self.temp_regular_polygon_item.setBrush(QBrush(fill_color))
                    self.temp_regular_polygon_item.setZValue(9)
                    self.canvas_view.scene.addItem(self.temp_regular_polygon_item)
                    self.drawing_regular_polygon = True
                    return True
            elif event_type == 'move':
                if self.drawing_regular_polygon and self.temp_regular_polygon_item and hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    end_x = max(0, min(int(scene_pos.x()), self.canvas_view.current_pixmap.width() - 1))
                    end_y = max(0, min(int(scene_pos.y()), self.canvas_view.current_pixmap.height() - 1))
                    polygon = self._compute_regular_polygon(self.regular_polygon_start, QPoint(end_x, end_y), sides)
                    self.temp_regular_polygon_item.setPolygon(polygon)
                    return True
            elif event_type == 'release':
                if self.drawing_regular_polygon and self.temp_regular_polygon_item and hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    end_x = max(0, min(int(scene_pos.x()), self.canvas_view.current_pixmap.width() - 1))
                    end_y = max(0, min(int(scene_pos.y()), self.canvas_view.current_pixmap.height() - 1))
                    polygon = self._compute_regular_polygon(self.regular_polygon_start, QPoint(end_x, end_y), sides)
                    w = abs(end_x - self.regular_polygon_start.x())
                    h = abs(end_y - self.regular_polygon_start.y())
                    if min(w, h) / 2.0 >= 3:
                        self._create_label_from_regular_polygon(polygon)
                    # 清理临时多边形
                    if self.temp_regular_polygon_item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(self.temp_regular_polygon_item)
                    self.temp_regular_polygon_item = None
                    self.drawing_regular_polygon = False
                    self.regular_polygon_start = None
                    return True
            return False
        except Exception as e:
            logger.error(f"正规多边形画笔绘制时发生错误: {e}")
            return False

    def _compute_regular_polygon(self, start: QPoint, end: QPoint, sides: int) -> QPolygonF:
        """根据拖拽起点/终点计算正规多边形顶点（默认顶部顶点朝上）"""
        try:
            if start is None or end is None:
                return QPolygonF()
            x1, y1 = int(start.x()), int(start.y())
            x2, y2 = int(end.x()), int(end.y())
            w = abs(x2 - x1)
            h = abs(y2 - y1)
            cx = min(x1, x2) + w / 2.0
            cy = min(y1, y2) + h / 2.0
            r = min(w, h) / 2.0
            r = max(r, 1.0)
            base_angle_deg = math.degrees(math.atan2(y2 - y1, x2 - x1))
            start_deg = (-90.0 - 180.0 / sides) + base_angle_deg
            points = []
            for i in range(sides):
                rad = math.radians(start_deg + i * (360.0 / sides))
                px = cx + r * math.cos(rad)
                py = cy + r * math.sin(rad)
                if hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                    pixmap = self.canvas_view.current_pixmap
                    px = max(0, min(int(px), pixmap.width() - 1))
                    py = max(0, min(int(py), pixmap.height() - 1))
                points.append(QPointF(px, py))
            return QPolygonF(points)
        except Exception as e:
            logger.error(f"计算正规多边形顶点时发生错误: {e}")
            return QPolygonF()

    def _create_label_from_regular_polygon(self, polygon: QPolygonF) -> None:
        """创建正规多边形标签（shape_type='polygon'）"""
        try:
            if not hasattr(self, 'canvas_view') or not hasattr(self.canvas_view, 'current_pixmap') or not self.canvas_view.current_pixmap:
                return
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
            parent = self.parent_label_list.get_selected() if self.parent_label_list else None
            if not parent:
                return
            flat_points = []
            polygon_points = []
            for p in polygon:
                x = int(p.x())
                y = int(p.y())
                flat_points.extend([x, y])
                polygon_points.append((x, y))
            child = self.parent_label_list.create_child_label(
                points=flat_points,
                image_info=image_info,
                mode='manual',
                shape_type='polygon',
                polygon_points=polygon_points
            )
            if hasattr(self.canvas_view, 'update_rects'):
                self.canvas_view.update_rects()
        except Exception as e:
            logger.error(f"从正规多边形创建标签时发生错误: {e}")

    def circle_huabi(self, event_type: str, event) -> bool:
        """
        圆形绘制方法：第一次点击确定圆心，第二次点击确定半径
        
        Args:
            event_type: 事件类型 ('press', 'move', 'release')
            event: 鼠标事件对象
            
        Returns:
            bool: 事件是否被处理
        """
        try:
            if getattr(self, 'ui_locked', False):
                return False
                
            if event_type == 'press':
                if event.button() == Qt.MouseButton.LeftButton and hasattr(self.canvas_view, 'image_item') and self.canvas_view.image_item:
                    # 必须选择父标签
                    if not self.parent_label_list or not self.parent_label_list.get_selected():
                        logger.info("圆形画笔：未选中父标签，忽略点击")
                        return False
                    
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    click_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
                    
                    # 裁剪到图像边界
                    pixmap = getattr(self.canvas_view, 'current_pixmap', None)
                    if pixmap:
                        click_point.setX(max(0, min(click_point.x(), pixmap.width() - 1)))
                        click_point.setY(max(0, min(click_point.y(), pixmap.height() - 1)))
                    
                    if not self.drawing_circle:
                        # 第一次点击：设置圆心
                        self.circle_center = click_point
                        self.drawing_circle = True
                        logger.info(f"圆形画笔：设置圆心 ({self.circle_center.x()}, {self.circle_center.y()})")
                        
                        # 创建临时圆形预览
                        self.temp_circle_item = QGraphicsEllipseItem(
                            self.circle_center.x() - 1, self.circle_center.y() - 1, 2, 2
                        )
                        parent = self.parent_label_list.get_selected()
                        color = parent.color if parent and hasattr(parent, 'color') and parent.color else QColor(255, 0, 0)
                        pen = QPen(color, 2, Qt.PenStyle.DashLine)
                        self.temp_circle_item.setPen(pen)
                        fill_color = QColor(color)
                        fill_color.setAlpha(40)
                        self.temp_circle_item.setBrush(QBrush(fill_color))
                        self.temp_circle_item.setZValue(9)
                        
                        # 确保场景存在并添加临时圆形
                        if hasattr(self.canvas_view, 'scene') and self.canvas_view.scene:
                            self.canvas_view.scene.addItem(self.temp_circle_item)
                            logger.info("圆形画笔：临时圆形预览已添加到场景")
                        else:
                            logger.warning("圆形画笔：无法添加临时圆形预览，场景不存在")
                        return True
                    else:
                        # 第二次点击：确定半径并创建圆形标签
                        radius = math.sqrt(
                            (click_point.x() - self.circle_center.x()) ** 2 + 
                            (click_point.y() - self.circle_center.y()) ** 2
                        )
                        
                        if radius >= 3:  # 最小半径阈值
                            self._create_label_from_circle(
                                self.circle_center.x(), self.circle_center.y(), radius
                            )
                            logger.info(f"圆形画笔：创建圆形标签，圆心({self.circle_center.x()}, {self.circle_center.y()})，半径{radius:.1f}")
                        
                        # 清理临时圆形
                        if self.temp_circle_item and self.temp_circle_item.scene() == self.canvas_view.scene:
                            self.canvas_view.scene.removeItem(self.temp_circle_item)
                        self.temp_circle_item = None
                        self.drawing_circle = False
                        self.circle_center = None
                        return True
                        
                elif event.button() == Qt.MouseButton.RightButton and self.drawing_circle:
                    # 右键撤销圆心
                    logger.info("圆形画笔：右键撤销圆心")
                    
                    # 清理临时圆形预览
                    if self.temp_circle_item and self.temp_circle_item.scene() == self.canvas_view.scene:
                        self.canvas_view.scene.removeItem(self.temp_circle_item)
                    
                    # 重置圆形绘制状态
                    self.temp_circle_item = None
                    self.drawing_circle = False
                    self.circle_center = None
                    return True
                        
            elif event_type == 'move':
                if self.drawing_circle and self.temp_circle_item and self.circle_center:
                    # 实时预览圆形
                    scene_pos = self.canvas_view.mapToScene(event.position().toPoint())
                    current_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
                    
                    # 裁剪到图像边界
                    pixmap = getattr(self.canvas_view, 'current_pixmap', None)
                    if pixmap:
                        current_point.setX(max(0, min(current_point.x(), pixmap.width() - 1)))
                        current_point.setY(max(0, min(current_point.y(), pixmap.height() - 1)))
                    
                    radius = math.sqrt(
                        (current_point.x() - self.circle_center.x()) ** 2 + 
                        (current_point.y() - self.circle_center.y()) ** 2
                    )
                    
                    # 更新临时圆形的大小和位置
                    diameter = radius * 2
                    self.temp_circle_item.setRect(
                        self.circle_center.x() - radius, 
                        self.circle_center.y() - radius, 
                        diameter, 
                        diameter
                    )
                    logger.debug(f"圆形画笔：更新预览圆形，半径={radius:.1f}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"圆形绘制时发生错误: {e}")
            return False

    def _create_label_from_circle(self, center_x: float, center_y: float, radius: float) -> None:
        """
        创建圆形标签
        
        Args:
            center_x: 圆心x坐标
            center_y: 圆心y坐标
            radius: 半径
        """
        try:
            if not hasattr(self, 'canvas_view') or not hasattr(self.canvas_view, 'current_pixmap') or not self.canvas_view.current_pixmap:
                return
                
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
                
            parent = self.parent_label_list.get_selected() if self.parent_label_list else None
            if not parent:
                return
            
            # 创建圆形子标签，points 格式为 [center_x, center_y, radius]
            points = [center_x, center_y, radius]
            
            child = self.parent_label_list.create_child_label(
                points=points,
                image_info=image_info,
                mode='manual',
                shape_type='circle'
            )
            
            if child:
                logger.info(f"创建了新的圆形标签: 圆心({center_x}, {center_y})，半径{radius}")
                
                # 更新画布显示
                if hasattr(self.canvas_view, 'update_rects'):
                    self.canvas_view.update_rects()
                
                # 检查自动标注开关状态并发送推理信号
                if hasattr(self.canvas_view, 'main_window') and self.canvas_view.main_window:
                    auto_annotation_enabled = getattr(self.canvas_view.main_window, 'auto_annotation_enabled', False)
                    if auto_annotation_enabled:
                        logger.info("自动标注开关已开启，发送推理信号")
                        try:
                            # 定义推理回调：停止动画并在主线程更新UI
                            def inference_callback(result):
                                try:
                                    # 停止扫描动画
                                    scan_manager = get_scan_animation_manager()
                                    if scan_manager:
                                        scan_manager.stop_animation()
                                    
                                    # 在主线程中更新UI
                                    QTimer.singleShot(0, self, lambda: self._update_ui_with_inference_result(result, child))
                                except Exception as e:
                                    logger.error(f"推理回调处理时发生错误: {e}")
                            
                            # 启动扫描动画
                            scan_manager = get_scan_animation_manager()
                            if scan_manager and hasattr(self.canvas_view, 'scene'):
                                scan_manager.start_animation(self.canvas_view.scene)
                            
                            # 启动推理线程
                            run_inference_with_specific_child(
                                get_image_info_func=self.get_image_info_func,
                                parent_label_list=self.parent_label_list,
                                child_label=child,
                                shape_type='circle',
                                callback=inference_callback,
                                main_window=self.canvas_view.main_window if hasattr(self.canvas_view, 'main_window') else None
                            )
                            
                        except Exception as e:
                            logger.error(f"启动推理时发生错误: {e}")
                            
        except Exception as e:
            logger.error(f"从圆形创建标签时发生错误: {e}")
