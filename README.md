# OpenLearnPDF

面向大型 PDF 书籍的本地多模态学习应用。当前打通《Real-Time Rendering 4th》中文版第五章闭环，包括正文、公式、图片、引用检索、问答和逐章节教学。

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
