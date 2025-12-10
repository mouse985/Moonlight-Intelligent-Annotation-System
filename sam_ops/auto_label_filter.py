def is_duplicate_rect(selected_parent, image_info, bbox, tol=1.0):
    try:
        if not selected_parent or not image_info or not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            return False
        b1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        for child in selected_parent.children_by_image.get(image_info, []):
            if getattr(child, 'is_placeholder', False):
                continue
            pts = getattr(child, 'points', None)
            if isinstance(pts, list) and len(pts) >= 8:
                xs = [pts[0], pts[2], pts[4], pts[6]]
                ys = [pts[1], pts[3], pts[5], pts[7]]
                b2 = (min(xs), min(ys), max(xs), max(ys))
            else:
                pp = getattr(child, 'polygon_points', None)
                if isinstance(pp, list) and len(pp) > 0:
                    xs = [p[0] for p in pp]
                    ys = [p[1] for p in pp]
                    b2 = (min(xs), min(ys), max(xs), max(ys))
                else:
                    xc = getattr(child, 'x_center', None)
                    yc = getattr(child, 'y_center', None)
                    w = getattr(child, 'width', None)
                    h = getattr(child, 'height', None)
                    if xc is None or yc is None or w is None or h is None:
                        continue
                    b2 = (xc - w / 2.0, yc - h / 2.0, xc + w / 2.0, yc + h / 2.0)
            ix1 = max(b1[0], b2[0])
            iy1 = max(b1[1], b2[1])
            ix2 = min(b1[2], b2[2])
            iy2 = min(b1[3], b2[3])
            iw = max(0.0, ix2 - ix1)
            ih = max(0.0, iy2 - iy1)
            inter = iw * ih
            a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
            a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
            union = a1 + a2 - inter
            iou = inter / union if union > 0 else 0.0
            if iou >= 0.5:
                return True
        return False
    except Exception:
        return False

def is_duplicate_polygon(selected_parent, image_info, polygon_points, image_width=None, image_height=None, tol_n=0.005):
    try:
        if not selected_parent or not image_info or not polygon_points:
            return False
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        b1 = (min(xs), min(ys), max(xs), max(ys))
        for child in selected_parent.children_by_image.get(image_info, []):
            if getattr(child, 'is_placeholder', False):
                continue
            pts = getattr(child, 'points', None)
            if isinstance(pts, list) and len(pts) >= 8:
                cxs = [pts[0], pts[2], pts[4], pts[6]]
                cys = [pts[1], pts[3], pts[5], pts[7]]
                b2 = (min(cxs), min(cys), max(cxs), max(cys))
            else:
                pp = getattr(child, 'polygon_points', None)
                if isinstance(pp, list) and len(pp) > 0:
                    cxs = [p[0] for p in pp]
                    cys = [p[1] for p in pp]
                    b2 = (min(cxs), min(cys), max(cxs), max(cys))
                else:
                    xc = getattr(child, 'x_center', None)
                    yc = getattr(child, 'y_center', None)
                    w = getattr(child, 'width', None)
                    h = getattr(child, 'height', None)
                    if xc is None or yc is None or w is None or h is None:
                        continue
                    b2 = (xc - w / 2.0, yc - h / 2.0, xc + w / 2.0, yc + h / 2.0)
            ix1 = max(b1[0], b2[0])
            iy1 = max(b1[1], b2[1])
            ix2 = min(b1[2], b2[2])
            iy2 = min(b1[3], b2[3])
            iw = max(0.0, ix2 - ix1)
            ih = max(0.0, iy2 - iy1)
            inter = iw * ih
            a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
            a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
            union = a1 + a2 - inter
            iou = inter / union if union > 0 else 0.0
            if iou >= 0.5:
                return True
        return False
    except Exception:
        return False
