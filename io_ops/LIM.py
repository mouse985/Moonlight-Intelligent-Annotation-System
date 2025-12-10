import os
import sys
import logging
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem
from PyQt6.QtGui import QImage, QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize

logger = logging.getLogger(__name__)

class ImageProcessingConfig:# 图片处理配置类
    SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp']
    SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'bmp', 'tif', 'tiff', 'webp']
    LARGE_DATASET_THRESHOLD = 1000
    MEMORY_OPTIMIZE_THRESHOLD = 5000

def load_image_directory(main_window):
    """加载图片目录功能
    
    Args:
        main_window: 主窗口实例
    """
    try:
        # 打开目录选择对话框
        directory = QFileDialog.getExistingDirectory(
            main_window,
            "选择图片目录",
            "",  # 初始目录
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if directory and os.path.isdir(directory):
            # 获取目录中的所有图片文件
            image_files = []
            
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in ImageProcessingConfig.SUPPORTED_EXTENSIONS):
                        image_files.append(os.path.join(root, file))
            
            if image_files:
                # 清空当前资源列表
                main_window.resource_list.clear()
                
                # 设置新的图片列表
                main_window.images = image_files
                
                # 为每个图片文件创建列表项
                for i, file_path in enumerate(image_files):
                    item = QListWidgetItem(os.path.basename(file_path))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setSizeHint(QSize(110, 130))
                    main_window.resource_list.addItem(item)
                    # 优化：只加载前10项的缩略图，其余项在滚动时加载
                    if i < 10:
                        main_window._load_thumbnail_for_item(file_path, i)
                
                # 更新窗口标题
                main_window.setWindowTitle(f'手动标注工具 - {directory}')
                
                # 设置当前图片信息
                if len(image_files) > 0:
                    main_window.parent_label_list.set_current_image_info(
                        image_files[0], total=len(image_files), current_idx=0)
                
                QMessageBox.information(main_window, "成功", f"已加载 {len(image_files)} 张图片")
            else:
                QMessageBox.warning(main_window, "警告", "所选目录中未找到图片文件")
        
    except Exception as e:
        QMessageBox.critical(main_window, "错误", f"加载图片目录时发生错误: {str(e)}")


def load_image_safe(image_path: str) -> QImage:
    """安全加载图片文件
    
    Args:
        image_path (str): 图片文件路径
        
    Returns:
        QImage: 加载的图片对象，如果加载失败则返回None
    """
    try:
        if not os.path.exists(image_path):
            logger.warning(f"图片文件不存在: {image_path}")
            return None
            
        # 检查文件扩展名
        _, ext = os.path.splitext(image_path)
        if ext.lower() not in ImageProcessingConfig.SUPPORTED_EXTENSIONS:
            logger.warning(f"不支持的图片格式: {image_path}")
            return None
            
        # 尝试加载图片
        image = QImage(image_path)
        if image.isNull():
            logger.warning(f"无法加载图片: {image_path}")
            return None
            
        return image
        
    except Exception as e:
        logger.error(f"加载图片时发生错误 {image_path}: {e}")
        return None


def load_image(main_window) -> None:
    """加载单张图片文件
    
    Args:
        main_window: 主窗口实例
    """
    try:
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            main_window, '选择图片', '', 
            'Images (*.' + ' *.'.join(ImageProcessingConfig.SUPPORTED_FORMATS) + ')')

        if file_path:
            # 使用load_image_safe安全加载图片
            image = load_image_safe(file_path)
            if image is not None:
                # 清空当前资源列表
                main_window.resource_list.clear()
                
                # 设置新的图片列表
                main_window.images = [file_path]
                
                # 为图片文件创建列表项
                item = QListWidgetItem(os.path.basename(file_path))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setSizeHint(QSize(110, 130))
                main_window.resource_list.addItem(item)
                # 加载缩略图
                main_window._load_thumbnail_for_item(file_path, 0)
                
                # 更新窗口标题
                main_window.setWindowTitle(f'手动标注工具 - {os.path.basename(file_path)}')
                
                # 设置当前图片信息
                main_window.parent_label_list.set_current_image_info(
                    file_path, total=1, current_idx=0)
                
                # 在画布上显示图片
                main_window.canvas.load_image(file_path)
                
                QMessageBox.information(main_window, "成功", "图片加载成功")
            else:
                QMessageBox.warning(main_window, "警告", "选择的文件不是有效的图片格式")

    except Exception as e:
        logger.error(f"加载图片时发生错误: {e}")
        QMessageBox.critical(main_window, "错误", f"加载图片失败: {e}")
