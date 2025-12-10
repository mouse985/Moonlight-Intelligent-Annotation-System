from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from app_ui.set import get_settings_manager
from inference.inference_batch_moon import batch_yoloe_inference, batch_yolov_inference


class BatchRectPenWorker(QObject):
    """
    在同一后台线程中顺序执行批量推理与标签创建/绘制的工作者。

    处理策略：
    - 先运行第一阶段（yolov_one）。若权重遍历后仍无结果，则发出 failed 并终止。
    - 若提供 resource_list，则按序对每张图片运行第二阶段（yolov_two）并使用第一阶段类别筛选，
    每张图片在推理得到 bbox 后立即发出 request_draw 让主线程创建标签并绘制；
    若某张图片无任何匹配/推理结果，则直接跳过该图片并继续下一张；
    仅在收到主线程 ack_draw(ok=True) 后继续下一张；否则终止。
    - 若不提供 resource_list，则在当前 image_path 上运行完整管线（yolov_inference），
    若无任何有效结果则跳过，不进行绘制；否则绘制并等待 ack，然后完成。
    """

    # 向主线程请求绘制：传递图片路径与 bbox 列表
    request_draw = pyqtSignal(str, list)
    # 进度/状态提示
    progress = pyqtSignal(str)
    # 每完成一张图片的标注，发出一次数值进度（current, total）
    progress_step = pyqtSignal(int, int)
    # 全部完成
    finished = pyqtSignal(dict)
    # 失败（包含错误信息）
    failed = pyqtSignal(str)

    def __init__(self, image_path: str, bboxes: List[List[float]], resource_list: Optional[List[str]] = None, use_yoloe: Optional[bool] = None):
        super().__init__()
        self.image_path = image_path
        self.bboxes = bboxes or []
        self.resource_list = list(resource_list) if resource_list else []
        # 是否使用YOLOE批量管线：默认遵循设置中的“跳过YOLOV”开关
        try:
            if use_yoloe is None:
                settings_manager = get_settings_manager()
                self.use_yoloe = bool(settings_manager.is_skip_yolov_enabled())
            else:
                self.use_yoloe = bool(use_yoloe)
        except Exception:
            self.use_yoloe = False

        # 主线程回执结果（由主线程调用 ack_draw 设定）
        self._last_draw_ok: bool = False
        self._ack_received: bool = False
        self._ack_count: int = 0
        self._total_images: int = 0
        # 取消标记
        self._cancelled: bool = False

    def run(self):
        try:
            # 基本校验：必须有提示框
            if not isinstance(self.bboxes, list) or len(self.bboxes) == 0:
                self.failed.emit('未提供有效的矩形框提示')
                return

            # YOLOE 管线：参考图+提示，逐图推理并立即绘制（不等待整批完成）
            if self.use_yoloe:
                res_list = self.resource_list if self.resource_list else [self.image_path]
                total = len(res_list)
                self._total_images = total
                self._ack_count = 0

                draw_request_count = 0
                for idx, res_path in enumerate(res_list, start=1):
                    if self._cancelled:
                        self.progress_step.emit(idx, total)
                        self.failed.emit('用户取消')
                        return

                    # 逐图调用统一 YOLOE 批量接口，但仅传入当前图片，实现边推理边绘制
                    result = batch_yoloe_inference(
                        refer_image_path=self.image_path,
                        bboxes_prompts=self.bboxes,
                        resource_list=[res_path],
                        cls_ids=None,
                    )
                    items = result.get('results_map', {}).get(res_path, [])
                    bbox_list = [it['bbox'] for it in items if isinstance(it, dict) and 'bbox' in it]

                    if not bbox_list:
                        self.progress.emit(f'已处理 {idx}/{total}，跳过：{res_path}（YOLOE无匹配结果）')
                        self.progress_step.emit(idx, total)
                        continue

                    draw_request_count += 1
                    self.request_draw.emit(res_path, bbox_list)
                    self.progress.emit(f'YOLOE推理完成 {idx}/{total}，已发送绘制请求')
                    self.progress_step.emit(idx, total)

                # 限时等待回执以汇总结果（不阻塞单张继续推理）
                if draw_request_count > 0:
                    import time
                    timeout_s = 15.0
                    interval = 0.05
                    waited = 0.0
                    while waited < timeout_s and self._ack_count < draw_request_count and not self._cancelled:
                        time.sleep(interval)
                        waited += interval

                if self._cancelled:
                    self.failed.emit('用户取消')
                    return

                self.finished.emit({
                    'success': True,
                    'processed': int(self._ack_count),
                    'total': total
                })
                return

            # YOLOV 管线：整批先做一次判定，统一使用 YOLOV 或 YOLOE；逐图推理后立即绘制
            if self.resource_list:
                res_list = self.resource_list
                total = len(res_list)
                self._total_images = total
                self._ack_count = 0

                # 先用参考图做一次 YOLOV 一阶段判定：成功则整批用 YOLOV，否则整批用 YOLOE
                decision = batch_yolov_inference(
                    image_path=self.image_path,
                    bboxes_prompts={
                        'bboxes': self.bboxes,
                        'resource_list': [self.image_path],  # 仅用参考图做一次综合判定
                    }
                )
                use_yoloe_batch = decision.get('fallback') == 'yoloe'
                if use_yoloe_batch:
                    self.progress.emit('YOLOV一阶段失败，整批改用YOLOE推理')
                else:
                    self.progress.emit('YOLOV一阶段成功，整批使用YOLOV推理')

                draw_request_count = 0
                for idx, res_path in enumerate(res_list, start=1):
                    if self._cancelled:
                        self.progress_step.emit(idx, total)
                        self.failed.emit('用户取消')
                        return

                    if use_yoloe_batch:
                        # 整批走 YOLOE：逐图调用 YOLOE 并绘制
                        result = batch_yoloe_inference(
                            refer_image_path=self.image_path,
                            bboxes_prompts=self.bboxes,
                            resource_list=[res_path],
                            cls_ids=None,
                        )
                        items = result.get('results_map', {}).get(res_path, [])
                    else:
                        # 整批走 YOLOV：逐图调用 YOLOV 并绘制
                        result = batch_yolov_inference(
                            image_path=self.image_path,
                            bboxes_prompts={
                                'bboxes': self.bboxes,
                                'resource_list': [res_path],
                            }
                        )
                        items_map: Dict[str, List[Dict[str, Any]]] = result.get('filtered', {})
                        items = items_map.get(res_path, [])

                    bbox_list = [it['bbox'] for it in items if isinstance(it, dict) and 'bbox' in it]
                    if not bbox_list:
                        self.progress.emit(f'已处理 {idx}/{total}，跳过：{res_path}（无匹配结果）')
                        self.progress_step.emit(idx, total)
                        continue

                    draw_request_count += 1
                    self.request_draw.emit(res_path, bbox_list)
                    self.progress.emit(f'{"YOLOE" if use_yoloe_batch else "YOLOV"}推理完成 {idx}/{total}，已发送绘制请求')
                    self.progress_step.emit(idx, total)

                # 限时等待回执以汇总结果（不阻塞单张继续推理）
                if draw_request_count > 0:
                    import time
                    timeout_s = 15.0
                    interval = 0.05
                    waited = 0.0
                    while waited < timeout_s and self._ack_count < draw_request_count and not self._cancelled:
                        time.sleep(interval)
                        waited += interval

                if self._cancelled:
                    self.failed.emit('用户取消')
                    return

                self.finished.emit({
                    'success': True,
                    'processed': int(self._ack_count),
                    'total': total
                })
                return

            # 未提供资源列表：单图模式，推理后立即绘制并限时等待回执
            if self._cancelled:
                self.progress_step.emit(1, 1)
                self.failed.emit('用户取消')
                return

            result = batch_yolov_inference(
                image_path=self.image_path,
                bboxes_prompts=self.bboxes,
            )
            bbox_list = result.get('bbox_list', [])
            ok = bool(result.get('success'))
            if not ok or not bbox_list:
                self.progress.emit('当前图片无有效结果，已跳过')
                self.progress_step.emit(1, 1)
                self.finished.emit({
                    'success': True,
                    'processed': 0,
                    'total': 1
                })
                return

            draw_request_count = 1
            self.request_draw.emit(self.image_path, bbox_list)

            # 限时等待一次回执
            import time
            timeout_s = 15.0
            interval = 0.05
            waited = 0.0
            while waited < timeout_s and self._ack_count < draw_request_count and not self._cancelled:
                time.sleep(interval)
                waited += interval

            processed = 1 if self._ack_count >= 1 else 0
            self.progress_step.emit(1, 1)
            self.finished.emit({
                'success': bool(processed == 1),
                'processed': processed,
                'total': 1
            })

        except Exception as e:
            self.failed.emit(f'批量顺序标注发生异常：{e}')

    def ack_draw(self, ok: bool):
        """由主线程在完成绘制/标签创建后调用，通知工作线程是否成功。"""
        self._last_draw_ok = bool(ok)
        self._ack_received = True
        # 成功绘制则计数
        if ok:
            try:
                self._ack_count += 1
            except Exception:
                pass

    def cancel(self):
        """被主线程调用以请求取消当前运行。"""
        self._cancelled = True

    def _wait_for_ack(self) -> bool:
        """
        简化版等待机制：通过事件轮询等待主线程设置 _last_draw_ok。
        由于 Qt 信号是排队的，这里使用短暂循环等待信号回执，避免阻塞 UI。
        """
        # 轮询等候回执（最多等待约15秒，以适应大图或复杂场景）
        import time
        timeout_s = 15.0
        interval = 0.02
        waited = 0.0
        # 重置状态
        self._last_draw_ok = False
        self._ack_received = False
        while waited < timeout_s:
            # 若收到取消请求则立即返回失败
            if self._cancelled:
                return False
            # 若主线程已回执（True/False）则直接返回对应结果
            if self._ack_received:
                return bool(self._last_draw_ok)
            time.sleep(interval)
            waited += interval
        return False
