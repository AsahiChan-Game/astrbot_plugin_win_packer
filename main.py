from astrbot.api.all import *
import subprocess
import os
import asyncio

@register_plugin("UnrealBuilder")
class UnrealBuilder(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 【重要】请修改这里的路径为你 bat 脚本所在的实际文件夹路径
        # 注意：在 Python 字符串中，反斜杠需要写两次 \\ 或者使用 r"路径"
        self.BAT_DIR = r"C:\WorkSpace\main\Lycoris_main\bat" 

    # ----------------------------------------------------------------
    # 命令 1: 简单打包 (对应 packsimple.bat)
    # 触发指令: /build_simple
    # ----------------------------------------------------------------
    @filter.command("build_simple")
    async def build_simple(self, event: AstrMessageEvent):
        yield event.plain_result("🚀 收到指令，开始执行 Simple Shipping 打包...")
        
        # 你的 packsimple.bat 内容是：call packet.bat simple Shipping 
        # 我们直接调用它
        bat_file = os.path.join(self.BAT_DIR, "packsimple.bat")
        
        await self.run_bat_async(event, bat_file)

    # ----------------------------------------------------------------
    # 命令 2: 自定义打包 (对应 packet.bat)
    # 触发指令: /build_custom [模式] [配置]
    # 例如: /build_custom all Develop
    # ----------------------------------------------------------------
    @filter.command("build_custom")
    async def build_custom(self, event: AstrMessageEvent, mode: str, config: str):
        # 校验参数，防止乱输
        valid_modes = ["all", "simple", "special"] # 根据 packet.bat 的逻辑 
        valid_configs = ["Shipping", "Develop", "Debug"] # 根据 packet.bat 的逻辑 

        if mode not in valid_modes:
            yield event.plain_result(f"❌ 模式错误。可选: {', '.join(valid_modes)}")
            return
        if config not in valid_configs:
            yield event.plain_result(f"❌ 配置错误。可选: {', '.join(valid_configs)}")
            return

        yield event.plain_result(f"🛠️ 开始执行自定义打包...\n模式: {mode}\n配置: {config}")

        # 构造命令，直接调用 packet.bat 并传入参数
        # 对应 packet.bat %1 %2 的逻辑
        bat_file = os.path.join(self.BAT_DIR, "packet.bat")
        cmd_args = [bat_file, mode, config]
        
        await self.run_bat_async(event, cmd_args)

    # ----------------------------------------------------------------
    # 核心执行逻辑 (异步执行防止卡死机器人)
    # ----------------------------------------------------------------
    async def run_bat_async(self, event, cmd):
        try:
            # 使用 asyncio 创建子进程，这样打包过程中机器人还能响应其他人
            process = await asyncio.create_subprocess_exec(
                *([cmd] if isinstance(cmd, str) else cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.BAT_DIR, # 确保在脚本所在目录执行
                shell=True
            )

            # 等待结束
            stdout, stderr = await process.communicate()
            
            # 解码输出 (Windows 通常是 GBK，但也可能是 UTF-8，视系统而定)
            try:
                log_out = stdout.decode('gbk', errors='ignore')
                log_err = stderr.decode('gbk', errors='ignore')
            except:
                log_out = stdout.decode('utf-8', errors='ignore')
                log_err = stderr.decode('utf-8', errors='ignore')

            if process.returncode == 0:
                # 成功
                msg = "✅ 打包流程执行完毕！\n(请检查服务器上的 BuildLog 确认最终结果)"
                # 如果你想看最后几行日志，可以取消下面这行的注释
                # msg += f"\n\n日志末尾:\n{log_out[-200:]}"
                await event.send(Plain(msg))
            else:
                # 失败
                await event.send(Plain(f"⚠️ 打包脚本返回错误代码: {process.returncode}\n错误信息:\n{log_err[-300:]}"))

        except Exception as e:
            await event.send(Plain(f"❌ 执行脚本时发生严重错误: {str(e)}"))
