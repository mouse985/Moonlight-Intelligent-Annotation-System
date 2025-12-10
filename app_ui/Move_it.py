import logging
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QCursor, QPolygonF
from PyQt6.QtWidgets import QApplication
from app_ui.choose_moon import highlight_moon, min_shape_moon, selected_rect_item, choose_your

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局变量，用于跟踪平移状态
is_moving = False
moving_item = None
moving_child_label = None
last_mouse_pos = None
original_item_pos = None

def init_move_mode(canvas):
    """初始化平移模式
    
    Args:
        canvas: GraphicsCanvas实例
    """
    global is_moving, moving_item, moving_child_label, last_mouse_pos, original_item_pos
    
    # 重置平移状态
    is_moving = False
    moving_item = None
    moving_child_label = None
    last_mouse_pos = None
    original_item_pos = None
    
    # 保存原始的鼠标事件处理方法
    if not hasattr(canvas, '_original_mousePressEvent'):
        canvas._original_mousePressEvent = canvas.mousePressEvent
    if not hasattr(canvas, '_original_mouseMoveEvent'):
        canvas._original_mouseMoveEvent = canvas.mouseMoveEvent
    if not hasattr(canvas, '_original_mouseReleaseEvent'):
        canvas._original_mouseReleaseEvent = canvas.mouseReleaseEvent
    
    # 连接鼠标事件
    canvas.mousePressEvent = lambda event: _handle_mouse_press(canvas, event)
    canvas.mouseMoveEvent = lambda event: _handle_mouse_move(canvas, event)
    canvas.mouseReleaseEvent = lambda event: _handle_mouse_release(canvas, event)

def _handle_mouse_press(canvas, event):
    """处理鼠标按下事件，开始平移操作
    
    Args:
        canvas: GraphicsCanvas实例
        event: 鼠标事件
    """
    global is_moving, moving_item, moving_child_label, last_mouse_pos, original_item_pos
    
    # 只在平移模式下处理
    if not canvas.pan_mode:
        # 调用原始的鼠标按下事件处理
        canvas._original_mousePressEvent(event)
        return
    
    try:
        # 获取鼠标在场景中的坐标
        scene_pos = canvas.mapToScene(event.pos())
        x, y = scene_pos.x(), scene_pos.y()
        
        # 获取鼠标位置下面积最小的形状
        min_shape = min_shape_moon(canvas, x, y)
        logger.info(f"鼠标按下位置: ({x:.2f}, {y:.2f}), 检测到形状: {min_shape is not None}")
        
        if min_shape:
            # 获取形状项和关联的子标签
            item = min_shape[-1]  # 最后一个元素是原始项
            logger.info(f"检测到图形项类型: {type(item).__name__}")
            
            # 确保形状项有子标签信息
            if hasattr(item, 'child_label') and item.child_label:
                logger.info(f"图形项有子标签，是否为OBB: {getattr(item.child_label, 'is_obb', False)}")
                # 使用choose_your函数确保正确关联子标签
                selected_item = choose_your(canvas, x, y)
                
                if selected_item and hasattr(selected_item, 'child_label') and selected_item.child_label:
                    logger.info(f"选中项类型: {type(selected_item).__name__}, 子标签是否为OBB: {getattr(selected_item.child_label, 'is_obb', False)}")
                    # 开始平移操作
                    is_moving = True
                    moving_item = selected_item
                    moving_child_label = selected_item.child_label
                    last_mouse_pos = (x, y)
                    
                    # 保存原始位置
                    if hasattr(selected_item, 'pos'):
                        original_item_pos = selected_item.pos()
                    else:
                        original_item_pos = QPointF(x, y)
                    
                    # 设置光标样式
                    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                    
                    # 移除高亮项，避免场景不匹配问题
                    from choose_moon import highlight_rect_item
                    if highlight_rect_item and highlight_rect_item.scene() == canvas.scene:
                        canvas.scene.removeItem(highlight_rect_item)
                        import choose_moon
                        choose_moon.highlight_rect_item = None
                else:
                    logger.warning("无法获取有效的子标签，调用原始鼠标事件处理")
                    canvas._original_mousePressEvent(event)
            else:
                logger.warning("形状项没有child_label属性，调用原始鼠标事件处理")
                canvas._original_mousePressEvent(event)
        else:
            # 如果没有选中任何形状，调用原始的鼠标按下事件处理
            canvas._original_mousePressEvent(event)
    
    except Exception as e:
        logger.error(f"处理鼠标按下事件时发生错误: {e}")
        # 发生错误时，调用原始的鼠标按下事件处理
        canvas._original_mousePressEvent(event)

def _handle_mouse_move(canvas, event):
    """处理鼠标移动事件，执行平移操作
    
    Args:
        canvas: GraphicsCanvas实例
        event: 鼠标事件
    """
    global is_moving, moving_item, moving_child_label, last_mouse_pos
    
    # 只在平移模式下处理
    if not canvas.pan_mode:
        # 调用原始的鼠标移动事件处理
        canvas._original_mouseMoveEvent(event)
        return
    
    try:
        # 获取鼠标在场景中的坐标
        scene_pos = canvas.mapToScene(event.pos())
        x, y = scene_pos.x(), scene_pos.y()
        
        if is_moving and moving_item and moving_child_label and last_mouse_pos:
            # 计算移动距离
            dx = x - last_mouse_pos[0]
            dy = y - last_mouse_pos[1]
            
            # 获取图片尺寸
            image_width = 0
            image_height = 0
            if hasattr(canvas, 'current_pixmap') and canvas.current_pixmap:
                image_width = canvas.current_pixmap.width()
                image_height = canvas.current_pixmap.height()
            
            # 如果有图片尺寸信息，进行边界检查
            if image_width > 0 and image_height > 0:
                # 计算图形元素的边界
                min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
                
                if hasattr(moving_item, 'setPos'):
                    # 对于QGraphicsItem，获取当前位置
                    current_pos = moving_item.pos()
                    item_x = current_pos.x()
                    item_y = current_pos.y()
                    
                    # 获取图形元素的边界框
                    if hasattr(moving_item, 'boundingRect'):
                        rect = moving_item.boundingRect()
                        min_x = item_x + rect.left()
                        min_y = item_y + rect.top()
                        max_x = item_x + rect.right()
                        max_y = item_y + rect.bottom()
                    else:
                        # 如果没有边界框信息，假设是一个点
                        min_x = max_x = item_x
                        min_y = max_y = item_y
                        
                elif hasattr(moving_item, 'setRect'):
                    # 对于QGraphicsRectItem，获取矩形位置和尺寸
                    rect = moving_item.rect()
                    min_x = rect.x()
                    min_y = rect.y()
                    max_x = rect.x() + rect.width()
                    max_y = rect.y() + rect.height()
                    
                elif hasattr(moving_item, 'setPolygon'):
                    # 对于QGraphicsPolygonItem，获取多边形边界
                    polygon = moving_item.polygon()
                    for i in range(polygon.size()):
                        point = polygon.at(i)
                        min_x = min(min_x, point.x())
                        min_y = min(min_y, point.y())
                        max_x = max(max_x, point.x())
                        max_y = max(max_y, point.y())
                
                # 计算移动后的边界
                new_min_x = min_x + dx
                new_min_y = min_y + dy
                new_max_x = max_x + dx
                new_max_y = max_y + dy
                
                # 检查是否会超出图片边界
                if new_min_x < 0:
                    dx = -min_x  # 调整dx，确保不会超出左边界
                elif new_max_x > image_width:
                    dx = image_width - max_x  # 调整dx，确保不会超出右边界
                    
                if new_min_y < 0:
                    dy = -min_y  # 调整dy，确保不会超出上边界
                elif new_max_y > image_height:
                    dy = image_height - max_y  # 调整dy，确保不会超出下边界
            
            # 移动图形项
            if hasattr(moving_item, 'setPos'):
                # 对于QGraphicsItem，使用setPos方法
                new_pos = moving_item.pos() + QPointF(dx, dy)
                moving_item.setPos(new_pos)
            elif hasattr(moving_item, 'setRect'):
                # 对于QGraphicsRectItem，更新矩形位置
                rect = moving_item.rect()
                moving_item.setRect(QRectF(rect.x() + dx, rect.y() + dy, rect.width(), rect.height()))
            elif hasattr(moving_item, 'setPolygon'):
                # 对于QGraphicsPolygonItem，更新多边形位置
                polygon = moving_item.polygon()
                translated_polygon = QPolygonF()
                for i in range(polygon.size()):
                    point = polygon.at(i)
                    translated_polygon.append(QPointF(point.x() + dx, point.y() + dy))
                moving_item.setPolygon(translated_polygon)
                
                # 如果是OBB矩形框，更新corner_points属性
                if hasattr(moving_item, 'child_label') and hasattr(moving_item.child_label, 'is_obb') and moving_item.child_label.is_obb:
                    if hasattr(moving_item.child_label, 'corner_points'):
                        logger.info(f"在多边形移动中处理OBB，原始corner_points: {moving_item.child_label.corner_points}")
                        # 获取图像缩放信息，将画布坐标偏移量转换为图像坐标偏移量
                        image_scale_x = getattr(canvas, 'image_scale_x', 1.0)
                        image_scale_y = getattr(canvas, 'image_scale_y', 1.0)
                        logger.info(f"多边形移动中的图像缩放比例: x={image_scale_x}, y={image_scale_y}")
                        
                        # 将画布坐标偏移量转换为图像坐标偏移量
                        pixel_dx = dx / image_scale_x if image_scale_x != 0 else dx
                        pixel_dy = dy / image_scale_y if image_scale_y != 0 else dy
                        logger.info(f"多边形移动中的坐标偏移 - canvas: ({dx:.2f}, {dy:.2f}), image: ({pixel_dx:.2f}, {pixel_dy:.2f})")
                        
                        # 更新OBB的角点坐标（图像坐标）
                        updated_corner_points = []
                        for point_x, point_y in moving_item.child_label.corner_points:
                            updated_corner_points.append((point_x + pixel_dx, point_y + pixel_dy))
                        moving_item.child_label.corner_points = updated_corner_points
                        logger.info(f"多边形移动中更新后的corner_points: {updated_corner_points}")
            
            # 调用子标签的移动方法（移除重复的OBB处理）
            moving_child_label.move(dx, dy)
            
            # 更新最后鼠标位置
            last_mouse_pos = (x, y)
            
            # 更新画布上的矩形框和多边形显示
            if hasattr(canvas, 'update_rects'):
                canvas.update_rects()
                
            # 在平移操作后刷新十字准星
            if hasattr(canvas, 'mouse_decorator_manager') and canvas.mouse_decorator_manager:
                if canvas.mouse_decorator_manager.is_crosshair_enabled():
                    scene_pos = canvas.mapToScene(event.pos())
                    canvas.mouse_decorator_manager.crosshair_decorator.update_crosshair(scene_pos)
        else:
            # 如果没有进行平移操作，高亮鼠标下的形状
            highlight_moon(canvas, x, y)
            
            # 调用原始的鼠标移动事件处理
            canvas._original_mouseMoveEvent(event)
    
    except Exception as e:
        logger.error(f"处理鼠标移动事件时发生错误: {e}")
        # 发生错误时，调用原始的鼠标移动事件处理
        canvas._original_mouseMoveEvent(event)

def _handle_mouse_release(canvas, event):
    """处理鼠标释放事件，结束平移操作
    
    Args:
        canvas: GraphicsCanvas实例
        event: 鼠标事件
    """
    global is_moving, moving_item, moving_child_label, last_mouse_pos, original_item_pos
    
    # 只在平移模式下处理
    if not canvas.pan_mode:
        # 调用原始的鼠标释放事件处理
        canvas._original_mouseReleaseEvent(event)
        return
    
    try:
        if is_moving:
            # 结束平移操作
            is_moving = False
            
            # 恢复光标样式
            QApplication.restoreOverrideCursor()
            
            # 更新子标签列表显示
            if hasattr(canvas, 'parent_label_list') and canvas.parent_label_list:
                image_info = canvas.get_image_info_func() if hasattr(canvas, 'get_image_info_func') else None
                if image_info:
                    # 使用moonlight.py中的refresh_child_labels_for_current_image方法
                    if hasattr(canvas, 'refresh_child_labels_for_current_image'):
                        canvas.refresh_child_labels_for_current_image()
                    # 使用ParentLabelList的update_child_labels_for_image方法
                    elif hasattr(canvas.parent_label_list, 'update_child_labels_for_image'):
                        canvas.parent_label_list.update_child_labels_for_image(image_info)
                    # 使用ParentLabelList的set_current_image_info方法
                    elif hasattr(canvas.parent_label_list, 'set_current_image_info'):
                        current_idx = 0
                        if hasattr(canvas, 'images') and hasattr(canvas, 'current_image_path') and canvas.current_image_path in canvas.images:
                            current_idx = canvas.images.index(canvas.current_image_path)
                        canvas.parent_label_list.set_current_image_info(
                            image_info, 
                            total=len(canvas.images) if hasattr(canvas, 'images') else 0, 
                            current_idx=current_idx
                        )
                    else:
                        logger.warning("未找到可用的子标签刷新方法")
                else:
                    logger.warning("无法获取当前图片信息")
            else:
                logger.warning("画布没有parent_label_list属性")
            
            # 更新画布上的矩形框和多边形显示
            if hasattr(canvas, 'update_rects'):
                canvas.update_rects()
            
            # 重置状态
            moving_item = None
            moving_child_label = None
            last_mouse_pos = None
            original_item_pos = None
        
        # 调用原始的鼠标释放事件处理
        canvas._original_mouseReleaseEvent(event)
    
    except Exception as e:
        logger.error(f"处理鼠标释放事件时发生错误: {e}")
        # 发生错误时，调用原始的鼠标释放事件处理
        canvas._original_mouseReleaseEvent(event)

def enable_move_mode(canvas):
    """启用平移模式
    
    Args:
        canvas: GraphicsCanvas实例
    """
    # 初始化平移模式
    init_move_mode(canvas)
    
    # 设置画布的平移模式
    canvas.set_pan_mode(True)
    
    logger.info("平移模式已启用")

def disable_move_mode(canvas):
    """禁用平移模式
    
    Args:
        canvas: GraphicsCanvas实例
    """
    # 设置画布的平移模式
    canvas.set_pan_mode(False)
    
    # 重置平移状态
    global is_moving, moving_item, moving_child_label, last_mouse_pos, original_item_pos
    is_moving = False
    moving_item = None
    moving_child_label = None
    last_mouse_pos = None
    original_item_pos = None
    
    # 恢复光标样式
    QApplication.restoreOverrideCursor()
    
    # 恢复原始的鼠标事件处理方法
    if hasattr(canvas, '_original_mousePressEvent'):
        canvas.mousePressEvent = canvas._original_mousePressEvent
        delattr(canvas, '_original_mousePressEvent')
    if hasattr(canvas, '_original_mouseMoveEvent'):
        canvas.mouseMoveEvent = canvas._original_mouseMoveEvent
        delattr(canvas, '_original_mouseMoveEvent')
    if hasattr(canvas, '_original_mouseReleaseEvent'):
        canvas.mouseReleaseEvent = canvas._original_mouseReleaseEvent
        delattr(canvas, '_original_mouseReleaseEvent')
    
    logger.info("平移模式已禁用")
