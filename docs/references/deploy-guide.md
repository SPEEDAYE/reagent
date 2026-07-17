# REagent 1.0 UI 部署指南

## 目录

- [当前部署状态](#当前部署状态)
- [服务器信息](#服务器信息)
- [环境要求](#环境要求)
- [一键部署（推荐）](#一键部署推荐)
- [手动部署](#手动部署)
- [部署后必做事项](#部署后必做事项)
- [本地访问（SSH 隧道）](#本地访问ssh-隧道)
- [外网访问（待配置）](#外网访问待配置)
- [日常运维](#日常运维)
- [API 使用说明](#api-使用说明)
- [常见问题排查](#常见问题排查)
- [部署后目录结构](#部署后目录结构)

---

## 当前部署状态

> 最后更新：2026-04-05

| 项目 | 状态 |
|------|------|
| API 服务 | 运行中，监听 `0.0.0.0:8000` |
| Nginx 反代 | 虚拟机上 nginx 端口 `9998`，转发到 `8000` |
| MongoDB | 运行中，认证已关闭（仅绑定 127.0.0.1） |
| LLM 后端 | DeepSeek (`deepseek-chat`) |
| 部署路径 | `/home/carl/reagent/` |
| 多项目隔离 | 已实现，制品存储在 `experiment/{project_id}/` |
| 外网访问 | 待网关配置 nginx 9998 → 192.168.1.101:8000 |

**本地访问方式**：通过 SSH 隧道将 8000 端口映射到本地，然后访问 `http://localhost:8000`。

---

## 服务器信息

### 网络架构

```
用户 → se.aiseclab.cn (122.51.195.198 网关) → nginx:9998 → 内网机 192.168.1.101:8000
```

### SSH 连接

| 项目 | 值 |
|------|-----|
| 地址 | `se.aiseclab.cn` |
| 网关 IP | `122.51.195.198` |
| 内网 IP | `192.168.1.101` |
| SSH 端口 | `10122` |
| 用户名 | `carl` |
| 密码 | `2wsx@WSX#EDC` |

```bash
sshpass -p '2wsx@WSX#EDC' ssh -p 10122 carl@se.aiseclab.cn
```

### 宝塔面板

| 项目 | 值 |
|------|-----|
| 面板地址 | `https://122.51.195.198:21748/67cbe54c` |
| 用户名 | `jsdftnvg` |
| 密码 | `2f0561a2` |

### 已安装的服务

| 服务 | 端口 | 说明 |
|------|------|------|
| MongoDB 8.0 | 27017 | 仅绑定 127.0.0.1，认证已关闭 |
| MySQL | 3306 | 已安装（本项目未使用） |
| Redis | 6379 | 已安装（本项目未使用） |
| Nginx 1.28 | 80 | 宝塔管理，**留给其他服务** |

### 当前 .env 配置

```ini
OPENAI_KEY=sk-26584f4627504243983a3859d5c088ec
OPENAI_API_KEY=sk-26584f4627504243983a3859d5c088ec
OPENAI_MODEL=deepseek-chat
# OPENAI_BASE_URL=https://api.deepseek.com/v1
MONGODB_URI=mongodb://localhost:27017
DB_NAME=reagent
```

---

## 环境要求

### 本地机器（执行部署脚本的机器）

| 依赖 | 安装方式 |
|------|----------|
| sshpass | `sudo apt install sshpass` |
| pip | 当前 Python 环境需有 pip |

### 远程服务器

| 依赖 | 状态 |
|------|------|
| Python 3.12 | 已安装 |
| MongoDB 8.0 | 已安装 |
| 宝塔面板 | 已安装 |

> carl 用户**无免密 sudo**，部署脚本使用 nohup 后台运行（不依赖 systemd）。

---

## 一键部署（推荐）

```bash
cd /home/chunkit/VScode_project/reagent1.0_UI
chmod +x deploy.sh
./deploy.sh
```

脚本自动完成：

| 步骤 | 操作 |
|------|------|
| 1. 打包 | `pip freeze` 导出依赖，打 tarball |
| 2. 上传 | SCP 自动输入密码上传到服务器 |
| 3. 远程安装 | 检查环境 → 解压 → 建 venv → 装依赖 → 生成 .env → 修复路径 → 创建管理脚本 → 启动（端口 **8000**） |

### 分步执行

```bash
./deploy.sh pack      # 仅打包
./deploy.sh upload    # 仅上传
./deploy.sh remote    # 仅执行远程安装
```

---

## 手动部署

### 1. 本地打包

```bash
cd /home/chunkit/VScode_project
cd reagent1.0_UI && pip freeze > requirements_deploy.txt && cd ..
tar czf /tmp/reagent1.0_UI.tar.gz \
    --exclude='reagent1.0_UI/.git' \
    --exclude='reagent1.0_UI/__pycache__' \
    --exclude='reagent1.0_UI/**/__pycache__' \
    --exclude='reagent1.0_UI/.DS_Store' \
    --exclude='reagent1.0_UI/uv.lock' \
    --exclude='reagent1.0_UI/venv' \
    reagent1.0_UI/
```

### 2. 上传

```bash
sshpass -p '2wsx@WSX#EDC' \
    scp -P 10122 -o StrictHostKeyChecking=no \
    /tmp/reagent1.0_UI.tar.gz carl@se.aiseclab.cn:/tmp/
```

### 3. 服务器上安装

```bash
sshpass -p '2wsx@WSX#EDC' ssh -p 10122 carl@se.aiseclab.cn
```

```bash
mkdir -p /home/carl/reagent
tar xzf /tmp/reagent1.0_UI.tar.gz -C /home/carl/reagent --strip-components=1
cd /home/carl/reagent

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements_deploy.txt
pip install fastapi motor prompt_toolkit

mkdir -p output uploads data

# 修复硬编码路径
sed -i "s|load_dotenv('.*')|load_dotenv('/home/carl/reagent/.env')|g" util/SoftwareManager.py
sed -i "s|load_dotenv(\".*\")|load_dotenv(\"/home/carl/reagent/.env\")|g" backend/config.py

# 编辑 .env
nano .env

# 启动
nohup venv/bin/python main.py serve --host 0.0.0.0 --port 8000 \
    >> reagent-api.log 2>&1 &
echo $! > reagent-api.pid
```

---

## 部署后必做事项

### Step 1: 填写 .env（首次部署）

```bash
sshpass -p '2wsx@WSX#EDC' ssh -p 10122 carl@se.aiseclab.cn
nano /home/carl/reagent/.env
```

```ini
# ===== LLM 配置 =====
OPENAI_KEY=your-api-key
OPENAI_API_KEY=your-api-key          # 两个字段值一样
OPENAI_MODEL=deepseek-chat           # 或 gpt-5.1 等
OPENAI_BASE_URL=https://api.deepseek.com/v1  # DeepSeek 需要填

# ===== MongoDB =====
MONGODB_URI=mongodb://localhost:27017
DB_NAME=reagent
```

### Step 2: 重启服务

```bash
/home/carl/reagent/restart.sh
```

### Step 3: 验证

```bash
curl http://localhost:8000/health
# 期望：{"status":"healthy","db_connected":true,...}
```

---

## 本地访问（SSH 隧道）

由于外网访问尚未配置，通过 SSH 隧道将服务器 8000 端口映射到本地：

```bash
# 建立隧道（后台运行）
sshpass -p '2wsx@WSX#EDC' ssh -p 10122 \
  -L 8000:127.0.0.1:8000 \
  -L 27017:127.0.0.1:27017 \
  -L 3306:127.0.0.1:3306 \
  -L 6379:127.0.0.1:6379 \
  carl@se.aiseclab.cn -N &
```

隧道建立后本地可访问：

| 服务 | 本地地址 |
|------|----------|
| REagent API | `http://localhost:8000` |
| MongoDB | `mongodb://localhost:27017` |
| MySQL | `localhost:3306` |
| Redis | `localhost:6379` |

### 运行测试脚本

```bash
cd /home/chunkit/VScode_project/reagent1.0_UI
python example_client.py quick   # 快速接口测试
python example_client.py         # 完整流程演示
```

### 用 mongosh 查看数据

```bash
mongosh mongodb://localhost:27017/reagent
> db.projects.find().pretty()
```

---

## 外网访问（待配置）

虚拟机上已部署 nginx（端口 9998），统一反代所有 web 应用。

**REagent API 的 nginx 配置（在虚拟机 nginx:9998 中添加）：**

```nginx
location /reagent/ {
    rewrite ^/reagent/(.*) /$1 break;
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    # SSE 长连接（必须加）
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;
}
```

**网关层（122.51.195.198）需将外部端口转发到虚拟机 nginx 9998。**

配好后访问地址：`http://se.aiseclab.cn:9998/reagent/health`

---

## 日常运维

### 服务管理（无需 sudo）

```bash
/home/carl/reagent/status.sh      # 查看状态 + 健康检查
/home/carl/reagent/start.sh       # 启动
/home/carl/reagent/stop.sh        # 停止
/home/carl/reagent/restart.sh     # 重启
```

### 查看日志

```bash
tail -f /home/carl/reagent/reagent-api.log     # 实时
tail -100 /home/carl/reagent/reagent-api.log   # 最近 100 行
grep -i error /home/carl/reagent/reagent-api.log  # 搜索错误
```

### 更新代码

```bash
# 本地执行一键重新部署
./deploy.sh

# 或分步
./deploy.sh pack && ./deploy.sh upload
sshpass -p '2wsx@WSX#EDC' ssh -p 10122 carl@se.aiseclab.cn
cd /home/carl/reagent
tar xzf /tmp/reagent1.0_UI.tar.gz -C /home/carl/reagent --strip-components=1
./restart.sh
```

> 重新部署不会覆盖 `.env`，不需要重新配置密钥。

### 开机自启

```bash
crontab -e
# 添加：
@reboot /home/carl/reagent/start.sh
```

### 宝塔面板管理

登录 `https://122.51.195.198:21748/67cbe54c`：

- 查看服务器资源（CPU / 内存 / 磁盘）
- MongoDB 启停管理
- **安全** → 防火墙端口管理
- **文件** → 浏览编辑项目文件
- **终端** → 命令行操作

---

## API 使用说明

### 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/project/create` | 创建项目 |
| GET | `/project/list/{user_id}` | 列出用户项目 |
| GET | `/project/{project_id}` | 获取项目详情 |
| DELETE | `/project/{project_id}` | 删除项目 |
| POST | `/graph/stream/create` | 启动 RE 流水线 |
| POST | `/graph/stream/resume` | 提交反馈恢复流水线 |
| GET | `/graph/stream/{project_id}` | SSE 实时事件流 |
| GET | `/artifacts/{project_id}` | 列出所有制品 + DAG |
| GET | `/artifacts/{project_id}/{name}` | 获取单个制品内容 |
| POST | `/artifacts/export_pdf` | 导出制品为 PDF |
| POST | `/files/upload` | 上传数据文件/SRS 模板 |

### 快速测试

```bash
BASE_URL="http://localhost:8000"  # 通过 SSH 隧道

# 健康检查
curl ${BASE_URL}/health

# 创建项目
curl -X POST ${BASE_URL}/project/create \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","project_name":"测试项目","description":"教授个人主页网站"}'

# 启动流水线
curl -X POST ${BASE_URL}/graph/stream/create \
  -H "Content-Type: application/json" \
  -d '{"project_id":"<pid>","user_id":"test","human_request":"构建一个个人主页"}'

# 监听 SSE 事件流
curl -N ${BASE_URL}/graph/stream/<pid>

# 查看制品
curl ${BASE_URL}/artifacts/<pid>
```

### SSE 事件类型

| 事件 | 说明 |
|------|------|
| `connected` | 连接建立 |
| `stage_start` | 阶段开始 |
| `crew_start` | Crew 任务执行中 |
| `artifact_complete` | 制品完成 |
| `interrupt` | 需要人工审核 |
| `feedback_processing` | 处理反馈中 |
| `srs_chapter` | SRS 章节完成 |
| `stage_complete` | 阶段完成 |
| `error` | 错误 |
| `finished` | 全部完成 |

### 人工审核（Interrupt）

流水线在 3 个节点暂停等待审核：business_scope、BRD、elicitation。

```bash
# 通过
curl -X POST ${BASE_URL}/graph/stream/resume \
  -H "Content-Type: application/json" \
  -d '{"project_id":"<pid>","resume_type":"accept","human_comment":"没问题"}'

# 要求修改
curl -X POST ${BASE_URL}/graph/stream/resume \
  -H "Content-Type: application/json" \
  -d '{"project_id":"<pid>","resume_type":"feedback","human_comment":"请补充移动端需求"}'
```

---

## 常见问题排查

### 服务启动失败

```bash
tail -50 /home/carl/reagent/reagent-api.log
```

| 原因 | 解决 |
|------|------|
| `.env` 未配置 | `nano /home/carl/reagent/.env` |
| MongoDB 未启动 | 宝塔面板启动 MongoDB |
| 端口 8000 被占用 | `ss -tlnp \| grep :8000`，kill 占用进程 |
| Python 依赖缺失 | `source venv/bin/activate && pip install -r requirements_deploy.txt` |

### MongoDB 连接失败

```bash
pgrep mongod        # 检查是否运行
# 或在宝塔面板 → 软件商店 → MongoDB → 启动
```

### MongoDB 认证错误

如果 MongoDB 重新开启了认证，需要关闭或配置密码：

```bash
# 方式一：关闭认证（sudo su 后执行）
sed -i 's/authorization: enabled/authorization: disabled/' /www/server/mongodb/config.conf
/etc/init.d/mongodb restart

# 方式二：配置密码（在 .env 中）
# MONGODB_URI=mongodb://用户名:密码@localhost:27017/reagent?authSource=admin
```

### API 返回 500

```bash
tail -f /home/carl/reagent/reagent-api.log
```

| 原因 | 解决 |
|------|------|
| API Key 无效 | 更新 `.env`，然后 `./restart.sh` |
| 无法访问 LLM API | 检查 `OPENAI_BASE_URL` 是否正确 |

### SSH 隧道断开

```bash
# 重新建立
sshpass -p '2wsx@WSX#EDC' ssh -p 10122 \
  -L 8000:127.0.0.1:8000 carl@se.aiseclab.cn -N &
```

### 服务器重启后 API 未恢复

```bash
/home/carl/reagent/start.sh
# 或设置 crontab 开机自启（见日常运维章节）
```

---

## 部署后目录结构

```
/home/carl/reagent/
├── .env                        ← 环境配置（API 密钥）
├── start.sh                    ← 启动脚本
├── stop.sh                     ← 停止脚本
├── restart.sh                  ← 重启脚本
├── status.sh                   ← 状态检查脚本
├── reagent-api.log             ← 运行日志
├── reagent-api.pid             ← 进程 PID
│
├── backend/                    ← FastAPI 后端
│   ├── main.py                 ←   应用入口（uvicorn 启动点）
│   ├── config.py               ←   配置管理
│   ├── db/mongo.py             ←   MongoDB 连接
│   ├── api/routes/             ←   API 路由
│   ├── models/                 ←   Pydantic 模型
│   └── services/               ←   业务逻辑
│       ├── execution.py        ←     流水线执行引擎
│       └── stream_manager.py   ←     SSE 事件管理
│
├── src/reagent/                ← CrewAI 流水线
│   ├── main.py                 ←   CLI 入口
│   ├── config/                 ←   agents.yaml + tasks.yaml
│   ├── StandardProcess.py
│   ├── BusinessRequirements.py
│   ├── RequirementElicitation.py
│   ├── RequirementAnalysis.py
│   └── RequirementSpecification.py
│
├── util/                       ← 工具库
│   ├── DAG.py                  ←   制品依赖图
│   ├── SoftwareManager.py      ←   CrewAI 基类
│   └── doc_template/           ←   BRD / SRS 文档模板
│
├── experiment/                     ← 生成的文档
├── dataset/uploads/                    ← 上传的文件
├── data/                       ← 项目数据
├── venv/                       ← Python 虚拟环境
└── example_client.py           ← API 调用示例
```
