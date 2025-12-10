from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, 
    QGraphicsScene, QMessageBox, QPushButton, QApplication, QProgressDialog,
    QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsLineItem, QGraphicsEllipseItem
)
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap
from PyQt6.QtCore import Qt, QPointF, QPoint, QThread, QObject, pyqtSignal
from io_ops.clean import free_torch_memory


class SimpleCanvas(QGraphicsView):
    def __init__(self, mode: str = 'rectangle', parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMouseTracking(True)
        self.mode = mode
        # 启用缩放/平移友好设置
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._min_scale = 0.1
        self._max_scale = 8.0
        
        # 临时状态
        self._drawing_rect = False
        self._rect_start = None
        self._temp_rect_item = None

        # 图片图元
        self.image_item = None
        self.current_pixmap = None
        self.current_image_path = None  # 记录当前图片路径（若通过路径加载）

        # 引用主窗口用于取父标签颜色
        self.main_window = None
        self.parent_label_list = None

    def set_mode(self, mode: str):
        self.mode = 'rectangle'

    def _get_parent_color(self) -> QColor:
        """获取父标签颜色，若不可用则使用默认绿色。"""
        try:
            pll = self.parent_label_list
            if pll is None and hasattr(self, 'main_window') and self.main_window:
                pll = getattr(self.main_window, 'parent_label_list', None)
            parent = pll.get_selected() if pll else None
            if parent and hasattr(parent, 'color') and parent.color:
                return parent.color
        except Exception:
            pass
        return QColor(39, 174, 96)  # 默认绿色

    def _clamp_to_image(self, scene_pos: QPointF) -> QPoint:
        """将场景坐标限制在当前图片边界内并返回整数点。"""
        if self.current_pixmap:
            x = min(max(scene_pos.x(), 0), self.current_pixmap.width())
            y = min(max(scene_pos.y(), 0), self.current_pixmap.height())
            return QPoint(int(x), int(y))
        return QPoint(int(scene_pos.x()), int(scene_pos.y()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == 'rectangle':
                self._drawing_rect = True
                scene_pos = self.mapToScene(event.pos())
                start_pt = self._clamp_to_image(scene_pos)
                self._rect_start = start_pt
                if self._temp_rect_item:
                    try:
                        self.scene.removeItem(self._temp_rect_item)
                    except Exception:
                        pass
                    self._temp_rect_item = None
                self._temp_rect_item = QGraphicsRectItem(start_pt.x(), start_pt.y(), 0, 0)
                color = self._get_parent_color()
                pen = QPen(color, 2, Qt.PenStyle.DashLine)  # 橡皮筋效果使用虚线
                self._temp_rect_item.setPen(pen)
                self._temp_rect_item.setBrush(QBrush(Qt.GlobalColor.transparent))
                try:
                    self._temp_rect_item.setData(0, 'temp_rect')  # 标记临时矩形
                except Exception:
                    pass
                self.scene.addItem(self._temp_rect_item)
        elif event.button() == Qt.MouseButton.RightButton:
            pass
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drawing_rect and self._rect_start and self._temp_rect_item:
            scene_pos = self.mapToScene(event.pos())
            end_pt = self._clamp_to_image(scene_pos)
            x1, y1 = self._rect_start.x(), self._rect_start.y()
            x2, y2 = end_pt.x(), end_pt.y()
            left, top = min(x1, x2), min(y1, y2)
            width, height = abs(x2 - x1), abs(y2 - y1)
            self._temp_rect_item.setRect(left, top, width, height)
        else:
            pass
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing_rect:
            # 结束矩形绘制，保留最终矩形
            self._drawing_rect = False
            scene_pos = self.mapToScene(event.pos())
            end_pt = self._clamp_to_image(scene_pos)
            if self._rect_start is not None:
                x1, y1 = self._rect_start.x(), self._rect_start.y()
                x2, y2 = end_pt.x(), end_pt.y()
                left, top = min(x1, x2), min(y1, y2)
                width, height = abs(x2 - x1), abs(y2 - y1)
                if width > 5 and height > 5:
                    final_item = QGraphicsRectItem(left, top, width, height)
                    color = self._get_parent_color()
                    final_item.setPen(QPen(color, 2, Qt.PenStyle.SolidLine))
                    fill = QColor(color)
                    fill.setAlpha(40)
                    final_item.setBrush(QBrush(fill))
                    try:
                        final_item.setData(0, 'final_rect')  # 标记最终矩形
                    except Exception:
                        pass
                    self.scene.addItem(final_item)
            # 清理临时矩形
            if self._temp_rect_item:
                try:
                    self.scene.removeItem(self._temp_rect_item)
                except Exception:
                    pass
                self._temp_rect_item = None
            self._rect_start = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """滚轮缩放视图，锚点为鼠标位置。"""
        try:
            # 无图片时沿用默认行为
            if not self.image_item:
                return super().wheelEvent(event)
            delta = event.angleDelta().y()
            if delta == 0:
                return
            # 计算缩放因子：向上放大，向下缩小
            zoom_in_factor = 1.25
            zoom_out_factor = 1.0 / zoom_in_factor
            factor = zoom_in_factor if delta > 0 else zoom_out_factor
            # 限制缩放范围
            current_scale = self.transform().m11()
            new_scale = current_scale * factor
            if new_scale < self._min_scale:
                factor = self._min_scale / max(1e-6, current_scale)
            elif new_scale > self._max_scale:
                factor = self._max_scale / max(1e-6, current_scale)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(factor, factor)
            event.accept()
        except Exception:
            # 发生异常则回退默认滚轮行为
            try:
                super().wheelEvent(event)
            except Exception:
                pass

    def load_image_pixmap(self, pixmap: QPixmap) -> bool:
        """加载QPixmap到场景作为底图。"""
        try:
            if not pixmap or pixmap.isNull():
                return False
            if self.image_item:
                self.scene.removeItem(self.image_item)
                self.image_item = None
            self.image_item = QGraphicsPixmapItem(pixmap)
            self.image_item.setZValue(-1)
            self.scene.addItem(self.image_item)
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            self.resetTransform()
            # 重置缩放状态
            # 注意：transform().m11() 代表当前视图X缩放
            # 重置后为 1.0
            self._min_scale = 0.1
            self._max_scale = 8.0
            self.current_pixmap = pixmap
            self.current_image_path = None  # 通过pixmap加载时路径未知
            return True
        except Exception:
            return False

    def load_image_path(self, file_path: str) -> bool:
        """从文件路径加载图片作为底图。"""
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                return False
            ok = self.load_image_pixmap(pixmap)
            if ok:
                self.current_image_path = file_path
            return ok
        except Exception:
            return False

    

    def get_bounding_boxes(self) -> list:
        """导出当前场景中的所有最终矩形框与多边形的外接矩形，返回[x1,y1,x2,y2]列表。"""
        bboxes = []
        try:
            for item in self.scene.items():
                # 跳过底图
                if isinstance(item, QGraphicsPixmapItem):
                    continue
                # 提取最终矩形
                if isinstance(item, QGraphicsRectItem):
                    tag = None
                    try:
                        tag = item.data(0)
                    except Exception:
                        tag = None
                    if tag == 'final_rect' or tag is None:
                        rect = item.rect()
                        x1, y1 = rect.left(), rect.top()
                        x2, y2 = rect.right(), rect.bottom()
                        bboxes.append([float(x1), float(y1), float(x2), float(y2)])
                
        except Exception:
            pass
        return bboxes


class VisionPromptWindow(QMainWindow):
    def __init__(self, mode: str = 'rectangle', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Vision Prompt - 批量标注')
        self.resize(800, 600)

        # 运行状态
        self._inference_thread: QThread | None = None
        self._inference_worker: QObject | None = None
        self._running: bool = False

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.mode_label = QLabel(f"当前模式: {self._mode_text(mode)}")
        layout.addWidget(self.mode_label)

        self.canvas = SimpleCanvas(mode=mode, parent=self)
        # 允许画布访问主窗口（父标签颜色、图片信息）
        try:
            if parent:
                self.canvas.main_window = parent
                self.canvas.parent_label_list = getattr(parent, 'parent_label_list', None)
        except Exception:
            pass
        layout.addWidget(self.canvas, stretch=1)

        # 底部控制栏：开始执行按钮 + 状态
        controls = QHBoxLayout()
        self.start_btn = QPushButton('开始执行')
        self.start_btn.setFixedSize(100, 32)
        try:
            self.start_btn.clicked.connect(self.on_start_execute)
        except Exception:
            pass
        self.status_label = QLabel('状态：空闲')
        self.status_label.setFixedHeight(32)
        controls.addStretch(1)
        controls.addWidget(self.status_label)
        controls.addWidget(self.start_btn)
        layout.addLayout(controls)

        self.setCentralWidget(central)

    def set_mode(self, mode: str):
        self.mode_label.setText(f"当前模式: {self._mode_text(mode)}")
        self.canvas.set_mode(mode)

    def _mode_text(self, mode: str) -> str:
        return '矩形框'

    def on_start_execute(self) -> None:
        """开始批量推理：收集矩形框、图片路径，调用批量推理并在当前画布展示结果或弹出摘要。"""
        try:
            # 若正在运行，避免重复启动
            if self._running:
                try:
                    QMessageBox.information(self, '提示', '推理正在进行中，请稍候。')
                except Exception:
                    pass
                return

            # 收集矩形框
            bboxes = self.canvas.get_bounding_boxes()
            if not bboxes:
                QMessageBox.information(self, '提示', '请先在图像上绘制至少一个矩形框或多边形。')
                return

            # 获取当前图片路径
            image_path = None
            if getattr(self.canvas, 'current_image_path', None):
                image_path = self.canvas.current_image_path
            elif self.canvas.main_window and hasattr(self.canvas.main_window, 'current_image_path'):
                image_path = getattr(self.canvas.main_window, 'current_image_path', None)
            elif self.canvas.main_window and hasattr(self.canvas.main_window, 'get_current_image_info'):
                try:
                    image_path = self.canvas.main_window.get_current_image_info()
                except Exception:
                    image_path = None
            if not image_path:
                QMessageBox.warning(self, '警告', '未能获取当前图片路径，请从主窗口加载图片。')
                return

            # 构造资源列表（若主窗口存在 images，则使用）
            resource_list = []
            if self.canvas.main_window and hasattr(self.canvas.main_window, 'images'):
                imgs = getattr(self.canvas.main_window, 'images', [])
                if isinstance(imgs, list) and imgs:
                    resource_list = imgs

        # 异步执行批量推理（后台线程）
            from batch_rect_pen import BatchRectPenWorker

            # 创建后台线程与顺序标注工作者
            self._inference_thread = QThread()
            self._inference_worker = BatchRectPenWorker(image_path=image_path, bboxes=bboxes, resource_list=resource_list)
            self._inference_worker.moveToThread(self._inference_thread)

            # 连接信号槽：启动、绘制请求、进度、完成/失败、退出清理
            self._inference_thread.started.connect(self._inference_worker.run)
            try:
                self._inference_worker.request_draw.connect(self._on_request_draw)
                self._inference_worker.progress.connect(self._on_progress)
                self._inference_worker.progress_step.connect(self._on_progress_step)
                self._inference_worker.finished.connect(self._on_batch_finished)
                self._inference_worker.failed.connect(self._on_batch_failed)
            except Exception:
                pass
            self._inference_worker.finished.connect(self._inference_thread.quit)
            self._inference_worker.failed.connect(self._inference_thread.quit)
            self._inference_thread.finished.connect(self._cleanup_thread)

            # 弹出进度条并隐藏当前窗口
            try:
                total = len(resource_list) if resource_list else 1
                self._progress_dialog = QProgressDialog('正在批量标注...', None, 0, total, self)
                self._progress_dialog.setWindowTitle('批量标注进度')
                self._progress_dialog.setMinimumDuration(0)
                self._progress_dialog.setValue(0)
                # 允许取消并绑定终止逻辑
                try:
                    self._progress_dialog.canceled.connect(self._on_progress_cancel)
                except Exception:
                    pass
                self._progress_dialog.show()
                # 隐藏当前提示窗口
                self.hide()
            except Exception:
                self._progress_dialog = None

            # 更新UI状态并启动线程
            self._running = True
            try:
                self.start_btn.setEnabled(False)
                self.start_btn.setText('执行中…')
                self.status_label.setText('状态：执行中')
            except Exception:
                pass
            self._inference_thread.start()
            return

        except Exception as e:
            try:
                QMessageBox.critical(self, '错误', f'批量推理执行失败：{e}')
            except Exception:
                pass

    def _handle_inference_result(self, result: dict):
        """在主线程处理推理结果并更新UI。"""
        try:
            # 若第一次推理无结果，则直接提示并终止后续处理
            if result.get('first_stage_no_result') or (not result.get('success') and result.get('error') == '第一次推理无结果'):
                try:
                    QMessageBox.information(self, '提示', '第一次推理无结果：请调整选框位置或更换权重文件。')
                except Exception:
                    pass
                return

            success = bool(result.get('success'))
            bbox_list = result.get('bbox_list') or []
            filtered = result.get('filtered')

            # 若当前图片有 bbox 结果，则在画布上绘制出来
            drawn_count = 0
            if bbox_list:
                try:
                    color = self.canvas._get_parent_color()
                    for bbox in bbox_list:
                        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                            x1, y1, x2, y2 = map(float, bbox)
                            left, top = min(x1, x2), min(y1, y2)
                            width, height = abs(x2 - x1), abs(y2 - y1)
                            if width > 1 and height > 1:
                                item = QGraphicsRectItem(left, top, width, height)
                                item.setPen(QPen(color, 2, Qt.PenStyle.SolidLine))
                                fill = QColor(color)
                                fill.setAlpha(40)
                                item.setBrush(QBrush(fill))
                                try:
                                    item.setData(0, 'final_rect')
                                except Exception:
                                    pass
                                self.canvas.scene.addItem(item)
                                drawn_count += 1
                except Exception:
                    pass

            # 构建摘要信息
            summary_lines = []
            if drawn_count > 0:
                summary_lines.append(f'当前图片新增 {drawn_count} 个矩形框。')
            if isinstance(filtered, dict):
                try:
                    matched = sum(len(v) for v in filtered.values())
                    summary_lines.append(f'资源列表匹配总计 {matched} 条目标。')
                except Exception:
                    pass
            if not summary_lines:
                summary_lines.append('未获得有效的筛选结果。')

            QMessageBox.information(self, '批量推理完成', '\n'.join(summary_lines))
        finally:
            # 重置UI运行状态
            self._reset_run_state()

    def _handle_inference_error(self, err: str):
        try:
            QMessageBox.critical(self, '错误', f'批量推理执行失败：{err}')
        finally:
            self._reset_run_state()

    def _cleanup_thread(self):
        try:
            if self._inference_worker:
                self._inference_worker.deleteLater()
            if self._inference_thread:
                self._inference_thread.deleteLater()
        except Exception:
            pass
        self._inference_worker = None
        self._inference_thread = None

    def _reset_run_state(self):
        self._running = False
        try:
            self.start_btn.setEnabled(True)
            self.start_btn.setText('开始执行')
            self.status_label.setText('状态：空闲')
        except Exception:
            pass

    def _on_request_draw(self, img_path: str, bbox_list: list):
        created_count = 0
        ok = False
        try:
            # 切换画布到目标图片
            try:
                self.canvas.load_image_path(img_path)
            except Exception:
                pass

            # 标签创建：需要父标签列表与选中父标签
            parent_label_list = getattr(self.canvas, 'parent_label_list', None)
            if not parent_label_list or not parent_label_list.get_selected():
                QMessageBox.information(self, '提示', '请先在父标签列表中选中一个标签。')
                self._inference_worker.ack_draw(False)
                return

            # 逐个 bbox 创建子标签（使用顶点坐标），不直接手动画布项
            for bbox in bbox_list:
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    x1, y1, x2, y2 = map(float, bbox)
                    points = [x1, y1, x2, y1, x2, y2, x1, y2]
                    created = parent_label_list.create_child_label(points=points, image_info=img_path, mode='auto', shape_type='rectangle', mask_data=None)
                    if created:
                        created_count += 1

            # 统一刷新画布，使用内置绘制管理器
            if created_count > 0 and hasattr(self.canvas, 'update_rects'):
                self.canvas.update_rects()
            ok = created_count > 0
        except Exception as e:
            QMessageBox.critical(self, '错误', f'绘制标签时发生错误：{e}')
            ok = False
        finally:
            # 在完成标签创建后，立即清理本次推理产生的显存与内存（安全快速）
            try:
                if ok:
                    free_torch_memory()
            except Exception:
                pass
            try:
                self._inference_worker.ack_draw(ok)
            except Exception:
                pass

    def _on_progress(self, text: str):
        try:
            self.status_label.setText(f'状态：{text}')
        except Exception:
            pass

    def _on_progress_step(self, current: int, total: int):
        try:
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                # 若总数有变化，更新范围
                if self._progress_dialog.maximum() != total:
                    self._progress_dialog.setRange(0, total)
                self._progress_dialog.setValue(max(0, min(current, total)))
                self._progress_dialog.setLabelText(f'正在批量标注... 已处理 {current}/{total}')
        except Exception:
            pass

    def _on_batch_finished(self, summary: dict):
        try:
            processed = summary.get('processed', 0)
            total = summary.get('total', 0)
            QMessageBox.information(self, '批量标注完成', f'已完成 {processed}/{total} 张图片的推理与绘制。')
        finally:
            try:
                if hasattr(self, '_progress_dialog') and self._progress_dialog:
                    self._progress_dialog.close()
                    self._progress_dialog = None
            except Exception:
                pass
            self._reset_run_state()
            try:
                self.close()
            except Exception:
                pass

    def _on_batch_failed(self, err: str):
        try:
            QMessageBox.warning(self, '批量标注失败', err)
        finally:
            try:
                if hasattr(self, '_progress_dialog') and self._progress_dialog:
                    self._progress_dialog.close()
                    self._progress_dialog = None
            except Exception:
                pass
            self._reset_run_state()

    def _on_progress_cancel(self):
        """进度对话框点击取消后立即终止推理线程并清理。"""
        try:
            # 请求工作者取消（优雅退出）
            try:
                if self._inference_worker and hasattr(self._inference_worker, 'cancel'):
                    self._inference_worker.cancel()
            except Exception:
                pass
            # 请求中断并强制终止线程（立即停止）
            try:
                if self._inference_thread:
                    try:
                        self._inference_thread.requestInterruption()
                    except Exception:
                        pass
                    self._inference_thread.terminate()
            except Exception:
                pass
            try:
                QMessageBox.information(self, '提示', '已终止推理。')
            except Exception:
                pass
        finally:
            try:
                if hasattr(self, '_progress_dialog') and self._progress_dialog:
                    self._progress_dialog.close()
                    self._progress_dialog = None
            except Exception:
                pass
            # 清理线程对象并恢复界面状态
            self._cleanup_thread()
            self._reset_run_state()
            try:
                self.show()
            except Exception:
                pass


def open_vision_prompt_window(main_window) -> VisionPromptWindow | None:
    mode = 'rectangle'
    win = VisionPromptWindow(mode=mode, parent=main_window)
    # 自动载入主画布当前图片
    try:
        current_pixmap = getattr(getattr(main_window, 'canvas', None), 'current_pixmap', None)
        if current_pixmap and not current_pixmap.isNull():
            # 复制以避免共享引用导致的潜在问题
            win.canvas.load_image_pixmap(current_pixmap.copy())
            # 若主窗口记录了当前图片路径，则同步到画布
            try:
                if hasattr(main_window, 'current_image_path'):
                    win.canvas.current_image_path = getattr(main_window, 'current_image_path', None)
            except Exception:
                pass
        else:
            image_path = None
            if hasattr(main_window, 'get_current_image_info'):
                image_path = main_window.get_current_image_info()
            elif hasattr(main_window, 'current_image_path'):
                image_path = getattr(main_window, 'current_image_path', None)
            if image_path:
                win.canvas.load_image_path(image_path)
    except Exception:
        pass
    win.show()
    return win


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    vpw = VisionPromptWindow(mode='rectangle')
    vpw.show()
    sys.exit(app.exec())
