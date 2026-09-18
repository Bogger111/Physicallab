# Changelog

PhysLab 的版本记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## 2.0 — 2026-09-18

PhysLab 2.0：从「实验数据处理工具」升级为具备真实数据共建能力的实验 AI 平台。

### Added

- **AI 实验共建模式**：首页与实验库提供「普通实验」和「AI 实验共建」两个入口，进入同一个实验工作台（`?mode=collection`），不复制任何实验页面、不额外要求填写表单
- **OCR 数据采集闭环**：自愿上传 → 私有存储会话 → 报告成功后确认数据 → 切分为单数值训练样本 → 导出训练集
- **OpenCV 实验表格分割**：以本仓库渲染的标准记录表为模板，按稳定字段 ID 定位单元格并裁出单个手写数值，含配准校验、质量筛选与表格线清理
- **PhysLab_OCR 数据导出**：`python -m backend.ocr_dataset.export` 把已确认的共建会话打包成 `physlab_ocr_dataset.zip`（`dataset/{images,labels.csv,manifest.json}`），解压即可直接训练
- **数据贡献反馈**：上传后的贡献卡片（实验类型 / 保存状态 / 后续动作 / 预计生成样本数）与实验完成后的感谢弹窗，含「撤回本次贡献」
- **开发者统计面板**：`GET /api/data-collection/stats`（会话数、已确认数、样本数、按实验分布）与 `/dev/data-collection` 页面
- **实验文件**：每个实验的标准记录表、数据特征参考（典型数据形态）与报告模板
- **模块化实验架构**：Experiment Registry + 每个实验独立的 config/adapter，新增实验不再需要改动中央引擎

### Improved

- 用户上传体验：同屏完成同意 → 选图 → 上传，失败不影响实验功能；错误提示改为学生可读的措辞
- 实验工作流程：实验库可直接下载记录表，工作台一屏完成录入 → 校验 → 计算 → 绘图 → 导出
- 输入提示：每个字段的建议范围改为与记录表印刷量程一致（此前部分字段显示 ±10000 的无意义提示）

### Privacy

- 用户授权机制：只有明确勾选同意才会保存；未同意时接口直接拒绝，普通模式不产生任何会话
- 本地数据隔离：`backend/data_collection/`（原图、metadata、数据集）与 `.env.local` 全部被 `.gitignore` 排除，不进仓库
- 图片脱敏：保存前重新编码以去除拍摄时间、位置等照片信息；不记录 IP、浏览器指纹与账号信息
- 撤回即删除：删除会话原图、metadata，以及由它生成的数据样本

### Fixed

- 修复导出路径在零样本时的崩溃（空数据集现在也会生成合法的空压缩包）
- 修复宽单元格裁切被误判为空白、竖直表格线残影被并入裁切的问题
- 历史 `scripts/export_ocr_dataset.py` 现在接受数字字符串（`"22.090"` 不再被静默丢弃），且不再把整页图片复制出私有存储

## 2.0.0-beta.1 — 2026-09-16

- 统一实验 schema 与后端校验（warning-first 的期望范围）
- 合并 `photoelectric-franck-hertz` 目录条目，同时保留旧 ID 与路由
- OCR provider 边界（`RapidOCRProvider`，可选 `PaddleOCRProvider`）与单元格反馈存储
- 匿名分析、OCR 纠正指标、consent-first 的数据集导出脚本
- 保存报告、绘图、记录表与偏振光/声速光速专用工作台的兼容性
- 公开测试版提示条与反馈入口

## 更早

- 1.x：单实验计算工具，覆盖偏振光与声速光速实验
