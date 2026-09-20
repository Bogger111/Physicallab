# 12 实验公式审计 · 已确认发现（findings）

> 与机器扫描 `formula-audit.md` 配套：扫描只摆出风险点，这里记录**人工对照讲义 + 独立 probe 后确认的结论**。
> probe 脚本与原始输出都在 `C:\Users\Bogger\OneDrive\Desktop\Hermes File\bridge-audit\`（含 `logs/`）。

## 1. 交直流电桥（bridge）—— 已修复（2026-09-20）

三处算法级错误 + 一处字段语义问题，全部按讲义修正并有回归测试；真实学生读数从
`R0=−27.67 Ω / α=−0.129 /°C / rL=2160 Ω / Q=0.0144` 回到 `R0=50.359 Ω / α=0.003882 /°C / rL=4.628 Ω / Q=6.7245`。
细节见 `TEST_REPORT.md` 与 `交直流电桥数据处理审计.md`。

**教训（写进判据）**：测试通过只说明代码符合 fixture；旧 fixture 用同一条错公式反推 U0，测试因此永远绿。
公式映射、单位、参数语义、fixture 出身必须分别核对。

## 2. 巨磁电阻（gmr）· 磁电转换特性 —— 已修复（2026-09-20）

**讲义口径**（`text_dumps/巨磁电阻效应与应用/巨磁电阻.docx.txt`）：
- 步骤 63：励磁电流 −200→+200 mA 单调递增（20+ 点），再 +200→−200 mA 单调递减（20+ 点）；
- B = μ0·N·I/L，N=3250 匝、L=130 mm ⇒ **0.31416 Gs/mA**（adapter 的 `.31416` 与此一致 ✓）；
- 数据处理：「以 B 作横坐标、电压为纵坐标做出磁电转换特性曲线（**磁场增大减小造成的曲线差异，反映了材料的磁滞特性**）」；
- 原文明确「输出电压与励磁电流**不是全程线性**关系」。

**原缺陷**：`transfer` 用一条直线拟合全部 42 点，且 `direction(1增/-1减)` 列 **0 次引用**——
磁滞回线的两支互相抵消，灵敏度不可信；若学生把励磁电流记成幅值（丢符号），会静默给出 k≈0。

**修法**（`experiments/gmr/adapter.py`）：
- 按 `direction` 分增磁/减磁两支，各自最小二乘拟合；`sensitivity = (|k_增|+|k_减|)/2`，
  另给 `sensitivity_up` / `sensitivity_down` / `hysteresis`（两支在 B=0 处的输出差）与两支模型的 R²；
  绘图改为两支各自读数 + 各自拟合线（讲义要的就是这条回线）。
- `_finalize` 点名三类录入问题：只测单支、方向列未填、**励磁电流全为非负但方向含 −1（符号丢失，B 无法定向）**。
- 报告正文新增「数据合理性提醒」一行（原来只显示 errors），提醒不再只停留在网页上。

**验收 probe**（`probe_gmr_transfer.py` + `logs/audit-gmr-probe-fixed.txt`）：adapter 的两支斜率与零场磁滞
**逐项等于独立手算**（同一份数据、另写的 numpy 最小二乘）；丢符号的录入手工构造后得到明确警告而不是 k≈0。

**顺带记录**：`resistance` 方法的 `R = 2U/I_R` 系数（讲义图12 的 14/23 短路接法）尚未逐条核对，
列为 gmr 的下一个审计点；`tests/fixtures/gmr/typical.json` 的电阻数据同样由该式反推（自证风险）。

## 3. 待办优先级（来自机器扫描 + 讲义结构）

| 优先级 | 实验 | 理由 |
|---|---|---|
| ~~P0~~ | ~~gmr 磁电转换特性~~ | **已修**（见上）；剩下 `resistance` 的 `R=2U/I_R` 系数待核对 |
| P1 | nmr（γ=gμN/h 拟合）、surface-tension（定标 K 拟合→σ）、thermal-conductivity（dT/dt 邻域拟合） | 拟合把输入错误放大成物理量（bridge 的 α 就是这样翻车的） |
| P1 | viscosity（η 依赖 ρ、球径、速度多单位）、michelson（λ=2Δd/N，unit_factor 标记） | 多单位换算 + 单点系数 |
| P2 | polarization、sound-light、solar-cell、multimeter、photoelectric-franck-hertz | 扫描未命中高风险标记，但 fixture 仍为 synthetic-only，需要一组手算 probe 才算过线 |

每个实验的验收动作固定：**讲义公式 → 手算一组可手验的 probe → 喂 adapter → 对比**；
对不上就是 bug；并检查 `verified=false / synthetic-only` 的 fixture 是否由实现反推。
