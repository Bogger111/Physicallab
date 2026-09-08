# Angle utilities for polarization lab
# All angle inputs are in (degree, minute) pairs from the dial readings.
# CRITICAL: Only differences within the SAME device are meaningful.

import math
from typing import Tuple, Optional


def dms_to_decimal(degree: float, minute: float) -> float:
    """Convert degree + minute to decimal degrees.
    
    Args:
        degree: integer degrees (0-359)
        minute: arc-minutes (0-59)
    
    Returns:
        Decimal degrees (e.g., 271°28' -> 271.4667)
    """
    return degree + minute / 60.0


def unwrap_angle_delta(delta: float) -> float:
    """Unwrap a small angle difference to handle 0°/360° boundary.
    
    For small rotations (e.g., 10° steps), the actual change should be
    the shortest-path interpretation. E.g., 358° -> 18° = +20° (not -340°).
    
    Args:
        delta: raw difference (new - old) in degrees
    
    Returns:
        Unwrapped delta in range (-180, 180]
    """
    delta = delta % 360
    if delta > 180:
        delta -= 360
    return delta


def unwrap_series(angles_deg: list) -> list:
    """Unwrap a series of angles to remove 0°/360° jumps.
    
    Used when consecutive readings might cross the 0°/360° boundary.
    Each subsequent angle is adjusted to be closest to the previous one.
    
    Args:
        angles_deg: list of angles in decimal degrees
    
    Returns:
        Unwrapped series (continuous, may exceed 360° or go negative)
    """
    if not angles_deg:
        return []
    result = [angles_deg[0]]
    for i in range(1, len(angles_deg)):
        delta = angles_deg[i] - angles_deg[i - 1]
        delta = (delta + 180) % 360 - 180  # wrap to (-180, 180]
        result.append(result[-1] + delta)
    return result


def compute_delta_series(readings_deg: list, initial_deg: float) -> list:
    """Compute relative angle changes from initial reading for the SAME device.
    
    CRITICAL: This only makes sense for readings from ONE device (one dial).
    Never use this to compare readings between different devices.
    
    Args:
        readings_deg: list of absolute dial readings (decimal degrees)
        initial_deg: initial dial reading (decimal degrees)
    
    Returns:
        List of Δ values (change from initial), unwrapped
    """
    deltas = []
    for r in readings_deg:
        raw_delta = r - initial_deg
        deltas.append(unwrap_angle_delta(raw_delta))
    return deltas


def validate_minute(minute: float) -> bool:
    """Check that minute value is in valid range [0, 60)."""
    return 0 <= minute < 60


def validate_angle(degree: float, minute: float) -> Tuple[bool, str]:
    """Validate a degree+minute input pair."""
    if not validate_minute(minute):
        return False, f"Minute value {minute} must be in [0, 60)"
    if degree < 0 or degree >= 360:
        return False, f"Degree value {degree} must be in [0, 360)"
    return True, ""


def circular_mean(angles_deg: list) -> float:
    """Compute circular mean of angles in degrees.
    
    Handles wrapping: e.g., mean of 350° and 10° = 0° (not 180°).
    """
    if not angles_deg:
        return 0.0
    sin_sum = sum(math.sin(math.radians(a)) for a in angles_deg)
    cos_sum = sum(math.cos(math.radians(a)) for a in angles_deg)
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360
