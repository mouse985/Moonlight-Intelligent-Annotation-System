import random
import colorsys
from typing import Tuple, List, Set


class ColorMoon:
    """定义各种鲜艳的颜色和随机选择颜色的方法"""
    
    # 类变量，跟踪已使用的颜色
    _used_colors: Set[Tuple[int, int, int]] = set()
    
    @classmethod
    def _generate_vibrant_color(cls) -> Tuple[int, int, int]:
        """生成一个鲜艳的随机颜色
        
        Returns:
            Tuple[int, int, int]: RGB格式的颜色元组
        """
        # 使用HSV颜色空间生成鲜艳的颜色
        # 随机色相 (0-1)
        h = random.random()
        # 高饱和度 (0.7-1.0) 确保颜色鲜艳
        s = random.uniform(0.7, 1.0)
        # 高亮度 (0.7-1.0) 确保颜色明亮
        v = random.uniform(0.7, 1.0)
        
        # 将HSV转换为RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        
        # 转换为0-255范围的整数
        return (int(r * 255), int(g * 255), int(b * 255))
    
    @classmethod
    def get_random_color(cls) -> Tuple[int, int, int]:
        """随机选择一个鲜艳的颜色，确保不重复
        
        Returns:
            Tuple[int, int, int]: RGB格式的颜色元组
        """
        # 尝试最多10次生成一个未使用的颜色
        for _ in range(10):
            color = cls._generate_vibrant_color()
            if color not in cls._used_colors:
                cls._used_colors.add(color)
                return color
        
        # 如果10次后仍未找到未使用的颜色，重置已使用颜色集合
        cls._used_colors.clear()
        color = cls._generate_vibrant_color()
        cls._used_colors.add(color)
        return color
    
    @classmethod
    def get_random_colors(cls, count: int) -> List[Tuple[int, int, int]]:
        """随机选择多个鲜艳的颜色，确保不重复
        
        Args:
            count: 需要选择的颜色数量
            
        Returns:
            List[Tuple[int, int, int]]: RGB格式的颜色元组列表
        """
        colors = []
        
        # 生成指定数量的不重复颜色
        for _ in range(count):
            # 尝试最多10次生成一个未使用的颜色
            for attempt in range(10):
                color = cls._generate_vibrant_color()
                if color not in colors and color not in cls._used_colors:
                    colors.append(color)
                    cls._used_colors.add(color)
                    break
                elif attempt == 9:  # 最后一次尝试
                    # 如果无法找到未使用的颜色，重置已使用颜色集合
                    cls._used_colors.clear()
                    color = cls._generate_vibrant_color()
                    colors.append(color)
                    cls._used_colors.add(color)
        
        return colors
    
    @classmethod
    def get_color_name(cls, color: Tuple[int, int, int]) -> str:
        """获取颜色的名称
        
        Args:
            color: RGB格式的颜色元组
            
        Returns:
            str: 颜色的名称
        """
        r, g, b = color
        
        # 将RGB转换为HSV以便更好地判断颜色类型
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        
        # 根据色相值判断颜色类型
        if s < 0.2:  # 低饱和度，可能是灰色
            if v < 0.3:
                return "黑色"
            elif v > 0.7:
                return "白色"
            else:
                return "灰色"
        
        # 根据色相值判断颜色类型
        h_degrees = h * 360
        if h_degrees < 30 or h_degrees >= 330:
            return "红色"
        elif h_degrees < 60:
            return "橙色"
        elif h_degrees < 90:
            return "黄色"
        elif h_degrees < 150:
            return "绿色"
        elif h_degrees < 210:
            return "青色"
        elif h_degrees < 270:
            return "蓝色"
        else:
            return "紫色"
    
    @classmethod
    def add_custom_color(cls, color: Tuple[int, int, int], name: str) -> None:
        """添加自定义颜色
        
        Args:
            color: RGB格式的颜色元组
            name: 颜色的名称
        """
        cls._used_colors.add(color)
    
    @classmethod
    def reset_used_colors(cls) -> None:
        """重置已使用颜色集合，允许所有颜色重新被选择"""
        cls._used_colors.clear()
    
    @classmethod
    def release_color(cls, color: Tuple[int, int, int]) -> None:
        """释放一个已使用的颜色，使其可以重新被选择
        
        Args:
            color: 要释放的RGB格式颜色元组
        """
        cls._used_colors.discard(color)
    
    @classmethod
    def get_available_colors_count(cls) -> int:
        """获取当前可用的颜色数量
        
        Returns:
            int: 可用颜色的数量
        """
        # 由于我们现在使用随机生成，理论上可以生成无限种颜色
        # 返回一个较大的数字表示有足够的颜色可用
        return 1000


# 使用示例
if __name__ == "__main__":
    # 获取一个随机颜色
    random_color = ColorMoon.get_random_color()
    print(f"随机颜色: {random_color}, 名称: {ColorMoon.get_color_name(random_color)}")
    
    # 获取多个随机颜色
    random_colors = ColorMoon.get_random_colors(5)
    print("多个随机颜色:")
    for color in random_colors:
        print(f"  {color}, 名称: {ColorMoon.get_color_name(color)}")
    
    # 添加自定义颜色
    ColorMoon.add_custom_color((100, 200, 50), "自定义绿")
    custom_color = (100, 200, 50)
    print(f"自定义颜色: {custom_color}, 名称: {ColorMoon.get_color_name(custom_color)}")
