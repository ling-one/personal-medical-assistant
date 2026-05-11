# 个人医疗助手

基于 **LangGraph + FastAPI + 微信小程序** 构建的 AI 家庭健康管理助手。支持家庭成员健康档案管理、体检报告 OCR 解读、多轮对话健康咨询，对话历史按成员隔离持久化，提供专业、个性化的医疗健康服务。

## 项目概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        微信小程序前端                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   首页    │  │   对话    │  │ 家庭成员  │  │   我的    │       │
│  │ 健康概览  │  │ AI咨询   │  │ 档案管理  │  │ 设置反馈  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS / WebSocket
┌─────────────────────────▼───────────────────────────────────────┐
│                      FastAPI 后端服务                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   用户管理    │  │   家庭组管理  │  │  家庭成员管理  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   对话服务    │  │ 体检报告OCR  │  │   知识库检索   │         │
│  │ REST+WebSocket│  │  千问OCR     │  │   FAISS      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                          │                                      │
│              ┌───────────▼───────────┐                         │
│              │     LangGraph Agent   │                         │
│              │  查询改写 → 记忆加载 → │                         │
│              │  意图分类 → RAG检索 → │                         │
│              │  回复生成 → 记忆更新  │                         │
│              └───────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

## 核心功能

### 1. 家庭成员健康管理
- 创建家庭组，邀请家人加入
- 每位成员独立的健康档案（病史、过敏、用药、体征）
- 健康数据随时查看与更新

### 2. AI 健康咨询对话
- **多轮对话**：WebSocket 流式回复，打字机效果
- **成员隔离**：选择不同家庭成员咨询，对话历史完全隔离
- **持久化记录**：30 分钟超时自动续对话，重启不丢失
- **建议追问**：每次回复附带 3 个相关追问建议

### 3. 体检报告 OCR 解读
- 上传体检报告图片（PDF/PNG/JPG）
- 千问 OCR 自动提取文字
- AI 解读异常指标，给出健康建议

### 4. 智能意图路由
基于 LangGraph 自动识别用户意图：
- **health_qa** — 健康知识问答
- **report_reader** — 报告解读
- **drug_query** — 用药查询
- **health_analysis** — 健康数据分析
- **lifestyle** — 生活方式建议

### 5. RAG 知识检索
- **向量检索**：BGE-small-zh-v1.5 + FAISS
- **用户私有向量库**：每位用户独立索引，支持长期记忆
- **LLM 自动提取**：对话中自动提取症状、用药、偏好存入长期记忆

### 6. Langfuse 可观测性
- 完整追踪每次对话执行链路
- 记录 token 消耗、延迟、意图分类结果
- 用户反馈（点赞/点踩）关联追踪

## 项目结构

```
个人医疗助手/
├── miniprogram/                    # 微信小程序前端
│   ├── app.js                      # 小程序入口
│   ├── app.json                    # 页面路由与TabBar配置
│   ├── pages/                      # 页面
│   │   ├── index/                  # 首页（家庭组概览）
│   │   ├── chat/                   # 对话页（成员选择 + 聊天）
│   │   ├── member/                 # 成员详情/编辑
│   │   ├── report/                 # 体检报告列表/详情
│   │   ├── group/                  # 创建/加入家庭组
│   │   └── profile/                # 我的页面
│   ├── components/                 # 自定义组件
│   │   ├── chat-bubble/            # 聊天气泡
│   │   ├── member-card/            # 成员卡片
│   │   ├── member-selector/        # 成员选择器
│   │   └── vital-signs-card/       # 体征卡片
│   └── utils/api.js                # 后端 API 封装
│
├── server/                         # FastAPI 后端
│   ├── main.py                     # 应用入口
│   ├── config.py                   # Pydantic 配置管理
│   ├── api/                        # REST API 路由
│   │   ├── chat.py                 # 对话（REST + WebSocket + SSE）
│   │   ├── user.py                 # 用户管理
│   │   ├── group.py                # 家庭组管理
│   │   ├── member.py               # 家庭成员管理
│   │   ├── report.py               # 体检报告上传与解读
│   │   └── knowledge.py            # 知识库检索
│   ├── agent/                      # LangGraph Agent
│   │   ├── graph.py                # 图定义与编排
│   │   ├── state.py                # AgentState 状态模型
│   │   ├── nodes/                  # 节点实现
│   │   │   ├── query_rewrite.py    # 查询改写
│   │   │   ├── memory_load.py      # 短期/长期记忆加载
│   │   │   ├── classify.py         # 意图分类
│   │   │   ├── retrieval.py        # RAG 知识检索
│   │   │   ├── respond.py          # 回复生成
│   │   │   ├── report_reader.py    # 报告解读
│   │   │   ├── drug_query.py       # 用药查询
│   │   │   ├── health_analysis.py  # 健康分析
│   │   │   ├── lifestyle.py        # 生活建议
│   │   │   └── memory_update.py    # 记忆更新 + LLM提取
│   │   ├── tools/                  # 工具函数
│   │   │   ├── knowledge_base.py   # 知识库搜索
│   │   │   ├── hybrid_retrieve.py  # 混合检索
│   │   │   ├── qwen_vl_rerank.py   # Qwen3-VL Rerank
│   │   │   └── web_search.py       # 联网搜索
│   │   └── prompts/                # 提示词模板（Markdown）
│   ├── services/                   # 业务服务
│   │   ├── conversation_service.py # 对话持久化（JSON文件）
│   │   ├── memory_service.py       # 短期记忆管理
│   │   ├── vector_store.py         # FAISS 向量库
│   │   ├── llm_service.py          # LLM 封装（小米/OpenAI）
│   │   ├── ocr_service.py          # 千问 OCR
│   │   ├── member_service.py       # 家庭成员 CRUD
│   │   ├── group_service.py        # 家庭组 CRUD
│   │   ├── user_service.py         # 用户会话管理
│   │   ├── stream_manager.py       # WebSocket 流式队列
│   │   └── trace_service.py        # Langfuse 追踪
│   └── models/                     # Pydantic 数据模型
│       ├── conversation.py
│       ├── group.py
│       ├── member.py
│       ├── profile.py
│       └── report.py
│
├── data/                           # 数据目录（运行时生成）
│   ├── users/                      # 用户数据 + 对话历史
│   ├── groups/                     # 家庭组数据
│   ├── members/                    # 成员健康档案
│   ├── reports/                    # 体检报告 OCR 文本
│   └── knowledge_base/             # 系统知识库
│
├── vector_store_faiss/             # FAISS 向量索引
├── langfuse/                       # Langfuse Docker Compose
├── docker-compose.yml.example      # Docker 编排模板（需手动复制）
├── pyproject.toml                  # Poetry 配置
├── requirements.txt                # pip 依赖
└── .env                            # 环境变量（不提交，见 .env.example）
```

## 技术栈

| 层级 | 技术 |
|:---|:---|
| **前端** | 微信小程序原生框架 |
| **后端** | Python 3.13 + FastAPI + uvicorn |
| **Agent** | LangGraph (StateGraph) + LangChain |
| **LLM** | 小米大模型 mimo-v2-flash / 任意 OpenAI 兼容 API |
| **OCR** | 千问 Qwen-VL-OCR |
| **嵌入模型** | BAAI/bge-small-zh-v1.5 |
| **向量库** | FAISS (用户私有索引) |
| **追踪** | Langfuse |
| **部署** | Docker Compose (可选) |

## 快速开始

### 环境要求

- Python 3.13+
- Node.js + 微信开发者工具（前端调试）
- Docker & Docker Compose（可选，用于 Langfuse）

### 1. 克隆项目

```bash
git clone https://github.com/ling-one/personal-medical-assistant.git
cd personal-medical-assistant
```

### 2. 配置环境变量

```bash
cp docker-compose.yml.example docker-compose.yml
```

创建 `.env` 文件：

```env
# LLM 配置（小米大模型 / OpenAI 兼容）
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.xiaomimimo.com/v1
LLM_MODEL=mimo-v2-flash

# OCR 配置（千问 OCR）
OCR_API_KEY=your_dashscope_key_here

# DashScope 配置（Rerank 等）
DASHSCOPE_API_KEY=your_dashscope_key_here

# Langfuse 追踪（可选）
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_BASE_URL=http://localhost:3000
```

### 3. 安装依赖

**方式一：Poetry（推荐）**

```bash
poetry install
poetry shell
```

**方式二：pip**

```bash
pip install -r requirements.txt
```

### 4. 启动服务

```bash
# 启动后端 API
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

# 启动 Langfuse（可选，需要 Docker）
cd langfuse
cp docker-compose.yml.example docker-compose.yml
docker-compose up -d
```

### 5. 启动微信小程序

1. 打开**微信开发者工具**
2. 导入项目 `miniprogram/` 目录
3. 复制示例配置：
   ```bash
   cp miniprogram/project.config.json.example miniprogram/project.config.json
   ```
4. 填入你的小程序 **AppID**
5. 修改 `miniprogram/app.js` 中的 `baseUrl` 指向你的后端地址
6. 点击编译预览

### 访问服务

| 服务 | 地址 |
|:---|:---|
| API 服务 | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| Langfuse | http://localhost:3000 |

## API 示例

### 创建用户

```bash
curl -X POST "http://localhost:8000/api/user/create" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_001"}'
```

### 发起对话（REST）

```bash
curl -X POST "http://localhost:8000/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "message": "最近有点头疼，怎么办？",
    "member_id": "member_001"
  }'
```

### 获取对话历史

```bash
# 获取用户的所有对话列表（按成员隔离）
curl "http://localhost:8000/api/chat/conversations?user_id=user_001"

# 获取某对话的消息列表
curl "http://localhost:8000/api/chat/messages/{conversation_id}"
```

### 上传体检报告

```bash
curl -X POST "http://localhost:8000/api/report/upload" \
  -F "file=@report.pdf" \
  -F "member_id=member_001"
```

## LangGraph 工作流

```
用户输入
    │
    ▼
┌─────────────┐
│ 查询改写     │  优化用户查询，补全上下文
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 记忆加载     │  加载短期历史 + FAISS长期记忆 + 成员档案
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 意图分类     │  health_qa / report_reader / drug_query / health_analysis / lifestyle
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ RAG 检索     │  向量检索 + BM25 + 用户私有索引
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ 功能节点     │ ──→ │ 回复生成     │
│ (条件路由)   │     │             │
└─────────────┘     └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ 记忆更新     │  更新短期记忆 + 持久化JSON + FAISS + LLM提取
                    └─────────────┘
```

## 开发指南

### 添加新节点

1. 在 `server/agent/nodes/` 创建节点文件
2. 在 `server/agent/nodes/__init__.py` 导出
3. 在 `server/agent/graph.py` 注册节点和边

### 更新提示词

编辑 `server/agent/prompts/*.md` 文件，无需重启服务（运行时读取）。

### 调试技巧

- **Langfuse**：访问 http://localhost:3000 查看完整执行链路
- **API 文档**：访问 http://localhost:8000/docs 在线调试
- **日志**：调整 `LOG_LEVEL=DEBUG` 查看详细日志

## 目录说明

| 路径 | 说明 |
|:---|:---|
| `data/users/conversations/` | 用户对话历史（JSON，按成员隔离） |
| `data/groups/` | 家庭组数据 |
| `data/members/` | 成员健康档案 |
| `data/reports/` | 体检报告 OCR 文本 |
| `vector_store_faiss/` | FAISS 向量索引（系统知识库 + 用户私有索引） |

## 安全提醒

- `.env` 和 `docker-compose.yml` 含敏感密钥，**切勿提交到 Git**
- 微信小程序 AppID 和 AppSecret 请妥善保管
- 生产环境请关闭 CORS 的 `allow_origins=["*"]`，改为指定域名
- 建议启用 HTTPS（微信小程序要求）

## License

MIT License
