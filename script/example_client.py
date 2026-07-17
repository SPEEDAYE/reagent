"""
REagent 1.0 API 调用示例

完整演示：创建项目 → 上传数据 → 启动流水线 → 监听 SSE → 处理审核中断 → 查看制品

使用前：
    pip install requests sseclient-py

配置：
    修改下方 BASE_URL 为你的服务器地址
"""

import requests
import json
import time
import sys

# ======================== 配置 ========================
BASE_URL = "http://localhost:8000"   # 通过 SSH 隧道访问内部端口
USER_ID = "demo_user"

# ======================== 工具函数 ========================

def api(method, path, **kwargs):
    """统一请求封装，自动打印结果"""
    url = f"{BASE_URL}{path}"
    resp = getattr(requests, method)(url, **kwargs)
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
    print(f"\n{'='*60}")
    print(f"{method.upper()} {path}")
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, (dict, list)) else data}")
    print(f"{'='*60}")
    return data


# ======================== 1. 健康检查 ========================

def check_health():
    """检查 API 是否正常运行"""
    print("\n>>> Step 1: 健康检查")
    data = api("get", "/health")
    if data.get("status") != "healthy":
        print("API 不健康，请检查服务器！")
        sys.exit(1)
    print("API 运行正常 ✓")
    return data


# ======================== 2. 项目管理 ========================

def create_project(name: str, description: str, srs_template: str = "Initial"):
    """创建新项目"""
    print(f"\n>>> Step 2: 创建项目 [{name}]")
    data = api("post", "/project/create", json={
        "user_id": USER_ID,
        "project_name": name,
        "description": description,
        "srs_template": srs_template,     # "IEEE" 或 "Initial"
    })
    project_id = data.get("project_id")
    print(f"项目 ID: {project_id}")
    return project_id


def list_projects():
    """列出当前用户的所有项目"""
    print("\n>>> 列出所有项目")
    return api("get", f"/project/list/{USER_ID}")


def get_project(project_id: str):
    """获取项目详情"""
    return api("get", f"/project/{project_id}")


def delete_project(project_id: str):
    """删除项目"""
    return api("delete", f"/project/{project_id}")


# ======================== 3. 文件上传 ========================

def upload_data_file(project_id: str, file_path: str):
    """上传项目数据文件（PDF/Word/图片等）"""
    print(f"\n>>> Step 3: 上传数据文件 [{file_path}]")
    with open(file_path, "rb") as f:
        return api("post", "/files/upload",
            data={"project_id": project_id, "file_type": "data"},
            files={"file": f},
        )


def upload_srs_template(project_id: str, file_path: str):
    """上传自定义 SRS 模板"""
    print(f"\n>>> 上传 SRS 模板 [{file_path}]")
    with open(file_path, "rb") as f:
        return api("post", "/files/upload",
            data={"project_id": project_id, "file_type": "template"},
            files={"file": f},
        )


# ======================== 4. 启动流水线 ========================

def start_pipeline(project_id: str, extra_request: str = None):
    """启动 RE 流水线"""
    print(f"\n>>> Step 4: 启动流水线 [project={project_id}]")
    body = {
        "project_id": project_id,
        "user_id": USER_ID,
    }
    if extra_request:
        body["human_request"] = extra_request
    return api("post", "/graph/stream/create", json=body)


# ======================== 5. 监听 SSE 事件流 ========================

def listen_sse(project_id: str, auto_approve: bool = False):
    """
    监听 SSE 实时事件流

    参数:
        project_id: 项目 ID
        auto_approve: True 时自动通过所有审核中断，False 时等待手动输入
    """
    print(f"\n>>> Step 5: 监听 SSE 事件流 [project={project_id}]")
    print("(Ctrl+C 可随时退出监听)\n")

    try:
        # sseclient-py 方式
        import sseclient
        resp = requests.get(
            f"{BASE_URL}/graph/stream/{project_id}",
            stream=True,
            headers={"Accept": "text/event-stream"},
        )
        client = sseclient.SSEClient(resp)

        for event in client.events():
            data = json.loads(event.data)
            event_type = data.get("type", event.event)
            timestamp = data.get("timestamp", "")

            # 格式化输出
            print(f"[{timestamp}] {event_type}", end="")

            if event_type == "connected":
                print(f" - 连接成功")

            elif event_type == "stage_start":
                label = data.get('stage_label', data.get('stage', ''))
                idx = data.get('stage_index', '?')
                total = data.get('total_stages', '?')
                print(f" - 阶段开始: {label} ({idx}/{total})")

            elif event_type == "crew_start":
                print(f" - Crew 执行中: {data.get('crew_name', '')}")

            elif event_type == "artifact_complete":
                print(f" - 制品完成: {data.get('crew_name', '')}")

            elif event_type == "interrupt":
                # 审核中断点
                artifacts = data.get("artifact_names", [])
                message = data.get("message", "")
                options = data.get("options", [])
                print(f" - 需要审核: {', '.join(artifacts)}")
                print(f"  提示: {message}")
                print(f"  可选操作: {options}")

                if auto_approve:
                    print("  [自动通过]")
                    submit_feedback(project_id, "accept", "自动通过")
                else:
                    print("\n  请选择操作:")
                    print("    1. accept   - 通过，继续执行")
                    print("    2. feedback  - 提供修改意见")
                    print("    3. skip     - 跳过此制品")
                    choice = input("  输入选项 (1/2/3): ").strip()

                    if choice == "2":
                        comment = input("  输入修改意见: ").strip()
                        submit_feedback(project_id, "feedback", comment)
                    elif choice == "3":
                        submit_feedback(project_id, "skip")
                    else:
                        submit_feedback(project_id, "accept", "确认通过")

            elif event_type == "srs_chapter":
                print(f" - SRS 章节完成: {data.get('chapter', '')}")

            elif event_type == "stage_complete":
                print(f" - 阶段完成: {data.get('stage', '')}")

            elif event_type == "error":
                recoverable = data.get("recoverable", False)
                print(f" - {'可恢复错误' if recoverable else '致命错误'}: {data.get('error', '')}")
                if not recoverable:
                    print("\n流水线因错误终止。")
                    break

            elif event_type in ("completed", "finished"):
                print(f" - 流水线全部完成!")
                break

            else:
                print(f" - {json.dumps(data, ensure_ascii=False)}")

    except ImportError:
        # 如果没有 sseclient，用原始方式解析
        print("(sseclient 未安装，使用原始 HTTP 流解析)")
        print("(建议安装: pip install sseclient-py)\n")
        _listen_sse_raw(project_id)

    except KeyboardInterrupt:
        print("\n\n已退出监听。流水线仍在后台运行。")


def _listen_sse_raw(project_id: str):
    """原始 HTTP 流方式解析 SSE（不依赖 sseclient）"""
    resp = requests.get(
        f"{BASE_URL}/graph/stream/{project_id}",
        stream=True,
        headers={"Accept": "text/event-stream"},
    )
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data:"):
            raw = line[len("data:"):].strip()
            try:
                data = json.loads(raw)
                event_type = data.get("type", "unknown")
                print(f"[{event_type}] {json.dumps(data, ensure_ascii=False)}")
                if event_type in ("completed", "finished", "error") and not data.get("recoverable"):
                    break
            except json.JSONDecodeError:
                print(f"[raw] {raw}")


# ======================== 6. 提交审核反馈 ========================

def submit_feedback(project_id: str, resume_type: str, comment: str = None,
                    target_artifact: str = None):
    """
    提交审核反馈

    resume_type 可选值:
        - "accept"        通过，继续执行
        - "feedback"      提供修改意见（需填 comment）
        - "redo_artifact"  重做某个制品（需填 target_artifact）
        - "skip"          跳过当前制品
    """
    print(f"\n>>> 提交反馈: {resume_type}")
    body = {
        "project_id": project_id,
        "resume_type": resume_type,
    }
    if comment:
        body["human_comment"] = comment
    if target_artifact:
        body["target_artifact"] = target_artifact
    return api("post", "/graph/stream/resume", json=body)


# ======================== 7. 查看制品 ========================

def list_artifacts(project_id: str):
    """列出所有制品 + DAG 依赖关系 + 进度"""
    print(f"\n>>> Step 6: 查看制品列表")
    return api("get", f"/artifacts/{project_id}")


def get_artifact_content(project_id: str, artifact_name: str):
    """
    获取单个制品的完整内容

    artifact_name 可选值:
        survey, context_diagram, event_list, user_introduction,
        feature_tree, business_scope, BRD, use_case,
        non_functional_requirements, functional_requirements,
        data_flow_diagram, ERD, data_dictionary, dialog_map,
        state_transition_diagram, usage_scenario, SRS
    """
    print(f"\n>>> 获取制品: {artifact_name}")
    return api("get", f"/artifacts/{project_id}/{artifact_name}")


def export_pdf(project_id: str, artifact_name: str, save_path: str = None):
    """导出制品为 PDF 并保存到本地"""
    print(f"\n>>> 导出 PDF: {artifact_name}")
    resp = requests.post(f"{BASE_URL}/artifacts/export_pdf", json={
        "project_id": project_id,
        "artifact_name": artifact_name,
    })
    if resp.headers.get("content-type", "").startswith("application/pdf"):
        save_path = save_path or f"{artifact_name}.pdf"
        with open(save_path, "wb") as f:
            f.write(resp.content)
        print(f"PDF 已保存: {save_path}")
    else:
        print(f"导出失败: {resp.text}")


# ======================== 完整流程示例 ========================

def full_demo():
    """
    完整演示：从创建项目到生成 SRS
    """
    print("=" * 60)
    print("  REagent 1.0 API 完整流程演示")
    print("=" * 60)

    # 1. 健康检查
    check_health()

    # 2. 创建项目
    project_id = create_project(
        name="教授个人主页网站",
        description="为刘洋教授构建一个学术个人主页网站，展示研究方向、论文列表、团队成员、课程信息等",
        srs_template="Initial",
    )

    # 3. 上传数据文件（可选，如果有参考资料）
    # upload_data_file(project_id, "dataset/samples/CV_LiuYang.pdf")

    # 4. 启动流水线
    start_pipeline(project_id, extra_request="需要支持中英文双语切换")

    # 5. 监听 SSE 事件（auto_approve=True 自动通过所有审核）
    #    改为 False 可手动审核
    listen_sse(project_id, auto_approve=True)

    # 6. 查看生成的制品
    artifacts = list_artifacts(project_id)

    # 7. 获取 BRD 和 SRS 内容
    get_artifact_content(project_id, "BRD")
    get_artifact_content(project_id, "SRS")

    # 8. 导出 PDF（可选）
    # export_pdf(project_id, "SRS", "SRS_output.pdf")

    print("\n" + "=" * 60)
    print("  演示完成!")
    print(f"  项目 ID: {project_id}")
    print(f"  可继续调用 API 查看制品或导出文档")
    print("=" * 60)


# ======================== 单独调用示例 ========================

def quick_examples():
    """
    各接口的独立调用示例（不运行完整流程）
    """
    def step(name, resp):
        data = resp.json()
        status = "OK" if resp.status_code == 200 else f"FAIL({resp.status_code})"
        preview = json.dumps(data, ensure_ascii=False)
        if len(preview) > 200:
            preview = preview[:200] + "..."
        print(f"  [{status}] {name}: {preview}")
        return data

    print(f"Quick API Test @ {BASE_URL}\n")

    # ----- 健康检查 -----
    step("Health", requests.get(f"{BASE_URL}/health"))

    # ----- 创建项目 -----
    resp = requests.post(f"{BASE_URL}/project/create", json={
        "user_id": "test",
        "project_name": "quick_test",
        "description": "快速测试项目",
    })
    pid = step("Create Project", resp).get("project_id")

    # ----- 列出项目 -----
    step("List Projects", requests.get(f"{BASE_URL}/project/list/test"))

    # ----- 获取项目 -----
    step("Get Project", requests.get(f"{BASE_URL}/project/{pid}"))

    # ----- 查看制品（流水线未跑，应为空）-----
    step("List Artifacts", requests.get(f"{BASE_URL}/artifacts/{pid}"))

    # ----- 删除项目 -----
    step("Delete Project", requests.delete(f"{BASE_URL}/project/{pid}"))

    print(f"\nAll done.")


# ======================== 入口 ========================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_examples()
    else:
        full_demo()
