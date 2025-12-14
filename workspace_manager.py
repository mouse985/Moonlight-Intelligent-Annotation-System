import logging
import os
from typing import List, Optional

from PyQt6.QtGui import QImage

from io_ops import LIM

logger = logging.getLogger(__name__)

class WorkspaceResourceManager:

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path or os.path.join(os.getcwd(), 'workspace')
        self._resource_list: List[str] = []
        self.main_window: Optional['MainWindow'] = None
        self._ensure_workspace_exists()

    def _ensure_workspace_exists(self) -> None:

        try:
            if not os.path.exists(self.workspace_path):
                os.makedirs(self.workspace_path)
                
        except OSError as e:
            logger.error(f"创建工作区目录失败: {e}")
            raise

    def scan_resources(self) -> List[str]:

        try:
            files = self._collect_image_files()
            files = sorted(files, key=lambda x: os.path.basename(x).lower())

            self._resource_list = files
            return files

        except Exception as e:
            logger.error(f"扫描资源时发生错误: {e}")
            return []

    def _collect_image_files(self) -> List[str]:

        files = []
        for root, _, filenames in os.walk(self.workspace_path):
            for filename in filenames:
                if any(filename.lower().endswith(ext) for ext in LIM.ImageProcessingConfig.SUPPORTED_EXTENSIONS):
                    file_path = os.path.join(root, filename)
                    files.append(file_path)
        return files
    def get_resource_list(self) -> List[str]:
        return self._resource_list.copy()

    def is_valid_image_path(self, file_path: str) -> bool:
        try:
            if not os.path.exists(file_path):
                return False
            if not os.path.isfile(file_path):
                return False
            _, ext = os.path.splitext(file_path)
            return ext.lower() in LIM.ImageProcessingConfig.SUPPORTED_EXTENSIONS
        except Exception as e:
            logger.error(f"检查图片路径有效性时发生错误 {file_path}: {e}")
            return False

    def load_image_safe(self, file_path: str) -> Optional[QImage]:
        try:
            if not self.is_valid_image_path(file_path):
                logger.warning(f"无效的图片路径: {file_path}")
                return None
            image = QImage(file_path)
            if image.isNull():
                logger.warning(f"无法加载图片: {file_path}")
                return None
            return image
        except Exception as e:
            logger.error(f"加载图片时发生错误 {file_path}: {e}")
            return None
