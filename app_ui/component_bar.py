import os
import sys
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
#组件栏
def _apply_button_style(btn):
    btn.setStyleSheet(
        "QPushButton {background-color: #F7F7F0; color: #333333; border: 1px solid #D0D0D0; border-radius: 4px; font-weight: bold;}"
        "QPushButton:checked {background-color: #4CAF50; color: white;}"
        "QPushButton:!checked {background-color: #F7F7F0; color: #333333;}"
        "QPushButton:hover {background-color: #EEEDE6;}"
        "QPushButton:!checked:hover {background-color: #EEEDE6;}"
    )

def _set_icon(btn, path, fallback_text):
    if os.path.exists(path):
        btn.setIcon(QIcon(path))
        btn.setIconSize(btn.size())
    else:
        btn.setText(fallback_text)

def setup_component_bar(main_window):
    bar = QFrame()
    bar.setMinimumWidth(0)
    bar.setMaximumWidth(40)
    bar.setStyleSheet("background-color: #FAFAF2; border-right: 1px solid #E6E4D6;")
    layout = QVBoxLayout(bar)
    layout.setContentsMargins(5, 10, 5, 10)
    layout.setSpacing(10)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    if hasattr(sys, '_MEIPASS'):
        app_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(base_dir)

    main_window.rect_mode_switch = QPushButton()
    main_window.rect_mode_switch.setFixedSize(30, 30)
    main_window.rect_mode_switch.setCheckable(True)
    main_window.rect_mode_switch.setChecked(True)
    main_window.rect_mode_switch.setToolTip("矩形框模式")
    _set_icon(main_window.rect_mode_switch, os.path.join(app_dir, "acc", "rectopenim.png"), "矩")
    _apply_button_style(main_window.rect_mode_switch)

    main_window.polygon_mode_switch = QPushButton()
    main_window.polygon_mode_switch.setFixedSize(30, 30)
    main_window.polygon_mode_switch.setCheckable(True)
    main_window.polygon_mode_switch.setChecked(False)
    main_window.polygon_mode_switch.setToolTip("多边形模式")
    _set_icon(main_window.polygon_mode_switch, os.path.join(app_dir, "acc", "polygon_icon.svg"), "多")
    _apply_button_style(main_window.polygon_mode_switch)

    main_window.pan_mode_switch = QPushButton()
    main_window.pan_mode_switch.setFixedSize(30, 30)
    main_window.pan_mode_switch.setCheckable(True)
    main_window.pan_mode_switch.setChecked(False)
    main_window.pan_mode_switch.setToolTip("平移模式")
    _set_icon(main_window.pan_mode_switch, os.path.join(app_dir, "acc", "moveitim.png"), "平")
    _apply_button_style(main_window.pan_mode_switch)

    main_window.mask_mode_switch = QPushButton()
    main_window.mask_mode_switch.setFixedSize(30, 30)
    main_window.mask_mode_switch.setCheckable(True)
    main_window.mask_mode_switch.setChecked(False)
    main_window.mask_mode_switch.setToolTip("MASK模式")
    _set_icon(main_window.mask_mode_switch, os.path.join(app_dir, "acc", "mask.png"), "M")
    _apply_button_style(main_window.mask_mode_switch)

    main_window.obb_mode_switch = QPushButton()
    main_window.obb_mode_switch.setFixedSize(30, 30)
    main_window.obb_mode_switch.setCheckable(True)
    main_window.obb_mode_switch.setChecked(False)
    main_window.obb_mode_switch.setToolTip("OBB模式")
    _set_icon(main_window.obb_mode_switch, os.path.join(app_dir, "acc", "obbopenim.png"), "O")
    _apply_button_style(main_window.obb_mode_switch)

    main_window.free_mode_switch = QPushButton()
    main_window.free_mode_switch.setFixedSize(30, 30)
    main_window.free_mode_switch.setCheckable(True)
    main_window.free_mode_switch.setChecked(False)
    main_window.free_mode_switch.setToolTip("自由标注模式")
    _set_icon(main_window.free_mode_switch, os.path.join(app_dir, "acc", "bi.png"), "自")
    _apply_button_style(main_window.free_mode_switch)

    main_window.rect_mode_switch.toggled.connect(main_window.toggle_rect_mode)
    main_window.polygon_mode_switch.toggled.connect(main_window.toggle_polygon_mode)
    main_window.pan_mode_switch.toggled.connect(main_window.toggle_pan_mode)
    main_window.mask_mode_switch.toggled.connect(main_window.toggle_mask_mode)
    main_window.obb_mode_switch.toggled.connect(main_window.toggle_obb_mode)
    main_window.free_mode_switch.toggled.connect(main_window.toggle_free_mode)

    layout.addWidget(main_window.pan_mode_switch)
    layout.addWidget(main_window.rect_mode_switch)
    layout.addWidget(main_window.polygon_mode_switch)
    layout.addWidget(main_window.mask_mode_switch)
    layout.addWidget(main_window.obb_mode_switch)
    layout.addWidget(main_window.free_mode_switch)
    layout.addStretch()

    return bar
