import os
import sys
import numpy as np
import cv2
from PIL import Image
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
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
        bpe_candidates = [
            os.path.join(repo_root, "assets", "bpe_simple_vocab_16e6.txt.gz"),
            os.path.join(os.getcwd(), "assets", "bpe_simple_vocab_16e6.txt.gz"),
            os.path.join(os.path.dirname(__file__), "..", "assets", "bpe_simple_vocab_16e6.txt.gz"),
        ]
        try:
            import sys as _sys
            if hasattr(_sys, "frozen") and _sys.frozen:
                bpe_candidates.append(os.path.join(os.path.dirname(_sys.executable), "assets", "bpe_simple_vocab_16e6.txt.gz"))
        except Exception:
            pass
        bpe_path = None
        for bp in bpe_candidates:
            ap = os.path.abspath(bp)
            if os.path.exists(ap):
                bpe_path = ap
                break
        self.model = build_sam3_image_model(
            bpe_path=bpe_path,
            device=device,
            eval_mode=True,
            checkpoint_path=checkpoint_path,
            load_from_HF=False,
            enable_segmentation=True,
            enable_inst_interactivity=False,
            compile=False,
        )
        self.processor = Sam3Processor(model=self.model, device=device)
        self.state = {}

    def _to_pil(self, image_input):
        if isinstance(image_input, np.ndarray):
            if image_input.ndim == 2:
                return Image.fromarray(image_input)
            return Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
        return Image.open(image_input).convert("RGB")

    def __call__(self, image_input, bboxes=None, points=None, labels=None):
        image = self._to_pil(image_input)
        self.state = self.processor.set_image(image)
        w, h = image.size
        if points and labels:
            import torch as _torch
            pts = []
            lbs = []
            for p, l in zip(points[0], labels[0]):
                x = max(0.0, min(1.0, float(p[0]) / float(w)))
                y = max(0.0, min(1.0, float(p[1]) / float(h)))
                pts.append([x, y])
                lbs.append([1 if l else 0])
            pts_t = _torch.tensor(pts, dtype=_torch.float32, device=self.processor.device).view(len(pts), 1, 2)
            lbs_t = _torch.tensor(lbs, dtype=_torch.long, device=self.processor.device).view(len(lbs), 1)
            if "geometric_prompt" not in self.state:
                self.state["geometric_prompt"] = self.model._get_dummy_prompt()
            self.state["geometric_prompt"].append_points(pts_t, lbs_t)
        if bboxes:
            for bb in bboxes:
                x0, y0, x1, y1 = bb
                nx0 = max(0.0, min(1.0, float(x0) / float(w)))
                ny0 = max(0.0, min(1.0, float(y0) / float(h)))
                nx1 = max(0.0, min(1.0, float(x1) / float(w)))
                ny1 = max(0.0, min(1.0, float(y1) / float(h)))
                cx = (nx0 + nx1) / 2.0
                cy = (ny0 + ny1) / 2.0
                bw = abs(nx1 - nx0)
                bh = abs(ny1 - ny0)
                self.state = self.processor.add_geometric_prompt([cx, cy, bw, bh], True, self.state)
        if "geometric_prompt" not in self.state:
            self.state["geometric_prompt"] = self.model._get_dummy_prompt()
        if "backbone_out" not in self.state:
            self.state["backbone_out"] = {}
        if "language_features" not in self.state.get("backbone_out", {}):
            try:
                dummy_text_outputs = self.model.backbone.forward_text(["visual"], device=self.processor.device)
                self.state["backbone_out"].update(dummy_text_outputs)
            except Exception:
                pass
        out = self.processor._forward_grounding(self.state)
        masks = out.get("masks")
        if masks is None:
            return []
        if hasattr(masks, "detach"):
            m = masks.detach().cpu().numpy()
        else:
            m = np.asarray(masks)
        if m.ndim == 4:
            m = m[:, 0]
        xy_list = []
        data_list = []
        for i in range(m.shape[0]):
            mm = (m[i] > 0.5).astype(np.uint8)
            data_list.append(mm)
            cnts, _ = cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            pts = []
            if cnts:
                c = max(cnts, key=cv2.contourArea)
                for p in c.reshape(-1, 2).tolist():
                    pts.append([float(p[0]), float(p[1])])
            xy_list.append(pts)
        class Masks:
            def __init__(self, xy, data):
                self.xy = xy
                self.data = data
        class Result:
            def __init__(self, masks):
                self.masks = masks
        return [Result(Masks(xy_list, data_list))]
