#单独直觉提示
import os
import logging
import time
import numpy as np
import cv2
from ultralytics.models.yolo.yoloe import YOLOEVPSegPredictor
from services.global_model_loader import get_global_model_loader
from app_ui.remote_sensing import is_remote_sensing_enabled

logger = logging.getLogger(__name__)

# 获取全局模型加载器
model_loader = get_global_model_loader()

# 全局YOLOE置信度阈值
YOLOE_CONFIDENCE_THRESHOLD = 0.03
# 全局YOLOE NMS IoU阈值（非极大值抑制的IoU门限）
YOLOE_NMS_IOU_THRESHOLD = 0.1
# 默认语义匹配阈值
YOLOE_SEMANTIC_THRESHOLD_DEFAULT = 0.8
# 默认提示权重
YOLOE_DEFAULT_PROMPT_WEIGHT = 0.8

def inference_with_semantic_prompts(image_path, semantic_descriptions, bboxes, cls_ids, prompt_weights=None, semantic_threshold=YOLOE_SEMANTIC_THRESHOLD_DEFAULT, main_window=None):
    """
    使用语义激活视觉提示进行YOLOE模型推理
    
    Args:
        image_path: 图片路径
        semantic_descriptions: 语义描述列表，如["a person standing"]
        bboxes: 边界框坐标列表，格式为[[x1, y1, x2, y2], ...]
        cls_ids: 类别ID列表，格式为[id1, id2, ...]
        prompt_weights: 提示权重列表，可选，默认为None
        semantic_threshold: 语义阈值，默认为0.3
        main_window: 主窗口对象，用于获取画布信息（遥感模式使用）
    
    Returns:
        YOLOE推理结果
    """
    # 检查YOLOE模型是否已加载，如果未加载则等待或返回空结果
    if not model_loader.is_model_loaded("yoloe"):
        logger.warning("YOLOE模型尚未加载完成，请稍后再试")
        return []
    
    # 获取YOLOE模型
    model = model_loader.get_model("yoloe")
    
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
                                    use_cropped_path = os.path.join(temp_dir, f'yoloe_semantic_prompt_crop_{ts}.png')
                                    run_image = crop
                                    
                                    # 调整边界框坐标到裁剪图
                                    adjusted_bboxes = []
                                    adjusted_cls_ids = []
                                    for i, bbox in enumerate(bboxes):
                                        x1, y1, x2, y2 = bbox
                                        # 计算边界框与裁剪区域的交集
                                        new_x1 = max(0, x1 - shift_x)
                                        new_y1 = max(0, y1 - shift_y)
                                        new_x2 = min(crop_w, x2 - shift_x)
                                        new_y2 = min(crop_h, y2 - shift_y)
                                        
                                        # 只保留有效边界框
                                        if new_x2 > new_x1 and new_y2 > new_y1:
                                            adjusted_bboxes.append([new_x1, new_y1, new_x2, new_y2])
                                            if i < len(cls_ids):
                                                adjusted_cls_ids.append(cls_ids[i])
                                    
                                    if adjusted_bboxes:
                                        bboxes = adjusted_bboxes
                                        cls_ids = adjusted_cls_ids
                                        # 调整提示权重
                                        if prompt_weights:
                                            adjusted_prompt_weights = []
                                            for i, bbox in enumerate(adjusted_bboxes):
                                                if i < len(prompt_weights):
                                                    adjusted_prompt_weights.append(prompt_weights[i])
                                                else:
                                                    adjusted_prompt_weights.append(YOLOE_DEFAULT_PROMPT_WEIGHT)
                                            prompt_weights = adjusted_prompt_weights
                                    else:
                                        # 如果没有有效的边界框，取消裁剪
                                        use_cropped_path = None
        except Exception as e:
            logger.warning(f"遥感模式裁剪失败，使用原图: {e}")
            use_cropped_path = None
    
    # 使用裁剪图路径或原图路径进行推理
    run_path = use_cropped_path if use_cropped_path else image_path
    
    # 如果没有提供提示权重，则使用默认值
    if prompt_weights is None:
        prompt_weights = [YOLOE_DEFAULT_PROMPT_WEIGHT] * len(bboxes)  # 默认所有提示权重相同

    # 语义描述与边界框数量对齐（避免长度不一致被忽略）
    if isinstance(semantic_descriptions, (str, bytes)):
        semantic_descriptions = [str(semantic_descriptions)]
    if len(bboxes) > 0 and len(semantic_descriptions) != len(bboxes):
        if len(semantic_descriptions) == 1:
            semantic_descriptions = semantic_descriptions * len(bboxes)
        else:
            # 若长度大于1但仍不匹配，按需要裁剪/填充
            semantic_descriptions = (semantic_descriptions + semantic_descriptions[:len(bboxes)])[:len(bboxes)]
    if len(bboxes) > 0 and len(prompt_weights) != len(bboxes):
        if len(prompt_weights) == 1:
            prompt_weights = prompt_weights * len(bboxes)
        else:
            prompt_weights = (prompt_weights + prompt_weights[:len(bboxes)])[:len(bboxes)]

    # 定义视觉提示字典，包含语义描述，并提供可能的键名同义以提升兼容性
    visual_prompts = dict(
        bboxes=np.array(bboxes),
        cls=np.array(cls_ids),
        prompts=semantic_descriptions,
        prompt_weights=np.array(prompt_weights),
        # 兼容键名（部分版本可能使用这些键）
        texts=semantic_descriptions,
        text_weights=np.array(prompt_weights),
        vp_bboxes=np.array(bboxes),
        vp_cls=np.array(cls_ids),
    )

    logger.info(f"YOLOE visual_prompts: keys={list(visual_prompts.keys())}, bboxes={len(bboxes)}, texts={len(semantic_descriptions)}")

    # 运行推理，优先尝试指定VP Seg预测器，失败则回退
    try:
            inp = run_image if run_image is not None else run_path
            results = model.predict(
                inp,
                visual_prompts=visual_prompts,
                predictor=YOLOEVPSegPredictor,
                conf=YOLOE_CONFIDENCE_THRESHOLD,
                iou=YOLOE_NMS_IOU_THRESHOLD,
            )
    except Exception as e:
        logger.warning(f"YOLOE predictor 覆盖失败，采用回退路径: {e}")
        try:
            inp = run_image if run_image is not None else run_path
            results = model.predict(
                inp,
                visual_prompts=visual_prompts,
                conf=YOLOE_CONFIDENCE_THRESHOLD,
                iou=YOLOE_NMS_IOU_THRESHOLD,
            )
        except Exception as e2:
            logger.error(f"YOLOE predict 调用失败: {e2}")
            return []
    
    # 如果使用了裁剪图，将结果坐标映射回原图
    if run_image is not None and crop_w and crop_h and results and len(results) > 0:
        # 获取检测结果
        boxes = results[0].boxes
        masks = results[0].masks
        
        if boxes is not None:
            # 转换边界框坐标
            adjusted_boxes = []
            for box in boxes:
                # 获取边界框坐标
                bbox = box.xyxy[0].cpu().numpy()
                # 将坐标映射回原图
                orig_x1 = bbox[0] + shift_x
                orig_y1 = bbox[1] + shift_y
                orig_x2 = bbox[2] + shift_x
                orig_y2 = bbox[3] + shift_y
                
                # 更新边界框坐标
                box.xyxy[0] = torch.tensor([orig_x1, orig_y1, orig_x2, orig_y2], device=box.xyxy[0].device)
                adjusted_boxes.append(box)
            
            # 更新结果中的边界框
            results[0].boxes = adjusted_boxes
            
            # 如果有掩码数据，需要调整掩码坐标
            if masks is not None:
                adjusted_masks = []
                # 预先读取原图尺寸，避免每次循环重复 I/O
                img0 = cv2.imread(image_path)
                orig_h, orig_w = (img0.shape[:2] if img0 is not None else (None, None))
                for i, mask in enumerate(masks.data):
                    mask_data = mask.cpu().numpy()
                    if orig_h is None or orig_w is None:
                        # 无法获取原图尺寸则跳过回映射
                        adjusted_masks.append(mask)
                        continue
                    # 将掩码先缩放到裁剪图尺寸（crop_h, crop_w），再贴回原图偏移位置
                    target_w = int(crop_w)
                    target_h = int(crop_h)
                    if mask_data.shape[1] != target_w or mask_data.shape[0] != target_h:
                        try:
                            mask_resized = cv2.resize(mask_data, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
                        except Exception:
                            mask_resized = mask_data
                    else:
                        mask_resized = mask_data

                    full_mask = np.zeros((orig_h, orig_w), dtype=mask_resized.dtype)
                    x_start = int(shift_x)
                    y_start = int(shift_y)
                    x_end = min(x_start + target_w, orig_w)
                    y_end = min(y_start + target_h, orig_h)

                    paste_h = max(0, y_end - y_start)
                    paste_w = max(0, x_end - x_start)
                    if paste_h > 0 and paste_w > 0:
                        full_mask[y_start:y_end, x_start:x_end] = mask_resized[:paste_h, :paste_w]
                    # 转换回tensor
                    adjusted_masks.append(torch.tensor(full_mask, device=mask.device))

                # 更新结果中的掩码
                if adjusted_masks:
                    masks.data = torch.stack(adjusted_masks)
    
    return results

def yoloe_inference(bboxes, cls_ids, image_path, main_window=None):
    """
    使用YOLOE模型进行推理
    
    Args:
        bboxes: 边界框坐标列表，格式为[[x1, y1, x2, y2], ...]
        cls_ids: 类别ID列表，格式为[id1, id2, ...]
        image_path: 图片路径
        main_window: 主窗口对象，用于获取画布信息（遥感模式使用）
    
    Returns:
        包含矩形框坐标、置信度和掩码的列表，格式为[{"bbox": [x1, y1, x2, y2], "confidence": 置信度, "mask": 掩码数据}, ...]
    """
    # 检查YOLOE模型是否已加载，如果未加载则等待或返回空结果
    if not model_loader.is_model_loaded("yoloe"):
        logger.warning("YOLOE模型尚未加载完成，请稍后再试")
        return []
    
    # 获取YOLOE模型
    model = model_loader.get_model("yoloe")
    
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
                                    use_cropped_path = os.path.join(temp_dir, f'yoloe_crop_{ts}.png')
                                    run_image = crop
                                    
                                    # 调整边界框坐标到裁剪图
                                    adjusted_bboxes = []
                                    adjusted_cls_ids = []
                                    for i, bbox in enumerate(bboxes):
                                        x1, y1, x2, y2 = bbox
                                        # 计算边界框与裁剪区域的交集
                                        new_x1 = max(0, x1 - shift_x)
                                        new_y1 = max(0, y1 - shift_y)
                                        new_x2 = min(crop_w, x2 - shift_x)
                                        new_y2 = min(crop_h, y2 - shift_y)
                                        
                                        # 只保留有效边界框
                                        if new_x2 > new_x1 and new_y2 > new_y1:
                                            adjusted_bboxes.append([new_x1, new_y1, new_x2, new_y2])
                                            if i < len(cls_ids):
                                                adjusted_cls_ids.append(cls_ids[i])
                                    
                                    if adjusted_bboxes:
                                        bboxes = adjusted_bboxes
                                        cls_ids = adjusted_cls_ids
                                    else:
                                        # 如果没有有效的边界框，取消裁剪
                                        use_cropped_path = None
        except Exception as e:
            logger.warning(f"遥感模式裁剪失败，使用原图: {e}")
            use_cropped_path = None
    
    # 使用裁剪图路径或原图路径进行推理
    run_path = use_cropped_path if use_cropped_path else image_path
    
    # 定义视觉提示字典
    visual_prompts = dict(
        bboxes=np.array(bboxes),
        cls=np.array(cls_ids),
    )

    # 运行推理，显式传递置信度阈值，失败时回退
    try:
        inp = run_image if run_image is not None else run_path
        results = model.predict(
            inp,
            visual_prompts=visual_prompts,
            predictor=YOLOEVPSegPredictor,
            conf=YOLOE_CONFIDENCE_THRESHOLD,
            iou=YOLOE_NMS_IOU_THRESHOLD,
        )
    except Exception as e:
        logger.warning(f"YOLOE predictor 覆盖失败，采用回退路径: {e}")
        try:
            inp = run_image if run_image is not None else run_path
            results = model.predict(
                inp,
                visual_prompts=visual_prompts,
                conf=YOLOE_CONFIDENCE_THRESHOLD,
                iou=YOLOE_NMS_IOU_THRESHOLD,
            )
        except Exception as e2:
            logger.error(f"YOLOE predict 调用失败: {e2}")
            return []

    # 提取矩形框坐标、置信度和掩码
    output_data = []
    if results and len(results) > 0:
        # 获取检测结果
        boxes = results[0].boxes
        masks = results[0].masks
        
        if boxes is not None:
            for i, box in enumerate(boxes):
                # 获取置信度
                confidence = float(box.conf[0].cpu().numpy())
                
                # 保留置信度过滤逻辑，但模型已经过滤过一次，这里作为双重保障
                if confidence >= YOLOE_CONFIDENCE_THRESHOLD:
                    # 获取边界框坐标
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    # 保留两位小数
                    bbox = [round(coord, 2) for coord in bbox]
                    
                    # 创建结果字典
                    result_item = {
                        "bbox": bbox,
                        "confidence": confidence
                    }
                    
                    # 如果有掩码数据，添加掩码信息
                    if masks is not None and i < len(masks.data):
                        mask_data = masks.data[i].cpu().numpy()
                        result_item["mask"] = mask_data
                    
                    output_data.append(result_item)
    
    # 如果使用了裁剪图，将结果坐标映射回原图
    if run_image is not None and crop_w and crop_h:
        adjusted_results = []
        for item in output_data:
            bbox = item["bbox"]
            x1, y1, x2, y2 = bbox
            # 将坐标映射回原图
            orig_x1 = x1 + shift_x
            orig_y1 = y1 + shift_y
            orig_x2 = x2 + shift_x
            orig_y2 = y2 + shift_y
            
            adjusted_item = {
                "bbox": [orig_x1, orig_y1, orig_x2, orig_y2],
                "confidence": item["confidence"]
            }
            
            # 如果有掩码数据，需要调整掩码坐标
            if "mask" in item:
                mask = item["mask"]
                # 预先读取原图尺寸以避免重复 I/O
                img0 = cv2.imread(image_path)
                if img0 is not None:
                    orig_h, orig_w = img0.shape[:2]
                    # 将掩码缩放到裁剪图尺寸（crop_h, crop_w），再贴回原图
                    target_w = int(crop_w)
                    target_h = int(crop_h)
                    if mask.shape[1] != target_w or mask.shape[0] != target_h:
                        try:
                            mask_resized = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
                        except Exception:
                            mask_resized = mask
                    else:
                        mask_resized = mask

                    full_mask = np.zeros((orig_h, orig_w), dtype=mask_resized.dtype)
                    x_start = int(shift_x)
                    y_start = int(shift_y)
                    x_end = min(x_start + target_w, orig_w)
                    y_end = min(y_start + target_h, orig_h)
                    paste_h = max(0, y_end - y_start)
                    paste_w = max(0, x_end - x_start)
                    if paste_h > 0 and paste_w > 0:
                        full_mask[y_start:y_end, x_start:x_end] = mask_resized[:paste_h, :paste_w]
                    adjusted_item["mask"] = full_mask
            
            adjusted_results.append(adjusted_item)
        
        return adjusted_results
    
    return output_data

def yoloe_semantic_inference(semantic_description, bboxes, cls_ids, image_path, prompt_weights=None, semantic_threshold=YOLOE_SEMANTIC_THRESHOLD_DEFAULT, main_window=None):
    """
    使用语义激活视觉提示进行YOLOE模型推理
    
    Args:
        semantic_description: 语义描述字符串，如"a person standing"
        bboxes: 边界框坐标列表，格式为[[x1, y1, x2, y2], ...]
        cls_ids: 类别ID列表，格式为[id1, id2, ...]
        image_path: 图片路径
        prompt_weights: 提示权重列表，可选，默认为None
        semantic_threshold: 语义阈值，默认为0.3
        main_window: 主窗口对象，用于获取画布信息（遥感模式使用）
    
    Returns:
        包含矩形框坐标、置信度和掩码的列表，格式为[{"bbox": [x1, y1, x2, y2], "confidence": 置信度, "mask": 掩码数据}, ...]
    """
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
                                    use_cropped_path = os.path.join(temp_dir, f'yoloe_semantic_crop_{ts}.png')
                                    run_image = crop
                                    
                                    # 调整边界框坐标到裁剪图
                                    adjusted_bboxes = []
                                    adjusted_cls_ids = []
                                    for i, bbox in enumerate(bboxes):
                                        x1, y1, x2, y2 = bbox
                                        # 计算边界框与裁剪区域的交集
                                        new_x1 = max(0, x1 - shift_x)
                                        new_y1 = max(0, y1 - shift_y)
                                        new_x2 = min(crop_w, x2 - shift_x)
                                        new_y2 = min(crop_h, y2 - shift_y)
                                        
                                        # 只保留有效边界框
                                        if new_x2 > new_x1 and new_y2 > new_y1:
                                            adjusted_bboxes.append([new_x1, new_y1, new_x2, new_y2])
                                            if i < len(cls_ids):
                                                adjusted_cls_ids.append(cls_ids[i])
                                    
                                    if adjusted_bboxes:
                                        bboxes = adjusted_bboxes
                                        cls_ids = adjusted_cls_ids
                                        # 调整提示权重
                                        if prompt_weights:
                                            adjusted_prompt_weights = []
                                            for i, bbox in enumerate(adjusted_bboxes):
                                                if i < len(prompt_weights):
                                                    adjusted_prompt_weights.append(prompt_weights[i])
                                                else:
                                                    adjusted_prompt_weights.append(YOLOE_DEFAULT_PROMPT_WEIGHT)
                                            prompt_weights = adjusted_prompt_weights
                                    else:
                                        # 如果没有有效的边界框，取消裁剪
                                        use_cropped_path = None
        except Exception as e:
            logger.warning(f"遥感模式裁剪失败，使用原图: {e}")
            use_cropped_path = None
    
    # 使用裁剪图路径或原图路径进行推理
    run_path = use_cropped_path if use_cropped_path else image_path
    
    # 如果没有提供提示权重，则使用默认值
    if prompt_weights is None:
        prompt_weights = [YOLOE_DEFAULT_PROMPT_WEIGHT] * len(bboxes)  # 默认所有提示权重相同

    # 将单个语义描述转换为与 bboxes 数量对齐的列表格式
    semantic_descriptions = [semantic_description] * len(bboxes) if len(bboxes) > 0 else [semantic_description]
    
    # 使用语义激活视觉提示进行推理
    semantic_results = inference_with_semantic_prompts(
        image_path=(run_image if run_image is not None else run_path),
        semantic_descriptions=semantic_descriptions,
        bboxes=bboxes,
        cls_ids=cls_ids,
        prompt_weights=prompt_weights,
        semantic_threshold=semantic_threshold
    )

    # 提取矩形框坐标、置信度和掩码
    output_data = []
    if semantic_results and len(semantic_results) > 0:
        # 获取检测结果
        boxes = semantic_results[0].boxes
        masks = semantic_results[0].masks
        
        if boxes is not None:
            for i, box in enumerate(boxes):
                # 获取置信度
                confidence = float(box.conf[0].cpu().numpy())
                
                # 保留置信度过滤逻辑，但模型已经过滤过一次，这里作为双重保障
                if confidence >= YOLOE_CONFIDENCE_THRESHOLD:
                    # 获取边界框坐标
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    # 保留两位小数
                    bbox = [round(coord, 2) for coord in bbox]
                    
                    # 创建结果字典
                    result_item = {
                        "bbox": bbox,
                        "confidence": confidence
                    }
                    
                    # 如果有掩码数据，添加掩码信息
                    if masks is not None and i < len(masks.data):
                        mask_data = masks.data[i].cpu().numpy()
                        result_item["mask"] = mask_data
                    
                    output_data.append(result_item)
    
    # 如果使用了裁剪图，将结果坐标映射回原图
    if run_image is not None and crop_w and crop_h:
        adjusted_results = []
        for item in output_data:
            bbox = item["bbox"]
            x1, y1, x2, y2 = bbox
            # 将坐标映射回原图
            orig_x1 = x1 + shift_x
            orig_y1 = y1 + shift_y
            orig_x2 = x2 + shift_x
            orig_y2 = y2 + shift_y
            
            adjusted_item = {
                "bbox": [orig_x1, orig_y1, orig_x2, orig_y2],
                "confidence": item["confidence"]
            }
            
            # 如果有掩码数据，需要调整掩码坐标
            if "mask" in item:
                mask = item["mask"]
                # 预先读取原图尺寸以避免重复 I/O
                img0 = cv2.imread(image_path)
                if img0 is not None:
                    orig_h, orig_w = img0.shape[:2]
                    # 将掩码缩放到裁剪图尺寸（crop_h, crop_w），再贴回原图
                    target_w = int(crop_w)
                    target_h = int(crop_h)
                    if mask.shape[1] != target_w or mask.shape[0] != target_h:
                        try:
                            mask_resized = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
                        except Exception:
                            mask_resized = mask
                    else:
                        mask_resized = mask

                    full_mask = np.zeros((orig_h, orig_w), dtype=mask_resized.dtype)
                    x_start = int(shift_x)
                    y_start = int(shift_y)
                    x_end = min(x_start + target_w, orig_w)
                    y_end = min(y_start + target_h, orig_h)
                    paste_h = max(0, y_end - y_start)
                    paste_w = max(0, x_end - x_start)
                    if paste_h > 0 and paste_w > 0:
                        full_mask[y_start:y_end, x_start:x_end] = mask_resized[:paste_h, :paste_w]
                    adjusted_item["mask"] = full_mask
            
            adjusted_results.append(adjusted_item)
        
        output_data = adjusted_results
    
    # 处理和显示结果
    if output_data:
        logger.info(f"检测到 {len(output_data)} 个目标")
        # 仅在调试模式下打印详细信息
        if logger.isEnabledFor(logging.DEBUG):
            for i, data in enumerate(output_data):
                logger.debug(f"目标 {i+1}: 置信度={data['confidence']:.4f}, 边界框={data['bbox']}, 掩码={'有' if 'mask' in data else '无'}")
    else:
        logger.info("未检测到目标")
    
    return output_data

