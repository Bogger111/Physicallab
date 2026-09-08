# Theoretical calculations for polarization lab
# All formulas sourced from PDF experiment handout

import math
import numpy as np
from typing import Tuple


def malus_law(theta_deg: np.ndarray, I0: float) -> np.ndarray:
    """Malus's Law: I = I0 * cos²(θ)
    
    Source: PDF formula (I = I₀cos²θ)
    
    Args:
        theta_deg: angle in degrees
        I0: incident intensity
    
    Returns:
        Transmitted intensity array
    """
    theta_rad = np.radians(theta_deg)
    return I0 * np.cos(theta_rad) ** 2


def cos2_theta(theta_deg: np.ndarray) -> np.ndarray:
    """Compute cos²(θ) from degrees.
    
    NOTE: Must use exact computation, NOT the rounded values from textbook table.
    Textbook table values (0.00, 0.03, 0.12, ...) are for display only.
    """
    return np.cos(np.radians(theta_deg)) ** 2


def half_wave_theory(delta_C_deg: float) -> float:
    """λ/2 waveplate theory: ΔP2 = 2ΔC
    
    Source: PDF formula (8) and text "偏振方向转过了2θ"
    
    Args:
        delta_C_deg: waveplate rotation from initial (degrees)
    
    Returns:
        Expected ΔP2 (degrees)
    """
    return 2.0 * delta_C_deg


def quarter_wave_intensity(phi_deg: np.ndarray, theta_deg: float, A: float) -> np.ndarray:
    """λ/4 waveplate intensity formula (9): I = A²[sin²θsin²φ + cos²θcos²φ]
    
    Source: PDF formula (9), when C is λ/4 and P1⊥P2, δ' = 3π/2
    
    Args:
        phi_deg: angle between C' optical axis and P2 (degrees), 0-360
        theta_deg: angle between P1 and C' optical axis (degrees), typically 30° or 60°
        A: amplitude parameter (extracted from experiment)
    
    Returns:
        Intensity array
    """
    phi_rad = np.radians(phi_deg)
    theta_rad = np.radians(theta_deg)
    return A**2 * (np.sin(theta_rad)**2 * np.sin(phi_rad)**2 +
                   np.cos(theta_rad)**2 * np.cos(phi_rad)**2)


def quarter_wave_Imax_Imin(theta_deg: float, A: float) -> Tuple[float, float]:
    """Compute theoretical Imax and Imin for λ/4 waveplate.
    
    Source: Derived from PDF formula (9)
    Imax = A² × max(sin²θ, cos²θ)
    Imin = A² × min(sin²θ, cos²θ)
    
    Args:
        theta_deg: angle between P1 and C' optical axis
        A: amplitude parameter
    
    Returns:
        (Imax, Imin)
    """
    theta_rad = np.radians(theta_deg)
    sin2 = np.sin(theta_rad)**2
    cos2 = np.cos(theta_rad)**2
    return A**2 * max(sin2, cos2), A**2 * min(sin2, cos2)


def quarter_wave_ratio_theory(theta_deg: float) -> float:
    """Theoretical Imax/Imin ratio for λ/4 waveplate.
    
    Source: Derived from PDF formula (9)
    R = max(sin²θ, cos²θ) / min(sin²θ, cos²θ)
    
    NOTE: For θ=30° or θ=60°, R = 3, but must NOT be hardcoded.
    """
    theta_rad = np.radians(theta_deg)
    sin2 = np.sin(theta_rad)**2
    cos2 = np.cos(theta_rad)**2
    return max(sin2, cos2) / min(sin2, cos2) if min(sin2, cos2) > 0 else float('inf')


def extract_A_from_extremes(I_max_exp: float, I_min_exp: float, theta_deg: float) -> Tuple[float, float]:
    """Extract A parameter from experimental Imax and Imin.
    
    Source: PDF data processing §3: "先由(9)式推得Imax或Imin的表达式，并与实验数据中的
    最大或最小值比较，从而得到A值"
    
    A_from_max = sqrt(Imax_exp / max(sin²θ, cos²θ))
    A_from_min = sqrt(Imin_exp / min(sin²θ, cos²θ))
    
    Args:
        I_max_exp: experimental maximum intensity
        I_min_exp: experimental minimum intensity
        theta_deg: θ angle in degrees
    
    Returns:
        (A_from_max, A_from_min)
    """
    theta_rad = np.radians(theta_deg)
    sin2 = np.sin(theta_rad)**2
    cos2 = np.cos(theta_rad)**2
    a_max = math.sqrt(I_max_exp / max(sin2, cos2)) if max(sin2, cos2) > 0 else 0
    a_min = math.sqrt(I_min_exp / min(sin2, cos2)) if min(sin2, cos2) > 0 else 0
    return a_max, a_min


def circular_ideal_intensity(A: float) -> float:
    """Ideal circular polarization intensity (constant for all P2 angles).
    
    Source: Derived from source theory. For θ=45° in formula (9):
    I = A²[sin²(45°)sin²φ + cos²(45°)cos²φ] = A² × 0.5
    """
    return A**2 * 0.5
