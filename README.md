# RTR4 学习系统

RTR4 多模态学习应用，包含 Python 后端与 React 前端。

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
npm test -- --run
npm run dev
```
