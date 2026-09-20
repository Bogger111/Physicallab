"""Formula-audit oracle scaffolding for every published experiment.

Why this exists
---------------
`bridge` shipped three formula-mapping bugs that all unit tests missed, because the
tests built their "expected" numbers from the *same* wrong expression the adapter
used (self-certifying fixtures).  "Tests pass" therefore proves the code matches
the fixture — not that the fixture matches the lecture.

This script does the mechanical part of an audit so a human can do the physical
part.  For every catalogue experiment it dumps the implementation surface
(formulas, params with units, result keys, numeric literals inside `calculate`),
records each fixture's provenance, and flags the specific risks that produced the
bridge bugs:

* ``circular_fixture`` — a test/support module that imports the adapter and also
  asserts numbers (its inputs are probably derived from the implementation);
* ``unit_factor`` — explicit ``1e-3`` / ``1e-6`` style conversions inside a
  calculation (bridge's inductor ``mH`` factor lives here);
* ``fit`` — a least-squares fit whose slope/intercept are reported as physics
  (bridge's ``alpha`` came out negative because of a wrong input);
* ``inverse_solve`` — a division by a difference of measured quantities, where the
  wrong parameter (or unit) silently rescales the answer (bridge's ``R``).

Usage
-----
    python scripts/audit_formula_oracle.py --json docs/validation/formula-audit.json \\
                                           --markdown docs/validation/formula-audit.md
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from experiments.core.registry import PUBLIC_EXPERIMENT_IDS, registry  # noqa: E402

ADAPTER_RELPATH = {
    "polarization": "experiments/polarization/adapter.py",
    "sound-light": "experiments/soundlight/engine.py",
    "photoelectric-franck-hertz": "experiments/photoelectric_franck_hertz/adapter.py",
}

UNIT_FACTOR = re.compile(r"\b1e-?\d+\b|\b\d+e-?\d+\b")
INVERSE = re.compile(r"/\s*\(\s*[A-Za-z_][\w\.]*\s*-\s*[A-Za-z_0-9\.]*\s*\)")


def adapter_path(experiment_id: str) -> Path:
    relative = ADAPTER_RELPATH.get(experiment_id, f"experiments/{experiment_id.replace('-', '_')}/adapter.py")
    return BACKEND / relative


def source_of(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def calculate_source(text: str) -> str:
    """Return the body of the module-level ``calculate``/``analyze`` entry point."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"calculate", "analyze"}:
            return ast.get_source_segment(text, node) or text
    return text


def numeric_literals(code: str) -> list[str]:
    """Decimal literals excluding 0/1/2 style loop constants."""
    found: list[str] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type == tokenize.NUMBER:
                value = token.string
                if value in {"0", "1", "2", "3", "4", "10", "100", "1000", "0.5"}:
                    continue
                if value not in found:
                    found.append(value)
    except tokenize.TokenError:
        pass
    return found


def config_methods(experiment) -> list[dict]:
    config = experiment.config
    if isinstance(config, list):                     # sound-light keeps a method array
        return config
    return config.get("methods") or config.get("subExperiments") or []


def formulas_map(experiment, experiment_id: str) -> dict:
    """`experiment.formulas` when the adapter exposes it, else the module's FORMULAS constant."""
    mapping = getattr(experiment, "formulas", None)
    if isinstance(mapping, dict) and mapping:
        return mapping
    text = source_of(adapter_path(experiment_id))
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "FORMULAS" for target in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return {}
            return value if isinstance(value, dict) else {}
    return {}


def fixture_report(experiment_id: str) -> list[dict]:
    directory = BACKEND / "tests" / "fixtures" / experiment_id
    entries = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        entries.append({
            "file": path.name,
            "source": payload.get("source", ""),
            "verified": payload.get("verified"),
            "scientific_validation": payload.get("scientific_validation", ""),
        })
    return entries


def circular_fixtures(experiment_id: str) -> list[str]:
    """Test modules that both import the adapter and assert numbers."""
    hits: list[str] = []
    candidates = [BACKEND / "tests", BACKEND / "scripts", BACKEND / "experiments" / "core"]
    adapter_module = f"experiments.{experiment_id.replace('-', '_')}"
    for directory in candidates:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            text = source_of(path)
            if adapter_module not in text:
                continue
            imports_adapter = re.search(rf"from {adapter_module}(\.\w+)? import|import {adapter_module}\b", text)
            if imports_adapter and ("approx(" in text or "assert" in text):
                hits.append(str(path.relative_to(BACKEND)).replace("\\", "/"))
    return hits


def shared_literals(experiment_id: str, adapter_body: str) -> list[dict]:
    """Numeric literals that appear in BOTH the adapter and a test/support module.

    A shared constant is not automatically wrong (``0.004280`` is the lecture's Cu50
    coefficient), but a shared *derived* constant (``4000`` = 4 × 1 kΩ bridge arm) is
    exactly how the bridge fixture certified the buggy expression.  Report the values
    so a reviewer judges the provenance instead of trusting a boolean.
    """
    literals = {value for value in numeric_literals(adapter_body)}
    if not literals:
        return []
    hits: list[dict] = []
    for directory in (BACKEND / "tests", BACKEND / "scripts"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            text = source_of(path)
            if experiment_id not in text and experiment_id.replace("-", "_") not in text:
                continue
            shared = sorted(value for value in numeric_literals(text) if value in literals)
            if shared:
                hits.append({"file": str(path.relative_to(BACKEND)).replace("\\", "/"),
                             "shared_literals": shared})
    return hits


def risk_flags(experiment_id: str, experiment) -> list[str]:
    text = source_of(adapter_path(experiment_id))
    body = calculate_source(text)
    flags = []
    if "_fit(" in body or "polyfit" in body or "curve_fit" in body:
        flags.append("fit")
    if UNIT_FACTOR.search(body):
        flags.append("unit_factor")
    if INVERSE.search(body):
        flags.append("inverse_solve")
    if circular_fixtures(experiment_id) or shared_literals(experiment_id, body):
        flags.append("circular_fixture")
    return flags


def audit(experiment_id: str) -> dict:
    experiment = registry.get(experiment_id)
    path = adapter_path(experiment_id)
    text = source_of(path)
    body = calculate_source(text)
    formulas = formulas_map(experiment, experiment_id)
    methods = []
    for method in config_methods(experiment):
        methods.append({
            "id": method.get("id"),
            "name": method.get("name"),
            "required": method.get("required", False),
            "params": [{"key": p.get("key"), "label": p.get("label"), "unit": p.get("unit", ""),
                        "default": p.get("default"), "required": p.get("required", False),
                        "hint": bool(p.get("hint"))} for p in method.get("params", [])],
            "columns": [{"key": c.get("key"), "label": c.get("label"), "unit": c.get("unit", "")}
                        for c in method.get("columns", [])],
            "results": [{"key": r.get("key"), "label": r.get("label"), "unit": r.get("unit", "")}
                        for r in method.get("results", [])],
            "formulas": formulas.get(method.get("id"), []),
        })
    return {
        "experiment_id": experiment_id,
        "name": experiment.config["name"] if isinstance(experiment.config, dict) else experiment_id,
        "adapter": str(path.relative_to(BACKEND)).replace("\\", "/"),
        "adapter_exists": path.is_file(),
        "methods": methods,
        "literals_in_calculate": numeric_literals(body),
        "risk_flags": risk_flags(experiment_id, experiment),
        "fixture_provenance": fixture_report(experiment_id),
        "circular_test_modules": circular_fixtures(experiment_id),
        "shared_literals": shared_literals(experiment_id, body),
    }


PRIORITY = {
    "fit": "高（拟合把输入错误放大成物理量）",
    "inverse_solve": "高（反解式最容易像 bridge 一样取错参数/单位）",
    "unit_factor": "中（单位换算只在一处写错就整体偏移）",
    "circular_fixture": "中（fixture 由实现反推＝自证循环）",
}


FIT_RESULT_KEYS = {"r_squared", "slope", "intercept", "alpha", "b_constant", "sensitivity",
                   "k", "h", "gamma", "wavelength", "sigma", "sigma_reference",
                   "absolute_error", "relative_error", "v0", "v_theory", "speed"}


def flagged_methods(item: dict) -> list[str]:
    """Methods whose reported quantities are fitted/derived (where a wrong input hides)."""
    names = []
    for method in item["methods"]:
        keys = {result["key"] for result in method["results"]}
        if keys & FIT_RESULT_KEYS:
            names.append(method["name"])
    return names


def markdown(report: dict) -> str:
    lines = [
        "# 12 实验公式审计清单（audit oracle）",
        "",
        "> 由 `backend/scripts/audit_formula_oracle.py` 生成。它只做**机械部分**：把实现面、常数、fixture 出身和风险点摆出来；",
        "> **物理部分（对照讲义原文、独立手算 probe）必须人工完成**，结论写在本表最后两列。",
        "",
        "## 判据（来自 bridge 的教训）",
        "",
        "1. **公式映射**：adapter 里每个变量是否就是讲义公式里的那个量（bridge 把卧式公式的 `R` 取成了桥臂 1000 Ω 而不是预平衡 Rn）。",
        "2. **单位**：`Cn` 是 μF 还是 F、`U0` 是 mV 还是 V，换算是否只在一处发生。",
        "3. **参数语义**：固定实验条件 vs 现场实测量（后者不该有 default、不该在空白记录表预填）。",
        "4. **fixture 是否循环自证**：测试数据如果由 adapter 的（错）公式反推，测试全绿也不能证明结果对。",
        "",
        "验收口径：**用讲义公式独立手算一组可手验的 probe → 喂给 adapter → 对比**；对不上就是 bug，不是 fixture 过期。",
        "",
        "## 机器扫描结果",
        "",
        "| 实验 | 方法数 | 风险标记 | 含拟合/派生结果量的方法（优先手算） | fixture | 手算 probe | 结论 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in report["experiments"]:
        flags = "、".join(item["risk_flags"]) or "—"
        high = flagged_methods(item)
        fixture = item["fixture_provenance"]
        fixture_note = "；".join(f"{f['file']}:{f['scientific_validation'] or f['source'] or '未标注'}"
                                 for f in fixture) or "无 fixture"
        pending = "待做" if item["experiment_id"] != "bridge" else "**已完成**（3 处算法错误 + 记录表语义，见 bridge 审计报告）"
        verdict = "已修" if item["experiment_id"] == "bridge" else "待审"
        lines.append(f"| {item['name']}（{item['experiment_id']}） | {len(item['methods'])} | {flags} | "
                     f"{'、'.join(high[:4])} | {fixture_note} | {pending} | {verdict} |")

    lines += ["", "## 逐实验实现面", ""]
    for item in report["experiments"]:
        lines.append(f"### {item['name']}（`{item['experiment_id']}`）")
        lines.append("")
        lines.append(f"- adapter：`{item['adapter']}`")
        lines.append(f"- 风险标记：{'、'.join(item['risk_flags']) or '无'}")
        if item["circular_test_modules"]:
            lines.append(f"- 同时 import adapter 又断言数值的测试模块：{'、'.join(item['circular_test_modules'])}")
        if item["shared_literals"]:
            lines.append("- **与测试/脚本共用的数值常量（逐条判断出处）**：")
            for hit in item["shared_literals"]:
                lines.append(f"  - `{hit['file']}`：`{'`, `'.join(hit['shared_literals'])}`")
        if item["fixture_provenance"]:
            for fixture in item["fixture_provenance"]:
                lines.append(f"- fixture `{fixture['file']}`：source={fixture['source'] or '—'}、"
                             f"verified={fixture['verified']}、validation={fixture['scientific_validation'] or '—'}")
        if item["literals_in_calculate"]:
            lines.append(f"- `calculate` 中的数值常量：`{'`, `'.join(item['literals_in_calculate'])}`（逐条核对出处）")
        lines.append("")
        lines.append("| 方法 | 必做 | 参数（含单位/默认/是否实测） | 数据列 | 结果量 |")
        lines.append("|---|---|---|---|---|")
        for method in item["methods"]:
            params = "；".join(
                f"{p['label']}({p['unit']})" + (f"={p['default']}" if p["default"] is not None else "=实测留空")
                + ("[必填]" if p["required"] else "")
                for p in method["params"]) or "—"
            columns = "；".join(f"{c['label']}({c['unit']})" if c["unit"] else c["label"] for c in method["columns"]) or "—"
            results = "；".join(r["label"] for r in method["results"]) or "—"
            lines.append(f"| {method['name']} | {'是' if method['required'] else '选做'} | {params} | {columns} | {results} |")
        lines.append("")
        for method in item["methods"]:
            if method["formulas"]:
                lines.append(f"- **{method['name']}** 公式（实现自述）：")
                for formula in method["formulas"]:
                    lines.append(f"  - `{formula}`")
        lines.append("")
        lines.append(f"- 手算 probe：待做（优先级：{PRIORITY.get(item['risk_flags'][0], '常规') if item['risk_flags'] else '常规'}）")
        lines.append(f"- 讲义对照结论：待填写")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=BACKEND.parent / "docs" / "validation" / "formula-audit.json")
    parser.add_argument("--markdown", type=Path,
                        default=BACKEND.parent / "docs" / "validation" / "formula-audit.md")
    args = parser.parse_args(argv)

    report = {"experiments": [audit(experiment_id) for experiment_id in PUBLIC_EXPERIMENT_IDS]}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.markdown.write_text(markdown(report), encoding="utf-8")

    counts: dict[str, int] = {}
    for item in report["experiments"]:
        for flag in item["risk_flags"]:
            counts[flag] = counts.get(flag, 0) + 1
    print(f"wrote {args.json} and {args.markdown}")
    print("risk counts:", counts)
    for item in report["experiments"]:
        print(f"  {item['experiment_id']:<28} flags={'、'.join(item['risk_flags']) or '—'}"
              f" methods={len(item['methods'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
