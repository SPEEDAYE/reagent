# REagent 1.0 API 设计文档

> 为 REagent 1.0 需求工程自动化平台设计的 FastAPI + SSE Web API 层（精简版，12 个端点）。
> 实现细节见 [api_impl_readme.md](api_impl_readme.md)，架构参考见 [arc_readme.md](arc_readme.md)。

---

## 1. 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| Web 框架 | **FastAPI 0.115+** | 异步支持、自动 OpenAPI 文档、依赖注入 |
| 流式通信 | **SSE (sse-starlette 3.0+)** | 实时推送 crew 执行进度，支持断线重连 |
| 数据库 | **MongoDB (motor 3.7+)** | 异步驱动，存储项目、artifact |
| 序列化 | **Pydantic v2** | 请求/响应模型验证 |
| 服务器 | **Uvicorn** | ASGI 服务器 |
| 跨域 | **CORS Middleware** | 允许前端跨域请求 |
| 文件上传 | **python-multipart** | 处理 multipart/form-data |

---

## 2. 项目结构

```
reagent1.0_UI/
├── src/reagent/                    # 现有 crewAI 核心（最小修改）
│   ├── main.py                     # CLI 入口 + RequirementSpecificationrun
│   ├── StandardProcess.py          # 5 阶段流程编排 (增加 project_id 参数)
│   ├── NonStandardProcess.py       # 补充制品生成
│   ├── BusinessRequirements.py     # BR 相关 crew 定义
│   ├── RequirementElicitation.py   # 需求获取 crew 定义
│   ├── RequirementAnalysis.py      # 需求分析 crew 定义
│   ├── RequirementSpecification.py # SRS 生成 crew 定义
│   ├── MetaAnalysis.py             # 元分析 crew 定义
│   └── config/
│       ├── agents.yaml             # Agent 定义
│       └── tasks.yaml              # Task 模板 (81KB, 26 种任务)
│
├── util/                           # 工具层（小幅修改）
│   ├── __init__.py                 # run_with_retry() + get_reference() (增加事件钩子)
│   ├── util.py                     # multiline_input() (增加 API 模式) + 23 个 getter
│   ├── DAG.py                      # 拓扑排序 + 依赖传播
│   ├── Artifacts.py                # Artifact-附录映射
│   ├── SoftwareManager.py          # CrewAI 基类
│   └── doc_template/               # 文档模板系统
│
├── backend/                        # 【新增】API 层
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # 环境配置
│   ├── dependencies.py             # 依赖注入
│   ├── db/
│   │   └── mongo.py                # MongoDB 连接
│   ├── api/routes/
│   │   ├── __init__.py             # 路由注册
│   │   ├── health.py               # 健康检查 (1 端点)
│   │   ├── project.py              # 项目管理 (4 端点)
│   │   ├── stream.py               # 流式执行 (3 端点)
│   │   ├── artifacts.py            # Artifact 管理 (3 端点)
│   │   └── files.py                # 文件上传 (1 端点)
│   ├── models/
│   │   ├── requests.py             # Pydantic 请求模型
│   │   └── responses.py            # Pydantic 响应模型
│   └── services/
│       ├── execution.py            # crewAI 执行封装（核心）
│       ├── stream_manager.py       # SSE 事件队列（核心）
│       ├── artifact_service.py     # Artifact CRUD
│       ├── project_service.py      # 项目 CRUD
│       └── file_service.py         # 文件处理
│
├── experiment/                         # 生成的 artifact (md + pkl)
└── requirements.txt                # Python 依赖
```

---

## 3. 全部 API 端点（12 个）

### 总览

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 1 | GET | `/health` | 健康检查 |
| 2 | POST | `/project/create` | 创建项目 |
| 3 | GET | `/project/list/{user_id}` | 项目列表 |
| 4 | GET | `/project/{project_id}` | 项目详情 |
| 5 | DELETE | `/project/{project_id}` | 删除项目 |
| 6 | POST | `/graph/stream/create` | 启动 RE 流程 |
| 7 | POST | `/graph/stream/resume` | 恢复执行（提交反馈） |
| 8 | GET | `/graph/stream/{project_id}` | SSE 事件流 |
| 9 | GET | `/artifacts/{project_id}` | Artifact 列表（含 DAG） |
| 10 | GET | `/artifacts/{project_id}/{name}` | 单个 Artifact 内容 |
| 11 | POST | `/artifacts/export_pdf` | 导出 PDF |
| 12 | POST | `/files/upload` | 上传文件/模板（统一入口） |

---

### 3.1 健康检查

#### `GET /health`

验证 crewAI 可用性、DB 连接、当前活跃项目数。

```json
{
    "status": "healthy",
    "crew_available": true,
    "db_connected": true,
    "active_projects": 1,
    "timestamp": "2026-03-29T10:00:00Z"
}
```

---

### 3.2 项目管理（4 个）

#### `POST /project/create`

创建新的 RE 项目。

```python
# 请求
{
    "user_id": "string",
    "project_name": "自动化软件源代码审查平台",
    "description": "项目描述文本...",
    "srs_template": "IEEE",              # 可选: "IEEE" | "Initial"
    "srs_example_path": "string"         # 可选: 自定义 SRS 模板路径
}

# 响应
{
    "project_id": "a1b2c3d4",
    "status": "created",
    "created_at": "2026-03-29T10:00:00Z"
}
```

#### `GET /project/list/{user_id}`

获取用户所有项目列表（侧边栏）。

```python
# 响应
{
    "projects": [
        {
            "project_id": "a1b2c3d4",
            "project_name": "自动化软件源代码审查平台",
            "status": "running",       # created | running | paused | completed | failed
            "current_stage": "requirement_elicitation",
            "created_at": "...",
            "updated_at": "..."
        }
    ]
}
```

#### `GET /project/{project_id}`

获取单个项目详情与当前状态。

```python
# 响应
{
    "project_id": "a1b2c3d4",
    "user_id": "user1",
    "project_name": "自动化软件源代码审查平台",
    "description": "项目描述...",
    "srs_template": "IEEE",
    "status": "running",
    "current_stage": "requirement_elicitation",
    "current_crew": "UserCaseCrew",
    "created_at": "...",
    "updated_at": "..."
}
```

#### `DELETE /project/{project_id}`

删除项目及所有关联数据。

```python
# 响应
{
    "status": "deleted",
    "project_id": "a1b2c3d4",
    "deleted_artifacts": 17,
    "deleted_files": 3
}
```

---

### 3.3 流式执行（3 个）— 核心

#### `POST /graph/stream/create`

启动 RE 流程。后端在独立线程中执行 5 阶段 pipeline，接口立即返回，前端随即订阅 SSE。

```python
# 请求
{
    "project_id": "a1b2c3d4",
    "user_id": "user1",
    "human_request": "重点关注安全性需求",  # 可选
    "data_files": ["f1e2d3"],              # 可选: 已上传的文件 ID
    "start_from": "meta_analysis"          # 可选: 从指定阶段开始
}

# 响应（立即返回）
{
    "status": "started",
    "project_id": "a1b2c3d4"
}
```

#### `POST /graph/stream/resume`

提交用户反馈，唤醒被暂停的执行线程。当 SSE 推送 `interrupt` 事件时调用。

```python
# 请求
{
    "project_id": "a1b2c3d4",
    "resume_type": "feedback",   # feedback | accept | redo_artifact | skip
    "human_comment": "用例3需要增加异常流处理...",   # feedback 时必填
    "target_artifact": "data_flow_diagram",          # redo_artifact 时必填
    "prune_downstream": true                         # redo_artifact 时可选
}
```

**resume_type 说明**：

| resume_type | 含义 | CLI 等价 | 后续动作 |
|-------------|------|----------|----------|
| `accept` | 接受当前结果 | 用户输入空行 → `"no"` | 继续下一阶段 |
| `feedback` | 提供修改意见 | 用户输入文本 | `modify_agent()` → DAG 传播 → 重新生成 |
| `redo_artifact` | 重做指定 artifact | CLI 无此能力 | 重置 + 可选下游 → 重跑 |
| `skip` | 跳过当前阶段 | 用户输入 `"exit"` | 终止当前阶段 |

#### `GET /graph/stream/{project_id}`

SSE 端点，前端通过 `EventSource` 持续接收事件。

```typescript
const es = new EventSource("http://localhost:8000/graph/stream/a1b2c3d4");
es.onmessage = (e) => {
    const event = JSON.parse(e.data);
    // 根据 event.type 处理
};
```

**SSE 事件类型**：

| 事件类型 | 触发时机 | 前端处理 |
|----------|----------|----------|
| `connected` | SSE 连接建立 | 显示已连接 |
| `stage_start` | 进入新阶段 | 更新进度条 |
| `crew_start` | 每个 crew 开始 | 显示当前任务名 |
| `artifact_complete` | crew 执行成功 | 刷新 artifact 面板 |
| `interrupt` | 需要用户反馈（3 处） | 弹出审查窗口 |
| `feedback_processing` | `modify_agent()` 执行中 | 显示处理状态 |
| `srs_chapter` | Phase 5 每章完成 | 更新 SRS 进度 |
| `stage_complete` | 阶段所有 crew 完成 | 进度条推进 |
| `error` | 执行出错 | 显示错误 |
| `finished` | 5 个阶段全部完成 | 关闭 SSE |

**事件数据示例**：

```python
# stage_start
{"type": "stage_start", "stage": "meta_analysis", "stage_index": 1, "total_stages": 5}

# crew_start
{"type": "crew_start", "crew_name": "SurveyCrew", "artifact_name": "survey", "stage": "business_requirements"}

# artifact_complete
{"type": "artifact_complete", "artifact_name": "survey", "content_preview": "前200字..."}

# interrupt（3 个中断点）
{
    "type": "interrupt",
    "interrupt_type": "business_review",       # business_review | brd_review | elicitation_review
    "artifact_names": ["business_scope"],
    "message": "业务范围文档已生成，请审查并提供反馈",
    "content": {"business_scope": "完整 markdown..."},
    "options": ["accept", "feedback", "skip"]
}

# feedback_processing
{"type": "feedback_processing", "affected_artifacts": ["context_diagram", "event_list"]}

# srs_chapter
{"type": "srs_chapter", "chapter_index": 3, "chapter_title": "3. 系统功能需求", "total_chapters": 8}

# finished
{"type": "finished", "total_artifacts": 17, "srs_generated": true, "duration_seconds": 1800}

# error
{"type": "error", "crew_name": "SurveyCrew", "error": "API rate limit", "retry_count": 3, "recoverable": true}
```

---

### 3.4 Artifact 管理（3 个）

#### `GET /artifacts/{project_id}`

获取所有 artifact 列表，**自带 DAG 依赖数据**（前端自行构建可视化）。同时返回完成度统计（替代原独立的 progress 端点）。

```python
# 响应
{
    "project_id": "a1b2c3d4",
    "artifacts": [
        {
            "artifact_name": "survey",
            "display_name": "市场调研报告",
            "filename": "survey.md",
            "stage": "business_requirements",
            "status": "completed",         # completed | in_progress | pending | failed
            "content_preview": "## 市场调研报告\n\n### 1. 现有解决方案...",
            "version": 1,
            "dependencies": [],            # 我依赖谁
            "dependents": ["context_diagram", "feature_tree"]  # 谁依赖我
        },
        {
            "artifact_name": "context_diagram",
            "display_name": "上下文图",
            "filename": "draft_context_diagram.md",
            "stage": "business_requirements",
            "status": "in_progress",
            "content_preview": "",
            "version": 0,
            "dependencies": ["survey"],
            "dependents": ["event_list", "user_introduction", "use_case", "data_flow_diagram", "ERD"]
        }
    ],
    "total": 17,
    "completed": 7,
    "in_progress": 1,
    "pending": 9
}
```

前端用 `dependencies` + `dependents` 自行构建 DAG 可视化（React Flow / D3）：

```typescript
// 前端构建 nodes + edges
const nodes = artifacts.map(a => ({ id: a.artifact_name, label: a.display_name, status: a.status }));
const edges = artifacts.flatMap(a => a.dependencies.map(dep => ({ from: dep, to: a.artifact_name })));
```

#### `GET /artifacts/{project_id}/{artifact_name}`

获取单个 artifact 的完整 markdown 内容。

```python
# GET /artifacts/a1b2c3d4/survey
{
    "artifact_name": "survey",
    "display_name": "市场调研报告",
    "status": "completed",
    "content": "## 市场调研报告\n\n### 1. 现有解决方案\n...(完整内容)...",
    "version": 1,
    "dependencies": [],
    "dependents": ["context_diagram", "feature_tree"],
    "crew_name": "SurveyCrew",
    "execution_time_ms": 45000,
    "updated_at": "..."
}
```

#### `POST /artifacts/export_pdf`

将 artifact markdown 导出为 PDF 二进制流。

```python
# 请求
{ "project_id": "a1b2c3d4", "artifact_name": "SRS" }

# 响应: application/pdf 二进制流
```

---

### 3.5 文件上传（1 个统一入口）

#### `POST /files/upload`

统一处理所有文件上传场景，靠 `file_type` + `action` 区分。

**场景 1：上传数据文件**

```python
# multipart/form-data
# file: 二进制文件 (PDF/DOCX/图片/Excel)
# project_id: "a1b2c3d4"
# file_type: "data"

# 响应
{
    "file_id": "f1e2d3",
    "filename": "项目需求.pdf",
    "file_type": "data",
    "size_bytes": 102400,
    "parsed": true,
    "extracted_content_preview": "1. 项目背景\n本项目旨在..."
}
```

**场景 2：上传 SRS 模板并预览**

```python
# file: SRS 模板文件
# project_id: "a1b2c3d4"
# file_type: "template"

# 响应（预览结构）
{
    "status": "preview",
    "template_name": "IEEE_SRS_Template",
    "source_format": "pdf",
    "section_count": 12,
    "sections": [
        {
            "section_number": "1",
            "section_title": "引言",
            "subsections": [
                {"section_number": "1.1", "section_title": "目的"},
                {"section_number": "1.2", "section_title": "范围"}
            ]
        }
    ],
    "summary": "IEEE 标准 SRS 模板，共 12 章 45 节"
}
```

**场景 3：确认模板**

```python
# 不传 file
# project_id: "a1b2c3d4"
# file_type: "template"
# action: "confirm"

# 响应
{ "status": "confirmed", "template_name": "IEEE_SRS_Template" }
```

**场景 4：带反馈修改模板**

```python
# 不传 file
# project_id: "a1b2c3d4"
# file_type: "template"
# action: "revise"
# feedback: "第3章应拆分为功能需求和非功能需求"

# 响应（新的预览结构）
{ "status": "preview", "section_count": 13, "sections": [...] }
```

---

## 4. 数据库设计（MongoDB）

精简为 3 个 collection（删除 conversations 和 events，由前端 SSE 缓存处理）：

```javascript
// ===== projects =====
{
    _id: ObjectId,
    project_id: "a1b2c3d4",
    user_id: "user1",
    project_name: "自动化软件源代码审查平台",
    description: "项目描述...",
    srs_template: "IEEE",
    status: "running",
    current_stage: "business_requirements",
    current_crew: "SurveyCrew",
    config: {
        srs_example_path: "src/util/doc_template/document_example.md",
        data_files: ["f1e2d3"]
    },
    meta_result: {                 // MetaAnalysis 阶段输出缓存
        document_template: Binary,
        document_skeleton: "string",
        doc_planning: "string",
        chapter_dependence: "string",
        artifact_planing: [["survey"], ["context_diagram", "feature_tree"]]
    },
    created_at: ISODate,
    updated_at: ISODate
}

// ===== artifacts =====
{
    _id: ObjectId,
    artifact_id: "uuid",
    project_id: "a1b2c3d4",
    artifact_name: "survey",
    display_name: "市场调研报告",
    stage: "business_requirements",
    status: "completed",
    content: "完整 markdown...",
    content_pickle: Binary,
    version: 1,
    crew_name: "SurveyCrew",
    execution_time_ms: 45000,
    dependencies: [],
    dependents: ["context_diagram", "feature_tree"],
    created_at: ISODate,
    updated_at: ISODate
}

// ===== files =====
{
    _id: ObjectId,
    file_id: "f1e2d3",
    project_id: "a1b2c3d4",
    filename: "项目需求.pdf",
    file_type: "data",
    file_path: "dataset/uploads/a1b2c3d4/项目需求.pdf",
    extracted_content: "提取的文本...",
    size_bytes: 102400,
    uploaded_at: ISODate
}
```

---

## 5. 执行阶段与 Artifact 全景图

```
阶段 1: meta_analysis（元分析）— 无交互
  ├── ExtractDocumentCrew  → document_skeleton
  ├── DocContentCrew       → doc_content
  ├── ChapterDependenceCrew→ chapter_dependence
  └── ArtifactPlanningCrew → artifact_planning
  [SHA256 缓存]

阶段 2: business_requirements（业务需求）— 2 个中断点
  ├── SurveyCrew           → survey.md
  ├── DraftContentDiagramCrew → draft_context_diagram.md
  ├── DraftEventListCrew   → draft_event_list.md
  ├── UserIntroductionDev  → user_introduction.md
  ├── FeatureTreeDev       → feature_tree.md
  ├── BusinessScopeDev     → business_scope.md
  ├── ⚡ INTERRUPT: business_review
  ├── BRDev (3 chapters)   → BRD.md
  └── ⚡ INTERRUPT: brd_review

阶段 3: requirement_elicitation（需求获取）— 1 个中断点
  ├── UserCaseCrew         → use_case.md
  ├── NFRCrew              → non_functional_requirements.md
  └── ⚡ INTERRUPT: elicitation_review

阶段 4: requirement_analysis（需求分析）— 无交互 [DAG 拓扑排序]
  ├── DataFlowDiagramCrew  → data_flow_diagram.md
  ├── ERDCrew              → entity_relationship_diagram.md
  ├── DataDictionaryCrew   → data_dictionary.md
  ├── DialogMapCrew        → dialog_map.md
  └── FRCrew               → functional_requirements.md

阶段 4b: non_standard — 无交互
  ├── UsageScenarioCrew    → usage_scenario.md
  └── STDCrew              → state_transition_diagram.md

阶段 5: srs_generation（SRS 生成）— 无交互 [逐章]
  ├── SRSplaningCrew × N   → srs_planning.md
  ├── SRSev × N            → SRS chapters
  └── 汇总                  → SRS.md
```

---

## 6. 前端 API 调用封装（TypeScript）

```typescript
// frontend/src/api/reagent.ts

const BACKEND_URL = "http://localhost:8000";

// ===== 类型定义 =====

interface StreamEvent {
    type: "connected" | "stage_start" | "crew_start" | "artifact_complete"
        | "interrupt" | "feedback_processing" | "srs_chapter"
        | "stage_complete" | "error" | "finished";
    project_id: string;
    timestamp: string;
    [key: string]: any;
}

type ResumeType = "feedback" | "accept" | "redo_artifact" | "skip";

// ===== 项目管理 =====

export const createProject = (data: {
    user_id: string;
    project_name: string;
    description: string;
    srs_template?: "IEEE" | "Initial";
}) =>
    fetch(`${BACKEND_URL}/project/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    }).then(r => r.json());

export const fetchProjectList = (userId: string) =>
    fetch(`${BACKEND_URL}/project/list/${userId}`).then(r => r.json());

export const fetchProject = (projectId: string) =>
    fetch(`${BACKEND_URL}/project/${projectId}`).then(r => r.json());

export const deleteProject = (projectId: string) =>
    fetch(`${BACKEND_URL}/project/${projectId}`, { method: "DELETE" }).then(r => r.json());

// ===== 流式执行 =====

export const startExecution = (data: {
    project_id: string;
    user_id: string;
    human_request?: string;
    start_from?: string;
}) =>
    fetch(`${BACKEND_URL}/graph/stream/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    }).then(r => r.json());

export const resumeExecution = (data: {
    project_id: string;
    resume_type: ResumeType;
    human_comment?: string;
    target_artifact?: string;
    prune_downstream?: boolean;
}) =>
    fetch(`${BACKEND_URL}/graph/stream/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    }).then(r => r.json());

export function subscribeStream(
    projectId: string,
    onEvent: (event: StreamEvent) => void,
    onError?: (error: Error) => void
): EventSource {
    const es = new EventSource(`${BACKEND_URL}/graph/stream/${projectId}`);
    es.onmessage = (e) => {
        const data: StreamEvent = JSON.parse(e.data);
        onEvent(data);
        if (data.type === "finished" || (data.type === "error" && !data.recoverable)) {
            es.close();
        }
    };
    es.onerror = () => {
        onError?.(new Error("SSE connection lost"));
        es.close();
    };
    return es;
}

// ===== Artifact =====

export const fetchArtifacts = (projectId: string) =>
    fetch(`${BACKEND_URL}/artifacts/${projectId}`).then(r => r.json());

export const fetchArtifactContent = (projectId: string, name: string) =>
    fetch(`${BACKEND_URL}/artifacts/${projectId}/${name}`).then(r => r.json());

export const exportPdf = (projectId: string, artifactName: string): Promise<Blob> =>
    fetch(`${BACKEND_URL}/artifacts/export_pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, artifact_name: artifactName }),
    }).then(r => r.blob());

// ===== 文件上传 =====

export const uploadFile = (projectId: string, file: File, fileType: string, action?: string, feedback?: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("project_id", projectId);
    form.append("file_type", fileType);
    if (action) form.append("action", action);
    if (feedback) form.append("feedback", feedback);
    return fetch(`${BACKEND_URL}/files/upload`, { method: "POST", body: form }).then(r => r.json());
};

// 模板确认（不传 file）
export const confirmTemplate = (projectId: string) => {
    const form = new FormData();
    form.append("project_id", projectId);
    form.append("file_type", "template");
    form.append("action", "confirm");
    return fetch(`${BACKEND_URL}/files/upload`, { method: "POST", body: form }).then(r => r.json());
};

// 模板修改（不传 file）
export const reviseTemplate = (projectId: string, feedback: string) => {
    const form = new FormData();
    form.append("project_id", projectId);
    form.append("file_type", "template");
    form.append("action", "revise");
    form.append("feedback", feedback);
    return fetch(`${BACKEND_URL}/files/upload`, { method: "POST", body: form }).then(r => r.json());
};
```

---

## 7. 前端页面与 API 映射

| 前端页面/组件 | 调用的 API | 交互模式 |
|--------------|------------|----------|
| **侧边栏项目列表** | `GET /project/list/{user_id}` | 页面加载时拉取 |
| **新建项目对话框** | `POST /project/create` | 表单提交 |
| **项目概览页** | `GET /project/{id}` | 进入时拉取 |
| **启动执行按钮** | `POST /graph/stream/create` → `GET /graph/stream/{id}` | 点击后启动 SSE |
| **执行进度面板** | SSE 事件 | 实时更新 |
| **DAG 依赖图** | `GET /artifacts/{id}` 的 dependencies/dependents | 前端自行构建 |
| **Artifact 列表** | `GET /artifacts/{id}` | SSE artifact_complete 时刷新 |
| **Artifact 详情** | `GET /artifacts/{id}/{name}` | 点击查看 |
| **审查反馈弹窗** | SSE `interrupt` → `POST /graph/stream/resume` | 中断时弹出 |
| **文件上传区** | `POST /files/upload` | 拖拽/选择 |
| **PDF 导出按钮** | `POST /artifacts/export_pdf` | 点击下载 |
| **对话历史** | 前端缓存 SSE 事件 | 本地构建，无需 API |

---

## 8. Artifact 名称对照表

| artifact_name | 显示名 | 文件名 | 依赖 |
|---------------|--------|--------|------|
| `survey` | 市场调研报告 | survey.md | — |
| `context_diagram` | 上下文图 | draft_context_diagram.md | survey |
| `event_list` | 事件列表 | draft_event_list.md | context_diagram |
| `user_introduction` | 用户介绍 | user_introduction.md | context_diagram |
| `feature_tree` | 功能树 | feature_tree.md | survey |
| `business_scope` | 业务范围 | business_scope.md | feature_tree |
| `BRD` | 业务需求文档 | BRD.md | user_introduction, feature_tree, event_list, business_scope |
| `use_case` | 用例 | use_case.md | event_list, user_introduction, context_diagram |
| `non_functional_requirements` | 非功能需求 | non_functional_requirements.md | BRD |
| `functional_requirements` | 功能需求 | functional_requirements.md | use_case |
| `data_flow_diagram` | 数据流图 | data_flow_diagram.md | context_diagram, use_case |
| `ERD` | 实体关系图 | entity_relationship_diagram.md | data_flow_diagram, context_diagram |
| `data_dictionary` | 数据字典 | data_dictionary.md | ERD |
| `dialog_map` | 对话图 | dialog_map.md | use_case |
| `state_transition_diagram` | 状态转换图 | state_transition_diagram.md | use_case |
| `usage_scenario` | 使用场景 | usage_scenario.md | use_case |
| `SRS` | 软件需求规格说明书 | SRS.md | 所有上述 artifact |

---

## 9. 启动方式

```bash
# 1. 安装依赖
pip install fastapi==0.115.12 uvicorn[standard]==0.34.3 \
    sse-starlette==3.0.3 motor==3.7.0 python-multipart

# 2. 启动 MongoDB
docker run -d -p 27017:27017 --name reagent-mongo mongo:7

# 3. 配置 .env
OPENAI_KEY=sk-...
OPENAI_MODEL=o1
MONGODB_URI=mongodb://localhost:27017
DB_NAME=reagent

# 4. 启动后端
python main.py serve --host 0.0.0.0 --port 8000 --reload

# 5. 启动前端
cd frontend && npm run dev

# API 文档: http://localhost:8000/docs
```
