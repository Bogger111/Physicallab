# PhysKiller 真实可用性回归测试报告

日期：2026-09-17

## 验证边界

本轮建立的是离线、可重复的 API 与报告回归测试。数据来自仓库原有单元测试、报告测试和配置结构，并补齐到当前公开表格要求的行数。测试不访问 Google Cloud、GitHub Pages、外部网络或用户数据。

这些结果证明当前代码路径、合成 fixture 和文档生成链可以稳定执行；它们不证明完整真实实验数据一定正确。仍需学生、助教和教师使用真实记录进行端到端验收。

## 公开实验与真实计算入口

| 公开实验 | ID | 类型 | 当前计算入口 | 状态 |
|---|---|---|---|---|
| 偏振光与双折射 | `polarization` | 专用 | `experiments.polarization.adapter.PolarizationAdapter` | 通过 |
| 声速光速的测量 | `sound-light` | 专用、逐方法处理 | `experiments.soundlight.engine.process_method` | 通过 |
| 万用表的组装与校准 | `multimeter` | 配置驱动 | `experiments.general.engine._multimeter` | 通过 |
| 交直流电桥的原理及应用 | `bridge` | 配置驱动 | `experiments.general.engine._bridge` | 通过 |
| 太阳能电池特性 | `solar-cell` | 配置驱动 | `experiments.general.engine._solar` | 通过 |
| 巨磁电阻效应及应用 | `gmr` | 配置驱动 | `experiments.general.engine._gmr` | 通过 |
| 核磁共振实验 | `nmr` | 配置驱动 | `experiments.general.engine._nmr` | 通过 |
| 落球法测液体粘滞系数 | `viscosity` | 配置驱动 | `experiments.general.engine._viscosity` | 通过 |
| 液体表面张力系数测量 | `surface-tension` | 配置驱动 | `experiments.general.engine._surface` | 通过 |
| 稳态法测固体导热系数 | `thermal-conductivity` | 配置驱动 | `experiments.general.engine._thermal` | 通过 |
| 迈克尔逊干涉实验 | `michelson` | 配置驱动 | `experiments.general.engine._michelson` | 通过 |
| 光电效应与弗兰克-赫兹实验 | `photoelectric-franck-hertz` | 合并公开入口 | `process_experiment` 分派至 `_photoelectric` 与 `_franck` | 通过 |

API 仍保留带 `legacy: true` 的旧 `photoelectric` 目录项；公开数量按前端实际过滤后的 12 项计算。

## Fixture 体系

每个公开实验在 `backend/tests/fixtures/<experiment_id>/` 下包含：

- `typical.json`：完整合成数据，覆盖 config、schema、validate、process、图表、DOCX 和 PDF。
- `boundary.json`：继承 typical 数据，并标记或修改配置/算法边界点。
- `invalid.json`：继承 typical 数据，制造一个缺失或非法必填读数。

偏振光和声速光速的边界值来自专用配置和引擎约束。其他实验尚无经过真实实验确认的统一合理区间，因此边界 fixture 主要覆盖配置预填端点、扫描端点、零载荷或起始时刻，并在文件中保留 `structure-derived` 说明。后续拿到真实数据后应优先替换这些边界依据，不应据此宣称科学范围已经验证。

## 自动回归覆盖

新增的参数化测试覆盖：

- 12 项公开目录与实际计算入口清单；
- 每项 `typical`、`boundary`、`invalid` 三类 fixture；
- `GET config` 和 `GET schema`；
- `POST validate`；
- 偏振光专用 process、声速光速逐方法 process、通用 process；
- 配置声明的结果字段；
- 所有解析后的数值结果必须为有限数；
- 生成的图表必须是有效 PNG；
- 12 项 DOCX 和 12 项 PDF 均通过真实报告 API 生成并校验文件结构。

完整后端测试结果：`180 passed, 2 warnings`，运行时间约 72 秒。两条 warning 来自 FastAPI/Starlette 当前测试客户端的依赖弃用提示，不影响测试结果。

## 本轮发现并修复的问题

### 配置与校验问题

通用实验和声速光速的 canonical schema 曾把表格列默认标记为非必填，导致部分填写的行仍可能返回 `valid: true`。现已做最小修复：表格列默认必填；参数仍保持原有默认值和可选行为。科学计算公式没有改动。

### 测试数据漂移

旧迈克尔逊测试数据没有包含当前配置已有的累计圈数、光路编号和定域标记。旧测试直接调用计算函数时没有暴露该问题；严格校验后出现失败。现已按 `configs.json` 的现有字段补齐测试数据，没有修改迈克尔逊公式。

### 测试实现问题

首轮测试曾在完整 JSON 文本中搜索字符串 `NaN`，而 PNG Base64 可能偶然包含相同字符。现改为解析 JSON 后递归检查实际数值，并逐个校验预期结果字段。

## 未发现的公式问题

本轮没有发现需要修改科学公式的 bug。现有关键物理结果回归、专用实验算法测试、通用引擎测试和新增 API 回归测试均通过。

## 架构问题与后续事项

- 三类 API 请求形状不同：偏振光一次处理全部子实验，声速光速一次处理一个方法，通用实验使用 `{data: ...}`。测试需要薄适配层。
- `backend/app/main.py` 集中了专用和通用路由，规模较大，但本轮未重构。
- API 目录保留旧近代物理入口，前端再依据 `legacy` 过滤；公开目录的定义不是单一来源。
- 多数通用实验合理范围尚未由真实实验数据确认，当前 boundary fixture 只能作为结构和算法边界回归。
- 报告生成包含 Matplotlib、DOCX 和 PDF，完整套件约需 72 秒；后续 CI 可将快速计算测试和完整文档测试拆成两个 job，但不应删除完整文档回归。

