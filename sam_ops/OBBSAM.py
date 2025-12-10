import os
import sys
import threading
import logging
import time
from PyQt6.QtCore import QObject, pyqtSignal, QPoint
import numpy as np
import torch
import cv2
from services.global_model_loader import get_global_model_loader
from io_ops.clean import cleansampoint
from app_ui.draw_jk import _get_visible_image_rect
from app_ui.remote_sensing import is_remote_sensing_enabled
from app_ui.scan_animation import get_scan_animation_manager

logger = logging.getLogger(__name__)

class SAMInferenceManager(QObject):
    """SAM推理管理器，负责处理OBB模式下的SAM推理"""
    
    # 信号定义
    inference_started = pyqtSignal()  # 推理开始信号
    inference_completed = pyqtSignal(object)  # 推理完成信号，传递结果
    inference_error = pyqtSignal(str)  # 推理错误信号
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.model = None
        self.current_points = []  # 存储当前点击的点
        self.current_labels = []  # 存储当前点的标签（1为正点，0为负点）
        self.current_bbox = None  # 存储当前BBOX坐标 [x1, y1, x2, y2]
        self.is_inference_running = False  # 推理是否正在进行中
        self.last_dense_polygons = []  # 最近一次推理得到的致密多边形
        self._get_model_from_global_loader()
    
    def _get_model_from_global_loader(self):
        """从全局模型加载器获取SAM模型"""
        try:
            # 获取全局模型加载器实例
            global_loader = get_global_model_loader()
            
            # 从全局加载器获取SAM模型
            self.model = global_loader.get_model("sam")
            
            if self.model is None:
                logger.warning("全局模型加载器中未找到SAM模型，OBB模式SAM功能将不可用")
            else:
                logger.info("从全局模型加载器成功获取SAM模型")
        except Exception as e:
            logger.error(f"从全局模型加载器获取SAM模型失败: {e}，OBB模式SAM功能将不可用")
            self.model = None
    
    
    
    def add_point(self, point, is_positive=True):
        """添加一个点（左键为正点，右键为负点）"""
        try:
            parent_selected = None
            if self.main_window and hasattr(self.main_window, 'parent_label_list') and self.main_window.parent_label_list:
                try:
                    parent_selected = self.main_window.parent_label_list.get_selected()
                except Exception:
                    parent_selected = None
            if not parent_selected:
                logger.warning("未选中父标签，禁止添加点输入")
                self.inference_error.emit("未选中父标签")
                return
        except Exception:
            pass
        # 检查模型是否已加载
        if not self.model:
            logger.warning("OBB模式SAM模型未加载，无法添加点")
            self.inference_error.emit("OBB模式SAM模型未加载，请等待模型加载完成")
            return
            
        # 添加点，无论是否正在运行推理
        self.current_points.append([point.x(), point.y()])
        self.current_labels.append(1 if is_positive else 0)
        
        # 记录添加的点
        logger.info(f"添加点击点: 坐标=({point.x()}, {point.y()}), 类型={'正点' if is_positive else '负点'}")
        
        # 如果有至少一个正点，且当前没有推理在运行，则开始推理
        if 1 in self.current_labels and not self.is_inference_running:
            self.start_inference()
    
    def clear_points(self):
        """清除所有点"""
        self.current_points = []
        self.current_labels = []
        self.current_bbox = None
        logger.info("已清除所有点击点")
    
    def reset_for_new_inference(self):
        """重置状态，准备新的推理"""
        self.clear_points()
        self.is_inference_running = False
        logger.info("已重置推理状态")

    def add_bbox(self, x1, y1, x2, y2):
        """添加BBOX坐标并触发推理"""
        try:
            parent_selected = None
            if self.main_window and hasattr(self.main_window, 'parent_label_list') and self.main_window.parent_label_list:
                try:
                    parent_selected = self.main_window.parent_label_list.get_selected()
                except Exception:
                    parent_selected = None
            if not parent_selected:
                logger.warning("未选中父标签，禁止添加BBOX输入")
                self.inference_error.emit("未选中父标签")
                return
        except Exception:
            pass
        if not self.model:
            logger.warning("OBB模式SAM模型未加载，无法添加BBOX")
            self.inference_error.emit("OBB模式SAM模型未加载，请等待模型加载完成")
            return
        self.current_bbox = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
        logger.info(f"添加BBOX坐标: ({self.current_bbox[0]:.2f}, {self.current_bbox[1]:.2f}) -> ({self.current_bbox[2]:.2f}, {self.current_bbox[3]:.2f})")
        if not self.is_inference_running:
            self.start_inference()
    
    def start_inference(self):
        """开始OBB模式下的SAM推理"""
        if not self.model:
            logger.warning("OBB模式SAM模型未加载，无法执行推理")
            self.inference_error.emit("OBB模式SAM模型未从全局加载器获取，请检查全局模型加载状态")
            return
            
        if not self.current_points and self.current_bbox is None:
            return
        
        if self.is_inference_running:
            logger.warning("OBB模式SAM推理正在进行中，请等待完成")
            return
        
        # 获取当前图片路径
        current_image_path = None
        if self.main_window and hasattr(self.main_window, 'images') and self.main_window.images:
            current_index = self.main_window.resource_list.currentRow()
            if 0 <= current_index < len(self.main_window.images):
                current_image_path = self.main_window.images[current_index]
        
        if not current_image_path or not os.path.exists(current_image_path):
            logger.error("无法获取当前图片路径")
            self.inference_error.emit("无法获取当前图片路径")
            return
        
        # 在后台线程中运行推理（主线程先抓取可视裁剪信息，避免跨线程访问UI）
        self.is_inference_running = True
        # 发送推理开始信号
        self.inference_started.emit()
        ui_crop_info = None
        try:
            remote_enabled = bool(is_remote_sensing_enabled())
        except Exception:
            remote_enabled = False

        if remote_enabled and self.main_window and hasattr(self.main_window, 'canvas') and self.main_window.canvas:
            try:
                view = self.main_window.canvas
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
                            ui_crop_info = {
                                'shift_x': int(crop_rect.x()),
                                'shift_y': int(crop_rect.y()),
                                'crop_w': int(crop_rect.width()),
                                'crop_h': int(crop_rect.height()),
                                'img_w': img_w,
                                'img_h': img_h,
                            }
            except Exception:
                ui_crop_info = None
        try:
            if self.main_window and hasattr(self.main_window, 'canvas') and self.main_window.canvas:
                get_scan_animation_manager(self.main_window.canvas).start_scan_animation()
        except Exception:
            pass
        threading.Thread(
            target=self._run_inference,
            args=(current_image_path, ui_crop_info),
            daemon=True
        ).start()

    def _run_inference(self, image_path, ui_crop_info=None):
        """在后台线程中运行OBB模式下的SAM推理"""
        try:
            logger.info(f"开始OBB模式SAM推理，图片路径: {image_path}")
            logger.info(f"输入点: {self.current_points}")
            logger.info(f"输入标签: {self.current_labels}")
            if self.current_bbox:
                logger.info(f"输入BBOX: {self.current_bbox}")
            
            # 保存当前点用于推理，因为推理过程中可能会有新的点添加
            inference_points = self.current_points.copy()
            inference_labels = self.current_labels.copy()
            inference_bbox = self.current_bbox.copy() if self.current_bbox else None
            
            # 遥感模式：使用主线程捕获的可视区域信息进行文件级裁剪，避免跨线程访问UI
            remote_enabled = False
            try:
                remote_enabled = bool(is_remote_sensing_enabled())
            except Exception:
                remote_enabled = False

            use_cropped_path = None
            shift_x = 0
            shift_y = 0
            crop_w = None
            crop_h = None
            run_image = None

            if remote_enabled and ui_crop_info:
                try:
                    shift_x = int(ui_crop_info.get('shift_x', 0))
                    shift_y = int(ui_crop_info.get('shift_y', 0))
                    crop_w = int(ui_crop_info.get('crop_w', 0))
                    crop_h = int(ui_crop_info.get('crop_h', 0))
                    if crop_w > 0 and crop_h > 0:
                        img = cv2.imread(image_path)
                        if img is not None:
                            h, w = img.shape[:2]
                            x0 = max(0, min(shift_x, w - 1))
                            y0 = max(0, min(shift_y, h - 1))
                            x1 = max(0, min(shift_x + crop_w, w))
                            y1 = max(0, min(shift_y + crop_h, h))
                            if x1 > x0 and y1 > y0:
                                crop = img[y0:y1, x0:x1]
                                ts = int(time.time() * 1000)
                                temp_dir = os.path.join(os.getcwd(), 'temp_crops')
                                os.makedirs(temp_dir, exist_ok=True)
                                proposed_path = os.path.join(temp_dir, f'sam_obb_crop_{ts}.png')
                                should_save = False
                                adj_points = []
                                adj_labels = []
                                for (x, y), lab in zip(inference_points, inference_labels):
                                    ax = int(x - shift_x)
                                    ay = int(y - shift_y)
                                    if 0 <= ax < (x1 - x0) and 0 <= ay < (y1 - y0):
                                        adj_points.append([ax, ay])
                                        adj_labels.append(lab)
                                if 1 in adj_labels:
                                    inference_points = adj_points
                                    inference_labels = adj_labels
                                    use_cropped_path = proposed_path
                                    run_image = crop
                                    should_save = True
                                else:
                                    use_cropped_path = None

                                if inference_bbox:
                                    bbox_x1 = max(0, min(inference_bbox[0] - shift_x, crop_w))
                                    bbox_y1 = max(0, min(inference_bbox[1] - shift_y, crop_h))
                                    bbox_x2 = max(0, min(inference_bbox[2] - shift_x, crop_w))
                                    bbox_y2 = max(0, min(inference_bbox[3] - shift_y, crop_h))
                                    if bbox_x2 <= bbox_x1 or bbox_y2 <= bbox_y1:
                                        use_cropped_path = None
                                    else:
                                        inference_bbox = [bbox_x1, bbox_y1, bbox_x2, bbox_y2]
                                        use_cropped_path = proposed_path
                                        run_image = crop
                                        should_save = True
                            
                            else:
                                use_cropped_path = None
                        else:
                            use_cropped_path = None
                except Exception as _e:
                    logger.warning(f"遥感模式可视裁剪过程异常，回退原图: {_e}")
                    use_cropped_path = None

            run_path = use_cropped_path if use_cropped_path else image_path
            if run_image is None:
                try:
                    run_image = cv2.imread(image_path)
                except Exception:
                    run_image = None
            # 根据输入类型选择推理方式
            if inference_bbox:
                try:
                    image_obj = run_image if run_image is not None else (cv2.imread(run_path) if cv2 is not None else None)
                    if image_obj is None:
                        results = self.model(run_path, bboxes=[inference_bbox])
                    else:
                        results = self.model(image_obj, bboxes=[inference_bbox])
                except Exception as e:
                    logger.error(f"BBOX推理失败: {e}")
                    results = self.model(run_path, bboxes=[inference_bbox])
            else:
                try:
                    image_obj = run_image if run_image is not None else (cv2.imread(run_path) if cv2 is not None else None)
                    if image_obj is None:
                        results = self.model(run_path, points=[inference_points], labels=[inference_labels])
                    else:
                        results = self.model(image_obj, points=[inference_points], labels=[inference_labels])
                except Exception as e:
                    logger.error(f"点推理失败: {e}")
                    results = self.model(run_path, points=[inference_points], labels=[inference_labels])
            
            # 调试信息
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"OBB模式SAM推理结果: 图片={os.path.basename(image_path)}, 输入点数={len(inference_points)}, 结果数={len(results) if results else 0}")
            
            # 映射结果坐标到原图：调整 masks.xy 偏移，并将 masks.data 填充到原图尺寸
            try:
                if use_cropped_path and results and len(results) > 0 and crop_w and crop_h:
                    # 原图尺寸使用主线程传入的 ui_crop_info 中的 img_w/img_h，避免子线程访问UI
                    orig_w = None
                    orig_h = None
                    try:
                        if ui_crop_info:
                            orig_w = int(ui_crop_info.get('img_w')) if ui_crop_info.get('img_w') is not None else None
                            orig_h = int(ui_crop_info.get('img_h')) if ui_crop_info.get('img_h') is not None else None
                    except Exception:
                        orig_w = None
                        orig_h = None

                    for res in results:
                        try:
                            if hasattr(res, 'masks') and res.masks is not None:
                                # 调整 xy 顶点偏移
                                if hasattr(res.masks, 'xy') and res.masks.xy is not None:
                                    new_xy = []
                                    for poly in res.masks.xy:
                                        poly_arr = np.asarray(poly, dtype=np.float32)
                                        poly_arr[:, 0] = poly_arr[:, 0] + float(shift_x)
                                        poly_arr[:, 1] = poly_arr[:, 1] + float(shift_y)
                                        new_xy.append(poly_arr.tolist())
                                    try:
                                        res.masks.xy = new_xy
                                    except Exception:
                                        pass
                                # 填充 data 到原图尺寸
                                if hasattr(res.masks, 'data') and res.masks.data is not None and orig_w and orig_h:
                                    full_masks = []
                                    for mk in res.masks.data:
                                        mk_np = mk.cpu().numpy() if hasattr(mk, 'cpu') else np.array(mk)
                                        if mk_np.dtype != np.uint8:
                                            mk_bin = (mk_np > 0.5).astype(np.uint8)
                                        else:
                                            mk_bin = (mk_np > 0).astype(np.uint8)
                                        full = np.zeros((int(orig_h), int(orig_w)), dtype=np.uint8)
                                        try:
                                            full[int(shift_y):int(shift_y)+int(crop_h), int(shift_x):int(shift_x)+int(crop_w)] = mk_bin
                                        except Exception:
                                            h, w = mk_bin.shape[:2]
                                            full[int(shift_y):int(shift_y)+int(h), int(shift_x):int(shift_x)+int(w)] = mk_bin
                                        full_masks.append(full)
                                    try:
                                        res.masks.data = full_masks
                                    except Exception:
                                        pass
                        except Exception:
                            pass
            except Exception:
                pass

            try:
                self.obb_rect_axis_aligned = bool(getattr(self.main_window, 'obb_rect_axis_aligned', False)) if self.main_window else False
            except Exception:
                self.obb_rect_axis_aligned = False
            # 发送信号通知主线程
            self.inference_completed.emit(results)
            logger.info("OBB模式SAM推理完成")

            # 生成更致密的多边形轮廓，贴合MASK
            self.last_dense_polygons = self._extract_dense_polygons_from_results(results, max_seg_len=1.5)
            if self.last_dense_polygons:
                logger.debug(f"生成致密多边形数量: {len(self.last_dense_polygons)}; 第一个多边形点数: {len(self.last_dense_polygons[0])}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"OBB模式致密多边形: 数量={len(self.last_dense_polygons)}, 示例点数={len(self.last_dense_polygons[0]) if len(self.last_dense_polygons) > 0 else 0}")
            
            # 清理输入点
            cleansampoint(self)
            
        except Exception as e:
            error_msg = f"OBB模式SAM推理失败: {e}"
            logger.error(error_msg)
            # 仅记录错误日志，不输出到控制台
            self.inference_error.emit(error_msg)
        finally:
            self.is_inference_running = False
            # 不清除所有点，只清除已经用于推理的点
            # 这样用户可以继续添加新的点进行推理
            # 清理显存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            try:
                if self.main_window and hasattr(self.main_window, 'canvas') and self.main_window.canvas:
                    get_scan_animation_manager(self.main_window.canvas).stop_scan_animation()
            except Exception:
                pass

    def _densify_polygon(self, poly_xy: np.ndarray, max_seg_len: float = 1.5):
        """将多边形按边分段插入点，提升点密度。"""
        if poly_xy is None or len(poly_xy) == 0:
            return []
        pts = []
        n = len(poly_xy)
        for i in range(n):
            p0 = poly_xy[i]
            p1 = poly_xy[(i + 1) % n]
            dx = float(p1[0] - p0[0])
            dy = float(p1[1] - p0[1])
            dist = (dx * dx + dy * dy) ** 0.5
            steps = max(1, int(dist // max_seg_len))
            if steps <= 1:
                pts.append([float(p0[0]), float(p0[1])])
            else:
                for t in np.linspace(0.0, 1.0, steps, endpoint=False):
                    x = float(p0[0] + t * dx)
                    y = float(p0[1] + t * dy)
                    pts.append([x, y])
        return pts

    def _extract_dense_polygons_from_results(self, results, max_seg_len: float = 1.5):
        """从SAM结果提取更致密的多边形，首选使用 results[0].masks.xy。"""
        dense_polys = []
        try:
            if results and len(results) > 0 and hasattr(results[0], 'masks') and results[0].masks is not None:
                masks = results[0].masks
                if hasattr(masks, 'xy') and masks.xy is not None:
                    for poly in masks.xy:
                        poly_arr = np.asarray(poly, dtype=np.float32)
                        dense = self._densify_polygon(poly_arr, max_seg_len=max_seg_len)
                        if dense:
                            dense_polys.append(dense)
        except Exception:
            pass
        return dense_polys

# 创建全局SAM推理管理器实例
sam_manager = None

def get_sam_manager(main_window=None):
    """获取全局OBB模式SAM推理管理器实例"""
    global sam_manager
    if sam_manager is None:
        sam_manager = SAMInferenceManager(main_window)
    return sam_manager
