import os
import sys
import numpy as np
import cv2
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class Sam3Adapter:
    def __init__(self, checkpoint_path=None, device=None):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if checkpoint_path is None:
            checkpoint_path = os.path.join(repo_root, "sam3.pt")
        
        if device is None:
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"
                
        # BPE path logic
        bpe_candidates = [
            os.path.join(repo_root, "acc", "bpe_simple_vocab_16e6.txt.gz"),
            os.path.join(os.getcwd(), "acc", "bpe_simple_vocab_16e6.txt.gz"),
            os.path.join(os.path.dirname(__file__), "..", "acc", "bpe_simple_vocab_16e6.txt.gz"),
        ]
        try:
            import sys as _sys
            if hasattr(_sys, "frozen") and _sys.frozen:
                bpe_candidates.append(os.path.join(os.path.dirname(_sys.executable), "acc", "bpe_simple_vocab_16e6.txt.gz"))
        except Exception:
            pass
        bpe_path = None
        for bp in bpe_candidates:
            ap = os.path.abspath(bp)
            if os.path.exists(ap):
                bpe_path = ap
                break
        
        try:
            from ultralytics.models.sam.predict import SAM3SemanticPredictor
            
            overrides = dict(
                conf=0.25, 
                task="segment", 
                mode="predict", 
                model=checkpoint_path, 
                half=(device != 'cpu')
            )
            if device:
                overrides['device'] = device# 初始化 Ultralytics SAM3 预测器
            logger.info(f"Initializing SAM3SemanticPredictor with bpe_path: {bpe_path}")
            self.predictor = SAM3SemanticPredictor(overrides=overrides, bpe_path=bpe_path)
            
            # 尝试强制加载模型，确保初始化时完成耗时操作
            try:
                if hasattr(self.predictor, 'setup_model'):
                    # 不传递 model 参数，让它使用 overrides 中的 model
                    self.predictor.setup_model(model=None)
                    logger.info("SAM3 model setup completed via setup_model()")
                elif hasattr(self.predictor, '_setup_model'):
                    self.predictor._setup_model(model=None)
                    logger.info("SAM3 model setup completed via _setup_model()")
            except Exception as load_e:
                logger.warning(f"Could not explicitly setup model (will load on first inference): {load_e}")

            self.model = self.predictor
            logger.info(f"SAM3 adapter initialized with ultralytics. Model: {checkpoint_path}, Device: {device}")
            
        except Exception as e:
            logger.error(f"Failed to initialize SAM3SemanticPredictor: {e}")
            raise

    def _to_pil(self, image_input):
        if isinstance(image_input, np.ndarray):
            if image_input.ndim == 2:
                return Image.fromarray(image_input)
            return Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
        return Image.open(image_input).convert("RGB")

    def __call__(self, image_input, bboxes=None, points=None, labels=None):
        try:
            # Set image
            self.predictor.set_image(image_input)

            # Prepare arguments
            kwargs = {"save": False}
            
            if bboxes:
                # Ensure bboxes are in list format
                kwargs["bboxes"] = bboxes
                
            if points and labels:
                # points: [[[x, y], ...]], labels: [[l, ...]] -> ultralytics expects flat lists for single image
                if len(points) > 0:
                    kwargs["points"] = points[0]
                if len(labels) > 0:
                    kwargs["labels"] = labels[0]
            
            # 记录详细参数用于调试
            # logger.debug(f"SAM3 inference args: points={kwargs.get('points')}, labels={kwargs.get('labels')}, bboxes={kwargs.get('bboxes')}")

            # Run inference
            results = self.predictor(**kwargs)
            
            # Format results
            xy_list = []
            data_list = []
            
            # results is a list of Results objects
            for result in results:
                if result.masks:
                    if result.masks.xy:
                        # result.masks.xy is a list of np.ndarray (segments)
                        for seg in result.masks.xy:
                            xy_list.append(seg.tolist())
                    
                    if result.masks.data is not None:
                        # result.masks.data is Tensor (N, H, W)
                        m = result.masks.data.cpu().numpy()
                        for i in range(m.shape[0]):
                            data_list.append(m[i])

            # Helper classes for compatibility
            class Masks:
                def __init__(self, xy, data):
                    self.xy = xy
                    self.data = data
            class Result:
                def __init__(self, masks):
                    self.masks = masks
                    
            return [Result(Masks(xy_list, data_list))]
            
        except RuntimeError as re:
            # 特别捕获 torch.cat 错误，通常意味着没有检测到结果
            if "torch.cat" in str(re) and "non-empty list" in str(re):
                logger.warning("SAM3 inference returned no results (empty list in torch.cat)")
                return []
            logger.error(f"RuntimeError during SAM3 inference: {re}")
            return []
        except Exception as e:
            logger.error(f"Error during SAM3 inference: {e}")
            return []
