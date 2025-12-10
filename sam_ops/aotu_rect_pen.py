import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QImage
import numpy as np
try:
    import cv2
except Exception:
    cv2 = None

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入项目中的模块
from inference.inference_moon import get_latest_inference_result, inference_results_queue
from app_ui.labelsgl import create_child_label
from app_ui.scan_animation import get_scan_animation_manager

class AutoRectPen(QObject):
    """自动矩形框画笔，用于自动获取推理结果并创建矩形框子标签"""
    
    # 信号：当创建新标签时发出
    new_label_created = pyqtSignal(object)
    # 信号：当更新画布时发出
    canvas_updated = pyqtSignal()
    
    def __init__(self, parent_label_list=None, canvas_view=None, get_image_info_func=None):
        """
        初始化自动矩形框画笔
        
        Args:
            parent_label_list: 父标签列表对象
            canvas_view: 画布视图对象
            get_image_info_func: 获取当前图片信息的函数
        """
        super().__init__()
        self.parent_label_list = parent_label_list
        self.canvas_view = canvas_view
        self.get_image_info_func = get_image_info_func
        self.enabled = True  # 默认启用
        self.processing = False  # 是否正在处理推理结果
        self.mask_detail_level = 0.001  # 默认MASK轮廓精细级别，值越小保留的点越多
        
        # 创建定时器，定期检查推理结果
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_inference_results)
        self.check_timer.start(500)  # 每500毫秒检查一次
    
    def set_enabled(self, enabled: bool) -> None:
        """
        设置自动矩形框画笔是否启用
        
        Args:
            enabled: 是否启用
        """
        self.enabled = enabled
        if enabled:
            logger.info("自动矩形框画笔已启用")
        else:
            logger.info("自动矩形框画笔已禁用")
    
    def set_mask_detail_level(self, detail_level: float) -> None:
        """
        设置MASK轮廓精细级别
        
        Args:
            detail_level: 轮廓精细级别，值越小保留的点越多，范围建议0.0001-0.01
        """
        if 0.0001 <= detail_level <= 0.01:
            self.mask_detail_level = detail_level
            logger.info(f"MASK轮廓精细级别已设置为: {detail_level}")
        else:
            logger.warning(f"无效的精细级别值: {detail_level}，请使用0.0001-0.01范围内的值")
    
    def _check_inference_results(self) -> None:
        """检查并处理推理结果"""
        if not self.enabled or self.processing:
            return
        
        try:
            # 获取最新的推理结果
            result = get_latest_inference_result()
            if result:
                logger.debug(f"获取到推理结果，类型: {type(result)}")
                # 仅在调试模式下打印完整结果内容
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"推理结果内容: {result}")
                self._process_inference_result(result)
            else:
                # 队列为空，没有新的推理结果
                pass
        except Exception as e:
            logger.error(f"检查推理结果时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
    
    def _process_inference_result(self, result: Any) -> None:
        """
        处理推理结果，创建矩形框子标签
        
        Args:
            result: 推理结果
        """
        try:
            self.processing = True
            logger.debug("开始处理推理结果...")
            
            # 获取当前图片信息
            image_info = self.get_image_info_func() if self.get_image_info_func else None
            if not image_info:
                logger.warning("无法获取当前图片信息")
                return
            
            logger.debug(f"当前图片信息: {image_info}")
            
            # 获取选中的父标签
            selected_parent = self.parent_label_list.get_selected() if self.parent_label_list else None
            if not selected_parent:
                logger.warning("没有选中的父标签")
                return
            
            logger.debug(f"选中的父标签: {selected_parent}")
            
            # 处理不同类型的推理结果
            if isinstance(result, dict):
                # 处理字典类型的推理结果
                logger.debug("处理字典类型的推理结果")
                self._process_dict_result(result, image_info, selected_parent)
            elif isinstance(result, list):
                # 处理列表类型的推理结果
                logger.debug("处理列表类型的推理结果")
                self._process_list_result(result, image_info, selected_parent)
            else:
                logger.warning(f"未知的推理结果类型: {type(result)}")
            
            # 更新画布
            logger.debug("更新画布显示...")
            self._update_canvas()
            logger.info("推理结果处理完成")
            
        except Exception as e:
            logger.error(f"处理推理结果时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
        finally:
            self.processing = False
    
    def _process_dict_result(self, result: Dict, image_info: Any, selected_parent: Any) -> None:
        """
        处理字典类型的推理结果
        
        Args:
            result: 字典类型的推理结果
            image_info: 图片信息
            selected_parent: 选中的父标签
        """
        try:
            # 检查是否是推理启动状态
            if 'status' in result and result['status'] == 'inference_started':
                logger.debug("推理已启动，等待结果...")
                return
            
            # 检查是否有错误
            if 'error' in result:
                logger.error(f"推理结果包含错误: {result['error']}")
                try:
                    from app_ui.scan_animation import get_scan_animation_manager
                    mgr = get_scan_animation_manager(self.canvas_view)
                    if mgr:
                        mgr.stop_scan_animation()
                except Exception:
                    pass
                return
            
            # 检查是否有YOLOE的检测结果
            if 'yoloe_result' in result and result['yoloe_result']:
                yoloe_result = result['yoloe_result']
                if isinstance(yoloe_result, list):
                    polygon_mode = self.canvas_view and hasattr(self.canvas_view, 'polygon_mode') and self.canvas_view.polygon_mode
                    if polygon_mode:
                        from sam_ops.IN_Sam_rect import get_sam_manager
                        sam_mgr = get_sam_manager()
                        bbox_list = [item['bbox'] for item in yoloe_result if isinstance(item, dict) and 'bbox' in item]
                        if bbox_list:
                            try:
                                try:
                                    sam_mgr.polygon_detected.disconnect(self._on_sam_polygon_detected)
                                except Exception:
                                    pass
                                sam_mgr.polygon_detected.connect(self._on_sam_polygon_detected)
                                sam_mgr.process_yolov_bboxes_for_polygon(bbox_list, image_info, selected_parent, self.parent_label_list, self.canvas_view)
                            except Exception as e:
                                logger.error(f"调用 SAM 处理 YOLOE bbox 时出错: {e}")
                    else:
                        for item in yoloe_result:
                            if isinstance(item, dict) and 'bbox' in item:
                                self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                logger.info(f"从YOLOE结果创建标签: {[round(coord, 2) for coord in item['bbox']]}")
                elif isinstance(yoloe_result, dict) and 'bbox' in yoloe_result:
                    polygon_mode = self.canvas_view and hasattr(self.canvas_view, 'polygon_mode') and self.canvas_view.polygon_mode
                    if polygon_mode:
                        from sam_ops.IN_Sam_rect import get_sam_manager
                        sam_mgr = get_sam_manager()
                        try:
                            try:
                                sam_mgr.polygon_detected.disconnect(self._on_sam_polygon_detected)
                            except Exception:
                                pass
                            sam_mgr.polygon_detected.connect(self._on_sam_polygon_detected)
                            sam_mgr.process_yolov_bboxes_for_polygon([yoloe_result['bbox']], image_info, selected_parent, self.parent_label_list, self.canvas_view)
                        except Exception as e:
                            logger.error(f"调用 SAM 处理 YOLOE bbox 时出错: {e}")
                    else:
                        self._create_label_from_bbox(yoloe_result['bbox'], image_info, selected_parent)
                        logger.debug(f"从YOLOE结果创建标签: {[round(coord, 2) for coord in yoloe_result['bbox']]}")
            
            # 兼容 YOLOE 返回的 filtered_results（仅 bbox）：
            # - 多边形模式：用 SAM 生成多边形
            # - 矩形模式：直接用 bbox 创建子标签
            if 'filtered_results' in result and result['filtered_results']:
                polygon_mode = self.canvas_view and hasattr(self.canvas_view, 'polygon_mode') and self.canvas_view.polygon_mode
                yoloe_available = 'yoloe_result' in result and result['yoloe_result']
                bbox_items = [item for item in result.get('filtered_results', []) if isinstance(item, dict) and 'bbox' in item]
                if polygon_mode and not yoloe_available:
                    from sam_ops.IN_Sam_rect import get_sam_manager
                    sam_mgr = get_sam_manager()
                    bbox_list = [item['bbox'] for item in bbox_items]
                    if bbox_list:
                        logger.info(f"多边形模式：使用 YOLOE bbox 调用 SAM 生成多边形，bbox count={len(bbox_list)}")
                        try:
                            try:
                                sam_mgr.polygon_detected.disconnect(self._on_sam_polygon_detected)
                            except Exception:
                                pass
                            sam_mgr.polygon_detected.connect(self._on_sam_polygon_detected)
                            sam_mgr.process_yolov_bboxes_for_polygon(bbox_list, image_info, selected_parent, self.parent_label_list, self.canvas_view)
                        except Exception as e:
                            logger.error(f"调用 SAM 处理 YOLOE bbox 时出错: {e}")
                    else:
                        logger.info("多边形模式：未找到有效的 YOLOE bbox，跳过")
                else:
                    for item in bbox_items:
                        self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                        logger.info(f"从YOLOE filtered_results创建矩形子标签: {[round(coord, 2) for coord in item['bbox']]}")
            
            # 检查是否有YOLOV8的检测结果
            if 'yolov_result' in result and result['yolov_result']:
                yolov_result = result['yolov_result']
                
                # 处理filtered_results
                if 'filtered_results' in yolov_result and yolov_result['filtered_results']:
                    # If we're in polygon mode and a SAM result exists for this inference,
                    # prefer creating polygon labels from the SAM output instead of directly
                    # using YOLOV bboxes. This keeps existing behavior for rectangle mode.
                    polygon_mode = self.canvas_view and hasattr(self.canvas_view, 'polygon_mode') and self.canvas_view.polygon_mode
                    sam_available = 'sam_result' in result and result['sam_result']
                    # 判断是否有 YOLOE 的结果（表示未跳过 YOLOE）
                    yoloe_available = 'yoloe_result' in result and result['yoloe_result']

                    # 如果处于多边形模式并且未运行 YOLOE（即需要使用 YOLOV->SAM 路径），且 SAM 结果可用，则使用 SAM 的 mask
                    if polygon_mode and sam_available and not yoloe_available:
                        # Try to use the SAM result to create polygon labels.
                        sam_result = result['sam_result']
                        try:
                            # If SAM returned an error dict, fallback to YOLOV bboxes
                            if isinstance(sam_result, dict) and 'error' in sam_result:
                                logger.warning(f"SAM 推理包含错误: {sam_result['error']}")
                                # 在多边形模式下，不应回退为使用 YOLOV bbox 创建多边形子标签，直接跳过创建
                                if polygon_mode:
                                    logger.info("多边形模式且 SAM 错误：跳过使用 YOLOV bbox 创建子标签")
                                else:
                                    # 在矩形模式下仍然可以使用 bbox 创建标签
                                    for item in yolov_result.get('filtered_results', []):
                                        if isinstance(item, dict) and 'bbox' in item:
                                            self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                            logger.info(f"从YOLOV结果创建标签(因为SAM错误回退): {[round(coord, 2) for coord in item['bbox']]}")
                            else:
                                # Try to extract mask from SAM result (enhanced compatibility)
                                mask = None

                                def _extract_mask_from_result(res):
                                    try:
                                        # object-like
                                        if hasattr(res, 'masks') and hasattr(res.masks, 'data') and len(res.masks.data) > 0:
                                            fm = res.masks.data[0]
                                            if hasattr(fm, 'cpu'):
                                                return fm.cpu().numpy()
                                            if hasattr(fm, 'numpy'):
                                                try:
                                                    return fm.numpy()
                                                except Exception:
                                                    pass
                                            if isinstance(fm, np.ndarray):
                                                return fm
                                            if isinstance(fm, (list, tuple)) and len(fm) > 0:
                                                try:
                                                    return np.asarray(fm[0])
                                                except Exception:
                                                    try:
                                                        return np.asarray(fm)
                                                    except Exception:
                                                        return None
                                            try:
                                                return np.asarray(fm)
                                            except Exception:
                                                return None
                                    except Exception:
                                        return None
                                    return None

                                mask = _extract_mask_from_result(sam_result)

                                # If result is list-like, try first element
                                if mask is None and isinstance(sam_result, (list, tuple)) and len(sam_result) > 0:
                                    mask = _extract_mask_from_result(sam_result[0])

                                # dict-like fallback
                                if mask is None and isinstance(sam_result, dict):
                                    try:
                                        masks_obj = sam_result.get('masks')
                                        if isinstance(masks_obj, dict) and 'data' in masks_obj and masks_obj['data']:
                                            first_mask = masks_obj['data'][0]
                                            if hasattr(first_mask, 'cpu'):
                                                mask = first_mask.cpu().numpy()
                                            elif hasattr(first_mask, 'numpy'):
                                                try:
                                                    mask = first_mask.numpy()
                                                except Exception:
                                                    mask = np.asarray(first_mask)
                                            elif isinstance(first_mask, np.ndarray):
                                                mask = first_mask
                                            else:
                                                try:
                                                    mask = np.asarray(first_mask)
                                                except Exception:
                                                    mask = None
                                    except Exception:
                                        mask = None

                                if mask is not None:
                                    # create polygon label from mask
                                    try:
                                        self._create_label_from_mask(mask, image_info, selected_parent, self.mask_detail_level)
                                        logger.info("从SAM mask创建多边形标签（优先于YOLOV bbox）")
                                    except Exception as e:
                                        logger.warning(f"从SAM mask创建多边形标签失败: {e}")
                                        if polygon_mode:
                                            logger.info("多边形模式且从SAM mask创建失败：跳过使用 YOLOV bbox 创建子标签")
                                        else:
                                            # 在矩形模式下回退到 bbox
                                            for item in yolov_result.get('filtered_results', []):
                                                if isinstance(item, dict) and 'bbox' in item:
                                                    self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                                    logger.info(f"从YOLOV结果创建标签(回退): {[round(coord, 2) for coord in item['bbox']]}")
                                else:
                                    # No usable mask found in SAM result
                                    if polygon_mode:
                                        logger.debug("多边形模式且 SAM 无可用 mask：跳过使用 YOLOV bbox 创建子标签")
                                    else:
                                        logger.debug("SAM 结果中未找到可用的 mask，使用 YOLOV bbox 创建标签")
                                        for item in yolov_result.get('filtered_results', []):
                                            if isinstance(item, dict) and 'bbox' in item:
                                                self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                                logger.debug(f"从YOLOV结果创建标签: {[round(coord, 2) for coord in item['bbox']]}")
                        except Exception as e:
                            logger.error(f"处理 SAM 结果时发生错误: {e}")
                            # 若处于多边形模式，则不要回退为使用 YOLOV bbox 创建多边形子标签
                            if polygon_mode:
                                logger.debug("多边形模式且处理SAM失败：跳过使用 YOLOV bbox 回退创建子标签")
                            else:
                                for item in yolov_result.get('filtered_results', []):
                                    if isinstance(item, dict) and 'bbox' in item:
                                        self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                        logger.info(f"从YOLOV结果创建标签(回退): {[round(coord, 2) for coord in item['bbox']]}")
                    else:
                        # Default behavior: if in polygon mode and no YOLOE masks are available, skip creating bbox-based polygon labels
                        if polygon_mode and not yoloe_available:
                            # 在多边形模式下，使用 YOLOV 的 bbox 作为 SAM 的输入以生成多边形
                            from IN_Sam_rect import get_sam_manager
                            sam_mgr = get_sam_manager()
                            bbox_list = [item['bbox'] for item in yolov_result.get('filtered_results', []) if isinstance(item, dict) and 'bbox' in item]
                            if bbox_list:
                                logger.info(f"多边形模式且未运行 YOLOE：使用 YOLOV bbox 调用 SAM 生成多边形，bbox count={len(bbox_list)}")
                                try:
                                    # 连接 polygon_detected 信号到主线程处理器
                                    try:
                                        sam_mgr.polygon_detected.disconnect(self._on_sam_polygon_detected)
                                    except Exception:
                                        pass
                                    sam_mgr.polygon_detected.connect(self._on_sam_polygon_detected)
                                    sam_mgr.process_yolov_bboxes_for_polygon(bbox_list, image_info, selected_parent, self.parent_label_list, self.canvas_view)
                                except Exception as e:
                                    logger.error(f"调用 SAM 处理 YOLOV bbox 时出错: {e}")
                            else:
                                logger.info("多边形模式且未运行 YOLOE，但未找到有效的 YOLOV bbox，跳过")
                        else:
                            # Create labels from YOLOV bboxes (rectangle mode or YOLOE available)
                            for item in yolov_result['filtered_results']:
                                if isinstance(item, dict) and 'bbox' in item:
                                    # 处理YOLOV8的边界框
                                    self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                    logger.info(f"从YOLOV结果创建标签: {[round(coord, 2) for coord in item['bbox']]}")
                
                # 处理yolov_one_results
                polygon_mode = self.canvas_view and hasattr(self.canvas_view, 'polygon_mode') and self.canvas_view.polygon_mode
                if 'yolov_one_results' in yolov_result and yolov_result['yolov_one_results']:
                    if polygon_mode:
                        # 在多边形模式下不要直接使用 YOLOV 的 bbox 创建多边形标签，
                        # 而应等待 YOLOE 的 mask 或 YOLOV->SAM 的 mask 路径生成多边形。
                        logger.info("多边形模式：跳过直接使用 yolov_one_results 创建 bbox，等待 YOLOE/SAM 输出")
                    else:
                        for item in yolov_result['yolov_one_results']:
                            if isinstance(item, dict) and 'bbox' in item:
                                # 处理YOLOV8的边界框
                                self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                logger.info(f"从YOLOV one结果创建标签: {[round(coord, 2) for coord in item['bbox']]}")
                
                # 处理yolov_two_results
                if 'yolov_two_results' in yolov_result and yolov_result['yolov_two_results']:
                    if polygon_mode:
                        logger.info("多边形模式：跳过直接使用 yolov_two_results 创建 bbox，等待 YOLOE/SAM 输出")
                    else:
                        for item in yolov_result['yolov_two_results']:
                            if isinstance(item, dict) and 'bbox' in item:
                                # 处理YOLOV8的边界框
                                self._create_label_from_bbox(item['bbox'], image_info, selected_parent)
                                logger.info(f"从YOLOV two结果创建标签: {[round(coord, 2) for coord in item['bbox']]}")
            
            # 检查是否有SAM的分割结果 - 优先从 mask 生成多边形，若无 mask 再回退到 bbox
            if 'sam_result' in result and result['sam_result']:
                sam_result = result['sam_result']

                # 检查是否有错误
                if isinstance(sam_result, dict) and 'error' in sam_result:
                    logger.warning(f"SAM推理结果包含错误: {sam_result['error']}")

                else:
                    # 尝试从 sam_result 中提取 mask（支持对象式和 dict-mock 两种格式）
                    mask = None
                    try:
                        # object-like (ultralytics result)
                        if hasattr(sam_result, 'masks') and hasattr(sam_result.masks, 'data') and len(sam_result.masks.data) > 0:
                            first_mask = sam_result.masks.data[0]
                            try:
                                if hasattr(first_mask, 'cpu'):
                                    mask = first_mask.cpu().numpy()
                                elif hasattr(first_mask, 'numpy'):
                                    mask = first_mask.numpy()
                                elif isinstance(first_mask, np.ndarray):
                                    mask = first_mask
                                else:
                                    mask = np.asarray(first_mask)
                            except Exception:
                                try:
                                    mask = np.asarray(first_mask)
                                except Exception:
                                    mask = None

                        # dict-like mock from inference_moon
                        if mask is None and isinstance(sam_result, dict) and 'masks' in sam_result:
                            masks_obj = sam_result['masks']
                            if isinstance(masks_obj, dict) and 'data' in masks_obj and masks_obj['data']:
                                first_mask = masks_obj['data'][0]
                                try:
                                    if hasattr(first_mask, 'cpu'):
                                        mask = first_mask.cpu().numpy()
                                    elif isinstance(first_mask, np.ndarray):
                                        mask = first_mask
                                    else:
                                        mask = np.asarray(first_mask)
                                except Exception:
                                    try:
                                        mask = np.asarray(first_mask)
                                    except Exception:
                                        mask = None

                    except Exception as e:
                        logger.warning(f"尝试解析 SAM 结果时出错: {e}")
                        mask = None

                    # 如果找到了 mask，则使用 mask->多边形路径创建标签
                    if mask is not None:
                        try:
                            self._create_label_from_mask(mask, image_info, selected_parent, self.mask_detail_level)
                            logger.debug("从SAM mask创建多边形标签（通用sam_result处理器）")
                        except Exception as e:
                            logger.error(f"从SAM mask创建多边形标签失败，回退到bbox: {e}")
                            # 如果无法从 mask 创建，则继续尝试 bbox
                            if isinstance(sam_result, dict) and 'bbox' in sam_result:
                                self._create_label_from_bbox(sam_result['bbox'], image_info, selected_parent)
                                logger.debug(f"从SAM结果创建标签(bbox回退): {sam_result['bbox']}")

                    else:
                        # 若没有 mask，则尝试使用 bbox（若存在）
                        if isinstance(sam_result, dict) and 'bbox' in sam_result:
                            self._create_label_from_bbox(sam_result['bbox'], image_info, selected_parent)
                            logger.debug(f"从SAM结果创建标签: {sam_result['bbox']}")
                
        except Exception as e:
            logger.error(f"处理字典类型推理结果时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")

    def _on_sam_polygon_detected(self, payload):
        """Slot: 在主线程创建多边形子标签（由 IN_Sam_rect 发出的信号触发）
        payload: dict with keys polygon_points, image_info, selected_parent, parent_label_list, canvas_view
        """
        try:
            polygon_points = payload.get('polygon_points')
            image_info = payload.get('image_info')
            selected_parent = payload.get('selected_parent')
            parent_label_list = payload.get('parent_label_list')
            # Use existing method to create child from polygon
            if polygon_points and parent_label_list and selected_parent:
                # Reuse create_child_labels_from_polygon logic by temporarily building an AutoPenManager-like helper
                # Here we will call parent_label_list.create_child_label directly
                original_selected = parent_label_list.get_selected()
                try:
                    for idx, label in enumerate(parent_label_list.labels):
                        label.selected = False
                        parent_label_list.list_widget.setIndicator(idx, False)
                    for idx, label in enumerate(parent_label_list.labels):
                        if label == selected_parent:
                            label.selected = True
                            parent_label_list.list_widget.setIndicator(idx, True)
                            break

                    child = parent_label_list.create_child_label(
                        points=None,
                        image_info=image_info,
                        mode='auto',
                        shape_type='polygon',
                        polygon_points=polygon_points
                    )
                    if child:
                        logger.info(f"从 SAM 输出创建多边形子标签: {child}")
                        self.new_label_created.emit(child)
                    else:
                        logger.warning("从 SAM 输出创建多边形子标签失败")
                finally:
                    if original_selected:
                        for idx, label in enumerate(parent_label_list.labels):
                            label.selected = False
                            parent_label_list.list_widget.setIndicator(idx, False)
                        for idx, label in enumerate(parent_label_list.labels):
                            if label == original_selected:
                                label.selected = True
                                parent_label_list.list_widget.setIndicator(idx, True)
                                break

        except Exception as e:
            logger.error(f"在主线程处理 SAM polygon payload 时发生错误: {e}")
        finally:
            # 在主线程停止扫描动画（防止遗漏）
            try:
                def _stop_animation():
                    try:
                        mgr = get_scan_animation_manager(self.canvas_view)
                        if mgr:
                            mgr.stop_scan_animation()
                    except Exception as e:
                        logger.error(f"AutoRectPen停止扫描动画失败: {e}")
                QTimer.singleShot(0, _stop_animation)
            except Exception as e:
                logger.error(f"AutoRectPen调度停止动画失败: {e}")
    
    def _process_list_result(self, result: List, image_info: Any, selected_parent: Any) -> None:
        """
        处理列表类型的推理结果
        
        Args:
            result: 列表类型的推理结果
            image_info: 图片信息
            selected_parent: 选中的父标签
        """
        try:
            for item in result:
                if isinstance(item, dict):
                    # 如果列表项是字典，递归处理
                    self._process_dict_result(item, image_info, selected_parent)
                elif isinstance(item, list) and len(item) >= 4:
                    # 如果列表项是列表且长度>=4，假设是边界框坐标 [x1, y1, x2, y2]
                    self._create_label_from_bbox(item, image_info, selected_parent)
                
        except Exception as e:
            logger.error(f"处理列表类型推理结果时发生错误: {e}")
    
    def _create_label_from_bbox(self, bbox: List[float], image_info: Any, selected_parent: Any) -> None:
        """
        根据边界框创建子标签
        
        Args:
            bbox: 边界框坐标 [x1, y1, x2, y2]
            image_info: 图片信息
            selected_parent: 选中的父标签
        """
        try:
            if not isinstance(bbox, list) or len(bbox) < 4:
                logger.warning(f"无效的边界框格式: {bbox}")
                return
            
            # 提取边界框坐标
            x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
            
            # 确保坐标有效
            if x1 >= x2 or y1 >= y2:
                logger.warning(f"无效的边界框坐标: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
                return
            
            # 在多边形模式下，禁止使用bbox创建标签
            if self.canvas_view and hasattr(self.canvas_view, 'polygon_mode') and self.canvas_view.polygon_mode:
                logger.info("多边形模式：跳过使用边界框创建子标签")
                return

            try:
                from auto_label_filter import is_duplicate_rect
                if selected_parent and hasattr(selected_parent, 'children_by_image') and image_info in selected_parent.children_by_image:
                    if is_duplicate_rect(selected_parent, image_info, bbox):
                        logger.info("检测到重复的矩形子标签，跳过创建")
                        return
            except Exception:
                pass

            # 仅矩形模式创建矩形标签
            shape_type = 'rectangle'
            logger.info("检测到矩形模式，将创建矩形标签")
            
            # 计算矩形的四个顶点坐标
            points = [x1, y1, x2, y1, x2, y2, x1, y2]
            
            logger.info(f"创建子标签，边界框坐标: x1={round(x1, 2)}, y1={round(y1, 2)}, x2={round(x2, 2)}, y2={round(y2, 2)}")
            logger.info(f"顶点坐标: {[round(coord, 2) for coord in points]}")
            
            # 确保有选中的父标签
            if not selected_parent:
                logger.warning("没有选中的父标签，无法创建子标签")
                return
            
            # 临时保存当前选中的父标签
            original_selected = self.parent_label_list.get_selected()
            
            try:
                # 临时设置选中的父标签为我们指定的父标签
                # 首先取消所有标签的选中状态
                for idx, label in enumerate(self.parent_label_list.labels):
                    label.selected = False
                    self.parent_label_list.list_widget.setIndicator(idx, False)
                
                # 设置我们指定的父标签为选中状态
                for idx, label in enumerate(self.parent_label_list.labels):
                    if label == selected_parent:
                        label.selected = True
                        self.parent_label_list.list_widget.setIndicator(idx, True)
                        break

                # 创建子标签，根据当前模式选择形状类型（在设置选中父标签后执行）
                # 如果是多边形模式，传入 polygon_points 参数以便 ChildLabel 保存为多边形
                if shape_type == 'polygon':
                    # 构造 polygon_points：以四个角点为多边形的顶点（保持与矩形一致的顺序）
                    polygon_points = [
                        (x1, y1),
                        (x2, y1),
                        (x2, y2),
                        (x1, y2)
                    ]
                    child = self.parent_label_list.create_child_label(
                        points=None,  # 不传入 points（矩形顶点），使用 polygon_points
                        image_info=image_info,
                        mode='auto',
                        shape_type=shape_type,
                        polygon_points=polygon_points
                    )
                else:
                    child = self.parent_label_list.create_child_label(
                        points=points,
                        image_info=image_info,
                        mode='auto',  # 标记为自动生成的标签
                        shape_type=shape_type  # 使用检测到的形状类型
                    )
                
                if child:
                    logger.info(f"成功创建了新的自动标签: {child}")
                    self.new_label_created.emit(child)
                else:
                    logger.warning("创建子标签失败")
            
            finally:
                # 恢复原始选中的父标签
                if original_selected:
                    # 首先取消所有标签的选中状态
                    for idx, label in enumerate(self.parent_label_list.labels):
                        label.selected = False
                        self.parent_label_list.list_widget.setIndicator(idx, False)
                    
                    # 设置原始选中的父标签为选中状态
                    for idx, label in enumerate(self.parent_label_list.labels):
                        if label == original_selected:
                            label.selected = True
                            self.parent_label_list.list_widget.setIndicator(idx, True)
                            break
            
        finally:
            try:
                from app_ui.scan_animation import get_scan_animation_manager
                mgr = get_scan_animation_manager(self.canvas_view)
                if mgr:
                    mgr.stop_scan_animation()
            except Exception:
                pass


    def _create_label_from_mask(self, mask: np.ndarray, image_info: Any, selected_parent: Any, detail_level: float = 0.001) -> None:
        """
        根据分割 mask 提取轮廓并创建多边形子标签

        Args:
            mask: numpy array 的 mask（H,W），值为 float/0-1 或 0/255
            image_info: 图片信息
            selected_parent: 选中的父标签
            detail_level: 轮廓精细级别，值越小保留的点越多，默认0.001
        """
        try:
            if mask is None:
                logger.warning("传入的mask为None，无法创建多边形")
                return

            if cv2 is None:
                logger.warning("cv2 未安装，无法从 mask 提取轮廓，回退到 bbox 创建")
                return

            # 将 mask 转为 uint8 二值图
            mask_arr = np.asarray(mask)
            # 有些 mask 为 float32 0/1 或概率，使用阈值0.5
            if mask_arr.dtype != np.uint8:
                bin_mask = (mask_arr > 0.5).astype(np.uint8) * 255
            else:
                # 假设已是0/255
                bin_mask = (mask_arr > 0).astype(np.uint8) * 255

            # 找到外部轮廓：使用 CHAIN_APPROX_NONE 保留所有轮廓点，不进行任何压缩
            contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not contours:
                logger.warning("未在 mask 中找到任何轮廓")
                return

            # 选择最大的轮廓（按面积）
            max_cnt = max(contours, key=lambda c: cv2.contourArea(c))
            area = cv2.contourArea(max_cnt)
            if area <= 0:
                logger.warning("找到的最大轮廓面积为0，跳过")
                return

            # 多边形近似：使用更小的 epsilon 值以保留更多细节点
            # detail_level 参数控制精细程度，值越小保留的点越多
            peri = cv2.arcLength(max_cnt, True)
            # 设置最小 epsilon 值，确保即使对于小轮廓也能保留足够细节
            min_epsilon = 0.3  # 最小 epsilon 值
            epsilon = max(min_epsilon, detail_level * peri)
            
            # 对于较大的轮廓，使用更精细的近似
            if area > 10000:  # 对于面积较大的轮廓，使用更小的 detail_level
                epsilon = max(min_epsilon, detail_level * 0.5 * peri)
            
            approx = cv2.approxPolyDP(max_cnt, epsilon, True)
            
            # 如果近似后的点数太少，尝试使用更小的 epsilon
            if len(approx) < 10:
                epsilon = max(0.1, detail_level * 0.3 * peri)
                approx = cv2.approxPolyDP(max_cnt, epsilon, True)
                logger.debug(f"轮廓点数太少，使用更小的 epsilon 重新近似，点数: {len(approx)}")

            # 构造 polygon_points 列表 (x,y) 元组（在 mask 空间）
            polygon_points_mask = []
            pts = approx.reshape(-1, 2) if approx is not None else []
            for pt in pts:
                x_mask, y_mask = float(pt[0]), float(pt[1])
                polygon_points_mask.append((x_mask, y_mask))

            if not polygon_points_mask:
                logger.warning("轮廓近似后无顶点，跳过创建多边形标签")
                return

            # 将 mask 空间坐标映射到图像/画布坐标
            mask_h, mask_w = bin_mask.shape[:2]

            # 首选使用绘图画布上的当前 pixmap 大小（已加载并适配显示的图像尺寸）
            img_w = None
            img_h = None
            if self.canvas_view and hasattr(self.canvas_view, 'current_pixmap') and self.canvas_view.current_pixmap:
                try:
                    img_w = float(self.canvas_view.current_pixmap.width())
                    img_h = float(self.canvas_view.current_pixmap.height())
                except Exception:
                    img_w = None
                    img_h = None

            # 回退：尝试使用 image_info（文件路径）读取原始图片尺寸
            if img_w is None or img_h is None:
                try:
                    qimg = QImage(image_info)
                    if not qimg.isNull():
                        img_w = float(qimg.width())
                        img_h = float(qimg.height())
                except Exception:
                    img_w = None
                    img_h = None

            # 如果仍然无法获取图像尺寸，则使用 mask 尺寸（等比映射为空操作）
            if img_w is None or img_h is None:
                img_w = float(mask_w)
                img_h = float(mask_h)

            # 进行缩放映射
            sx = img_w / float(mask_w) if mask_w != 0 else 1.0
            sy = img_h / float(mask_h) if mask_h != 0 else 1.0

            polygon_points = []
            for x_mask, y_mask in polygon_points_mask:
                x_img = x_mask * sx
                y_img = y_mask * sy
                polygon_points.append((x_img, y_img))

            if not polygon_points:
                logger.warning("轮廓近似后无顶点，跳过创建多边形标签")
                return

            # 确保有选中的父标签
            if not selected_parent:
                logger.warning("没有选中的父标签，无法创建多边形子标签")
                return

            # 临时设置选中父标签并创建子标签（与_bbox方法相同的选择逻辑）
            original_selected = self.parent_label_list.get_selected()
            try:
                for idx, label in enumerate(self.parent_label_list.labels):
                    label.selected = False
                    self.parent_label_list.list_widget.setIndicator(idx, False)
                for idx, label in enumerate(self.parent_label_list.labels):
                    if label == selected_parent:
                        label.selected = True
                        self.parent_label_list.list_widget.setIndicator(idx, True)
                        break

                child = self.parent_label_list.create_child_label(
                    points=None,
                    image_info=image_info,
                    mode='auto',
                    shape_type='polygon',
                    polygon_points=polygon_points
                )

                if child:
                    logger.debug(f"成功创建了新的自动多边形标签，点数: {len(polygon_points)}")
                    self.new_label_created.emit(child)
                else:
                    logger.warning("创建多边形子标签失败")
            finally:
                # 恢复原始选中的父标签
                if original_selected:
                    for idx, label in enumerate(self.parent_label_list.labels):
                        label.selected = False
                        self.parent_label_list.list_widget.setIndicator(idx, False)
                    for idx, label in enumerate(self.parent_label_list.labels):
                        if label == original_selected:
                            label.selected = True
                            self.parent_label_list.list_widget.setIndicator(idx, True)
                            break

        except Exception as e:
            logger.error(f"根据 mask 创建多边形子标签时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
        finally:
            # 在主线程停止扫描动画（防止遗漏）
            try:
                def _stop_animation():
                    try:
                        mgr = get_scan_animation_manager(self.canvas_view)
                        if mgr:
                            mgr.stop_scan_animation()
                    except Exception as e:
                        logger.error(f"AutoRectPen停止扫描动画失败: {e}")
                QTimer.singleShot(0, _stop_animation)
            except Exception as e:
                logger.error(f"AutoRectPen调度停止动画失败: {e}")
    
    def _update_canvas(self) -> None:
        """更新画布显示"""
        try:
            if self.canvas_view and hasattr(self.canvas_view, 'update_rects'):
                logger.debug("调用canvas_view.update_rects()更新画布...")
                self.canvas_view.update_rects()
                self.canvas_updated.emit()
                logger.debug("画布更新成功")
            else:
                logger.warning("无法更新画布：canvas_view为空或没有update_rects方法")
        except Exception as e:
            logger.error(f"更新画布时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
    
    def stop(self) -> None:
        """停止自动矩形框画笔"""
        self.check_timer.stop()
        logger.info("自动矩形框画笔已停止")


# 示例使用方式
if __name__ == "__main__":
    # 这里仅作为示例，实际使用时需要传入正确的参数
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 假设有以下对象（实际使用时需要从项目中获取）
    # parent_label_list = ParentLabelList()
    # canvas_view = GraphicsCanvas()
    # get_image_info_func = some_function_to_get_image_info
    
    # 创建自动矩形框画笔
    # auto_rect_pen = AutoRectPen(
    #     parent_label_list=parent_label_list,
    #     canvas_view=canvas_view,
    #     get_image_info_func=get_image_info_func
    # )
    
    print("自动矩形框画笔示例")
    print("实际使用时，请将此脚本集成到主应用程序中，并传入正确的参数")
    
    sys.exit(app.exec())
