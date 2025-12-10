import logging
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KeyboardShortcuts:
    """键盘快捷键管理类"""
    
    def __init__(self, main_window=None):
        """初始化键盘快捷键管理器
        
        Args:
            main_window: 主窗口实例
        """
        self.main_window = main_window
        self.shortcuts = {}
        
    def setup_shortcuts(self):
        """设置键盘快捷键"""
        try:
            # 导入设置管理器
            from set import get_settings_manager
            settings_manager = get_settings_manager()
            
            # 获取快捷键设置
            shortcuts = settings_manager.get_all_shortcuts()
            
            # 设置快捷键，使用配置中的值
            self.add_shortcut(shortcuts.get("shortcuts/load_image_dir", "Ctrl+K"), self.trigger_load_image_directory)
            self.add_shortcut(shortcuts.get("shortcuts/create_label", "Ctrl+W"), self.trigger_create_label)
            self.add_shortcut(shortcuts.get("shortcuts/delete_rect", "Ctrl+D"), self.trigger_delete_rect)
            self.add_shortcut(shortcuts.get("shortcuts/delete_by_box", "Ctrl+F"), self.trigger_delete_by_box)
            self.add_shortcut(shortcuts.get("shortcuts/prev_image", "A"), self.trigger_previous_image)
            self.add_shortcut(shortcuts.get("shortcuts/next_image", "D"), self.trigger_next_image)
            self.add_shortcut(shortcuts.get("shortcuts/toggle_auto_annotation", "Ctrl+A"), self.trigger_toggle_auto_annotation)
            self.add_shortcut(shortcuts.get("shortcuts/open_batch_annotation", "Ctrl+P"), self.trigger_batch_annotation)
            self.add_shortcut(shortcuts.get("shortcuts/prev_parent_label", "Q"), self.trigger_previous_parent_label)
            self.add_shortcut(shortcuts.get("shortcuts/next_parent_label", "E"), self.trigger_next_parent_label)

            try:
                kb = shortcuts.get("shortcuts/delete_by_box", "Ctrl+F")
                if kb in self.shortcuts:
                    self.shortcuts[kb].setAutoRepeat(False)
            except Exception:
                pass
            
            logger.info("键盘快捷键设置完成")
            
        except Exception as e:
            logger.error(f"设置键盘快捷键时发生错误: {e}")
    
    def add_shortcut(self, key_sequence, callback):
        """添加键盘快捷键
        
        Args:
            key_sequence: 快捷键序列，如"Ctrl+K"
            callback: 回调函数
        """
        try:
            if not self.main_window:
                logger.warning("主窗口实例为空，无法添加快捷键")
                return False
                
            # 创建快捷键
            shortcut = QShortcut(QKeySequence(key_sequence), self.main_window)
            shortcut.activated.connect(callback)
            
            # 保存快捷键引用
            self.shortcuts[key_sequence] = shortcut
            
            logger.info(f"已添加快捷键: {key_sequence}")
            return True
            
        except Exception as e:
            logger.error(f"添加快捷键 {key_sequence} 时发生错误: {e}")
            return False
    
    def trigger_load_image_directory(self):
        """触发打开图片目录功能"""
        try:
            if self.main_window and hasattr(self.main_window, 'load_image_directory'):
                logger.info("通过快捷键触发打开图片目录功能")
                self.main_window.load_image_directory()
            else:
                logger.warning("无法触发打开图片目录功能：主窗口或方法不存在")
                
        except Exception as e:
            logger.error(f"触发打开图片目录功能时发生错误: {e}")
    
    def trigger_create_label(self):
        """触发创建新标签功能"""
        try:
            if self.main_window and hasattr(self.main_window, 'create_label_btn'):
                logger.info("通过快捷键触发创建新标签功能")
                # 模拟按钮点击
                self.main_window.create_label_btn.click()
            else:
                logger.warning("无法触发创建新标签功能：主窗口或按钮不存在")
                
        except Exception as e:
            logger.error(f"触发创建新标签功能时发生错误: {e}")
    
    def trigger_delete_rect(self):
        """触发删除矩形框功能"""
        try:
            if self.main_window and hasattr(self.main_window, 'canvas'):
                logger.info("通过快捷键触发删除矩形框功能")
                
                # 导入delet_moon模块中的I_deleted_you函数
                from delet_moon import I_deleted_you
                
                # 获取当前鼠标在窗口中的位置
                window_pos = self.main_window.cursor().pos()
                
                # 转换为画布坐标
                canvas_pos = self.main_window.canvas.mapFromGlobal(window_pos)
                
                # 转换为场景坐标
                scene_pos = self.main_window.canvas.mapToScene(canvas_pos)
                
                # 调用I_deleted_you函数删除矩形框，使用场景坐标
                I_deleted_you(self.main_window.canvas, scene_pos.x(), scene_pos.y())
            else:
                logger.warning("无法触发删除矩形框功能：主窗口或画布不存在")
                
        except Exception as e:
            logger.error(f"触发删除矩形框功能时发生错误: {e}")

    def trigger_delete_by_box(self):
        """启用框选删除模式（Ctrl+F）"""
        try:
            if self.main_window and hasattr(self.main_window, 'canvas'):
                canvas = self.main_window.canvas
                if getattr(canvas, 'delete_select_mode', False):
                    return
                canvas.delete_select_mode = True
                canvas.delete_select_start = None
                # 解锁橡皮筋拖拽
                canvas.set_ui_locked(False)
                logger.info("已启用框选删除模式：按住左键拖拽，右键撤销")
            else:
                logger.warning("无法启用框选删除：主窗口或画布不存在")
        except Exception as e:
            logger.error(f"启用框选删除模式时发生错误: {e}")

    def trigger_toggle_auto_annotation(self):
        """触发自动标注开关切换（Ctrl+A）"""
        try:
            if self.main_window and hasattr(self.main_window, 'toggle_auto_annotation'):
                logger.info("通过快捷键触发自动标注开关切换")
                # 直接调用toggle_auto_annotation方法，传入当前状态的反值
                current_state = getattr(self.main_window, 'auto_annotation_enabled', False)
                self.main_window.toggle_auto_annotation(not current_state)
            else:
                logger.warning("无法触发自动标注开关：主窗口或方法不存在")
        except Exception as e:
            logger.error(f"触发自动标注开关时发生错误: {e}")
    
    def trigger_previous_image(self):
        """触发上一张图片功能"""
        try:
            if self.main_window and hasattr(self.main_window, 'show_previous_image'):
                logger.debug("通过快捷键触发上一张图片功能")
                # 直接调用方法
                self.main_window.show_previous_image()
            else:
                logger.warning("无法触发上一张图片功能：主窗口或方法不存在")
                
        except Exception as e:
            logger.error(f"触发上一张图片功能时发生错误: {e}")
    
    def trigger_next_image(self):
        """触发下一张图片功能"""
        try:
            if self.main_window and hasattr(self.main_window, 'show_next_image'):
                logger.debug("通过快捷键触发下一张图片功能")
                # 直接调用方法
                self.main_window.show_next_image()
            else:
                logger.warning("无法触发下一张图片功能：主窗口或方法不存在")
                
        except Exception as e:
            logger.error(f"触发下一张图片功能时发生错误: {e}")

    def trigger_batch_annotation(self):
        """触发批量标注按钮（Ctrl+P）"""
        try:
            if self.main_window and hasattr(self.main_window, 'open_batch_annotation_window'):
                logger.info("通过快捷键触发批量标注功能")
                # 直接调用打开批量标注窗口的方法
                self.main_window.open_batch_annotation_window()
            else:
                logger.warning("无法触发批量标注：主窗口或方法不存在")
        except Exception as e:
            logger.error(f"触发批量标注功能时发生错误: {e}")
    
    def trigger_previous_parent_label(self):
        """触发切换到上一个父标签（Q）"""
        try:
            if self.main_window and hasattr(self.main_window, 'parent_label_list'):
                logger.info("通过快捷键触发切换到上一个父标签")
                # 调用ParentLabelList的select_previous方法
                success = self.main_window.parent_label_list.select_previous()
                if not success:
                    logger.warning("切换到上一个父标签失败：可能没有父标签")
            else:
                logger.warning("无法触发切换父标签：主窗口或控件不存在")
        except Exception as e:
            logger.error(f"触发切换到上一个父标签时发生错误: {e}")
    
    def trigger_next_parent_label(self):
        """触发切换到下一个父标签（E）"""
        try:
            if self.main_window and hasattr(self.main_window, 'parent_label_list'):
                logger.info("通过快捷键触发切换到下一个父标签")
                # 调用ParentLabelList的select_next方法
                success = self.main_window.parent_label_list.select_next()
                if not success:
                    logger.warning("切换到下一个父标签失败：可能没有父标签")
            else:
                logger.warning("无法触发切换父标签：主窗口或控件不存在")
        except Exception as e:
            logger.error(f"触发切换到下一个父标签时发生错误: {e}")
    
    def remove_shortcut(self, key_sequence):
        """移除键盘快捷键
        
        Args:
            key_sequence: 要移除的快捷键序列
        """
        try:
            if key_sequence in self.shortcuts:
                self.shortcuts[key_sequence].setEnabled(False)
                del self.shortcuts[key_sequence]
                logger.info(f"已移除快捷键: {key_sequence}")
                return True
            else:
                logger.warning(f"快捷键不存在: {key_sequence}")
                return False
                
        except Exception as e:
            logger.error(f"移除快捷键 {key_sequence} 时发生错误: {e}")
            return False
    
    def enable_shortcut(self, key_sequence, enabled=True):
        """启用或禁用快捷键
        
        Args:
            key_sequence: 快捷键序列
            enabled: 是否启用
        """
        try:
            if key_sequence in self.shortcuts:
                self.shortcuts[key_sequence].setEnabled(enabled)
                logger.info(f"{'启用' if enabled else '禁用'}快捷键: {key_sequence}")
                return True
            else:
                logger.warning(f"快捷键不存在: {key_sequence}")
                return False
                
        except Exception as e:
            logger.error(f"{'启用' if enabled else '禁用'}快捷键 {key_sequence} 时发生错误: {e}")
            return False
    
    def cleanup(self):
        """清理所有快捷键"""
        try:
            for key_sequence, shortcut in self.shortcuts.items():
                shortcut.setEnabled(False)
            
            self.shortcuts.clear()
            logger.info("已清理所有快捷键")
            
        except Exception as e:
            logger.error(f"清理快捷键时发生错误: {e}")

# 全局变量，用于保存键盘快捷键管理器实例
keyboard_shortcuts_manager = None

def init_keyboard_shortcuts(main_window):
    """初始化键盘快捷键管理器
    
    Args:
        main_window: 主窗口实例
        
    Returns:
        KeyboardShortcuts: 键盘快捷键管理器实例
    """
    global keyboard_shortcuts_manager
    
    try:
        # 创建键盘快捷键管理器
        keyboard_shortcuts_manager = KeyboardShortcuts(main_window)
        
        # 设置快捷键
        keyboard_shortcuts_manager.setup_shortcuts()
        
        logger.info("键盘快捷键管理器初始化完成")
        return keyboard_shortcuts_manager
        
    except Exception as e:
        logger.error(f"初始化键盘快捷键管理器时发生错误: {e}")
        return None

def get_keyboard_shortcuts_manager():
    """获取键盘快捷键管理器实例
    
    Returns:
        KeyboardShortcuts: 键盘快捷键管理器实例，如果未初始化则返回None
    """
    return keyboard_shortcuts_manager

# 使用示例
if __name__ == "__main__":
    # 这里可以添加测试代码
    pass
