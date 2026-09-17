# PhysKiller 2.0 工程说明

## 统一实验标准

通用实验配置由 `backend/experiments/schema.py` 在加载时补充 `schemaVersion`、metadata、字段类型、必填标志、合理范围和小数位建议。原有 `columns`、`params`、`results` 和请求结构保持兼容。后端 `validate_payload` 是 canonical validation；超出常见范围和小数位只产生 warning，非有限值、非数字和明确必填缺失才产生 error。

偏振光和声速光速保留专用计算适配器，同时通过配置接口暴露同样的 schema 元数据。新增实验优先增加配置与 Calculation Adapter，而不是复制工作台。

## 光电效应与弗兰克-赫兹

公开实验入口为 `photoelectric-franck-hertz`。旧的 `photoelectric` 和 `franck-hertz` ID、API、计算和报告仍保留，方便旧链接继续访问。合并入口使用两套原有计算适配器并合并结果、图像和报告表格。

## OCR Beta 与数据闭环

默认 provider 是 RapidOCR 3.9.2/PP-OCRv6-small ONNX Runtime；可以通过 `PHYSICSLAB_OCR_PROVIDER=paddleocr` 选择可选的 PP-OCRv5 provider（部署环境需额外安装 PaddleOCR）。OCR 只返回候选数字，用户在浏览器逐格复核后才会填入工作台。

原有逐单元格 OCR 反馈仍只有在用户明确同意且将单元格标记为 verified 后才写入 SQLite。

此外提供独立、默认关闭的原始记录表贡献旁路。设置 `ENABLE_DATA_COLLECTION=true` 后，前端才显示该入口。用户必须主动选择已去除姓名、学号、电话、微信、面部、证件和其他个人信息的图片并勾选同意；未同意时后端不创建目录或文件。图片解码后重新编码为 JPEG，从而移除 EXIF 和嵌入元数据。会话只使用服务端 UUID，不从文件名建立身份关联，也不记录 IP、请求头、浏览器指纹或用户账户。

上传后的会话处于 `pending_confirmation`。只有报告下载成功，前端才把本次最终数据提交为 `confirmed` 标签；后续修改并再次生成报告会更新同一会话并递增 revision。字段 ID 由后端实验配置生成，不依赖 DOM 顺序。收集错误由独立接口处理，不会改变 validate、process 或 report 的结果。

本地实现位于 `backend/data_collection/raw` 与 `metadata`，存储边界为 `CollectionStorage` / `LocalCollectionStorage`。可用 `PHYSICSLAB_COLLECTION_ROOT` 改变根目录。Cloud Run 本地文件系统是临时的；正式启用前应替换为持久化存储实现。

离线数据集构建位于 `backend/ocr_dataset`，只读取已同意且已确认的会话，按最新 revision 导出单值训练裁剪：`python -m backend.ocr_dataset.build --output data/ocr_dataset`。裁切坐标来自本仓库自己渲染的空白记录表（`layouts/<experiment_id>.json`，`fields` + `anchors` + `lattice`），构建前先做模板配准与倒置检测，配准不通过时整个会话进入 `rejected.csv` 而不是猜测字段；标签保留提交时的字符串（`"22.090"` 不会被转成 `22.09`），输出 `labels.csv` / `rejected.csv` / `manifest.json` / `preview/contact_sheet.png`，且从不复制整页原图。每个实验当前只覆盖记录表第 1 页，因为一个会话只保存一张图片。旧的 `scripts/export_ocr_dataset.py` 仍可导出 `manifest.csv` 与未裁剪原图副本，传入 `--database` 时执行旧版 SQLite 单元格反馈导出，与本管线无关。

## 匿名分析

`/api/analytics/events` 接受白名单事件和匿名 session ID，过滤 rows、data、image、raw_text 等内容。SQLite 写入失败会静默降级，不影响计算和报告。`/api/analytics/summary` 提供事件计数、实验打开排行、OCR confirmed/corrected 与 correction rate。

## 数据特征参考

每个公开实验在 `backend/experiments/<experiment>/data_reference.json` 中维护一份典型数据参考（`name` / `field` / `example` / `pattern`）。前端实验详情页在「下载记录表」区域下方渲染成一张卡片，用来说明各测量量的量级、相邻点间距与正常趋势。

- 数据是**信息性**的：卡片没有输入控件、不调用计算链、也不会预填记录表。
- 数值由实验自身的公式与标准值反推，并保持手写精度（≤4 位小数、无科学计数法）：例如表面张力由 σ = 0.07275 N/m 反解出 ΔU ≈ 15.6 mV 与 h ≈ 37.1 mm。
- `backend/tests/test_data_reference.py` 会重新推导这些数值（马吕斯定律、声速、光速、Cu50 斜率、太阳能电池填充因子与充电截止电压、GMR 单支灵敏度、核磁旋磁比、粘滞系数、表面张力、迈克尔逊波长、普朗克常量、弗兰克-赫兹峰间距），公式不符即测试失败。
- `field` 指向采集层的稳定字段 ID（`method.rows.*.key`），与 `valid_stable_field_id` 校验一致；派生量填 `null`。

## 验证边界

自动化测试验证 schema 合法性、数值校验、OCR 反馈同意门槛、指标计算、API 合约和原有实验回归。合成 fixture 不能证明真实实验结果或真实手写识别准确率；正式 benchmark 需要按书写者隔离的真实标注单元格数据，并重点报告 Cell Exact Match Accuracy。
