# RTR4 学习系统

RTR4 多模态学习应用，包含 Python 后端与 React 前端。

## 阅读入口与当前范围

- 左侧可阅读整本 PDF，可翻页或输入页码后确认跳转；范围读取书籍登记信息（本地 RTR4 为 903 页）。这里是 PDF 页码，不是书内印刷页码。
- 右侧已有 5.1、5.2、5.2.2 内容；未覆盖页明确提示暂无精讲。当前课程与页码关联仍为第五章兼容规则，通用课程目录与跨章精读尚待后续批次。
- 书籍目录仅显示已登记章节，不代表完整目录；未解析页面仍可读原书，不提供尚不存在的区域定位。
- 来源框可关闭；课程中的 ShaderToy 源码可复制到外部编辑器运行，链接不会自动载入代码。
- 第五章检索评测覆盖 20 个问题，但不代表整本书或第五章全部精讲已经完成。问答目前是本地来源摘录，不是生成式教师。
- PDF、模型、解析数据和环境仅保留本地，不随 GitHub 上传。新克隆需按 [本地运行手册](docs/runbooks/local-development.md)准备数据。

全书架构与后续批次见 [实施路线](docs/plans/2026-09-28-whole-book-roadmap.md)。2026-09-28 首批交付全书页面接口、书籍驱动页码范围、已登记章节导航与未解析降级；不等于完成全书解析/精讲。

## 本机启动（已有环境和数据）

PowerShell 终端一：

```powershell
cd I:\pdf_reaserch\.worktrees\rtr4-learning\backend
$env:RTR4_DATA_ROOT = 'I:\pdf_reaserch\data'
$env:RTR4_CONTENT_ROOT = 'I:\pdf_reaserch\.worktrees\rtr4-learning\content'
$env:RTR4_SOURCE_ROOTS = 'I:\pdf_reaserch'
.\.venv\Scripts\python.exe -m uvicorn rtr4_learning.server:create_environment_app --factory --host 127.0.0.1 --port 8000
```

PowerShell 终端二：

```powershell
cd I:\pdf_reaserch\.worktrees\rtr4-learning\frontend
npm run dev -- --host 127.0.0.1 --port 15173 --strictPort
```

打开 http://127.0.0.1:15173/ 。本机 5173 端口出现 EACCES 时可使用这个替代端口；API 仍使用 8000。

## 后端

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

## 前端

```powershell
cd frontend
npm install
npm test
npm run dev
```
