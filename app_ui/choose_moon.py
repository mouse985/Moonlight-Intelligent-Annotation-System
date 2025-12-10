import logging
import math
from PyQt6.QtGui import QColor, QPen, QBrush, QPolygonF
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsEllipseItem, QGraphicsLineItem
from app_ui.labelsgl import ParentLabel, ChildLabel
from algorithms.calculate_anyone_polygoon_area import calculate_polygon_area

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局变量，用于跟踪当前选中的矩形框
selected_rect_item = None
highlight_rect_item = None

def get_shape_info_at_position(canvas, x, y):
    """获取指定位置下的形状信息（矩形框或多边形、点、线）
    
    Args:
        canvas: GraphicsCanvas实例
        x: 鼠标x坐标
        y: 鼠标y坐标
        
    Returns:
        tuple: 如果是矩形框，返回(points, area, 'rectangle', item)
               如果是多边形，返回(polygon_points, area, 'polygon', item)
               如果是点，返回([(cx, cy)], area_pixels, 'point', item)
               如果是线，返回([(x1, y1), (x2, y2)], area_pixels, 'line', item)
               如果没有形状则返回None
    """
    try:
        # 获取场景中的所有项
        items = canvas.scene.items(QPointF(x, y))
        
        # 遍历所有项，查找形状
        for item in items:
            # 检查是否是矩形框项
            if isinstance(item, QGraphicsRectItem) and hasattr(item, 'child_label'):
                try:
                    rect = item.rect()
                    rect_x, rect_y = rect.x(), rect.y()
                    width, height = rect.width(), rect.height()
                    
                    # 计算矩形的四个顶点坐标
                    points = [
                        (rect_x, rect_y),  # 左上
                        (rect_x + width, rect_y),  # 右上
                        (rect_x + width, rect_y + height),  # 右下
                        (rect_x, rect_y + height)  # 左下
                    ]
                    
                    # 计算面积
                    area = width * height
                    return (points, area, 'rectangle', item)
                except Exception as e:
                    logger.error(f"处理矩形框时发生错误: {e}")
            
            # 检查是否是多边形项
            elif isinstance(item, QGraphicsPolygonItem) and hasattr(item, 'child_label'):
                try:
                    # 确保item有polygon方法
                    if not callable(getattr(item, 'polygon', None)):
                        continue
                        
                    polygon = item.polygon()
                    
                    # 检查鼠标坐标是否在多边形内
                    if polygon.containsPoint(QPointF(x, y), Qt.FillRule.OddEvenFill):
                        # 获取多边形点
                        polygon_points = []
                        for i in range(polygon.size()):
                            point = polygon.at(i)
                            polygon_points.append((point.x(), point.y()))
                        
                        # 使用calculate_polygon_area方法计算多边形面积
                        area = calculate_polygon_area(polygon_points)
                        
                        return (polygon_points, area, 'polygon', item)
                except Exception as e:
                    logger.error(f"处理多边形项时发生错误: {e}")
                    continue
            
            # 检查是否是点（小圆）
            elif isinstance(item, QGraphicsEllipseItem) and hasattr(item, 'child_label'):
                try:
                    local_pt = item.mapFromScene(QPointF(x, y))
                    if item.shape().contains(local_pt):
                        rect = item.rect()
                        cx = rect.center().x()
                        cy = rect.center().y()
                        rx = rect.width() / 2.0
                        ry = rect.height() / 2.0
                        # 像素面积近似：椭圆面积
                        area_pixels = int(round(math.pi * rx * ry))
                        return ([(cx, cy)], area_pixels, 'point', item)
                except Exception as e:
                    logger.error(f"处理点项时发生错误: {e}")
            
            # 检查是否是线
            elif isinstance(item, QGraphicsLineItem) and hasattr(item, 'child_label'):
                try:
                    local_pt = item.mapFromScene(QPointF(x, y))
                    if item.shape().contains(local_pt):
                        line = item.line()
                        x1, y1 = line.x1(), line.y1()
                        x2, y2 = line.x2(), line.y2()
                        length = line.length()
                        # 像素面积近似：线段长度 * 线宽
                        pen_width = 1.0
                        try:
                            pen_width = max(1.0, float(item.pen().widthF()))
                        except Exception:
                            pass
                        area_pixels = int(round(length * pen_width))
                        return ([(x1, y1), (x2, y2)], area_pixels, 'line', item)
                except Exception as e:
                    logger.error(f"处理线项时发生错误: {e}")
             
        return None
            
    except Exception as e:
        logger.error(f"获取形状信息时发生错误: {e}")
        return None

def handle_mouse_move_event(canvas, event):
    """处理鼠标移动事件，获取坐标和形状信息（矩形框或多边形）
    
    Args:
        canvas: GraphicsCanvas实例
        event: 鼠标移动事件
        
    Returns:
        tuple: (mouse_x, mouse_y, shape_info) 
            mouse_x, mouse_y: 鼠标坐标
            shape_info: 形状信息，如果是矩形框则为(rect_x, rect_y, width, height, area, 'rectangle', item)，
                      如果是多边形则为(polygon_points, area, 'polygon', item)，否则为None
    """
    if canvas.ui_locked:
        return None, None, None
        
    try:
        # 获取鼠标在场景中的坐标
        scene_pos = canvas.mapToScene(event.pos())
        x, y = scene_pos.x(), scene_pos.y()
        
        # 检查鼠标位置下是否有形状
        shape_info = get_shape_info_at_position(canvas, x, y)
        
        # 高亮最小形状
        highlight_moon(canvas, x, y)
            
        return x, y, shape_info
            
    except Exception as e:
        logger.error(f"处理鼠标移动事件时发生错误: {e}")
        return None, None, None

def min_shape_moon(canvas, x, y):
    """获取鼠标位置下面积最小的形状（矩形框、多边形、点或线）
    
    Args:
        canvas: GraphicsCanvas实例
        x: 鼠标x坐标
        y: 鼠标y坐标
        
    Returns:
        list: 包含形状信息的列表，如果没有形状则返回None
            - 矩形框: [points, area, 'rectangle', item]
            - 多边形: [polygon_points, area, 'polygon', item]
            - 点: [[(cx, cy)], area_pixels, 'point', item]
            - 线: [[(x1, y1), (x2, y2)], area_pixels, 'line', item]
    """
    try:
        # 获取场景中的所有项
        items = canvas.scene.items(QPointF(x, y))
        
        min_shape = None
        min_area = float('inf')
        
        for item in items:
            # 检查是否是矩形框
            if isinstance(item, QGraphicsRectItem) and hasattr(item, 'child_label'):
                try:
                    rect = item.rect()
                    area = rect.width() * rect.height()
                    
                    if area < min_area:
                        min_area = area
                        points = [
                            (rect.x(), rect.y()),  # 左上
                            (rect.x() + rect.width(), rect.y()),  # 右上
                            (rect.x() + rect.width(), rect.y() + rect.height()),  # 右下
                            (rect.x(), rect.y() + rect.height())  # 左下
                        ]
                        min_shape = [points, area, 'rectangle', item]
                except Exception as e:
                    logger.error(f"处理矩形框时发生错误: {e}")
            
            # 检查是否是多边形
            elif isinstance(item, QGraphicsPolygonItem) and hasattr(item, 'child_label'):
                try:
                    # 确保item有polygon方法
                    if not callable(getattr(item, 'polygon', None)):
                        continue
                        
                    polygon = item.polygon()
                    if not polygon.isEmpty():
                        # 获取多边形点列表
                        polygon_points = []
                        for i in range(polygon.size()):
                            point = polygon.at(i)
                            polygon_points.append((point.x(), point.y()))
                        
                        # 计算多边形面积
                        area = calculate_polygon_area(polygon_points)
                        
                        if area < min_area:
                            min_area = area
                            min_shape = [polygon_points, area, 'polygon', item]
                except Exception as e:
                    logger.error(f"处理多边形时发生错误: {e}")
            
            # 检查是否是点（小圆）
            elif isinstance(item, QGraphicsEllipseItem) and hasattr(item, 'child_label'):
                try:
                    local_pt = item.mapFromScene(QPointF(x, y))
                    if item.shape().contains(local_pt):
                        rect = item.rect()
                        cx = rect.center().x()
                        cy = rect.center().y()
                        rx = rect.width() / 2.0
                        ry = rect.height() / 2.0
                        area_pixels = int(round(math.pi * rx * ry))
                        if area_pixels < min_area:
                            min_area = area_pixels
                            min_shape = [[(cx, cy)], area_pixels, 'point', item]
                except Exception as e:
                    logger.error(f"计算点面积时发生错误: {e}")
            
            # 检查是否是线
            elif isinstance(item, QGraphicsLineItem) and hasattr(item, 'child_label'):
                try:
                    local_pt = item.mapFromScene(QPointF(x, y))
                    if item.shape().contains(local_pt):
                        line = item.line()
                        x1, y1 = line.x1(), line.y1()
                        x2, y2 = line.x2(), line.y2()
                        length = line.length()
                        pen_width = 1.0
                        try:
                            pen_width = max(1.0, float(item.pen().widthF()))
                        except Exception:
                            pass
                        area_pixels = int(round(length * pen_width))
                        if area_pixels < min_area:
                            min_area = area_pixels
                            min_shape = [[(x1, y1), (x2, y2)], area_pixels, 'line', item]
                except Exception as e:
                    logger.error(f"计算线面积时发生错误: {e}")
        
        return min_shape
        
    except Exception as e:
        logger.error(f"获取最小形状时发生错误: {e}")
        return None

def highlight_moon(canvas, x, y):
    """高亮显示鼠标位置下面积最小的形状（矩形框、多边形、点、线）
    
    Args:
        canvas: GraphicsCanvas实例
        x: 鼠标x坐标
        y: 鼠标y坐标
        
    Returns:
        QGraphicsRectItem、QGraphicsPolygonItem、QGraphicsEllipseItem或QGraphicsLineItem: 高亮形状项，如果没有形状则返回None
    """
    global highlight_rect_item
    
    try:
        # 获取最小形状
        min_shape = min_shape_moon(canvas, x, y)
        
        # 如果之前有高亮形状，先移除
        if highlight_rect_item:
            canvas.scene.removeItem(highlight_rect_item)
            highlight_rect_item = None
        
        # 如果有最小形状，创建高亮形状
        if min_shape:
            shape_type = min_shape[-2]  # 倒数第二个元素是形状类型
            original_item = min_shape[-1]  # 最后一个元素是原始项
            
            if shape_type == 'rectangle':
                # 矩形框
                points, area, _, _ = min_shape
                
                # 从顶点坐标计算矩形框的位置和大小
                if len(points) >= 4:
                    # 获取四个顶点
                    x1, y1 = points[0]
                    x2, y2 = points[1]
                    x3, y3 = points[2]
                    x4, y4 = points[3]
                    
                    # 计算矩形的边界
                    min_x = min(x1, x2, x3, x4)
                    max_x = max(x1, x2, x3, x4)
                    min_y = min(y1, y2, y3, y4)
                    max_y = max(y1, y2, y3, y4)
                    
                    rect_x = min_x
                    rect_y = min_y
                    width = max_x - min_x
                    height = max_y - min_y
                else:
                    # 如果顶点数量不足，使用默认值
                    rect_x, rect_y, width, height = 0, 0, 0, 0
                
                # 创建高亮矩形框
                highlight_rect_item = QGraphicsRectItem(rect_x, rect_y, width, height)
                
                # 设置高亮样式（取反色）
                original_pen = original_item.pen()
                original_color = original_pen.color()
                
                # 计算反色
                inverted_color = QColor(255 - original_color.red(), 
                                       255 - original_color.green(), 
                                       255 - original_color.blue())
                
                # 设置高亮矩形框的样式
                highlight_pen = QPen(inverted_color, 3)  # 线宽加粗
                highlight_rect_item.setPen(highlight_pen)
                highlight_rect_item.setZValue(original_item.zValue() + 1)  # 确保高亮图层高于原矩形框
                
                # 添加到场景
                canvas.scene.addItem(highlight_rect_item)
                
                return highlight_rect_item
            
            elif shape_type == 'polygon':
                # 多边形
                polygon_points, area, _, _ = min_shape
                
                # 创建多边形
                polygon = QPolygonF()
                for point_x, point_y in polygon_points:
                    polygon.append(QPointF(point_x, point_y))
                
                # 创建高亮多边形
                highlight_rect_item = QGraphicsPolygonItem(polygon)
                
                # 设置高亮样式（取反色）
                original_pen = original_item.pen()
                original_color = original_pen.color()
                
                # 计算反色
                inverted_color = QColor(255 - original_color.red(), 
                                       255 - original_color.green(), 
                                       255 - original_color.blue())
                
                # 检查是否是polygon_mask类型
                is_polygon_mask = False
                if hasattr(original_item, 'child_label') and original_item.child_label:
                    if hasattr(original_item.child_label, 'shape_type') and original_item.child_label.shape_type == 'polygon_mask':
                        is_polygon_mask = True
                
                if is_polygon_mask:
                    # 对于polygon_mask类型，不显示边框，而是填充整个区域
                    highlight_rect_item.setPen(QPen(inverted_color, 0, Qt.PenStyle.NoPen))  # 无边框
                    # 设置半透明填充
                    fill_color = QColor(inverted_color)
                    fill_color.setAlpha(100)  # 设置透明度
                    highlight_rect_item.setBrush(QBrush(fill_color))
                else:
                    # 普通多边形，只显示边框，不填充
                    highlight_pen = QPen(inverted_color, 3)  # 线宽加粗
                    highlight_rect_item.setPen(highlight_pen)
                    highlight_rect_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))  # 确保不填充
                
                highlight_rect_item.setZValue(original_item.zValue() + 1)  # 确保高亮图层高于原多边形
                
                # 添加到场景
                canvas.scene.addItem(highlight_rect_item)
                
                return highlight_rect_item
            
            elif shape_type == 'point':
                # 点（小圆/椭圆）
                try:
                    rect = original_item.rect()
                    highlight_rect_item = QGraphicsEllipseItem(rect)
                    original_pen = original_item.pen()
                    original_color = original_pen.color()
                    inverted_color = QColor(255 - original_color.red(),
                                            255 - original_color.green(),
                                            255 - original_color.blue())
                    highlight_pen = QPen(inverted_color, 3)
                    highlight_rect_item.setPen(highlight_pen)
                    highlight_rect_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                    highlight_rect_item.setZValue(original_item.zValue() + 1)
                    canvas.scene.addItem(highlight_rect_item)
                    return highlight_rect_item
                except Exception as e:
                    logger.error(f"高亮点时发生错误: {e}")
            
            elif shape_type == 'line':
                # 线段
                try:
                    line = original_item.line()
                    highlight_rect_item = QGraphicsLineItem(line)
                    original_pen = original_item.pen()
                    original_color = original_pen.color()
                    inverted_color = QColor(255 - original_color.red(),
                                            255 - original_color.green(),
                                            255 - original_color.blue())
                    width = 3
                    try:
                        width = max(3, int(round(original_pen.widthF())) + 1)
                    except Exception:
                        pass
                    highlight_pen = QPen(inverted_color, width)
                    highlight_rect_item.setPen(highlight_pen)
                    highlight_rect_item.setZValue(original_item.zValue() + 1)
                    canvas.scene.addItem(highlight_rect_item)
                    return highlight_rect_item
                except Exception as e:
                    logger.error(f"高亮线时发生错误: {e}")
        
        return None
            
    except Exception as e:
        logger.error(f"高亮形状时发生错误: {e}")
        return None

def highlight_child_label(canvas, child_label):
    global highlight_rect_item, selected_rect_item
    try:
        if highlight_rect_item:
            canvas.scene.removeItem(highlight_rect_item)
            highlight_rect_item = None
        target = None
        for item in canvas.scene.items():
            if hasattr(item, 'child_label') and item.child_label is child_label:
                target = item
                break
        if not target:
            return None
        selected_rect_item = target
        from PyQt6.QtGui import QPen, QBrush
        from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsEllipseItem, QGraphicsLineItem
        from PyQt6.QtCore import QPointF
        original_pen = target.pen() if hasattr(target, 'pen') else QPen(QColor(255,0,0), 2)
        original_color = original_pen.color()
        inverted_color = QColor(255 - original_color.red(), 255 - original_color.green(), 255 - original_color.blue())
        if isinstance(target, QGraphicsRectItem):
            rect = target.rect()
            highlight_rect_item = QGraphicsRectItem(rect.x(), rect.y(), rect.width(), rect.height())
            highlight_pen = QPen(inverted_color, 3)
            highlight_rect_item.setPen(highlight_pen)
            highlight_rect_item.setZValue(target.zValue() + 1)
            canvas.scene.addItem(highlight_rect_item)
            return highlight_rect_item
        if isinstance(target, QGraphicsPolygonItem):
            polygon = target.polygon()
            highlight_rect_item = QGraphicsPolygonItem(polygon)
            if hasattr(target, 'child_label') and target.child_label and getattr(target.child_label, 'shape_type', '') == 'polygon_mask':
                highlight_rect_item.setPen(QPen(inverted_color, 0, Qt.PenStyle.NoPen))
                fill_color = QColor(inverted_color)
                fill_color.setAlpha(100)
                highlight_rect_item.setBrush(QBrush(fill_color))
            else:
                highlight_pen = QPen(inverted_color, 3)
                highlight_rect_item.setPen(highlight_pen)
                highlight_rect_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            highlight_rect_item.setZValue(target.zValue() + 1)
            canvas.scene.addItem(highlight_rect_item)
            return highlight_rect_item
        if isinstance(target, QGraphicsEllipseItem):
            rect = target.rect()
            highlight_rect_item = QGraphicsEllipseItem(rect)
            highlight_pen = QPen(inverted_color, 3)
            highlight_rect_item.setPen(highlight_pen)
            highlight_rect_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            highlight_rect_item.setZValue(target.zValue() + 1)
            canvas.scene.addItem(highlight_rect_item)
            return highlight_rect_item
        if isinstance(target, QGraphicsLineItem):
            line = target.line()
            highlight_rect_item = QGraphicsLineItem(line)
            width = 3
            try:
                width = max(3, int(round(original_pen.widthF())) + 1)
            except Exception:
                pass
            highlight_pen = QPen(inverted_color, width)
            highlight_rect_item.setPen(highlight_pen)
            highlight_rect_item.setZValue(target.zValue() + 1)
            canvas.scene.addItem(highlight_rect_item)
            return highlight_rect_item
        return None
    except Exception as e:
        logger.error(f"按子标签高亮时发生错误: {e}")
        return None

def choose_your(canvas, x, y):
    """定义被高亮的形状为选中的形状（矩形框或多边形）
    
    Args:
        canvas: GraphicsCanvas实例
        x: 鼠标x坐标
        y: 鼠标y坐标
        
    Returns:
        QGraphicsRectItem或QGraphicsPolygonItem: 选中的形状项，如果没有选中则返回None
    """
    global selected_rect_item
    
    try:
        # 获取最小形状
        min_shape = min_shape_moon(canvas, x, y)
        
        # 如果之前有选中的形状，恢复其原始样式
        if selected_rect_item:
            # 这里可以根据需要恢复原始样式
            selected_rect_item = None
        
        # 如果有最小形状，将其设为选中状态
        if min_shape:
            shape_type = min_shape[-2]  # 倒数第二个元素是形状类型
            item = min_shape[-1]  # 最后一个元素是原始项
            selected_rect_item = item
            
            # 确保形状项有子标签信息
            if hasattr(item, 'child_label') and item.child_label:
                # 检查子标签是否是ChildLabel类型
                if not isinstance(item.child_label, ChildLabel):
                    logger.warning("形状的child_label不是ChildLabel类型")
                    # 尝试从画布的父标签列表中查找对应的子标签
                    if hasattr(canvas, 'parent_label_list') and canvas.parent_label_list:
                        # 获取当前图片信息
                        image_info = None
                        if hasattr(canvas, 'current_image_info'):
                            image_info = canvas.current_image_info
                        
                        if image_info:
                            if shape_type == 'rectangle':
                                # 矩形框
                                points, area, _, _ = min_shape
                                
                                # 从顶点坐标计算中心点
                                if len(points) >= 4:
                                    # 获取四个顶点
                                    x1, y1 = points[0]
                                    x2, y2 = points[1]
                                    x3, y3 = points[2]
                                    x4, y4 = points[3]
                                    
                                    # 计算中心点
                                    center_x = (x1 + x2 + x3 + x4) / 4
                                    center_y = (y1 + y2 + y3 + y4) / 4
                                else:
                                    # 如果顶点数量不足，使用第一个点作为中心点
                                    if points:
                                        center_x, center_y = points[0]
                                    else:
                                        center_x, center_y = 0, 0
                                
                                # 使用ParentLabelList的get_smallest_child_label_at_point方法查找子标签
                                child_label = canvas.parent_label_list.get_smallest_child_label_at_point(center_x, center_y, image_info)
                                
                                if child_label:
                                    item.child_label = child_label
                                    logger.info(f"已为矩形框关联正确的子标签: {child_label}")
                                else:
                                    logger.warning("未找到匹配的子标签")
                            
                            elif shape_type == 'polygon':
                                # 多边形
                                polygon_points, area, _, _ = min_shape
                                
                                # 使用实际坐标，直接使用第一个点作为参考点
                                if polygon_points:
                                    center_x, center_y = polygon_points[0]
                                    
                                    # 使用ParentLabelList的get_smallest_child_label_at_point方法查找子标签
                                    child_label = canvas.parent_label_list.get_smallest_child_label_at_point(center_x, center_y, image_info)
                                    
                                    if child_label:
                                        item.child_label = child_label
                                        logger.info(f"已为多边形关联正确的子标签: {child_label}")
                                    else:
                                        logger.warning("未找到匹配的子标签")
                        else:
                            logger.warning("没有当前图片信息，无法关联子标签")
                    else:
                        logger.warning("画布没有parent_label_list属性，无法关联子标签")
                else:
                    logger.info("形状已有正确的ChildLabel类型子标签")
            else:
                logger.warning("形状没有child_label属性")
            
            # 这里可以添加选中状态的样式变化
            return item
            
        return None
            
    except Exception as e:
        logger.error(f"选择形状时发生错误: {e}")
        return None
