from unittest.mock import patch

import matplotlib.pyplot as plt

from experiments.core.numerics import plot


def test_plot_can_connect_measurements_into_a_curve():
    original = plt.Axes.plot
    with patch.object(plt.Axes, "plot", autospec=True, side_effect=original) as draw_line:
        plot(
            [0, 1, 2],
            [([1, 3, 2], "实验曲线", "#2563eb")],
            "x",
            "y",
            "特性曲线",
            connect_points=True,
        )
    assert draw_line.call_count == 1


def test_plot_highlights_and_draws_the_selected_local_fit():
    original_scatter = plt.Axes.scatter
    original_plot = plt.Axes.plot
    with (
        patch.object(plt.Axes, "scatter", autospec=True, side_effect=original_scatter) as draw_points,
        patch.object(plt.Axes, "plot", autospec=True, side_effect=original_plot) as draw_line,
    ):
        plot(
            [0.0, 1.0, 2.0, 3.0],
            [([40.0, 38.0, 36.0, 35.0], "冷却曲线", "#2563eb")],
            "t / s",
            "TC / °C",
            "自然冷却曲线",
            connect_points=True,
            fit_indices=[1, 2, 3],
        )
    assert draw_points.call_count == 1
    assert draw_line.call_count == 2
    assert any("局部线性拟合" in str(call.kwargs.get("label")) for call in draw_line.call_args_list)


def test_fit_plot_keeps_measurement_points_and_draws_fit_line():
    original_scatter = plt.Axes.scatter
    original_plot = plt.Axes.plot
    with (
        patch.object(plt.Axes, "scatter", autospec=True, side_effect=original_scatter) as draw_points,
        patch.object(plt.Axes, "plot", autospec=True, side_effect=original_plot) as draw_line,
    ):
        plot(
            [0, 1, 2],
            [([1, 3, 5], "测量点", "#2563eb")],
            "x",
            "y",
            "线性拟合",
            fit_lines=True,
        )
    assert draw_points.call_count == 1
    assert draw_line.call_count == 1
