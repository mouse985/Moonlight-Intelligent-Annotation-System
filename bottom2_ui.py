import os
import sys
import numpy as np
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QSlider, QPushButton, QSizePolicy, QMenu, QWidgetAction, QWidget, QRadioButton, QButtonGroup
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
try:
    import cv2
except Exception:
    cv2 = None

def setup_bottom2_toolbar(main_window):
    right = QFrame()
    right.setStyleSheet("background-color: #FAFAF2; border-top: 1px solid #E6E4D6;")
    layout = QVBoxLayout(right)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(4)
    try:
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    except Exception:
        pass
    def _current_image_path():
        try:
            if hasattr(main_window, 'images') and main_window.images and hasattr(main_window, 'resource_list'):
                idx = main_window.resource_list.currentRow()
                if 0 <= idx < len(main_window.images):
                    return main_window.images[idx]
        except Exception:
            pass
        return None
    def _ensure_original_bgr():
        try:
            if not hasattr(main_window.canvas, '_rgb_original_bgr') or main_window.canvas._rgb_original_bgr is None:
                p = _current_image_path()
                if p and cv2 is not None:
                    img = cv2.imread(p)
                    if img is not None:
                        main_window.canvas._rgb_original_bgr = img
        except Exception:
            pass
    def _apply_rgb(rp, gp, bp):
        try:
            _ensure_original_bgr()
            img = getattr(main_window.canvas, '_rgb_original_bgr', None)
            if img is None:
                return
            bgr = img.astype(np.float32)
            fr = float(rp) / 100.0
            fg = float(gp) / 100.0
            fb = float(bp) / 100.0
            bgr[..., 2] = np.clip(bgr[..., 2] * fr, 0, 255)
            bgr[..., 1] = np.clip(bgr[..., 1] * fg, 0, 255)
            bgr[..., 0] = np.clip(bgr[..., 0] * fb, 0, 255)
            bgr_u8 = bgr.astype(np.uint8)
            rgb = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2RGB) if cv2 is not None else bgr_u8[..., ::-1]
            h, w = rgb.shape[:2]
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            qpix = QPixmap.fromImage(qimg)
            view = main_window.canvas
            try:
                if hasattr(view, 'image_item') and view.image_item:
                    view.image_item.setPixmap(qpix)
                else:
                    if hasattr(view, 'current_pixmap'):
                        view.current_pixmap = qpix
                    if hasattr(view, 'scene') and isinstance(view.scene(), type(view.scene())):
                        pass
            except Exception:
                pass
        except Exception:
            pass
    def _reset():
        try:
            if hasattr(main_window.canvas, '_rgb_original_bgr') and main_window.canvas._rgb_original_bgr is not None:
                img = main_window.canvas._rgb_original_bgr
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if cv2 is not None else img[..., ::-1]
                h, w = rgb.shape[:2]
                qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
                qpix = QPixmap.fromImage(qimg)
                view = main_window.canvas
                try:
                    if hasattr(view, 'image_item') and view.image_item:
                        view.image_item.setPixmap(qpix)
                    else:
                        if hasattr(view, 'current_pixmap'):
                            view.current_pixmap = qpix
                    r_slider.setValue(100)
                    g_slider.setValue(100)
                    b_slider.setValue(100)
                except Exception:
                    pass
        except Exception:
            pass
    r_label = QLabel("R")
    g_label = QLabel("G")
    b_label = QLabel("B")
    r_slider = QSlider(Qt.Orientation.Horizontal)
    g_slider = QSlider(Qt.Orientation.Horizontal)
    b_slider = QSlider(Qt.Orientation.Horizontal)
    for s in (r_slider, g_slider, b_slider):
        s.setRange(0, 200)
        s.setValue(100)
        s.setFixedWidth(100)
    r_slider.valueChanged.connect(lambda v: _apply_rgb(v, g_slider.value(), b_slider.value()))
    g_slider.valueChanged.connect(lambda v: _apply_rgb(r_slider.value(), v, b_slider.value()))
    b_slider.valueChanged.connect(lambda v: _apply_rgb(r_slider.value(), g_slider.value(), v))
    reset_btn = QPushButton("重置")
    reset_btn.setFixedSize(50, 24)
    reset_btn.clicked.connect(_reset)
    rgb_btn = QPushButton("RGB")
    rgb_btn.setFixedSize(44, 24)
    def _show_rgb_menu():
        try:
            menu = QMenu(main_window)
            cont = QWidget()
            v = QVBoxLayout(cont)
            v.setContentsMargins(8, 6, 8, 6)
            v.setSpacing(6)
            title = QLabel("颜色调节")
            v.addWidget(title)
            r_row = QFrame()
            r_row_layout = QHBoxLayout(r_row)
            r_row_layout.setContentsMargins(0, 0, 0, 0)
            r_row_layout.setSpacing(8)
            r_row_layout.addWidget(r_label)
            r_row_layout.addWidget(r_slider)
            v.addWidget(r_row)
            g_row = QFrame()
            g_row_layout = QHBoxLayout(g_row)
            g_row_layout.setContentsMargins(0, 0, 0, 0)
            g_row_layout.setSpacing(8)
            g_row_layout.addWidget(g_label)
            g_row_layout.addWidget(g_slider)
            v.addWidget(g_row)
            b_row = QFrame()
            b_row_layout = QHBoxLayout(b_row)
            b_row_layout.setContentsMargins(0, 0, 0, 0)
            b_row_layout.setSpacing(8)
            b_row_layout.addWidget(b_label)
            b_row_layout.addWidget(b_slider)
            v.addWidget(b_row)
            v.addWidget(reset_btn)
            act = QWidgetAction(main_window)
            act.setDefaultWidget(cont)
            menu.addAction(act)
            pos = rgb_btn.mapToGlobal(rgb_btn.rect().topLeft())
            menu.exec(pos)
        except Exception:
            pass
    rgb_btn.clicked.connect(_show_rgb_menu)
    def _has_image():
        try:
            if hasattr(main_window, 'canvas') and getattr(main_window.canvas, 'image_item', None):
                return True
            p = _current_image_path()
            return bool(p and os.path.exists(p))
        except Exception:
            return False
    rgb_btn.setVisible(_has_image())
    try:
        if hasattr(main_window, 'resource_list') and hasattr(main_window.resource_list, 'currentRowChanged'):
            main_window.resource_list.currentRowChanged.connect(lambda _i: rgb_btn.setVisible(_has_image()))
    except Exception:
        pass
    

    sam_row = QFrame()
    sam_row_layout = QHBoxLayout(sam_row)
    sam_row_layout.setContentsMargins(0, 0, 0, 0)
    sam_row_layout.setSpacing(6)
    sam_label = QLabel("SAM")
    sam_label.setStyleSheet("font-size: 12px; color: #333;")
    try:
        sam_row.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    except Exception:
        pass
    btn_style = (
        "QPushButton { background-color: #EDEFEA; color: #333333; border: none; border-radius: 4px; font-weight: bold; }"
        "QPushButton:checked { background-color: #66BB6A; color: white; }"
        "QPushButton:hover { background-color: #EEEDE6; }"
        "QToolTip { background-color: #FFF7D6; color: #333333; border: 1px solid #999999; padding: 2px; font-size: 12px; }"
    )
    b_sam3 = QPushButton()
    b_sam3.setCheckable(True)
    b_sam3.setFixedSize(60, 24)
    b_sam3.setToolTip("SAM3")
    b_sam3.setText("SAM3")
    b_sam3.setStyleSheet(btn_style)
    b_sam2 = QPushButton()
    b_sam2.setCheckable(True)
    b_sam2.setFixedSize(60, 24)
    b_sam2.setToolTip("SAM2")
    b_sam2.setText("SAM2")
    b_sam2.setStyleSheet(btn_style)
    sam_group = QButtonGroup(main_window)
    sam_group.setExclusive(True)
    sam_group.addButton(b_sam3)
    sam_group.addButton(b_sam2)
    sam_row_layout.addWidget(sam_label)
    sam_row_layout.addWidget(b_sam3)
    sam_row_layout.addWidget(b_sam2)
    sam_row_layout.addStretch()

    _sam_syncing = {'v': False}
    _sam_loading = {'dlg': None}

    def _show_loading_dialog():
        try:
            from PyQt6.QtWidgets import QProgressDialog
            dlg = QProgressDialog('正在加载SAM模型…', None, 0, 100, main_window)
            dlg.setWindowTitle('加载中')
            dlg.setMinimumDuration(0)
            dlg.setValue(0)
            dlg.setCancelButton(None)
            _sam_loading['dlg'] = dlg
            dlg.show()
        except Exception:
            _sam_loading['dlg'] = None

    def _close_loading_dialog():
        try:
            if _sam_loading['dlg']:
                _sam_loading['dlg'].close()
                _sam_loading['dlg'] = None
        except Exception:
            pass

    def _apply_sam_model(path):
        try:
            from services.global_model_loader import get_global_model_loader
        except Exception:
            try:
                from global_model_loader import get_global_model_loader
            except Exception:
                return
        loader = get_global_model_loader()
        try:
            model = loader.get_model("sam")
            if model is not None:
                cname = model.__class__.__name__
                if cname != "Sam3Adapter":
                    wpath = getattr(model, "pt", None)
                    if wpath and os.path.abspath(wpath) == os.path.abspath(path):
                        _sync_sam_ui_state()
                        return
                else:
                    base = os.path.basename(path).lower()
                    if base == "sam3.pt" and cname == "Sam3Adapter":
                        _sync_sam_ui_state()
                        return
        except Exception:
            pass
        _show_loading_dialog()
        import threading
        def _run():
            try:
                loader.switch_sam_model(path)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def _sync_sam_ui_state():
        _sam_syncing['v'] = True
        try:
            from services.global_model_loader import get_global_model_loader
        except Exception:
            try:
                from global_model_loader import get_global_model_loader
            except Exception:
                _sam_syncing['v'] = False
                return
        loader = get_global_model_loader()
        model = loader.get_model("sam")
        if model is None:
            _sam_syncing['v'] = False
            return
        cname = model.__class__.__name__
        if cname == "Sam3Adapter":
            b_sam3.setChecked(True)
        else:
            b_sam2.setChecked(True)
        _sam_syncing['v'] = False

    try:
        from services.global_model_loader import get_global_model_loader
    except Exception:
        try:
            from global_model_loader import get_global_model_loader
        except Exception:
            get_global_model_loader = None
    if get_global_model_loader:
        _loader = get_global_model_loader()
        def _on_loading_started(name):
            if name == "SAM" and _sam_loading['dlg']:
                try:
                    _sam_loading['dlg'].setValue(0)
                except Exception:
                    pass
        def _on_loading_progress(name, pct):
            if name == "SAM" and _sam_loading['dlg']:
                try:
                    _sam_loading['dlg'].setValue(max(0, min(int(pct), 100)))
                except Exception:
                    pass
        def _on_loading_completed(name):
            if name == "SAM":
                try:
                    from sam_ops.OBBSAM import sam_manager as _obb_mgr
                except Exception:
                    _obb_mgr = None
                try:
                    import sam_ops.MASKSAM as _ms
                    _mask_mgr = getattr(_ms, 'mask_sam_manager', None)
                except Exception:
                    _mask_mgr = None
                try:
                    if _obb_mgr is not None:
                        _obb_mgr.model = _loader.get_model("sam")
                except Exception:
                    pass
                try:
                    if _mask_mgr is not None:
                        _mask_mgr.model = _loader.get_model("sam")
                except Exception:
                    pass
                _close_loading_dialog()
                _sync_sam_ui_state()
        def _on_loading_error(name, msg):
            if name == "SAM":
                _close_loading_dialog()
                _sync_sam_ui_state()
        try:
            _loader.loading_started.connect(_on_loading_started)
            _loader.loading_progress.connect(_on_loading_progress)
            _loader.loading_completed.connect(_on_loading_completed)
            _loader.loading_error.connect(_on_loading_error)
        except Exception:
            pass

    def _on_rb_sam3_toggled(checked):
        if not checked or _sam_syncing['v']:
            return
        repo_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        candidates = [
            os.path.join(repo_root, 'sam3.pt'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'weights', 'SAMmodels', 'sam3.pt'),
            os.path.join(os.getcwd(), 'models', 'weights', 'SAMmodels', 'sam3.pt'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'weights', 'sam3.pt'),
            os.path.join(os.getcwd(), 'models', 'weights', 'sam3.pt'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'weights', 'SAMmodels', 'SAM3', 'sam3.pt'),
            os.path.join(os.getcwd(), 'models', 'weights', 'SAMmodels', 'SAM3', 'sam3.pt'),
        ]
        if hasattr(sys, 'frozen') and sys.frozen:
            candidates.extend([
                os.path.join(os.path.dirname(sys.executable), 'models', 'weights', 'SAMmodels', 'SAM3', 'sam3.pt'),
                os.path.join(os.path.dirname(sys.executable), 'models', 'weights', 'SAMmodels', 'sam3.pt'),
                os.path.join(os.path.dirname(sys.executable), 'models', 'weights', 'sam3.pt'),
                os.path.join(os.path.dirname(sys.executable), 'sam3.pt'),
            ])
        model_path = None
        for p in candidates:
            if os.path.exists(p):
                model_path = p
                break
        try:
            try:
                from services.global_model_loader import get_global_model_loader, select_active_sam
            except Exception:
                from global_model_loader import get_global_model_loader, select_active_sam
            loader = get_global_model_loader()
            if getattr(loader, 'is_model_loaded', None) and loader.is_model_loaded('sam3'):
                select_active_sam('sam3')
            elif model_path:
                _apply_sam_model(model_path)
        except Exception:
            if model_path:
                _apply_sam_model(model_path)

    def _on_rb_sam2_toggled(checked):
        if not checked or _sam_syncing['v']:
            return
        try:
            sam2_dir = r"c:\moonlightv\models\weights\SAMmodels\SAM2"
            if os.path.isdir(sam2_dir):
                files = [os.path.join(sam2_dir, f) for f in os.listdir(sam2_dir) if f.endswith('.pt')]
                if files:
                    path = min(files, key=lambda p: os.path.getsize(p))
                    try:
                        try:
                            from services.global_model_loader import get_global_model_loader, select_active_sam
                        except Exception:
                            from global_model_loader import get_global_model_loader, select_active_sam
                        loader = get_global_model_loader()
                        if getattr(loader, 'is_model_loaded', None) and loader.is_model_loaded('sam2'):
                            select_active_sam('sam2')
                        else:
                            _apply_sam_model(path)
                    except Exception:
                        _apply_sam_model(path)
        except Exception:
            _close_loading_dialog()

    b_sam3.toggled.connect(_on_rb_sam3_toggled)
    b_sam2.toggled.connect(_on_rb_sam2_toggled)

    def _is_mask_or_obb():
        try:
            cm = getattr(main_window, 'canvas', None)
            if cm is not None:
                if getattr(cm, 'mask_mode', False) or getattr(cm, 'obb_mode', False):
                    return True
            if hasattr(main_window, 'mask_mode_switch') and main_window.mask_mode_switch.isChecked():
                return True
            if hasattr(main_window, 'obb_mode_switch') and main_window.obb_mode_switch.isChecked():
                return True
        except Exception:
            pass
        return False

    sam_row.setVisible(_is_mask_or_obb())
    def _ensure_vis_binding():
        try:
            bound = False
            if hasattr(main_window, 'mask_mode_switch') and not getattr(_ensure_vis_binding, '_mask_connected', False):
                main_window.mask_mode_switch.toggled.connect(lambda _b: sam_row.setVisible(_is_mask_or_obb()))
                _ensure_vis_binding._mask_connected = True
                bound = True
            if hasattr(main_window, 'obb_mode_switch') and not getattr(_ensure_vis_binding, '_obb_connected', False):
                main_window.obb_mode_switch.toggled.connect(lambda _b: sam_row.setVisible(_is_mask_or_obb()))
                _ensure_vis_binding._obb_connected = True
                bound = True
            if not getattr(_ensure_vis_binding, '_scheduled', False):
                _ensure_vis_binding._scheduled = True
                def _retry():
                    if not (getattr(_ensure_vis_binding, '_mask_connected', False) and getattr(_ensure_vis_binding, '_obb_connected', False)):
                        _ensure_vis_binding._scheduled = False
                        QTimer.singleShot(200, _ensure_vis_binding)
                QTimer.singleShot(0 if bound else 200, _retry)
        except Exception:
            pass
    _ensure_vis_binding()

    try:
        try:
            from services.global_model_loader import get_global_model_loader, select_active_sam
        except Exception:
            from global_model_loader import get_global_model_loader, select_active_sam
        loader = get_global_model_loader()
        try:
            if getattr(loader, 'is_model_loaded', None) and loader.is_model_loaded('sam2'):
                select_active_sam('sam2')
            else:
                sam2_dir = r"c:\moonlightv\models\weights\SAMmodels\SAM2"
                if os.path.isdir(sam2_dir):
                    files = [os.path.join(sam2_dir, f) for f in os.listdir(sam2_dir) if f.endswith('.pt')]
                    if files:
                        path = min(files, key=lambda p: os.path.getsize(p))
                        _apply_sam_model(path)
        except Exception:
            pass
    except Exception:
        pass
    try:
        from app_ui.tutorial import show_tutorial_if_needed
        show_tutorial_if_needed(main_window)
    except Exception:
        pass

    _sync_sam_ui_state()
    row = QFrame()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    row_layout.addWidget(rgb_btn)
    row_layout.addWidget(sam_row)
    row_layout.addStretch()
    layout.addWidget(row)
    return right
