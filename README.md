# PhysicsLab — 大学物理实验助手

实验结束，数据处理也结束。

## 功能

- **实验前**: 下载标准数据记录表，打印后带入实验室
- **实验中**: 在纸质表格上手写记录实验数据
- **实验后**: 上传/输入数据，自动完成计算、拟合与绘图

## 技术栈

- **前端**: Next.js + TypeScript + Tailwind CSS + shadcn/ui + Lucide React
- **后端**: FastAPI + NumPy + SciPy + Matplotlib
- **实验计算**: 复用经过实际实验验证的 Python 代码

## 项目结构

```
physicslab/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 应用
│   │   └── routers/           # API 路由
│   ├── experiments/
│   │   └── polarization/      # 偏振光实验
│   │       ├── theory.py      # 理论公式 (复用)
│   │       ├── angles.py      # 角度工具 (复用)
│   │       ├── adapter.py     # 适配器层
│   │       └── config.json    # 实验配置
│   ├── tests/                 # 回归测试
│   └── requirements.txt
├── frontend/                  # Next.js 前端
│   ├── src/
│   │   ├── app/               # 页面
│   │   │   ├── page.tsx       # 首页
│   │   │   ├── experiments/   # 实验库 + 详情 + 工作台
│   │   │   └── layout.tsx     # 布局
│   │   ├── components/        # 组件
│   │   └── lib/               # 工具函数
│   └── public/
│       └── record-sheets/     # 实验记录表 PDF
└── README.md
```

## 快速启动

### 后端
```bash
cd backend
uv venv
uv pip install -r requirements.txt
python run.py
# API 运行在 http://localhost:8000
```

### 前端
```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:3000
```

### 运行测试
```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/ -v
```

## 当前可用实验

### 偏振光与双折射 (polarization)
- 马吕斯定律: I vs cos²θ 线性拟合
- 半波片: ΔP2 vs ΔC 关系验证
- 四分之一波片: 椭圆偏振光强分布
- 圆偏振光: 光强恒定性验证

## 新增实验

新增实验只需:
1. 创建 `backend/experiments/<exp>/` 目录
2. 添加 Python 计算代码 + `config.json`
3. 在前端 `src/lib/experiments.ts` 注册配置
4. 无需重写 UI 组件

## 设计原则

- 中文界面，浅色模式
- Apple / Linear 克制感
- 图表和数据是视觉中心
- PC/Mac/iPad 好用，手机可查看
- 不做 AI 魔法按钮

## 运行说明（2026-09-09 更新）

- 后端：`cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001`
  （8000 端口残留了一个无法在普通会话终止的旧进程，故统一走 8001；如需清掉请用管理员终端或重启后删除。）
- 前端：`cd frontend && npm run build && npx next start -p 3000`；构建会读取 `.env.local`（NEXT_PUBLIC_API_URL=http://localhost:8001）。
- 报告管线（新增）：`backend/experiments/polarization/{reports.py,docbuild.py}`。
  - `GET  /api/record-sheets/polarization.{docx|pdf}`：空白记录表（Word / 紧凑 PDF，无填充色）
  - `POST /api/experiments/polarization/report?part=basic|advanced&fmt=docx|pdf`：基准/拓展报告
- 依赖新增：python-docx、reportlab（见 backend/requirements.txt）。
