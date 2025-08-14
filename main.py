from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
import os
import re
import time
import asyncio
from typing import List, Optional, Tuple

@register("astrbot_plugin_ww_route_menu", "Futureppo", "ww路线图片菜单插件", "1.0.1")
class WWRouteMenu(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.menu_dir = os.path.join(self.base_dir, "menu")
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']

        # 只缓存图片名称到路径的映射（dict），减少内存占用
        self._image_cache: Optional[dict] = None
        self._cache_timestamp = 0
        self._cache_duration = 300  # 5分钟缓存

        # 定期自动清理缓存任务
        self._cache_cleaner_task = asyncio.create_task(self._periodic_cache_cleaner())

        # 初始化时检查并创建菜单文件夹
        self._ensure_menu_directory()

    async def _periodic_cache_cleaner(self):
        """定期清理缓存，释放内存（每30分钟清理一次）"""
        while True:
            await asyncio.sleep(1800)
            self._invalidate_cache()
            logger.debug("定时任务：图片缓存已自动清理")

    def _ensure_menu_directory(self):
        """确保menu文件夹存在"""
        if not os.path.exists(self.menu_dir):
            try:
                os.makedirs(self.menu_dir, exist_ok=True)
                logger.info(f"menu文件夹已创建: {self.menu_dir}")
            except Exception as e:
                logger.error(f"无法创建menu文件夹: {self.menu_dir}, 错误: {e}")

    def _get_image_files(self) -> dict:
        """获取menu文件夹中的所有图片文件，返回dict：{显示名称: 完整路径}"""
        if not os.path.exists(self.menu_dir):
            return {}

        image_dict = {}
        try:
            for filename in os.listdir(self.menu_dir):
                file_path = os.path.join(self.menu_dir, filename)
                if (os.path.isfile(file_path) and
                    os.path.splitext(filename)[1].lower() in self.image_extensions):
                    display_name = os.path.splitext(filename)[0]
                    image_dict[display_name] = file_path
            return image_dict
        except Exception as e:
            logger.error(f"读取menu文件夹出错: {e}")
            return {}

    def _get_image_files_cached(self) -> dict:
        """带缓存的图片文件获取，避免重复扫描"""
        current_time = time.time()
        if (self._image_cache is not None and
            current_time - self._cache_timestamp < self._cache_duration):
            return self._image_cache

        self._image_cache = self._get_image_files()
        self._cache_timestamp = current_time
        logger.debug(f"图片缓存已更新，共 {len(self._image_cache)} 张图片")
        return self._image_cache

    def _find_image_by_name(self, name: str) -> Optional[str]:
        """根据名称查找图片文件（使用缓存）"""
        image_dict = self._get_image_files_cached()
        return image_dict.get(name.strip(), None)

    def _invalidate_cache(self):
        """手动使缓存失效"""
        self._image_cache = None
        self._cache_timestamp = 0
        logger.debug("图片缓存已清除")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("ww路线")
    async def show_route_menu(self, event: AstrMessageEvent):
        """显示所有可用的路线图片名称（仅管理员可用）"""
        image_dict = self._get_image_files_cached()
        
        if not image_dict:
            yield event.plain_result(
                "❌ menu文件夹中没有找到任何图片文件！\n"
                f"请将路线图片放入以下目录：\n{self.menu_dir}\n"
                "支持的图片格式：jpg, jpeg, png, gif, bmp, webp"
            )
            return

        # 构建图片列表消息
        menu_text = "️ 可用的ww路线图片：\n\n"
        
        for i, display_name in enumerate(sorted(image_dict.keys()), 1):
            menu_text += f"{i:2d}. {display_name}\n"
        
        menu_text += f" 使用方法：直接发送图片名称即可获取对应路线图\n"
        menu_text += f" 共找到 {len(image_dict)} 张路线图片"
        
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
                # 构建回复消息
                chain = [
                    Plain(f"️ 路线图：{message_text}\n"),
                    Image.fromFileSystem(image_path)
                ]
                
                yield event.chain_result(chain)
                logger.info(f"发送路线图片：{message_text} -> {os.path.basename(image_path)}")
                
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
            # 清理缓存
            self._invalidate_cache()
            
            # 重新扫描文件夹
            image_dict = self._get_image_files_cached()
            yield event.plain_result(f"✅ 缓存已清理，重新扫描到 {len(image_dict)} 张图片")
            logger.info("路线图片缓存已清理并重新扫描")
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            yield event.plain_result("❌ 清理缓存失败")

    @filter.command("路线统计")
    async def route_statistics(self, event: AstrMessageEvent):
        """显示路线图片统计信息（优化版）"""
        image_dict = self._get_image_files_cached()
        
        if not image_dict:
            yield event.plain_result(" 暂无路线图片数据")
            return
        
        # 批量处理统计信息
        ext_count = {}
        total_size = 0
        valid_files = 0
        invalid_files = []
        
        # 延迟获取文件大小，只在统计时获取
        for display_name, file_path in image_dict.items():
            ext = os.path.splitext(file_path)[1].lower()
            ext_count[ext] = ext_count.get(ext, 0) + 1
            try:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    valid_files += 1
                else:
                    invalid_files.append(display_name)
            except OSError as e:
                logger.warning(f"无法获取文件大小: {file_path}, 错误: {e}")
                invalid_files.append(display_name)
        
        # 构建统计信息
        stats_text = " ww路线图片统计："
        stats_text += f" 总数量：{len(image_dict)} 张\n"
        
        if invalid_files:
            stats_text += f"✅ 有效文件：{valid_files} 张\n"
            stats_text += f"❌ 无效文件：{len(invalid_files)} 张\n"
        
        stats_text += f" 总大小：{total_size / 1024 / 1024:.2f} MB\n"
        
        if valid_files > 0:
            stats_text += f" 平均大小：{total_size / valid_files / 1024:.1f} KB\n"
        
        if ext_count:
            stats_text += "\n 格式分布："
            for ext, count in sorted(ext_count.items()):
                percentage = (count / len(image_dict)) * 100
                stats_text += f"  {ext}: {count} 张 ({percentage:.1f}%)\n"
        
        if invalid_files:
            stats_text += f"\n⚠️ 无效文件列表：\n"
            for invalid_file in invalid_files[:5]:  # 只显示前5个
                stats_text += f"  • {invalid_file}\n"
            if len(invalid_files) > 5:
                stats_text += f"  ... 还有 {len(invalid_files) - 5} 个文件\n"
        
        stats_text += f"\n存储位置：{self.menu_dir}"
        stats_text += f"\n⏰ 缓存状态：{'已缓存' if self._image_cache else '未缓存'}"
        
        if self._image_cache:
            cache_age = time.time() - self._cache_timestamp
            stats_text += f" ({cache_age:.0f}秒前更新)"
        
        yield event.plain_result(stats_text)

    @filter.command("强制刷新路线")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def force_refresh(self, event: AstrMessageEvent):
        """强制刷新路线图片缓存（管理员专用）"""
        try:
            old_count = len(self._image_cache) if self._image_cache else 0
            self._invalidate_cache()
            new_dict = self._get_image_files_cached()
            new_count = len(new_dict)
            
            if new_count != old_count:
                yield event.plain_result(
                    f"路线缓存已强制刷新\n"
                    f"图片数量：{old_count} → {new_count}\n"
                    f"{'发现新图片' if new_count > old_count else '部分图片已移除' if new_count < old_count else '数量无变化'}"
                )
            else:
                yield event.plain_result(f"路线缓存已强制刷新，图片数量未变化 ({new_count} 张)")
            
            logger.info(f"强制刷新路线缓存：{old_count} -> {new_count}")
        except Exception as e:
            logger.error(f"强制刷新失败: {e}")
            yield event.plain_result("❌ 强制刷新失败")

    async def terminate(self):
        """插件卸载时调用"""
        # 清理缓存，释放内存
        self._invalidate_cache()
        logger.info("ww路线菜单插件已卸载，缓存已清理")