from astrbot.api.all import *
import subprocess
import sys  # 引入 sys 模块，用来获取当前 Python 路径

# 脚本绝对路径 (确保这个文件真实存在)
SCRIPT_PATH = r"E:\BOT\MyBotScripts\do_pack.py"

@register("Win打包助手", "YourName", "1.0.0", "Windows本地打包工具")
class WinPackerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    # 【修正1】去掉斜杠，只写中文指令名
    @command("打包游戏")
    async def pack_game_cmd(self, event: AstrMessageEvent):
        """发送 '/打包游戏' 触发"""
        
        yield event.plain_result("收到指令！🚀 正在后台启动打包脚本，请留意飞书通知...")

        try:
            # 【修正2】使用 sys.executable 确保使用正确的 Python 环境
            # 使用列表传参，shell=True 在 Windows 上允许弹出/后台运行
            cmd = [sys.executable, SCRIPT_PATH]
            
            # Popen 是异步启动，不会卡住 AstrBot
            subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            
        except Exception as e:
            yield event.plain_result(f"❌ 启动脚本失败: {e}")
