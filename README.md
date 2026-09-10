# PhysicsLab — 大学物理实验助手

实验结束，数据处理也结束。

实验库现包含 13 个实验。偏振光与声速/光速保留专用工作区，其余 11 个实验由
`backend/experiments/general/configs.json` 驱动，共用数据录入、计算、绘图、记录表和报告流程。

## 功能

- **实验前**: 下载标准数据记录表，打印后带入实验室
- **实验中**: 在纸质表格上手写记录实验数据
- **实验后**: 上传/输入数据，自动完成计算、拟合与绘图

## 技术栈

- **前端**: Next.js + TypeScript + Tailwind CSS + shadcn/ui + Lucide React
- **后端**: FastAPI + NumPy + SciPy + Matplotlib
- **实验计算**: 独立 Python 计算引擎，由回归测试与合成 fixture 验证

## 验证边界

- 算法单元测试、API 合约测试与合成 fixture 文档 QA 已覆盖。
- 尚未使用完整真实实验数据完成端到端验证，不对真实实验结果作必然正确的保证。

## 项目结构

```
physicslab/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 应用
│   │   └── routers/           # API 路由
│   ├── experiments/
│   │   ├── polarization/      # 偏振光实验
│   │   ├── soundlight/        # 声速与光速实验
│   │   └── general/           # 其余 11 个配置驱动实验
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
├── docs/                      # 讲义覆盖审查与发布说明
├── scripts/                   # 可重复执行的 QA / 报告脚本
├── artifacts/                 # 记录表审查与模拟报告产物
└── README.md
```

## 快速启动

### 后端
```bash
cd backend
uv venv
uv pip install -r requirements.txt
python run.py
# API 运行在 http://localhost:8001（生产命令见下方运行说明）
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

共 13 个：万用表、交直流电桥、偏振光、光电效应、弗兰克-赫兹、声速光速、
太阳能电池、巨磁电阻、核磁共振、液体粘滞系数、液体表面张力、固体导热系数、
迈克尔逊干涉。

通用实验接口：

- `GET /api/experiments/{experiment_id}/config`
- `POST /api/experiments/{experiment_id}/process`
- `GET /api/record-sheets/{experiment_id}.docx|pdf`
- `POST /api/experiments/{experiment_id}/report?fmt=docx|pdf`

所有实验报告均为一份完整报告，按“全部表格 → 全部图片 → 详细数据分析 →
拓展、建议、误差分析与总结”排列，相邻部分强制换页。

### 偏振光与双折射 (polarization)
- 马吕斯定律: I vs cos²θ 线性拟合
- 半波片: ΔP2 vs ΔC 关系验证
- 四分之一波片: 椭圆偏振光强分布
- 圆偏振光: 光强恒定性验证

### 声速光速的测量 (sound-light)
- 空气共振法、水中相位法、时差法测声速
- 正弦波相位法、方波相位法、李萨如法测光速

## 新增实验

新增同类实验的主要步骤:
1. 创建 `backend/experiments/<exp>/` 目录
2. 添加实验 `config.json` 与 Calculation Adapter
3. 注册 API 路由和前端实验入口
4. 复用现有记录表、报告和工作台组件；特殊交互再增加薄适配层

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
  - `POST /api/experiments/polarization/report?fmt=docx|pdf`：四部分完整报告
  - `POST /api/experiments/sound-light/report?fmt=docx|pdf`：四部分完整报告
  - 完整报告统一按“全部表格 → 全部图片 → 详细数据处理 → 拓展、建议、误差分析与总结”排列，各部分强制换页。
- 依赖新增：python-docx、reportlab（见 backend/requirements.txt）。

## QA 产物

- `docs/validation/lecture-coverage-audit.md`：讲义必做/选做项目覆盖审查。
- `artifacts/record-sheet-audit/`：空白记录表的 Word/PDF 与缩略图审查。
- `artifacts/simulation-reports/`：13 个实验的合成数据模拟报告、结果汇总和缩略图。
- `scripts/generate_simulated_reports.py`：重新生成模拟报告；结果只用于算法与排版 QA，不能替代真实数据验收。

## GitHub Pages 部署边界

GitHub Pages 只能托管 `frontend/` 的静态页面，不能运行 FastAPI、NumPy、SciPy 或报告生成服务。要让在线工作台真正计算数据，后端必须部署到独立的 HTTPS 服务，并通过 `NEXT_PUBLIC_API_URL` 配置给前端；如果只发布 Pages 而不部署后端，实验浏览和静态记录表可以打开，数据处理与报告下载将不可用。
