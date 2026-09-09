export interface Measurement {
  key: string;
  label: string;
  unit: string;
}

export interface ResultField {
  key: string;
  label: string;
  unit: string;
  format?: "integer" | "decimal" | "percent" | "ratio";
}

export interface SubExperiment {
  id: string;
  name: string;
  required: boolean;
  description: string;
  resultFields: ResultField[];
}

export interface ExperimentConfig {
  id: string;
  name: string;
  category: string;
  description: string;
  processingTime: string;
  recordSheet: string;
  measurements: string[];
  subExperiments: SubExperiment[];
}

export const experiments: ExperimentConfig[] = [
  {
    id: "polarization",
    name: "偏振光与双折射",
    category: "光学",
    description:
      "验证马吕斯定律、研究半波片和四分之一波片的光学特性、分析圆偏振光",
    processingTime: "~30秒",
    recordSheet: "/record-sheets/polarization_lab.pdf",
    measurements: [
      "θ (偏振片角度)",
      "I (透射光强)",
      "φ (方位角)",
      "ΔC (半波片转角)",
      "ΔP2 (检偏器转角)",
    ],
    subExperiments: [
      {
        id: "malus",
        name: "马吕斯定律",
        required: true,
        description: "测量不同偏振角下的透射光强，验证 I = I₀cos²θ",
        resultFields: [
          { key: "slope", label: "斜率 (I₀)", unit: "μW" },
          { key: "intercept", label: "截距", unit: "μW" },
          { key: "r_squared", label: "R²", unit: "" },
          { key: "extinction_ratio", label: "消光比", unit: ":1" },
          { key: "degree_of_polarization", label: "偏振度", unit: "" },
        ],
      },
      {
        id: "halfwave",
        name: "半波片",
        required: true,
        description: "验证半波片使偏振方向旋转 2θ",
        resultFields: [
          { key: "slope", label: "斜率", unit: "" },
          { key: "r_squared", label: "R²", unit: "" },
          { key: "theory_slope", label: "理论斜率", unit: "" },
          { key: "slope_deviation_pct", label: "斜率偏差", unit: "%" },
        ],
      },
      {
        id: "quarterwave",
        name: "四分之一波片",
        required: true,
        description: "测量椭圆偏振光的光强分布，确定振幅参数 A",
        resultFields: [
          { key: "I_max_exp", label: "I_max (实验)", unit: "μW" },
          { key: "I_min_exp", label: "I_min (实验)", unit: "μW" },
          { key: "ratio_exp", label: "Imax/Imin (实验)", unit: "" },
          { key: "ratio_theory", label: "Imax/Imin (理论)", unit: "" },
          { key: "A_avg", label: "振幅参数 A", unit: "" },
          { key: "relative_diff_pct", label: "相对偏差", unit: "%" },
        ],
      },
      {
        id: "circular",
        name: "圆偏振光",
        required: false,
        description: "验证圆偏振光通过检偏器后光强恒定",
        resultFields: [
          { key: "I_mean", label: "平均光强", unit: "μW" },
          { key: "ratio", label: "Imax/Imin", unit: "" },
          { key: "cv_pct", label: "变异系数 CV", unit: "%" },
        ],
      },
    ],
  },
  {
    id: "sound-light",
    name: "声速光速的测量",
    category: "波动",
    description:
      "实验一 · 超声声速：共振干涉法（空气）与相位比较法（水）测声速、时差法（选做）；实验二 · 光速：相位法（正弦波）与李萨如法测光速、方波相位法（选做）",
    processingTime: "~1分钟",
    recordSheet: "/record-sheets/sound_light_record_sheet.pdf",
    measurements: [
      "S2 共振位置 l (mm，空气 / 水)",
      "传播距离 L (mm) 与飞行时间 T (μs)",
      "差频周期 T / 相位差 Δt (μs)",
      "反射镜位置 x₁ / x₂ (mm)",
    ],
    subExperiments: [
      {
        id: "air_resonance",
        name: "① 共振干涉法（空气）",
        required: true,
        description: "驻波共振位置 12 点逐差法：v = 2f·Δl̄，与温度修正理论声速对比",
        resultFields: [
          { key: "v_exp", label: "实验声速", unit: "m/s" },
          { key: "v_theory", label: "理论声速", unit: "m/s" },
          { key: "error_rel", label: "相对误差", unit: "%" },
          { key: "delta_l_mean", label: "Δl 均值", unit: "mm" },
        ],
      },
      {
        id: "water_phase",
        name: "② 相位比较法（水）",
        required: true,
        description: "水中相位匹配位置逐差法测声速，含 A 类不确定度 U_A",
        resultFields: [
          { key: "v_exp", label: "水中声速", unit: "m/s" },
          { key: "u_a", label: "A 类不确定度", unit: "m/s" },
          { key: "delta_l_mean", label: "Δl 均值", unit: "mm" },
        ],
      },
      {
        id: "tof",
        name: "③ 时差法 · 水（选做）",
        required: false,
        description: "脉冲波 L / T 直接测速：等间距 20 mm 连续 12 组",
        resultFields: [
          { key: "v_mean", label: "平均声速", unit: "m/s" },
          { key: "v_std", label: "标准差", unit: "m/s" },
        ],
      },
      {
        id: "light_sine",
        name: "① 相位法（正弦波）",
        required: true,
        description: "差频正弦相位法：λ = (T̄/Δt̄)·2Δx̄，c = f_t·λ",
        resultFields: [
          { key: "c_exp", label: "实验光速", unit: "m/s" },
          { key: "error_rel", label: "相对误差", unit: "%" },
        ],
      },
      {
        id: "light_square",
        name: "② 相位法（方波，选做）",
        required: false,
        description: "换方波挡位重测：方法与正弦波完全相同",
        resultFields: [
          { key: "c_exp", label: "实验光速", unit: "m/s" },
          { key: "error_rel", label: "相对误差", unit: "%" },
        ],
      },
      {
        id: "light_lissajous",
        name: "③ 李萨如图形法",
        required: true,
        description: "李萨如 π 相位变化：λ = 4Δx̄，c = f_t·λ",
        resultFields: [
          { key: "c_exp", label: "实验光速", unit: "m/s" },
          { key: "error_rel", label: "相对误差", unit: "%" },
        ],
      },
    ],
  },
];

export function getExperiment(id: string): ExperimentConfig | undefined {
  return experiments.find((e) => e.id === id);
}

export const categories = [
  "全部",
  "力学",
  "波动",
  "热学",
  "光学",
  "电磁学",
  "近代物理",
];
