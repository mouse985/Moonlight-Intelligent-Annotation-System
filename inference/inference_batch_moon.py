from typing import List, Dict, Any, Tuple, Union
import numpy as np
from ultralytics.models.yolo.yoloe import YOLOEVPSegPredictor
from services.global_model_loader import get_global_model_loader, initialize_global_models
from inference.yolov_moon import yolov_one, yolov_two, filter_results_by_class, yolov_inference
def batch_yolov_inference(image_path: str,
                          bboxes_prompts: Union[List[List[float]], Dict[str, Any]]) -> Dict[str, Any]:
    """
    批量YOLOV推理（与 vision_prompt 一致）：
    - 第一阶段：对指定图片 `image_path` 与输入矩形框 `bboxes` 使用 yolov_one
    - 第二阶段：若提供 `resource_list`，则对每个资源图片使用 yolov_two，并根据第一阶段类别进行筛选；
                若未提供，则仅在当前 `image_path` 上进行 yolov_two 并筛选。

    Args:
        image_path: 当前图片路径
        bboxes_prompts: 可为矩形框列表 [[x1,y1,x2,y2], ...]，或包含键 {"bboxes": [...], "resource_list": [...]} 的字典

    Returns:
        dict: {
            "success": bool,
            "bbox_list": List[List[float]],  # 当未提供 resource_list 时返回当前图片的筛选后 bbox 列表
            "one_results": List[Dict[str, Any]],
            "two_results": Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]],
            "filtered": Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]],
        }
    """
    # 解析输入格式
    if isinstance(bboxes_prompts, dict):
        bboxes = bboxes_prompts.get("bboxes") or bboxes_prompts.get("prompts") or bboxes_prompts.get("rects") or []
        resource_list = bboxes_prompts.get("resource_list") or []
    else:
        bboxes = bboxes_prompts
        resource_list = []

    # 基本校验
    if not isinstance(bboxes, list) or len(bboxes) == 0:
        return {
            "success": False,
            "bbox_list": [],
            "one_results": [],
            "two_results": [] if not resource_list else {},
            "filtered": [] if not resource_list else {},
            "error": "未提供有效的矩形框提示"
        }

    # 第一阶段：yolov_one（按类别提取 ROI）
    one_results, one_success = yolov_one(bboxes, image_path)
    # 若第一阶段遍历权重后仍无结果，则直接返回并不进行第二次推理
    if not one_success:
        # 回退到 YOLOE：将 vision prompt 的矩形框直接作为视觉提示传给 YOLOE
        if resource_list:
            yoloe_res = batch_yoloe_inference(
                refer_image_path=image_path,
                bboxes_prompts=bboxes,
                resource_list=resource_list,
                cls_ids=None,
            )
            return {
                "success": bool(yoloe_res.get("success")),
                "bbox_list": [],
                "one_results": one_results,
                # 在批量场景中，用 YOLOE 的 results_map 作为 two_results 返回，保持键类型为 Dict[str, List[...]]
                "two_results": yoloe_res.get("results_map", {}),
                # 无需 YOLOV 类别筛选，此处返回空映射
                "filtered": {},
                "fallback": "yoloe",
                "yoloe_result": yoloe_res,
            }
        else:
            # 无资源列表则仅对当前图片进行 YOLOE 推理
            yoloe_res = batch_yoloe_inference(
                refer_image_path=image_path,
                bboxes_prompts=bboxes,
                resource_list=[image_path],
                cls_ids=None,
            )
            rmap = yoloe_res.get("results_map", {})
            items = rmap.get(image_path, [])
            bbox_list = [item["bbox"] for item in items if isinstance(item, dict) and "bbox" in item]
            return {
                "success": bool(len(bbox_list) > 0),
                "bbox_list": bbox_list,
                "one_results": one_results,
                "two_results": [],
                "filtered": [],
                "fallback": "yoloe",
                "yoloe_result": yoloe_res,
            }

    # 若提供资源列表：对每个资源运行第二阶段并筛选
    if resource_list:
        two_results_map: Dict[str, List[Dict[str, Any]]] = {}
        filtered_map: Dict[str, List[Dict[str, Any]]] = {}
        for res_path in resource_list:
            try:
                two = yolov_two(res_path)
            except Exception:
                two = []
            two_results_map[res_path] = two or []
            filtered_map[res_path] = filter_results_by_class(one_results, two or [])
        # 聚合是否成功（任一资源有匹配即视为成功）
        any_bbox = any(len([item.get('bbox') for item in filtered_map.get(p, []) if isinstance(item, dict) and 'bbox' in item]) > 0 for p in filtered_map)
        return {
            "success": bool(any_bbox),
            "bbox_list": [],
            "one_results": one_results,
            "two_results": two_results_map,
            "filtered": filtered_map,
        }

    # 未提供资源列表：在当前图片运行第二阶段并筛选（等价于 yolov_inference）
    try:
        bbox_list, ok = yolov_inference(bboxes, image_path)
    except Exception:
        bbox_list, ok = [], False
    # 同时返回详细的 one/two/filtered 以便调试或上层使用
    two_results = yolov_two(image_path)
    filtered = filter_results_by_class(one_results, two_results)
    return {
        "success": bool(ok),
        "bbox_list": bbox_list,
        "one_results": one_results,
        "two_results": two_results,
        "filtered": filtered,
    }
from yoloe_moon import YOLOE_CONFIDENCE_THRESHOLD    
def batch_yoloe_inference(
    refer_image_path: str,
    bboxes_prompts: Union[List[List[float]], Dict[str, Any]],
    resource_list: List[str],
    cls_ids: Union[List[int], None] = None,
) -> Dict[str, Any]:
    """
    使用 vision_prompt 界面加载的图片作为参考图（refer_image），将其上绘制的矩形框作为视觉提示，
    然后对资源列表中的所有图片依次进行 YOLOE 推理。

    Args:
        refer_image_path: 参考图（vision_prompt 当前图）的路径。
        bboxes_prompts: 矩形框提示列表，或包含键 {"bboxes": [...]} 的字典。
        resource_list: 资源列表中的目标图片路径列表，按顺序推理。
        cls_ids: 对应每个矩形框的类别ID列表，可选；未提供时默认全部为0。

    Returns:
        dict: {
            "success": bool,                # 是否至少有一张图片检测到结果
            "refer_image": str,             # 参考图路径
            "bboxes": List[List[float]],    # 使用的矩形框提示
            "results_map": Dict[str, List[Dict[str, Any]]],  # 每张图片的检测结果
            "processed": int,               # 已推理的图片数量
            "total": int,                   # 资源列表总数
        }
    """

    # 解析输入提示格式
    if isinstance(bboxes_prompts, dict):
        bboxes = bboxes_prompts.get("bboxes") or bboxes_prompts.get("prompts") or bboxes_prompts.get("rects") or []
    else:
        bboxes = bboxes_prompts

    if not isinstance(bboxes, list) or len(bboxes) == 0:
        return {
            "success": False,
            "refer_image": refer_image_path,
            "bboxes": [],
            "results_map": {},
            "processed": 0,
            "total": len(resource_list) if isinstance(resource_list, list) else 0,
            "error": "未提供有效的矩形框提示"
        }

    # 使用全局加载器获取YOLOE模型（若未加载则初始化）
    loader = get_global_model_loader()
    model = loader.get_model("yoloe")
    if model is None:
        initialize_global_models()
        model = loader.get_model("yoloe")
        if model is None:
            return {
                "success": False,
                "refer_image": refer_image_path,
                "bboxes": bboxes,
                "results_map": {},
                "processed": 0,
                "total": len(resource_list) if isinstance(resource_list, list) else 0,
                "error": "YOLOE 模型尚未通过全局加载器加载"
            }

    # 类别ID对齐：若未提供则默认0；长度与bboxes一致
    if cls_ids is None or not isinstance(cls_ids, list) or len(cls_ids) != len(bboxes):
        cls_ids = [0] * len(bboxes)

    # 构建视觉提示
    visual_prompts = dict(
        bboxes=np.array(bboxes, dtype=np.float32),
        cls=np.array(cls_ids, dtype=np.int32),
    )

    # 统一资源列表：若未提供或为空，则回退到仅对参考图进行推理
    res_list = resource_list if isinstance(resource_list, list) and len(resource_list) > 0 else [refer_image_path]
    results_map: Dict[str, List[Dict[str, Any]]] = {}
    processed = 0
    total = len(res_list)

    # 顺序推理资源列表中的每张图片（使用参考图+视觉提示）
    for img_path in res_list:
            try:
                results = model.predict(
                    img_path,
                    refer_image=refer_image_path,
                    visual_prompts=visual_prompts,
                    predictor=YOLOEVPSegPredictor,
                    conf=0.1,
                )

                # 解析结果为标准结构（bbox/conf/mask）
                img_items: List[Dict[str, Any]] = []
                if results and len(results) > 0:
                    boxes = getattr(results[0], 'boxes', None)
                    masks = getattr(results[0], 'masks', None)
                    if boxes is not None:
                        for i, box in enumerate(boxes):
                            try:
                                conf = float(box.conf[0].cpu().numpy())
                            except Exception:
                                conf = 0.0
                            try:
                                xyxy = box.xyxy[0].cpu().numpy().tolist()
                                xyxy = [round(float(v), 2) for v in xyxy]
                            except Exception:
                                xyxy = []
                            item: Dict[str, Any] = {}
                            if xyxy:
                                item["bbox"] = xyxy
                            item["confidence"] = conf
                            # 可选添加mask
                            try:
                                if masks is not None and i < len(masks.data):
                                    item["mask"] = masks.data[i].cpu().numpy()
                            except Exception:
                                pass
                            if "bbox" in item:
                                img_items.append(item)
                results_map[img_path] = img_items
            except Exception:
                # 单张失败则置空列表，但继续下一个
                results_map[img_path] = []
            finally:
                processed += 1

    success = any(len(v) > 0 for v in results_map.values())
    return {
        "success": bool(success),
        "refer_image": refer_image_path,
        "bboxes": bboxes,
        "results_map": results_map,
        "processed": processed,
        "total": total,
    }
