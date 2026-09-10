"""
Polarization Lab Adapter — wraps existing verified computation logic
for use via REST API. Does NOT rewrite formulas; uses theory.py and angles.py as-is.

Input: JSON data from frontend
Output: computed results + matplotlib plots as base64 PNG
"""

import io
import base64
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from typing import Optional

from .theory import (
    malus_law, cos2_theta, half_wave_theory, quarter_wave_intensity,
    quarter_wave_Imax_Imin, quarter_wave_ratio_theory, extract_A_from_extremes,
    circular_ideal_intensity,
)
from .angles import dms_to_decimal, unwrap_angle_delta


def _num(value, default: float = 0.0) -> float:
    """float() that tolerates blank cells.

    The entry table serialises an untouched cell to null, and dict.get(key, 0) does
    not help when the key exists with a null value — float(None) would raise a
    TypeError that reaches the browser as a cryptic message.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    return float(value)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Matplotlib styling for clean scientific plots
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Noto Sans CJK SC', 'Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'DejaVu Sans', 'Arial'],
    'axes.unicode_minus': False,
    'figure.dpi': 150,
    'savefig.dpi': 200,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'axes.spines.top': False,
    'axes.spines.right': False,
})


class PolarizationAdapter:
    """Processes polarization experiment data and generates results + plots."""

    def __init__(self, bg_uw: float = 0.0, theta_qwp: float = 30.0):
        self.bg_uw = bg_uw
        self.theta_qwp = theta_qwp

    def process_all(self, data: dict) -> dict:
        """
        Process all sub-experiments from JSON input.
        
        Args:
            data: dict with keys 'malus', 'halfwave', 'quarterwave', 'circular'
                  each containing the relevant sub-experiment data
        
        Returns:
            dict with 'results' and 'plots' (base64 PNG strings)
        """
        results = {}
        plots = {}

        if 'malus' in data and data['malus']:
            r = self._process_malus(data['malus'])
            if r:
                results['malus'] = r['summary']
                plots['malus'] = self._plot_malus(r)

        if 'halfwave' in data and data['halfwave']:
            r = self._process_halfwave(data['halfwave'])
            if r:
                results['halfwave'] = r['summary']
                plots['halfwave'] = self._plot_halfwave(r)

        if 'quarterwave' in data and data['quarterwave']:
            r = self._process_quarterwave(data['quarterwave'])
            if r:
                results['quarterwave'] = r['summary']
                plots['quarterwave'] = self._plot_quarterwave(r)

        if 'circular' in data and data['circular']:
            r = self._process_circular(data['circular'])
            if r:
                results['circular'] = r['summary']
                plots['circular'] = self._plot_circular(r)

        return {'results': results, 'plots': plots}

    # ─── Experiment 1: Malus's Law ───────────────────────────
    def _process_malus(self, data: dict) -> Optional[dict]:
        rows = data.get('rows', [])
        if not rows:
            return None

        thetas, I_left_raw, I_right_raw = [], [], []
        for row in rows:
            theta = row.get('theta')
            if theta is None:
                continue
            thetas.append(float(theta))
            I_left_raw.append(float(row.get('i_left', np.nan)) if row.get('i_left') is not None else np.nan)
            I_right_raw.append(float(row.get('i_right', np.nan)) if row.get('i_right') is not None else np.nan)

        if len(thetas) < 2:
            return None

        thetas = np.array(thetas)
        I_left_raw = np.array(I_left_raw, dtype=float)
        I_right_raw = np.array(I_right_raw, dtype=float)

        I_left_corr = I_left_raw - self.bg_uw
        I_right_corr = I_right_raw - self.bg_uw
        I_mean = np.nanmean([I_left_corr, I_right_corr], axis=0)
        cos2 = np.cos(np.radians(thetas)) ** 2

        valid = ~np.isnan(I_mean) & (I_mean > 0)
        if valid.sum() < 2:
            return None

        slope, intercept, r_value, p_value, std_err = stats.linregress(cos2[valid], I_mean[valid])

        # Also compute uncorrected for comparison
        I_mean_raw = np.nanmean([I_left_raw, I_right_raw], axis=0)
        valid_raw = ~np.isnan(I_mean_raw)
        slope_raw, intercept_raw, r_raw, _, _ = stats.linregress(cos2[valid_raw], I_mean_raw[valid_raw])

        I_max = float(np.nanmax(I_mean))
        I_min = float(np.nanmin(I_mean))
        ext_ratio = I_max / I_min if I_min > 0 else float('inf')
        DoP = (I_max - I_min) / (I_max + I_min) if (I_max + I_min) > 0 else 0

        return {
            'thetas': thetas, 'I_mean': I_mean, 'I_mean_raw': I_mean_raw,
            'I_left_corr': I_left_corr, 'I_right_corr': I_right_corr,
            'cos2': cos2, 'slope': slope, 'intercept': intercept,
            'r_squared': r_value ** 2,
            'summary': {
                'slope': round(float(slope), 4),
                'intercept': round(float(intercept), 4),
                'r_squared': round(float(r_value ** 2), 6),
                'I_max': round(I_max, 4),
                'I_min': round(I_min, 4),
                'extinction_ratio': round(ext_ratio, 1),
                'degree_of_polarization': round(DoP, 6),
                'slope_raw': round(float(slope_raw), 4),
                'r_squared_raw': round(float(r_raw), 6),
                'data_points': int(valid.sum()),
            }
        }

    def _plot_malus(self, r: dict) -> str:
        """Malus: I_left and I_right series on the SAME axes, each with its own
        linear fit, plus the mean-series fit (the one used for the report numbers)."""
        fig, ax = plt.subplots(figsize=(8, 5.5))

        def fit_line(y_series, label_color):
            mask = np.isfinite(r['cos2']) & np.isfinite(y_series)
            if mask.sum() < 2:
                return None
            sl, ic, rv, _, _ = stats.linregress(r['cos2'][mask], y_series[mask])
            xs = np.linspace(0, 1, 80)
            ax.plot(xs, sl * xs + ic, linestyle='--', linewidth=1.6,
                    color=label_color, alpha=0.85, zorder=3)
            return sl, ic, rv ** 2

        ax.scatter(r['cos2'], r['I_left_corr'], c='#2563eb', marker='o', s=52, zorder=5,
                   label='I 左旋', edgecolors='white', linewidths=0.6)
        ax.scatter(r['cos2'], r['I_right_corr'], c='#f59e0b', marker='s', s=44, zorder=5,
                   label='I 右旋', edgecolors='white', linewidths=0.6)

        fit_l = fit_line(r['I_left_corr'], '#2563eb')
        fit_r = fit_line(r['I_right_corr'], '#f59e0b')

        # mean-series fit = canonical reported fit
        x_fit = np.linspace(0, 1, 100)
        y_fit = r['slope'] * x_fit + r['intercept']
        ax.plot(x_fit, y_fit, '-', color='#dc2626', linewidth=2.2, zorder=6,
                label=f"拟合(平均): I = {r['slope']:.2f}cos²θ + {r['intercept']:.2f}   R² = {r['r_squared']:.5f}")
        if fit_l:
            ax.plot([], [], '--', color='#2563eb', alpha=0.85,
                    label=f"拟合(左): R² = {fit_l[2]:.5f}")
        if fit_r:
            ax.plot([], [], '--', color='#f59e0b', alpha=0.85,
                    label=f"拟合(右): R² = {fit_r[2]:.5f}")

        ax.set_xlabel('cos²θ', fontsize=12)
        ax.set_ylabel('I / μW', fontsize=12)
        ax.set_title('马吕斯定律：I 左 / I 右 与 cos²θ 的关系（背景已校正）', fontsize=13, fontweight='bold')
        ax.legend(fontsize=9, framealpha=0.9, loc='upper left')
        fig.tight_layout()
        return _fig_to_base64(fig)

    # ─── Experiment 2: Half-Wave Plate ───────────────────────
    def _process_halfwave(self, data: dict) -> Optional[dict]:
        init = data.get('initial', {})
        rows = data.get('rows', [])
        if not rows or not init:
            return None

        c0 = dms_to_decimal(_num(init.get('c_deg')), _num(init.get('c_min')))
        p20 = dms_to_decimal(_num(init.get('p2_deg')), _num(init.get('p2_min')))

        offsets, delta_c, delta_p2 = [], [], []
        for row in rows:
            c_deg = row.get('c_deg')
            p2_deg = row.get('p2_deg')
            if c_deg is None or p2_deg is None:
                continue
            offsets.append(_num(row.get('offset', 0)))
            c_dec = dms_to_decimal(_num(c_deg), _num(row.get('c_min')))
            p2_dec = dms_to_decimal(_num(p2_deg), _num(row.get('p2_min')))
            delta_c.append(unwrap_angle_delta(c_dec - c0))
            delta_p2.append(unwrap_angle_delta(p2_dec - p20))

        if len(offsets) < 2:
            return None

        delta_c = np.array(delta_c)
        delta_p2 = np.array(delta_p2)
        theory_2dc = 2 * delta_c
        errors = delta_p2 - theory_2dc
        rel_errors = np.abs(errors / np.where(theory_2dc != 0, theory_2dc, np.nan)) * 100

        slope, intercept, r_value, _, _ = stats.linregress(delta_c, delta_p2)

        return {
            'offsets': offsets, 'delta_c': delta_c, 'delta_p2': delta_p2,
            'theory_2dc': theory_2dc, 'errors': errors, 'rel_errors': rel_errors,
            'slope': slope, 'intercept': intercept, 'r_squared': r_value ** 2,
            'summary': {
                'slope': round(float(slope), 4),
                'intercept': round(float(intercept), 4),
                'r_squared': round(float(r_value ** 2), 6),
                'theory_slope': 2.0,
                'slope_deviation_pct': round(abs(float(slope) - 2) / 2 * 100, 2),
                'data_points': len(offsets),
                'max_abs_error': round(float(np.nanmax(np.abs(errors))), 2),
            }
        }

    def _plot_halfwave(self, r: dict) -> str:
        fig, ax = plt.subplots(figsize=(8, 5.5))
        ax.scatter(r['delta_c'], r['delta_p2'], c='#2563eb', marker='o', s=50, zorder=5,
                   label='实验数据 ΔP2', edgecolors='white', linewidths=0.5)
        x_theory = np.array(r['delta_c'])
        ax.plot(x_theory, 2 * x_theory, 'g--', linewidth=2, label='理论: ΔP2 = 2ΔC')
        x_fit = np.linspace(min(r['delta_c']), max(r['delta_c']), 100)
        y_fit = r['slope'] * x_fit + r['intercept']
        ax.plot(x_fit, y_fit, 'r-', linewidth=2,
                label=f"拟合: 斜率={r['slope']:.4f}, R²={r['r_squared']:.6f}")
        ax.set_xlabel('ΔC / °', fontsize=12)
        ax.set_ylabel('ΔP2 / °', fontsize=12)
        ax.set_title("半波片: ΔP2 与 ΔC 的关系", fontsize=14, fontweight='bold')
        ax.legend(fontsize=10, framealpha=0.9)
        fig.tight_layout()
        return _fig_to_base64(fig)

    # ─── Experiment 3: Quarter-Wave Plate ────────────────────
    def _process_quarterwave(self, data: dict) -> Optional[dict]:
        rows = data.get('rows', [])
        if not rows:
            return None

        phis, I_raw = [], []
        for row in rows:
            phi = row.get('phi')
            if phi is None:
                continue
            phis.append(float(phi))
            i_val = row.get('i_raw')
            I_raw.append(float(i_val) if i_val is not None else np.nan)

        phis = np.array(phis)
        I_raw = np.array(I_raw)
        I_corr = I_raw - self.bg_uw
        I_use = I_corr if self.bg_uw > 0 else I_raw

        valid = ~np.isnan(I_use)
        if valid.sum() < 2:
            return None

        I_max_exp = float(np.nanmax(I_use))
        I_min_exp = float(np.nanmin(I_use))
        ratio_exp = I_max_exp / I_min_exp if I_min_exp > 0 else float('inf')

        A_from_max, A_from_min = extract_A_from_extremes(I_max_exp, I_min_exp, self.theta_qwp)
        A_avg = (A_from_max + A_from_min) / 2

        Imax_theory, Imin_theory = quarter_wave_Imax_Imin(self.theta_qwp, A_avg)
        ratio_theory = quarter_wave_ratio_theory(self.theta_qwp)

        phi_fine = np.linspace(0, 360, 361)
        I_theory_fine = quarter_wave_intensity(phi_fine, self.theta_qwp, A_avg)
        I_theory_at_exp = quarter_wave_intensity(phis, self.theta_qwp, A_avg)

        rel_diff = abs(ratio_exp - ratio_theory) / ratio_theory * 100 if ratio_theory > 0 else 0

        # Nonlinear fit
        A_fit, theta_fit, perr = None, None, None
        try:
            def qw_model(phi_deg, A, theta_deg):
                phi = np.radians(phi_deg)
                theta = np.radians(theta_deg)
                return A**2 * (np.sin(theta)**2 * np.sin(phi)**2 + np.cos(theta)**2 * np.cos(phi)**2)

            popt, pcov = curve_fit(qw_model, phis[valid], I_use[valid], p0=[12, 30],
                                   bounds=([0, 0], [100, 90]))
            A_fit, theta_fit = popt
            perr = np.sqrt(np.diag(pcov))
        except Exception:
            pass

        summary = {
            'theta_qwp': self.theta_qwp,
            'I_max_exp': round(I_max_exp, 4),
            'I_min_exp': round(I_min_exp, 4),
            'ratio_exp': round(ratio_exp, 4),
            'A_from_max': round(A_from_max, 4),
            'A_from_min': round(A_from_min, 4),
            'A_avg': round(A_avg, 4),
            'Imax_theory': round(Imax_theory, 4),
            'Imin_theory': round(Imin_theory, 4),
            'ratio_theory': round(ratio_theory, 4),
            'relative_diff_pct': round(rel_diff, 2),
            'data_points': int(valid.sum()),
        }
        if A_fit is not None:
            summary['A_nl_fit'] = round(float(A_fit), 4)
            summary['theta_nl_fit'] = round(float(theta_fit), 2)
            summary['A_nl_err'] = round(float(perr[0]), 4)
            summary['theta_nl_err'] = round(float(perr[1]), 2)

        return {
            'phis': phis, 'I_use': I_use, 'I_corr': I_corr,
            'phi_fine': phi_fine, 'I_theory_fine': I_theory_fine,
            'I_theory_at_exp': I_theory_at_exp,
            'A_avg': A_avg, 'A_fit': A_fit, 'theta_fit': theta_fit,
            'ratio_exp': ratio_exp, 'ratio_theory': ratio_theory,
            'summary': summary,
        }

    def _plot_quarterwave(self, r: dict) -> str:
        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={'projection': 'polar'})
        valid = ~np.isnan(r['I_use'])
        ax.scatter(np.radians(r['phis'][valid]), r['I_use'][valid],
                   c='#2563eb', marker='o', s=40, zorder=5, label='实验数据',
                   edgecolors='white', linewidths=0.5)
        ax.plot(np.radians(r['phi_fine']), r['I_theory_fine'], 'r-', linewidth=2,
                label=f"理论曲线 (θ={self.theta_qwp}°)")
        if r['A_fit'] is not None:
            phi_fine = np.linspace(0, 360, 361)
            I_nl = r['A_fit']**2 * (np.sin(np.radians(r['theta_fit']))**2 * np.sin(np.radians(phi_fine))**2 +
                                     np.cos(np.radians(r['theta_fit']))**2 * np.cos(np.radians(phi_fine))**2)
            ax.plot(np.radians(phi_fine), I_nl, 'g--', linewidth=2,
                    label=f"非线性拟合 (A={r['A_fit']:.2f}, θ={r['theta_fit']:.1f}°)")
        ax.set_title(f"λ/4 波片: 椭圆偏振光强分布\nImax/Imin = {r['ratio_exp']:.3f} (理论: {r['ratio_theory']:.3f})",
                     fontsize=12, pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=9)
        fig.tight_layout()
        return _fig_to_base64(fig)

    # ─── Experiment 6: Circular Polarization ─────────────────
    def _process_circular(self, data: dict) -> Optional[dict]:
        rows = data.get('rows', [])
        if not rows:
            return None

        angles, I_raw = [], []
        for row in rows:
            angle = row.get('angle')
            if angle is None:
                continue
            angles.append(float(angle))
            i_val = row.get('i_raw')
            I_raw.append(float(i_val) if i_val is not None else np.nan)

        angles = np.array(angles)
        I_raw = np.array(I_raw)
        I_corr = I_raw - self.bg_uw
        I_use = I_corr if self.bg_uw > 0 else I_raw

        valid = ~np.isnan(I_use)
        if valid.sum() < 2:
            return None

        I_valid = I_use[valid]
        I_mean = float(np.mean(I_valid))
        I_max = float(np.max(I_valid))
        I_min = float(np.min(I_valid))
        I_std = float(np.std(I_valid, ddof=1)) if len(I_valid) > 1 else 0
        ratio = I_max / I_min if I_min > 0 else float('inf')
        cv = (I_std / I_mean) * 100 if I_mean > 0 else 0

        return {
            'angles': angles, 'I_use': I_use, 'I_corr': I_corr,
            'I_mean': I_mean, 'I_max': I_max, 'I_min': I_min,
            'summary': {
                'I_mean': round(I_mean, 4),
                'I_max': round(I_max, 4),
                'I_min': round(I_min, 4),
                'ratio': round(ratio, 4),
                'std_dev': round(I_std, 4),
                'cv_pct': round(cv, 2),
                'data_points': int(valid.sum()),
            }
        }

    def _plot_circular(self, r: dict) -> str:
        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={'projection': 'polar'})
        valid = ~np.isnan(r['I_use'])
        ax.scatter(np.radians(r['angles'][valid]), r['I_use'][valid],
                   c='#2563eb', marker='o', s=40, zorder=5, label='实验数据',
                   edgecolors='white', linewidths=0.5)
        theta_circ = np.linspace(0, 2 * np.pi, 361)
        ax.plot(theta_circ, [r['I_mean']] * len(theta_circ), 'r-', linewidth=2,
                label=f"均值 = {r['I_mean']:.2f} μW")
        summary = r['summary']
        ax.set_title(f"圆偏振光: 光强分布\nCV = {summary['cv_pct']:.2f}%, Imax/Imin = {summary['ratio']:.3f}",
                     fontsize=12, pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=9)
        fig.tight_layout()
        return _fig_to_base64(fig)


def _fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')
