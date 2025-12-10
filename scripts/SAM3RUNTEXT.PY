import os
import numpy as np
import cv2
from PIL import Image
import torch
from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor

class SAM3:
    def __init__(self, checkpoint_path=None, device=None, bpe_path=None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if checkpoint_path is None:
            checkpoint_path = os.path.abspath("sam3.pt")
        if bpe_path is None:
            candidates = [
                os.path.join(os.getcwd(), "assets", "bpe_simple_vocab_16e6.txt.gz"),
                os.path.join(os.path.dirname(__file__), "assets", "bpe_simple_vocab_16e6.txt.gz"),
            ]
            try:
                import sys as _sys
                if hasattr(_sys, "frozen") and _sys.frozen:
                    candidates.append(os.path.join(os.path.dirname(_sys.executable), "assets", "bpe_simple_vocab_16e6.txt.gz"))
            except Exception:
                pass
            for bp in candidates:
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
        if bboxes is not None:
            if isinstance(bboxes, (list, tuple)):
                if len(bboxes) == 4 and not isinstance(bboxes[0], (list, tuple)):
                    bboxes = [list(bboxes)]
        if points is not None:
            if isinstance(points, (list, tuple)):
                if len(points) == 2 and not isinstance(points[0], (list, tuple)):
                    points = [list(points)]
                    if labels is not None:
                        if isinstance(labels, (list, tuple)) and len(labels) == 1 and not isinstance(labels[0], (list, tuple)):
                            labels = [[int(labels[0])]]
                        elif isinstance(labels, (int, float)):
                            labels = [[int(labels)]]
                elif len(points) > 0 and isinstance(points[0], (list, tuple)) and len(points[0]) == 2 and not isinstance(points[0][0], (list, tuple)):
                    points = [list(points)]
                    if labels is not None and isinstance(labels, (list, tuple)) and len(labels) > 0 and not isinstance(labels[0], (list, tuple)):
                        labels = [list(labels)]
        if points and labels:
            pts = []
            lbs = []
            for p, l in zip(points[0], labels[0]):
                x = max(0.0, min(1.0, float(p[0]) / float(w)))
                y = max(0.0, min(1.0, float(p[1]) / float(h)))
                pts.append([x, y])
                lbs.append([1 if l else 0])
            pts_t = torch.tensor(pts, dtype=torch.float32, device=self.processor.device).view(len(pts), 1, 2)
            lbs_t = torch.tensor(lbs, dtype=torch.long, device=self.processor.device).view(len(lbs), 1)
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
                dummy = self.model.backbone.forward_text(["visual"], device=self.processor.device)
                self.state["backbone_out"].update(dummy)
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

    def info(self):
        name = self.model.__class__.__name__
        dev = str(self.processor.device)
        try:
            modules = sum(1 for _ in self.model.modules())
        except Exception:
            modules = None
        has_backbone = hasattr(self.model, "backbone")
        return {"name": name, "device": dev, "modules": modules, "has_backbone": has_backbone}

if __name__ == "__main__":
    model = SAM3("sam3.pt")
    print(model.info())
    image_path = "path/to/image.jpg"
    r1 = model(image_path, bboxes=[100, 100, 200, 200])
    print(len(r1))
    r2 = model(image_path, points=[900, 370], labels=[1])
    print(len(r2))
    r3 = model(image_path, points=[[400, 370], [900, 370]], labels=[1, 1])
    print(len(r3))
    r4 = model(image_path, points=[[[400, 370], [900, 370]]], labels=[[1, 1]])
    print(len(r4))
    r5 = model(image_path, points=[[[400, 370], [900, 370]]], labels=[[1, 0]])
    print(len(r5))
