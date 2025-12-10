"""
inference_moon.py - 调用yoloe_moon.py中的推理方法进行推理
"""

import logging
import threading
import queue
from typing import List, Tuple, Optional, Dict, Any
from algorithms.polygon_bounding_rectangle import calculate_bounding_rectangle
from inference.yoloe_moon import yoloe_inference, yoloe_semantic_inference
from inference.yolov_moon import yolov_inference
from app_ui.set import get_settings_manager

logger = logging.getLogger(__name__)

# 创建一个全局队列用于存储推理结果
inference_results_queue = queue.Queue()

def run_inference_with_manual_label(
    get_image_info_func,
    parent_label_list,
    child_labels: List[Any] = None,
    shape_type: str = 'rectangle',
    callback=None,
    main_window=None
) -> Dict[str, Any]:
    """
    使用手动绘制的矩形框或多边形的外接矩形进行推理
    
    Args:
        get_image_info_func: 获取图片信息的函数
        parent_label_list: 父标签列表，用于获取选中的父标签
        child_labels: 子标签列表，如果为None则使用选中的父标签下的所有子标签
        shape_type: 形状类型，'rectangle'表示矩形框，'polygon'表示多边形
        callback: 回调函数，用于在推理完成后处理结果
    
    Returns:
        Dict[str, Any]: 推理结果，包含检测框和置信度等信息
    """
    def inference_thread():
        try:
            # 获取图片地址
            image_path = get_image_info_func()
            if not image_path:
                result = {"error": "无法获取图片地址"}
                if callback:
                    callback(result)
                inference_results_queue.put(result)
                return
            
            # 获取选中的父标签
            selected_parent = parent_label_list.get_selected()
            if not selected_parent:
                result = {"error": "没有选中的父标签"}
                if callback:
                    callback(result)
                inference_results_queue.put(result)
                return
            
            # 获取类别ID和父标签名称
            category_id = selected_parent.id
            parent_label_name = selected_parent.name if hasattr(selected_parent, 'name') else "object"
            
            # 获取设置管理器并检查语义激活开关状态
            settings_manager = get_settings_manager()
            semantic_enabled = settings_manager.is_semantic_enabled()
            
            # 获取边界框坐标
            bounding_boxes = []
            category_ids = []
            
            # 获取要处理的子标签列表
            local_child_labels = child_labels
            if local_child_labels is None:
                # 获取当前图片的子标签
                image_info = image_path
                if hasattr(selected_parent, 'children_by_image') and image_info in selected_parent.children_by_image:
                    local_child_labels = selected_parent.children_by_image[image_info]
                else:
                    local_child_labels = []
            
            # 确保local_child_labels是列表类型
            if not isinstance(local_child_labels, list):
                local_child_labels = []
            
            # 处理每个子标签
            for child in local_child_labels:
                # 跳过占位符标签
                if getattr(child, 'is_placeholder', False):
                    continue
                    
                # 根据形状类型获取边界框
                if shape_type == 'rectangle' and hasattr(child, 'points') and len(child.points) >= 8:
                    # 矩形框，直接使用四个顶点坐标
                    points = child.points
                    # 确保是四个点
                    if len(points) >= 8:
                        # 直接使用顶点坐标计算边界框 (x_min, y_min, x_max, y_max)
                        x_coords = [points[i] for i in range(0, len(points), 2)]
                        y_coords = [points[i+1] for i in range(0, len(points), 2)]
                        
                        x_min = round(min(x_coords), 2)
                        y_min = round(min(y_coords), 2)
                        x_max = round(max(x_coords), 2)
                        y_max = round(max(y_coords), 2)
                        
                        bounding_boxes.append([x_min, y_min, x_max, y_max])
                        category_ids.append(category_id)
                
                elif shape_type == 'polygon' and hasattr(child, 'points') and len(child.points) >= 3:
                    # 多边形，计算外接矩形
                    try:
                        # 检查多边形点的数据类型
                        if isinstance(child.points[0], (list, tuple)) and len(child.points[0]) >= 2:
                            # 点已经是列表或元组格式
                            polygon_coords = [(point[0], point[1]) for point in child.points]
                        elif isinstance(child.points[0], int) and len(child.points) >= 6:
                            # 点是整数格式，需要两两配对
                            polygon_coords = [(child.points[i], child.points[i+1]) for i in range(0, len(child.points), 2)]
                        else:
                            logger.warning(f"多边形点数据格式不支持: {type(child.points[0])}")
                            continue
                        
                        bounding_rect = calculate_bounding_rectangle(polygon_coords)
                        
                        if bounding_rect and len(bounding_rect) >= 4:
                            # 获取外接矩形的四个顶点
                            x1, y1 = bounding_rect[0]
                            x2, y2 = bounding_rect[1]
                            x3, y3 = bounding_rect[2]
                            x4, y4 = bounding_rect[3]
                            
                            # 计算边界框 (x_min, y_min, x_max, y_max)
                            x_min = round(min(x1, x2, x3, x4), 2)
                            y_min = round(min(y1, y2, y3, y4), 2)
                            x_max = round(max(x1, x2, x3, x4), 2)
                            y_max = round(max(y1, y2, y3, y4), 2)
                            
                            bounding_boxes.append([x_min, y_min, x_max, y_max])
                            category_ids.append(category_id)
                    except Exception as e:
                        logger.error(f"处理多边形点时发生错误: {e}")
                        continue
            
            # 如果没有有效的边界框，返回错误
            if not bounding_boxes:
                result = {"error": "没有找到有效的边界框"}
                if callback:
                    callback(result)
                inference_results_queue.put(result)
                return
            
            # 检查是否跳过yolov推理
            skip_yolov = settings_manager.is_skip_yolov_enabled()

            # 初始化变量，确保后续分支中可用
            yolov_one_results = []
            yolov_two_results = []
            filtered_results = []
            yolov_boxes = []

            if skip_yolov:
                logger.info("设置中已启用跳过YOLOV推理，直接使用YOLOE进行推理")
                use_yoloe = True
            else:
                # 使用新的 yolov_inference 包装函数进行推理
                logger.info(f"开始YOLOV推理（通过 yolov_inference），图片路径: {image_path}, 边界框数量: {len(bounding_boxes)}")
                try:
                    bbox_list, yolov_success = yolov_inference(bounding_boxes, image_path, main_window=main_window)
                except Exception as e:
                    logger.error(f"调用 yolov_inference 失败: {e}")
                    bbox_list, yolov_success = [], False

                if not yolov_success:
                    logger.info("yolov_inference 返回失败标志，将使用yoloe进行推理")
                    use_yoloe = True
                else:
                    # 将返回的 bbox 列表包装为与原逻辑兼容的筛选结果格式
                    filtered_results = [{"bbox": bbox} for bbox in bbox_list]
                    yolov_boxes = [bbox for bbox in bbox_list]
                    use_yoloe = False
            
            # 如果yolov推理成功，则直接返回YOLOV结果（无论语义激活与否）
            if not use_yoloe:
                logger.info("YOLOV推理成功，直接返回结果（语义激活不触发YOLOE）")
                result = {
                    "yolov_result": {
                        "yolov_one_results": yolov_one_results,
                        "yolov_two_results": yolov_two_results,
                        "filtered_results": filtered_results
                    }
                }
                if callback:
                    callback(result)
                inference_results_queue.put(result)
                return
            
            # 调用yoloe_moon.py中的推理方法
            logger.info(f"开始YOLOE推理，图片路径: {image_path}, 边界框数量: {len(bounding_boxes)}")
            
            # 根据语义激活开关状态选择推理方法
            if semantic_enabled:
                # 使用语义激活推理
                logger.info(f"使用语义激活推理，语义描述: {parent_label_name}")
                yoloe_result = yoloe_semantic_inference(
                    semantic_description=parent_label_name,
                    bboxes=bounding_boxes,
                    cls_ids=category_ids,  # category_ids已经是列表
                    image_path=image_path,
                    main_window=main_window
                )
            else:
                # 使用普通推理
                yoloe_result = yoloe_inference(bounding_boxes, category_ids, image_path, main_window=main_window)
            
            # 检查YOLOE推理结果
            if not yoloe_result:
                result = {"error": "YOLOE推理未返回有效结果"}
                if callback:
                    callback(result)
                inference_results_queue.put(result)
                return
            
            # 仅返回 YOLOE 的 bbox，统一形态供上层驱动 SAM 分割
            yoloe_boxes = [item["bbox"] for item in yoloe_result if "bbox" in item]
            if not yoloe_boxes:
                result = {"error": "YOLOE推理结果中未找到有效的边界框"}
                if callback:
                    callback(result)
                inference_results_queue.put(result)
                return

            result = {
                "filtered_results": [{"bbox": bbox} for bbox in yoloe_boxes]
            }
            if callback:
                callback(result)
            inference_results_queue.put(result)
            return
        except Exception as e:
            error_result = {"error": str(e)}
            logger.error(f"推理过程中发生错误: {e}")
            if callback:
                callback(error_result)
            inference_results_queue.put(error_result)
    
    # 创建并启动后台线程执行推理
    thread = threading.Thread(target=inference_thread)
    thread.daemon = True  # 设置为守护线程，主程序退出时自动结束
    thread.start()
    
    # 返回一个占位结果，实际结果将通过回调函数或队列获取
    return {"status": "inference_started", "message": "推理已在后台线程中启动"}


def run_inference_with_specific_child(
    get_image_info_func,
    parent_label_list,
    child_label: Any,
    shape_type: str = 'rectangle',
    callback=None,
    main_window=None
) -> Dict[str, Any]:
    """
    使用特定的子标签进行推理
    
    Args:
        get_image_info_func: 获取图片信息的函数
        parent_label_list: 父标签列表，用于获取选中的父标签
        child_label: 特定的子标签
        shape_type: 形状类型，'rectangle'表示矩形框，'polygon'表示多边形
        callback: 回调函数，用于在推理完成后处理结果
    
    Returns:
        Dict[str, Any]: 推理结果，包含检测框和置信度等信息
    """
    return run_inference_with_manual_label(
        get_image_info_func,
        parent_label_list,
        [child_label],
        shape_type,
        callback,
        main_window
    )

def get_latest_inference_result():
    """
    获取最新的推理结果
    
    Returns:
        Dict[str, Any]: 最新的推理结果，如果没有结果则返回None
    """
    try:
        return inference_results_queue.get_nowait()
    except queue.Empty:
        return None
