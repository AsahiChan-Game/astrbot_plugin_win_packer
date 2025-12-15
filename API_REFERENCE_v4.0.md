# 🔌 API 参考文档 v4.0

## 📋 目录

- [命令 API](#-命令-api)
- [配置 API](#-配置-api)
- [Web API](#-web-api)
- [内部组件 API](#-内部组件-api)
- [事件和回调](#-事件和回调)

## 🎮 命令 API

### 核心构建命令

#### `pack`
执行 Unreal Engine 打包任务

**语法：**
```bash
pack <branch> <strategy> [arg3]
```

**参数：**
- `branch` (string, required) - 分支名称
- `strategy` (string, required) - 打包策略
- `arg3` (string, optional) - 额外参数

**策略选项：**
- `simple` - 简单打包
- `develop` - 开发版本打包
- `debug` - 调试版本打包
- `special` - 特殊打包（需要 arg3）
- `all` - 完整打包

**返回：**
- 成功：构建结果和下载链接
- 失败：错误信息和AI分析

**示例：**
```bash
pack main simple
pack develop debug
pack test special MyCustomArg
```

#### `build_stats`
查看构建统计信息

**语法：**
```bash
build_stats
```

**返回：**
- 文本报告：各分支平均耗时统计
- 图表：构建时间趋势图（需要 matplotlib）

**输出格式：**
```
📊 **打包耗时统计**
- main_simple: 平均 180秒 (最近10次)
- develop_debug: 平均 240秒 (最近8次)
```

#### `build_stop`
停止当前构建任务

**语法：**
```bash
build_stop
```

**行为：**
- 终止当前进程树
- 清理临时资源
- 清空任务队列
- 通知相关任务

**返回：**
- 成功：`🛑 任务已终止`
- 无任务：`🛑 无任务`
- 失败：错误信息

### 队列管理命令

#### `build_status`
查看系统整体状态

**语法：**
```bash
build_status
```

**返回信息：**
```
🔧 **构建系统状态**

🏗️ **当前任务**: [main] simple (running)
📋 **队列**: 2 个任务
🌐 **Web服务**: 运行中 (http://192.168.1.100:8090)
🤖 **AI服务**: AstrBot (可用)
```

#### `build_queue`
查看任务队列详情

**语法：**
```bash
build_queue
```

**返回信息：**
```
📋 **任务队列** (3 个任务)

🔸 HIGH: 1 个任务
🔸 NORMAL: 2 个任务

**按分支分组**:
📂 main: 2 个任务
📂 develop: 1 个任务

⏰ 最早任务等待时间: 5.2 分钟
```

#### `build_clear_queue`
清空任务队列

**语法：**
```bash
build_clear_queue
```

**返回：**
```
🗑️ 已清空队列，移除了 3 个任务
```

### 兼容命令

#### `build_simple`
快捷打包命令

**语法：**
```bash
build_simple
```

**等价于：**
```bash
pack main simple
```

## ⚙️ 配置 API

### 配置文件结构

**文件位置：** `config.json`

**完整配置：**
```json
{
    // 路径配置
    "workspace_root": "C:\\WorkSpace",
    "publish_root_base": "d:\\publish",
    
    // 大小阈值 (字节)
    "min_size_threshold": 2147483648,      // 2GB
    "disk_warn_threshold": 21474836480,    // 20GB
    
    // 网络配置
    "web_port": 8090,
    "web_host": "0.0.0.0",
    
    // 文件配置
    "history_file": "build_history.json",
    "max_history_entries": 50,
    
    // 进程配置
    "process_timeout": 5.0,                // 秒
    "max_log_lines": 10000,
    
    // AI配置
    "ai_timeout": 30.0,                    // 秒
    "ai_max_retries": 3,
    
    // 日志配置
    "log_level": "INFO",                   // DEBUG|INFO|WARNING|ERROR|CRITICAL
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}
```

### 环境变量覆盖

**支持的环境变量：**
```bash
BUILD_WORKSPACE_ROOT      # 覆盖 workspace_root
BUILD_PUBLISH_ROOT        # 覆盖 publish_root_base  
BUILD_WEB_PORT           # 覆盖 web_port
BUILD_LOG_LEVEL          # 覆盖 log_level
```

**优先级：** 环境变量 > 配置文件 > 默认值

### 配置验证规则

**路径验证：**
- 必须是非空字符串
- 不能包含非法字符
- 目录必须存在或可创建

**端口验证：**
- 范围：1-65535
- 不能被其他程序占用

**阈值验证：**
- 必须为正数
- min_size_threshold < disk_warn_threshold

## 🌐 Web API

### HTTP 服务

**基础URL：** `http://<local_ip>:<web_port>`

**默认端口：** 8090

### 文件下载

#### GET `/path/to/file`
下载构建产物

**请求：**
```http
GET /Lycoris_main/20231215_ver_1.0.0_Shipping/Game.exe HTTP/1.1
Host: 192.168.1.100:8090
```

**响应：**
```http
HTTP/1.1 200 OK
Content-Type: application/octet-stream
Content-Length: 1073741824
Accept-Ranges: bytes

[文件内容]
```

**特性：**
- 支持大文件流式传输
- 自动 MIME 类型检测
- 访问日志记录
- 路径安全验证

### 服务器信息

**获取方式：** 通过 `build_status` 命令

**信息包含：**
- 服务器运行状态
- 监听地址和端口
- 启动时间和运行时长
- 请求统计

## 🔧 内部组件 API

### BuildOrchestrator

**职责：** 构建流程编排和协调

**主要方法：**
```python
async def submit_build_request(
    branch: str, 
    strategy: str, 
    arg3: Optional[str] = None,
    priority: QueuePriority = QueuePriority.NORMAL
) -> Dict[str, Any]

async def cancel_build(task_id: Optional[str] = None) -> Dict[str, Any]

async def get_build_status() -> Dict[str, Any]
```

### TaskQueue

**职责：** 任务队列管理

**主要方法：**
```python
async def enqueue(task: BuildTask, priority: QueuePriority) -> bool

async def dequeue() -> Optional[BuildTask]

async def get_queue_size() -> int

async def get_queue_status() -> Dict[str, Any]

async def cancel_task(task_id: str) -> bool

async def clear_queue() -> int
```

### FileManager

**职责：** 安全文件操作

**主要方法：**
```python
def get_branch_paths(branch: str) -> Tuple[str, str]

def get_latest_build_info(
    root: str, 
    after_timestamp: Optional[float] = None
) -> Tuple[bool, BuildInfo, Optional[str]]

def validate_path(path: str, base_path: Optional[str] = None) -> bool

def check_disk_space() -> Optional[str]
```

### WebServer

**职责：** HTTP 文件服务

**主要方法：**
```python
async def start() -> bool

async def stop() -> None

def get_download_url(file_path: str) -> str

def get_server_stats() -> Dict[str, Any]
```

### AIProvider

**职责：** AI 服务集成

**主要方法：**
```python
async def analyze_failure(
    log_content: str, 
    context: Optional[Dict[str, Any]] = None
) -> AIResponse

async def generate_changelog(
    changes_text: str, 
    context: Optional[Dict[str, Any]] = None
) -> AIResponse

def is_available() -> bool
```

## 📡 事件和回调

### 进度事件

**ProgressUpdate 结构：**
```python
@dataclass
class ProgressUpdate:
    task_id: str
    stage: str
    message: str
    timestamp: datetime
```

**阶段类型：**
- `preparation` - 准备阶段
- `init_uat` - 初始化 UAT
- `start_build` - 开始构建
- `cooking` - 资源烹饪
- `staging` - 资源暂存
- `packaging` - 打包阶段
- `finalizing` - 完成阶段

### 构建结果事件

**BuildResult 结构：**
```python
@dataclass
class BuildResult:
    task: BuildTask
    success: bool
    build_info: Optional[BuildInfo] = None
    error_message: Optional[str] = None
    log_content: Optional[str] = None
    duration: Optional[float] = None
```

### 回调注册

**进度回调：**
```python
orchestrator.add_progress_callback(callback_function)
```

**结果回调：**
```python
orchestrator.add_result_callback(callback_function)
```

## 📊 数据模型

### BuildTask

**任务实体：**
```python
@dataclass
class BuildTask:
    branch: str
    strategy: BuildStrategy
    task_id: str = field(default_factory=uuid4)
    arg3: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### BuildInfo

**构建信息：**
```python
@dataclass
class BuildInfo:
    path: str
    folder_name: str
    ymd: str = "?"
    version: str = "?"
    build_type: BuildType = BuildType.UNKNOWN
    size_str: str = "0 MB"
    size_bytes: int = 0
```

### 枚举类型

**BuildStrategy：**
```python
class BuildStrategy(Enum):
    SIMPLE = "simple"
    DEVELOP = "develop"
    DEBUG = "debug"
    SPECIAL = "special"
    ALL = "all"
```

**TaskStatus：**
```python
class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

**QueuePriority：**
```python
class QueuePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
```

## 🔍 错误处理

### 异常层次

```python
BuildSystemError                    # 基础异常
├── ConfigurationError             # 配置错误
├── BuildExecutionError            # 构建执行错误
├── FileSystemError               # 文件系统错误
├── NetworkError                  # 网络错误
├── TaskQueueError               # 任务队列错误
├── AIServiceError               # AI服务错误
├── ValidationError              # 验证错误
├── SecurityError                # 安全错误
└── ProcessError                 # 进程错误
```

### 错误响应格式

**命令错误：**
```
❌ 错误类型: 具体错误信息
建议的解决方案
```

**API错误：**
```python
{
    "success": false,
    "error_type": "ValidationError",
    "error_message": "Branch name contains invalid characters",
    "context": {
        "branch": "test<>branch",
        "invalid_chars": ["<", ">"]
    }
}
```

---

**📚 更多信息请参考：**
- [用户手册](USER_MANUAL_v4.0.md)
- [完整文档](README_v4.0.md)
- [更新日志](CHANGELOG_v4.0.md)