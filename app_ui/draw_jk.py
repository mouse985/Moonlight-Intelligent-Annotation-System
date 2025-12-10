"""
简洁的画布可视区域裁剪工具（PyQt6）。

功能：
- 根据当前画布窗口的可视区域，从原始图片像素坐标裁剪出对应区域；
- 仅当图片尺寸大于画布窗口尺寸时触发裁剪；
- 不缩放、不改变分辨率（像素级裁剪）。

使用方式：
- 传入当前的画布视图对象（QGraphicsView 的实例，如 vision_prompt_win.py 中的 canvas），
  函数将基于其 viewport 映射到 scene 的可见矩形进行裁剪。

注意：
- 依赖项目中已加载的 QPixmap（即 view.current_pixmap）。
- 若未加载图片或可视区域与图片无交集，返回 None。
"""

import logging
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QRect

logger = logging.getLogger(__name__)

# 会话级裁剪缓存：仅缓存当前图像的不同矩形裁剪
_crop_cache = {}
_cached_image_path = None


def _get_visible_image_rect(view) -> QRect | None:
    """
    获取画布窗口当前可视区域在图片像素坐标中的矩形。

    返回 QRect（基于图片坐标），若无法计算则返回 None。
    """
    try:
        # 需要当前底图 QPixmap
        pixmap: QPixmap = getattr(view, 'current_pixmap', None)
        if pixmap is None or pixmap.isNull():
            return None

        # 视口矩形（窗口坐标） -> 映射到场景坐标
        viewport_rect = view.viewport().rect()
        scene_poly = view.mapToScene(viewport_rect)
        scene_rectf = scene_poly.boundingRect()

        # 转整数矩形，并与图片范围相交裁剪
        scene_rect = scene_rectf.toRect()
        image_rect = QRect(0, 0, pixmap.width(), pixmap.height())
        intersect_rect = scene_rect.intersected(image_rect)

        if intersect_rect.isNull() or intersect_rect.width() <= 0 or intersect_rect.height() <= 0:
            return None
        return intersect_rect
    except Exception:
        return None


def crop_canvas_visible_image(view, save_path: str | None = None, trigger_only_if_larger: bool = True) -> QImage | None:
    """
    根据画布窗口可视区域裁剪当前图片，像素级裁剪，分辨率不变。

    参数：
    - view: QGraphicsView 实例（需具有 current_pixmap）。
    - save_path: 可选，保存裁剪结果到该路径（格式由后缀决定）。
    - trigger_only_if_larger: 为 True 时，仅当图片尺寸大于画布窗口尺寸时触发裁剪。

    返回：
    - QImage（裁剪结果）；若不触发或失败，返回 None。
    """
    try:
        global _crop_cache, _cached_image_path

        pixmap: QPixmap = getattr(view, 'current_pixmap', None)
        if pixmap is None or pixmap.isNull():
            return None

        # 判定触发条件：只有图片尺寸大于画布窗口尺寸时才裁剪
        if trigger_only_if_larger:
            vp = view.viewport().rect()
            if pixmap.width() <= vp.width() and pixmap.height() <= vp.height():
                rect = QRect(0, 0, pixmap.width(), pixmap.height())
            else:
                rect = _get_visible_image_rect(view)
        else:
            rect = _get_visible_image_rect(view)
        if rect is None:
            return None

        # 获取当前图像路径，用于管理缓存（若不可用则不使用缓存）
        current_image_path = None
        try:
            if hasattr(view, 'get_image_info_func') and view.get_image_info_func:
                info = view.get_image_info_func()
                if info and isinstance(info, dict):
                    current_image_path = info.get('path')
        except Exception:
            current_image_path = None

        # 如果图像路径变化，则清空缓存
        if current_image_path and current_image_path != _cached_image_path:
            _crop_cache.clear()
            _cached_image_path = current_image_path

        # 命中缓存直接返回
        cache_key = None
        if current_image_path:
            cache_key = (rect.x(), rect.y(), rect.width(), rect.height())
            cached = _crop_cache.get(cache_key)
            if cached is not None:
                return cached

        # 像素级裁剪，不缩放
        cropped_pixmap = pixmap.copy(rect)
        if cropped_pixmap.isNull():
            return None

        # 可选保存
        if save_path:
            # 先转换为 QImage 再保存，避免重复转换
            img = cropped_pixmap.toImage()
            img.save(save_path)
        else:
            img = cropped_pixmap.toImage()

        # 写入缓存
        if cache_key is not None:
            _crop_cache[cache_key] = img

        # 返回 QImage（保持像素数据）
        return img
    except Exception:
        return None
