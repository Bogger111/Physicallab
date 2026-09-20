export interface InputRangeHint {
  min: number;
  max: number;
  note?: string;
}

type MethodRanges = Record<string, Record<string, InputRangeHint>>;

const r = (min: number, max: number, note?: string): InputRangeHint => ({ min, max, note });

// Frontend-only guidance. This module is deliberately not imported by the
// backend, calculation adapters, record sheets, or report builders.
const RANGE_CATALOG: Record<string, MethodRanges> = {
  polarization: {
    setup: { bg_uw: r(0, 100, "背景读数应为非负值"), theta_qwp: r(0, 360) },
    malus: { theta: r(0, 360), i_left: r(0, 1000), i_right: r(0, 1000) },
    halfwave: {
      offset: r(0, 180), c_deg: r(0, 359), c_min: r(0, 59.99),
      p2_deg: r(0, 359), p2_min: r(0, 59.99),
    },
    quarterwave: { phi: r(0, 360), i_raw: r(0, 1000) },
    circular: { angle: r(0, 360), i_raw: r(0, 1000) },
  },
  "sound-light": {
    air_resonance: { temperature_degC: r(0, 50), f_khz: r(30, 50), l: r(0, 1000) },
    water_phase: { f_mhz: r(0.5, 2), l: r(0, 1000) },
    tof: { L: r(0, 1000), T: r(1, 2000) },
    light_sine: { f_mhz: r(100, 200), c_ref: r(2.5e8, 3.5e8), T: r(0.01, 100), dt: r(0, 100), x1: r(0, 3000), x2: r(0, 3000) },
    light_square: { f_mhz: r(100, 200), c_ref: r(2.5e8, 3.5e8), T: r(0.01, 100), dt: r(0, 100), x1: r(0, 3000), x2: r(0, 3000) },
    light_lissajous: { f_mhz: r(100, 200), c_ref: r(2.5e8, 3.5e8), x1: r(0, 3000), x2: r(0, 3000) },
  },
  multimeter: {
    voltage: { set: r(-1000, 1000), measured: r(-1000, 1000) },
    current: { set: r(-1000, 1000), measured: r(-1000, 1000) },
    resistance: { set: r(0, 10000), measured: r(0, 10000) },
    unknown: { reference: r(0, 10000), measured: r(0, 10000) },
    ac_voltage: { set: r(0, 1000), measured: r(0, 1000) },
    ac_current: { set: r(0, 1000), measured: r(0, 1000) },
  },
  bridge: {
    balanced: { ra: r(0, 20000), rb: r(0, 20000), us: r(0, 15), t_room: r(0, 60), rn: r(0, 2000) },
    cu50: { us: r(0, 15), rn: r(0, 200), temperature: r(0, 120), u0: r(-500, 500) },
    capacitor: { ra: r(0, 20000), rb: r(0, 20000), f: r(500, 2000), cn: r(0, 10), rn: r(0, 200) },
    inductor: { ra: r(0, 20000), rb: r(0, 20000), f: r(500, 2000), cn: r(0, 10), rn: r(0, 20000) },
    thermistor: { us: r(0, 15), r_prime: r(0, 2000), rn: r(500, 20000), temperature: r(0, 120), u0: r(-500, 500) },
  },
  photoelectric: {
    planck: { wavelength: r(300, 800), us1: r(-5, 5), us2: r(-5, 5), us3: r(-5, 5), us4: r(-5, 5) },
    iv_436: { voltage: r(-5, 50), current: r(-1000, 10000) },
    iv_546: { voltage: r(-5, 50), current: r(-1000, 10000) },
    saturation: { wavelength: r(300, 800), diameter: r(0.1, 20), i1: r(0, 10000), i2: r(0, 10000), i3: r(0, 10000) },
    compensation: { aperture: r(0.1, 20), wavelength: r(300, 800), us1: r(-5, 5), us2: r(-5, 5), us3: r(-5, 5) },
  },
  "franck-hertz": {
    curve: { temperature: r(100, 250), vf: r(0, 10), vg1k: r(0, 10), vg2p: r(-20, 20), voltage: r(0, 100), current: r(0, 5000) },
    peaks: { peak_voltage: r(0, 100) },
    parameter_curve: { temperature: r(100, 250), vf: r(0, 10), vg1k: r(0, 10), vg2p: r(-20, 20), voltage: r(0, 100), current_reference: r(0, 5000), current_variant: r(0, 5000) },
    higher_curve: { temperature: r(100, 250), vf: r(0, 10), vg2p: r(-20, 20), voltage: r(0, 100), current: r(0, 5000) },
  },
  "solar-cell": {
    iv: { isc: r(0, 1000), uoc: r(0, 20), voltage: r(0, 20), current: r(0, 1000) },
    shading: { condition: r(0, 10), isc: r(0, 1000) },
    charge_direct: { time: r(0, 180), voltage: r(0, 20), current: r(0, 1000) },
    charge_dcdc: { time: r(0, 180), voltage: r(0, 20), current: r(0, 1000) },
    fan: { voltage: r(0, 30), current: r(0, 2000) },
    load_dcdc: { voltage_before: r(0, 30), current_before: r(0, 2000), voltage_after: r(0, 30), current_after: r(0, 2000) },
    inverter: { input_voltage: r(0, 30), input_current: r(0, 5000), lit_code: r(0, 1, "0 表示否，1 表示是") },
  },
  gmr: {
    transfer: { excitation: r(-1000, 1000), output: r(-5000, 5000), direction: r(-1, 1, "按页面约定填写方向编码") },
    resistance: { supply: r(0, 30), excitation: r(-1000, 1000), ir_a: r(-1000, 1000), ir_b: r(-1000, 1000) },
    current_sensor: { current: r(-5000, 5000), output25: r(-5000, 5000), output100: r(-5000, 5000) },
  },
  nmr: {
    waveform: { sample_code: r(1, 3), tail_count: r(0, 100), t1: r(0, 10000), t2: r(0, 10000) },
    hydrogen: { frequency: r(0.1, 100), field: r(0, 2000) },
    fluorine: { frequency: r(0.1, 100), field: r(0, 2000) },
    pure_water: { frequency: r(0.1, 100), field: r(0, 2000) },
  },
  viscosity: {
    diameter: { x1: r(0, 100), x2: r(0, 100) },
    viscosity: { distance: r(1, 100), diameter: r(0.1, 10), rho_ball: r(5000, 10000), rho_oil: r(500, 2000), tube_diameter: r(0.5, 20), g: r(9, 10.5), temperature: r(0, 100), t1: r(0.1, 300), t2: r(0.1, 300), t3: r(0.1, 300), t4: r(0.1, 300) },
    diameter_effect: { distance: r(1, 100), temperature: r(0, 100), rho_ball: r(5000, 10000), rho_oil: r(500, 2000), tube_diameter: r(0.5, 20), g: r(9, 10.5), diameter: r(0.1, 10), t1: r(0.1, 300), t2: r(0.1, 300), t3: r(0.1, 300), t4: r(0.1, 300) },
  },
  "surface-tension": {
    calibration: { g: r(9, 10.5), mass: r(0, 20), u_up: r(-5000, 5000), u_down: r(-5000, 5000) },
    pull_off: { d1: r(0.1, 20), d2: r(0.1, 20), sigma_reference: r(0.01, 0.2), u1: r(-5000, 5000), u2: r(-5000, 5000) },
    capillary: { density: r(500, 2000), g: r(9, 10.5), sigma_reference: r(0.01, 0.2), y1: r(0, 200), y2: r(0, 200), x1: r(0, 100), x2: r(0, 100) },
    salt_pull_off: { concentration: r(0, 30), sensitivity: r(1, 100000), d1: r(0.1, 20), d2: r(0.1, 20), u1: r(-5000, 5000), u2: r(-5000, 5000) },
    salt_capillary: { concentration: r(0, 30), density: r(500, 2000), g: r(9, 10.5), y1: r(0, 200), y2: r(0, 200), x1: r(0, 100), x2: r(0, 100) },
  },
  "thermal-conductivity": {
    geometry: { dc: r(10, 300), hc: r(1, 100), db: r(10, 300), hb: r(0.1, 100) },
    heating: { time: r(0, 300), ta: r(0, 200), tc: r(0, 200) },
    cooling: { mass: r(10, 5000), specific_heat: r(100, 2000), t1: r(0, 200), t2: r(0, 200), dc: r(10, 300), hc: r(1, 100), db: r(10, 300), hb: r(0.1, 100), time: r(0, 10000), temperature: r(0, 200) },
  },
  michelson: {
    wavelength: { fringes_per_step: r(1, 1000), fringe_count: r(0, 10000), position: r(0, 100) },
    observations: { setup_code: r(1, 3), pattern_code: r(1, 2), motion_code: r(-1, 1), localized_code: r(0, 1) },
  },
};

export function getInputRange(
  experimentId: string,
  methodId: string,
  fieldKey: string
): InputRangeHint | undefined {
  return RANGE_CATALOG[experimentId]?.[methodId]?.[fieldKey];
}

export function isOutsideRange(value: string | number, hint?: InputRangeHint): boolean {
  if (!hint || value === "") return false;
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) && (numeric < hint.min || numeric > hint.max);
}

function displayNumber(value: number): string {
  if (Math.abs(value) >= 1e6) return value.toExponential(2);
  return Number.isInteger(value) ? String(value) : String(value);
}

export function rangeLabel(hint?: InputRangeHint, unit?: string): string | undefined {
  if (!hint) return undefined;
  return `建议 ${displayNumber(hint.min)}–${displayNumber(hint.max)}${unit ? ` ${unit}` : ""}`;
}

export const RANGE_EXPERIMENT_IDS = Object.freeze(Object.keys(RANGE_CATALOG));
