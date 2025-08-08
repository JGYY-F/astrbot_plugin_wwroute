from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
import os
import re
from typing import List

@register("astrbot_plugin_ww_route_menu", "Futureppo", "ww路线图片菜单插件", "1.0.1")
class WWRouteMenu(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.menu_dir = os.path.join(self.base_dir, "menu")
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        
        # 初始化时检查并创建菜单文件夹
        self._ensure_menu_directory()

    def _ensure_menu_directory(self):
        """确保menu文件夹存在"""
        if not os.path.exists(self.menu_dir):
            try:
                os.makedirs(self.menu_dir, exist_ok=True)
                logger.info(f"menu文件夹已创建: {self.menu_dir}")
            except Exception as e:
                logger.error(f"无法创建menu文件夹: {self.menu_dir}, 错误: {e}")

    def _get_image_files(self) -> List[tuple]:
        """获取menu文件夹中的所有图片文件
        
        Returns:
            List[tuple]: 包含(文件名, 完整路径)的元组列表
        """
        if not os.path.exists(self.menu_dir):
            return []
            
        image_files = []
        try:
            for filename in os.listdir(self.menu_dir):
                file_path = os.path.join(self.menu_dir, filename)
                if (os.path.isfile(file_path) and 
                    os.path.splitext(filename)[1].lower() in self.image_extensions):
                    # 移除扩展名作为显示名称
                    display_name = os.path.splitext(filename)[0]
                    image_files.append((display_name, file_path, filename))
            
            # 按文件名排序
            image_files.sort(key=lambda x: x[0])
            return image_files
        except Exception as e:
            logger.error(f"读取menu文件夹出错: {e}")
            return []

    def _find_image_by_name(self, name: str) -> str:
        """根据名称查找图片文件
        
        Args:
            name: 图片名称（不含扩展名）
            
        Returns:
            str: 图片完整路径，如果找不到返回空字符串
        """
        image_files = self._get_image_files()
        
        # 精确匹配
        for display_name, file_path, filename in image_files:
            if display_name.lower() == name.lower():
                return file_path
        
        # 模糊匹配（包含关系）
        for display_name, file_path, filename in image_files:
            if name.lower() in display_name.lower() or display_name.lower() in name.lower():
                return file_path
                
        return ""

    @filter.command("ww路线", alias=['路线菜单', '路线图', '路线帮助'])
    async def show_route_menu(self, event: AstrMessageEvent):
        """显示所有可用的路线图片名称"""
        image_files = self._get_image_files()
        
        if not image_files:
            yield event.plain_result(
                "❌ menu文件夹中没有找到任何图片文件！\n"
                f"请将路线图片放入以下目录：\n{self.menu_dir}\n"
                "支持的图片格式：jpg, jpeg, png, gif, bmp, webp"
            )
            return

        # 构建图片列表消息
        menu_text = "可用的ww路线图片：\n\n"
        
        for i, (display_name, _, _) in enumerate(image_files, 1):
            menu_text += f"{i:2d}. {display_name}\n"
        
        menu_text += f"使用方法：直接发送图片名称即可获取对应路线图"
        menu_text += f"共找到 {len(image_files)} 张路线图片"
        
        yield event.plain_result(menu_text)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_image_request(self, event: AstrMessageEvent):
        """处理图片名称请求"""
        message_text = event.message_str.strip()
        
        # 忽略空消息和指令
        if not message_text or message_text.startswith('/'):
            return
            
        # 忽略太长的消息（避免误触发）
        if len(message_text) > 50:
            return
            
        # 尝试查找对应的图片
        image_path = self._find_image_by_name(message_text)
        
        if image_path and os.path.exists(image_path):
            try:
                # 获取图片信息
                image_files = self._get_image_files()
                matched_info = next((info for info in image_files if info[1] == image_path), None)
                
                if matched_info:
                    display_name, _, original_filename = matched_info
                    
                    # 构建回复消息
                    chain = [
                        Plain(f"路线图：{display_name}\n"),
                        Image.fromFileSystem(image_path)
                    ]
                    
                    yield event.chain_result(chain)
                    logger.info(f"发送路线图片：{display_name} -> {original_filename}")
                    
                    # 停止事件传播，避免其他插件处理
                    event.stop_event()
                    
            except Exception as e:
                logger.error(f"发送图片失败: {image_path}, 错误: {e}")
                yield event.plain_result(f"❌ 发送图片失败：{message_text}")

    @filter.command("清理路线缓存")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def clear_cache(self, event: AstrMessageEvent):
        """清理路线图片缓存（管理员专用）"""
        try:
            # 重新扫描文件夹
            image_files = self._get_image_files()
            yield event.plain_result(f"✅ 缓存已清理，重新扫描到 {len(image_files)} 张图片")
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            yield event.plain_result("❌ 清理缓存失败")

    @filter.command("路线统计")
    async def route_statistics(self, event: AstrMessageEvent):
        """显示路线图片统计信息"""
        image_files = self._get_image_files()
        
        if not image_files:
            yield event.plain_result("暂无路线图片数据")
            return
            
        # 按扩展名统计
        ext_count = {}
        total_size = 0
        
        for _, file_path, filename in image_files:
            ext = os.path.splitext(filename)[1].lower()
            ext_count[ext] = ext_count.get(ext, 0) + 1
            
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
            except:
                pass
        
        # 构建统计信息
        stats_text = "ww路线图片统计："
        stats_text += f"总数量：{len(image_files)} 张\n"
        stats_text += f"总大小：{total_size / 1024 / 1024:.2f} MB\n\n"
        
        stats_text += "格式分布："
        for ext, count in sorted(ext_count.items()):
            stats_text += f"  {ext}: {count} 张\n"
            
        stats_text += f"存储位置：{self.menu_dir}"
        
        yield event.plain_result(stats_text)

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("ww路线菜单插件已卸载")
