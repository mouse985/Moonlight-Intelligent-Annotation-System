import os
import sys
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QButtonGroup,
)


def setup_bottom_toolbar(main_window):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    btn_style = (
        "QPushButton { background-color: #EDEFEA; color: #333333; border: none; border-radius: 4px; font-weight: bold; }"
        "QPushButton:checked { background-color: #66BB6A; color: white; }"
        "QPushButton:hover { background-color: #EEEDE6; }"
        "QToolTip { background-color: #FFF7D6; color: #333333; border: 1px solid #999999; padding: 2px; font-size: 12px; }"
    )

    def new_toggle_btn(text: str, checked: bool, tip: str) -> QPushButton:
        b = QPushButton()
        b.setCheckable(True)
        b.setChecked(checked)
        b.setFixedSize(80, 30)
        b.setToolTip(tip)
        b.setText(text)
        b.setStyleSheet(btn_style)
        return b

    main_window.bottom_toolbar = QFrame()
    main_window.bottom_toolbar.setMinimumHeight(0)
    main_window.bottom_toolbar.setMaximumHeight(40)
    main_window.bottom_toolbar.setStyleSheet(
        "background-color: #FAFAF2; border-top: 1px solid #E6E4D6;"
    )

    main_window.bottom_toolbar_layout = QHBoxLayout(main_window.bottom_toolbar)
    main_window.bottom_toolbar_layout.setContentsMargins(12, 6, 12, 6)
    main_window.bottom_toolbar_layout.setSpacing(10)

    main_window.bottom_toolbar_left = QFrame()
    main_window.bottom_toolbar_left.setStyleSheet("background-color: transparent;")
    main_window.bottom_toolbar_left_layout = QHBoxLayout(main_window.bottom_toolbar_left)
    main_window.bottom_toolbar_left_layout.setContentsMargins(0, 0, 0, 0)
    main_window.bottom_toolbar_left_layout.setSpacing(10)

    try:
        from bottom2_ui import setup_bottom2_toolbar
        main_window.bottom_toolbar_right = setup_bottom2_toolbar(main_window)
    except Exception:
        main_window.bottom_toolbar_right = QFrame()
        main_window.bottom_toolbar_right.setStyleSheet("background-color: transparent;")
        _right_layout = QHBoxLayout(main_window.bottom_toolbar_right)
        _right_layout.setContentsMargins(0, 0, 0, 0)
        _right_layout.setSpacing(10)

    main_window.bottom_toolbar_layout.addWidget(main_window.bottom_toolbar_left, stretch=1)
    main_window.bottom_toolbar_layout.addWidget(main_window.bottom_toolbar_right, stretch=1)

    # MASK 模式栏
    main_window.mask_mode_bar = QFrame()
    main_window.mask_mode_bar.setStyleSheet("background-color: transparent;")
    mask_mode_layout = QHBoxLayout(main_window.mask_mode_bar)
    mask_mode_layout.setContentsMargins(0, 0, 0, 0)
    mask_mode_layout.setSpacing(10)

    main_window.mask_point_input_btn = new_toggle_btn("点输入", True, "点输入模式")
    main_window.mask_bbox_input_btn = new_toggle_btn("BBOX输入", False, "BBOX输入模式")

    main_window.mask_input_group = QButtonGroup(main_window)
    main_window.mask_input_group.setExclusive(True)
    main_window.mask_input_group.addButton(main_window.mask_point_input_btn)
    main_window.mask_input_group.addButton(main_window.mask_bbox_input_btn)

    main_window.mask_point_input_btn.toggled.connect(main_window._on_mask_input_mode_changed)
    main_window.mask_bbox_input_btn.toggled.connect(main_window._on_mask_input_mode_changed)

    mask_mode_layout.addWidget(QLabel("输入模式:"))
    mask_mode_layout.addWidget(main_window.mask_point_input_btn)
    mask_mode_layout.addWidget(main_window.mask_bbox_input_btn)
    mask_mode_layout.addStretch()
    main_window.mask_mode_bar.setVisible(False)
    main_window.bottom_toolbar_left_layout.addWidget(main_window.mask_mode_bar)

    # OBB 模式栏
    main_window.obb_mode_bar = QFrame()
    main_window.obb_mode_bar.setStyleSheet("background-color: transparent;")
    obb_mode_layout = QHBoxLayout(main_window.obb_mode_bar)
    obb_mode_layout.setContentsMargins(0, 0, 0, 0)
    obb_mode_layout.setSpacing(8)

    main_window.obb_point_input_btn = new_toggle_btn("点输入", True, "点输入模式")
    main_window.obb_bbox_input_btn = new_toggle_btn("BBOX输入", False, "BBOX输入模式")

    main_window.obb_input_group = QButtonGroup(main_window)
    main_window.obb_input_group.setExclusive(True)
    main_window.obb_input_group.addButton(main_window.obb_point_input_btn)
    main_window.obb_input_group.addButton(main_window.obb_bbox_input_btn)
    main_window.obb_point_input_btn.toggled.connect(main_window._on_obb_input_mode_changed)
    main_window.obb_bbox_input_btn.toggled.connect(main_window._on_obb_input_mode_changed)

    lbl_input = QLabel("输入模式:")
    main_window.obb_point_input_btn.setFixedSize(60, 24)
    main_window.obb_bbox_input_btn.setFixedSize(60, 24)
    obb_mode_layout.addWidget(lbl_input)
    obb_mode_layout.addWidget(main_window.obb_point_input_btn)
    obb_mode_layout.addWidget(main_window.obb_bbox_input_btn)

    lbl_output = QLabel("输出框类型:")
    main_window.obb_rect_min_btn = new_toggle_btn("最小外接矩形", True, "输出最小外接矩形")
    main_window.obb_rect_axis_btn = new_toggle_btn("正矩形", False, "输出轴对齐正矩形")
    main_window.obb_rect_group = QButtonGroup(main_window)
    main_window.obb_rect_group.setExclusive(True)
    main_window.obb_rect_group.addButton(main_window.obb_rect_min_btn)
    main_window.obb_rect_group.addButton(main_window.obb_rect_axis_btn)
    main_window.obb_rect_min_btn.toggled.connect(main_window._on_obb_rect_type_changed)
    main_window.obb_rect_axis_btn.toggled.connect(main_window._on_obb_rect_type_changed)
    main_window.obb_rect_min_btn.setFixedSize(90, 24)
    main_window.obb_rect_axis_btn.setFixedSize(70, 24)
    obb_mode_layout.addWidget(lbl_output)
    obb_mode_layout.addWidget(main_window.obb_rect_min_btn)
    obb_mode_layout.addWidget(main_window.obb_rect_axis_btn)
    obb_mode_layout.addStretch()
    main_window.obb_mode_bar.setVisible(False)
    main_window.bottom_toolbar_left_layout.addWidget(main_window.obb_mode_bar)

    # 自由画笔栏
    main_window.free_brush_bar = QFrame()
    main_window.free_brush_bar.setStyleSheet("background-color: transparent;")
    free_brush_layout = QHBoxLayout(main_window.free_brush_bar)
    free_brush_layout.setContentsMargins(0, 0, 0, 0)
    free_brush_layout.setSpacing(10)

    main_window.brush_point_btn = QPushButton()
    main_window.brush_point_btn.setCheckable(True)
    main_window.brush_point_btn.setFixedSize(50, 30)
    main_window.brush_point_btn.setToolTip("点画笔")
    point_icon_path = os.path.join(base_path, "acc", "porintimage.png")
    if os.path.exists(point_icon_path):
        main_window.brush_point_btn.setIcon(QIcon(point_icon_path))
        main_window.brush_point_btn.setIconSize(main_window.brush_point_btn.size())
    else:
        main_window.brush_point_btn.setText("点")
    main_window.brush_point_btn.setStyleSheet(btn_style)

    main_window.brush_line_btn = QPushButton()
    main_window.brush_line_btn.setCheckable(True)
    main_window.brush_line_btn.setFixedSize(50, 30)
    main_window.brush_line_btn.setToolTip("线画笔")
    line_icon_path = os.path.join(base_path, "acc", "lineimage.png")
    if os.path.exists(line_icon_path):
        main_window.brush_line_btn.setIcon(QIcon(line_icon_path))
        main_window.brush_line_btn.setIconSize(main_window.brush_line_btn.size())
    else:
        main_window.brush_line_btn.setText("线")
    main_window.brush_line_btn.setStyleSheet(btn_style)

    main_window.brush_triangle_btn = QPushButton()
    main_window.brush_triangle_btn.setCheckable(True)
    main_window.brush_triangle_btn.setFixedSize(60, 30)
    main_window.brush_triangle_btn.setToolTip("正三角形画笔")
    triangle_icon_path = os.path.join(base_path, "acc", "triangleimage.png")
    if os.path.exists(triangle_icon_path):
        main_window.brush_triangle_btn.setIcon(QIcon(triangle_icon_path))
        main_window.brush_triangle_btn.setIconSize(main_window.brush_triangle_btn.size())
    else:
        main_window.brush_triangle_btn.setText("三角")
    main_window.brush_triangle_btn.setStyleSheet(btn_style)

    main_window.brush_hexagon_btn = QPushButton()
    main_window.brush_hexagon_btn.setCheckable(True)
    main_window.brush_hexagon_btn.setFixedSize(60, 30)
    main_window.brush_hexagon_btn.setToolTip("正六边形画笔")
    hexagon_icon_path = os.path.join(base_path, "acc", "reguarimage.png")
    if os.path.exists(hexagon_icon_path):
        main_window.brush_hexagon_btn.setIcon(QIcon(hexagon_icon_path))
        main_window.brush_hexagon_btn.setIconSize(main_window.brush_hexagon_btn.size())
    else:
        main_window.brush_hexagon_btn.setText("六边")
    main_window.brush_hexagon_btn.setStyleSheet(btn_style)

    main_window.brush_octagon_btn = QPushButton()
    main_window.brush_octagon_btn.setCheckable(True)
    main_window.brush_octagon_btn.setFixedSize(60, 30)
    main_window.brush_octagon_btn.setToolTip("正八边形画笔")
    octagon_icon_path = os.path.join(base_path, "acc", "e8bianx.png")
    if os.path.exists(octagon_icon_path):
        main_window.brush_octagon_btn.setIcon(QIcon(octagon_icon_path))
        main_window.brush_octagon_btn.setIconSize(main_window.brush_octagon_btn.size())
    else:
        main_window.brush_octagon_btn.setText("八边")
    main_window.brush_octagon_btn.setStyleSheet(btn_style)

    main_window.brush_circle_btn = QPushButton()
    main_window.brush_circle_btn.setCheckable(True)
    main_window.brush_circle_btn.setFixedSize(60, 30)
    main_window.brush_circle_btn.setToolTip("圆形画笔")
    circle_icon_path = os.path.join(base_path, "acc", "circularimage.png")
    if os.path.exists(circle_icon_path):
        main_window.brush_circle_btn.setIcon(QIcon(circle_icon_path))
        main_window.brush_circle_btn.setIconSize(QSize(56, 26))
    else:
        main_window.brush_circle_btn.setText("圆形")
    main_window.brush_circle_btn.setStyleSheet(btn_style)

    main_window.free_brush_group = QButtonGroup(main_window)
    main_window.free_brush_group.setExclusive(True)
    main_window.free_brush_group.addButton(main_window.brush_point_btn)
    main_window.free_brush_group.addButton(main_window.brush_line_btn)
    main_window.free_brush_group.addButton(main_window.brush_triangle_btn)
    main_window.free_brush_group.addButton(main_window.brush_hexagon_btn)
    main_window.free_brush_group.addButton(main_window.brush_octagon_btn)
    main_window.free_brush_group.addButton(main_window.brush_circle_btn)

    main_window.brush_point_btn.toggled.connect(lambda checked: main_window._on_brush_selected('point', checked))
    main_window.brush_line_btn.toggled.connect(lambda checked: main_window._on_brush_selected('line', checked))
    main_window.brush_triangle_btn.toggled.connect(lambda checked: main_window._on_brush_selected('triangle', checked))
    main_window.brush_hexagon_btn.toggled.connect(lambda checked: main_window._on_brush_selected('hexagon', checked))
    main_window.brush_octagon_btn.toggled.connect(lambda checked: main_window._on_brush_selected('octagon', checked))
    main_window.brush_circle_btn.toggled.connect(lambda checked: main_window._on_brush_selected('circle', checked))

    free_brush_layout.addWidget(QLabel("画笔:"))
    free_brush_layout.addWidget(main_window.brush_point_btn)
    free_brush_layout.addWidget(main_window.brush_line_btn)
    free_brush_layout.addWidget(main_window.brush_triangle_btn)
    free_brush_layout.addWidget(main_window.brush_hexagon_btn)
    free_brush_layout.addWidget(main_window.brush_octagon_btn)
    free_brush_layout.addWidget(main_window.brush_circle_btn)
    main_window.free_brush_bar.setVisible(False)
    main_window.bottom_toolbar_left_layout.addWidget(main_window.free_brush_bar)

    main_window.bottom_toolbar_layout.addStretch()

    main_window.bottom_toggle_btn = QPushButton("▲")
    main_window.bottom_toggle_btn.setFixedSize(35, 30)
    main_window.bottom_toggle_btn.setStyleSheet(
        "QPushButton { background-color: transparent; color: #333333; border: none; } QPushButton:hover { background-color: #EFEFE7; }"
    )
    main_window.bottom_toggle_btn.setToolTip("上拉底部栏")
    main_window.bottom_toggle_btn.clicked.connect(main_window.toggle_bottom_toolbar)
    main_window.bottom_toolbar_layout.addWidget(
        main_window.bottom_toggle_btn, alignment=Qt.AlignmentFlag.AlignRight
    )

    try:
        def _right_click_toggle(ev):
            try:
                if ev.button() == Qt.MouseButton.LeftButton:
                    main_window.toggle_bottom_toolbar()
            except Exception:
                pass
        if hasattr(main_window, 'bottom_toolbar_right') and main_window.bottom_toolbar_right:
            main_window.bottom_toolbar_right.mousePressEvent = _right_click_toggle
    except Exception:
        pass

    return main_window.bottom_toolbar
