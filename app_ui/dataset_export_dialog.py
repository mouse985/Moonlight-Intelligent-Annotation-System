import os
import json
import shutil
import random
from typing import Dict, List, Tuple, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QProgressBar,
    QTextEdit, QGroupBox, QCheckBox, QFileDialog, QMessageBox,
    QTabWidget, QWidget, QGridLayout, QComboBox, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import numpy as np
from app_ui.labelsgl import ParentLabel, ChildLabel


class DatasetExportWorker(QThread):
    """数据集导出工作线程"""
    progress_updated = pyqtSignal(int)  # 进度更新信号
    status_updated = pyqtSignal(str)   # 状态更新信号
    export_finished = pyqtSignal(bool, str)  # 导出完成信号
    
    def __init__(self, main_window, export_path, export_format, train_ratio, normalize_coords=True, export_masks=False, use_dota_format=False):
        super().__init__()
        self.main_window = main_window
        self.export_path = export_path
        self.export_format = export_format
        self.train_ratio = train_ratio
        self.normalize_coords = normalize_coords  # 是否归一化坐标
        self.export_masks = export_masks  # 是否导出掩码图
        self.use_dota_format = use_dota_format  # 是否使用DOTA格式导出OBB标签
        
        # 从主窗口获取父标签
        self.parent_labels = main_window.parent_label_list
        
    def run(self):
        try:
            self.status_updated.emit("正在准备导出数据集...")
            
            # 创建导出目录结构
            os.makedirs(os.path.join(self.export_path, "images", "train"), exist_ok=True)
            os.makedirs(os.path.join(self.export_path, "images", "val"), exist_ok=True)
            os.makedirs(os.path.join(self.export_path, "labels", "train"), exist_ok=True)
            os.makedirs(os.path.join(self.export_path, "labels", "val"), exist_ok=True)
            
            # 如果需要导出掩码图，创建掩码图目录
            if self.export_masks:
                os.makedirs(os.path.join(self.export_path, "masks", "train"), exist_ok=True)
                os.makedirs(os.path.join(self.export_path, "masks", "val"), exist_ok=True)
            
            # 收集所有有标签的图片
            labeled_images = self._collect_labeled_images()
            total_images = len(labeled_images)
            
            if total_images == 0:
                self.export_finished.emit(False, "没有找到带有标签的图片")
                return
                
            # 随机打乱并分割训练集和验证集
            random.shuffle(labeled_images)
            split_idx = int(total_images * self.train_ratio)
            train_images = labeled_images[:split_idx]
            val_images = labeled_images[split_idx:]
            
            self.status_updated.emit(f"开始导出数据集，共{total_images}张图片（训练集：{len(train_images)}，验证集：{len(val_images)}）")
            
            # 导出训练集
            for i, image_path in enumerate(train_images):
                self._export_image_and_labels(image_path, "train")
                progress = int((i + 1) / total_images * 50)  # 训练集占50%进度
                self.progress_updated.emit(progress)
                self.status_updated.emit(f"正在导出训练集图片 {i+1}/{len(train_images)}")
            
            # 导出验证集
            for i, image_path in enumerate(val_images):
                self._export_image_and_labels(image_path, "val")
                progress = 50 + int((i + 1) / total_images * 50)  # 验证集占50%进度
                self.progress_updated.emit(progress)
                self.status_updated.emit(f"正在导出验证集图片 {i+1}/{len(val_images)}")
            
            # 创建数据集信息文件
            self._create_dataset_info(total_images, len(train_images), len(val_images))
            
            self.export_finished.emit(True, f"数据集导出成功！共导出{total_images}张图片")
            
        except Exception as e:
            self.export_finished.emit(False, f"导出过程中发生错误：{str(e)}")
    
    def _collect_labeled_images(self) -> List[str]:
        """收集所有有标签的图片路径"""
        labeled_images = set()
        
        for parent_label in self.parent_labels.labels:
            # 从children_by_image字典中获取所有图片的子标签
            if hasattr(parent_label, 'children_by_image'):
                for image_path, children in parent_label.children_by_image.items():
                    # 跳过占位符标签
                    for child in children:
                        if not getattr(child, 'is_placeholder', False):
                            labeled_images.add(image_path)
                            break  # 只要有一个非占位符子标签，就添加该图片
        
        return list(labeled_images)
    
    def _export_image_and_labels(self, image_path: str, split: str):
        """导出图片及其标签"""
        # 复制图片
        image_filename = os.path.basename(image_path)
        dest_image_path = os.path.join(self.export_path, "images", split, image_filename)
        shutil.copy2(image_path, dest_image_path)
        
        # 导出标签
        if self.export_format == "labelme":
            self._export_labelme_format(image_path, split)
        elif self.export_format == "yolo":
            self._export_yolo_format(image_path, split)
        
        # 如果需要导出掩码图，生成并保存掩码图
        if self.export_masks:
            self._export_mask_image(image_path, split)
    
    def _export_labelme_format(self, image_path: str, split: str):
        """导出LabelMe格式的JSON标签文件"""
        image_filename = os.path.basename(image_path)
        label_filename = os.path.splitext(image_filename)[0] + ".json"
        label_path = os.path.join(self.export_path, "labels", split, label_filename)
        
        # 获取图片尺寸
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                image_width, image_height = img.size
        except:
            image_width, image_height = 0, 0
        
        # 收集所有标签
        shapes = []
        for parent_label in self.parent_labels.labels:
            # 从children_by_image字典中获取该图片的子标签
            if hasattr(parent_label, 'children_by_image') and image_path in parent_label.children_by_image:
                for child in parent_label.children_by_image[image_path]:
                    # 跳过占位符标签
                    if not getattr(child, 'is_placeholder', False):
                        shape = self._convert_to_labelme_shape(child, parent_label, image_width, image_height)
                        if shape:
                            shapes.append(shape)
        
        # 创建LabelMe格式的JSON
        label_data = {
            "version": "5.0.1",
            "flags": {},
            "shapes": shapes,
            "imagePath": image_filename,
            "imageData": None,
            "imageHeight": image_height,
            "imageWidth": image_width
        }
        
        # 保存JSON文件
        with open(label_path, 'w', encoding='utf-8') as f:
            json.dump(label_data, f, indent=2, ensure_ascii=False)
    
    def _export_yolo_format(self, image_path: str, split: str):
        """导出YOLO格式的TXT标签文件"""
        image_filename = os.path.basename(image_path)
        label_filename = os.path.splitext(image_filename)[0] + ".txt"
        label_path = os.path.join(self.export_path, "labels", split, label_filename)
        
        # 获取图片尺寸
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                image_width, image_height = img.size
        except:
            image_width, image_height = 0, 0
        
        # 收集所有标签并转换为YOLO格式
        yolo_labels = []
        for parent_label in self.parent_labels.labels:
            # 从children_by_image字典中获取该图片的子标签
            if hasattr(parent_label, 'children_by_image') and image_path in parent_label.children_by_image:
                for child in parent_label.children_by_image[image_path]:
                    # 跳过占位符标签
                    if not getattr(child, 'is_placeholder', False):
                        yolo_label = self._convert_to_yolo_label(child, parent_label, image_width, image_height)
                        if yolo_label:
                            yolo_labels.append(yolo_label)
        
        # 保存TXT文件
        with open(label_path, 'w', encoding='utf-8') as f:
            for label in yolo_labels:
                f.write(label + '\n')
    
    def _export_mask_image(self, image_path: str, split: str):
        """导出掩码图"""
        try:
            from PIL import Image, ImageDraw
            import numpy as np
            
            # 获取图片尺寸
            with Image.open(image_path) as img:
                image_width, image_height = img.size
            
            # 创建空白掩码图（灰度图）
            mask = np.zeros((image_height, image_width), dtype=np.uint8)
            
            # 为每个类别分配不同的灰度值（使用更明显的值）
            class_id_map = {}
            class_names = {}
            for i, parent_label in enumerate(self.parent_labels.labels):
                # 使用更明显的灰度值，从50开始，每个类别间隔50
                class_id = min(50 + i * 50, 255)  # 确保不超过255
                class_id_map[parent_label.id] = class_id
                class_names[class_id] = parent_label.name
            
            # 收集所有标签并绘制到掩码图上
            has_labels = False
            label_count = 0
            for parent_label in self.parent_labels.labels:
                if hasattr(parent_label, 'children_by_image') and image_path in parent_label.children_by_image:
                    class_id = class_id_map.get(parent_label.id, 50)
                    
                    for child in parent_label.children_by_image[image_path]:
                        # 跳过占位符标签
                        if not getattr(child, 'is_placeholder', False):
                            has_labels = True
                            label_count += 1
                            
                            # 处理OBB（旋转边界框）
                            obb_pts = None
                            if hasattr(child, 'is_obb') and child.is_obb and hasattr(child, 'corner_points') and child.corner_points:
                                obb_pts = child.corner_points
                            elif getattr(child, 'shape_type', '') == 'rectangle' and hasattr(child, 'get_rotated_rect_corners'):
                                rc = child.get_rotated_rect_corners()
                                if rc and len(rc) == 4:
                                    obb_pts = rc
                            if obb_pts:
                                points = [(int(x), int(y)) for x, y in obb_pts]
                                mask = self._draw_polygon_on_mask(mask, points, class_id)
                                
                            elif child.shape_type == 'rectangle' and child.points and len(child.points) >= 8:
                                # 矩形 - 转换为多边形点
                                points = [
                                    (int(child.points[0]), int(child.points[1])),
                                    (int(child.points[2]), int(child.points[3])),
                                    (int(child.points[4]), int(child.points[5])),
                                    (int(child.points[6]), int(child.points[7]))
                                ]
                                # 绘制多边形
                                mask = self._draw_polygon_on_mask(mask, points, class_id)
                            elif child.shape_type == 'rectangle' and child.x_center is not None and child.y_center is not None and child.width is not None and child.height is not None:
                                rc = None
                                if hasattr(child, 'get_rotated_rect_corners'):
                                    rc = child.get_rotated_rect_corners()
                                if rc and len(rc) == 4:
                                    points = [(int(x), int(y)) for x, y in rc]
                                    mask = self._draw_polygon_on_mask(mask, points, class_id)
                                else:
                                    half_w = child.width / 2
                                    half_h = child.height / 2
                                    points = [
                                        (int(child.x_center - half_w), int(child.y_center - half_h)),
                                        (int(child.x_center + half_w), int(child.y_center - half_h)),
                                        (int(child.x_center + half_w), int(child.y_center + half_h)),
                                        (int(child.x_center - half_w), int(child.y_center + half_h))
                                    ]
                                    mask = self._draw_polygon_on_mask(mask, points, class_id)
                            
                            elif (child.shape_type == 'polygon' or child.shape_type == 'polygon_mask') and child.polygon_points:
                                # 多边形
                                points = [(int(x), int(y)) for x, y in child.polygon_points]
                                # 绘制多边形
                                mask = self._draw_polygon_on_mask(mask, points, class_id)
                            elif child.shape_type == 'polygon_mask' and hasattr(child, 'mask_data') and child.mask_data is not None:
                                mask_np = child.mask_data
                                try:
                                    if mask_np.ndim == 3:
                                        mask_np = mask_np[..., 0]
                                    if mask_np.shape[1] != image_width or mask_np.shape[0] != image_height:
                                        mimg = Image.fromarray(mask_np.astype(np.uint8), mode='L')
                                        mimg = mimg.resize((image_width, image_height), Image.NEAREST)
                                        mask_np = np.array(mimg)
                                    mask[mask_np > 0] = class_id
                                except Exception:
                                    pass
                            
                            elif child.shape_type == 'circle' and child.x_center is not None and child.y_center is not None and child.radius is not None:
                                # 圆形 - 绘制圆形
                                mask = self._draw_circle_on_mask(mask, int(child.x_center), int(child.y_center), int(child.radius), class_id)
                                
                            elif child.shape_type == 'point' and child.points and len(child.points) >= 2:
                                # 点 - 绘制小圆点（半径为3像素）
                                mask = self._draw_circle_on_mask(mask, int(child.points[0]), int(child.points[1]), 3, class_id)
                                
                            elif child.shape_type == 'line' and child.points and len(child.points) >= 4:
                                # 线 - 绘制线段
                                x1, y1 = int(child.points[0]), int(child.points[1])
                                x2, y2 = int(child.points[2]), int(child.points[3])
                                mask = self._draw_line_on_mask(mask, x1, y1, x2, y2, class_id)
            
            # 如果没有标签，创建一个空掩码图
            if not has_labels:
                self.status_updated.emit(f"警告: 图片 {os.path.basename(image_path)} 没有有效的标签")
            else:
                self.status_updated.emit(f"图片 {os.path.basename(image_path)} 找到 {label_count} 个标签，正在生成掩码图")
            
            # 检查掩码图是否有非零像素
            non_zero_pixels = np.count_nonzero(mask)
            if non_zero_pixels > 0:
                self.status_updated.emit(f"掩码图包含 {non_zero_pixels} 个非零像素")
            else:
                self.status_updated.emit("警告: 掩码图全为黑色（没有非零像素）")
            
            # 保存掩码图
            image_filename = os.path.basename(image_path)
            mask_filename = os.path.splitext(image_filename)[0] + "_mask.png"
            mask_path = os.path.join(self.export_path, "masks", split, mask_filename)
            
            # 将numpy数组转换为PIL图像并保存
            mask_image = Image.fromarray(mask, mode='L')  # 明确指定为灰度图
            mask_image.save(mask_path)
            
        except Exception as e:
            self.status_updated.emit(f"生成掩码图时出错: {str(e)}")
    
    def _draw_polygon_on_mask(self, mask, points, class_id):
        """在掩码图上绘制多边形"""
        try:
            from PIL import Image, ImageDraw
            import numpy as np
            
            # 创建临时图像用于绘制
            temp_image = Image.fromarray(mask, mode='L')
            draw = ImageDraw.Draw(temp_image)
            
            # 确保坐标是整数且在图像范围内
            height, width = mask.shape
            valid_points = []
            for x, y in points:
                # 确保坐标是整数且在图像范围内
                x = max(0, min(int(x), width - 1))
                y = max(0, min(int(y), height - 1))
                valid_points.append((x, y))
            
            # 只有当有至少3个有效点时才绘制多边形
            if len(valid_points) >= 3:
                # 绘制填充多边形
                draw.polygon(valid_points, fill=class_id)
            
            # 转换回numpy数组
            return np.array(temp_image)
        except Exception as e:
            self.status_updated.emit(f"绘制多边形时出错: {str(e)}")
            return mask
    
    def _draw_circle_on_mask(self, mask, center_x, center_y, radius, class_id):
        """在掩码图上绘制圆形"""
        try:
            from PIL import Image, ImageDraw
            import numpy as np
            
            # 创建临时图像用于绘制
            temp_image = Image.fromarray(mask, mode='L')
            draw = ImageDraw.Draw(temp_image)
            
            # 确保坐标在图像范围内
            height, width = mask.shape
            center_x = max(0, min(int(center_x), width - 1))
            center_y = max(0, min(int(center_y), height - 1))
            radius = max(1, int(radius))
            
            # 计算边界框
            left = max(0, center_x - radius)
            top = max(0, center_y - radius)
            right = min(width - 1, center_x + radius)
            bottom = min(height - 1, center_y + radius)
            
            # 绘制填充圆形
            draw.ellipse([left, top, right, bottom], fill=class_id)
            
            # 转换回numpy数组
            return np.array(temp_image)
        except Exception as e:
            self.status_updated.emit(f"绘制圆形时出错: {str(e)}")
            return mask
    
    def _draw_line_on_mask(self, mask, x1, y1, x2, y2, class_id, width=3):
        """在掩码图上绘制线段"""
        try:
            from PIL import Image, ImageDraw
            import numpy as np
            
            # 创建临时图像用于绘制
            temp_image = Image.fromarray(mask, mode='L')
            draw = ImageDraw.Draw(temp_image)
            
            # 确保坐标在图像范围内
            height, width_img = mask.shape
            x1 = max(0, min(int(x1), width_img - 1))
            y1 = max(0, min(int(y1), height - 1))
            x2 = max(0, min(int(x2), width_img - 1))
            y2 = max(0, min(int(y2), height - 1))
            
            # 绘制线段
            draw.line([(x1, y1), (x2, y2)], fill=class_id, width=width)
            
            # 转换回numpy数组
            return np.array(temp_image)
        except Exception as e:
            self.status_updated.emit(f"绘制线段时出错: {str(e)}")
            return mask
    
    def _convert_to_labelme_shape(self, child: ChildLabel, parent_label: ParentLabel, image_width: int, image_height: int) -> Dict:
        """将子标签转换为LabelMe格式的形状"""
        # 处理OBB（旋转边界框）
        obb_points = None
        if hasattr(child, 'is_obb') and child.is_obb and hasattr(child, 'corner_points') and child.corner_points:
            obb_points = child.corner_points
        elif getattr(child, 'shape_type', '') == 'rectangle' and hasattr(child, 'get_rotated_rect_corners'):
            rc = child.get_rotated_rect_corners()
            if rc and len(rc) == 4:
                obb_points = rc
        if obb_points:
            points = [[x, y] for x, y in obb_points]
            
            # 如果需要归一化坐标
            if self.normalize_coords and image_width > 0 and image_height > 0:
                points = [[x / image_width, y / image_height] for x, y in points]
            
            return {
                "label": parent_label.name,
                "points": points,
                "group_id": None,
                "shape_type": "polygon",
                "flags": {"obb": True}  # 标记为OBB
            }
        elif child.shape_type == 'rectangle' and child.points and len(child.points) >= 8:
            # 矩形
            points = [
                [child.points[0], child.points[1]],  # x1, y1
                [child.points[2], child.points[3]],  # x2, y2
                [child.points[4], child.points[5]],  # x3, y3
                [child.points[6], child.points[7]]   # x4, y4
            ]
            
            # 如果需要归一化坐标
            if self.normalize_coords and image_width > 0 and image_height > 0:
                points = [[x / image_width, y / image_height] for x, y in points]
            
            return {
                "label": parent_label.name,
                "points": points,
                "group_id": None,
                "shape_type": "polygon",
                "flags": {}
            }
        elif child.shape_type == 'polygon' and child.polygon_points:
            # 多边形
            points = [[x, y] for x, y in child.polygon_points]
            
            # 如果需要归一化坐标
            if self.normalize_coords and image_width > 0 and image_height > 0:
                points = [[x / image_width, y / image_height] for x, y in points]
            
            return {
                "label": parent_label.name,
                "points": points,
                "group_id": None,
                "shape_type": "polygon",
                "flags": {}
            }
        elif child.shape_type == 'circle' and child.x_center is not None and child.y_center is not None and child.radius is not None:
            # 圆形 - 转换为多边形（32个点的近似圆）
            import math
            points = []
            num_points = 32
            for i in range(num_points):
                angle = 2 * math.pi * i / num_points
                x = child.x_center + child.radius * math.cos(angle)
                y = child.y_center + child.radius * math.sin(angle)
                points.append([x, y])
            
            # 如果需要归一化坐标
            if self.normalize_coords and image_width > 0 and image_height > 0:
                points = [[x / image_width, y / image_height] for x, y in points]
            
            return {
                "label": parent_label.name,
                "points": points,
                "group_id": None,
                "shape_type": "polygon",
                "flags": {"circle": True, "radius": child.radius}  # 标记为圆形并保存半径
            }
        elif child.shape_type == 'point' and child.points and len(child.points) >= 2:
            # 点
            points = [[child.points[0], child.points[1]]]
            
            # 如果需要归一化坐标
            if self.normalize_coords and image_width > 0 and image_height > 0:
                points = [[x / image_width, y / image_height] for x, y in points]
            
            return {
                "label": parent_label.name,
                "points": points,
                "group_id": None,
                "shape_type": "point",
                "flags": {}
            }
        elif child.shape_type == 'line' and child.points and len(child.points) >= 4:
            # 线
            points = [
                [child.points[0], child.points[1]],  # x1, y1
                [child.points[2], child.points[3]]   # x2, y2
            ]
            
            # 如果需要归一化坐标
            if self.normalize_coords and image_width > 0 and image_height > 0:
                points = [[x / image_width, y / image_height] for x, y in points]
            
            return {
                "label": parent_label.name,
                "points": points,
                "group_id": None,
                "shape_type": "line",
                "flags": {}
            }
        
        return None
    
    def _convert_to_yolo_label(self, child: ChildLabel, parent_label: ParentLabel, image_width: int, image_height: int) -> str:
        """将子标签转换为YOLO格式的标签"""
        class_id = parent_label.id
        # 优先处理 DOTA 8点坐标（当勾选且可取得四顶点时）
        try:
            if getattr(self, 'use_dota_format', False):
                points = None
                if hasattr(child, 'get_rotated_rect_corners'):
                    rc = child.get_rotated_rect_corners()
                    if rc and len(rc) == 4:
                        points = rc
                if hasattr(child, 'corner_points') and child.corner_points and len(child.corner_points) == 4:
                    points = child.corner_points
                elif getattr(child, 'shape_type', '') == 'rectangle' and child.points and len(child.points) >= 8:
                    pts = []
                    for i in range(0, 8, 2):
                        pts.append((child.points[i], child.points[i+1]))
                    points = pts
                elif getattr(child, 'shape_type', '') == 'polygon' and hasattr(child, 'polygon_points') and child.polygon_points and len(child.polygon_points) == 4:
                    points = child.polygon_points
                if points:
                    parts = []
                    for x, y in points:
                        if self.normalize_coords and image_width > 0 and image_height > 0:
                            parts.extend([f"{(x / image_width):.6f}", f"{(y / image_height):.6f}"])
                        else:
                            parts.extend([f"{float(x):.6f}", f"{float(y):.6f}"])
                    return f"{class_id} {' '.join(parts)}"
        except Exception:
            pass
        
        # 处理OBB（旋转边界框）
        obb_points = None
        if hasattr(child, 'is_obb') and child.is_obb and hasattr(child, 'corner_points') and child.corner_points:
            obb_points = child.corner_points
        elif getattr(child, 'shape_type', '') == 'rectangle' and hasattr(child, 'get_rotated_rect_corners'):
            rc = child.get_rotated_rect_corners()
            if rc and len(rc) == 4:
                obb_points = rc
        if obb_points:
            # 检查是否使用DOTA格式（8个坐标点）
            if hasattr(self, 'use_dota_format') and self.use_dota_format:
                # DOTA格式：类别ID x1 y1 x2 y2 x3 y3 x4 y4
                # 按顺序输出四个角点的坐标
                points_str = []
                for x, y in obb_points:
                    if self.normalize_coords and image_width > 0 and image_height > 0:
                        # 归一化坐标
                        norm_x = x / image_width
                        norm_y = y / image_height
                        points_str.extend([f"{norm_x:.6f}", f"{norm_y:.6f}"])
                    else:
                        # 使用原始坐标
                        points_str.extend([f"{x:.6f}", f"{y:.6f}"])
                
                return f"{class_id} {' '.join(points_str)}"
            else:
                # 标准YOLO格式：使用边界框
                x_coords = [p[0] for p in obb_points]
                y_coords = [p[1] for p in obb_points]
                
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)
                
                # 计算中心点和宽高
                if self.normalize_coords:
                    # 归一化坐标
                    x_center = (min_x + max_x) / 2 / image_width
                    y_center = (min_y + max_y) / 2 / image_height
                    width = (max_x - min_x) / image_width
                    height = (max_y - min_y) / image_height
                else:
                    # 使用原始坐标
                    x_center = (min_x + max_x) / 2
                    y_center = (min_y + max_y) / 2
                    width = max_x - min_x
                    height = max_y - min_y
                
                return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        elif child.shape_type == 'rectangle' and child.x_center is not None and child.y_center is not None:
            # 矩形
            if child.width is None or child.height is None:
                return None
                
            # 根据normalize_coords参数决定是否归一化坐标
            if self.normalize_coords:
                # 归一化坐标
                x_center = child.x_center / image_width
                y_center = child.y_center / image_height
                width = child.width / image_width
                height = child.height / image_height
            else:
                # 使用原始坐标
                x_center = child.x_center
                y_center = child.y_center
                width = child.width
                height = child.height
            
            return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        
        elif child.shape_type == 'polygon' and child.polygon_points:
            # 多边形 - 使用边界框
            x_coords = [p[0] for p in child.polygon_points]
            y_coords = [p[1] for p in child.polygon_points]
            
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # 计算中心点和宽高
            if self.normalize_coords:
                # 归一化坐标
                x_center = (min_x + max_x) / 2 / image_width
                y_center = (min_y + max_y) / 2 / image_height
                width = (max_x - min_x) / image_width
                height = (max_y - min_y) / image_height
            else:
                # 使用原始坐标
                x_center = (min_x + max_x) / 2
                y_center = (min_y + max_y) / 2
                width = max_x - min_x
                height = max_y - min_y
            
            return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        
        elif child.shape_type == 'circle' and child.x_center is not None and child.y_center is not None and child.radius is not None:
            # 圆形 - 使用边界框
            if self.normalize_coords:
                # 归一化坐标
                x_center = child.x_center / image_width
                y_center = child.y_center / image_height
                width = (2 * child.radius) / image_width
                height = (2 * child.radius) / image_height
            else:
                # 使用原始坐标
                x_center = child.x_center
                y_center = child.y_center
                width = 2 * child.radius
                height = 2 * child.radius
            
            return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        
        elif child.shape_type == 'point' and child.points and len(child.points) >= 2:
            # 点 - 使用极小的边界框
            if self.normalize_coords:
                # 归一化坐标
                x = child.points[0] / image_width
                y = child.points[1] / image_height
                
                # 使用1像素的边界框
                width = 1.0 / image_width
                height = 1.0 / image_height
            else:
                # 使用原始坐标
                x = child.points[0]
                y = child.points[1]
                
                # 使用1像素的边界框
                width = 1.0
                height = 1.0
            
            return f"{class_id} {x:.6f} {y:.6f} {width:.6f} {height:.6f}"
        
        elif child.shape_type == 'line' and child.points and len(child.points) >= 4:
            # 线 - 使用边界框
            x1, y1 = child.points[0], child.points[1]
            x2, y2 = child.points[2], child.points[3]
            
            min_x, max_x = min(x1, x2), max(x1, x2)
            min_y, max_y = min(y1, y2), max(y1, y2)
            
            # 计算中心点和宽高
            if self.normalize_coords:
                # 归一化坐标
                x_center = (min_x + max_x) / 2 / image_width
                y_center = (min_y + max_y) / 2 / image_height
                width = max(1.0, max_x - min_x) / image_width  # 至少1像素宽
                height = max(1.0, max_y - min_y) / image_height  # 至少1像素高
            else:
                # 使用原始坐标
                x_center = (min_x + max_x) / 2
                y_center = (min_y + max_y) / 2
                width = max(1.0, max_x - min_x)  # 至少1像素宽
                height = max(1.0, max_y - min_y)  # 至少1像素高
            
            return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        
        return None
    
    def _create_dataset_info(self, total_images: int, train_count: int, val_count: int):
        """创建数据集信息文件"""
        info = {
            "total_images": total_images,
            "train_images": train_count,
            "val_images": val_count,
            "train_ratio": self.train_ratio,
            "format": self.export_format,
            "normalize_coordinates": self.normalize_coords,  # 记录是否归一化坐标
            "export_masks": self.export_masks,  # 记录是否导出掩码图
            "classes": []
        }
        
        # 添加类别信息
        for parent_label in self.parent_labels.labels:
            info["classes"].append({
                "id": parent_label.id,
                "name": parent_label.name
            })
        
        # 保存信息文件
        info_path = os.path.join(self.export_path, "dataset_info.json")
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)


class DatasetExportDialog(QDialog):
    """数据集导出对话框"""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.parent_labels = main_window.parent_label_list  # 从主窗口获取父标签
        self.export_worker = None
        
        self.setWindowTitle("导出数据集")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self._init_ui()
        self._setup_connections()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 导出设置组
        settings_group = QGroupBox("导出设置")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setHorizontalSpacing(8)
        settings_layout.setVerticalSpacing(6)
        
        # 导出格式选择
        settings_layout.addWidget(QLabel("导出格式:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["labelme", "yolo"])
        self.format_combo.setCurrentText("labelme")
        settings_layout.addWidget(self.format_combo, 0, 1)
        
        # 训练集比例
        settings_layout.addWidget(QLabel("训练集比例:"), 1, 0)
        self.train_ratio_spin = QDoubleSpinBox()
        self.train_ratio_spin.setRange(0.1, 0.9)
        self.train_ratio_spin.setSingleStep(0.05)
        self.train_ratio_spin.setValue(0.8)
        self.train_ratio_spin.setDecimals(2)
        settings_layout.addWidget(self.train_ratio_spin, 1, 1)
        
        # 验证集比例（自动计算）
        settings_layout.addWidget(QLabel("验证集比例:"), 2, 0)
        self.val_ratio_label = QLabel("0.20")
        settings_layout.addWidget(self.val_ratio_label, 2, 1)
        
        # 导出路径
        settings_layout.addWidget(QLabel("导出路径:"), 3, 0)
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setText(os.path.join(os.path.expanduser("~"), "dataset_export"))
        self.browse_btn = QPushButton("浏览...")
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        settings_layout.addLayout(path_layout, 3, 1)
        
        # 是否归一化坐标
        settings_layout.addWidget(QLabel("归一化坐标:"), 4, 0)
        self.normalize_coords_check = QCheckBox("启用坐标归一化")
        self.normalize_coords_check.setChecked(True)  # 默认启用
        settings_layout.addWidget(self.normalize_coords_check, 4, 1)
        
        # 是否导出掩码图
        settings_layout.addWidget(QLabel("导出掩码图:"), 5, 0)
        self.export_masks_check = QCheckBox("导出掩码图")
        self.export_masks_check.setChecked(False)  # 默认不启用
        settings_layout.addWidget(self.export_masks_check, 5, 1)
        
        # 是否使用DOTA格式导出OBB标签
        settings_layout.addWidget(QLabel("OBB标签格式:"), 6, 0)
        self.dota_format_check = QCheckBox("使用DOTA格式(8点坐标)")
        self.dota_format_check.setChecked(False)  # 默认不启用
        self.dota_format_check.setToolTip("勾选此项将OBB标签导出为DOTA格式的8点坐标，否则使用标准YOLO格式的边界框")
        settings_layout.addWidget(self.dota_format_check, 6, 1)
        
        title_font = QFont()
        title_font.setBold(True)
        settings_group.setFont(title_font)
        layout.addWidget(settings_group)
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep1)
        
        # 统计信息组
        stats_group = QGroupBox("统计信息")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setContentsMargins(8, 8, 8, 8)
        stats_layout.setHorizontalSpacing(8)
        stats_layout.setVerticalSpacing(6)
        
        # 计算标签统计
        total_labels = 0
        labeled_images_set = set()
        
        # 统计各种标签类型（区分旋转矩形为OBB，单独统计polygon_mask）
        label_types = {"rectangle": 0, "obb": 0, "polygon": 0, "polygon_mask": 0, "point": 0, "line": 0, "circle": 0}
        
        for parent_label in self.parent_labels.labels:
            # 从children_by_image字典中获取所有子标签
            if hasattr(parent_label, 'children_by_image'):
                for image_path, children in parent_label.children_by_image.items():
                    for child in children:
                        # 跳过占位符标签
                        if not getattr(child, 'is_placeholder', False):
                            total_labels += 1
                            labeled_images_set.add(image_path)
                            
                            # 统计标签类型（优先判定OBB）
                            is_obb_flag = False
                            if getattr(child, 'is_obb', False) and getattr(child, 'corner_points', None):
                                is_obb_flag = True
                            elif getattr(child, 'shape_type', '') == 'rectangle' and getattr(child, 'rotation_angle', 0) != 0:
                                is_obb_flag = True
                            if is_obb_flag:
                                label_types["obb"] += 1
                            else:
                                st = getattr(child, 'shape_type', '')
                                if st == 'polygon_mask':
                                    label_types['polygon_mask'] += 1
                                elif st in label_types:
                                    label_types[st] += 1
        
        total_images = len(labeled_images_set)
        
        stats_layout.addWidget(QLabel("父标签数量:"), 0, 0)
        stats_layout.addWidget(QLabel(str(len(self.parent_labels.labels))), 0, 1)
        
        stats_layout.addWidget(QLabel("子标签数量:"), 1, 0)
        stats_layout.addWidget(QLabel(str(total_labels)), 1, 1)
        
        stats_layout.addWidget(QLabel("已标注图片数量:"), 2, 0)
        stats_layout.addWidget(QLabel(str(total_images)), 2, 1)
        
        stats_layout.addWidget(QLabel("矩形框:"), 3, 0)
        stats_layout.addWidget(QLabel(str(label_types["rectangle"])), 3, 1)
        
        stats_layout.addWidget(QLabel("多边形:"), 4, 0)
        stats_layout.addWidget(QLabel(str(label_types["polygon"])), 4, 1)
        
        stats_layout.addWidget(QLabel("多边形掩码:"), 5, 0)
        stats_layout.addWidget(QLabel(str(label_types["polygon_mask"])), 5, 1)
        
        stats_layout.addWidget(QLabel("点:"), 6, 0)
        stats_layout.addWidget(QLabel(str(label_types["point"])), 6, 1)
        
        stats_layout.addWidget(QLabel("线:"), 7, 0)
        stats_layout.addWidget(QLabel(str(label_types["line"])), 7, 1)
        
        stats_layout.addWidget(QLabel("圆形:"), 8, 0)
        stats_layout.addWidget(QLabel(str(label_types["circle"])), 8, 1)
        
        stats_layout.addWidget(QLabel("旋转边界框(OBB):"), 9, 0)
        stats_layout.addWidget(QLabel(str(label_types["obb"])), 9, 1)
        
        stats_group.setFont(title_font)
        stats_scroll = QScrollArea()
        stats_scroll.setWidget(stats_group)
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setMinimumHeight(200)
        layout.addWidget(stats_scroll)
        
        # 进度条和状态
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("准备就绪")
        layout.addWidget(self.status_label)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.export_btn = QPushButton("开始导出")
        self.cancel_btn = QPushButton("取消")
        self.close_btn = QPushButton("关闭")
        self.export_btn.setMinimumWidth(100)
        self.cancel_btn.setMinimumWidth(90)
        self.close_btn.setMinimumWidth(90)
        
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _setup_connections(self):
        """设置信号连接"""
        self.browse_btn.clicked.connect(self._browse_export_path)
        self.train_ratio_spin.valueChanged.connect(self._update_val_ratio)
        self.export_btn.clicked.connect(self._start_export)
        self.cancel_btn.clicked.connect(self._cancel_export)
        self.close_btn.clicked.connect(self.accept)
    
    def _browse_export_path(self):
        """浏览导出路径"""
        path = QFileDialog.getExistingDirectory(
            self, "选择导出目录", self.path_edit.text()
        )
        if path:
            self.path_edit.setText(path)
    
    def _update_val_ratio(self, value):
        """更新验证集比例"""
        val_ratio = 1.0 - value
        self.val_ratio_label.setText(f"{val_ratio:.2f}")
    
    def _start_export(self):
        """开始导出"""
        export_path = self.path_edit.text().strip()
        if not export_path:
            QMessageBox.warning(self, "警告", "请选择导出路径")
            return
        
        train_ratio = self.train_ratio_spin.value()
        export_format = self.format_combo.currentText()
        normalize_coords = self.normalize_coords_check.isChecked()
        export_masks = self.export_masks_check.isChecked()
        use_dota_format = self.dota_format_check.isChecked()
        
        # 禁用控件
        self.export_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.train_ratio_spin.setEnabled(False)
        self.format_combo.setEnabled(False)
        self.path_edit.setEnabled(False)
        self.normalize_coords_check.setEnabled(False)
        self.export_masks_check.setEnabled(False)
        self.dota_format_check.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 创建并启动工作线程
        self.export_worker = DatasetExportWorker(
            self.main_window,
            export_path,
            export_format,
            train_ratio,
            normalize_coords,
            export_masks,
            use_dota_format
        )
        self.export_worker.progress_updated.connect(self.progress_bar.setValue)
        self.export_worker.status_updated.connect(self.status_label.setText)
        self.export_worker.status_updated.connect(self._add_log)
        self.export_worker.export_finished.connect(self._on_export_finished)
        
        self.export_worker.start()
    
    def _cancel_export(self):
        """取消导出"""
        if self.export_worker and self.export_worker.isRunning():
            self.export_worker.terminate()
            self.export_worker.wait()
        
        self._reset_ui()
        self.status_label.setText("导出已取消")
    
    def _on_export_finished(self, success, message):
        """导出完成处理"""
        self._reset_ui()
        
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "错误", message)
    
    def _reset_ui(self):
        """重置UI状态"""
        self.export_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.train_ratio_spin.setEnabled(True)
        self.format_combo.setEnabled(True)
        self.path_edit.setEnabled(True)
        self.normalize_coords_check.setEnabled(True)
        self.export_masks_check.setEnabled(True)
        self.dota_format_check.setEnabled(True)
        self.progress_bar.setVisible(False)
    
    def _add_log(self, message):
        """添加日志"""
        self.log_text.append(message)
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
