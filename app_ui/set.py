
import os
import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QDialogButtonBox, QCheckBox, 
                            QListWidget, QListWidgetItem, QStackedWidget,
                            QSplitter, QWidget, QFormLayout, QLineEdit, QTabWidget, QComboBox, QFileDialog, QFrame, QScrollArea, QRadioButton)
from PyQt6.QtCore import Qt, QSettings
from app_ui.remote_sensing import is_remote_sensing_enabled, set_remote_sensing_enabled

class SettingsDialog(QDialog):
    """设置对话框类"""
    
    def __init__(self, parent=None):
        """初始化设置对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(600, 400)
        self.resize(700, 480)
        self.settings = QSettings("MoonlightV2", "Settings")
        self.init_ui()
    
    def init_ui(self):
        """初始化设置界面"""
        # 创建主布局
        main_layout = QVBoxLayout()
        
        # 创建侧边栏和内容区域的分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 创建侧边栏
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(150)
        self.sidebar.addItem("自动标注设置")
        self.sidebar.addItem("快捷键设置")
        self.sidebar.addItem("遥感设置")
        self.sidebar.addItem("图像分辨率")
        
        self.sidebar.currentRowChanged.connect(self.change_page)
        
        # 创建内容区域的堆叠窗口
        self.stacked_widget = QStackedWidget()
        
        # 创建自动标注设置页面（使用滚动容器包裹，避免内容溢出）
        self.auto_annotation_page = self.create_auto_annotation_page()
        auto_scroll = QScrollArea()
        auto_scroll.setWidget(self.auto_annotation_page)
        auto_scroll.setWidgetResizable(True)
        self.stacked_widget.addWidget(auto_scroll)

        # 创建快捷键设置页面
        self.shortcuts_page = self.create_shortcuts_page()
        self.stacked_widget.addWidget(self.shortcuts_page)

        # 创建其他设置页面
        self.other_settings_page = self.create_other_settings_page()
        self.stacked_widget.addWidget(self.other_settings_page)
        self.resolution_settings_page = self.create_resolution_settings_page()
        self.stacked_widget.addWidget(self.resolution_settings_page)
        
        
        # 将侧边栏和内容区域添加到分割器
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.stacked_widget)
        splitter.setSizes([150, 450])  # 设置初始大小比例
        
        # 将分割器添加到主布局
        main_layout.addWidget(splitter)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        
        # 添加确定和取消按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # 将按钮添加到按钮布局，并设置靠右对齐
        button_layout.addStretch()
        button_layout.addWidget(button_box)
        
        # 将按钮布局添加到主布局
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)

    def create_resolution_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title_label = QLabel("图像分辨率阈值")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        form = QFormLayout()
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["1080P", "1.5K", "2K", "4K", "8K", "16K"])
        current = self.settings.value("resolution_threshold", "1080p", type=str)
        idx_map = {"1080p":0, "1.5k":1, "2k":2, "4k":3, "8k":4, "16k":5}
        self.resolution_combo.setCurrentIndex(idx_map.get(str(current).lower(), 0))
        form.addRow(QLabel("目标分辨率"), self.resolution_combo)
        layout.addLayout(form)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def create_shortcuts_page(self):
        """创建快捷键设置页面"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题
        title_label = QLabel("快捷键设置")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        desc_label = QLabel("为常用操作设置键盘快捷键（如 Ctrl+K）。值将保存到系统配置中并在下次启动时生效。")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc_label)

        # 表单布局
        form = QFormLayout()

        # 默认快捷键映射（与 key_moon.py 中保持一致）
        defaults = {
            "shortcuts/load_image_dir": "Ctrl+K",
            "shortcuts/create_label": "Ctrl+W",
            "shortcuts/delete_rect": "Ctrl+D",
            "shortcuts/delete_by_box": "Ctrl+F",
            "shortcuts/prev_image": "A",
            "shortcuts/next_image": "D",
            "shortcuts/toggle_auto_annotation": "Ctrl+A",
            "shortcuts/open_batch_annotation": "Ctrl+P",
            "shortcuts/prev_parent_label": "Q",
            "shortcuts/next_parent_label": "E",
        }

        # 保存输入框引用，便于保存
        self.shortcut_edits = {}

        def add_row(key: str, label_text: str, default_value: str):
            value = self.settings.value(key, default_value, type=str)
            edit = QLineEdit()
            edit.setText(value)
            edit.setPlaceholderText("例如：Ctrl+K、A、Ctrl+Shift+O")
            form.addRow(QLabel(label_text), edit)
            self.shortcut_edits[key] = edit

        add_row("shortcuts/load_image_dir", "打开图片目录", defaults["shortcuts/load_image_dir"]) 
        add_row("shortcuts/create_label", "创建新标签", defaults["shortcuts/create_label"]) 
        add_row("shortcuts/delete_rect", "删除矩形框", defaults["shortcuts/delete_rect"]) 
        add_row("shortcuts/delete_by_box", "框选删除", defaults["shortcuts/delete_by_box"]) 
        add_row("shortcuts/prev_image", "上一张图片", defaults["shortcuts/prev_image"]) 
        add_row("shortcuts/next_image", "下一张图片", defaults["shortcuts/next_image"]) 
        add_row("shortcuts/toggle_auto_annotation", "自动标注开关", defaults["shortcuts/toggle_auto_annotation"]) 
        add_row("shortcuts/open_batch_annotation", "批量标注", defaults["shortcuts/open_batch_annotation"]) 
        add_row("shortcuts/prev_parent_label", "上一个父标签", defaults["shortcuts/prev_parent_label"]) 
        add_row("shortcuts/next_parent_label", "下一个父标签", defaults["shortcuts/next_parent_label"]) 

        layout.addLayout(form)

        # 提示
        tip = QLabel("注：快捷键修改会保存到配置。若当前会话未自动应用，请重启程序或稍后在主界面启用。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #999; font-size: 11px; margin-top: 10px;")
        layout.addWidget(tip)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def create_auto_annotation_page(self):
        """创建自动标注设置页面"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 添加标题标签
        title_label = QLabel("自动标注设置")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 添加语义激活开关
        self.semantic_checkbox = QCheckBox("启用语义激活")
        semantic_enabled = self.settings.value("semantic_enabled", False, type=bool)
        self.semantic_checkbox.setChecked(semantic_enabled)
        layout.addWidget(self.semantic_checkbox)
        
        # 添加说明标签
        semantic_desc = QLabel("启用语义激活后，YOLOE推理将使用语义描述增强检测效果但目前处于测试阶段未必有效")
        semantic_desc.setWordWrap(True)
        semantic_desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(semantic_desc)
        
        # 添加分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("margin: 10px 0; background: #ddd;")
        layout.addWidget(line)
        
        # 添加跳过yolov开关
        self.skip_yolov_checkbox = QCheckBox("跳过YOLOV推理")
        skip_yolov_enabled = self.settings.value("skip_yolov", False, type=bool)
        self.skip_yolov_checkbox.setChecked(skip_yolov_enabled)
        layout.addWidget(self.skip_yolov_checkbox)
        
        # 添加说明标签
        skip_yolov_desc = QLabel("启用后将跳过所有YOLOV推理，直接将框选区域输入给YOLOE")
        skip_yolov_desc.setWordWrap(True)
        skip_yolov_desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(skip_yolov_desc)
        
        # 添加分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        line2.setStyleSheet("margin: 10px 0; background: #ddd;")
        layout.addWidget(line2)

        yolov_title = QLabel("YOLOV 模型选择")
        yolov_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        yolov_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 6px;")
        layout.addWidget(yolov_title)

        self.yolov_custom_btn = QPushButton("使用自定义YOLOV模型")
        def _choose_yolov_weight():
            try:
                start_dir = os.path.join(os.getcwd(), 'models', 'weights', 'rect')
                if not os.path.isdir(start_dir):
                    start_dir = os.getcwd()
                file_path, _ = QFileDialog.getOpenFileName(self, "选择YOLOV权重文件", start_dir, "权重文件 (*.pt)")
                if file_path:
                    try:
                        mgr = get_settings_manager()
                    except Exception:
                        mgr = None
                    if mgr is not None:
                        try:
                            mgr.custom_yolov_weight = file_path
                        except Exception:
                            pass
                    try:
                        base = os.path.basename(file_path)
                        self.yolov_custom_label.setText(f"当前自定义权重: {base}")
                    except Exception:
                        self.yolov_custom_label.setText("当前自定义权重: 已选择")
            except Exception:
                pass
        self.yolov_custom_btn.clicked.connect(_choose_yolov_weight)
        layout.addWidget(self.yolov_custom_btn)

        self.yolov_custom_label = QLabel()
        self.yolov_custom_label.setText("当前自定义权重: 未选择")
        layout.addWidget(self.yolov_custom_label)
        
    # NOTE: 用户不再允许通过设置界面控制是否跳过 SAM 推理，
    # SAM 的启用/禁用由程序内部逻辑控制（例如矩形模式下会自动跳过）。
        
        # SAM设置已移动到单独的页面
        
        # 添加弹性空间
        layout.addStretch()
        
        page.setLayout(layout)
        return page

        
    
    def create_other_settings_page(self):
        """创建其他设置页面"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 添加标题标签
        title_label = QLabel("其他设置")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 添加占位符标签
        placeholder_label = QLabel("其他设置选项将在这里添加")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet("color: #999; font-size: 14px; margin: 50px 0;")
        layout.addWidget(placeholder_label)
        
        # 已移除：遥感模式开关迁移至顶部栏，取消持久化
        
        # 添加弹性空间
        layout.addStretch()
        
        page.setLayout(layout)
        return page
    
    def change_page(self, row):
        """切换设置页面
        
        Args:
            row: 侧边栏选中的行索引
        """
        self.stacked_widget.setCurrentIndex(row)
    
    def accept(self):
        """保存设置并关闭对话框"""
        # 保存语义激活开关状态
        self.settings.setValue("semantic_enabled", self.semantic_checkbox.isChecked())
        # 保存跳过yolov开关状态
        self.settings.setValue("skip_yolov", self.skip_yolov_checkbox.isChecked())
        # 遥感模式开关已迁移至顶部栏，此处不再保存
        # SAM切换改为即时触发，此处不再处理切换
        # 保存快捷键设置
        if hasattr(self, 'shortcut_edits') and isinstance(self.shortcut_edits, dict):
            for key, edit in self.shortcut_edits.items():
                value = edit.text().strip()
                # 简单校验：非空
                if value:
                    self.settings.setValue(key, value)
                else:
                    # 若为空，不保存（保留原值）
                    pass
        # 不再保存 skip_sam，用户无权通过设置界面跳过 SAM
        if hasattr(self, 'resolution_combo'):
            text = self.resolution_combo.currentText().lower()
            mapping = {"1080p":"1080p","1.5k":"1.5k","2k":"2k","4k":"4k","8k":"8k","16k":"16k"}
            self.settings.setValue("resolution_threshold", mapping.get(text, "1080p"))
        super().accept()


class SettingsManager:
    """设置管理器类"""
    
    def __init__(self):
        """初始化设置管理器"""
        self.settings_dialog = None
        self.settings = QSettings("MoonlightV2", "Settings")
        self.custom_yolov_weight = None
    
    def show_settings_dialog(self, parent=None):
        """显示设置对话框
        
        Args:
            parent: 父窗口
        """
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(parent)
        self.settings_dialog.show()
    
    def is_semantic_enabled(self):
        """获取语义激活开关状态
        
        Returns:
            bool: 语义激活是否启用
        """
        return self.settings.value("semantic_enabled", False, type=bool)
    
    def is_skip_yolov_enabled(self):
        """获取跳过yolov开关状态
        
        Returns:
            bool: 是否跳过yolov推理
        """
        return self.settings.value("skip_yolov", False, type=bool)
    
    def is_skip_sam_enabled(self):
        """获取跳过SAM开关状态
        
        Returns:
            bool: 是否跳过SAM推理
        """
        # 用户不再可以通过设置控制 SAM；默认为 False（不跳过），
        # 具体是否跳过由推理逻辑中的条件（例如矩形模式）决定。
        return False

    

    def get_shortcut(self, key: str, default_value: str = "") -> str:
        """获取快捷键值
        
        Args:
            key: 存储键，例如 'shortcuts/load_image_dir'
            default_value: 默认值
        Returns:
            str: 快捷键字符串（如 'Ctrl+K'）
        """
        return self.settings.value(key, default_value, type=str)

    def get_all_shortcuts(self) -> dict:
        """获取所有快捷键信息的字典"""
        defaults = {
            "shortcuts/load_image_dir": "Ctrl+K",
            "shortcuts/create_label": "Ctrl+W",
            "shortcuts/delete_rect": "Ctrl+D",
            "shortcuts/delete_by_box": "Ctrl+F",
            "shortcuts/prev_image": "A",
            "shortcuts/next_image": "D",
            "shortcuts/toggle_auto_annotation": "Ctrl+A",
            "shortcuts/open_batch_annotation": "Ctrl+P",
            "shortcuts/prev_parent_label": "Q",
            "shortcuts/next_parent_label": "E",
        }
        return {k: self.get_shortcut(k, v) for k, v in defaults.items()}


# 全局设置管理器实例
settings_manager = None


def get_settings_manager():
    """获取全局设置管理器实例
    
    Returns:
        SettingsManager: 设置管理器实例
    """
    global settings_manager
    if settings_manager is None:
        settings_manager = SettingsManager()
    return settings_manager
