import os
import logging
import time
import numpy as np
import cv2
from services.global_model_loader import get_global_model_loader
from app_ui.set import get_settings_manager
from app_ui.remote_sensing import is_remote_sensing_enabled

# 获取全局模型加载器实例
model_loader = get_global_model_loader()
logger = logging.getLogger(__name__)


# 全局YOLO置信度阈值
YOLO_CONFIDENCE_THRESHOLD = 0.5

def yolov_one(bboxes, image_path):
    """
    使用YOLO模型对图片的输入坐标区域进行推理
    
    Args:
        bboxes: 边界框坐标列表，格式为[[x1, y1, x2, y2], ...]
        image_path: 图片路径
    
    Returns:
        包含矩形框坐标、置信度和类别ID的列表，格式为[{"bbox": [x1, y1, x2, y2], "confidence": 置信度, "class_id": 类别ID}, ...]
    """
    # 检查YOLO模型是否已加载，如果未加载则等待或返回空结果
    if not model_loader.is_model_loaded("yolov"):
        logger.warning("YOLO模型尚未加载完成，请稍后再试")
        return []
    
    try:
        settings_mgr = get_settings_manager()
        custom_path = getattr(settings_mgr, 'custom_yolov_weight', None)
        if custom_path and os.path.exists(custom_path):
            current_model = model_loader.get_model("yolov")
            current_weight = getattr(current_model, 'pt', None)
            if str(current_weight) != str(custom_path):
                model_loader.switch_yolov_model(custom_path)
    except Exception:
        pass

    # 线程安全地运行当前 YOLO 模型的推理
    results = model_loader.run_yolov_inference(image_path)
    
    # 提取矩形框坐标、置信度和类别ID
    output_data = []
    if results and len(results) > 0:
        # 获取检测结果
        boxes = results[0].boxes
        if boxes is not None:
            for box in boxes:
                # 获取置信度
                confidence = float(box.conf[0].cpu().numpy())
                
                # 使用全局置信度阈值过滤结果
                if confidence >= YOLO_CONFIDENCE_THRESHOLD:
                    # 获取边界框坐标
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    # 保留两位小数
                    bbox = [round(coord, 2) for coord in bbox]
                    
                    # 获取类别ID
                    class_id = int(box.cls[0].cpu().numpy())
                    
                    # 检查边界框是否在输入的坐标区域内
                    for input_bbox in bboxes:
                        x1, y1, x2, y2 = input_bbox
                        # 简单检查边界框中心点是否在输入区域内
                        center_x = (bbox[0] + bbox[2]) / 2
                        center_y = (bbox[1] + bbox[3]) / 2
                        
                        if x1 <= center_x <= x2 and y1 <= center_y <= y2:
                            output_data.append({
                                "bbox": bbox,
                                "confidence": confidence,
                                "class_id": class_id
                            })
                            break  # 只要在一个输入区域内就添加，避免重复
    
    # 如果没有检测到目标，尝试使用不同的权重文件
    if not output_data:
        logger.info("当前权重文件未检测到目标，尝试使用其他权重文件...")
        success, new_output_data = model_loader.try_different_yolov_weights(bboxes, image_path, YOLO_CONFIDENCE_THRESHOLD)
        if success:
            output_data = new_output_data
            logger.info("找到合适的权重文件并成功检测到目标")
        else:
            logger.warning("yolov一阶段失败：尝试了所有权重文件，但没有找到能检测到目标的权重")

    # 返回结果列表和成功标志
    return output_data, bool(output_data)

def yolov_two(image_path):
    """
    使用YOLO模型对地址图片进行推理
    
    Args:
        image_path: 图片路径
    
    Returns:
        包含矩形框坐标、置信度和类别ID的列表，格式为[{"bbox": [x1, y1, x2, y2], "confidence": 置信度, "class_id": 类别ID}, ...]
    """
    # 检查YOLO模型是否已加载，如果未加载则等待或返回空结果
    if not model_loader.is_model_loaded("yolov"):
        logger.warning("YOLO模型尚未加载完成，请稍后再试")
        return []
    
    # 线程安全地运行当前 YOLO 模型的推理
    results = model_loader.run_yolov_inference(image_path)
    
    # 提取矩形框坐标、置信度和类别ID
    output_data = []
    if results and len(results) > 0:
        # 获取检测结果
        boxes = results[0].boxes
        if boxes is not None:
            for box in boxes:
                # 获取置信度
                confidence = float(box.conf[0].cpu().numpy())
                
                # 使用全局置信度阈值过滤结果
                if confidence >= YOLO_CONFIDENCE_THRESHOLD:
                    # 获取边界框坐标
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    
                    # 获取类别ID
                    class_id = int(box.cls[0].cpu().numpy())
                    
                    output_data.append({
                        "bbox": bbox,
                        "confidence": confidence,
                        "class_id": class_id
                    })
    
    # 如果没有检测到目标，输出提示信息
    if not output_data:
        logger.info("yolov第二阶段无结果")
    
    return output_data

def filter_results_by_class(yolov_one_results, yolov_two_results):
    """
    使用yolov_one输出的类别id为基准对yolov_two输出的目标进行筛选
    
    Args:
        yolov_one_results: yolov_one方法的输出结果，格式为[{"bbox": [x1, y1, x2, y2], "confidence": 置信度, "class_id": 类别ID}, ...]
        yolov_two_results: yolov_two方法的输出结果，格式为[{"bbox": [x1, y1, x2, y2], "confidence": 置信度, "class_id": 类别ID}, ...]
    
    Returns:
        筛选后的结果列表，格式为[{"bbox": [x1, y1, x2, y2], "confidence": 置信度, "class_id": 类别ID}, ...]
    """
    # 提取yolov_one结果中的所有类别ID
    yolov_one_class_ids = set()
    for result in yolov_one_results:
        yolov_one_class_ids.add(result["class_id"])
    
    # 如果yolov_one结果中没有类别ID，返回空列表
    if not yolov_one_class_ids:
        return []
    
    # 筛选yolov_two结果中类别ID与yolov_one结果中类别ID相同的目标
    filtered_results = []
    for result in yolov_two_results:
        if result["class_id"] in yolov_one_class_ids:
            filtered_results.append(result)
    
    # 如果没有匹配的结果，输出提示信息
    if not filtered_results:
        logger.info("yolov结果不匹配")
    
    return filtered_results


def yolov_inference(bboxes, image_path, main_window=None):
    """
    使用YOLOV模型进行推理
    
    Args:
        bboxes: 边界框坐标列表，格式为[[x1, y1, x2, y2], ...]
        image_path: 图片路径
        main_window: 主窗口对象，用于获取画布信息（遥感模式使用）
    
    Returns:
        包含矩形框坐标的列表，格式为[[x1, y1, x2, y2], ...]
    """
    # 检查YOLOV模型是否已加载，如果未加载则等待或返回空结果
    if not model_loader.is_model_loaded("yolov"):
        logger.warning("YOLOV模型尚未加载完成，请稍后再试")
        return [], False
    
    # 检查是否启用遥感模式
    remote_enabled = False
    use_cropped_path = None
    run_image = None
    shift_x = 0
    shift_y = 0
    crop_w = None
    crop_h = None
    
    try:
        remote_enabled = bool(is_remote_sensing_enabled())
    except Exception:
        remote_enabled = False
    
    # 遥感模式处理
    if remote_enabled and main_window and hasattr(main_window, 'canvas') and main_window.canvas:
        try:
            from draw_jk import _get_visible_image_rect
            view = main_window.canvas
            pixmap = None
            if hasattr(view, 'image_item') and view.image_item:
                try:
                    pixmap = view.image_item.pixmap()
                except Exception:
                    pixmap = None
            if pixmap is None and hasattr(view, 'current_pixmap'):
                pixmap = getattr(view, 'current_pixmap', None)

            if pixmap is not None and not pixmap.isNull():
                crop_rect = _get_visible_image_rect(view)
                if crop_rect and crop_rect.width() > 0 and crop_rect.height() > 0:
                    img_w = int(pixmap.width())
                    img_h = int(pixmap.height())
                    if not (crop_rect.width() >= img_w and crop_rect.height() >= img_h):
                            # 文件级裁剪原图
                            img = cv2.imread(image_path)
                            if img is not None:
                                h, w = img.shape[:2]
                                shift_x = max(0, min(crop_rect.x(), w - 1))
                                shift_y = max(0, min(crop_rect.y(), h - 1))
                                crop_w = min(crop_rect.width(), w - shift_x)
                                crop_h = min(crop_rect.height(), h - shift_y)
                                
                                if crop_w > 0 and crop_h > 0:
                                    x1 = shift_x
                                    y1 = shift_y
                                    x2 = shift_x + crop_w
                                    y2 = shift_y + crop_h
                                    crop = img[y1:y2, x1:x2]
                                    ts = int(time.time() * 1000)
                                    temp_dir = os.path.join(os.getcwd(), 'temp_crops')
                                    os.makedirs(temp_dir, exist_ok=True)
                                    use_cropped_path = os.path.join(temp_dir, f'yolov_crop_{ts}.png')
                                    run_image = crop
                                    
                                    # 调整边界框坐标到裁剪图
                                    adjusted_bboxes = []
                                    for bbox in bboxes:
                                        x1, y1, x2, y2 = bbox
                                        # 计算边界框与裁剪区域的交集
                                        new_x1 = max(0, x1 - shift_x)
                                        new_y1 = max(0, y1 - shift_y)
                                        new_x2 = min(crop_w, x2 - shift_x)
                                        new_y2 = min(crop_h, y2 - shift_y)
                                        
                                        # 只保留有效边界框
                                        if new_x2 > new_x1 and new_y2 > new_y1:
                                            adjusted_bboxes.append([new_x1, new_y1, new_x2, new_y2])
                                    
                                    if adjusted_bboxes:
                                        bboxes = adjusted_bboxes
                                    else:
                                        # 如果没有有效的边界框，取消裁剪
                                        use_cropped_path = None
        except Exception as e:
            logger.warning(f"遥感模式裁剪失败，使用原图: {e}")
            use_cropped_path = None
    
    # 使用裁剪图路径或原图路径进行推理
    run_path = use_cropped_path if use_cropped_path else image_path
    
    try:
        # First stage using the provided bboxes, now returns (results, success_flag)
        one_results, one_success = yolov_one(bboxes, (run_image if run_image is not None else run_path))

        # 只有当第一阶段成功时才执行第二阶段
        if not one_success:
            return [], False

        # 第二阶段执行
        two_results = yolov_two((run_image if run_image is not None else run_path))

        # Filter results by class consistency
        filtered = filter_results_by_class(one_results, two_results)

        # Extract bbox coordinates
        bbox_list = [item['bbox'] for item in filtered if isinstance(item, dict) and 'bbox' in item]
        
        # 如果使用了裁剪图，将结果坐标映射回原图
        if use_cropped_path and crop_w and crop_h:
            adjusted_results = []
            for bbox in bbox_list:
                x1, y1, x2, y2 = bbox
                # 将坐标映射回原图
                orig_x1 = x1 + shift_x
                orig_y1 = y1 + shift_y
                orig_x2 = x2 + shift_x
                orig_y2 = y2 + shift_y
                adjusted_results.append([orig_x1, orig_y1, orig_x2, orig_y2])
            return adjusted_results, bool(adjusted_results)
        
        success = bool(bbox_list)
        return bbox_list, success
    except Exception as e:
        # 错误日志并返回失败标志
        logger.error(f"yolov_inference 错误: {e}")
        return [], False
