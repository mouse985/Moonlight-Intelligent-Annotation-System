"""
最小外接矩形框算法实现

该模块实现了计算点集最小外接矩形（Minimum Bounding Rectangle）的算法。
使用旋转卡壳（Rotating Calipers）算法来找到面积最小的外接矩形。

坐标系说明：
- 使用与项目相同的笛卡尔坐标系
- 原点(0,0)位于左上角
- x轴向右增加，y轴向下增加
- 所有坐标单位为像素
"""

import math
import numpy as np
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class MinimumBoundingBox:
    """最小外接矩形框算法类"""
    
    def __init__(self):
        pass
    
    def calculate_convex_hull(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        计算点集的凸包（使用Jarvis步进法）
        
        Args:
            points: 点集列表，每个点为(x, y)元组
            
        Returns:
            凸包点集列表，按逆时针顺序排列
        """
        if len(points) < 3:
            return points.copy()
        
        # 找到最左边的点（x坐标最小，如果有多个则取y坐标最小的）
        leftmost = min(points, key=lambda p: (p[0], p[1]))
        
        hull = []
        current_point = leftmost
        
        while True:
            hull.append(current_point)
            
            # 选择下一个点
            next_point = points[0]
            for point in points[1:]:
                if next_point == current_point:
                    next_point = point
                    continue
                
                # 计算叉积，判断点是否在当前边的右侧
                cross = self._cross_product(current_point, next_point, point)
                if cross < 0 or (cross == 0 and self._distance(current_point, point) > self._distance(current_point, next_point)):
                    next_point = point
            
            current_point = next_point
            
            # 如果回到起点，结束循环
            if current_point == leftmost:
                break
        
        return hull
    
    def _cross_product(self, p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float]) -> float:
        """
        计算三个点的叉积
        
        Args:
            p1: 第一个点
            p2: 第二个点
            p3: 第三个点
            
        Returns:
            叉积值
        """
        return (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
    
    def _distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """
        计算两点间距离
        
        Args:
            p1: 第一个点
            p2: 第二个点
            
        Returns:
            两点间距离
        """
        return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
    
    def _normalize_angle(self, angle: float) -> float:
        """
        将角度规范化到0-180度范围
        
        Args:
            angle: 原始角度
            
        Returns:
            规范化后的角度
        """
        while angle < 0:
            angle += 180
        while angle >= 180:
            angle -= 180
        return angle
    
    def _rotate_point(self, point: Tuple[float, float], angle_rad: float, center: Tuple[float, float] = (0, 0)) -> Tuple[float, float]:
        """
        旋转点
        
        Args:
            point: 要旋转的点
            angle_rad: 旋转角度（弧度）
            center: 旋转中心
            
        Returns:
            旋转后的点
        """
        # 将点平移到以旋转中心为原点的坐标系
        x_translated = point[0] - center[0]
        y_translated = point[1] - center[1]
        
        # 旋转
        x_rotated = x_translated * math.cos(angle_rad) - y_translated * math.sin(angle_rad)
        y_rotated = x_translated * math.sin(angle_rad) + y_translated * math.cos(angle_rad)
        
        # 将点平移回原坐标系
        x_final = x_rotated + center[0]
        y_final = y_rotated + center[1]
        
        return (x_final, y_final)
    
    def find_minimum_bounding_rectangle(self, points: List[Tuple[float, float]]) -> dict:
        """
        找到点集的最小外接矩形
        
        Args:
            points: 点集列表，每个点为(x, y)元组
            
        Returns:
            包含最小外接矩形信息的字典：
            {
                'area': 矩形面积,
                'width': 矩形宽度,
                'height': 矩形高度,
                'angle': 矩形旋转角度（度）,
                'center': 矩形中心点(x, y),
                'corners': 矩形四个角点[(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
            }
        """
        logger.debug(f"[MinimumBoundingBox] 开始计算最小外接矩形，点数: {len(points)}")
        
        if len(points) < 2:
            logger.debug(f"[MinimumBoundingBox] 点数不足: {len(points)} < 2")
            raise ValueError("至少需要2个点来计算最小外接矩形")
        
        # 计算凸包
        hull = self.calculate_convex_hull(points)
        logger.debug(f"[MinimumBoundingBox] 凸包点数: {len(hull)}")
        
        if len(hull) < 2:
            logger.debug(f"[MinimumBoundingBox] 凸包点数不足: {len(hull)} < 2")
            raise ValueError("无法计算凸包")
        
        # 如果只有两个点，直接返回连接两点的矩形
        if len(hull) == 2:
            logger.debug(f"[MinimumBoundingBox] 只有两个点，直接返回连接两点的矩形")
            p1, p2 = hull
            width = self._distance(p1, p2)
            height = 0  # 高度为0，因为只有两个点
            center = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            angle = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
            
            result = {
                'area': width * height,
                'width': width,
                'height': height,
                'angle': angle,
                'center': center,
                'corners': [p1, p2, p2, p1]  # 重复点以保持四个角点
            }
            
            logger.debug(f"[MinimumBoundingBox] 两点矩形结果: 面积={result['area']}, 宽度={result['width']}, 高度={result['height']}, 角度={result['angle']:.2f}°")
            return result
        
        # 初始化最小面积和对应的矩形参数
        min_area = float('inf')
        min_rect = None
        
        # 遍历凸包的每条边
        n = len(hull)
        logger.debug(f"[MinimumBoundingBox] 开始遍历凸包边，共 {n} 条边")
        
        for i in range(n):
            # 当前边的两个端点
            p1 = hull[i]
            p2 = hull[(i + 1) % n]
            
            # 计算当前边的角度
            edge_angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
            
            # 旋转所有点，使当前边与x轴平行
            rotated_points = []
            for point in hull:
                rotated_point = self._rotate_point(point, -edge_angle)
                rotated_points.append(rotated_point)
            
            # 计算旋转后点的边界
            x_coords = [p[0] for p in rotated_points]
            y_coords = [p[1] for p in rotated_points]
            
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # 计算矩形的宽度和高度
            width = max_x - min_x
            height = max_y - min_y
            area = width * height
            
            # 确保area是标量值
            if hasattr(area, 'item'):
                area = area.item()
            
            # 如果面积更小，更新最小矩形
            if area < min_area:
                min_area = area
                
                # 计算矩形的中心点（在旋转后的坐标系中）
                center_rotated = ((min_x + max_x) / 2, (min_y + max_y) / 2)
                
                # 计算矩形的四个角点（在旋转后的坐标系中）
                corners_rotated = [
                    (min_x, min_y),  # 左上
                    (max_x, min_y),  # 右上
                    (max_x, max_y),  # 右下
                    (min_x, max_y)   # 左下
                ]
                
                # 将中心点和角点旋转回原坐标系
                center = self._rotate_point(center_rotated, edge_angle)
                corners = [self._rotate_point(corner, edge_angle) for corner in corners_rotated]
                
                # 保存矩形参数
                min_rect = {
                    'area': area,
                    'width': width,
                    'height': height,
                    'angle': math.degrees(edge_angle),
                    'center': center,
                    'corners': corners
                }
                logger.debug(f"[MinimumBoundingBox] 更新最小面积: {area}, 角度: {math.degrees(edge_angle):.2f}°")
        
        if min_rect is None:
            logger.debug(f"[MinimumBoundingBox] 未能计算最小外接矩形")
            return None
        
        logger.debug(f"[MinimumBoundingBox] 最小面积: {min_rect['area']}")
        logger.debug(f"[MinimumBoundingBox] 矩形尺寸: {min_rect['width']} x {min_rect['height']}")
        logger.debug(f"[MinimumBoundingBox] 旋转角度: {min_rect['angle']:.2f}°")
        logger.debug(f"[MinimumBoundingBox] 中心点: {min_rect['center']}")
        logger.debug(f"[MinimumBoundingBox] 角点: {min_rect['corners']}")
        logger.debug("[MinimumBoundingBox] 成功计算最小外接矩形")
        
        return min_rect
    
    def find_minimum_bounding_rectangle_numpy(self, points: np.ndarray) -> dict:
        """
        使用NumPy优化的方法找到点集的最小外接矩形
        
        Args:
            points: 点集NumPy数组，形状为(N, 2)，每行为(x, y)
            
        Returns:
            包含最小外接矩形信息的字典：
            {
                'area': 矩形面积,
                'width': 矩形宽度,
                'height': 矩形高度,
                'angle': 矩形旋转角度（度）,
                'center': 矩形中心点(x, y),
                'corners': 矩形四个角点[(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
            }
        """
        if points.shape[0] < 2:
            raise ValueError("至少需要2个点来计算最小外接矩形")
        
        # 将NumPy数组转换为点列表
        points_list = [(points[i, 0], points[i, 1]) for i in range(points.shape[0])]
        
        # 使用常规方法计算最小外接矩形
        return self.find_minimum_bounding_rectangle(points_list)
# 示例用法
if __name__ == "__main__":
    # 创建最小外接矩形计算器实例
    mbb = MinimumBoundingBox()
    
    # 测试点集
    test_points = [
        (0, 0),
        (4, 0),
        (4, 3),
        (0, 3),
        (2, 5)
    ]
    
    # 计算最小外接矩形
    result = mbb.find_minimum_bounding_rectangle(test_points)
    
    # 打印结果
    print("最小外接矩形信息：")
    print(f"面积: {result['area']}")
    print(f"宽度: {result['width']}")
    print(f"高度: {result['height']}")
    print(f"旋转角度: {result['angle']} 度")
    print(f"中心点: {result['center']}")
    print(f"四个角点: {result['corners']}")
    
    # 使用NumPy数组测试
    test_points_np = np.array(test_points)
    result_np = mbb.find_minimum_bounding_rectangle_numpy(test_points_np)
    
    print("\n使用NumPy数组计算的结果：")
    print(f"面积: {result_np['area']}")
    print(f"宽度: {result_np['width']}")
    print(f"高度: {result_np['height']}")
    print(f"旋转角度: {result_np['angle']} 度")
    print(f"中心点: {result_np['center']}")
    print(f"四个角点: {result_np['corners']}")
