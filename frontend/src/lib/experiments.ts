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
];

export function getExperiment(id: string): ExperimentConfig | undefined {
  return experiments.find((e) => e.id === id);
}

export const categories = [
  "全部",
  "力学",
  "热学",
  "光学",
  "电磁学",
  "近代物理",
];
