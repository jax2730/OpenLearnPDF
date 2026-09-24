# Companion Reader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 RTR4 已有第五章内容改为原书驱动、可回溯来源、可自测的伴读工作台。

**Architecture:** 保留 React/PDF.js/FastAPI；集中管理阅读导航和旁证返回状态，用来源块构建页到知识点索引。先打通平方反比的纵向样板，再迁移现有课程；无精讲的页面明确降级为原书阅读。

**Tech Stack:** TypeScript、React 19、Vitest、Testing Library、PDF.js、Python、Pydantic、pytest。

---

设计依据：`docs/plans/2026-09-24-companion-reader-design.md`。这是待执行计划，不是功能完成报告。

## 工作约束

- 工作树：`I:\pdf_reaserch\.worktrees\rtr4-learning`；保留现有 feature/rtr4-learning 分支与提交历史，不改外层旧 master，不提交 .run、PDF、数据库、模型、环境。
- 开工前读取 AGENTS.md、检查 git status；仅暂存任务明确文件。用户本轮只要求设计规划，收到实施指令后才执行以下任务。
- 每任务遵循：写失败测试 → 运行确认行为失败 → 最小实现 → 回归 → 独立提交。每个步骤再按 2–5 分钟单项操作推进；不用一次提交吞掉全部任务。
- 教材图片/公式审校先读取适用 PDF 技能；实现时读取 TDD、验证技能。优先既有能力，不安装新模型；不默认调度子代理。

## Task 1：建立确定性的阅读状态与来源索引

**Files:** 新增 `frontend/src/readerState.ts`、`frontend/src/readerState.test.ts`；修改 `frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/components/LessonPanel.tsx`。

1. 写单元测试，使用 p110/p111 跨页点与 p109 多点夹具，测试 FLIP_PAGE、SELECT_BLOCK、OPEN_EVIDENCE、RETURN_TO_READING。下例约定 API：

```ts
it('keeps the lesson while visiting evidence', () => {
  const initial = { page: 110, pointId: 'inverse-square', returnTo: null };
  const next = readerReducer(initial, {
    type: 'OPEN_EVIDENCE', page: 111, blockId: 'p111-formula-5.11',
  });
  expect(next.page).toBe(111);
  expect(next.pointId).toBe('inverse-square');
  expect(next.returnTo?.page).toBe(110);
  expect(readerReducer(next, { type: 'RETURN_TO_READING' }).page).toBe(110);
});
```

2. 在 frontend 运行 `npm test -- src/readerState.test.ts`，预期新模块不存在导致失败。
3. 实现纯 reducer；扩展状态时让返回锚点包括滚动位置与原选中块。引用索引合并 point/card 引用并按页内阅读顺序排列；页码来自服务端 SourceBlock，不能从 ID 字符串猜测。
4. 增加测试：无映射页 pointId 为空、同页保留当前点、连续旁证不覆盖初始返回位置、旁证期间翻页清除返回点、多个课程同页可正确选择。
5. 接入 App，移除互相驱动的导航 effect；为尚未加载/失败的映射显示独立状态，防止旧课程闪现。运行 `npm test -- src/readerState.test.ts src/App.test.tsx`。
6. 提交 `feat: centralize companion reading navigation`。

## Task 2：扩展内容契约，保留旧数据兼容

**Files:** 修改 `backend/src/rtr4_learning/teaching.py`、`backend/tests/test_teaching.py`、`frontend/src/types.ts`；新增 `backend/tests/test_companion_content.py`。

1. 为可选 companion 字段写模型测试：objective、prerequisites、symbols（含 meaning/unit）、derivation、check（prompt/hint/answer/explanation）、practice（instructions/expected_observation）、origin（book/teaching/engineering）与 citations。旧 JSON 无 companion 仍通过。
2. 运行 `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_teaching.py backend/tests/test_companion_content.py -q`（仓库根目录），预期新增契约用例失败。
3. 按现有 ContractModel 模式添加类型，不接收任意 HTML；所有新引用加入 validate_lesson_bundle 的引用集合。Frontend 同步类型，含现有 questions，不用 any。
4. 加入负例：未知来源、空解释、缺失答案、重复 ID；伴读发布校验与旧内容读取校验分离，避免一次改模型导致现有课程全不可读。
5. 重跑目标测试及 `npm run build`（frontend），确认兼容；提交 `feat: add structured companion teaching contracts`。

## Task 3：制作平方反比样板并完成内容审校

**Files:** 修改 `content/rtr4-cn/chapter-05/section-5.2.2.json`、`backend/tests/test_companion_content.py`；新增 `docs/reviews/2026-09-24-companion-content-review.md`。

1. 从本地原书复核 p110 图5.5、p111 公式5.11及上下文；记录书页、符号约定、原文与教学补充区别，不提交原书截图。
2. 写发布校验：该点具备目标、假设、符号、推导、数值例子、自测与来源；`2→6` 的相对比例为 `1/9`。先运行确认失败。
3. 填入设计样板的完整内容；解释辐射量与显示亮度区别、近场奇点与工程近似；不把面积扩散误讲成介质吸收。
4. 给该知识点设置可复现的验证任务；若既有 shader 鼠标操作同时改变方向，不把它作为隔离距离规律的实验，先用数值表验证。
5. 测试通过后人工复核引用是否真正支撑结论；在审校文档标记已核/待核，不用程序引用存在检查代替审校。提交 `content: author inverse-square companion lesson`。

## Task 4：实现伴读面板与证据卡

**Files:** 新增 `frontend/src/components/CompanionPanel.tsx`、`CompanionPanel.test.tsx`、`EvidenceCard.tsx`、`EvidenceCard.test.tsx`；修改 `frontend/src/App.tsx`、`frontend/src/components/LessonPanel.tsx`、`frontend/src/app.css`。

1. 写组件测试：首屏只展示目标、直觉、关键证据；推导/练习可独立展开；未覆盖页不显示旧课程；加载失败可重试且 PDF 保留。
2. 运行 `npm test -- src/components/CompanionPanel.test.tsx src/components/EvidenceCard.test.tsx`，确认失败。
3. 复用课程加载和 Formula/SourceCitation；显式回调派发导航事件。证据卡支持公式、段落、图像状态；图像优先已有资源，无安全端点时先保留原书定位。
4. 若必须新增图像端点：修改 `backend/src/rtr4_learning/api.py`、`backend/tests/test_api.py`；先添加未知块、越界路径、symlink、错误书籍、有效图片测试，再实现服务端块 ID 到可信资产的解析。不得直接拼 asset_path 成静态 URL。
5. 渲染提示/参考答案时用户主动展开；自评状态不能自动写成已掌握。将当前“标记已掌握”改为可撤销的已阅读/待复习/自测通过（自评）。
6. 跑前端测试，先对样板做真实浏览器走查，信息密度可接受后提交 `feat: add evidence-led companion panel`。

## Task 5：改善原书阅读交互

**Files:** 修改 `frontend/src/components/PdfReader.tsx`、`PdfReader.test.tsx`、`BlockOverlay.tsx`、`frontend/src/App.tsx`、`frontend/src/app.css`；新增 `frontend/src/components/BlockOverlay.test.tsx`。

1. 测试默认不铺满彩框、键盘聚焦可见、页眉页脚不进入定位列表、选中块可见、缩放后坐标一致、切页取消旧 render。
2. 运行 `npm test -- src/components/PdfReader.test.tsx src/components/BlockOverlay.test.tsx`，确认新增行为失败。
3. 增加适宽与受限缩放（初始拟 75–200%，实机调整）；Canvas 像素尺寸考虑 DPR 并设上限。保持单文档复用，禁止预渲染几十页。
4. 添加紧凑工具条、原书专注开关、可调分栏及键盘等价操作；小屏原书/伴读切换不卸载阅读状态。
5. 实现目标块滚入可视区与旁证返回滚动恢复；等待正确页 render 完成，不拿旧页 bbox 定位。
6. 回归测试并在实际大 PDF 下测试 1280/1920 桌面与窄屏、连续翻页、缩放、返回。提交 `feat: improve focused PDF reading controls`。

## Task 6：统一已有精讲内容与外部实践

**Files:** 修改 `content/rtr4-cn/chapter-05/section-5.1.json`、`section-5.2.json`、`section-5.2.2.json`、`backend/tests/test_companion_content.py`、`frontend/src/components/CompanionPanel.tsx` 及测试；更新审校记录。

1. 按 Task 3 标准，先给 5.1 知识点化并写发布测试，再逐项补齐冷暖插值、归一化、高光与实现差异。
2. 每点经过原书复核、目标测试后提交内容变更，不一次生成全部文本。相同流程迁移 5.2 的光照分解、余弦项与方向光。
3. 复核 5.2.2 其余点的奇点、有限范围和聚光锥；特别验证内外角术语和 smoothstep 参数顺序，区分原书模型与示例近似。
4. 为每个实践给中文目标、关键代码映射、要改的参数与预测问题；复制 ShaderToy 代码、channel 需求说明、复制失败退路均写测试。
5. 测试课程所有新字段来源有效；旧 sections 保留作兼容但不重复显示。内容迁移按节独立提交；外部实践 UI 单独提交。

## Task 7：阅读恢复与诚实的检索入口

**Files:** 新增 `frontend/src/readingStorage.ts`、`readingStorage.test.ts`；修改 `frontend/src/App.tsx`、`App.test.tsx`、`frontend/src/components/QuestionPanel.tsx`、`QuestionPanel.test.tsx`、`KnowledgeLessonPanel.tsx`。

1. 先测试损坏 JSON、localStorage 拒绝、过期点 ID、越界页、旧进度迁移与撤销，不让存储故障阻断阅读。
2. 实现书籍/内容版本命名空间，保存有效页、点、展开状态和版面；不持久化大 PDF/图像/临时旁证栈。首次无记录从默认页进入。
3. 测试检索入口默认折叠、文案显示第五章来源检索、来源跳转是旁证、检索失败不影响原书。当前术语预填让用户确认后提交，不暗中发送段落。
4. 运行相关 Vitest；刷新浏览器验证恢复状态，手动检查旧“已掌握”被标为自评而非测验结果。
5. 提交 `feat: resume reading and clarify source lookup`。

## Task 8：最终验收与发布

**Files:** 更新 `README.md`、`docs/runbooks/local-development.md`、`docs/reviews/2026-09-24-companion-content-review.md`。

1. 在 backend 运行 `.\.venv\Scripts\python.exe -m pytest -q`；真实数据 E2E 使用既有 RTR4_E2E_DATA_ROOT 和 RTR4_E2E_PROBE_ROOT，记录实际 pass/skip 而非照抄历史 336。
2. backend 运行 `.\.venv\Scripts\ruff.exe check src tests`；frontend 运行 `npm test` 与 `npm run build`；运行已有 `scripts/evaluate-chapter.ps1`，先阅读脚本参数后执行。
3. 用真实原书完成设计中 p110→p111→返回→自测→外部实践→刷新流程；再验未覆盖页、引用缺失、API 暂不可用、窄屏、键盘。
4. 测量大书冷启动和热翻页、连续导航内存趋势，与实施前基线比较；不承诺未测性能，不把测试通过当教学正确。
5. 检查 `git diff --check` 和精确暂存清单；更新覆盖范围、局限与启动方法，提交文档。维护每项提交记录，不回写历史日期。
6. 推送 feature/rtr4-learning；检查 main 工作树干净及远程分叉，普通 merge 保留历史后推送 main。冲突或远程新增提交先审查，禁止 force push。
7. 验证远端哈希，交付运行入口、改动列表、实际测试结果、提交数和仍未覆盖内容。

## 执行交接

推荐在当前独立工作树按任务顺序执行，每个阶段验证后继续，不默认使用子代理。也可在独立会话加载 executing-plans，按本文件批次实施。开始实施前以平方反比样板作为首个评审点，避免全量内容迁移后才发现交互方向不合适。
