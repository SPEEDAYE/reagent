# REagent 1.0 API 实现规划

> 基于 `arc_readme.md` 架构文档和源码分析，详细规划如何将 CLI 应用改造为 FastAPI + SSE 的 Web API。
> API 设计见 [API_README.md](API_README.md)（精简版 12 个端点）。

---

## 1. 改造总览

### 1.1 核心问题

| 问题 | 根因 | 解法 |
|------|------|------|
| **同步阻塞** | `crew.kickoff()` 单次执行几十秒到几分钟 | `asyncio.run_in_executor()` 放入线程池 |
| **CLI 阻塞输入** | `multiline_input()` 在 3 处阻塞等终端输入 | 替换为 `threading.Event` + resume API |
| **文件耦合** | 所有状态通过 `experiment/` 目录的 md/pkl 文件通信 | 保留文件系统，上层加 MongoDB 索引 |

### 1.2 改造原则

1. **最小侵入**：不重写现有 crew 逻辑，只在外围包装
2. **单一线程执行**：crewAI 不支持并发，每个项目独立线程串行
3. **事件驱动通信**：线程通过 `StreamManager` 向 SSE 推送事件
4. **中断点注入**：在 3 个 `multiline_input()` 位置注入可等待的中断

---

## 2. 需要修改的现有文件（仅 3 个）

### 2.1 `util/util.py` — 注入 API 模式开关

**改动点**：`multiline_input()` 函数（第 24-49 行）

```python
import threading

# 全局注册表：project_id -> {event, value}
_feedback_registry: dict[str, dict] = {}
_stream_callback = None  # 由 backend 注入

def register_feedback_slot(project_id: str):
    """为某个项目注册一个反馈等待槽"""
    _feedback_registry[project_id] = {
        "event": threading.Event(),
        "value": None
    }

def submit_feedback(project_id: str, feedback: str):
    """从 API resume 端点调用，唤醒等待线程"""
    slot = _feedback_registry.get(project_id)
    if slot:
        slot["value"] = feedback
        slot["event"].set()

def set_stream_callback(callback):
    """由 backend 启动时注入，用于发送 interrupt 事件"""
    global _stream_callback
    _stream_callback = callback

def multiline_input(prompt_text="请输入反馈：", project_id=None, interrupt_data=None):
    """
    CLI 模式：project_id=None，走原逻辑
    API 模式：project_id 存在，阻塞等待 threading.Event
    """
    if project_id and project_id in _feedback_registry:
        # 发送 interrupt 事件通知前端
        if interrupt_data and _stream_callback:
            _stream_callback(project_id, {"type": "interrupt", **interrupt_data})

        # 阻塞工作线程，等待 submit_feedback() 被调用
        slot = _feedback_registry[project_id]
        slot["event"].clear()
        slot["event"].wait()
        value = slot["value"]
        slot["value"] = None
        return value if value else "no"
    else:
        # 原 CLI 逻辑不变
        # ... existing prompt_toolkit code ...
```

### 2.2 `src/reagent/StandardProcess.py` — 透传 project_id

3 处 `multiline_input()` 调用需要传入 `project_id`：

| 行号 | 函数 | 中断类型 | 审查内容 |
|------|------|----------|----------|
| ~168 | `BRDevrun()` | `business_review` | business_scope.md |
| ~208 | `BRDevrun()` | `brd_review` | BRD.md |
| ~244 | `RequirementElicitationrun()` | `elicitation_review` | use_case.md + NFR |

```python
# 改动前
feedback = multiline_input()

# 改动后（3 处）
feedback = multiline_input(
    project_id=project_id,
    interrupt_data={
        "interrupt_type": "business_review",
        "artifact_names": ["business_scope"],
        "message": "业务范围文档已生成，请审查并提供反馈",
    }
)
```

函数签名增加 `project_id=None` 参数，逐层透传：
- `StandardProcessrun(... project_id=None)`
- `BRDevrun(... project_id=None)`
- `RequirementElicitationrun(... project_id=None)`

### 2.3 `util/__init__.py` — `run_with_retry()` 增加事件钩子

```python
import threading

_thread_local = threading.local()

def set_event_callbacks(on_start=None, on_complete=None, on_error=None):
    """由 ExecutionService 在工作线程中调用，注册事件回调"""
    _thread_local.on_start = on_start
    _thread_local.on_complete = on_complete
    _thread_local.on_error = on_error

def run_with_retry(crew_callable, inputs, name, retries=5, delay=15,
                   post_process_callable=None, post_process_params=None):
    on_start = getattr(_thread_local, 'on_start', None)
    on_complete = getattr(_thread_local, 'on_complete', None)
    on_error = getattr(_thread_local, 'on_error', None)

    for attempt in range(retries):
        try:
            if on_start:
                on_start(name, attempt)

            result = crew_callable().crew().kickoff(inputs=inputs)

            if on_complete:
                on_complete(name, str(result))

            # ... 原有 post_process 逻辑不变 ...
        except Exception as e:
            if on_error:
                on_error(name, str(e), attempt)
            # ... 原有重试逻辑不变 ...
```

---

## 3. 新增文件（backend/）

### 3.1 目录结构

```
backend/
├── __init__.py
├── main.py                    # FastAPI 应用入口
├── config.py                  # 配置管理
├── dependencies.py            # 依赖注入
├── api/routes/
│   ├── __init__.py            # 路由注册
│   ├── health.py              # GET /health
│   ├── project.py             # 4 个项目管理端点
│   ├── stream.py              # 3 个流式执行端点（核心）
│   ├── artifacts.py           # 3 个 artifact 端点
│   └── files.py               # 1 个文件上传端点
├── models/
│   ├── requests.py            # Pydantic 请求模型
│   └── responses.py           # Pydantic 响应模型
├── services/
│   ├── execution.py           # crewAI 执行封装（核心）
│   ├── stream_manager.py      # SSE 事件队列（核心）
│   ├── artifact_service.py    # Artifact 读写
│   ├── project_service.py     # 项目 CRUD
│   └── file_service.py        # 文件处理
└── db/
    └── mongo.py               # MongoDB 连接
```

### 3.2 `backend/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import register_routes
from backend.db.mongo import connect_db, close_db

app = FastAPI(title="REagent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await connect_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()

register_routes(app)
```

### 3.3 `backend/services/stream_manager.py`

```python
import asyncio
import json

class StreamManager:
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def create_queue(self, project_id: str):
        self._queues[project_id] = asyncio.Queue()

    def remove_queue(self, project_id: str):
        self._queues.pop(project_id, None)

    async def publish(self, project_id: str, event: dict):
        queue = self._queues.get(project_id)
        if queue:
            await queue.put(event)

    async def subscribe(self, project_id: str):
        queue = self._queues.get(project_id)
        if not queue:
            yield {"data": json.dumps({"type": "error", "error": "No active session"})}
            return
        while True:
            event = await queue.get()
            yield {
                "event": event.get("type", "message"),
                "data": json.dumps(event, ensure_ascii=False)
            }
            if event.get("type") in ("finished", "error"):
                break
```

### 3.4 `backend/services/execution.py` — 核心

```
┌─────────────────────────────────────────────────────┐
│  FastAPI (async event loop)                          │
│                                                      │
│  POST /graph/stream/create                           │
│    │                                                 │
│    ├─► run_in_executor(executor, _run_pipeline)      │
│    │     │                                           │
│    │     │  ┌──────────────────────────────────┐     │
│    │     └─►│  Thread Pool (1 per project)      │    │
│    │        │                                    │   │
│    │        │  _run_pipeline():                   │   │
│    │        │    MetaAnalysisrun()                │   │
│    │        │    BRDevrun(project_id=...)         │   │
│    │        │      ├─ crew.kickoff() x N          │   │
│    │        │      ├─ multiline_input() ──BLOCK── │ ◄── threading.Event.wait()
│    │        │    RequirementElicitationrun()      │   │
│    │        │      ├─ multiline_input() ──BLOCK── │ ◄── threading.Event.wait()
│    │        │    RequirementAnalysisrun()         │   │
│    │        │    NonStandardProcessrun()          │   │
│    │        │    RequirementSpecificationrun()    │   │
│    │        └──────────────────────────────────┘     │
│                                                      │
│  GET /graph/stream/{id}  ◄── StreamManager.subscribe │
│                                                      │
│  POST /graph/stream/resume                           │
│    └─► submit_feedback() ─► Event.set() ──UNBLOCK──► │
└─────────────────────────────────────────────────────┘
```

```python
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="reagent")
_active_tasks: dict[str, asyncio.Task] = {}

class ExecutionService:
    def __init__(self, stream_manager):
        self.stream = stream_manager

    async def start(self, project_id: str, config: dict):
        if project_id in _active_tasks:
            raise RuntimeError(f"Project {project_id} already running")

        from util.util import register_feedback_slot, set_stream_callback
        register_feedback_slot(project_id)

        # 注入 stream callback（从同步线程安全发送 SSE 事件）
        loop = asyncio.get_event_loop()
        def sync_emit(pid, event):
            asyncio.run_coroutine_threadsafe(
                self.stream.publish(pid, {**event, "timestamp": _now()}), loop
            )
        set_stream_callback(sync_emit)

        self.stream.create_queue(project_id)
        task = loop.run_in_executor(_executor, self._run_pipeline, project_id, config, loop)
        _active_tasks[project_id] = task

    def _run_pipeline(self, project_id, config, loop):
        # 注册 run_with_retry 事件钩子
        from util import set_event_callbacks
        def on_start(name, attempt):
            self._emit(loop, project_id, "crew_start", crew_name=name)
        def on_complete(name, result):
            self._emit(loop, project_id, "artifact_complete", crew_name=name,
                       content_preview=result[:200] if result else "")
        def on_error(name, error, attempt):
            self._emit(loop, project_id, "error", crew_name=name, error=error,
                       retry_count=attempt, recoverable=True)
        set_event_callbacks(on_start, on_complete, on_error)

        try:
            # Phase 1: MetaAnalysis
            self._emit(loop, project_id, "stage_start", stage="meta_analysis", stage_index=1)
            from src.reagent.StandardProcess import MetaAnalysisrun
            result = MetaAnalysisrun(
                doc_example_path=config["srs_example_path"],
                SRS_template=config.get("srs_template"),
                project_name=config["project_name"],
                Description=config["description"],
            )
            doc_template, doc_skeleton, doc_planning, ch_dep, art_plan = result
            self._emit(loop, project_id, "stage_complete", stage="meta_analysis")

            # Phase 2: BusinessRequirements (2 interrupts)
            self._emit(loop, project_id, "stage_start", stage="business_requirements", stage_index=2)
            from src.reagent.StandardProcess import BRDevrun
            BRDevrun(project_name=config["project_name"],
                     Description=config["description"],
                     project_id=project_id)
            self._emit(loop, project_id, "stage_complete", stage="business_requirements")

            # Phase 3: RequirementElicitation (1 interrupt)
            self._emit(loop, project_id, "stage_start", stage="requirement_elicitation", stage_index=3)
            from src.reagent.StandardProcess import RequirementElicitationrun
            RequirementElicitationrun(project_name=config["project_name"],
                                     Description=config["description"],
                                     project_id=project_id)
            self._emit(loop, project_id, "stage_complete", stage="requirement_elicitation")

            # Phase 4: RequirementAnalysis (no interrupt)
            self._emit(loop, project_id, "stage_start", stage="requirement_analysis", stage_index=4)
            from src.reagent.StandardProcess import RequirementAnalysisrun
            RequirementAnalysisrun(project_name=config["project_name"],
                                  Description=config["description"],
                                  artifact_planing=art_plan)
            self._emit(loop, project_id, "stage_complete", stage="requirement_analysis")

            # Phase 4b: NonStandard
            self._emit(loop, project_id, "stage_start", stage="non_standard", stage_index=5)
            from src.reagent.NonStandardProcess import NonStandardProcessrun
            NonStandardProcessrun(project_name=config["project_name"],
                                  Description=config["description"],
                                  artifact_planing=art_plan)
            self._emit(loop, project_id, "stage_complete", stage="non_standard")

            # Phase 5: SRS Generation
            self._emit(loop, project_id, "stage_start", stage="srs_generation", stage_index=6)
            from src.reagent.main import RequirementSpecificationrun
            RequirementSpecificationrun(doc_template, doc_skeleton, doc_planning,
                                        ch_dep, None, config["srs_example_path"])
            self._emit(loop, project_id, "stage_complete", stage="srs_generation")

            self._emit(loop, project_id, "finished", total_artifacts=17, srs_generated=True)

        except Exception as e:
            self._emit(loop, project_id, "error", error=str(e), recoverable=False)
        finally:
            _active_tasks.pop(project_id, None)

    def _emit(self, loop, project_id, event_type, **kwargs):
        event = {"type": event_type, "project_id": project_id,
                 "timestamp": _now(), **kwargs}
        asyncio.run_coroutine_threadsafe(self.stream.publish(project_id, event), loop)

def _now():
    return datetime.now(timezone.utc).isoformat()
```

### 3.5 `backend/api/routes/stream.py`

```python
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from backend.models.requests import StreamCreateRequest, StreamResumeRequest

router = APIRouter(prefix="/graph", tags=["stream"])

@router.post("/stream/create")
async def stream_create(req: StreamCreateRequest, exec_svc=Depends()):
    await exec_svc.start(req.project_id, req.dict())
    return {"status": "started", "project_id": req.project_id}

@router.post("/stream/resume")
async def stream_resume(req: StreamResumeRequest):
    from util.util import submit_feedback
    feedback_map = {
        "accept": "no",
        "feedback": req.human_comment or "no",
        "redo_artifact": req.human_comment or "redo",
        "skip": "exit",
    }
    submit_feedback(req.project_id, feedback_map.get(req.resume_type, "no"))
    return {"status": "resumed", "project_id": req.project_id}

@router.get("/stream/{project_id}")
async def stream_events(project_id: str, stream_mgr=Depends()):
    return EventSourceResponse(stream_mgr.subscribe(project_id))
```

### 3.6 `backend/api/routes/project.py`

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/project", tags=["project"])

@router.post("/create")
async def create_project(req, svc=Depends()):
    return await svc.create(req)

@router.get("/list/{user_id}")
async def list_projects(user_id: str, svc=Depends()):
    return await svc.list_by_user(user_id)

@router.get("/{project_id}")
async def get_project(project_id: str, svc=Depends()):
    return await svc.get(project_id)

@router.delete("/{project_id}")
async def delete_project(project_id: str, svc=Depends()):
    return await svc.delete(project_id)
```

### 3.7 `backend/api/routes/artifacts.py`

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

@router.get("/{project_id}")
async def list_artifacts(project_id: str, svc=Depends()):
    """列出所有 artifact + DAG 依赖数据 + 完成度统计"""
    return await svc.list_all(project_id)

@router.get("/{project_id}/{artifact_name}")
async def get_artifact(project_id: str, artifact_name: str, svc=Depends()):
    return await svc.get_content(project_id, artifact_name)

@router.post("/export_pdf")
async def export_pdf(body: dict, svc=Depends()):
    pdf_bytes = await svc.export_pdf(body["project_id"], body["artifact_name"])
    return StreamingResponse(pdf_bytes, media_type="application/pdf")
```

### 3.8 `backend/api/routes/files.py`

```python
from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import Optional

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload")
async def upload_file(
    project_id: str = Form(...),
    file_type: str = Form(...),          # "data" | "template"
    action: Optional[str] = Form(None),  # "confirm" | "revise" (模板专用)
    feedback: Optional[str] = Form(None),# revise 时的反馈
    file: Optional[UploadFile] = File(None),
    svc=Depends()
):
    if file_type == "template":
        if action == "confirm":
            return await svc.confirm_template(project_id)
        elif action == "revise":
            return await svc.revise_template(project_id, feedback)
        else:
            return await svc.upload_template(project_id, file)
    else:
        return await svc.upload_data(project_id, file)
```

### 3.9 `backend/models/requests.py`

```python
from pydantic import BaseModel
from typing import Optional, Literal

class ProjectCreateRequest(BaseModel):
    user_id: str
    project_name: str
    description: str
    srs_template: Optional[Literal["IEEE", "Initial"]] = None
    srs_example_path: Optional[str] = None

class StreamCreateRequest(BaseModel):
    project_id: str
    user_id: str
    human_request: Optional[str] = None
    data_files: Optional[list[str]] = None
    start_from: Optional[str] = None

class StreamResumeRequest(BaseModel):
    project_id: str
    resume_type: Literal["feedback", "accept", "redo_artifact", "skip"]
    human_comment: Optional[str] = None
    target_artifact: Optional[str] = None
    prune_downstream: Optional[bool] = False

class ExportPdfRequest(BaseModel):
    project_id: str
    artifact_name: str
```

### 3.10 `backend/services/artifact_service.py`

```python
import os
from util.DAG import Artifact_Dependance_rules
from util.util import store_path, read_markdown

ARTIFACT_META = {
    "survey":                       ("市场调研报告",     "survey.md"),
    "context_diagram":              ("上下文图",         "draft_context_diagram.md"),
    "event_list":                   ("事件列表",         "draft_event_list.md"),
    "user_introduction":            ("用户介绍",         "user_introduction.md"),
    "feature_tree":                 ("功能树",           "feature_tree.md"),
    "business_scope":               ("业务范围",         "business_scope.md"),
    "BRD":                          ("业务需求文档",     "BRD.md"),
    "use_case":                     ("用例",             "use_case.md"),
    "non_functional_requirements":  ("非功能需求",       "non_functional_requirements.md"),
    "functional_requirements":      ("功能需求",         "functional_requirements.md"),
    "data_flow_diagram":            ("数据流图",         "data_flow_diagram.md"),
    "ERD":                          ("实体关系图",       "entity_relationship_diagram.md"),
    "data_dictionary":              ("数据字典",         "data_dictionary.md"),
    "dialog_map":                   ("对话图",           "dialog_map.md"),
    "state_transition_diagram":     ("状态转换图",       "state_transition_diagram.md"),
    "usage_scenario":               ("使用场景",         "usage_scenario.md"),
    "SRS":                          ("软件需求规格说明书","SRS.md"),
}

# 构建反向依赖（谁依赖我）
def _build_dependents():
    dependents = {name: [] for name in ARTIFACT_META}
    for name, deps in Artifact_Dependance_rules.items():
        for dep in deps:
            if dep in dependents:
                dependents[dep].append(name)
    return dependents

_DEPENDENTS = _build_dependents()

class ArtifactService:
    async def list_all(self, project_id: str) -> dict:
        artifacts = []
        for name, (display, filename) in ARTIFACT_META.items():
            filepath = os.path.join(store_path, filename)
            status = "completed" if os.path.exists(filepath) else "pending"
            preview = ""
            if status == "completed":
                preview = read_markdown(filepath)[:200]
            artifacts.append({
                "artifact_name": name,
                "display_name": display,
                "filename": filename,
                "status": status,
                "content_preview": preview,
                "dependencies": Artifact_Dependance_rules.get(name, []),
                "dependents": _DEPENDENTS.get(name, []),
            })
        completed = sum(1 for a in artifacts if a["status"] == "completed")
        return {
            "project_id": project_id,
            "artifacts": artifacts,
            "total": len(artifacts),
            "completed": completed,
            "in_progress": 0,
            "pending": len(artifacts) - completed,
        }

    async def get_content(self, project_id: str, artifact_name: str) -> dict:
        meta = ARTIFACT_META.get(artifact_name)
        if not meta:
            return {"error": f"Unknown artifact: {artifact_name}"}
        display, filename = meta
        filepath = os.path.join(store_path, filename)
        content = read_markdown(filepath) if os.path.exists(filepath) else ""
        return {
            "artifact_name": artifact_name,
            "display_name": display,
            "status": "completed" if content else "pending",
            "content": content,
            "dependencies": Artifact_Dependance_rules.get(artifact_name, []),
            "dependents": _DEPENDENTS.get(artifact_name, []),
        }
```

### 3.11 `backend/db/mongo.py`

```python
from motor.motor_asyncio import AsyncIOMotorClient
import os

_client = None
_db = None

async def connect_db():
    global _client, _db
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "reagent")
    _client = AsyncIOMotorClient(uri)
    _db = _client[db_name]

async def close_db():
    if _client:
        _client.close()

def get_db():
    return _db

def projects_col():   return _db["projects"]
def artifacts_col():  return _db["artifacts"]
def files_col():      return _db["files"]
```

---

## 4. 实现步骤

### Phase 1: 基础框架

| 步骤 | 文件 | 说明 |
|------|------|------|
| 1.1 | `backend/main.py`, `config.py` | FastAPI 骨架 + CORS |
| 1.2 | `backend/db/mongo.py` | MongoDB 连接 |
| 1.3 | `backend/models/requests.py` | Pydantic 模型 |
| 1.4 | `backend/api/routes/__init__.py` | 路由注册 |
| 1.5 | `backend/api/routes/health.py` | `GET /health` |

**里程碑**：`python main.py serve` 启动，`/health` 返回 200

### Phase 2: 项目管理

| 步骤 | 文件 |
|------|------|
| 2.1 | `backend/services/project_service.py` |
| 2.2 | `backend/api/routes/project.py` |

**里程碑**：API 创建/查询/删除项目

### Phase 3: 核心执行流（最复杂）

| 步骤 | 文件 | 说明 |
|------|------|------|
| 3.1 | `backend/services/stream_manager.py` | SSE 队列 |
| 3.2 | `util/util.py` | 改造 `multiline_input()` |
| 3.3 | `src/reagent/StandardProcess.py` | 透传 `project_id` |
| 3.4 | `util/__init__.py` | `run_with_retry()` 加钩子 |
| 3.5 | `backend/services/execution.py` | 后台线程 + 事件发射 |
| 3.6 | `backend/api/routes/stream.py` | 3 个端点 |

**里程碑**：API 启动执行 → SSE 接收进度 → interrupt 时 resume → 继续

### Phase 4: Artifact + 文件

| 步骤 | 文件 |
|------|------|
| 4.1 | `backend/services/artifact_service.py` |
| 4.2 | `backend/api/routes/artifacts.py` |
| 4.3 | `backend/services/file_service.py` |
| 4.4 | `backend/api/routes/files.py` |

**里程碑**：查询 artifact 列表/内容/DAG，上传文件

### Phase 5: 多项目隔离

| 步骤 | 说明 |
|------|------|
| 5.1 | `store_path` → `experiment/{project_id}/` |
| 5.2 | getter 函数接受 `store_path` 参数 |
| 5.3 | PDF 导出实现 |

---

## 5. 关键实现难点

### 5.1 线程安全：工作线程 → async 队列

```python
# 工作线程中安全发送事件到 async 队列
asyncio.run_coroutine_threadsafe(
    stream_manager.publish(project_id, event),
    main_event_loop
)
```

### 5.2 中断-恢复同步

使用 `threading.Event`（非 `asyncio.Event`），阻塞工作线程但不影响 FastAPI 事件循环：

```
工作线程                FastAPI 事件循环
    │                        │
    ├─ Event.wait() ─BLOCK   │
    │                        ├─ POST /resume 到达
    │                        ├─ submit_feedback()
    │                        ├─ Event.set() ──► UNBLOCK
    ├─ 继续执行...            │
```

### 5.3 crewAI 全局状态

- Phase 1：`ThreadPoolExecutor(max_workers=1)` 串行
- Phase 2：`experiment/{project_id}/` 目录隔离
- Phase 3（未来）：`multiprocessing` 进程隔离

### 5.4 SSE 断线重连

前端断线后重连 SSE，通过 `GET /artifacts/{id}` 同步当前状态（替代原方案中的 events collection），然后重新订阅 SSE 继续接收后续事件。

---

## 6. 依赖安装

```bash
pip install fastapi==0.115.12 uvicorn[standard]==0.34.3 \
    sse-starlette==3.0.3 motor==3.7.0 python-multipart

docker run -d -p 27017:27017 --name reagent-mongo mongo:7
```

---

## 7. 工作量评估

| 类别 | 数量 | 说明 |
|------|------|------|
| **新增文件** | ~15 | backend/ 下所有文件 |
| **修改现有文件** | 3 | `util/util.py`, `util/__init__.py`, `StandardProcess.py` |
| **不动的文件** | ~20+ | 所有 crew、tasks.yaml、agents.yaml、模板等 |

改动集中在外围包装层，crewAI 核心执行逻辑完全不变。
