import os
import sys
import threading
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QPoint, QRectF, QTimer
from PyQt6.QtGui import QImage
import numpy as np
import torch
try:
    import cv2
except Exception:
    cv2 = None
from services.global_model_loader import get_global_model_loader
from io_ops.clean import cleansampoint
from app_ui.scan_animation import get_scan_animation_manager

logger = logging.getLogger(__name__)

class SAMInferenceManager(QObject):
    """SAM推理管理器，负责处理SAM推理"""
    
    # 信号定义
    inference_started = pyqtSignal()  # 推理开始信号
    inference_completed = pyqtSignal(object)  # 推理完成信号，传递结果
    inference_error = pyqtSignal(str)  # 推理错误信号
    # 当解析出 polygon points 时发出该信号，payload 为 dict: {"polygon_points": ..., "image_info": ..., "selected_parent": ..., "parent_label_list": ..., "canvas_view": ...}
    polygon_detected = pyqtSignal(object)
    
    def __init__(self):
        super().__init__()
        self.main_window = None
        self.model = None
        self.current_bbox = None  # 存储当前矩形框 [x1, y1, x2, y2]
        self.current_image_path = None  # 存储当前图片路径
        self.is_inference_running = False  # 推理是否正在进行中
        self._get_model_from_global_loader()
    
    def set_image_path(self, image_path):
        """设置图片路径
        Args:
            image_path: 图片路径
        """
        self.current_image_path = image_path
        logger.info(f"设置图片路径: {image_path}")
    
    def _get_model_from_global_loader(self):
        """从全局模型加载器获取SAM模型"""
        try:
            mobile_candidates = [
            os.path.join(os.getcwd(), 'models', 'weights', 'SAMmodels', 'SAM2', 'mobile_sam.pt')
            ]
            try:
                if hasattr(sys, 'frozen') and sys.frozen:
                    mobile_candidates.append(os.path.join(os.path.dirname(sys.executable), 'models', 'weights', 'SAMmodels', 'SAM2', 'mobile_sam.pt'))
            except Exception:
                pass
            mobile_path = None
            for p in mobile_candidates:
                if os.path.exists(p):
                    mobile_path = p
                    break
            if mobile_path:
                try:
                    from ultralytics import SAM
                    self.model = SAM(mobile_path)
                    logger.info(f"矩形框模式固定使用MobileSAM: {mobile_path}")
                    return
                except Exception as ie:
                    logger.warning(f"加载MobileSAM失败，回退全局模型: {ie}")
            try:
                smallest_path = None
                smallest_size = None
                sam2_dirs = [
                    os.path.join(os.getcwd(), 'models', 'weights', 'SAMmodels', 'SAM2')
                ]
                if hasattr(sys, 'frozen') and sys.frozen:
                    sam2_dirs.append(os.path.join(os.path.dirname(sys.executable), 'models', 'weights', 'SAMmodels', 'SAM2'))
                for d in sam2_dirs:
                    if os.path.isdir(d):
                        for f in os.listdir(d):
                            if f.endswith('.pt'):
                                p = os.path.join(d, f)
                                try:
                                    sz = os.path.getsize(p)
                                except Exception:
                                    sz = None
                                if sz is not None and (smallest_size is None or sz < smallest_size):
                                    smallest_path = p
                                    smallest_size = sz
                if smallest_path:
                    from ultralytics import SAM
                    self.model = SAM(smallest_path)
                    logger.info(f"矩形框模式使用SAM2最小权重: {smallest_path}")
                    return
            except Exception:
                pass
            global_loader = get_global_model_loader()
            self.model = global_loader.get_model("sam")
            if self.model is None:
                logger.warning("全局模型加载器中未找到SAM模型，矩形框模式SAM功能将不可用")
            else:
                logger.info("从全局模型加载器成功获取SAM模型")
        except Exception as e:
            logger.error(f"从全局模型加载器获取SAM模型失败: {e}，矩形框模式SAM功能将不可用")
            self.model = None
    
    def set_bbox(self, bbox):
        """设置矩形框
        Args:
            bbox: 矩形框，格式为 [x1, y1, x2, y2] 或 QRectF
        """
        # 检查模型是否已加载
        if not self.model:
            logger.warning("SAM模型未加载，无法设置矩形框")
            self.inference_error.emit("SAM模型未加载，请等待模型加载完成")
            return False
        
        # 转换QRectF为列表格式
        if isinstance(bbox, QRectF):
            self.current_bbox = [
                bbox.left(),
                bbox.top(),
                bbox.right(),
                bbox.bottom()
            ]
        else:
            self.current_bbox = bbox
        
        # 记录设置的矩形框
        logger.info(f"设置矩形框: 坐标={self.current_bbox}")
        
        # 开始推理
        if not self.is_inference_running:
            self.start_inference()
        
        return True
    
    def clear_bbox(self):
        """清除矩形框"""
        self.current_bbox = None
        logger.info("已清除矩形框")
    
    def clear_points(self):
        """清理SAM推理输入点（为了兼容cleansampoint函数）"""
        # 在矩形框模式下，我们不需要清理点，但为了兼容性提供此方法
        logger.info("SAM推理输入点清理（无操作）")
    
    def reset_for_new_inference(self):
        """重置状态，准备新的推理"""
        self.clear_bbox()
        self.is_inference_running = False
        logger.info("已重置推理状态")
    
    def start_inference(self):
        """开始SAM推理"""
        if not self.model:
            logger.warning("SAM模型未加载，无法执行推理")
            self.inference_error.emit("SAM模型未从全局加载器获取，请检查全局模型加载状态")
            return
            
        if not self.current_bbox:
            logger.warning("未设置矩形框，无法执行推理")
            return
        
        if self.is_inference_running:
            logger.warning("SAM推理正在进行中，请等待完成")
            return
        
        # 使用设置的图片路径
        current_image_path = self.current_image_path
        
        if not current_image_path or not os.path.exists(current_image_path):
            logger.error("无法获取当前图片路径")
            self.inference_error.emit("无法获取当前图片路径")
            return
        
        # 在后台线程中运行推理
        self.is_inference_running = True
        # 发送推理开始信号
        self.inference_started.emit()
        threading.Thread(
            target=self._run_inference,
            args=(current_image_path,),
            daemon=True
        ).start()
    
    def _run_inference(self, image_path):
        """在后台线程中运行SAM推理"""
        try:
            logger.info(f"开始SAM推理，图片路径: {image_path}")
            logger.info(f"输入矩形框: {self.current_bbox}")
            
            # 保存当前矩形框用于推理
            inference_bbox = self.current_bbox.copy()
            
            # 运行推理
            with torch.no_grad():
                image_obj = None
                try:
                    if cv2 is not None:
                        image_obj = cv2.imread(image_path)
                except Exception:
                    image_obj = None
                if image_obj is not None:
                    results = self.model(image_obj, bboxes=[inference_bbox])
                else:
                    results = self.model(image_path, bboxes=[inference_bbox])
            
            # 调试信息
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"SAM推理结果: 图片={image_path}, BBOX={inference_bbox}, 结果摘要={str(results)[:200] if results is not None else 'None'}")
            
            # 发送信号通知主线程
            self.inference_completed.emit(results)
            logger.info("SAM推理完成")
            
            # 清理输入矩形框
            cleansampoint(self)
            
        except Exception as e:
            error_msg = f"SAM推理失败: {e}"
            logger.error(error_msg)
            # 仅记录错误日志，不输出到控制台
            self.inference_error.emit(error_msg)
        finally:
            self.is_inference_running = False
            # 不清除矩形框，允许用户继续使用同一矩形框进行推理
            # 清理显存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def process_yolov_bboxes_for_polygon(self, bbox_list, image_info, selected_parent, parent_label_list, canvas_view):
        """在后台线程中处理 YOLOV 的 bbox 列表，针对每个 bbox 调用 SAM，使用 SAM 输出的 mask 提取多边形并创建子标签。

        仅在多边形模式下使用此方法。该方法会在内部异步运行，结果通过创建子标签体现。
        Args:
            bbox_list: list of bbox, each is [x1,y1,x2,y2]
            image_info: 图片路径
            selected_parent: 父标签对象
            parent_label_list: 父标签列表对象
            canvas_view: 画布视图对象（用于尺寸映射）
        """
        if not bbox_list:
            logger.info("没有要处理的 YOLOV bbox")
            return

        if self.model is None:
            logger.warning("SAM 模型未加载，无法对 YOLOV bbox 执行 SAM")
            return

        # 启动扫描动画（在主线程中）
        try:
            scan_mgr = get_scan_animation_manager(canvas_view)
            if scan_mgr:
                scan_mgr.start_scan_animation()
        except Exception:
            pass

        # 在后台线程中顺序处理每个 bbox，避免 UI 阻塞
        threading.Thread(
            target=self._process_bboxes_thread,
            args=(bbox_list, image_info, selected_parent, parent_label_list, canvas_view),
            daemon=True
        ).start()

    def _process_bboxes_thread(self, bbox_list, image_info, selected_parent, parent_label_list, canvas_view):
        try:
            for bbox in bbox_list:
                try:
                    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
                        logger.warning(f"跳过无效 bbox: {bbox}")
                        continue

                    # 读取图像尺寸以便裁剪 bbox
                    img_w = None
                    img_h = None
                    try:
                        if canvas_view and hasattr(canvas_view, 'current_pixmap') and canvas_view.current_pixmap:
                            img_w = float(canvas_view.current_pixmap.width())
                            img_h = float(canvas_view.current_pixmap.height())
                        else:
                            qimg = QImage(image_info)
                            if not qimg.isNull():
                                img_w = float(qimg.width())
                                img_h = float(qimg.height())
                    except Exception:
                        img_w = None
                        img_h = None

                    # 复制并规范化 bbox
                    try:
                        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                    except Exception:
                        logger.warning(f"无效 bbox 格式，跳过: {bbox}")
                        continue

                    # 如果有图像尺寸信息则裁剪并取整
                    if img_w is not None and img_h is not None:
                        # padding: 2% 的宽/高，最少 3 像素
                        pad_w = max(3, int(0.02 * max(1, x2 - x1)))
                        pad_h = max(3, int(0.02 * max(1, y2 - y1)))

                        xi1 = max(0, int(x1) - pad_w)
                        yi1 = max(0, int(y1) - pad_h)
                        xi2 = min(int(img_w) - 1, int(x2) + pad_w)
                        yi2 = min(int(img_h) - 1, int(y2) + pad_h)
                    else:
                        # 没有图像尺寸则仅取整并做基本有效性检查
                        xi1 = int(round(x1))
                        yi1 = int(round(y1))
                        xi2 = int(round(x2))
                        yi2 = int(round(y2))

                    # 确保 bbox 有效
                    if xi2 <= xi1 or yi2 <= yi1:
                        logger.warning(f"裁剪后 bbox 无效，跳过: {[xi1, yi1, xi2, yi2]} 原始: {bbox}")
                        continue

                    sanitized_bbox = [xi1, yi1, xi2, yi2]
                    logger.info(f"对 bbox 运行 SAM (sanitized): {sanitized_bbox}, image_size=({img_w},{img_h})")

                    # 调用 SAM 推理（单个 bbox）
                    with torch.no_grad():
                        image_obj = None
                        try:
                            if cv2 is not None:
                                image_obj = cv2.imread(image_info)
                        except Exception:
                            image_obj = None
                        if image_obj is not None:
                            results = self.model(image_obj, bboxes=[sanitized_bbox])
                        else:
                            results = self.model(image_info, bboxes=[sanitized_bbox])

                    # 尝试解析结果中的 mask（增强兼容性：object-like / list-like / dict-like）
                    mask = None

                    def _try_extract_from_obj(obj):
                        try:
                            # object-like (ultralytics-like)
                            if hasattr(obj, 'masks') and hasattr(obj.masks, 'data') and len(obj.masks.data) > 0:
                                first_mask = obj.masks.data[0]
                                # torch tensor
                                if hasattr(first_mask, 'cpu'):
                                    return first_mask.cpu().numpy()
                                # numpy-like
                                if hasattr(first_mask, 'numpy'):
                                    try:
                                        return first_mask.numpy()
                                    except Exception:
                                        pass
                                if isinstance(first_mask, np.ndarray):
                                    return first_mask
                                # list/tuple of arrays
                                if isinstance(first_mask, (list, tuple)) and len(first_mask) > 0:
                                    try:
                                        return np.asarray(first_mask[0])
                                    except Exception:
                                        try:
                                            return np.asarray(first_mask)
                                        except Exception:
                                            return None
                                try:
                                    return np.asarray(first_mask)
                                except Exception:
                                    return None
                        except Exception:
                            return None
                        return None

                    # 1) 尝试 object-like 结果
                    mask = _try_extract_from_obj(results)

                    # 2) 若结果是 list/tuple（某些包装器会返回列表），尝试从第一个元素解析
                    if mask is None and isinstance(results, (list, tuple)) and len(results) > 0:
                        mask = _try_extract_from_obj(results[0])

                    # 3) dict-like 解析（inference_moon 可能 mock 出此结构）
                    if mask is None and isinstance(results, dict):
                        try:
                            masks_obj = results.get('masks')
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

                    # 4) 如果仍未找到 mask，记录更详细的调试信息以便排查
                    if mask is None:
                        try:
                            summary = {
                                'bbox': sanitized_bbox,
                                'results_type': type(results).__name__,
                            }
                            # object-like 属性摘要
                            if hasattr(results, '__dict__'):
                                summary['attrs'] = list(getattr(results, '__dict__').keys())[:10]
                            # dict-like keys
                            if isinstance(results, dict):
                                summary['keys'] = list(results.keys())
                                if 'masks' in results and isinstance(results['masks'], dict):
                                    try:
                                        summary['masks_data_len'] = len(results['masks'].get('data') or [])
                                    except Exception:
                                        summary['masks_data_len'] = 'unknown'
                            # object-like masks.data length
                            try:
                                if hasattr(results, 'masks') and hasattr(results.masks, 'data'):
                                    summary['masks_data_len_obj'] = len(results.masks.data)
                            except Exception:
                                pass
                            logger.info(f"SAM 未返回 mask，摘要: {summary}")
                        except Exception:
                            logger.info(f"SAM 未返回 mask，bbox (sanitized): {sanitized_bbox}")
                        continue

                    # 使用 mask 创建多边形并创建子标签（复用 aotu_rect_pen 的坐标映射逻辑）
                    try:
                        polygon_points = []
                        mask_arr = np.asarray(mask)
                        if mask_arr.dtype != np.uint8:
                            bin_mask = (mask_arr > 0.5).astype(np.uint8) * 255
                        else:
                            bin_mask = (mask_arr > 0).astype(np.uint8) * 255

                        if cv2 is None:
                            logger.warning("cv2 未安装，无法从 mask 提取轮廓，跳过此 bbox")
                            continue

                        # 保留细节点，后续用轻度近似提高贴合度
                        contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
                        if not contours:
                            logger.warning("在 mask 中未找到轮廓，跳过")
                            continue

                        max_cnt = max(contours, key=lambda c: cv2.contourArea(c))
                        area = cv2.contourArea(max_cnt)
                        if area <= 0:
                            logger.warning("找到的最大轮廓面积为0，跳过")
                            continue

                        peri = cv2.arcLength(max_cnt, True)
                        epsilon = max(0.5, 0.002 * peri)
                        approx = cv2.approxPolyDP(max_cnt, epsilon, True)
                        pts = approx.reshape(-1, 2) if approx is not None else []
                        polygon_points_mask = [(float(pt[0]), float(pt[1])) for pt in pts]

                        if not polygon_points_mask:
                            logger.warning("轮廓近似后无顶点，跳过")
                            continue

                        # 映射到图像坐标
                        mask_h, mask_w = bin_mask.shape[:2]
                        img_w = None
                        img_h = None
                        if canvas_view and hasattr(canvas_view, 'current_pixmap') and canvas_view.current_pixmap:
                            try:
                                img_w = float(canvas_view.current_pixmap.width())
                                img_h = float(canvas_view.current_pixmap.height())
                            except Exception:
                                img_w = None
                                img_h = None

                        if img_w is None or img_h is None:
                            try:
                                qimg = QImage(image_info)
                                if not qimg.isNull():
                                    img_w = float(qimg.width())
                                    img_h = float(qimg.height())
                            except Exception:
                                img_w = None
                                img_h = None

                        if img_w is None or img_h is None:
                            img_w = float(mask_w)
                            img_h = float(mask_h)

                        sx = img_w / float(mask_w) if mask_w != 0 else 1.0
                        sy = img_h / float(mask_h) if mask_h != 0 else 1.0

                        polygon_points = [(x_mask * sx, y_mask * sy) for (x_mask, y_mask) in polygon_points_mask]

                        if not polygon_points:
                            logger.warning("映射后无顶点，跳过")
                            continue

                        # 发出 signal，将 polygon 数据交给主线程去创建子标签，避免在后台线程直接操作 UI
                        payload = {
                            'polygon_points': polygon_points,
                            'image_info': image_info,
                            'selected_parent': selected_parent,
                            'parent_label_list': parent_label_list,
                            'canvas_view': canvas_view
                        }
                        try:
                            self.polygon_detected.emit(payload)
                        except Exception as e:
                            logger.error(f"发出 polygon_detected 信号失败: {e}")

                    except Exception as e:
                        logger.error(f"从 SAM mask 创建多边形标签时出错: {e}")

                except Exception as e:
                    logger.error(f"处理单个 bbox 时发生错误: {e}")

            # 完成后触发一次 canvas 更新
            try:
                if canvas_view and hasattr(canvas_view, 'update_rects'):
                    canvas_view.update_rects()
            except Exception:
                pass
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception as e:
            logger.error(f"批量处理 YOLOV bbox 时发生错误: {e}")
        finally:
            # 在主线程停止扫描动画
            try:
                def _stop_animation():
                    mgr = get_scan_animation_manager(canvas_view)
                    if mgr:
                        mgr.stop_scan_animation()
                QTimer.singleShot(0, _stop_animation)
            except Exception:
                pass

# 创建全局SAM推理管理器实例
sam_manager = None

def get_sam_manager():
    """获取全局SAM推理管理器实例"""
    global sam_manager
    if sam_manager is None:
        sam_manager = SAMInferenceManager()
    return sam_manager
