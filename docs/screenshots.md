# 项目截图

README 引用的界面截图都存放在 `docs/images/`，全部来自真实运行的开发环境（本机 `npm run dev` + 后端 `uvicorn`），不是设计稿。

| 文件 | 位置 | 说明 |
|---|---|---|
| `docs/images/home.png` | 首页 | 两个入口（普通实验 / AI 实验共建）与工作流程介绍 |
| `docs/images/experiments.png` | 实验库 | 12 个大学物理实验，可按分类与关键词筛选 |
| `docs/images/workspace.png` | 实验工作台 | 子实验切换、数据录入表格、图片识别入口与报告按钮 |
| `docs/images/cobuild-intro.png` | 实验详情页 | 「参与 PhysLab AI 实验共建」说明卡片（自愿 / 不影响实验 / 上传前脱敏 / 可撤回） |
| `docs/images/report.png` | 实验工作台底部 | 计算、绘图与报告导出区域 |

## 重新生成截图

```bash
# 1) 启动本地环境
cd backend  && uvicorn app.main:app --port 8001      # 后端
cd frontend && npm run dev                            # 前端（默认 3000，指向后端 8001）

# 2) 打开对应页面截图并覆盖同名文件
#    首页                http://localhost:3000/
#    实验库              http://localhost:3000/experiments/
#    实验工作台          http://localhost:3000/experiments/multimeter/workspace
#    AI 共建说明          http://localhost:3000/experiments/multimeter?mode=collection
#    报告区域            http://localhost:3000/experiments/multimeter/workspace
```

建议：桌面视口 1440×900，截取时保留页面外边距，避免截到滚动条或开发工具；截图中不要出现真实姓名、学号等个人信息（示例实验使用合成数据）。

## 需要补充真实截图的情况

如果某张截图暂时没有（例如还没有可展示的报告样例），请在该位置保留占位图片并在本文件注明「待补充」，不要引用不存在的文件——README 中的链接必须全部有效。
