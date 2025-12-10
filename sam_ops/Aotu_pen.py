import os
import logging
import math
from typing import List, Dict, Tuple, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal, QPointF, QThread, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication
import numpy as np
import cv2
from algorithms.minimum_bounding_rectangle import MinimumBoundingBox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoPenManager(QObject):
    """MASK模式自动绘制管理器，负责MASK子标签的创建与绘制"""
    
    # 信号定义
    drawing_started = pyqtSignal(str)  # 开始绘制信号
    drawing_progress = pyqtSignal(str, int, int)  # 绘制进度信号
    drawing_completed = pyqtSignal(list)  # 绘制完成信号
    drawing_error = pyqtSignal(str)  # 绘制错误信号
    
    def __init__(self, parent_label_list=None, canvas=None):
        """
        初始化MASK模式自动绘制管理器
        
        Args:
            parent_label_list: 父标签列表
            canvas: 画布对象
        """
        super().__init__()
        
        self.parent_label_list = parent_label_list
        self.canvas = canvas
        
        # 使用硬编码的默认配置值
        self.config = {
            'min_polygon_points': 3,
            'min_bbox_area': 0,
            'confidence_threshold': 0.3,
            'polygon_simplify_epsilon': 2.0,
        }
        
        logger.info("MASK模式自动绘制管理器初始化完成")
    
    def process_mask_sam_results(self, mask_sam_results, image_info, image_width, image_height, confidence=None):
        """
        处理MASK模式的SAM推理结果，提取掩码数据，计算多边形轮廓，然后创建子标签
        
        Args:
            mask_sam_results: MASK模式SAM推理结果
            image_info: 图像信息
            image_width: 图像宽度
            image_height: 图像高度
            confidence: 置信度
            
        Returns:
            创建的标签对象列表
        """
        try:
            if not mask_sam_results:
                logger.warning("MASK模式SAM推理结果为空")
                return []
            
            created_labels = []
            # 用于存储已创建的标签信息，用于去重
            created_label_info = set()
            created_count = 0
            
            # 处理MASK模式SAM结果
            for result in mask_sam_results:
                try:
                    # 检查结果中是否有掩码数据
                    if hasattr(result, 'masks') and result.masks is not None:
                        masks = result.masks.data  # 获取掩码数据
                        
                        for i, mask in enumerate(masks):
                            # 将掩码转换为numpy数组
                            mask_np = mask.cpu().numpy() if hasattr(mask, 'cpu') else np.array(mask)
                            
                            polygon_points = self.extract_polygon_from_mask(mask_np, image_width, image_height)
                            
                            if not polygon_points or len(polygon_points) < self.config['min_polygon_points']:
                                logger.debug(f"MASK模式掩码 {i} 提取的多边形点数不足，跳过")
                                continue
                            
                            # 计算多边形的几何中心（用于去重检查）
                            center_x = sum(p[0] for p in polygon_points) / len(polygon_points)
                            center_y = sum(p[1] for p in polygon_points) / len(polygon_points)
                            
                            # 计算多边形面积（使用鞋带公式）
                            area = 0.0
                            n = len(polygon_points)
                            for i in range(n):
                                j = (i + 1) % n
                                area += polygon_points[i][0] * polygon_points[j][1]
                                area -= polygon_points[j][0] * polygon_points[i][1]
                            area = abs(area) / 2.0
                            
                            # 检查面积是否满足要求
                            if area < self.config['min_bbox_area']:
                                logger.debug(f"MASK模式多边形面积过小，跳过: {area}")
                                continue
                            
                            # 归一化中心点坐标用于去重检查
                            norm_center_x = center_x / image_width
                            norm_center_y = center_y / image_height
                            
                            # 四舍五入到3位小数，用于比较
                            center_x_rounded = round(norm_center_x, 3)
                            center_y_rounded = round(norm_center_y, 3)
                            area_rounded = round(area, 0)
                            
                            # 检查是否已经创建了相似位置和大小的多边形标签
                            label_key = (center_x_rounded, center_y_rounded, area_rounded)
                            if label_key in created_label_info:
                                logger.debug(f"MASK模式发现重复多边形标签，跳过: 中心({center_x_rounded}, {center_y_rounded}), 面积{area_rounded}")
                                continue
                            
                            # 提取置信度
                            mask_confidence = confidence
                            if mask_confidence is None:
                                mask_confidence = self._extract_mask_confidence(result, mask, i)
                            
                            # 创建多边形子标签
                            child = self.create_child_labels_from_polygon(
                                polygon_points, image_info, image_width, image_height, mask_confidence, mask_data=mask_np
                            )
                            
                            if child:
                                created_labels.append(child)
                                created_label_info.add(label_key)
                                logger.debug(f"从MASK模式掩码 {i} 成功创建多边形标签")
                                created_count += 1
                                if created_count % 8 == 0:
                                    try:
                                        QApplication.processEvents()
                                    except Exception:
                                        pass
                            
                except Exception as e:
                    logger.error(f"处理MASK模式SAM结果中的掩码时发生错误: {str(e)}")
                    continue
            
            # 更新画布
            if created_labels and self.canvas:
                try:
                    QTimer.singleShot(0, lambda: self.canvas.update_rects())
                except Exception:
                    self.canvas.update_rects()
                
                # 刷新缩略图
                if hasattr(self.canvas, 'main_window') and hasattr(self.canvas.main_window, '_refresh_thumbnail_for_image'):
                    try:
                        QTimer.singleShot(0, lambda: self.canvas.main_window._refresh_thumbnail_for_image(image_info))
                    except Exception:
                        self.canvas.main_window._refresh_thumbnail_for_image(image_info)

                # 确认标签绘制成功后清空临时裁剪文件夹
                try:
                    temp_dir = r"c:\moonlightv2.104重制版\temp_crops"
                    if os.path.isdir(temp_dir):
                        for name in os.listdir(temp_dir):
                            fp = os.path.join(temp_dir, name)
                            try:
                                if os.path.isfile(fp) or os.path.islink(fp):
                                    os.remove(fp)
                                elif os.path.isdir(fp):
                                    # 尽量清空子目录后移除子目录
                                    for sub in os.listdir(fp):
                                        sp = os.path.join(fp, sub)
                                        if os.path.isfile(sp) or os.path.islink(sp):
                                            os.remove(sp)
                                    try:
                                        os.rmdir(fp)
                                    except Exception:
                                        pass
                            except Exception:
                                # 单个文件/子目录清理失败不影响整体
                                pass
                        logger.info("已清空临时裁剪目录 temp_crops")
                except Exception:
                    # 静默失败，避免影响正常流程
                    pass
            
            logger.info(f"从MASK模式SAM推理结果成功创建了 {len(created_labels)} 个多边形标签")
            return created_labels
            
        except Exception as e:
            logger.error(f"处理MASK模式SAM推理结果时发生错误: {str(e)}")
            return []
    
    def extract_polygon_from_mask(self, mask, image_width, image_height):
        """
        从掩码数据中提取多边形轮廓
        
        Args:
            mask: 掩码数据（numpy数组）
            image_width: 图像宽度
            image_height: 图像高度
            
        Returns:
            多边形点列表，格式为[(x1, y1), (x2, y2), ...]
        """
        try:
            logger.debug(f"开始从掩码提取多边形轮廓，掩码形状: {mask.shape}, 掩码类型: {mask.dtype}")
            
            # 确保掩码是二值图像
            if mask.dtype != np.uint8:
                logger.debug(f"将掩码从 {mask.dtype} 转换为 uint8")
                mask = (mask > 0.5).astype(np.uint8) * 255
            
            # 使用OpenCV查找轮廓 - 使用CHAIN_APPROX_NONE获取所有轮廓点
            logger.debug("使用OpenCV查找轮廓")
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            
            logger.debug(f"找到 {len(contours)} 个轮廓")
            
            if not contours:
                logger.warning("未找到任何轮廓")
                return []
            
            # 找到最大的轮廓
            largest_contour = max(contours, key=cv2.contourArea)
            logger.debug(f"最大轮廓面积: {cv2.contourArea(largest_contour)}")
            
            # 获取所有轮廓点（不进行简化）
            polygon_points = []
            for point in largest_contour:
                x, y = point[0]
                # 确保坐标在图像范围内
                x = max(0, min(image_width - 1, int(x)))
                y = max(0, min(image_height - 1, int(y)))
                polygon_points.append((x, y))
            
            logger.debug(f"提取的多边形点数: {len(polygon_points)}")
            
            # 如果点数太多，进行适度的简化以减少计算量
            if len(polygon_points) > 100:
                logger.warning(f"多边形点数过多 ({len(polygon_points)} > 100)，进行进一步简化")
                
                # 使用更小的epsilon值进行简化，保留更多细节
                epsilon = 0.002 * cv2.arcLength(largest_contour, True)
                logger.debug(f"使用 epsilon={epsilon} 简化轮廓")
                approx_polygon = cv2.approxPolyDP(largest_contour, epsilon, True)
                
                # 重新提取简化后的点
                polygon_points = []
                for point in approx_polygon:
                    x, y = point[0]
                    # 确保坐标在图像范围内
                    x = max(0, min(image_width - 1, int(x)))
                    y = max(0, min(image_height - 1, int(y)))
                    polygon_points.append((x, y))
                
                logger.debug(f"简化后的多边形点数: {len(polygon_points)}")
            
            logger.debug("成功提取多边形轮廓")
            return polygon_points
            
        except Exception as e:
            logger.error(f"从掩码提取多边形时发生错误: {str(e)}")
            return []
    
    def create_child_labels_from_polygon(self, polygon_points, image_info, image_width, image_height, confidence=None, mask_data=None):
        """
        根据多边形点集创建多边形子标签
        
        Args:
            polygon_points: 多边形点集，格式为[(x1, y1), (x2, y2), ...]
            image_info: 图像信息
            image_width: 图像宽度
            image_height: 图像高度
            confidence: 置信度
            mask_data: 原始MASK数据，用于polygon_mask类型标签
            
        Returns:
            创建的标签对象，如果创建失败则返回None
        """
        try:
            if not polygon_points or len(polygon_points) < self.config['min_polygon_points']:
                logger.warning(f"多边形点数不足，跳过创建多边形标签")
                return None
                
            # 计算边界框（用于标签的基本信息）
            x_coords = [p[0] for p in polygon_points]
            y_coords = [p[1] for p in polygon_points]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # 计算边界框信息
            bbox_info = {
                'center': ((min_x + max_x) / 2, (min_y + max_y) / 2),
                'width': max_x - min_x,
                'height': max_y - min_y
            }
            
            # 检查面积是否满足要求
            area = bbox_info['width'] * bbox_info['height']
            if area < self.config['min_bbox_area']:
                logger.debug(f"多边形面积过小，跳过: {area}")
                return None
            
            # 归一化坐标
            x_center = bbox_info['center'][0] / image_width
            y_center = bbox_info['center'][1] / image_height
            norm_w = bbox_info['width'] / image_width
            norm_h = bbox_info['height'] / image_height
            
            # 确保坐标在有效范围内
            x_center = max(0.0, min(1.0, x_center))
            y_center = max(0.0, min(1.0, y_center))
            norm_w = max(0.0, min(1.0, norm_w))
            norm_h = max(0.0, min(1.0, norm_h))
            
            try:
                from auto_label_filter import is_duplicate_polygon
                parent = self.parent_label_list.get_selected() if self.parent_label_list else None
                if parent and hasattr(parent, 'children_by_image') and image_info in parent.children_by_image:
                    if is_duplicate_polygon(parent, image_info, polygon_points, image_width, image_height):
                        return None
            except Exception:
                pass

            # 创建标签
            if self.parent_label_list:
                # 处理置信度
                if confidence is not None:
                    try:
                        confidence = float(confidence)
                        confidence = max(0.0, min(1.0, confidence))
                    except Exception:
                        confidence = None
                
                # 创建子标签 - 使用实际像素坐标而不是归一化坐标
                child = self.parent_label_list.create_child_label(
                    x_center=x_center, y_center=y_center, width=norm_w, height=norm_h, 
                    image_info=image_info,
                    shape_type='polygon_mask',  # 使用polygon_mask类型以支持原始MASK数据
                    polygon_points=polygon_points,  # 使用原始像素坐标
                    mask_data=mask_data  # 传递原始MASK数据
                )
                
                if child:
                    logger.debug(f"成功创建多边形子标签: ({x_center:.3f}, {y_center:.3f}, {norm_w:.3f}, {norm_h:.3f}), 点数: {len(polygon_points)}, conf={confidence if confidence is not None else 'None'}")
                    
                    # 保存多边形信息 - 使用原始像素坐标
                    child.polygon_points = polygon_points
                    child.is_polygon = True  # 标记为多边形标签
                    
                    return child
                else:
                    # 如果返回的是已存在的标签（不是None），说明是重复标签，直接返回
                    if child is not None:
                        # 更新多边形信息，确保即使是重复标签也有正确的信息
                        child.polygon_points = polygon_points
                        child.is_polygon = True
                        return child
            
            return None
            
        except Exception as e:
            logger.error(f"创建多边形子标签时发生错误: {str(e)}")
            return None

    
    def _extract_mask_confidence(self, result, mask, mask_index):
        """
        从MASK模式SAM结果中提取掩码的置信度
        
        Args:
            result: SAM推理结果
            mask: 掩码数据
            mask_index: 掩码索引
            
        Returns:
            置信度值
        """
        try:
            # 尝试从结果中获取置信度信息
            if hasattr(result, 'scores') and result.scores is not None:
                if len(result.scores) > mask_index:
                    return float(result.scores[mask_index])
            
            # 如果没有明确的置信度信息，返回默认值
            return 0.5
            
        except Exception as e:
            logger.warning(f"提取掩码置信度时发生错误: {str(e)}")
            return 0.5
    
    def process_obb_sam_results(self, obb_sam_results, image_info, image_width, image_height, confidence=None):
        """
        处理OBB模式的SAM推理结果，提取掩码数据，计算最小外接矩形，然后创建子标签
        
        Args:
            obb_sam_results: OBB模式SAM推理结果
            image_info: 图像信息
            image_width: 图像宽度
            image_height: 图像高度
            confidence: 置信度
            
        Returns:
            创建的标签对象列表
        """
        try:
            logger.info(f"开始处理OBB模式SAM推理结果，结果数量: {len(obb_sam_results) if obb_sam_results else 0}")
            
            if not obb_sam_results:
                logger.warning("OBB模式SAM推理结果为空")
                return []
            
            created_labels = []
            # 用于存储已创建的标签信息，用于去重
            created_label_info = set()
            
            # 处理OBB模式SAM结果
            for result_idx, result in enumerate(obb_sam_results):
                try:
                    logger.info(f"处理OBB模式结果 {result_idx}")
                    
                    # 检查结果中是否有掩码数据
                    if hasattr(result, 'masks') and result.masks is not None:
                        masks = result.masks.data  # 获取掩码数据
                        logger.info(f"找到 {len(masks) if masks is not None else 0} 个掩码")
                        
                        for i, mask in enumerate(masks):
                            logger.info(f"处理掩码 {i}")
                            
                            # 将掩码转换为numpy数组
                            mask_np = mask.cpu().numpy() if hasattr(mask, 'cpu') else np.array(mask)
                            logger.info(f"掩码形状: {mask_np.shape}, 掩码类型: {mask_np.dtype}")
                            
                            # 提取掩码的轮廓
                            polygon_points = self.extract_polygon_from_mask(mask_np, image_width, image_height)
                            logger.info(f"提取的多边形点数: {len(polygon_points) if polygon_points else 0}")
                            
                            if not polygon_points or len(polygon_points) < self.config['min_polygon_points']:
                                logger.warning(f"OBB模式掩码 {i} 提取的多边形点数不足（需要至少 {self.config['min_polygon_points']} 个点），跳过")
                                continue
                            
                            use_axis = False
                            try:
                                mw = getattr(self.canvas, 'main_window', None)
                                use_axis = bool(getattr(mw, 'obb_rect_axis_aligned', False)) if mw else False
                            except Exception:
                                use_axis = False
                            if use_axis:
                                xs = [p[0] for p in polygon_points]
                                ys = [p[1] for p in polygon_points]
                                min_x, max_x = min(xs), max(xs)
                                min_y, max_y = min(ys), max(ys)
                                corners = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
                                area = (max_x - min_x) * (max_y - min_y)
                                obb_result = {"corners": corners, "center": ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0), "area": area}
                            else:
                                min_bounding_box = MinimumBoundingBox()
                                obb_result = min_bounding_box.find_minimum_bounding_rectangle(polygon_points)
                            
                            if not obb_result:
                                logger.warning(f"OBB模式掩码 {i} 无法计算最小外接矩形，跳过")
                                continue
                            
                            logger.info(f"最小外接矩形计算成功，面积: {obb_result.get('area', 'N/A')}")
                            
                            # 检查面积是否满足要求
                            area = obb_result['area']
                            if area < self.config['min_bbox_area']:
                                try:
                                    ca = cv2.contourArea(np.array(polygon_points, dtype=np.int32))
                                except Exception:
                                    ca = 0
                                if ca < self.config['min_bbox_area']:
                                    logger.warning(f"OBB模式多边形面积过小（需要至少 {self.config['min_bbox_area']}），跳过: {area}")
                                    continue
                            
                            # 归一化中心点坐标用于去重检查
                            center_x = obb_result['center'][0]
                            center_y = obb_result['center'][1]
                            norm_center_x = center_x / image_width
                            norm_center_y = center_y / image_height
                            
                            # 四舍五入到3位小数，用于比较
                            center_x_rounded = round(norm_center_x, 3)
                            center_y_rounded = round(norm_center_y, 3)
                            area_rounded = round(area, 0)
                            
                            # 检查是否已经创建了相似位置和大小的OBB标签
                            label_key = (center_x_rounded, center_y_rounded, area_rounded)
                            if label_key in created_label_info:
                                logger.warning(f"OBB模式发现重复标签，跳过: 中心({center_x_rounded}, {center_y_rounded}), 面积{area_rounded}")
                                continue
                            
                            # 提取置信度
                            mask_confidence = confidence
                            if mask_confidence is None:
                                mask_confidence = self._extract_mask_confidence(result, mask, i)
                            
                            logger.info(f"准备创建OBB子标签，置信度: {mask_confidence}")
                            
                            # 创建OBB子标签
                            child = self.create_child_labels_from_obb(
                                obb_result, image_info, image_width, image_height, mask_confidence, mask_np
                            )
                            
                            if child:
                                created_labels.append(child)
                                created_label_info.add(label_key)
                                logger.info(f"从OBB模式掩码 {i} 成功创建OBB标签")
                            else:
                                logger.warning(f"从OBB模式掩码 {i} 创建OBB标签失败")
                            
                    else:
                        logger.warning(f"OBB模式结果 {result_idx} 没有掩码数据")
                            
                except Exception as e:
                    logger.error(f"处理OBB模式SAM结果中的掩码时发生错误: {str(e)}")
                    continue
            
            # 更新画布
            if created_labels and self.canvas:
                try:
                    QTimer.singleShot(0, lambda: self.canvas.update_rects())
                except Exception:
                    self.canvas.update_rects()
                
                # 刷新缩略图
                if hasattr(self.canvas, 'main_window') and hasattr(self.canvas.main_window, '_refresh_thumbnail_for_image'):
                    try:
                        QTimer.singleShot(0, lambda: self.canvas.main_window._refresh_thumbnail_for_image(image_info))
                    except Exception:
                        self.canvas.main_window._refresh_thumbnail_for_image(image_info)

                # 确认标签绘制成功后清空临时裁剪文件夹
                try:
                    temp_dir = r"c:\moonlightv2.104重制版\temp_crops"
                    if os.path.isdir(temp_dir):
                        for name in os.listdir(temp_dir):
                            fp = os.path.join(temp_dir, name)
                            try:
                                if os.path.isfile(fp) or os.path.islink(fp):
                                    os.remove(fp)
                                elif os.path.isdir(fp):
                                    for sub in os.listdir(fp):
                                        sp = os.path.join(fp, sub)
                                        if os.path.isfile(sp) or os.path.islink(sp):
                                            os.remove(sp)
                                    try:
                                        os.rmdir(fp)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        logger.info("已清空临时裁剪目录 temp_crops")
                except Exception:
                    pass
            
            logger.info(f"从OBB模式SAM推理结果成功创建了 {len(created_labels)} 个OBB标签")
            return created_labels
            
        except Exception as e:
            logger.error(f"处理OBB模式SAM推理结果时发生错误: {str(e)}")
            return []
    
    def create_child_labels_from_obb(self, obb_result, image_info, image_width, image_height, confidence=None, mask_data=None):
        """
        根据最小外接矩形结果创建OBB子标签
        
        Args:
            obb_result: 最小外接矩形结果
            image_info: 图像信息
            image_width: 图像宽度
            image_height: 图像高度
            confidence: 置信度
            mask_data: 原始MASK数据，用于polygon_mask类型标签
            
        Returns:
            创建的标签对象，如果创建失败则返回None
        """
        try:
            logger.info(f"开始从OBB结果创建子标签")
            
            # 检查OBB结果是否有效
            if not obb_result:
                logger.warning("OBB结果为空，无法创建标签")
                return None
                
            # 检查图像信息是否有效
            if not image_info:
                logger.warning("图像信息为空，无法创建标签")
                return None
                
            # 检查图像尺寸是否有效
            if image_width <= 0 or image_height <= 0:
                logger.warning(f"图像尺寸无效: {image_width}x{image_height}，无法创建标签")
                return None
            
            # 检查面积是否满足要求
            area = obb_result['area']
            logger.info(f"OBB面积: {area}")
            if area < self.config['min_bbox_area']:
                try:
                    ca = cv2.contourArea(np.array(obb_result.get('corners', []), dtype=np.int32))
                except Exception:
                    ca = 0
                if ca < self.config['min_bbox_area']:
                    logger.warning(f"OBB面积过小，跳过: {area} < {self.config['min_bbox_area']}")
                    return None
            
            # 获取最小外接矩形的四个角点
            corner_points = obb_result['corners']
            logger.info(f"OBB角点数量: {len(corner_points)}")
            
            # 检查角点数量是否有效
            if len(corner_points) != 4:
                logger.warning(f"OBB角点数量无效: {len(corner_points)}，需要4个角点")
                return None
            
            # 不再使用角度等旋转信息，OBB视为四点多边形
            
            # 创建标签
            if self.parent_label_list:
                logger.debug("父标签列表存在，准备创建子标签")
                
                # 处理置信度
                if confidence is not None:
                    logger.debug(f"使用提供的置信度: {confidence}")
                    try:
                        confidence = float(confidence)
                        confidence = max(0.0, min(1.0, confidence))
                        logger.debug(f"调整后置信度: {confidence}")
                    except Exception as e:
                        logger.warning(f"置信度转换失败: {str(e)}")
                        confidence = None
                else:
                    logger.debug("未提供置信度")
                
                try:
                    from auto_label_filter import is_duplicate_polygon
                    parent = self.parent_label_list.get_selected() if self.parent_label_list else None
                    if parent and hasattr(parent, 'children_by_image') and image_info in parent.children_by_image:
                        if is_duplicate_polygon(parent, image_info, corner_points, image_width, image_height):
                            return None
                except Exception:
                    pass

                # 创建子标签：将OBB作为四点多边形标签
                logger.debug("调用create_child_label方法创建多边形子标签(四点)")
                child = self.parent_label_list.create_child_label(
                    image_info=image_info,
                    shape_type='polygon',
                    polygon_points=corner_points,
                    mask_data=None
                )
                
                if child:
                    logger.debug(f"成功创建多边形子标签(四点): 面积{area:.2f}, conf={confidence if confidence is not None else 'None'}")
                    # 统一为多边形数据结构
                    child.polygon_points = corner_points
                    child.is_polygon = True
                    return child
                else:
                    logger.warning("create_child_label返回None，创建标签失败")
                    # 如果返回的是已存在的标签（不是None），说明是重复标签，直接返回
                    if child is not None:
                        logger.debug("检测到重复标签，更新多边形信息")
                        child.polygon_points = corner_points
                        child.is_polygon = True
                        return child
            else:
                logger.warning("父标签列表不存在，无法创建子标签")
            
            return None
            
        except Exception as e:
            logger.error(f"创建OBB子标签时发生错误: {str(e)}")
            return None


# 全局实例获取函数
_auto_pen_manager = None

def get_auto_pen_manager():
    """
    获取全局AutoPenManager实例
    
    Returns:
        AutoPenManager实例
    """
    global _auto_pen_manager
    if _auto_pen_manager is None:
        _auto_pen_manager = AutoPenManager()
    return _auto_pen_manager


def main():
    """测试函数"""
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    auto_pen_manager = AutoPenManager()

    auto_pen_manager.drawing_started.connect(lambda msg: print(f"开始绘制: {msg}"))
    auto_pen_manager.drawing_progress.connect(lambda msg, curr, total: print(f"绘制进度: {msg} ({curr}/{total})"))
    auto_pen_manager.drawing_completed.connect(lambda labels: print(f"绘制完成，创建了 {len(labels)} 个标签"))
    auto_pen_manager.drawing_error.connect(lambda err: print(f"绘制错误: {err}"))

    print("MASK模式自动绘制管理器初始化完成")


if __name__ == "__main__":
    main()
