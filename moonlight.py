from PyQt6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout, 
                             QListWidget, QListWidgetItem, QFrame, QLabel, 
                             QFileDialog, QPushButton, QButtonGroup,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, 
                             QGraphicsRectItem, QMessageBox, QProgressBar, 
                             QDialog, QMainWindow, QMenu)

from PyQt6.QtCore import (Qt, QPoint, QSize)
from PyQt6.QtGui import QPixmap, QImage, QPen, QColor, QBrush, QPainter, QIcon, QCursor, QPainterPath, QRegion, QImageReader
import sys
import os
BASE_DIR = os.path.dirname(__file__)
for _p in ("app_ui","inference","sam_ops","algorithms","io_ops","services","utils"):
    sys.path.append(os.path.join(BASE_DIR, _p))
os.environ['QT_IMAGEIO_MAXALLOC'] = '0'
QImageReader.setAllocationLimit(0)
import glob
import logging
import time
import numpy as np
from typing import List, Optional, Tuple, Dict, Any, Callable, Union
from app_ui.labelsgl import ParentLabelList
from app_ui.label_draw_manage import LabelDrawManager
from io_ops import LIM
from app_ui.choose_moon import handle_mouse_move_event, highlight_moon, choose_your
from app_ui.key_moon import init_keyboard_shortcuts
from services.auto_annotation_manager import get_auto_annotation_manager
from app_ui.mouse_decorator import MouseDecoratorManager
from algorithms.image_resize import adjust_current_image_to_1080p

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from services.workspace_manager import WorkspaceResourceManager
from app_ui.canvas import GraphicsCanvas

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.images: List[str] = []
        self.current_image_path: Optional[str] = None
        self.resource_manager = WorkspaceResourceManager()
        self.resource_manager.main_window = self
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._drag_position = None
        self._is_dragging = False
        self._resize_area = None  # 记录鼠标在哪个边缘区域
        self._resize_enabled = False  # 是否正在调整大小
        self._resize_margin = 5  # 边缘检测的边距
        self._corner_radius = 12
        
        # 设置窗口图标
        import os
        from PyQt6.QtGui import QIcon
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base, "acc", "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 初始化自动矩形框绘制器
        self.auto_rect_pen = None
        # 新增：自由标注模式状态
        self.free_mode = False
        # 自动标注状态
        self.auto_annotation_enabled = False
        self.obb_rect_axis_aligned = False
        # 记录模型加载是否出现错误（用于决定启动时自动标注初始状态）
        self._model_loading_had_error = False
        # 底部栏展开状态（用于控制上拉/收起）
        self.bottom_expanded = False
        self._solo_mode = False
        self.initUI()

    def initUI(self) -> None:
        try:
            self.setWindowTitle('moonlight')
            screen = QApplication.primaryScreen().geometry()
            width = min(1200, screen.width())
            height = min(800, screen.height())
            self.resize(width, height)
            # 将窗口居中显示在屏幕上
            x = (screen.width() - width) // 2
            y = (screen.height() - height) // 2
            self.move(x, y) 
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            central_widget.setStyleSheet("background-color: #FAFAF2;")  # 护眼淡色背景
            self.create_top_toolbar()
            main_layout.addWidget(self.top_toolbar)
            content_widget= QWidget()
            content_layout = QHBoxLayout(content_widget)
            content_layout.setContentsMargins(5, 5, 5, 5)
            content_layout.setSpacing(5)
            # 内容区域背景继承自主窗口，无需重复设置
            self._create_control_panel()
            self._create_resource_list()
            content_layout.addWidget(self.resource_list)
            self.canvas = GraphicsCanvas(
                parent_label_list=self.parent_label_list,
                get_image_info_func=self.get_current_image_info,
                parent=self)
            # 创建画布的垂直布局（包含底部工具栏）
            canvas_layout = QVBoxLayout()
            canvas_layout.addWidget(self.canvas, stretch=5)
            
            from bottom_ui import setup_bottom_toolbar
            setup_bottom_toolbar(self)
            
            # 将底部工具栏添加到画布布局中
            canvas_layout.addWidget(self.bottom_toolbar)
            
            # 将画布布局添加到内容布局中
            canvas_widget = QWidget()
            canvas_widget.setLayout(canvas_layout)
            canvas_widget.setStyleSheet("background-color: #FAFAFA; border-left: 1px solid #DADADA;")
            content_layout.addWidget(canvas_widget, stretch=5)
            
            from app_ui.component_bar import setup_component_bar
            self.component_bar = setup_component_bar(self)
            content_layout.addWidget(self.component_bar)
            
            content_layout.addWidget(self.control_panel)
            main_layout.addWidget(content_widget)
            # 设置事件连接
            self._setup_event_connections()
            
            # 初始化键盘快捷键
            init_keyboard_shortcuts(self)
        except Exception as e:
            logger.error(f"初始化UI时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"初始化界面失败: {e}")
    def toggle_rect_mode(self, checked: bool) -> None:
        from Pattern_management import toggle_rect_mode as pm_toggle_rect_mode
        pm_toggle_rect_mode(self, checked)
    
    def toggle_polygon_mode(self, checked: bool) -> None:
        from Pattern_management import toggle_polygon_mode as pm_toggle_polygon_mode
        pm_toggle_polygon_mode(self, checked)
            
    def toggle_pan_mode(self, checked: bool) -> None:
        from Pattern_management import toggle_pan_mode as pm_toggle_pan_mode
        pm_toggle_pan_mode(self, checked)
            
    def _on_mask_input_mode_changed(self, checked: bool) -> None:
        from Pattern_management import _on_mask_input_mode_changed as pm_mask_input_changed
        pm_mask_input_changed(self, checked)

    def _remove_bbox_hint(self, hint_item):
        from Pattern_management import _remove_bbox_hint as pm_remove_bbox_hint
        pm_remove_bbox_hint(self, hint_item)

    def _on_obb_input_mode_changed(self, checked: bool) -> None:
        from Pattern_management import _on_obb_input_mode_changed as pm_obb_input_changed
        pm_obb_input_changed(self, checked)

    def _on_obb_rect_type_changed(self) -> None:
        try:
            axis = False
            if hasattr(self, 'obb_rect_axis_btn') and self.obb_rect_axis_btn.isChecked():
                axis = True
            self.obb_rect_axis_aligned = axis
        except Exception:
            self.obb_rect_axis_aligned = False

    def toggle_mask_mode(self, checked: bool) -> None:
        from Pattern_management import toggle_mask_mode as pm_toggle_mask_mode
        pm_toggle_mask_mode(self, checked)
            
    def toggle_obb_mode(self, checked: bool) -> None:
        from Pattern_management import toggle_obb_mode as pm_toggle_obb_mode
        pm_toggle_obb_mode(self, checked)
    def toggle_free_mode(self, checked: bool) -> None:
        from Pattern_management import toggle_free_mode as pm_toggle_free_mode
        pm_toggle_free_mode(self, checked)

    def _on_brush_selected(self, brush_type: str, checked: bool) -> None:
        from Pattern_management import _on_brush_selected as pm_on_brush_selected
        pm_on_brush_selected(self, brush_type, checked)

    def create_top_toolbar(self) -> None:
        self.top_toolbar = QFrame()
        self.top_toolbar.setFixedHeight(45)  # 设置工具栏高度
        self.top_toolbar.setStyleSheet("background-color: #FAFAF2; color: #333333; border-bottom: 1px solid #E6E4D6;")
        title_layout = QHBoxLayout(self.top_toolbar)  # 创建标题栏布局
        title_layout.setContentsMargins(5, 0, 0, 0)  # 设置标题栏布局边距
        self.title_label = QLabel("moonlight")
        self.title_label.setStyleSheet("font-weight: bold;")  # 设置标题栏文字为加粗
        title_layout.addWidget(self.title_label)
        try:
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect
            from PyQt6.QtGui import QColor
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 2)
            shadow.setColor(QColor(0, 0, 0, 30))
            self.top_toolbar.setGraphicsEffect(shadow)
        except Exception:
            pass
        
        # 添加加载图片目录按钮
        self.load_btn = QPushButton()
        self.load_btn.setFixedSize(45, 30)
        # 设置加载图片目录按钮图标
        load_icon_path = os.path.join(os.path.dirname(__file__), 'acc', 'openimage.png')
        if os.path.exists(load_icon_path):
            self.load_btn.setIcon(QIcon(load_icon_path))
            self.load_btn.setIconSize(QSize(45, 45))
            self.load_btn.setToolTip('加载图片目录')  # 添加工具提示
        else:
            self.load_btn.setText('加载图片目录')  # 如果图标不存在，显示文字
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: black;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        self.load_btn.clicked.connect(self.load_image_directory)
        title_layout.addWidget(self.load_btn)
        
        
        # 添加AI按钮
        self.ai_btn = QPushButton()
        self.ai_btn.setFixedSize(40, 30)
        # 设置AI按钮图标
        ai_icon_path = os.path.join(os.path.dirname(__file__), 'acc', 'aizidong.png')
        if os.path.exists(ai_icon_path):
            self.ai_btn.setIcon(QIcon(ai_icon_path))
            self.ai_btn.setIconSize(QSize(45, 45))
        else:
            self.ai_btn.setText('AI')  # 如果图标不存在，显示文字
        self.ai_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: black;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        # 连接按钮到AI菜单功能
        self.ai_btn.clicked.connect(self.show_ai_menu)
        title_layout.addWidget(self.ai_btn)

        # 遥感模式开关按钮（顶部栏）
        self.remote_btn = QPushButton()
        self.remote_btn.setCheckable(True)
        self.remote_btn.setFixedSize(60, 30)
        self.remote_btn.setText("遥感")
        self.remote_btn.setToolTip("遥感模式开关（会话级）")
        self.remote_btn.setStyleSheet("""
            QPushButton { background-color: #F5F5F5; color: black; border: 1px solid #D0D0D0; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #E8E8E8; }
            QPushButton:checked { background-color: #4CAF50; color: white; }
        """)
        try:
            from app_ui.remote_sensing import is_remote_sensing_enabled, set_remote_sensing_enabled
            self.remote_btn.setChecked(bool(is_remote_sensing_enabled()))
            self.remote_btn.toggled.connect(lambda v: set_remote_sensing_enabled(bool(v)))
        except Exception:
            pass
        title_layout.addWidget(self.remote_btn)
        
        
        title_layout.addStretch()
        
        # 添加设置按钮（靠右对齐）
        self.settings_btn = QPushButton()
        self.settings_btn.setFixedSize(30, 30)
        # 设置设置按钮图标
        settings_icon_path = os.path.join(os.path.dirname(__file__), 'acc', 'setimage.png')
        if os.path.exists(settings_icon_path):
            self.settings_btn.setIcon(QIcon(settings_icon_path))
            self.settings_btn.setIconSize(QSize(45, 45))
            self.settings_btn.setToolTip('设置')  # 添加工具提示
        else:
            self.settings_btn.setText('设置')  # 如果图标不存在，显示文字
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: black;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
            }
        """)
        # 导入设置模块并连接按钮点击事件
        from set import get_settings_manager
        self.settings_manager = get_settings_manager()
        self.settings_btn.clicked.connect(lambda: self.settings_manager.show_settings_dialog(self))
        title_layout.addWidget(self.settings_btn)
        
        # 添加50像素的间距
        title_layout.addSpacing(105)
        
        self.minimize_btn = QPushButton("—")
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.setStyleSheet("""QPushButton {background-color: transparent;color: #333333;border: none;font-size: 16px;}QPushButton:hover {background-color: #EFEFE7;}
""")
        self.minimize_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(self.minimize_btn)
        # 最大化/还原按钮
        self.fullscreen_btn = QPushButton("□")
        self.fullscreen_btn.setFixedSize(30, 30)
        self.fullscreen_btn.setStyleSheet("""QPushButton {background-color: transparent;color: #333333;border: none;font-size: 16px;}QPushButton:hover {background-color: #EFEFE7;}""")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        title_layout.addWidget(self.fullscreen_btn)
        # 关闭按钮
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("""QPushButton {background-color: transparent;color: #333333;border: none;font-size: 16px;}QPushButton:hover {background-color: #F9E3E3;}""")
        self.close_btn.clicked.connect(self.close)
        title_layout.addWidget(self.close_btn)
    def toggle_solo_mode(self, checked: bool) -> None:
        try:
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
            widgets = []
            if hasattr(self, 'resource_list') and self.resource_list:
                widgets.append(self.resource_list)
            if hasattr(self, 'control_panel') and self.control_panel:
                widgets.append(self.control_panel)
            if hasattr(self, 'component_bar') and self.component_bar:
                widgets.append(self.component_bar)
            bottom = getattr(self, 'bottom_toolbar', None)

            if not hasattr(self, '_solo_orig_widths'):
                self._solo_orig_widths = {w: max(1, w.width()) for w in widgets}
            if bottom and not hasattr(self, '_solo_orig_bottom_h'):
                self._solo_orig_bottom_h = max(1, bottom.height())

            group = QParallelAnimationGroup(self)
            for w in widgets:
                if not checked:
                    w.setVisible(True)
                w.setMaximumWidth(w.width())
                anim = QPropertyAnimation(w, b"maximumWidth", self)
                anim.setDuration(250)
                anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                anim.setStartValue(w.width())
                target = 0 if checked else self._solo_orig_widths.get(w, max(1, w.width()))
                anim.setEndValue(target)
                group.addAnimation(anim)

            if bottom:
                if not checked:
                    bottom.setVisible(True)
                bottom.setMaximumHeight(bottom.height())
                b_anim = QPropertyAnimation(bottom, b"maximumHeight", self)
                b_anim.setDuration(250)
                b_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                b_anim.setStartValue(bottom.height())
                b_target = 0 if checked else getattr(self, '_solo_orig_bottom_h', max(1, bottom.height()))
                b_anim.setEndValue(b_target)
                group.addAnimation(b_anim)

            def on_finished():
                if checked:
                    for w in widgets:
                        w.setVisible(False)
                    if bottom:
                        bottom.setVisible(False)
                    self.title_label.setText("moonlight • Solo")
                else:
                    self.title_label.setText("moonlight")

            group.finished.connect(on_finished)
            self._solo_anim_group = group
            group.start()
            self._solo_mode = checked
        except Exception as e:
            logger.error(f"切换Solo模式失败: {e}")
    def open_batch_annotation_window(self) -> None:
        """打开批量标注画布窗口，并按当前模式设置绘制方式。"""
        try:
            # 前置条件：必须选中至少一个父标签，且画布已加载图片
            selected_parent = None
            if hasattr(self, 'parent_label_list') and self.parent_label_list:
                try:
                    selected_parent = self.parent_label_list.get_selected()
                except Exception:
                    selected_parent = None

            has_image = False
            if hasattr(self, 'canvas') and self.canvas:
                has_image = getattr(self.canvas, 'image_item', None) is not None

            if not selected_parent and not has_image:
                QMessageBox.information(self, "提示", "请先选中至少一个父标签，并在画布上加载至少一张图片。")
                return
            if not selected_parent:
                QMessageBox.information(self, "提示", "请先在父标签列表中选中一个父标签。")
                return
            if not has_image:
                QMessageBox.information(self, "提示", "请先在资源列表中选择图片并加载到画布。")
                return

            from vision_prompt_win import open_vision_prompt_window
            # 打开窗口并保持引用，避免被GC回收
            self._batch_window = open_vision_prompt_window(self)
        except Exception as e:
            logger.error(f"打开批量标注窗口时发生错误: {e}")
    def enlarge_current_image_10x(self) -> None:
        try:
            adjust_current_image_to_1080p(self)
        except Exception as e:
            logger.error(f"放大分辨率失败: {e}")
    def toggle_auto_annotation(self, checked: bool) -> None:
        """切换自动标注模式
        
        Args:
            checked: 开关是否被选中
        """
        try:
            self.auto_annotation_enabled = checked
            
            # 更新AI按钮的样式
            self.update_ai_button_style()
            
            if checked:
                logger.info("自动标注模式已开启")
                
                # 初始化自动矩形框绘制器（如果尚未初始化）
                if self.auto_rect_pen is None:
                    from aotu_rect_pen import AutoRectPen
                    self.auto_rect_pen = AutoRectPen(
                        parent_label_list=self.parent_label_list,
                        canvas_view=self.canvas,
                        get_image_info_func=self.get_current_image_info
                    )
                
                # 启用自动矩形框绘制器
                if self.auto_rect_pen:
                    self.auto_rect_pen.set_enabled(True)
                    logger.info("自动矩形框绘制器已启用")
                
                # 初始化自动标注管理器（如果尚未初始化）
                if hasattr(self, 'canvas') and self.canvas.auto_annotation_manager is None:
                    self.canvas.auto_annotation_manager = get_auto_annotation_manager(
                        self, self.canvas.parent_label_list, self.canvas
                    )
            else:
                logger.info("自动标注模式已关闭")
                
                # 禁用自动矩形框绘制器
                if self.auto_rect_pen:
                    self.auto_rect_pen.set_enabled(False)
                    logger.info("自动矩形框绘制器已禁用")
        except Exception as e:
            logger.error(f"切换自动标注模式时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
    
    def update_ai_button_style(self) -> None:
        """更新AI按钮的样式，根据自动标注状态改变背景色"""
        try:
            # 重新设置图标以确保在样式更新后仍然显示
            ai_icon_path = os.path.join(os.path.dirname(__file__), 'acc', 'aizidong.png')
            if os.path.exists(ai_icon_path):
                self.ai_btn.setIcon(QIcon(ai_icon_path))
                self.ai_btn.setIconSize(QSize(45, 45))
            
            if self.auto_annotation_enabled:
                # 自动标注开启时，AI按钮显示激活状态（蓝色背景）
                self.ai_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3498DB;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #2980B9;
                    }
                """)
            else:
                # 自动标注关闭时，AI按钮显示默认状态
                self.ai_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #445566;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #546676;
                    }
                """)
        except Exception as e:
            logger.error(f"更新AI按钮样式时发生错误: {e}")
    
    def show_ai_menu(self) -> None:
        """显示AI按钮的下拉菜单"""
        try:
            # 创建下拉菜单
            menu = QMenu(self)
            
            # 设置菜单样式
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2C3E50;
                    color: white;
                    border: 1px solid #445566;
                    border-radius: 4px;
                    padding: 5px;
                }
                QMenu::item {
                    background-color: transparent;
                    padding: 8px 20px;
                    border-radius: 3px;
                }
                QMenu::item:selected {
                    background-color: #445566;
                }
                QMenu::item:disabled {
                    color: #7F8C8D;
                }
                QMenu::item:checked {
                    background-color: #3498DB;
                }
            """)
            
            # 添加自动标注开关
            auto_annotation_action = menu.addAction("自动标注")
            auto_annotation_action.setCheckable(True)
            auto_annotation_action.setChecked(self.auto_annotation_enabled)
            auto_annotation_action.triggered.connect(self.toggle_auto_annotation)
            
            # 添加批量标注功能
            batch_annotation_action = menu.addAction("批量标注")
            batch_annotation_action.triggered.connect(self.open_batch_annotation_window)
            
            # 在按钮下方显示菜单
            button_pos = self.ai_btn.mapToGlobal(self.ai_btn.rect().bottomLeft())
            menu.exec(button_pos)
            
        except Exception as e:
            logger.error(f"显示AI菜单时发生错误: {e}")
    
    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("□")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("❐")

    def toggle_bottom_toolbar(self) -> None:
        """点击底部栏右侧小三角后，适当上拉（展开/收起）底部栏。"""
        try:
            default_height = 40
            expanded_height = 80
            if getattr(self, 'bottom_expanded', False):
                self.bottom_toolbar.setFixedHeight(default_height)
                self.bottom_toggle_btn.setText("▲")
                self.bottom_expanded = False
            else:
                self.bottom_toolbar.setFixedHeight(expanded_height)
                self.bottom_toggle_btn.setText("▼")
                self.bottom_expanded = True
        except Exception as e:
            logger.error(f"切换底部栏失败: {e}")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否在窗口边缘区域
            resize_area = self._get_resize_area(event.pos())
            if resize_area:
                self._resize_area = resize_area
                self._resize_enabled = True
                event.accept()
            elif self.top_toolbar.geometry().contains(event.pos()):
                self._is_dragging = True
                self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    def mouseMoveEvent(self, event) -> None:
        # 处理窗口大小调整
        if event.buttons() == Qt.MouseButton.LeftButton and self._resize_enabled and self._resize_area:
            self._resize_window(event)
            event.accept()
        # 处理窗口拖动
        elif event.buttons() == Qt.MouseButton.LeftButton and self._is_dragging:
            if self._drag_position is not None:
                self.move(event.globalPosition().toPoint() - self._drag_position)
                event.accept()
        else:
            # 检查鼠标是否在窗口边缘，并设置相应的鼠标指针
            resize_area = self._get_resize_area(event.pos())
            if resize_area:
                self._set_cursor_for_resize_area(resize_area)
            else:
                self.unsetCursor()
            super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._drag_position = None
            self._resize_enabled = False
            self._resize_area = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        try:
            super().resizeEvent(event)
            radius = getattr(self, '_corner_radius', 12)
            rect = self.rect()
            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)
            region = QRegion(path.toFillPolygon().toPolygon())
            self.setMask(region)
        except Exception:
            pass
            
    def _get_resize_area(self, pos):
        """检测鼠标是否在窗口边缘区域
        
        Args:
            pos: 鼠标位置
            
        Returns:
            str: 返回边缘区域类型，None表示不在边缘区域
        """
        rect = self.rect()
        x, y = pos.x(), pos.y()
        margin = self._resize_margin
        
        # 检查是否在左边缘
        if x <= margin:
            if y <= margin:
                return 'top_left'
            elif y >= rect.height() - margin:
                return 'bottom_left'
            else:
                return 'left'
        # 检查是否在右边缘
        elif x >= rect.width() - margin:
            if y <= margin:
                return 'top_right'
            elif y >= rect.height() - margin:
                return 'bottom_right'
            else:
                return 'right'
        # 检查是否在上边缘
        elif y <= margin:
            return 'top'
        # 检查是否在下边缘
        elif y >= rect.height() - margin:
            return 'bottom'
            
        return None
        
    def _set_cursor_for_resize_area(self, area):
        """根据边缘区域设置鼠标指针
        
        Args:
            area: 边缘区域类型
        """
        if area in ('left', 'right'):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif area in ('top', 'bottom'):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif area in ('top_left', 'bottom_right'):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif area in ('top_right', 'bottom_left'):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            
    def _resize_window(self, event):
        """调整窗口大小
        
        Args:
            event: 鼠标事件
        """
        if not self._resize_area:
            return
            
        global_pos = event.globalPosition().toPoint()
        rect = self.geometry()
        
        if self._resize_area == 'left':
            new_width = rect.right() - global_pos.x()
            if new_width > self.minimumWidth():
                rect.setLeft(global_pos.x())
                self.setGeometry(rect)
        elif self._resize_area == 'right':
            new_width = global_pos.x() - rect.left()
            if new_width > self.minimumWidth():
                rect.setRight(global_pos.x())
                self.setGeometry(rect)
        elif self._resize_area == 'top':
            new_height = rect.bottom() - global_pos.y()
            if new_height > self.minimumHeight():
                rect.setTop(global_pos.y())
                self.setGeometry(rect)
        elif self._resize_area == 'bottom':
            new_height = global_pos.y() - rect.top()
            if new_height > self.minimumHeight():
                rect.setBottom(global_pos.y())
                self.setGeometry(rect)
        elif self._resize_area == 'top_left':
            new_width = rect.right() - global_pos.x()
            new_height = rect.bottom() - global_pos.y()
            if new_width > self.minimumWidth() and new_height > self.minimumHeight():
                rect.setTopLeft(global_pos)
                self.setGeometry(rect)
        elif self._resize_area == 'top_right':
            new_width = global_pos.x() - rect.left()
            new_height = rect.bottom() - global_pos.y()
            if new_width > self.minimumWidth() and new_height > self.minimumHeight():
                rect.setTopRight(global_pos)
                self.setGeometry(rect)
        elif self._resize_area == 'bottom_left':
            new_width = rect.right() - global_pos.x()
            new_height = global_pos.y() - rect.top()
            if new_width > self.minimumWidth() and new_height > self.minimumHeight():
                rect.setBottomLeft(global_pos)
                self.setGeometry(rect)
        elif self._resize_area == 'bottom_right':
            new_width = global_pos.x() - rect.left()
            new_height = global_pos.y() - rect.top()
            if new_width > self.minimumWidth() and new_height > self.minimumHeight():
                rect.setBottomRight(global_pos)
                self.setGeometry(rect)
    def load_image_directory(self) -> None:
        """加载图片目录功能"""
        LIM.load_image_directory(self)
    def _create_resource_list(self) -> None:
        self.resource_list = QListWidget()
        self.resource_list.setMinimumWidth(0)
        self.resource_list.setMaximumWidth(220)
        self.resource_list.setIconSize(QSize(80, 80))  
        self.resource_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.resource_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.resource_list.setMovement(QListWidget.Movement.Static)
        self.resource_list.setSpacing(10)
        self.resource_list.setWordWrap(True)
        self.resource_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # 添加这行
        self.resource_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.resource_list.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.resource_list.setStyleSheet("background-color: #FAFAF2; color: #333333; border: 1px solid #E6E4D6;")

    def _create_control_panel(self) -> None:
        self.control_panel = QFrame()
        self.control_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.control_panel.setMinimumWidth(0)
        self.control_panel.setMaximumWidth(200)
        self.control_panel.setStyleSheet("background-color: #FAFAF2; color: #333333; border: 1px solid #E6E4D6;")
        control_layout = QVBoxLayout(self.control_panel)
        control_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        control_layout.addWidget(QLabel('控制面板'))
        self.parent_label_list = ParentLabelList()
        self.create_label_btn = self.parent_label_list.btn_add
        control_layout.addWidget(self.create_label_btn)
        
        # 添加导出数据集按钮
        self.export_dataset_btn = QPushButton('导出数据集')
        control_layout.addWidget(self.export_dataset_btn)
        # 添加修改分辨率按钮（位于导出数据集与父标签列表之间）
        self.resize_btn = QPushButton('修改图像分辨率')
        control_layout.addWidget(self.resize_btn)
        self.resize_btn.clicked.connect(self.enlarge_current_image_10x)

        control_layout.addWidget(self.parent_label_list)
        
    def _setup_event_connections(self) -> None:
        try:
            # 连接滚动条滚动事件
            self.resource_list.verticalScrollBar().valueChanged.connect(self._on_resource_list_scrolled)
            self.resource_list.horizontalScrollBar().valueChanged.connect(self._on_resource_list_scrolled)
            
            # 添加资源列表点击事件连接
            self.resource_list.itemClicked.connect(self.on_resource_selected)
            
            # 连接导出数据集按钮
            self.export_dataset_btn.clicked.connect(self.show_export_dataset_dialog)

            # 连接父标签列表变化信号，刷新画布
            if hasattr(self, 'parent_label_list') and self.parent_label_list:
                try:
                    self.parent_label_list.labels_changed.connect(lambda: (self.canvas.update_rects() if hasattr(self, 'canvas') and self.canvas else None))
                except Exception:
                    pass
                try:
                    self.parent_label_list.child_label_list.child_hovered.connect(self._on_child_label_hovered)
                except Exception:
                    pass
                try:
                    self.parent_label_list.child_label_list.child_delete_requested.connect(self._on_child_label_delete_requested)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"设置事件连接时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")

    def _on_child_label_hovered(self, child):
        try:
            from app_ui.choose_moon import highlight_child_label
            if hasattr(self, 'canvas') and self.canvas:
                highlight_child_label(self.canvas, child)
        except Exception:
            pass

    def _on_child_label_delete_requested(self, child):
        try:
            from app_ui.delet_moon import delete_child_label_by_object
            if hasattr(self, 'canvas') and self.canvas:
                delete_child_label_by_object(self.canvas, child)
        except Exception:
            pass

    def init_workspace(self) -> None:

        try:
            
            self.setWindowTitle('手动标注工具 - 正在扫描工作区...')
            QApplication.processEvents()
            files = self.resource_manager.scan_resources()
            self.resource_list.clear()
            if files:
                self.images = files
                if len(files) > 0:
                    self.parent_label_list.set_current_image_info(
                        files[0], total=len(files), current_idx=0)
            else:
                self.images = []
            self.setWindowTitle('moonlight')

        except Exception as e:
            logger.error(f"初始化工作区时发生错误: {e}")
            import traceback
            logger.error(f"错误堆栈信息: {traceback.format_exc()}")
            QMessageBox.warning(self, "警告", f"初始化工作区失败: {e}")
            self.setWindowTitle('手动标注工具')
    def _load_thumbnail_for_item(self, file_path: str, list_idx: int) -> None:

        try:
            # 检查列表项是否存在
            item = self.resource_list.item(list_idx)
            if not item:
                return
                
            # 如果已经有图标，跳过
            if not item.icon().isNull():
                return
                
            # 加载图片
            image = self.resource_manager.load_image_safe(file_path)
            if not image:
                return
                
            # 创建缩略图
            thumbnail = QPixmap.fromImage(image).scaled(
                        80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            # 设置图标
            item.setIcon(QIcon(thumbnail))

        except Exception as e:
            logger.error(f"为列表项加载缩略图时发生错误 {file_path}: {e}")

    def on_resource_selected(self, item: QListWidgetItem) -> None:

        try:
            idx = self.resource_list.row(item)
            if 0 <= idx < len(self.images):
                image_path = self.images[idx]
                if self.resource_manager.is_valid_image_path(image_path):
                    # 设置当前图片路径
                    self.current_image_path = image_path
                    # 使用GraphicsCanvas的load_image方法加载图片
                    self.canvas.load_image(image_path)
                    self._update_current_image_info(image_path, idx)
                else:
                    logger.warning(f"选择的图片路径无效: {image_path}")
                    QMessageBox.warning(self, "警告", "选择的图片文件无效或已被删除")

        except Exception as e:
            logger.error(f"处理资源选择事件时发生错误: {e}")

    def _on_resource_list_scrolled(self) -> None:
        """处理资源列表滚动事件，加载可见的图片预览"""
        try:
            # 遍历所有列表项
            for i in range(self.resource_list.count()):
                item = self.resource_list.item(i)
                if not item:
                    continue
                    
                # 如果已经有图标，跳过
                if not item.icon().isNull():
                    continue
                    
                # 检查项是否可见
                rect = self.resource_list.visualItemRect(item)
                if self.resource_list.viewport().rect().intersects(rect):
                    # 项可见，加载缩略图
                    if i < len(self.images):
                        self._load_thumbnail_for_item(self.images[i], i)
        except Exception as e:
            logger.error(f"处理资源列表滚动事件时发生错误: {e}")

    def update_resource_list_for_image(self, image_path: str) -> None:

        try:
            if not self.resource_manager.is_valid_image_path(image_path):
                logger.warning(f"无效的图片路径: {image_path}")
                return
            dir_path = os.path.dirname(image_path)

            files = []
            for ext in LIM.ImageProcessingConfig.SUPPORTED_FORMATS:
                pattern = os.path.join(dir_path, f'*.{ext}')
                files.extend(glob.glob(pattern))
            files = sorted(files, key=lambda x: os.path.basename(x).lower())
            self.resource_list.clear()
            self.images = files
            # 为每个图片文件创建列表项
            for i, file_path in enumerate(files):
                item = QListWidgetItem(os.path.basename(file_path))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setSizeHint(QSize(110, 130))
                self.resource_list.addItem(item)
                self._load_thumbnail_for_item(file_path, i)
            base_name = os.path.basename(image_path)
            current_idx = 0
            for i in range(len(files)):
                if os.path.basename(files[i]) == base_name:
                    current_idx = i
                    break

            self.parent_label_list.set_current_image_info(
                image_path, total=len(files), current_idx=current_idx)
            # 在画布上显示选中的图片
            self.canvas.load_image(image_path)

        except Exception as e:
            logger.error(f"更新资源列表时发生错误: {e}")
            QMessageBox.warning(self, "警告", f"更新资源列表失败: {e}")

    def display_image(self, image_path: str) -> None:

        try:
            if not self.resource_manager.is_valid_image_path(image_path):
                logger.warning(f"尝试显示无效图片: {image_path}")
                return
            self.current_image_path = image_path

            if image_path in self.images:
                idx = self.images.index(image_path)
                self.parent_label_list.set_current_image_info(
                    image_path, total=len(self.images), current_idx=idx)
            else:
                self.parent_label_list.set_current_image_info(
                    image_path, total=1, current_idx=0)

            success = self.canvas.load_image(image_path)

            if not success:
                logger.warning(f"无法加载图片: {image_path}")

        except Exception as e:
            logger.error(f"显示图片时发生错误 {image_path}: {e}")
            self.setWindowTitle('手动标注工具')

    def get_current_image_info(self) -> Optional[str]:

        return getattr(self, 'current_image_path', None)

    def refresh_child_labels_for_current_image(self) -> None:
        """刷新当前图片的子标签显示"""
        try:
            if hasattr(self, 'current_image_path') and self.current_image_path:
                current_idx = 0
                if self.current_image_path in self.images:
                    current_idx = self.images.index(self.current_image_path)

                self.parent_label_list.set_current_image_info(
                    self.current_image_path, 
                    total=len(self.images), 
                    current_idx=current_idx)

        except Exception as e:
            logger.error(f"刷新子标签显示时发生错误: {e}")
    def get_existing_bboxes(self, image_path: str) -> List[Tuple[float, float, float, float]]:

        try:
            existing_boxes = []
            parent = self.parent_label_list.get_selected()

            if (not parent or 
                not hasattr(parent, 'children_by_image') or 
                image_path not in parent.children_by_image):
                return existing_boxes

            for child in parent.children_by_image[image_path]:
                if getattr(child, 'is_placeholder', False):
                    continue
                existing_boxes.append((
                    child.x_center, child.y_center, child.width, child.height))

            return existing_boxes

        except Exception as e:
            logger.error(f"获取已存在标注框时发生错误: {e}")
            return []

    def create_label(self, x_center: float, y_center: float, 
                    width: float, height: float, image_path: str) -> bool:

        try:
            parent = self.parent_label_list.get_selected()
            if not parent:
                logger.warning("未选择父标签，无法创建子标签")
                return False

            child = self.parent_label_list.create_child_label(
                x_center, y_center, width, height, image_info=image_path, mask_data=None)

            success = child is not None
            if success:
                return success

        except Exception as e:
            logger.error(f"创建标签时发生错误: {e}")
            return False
            
    def show_previous_image(self) -> None:
        """显示上一张图片"""
        try:
            if not hasattr(self, 'images') or not self.images:
                return
                
            current_image_path = self.get_current_image_info()
            
            # 如果画布上没有图片，加载资源列表中的第一张图片
            if not current_image_path:
                first_image_path = self.images[0]
                self.display_image(first_image_path)
                self.resource_list.setCurrentRow(0)
                return
                
            # 获取当前图片索引
            current_idx = -1
            if current_image_path in self.images:
                current_idx = self.images.index(current_image_path)
                
            # 计算上一张图片索引
            prev_idx = current_idx - 1
            if prev_idx < 0:
                prev_idx = len(self.images) - 1  # 循环到最后一张
                
            # 显示上一张图片
            if 0 <= prev_idx < len(self.images):
                prev_image_path = self.images[prev_idx]
                self.display_image(prev_image_path)
                
                # 更新资源列表选中状态
                self.resource_list.setCurrentRow(prev_idx)
                
        except Exception as e:
            logger.error(f"显示上一张图片时发生错误: {e}")
            
    def show_next_image(self) -> None:
        """显示下一张图片"""
        try:
            if not hasattr(self, 'images') or not self.images:
                return
                
            current_image_path = self.get_current_image_info()
            
            # 如果画布上没有图片，加载资源列表中的第一张图片
            if not current_image_path:
                first_image_path = self.images[0]
                self.display_image(first_image_path)
                self.resource_list.setCurrentRow(0)
                return
                
            # 获取当前图片索引
            current_idx = -1
            if current_image_path in self.images:
                current_idx = self.images.index(current_image_path)
                
            # 计算下一张图片索引
            next_idx = current_idx + 1
            if next_idx >= len(self.images):
                next_idx = 0  # 循环到第一张
                
            # 显示下一张图片
            if 0 <= next_idx < len(self.images):
                next_image_path = self.images[next_idx]
                self.display_image(next_image_path)
                
                # 更新资源列表选中状态
                self.resource_list.setCurrentRow(next_idx)
                
        except Exception as e:
            logger.error(f"显示下一张图片时发生错误: {e}")
    def closeEvent(self, event) -> None:

        try:
            # 停止自动矩形框绘制器
            if hasattr(self, 'auto_rect_pen') and self.auto_rect_pen:
                self.auto_rect_pen.stop()
                logger.info("自动矩形框绘制器已停止")
            try:
                if hasattr(self, '_resize_worker') and self._resize_worker:
                    if self._resize_worker.isRunning():
                        self._resize_worker.quit()
                        self._resize_worker.wait(3000)
                        if self._resize_worker.isRunning():
                            self._resize_worker.terminate()
                            self._resize_worker.wait(1000)
            except Exception:
                pass

            import gc
            gc.collect()
            event.accept()

        except Exception as e:
            logger.error(f"关闭应用程序时发生错误: {e}")
            event.accept()
    def show_export_dataset_dialog(self) -> None:
        """显示数据集导出对话框"""
        try:
            from dataset_export_dialog import DatasetExportDialog
            
            # 检查是否有标签数据
            if not self.parent_label_list.labels:
                QMessageBox.warning(self, "警告", "没有可导出的标签数据")
                return
                
            # 创建并显示导出对话框
            dialog = DatasetExportDialog(self, self)
            dialog.exec()
            
        except Exception as e:
            logger.error(f"显示数据集导出对话框时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"显示数据集导出对话框失败: {e}")

    def _update_current_image_info(self, image_path: str, idx: int) -> None:

        try:
            self.parent_label_list.set_current_image_info(
                image_path, total=len(self.images), current_idx=idx)
        except Exception as e:
            logger.error(f"更新当前图片信息时发生错误: {e}")
def main():

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Moonlight标注工具")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("Moonlight标注工具")
        
        # 设置应用程序图标
        import os
        from PyQt6.QtGui import QIcon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acc", "logo.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        window = MainWindow()
        window.show()
        # 初始化全局模型加载器（在后台线程中加载模型）
        from services.global_model_loader import get_global_model_loader
        global_model_loader = get_global_model_loader()
        
        # 连接模型加载异常信号：出现任一错误则保持自动标注关闭
        global_model_loader.loading_error.connect(lambda name, msg: (
            setattr(window, '_model_loading_had_error', True),
            logger.warning(f"模型加载异常: {name} - {msg}")
        ))

        # 连接模型加载完成信号：仅当无错误时，自动开启自动标注
        global_model_loader.all_models_loaded.connect(lambda: (
            logger.info("所有模型加载完成"),
            (window.toggle_auto_annotation(True) if not getattr(window, '_model_loading_had_error', False) else logger.info("检测到权重加载异常，自动标注初始状态保持关闭"))
        ))
        
        # 启动模型加载
        global_model_loader.load_all_models()
        
        
        sys.exit(app.exec())

    except Exception as e:
        logger.critical(f"启动应用程序时发生严重错误: {e}")
        import traceback
        logger.critical(f"错误堆栈信息: {traceback.format_exc()}")
        if 'app' in locals():
            QMessageBox.critical(None, "严重错误", f"应用程序启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
