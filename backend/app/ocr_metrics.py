"""Metrics used by a future OCR benchmark and the feedback dashboard."""

from __future__ import annotations

from itertools import zip_longest


def cell_exact_match_accuracy(predictions: list[str], ground_truth: list[str]) -> float:
    if not ground_truth:
        return 0.0
    return sum(pred == truth for pred, truth in zip_longest(predictions, ground_truth, fillvalue="")) / len(ground_truth)


def character_accuracy(predictions: list[str], ground_truth: list[str]) -> float:
    if not ground_truth:
        return 0.0
    correct = total = 0
    for prediction, truth in zip_longest(predictions, ground_truth, fillvalue=""):
        correct += sum(a == b for a, b in zip(prediction, truth))
        total += max(len(prediction), len(truth))
    return correct / total if total else 0.0


def correction_rate(predictions: list[str], confirmed: list[str]) -> float:
    if not confirmed:
        return 0.0
    return sum(pred != value for pred, value in zip_longest(predictions, confirmed, fillvalue="")) / len(confirmed)
