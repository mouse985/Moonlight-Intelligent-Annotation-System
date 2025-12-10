"""
计算多边形的外接矩形（普通矩形，不是最小外接矩形）

该脚本提供了一个方法，输入多边形的顶点坐标，计算并返回外接矩形的四个顶点坐标。
外接矩形是指能够完全包围多边形的最小轴对齐矩形。
"""

import numpy as np


def calculate_bounding_rectangle(polygon_points):
    """
    计算多边形的外接矩形（普通矩形，不是最小外接矩形）
    
    
    Args:
        polygon_points: 多边形顶点坐标列表，格式为[(x1, y1), (x2, y2), ..., (xn, yn)]
    
    Returns:
        外接矩形的四个顶点坐标，格式为[(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
        按照顺时针顺序返回：左下、右下、右上、左上
    """
    if not polygon_points or len(polygon_points) < 3:
        raise ValueError("多边形至少需要3个顶点")
    
    # 将输入转换为numpy数组以便计算
    points = np.array(polygon_points)
    
    # 找出x和y的最小值和最大值
    x_min = np.min(points[:, 0])
    x_max = np.max(points[:, 0])
    y_min = np.min(points[:, 1])
    y_max = np.max(points[:, 1])
    
    # 返回外接矩形的四个顶点坐标（顺时针顺序：左下、右下、右上、左上）
    bounding_rect = [
        (x_min, y_min),  # 左下角
        (x_max, y_min),  # 右下角
        (x_max, y_max),  # 右上角
        (x_min, y_max)   # 左上角
    ]
    
    return bounding_rect


def print_bounding_rectangle_info(polygon_points, bounding_rect):
    """
    打印多边形和外接矩形的信息
    
    Args:
        polygon_points: 多边形顶点坐标列表
        bounding_rect: 外接矩形的四个顶点坐标
    """
    print("多边形顶点坐标:")
    for i, point in enumerate(polygon_points):
        print(f"  点{i+1}: {point}")
    
    print("\n外接矩形顶点坐标:")
    for i, point in enumerate(bounding_rect):
        corner_names = ["左下角", "右下角", "右上角", "左上角"]
        print(f"  {corner_names[i]}: {point}")
    
    # 计算并打印矩形的宽度和高度
    width = bounding_rect[1][0] - bounding_rect[0][0]
    height = bounding_rect[2][1] - bounding_rect[1][1]
    print(f"\n外接矩形宽度: {width:.2f}")
    print(f"外接矩形高度: {height:.2f}")
    print(f"外接矩形面积: {width * height:.2f}")


# 示例使用
if __name__ == "__main__":
    # 示例1：三角形
    triangle = [(1, 1), (3, 5), (6, 2)]
    rect = calculate_bounding_rectangle(triangle)
    print("示例1：三角形")
    print_bounding_rectangle_info(triangle, rect)
    
    print("\n" + "="*50 + "\n")
    
    # 示例2：四边形
    quadrilateral = [(2, 3), (5, 1), (7, 4), (4, 6)]
    rect = calculate_bounding_rectangle(quadrilateral)
    print("示例2：四边形")
    print_bounding_rectangle_info(quadrilateral, rect)
    
    print("\n" + "="*50 + "\n")
    
    # 示例3：五边形
    pentagon = [(3, 2), (6, 1), (8, 4), (5, 7), (2, 5)]
    rect = calculate_bounding_rectangle(pentagon)
    print("示例3：五边形")
    print_bounding_rectangle_info(pentagon, rect)
    
    print("\n" + "="*50 + "\n")
    
    # 示例4：不规则多边形
    irregular_polygon = [(1, 1), (2, 5), (4, 3), (7, 6), (5, 8), (3, 7), (0, 4)]
    rect = calculate_bounding_rectangle(irregular_polygon)
    print("示例4：不规则多边形")
    print_bounding_rectangle_info(irregular_polygon, rect)
