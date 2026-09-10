"""Regression tests for polarization adapter.

Ensures that the adapter produces the same results as the original
computation functions from theory.py and angles.py.
"""

import sys
import os
import pytest
import numpy as np

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.polarization.theory import (
    malus_law, cos2_theta, half_wave_theory, quarter_wave_intensity,
    quarter_wave_Imax_Imin, quarter_wave_ratio_theory, extract_A_from_extremes,
    circular_ideal_intensity,
)
from experiments.polarization.angles import (
    dms_to_decimal, unwrap_angle_delta, unwrap_series,
)
from experiments.polarization.adapter import PolarizationAdapter


# ─── theory.py regression tests ──────────────────────────────

class TestTheoryRegression:
    """Verify theory.py functions produce expected results."""

    def test_malus_law_basic(self):
        theta = np.array([0, 30, 45, 60, 90])
        I0 = 100.0
        result = malus_law(theta, I0)
        expected = I0 * np.cos(np.radians(theta)) ** 2
        np.testing.assert_allclose(result, expected, rtol=1e-10)

    def test_malus_law_values(self):
        theta = np.array([0, 45, 90])
        I0 = 150.0
        result = malus_law(theta, I0)
        assert abs(result[0] - 150.0) < 1e-10  # cos²(0) = 1
        assert abs(result[1] - 75.0) < 1e-10   # cos²(45) = 0.5
        assert abs(result[2] - 0.0) < 1e-10    # cos²(90) = 0

    def test_cos2_theta(self):
        theta = np.array([0, 60, 90])
        result = cos2_theta(theta)
        assert abs(result[0] - 1.0) < 1e-10
        assert abs(result[1] - 0.25) < 1e-10
        assert abs(result[2] - 0.0) < 1e-10

    def test_half_wave_theory(self):
        assert half_wave_theory(0) == 0.0
        assert half_wave_theory(10) == 20.0
        assert half_wave_theory(45) == 90.0

    def test_quarter_wave_intensity(self):
        # At phi=0, theta=30: I = A² * cos²(30°) = A² * 0.75
        A = 10.0
        result = quarter_wave_intensity(np.array([0]), 30, A)
        expected = A**2 * np.cos(np.radians(30))**2
        assert abs(result[0] - expected) < 1e-10

    def test_quarter_wave_Imax_Imin(self):
        A = 10.0
        theta = 30
        imax, imin = quarter_wave_Imax_Imin(theta, A)
        # For theta=30: cos²30=0.75, sin²30=0.25 → Imax=A²*0.75, Imin=A²*0.25
        assert abs(imax - A**2 * 0.75) < 1e-10
        assert abs(imin - A**2 * 0.25) < 1e-10

    def test_quarter_wave_ratio_theory(self):
        # For theta=30 or 60, ratio should be 3
        assert abs(quarter_wave_ratio_theory(30) - 3.0) < 1e-10
        assert abs(quarter_wave_ratio_theory(60) - 3.0) < 1e-10
        assert abs(quarter_wave_ratio_theory(45) - 1.0) < 1e-10

    def test_extract_A_from_extremes(self):
        A_true = 12.0
        theta = 30
        imax = A_true**2 * 0.75  # max(sin²30, cos²30)
        imin = A_true**2 * 0.25  # min(sin²30, cos²30)
        a_from_max, a_from_min = extract_A_from_extremes(imax, imin, theta)
        assert abs(a_from_max - A_true) < 1e-10
        assert abs(a_from_min - A_true) < 1e-10


# ─── angles.py regression tests ─────────────────────────────

class TestAnglesRegression:
    def test_dms_to_decimal(self):
        assert abs(dms_to_decimal(271, 28) - 271.4667) < 0.001
        assert abs(dms_to_decimal(0, 0) - 0.0) < 1e-10
        assert abs(dms_to_decimal(90, 30) - 90.5) < 1e-10

    def test_unwrap_angle_delta(self):
        assert abs(unwrap_angle_delta(10) - 10) < 1e-10
        assert abs(unwrap_angle_delta(-10) - (-10)) < 1e-10
        assert abs(unwrap_angle_delta(350) - (-10)) < 1e-10  # wrap around

    def test_unwrap_series(self):
        result = unwrap_series([350, 355, 0, 5, 10])
        # Should be continuous: 350, 355, 360, 365, 370
        assert abs(result[2] - 360) < 1  # 0° should unwrap to ~360°


# ─── Adapter regression tests ───────────────────────────────

class TestAdapterRegression:
    """Verify adapter produces same results as direct theory computation."""

    def test_malus_adapter_matches_theory(self):
        """Adapter malus computation should match direct theory.py calls."""
        adapter = PolarizationAdapter(bg_uw=0.0)
        data = {
            'malus': {
                'rows': [
                    {'theta': t, 'i_left': 100 * np.cos(np.radians(t))**2,
                     'i_right': 100 * np.cos(np.radians(t))**2 + 0.5}
                    for t in range(0, 100, 10)
                ]
            }
        }
        result = adapter.process_all(data)
        assert result['results']['malus']['data_points'] == 10
        # Slope should be close to 100 (the I0 we used)
        assert abs(result['results']['malus']['slope'] - 100) < 1.0

    def test_halfwave_adapter_slope_near_2(self):
        """With perfect data (ΔP2 = 2ΔC), adapter slope should be ~2."""
        adapter = PolarizationAdapter()
        data = {
            'halfwave': {
                'initial': {'c_deg': 0, 'c_min': 0, 'p2_deg': 0, 'p2_min': 0},
                'rows': [
                    {'offset': i * 10, 'c_deg': i * 10, 'c_min': 0,
                     'p2_deg': i * 20, 'p2_min': 0}
                    for i in range(1, 7)
                ]
            }
        }
        result = adapter.process_all(data)
        assert abs(result['results']['halfwave']['slope'] - 2.0) < 0.01

    def test_quarterwave_adapter_with_theory_data(self):
        """Adapter quarterwave with theory-generated data should recover A and theta."""
        A_true = 12.0
        theta_true = 30
        phis = np.arange(0, 360, 10)
        I_theory = quarter_wave_intensity(phis, theta_true, A_true)

        adapter = PolarizationAdapter(bg_uw=0.0, theta_qwp=30)
        data = {
            'quarterwave': {
                'rows': [{'phi': float(p), 'i_raw': float(i)} for p, i in zip(phis, I_theory)]
            }
        }
        result = adapter.process_all(data)
        qw = result['results']['quarterwave']
        # ratio should be 3.0 for theta=30
        assert abs(qw['ratio_theory'] - 3.0) < 0.01
        assert abs(qw['ratio_exp'] - 3.0) < 0.01
        # A_avg should be close to A_true
        assert abs(qw['A_avg'] - A_true) < 0.5

    def test_background_correction(self):
        """Non-zero bg should shift intensities."""
        adapter = PolarizationAdapter(bg_uw=5.0)
        data = {
            'malus': {
                'rows': [
                    {'theta': 0, 'i_left': 105.0, 'i_right': 105.0},
                    {'theta': 45, 'i_left': 57.5, 'i_right': 57.5},
                    {'theta': 90, 'i_left': 5.0, 'i_right': 5.0},
                ]
            }
        }
        result = adapter.process_all(data)
        # With bg=5, I_mean at 90° should be 0 (5-5=0)
        # Slope should be ~100 (I0=100, bg subtracted)
        assert result['results']['malus']['slope'] > 90

    def test_parameter_summary_has_no_hardcoded_malus_reference(self):
        """Malus I0 is fitted from measurements; 100 μW is not universal theory."""
        from pathlib import Path
        report_source = Path(__file__).parents[1] / 'experiments' / 'polarization' / 'reports.py'
        source = report_source.read_text(encoding='utf-8')
        assert '"理论 100"' not in source


# ─── Config tests ────────────────────────────────────────────

class TestConfig:
    def test_config_loads(self):
        import json
        config_path = os.path.join(os.path.dirname(__file__), '..', 'experiments', 'polarization', 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        assert config['id'] == 'polarization'
        assert len(config['subExperiments']) == 4
        assert config['subExperiments'][0]['id'] == 'malus'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
