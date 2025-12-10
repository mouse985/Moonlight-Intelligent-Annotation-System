import logging
import math
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QDialog, QLineEdit, QSpinBox, QHBoxLayout, QMessageBox, QMenu
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from app_ui.color_moon import ColorMoon
logger = logging.getLogger(__name__)

# 旋转角度空间规范化常量
MIN_ROTATION_ANGLE = 0  # 最小旋转角度（度）
MAX_ROTATION_ANGLE = 360  # 最大旋转角度（度）
DEG_TO_RAD = math.pi / 180.0  # 角度转弧度系数
RAD_TO_DEG = 180.0 / math.pi  # 弧度转角度系数

class ParentLabel:
    def __init__(self, name, id_):
        self.name = name  # 类别名称
        self.id = id_     # 类别ID
        self.selected = False  # 是否被选中
        self.children = []     # 子标签列表（ChildLabel对象）
        self.children_by_image = {}  # 分页存储
        # 使用ColorMoon获取随机鲜艳颜色
        rgb_color = ColorMoon.get_random_color()
        self.color = QColor(rgb_color[0], rgb_color[1], rgb_color[2])  # 为父标签生成随机颜色

    def __str__(self):
        return f"{self.name} (ID: {self.id})"

class ChildLabel:
    def __init__(self, parent_label, points=None, mode='manual', image_info=None, is_placeholder=False, shape_type='rectangle', polygon_points=None, rotation_angle=0, mask_data=None):
        self.class_name = parent_label.name
        self.class_id = parent_label.id
        self.color = parent_label.color  # 继承父标签的颜色
        self.mode = mode  # 'manual' or 'auto'
        self.shape_type = shape_type  # 'rectangle', 'polygon', 'line', 'point', or 'circle'
        
        # 实际坐标（像素坐标）
        # 对于矩形，points包含四个顶点的坐标 [x1, y1, x2, y2, x3, y3, x4, y4]
        # 对于多边形，points包含所有顶点的坐标 [x1, y1, x2, y2, ..., xn, yn]
        # 对于圆形，points包含圆心坐标和半径 [center_x, center_y, radius]
        self.points = points if points else []
        
        # 为了向后兼容，保留原有的中心点和宽高属性，但通过points计算得出
        self.x_center = None
        self.y_center = None
        self.width = None
        self.height = None
        
        # 圆形特有属性
        self.radius = None
        
        # 如果提供了points，计算中心点和宽高（根据shape_type）
        if self.points:
            if self.shape_type == 'rectangle' and len(self.points) >= 8:  # 矩形至少需要8个值（4个点）
                self._update_center_and_size_from_points()
            elif self.shape_type == 'line' and len(self.points) >= 4:
                # 线段两个端点 (x1,y1,x2,y2)
                x1, y1, x2, y2 = self.points[0], self.points[1], self.points[2], self.points[3]
                self.x_center = (x1 + x2) / 2.0
                self.y_center = (y1 + y2) / 2.0
                # 使用包围盒宽高，便于部分通用逻辑
                self.width = abs(x2 - x1)
                self.height = abs(y2 - y1)
            elif self.shape_type == 'point' and len(self.points) >= 2:
                # 单点 (x,y)
                self.x_center = self.points[0]
                self.y_center = self.points[1]
                self.width = 0.0
                self.height = 0.0
            elif self.shape_type == 'circle' and len(self.points) >= 3:
                # 圆形 (center_x, center_y, radius)
                self.x_center = self.points[0]
                self.y_center = self.points[1]
                self.radius = self.points[2]
                # 圆形的包围盒宽高等于直径
                self.width = self.radius * 2
                self.height = self.radius * 2
        
        self.image_info = image_info  # 新增：当前加载到画布上的图片信息
        self.is_placeholder = is_placeholder  # 是否为占位空子标签
        self.screenshot = None  # 截图文件路径
        # 多边形点信息（实际坐标）
        self.polygon_points = polygon_points if polygon_points else []
        # 旋转角度（度数，规范化到0-360度范围，以标签中心为旋转中心）
        self.rotation_angle = rotation_angle % MAX_ROTATION_ANGLE
        if self.rotation_angle < MIN_ROTATION_ANGLE:
            self.rotation_angle += MAX_ROTATION_ANGLE
        
        # 原始MASK数据（仅用于polygon_mask类型）
        self.mask_data = mask_data if mask_data is not None else None
    
    def _update_center_and_size_from_points(self):
        """从顶点坐标计算中心点和宽高"""
        if not self.points or len(self.points) < 8:
            return
        
        # 提取所有x和y坐标
        x_coords = [self.points[i] for i in range(0, len(self.points), 2)]
        y_coords = [self.points[i+1] for i in range(0, len(self.points), 2)]
        
        # 计算中心点
        self.x_center = sum(x_coords) / len(x_coords)
        self.y_center = sum(y_coords) / len(y_coords)
        
        # 计算宽高（对于矩形，使用最小和最大坐标）
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        self.width = max_x - min_x
        self.height = max_y - min_y
    
    def set_rectangle_points(self, x1, y1, x2, y2, x3, y3, x4, y4):
        """设置矩形的四个顶点坐标并更新中心点和宽高"""
        self.points = [x1, y1, x2, y2, x3, y3, x4, y4]
        self.shape_type = 'rectangle'
        self._update_center_and_size_from_points()
    
    def get_rectangle_points(self):
        """获取矩形的四个顶点坐标"""
        if self.shape_type != 'rectangle' or not self.points or len(self.points) < 8:
            return []
        
        # 返回四个顶点的坐标
        return [
            (self.points[0], self.points[1]),  # 第一个点
            (self.points[2], self.points[3]),  # 第二个点
            (self.points[4], self.points[5]),  # 第三个点
            (self.points[6], self.points[7])   # 第四个点
        ]
        
    def get_area(self):
        """计算标签面积（矩形、多边形、圆形；线/点返回0）"""
        if self.is_placeholder:
            return float('inf')  # 返回无穷大，确保占位符不会被选中
        
        if (self.shape_type == 'polygon' or self.shape_type == 'polygon_mask') and self.polygon_points:
            # 使用多边形面积公式
            points = self.polygon_points
            if len(points) < 3:
                return float('inf')
            # 使用鞋带公式计算多边形面积
            area = 0.0
            n = len(points)
            for i in range(n):
                j = (i + 1) % n
                area += points[i][0] * points[j][1]
                area -= points[j][0] * points[i][1]
            area = abs(area) / 2.0
            return area
        elif self.shape_type == 'rectangle':
            # 矩形面积
            if self.width is None or self.height is None:
                return float('inf')
            return self.width * self.height
        elif self.shape_type == 'circle':
            # 圆形面积 π * r²
            if self.radius is None or self.radius <= 0:
                return float('inf')
            return math.pi * self.radius * self.radius
        elif self.shape_type == 'line':
            # 线段面积视为0
            return 0.0
        elif self.shape_type == 'point':
            # 点面积视为0
            return 0.0
        else:
            return float('inf')

    def move(self, dx, dy):
        """移动标签位置
        
        Args:
            dx: x方向的移动距离
            dy: y方向的移动距离
        """
        # 更新中心点位置
        if self.x_center is not None:
            self.x_center += dx
        if self.y_center is not None:
            self.y_center += dy
        
        # 更新顶点坐标
        if self.points and len(self.points) >= 2:
            if self.shape_type == 'circle':
                # 对于圆形，只需要更新圆心坐标，半径不变
                self.points[0] += dx  # center_x
                self.points[1] += dy  # center_y
                # points[2] 是半径，不需要改变
            else:
                # 对于其他形状，更新所有坐标点
                for i in range(0, len(self.points), 2):
                    self.points[i] += dx      # x坐标
                    if i + 1 < len(self.points):
                        self.points[i + 1] += dy  # y坐标
        
        # 更新多边形点坐标
        if self.polygon_points:
            updated_points = []
            for x, y in self.polygon_points:
                updated_points.append((x + dx, y + dy))
            self.polygon_points = updated_points

    def scale(self, factor):
        if self.is_placeholder:
            return
        if self.x_center is not None:
            self.x_center *= factor
        if self.y_center is not None:
            self.y_center *= factor
        if self.shape_type == 'circle':
            if self.radius is not None:
                self.radius *= factor
            if self.points and len(self.points) >= 3:
                self.points[0] = self.x_center if self.x_center is not None else self.points[0]
                self.points[1] = self.y_center if self.y_center is not None else self.points[1]
                self.points[2] = self.radius
            self.width = (self.radius * 2) if self.radius is not None else self.width
            self.height = (self.radius * 2) if self.radius is not None else self.height
        elif self.shape_type == 'rectangle':
            if self.points and len(self.points) >= 8:
                scaled = []
                for i in range(0, 8):
                    v = self.points[i] * factor
                    scaled.append(v)
                self.points[:8] = scaled
                self._update_center_and_size_from_points()
            else:
                if self.width is not None:
                    self.width *= factor
                if self.height is not None:
                    self.height *= factor
        elif self.shape_type == 'polygon' or self.shape_type == 'polygon_mask':
            if self.polygon_points:
                self.polygon_points = [(x * factor, y * factor) for (x, y) in self.polygon_points]
                xs = [p[0] for p in self.polygon_points]
                ys = [p[1] for p in self.polygon_points]
                if xs and ys:
                    self.x_center = sum(xs) / len(xs)
                    self.y_center = sum(ys) / len(ys)
                    self.width = (max(xs) - min(xs))
                    self.height = (max(ys) - min(ys))
        elif self.shape_type == 'line':
            if self.points and len(self.points) >= 4:
                x1, y1, x2, y2 = self.points[0], self.points[1], self.points[2], self.points[3]
                x1 *= factor; y1 *= factor; x2 *= factor; y2 *= factor
                self.points[0] = x1; self.points[1] = y1; self.points[2] = x2; self.points[3] = y2
                self.x_center = (x1 + x2) / 2.0
                self.y_center = (y1 + y2) / 2.0
                self.width = abs(x2 - x1)
                self.height = abs(y2 - y1)
        elif self.shape_type == 'point':
            pass
        if hasattr(self, 'corner_points') and getattr(self, 'corner_points'):
            try:
                self.corner_points = [(x * factor, y * factor) for (x, y) in self.corner_points]
            except Exception:
                pass

    def set_rotation_angle(self, angle):
        """设置旋转角度（以标签中心为旋转中心），自动规范化到0-360度范围"""
        # 规范化角度到0-360度范围
        normalized_angle = angle % MAX_ROTATION_ANGLE
        if normalized_angle < MIN_ROTATION_ANGLE:
            normalized_angle += MAX_ROTATION_ANGLE
        self.rotation_angle = normalized_angle
        
    def get_rotation_angle(self):
        """获取旋转角度"""
        return self.rotation_angle
        
    def rotate(self, angle):
        """旋转指定角度（以标签中心为旋转中心），自动规范化到0-360度范围"""
        self.rotation_angle = (self.rotation_angle + angle) % MAX_ROTATION_ANGLE
        if self.rotation_angle < MIN_ROTATION_ANGLE:
            self.rotation_angle += MAX_ROTATION_ANGLE
            
    def normalize_angle(self, angle):
        """将角度规范化到0-360度范围"""
        normalized_angle = angle % MAX_ROTATION_ANGLE
        if normalized_angle < MIN_ROTATION_ANGLE:
            normalized_angle += MAX_ROTATION_ANGLE
        return normalized_angle
        
    def degrees_to_radians(self, angle_deg):
        """将角度转换为弧度"""
        return angle_deg * DEG_TO_RAD
        
    def radians_to_degrees(self, angle_rad):
        """将弧度转换为角度"""
        return angle_rad * RAD_TO_DEG
        
    def get_rotated_polygon_points(self):
        """获取旋转后的多边形点坐标（基于顶点坐标）"""
        if self.shape_type == 'polygon' or self.shape_type == 'polygon_mask':
            # 对于多边形，使用现有的旋转逻辑
            if not self.polygon_points:
                return []
                
            # 使用辅助方法将角度转换为弧度
            angle_rad = self.degrees_to_radians(self.rotation_angle)
            
            # 计算旋转后的点坐标（以多边形中心为旋转中心）
            rotated_points = []
            for x, y in self.polygon_points:
                # 将点平移到以中心点为原点的坐标系
                x_translated = x - self.x_center
                y_translated = y - self.y_center
                
                # 以中心点为旋转中心进行旋转
                x_rotated = x_translated * math.cos(angle_rad) - y_translated * math.sin(angle_rad)
                y_rotated = x_translated * math.sin(angle_rad) + y_translated * math.cos(angle_rad)
                
                # 将点平移回原坐标系
                x_final = x_rotated + self.x_center
                y_final = y_rotated + self.y_center
                
                rotated_points.append((x_final, y_final))
                
            return rotated_points
        
        elif self.shape_type == 'rectangle':
            # 对于矩形，使用顶点坐标
            if not self.points or len(self.points) < 8:
                # 如果没有顶点坐标但有中心点和宽高，则计算顶点坐标
                if self.x_center is None or self.y_center is None or self.width is None or self.height is None:
                    return []
                
                # 计算未旋转的四个角点坐标
                half_width = self.width / 2
                half_height = self.height / 2
                
                # 四个角点（左上、右上、右下、左下）
                corners = [
                    (self.x_center - half_width, self.y_center - half_height),  # 左上
                    (self.x_center + half_width, self.y_center - half_height),  # 右上
                    (self.x_center + half_width, self.y_center + half_height),  # 右下
                    (self.x_center - half_width, self.y_center + half_height)   # 左下
                ]
                
                # 如果有旋转角度，应用旋转变换
                if self.rotation_angle != 0:
                    angle_rad = math.radians(self.rotation_angle)
                    cos_angle = math.cos(angle_rad)
                    sin_angle = math.sin(angle_rad)
                    
                    rotated_corners = []
                    for x, y in corners:
                        # 将点平移到原点
                        x_translated = x - self.x_center
                        y_translated = y - self.y_center
                        
                        # 旋转
                        x_rotated = x_translated * cos_angle - y_translated * sin_angle
                        y_rotated = x_translated * sin_angle + y_translated * cos_angle
                        
                        # 平移回原位置
                        x_final = x_rotated + self.x_center
                        y_final = y_rotated + self.y_center
                        
                        rotated_corners.append((x_final, y_final))
                    
                    corners = rotated_corners
                
                # 更新points属性
                self.points = []
                for x, y in corners:
                    self.points.extend([x, y])
                
                return corners
            
            # 如果已有顶点坐标，直接返回
            else:
                return self.get_rectangle_points()
        
        return []
        
    def get_rotated_rect_corners(self):
        """获取旋转后矩形的四个角点坐标（基于顶点坐标）"""
        if self.shape_type != 'rectangle':
            return []
        
        # 如果没有顶点坐标但有中心点和宽高，则计算顶点坐标
        if not self.points and self.x_center is not None and self.y_center is not None and self.width is not None and self.height is not None:
            # 计算未旋转的四个角点坐标
            half_width = self.width / 2
            half_height = self.height / 2
            
            # 四个角点（左上、右上、右下、左下）
            corners = [
                (self.x_center - half_width, self.y_center - half_height),  # 左上
                (self.x_center + half_width, self.y_center - half_height),  # 右上
                (self.x_center + half_width, self.y_center + half_height),  # 右下
                (self.x_center - half_width, self.y_center + half_height)   # 左下
            ]
            
            # 如果有旋转角度，应用旋转变换
            if self.rotation_angle != 0:
                angle_rad = math.radians(self.rotation_angle)
                cos_angle = math.cos(angle_rad)
                sin_angle = math.sin(angle_rad)
                
                rotated_corners = []
                for x, y in corners:
                    # 将点平移到原点
                    x_translated = x - self.x_center
                    y_translated = y - self.y_center
                    
                    # 旋转
                    x_rotated = x_translated * cos_angle - y_translated * sin_angle
                    y_rotated = x_translated * sin_angle + y_translated * cos_angle
                    
                    # 平移回原位置
                    x_final = x_rotated + self.x_center
                    y_final = y_rotated + self.y_center
                    
                    rotated_corners.append((x_final, y_final))
                
                corners = rotated_corners
            
            # 更新points属性
            self.points = []
            for x, y in corners:
                self.points.extend([x, y])
            
            return corners
        
        # 如果已有顶点坐标，直接返回
        elif self.points and len(self.points) >= 8:
            return self.get_rectangle_points()
        
        return []

    def to_yolov(self, image_width=None, image_height=None):
        """将子标签的实际坐标转换为YOLOv格式的归一化坐标（基于顶点坐标）"""
        if self.is_placeholder:
            return ''
            
        if self.shape_type == 'polygon' or self.shape_type == 'polygon_mask':
            # 对于多边形，使用多边形点信息
            if not self.polygon_points:
                return ''
            
            # 获取多边形的所有顶点
            polygon_points = self.polygon_points
            
            # 计算多边形的边界框
            x_coords = [p[0] for p in polygon_points]
            y_coords = [p[1] for p in polygon_points]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # 计算中心点和宽高
            x_center = (min_x + max_x) / 2
            y_center = (min_y + max_y) / 2
            width = max_x - min_x
            height = max_y - min_y
            
        elif self.shape_type == 'rectangle':
            # 对于矩形，使用顶点坐标计算中心点和宽高
            if not self.points or len(self.points) < 8:
                # 如果没有顶点坐标，使用原有的中心点和宽高
                if self.x_center is None or self.y_center is None or self.width is None or self.height is None:
                    return ''
                
                x_center = self.x_center
                y_center = self.y_center
                width = self.width
                height = self.height
            else:
                # 从顶点坐标计算中心点和宽高
                x_coords = [self.points[i] for i in range(0, len(self.points), 2)]
                y_coords = [self.points[i+1] for i in range(0, len(self.points), 2)]
                
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)
                
                x_center = (min_x + max_x) / 2
                y_center = (min_y + max_y) / 2
                width = max_x - min_x
                height = max_y - min_y
        else:
            return ''
        
        # 如果没有提供图片尺寸，尝试从image_info获取
        if image_width is None or image_height is None:
            if hasattr(self, 'image_info') and self.image_info:
                # 尝试从图片路径获取图片尺寸
                try:
                    from PyQt6.QtGui import QImageReader
                    reader = QImageReader(self.image_info)
                    if reader.canRead():
                        size = reader.size()
                        image_width = size.width()
                        image_height = size.height()
                except Exception:
                    pass
        
        # 如果仍然没有获取到图片尺寸，无法进行归一化
        if image_width is None or image_height is None or image_width <= 0 or image_height <= 0:
            # 返回实际坐标，但添加警告
            logger.warning(f"无法获取图片尺寸，返回实际坐标: {x_center}, {y_center}, {width}, {height}")
            return f"{self.class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        
        # 归一化坐标
        x_center_norm = x_center / image_width
        y_center_norm = y_center / image_height
        width_norm = width / image_width
        height_norm = height / image_height
        
        return f"{self.class_id} {x_center_norm:.6f} {y_center_norm:.6f} {width_norm:.6f} {height_norm:.6f}"

    def save_screenshot(self, qimage, save_dir='temp_crops'):
        """
        截取当前框选区域的图片并保存到save_dir，路径赋值给self.screenshot。
        qimage: 当前画布QImage
        """
        import os
        import time
        if self.is_placeholder or not all([self.x_center is not None, self.y_center is not None, self.width is not None, self.height is not None]):
            return None
        iw, ih = qimage.width(), qimage.height()
        # 实际坐标（像素），超出部分自动截断
        x1 = max(0, int(self.x_center - self.width/2))
        y1 = max(0, int(self.y_center - self.height/2))
        x2 = min(iw, int(self.x_center + self.width/2))
        y2 = min(ih, int(self.y_center + self.height/2))
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            return None
        crop = qimage.copy(x1, y1, w, h)
        os.makedirs(save_dir, exist_ok=True)
        # 使用时间戳和随机数生成唯一文件名
        timestamp = int(time.time() * 1000)
        filename = f'{self.class_name}_{self.class_id}_{timestamp}_{id(self) % 10000}.png'
        save_path = os.path.join(save_dir, filename)
        crop.save(save_path)
        self.screenshot = save_path
        return save_path

    def set_polygon_points(self, polygon_points):
        """设置多边形点信息"""
        self.shape_type = 'polygon'
        self.polygon_points = polygon_points
        
    def get_polygon_points(self):
        """获取多边形点信息"""
        return self.polygon_points if (self.shape_type == 'polygon' or self.shape_type == 'polygon_mask') else []
        
    def is_point_inside(self, x, y):
        """
        检查点(x, y)是否在标签内
        x, y: 实际坐标(像素)
        支持 polygon、rectangle、line、point。
        """
        if self.is_placeholder:
            return False

        # 点形状：距离中心点在阈值内
        if self.shape_type == 'point':
            if self.x_center is None or self.y_center is None:
                # 若未设置中心点，尝试从points中取
                if self.points and len(self.points) >= 2:
                    cx, cy = self.points[0], self.points[1]
                else:
                    return False
            else:
                cx, cy = self.x_center, self.y_center
            tol = 5.0  # 像素容差
            dx = x - cx
            dy = y - cy
            return (dx*dx + dy*dy) <= (tol*tol)

        # 线段形状：点到线段的最短距离在阈值内
        if self.shape_type == 'line':
            if not self.points or len(self.points) < 4:
                return False
            # 线段端点
            x1, y1, x2, y2 = self.points[0], self.points[1], self.points[2], self.points[3]
            # 若存在旋转，按中心旋转端点
            if self.rotation_angle and self.x_center is not None and self.y_center is not None:
                angle_rad = self.degrees_to_radians(self.rotation_angle)
                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                def rot(px, py):
                    tx = px - self.x_center
                    ty = py - self.y_center
                    rx = tx * cos_a - ty * sin_a
                    ry = tx * sin_a + ty * cos_a
                    return rx + self.x_center, ry + self.y_center
                x1, y1 = rot(x1, y1)
                x2, y2 = rot(x2, y2)
            # 计算点到线段距离
            def dist_to_seg(px, py, ax, ay, bx, by):
                vx = bx - ax
                vy = by - ay
                wx = px - ax
                wy = py - ay
                c1 = vx*wx + vy*wy
                if c1 <= 0:
                    dx = px - ax
                    dy = py - ay
                    return math.hypot(dx, dy)
                c2 = vx*vx + vy*vy
                if c2 <= 0:
                    dx = px - ax
                    dy = py - ay
                    return math.hypot(dx, dy)
                t = c1 / c2
                if t >= 1:
                    dx = px - bx
                    dy = py - by
                    return math.hypot(dx, dy)
                projx = ax + t * vx
                projy = ay + t * vy
                dx = px - projx
                dy = py - projy
                return math.hypot(dx, dy)
            tol = 5.0
            return dist_to_seg(x, y, x1, y1, x2, y2) <= tol
            
        # 检查是否是OBB标签，如果是，使用corner_points进行检测
        if hasattr(self, 'is_obb') and self.is_obb and hasattr(self, 'corner_points') and self.corner_points:
            # 使用OBB的角点坐标进行多边形检测
            return self._point_in_polygon(x, y, self.corner_points)
            
        # 处理多边形和多边形MASK类型
        if (self.shape_type == 'polygon' or self.shape_type == 'polygon_mask') and self.polygon_points:
            # 对于polygon_mask类型，如果有原始MASK数据，优先使用MASK数据进行点检测
            if self.shape_type == 'polygon_mask' and hasattr(self, 'mask_data') and self.mask_data is not None:
                try:
                    # 使用原始MASK数据进行点检测
                    mask_np = self.mask_data
                    # 确保坐标在MASK范围内
                    if 0 <= int(y) < mask_np.shape[0] and 0 <= int(x) < mask_np.shape[1]:
                        return bool(mask_np[int(y), int(x)])
                    return False
                except Exception:
                    # 如果MASK数据检测失败，回退到多边形点检测
                    pass
            
            # 如果有旋转角度，使用旋转后的点
            if self.rotation_angle != 0:
                rotated_points = self.get_rotated_polygon_points()
                return self._point_in_polygon(x, y, rotated_points)
            else:
                # 没有旋转，使用原始点
                return self._point_in_polygon(x, y, self.polygon_points)
        elif self.shape_type == 'rectangle':
            # 如果有旋转角度，需要特殊处理（以矩形中心为旋转中心）
            if self.rotation_angle != 0:
                # 将点转换到矩形的局部坐标系（以矩形中心为原点）
                x_translated = x - self.x_center
                y_translated = y - self.y_center
                
                # 将点反向旋转相同的角度（以矩形中心为旋转中心）
                angle_rad = -self.degrees_to_radians(self.rotation_angle)
                x_rotated = x_translated * math.cos(angle_rad) - y_translated * math.sin(angle_rad)
                y_rotated = x_translated * math.sin(angle_rad) + y_translated * math.cos(angle_rad)
                
                # 检查旋转后的点是否在未旋转的矩形内
                half_width = self.width / 2
                half_height = self.height / 2
                
                return (-half_width <= x_rotated <= half_width and 
                        -half_height <= y_rotated <= half_height)
            else:
                # 没有旋转，使用普通矩形检查
                if None in (self.x_center, self.y_center, self.width, self.height):
                    return False
                    
                # 计算矩形框的边界
                x1 = self.x_center - self.width / 2
                y1 = self.y_center - self.height / 2
                x2 = self.x_center + self.width / 2
                y2 = self.y_center + self.height / 2
                
                # 检查点是否在边界内
                return x1 <= x <= x2 and y1 <= y <= y2
        
        return False

    def _point_in_polygon(self, x, y, polygon):
        """
        使用射线法判断点是否在多边形内
        x, y: 实际坐标(像素)
        polygon: 多边形点列表，每个点为(x, y)元组
        """
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
            
        return inside
        
    def __str__(self):
        """返回子标签的字符串表示（基于顶点坐标）"""
        if self.is_placeholder:
            return ''
        
        points_to_display = []
        
        if self.shape_type == 'polygon' or self.shape_type == 'polygon_mask':
            if self.polygon_points:
                points_to_display = self.polygon_points
        
        elif self.shape_type == 'rectangle':
            if self.points and len(self.points) >= 8:
                points_to_display = self.get_rectangle_points()
            elif self.x_center is not None and self.y_center is not None and self.width is not None and self.height is not None:
                 try:
                     points_to_display = self.get_rotated_rect_corners()
                 except Exception:
                     half_w, half_h = self.width / 2, self.height / 2
                     cx, cy = self.x_center, self.y_center
                     points_to_display = [
                         (cx - half_w, cy - half_h),
                         (cx + half_w, cy - half_h),
                         (cx + half_w, cy + half_h),
                         (cx - half_w, cy + half_h)
                     ]

        elif self.shape_type == 'line':
            if self.points and len(self.points) >= 4:
                points_to_display = [(self.points[0], self.points[1]), (self.points[2], self.points[3])]
        
        elif self.shape_type == 'point':
            if self.x_center is not None and self.y_center is not None:
                points_to_display = [(self.x_center, self.y_center)]
            elif self.points and len(self.points) >= 2:
                points_to_display = [(self.points[0], self.points[1])]
        
        points_str = ""
        if points_to_display:
            formatted_points = [f"({x:.1f},{y:.1f})" for x, y in points_to_display]
            full_str = ', '.join(formatted_points)
            
            if len(full_str) > 40:
                 if len(formatted_points) >= 2:
                      points_str = f"{formatted_points[0]}, {formatted_points[1]}, ..."
                 else:
                      points_str = full_str[:37] + "..."
            else:
                 points_str = full_str

        return f"{self.class_name}|{self.class_id}|point=[{points_str}]"

def create_child_label(parent_label, points=None, x_center=None, y_center=None, width=None, height=None, mode='manual', image_info=None, is_placeholder=False, shape_type='rectangle', polygon_points=None, rotation_angle=0, mask_data=None):
    """
    创建子标签的便捷函数（支持顶点坐标和中心点宽高两种表示方式）
    
    参数:
        parent_label: 父标签对象
        points: 顶点坐标列表 [x1, y1, x2, y2, x3, y3, x4, y4]（矩形）或 [x1, y1, x2, y2, ..., xn, yn]（多边形）
        x_center, y_center: 中心点坐标（实际坐标/像素）（与points二选一）
        width, height: 宽高（实际坐标/像素）（与points二选一）
        mode: 'manual' or 'auto'
        image_info: 图片信息
        is_placeholder: 是否为占位符
        shape_type: 'rectangle' or 'polygon'
        polygon_points: 多边形点列表
        rotation_angle: 旋转角度（度数，将自动规范化到0-360度范围，以标签中心为旋转中心）
        mask_data: 原始MASK数据（仅用于polygon_mask类型）
    
    返回:
        ChildLabel对象
    """
    # 优先使用顶点坐标
    if points is not None:
        child_label = ChildLabel(
            parent_label=parent_label,
            points=points,
            mode=mode,
            image_info=image_info,
            is_placeholder=is_placeholder,
            shape_type=shape_type,
            polygon_points=polygon_points,
            rotation_angle=rotation_angle,
            mask_data=mask_data
        )
    # 如果没有顶点坐标但有中心点和宽高，则使用中心点和宽高
    elif x_center is not None and y_center is not None and width is not None and height is not None:
        # 创建临时ChildLabel对象
        child_label = ChildLabel(
            parent_label=parent_label,
            points=None,
            mode=mode,
            image_info=image_info,
            is_placeholder=is_placeholder,
            shape_type=shape_type,
            polygon_points=polygon_points,
            rotation_angle=rotation_angle,
            mask_data=mask_data
        )
        
        # 设置中心点和宽高
        child_label.x_center = x_center
        child_label.y_center = y_center
        child_label.width = width
        child_label.height = height
        
        # 如果是矩形，计算顶点坐标
        if shape_type == 'rectangle':
            # 计算未旋转的四个角点坐标
            half_width = width / 2
            half_height = height / 2
            
            # 四个角点（左上、右上、右下、左下）
            corners = [
                (x_center - half_width, y_center - half_height),  # 左上
                (x_center + half_width, y_center - half_height),  # 右上
                (x_center + half_width, y_center + half_height),  # 右下
                (x_center - half_width, y_center + half_height)   # 左下
            ]
            
            # 如果有旋转角度，应用旋转变换
            if rotation_angle != 0:
                angle_rad = math.radians(rotation_angle)
                cos_angle = math.cos(angle_rad)
                sin_angle = math.sin(angle_rad)
                
                rotated_corners = []
                for x, y in corners:
                    # 将点平移到原点
                    x_translated = x - x_center
                    y_translated = y - y_center
                    
                    # 旋转
                    x_rotated = x_translated * cos_angle - y_translated * sin_angle
                    y_rotated = x_translated * sin_angle + y_translated * cos_angle
                    
                    # 平移回原位置
                    x_final = x_rotated + x_center
                    y_final = y_rotated + y_center
                    
                    rotated_corners.append((x_final, y_final))
                
                corners = rotated_corners
            
            # 更新points属性
            child_label.points = []
            for x, y in corners:
                child_label.points.extend([x, y])
    else:
        # 如果没有提供足够的坐标信息，创建空标签
        child_label = ChildLabel(
            parent_label=parent_label,
            points=None,
            mode=mode,
            image_info=image_info,
            is_placeholder=is_placeholder,
            shape_type=shape_type,
            polygon_points=polygon_points,
            rotation_angle=rotation_angle
        )
    
    return child_label

class IndicatorListWidgetItem(QListWidgetItem):
    def __init__(self, label: str, selected: bool = False, color: QColor = None):
        super().__init__(label)
        self.selected = selected
        self.color = color  # 存储标签颜色

class IndicatorListWidget(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setIconSize(QSize(16, 16))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, position):
        """显示右键菜单"""
        # 获取点击位置的项
        item = self.itemAt(position)
        if item is None:
            return
            
        # 创建菜单
        menu = QMenu()
        edit_action = menu.addAction("编辑标签")
        delete_action = menu.addAction("删除父标签")
        
        # 显示菜单并获取选择的操作
        action = menu.exec(self.mapToGlobal(position))
        
        # 处理菜单操作
        if action == edit_action:
            # 获取父控件(ParentLabelList)并调用编辑方法
            parent_widget = self.parent()
            while parent_widget and not isinstance(parent_widget, ParentLabelList):
                parent_widget = parent_widget.parent()
                
            if parent_widget:
                row = self.row(item)
                parent_widget.edit_label(row)
        elif action == delete_action:
            parent_widget = self.parent()
            while parent_widget and not isinstance(parent_widget, ParentLabelList):
                parent_widget = parent_widget.parent()
            if parent_widget:
                from PyQt6.QtWidgets import QMessageBox
                row = self.row(item)
                confirm = QMessageBox.question(self, "确认删除", "是否删除该父标签？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if confirm == QMessageBox.StandardButton.Yes:
                    for idx, label in enumerate(parent_widget.labels):
                        label.selected = (idx == row)
                        self.setIndicator(idx, label.selected)
                    deleted = parent_widget.delete_selected_label()
                    if deleted:
                        parent_widget.child_label_list.set_labels([])

    def addIndicatorItem(self, label: str, selected: bool = False, color: QColor = None):
        item = IndicatorListWidgetItem(label, selected, color)
        icon = self._make_icon(selected, color)
        item.setIcon(QIcon(icon))
        self.addItem(item)

    def setIndicator(self, row: int, selected: bool):
        item = self.item(row)
        if isinstance(item, IndicatorListWidgetItem):
            item.selected = selected
            item.setIcon(QIcon(self._make_icon(selected, item.color)))

    def _make_icon(self, selected: bool, color: QColor = None):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        
        # 使用标签颜色或默认颜色
        if color:
            indicator_color = color if selected else QColor(color.red(), color.green(), color.blue(), 100)
        else:
            indicator_color = QColor(0, 200, 0) if selected else QColor(180, 180, 180)
            
        painter.setBrush(indicator_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        return pixmap

class ParentLabelList(QWidget):
    labels_changed = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.addWidget(QLabel('父标签列表'))
        self.list_widget = IndicatorListWidget()
        layout.addWidget(self.list_widget)
        # 创建新标签按钮
        self.btn_add = QPushButton('创建新标签')
        self.btn_add.clicked.connect(self.create_new_label)
        layout.addWidget(self.btn_add)
        # 子标签分页列表
        self.child_label_list = PagedChildLabelList()
        layout.addWidget(self.child_label_list)
        self.setLayout(layout)
        self.labels = []  # 存储ParentLabel对象
        self.name_id_set = set()  # 用于唯一性校验
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.current_image_info = None
        # 添加main_window属性
        self.main_window = None
        # 如果有父窗口，尝试获取MainWindow实例
        if parent:
            p = parent
            while p and not isinstance(p, QMainWindow):
                p = p.parent()
            if p:
                self.main_window = p

    def set_current_image_info(self, image_info, total=0, current_idx=0):
        self.current_image_info = image_info
        self.child_label_list.set_current_image_info(image_info, total, current_idx)
        # 只判断选中父标签
        parent = self.get_selected()
        if parent and hasattr(parent, 'children_by_image') and image_info in parent.children_by_image:
            visible = [c for c in parent.children_by_image[image_info] if not getattr(c, 'is_placeholder', False)]
            if visible:
                self.child_label_list.set_labels(visible)
            else:
                self.child_label_list.set_labels(["没有该类别子标签"])
        else:
            self.child_label_list.set_labels([])

    def create_new_label(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('新建父标签')
        try:
            dialog.setModal(True)
        except Exception:
            pass
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        from PyQt6.QtWidgets import QFormLayout
        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(8)
        name_input = QLineEdit()
        name_input.setPlaceholderText('例如：Car、Building、Tree')
        id_input = QSpinBox()
        id_input.setRange(0, 999999)
        # 自动填充为当前最大ID+1
        if self.labels:
            max_id = max(label.id for label in self.labels)
            id_input.setValue(max_id + 1)
        else:
            id_input.setValue(0)
        form.addRow(QLabel('类别名称'), name_input)
        form.addRow(QLabel('类别ID'), id_input)
        layout.addLayout(form)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 6, 0, 0)
        btn_layout.addStretch()
        btn_ok = QPushButton('确定')
        try:
            btn_ok.setDefault(True)
        except Exception:
            pass
        btn_cancel = QPushButton('取消')
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        dialog.setStyleSheet(
            'QDialog{background:#FAFAF2;border:1px solid #E6E4D6;border-radius:8px;}'
            'QLineEdit{border:1px solid #D0D0D0;border-radius:4px;padding:4px;}'
            'QLineEdit:focus{border:1px solid #4CAF50;}'
            'QSpinBox{border:1px solid #D0D0D0;border-radius:4px;padding:2px;}'
            'QPushButton{background-color:#EDEFEA;color:#333333;border:none;border-radius:4px;padding:6px 12px;}'
            'QPushButton:hover{background-color:#EEEDE6;}'
            'QPushButton:disabled{background-color:#9aa6b2;color:#eee;}'
        )
        def try_accept():
            name = name_input.text().strip()
            id_ = int(id_input.value())
            if not name:
                QMessageBox.warning(dialog, '错误', '类别名称不能为空')
                return
            if (name, id_) in self.name_id_set or any(l.name == name or l.id == id_ for l in self.labels):
                QMessageBox.warning(dialog, '错误', '类别名称或ID已存在')
                return
            dialog.accept()
        btn_ok.clicked.connect(try_accept)
        btn_cancel.clicked.connect(dialog.reject)
        try:
            name_input.setFocus()
        except Exception:
            pass
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.add_label(name_input.text().strip(), int(id_input.value()))

    def add_label(self, name, id_):
        # 唯一性校验
        if (name, id_) in self.name_id_set:
            return False
        for label in self.labels:
            if label.name == name or label.id == id_:
                return False
        label = ParentLabel(name, id_)
        # 自动为每个父标签添加一个空子标签（不可见、不可删除）
        placeholder = ChildLabel(label, is_placeholder=True)
        label.children_by_image = {}
        label.children_by_image['__placeholder__'] = [placeholder]
        self.labels.append(label)
        self.name_id_set.add((name, id_))
        
        # 先取消所有标签的选中状态
        for idx, existing_label in enumerate(self.labels):
            existing_label.selected = False
            self.list_widget.setIndicator(idx, False)
            
        # 添加新标签到列表并设置为选中状态
        new_item_idx = len(self.labels) - 1
        self.list_widget.addIndicatorItem(str(label), selected=True, color=label.color)
        label.selected = True
        
        # 更新子标签列表显示
        if self.current_image_info:
            visible = [c for c in label.children_by_image.get(self.current_image_info, []) if not getattr(c, 'is_placeholder', False)]
            self.child_label_list.set_labels(visible or ["没有该类别子标签"])
        else:
            self.child_label_list.set_labels([])
            
        return True

    def set_labels(self, label_list):
        """label_list: list of (name, id, [children])"""
        self.list_widget.clear()
        # 保留原有children_by_image
        old_map = { (l.name, l.id): getattr(l, 'children_by_image', {}) for l in self.labels }
        old_colors = { (l.name, l.id): getattr(l, 'color', None) for l in self.labels }
        self.labels = []
        self.name_id_set = set()
        for entry in label_list:
            name, id_ = entry[0], entry[1]
            children = entry[2] if len(entry) > 2 else []
            if (name, id_) in self.name_id_set:
                continue
            label = ParentLabel(name, id_)
            # 恢复原有颜色（如果存在）
            if (name, id_) in old_colors and old_colors[(name, id_)]:
                label.color = old_colors[(name, id_)]
            label.children = children
            # 恢复children_by_image
            if (name, id_) in old_map:
                label.children_by_image = old_map[(name, id_)]
            self.labels.append(label)
            self.name_id_set.add((name, id_))
            self.list_widget.addIndicatorItem(str(label), selected=False, color=label.color)

    def on_item_clicked(self, item):
        if len(self.labels) == 1:
            label = self.labels[0]
            label.selected = not label.selected
            self.list_widget.setIndicator(0, label.selected)
            if label.selected and self.current_image_info:
                visible = [c for c in label.children_by_image.get(self.current_image_info, []) if not getattr(c, 'is_placeholder', False)]
                self.child_label_list.set_labels(visible or ["没有该类别子标签"])
            else:
                self.child_label_list.set_labels([])
            return

        # 多个父标签情况下：仅将被点击项设为选中，其他取消选中
        for idx, label in enumerate(self.labels):
            label.selected = (self.list_widget.item(idx) == item)
            self.list_widget.setIndicator(idx, label.selected)
        parent = self.get_selected()
        if parent and self.current_image_info:
            visible = [c for c in parent.children_by_image.get(self.current_image_info, []) if not getattr(c, 'is_placeholder', False)]
            self.child_label_list.set_labels(visible or ["没有该类别子标签"])
        else:
            self.child_label_list.set_labels([])

    def get_selected(self):
        for label in self.labels:
            if label.selected:
                return label
        return None

    def delete_selected_label(self):
        """
        删除当前选中的父标签及其所有相关信息（包括子标签、矩形框、截图、坐标信息等）。
        仅实现方法，不添加按钮或其他 UI 触发。
        """
        selected_idx = None
        for idx, label in enumerate(self.labels):
            if label.selected:
                selected_idx = idx
                break
        if selected_idx is not None:
            label = self.labels.pop(selected_idx)
            self.name_id_set.discard((label.name, label.id))
            self.list_widget.takeItem(selected_idx)
            try:
                if hasattr(label, 'children_by_image') and isinstance(label.children_by_image, dict):
                    for image_info, children in list(label.children_by_image.items()):
                        for child in list(children):
                            if getattr(child, 'screenshot', None):
                                try:
                                    import os
                                    if os.path.exists(child.screenshot):
                                        os.remove(child.screenshot)
                                except Exception:
                                    pass
                        label.children_by_image[image_info] = []
                label.children.clear()
            except Exception:
                pass
            try:
                if self.current_image_info:
                    self.child_label_list.set_labels([])
            except Exception:
                pass
            try:
                if self.labels:
                    last_idx = len(self.labels) - 1
                    for i, lb in enumerate(self.labels):
                        lb.selected = (i == last_idx)
                        self.list_widget.setIndicator(i, lb.selected)
                    try:
                        self.list_widget.setCurrentRow(last_idx)
                    except Exception:
                        pass
                    try:
                        if self.current_image_info:
                            parent = self.labels[last_idx]
                            visible = [c for c in parent.children_by_image.get(self.current_image_info, []) if not getattr(c, 'is_placeholder', False)]
                            self.child_label_list.set_labels(visible or ["没有该类别子标签"])
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if self.main_window and hasattr(self.main_window, 'canvas') and self.main_window.canvas:
                    self.main_window.canvas.update_rects()
            except Exception:
                pass
            try:
                self.labels_changed.emit()
            except Exception:
                pass
            return label
        return None

    def create_child_label(self, x_center=None, y_center=None, width=None, height=None, image_info=None, mode='manual', shape_type='rectangle', polygon_points=None, rotation_angle=0, points=None, mask_data=None):
        """
        在当前选中父标签下创建子标签。
        支持两种表示方式：
        1. 中心点和宽高（x_center, y_center, width, height）
        2. 顶点坐标（points）
        参数均为实际坐标（像素），image_info为图片信息（如路径）。
        mask_data为原始MASK数据，用于polygon_mask类型标签。
        """
        parent = self.get_selected()
        if parent is None:
            return None
            
        # 分页存储
        if not hasattr(parent, 'children_by_image'):
            parent.children_by_image = {}
        if image_info not in parent.children_by_image:
            parent.children_by_image[image_info] = []
            
        # 优先使用顶点坐标创建子标签
        if points is not None:
            # 直接使用ChildLabel构造函数创建子标签
            child = ChildLabel(
                parent_label=parent,
                points=points,
                mode=mode,
                image_info=image_info,
                shape_type=shape_type,
                polygon_points=polygon_points,
                rotation_angle=rotation_angle,
                mask_data=mask_data
            )
        else:
            # 使用中心点创建子标签（支持 rectangle 与 point）
            if shape_type == 'rectangle' and x_center is not None and y_center is not None and width is not None and height is not None:
                # 计算矩形的四个顶点坐标
                x1 = x_center - width / 2
                y1 = y_center - height / 2
                x2 = x_center + width / 2
                y2 = y_center - height / 2
                x3 = x_center + width / 2
                y3 = y_center + height / 2
                x4 = x_center - width / 2
                y4 = y_center + height / 2
                
                # 创建顶点坐标列表
                points = [x1, y1, x2, y2, x3, y3, x4, y4]
                
                # 使用顶点坐标创建子标签
                child = ChildLabel(
                    parent_label=parent,
                    points=points,
                    mode=mode,
                    image_info=image_info,
                    shape_type=shape_type,
                    polygon_points=polygon_points,
                    rotation_angle=rotation_angle,
                    mask_data=mask_data
                )
            elif shape_type == 'point' and x_center is not None and y_center is not None:
                # 使用中心点创建“点”标签
                child = ChildLabel(
                    parent_label=parent,
                    points=[x_center, y_center],
                    mode=mode,
                    image_info=image_info,
                    shape_type='point',
                    rotation_angle=rotation_angle
                )
            else:
                # 如果缺少必要的参数，创建一个空的子标签
                child = ChildLabel(
                    parent_label=parent,
                    mode=mode,
                    image_info=image_info,
                    shape_type=shape_type,
                    polygon_points=polygon_points,
                    rotation_angle=rotation_angle,
                    mask_data=mask_data
                )
            
        parent.children_by_image[image_info].append(child)
        
        # 更新当前页显示
        if self.current_image_info == image_info:
            self.child_label_list.set_labels(parent.children_by_image[image_info])
        return child
        
    def delete_child_label(self, child_label, image_info=None):
        """
        删除指定的子标签。
        
        参数:
        - child_label: 要删除的子标签对象
        - image_info: 图片信息，如果为None则使用当前图片信息
        
        返回:
        - 是否成功删除
        """
        if image_info is None:
            image_info = self.current_image_info
            
        if not image_info:
            return False
            
        # 查找子标签所属的父标签
        parent = None
        for p in self.labels:
            if hasattr(p, 'children_by_image') and image_info in p.children_by_image:
                if child_label in p.children_by_image[image_info]:
                    parent = p
                    break
        
        if not parent:
            return False
            
        # 删除截图文件
        if hasattr(child_label, 'screenshot') and child_label.screenshot:
            try:
                import os
                if os.path.exists(child_label.screenshot):
                    os.remove(child_label.screenshot)
            except Exception as e:
                logger.warning(f"删除截图文件失败: {e}")
        
        # 从列表中移除子标签
        parent.children_by_image[image_info].remove(child_label)
        
        if self.current_image_info == image_info:
            visible = [c for c in parent.children_by_image.get(image_info, []) if not getattr(c, 'is_placeholder', False)]
            self.child_label_list.set_labels(visible or ["没有该类别子标签"])
                
        return True

    def edit_label(self, row):
        """
        编辑指定行的父标签
        
        参数:
        - row: 标签在列表中的行索引
        """
        if row < 0 or row >= len(self.labels):
            return
            
        # 获取要编辑的标签
        label = self.labels[row]
        old_name = label.name
        old_id = label.id
        
        # 创建编辑对话框
        dialog = QDialog(self)
        dialog.setWindowTitle('编辑父标签')
        layout = QVBoxLayout(dialog)
        
        # 添加名称输入框
        layout.addWidget(QLabel('类别名称:'))
        name_input = QLineEdit()
        name_input.setText(label.name)
        layout.addWidget(name_input)
        
        # 添加ID输入框
        layout.addWidget(QLabel('类别ID:'))
        id_input = QSpinBox()
        id_input.setRange(0, 999999)
        id_input.setValue(label.id)
        layout.addWidget(id_input)
        
        # 添加按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton('确定')
        btn_cancel = QPushButton('取消')
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        # 验证输入并接受对话框
        def try_accept():
            name = name_input.text().strip()
            id_ = int(id_input.value())
            
            # 验证名称不为空
            if not name:
                QMessageBox.warning(dialog, '错误', '类别名称不能为空')
                return
                
            # 验证名称和ID的唯一性（排除自身）
            for idx, l in enumerate(self.labels):
                if idx != row and (l.name == name or l.id == id_):
                    QMessageBox.warning(dialog, '错误', '类别名称或ID已存在')
                    return
                    
            dialog.accept()
            
        btn_ok.clicked.connect(try_accept)
        btn_cancel.clicked.connect(dialog.reject)
        
        # 显示对话框并处理结果
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = name_input.text().strip()
            new_id = int(id_input.value())
            
            # 更新标签信息
            self.update_label(row, new_name, new_id)
    
    def update_label(self, row, new_name, new_id):
        """
        更新标签信息并同步更新所有关联数据
        
        参数:
        - row: 标签在列表中的行索引
        - new_name: 新的标签名称
        - new_id: 新的标签ID
        """
        if row < 0 or row >= len(self.labels):
            return False
            
        label = self.labels[row]
        old_name = label.name
        old_id = label.id
        
        # 如果名称和ID都没有变化，则不需要更新
        if old_name == new_name and old_id == new_id:
            return True
            
        # 更新name_id_set
        self.name_id_set.discard((old_name, old_id))
        self.name_id_set.add((new_name, new_id))
        
        # 更新父标签信息
        label.name = new_name
        label.id = new_id
        
        # 更新列表项显示
        self.list_widget.item(row).setText(f"{new_name} (ID: {new_id})")
        
        # 更新所有子标签的信息
        if hasattr(label, 'children_by_image'):
            for image_info, children in label.children_by_image.items():
                for child in children:
                    if not getattr(child, 'is_placeholder', False):
                        child.class_name = new_name
                        child.class_id = new_id
        
        # 如果当前有选中的图片，更新子标签列表显示
        if self.current_image_info and label.selected:
            if hasattr(label, 'children_by_image') and self.current_image_info in label.children_by_image:
                visible = [c for c in label.children_by_image[self.current_image_info] if not getattr(c, 'is_placeholder', False)]
                if visible:
                    self.child_label_list.set_labels(visible)
                else:
                    self.child_label_list.set_labels(["没有该类别子标签"])
        
        return True
            
    def get_child_labels_at_point(self, x, y, image_info=None):
        """
        获取指定点下所有标签（矩形或多边形），并按面积从小到大排序
        
        参数:
        - x, y: 实际坐标(像素)
        - image_info: 图片信息，如果为None则使用当前图片信息
        
        返回:
        - 按面积从小到大排序的子标签列表
        """
        if image_info is None:
            image_info = self.current_image_info
            
        if not image_info:
            return []
            
        # 收集所有包含该点的子标签
        labels_at_point = []
        for parent in self.labels:
            if hasattr(parent, 'children_by_image') and image_info in parent.children_by_image:
                for child in parent.children_by_image[image_info]:
                    if not child.is_placeholder and child.is_point_inside(x, y):
                        labels_at_point.append(child)
        
        # 按面积从小到大排序
        return sorted(labels_at_point, key=lambda child: child.get_area())
    
    def get_smallest_child_label_at_point(self, x, y, image_info=None):
        """
        获取指定点下面积最小的标签（矩形或多边形）
        
        参数:
        - x, y: 实际坐标(像素)
        - image_info: 图片信息，如果为None则使用当前图片信息
        
        返回:
        - 面积最小的子标签，如果没有则返回None
        """
        labels = self.get_child_labels_at_point(x, y, image_info)
        return labels[0] if labels else None
    
    def update_child_labels_for_image(self, image_info):
        """
        只显示当前选中父标签下，image_info为当前图片的子标签。
        """
        parent = self.get_selected()
        if parent is None:
            self.child_label_list.clear()
            return
        if hasattr(parent, 'children_by_image') and image_info in parent.children_by_image:
            self.child_label_list.set_labels(parent.children_by_image[image_info])
        else:
            self.child_label_list.clear()
    
    def select_next(self):
        """选择下一个父标签，循环切换"""
        if not self.labels:
            return False
            
        # 获取当前选中的标签索引
        current_idx = None
        for i, label in enumerate(self.labels):
            if label.selected:
                current_idx = i
                break
        
        # 计算下一个标签索引（循环）
        if current_idx is None:
            next_idx = 0  # 如果没有选中的，选择第一个
        else:
            next_idx = (current_idx + 1) % len(self.labels)
        
        # 更新选中状态
        for i, label in enumerate(self.labels):
            label.selected = (i == next_idx)
            self.list_widget.setIndicator(i, label.selected)

        # 更新列表选中、滚动并移动鼠标光标到当前项
        try:
            self.list_widget.setCurrentRow(next_idx)
            item = self.list_widget.item(next_idx)
            if item is not None:
                self.list_widget.scrollToItem(item)
                rect = self.list_widget.visualItemRect(item)
            self.list_widget.setFocus()
        except Exception:
            pass
        
        parent = self.get_selected()
        if parent and self.current_image_info:
            visible = [c for c in parent.children_by_image.get(self.current_image_info, []) if not getattr(c, 'is_placeholder', False)]
            self.child_label_list.set_labels(visible or ["没有该类别子标签"])
        else:
            self.child_label_list.set_labels([])
        
        return True
    
    def select_previous(self):
        """选择上一个父标签，循环切换"""
        if not self.labels:
            return False
            
        # 获取当前选中的标签索引
        current_idx = None
        for i, label in enumerate(self.labels):
            if label.selected:
                current_idx = i
                break
        
        # 计算上一个标签索引（循环）
        if current_idx is None:
            prev_idx = len(self.labels) - 1  # 如果没有选中的，选择最后一个
        else:
            prev_idx = (current_idx - 1 + len(self.labels)) % len(self.labels)
        
        # 更新选中状态
        for i, label in enumerate(self.labels):
            label.selected = (i == prev_idx)
            self.list_widget.setIndicator(i, label.selected)

        # 更新列表选中、滚动并移动鼠标光标到当前项
        try:
            self.list_widget.setCurrentRow(prev_idx)
            item = self.list_widget.item(prev_idx)
            if item is not None:
                self.list_widget.scrollToItem(item)
                rect = self.list_widget.visualItemRect(item)
            self.list_widget.setFocus()
        except Exception:
            pass
        
        parent = self.get_selected()
        if parent and self.current_image_info:
            visible = [c for c in parent.children_by_image.get(self.current_image_info, []) if not getattr(c, 'is_placeholder', False)]
            self.child_label_list.set_labels(visible or ["没有该类别子标签"])
        else:
            self.child_label_list.set_labels([])
        
        return True

class PagedChildLabelList(QWidget):
    child_hovered = pyqtSignal(object)
    child_delete_requested = pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.addWidget(QLabel('子标签列表（分页）'))
        self.page_label = QLabel('第 0 / 0 页')
        layout.addWidget(self.page_label)
        self.list_widget = QListWidget()
        self.list_widget.setMouseTracking(True)
        self.list_widget.itemEntered.connect(self._on_item_entered)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        self.current_image_info = None
        self.total_pages = 0
        self.current_page = 0

    def set_total_pages(self, total, current_idx):
        self.total_pages = total
        self.current_page = current_idx + 1 if total > 0 else 0
        self.page_label.setText(f'第 {self.current_page} / {self.total_pages} 页')

    def set_current_image_info(self, image_info, total=0, current_idx=0):
        self.current_image_info = image_info
        self.set_total_pages(total, current_idx)
        self.clear()

    def set_labels(self, labels):
        self.list_widget.clear()
        for label in labels:
            if isinstance(label, str):
                self.list_widget.addItem(label)
                continue
            if hasattr(label, 'is_placeholder') and label.is_placeholder:
                continue  # 不显示占位子标签
            item = QListWidgetItem(str(label))
            try:
                item.setData(Qt.ItemDataRole.UserRole, label)
            except Exception:
                pass
            self.list_widget.addItem(item)

    def clear(self):
        self.list_widget.clear()

    def _on_item_entered(self, item: QListWidgetItem):
        try:
            child = item.data(Qt.ItemDataRole.UserRole)
            if child:
                self.child_hovered.emit(child)
        except Exception:
            pass

    def _on_context_menu(self, position):
        try:
            item = self.list_widget.itemAt(position)
            if not item:
                return
            child = item.data(Qt.ItemDataRole.UserRole)
            if not child:
                return
            menu = QMenu(self)
            delete_action = menu.addAction('删除子标签')
            action = menu.exec(self.list_widget.mapToGlobal(position))
            if action == delete_action:
                from PyQt6.QtWidgets import QMessageBox
                confirm = QMessageBox.question(self, '确认删除', '是否删除该子标签？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if confirm == QMessageBox.StandardButton.Yes:
                    self.child_delete_requested.emit(child)
        except Exception:
            pass
