from astrbot.api.all import *
import subprocess

# 修改为你刚才创建的脚本的绝对路径
SCRIPT_PATH = r"E:\BOT\MyBotScripts\do_pack.py"

@register("Win打包助手", "YourName", "1.0.0", "Windows本地打包工具")
class WinPackerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @command("/打包游戏")
    async def pack_game_cmd(self, event: AstrMessageEvent):
        """发送 '/打包游戏' 触发"""
        
        yield event.plain_result("收到指令！正在后台启动打包脚本，请留意飞书通知...")

        # 使用 subprocess 在后台运行，不会卡住 AstrBot
        # shell=True 允许弹出黑窗口(调试用)，正式用可以去掉
        try:
            subprocess.Popen(["python", SCRIPT_PATH], shell=True)
        except Exception as e:
            yield event.plain_result(f"❌ 启动脚本失败: {e}")
