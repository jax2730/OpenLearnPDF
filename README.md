# OpenLearnPDF

面向大型 PDF 书籍的本地多模态学习应用。当前打通《Real-Time Rendering 4th》中文版第五章闭环，包括正文、公式、图片、引用检索、问答和逐章节教学。

## 阅读入口与当前范围

- 左侧阅读 PDF 第 104–154 页，可翻页或输入页码后确认跳转。这里是 PDF 页码，不是书内印刷页码。
- 右侧精讲 5.1、5.2、5.2.2；切换课程定位对应起始页，点击引用定位具体公式或图。手动翻页不会自动切换课程。
- 来源框可关闭；课程中的 ShaderToy 源码可复制到外部编辑器运行，链接不会自动载入代码。
- 第五章检索评测覆盖 20 个问题，但不代表整本书或第五章全部精讲已经完成。问答目前是本地来源摘录，不是生成式教师。
- PDF、模型、解析数据和环境仅保留本地，不随 GitHub 上传。新克隆需按 [本地运行手册](docs/runbooks/local-development.md)准备数据。

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

本地运行、MinerU 数据位置与第五章评测流程见 `docs/runbooks/local-development.md`。
