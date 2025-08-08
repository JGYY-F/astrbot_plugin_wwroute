from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
from astrbot.api.event import filter, AstrMessageEvent
import os
import re
import aiohttp
import json
from typing import List

@register("astrbot_plugin_custom_menu", "Futureppo", "自定义图片菜单。更新前记得备份你的图片！！！", "1.0.0")
class custommenu(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.menu_dir = os.path.join(self.base_dir, "menu")

    @filter.command("菜单", alias=['帮助', '功能', '你怎么用'])
    async def list_images(self, event: AstrMessageEvent):
        # 检查并创建菜单文件夹
        if not os.path.exists(self.menu_dir) or not os.path.isdir(self.menu_dir):
            try:
                os.makedirs(self.menu_dir, exist_ok=True)
                logger.info(f"menu文件夹已成功创建: {self.menu_dir}")
            except Exception as e:
                logger.error(f"无法创建menu文件夹: {self.menu_dir}, 错误信息: {e}")
                return

        # 获取所有图片文件名
        image_files = [
            f for f in os.listdir(self.menu_dir)
            if os.path.isfile(os.path.join(self.menu_dir, f)) and 
            os.path.splitext(f)[1].lower() in self.image_extensions
        ]

        if not image_files:
            yield event.plain_result("menu文件夹中没有找到任何图片")
            return

        # 生成文件名列表
        file_list = "可用的图片列表：\n" + "\n".join([
            os.path.splitext(f)[0] for f in image_files
        ])
        yield event.plain_result(file_list)

    @filter.command("")  # 匹配所有消息
    async def send_image(self, event: AstrMessageEvent):
        msg = event.message.extract_plain_text().strip()
        
        # 如果消息为空，直接返回
        if not msg:
            return
        
        # 检查文件夹是否存在
        if not os.path.exists(self.menu_dir) or not os.path.isdir(self.menu_dir):
            yield event.plain_result("menu文件夹不存在")
            return
        
        # 标记是否找到图片
        found = False
        
        # 遍历所有支持的图片扩展名
        for ext in self.image_extensions:
            image_path = os.path.join(self.menu_dir, f"{msg}{ext}")
            if os.path.exists(image_path):
                try:
                    image = Image.fromFileSystem(image_path)
                    yield event.chain_result([image])
                    found = True
                    break  # 找到图片后立即退出循环
                except Exception as e:
                    logger.error(f"加载图片失败: {image_path}, 错误信息: {e}")
                    yield event.plain_result(f"加载图片失败: {str(e)}")
                    return
        
        # 如果没有找到对应的图片，给出提示
        if not found:
            yield event.plain_result(f"未找到名为 '{msg}' 的图片")
