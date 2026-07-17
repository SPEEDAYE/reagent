# REagent 1.0 前端对接指南

## 一、API 调用时序

```
1. POST /project/create          → 获取 project_id
2. POST /files/upload (可选)      → 上传数据文件
3. POST /graph/stream/create     → 启动流水线
4. GET  /graph/stream/{pid}      → SSE 长连接（实时监听）
   ├─ event: stage_start         → 更新进度条
   ├─ event: crew_start          → 显示当前任务
   ├─ event: artifact_complete   → 标记制品完成
   ├─ event: interrupt           → 弹出审核对话框
   │   └─ POST /graph/stream/resume  → 提交反馈（恢复流水线）
   ├─ event: error               → 显示错误提示
   ├─ event: completed           → 跳转到结果页（成功终态）
   └─ event: finished            → 兼容旧客户端的成功终态
5. GET  /artifacts/{pid}         → 获取制品列表+DAG
6. GET  /artifacts/{pid}/{name}  → 查看制品内容
7. POST /artifacts/export_pdf    → 导出 PDF
```

## 二、SSE 连接关键实现

### 2.1 建立 SSE 连接

```typescript
// 使用浏览器原生 EventSource
const BASE_URL = "http://localhost:8000";

function connectSSE(projectId: string, handlers: SSEHandlers) {
  const es = new EventSource(`${BASE_URL}/graph/stream/${projectId}`);

  // 每种事件类型单独监听
  es.addEventListener("connected", (e) => {
    handlers.onConnected?.(JSON.parse(e.data));
  });

  es.addEventListener("stage_start", (e) => {
    handlers.onStageStart?.(JSON.parse(e.data));
  });

  es.addEventListener("crew_start", (e) => {
    handlers.onCrewStart?.(JSON.parse(e.data));
  });

  es.addEventListener("artifact_complete", (e) => {
    handlers.onArtifactComplete?.(JSON.parse(e.data));
  });

  es.addEventListener("interrupt", (e) => {
    // 关键：收到 interrupt 后需要用户操作
    handlers.onInterrupt?.(JSON.parse(e.data));
  });

  es.addEventListener("stage_complete", (e) => {
    handlers.onStageComplete?.(JSON.parse(e.data));
  });

  es.addEventListener("error", (e) => {
    const data = JSON.parse(e.data);
    if (!data.recoverable) {
      es.close(); // 致命错误关闭连接
    }
    handlers.onError?.(data);
  });

  const handleSuccess = (e: MessageEvent) => {
    es.close(); // 流水线完成，关闭 SSE
    handlers.onFinished?.(JSON.parse(e.data));
  };
  es.addEventListener("completed", handleSuccess);
  es.addEventListener("finished", handleSuccess);

  // 连接级别错误（网络断开等）
  es.onerror = () => {
    handlers.onConnectionError?.();
  };

  return es; // 返回以便外部可以 es.close()
}

// 类型定义
interface SSEHandlers {
  onConnected?: (data: any) => void;
  onStageStart?: (data: StageEvent) => void;
  onCrewStart?: (data: CrewEvent) => void;
  onArtifactComplete?: (data: ArtifactEvent) => void;
  onInterrupt?: (data: InterruptEvent) => void;
  onStageComplete?: (data: StageEvent) => void;
  onError?: (data: ErrorEvent) => void;
  onFinished?: (data: FinishedEvent) => void;
  onConnectionError?: () => void;
}

interface StageEvent {
  type: string;
  project_id: string;
  stage: string;
  stage_index: number;
  total_stages: number;
  stage_label: string;
}

interface InterruptEvent {
  type: "interrupt";
  project_id: string;
  interrupt_type: "business_review" | "brd_review" | "elicitation_review";
  artifact_names: string[];
  message: string;
  options: ("accept" | "feedback" | "skip")[];
}

interface FinishedEvent {
  type: "completed" | "finished";
  status?: "completed";
  total_artifacts: number;
  srs_generated: boolean;
}
```

### 2.2 处理中断（核心交互）

流水线有 3 个中断点，前端收到 `interrupt` 事件后必须让用户操作，然后 POST 反馈：

```typescript
async function handleInterrupt(data: InterruptEvent, projectId: string) {
  // 1. 弹出审核对话框，显示相关制品内容
  //    可以先用 GET /artifacts/{pid}/{name} 获取制品预览

  // 2. 等待用户选择
  //    - "通过" → resume_type = "accept"
  //    - "修改" → resume_type = "feedback", 附带修改意见
  //    - "跳过" → resume_type = "skip"

  // 3. 提交反馈
  const response = await fetch(`${BASE_URL}/graph/stream/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      resume_type: "accept",        // 或 "feedback" / "skip"
      human_comment: "没问题，继续",  // feedback 时填写
    }),
  });
  // 提交后 SSE 会继续推送后续事件，不需要额外操作
}
```

### 2.3 三个中断点的 UI 设计建议

| 中断点 | interrupt_type | 展示内容 | 用户操作 |
|--------|---------------|---------|---------|
| 1. 业务范围审核 | `business_review` | `business_scope.md` 内容 | 通过/提修改意见/跳过 |
| 2. BRD 审核 | `brd_review` | `BRD.md` 全文（重点关注 2.1 章） | 通过/提修改意见/跳过 |
| 3. 需求获取审核 | `elicitation_review` | `use_case.md` + `non_functional_requirements.md` | 通过/提修改意见/跳过 |

收到中断时可先调 API 获取制品内容供用户审阅：

```typescript
// 获取制品内容供审阅
async function fetchArtifactForReview(projectId: string, artifactName: string) {
  const resp = await fetch(`${BASE_URL}/artifacts/${projectId}/${artifactName}`);
  const data = await resp.json();
  return data.content; // Markdown 格式的文本
}
```

## 三、完整页面流程实现

### 3.1 创建项目页面

```typescript
async function createProject(name: string, description: string) {
  const resp = await fetch(`${BASE_URL}/project/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: getCurrentUserId(),
      project_name: name,
      description: description,
      // srs_template: "Initial",  // 可选: "IEEE" 或 "Initial"
    }),
  });
  const { project_id } = await resp.json();
  return project_id;
}
```

### 3.2 上传文件（可选）

```typescript
async function uploadDataFile(projectId: string, file: File) {
  const formData = new FormData();
  formData.append("project_id", projectId);
  formData.append("file_type", "data");
  formData.append("file", file);

  const resp = await fetch(`${BASE_URL}/files/upload`, {
    method: "POST",
    body: formData,
  });
  return resp.json();
}
```

### 3.3 启动流水线 + 监听

```typescript
async function startPipeline(projectId: string, extraRequest?: string) {
  // 启动
  await fetch(`${BASE_URL}/graph/stream/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      user_id: getCurrentUserId(),
      human_request: extraRequest,
    }),
  });

  // 立即建立 SSE 连接
  const eventSource = connectSSE(projectId, {
    onStageStart: (data) => {
      updateProgressBar(data.stage_index, data.total_stages, data.stage_label);
    },
    onCrewStart: (data) => {
      showStatus(`正在执行: ${data.crew_name}`);
    },
    onArtifactComplete: (data) => {
      markArtifactDone(data.crew_name);
    },
    onInterrupt: (data) => {
      showReviewDialog(data, projectId);
    },
    onStageComplete: (data) => {
      showStatus(`阶段完成: ${data.stage}`);
    },
    onError: (data) => {
      if (data.recoverable) {
        showWarning(`可恢复错误: ${data.error}`);
      } else {
        showError(`流水线错误: ${data.error}`);
      }
    },
    onFinished: (data) => {
      showSuccess(`完成！共生成 ${data.total_artifacts} 个制品`);
      navigateToResults(projectId);
    },
    onConnectionError: () => {
      showWarning("连接中断，尝试重连...");
      // SSE 浏览器原生 EventSource 会自动重连
    },
  });
}
```

### 3.4 审核对话框

```typescript
async function showReviewDialog(interrupt: InterruptEvent, projectId: string) {
  // 1. 获取待审阅制品内容
  const contents: Record<string, string> = {};
  for (const name of interrupt.artifact_names) {
    const resp = await fetch(`${BASE_URL}/artifacts/${projectId}/${name}`);
    const data = await resp.json();
    contents[name] = data.content;
  }

  // 2. 弹出对话框（伪代码，按你的 UI 框架实现）
  const dialog = openDialog({
    title: interrupt.message,
    content: contents,              // Markdown 渲染展示
    actions: [
      { label: "通过", value: "accept" },
      { label: "提交修改意见", value: "feedback", hasInput: true },
      { label: "跳过", value: "skip" },
    ],
  });

  // 3. 等待用户操作
  const { action, comment } = await dialog.waitForAction();

  // 4. 提交反馈
  await fetch(`${BASE_URL}/graph/stream/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      resume_type: action,
      human_comment: comment || undefined,
    }),
  });
  // SSE 会自动继续推送后续事件
}
```

### 3.5 结果页面（制品列表 + DAG 可视化）

```typescript
async function loadResults(projectId: string) {
  // 获取所有制品 + DAG 关系
  const resp = await fetch(`${BASE_URL}/artifacts/${projectId}`);
  const data = await resp.json();

  // data 结构:
  // {
  //   project_id: "xxx",
  //   total: 17,
  //   completed: 17,
  //   pending: 0,
  //   artifacts: [
  //     {
  //       artifact_name: "survey",
  //       display_name: "市场调研报告",
  //       status: "completed",
  //       content_preview: "前200字...",
  //       dependencies: [],
  //       dependents: ["context_diagram", "feature_tree", ...]
  //     },
  //     ...
  //   ]
  // }

  // 渲染制品列表
  renderArtifactList(data.artifacts);

  // 渲染 DAG 可视化（用 D3.js / vis.js / mermaid 等）
  renderDAG(data.artifacts);
}

// 查看单个制品详情
async function viewArtifact(projectId: string, name: string) {
  const resp = await fetch(`${BASE_URL}/artifacts/${projectId}/${name}`);
  const data = await resp.json();
  // data.content 是 Markdown 文本，用 markdown 渲染库显示
  renderMarkdown(data.content);
}

// 导出 PDF
async function exportPDF(projectId: string, artifactName: string) {
  const resp = await fetch(`${BASE_URL}/artifacts/export_pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      artifact_name: artifactName,
    }),
  });
  if (resp.headers.get("content-type")?.includes("pdf")) {
    const blob = await resp.blob();
    downloadBlob(blob, `${artifactName}.pdf`);
  }
}
```

## 四、前端状态管理建议

```typescript
// 项目执行状态
interface PipelineState {
  status: "idle" | "running" | "interrupted" | "completed" | "finished" | "error";
  currentStage: string | null;       // 当前阶段名
  stageIndex: number;                // 第几阶段 (1-6)
  totalStages: number;               // 总阶段数 (6)
  currentCrew: string | null;        // 当前执行的 Crew
  completedArtifacts: string[];      // 已完成的制品名列表
  interrupt: InterruptEvent | null;  // 当前中断数据（如果处于审核状态）
  error: string | null;
}

// 根据 SSE 事件更新状态
function reduceSSEEvent(state: PipelineState, event: any): PipelineState {
  switch (event.type) {
    case "stage_start":
      return {
        ...state,
        status: "running",
        currentStage: event.stage,
        stageIndex: event.stage_index,
        totalStages: event.total_stages,
        interrupt: null,
      };

    case "crew_start":
      return { ...state, currentCrew: event.crew_name };

    case "artifact_complete":
      return {
        ...state,
        completedArtifacts: [...state.completedArtifacts, event.crew_name],
      };

    case "interrupt":
      return { ...state, status: "interrupted", interrupt: event };

    case "stage_complete":
      return { ...state, currentCrew: null };

    case "error":
      return {
        ...state,
        status: event.recoverable ? state.status : "error",
        error: event.error,
      };

    case "completed":
      return { ...state, status: "completed", currentStage: null };

    case "finished":
      return {
        ...state,
        status: event.status === "completed" ? "completed" : "finished",
        currentStage: null,
      };

    default:
      return state;
  }
}
```

## 五、关键注意事项

### 5.1 SSE 连接稳定性

```typescript
// EventSource 原生支持自动重连，但有些情况需要手动处理
function createRobustSSE(projectId: string, handlers: SSEHandlers) {
  let es: EventSource;
  let retryCount = 0;
  const MAX_RETRIES = 5;

  function connect() {
    es = connectSSE(projectId, {
      ...handlers,
      onConnected: (data) => {
        retryCount = 0; // 连接成功重置计数
        handlers.onConnected?.(data);
      },
    });

    es.onerror = () => {
      if (retryCount < MAX_RETRIES) {
        retryCount++;
        setTimeout(connect, 3000 * retryCount); // 递增重连延迟
      } else {
        handlers.onConnectionError?.();
      }
    };
  }

  connect();
  return { close: () => es?.close() };
}
```

### 5.2 Nginx 反代 SSE 配置（必须）

前端通过 nginx 访问时，nginx 必须关闭缓冲，否则 SSE 事件会堆积：

```nginx
location /reagent/ {
    rewrite ^/reagent/(.*) /$1 break;
    proxy_pass http://127.0.0.1:8000;

    # SSE 必须配置
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;  # 流水线可能跑 30+ 分钟
}
```

### 5.3 跨域 (CORS)

后端已配置 `CORS_ORIGINS: ["*"]`，开发阶段前端任意域名都可以访问。生产环境建议改为具体域名。

### 5.4 流水线运行时间

完整流水线（6 阶段 17 个制品）耗时约 **20-40 分钟**（取决于 LLM 响应速度）。前端需要：
- 显示持续的进度指示（不要用短超时的 loading spinner）
- SSE 连接保持打开整个过程
- 处理网络断开后的重连和状态恢复

### 5.5 制品内容渲染

所有制品内容是 **Markdown 格式**，部分包含 **Mermaid 图表**（上下文图、DFD、ERD、状态转换图、对话图）。前端需要：
- Markdown 渲染库（如 `react-markdown`、`marked`）
- Mermaid 图表渲染（如 `mermaid.js`）

## 六、推荐技术栈

| 层面 | 推荐 | 说明 |
|------|------|------|
| 框架 | React / Vue 3 | 状态管理 SSE 事件 |
| SSE 客户端 | 浏览器原生 `EventSource` | 自带重连 |
| Markdown 渲染 | react-markdown + remark-gfm | 支持表格、代码块 |
| Mermaid 图表 | mermaid.js | 渲染 DFD、ERD 等图 |
| DAG 可视化 | vis-network / d3-dag / reactflow | 制品依赖关系图 |
| HTTP 客户端 | fetch / axios | API 调用 |
| 状态管理 | zustand / pinia | 轻量级状态管理 |
