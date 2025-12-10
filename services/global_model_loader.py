import os
import sys
import threading
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QSettings
import numpy as np
from services.sam3_adapter import Sam3Adapter
# 延迟导入ultralytics相关模型，避免未安装库导致启动失败
try:
    import ultralytics  # 仅检测库是否可用
    ULTRALYTICS_INSTALLED = True
except Exception:
    ULTRALYTICS_INSTALLED = False

logger = logging.getLogger(__name__)

class GlobalModelLoader(QObject):
    """全局模型加载器，负责在软件启动时在后台线程加载所有模型"""
    
    # 信号定义
    loading_started = pyqtSignal(str)  # 开始加载信号，传递模型名称
    loading_progress = pyqtSignal(str, int)  # 加载进度信号，传递模型名称和进度百分比
    loading_completed = pyqtSignal(str)  # 加载完成信号，传递模型名称
    loading_error = pyqtSignal(str, str)  # 加载错误信号，传递模型名称和错误信息
    all_models_loaded = pyqtSignal()  # 所有模型加载完成信号
    
    def __init__(self):
        super().__init__()
        self.models = {}
        self.sam_paths = {"sam2": None, "sam3": None}
        self.active_sam_type = None
        self.loading_threads = {}
        self.is_loading = False
        # 用于保护 yolov 模型切换与推理的锁，防止并发切换导致竞态
        self._yolov_lock = threading.RLock()
        # 用于保护 SAM 模型切换与加载的锁
        self._sam_lock = threading.RLock()
        
    def _is_safe_weight(self, path, allowed_dirs, exts=(".pt", ".pth", ".onnx")):
        try:
            if not path:
                return False
            ap = os.path.abspath(path)
            if not os.path.isfile(ap):
                return False
            if os.path.splitext(ap)[1].lower() not in exts:
                return False
            aug_allowed = []
            try:
                if hasattr(sys, "frozen") and sys.frozen:
                    exe_dir = os.path.dirname(sys.executable)
                    aug_allowed.append(exe_dir)
                    aug_allowed.append(os.path.join(exe_dir, "models", "weights"))
                    if hasattr(sys, "_MEIPASS"):
                        aug_allowed.append(os.path.abspath(getattr(sys, "_MEIPASS")))
            except Exception:
                pass
            for d in list(allowed_dirs) + aug_allowed:
                ad = os.path.abspath(d)
                try:
                    if os.path.commonpath([ap, ad]) == ad:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
        
    def load_all_models(self):
        """在后台线程中加载所有模型"""
        # 若正在加载，或已存在任意模型，则避免重复整体加载
        if self.is_loading:
            logger.warning("模型正在加载中，请勿重复调用")
            return
        if any(k in self.models for k in ("sam", "yoloe", "yolov")):
            logger.info("检测到模型已存在，跳过全量加载")
            return
            
        self.is_loading = True
        # 启动后台线程加载模型
        threading.Thread(target=self._load_models_in_background, daemon=True).start()
    
    def _load_models_in_background(self):
        """在后台线程中加载所有模型"""
        try:
            # 加载SAM模型
            self._load_sam_model()
            
            # 加载YOLOE模型
            self._load_yoloe_model()
            
            # 加载YOLO模型
            self._load_yolo_model()
            
            # 发送所有模型加载完成信号
            self.all_models_loaded.emit()
            logger.info("所有模型加载完成")
            
        except Exception as e:
            logger.error(f"加载模型时发生错误: {e}")
        finally:
            self.is_loading = False
    
    def _load_sam_model(self):
        if self.models.get("sam") is not None and (self.models.get("sam2") is not None or self.models.get("sam3") is not None):
            logger.info("SAM模型已存在，跳过重新加载")
            return
        model_name = "SAM"
        self.loading_started.emit(model_name)
        self.loading_progress.emit(model_name, 0)
        try:
            candidate_dirs = [
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels"),
            ]
            if hasattr(sys, "frozen") and sys.frozen:
                candidate_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights", "SAMmodels"))
            search_dirs = []
            for d in candidate_dirs:
                search_dirs.append(d)
                sd2 = os.path.join(d, "SAM2")
                sd3 = os.path.join(d, "SAM3")
                if os.path.isdir(sd2):
                    search_dirs.append(sd2)
                if os.path.isdir(sd3):
                    search_dirs.append(sd3)
            smallest_path = None
            smallest_size = None
            for d in search_dirs:
                try:
                    if os.path.isdir(d):
                        for f in os.listdir(d):
                            if f.endswith(".pt"):
                                p = os.path.join(d, f)
                                try:
                                    sz = os.path.getsize(p)
                                except Exception:
                                    sz = None
                                if sz is not None and (smallest_size is None or sz < smallest_size):
                                    smallest_path = p
                                    smallest_size = sz
                except Exception:
                    pass
            if smallest_path and self._is_safe_weight(smallest_path, candidate_dirs, exts=(".pt",)):
                is_sam3 = os.path.basename(smallest_path).lower().startswith("sam3") or os.path.basename(smallest_path).lower() == "sam3.pt"
                self.loading_progress.emit(model_name, 50)
                with self._sam_lock:
                    if is_sam3:
                        try:
                            model = Sam3Adapter(checkpoint_path=smallest_path)
                            self.models["sam3"] = model
                            self.sam_paths["sam3"] = smallest_path
                            self.models["sam"] = model
                            self.active_sam_type = "sam3"
                        except Exception:
                            for d in search_dirs:
                                try:
                                    if os.path.isdir(d):
                                        candidates = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".pt") and not f.lower().startswith("sam3")]
                                        if candidates:
                                            mp = min(candidates, key=lambda x: os.path.getsize(x))
                                            from ultralytics import SAM
                                            model = SAM(mp)
                                            self.models["sam2"] = model
                                            self.sam_paths["sam2"] = mp
                                            self.models["sam"] = model
                                            self.active_sam_type = "sam2"
                                            break
                                except Exception:
                                    pass
                    else:
                        from ultralytics import SAM
                        model = SAM(smallest_path)
                        self.models["sam2"] = model
                        self.sam_paths["sam2"] = smallest_path
                        self.models["sam"] = model
                        self.active_sam_type = "sam2"
                    try:
                        import torch
                        torch.cuda.empty_cache()
                    except Exception:
                        pass
                self.loading_progress.emit(model_name, 100)
                self.loading_completed.emit(model_name)
                logger.info(f"SAM模型加载成功: {smallest_path}")
                # 尝试预加载另一类型（不改变当前激活模型）
                try:
                    if self.active_sam_type == "sam2":
                        # 预加载SAM3
                        for p in sam3_candidates:
                            if os.path.exists(p) and self._is_safe_weight(p, [
                                repo_root,
                                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels"),
                                os.path.join(os.getcwd(), "models", "weights", "SAMmodels"),
                            ], exts=(".pt",)):
                                with self._sam_lock:
                                    try:
                                        self.models["sam3"] = Sam3Adapter(checkpoint_path=p)
                                        self.sam_paths["sam3"] = p
                                    except Exception:
                                        pass
                                break
                    elif self.active_sam_type == "sam3":
                        # 预加载SAM2：在search_dirs中选体积最小
                        sam2_dir = None
                        for d in search_dirs:
                            if os.path.isdir(d) and os.path.basename(d).lower().endswith("sam2"):
                                sam2_dir = d
                                break
                        if sam2_dir:
                            candidates2 = [os.path.join(sam2_dir, f) for f in os.listdir(sam2_dir) if f.endswith(".pt")]
                            if candidates2:
                                mp = min(candidates2, key=lambda x: os.path.getsize(x))
                                if self._is_safe_weight(mp, candidate_dirs, exts=(".pt",)):
                                    from ultralytics import SAM
                                    with self._sam_lock:
                                        try:
                                            self.models["sam2"] = SAM(mp)
                                            self.sam_paths["sam2"] = mp
                                        except Exception:
                                            pass
                except Exception:
                    pass
                return
            repo_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
            sam3_candidates = [
                os.path.join(repo_root, "sam3.pt"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels", "sam3.pt"),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels", "sam3.pt"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "sam3.pt"),
                os.path.join(os.getcwd(), "models", "weights", "sam3.pt"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels", "SAM3", "sam3.pt"),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels", "SAM3", "sam3.pt"),
            ]
            if hasattr(sys, "frozen") and sys.frozen:
                sam3_candidates.extend([
                    os.path.join(os.path.dirname(sys.executable), "models", "weights", "SAMmodels", "sam3.pt"),
                    os.path.join(os.path.dirname(sys.executable), "models", "weights", "sam3.pt"),
                    os.path.join(os.path.dirname(sys.executable), "sam3.pt"),
                    os.path.join(os.path.dirname(sys.executable), "models", "weights", "SAMmodels", "SAM3", "sam3.pt"),
                ])
            sam3_path = None
            for p in sam3_candidates:
                if os.path.exists(p):
                    sam3_path = p
                    break
            if sam3_path and self._is_safe_weight(sam3_path, [
                repo_root,
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels", "SAM3"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights"),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels"),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels", "SAM3"),
                os.path.join(os.getcwd(), "models", "weights"),
            ], exts=(".pt",)):
                self.loading_progress.emit(model_name, 50)
                with self._sam_lock:
                    model = Sam3Adapter(checkpoint_path=sam3_path)
                    self.models["sam3"] = model
                    self.sam_paths["sam3"] = sam3_path
                    self.models["sam"] = model
                    self.active_sam_type = "sam3"
                    try:
                        import torch
                        torch.cuda.empty_cache()
                    except Exception:
                        pass
                self.loading_progress.emit(model_name, 100)
                self.loading_completed.emit(model_name)
                logger.info(f"SAM3模型加载成功: {sam3_path}")
                return
            settings = QSettings("MoonlightV2", "Settings")
            variant = settings.value("sam_model_variant", "b", type=str)
            filename_map = {"b": "sam2.1_b.pt", "s": "sam2.1_s.pt", "l": "sam2.1_l.pt"}
            model_filename = filename_map.get(str(variant).lower(), "sam2.1_b.pt")
            possible_paths = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels", model_filename),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels", "SAM2", model_filename),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels", model_filename),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels", "SAM2", model_filename),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", model_filename),
                os.path.join(os.getcwd(), "models", "weights", model_filename),
            ]
            if hasattr(sys, "frozen") and sys.frozen:
                possible_paths.extend([
                    os.path.join(os.path.dirname(sys.executable), "models", "weights", "SAMmodels", model_filename),
                    os.path.join(os.path.dirname(sys.executable), "models", "weights", model_filename),
                ])
            model_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    break
            if not model_path or not os.path.exists(model_path):
                msg = f"无法找到SAM模型文件: {model_path}"
                logger.warning(msg)
                self.loading_error.emit(model_name, msg)
                return
            allowed_dirs = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels", "SAM2"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights"),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels"),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels", "SAM2"),
                os.path.join(os.getcwd(), "models", "weights"),
            ]
            if hasattr(sys, "frozen") and sys.frozen:
                allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights", "SAMmodels"))
                allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights", "SAMmodels", "SAM2"))
                allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights"))
            if not self._is_safe_weight(model_path, allowed_dirs, exts=(".pt",)):
                msg = f"拒绝加载不安全的SAM权重: {model_path}"
                logger.warning(msg)
                self.loading_error.emit(model_name, msg)
                return
            try:
                from ultralytics import SAM
            except Exception as ie:
                msg = f"未安装Ultralytics或SAM不可用: {ie}"
                logger.warning(msg)
                self.loading_error.emit(model_name, msg)
                return
            self.loading_progress.emit(model_name, 50)
            with self._sam_lock:
                model = SAM(model_path)
                self.models["sam2"] = model
                self.sam_paths["sam2"] = model_path
                self.models["sam"] = model
                self.active_sam_type = "sam2"
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            self.loading_progress.emit(model_name, 100)
            self.loading_completed.emit(model_name)
            logger.info(f"SAM模型加载成功: {model_path}")
        except Exception as e:
            msg = f"加载SAM模型失败: {e}"
            logger.error(msg)
            self.loading_error.emit(model_name, msg)
    
    def _load_yoloe_model(self):
        """加载YOLOE模型"""
        # 已加载则跳过
        if self.models.get("yoloe") is not None:
            logger.info("YOLOE模型已存在，跳过重新加载")
            return
        model_name = "YOLOE"
        self.loading_started.emit(model_name)
        self.loading_progress.emit(model_name, 0)
        
        try:
            # 定义模型文件名
            model_filename = "yoloe-11l-seg.pt"
            
            # 尝试从不同位置查找模型文件（优先新目录 yoloemodels，其次旧目录 weights）
            possible_paths = [
                # 新目录结构：yoloemodels
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "yoloemodels", model_filename),
                os.path.join(os.getcwd(), "models", "weights", "yoloemodels", model_filename),
                # 旧目录结构：直接在 weights 下
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", model_filename),
                os.path.join(os.getcwd(), "models", "weights", model_filename)
            ]
            
            # 如果是打包后的exe，添加exe所在目录
            if hasattr(sys, 'frozen') and sys.frozen:
                possible_paths.extend([
                    os.path.join(os.path.dirname(sys.executable), "models", "weights", "yoloemodels", model_filename),
                    os.path.join(os.path.dirname(sys.executable), "models", "weights", model_filename)
                ])
            
            # 查找第一个存在的模型文件
            model_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    break
            
            # 最终检查文件是否存在
            if not model_path or not os.path.exists(model_path):
                error_msg = f"无法找到YOLOE模型文件: {model_path}"
                logger.warning(error_msg)
                self.loading_error.emit(model_name, error_msg)
                return
            allowed_dirs = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "yoloemodels"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights"),
                os.getcwd(),
            ]
            if hasattr(sys, 'frozen') and sys.frozen:
                allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights", "yoloemodels"))
                allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights"))
            if not self._is_safe_weight(model_path, allowed_dirs, exts=(".pt",)):
                msg = f"拒绝加载不安全的YOLOE权重: {model_path}"
                logger.warning(msg)
                self.loading_error.emit(model_name, msg)
                return
            
            # 延迟导入，避免未安装库导致启动异常
            try:
                from ultralytics import YOLOE
            except Exception as ie:
                error_msg = f"未安装Ultralytics或YOLOE不可用: {ie}"
                logger.warning(error_msg)
                self.loading_error.emit(model_name, error_msg)
                return

            self.loading_progress.emit(model_name, 50)
            
            # 加载模型
            model = YOLOE(model_path)
            self.models["yoloe"] = model
            
            self.loading_progress.emit(model_name, 100)
            self.loading_completed.emit(model_name)
            logger.info(f"YOLOE模型加载成功: {model_path}")
            
        except Exception as e:
            error_msg = f"加载YOLOE模型失败: {e}"
            logger.error(error_msg)
            self.loading_error.emit(model_name, error_msg)
    
    def _load_yolo_model(self):
        """加载YOLO模型"""
        # 已加载则跳过
        if self.models.get("yolov") is not None:
            logger.info("YOLO/RT-DETR 模型已存在，跳过重新加载")
            return
        model_name = "YOLO"
        self.loading_started.emit(model_name)
        self.loading_progress.emit(model_name, 0)
        
        try:
            # 优先尝试加载 RT-DETR 权重，其次回退到默认 YOLO 权重
            candidate_filenames = [
                "rtdetr-l.pt",  # RT-DETR-L（优先）
                "yolo11n.pt"     # YOLO 默认权重（回退）
            ]
            
            # 尝试从不同位置查找模型文件（依次按候选名查找）
            model_path = None
            chosen_filename = None
            for model_filename in candidate_filenames:
                possible_paths = [
                    # 当前脚本所在目录
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "rect", model_filename),
                    # 工作目录
                    os.path.join(os.getcwd(), "models", "weights", "rect", model_filename)
                ]
            
                # 如果是打包后的exe，添加exe所在目录
                if hasattr(sys, 'frozen') and sys.frozen:
                    possible_paths.append(
                        os.path.join(os.path.dirname(sys.executable), "models", "weights", "rect", model_filename)
                    )
                
                # 查找第一个存在的模型文件
                for path in possible_paths:
                    if os.path.exists(path):
                        model_path = path
                        chosen_filename = model_filename
                        break
                if model_path:
                    break
            
            # 最终检查文件是否存在
            if not model_path or not os.path.exists(model_path):
                error_msg = f"无法找到YOLO/RT-DETR模型文件: {model_path}"
                logger.warning(error_msg)
                self.loading_error.emit(model_name, error_msg)
                return
            allowed_dirs = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "rect"),
                os.path.join(os.getcwd(), "models", "weights", "rect"),
            ]
            if hasattr(sys, 'frozen') and sys.frozen:
                allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights", "rect"))
            if not self._is_safe_weight(model_path, allowed_dirs, exts=(".pt",)):
                msg = f"拒绝加载不安全的检测权重: {model_path}"
                logger.warning(msg)
                self.loading_error.emit(model_name, msg)
                return
            
            # 根据权重类型选择对应的Ultralytics模型类
            loader_cls = None
            try:
                lower_name = (chosen_filename or "").lower()
                if "rtdetr" in lower_name or "rtdtr" in lower_name:
                    from ultralytics import RTDETR
                    loader_cls = RTDETR
                else:
                    from ultralytics import YOLO
                    loader_cls = YOLO
            except Exception as ie:
                error_msg = f"未安装Ultralytics或目标模型不可用: {ie}"
                logger.warning(error_msg)
                self.loading_error.emit(model_name, error_msg)
                return

            self.loading_progress.emit(model_name, 50)
            
            # 加载模型
            model = loader_cls(model_path)
            self.models["yolov"] = model
            
            self.loading_progress.emit(model_name, 100)
            self.loading_completed.emit(model_name)
            logger.info(f"检测模型加载成功: {model_path}")
            
        except Exception as e:
            error_msg = f"加载检测模型失败: {e}"
            logger.error(error_msg)
            self.loading_error.emit(model_name, error_msg)
    
    def get_model(self, model_name):
        """获取已加载的模型
        
        Args:
            model_name: 模型名称，如"sam"
            
        Returns:
            已加载的模型实例，如果模型未加载则返回None
        """
        return self.models.get(model_name)
    
    def is_model_loaded(self, model_name):
        """检查模型是否已加载
        
        Args:
            model_name: 模型名称，如"sam"
            
        Returns:
            bool: 模型是否已加载
        """
        return model_name in self.models
    
    def get_yolov_weight_files(self):
        """获取rect文件夹中所有的yolov权重文件
        
        Returns:
            list: 所有权重文件路径的列表
        """
        weight_files = []
        
        # 定义可能的权重文件夹路径
        possible_weight_dirs = [
            # 当前脚本所在目录
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "rect"),
            # 工作目录
            os.path.join(os.getcwd(), "models", "weights", "rect")
        ]
        
        # 如果是打包后的exe，添加exe所在目录
        if hasattr(sys, 'frozen') and sys.frozen:
            possible_weight_dirs.append(
                os.path.join(os.path.dirname(sys.executable), "models", "weights", "rect")
            )
        
        # 查找第一个存在的权重文件夹
        weight_dir = None
        for dir_path in possible_weight_dirs:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                weight_dir = dir_path
                break
        
        if weight_dir is None:
            logger.warning("无法找到权重文件夹")
            return weight_files
        
        # 遍历权重文件夹，查找所有的.pt文件
        for file in os.listdir(weight_dir):
            if file.endswith(".pt"):
                weight_files.append(os.path.join(weight_dir, file))
        
        return weight_files
    
    def switch_yolov_model(self, weight_path):
        """切换YOLO模型
        
        Args:
            weight_path: 新的权重文件路径
            
        Returns:
            bool: 切换是否成功
        """
        try:
            # 在切换模型时加锁，确保不会和其他切换/推理冲突
            with self._yolov_lock:
                # 检查权重路径是否有效
                if not weight_path or not os.path.exists(weight_path):
                    logger.warning(f"无效的权重路径: {weight_path}")
                    return False
                allowed_dirs = [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "rect"),
                    os.path.join(os.getcwd(), "models", "weights", "rect"),
                ]
                if hasattr(sys, 'frozen') and sys.frozen:
                    allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights", "rect"))
                if not self._is_safe_weight(weight_path, allowed_dirs, exts=(".pt",)):
                    logger.warning(f"拒绝切换到不安全的权重: {weight_path}")
                    return False
                # 根据权重类型选择对应的Ultralytics模型类
                try:
                    lower_name = os.path.basename(weight_path).lower()
                    if "rtdetr" in lower_name or "rtdtr" in lower_name:
                        from ultralytics import RTDETR
                        model = RTDETR(weight_path)
                    else:
                        from ultralytics import YOLO
                        model = YOLO(weight_path)
                except Exception as ie:
                    logger.error(f"未安装Ultralytics或目标模型不可用: {ie}")
                    return False
                self.models["yolov"] = model
            logger.info(f"YOLO模型切换成功: {weight_path}")
            return True
        except Exception as e:
            logger.error(f"切换YOLO模型失败: {e}")
            return False

    def switch_sam_model(self, weight_path):
        model_name = "SAM"
        try:
            self.loading_started.emit(model_name)
            self.loading_progress.emit(model_name, 0)
            if not weight_path or not os.path.exists(weight_path):
                msg = f"无效的SAM权重路径: {weight_path}"
                logger.warning(msg)
                self.loading_error.emit(model_name, msg)
                return False
            allowed_dirs = [
                os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "weights", "SAMmodels"),
                os.path.join(os.getcwd(), "models", "weights", "SAMmodels"),
            ]
            if hasattr(sys, "frozen") and sys.frozen:
                allowed_dirs.append(os.path.join(os.path.dirname(sys.executable), "models", "weights", "SAMmodels"))
            if not self._is_safe_weight(weight_path, allowed_dirs, exts=(".pt",)):
                msg = f"拒绝切换到不安全的SAM权重: {weight_path}"
                logger.warning(msg)
                self.loading_error.emit(model_name, msg)
                return False
            is_sam3 = os.path.basename(weight_path).lower().startswith("sam3") or os.path.basename(weight_path).lower() == "sam3.pt"
            self.loading_progress.emit(model_name, 50)
            with self._sam_lock:
                if is_sam3:
                    model = Sam3Adapter(checkpoint_path=weight_path)
                    self.models["sam3"] = model
                    self.sam_paths["sam3"] = weight_path
                    self.models["sam"] = model
                    self.active_sam_type = "sam3"
                else:
                    from ultralytics import SAM
                    model = SAM(weight_path)
                    self.models["sam2"] = model
                    self.sam_paths["sam2"] = weight_path
                    self.models["sam"] = model
                    self.active_sam_type = "sam2"
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            self.loading_progress.emit(model_name, 100)
            self.loading_completed.emit(model_name)
            logger.info(f"SAM模型切换成功: {weight_path}")
            return True
        except Exception as e:
            logger.error(f"切换SAM模型失败: {e}")
            self.loading_error.emit(model_name, str(e))
            return False
    
    def try_different_yolov_weights(self, bboxes, image_path, confidence_threshold=0.5):
        """尝试不同的yolov权重文件，直到找到能检测到目标的权重
        
        Args:
            bboxes: 边界框坐标列表，格式为[[x1, y1, x2, y2], ...]
            image_path: 图片路径
            confidence_threshold: 置信度阈值
            
        Returns:
            tuple: (是否找到合适的权重, 检测结果列表)
        """
        # 获取所有的权重文件
        weight_files = self.get_yolov_weight_files()
        
        # 如果没有权重文件，返回False
        if not weight_files:
            logger.warning("没有找到任何权重文件")
            return False, []
        
        # 获取当前使用的权重文件路径
        current_model = self.models.get("yolov")
        current_weight_path = None
        if current_model is not None and hasattr(current_model, 'pt'):
            current_weight_path = current_model.pt
        
        # 记录已经尝试过的权重文件
        tried_weights = []
        
        # 如果当前有模型，先记录当前权重文件
        if current_weight_path:
            tried_weights.append(current_weight_path)
        
        # 尝试每个权重文件
        for weight_path in weight_files:
            # 跳过已经尝试过的权重文件
            if weight_path in tried_weights:
                continue
                
            # 切换到新的权重文件
            if not self.switch_yolov_model(weight_path):
                continue

            tried_weights.append(weight_path)

            # 使用新的权重文件进行推理（在 run_yolov_inference 中会使用锁）
            results = self.run_yolov_inference(image_path)
            
            # 提取矩形框坐标、置信度和类别ID
            output_data = []
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None:
                    for box in boxes:
                        confidence = float(box.conf[0].cpu().numpy())
                        
                        if confidence >= confidence_threshold:
                            bbox = box.xyxy[0].cpu().numpy().tolist()
                            # 保留两位小数
                            bbox = [round(coord, 2) for coord in bbox]
                            class_id = int(box.cls[0].cpu().numpy())
                            
                            # 检查边界框是否在输入的坐标区域内
                            for input_bbox in bboxes:
                                x1, y1, x2, y2 = input_bbox
                                center_x = (bbox[0] + bbox[2]) / 2
                                center_y = (bbox[1] + bbox[3]) / 2
                                
                                if x1 <= center_x <= x2 and y1 <= center_y <= y2:
                                    output_data.append({
                                        "bbox": bbox,
                                        "confidence": confidence,
                                        "class_id": class_id
                                    })
                                    break
            
            # 如果检测到了目标，返回成功
            if output_data:
                logger.info(f"找到合适的权重文件: {weight_path}")
                return True, output_data
        
        # 如果尝试了所有权重文件都没有检测到目标，恢复原来的权重文件（如果有）
        if current_weight_path and current_model:
            self.switch_yolov_model(current_weight_path)
            
        logger.warning("尝试了所有权重文件，但没有找到能检测到目标的权重")
        return False, []

    def run_yolov_inference(self, image_input):
        """线程安全地在当前 yolov 模型上执行推理并返回原始模型输出（不进行后处理）。

        支持传入文件路径或 numpy 图像数组。内部使用 `_yolov_lock` 保证并发安全。
        """
        with self._yolov_lock:
            model = self.models.get("yolov")
            if model is None:
                return None
            try:
                if isinstance(image_input, np.ndarray):
                    results = model(image_input)
                else:
                    results = model(image_input)
                return results
            except Exception as e:
                logger.error(f"运行YOLO推理时出错: {e}")
                return None

# 创建全局模型加载器实例
global_model_loader = None

def get_global_model_loader():
    """获取全局模型加载器实例"""
    global global_model_loader
    if global_model_loader is None:
        global_model_loader = GlobalModelLoader()
    return global_model_loader

def _safe_str(x):
    try:
        return str(x)
    except Exception:
        return ""

def select_active_sam(kind: str):
    """选择当前生效的SAM类型（"sam2"/"sam3"），不重新加载，仅切换引用并发信号。"""
    try:
        loader = get_global_model_loader()
        if kind not in ("sam2", "sam3"):
            return False
        with loader._sam_lock:
            model = loader.models.get(kind)
            if model is None:
                return False
            loader.models["sam"] = model
            loader.active_sam_type = kind
        try:
            loader.loading_completed.emit("SAM")
        except Exception:
            pass
        logger.info(f"SAM模型激活切换为: {_safe_str(kind)}")
        return True
    except Exception:
        return False

def initialize_global_models():
    """初始化全局模型加载，在软件启动时调用"""
    loader = get_global_model_loader()
    loader.load_all_models()
    return loader
