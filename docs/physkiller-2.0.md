# PhysKiller 2.0 工程说明

## 统一实验标准

通用实验配置由 `backend/experiments/schema.py` 在加载时补充 `schemaVersion`、metadata、字段类型、必填标志、合理范围和小数位建议。原有 `columns`、`params`、`results` 和请求结构保持兼容。后端 `validate_payload` 是 canonical validation；超出常见范围和小数位只产生 warning，非有限值、非数字和明确必填缺失才产生 error。

偏振光和声速光速保留专用计算适配器，同时通过配置接口暴露同样的 schema 元数据。新增实验优先增加配置与 Calculation Adapter，而不是复制工作台。

## 光电效应与弗兰克-赫兹

公开实验入口为 `photoelectric-franck-hertz`。旧的 `photoelectric` 和 `franck-hertz` ID、API、计算和报告仍保留，方便旧链接继续访问。合并入口使用两套原有计算适配器并合并结果、图像和报告表格。

## OCR Beta 与数据闭环

默认 provider 是 RapidOCR 3.9.2/PP-OCRv6-small ONNX Runtime；可以通过 `PHYSICSLAB_OCR_PROVIDER=paddleocr` 选择可选的 PP-OCRv5 provider（部署环境需额外安装 PaddleOCR）。OCR 只返回候选数字，用户在浏览器逐格复核后才会填入工作台。

只有用户明确同意匿名采集且将单元格标记为 verified，反馈才写入 SQLite。默认不保存整张表格图片；当前反馈接口的 `cell_image_path` 仅为未来开发导出预留。`scripts/export_ocr_dataset.py` 只导出有明确同意、已确认且确实存在单元格图片的样本。

## 匿名分析

`/api/analytics/events` 接受白名单事件和匿名 session ID，过滤 rows、data、image、raw_text 等内容。SQLite 写入失败会静默降级，不影响计算和报告。`/api/analytics/summary` 提供事件计数、实验打开排行、OCR confirmed/corrected 与 correction rate。

## 验证边界

自动化测试验证 schema 合法性、数值校验、OCR 反馈同意门槛、指标计算、API 合约和原有实验回归。合成 fixture 不能证明真实实验结果或真实手写识别准确率；正式 benchmark 需要按书写者隔离的真实标注单元格数据，并重点报告 Cell Exact Match Accuracy。
