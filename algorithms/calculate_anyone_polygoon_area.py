"""
计算任意多边形面积的脚本
参考鞋带公式（Shoelace formula）实现
"""

def calculate_polygon_area(points):
    """
    计算任意多边形的面积
    
    参数:
        points: 多边形顶点列表，每个顶点是一个包含x和y坐标的对象或元组
        
    返回:
        float: 多边形的面积，如果顶点数小于3则返回0
    """
    cnt = len(points)
    if cnt < 3:
        return 0
    
    res = 0
    for i in range(cnt):
        j = (i - 1) % cnt  # 等同于 j = cnt-1 当 i=0 时，否则 j = i-1
        # 获取点的坐标，支持不同的点表示方式
        if hasattr(points[i], 'x') and hasattr(points[i], 'y'):
            # 对象形式，如 point.x(), point.y()
            x_i, y_i = points[i].x(), points[i].y()
            x_j, y_j = points[j].x(), points[j].y()
        elif hasattr(points[i], 'X') and hasattr(points[i], 'Y'):
            # 对象形式，如 point.X(), point.Y()
            x_i, y_i = points[i].X(), points[i].Y()
            x_j, y_j = points[j].X(), points[j].Y()
        else:
            # 元组或列表形式，如 (x, y)
            x_i, y_i = points[i][0], points[i][1]
            x_j, y_j = points[j][0], points[j][1]
        
        res += (x_j + x_i) * (y_j - y_i)
    
    return abs(0.5 * res)


def calculate_polygon_area_from_tuples(points):
    """
    计算任意多边形的面积（专门处理元组或列表形式的点）
    
    参数:
        points: 多边形顶点列表，每个顶点是一个包含x和y坐标的元组或列表，如 [(x1, y1), (x2, y2), ...]
        
    返回:
        float: 多边形的面积，如果顶点数小于3则返回0
    """
    cnt = len(points)
    if cnt < 3:
        return 0
    
    res = 0
    for i in range(cnt):
        j = (i - 1) % cnt
        x_i, y_i = points[i][0], points[i][1]
        x_j, y_j = points[j][0], points[j][1]
        res += (x_j + x_i) * (y_j - y_i)
    
    return abs(0.5 * res)


# 测试代码
if __name__ == "__main__":
    # 测试用例1：矩形
    rectangle_points = [(0, 0), (4, 0), (4, 3), (0, 3)]
    area1 = calculate_polygon_area_from_tuples(rectangle_points)
    print(f"矩形面积: {area1} (预期: 12)")
    
    # 测试用例2：三角形
    triangle_points = [(0, 0), (4, 0), (2, 3)]
    area2 = calculate_polygon_area_from_tuples(triangle_points)
    print(f"三角形面积: {area2} (预期: 6)")
    
    # 测试用例3：复杂多边形
    complex_points = [(0, 0), (2, 0), (3, 2), (2, 4), (0, 4), (-1, 2)]
    area3 = calculate_polygon_area_from_tuples(complex_points)
    print(f"复杂多边形面积: {area3} (预期: 14)")
