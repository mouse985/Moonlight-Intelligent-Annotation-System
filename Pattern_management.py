import logging
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsView


def toggle_rect_mode(main_window, checked: bool) -> None:
    try:
        if checked:
            if hasattr(main_window, 'polygon_mode_switch'):
                main_window.polygon_mode_switch.setChecked(False)
            if hasattr(main_window, 'pan_mode_switch'):
                main_window.pan_mode_switch.setChecked(False)
            if hasattr(main_window, 'mask_mode_switch'):
                main_window.mask_mode_switch.setChecked(False)
            if hasattr(main_window, 'obb_mode_switch'):
                main_window.obb_mode_switch.setChecked(False)
            if hasattr(main_window, 'free_mode_switch'):
                main_window.free_mode_switch.setChecked(False)
        if hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'draw_manager'):
            main_window.canvas.set_ui_locked(not checked)
            status_text = "矩形框模式已开启" if checked else "矩形框模式已关闭"
            main_window.setWindowTitle(f'moonlight - {status_text}')
    except Exception as e:
        logging.getLogger(__name__).error(f"切换矩形框模式时发生错误: {e}")


def toggle_polygon_mode(main_window, checked: bool) -> None:
    try:
        if checked:
            if hasattr(main_window, 'rect_mode_switch'):
                main_window.rect_mode_switch.setChecked(False)
            if hasattr(main_window, 'pan_mode_switch'):
                main_window.pan_mode_switch.setChecked(False)
            if hasattr(main_window, 'mask_mode_switch'):
                main_window.mask_mode_switch.setChecked(False)
            if hasattr(main_window, 'obb_mode_switch'):
                main_window.obb_mode_switch.setChecked(False)
            if hasattr(main_window, 'free_mode_switch'):
                main_window.free_mode_switch.setChecked(False)
        if hasattr(main_window, 'canvas'):
            main_window.canvas.set_polygon_mode(checked)
            main_window.canvas.set_ui_locked(False)
        status_text = "多边形模式已开启" if checked else "多边形模式已关闭"
        main_window.setWindowTitle(f'moonlight - {status_text}')
    except Exception as e:
        logging.getLogger(__name__).error(f"切换多边形模式时发生错误: {e}")


def toggle_pan_mode(main_window, checked: bool) -> None:
    try:
        if checked:
            if hasattr(main_window, 'rect_mode_switch'):
                main_window.rect_mode_switch.setChecked(False)
            if hasattr(main_window, 'polygon_mode_switch'):
                main_window.polygon_mode_switch.setChecked(False)
            if hasattr(main_window, 'mask_mode_switch'):
                main_window.mask_mode_switch.setChecked(False)
            if hasattr(main_window, 'obb_mode_switch'):
                main_window.obb_mode_switch.setChecked(False)
            if hasattr(main_window, 'free_mode_switch'):
                main_window.free_mode_switch.setChecked(False)
        if hasattr(main_window, 'canvas'):
            main_window.canvas.set_pan_mode(checked)
            try:
                from Move_it import enable_move_mode, disable_move_mode
                if checked:
                    enable_move_mode(main_window.canvas)
                else:
                    disable_move_mode(main_window.canvas)
            except ImportError:
                import logging
                logging.getLogger(__name__).warning("无法导入Move_it模块，使用默认平移模式")
        status_text = "平移模式已开启" if checked else "平移模式已关闭"
        main_window.setWindowTitle(f'moonlight - {status_text}')
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"切换平移模式时发生错误: {e}")


def _on_mask_input_mode_changed(main_window, checked: bool) -> None:
    try:
        is_point_input = main_window.mask_point_input_btn.isChecked()
        is_mask_active = hasattr(main_window, 'canvas') and getattr(main_window.canvas, 'mask_mode', False)
        if hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'auto_annotation_manager') and main_window.canvas.auto_annotation_manager:
            if is_point_input:
                if main_window.canvas.auto_annotation_manager.mask_sam_manager:
                    main_window.canvas.auto_annotation_manager.mask_sam_manager.reset_for_new_inference()
                if hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'scene'):
                    from PyQt6.QtWidgets import QGraphicsTextItem
                    for item in main_window.canvas.scene.items():
                        if isinstance(item, QGraphicsTextItem) and hasattr(item, 'is_bbox_hint'):
                            main_window.canvas.scene.removeItem(item)
                if is_mask_active:
                    main_window.canvas.bbox_input_mode = False
            else:
                if main_window.canvas.auto_annotation_manager.mask_sam_manager:
                    main_window.canvas.auto_annotation_manager.mask_sam_manager.clear_points()
                if is_mask_active:
                    main_window.canvas.bbox_input_mode = True
                if not hasattr(main_window.canvas, 'bbox_start_point'):
                    main_window.canvas.bbox_start_point = None
                if not hasattr(main_window.canvas, 'bbox_temp_item'):
                    main_window.canvas.bbox_temp_item = None
                if is_mask_active and hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'scene'):
                    # 清除旧的提示，避免重复
                    from PyQt6.QtWidgets import QGraphicsTextItem
                    for item in list(main_window.canvas.scene.items()):
                        if isinstance(item, QGraphicsTextItem) and hasattr(item, 'is_bbox_hint'):
                            main_window.canvas.scene.removeItem(item)
                    from PyQt6.QtWidgets import QGraphicsTextItem
                    from PyQt6.QtGui import QColor as _QColor
                    hint_text = QGraphicsTextItem("BBOX输入模式：拖动鼠标绘制矩形框")
                    hint_text.setPos(10, 10)
                    hint_text.setDefaultTextColor(_QColor(0, 128, 0))
                    font = hint_text.font()
                    font.setPointSize(14)
                    font.setBold(True)
                    hint_text.setFont(font)
                    hint_text.is_bbox_hint = True
                    main_window.canvas.scene.addItem(hint_text)
                    QTimer.singleShot(5000, lambda: _remove_bbox_hint(main_window, hint_text))
        else:
            import logging
            logging.getLogger(__name__).warning("无法更新MASK模式输入状态：自动标注管理器未初始化")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"处理MASK模式输入模式切换时发生错误: {e}")


def _remove_bbox_hint(main_window, hint_item):
    try:
        if hint_item and hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'scene'):
            main_window.canvas.scene.removeItem(hint_item)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"移除BBOX输入模式提示时发生错误: {e}")


def _on_obb_input_mode_changed(main_window, checked: bool) -> None:
    try:
        is_point_input = main_window.obb_point_input_btn.isChecked()
        is_obb_active = hasattr(main_window, 'canvas') and getattr(main_window.canvas, 'obb_mode', False)
        if hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'auto_annotation_manager') and main_window.canvas.auto_annotation_manager:
            if is_point_input:
                if main_window.canvas.auto_annotation_manager.obb_sam_manager:
                    main_window.canvas.auto_annotation_manager.obb_sam_manager.reset_for_new_inference()
                if hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'scene'):
                    from PyQt6.QtWidgets import QGraphicsTextItem
                    for item in main_window.canvas.scene.items():
                        if isinstance(item, QGraphicsTextItem) and hasattr(item, 'is_bbox_hint'):
                            main_window.canvas.scene.removeItem(item)
                if is_obb_active:
                    main_window.canvas.bbox_input_mode = False
            else:
                if main_window.canvas.auto_annotation_manager.obb_sam_manager:
                    main_window.canvas.auto_annotation_manager.obb_sam_manager.clear_points()
                if is_obb_active:
                    main_window.canvas.bbox_input_mode = True
                if not hasattr(main_window.canvas, 'bbox_start_point'):
                    main_window.canvas.bbox_start_point = None
                if not hasattr(main_window.canvas, 'bbox_temp_item'):
                    main_window.canvas.bbox_temp_item = None
                if is_obb_active and hasattr(main_window, 'canvas') and hasattr(main_window.canvas, 'scene'):
                    # 清除旧的提示，避免重复
                    from PyQt6.QtWidgets import QGraphicsTextItem
                    for item in list(main_window.canvas.scene.items()):
                        if isinstance(item, QGraphicsTextItem) and hasattr(item, 'is_bbox_hint'):
                            main_window.canvas.scene.removeItem(item)
                    from PyQt6.QtWidgets import QGraphicsTextItem
                    from PyQt6.QtGui import QColor as _QColor
                    hint_text = QGraphicsTextItem("BBOX输入模式：拖动鼠标绘制矩形框")
                    hint_text.setPos(10, 10)
                    hint_text.setDefaultTextColor(_QColor(0, 128, 0))
                    font = hint_text.font()
                    font.setPointSize(14)
                    font.setBold(True)
                    hint_text.setFont(font)
                    hint_text.is_bbox_hint = True
                    main_window.canvas.scene.addItem(hint_text)
                    QTimer.singleShot(5000, lambda: _remove_bbox_hint(main_window, hint_text))
        else:
            import logging
            logging.getLogger(__name__).warning("无法更新OBB模式输入状态：自动标注管理器未初始化")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"处理OBB模式输入模式切换时发生错误: {e}")


def toggle_mask_mode(main_window, checked: bool) -> None:
    try:
        if checked:
            if hasattr(main_window, 'rect_mode_switch'):
                main_window.rect_mode_switch.setChecked(False)
            if hasattr(main_window, 'polygon_mode_switch'):
                main_window.polygon_mode_switch.setChecked(False)
            if hasattr(main_window, 'pan_mode_switch'):
                main_window.pan_mode_switch.setChecked(False)
            if hasattr(main_window, 'obb_mode_switch'):
                main_window.obb_mode_switch.setChecked(False)
            if hasattr(main_window, 'free_mode_switch'):
                main_window.free_mode_switch.setChecked(False)
        if hasattr(main_window, 'canvas'):
            main_window.canvas.mask_mode = checked
            from auto_annotation_manager import get_auto_annotation_manager
            if checked and main_window.canvas.auto_annotation_manager is None:
                main_window.canvas.auto_annotation_manager = get_auto_annotation_manager(
                    main_window, main_window.canvas.parent_label_list, main_window.canvas
                )
            if main_window.canvas.auto_annotation_manager:
                main_window.canvas.auto_annotation_manager.set_mask_mode(checked)
                if checked and main_window.canvas.auto_annotation_manager.mask_sam_manager:
                    if not main_window.canvas.auto_annotation_manager.mask_sam_manager.model:
                        main_window.canvas.auto_annotation_manager.mask_sam_manager._get_model_from_global_loader()
                    main_window.canvas.auto_annotation_manager.mask_sam_manager.reset_for_new_inference()
            main_window.canvas.set_ui_locked(False)
            if checked:
                main_window.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
            else:
                if main_window.canvas.ui_locked:
                    main_window.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
                else:
                    main_window.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            if checked:
                main_window.canvas.bbox_input_mode = not main_window.mask_point_input_btn.isChecked()
            else:
                if getattr(main_window.canvas, 'obb_mode', False):
                    main_window.canvas.bbox_input_mode = not main_window.obb_point_input_btn.isChecked()
                else:
                    main_window.canvas.bbox_input_mode = False
        status_text = "MASK模式已开启" if checked else "MASK模式已关闭"
        main_window.setWindowTitle(f'moonlight - {status_text}')
        if hasattr(main_window, 'mask_mode_bar'):
            main_window.mask_mode_bar.setVisible(checked)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"切换MASK模式时发生错误: {e}")


def toggle_obb_mode(main_window, checked: bool) -> None:
    try:
        if checked:
            if hasattr(main_window, 'rect_mode_switch'):
                main_window.rect_mode_switch.setChecked(False)
            if hasattr(main_window, 'polygon_mode_switch'):
                main_window.polygon_mode_switch.setChecked(False)
            if hasattr(main_window, 'pan_mode_switch'):
                main_window.pan_mode_switch.setChecked(False)
            if hasattr(main_window, 'mask_mode_switch'):
                main_window.mask_mode_switch.setChecked(False)
            if hasattr(main_window, 'free_mode_switch'):
                main_window.free_mode_switch.setChecked(False)
        if hasattr(main_window, 'canvas'):
            main_window.canvas.obb_mode = checked
            from auto_annotation_manager import get_auto_annotation_manager
            if checked and main_window.canvas.auto_annotation_manager is None:
                main_window.canvas.auto_annotation_manager = get_auto_annotation_manager(
                    main_window, main_window.canvas.parent_label_list, main_window.canvas
                )
            if main_window.canvas.auto_annotation_manager:
                main_window.canvas.auto_annotation_manager.set_obb_mode(checked)
                if checked and main_window.canvas.auto_annotation_manager.obb_sam_manager:
                    if not main_window.canvas.auto_annotation_manager.obb_sam_manager.model:
                        main_window.canvas.auto_annotation_manager.obb_sam_manager._get_model_from_global_loader()
                    main_window.canvas.auto_annotation_manager.obb_sam_manager.reset_for_new_inference()
            main_window.canvas.set_ui_locked(False)
            if checked:
                main_window.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
            else:
                if main_window.canvas.ui_locked:
                    main_window.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
                else:
                    main_window.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            if checked:
                main_window.canvas.bbox_input_mode = not main_window.obb_point_input_btn.isChecked()
            else:
                if getattr(main_window.canvas, 'mask_mode', False):
                    main_window.canvas.bbox_input_mode = not main_window.mask_point_input_btn.isChecked()
                else:
                    main_window.canvas.bbox_input_mode = False
        status_text = "OBB模式已开启" if checked else "OBB模式已关闭"
        main_window.setWindowTitle(f'moonlight - {status_text}')
        if hasattr(main_window, 'obb_mode_bar'):
            main_window.obb_mode_bar.setVisible(checked)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"切换OBB模式时发生错误: {e}")


def toggle_free_mode(main_window, checked: bool) -> None:
    try:
        if checked:
            if hasattr(main_window, 'rect_mode_switch'):
                main_window.rect_mode_switch.setChecked(False)
            if hasattr(main_window, 'polygon_mode_switch'):
                main_window.polygon_mode_switch.setChecked(False)
            if hasattr(main_window, 'pan_mode_switch'):
                main_window.pan_mode_switch.setChecked(False)
            if hasattr(main_window, 'mask_mode_switch'):
                main_window.mask_mode_switch.setChecked(False)
            if hasattr(main_window, 'obb_mode_switch'):
                main_window.obb_mode_switch.setChecked(False)
        main_window.free_mode = checked
        if hasattr(main_window, 'free_brush_bar'):
            main_window.free_brush_bar.setVisible(checked)
        if hasattr(main_window, 'canvas'):
            main_window.canvas.free_mode = checked
            if checked:
                if hasattr(main_window, 'brush_point_btn'):
                    main_window.brush_point_btn.setChecked(True)
                main_window.canvas.free_brush_type = 'point'
                main_window.canvas.set_ui_locked(False)
                main_window.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
            else:
                main_window.canvas.free_brush_type = None
                if main_window.canvas.ui_locked:
                    main_window.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
                else:
                    main_window.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        status_text = "自由标注模式已开启" if checked else "自由标注模式已关闭"
        main_window.setWindowTitle(f"moonlight - {status_text}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"切换自由标注模式时发生错误: {e}")


def _on_brush_selected(main_window, brush_type: str, checked: bool) -> None:
    try:
        if not hasattr(main_window, 'canvas'):
            return
        if checked:
            main_window.canvas.free_brush_type = brush_type
        else:
            btns = []
            for name in ['brush_point_btn','brush_line_btn','brush_triangle_btn','brush_hexagon_btn','brush_octagon_btn','brush_circle_btn']:
                if hasattr(main_window, name):
                    btn = getattr(main_window, name)
                    if btn:
                        btns.append(btn)
            if btns and not any(btn.isChecked() for btn in btns):
                main_window.canvas.free_brush_type = None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"选择画笔类型时发生错误: {e}")