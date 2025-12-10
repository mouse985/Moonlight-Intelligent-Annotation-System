import logging
import gc

try:
    import torch
except Exception:
    torch = None

logger = logging.getLogger(__name__)


def free_torch_memory():
    """释放由推理过程产生的显存与内存（不影响模型对象）。

    - 优先释放 CUDA/MPS 的缓存显存（若可用）。
    - 触发 Python GC 以回收无引用对象的内存。
    - 整体设计为安全、快速，不依赖具体推理对象引用。
    """
    try:
        # 释放 GPU 显存缓存（CUDA）
        if torch is not None and hasattr(torch, 'cuda') and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            # 兼容可能存在的进程间缓存收集
            try:
                if hasattr(torch.cuda, 'ipc_collect'):
                    torch.cuda.ipc_collect()
            except Exception:
                pass
            # 重置峰值统计（可选，便于后续监控）
            try:
                torch.cuda.reset_peak_memory_stats()
            except Exception:
                pass

        # 释放 GPU 显存缓存（Apple MPS）
        if torch is not None and hasattr(torch, 'mps') and hasattr(torch.mps, 'empty_cache'):
            try:
                torch.mps.empty_cache()
            except Exception:
                pass

        # 触发 Python 垃圾回收（CPU 内存）
        try:
            gc.collect()
        except Exception:
            pass
    except Exception as e:
        # 使用 debug 级别，避免影响正常日志级别
        try:
            logger.debug(f"free_torch_memory encountered error: {e}")
        except Exception:
            pass


def cleansampoint(mask_sam_manager):
    """
    清理SAM推理的输入点
    
    Args:
        mask_sam_manager: MASK模式SAM推理管理器实例
    """
    try:
        if mask_sam_manager:
            # 清理所有输入点
            mask_sam_manager.clear_points()
            logger.info("已清理SAM推理输入点")
        else:
            logger.warning("MASK模式SAM推理管理器实例为空，无法清理输入点")
    except Exception as e:
        logger.error(f"清理SAM推理输入点时发生错误: {e}")
