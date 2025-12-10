# Moonlight Annotation Tool / Moonlight 标注工具

<p align="center">
  <img src="acc/logo.png" alt="Moonlight Logo" width="128" height="128">
</p>

<p align="center">
  <a href="#english">English</a> | <a href="#chinese">中文</a>
</p>

---

<div id="english"></div>

## 🌙 Overview

**Moonlight** is a powerful, intelligent image annotation tool designed for computer vision tasks. Built with PyQt6, it combines manual labeling capabilities with advanced AI assistance to significantly speed up the data annotation process. Whether you are working on object detection, segmentation, or remote sensing analysis, Moonlight provides a seamless and efficient workflow.

## ✨ Key Features

-   **🤖 AI-Assisted Annotation**: Integrated with **SAM (Segment Anything Model)** and **YOLO** for automatic object detection and segmentation.
-   **📐 Versatile Labeling Tools**: Support for multiple annotation types including:
    -   Rectangle (Bounding Box)
    -   Polygon
    -   Oriented Bounding Box (OBB)
    -   Mask / Brush
-   **🛰️ Remote Sensing Mode**: Specialized mode optimized for handling large-scale remote sensing imagery.
-   **⚡ Batch Processing**: Capabilities for batch annotation to handle large datasets efficiently.
-   **🔍 Image Enhancement**: Built-in super-resolution tools to upscale images (up to 10x) for better detail visibility.
-   **🎯 Focus Mode**: "Solo Mode" to hide UI distractions and focus purely on the canvas.
-   **💾 Dataset Export**: Easy export functionality to standard dataset formats.
-   **⌨️ Customizable Workflow**: Support for keyboard shortcuts and intuitive mouse interactions.

## 🛠️ Installation

### Prerequisites

-   Python 3.12
-   CUDA-enabled GPU (recommended for AI features)

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/moonlight.git
    cd moonlight
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment (conda or venv).
    ```bash
    pip install PyQt6
    pip install ultralytics
    pip install sam3
    ```

## 🚀 Usage

1.  **Start the application:**
    ```bash
    python moonlight.py
    ```

2.  **Basic Workflow:**
    -   Click **"Load Image Directory"** (folder icon) to import your dataset.
    -   Select an annotation tool from the component bar (Rect, Polygon, etc.).
    -   Toggle **"AI"** button to enable auto-annotation features.
    -   Use the **Control Panel** to manage labels and classes.
    -   Export your work via the **"Export Dataset"** button.

## 📝 License

[License Name] - See the [LICENSE](LICENSE) file for details.

---

<div id="chinese"></div>

## 🌙 简介

**Moonlight** 是一款专为计算机视觉任务设计的强大智能图像标注工具。基于 PyQt6 开发，它完美结合了手动标注与先进的 AI 辅助功能，旨在显著提升数据标注效率。无论您是进行目标检测、语义分割，还是遥感图像分析，Moonlight 都能为您提供流畅高效的工作流。

## ✨ 主要功能

-   **🤖 AI 智能辅助**: 集成 **SAM (Segment Anything Model)** 和 **YOLO** 模型，支持自动目标检测和分割，大幅减少人工操作。
-   **📐 多样化标注工具**: 支持多种标注形式，满足不同需求：
    -   矩形框 (Rectangle/BBox)
    -   多边形 (Polygon)
    -   旋转矩形框 (OBB)
    -   掩码/画笔 (Mask/Brush)
-   **🛰️ 遥感模式**: 专为处理大尺寸遥感影像优化的标注模式。
-   **⚡ 批量处理**: 支持批量标注功能，高效处理大规模数据集。
-   **🔍 图像增强**: 内置超分辨率工具，支持图像放大（最高10倍），提升细节清晰度。
-   **🎯 专注模式**: 提供 "Solo 模式" (Solo Mode)，一键隐藏无关 UI 元素，让您专注于画布内容。
-   **💾 数据集导出**: 便捷的数据集导出功能，支持主流数据格式。
-   **⌨️ 高效交互**: 支持丰富的键盘快捷键和直观的鼠标操作。

## 🛠️ 安装说明

### 环境要求

-   Python 3.12
-   支持 CUDA 的 GPU (推荐用于 AI 加速)

### 安装步骤

1.  **克隆项目:**
    ```bash
    git clone https://github.com/yourusername/moonlight.git
    cd moonlight
    ```

2.  **安装依赖:**
    建议使用虚拟环境 (conda 或 venv) 进行安装。
    ```bash
    pip install PyQt6
    pip install ultralytics
    pip install sam3
    ```

## 🚀 使用指南

1.  **启动程序:**
    ```bash
    python moonlight.py
    ```

2.  **基本流程:**
    -   点击 **"加载图片目录"** (文件夹图标) 导入您的图片数据。
    -   在组件栏选择合适的标注工具 (矩形、多边形等)。
    -   点击 **"AI"** 按钮开启智能辅助标注功能。
    -   使用 **控制面板** 管理标签类别和对象。
    -   完成标注后，点击 **"导出数据集"** 保存工作成果。

## 📝 开源协议

[License Name] - 查看 [LICENSE](LICENSE) 文件了解更多详情。
