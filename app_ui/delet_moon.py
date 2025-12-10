import logging
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem
from app_ui.labelsgl import ChildLabel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def I_deleted_you(canvas, x, y):
    """删除选中的矩形框和对应的子标签
    
    Args:
        canvas: GraphicsCanvas实例
        x: 鼠标x坐标
        y: 鼠标y坐标
        
    Returns:
        bool: 成功删除返回True，否则返回False
    """
    try:
        # 导入choose_your函数以获取选中的矩形框
        from app_ui.choose_moon import choose_your
        
        # 获取选中的矩形框
        selected_item = choose_your(canvas, x, y)
        
        if not selected_item:
            logger.info("没有找到选中的矩形框")
            return False
        
        # 检查选中的项是否有子标签
        if hasattr(selected_item, 'child_label') and selected_item.child_label:
            delete_child_label_by_object(canvas, selected_item.child_label)
        else:
            logger.warning("选中项没有子标签，按图形删除")
        
        # 从场景中移除矩形框
        canvas.scene.removeItem(selected_item)
        logger.info("已删除矩形框")
        
        # 清除高亮显示的虚线框
        try:
            # 导入choose_moon模块中的全局变量
            import choose_moon
            
            # 清除高亮虚线框
            if hasattr(choose_moon, 'highlight_rect_item') and choose_moon.highlight_rect_item:
                canvas.scene.removeItem(choose_moon.highlight_rect_item)
                choose_moon.highlight_rect_item = None
                logger.info("已清除高亮虚线框")
                
        except Exception as e:
            logger.error(f"清除高亮虚线框时发生错误: {e}")
        
        # 强制更新场景
        canvas.scene.update()
        
        # 刷新子标签列表显示
        if hasattr(canvas, 'main_window') and canvas.main_window:
            canvas.main_window.refresh_child_labels_for_current_image()
            logger.info("已刷新子标签列表显示")
        
        return True
        
    except Exception as e:
        logger.error(f"删除矩形框和子标签时发生错误: {e}")
        return False

def delete_child_label_by_object(canvas, child_label):
    try:
        if not isinstance(child_label, ChildLabel):
            logger.warning("子标签类型不正确，无法删除")
            return False
        target = None
        for item in canvas.scene.items():
            if hasattr(item, 'child_label') and item.child_label is child_label:
                target = item
                break
        # 从父标签结构中移除
        image_info = getattr(child_label, 'image_info', None)
        parent_label = None
        if hasattr(canvas, 'parent_label_list') and canvas.parent_label_list:
            for p in canvas.parent_label_list.labels:
                if hasattr(p, 'children_by_image') and image_info in p.children_by_image:
                    if child_label in p.children_by_image[image_info]:
                        parent_label = p
                        p.children_by_image[image_info].remove(child_label)
                        logger.info("已从父标签中移除子标签")
                        break
        # 从场景移除图形
        if target:
            canvas.scene.removeItem(target)
            logger.info("已删除对应图形")
        # 清除高亮
        try:
            import choose_moon
            if hasattr(choose_moon, 'highlight_rect_item') and choose_moon.highlight_rect_item:
                canvas.scene.removeItem(choose_moon.highlight_rect_item)
                choose_moon.highlight_rect_item = None
        except Exception as e:
            logger.error(f"清除高亮时发生错误: {e}")
        # 更新显示
        canvas.scene.update()
        if hasattr(canvas, 'parent_label_list') and canvas.parent_label_list and parent_label and image_info:
            selected_parent = canvas.parent_label_list.get_selected()
            if selected_parent == parent_label and hasattr(canvas, 'current_image_info') and canvas.current_image_info == image_info:
                visible = [c for c in parent_label.children_by_image[image_info] if not getattr(c, 'is_placeholder', False)]
                if not visible:
                    canvas.parent_label_list.child_label_list.set_labels(["没有该类别子标签"])
                else:
                    canvas.parent_label_list.child_label_list.set_labels(visible)
        if hasattr(canvas, 'main_window') and canvas.main_window:
            canvas.main_window.refresh_child_labels_for_current_image()
        return True
    except Exception as e:
        logger.error(f"按对象删除子标签时发生错误: {e}")
        return False

# 使用示例
if __name__ == "__main__":
    # 这里可以添加测试代码
    pass
