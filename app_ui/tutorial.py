from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QStackedWidget
from PyQt6.QtCore import Qt, QSettings

class TutorialGuide(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新手教程")
        try:
            self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        except Exception:
            pass
        self.setMinimumSize(520, 320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.pages = []
        def _page(title, lines):
            p = QFrame()
            v = QVBoxLayout(p)
            v.setContentsMargins(6, 6, 6, 6)
            v.setSpacing(6)
            t = QLabel(title)
            t.setAlignment(Qt.AlignmentFlag.AlignLeft)
            t.setStyleSheet("font-size:16px;font-weight:bold;")
            v.addWidget(t)
            for s in lines:
                lab = QLabel(s)
                lab.setWordWrap(True)
                lab.setStyleSheet("color:#555;font-size:13px;")
                v.addWidget(lab)
            v.addStretch()
            return p
        self.pages.append(_page("欢迎", [
            "欢迎使用 Moonlight智能标注工具。此教程将引导你完成基础操作。",
            "你可以随时点击‘跳过’，稍后通过界面入口再次查看。",
        ]))
        self.pages.append(_page("加载图片目录", [
            "在主界面使用‘打开图片目录’（快捷键取决于设置，例如默认为 Ctrl+K）。",
            "加载成功后，资源列表会显示图片条目。",
        ]))
        self.pages.append(_page("模式切换（左侧组件栏）", [
            "左侧组件栏提供模式切换：平移、矩形框、多边形、MASK、OBB、自由标注（按钮可勾选）。",
            "进入 MASK 或 OBB 模式后，底部栏会显示相关控件；RGB 与 SAM 切换仅在有图像且处于 MASK/OBB 时可见。",
            "默认矩形框模式开启，其余模式按需启用。",
        ]))
        self.pages.append(_page("底部栏：RGB 调节", [
            "在底部栏点击 RGB 按钮，打开颜色调节滑块来微调显示效果。",
            "需要已加载图像才会显示 RGB 控件。",
        ]))
        self.pages.append(_page("底部栏：SAM2/SAM3 切换", [
            "在 MASK 或 OBB 模式下，底部栏显示 SAM 模型切换控件。",
            "默认激活 SAM2；你也可以切换至 SAM3。两类模型相似但权重不同。",
        ]))
        self.pages.append(_page("标注教程：", [
            "1.打开图片目录加载图片",
            "2.创建新标签",
            "3.在图像上绘制标注",
            "4.导出数据集并指定路径",
        ]))
        self.pages.append(_page("结束", [
            "教程已完成。你可以在界面入口再次打开本教程。",
        ]))
        for p in self.pages:
            self.stack.addWidget(p)
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(8)
        btn_prev = QPushButton("上一页")
        btn_next = QPushButton("下一页")
        btn_skip = QPushButton("跳过")
        nav.addWidget(btn_prev)
        nav.addWidget(btn_next)
        nav.addStretch()
        nav.addWidget(btn_skip)
        layout.addLayout(nav)
        def _update():
            idx = self.stack.currentIndex()
            btn_prev.setEnabled(idx > 0)
            if idx >= len(self.pages) - 1:
                btn_next.setText("完成")
            else:
                btn_next.setText("下一页")
        def _prev():
            i = max(0, self.stack.currentIndex() - 1)
            self.stack.setCurrentIndex(i)
            _update()
        def _next():
            i = self.stack.currentIndex() + 1
            if i >= len(self.pages):
                self._mark_shown()
                self.accept()
                return
            self.stack.setCurrentIndex(i)
            _update()
        def _skip():
            self._mark_shown()
            self.reject()
        btn_prev.clicked.connect(_prev)
        btn_next.clicked.connect(_next)
        btn_skip.clicked.connect(_skip)
        _update()
    def _mark_shown(self):
        try:
            s = QSettings("MoonlightV2", "Settings")
            s.setValue("tutorial_shown", True)
        except Exception:
            pass
def show_tutorial(parent=None):
    dlg = TutorialGuide(parent)
    dlg.exec()

def show_tutorial_if_needed(parent=None):
    try:
        s = QSettings("MoonlightV2", "Settings")
        shown = s.value("tutorial_shown", False, type=bool)
    except Exception:
        shown = False
    if not shown:
        show_tutorial(parent)
