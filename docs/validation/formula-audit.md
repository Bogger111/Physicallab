# 12 实验公式审计清单（audit oracle）

> 由 `backend/scripts/audit_formula_oracle.py` 生成。它只做**机械部分**：把实现面、常数、fixture 出身和风险点摆出来；
> **物理部分（对照讲义原文、独立手算 probe）必须人工完成**，结论写在本表最后两列。

## 判据（来自 bridge 的教训）

1. **公式映射**：adapter 里每个变量是否就是讲义公式里的那个量（bridge 把卧式公式的 `R` 取成了桥臂 1000 Ω 而不是预平衡 Rn）。
2. **单位**：`Cn` 是 μF 还是 F、`U0` 是 mV 还是 V，换算是否只在一处发生。
3. **参数语义**：固定实验条件 vs 现场实测量（后者不该有 default、不该在空白记录表预填）。
4. **fixture 是否循环自证**：测试数据如果由 adapter 的（错）公式反推，测试全绿也不能证明结果对。

验收口径：**用讲义公式独立手算一组可手验的 probe → 喂给 adapter → 对比**；对不上就是 bug，不是 fixture 过期。

## 机器扫描结果

| 实验 | 方法数 | 风险标记 | 含拟合/派生结果量的方法（优先手算） | fixture | 手算 probe | 结论 |
|---|---|---|---|---|---|---|
| 偏振光与双折射（polarization） | 4 | fit、circular_fixture |  | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| sound-light（sound-light） | 6 | circular_fixture |  | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 万用表的组装与校准（multimeter） | 6 | — | 直流电压档校准、直流电流档校准、电阻档校准、未知电阻测量 | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 交直流电桥的原理及应用（bridge） | 5 | fit、unit_factor、inverse_solve、circular_fixture | 平衡直流电桥、卧式电桥测 Cu50、热敏电阻（选做） | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | **已完成**（3 处算法错误 + 记录表语义，见 bridge 审计报告） | 已修 |
| 太阳能电池特性（solar-cell） | 7 | circular_fixture |  | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 巨磁电阻效应及应用（gmr） | 3 | fit、circular_fixture | 磁电转换特性 | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 核磁共振实验（nmr） | 4 | fit、circular_fixture | 1H 核磁共振、19F 核磁共振、纯水样品 g 因子（选做） | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 落球法测液体粘滞系数（viscosity） | 3 | circular_fixture |  | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 液体表面张力系数测量（surface-tension） | 5 | fit、circular_fixture | 力敏传感器定标、拉脱法、毛细管法、盐水表面张力·拉脱法（拓展选做） | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 稳态法测固体导热系数（thermal-conductivity） | 3 | fit、circular_fixture | 自然冷却曲线 | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 迈克尔逊干涉实验（michelson） | 2 | unit_factor、circular_fixture | He-Ne 激光波长测量 | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |
| 光电效应与弗兰克-赫兹实验（photoelectric-franck-hertz） | 9 | — | 零电流法测普朗克常数、补偿法测普朗克常数（选做）、峰值位置与逐差 | boundary.json:structure-derived boundary coverage; replace with lab-confirmed ranges when available；invalid.json:intentionally incomplete required measurement；typical.json:synthetic-only | 待做 | 待审 |

## 逐实验实现面

### 偏振光与双折射（`polarization`）

- adapter：`experiments/polarization/adapter.py`
- 风险标记：fit、circular_fixture
- 同时 import adapter 又断言数值的测试模块：tests/test_documents.py、tests/test_polarization.py
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_api_contract.py`：`0.0`, `0.85`, `0.9`, `12`, `20`, `200`, `30`, `30.0`, `360`, `5`, `50`
  - `tests/test_data_collection.py`：`20`, `200`, `80`
  - `tests/test_data_reference.py`：`0.3`, `0.9`, `2.0`, `20`, `30`, `5`, `50`, `6`, `90`
  - `tests/test_documents.py`：`12`, `20`, `30.0`, `360`, `6`, `7`, `8`, `9`, `90`
  - `tests/test_polarization.py`：`0.0`, `2.0`, `20`, `30`, `360`, `5`, `7`, `90`
  - `tests/test_public_experiment_usability.py`：`12`, `200`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`0.0`, `150`, `200`, `0.3`, `30.0`, `6`, `8`, `5.5`, `80`, `1.6`, `0.85`, `52`, `5`, `0.6`, `44`, `2.2`, `12`, `13`, `9`, `0.9`, `2.0`, `50`, `14`, `360`, `361`, `30`, `90`, `7`, `40`, `20`, `1.35`, `1.1`, `1.3`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 马吕斯定律 | 是 | — | — | — |
| 半波片 | 是 | — | — | — |
| 四分之一波片 | 是 | — | — | — |
| 圆偏振光 | 选做 | — | — | — |


- 手算 probe：待做（优先级：高（拟合把输入错误放大成物理量））
- 讲义对照结论：待填写

### sound-light（`sound-light`）

- adapter：`experiments/soundlight/engine.py`
- 风险标记：circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_data_reference.py`：`6`
  - `tests/test_documents.py`：`6`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`6`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 空气中共振法测声速 | 选做 | 环境温度 t(°C)=25.0；共振频率 f(kHz)=38.0 | — | — |
| 水中相位法测声速 | 选做 | 水中超声波频率 f(MHz)=1.0 | — | — |
| 飞行时间法测声速 | 选做 | — | — | — |
| 光速测量（正弦法） | 选做 | 调制频率 f(MHz)=150.0；光速参考值 c_ref(m/s)=299800000 | — | — |
| 光速测量（方波） | 选做 | 调制频率 f(MHz)=150.0；光速参考值 c_ref(m/s)=299800000 | — | — |
| 光速测量（李萨如法） | 选做 | 调制频率 f(MHz)=150.0；光速参考值 c_ref(m/s)=299800000 | — | — |


- 手算 probe：待做（优先级：中（fixture 由实现反推＝自证循环））
- 讲义对照结论：待填写

### 万用表的组装与校准（`multimeter`）

- adapter：`experiments/multimeter/adapter.py`
- 风险标记：无
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 直流电压档校准 | 是 | — | U设(mV)；U测(mV) | 校准斜率；截距；R²；最大绝对误差 |
| 直流电流档校准 | 是 | — | I设(mA)；I测(mA) | 校准斜率；截距；R²；最大绝对误差 |
| 电阻档校准 | 是 | — | R设(kΩ)；R测(kΩ) | 校准斜率；截距；R²；最大绝对误差 |
| 未知电阻测量 | 是 | — | 标准表读数(kΩ)；组装表读数(kΩ) | 标准值均值；测量值均值；相对误差 |
| 交流电压档校准（选做） | 选做 | — | U设(mV)；U测(mV) | 校准斜率；截距；R²；最大绝对误差 |
| 交流电流档校准（选做） | 选做 | — | I设(mA)；I测(mA) | 校准斜率；截距；R²；最大绝对误差 |

- **直流电压档校准** 公式（实现自述）：
  - `\Delta U_i=U_{{\rm meas},i}-U_{{\rm set},i}`
  - `U_{\rm meas}=kU_{\rm set}+b`
- **直流电流档校准** 公式（实现自述）：
  - `\Delta I_i=I_{{\rm meas},i}-I_{{\rm set},i}`
  - `I_{\rm meas}=kI_{\rm set}+b`
- **电阻档校准** 公式（实现自述）：
  - `\Delta R_i=R_{{\rm meas},i}-R_{{\rm set},i}`
  - `R_{\rm meas}=kR_{\rm set}+b`
- **未知电阻测量** 公式（实现自述）：
  - `\varepsilon_r=\frac{|\overline{R}_{\rm meas}-\overline{R}_{\rm ref}|}{\overline{R}_{\rm ref}}\times100\%`
- **交流电压档校准（选做）** 公式（实现自述）：
  - `\Delta U_i=U_{{\rm meas},i}-U_{{\rm set},i}`
  - `U_{\rm meas}=kU_{\rm set}+b`
- **交流电流档校准（选做）** 公式（实现自述）：
  - `\Delta I_i=I_{{\rm meas},i}-I_{{\rm set},i}`
  - `I_{\rm meas}=kI_{\rm set}+b`

- 手算 probe：待做（优先级：常规）
- 讲义对照结论：待填写

### 交直流电桥的原理及应用（`bridge`）

- adapter：`experiments/bridge/adapter.py`
- 风险标记：fit、unit_factor、inverse_solve、circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_api_contract.py`：`120`, `5000`
  - `tests/test_data_reference.py`：`1e-3`, `1e-6`, `273.15`
  - `tests/test_general_experiments.py`：`120`, `1e-3`, `1e-6`, `273.15`, `298.15`, `5000`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`5000`, `120`, `1e-6`, `1e-3`, `273.15`, `298.15`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 平衡直流电桥 | 是 | Ra(Ω)=1000；Rb(Ω)=5000；电源电压 Us(V)=3.0；室温 t(°C)=实测留空 | 平衡电阻 Rn(Ω) | Rx 均值；室温理论值；相对误差 |
| 卧式电桥测 Cu50 | 是 | 电源 Us(V)=3；预平衡 Rn(Ω)=实测留空[必填] | 温度 t(°C)；输出 U0(mV) | 拟合 R0；R0 相对误差；温度系数 α；R²；α 相对误差 |
| 交流电桥测电容 | 是 | Ra(Ω)=100；Rb(Ω)=120；频率 f(Hz)=1000 | Cn(μF)；Rn(Ω) | Cx 均值；rC 均值；tanδ 均值 |
| 交流电桥测电感 | 是 | Ra(Ω)=100；Rb(Ω)=100；频率 f(Hz)=1000 | Cn(μF)；Rn(Ω) | Lx 均值；rL 均值；Q 均值 |
| 热敏电阻（选做） | 选做 | 电源 Us(V)=3；桥臂 Ra=Rb(Ω)=100；预平衡 Rn(Ω)=实测留空 | 温度 t(°C)；输出 U0(mV) | 材料常数 B；R25；R² |

- **平衡直流电桥** 公式（实现自述）：
  - `R_x=\frac{R_a}{R_b}R_n`
  - `R_x(t)=R_0(1+\alpha t),\quad R_0=50.0\,\Omega,\ \alpha=0.004280\,\mathrm{^{o}C^{-1}}`
  - `E_r=\frac{|R_x-R_x(t)|}{R_x(t)}\times100\%`
- **卧式电桥测 Cu50** 公式（实现自述）：
  - `\Delta R_x=\frac{4R_nU_0}{U_s-2U_0},\quad R_x=R_n+\Delta R_x`
  - `R_x=R_0(1+\alpha t),\quad \alpha=\frac{k}{R_0}`
- **交流电桥测电容** 公式（实现自述）：
  - `C_x=\frac{R_b}{R_a}C_n,\quad r_C=\frac{R_a}{R_b}R_n`
  - `\tan\delta=2\pi fC_nR_n`
- **交流电桥测电感** 公式（实现自述）：
  - `L_x=R_aR_bC_n,\quad r_L=\frac{R_aR_b}{R_n}`
  - `Q=\frac{\omega L_x}{r_L}=\omega C_nR_n`
- **热敏电阻（选做）** 公式（实现自述）：
  - `\Delta R_x=\frac{U_0(R_n+R^\prime)^2}{U_sR^\prime-U_0(R_n+R^\prime)},\quad R_x=R_n+\Delta R_x`
  - `\ln R=\ln R_{25}+B\left(\frac{1}{T}-\frac{1}{298.15}\right)`

- 手算 probe：待做（优先级：高（拟合把输入错误放大成物理量））
- 讲义对照结论：待填写

### 太阳能电池特性（`solar-cell`）

- adapter：`experiments/solar_cell/adapter.py`
- 风险标记：circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_data_collection.py`：`80`
  - `tests/test_data_reference.py`：`4.5`
  - `tests/test_general_experiments.py`：`12`, `80`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`12`, `80`, `7.2`, `4.5`, `.25`, `.06`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 伏安与功率特性 | 是 | 短路电流 Isc(mA)=80；开路电压 Uoc(V)=12 | U(V)；I(mA) | 最大功率 Pmax；最佳电压；最佳电流；填充因子 FF |
| 遮挡影响 | 是 | — | 工况编号；短路电流(mA) | 无遮挡 Isc；最小保留比例 |
| 超级电容直接充电 | 是 | — | t(min)；U(V)；I(mA) | 输入能量；末电压；充电时长 |
| DC-DC 恒功率充电 | 是 | — | t(min)；U(V)；I(mA) | 输入能量；末电压；充电时长 |
| 直流风扇负载 | 是 | — | U(V)；I(mA) | 并联前功率；并联后功率 |
| DC-DC 匹配直流负载（选做） | 选做 | — | 接入前 U1(V)；接入前 I1(mA)；接入后 U2(V)；接入后 I2(mA) | 接入前功率；接入后功率；功率增量 |
| DC-AC 逆变与交流负载（选做） | 选做 | — | 直流侧电压(V)；直流侧电流(mA)；节能灯点亮(1是/0否) | 直流侧输入功率；点亮记录 |

- **伏安与功率特性** 公式（实现自述）：
  - `P_i=U_iI_i,\quad P_{\max}=\max(P_i)`
  - `FF=\frac{P_{\max}}{U_{oc}I_{sc}}`
- **遮挡影响** 公式（实现自述）：
  - `r_i=\frac{I_{sc,i}}{I_{sc,0}}\times100\%`
- **超级电容直接充电** 公式（实现自述）：
  - `P(t)=U(t)I(t),\quad E=\int P(t)\,dt`
- **DC-DC 恒功率充电** 公式（实现自述）：
  - `P(t)=U(t)I(t),\quad E=\int P(t)\,dt`
- **直流风扇负载** 公式（实现自述）：
  - `P=UI`
- **DC-DC 匹配直流负载（选做）** 公式（实现自述）：
  - `P_1=U_1I_1,\quad P_2=U_2I_2,\quad \Delta P=P_2-P_1`
- **DC-AC 逆变与交流负载（选做）** 公式（实现自述）：
  - `P_{\rm in}=U_{\rm dc}I_{\rm dc}`

- 手算 probe：待做（优先级：中（fixture 由实现反推＝自证循环））
- 讲义对照结论：待填写

### 巨磁电阻效应及应用（`gmr`）

- adapter：`experiments/gmr/adapter.py`
- 风险标记：fit、circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_general_experiments.py`：`.31416`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`.31416`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 磁电转换特性 | 是 | — | 励磁电流(mA)；Vout(mV)；方向(1增/-1减) | 线性灵敏度；R²；最大磁场 |
| 内部磁阻特性 | 是 | 工作电压 U(V)=2 | 励磁电流(mA)；状态 A 回路电流(mA)；状态 B 回路电流(mA) | 状态 A GMR；状态 B GMR；敏感状态(A=1/B=2) |
| 无接触电流测量（选做） | 选做 | — | 导线电流(mA)；25mV偏置输出(mV)；100mV偏置输出(mV) | 25mV 灵敏度；100mV 灵敏度 |

- **磁电转换特性** 公式（实现自述）：
  - `B({\rm Gs})=0.31416I({\rm mA}),\quad V_{out}=kB+b`
- **内部磁阻特性** 公式（实现自述）：
  - `R=\frac{2U}{I_R}`
  - `GMR=\frac{R_{\max}-R_{\min}}{R_{\min}}\times100\%`
- **无接触电流测量（选做）** 公式（实现自述）：
  - `V_{out}=kI+b`

- 手算 probe：待做（优先级：高（拟合把输入错误放大成物理量））
- 讲义对照结论：待填写

### 核磁共振实验（`nmr`）

- adapter：`experiments/nmr/adapter.py`
- 风险标记：fit、circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_data_reference.py`：`5.5857`, `7.6225914`
  - `tests/test_general_experiments.py`：`5.2567`, `5.5857`, `7.6225914`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`7.6225914`, `5.5857`, `5.2567`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 共振信号与尾波观察 | 是 | — | 样品(1水/2聚四氟乙烯)；尾波振荡次数(次)；T1(ms)；T2(ms) | 已记录样品数；最大 |T1-T2| |
| 1H 核磁共振 | 是 | — | ν(MHz)；B0(mT) | γ/2π；g 因子；相对误差；R^2 |
| 19F 核磁共振 | 是 | — | ν(MHz)；B0(mT) | γ/2π；g 因子；相对误差；R^2 |
| 纯水样品 g 因子（选做） | 选做 | — | ν(MHz)；B0(mT) | γ/2π；g 因子；相对误差；R^2 |

- **共振信号与尾波观察** 公式（实现自述）：
  - `\Delta T=|T_1-T_2|`
- **1H 核磁共振** 公式（实现自述）：
  - `\nu=kB_0+b,\quad \frac{\gamma}{2\pi}=10^3k`
  - `g=\frac{\gamma/(2\pi)}{\mu_N/h}`
- **19F 核磁共振** 公式（实现自述）：
  - `\nu=kB_0+b,\quad \frac{\gamma}{2\pi}=10^3k`
  - `g=\frac{\gamma/(2\pi)}{\mu_N/h}`
- **纯水样品 g 因子（选做）** 公式（实现自述）：
  - `\nu=kB_0+b,\quad \frac{\gamma}{2\pi}=10^3k`
  - `g=\frac{\gamma/(2\pi)}{\mu_N/h}`

- 手算 probe：待做（优先级：高（拟合把输入错误放大成物理量））
- 讲义对照结论：待填写

### 落球法测液体粘滞系数（`viscosity`）

- adapter：`experiments/viscosity/adapter.py`
- 风险标记：circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_data_collection.py`：`20`
  - `tests/test_data_reference.py`：`20`
  - `tests/test_general_experiments.py`：`.1`, `1.5`, `16`, `18`, `2.4`, `20`, `7800`, `9.794`, `950`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`20`, `7800`, `950`, `9.794`, `18`, `2.4`, `.1`, `16`, `1.5`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 钢球直径测量 | 是 | — | 边缘坐标 x1(mm)；边缘坐标 x2(mm) | 平均直径 d；标准差 |
| 不同温度粘滞系数 | 是 | 下落距离 L(cm)=20；钢球直径 d(mm)=1.5；钢球密度(kg/m³)=7800；油密度(kg/m³)=950；管内径 D(cm)=2；重力加速度(m/s²)=9.794 | 温度 T(°C)；t1(s)；t2(s)；t3(s)；t4(s) | 首温度 η′；Re 最小值；Re 最大值 |
| 不同球径对比（拓展） | 选做 | 下落距离 L(cm)=20；液体温度 T(°C)=40；钢球密度(kg/m³)=7800；油密度(kg/m³)=950；管内径 D(cm)=2；重力加速度(m/s²)=9.794 | 小球直径 d(mm)；t1(s)；t2(s)；t3(s)；t4(s) | 有效小球数；平均修正粘度；最大 Re |

- **钢球直径测量** 公式（实现自述）：
  - `d_i=|x_{2,i}-x_{1,i}|,\quad \overline{d}=\frac{1}{n}\sum_i d_i`
- **不同温度粘滞系数** 公式（实现自述）：
  - `v_0=\frac{L}{\overline{t}}`
  - `\eta_0=\frac{gd^2(\rho-\rho_0)}{18v_0(1+2.4d/D)}`
  - `Re=\frac{\rho_0v_0d}{\eta_0},\quad \eta'=\eta_0\left(1-\frac{3}{16}Re\right)`
- **不同球径对比（拓展）** 公式（实现自述）：
  - `v_0=\frac{L}{\overline{t}}`
  - `Re=\frac{\rho_0v_0d}{\eta_0}`

- 手算 probe：待做（优先级：中（fixture 由实现反推＝自证循环））
- 讲义对照结论：待填写

### 液体表面张力系数测量（`surface-tension`）

- adapter：`experiments/surface_tension/adapter.py`
- 风险标记：fit、circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_general_experiments.py`：`3.31`, `3.496`, `9.79338`, `998`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`9.79338`, `3.31`, `3.496`, `.07275`, `.25`, `998`, `6000`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 力敏传感器定标 | 是 | 重力加速度(m/s²)=9.79338 | 砝码质量(g)；加载 U(mV)；卸载 U(mV) | 灵敏度 K；R²；最大回程差 |
| 拉脱法 | 是 | 吊环直径 D1(cm)=3.31；吊环直径 D2(cm)=3.496；纯水标准值 σ0(N/m)=0.07275 | 破膜前 U1(mV)；破膜后 U2(mV) | 采用的定标 K；表面张力 σ；重复测量标准差；纯水标准值 σ0；绝对误差 Δσ；相对误差 Er |
| 毛细管法 | 是 | 液体密度 ρ(kg/m³)=998；重力加速度(m/s²)=9.79338；纯水标准值 σ0(N/m)=0.07275 | 凹液面 y1(mm)；烧杯液面 y2(mm)；内壁 x1(mm)；内壁 x2(mm) | 表面张力 σ；平均液柱高；平均内径；纯水标准值 σ0；绝对误差 Δσ；相对误差 Er |
| 盐水表面张力·拉脱法（拓展选做） | 选做 | 盐水浓度(%)=5；传感器 K(mV/N)=1000；吊环直径 D1(cm)=3.31；吊环直径 D2(cm)=3.496 | 破膜前 U1(mV)；破膜后 U2(mV) | 表面张力 σ；标准差 |
| 盐水表面张力·毛细管法（拓展选做） | 选做 | 盐水浓度(%)=5；盐水密度 ρ(kg/m³)=1035；重力加速度(m/s²)=9.79338 | 凹液面 y1(mm)；烧杯液面 y2(mm)；内壁 x1(mm)；内壁 x2(mm) | 表面张力 σ；平均液柱高；平均内径 |

- **力敏传感器定标** 公式（实现自述）：
  - `F=mg,\quad U=KF+b`
- **拉脱法** 公式（实现自述）：
  - `\sigma=\frac{|U_1-U_2|}{\pi(D_1+D_2)K}`
  - `\Delta\sigma=|\sigma-\sigma_0|,\quad E_r=\frac{|\sigma-\sigma_0|}{\sigma_0}\times100\%`
- **毛细管法** 公式（实现自述）：
  - `h=|y_1-y_2|,\quad d=|x_1-x_2|`
  - `\sigma=\frac{1}{4}\rho gd\left(h+\frac{d}{6}\right)`
  - `\Delta\sigma=|\sigma-\sigma_0|,\quad E_r=\frac{|\sigma-\sigma_0|}{\sigma_0}\times100\%`
- **盐水表面张力·拉脱法（拓展选做）** 公式（实现自述）：
  - `\sigma=\frac{|U_1-U_2|}{\pi(D_1+D_2)K}`
- **盐水表面张力·毛细管法（拓展选做）** 公式（实现自述）：
  - `\sigma=\frac{1}{4}\rho gd\left(h+\frac{d}{6}\right)`

- 手算 probe：待做（优先级：高（拟合把输入错误放大成物理量））
- 讲义对照结论：待填写

### 稳态法测固体导热系数（`thermal-conductivity`）

- adapter：`experiments/thermal_conductivity/adapter.py`
- 风险标记：fit、circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_data_reference.py`：`2000`, `5`, `50`
  - `tests/test_general_experiments.py`：`35`, `394`, `5`, `50`, `500`, `8`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`5`, `35`, `500`, `394`, `2000`, `8`, `50`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 几何参数 | 是 | — | 铜盘直径 DC(mm)；铜盘厚度 hC(mm)；样品直径 DB(mm)；样品厚度 hB(mm) | DC 均值；hC 均值；DB 均值；hB 均值 |
| 升温与稳态记录 | 是 | — | t(min)；TA(°C)；TC(°C) | 稳态 T1；稳态 T2；末五点最大漂移 |
| 自然冷却曲线 | 是 | 铜盘质量 m(g)=500；紫铜比热 c(J/(kg·K))=394；稳态 T1(°C)=50；稳态 T2(°C)=35；铜盘直径 DC(mm)=100；铜盘厚度 hC(mm)=10；样品直径 DB(mm)=100；样品厚度 hB(mm)=8 | t(s)；TC(°C) | |dT/dt|；导热系数 λ；几何修正 ξ；局部拟合 R² |

- **几何参数** 公式（实现自述）：
  - `\overline{x}=\frac{1}{n}\sum_i x_i`
- **升温与稳态记录** 公式（实现自述）：
  - `T_1=\overline{T_A},\quad T_2=\overline{T_C}`
- **自然冷却曲线** 公式（实现自述）：
  - `\xi=\frac{2R_C+h_C}{2R_C+2h_C}`
  - `\lambda=\frac{mc|dT/dt|_{T_2}h_B}{\pi R_B^2(T_1-T_2)}\xi`

- 手算 probe：待做（优先级：高（拟合把输入错误放大成物理量））
- 讲义对照结论：待填写

### 迈克尔逊干涉实验（`michelson`）

- adapter：`experiments/michelson/adapter.py`
- 风险标记：unit_factor、circular_fixture
- **与测试/脚本共用的数值常量（逐条判断出处）**：
  - `tests/test_api_contract.py`：`5`, `50`
  - `tests/test_data_reference.py`：`1e6`, `5`, `50`, `6`, `632.8`
  - `tests/test_general_experiments.py`：`5`, `50`, `6`, `632.8`
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only
- `calculate` 中的数值常量：`5`, `50`, `1e6`, `632.8`, `6`（逐条核对出处）

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| He-Ne 激光波长测量 | 是 | 每档环数(环)=50 | 累计圈数 N(环)；反射镜位置 d(mm) | 实验波长 λ；相对误差；逐差平均 Δd；逐差标准差 |
| 点光源与扩展光源干涉现象 | 是 | — | 光路(1未扩束/2扩束/3钠灯)；形态(1圆环/2直纹)；移动(1涌出/-1淹没/0不适用)；定域(1是/0否) | 已记录现象数 |

- **He-Ne 激光波长测量** 公式（实现自述）：
  - `\Delta d_i=|d_{i+5}-d_i|`
  - `\lambda=\frac{2\overline{\Delta d}}{250}=\frac{\overline{\Delta d}}{125}`

- 手算 probe：待做（优先级：中（单位换算只在一处写错就整体偏移））
- 讲义对照结论：待填写

### 光电效应与弗兰克-赫兹实验（`photoelectric-franck-hertz`）

- adapter：`experiments/photoelectric_franck_hertz/adapter.py`
- 风险标记：无
- fixture `boundary.json`：source=structure-derived、verified=False、validation=structure-derived boundary coverage; replace with lab-confirmed ranges when available
- fixture `invalid.json`：source=synthetic、verified=False、validation=intentionally incomplete required measurement
- fixture `typical.json`：source=synthetic、verified=False、validation=synthetic-only

| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |
|---|---|---|---|---|
| 零电流法测普朗克常数 | 是 | — | 波长 λ(nm)；US1(V)；US2(V)；US3(V)；US4(V) | 普朗克常数 h；h 相对误差；红限频率 ν0；逸出功；R² |
| 436 nm 伏安特性 | 是 | — | UAK(V)；I(10⁻¹³ A) | 最大光电流；最小光电流 |
| 546 nm 伏安特性 | 是 | — | UAK(V)；I(10⁻¹³ A) | 最大光电流；最小光电流 |
| 饱和电流与光强 | 是 | — | 波长(nm)；光阑 Φ(mm)；I1(10⁻¹⁰ A)；I2(10⁻¹⁰ A)；I3(10⁻¹⁰ A) | 436 nm R²；546 nm R² |
| 补偿法测普朗克常数（选做） | 选做 | 光阑 Φ(mm)=4 | 波长 λ(nm)；US1(V)；US2(V)；US3(V) | 普朗克常数 h；h 相对误差；红限频率 ν0；逸出功；R² |
| IP-VG2K 特性 | 是 | 炉温(°C)=220；VF(V)=0.9；VG1K(V)=1.5；VG2P(V)=1.3 | VG2K(V)；IP(nA) | 有效点数；最大板极电流 |
| 峰值位置与逐差 | 是 | — | 峰值电压 Up(V) | 第一激发电位 V0；相对误差；峰间距标准差 |
| 改变工作参数的对比曲线（选做） | 选做 | 炉温(°C)=220；VF(V)=0.9；VG1K(V)=1.5；VG2P(V)=1.3 | VG2K(V)；IP 基准(nA)；IP 改参后(nA) | 有效对比点数；最大电流差 |
| 较高激发能级（选做） | 选做 | 炉温(°C)=120；VF(V)=0.9；VG2P(V)=1.3 | UKG1(V)；IP(nA) | 有效点数；最大板极电流 |

- **零电流法测普朗克常数** 公式（实现自述）：
  - `\nu=\frac{c}{\lambda},\quad U_S=k\nu+b`
  - `h=ek,\quad \nu_0=-\frac{b}{k},\quad W=-eb`
- **436 nm 伏安特性** 公式（实现自述）：
  - `I=I(U_{AK})`
- **546 nm 伏安特性** 公式（实现自述）：
  - `I=I(U_{AK})`
- **饱和电流与光强** 公式（实现自述）：
  - `P_{\rm rel}\propto\Phi^2,\quad I_m=a\Phi^2+b`
- **补偿法测普朗克常数（选做）** 公式（实现自述）：
  - `\nu=\frac{c}{\lambda},\quad U_S=k\nu+b`
  - `h=ek,\quad \nu_0=-\frac{b}{k}`
- **IP-VG2K 特性** 公式（实现自述）：
  - `I_P=f(V_{G2K})`
- **峰值位置与逐差** 公式（实现自述）：
  - `\Delta U_i=\frac{U_{p(i+3)}-U_{pi}}{3}`
  - `V_0=\overline{\Delta U},\quad E_r=\frac{|V_0-4.90|}{4.90}\times100\%`
- **改变工作参数的对比曲线（选做）** 公式（实现自述）：
  - `\Delta I_i=I_{{\rm variant},i}-I_{{\rm reference},i}`
- **较高激发能级（选做）** 公式（实现自述）：
  - `I_P=f(U_{KG1})`

- 手算 probe：待做（优先级：常规）
- 讲义对照结论：待填写
