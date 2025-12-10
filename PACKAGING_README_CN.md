# Moonlight 桌面版使用说明（Windows）

## 构建（开发者）
- 安装依赖：根据 `requirements.txt` 安装，并包含 `ultralytics`。
- 使用 `moonlight.spec` 构建：在本仓库根目录执行 PyInstaller 构建，输出到 `dist/Moonlight/`。

### 64 位构建要求
- 必须使用 64 位 Python 解释器与 64 位依赖（Windows 默认 Anaconda 为 64 位）。
- PyInstaller 不支持跨架构打包，64 位输出取决于构建环境的位数。
- 构建完成后，`dist/Moonlight/` 下的 `Moonlight.exe` 即为 64 位程序。

## 分发
- 将 `dist/Moonlight/` 文件夹压缩为 `Moonlight.zip` 提供给用户。
- 文件夹内包含：`Moonlight.exe`、`acc/`、`models/weights/` 与运行所需的库。

## 使用（用户）
- 解压 `Moonlight.zip`。
- 双击 `Moonlight.exe` 启动。
- 首次启动会扫描并加载模型；若无显卡将自动使用 CPU。

### 64 位验证（无需命令行）
- 打开任务管理器，找到 `Moonlight.exe`，在“详细信息”列确认为 64 位进程（常见标识为不带 *32）。

## 常见问题
- 杀毒误报：如报毒，添加白名单后重试。
- 模型加载错误：确保 `models/weights/` 下存在最小权重（如 `SAMmodels/SAM2/mobile_sam.pt`、`rect/yolo11n.pt`、`yoloemodels/yoloe-11l-seg.pt`）。
- 资源不显示：确认 `acc` 目录随分发包一同存在。
