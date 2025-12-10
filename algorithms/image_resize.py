import logging
import os

from PyQt6.QtCore import Qt, QSettings, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QMessageBox, QProgressDialog

from app_ui.remote_sensing import is_remote_sensing_enabled

logger = logging.getLogger(__name__)
_warned_once = False

class _ResizeWorker(QThread):
    done = pyqtSignal(QImage, int, int, float)
    failed = pyqtSignal(str)
    def __init__(self, img: QImage, target_w: int, target_h: int):
        super().__init__()
        self.img = img
        self.target_w = target_w
        self.target_h = target_h
    def run(self):
        try:
            orig_w = self.img.width()
            orig_h = self.img.height()
            scale_w = self.target_w / max(1, orig_w)
            scale_h = self.target_h / max(1, orig_h)
            factor = min(scale_w, scale_h)
            new_w = int(orig_w * factor)
            new_h = int(orig_h * factor)
            new_img = self.img.scaled(new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            if new_img.isNull():
                self.failed.emit("scaled 结果为空")
            else:
                self.done.emit(new_img, new_w, new_h, factor)
        except Exception as e:
            self.failed.emit(str(e))

def enlarge_image(image: QImage, factor: int) -> QImage:
    if image is None or image.isNull():
        return image
    w = image.width()
    h = image.height()
    return image.scaled(QSize(w * factor, h * factor), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

def adjust_current_image_to_1080p(main_window) -> bool:
    try:
        settings = QSettings("MoonlightV2", "Settings")
        if not is_remote_sensing_enabled():
            QMessageBox.information(main_window, "提示", "请先在设置中开启“遥感模式”后使用该功能")
            return False
        global _warned_once
        if not _warned_once:
            QMessageBox.warning(main_window, "警告", "该功能可能会损坏数据集，请谨慎使用")
            _warned_once = True
        if not hasattr(main_window, 'canvas') or not main_window.canvas or not getattr(main_window.canvas, 'image_item', None):
            logger.info("1080P调整未执行：画布未加载图片")
            return False
        pix = main_window.canvas.image_item.pixmap()
        if pix.isNull():
            logger.info("1080P调整未执行：当前贴图为空")
            return False
        img = pix.toImage()
        orig_w = img.width()
        orig_h = img.height()
        threshold = str(settings.value("resolution_threshold", "1080p", type=str)).lower()
        res_map = {
            "1080p": (1920, 1080),
            "1.5k": (1536, 864),
            "2k": (2560, 1440),
            "4k": (3840, 2160),
            "8k": (7680, 4320),
            "16k": (15360, 8640),
        }
        target_w, target_h = res_map.get(threshold, (1920, 1080))
        if orig_w >= target_w or orig_h >= target_h:
            QMessageBox.information(main_window, "提示", f"当前图片分辨率不小于当前设定的分辨率阈值（{target_w}x{target_h}，{threshold.upper()}），未进行调整。")
            logger.info(f"阈值调整跳过：当前分辨率 {orig_w}x{orig_h} 不小于 {target_w}x{target_h}（{threshold}）")
            return False
        scale_w = target_w / max(1, orig_w)
        scale_h = target_h / max(1, orig_h)
        factor = min(scale_w, scale_h)
        new_w = int(orig_w * factor)
        new_h = int(orig_h * factor)
        if new_w * new_h > 50_000_000:
            QMessageBox.information(main_window, "提示", "目标分辨率过大，可能导致内存崩溃，已取消操作。")
            return False
        image_path = getattr(main_window, 'current_image_path', None)
        if not image_path or not os.path.exists(image_path):
            logger.error("1080P调整失败：找不到当前图片路径")
            return False
        base = os.path.basename(image_path)
        backup_root = os.path.join(main_window.resource_manager.workspace_path, 'backup')
        os.makedirs(backup_root, exist_ok=True)
        backup_path = os.path.join(backup_root, base)
        if not os.path.exists(backup_path):
            try:
                img.save(backup_path)
                logger.info(f"原图已备份：{backup_path}")
            except Exception as be:
                logger.error(f"备份原图失败：{be}")
                QMessageBox.warning(main_window, "警告", f"备份原图失败：{be}")
                return False
        progress = QProgressDialog("正在调整分辨率...", "取消", 0, 0, main_window)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setAutoClose(True)
        progress.show()
        def on_done(new_img_obj: QImage, nw: int, nh: int, f: float):
            try:
                if not new_img_obj.save(image_path):
                    logger.error("覆盖原图失败：保存返回False")
                    QMessageBox.critical(main_window, "错误", "覆盖原图失败")
                    return
                if hasattr(main_window, 'parent_label_list') and main_window.parent_label_list:
                    img_path = image_path
                    for label in main_window.parent_label_list.labels:
                        if hasattr(label, 'children_by_image') and img_path in label.children_by_image:
                            for child in label.children_by_image[img_path]:
                                if getattr(child, 'is_placeholder', False):
                                    continue
                                child.scale(f)
                main_window.canvas.load_image(image_path)
                main_window.canvas.update_rects()
                QMessageBox.information(main_window, "成功", f"已备份原图并将图像等比调整到 {nw}x{nh}")
                logger.info(f"分辨率调整成功：{orig_w}x{orig_h} -> {nw}x{nh}，factor={f:.4f}，阈值={target_w}x{target_h}")
            finally:
                progress.close()
        def on_failed(msg: str):
            progress.close()
            logger.error(f"分辨率调整失败：{msg}")
            QMessageBox.critical(main_window, "错误", f"分辨率调整失败：{msg}")
        worker = _ResizeWorker(img, target_w, target_h)
        main_window._resize_worker = worker
        worker.done.connect(on_done)
        worker.failed.connect(on_failed)
        try:
            worker.finished.connect(worker.deleteLater)
            worker.finished.connect(lambda: setattr(main_window, '_resize_worker', None))
        except Exception:
            pass
        worker.start()
        return True
    except Exception as e:
        logger.error(f"1080P调整流程失败: {e}")
        return False
