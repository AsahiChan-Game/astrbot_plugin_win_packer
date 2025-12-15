# 📖 Unreal Engine 打包插件 v4.0 用户手册

## 🚀 快速上手

### 基本命令

```bash
# 打包命令
pack main simple        # 主分支简单打包
pack develop debug      # 开发分支调试打包

# 查看状态
build_status           # 系统状态
build_queue           # 任务队列
build_stats           # 统计图表

# 管理任务
build_stop            # 停止当前任务
build_clear_queue     # 清空队列
```

## ⚙️ 配置文件

首次运行自动生成 `config.json`：

```json
{
    "workspace_root": "C:\\WorkSpace",     // 工作目录
    "publish_root_base": "d:\\publish",    // 发布目录
    "web_port": 8090,                      // Web端口
    "min_size_threshold": 2147483648,      // 最小包大小(2GB)
    "ai_timeout": 30.0,                    // AI超时时间
    "log_level": "INFO"                    // 日志级别
}
```

## 🔧 环境变量

```bash
# Windows
set BUILD_WORKSPACE_ROOT=D:\MyWorkspace
set BUILD_WEB_PORT=8091

# Linux/Mac  
export BUILD_WORKSPACE_ROOT=/path/to/workspace
export BUILD_WEB_PORT=8091
```

## 📊 Web界面

访问 `http://localhost:8090` 下载构建产物

## 🆕 新功能

### 任务队列
- 支持多任务排队
- 优先级管理
- 任务持久化

### 智能分析
- AI驱动的失败分析
- 自动生成变更日志
- 性能趋势分析

### 配置热重载
- 修改配置无需重启
- 实时生效

## 🛠️ 故障排除

### 常见问题

**端口被占用**
```json
{"web_port": 8091}  // 修改端口
```

**模块缺失**
```bash
pip install watchdog aiofiles
```

**权限问题**
- 以管理员身份运行
- 检查目录权限

### 回滚方案

```bash
copy main_backup.py main.py  # 恢复旧版本
```

## 📈 性能对比

| 指标 | v3.x | v4.0 | 提升 |
|------|------|------|------|
| 启动时间 | 2s | 1s | 50% |
| 内存使用 | 50MB | 30MB | 40% |
| 文件扫描 | 慢 | 快 | 3-5x |

## 🎯 最佳实践

1. **定期清理** - 使用 `build_clear_queue` 清理队列
2. **监控状态** - 定期检查 `build_status`
3. **配置备份** - 备份 `config.json` 文件
4. **日志分析** - 启用 DEBUG 模式排查问题

---

**需要帮助？** 查看完整文档 [README_v4.0.md](README_v4.0.md)