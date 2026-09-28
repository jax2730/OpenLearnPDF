# Reading Workspace Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为全书阅读提供可收展且不丢位置的伴读侧栏、窄屏切换和分层解释。

**Architecture:** ReadingWorkspace只管理布局；阅读导航、版面偏好、学习内容状态分别维护。沿用单个PDF.js文档及现有课程接口，新增通用课程目录前不伪造全书教学映射。

**Tech Stack:** React、TypeScript、PDF.js、CSS、Vitest、Testing Library；现有FastAPI接口回归。

---

工作树：`I:\pdf_reaserch\.worktrees\rtr4-learning`。设计依据：`docs/plans/2026-09-28-reading-workspace-design.md`。本轮仅保存设计，不执行本计划。实施前读取TDD和验证技能；保留.run及其他用户文件，无需新工作树或依赖下载。

## Task 1：版面状态与偏好契约

Files：新增 `frontend/src/workspaceState.ts`、`frontend/src/workspaceState.test.ts`。

1. 写失败测试：收展不改阅读页；窄屏面板变化不覆盖宽屏偏好；损坏JSON/异常类型/越界比例/存储拒绝退回默认。
2. frontend运行 `npm test -- src/workspaceState.test.ts`，确认新行为失败。
3. 实现纯状态转换，默认 sidebarOpen=true、studyRatio=0.4、compactPanel=pdf；窄屏视口状态不落库，用户宽屏偏好可落库。
4. 实现小型版本化存储包装，读写均catch，ratio必须有限数且受有效布局边界约束；不存内容与图片。
5. 同命令确认通过；精确暂存这两个文件，提交 `feat: model persistent reading workspace preferences`。

## Task 2：可收展壳层

Files：新增 `frontend/src/components/ReadingWorkspace.tsx`、`ReadingWorkspace.test.tsx`；修改 `frontend/src/App.tsx`、`frontend/src/app.css`、`frontend/src/App.test.tsx`、`frontend/src/WholeBook.test.tsx`。

1. 写组件测试：顶部始终存在开关；收起后原书单栏；隐藏侧栏不可聚焦；展开恢复草稿和打开的details。
2. 运行 `npm test -- src/components/ReadingWorkspace.test.tsx`，先看失败。
3. 壳层接受原书/伴读children及受控状态；隐藏不能卸载PDF或清学习状态。关闭后显式恢复焦点到顶部开关，使用hidden使隐藏区域退出无障碍树。
4. 将App布局迁入壳层，不同时重写课程数据；不保留无效grid空列。
5. 运行 `npm test -- src/components/ReadingWorkspace.test.tsx src/App.test.tsx src/WholeBook.test.tsx`，通过后提交 `feat: collapse companion pane without resetting study state`。

## Task 3：阅读锚点与渲染生命周期

Files：新增 `frontend/src/readingAnchor.ts`、`readingAnchor.test.ts`；修改 `frontend/src/components/PdfReader.tsx`、`PdfReader.test.tsx`、`ReadingWorkspace.tsx`及测试。

1. 给归一化换算写数值测试：页框起点、页中、页底、零尺寸、越界；渲染生命周期测试中记录getDocument调用数。
2. 运行 `npm test -- src/readingAnchor.test.ts src/components/PdfReader.test.tsx`，确认新行为失败。
3. 捕获相对页框的可见锚点；适宽重排后按新尺寸恢复，限制scroll范围；先实现垂直锚点，不冒充完整缩放功能。
4. 增加恢复令牌，页码变化和用户主动滚动使旧恢复作废；不与已有串行resize渲染发生重复恢复。
5. 测试收展期间单文档复用、旧render取消、过期恢复不覆盖新页。实机滚到原书中段收展三次，核对相同文字仍在可见区。
6. 通过后提交 `fix: preserve PDF reading anchors during workspace resize`。

## Task 4：可调分栏与窄屏切换

Files：修改 `frontend/src/components/ReadingWorkspace.tsx`、`ReadingWorkspace.test.tsx`、`frontend/src/app.css`。

1. 写失败测试：窄屏不堆叠，切换仅一面可见；从窄屏回宽屏保留原偏好；键盘左右键调比例、Home复位、不能超出最小尺寸。
2. 运行壳层测试确认失败。
3. 使用工作区宽度决定模式；pointer capture处理拖动与取消，requestAnimationFrame合并更新；separator提供role、方向和当前值。
4. 紧凑布局提供“原书/伴读”文本切换，查看引用切原书，返回切伴读；布局变化不加载新文档。
5. 同命令回归，实机验证窄窗口、宽窗口、200%浏览器缩放、键盘Tab及长公式不撑开页面。
6. 提交 `feat: add accessible split sizing and compact reading panels`。

## Task 5：分层解释与导航迁移

Files：修改 `frontend/src/components/LessonPanel.tsx`、`LessonPanel.test.tsx`、`KnowledgeLessonPanel.tsx`、`KnowledgeLessonPanel.test.tsx`、`QuestionPanel.tsx`、`frontend/src/types.ts`；视需要新增 `frontend/src/components/ExplanationGroup.tsx`及测试。

1. 先检查全书通用课程目录是否已经实现。若未完成，目录迁移仍标为依赖任务，不用新硬编码绕过；分层展示可以独立实施。
2. 写失败测试：核心解释始终可见，推导与例子可同时打开，缺失内容不显示空分组，揭示答案不改变掌握状态，切知识点后展开状态互不污染。
3. 运行 `npm test -- src/components/LessonPanel.test.tsx src/components/KnowledgeLessonPanel.test.tsx`。
4. 以受控展开组展示现有sections/cards，保留所有内容和来源；不把未展示卡片丢弃，不重复绘制同一正文。Shader与检索放次要入口，不承诺未提供的笔记功能。
5. 展开组按书籍/课程/知识点/内容版本存储；版本尚无公开契约时先会话保存，待契约接入再持久化，避免伪造版本。
6. 回归并实机对照已存在的5.1、5.2、5.2.2全部内容没有遗漏；按界面与内容兼容分别提交。

## Task 6：验收与发布

Files：更新 `README.md`、`docs/runbooks/local-development.md`；新增 `docs/reviews/reading-workspace-acceptance.md`。

1. frontend运行 `npm test`、`npm run build`；backend运行 `.\.venv\Scripts\python.exe -m pytest -q`、`.\.venv\Scripts\ruff.exe check src tests`。真实数据E2E使用既有环境配置，记录实际结果。
2. 真实浏览器执行设计第9节各场景；视口宽度至少覆盖窄屏、断点附近和宽屏。特别检查收起后焦点、草稿、PDF位置和文档实例。
3. 验收文档区分自动测试、实机通过、未实施依赖。更新运行说明与已知限制，不能称全书教学完成。
4. `git diff --check`，按任务精确暂存并提交；推送feature/rtr4-learning，核对远端哈希。若按既有主分支集成流程合并，先检查main工作树和远程变化，不强推。
5. 交付入口、提交数、测试结果及待办。用户确认的是交互方向，不需要再次询问相同设计；实施过程中只对新范围或真实阻塞提问。

## 执行交接

推荐当前会话按批次顺序实施，先Task 1–3形成可体验的侧栏闭环；也可在独立执行会话加载本文件。默认不启用子代理。全书目录与教学发布任务继续沿总路线推进，本计划只负责阅读工作区。
