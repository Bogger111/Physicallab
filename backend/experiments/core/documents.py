"""Shared blank-sheet and four-section report rendering infrastructure."""

from __future__ import annotations

import math

from experiments.polarization import docbuild
from experiments.report_layout import four_section_report, latex


_TEXT_TRANSLATION = str.maketrans({"⁰":"0","¹":"1","²":"^2","³":"^3","⁴":"4",
                                   "⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9","⁻":"-"})


def safe_text(value: str) -> str:
    """Avoid code points missing from the embedded Chinese PDF fonts."""
    return value.translate(_TEXT_TRANSLATION)


def fmt(value) -> str:
    if value is None or value == "": return ""
    if isinstance(value, str): return safe_text(value)
    try:
        number=float(value)
        if not math.isfinite(number): return "—"
        if abs(number) >= 1e5 or (number and abs(number) < 1e-4): return f"{number:.6e}"
        return f"{number:.6f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError): return str(value)


def _table(rows: list[list], columns: int, font: float = 8.2,
           row_h: float = .52, fixed_row_height: bool = False) -> dict:
    spec = {"kind":"table","widths":[17.7/columns]*columns,"font":font,
            "row_h":row_h,"rows":[[{"text":fmt(cell)} for cell in row] for row in rows]}
    if fixed_row_height:
        spec["fixed_row_height"] = True
    return spec


def _method_raw_table(method: dict, payload: dict, blank: bool = False) -> dict:
    columns=method["columns"]; head=[f"{c['label']} ({c['unit']})" if c.get("unit") else c["label"] for c in columns]
    source=payload.get("rows",[]) if not blank else []
    rows=[head]
    if blank:
        row_count = method["rowCount"]
    else:
        # A completed report should not pad a partially filled optional table
        # with the remaining blank template rows.  Keep gaps inside the data,
        # but trim empty rows after the last submitted value.
        row_count = max(
            (idx + 1 for idx, item in enumerate(source)
             if any(item.get(col["key"]) not in (None, "") for col in columns)),
            default=0,
        )
    for idx in range(row_count):
        item=source[idx] if idx<len(source) else {}
        row=[]
        for col in columns:
            value=item.get(col["key"],"")
            if blank and value=="":
                prefill=method.get("prefill",{}).get(col["key"],[])
                value=prefill[idx] if idx<len(prefill) else ""
            row.append(value)
        rows.append(row)
    if len(rows) > 31 and len(columns) <= 3:
        rows = _fold_rows(rows, target_rows=30)
    if blank:
        # Blank sheets are written on by hand.  Use visibly taller rows while
        # keeping even the longest lecture-prescribed tables on portrait A4.
        body_rows = len(rows) - 1
        row_h = .88 if body_rows <= 12 else .78 if body_rows <= 22 else .68
    else:
        row_h = .52
    return _table(rows,len(rows[0]),7.2 if len(rows[0])>6 else 8.2,
                  row_h=row_h, fixed_row_height=blank)


def _fold_rows(rows: list[list], target_rows: int = 22) -> list[list]:
    """Fold long narrow datasets into repeated horizontal column groups."""
    head, body = rows[0], rows[1:]
    groups = math.ceil(len(body) / target_rows)
    per_group = math.ceil(len(body) / groups)
    folded = [head * groups]
    for row_index in range(per_group):
        line = []
        for group in range(groups):
            source_index = group * per_group + row_index
            line.extend(body[source_index] if source_index < len(body) else [""] * len(head))
        folded.append(line)
    return folded


def record_blocks(experiment) -> list[dict]:
    config=experiment.config; blocks=[]
    for method in config["methods"]:
        blocks.append({"kind":"h2","text":safe_text(("选做：" if not method.get("required") else "")+method["name"])})
        if method.get("params"):
            blocks.append(_table([[f"{p['label']} ({p['unit']})" if p.get('unit') else p['label'] for p in method["params"]],
                                 [p.get("default","") for p in method["params"]]],
                                 len(method["params"]), row_h=.78,
                                 fixed_row_height=True))
            # 现场实测的参数（室温、预平衡 Rn …）在空白表上留空，只给浅灰参考范围提示：
            # 「记录 Rn」记的是学生调平衡后的实测值，预填数字会让空白表看起来像在提供实验数据。
            for parameter in method["params"]:
                if parameter.get("hint"):
                    label = f"{parameter['label']}（{parameter['unit']}）" if parameter.get("unit") else parameter["label"]
                    blocks.append({"kind":"note","text":safe_text(f"{label}：{parameter['hint']}")})
        blocks.append(_method_raw_table(method,{},True)); blocks.append({"kind":"spacer","cm":.12})
    return blocks


def record_bytes(experiment, fmt: str) -> bytes:
    blocks=record_blocks(experiment)
    return docbuild.render_docx(blocks,landscape=False,cn="宋体",cn_en="宋体") if fmt=="docx" else docbuild.render_pdf(blocks,landscape=False,cn_pref="msyh")


def _result_table(method: dict, values: dict) -> dict:
    rows=[["结果量","数值","单位"]]
    for field in method.get("results",[]): rows.append([field["label"],values.get(field["key"]),field.get("unit","")])
    return _table(rows,3)


def _derived_table(rows: list[dict]) -> dict | None:
    if not rows: return None
    keys=list(rows[0].keys()); table_rows=[keys]+[[row.get(key,"") for key in keys] for row in rows]
    if len(table_rows)>25 and len(keys)<=3: table_rows=_fold_rows(table_rows)
    return _table(table_rows,len(table_rows[0]),7.2 if len(table_rows[0])>6 else 8)


def report_blocks(experiment, data: dict) -> list[dict]:
    config=experiment.config; run=experiment.process(data)
    if run["status"]!="success": raise ValueError("；".join(run.get("errors",[])) or "没有可处理的数据")
    tables=[]; figures=[]; analysis=[]
    methods={m["id"]:m for m in config["methods"]}
    for method_id,result in run["results"].items():
        method=methods[method_id]; payload=data.get(method_id,{})
        if method.get("params"):
            tables.append((safe_text(f"{method['name']}参数"),_table([[p["label"] for p in method["params"]],[fmt(payload.get("params",{}).get(p["key"],p.get("default",""))) for p in method["params"]]],len(method["params"]))))
        tables.append((safe_text(f"{method['name']}原始数据"),_method_raw_table(method,payload)))
        detail_rows=run["derived"].get(method_id,[])
        detail=_derived_table(detail_rows)
        if detail: tables.append((safe_text(f"{method['name']}计算明细"),detail))
        tables.append((safe_text(f"{method['name']}结果汇总"),_result_table(method,result)))
        if method_id in run["plots"]:
            figures.append((safe_text(method["name"]),{"b64":run["plots"][method_id],"width_cm":12.5}))
        analysis.append({"kind":"h3","text":safe_text(method["name"])})
        analysis.append({"kind":"para","text":safe_text(method["description"]+"。先筛除空白行并统一到公式所示单位，再计算明细表和汇总结果。")})
        for formula in experiment.formulas.get(method_id,[]): analysis.append(latex(formula))
        for row_index, row in enumerate(detail_rows, start=1):
            substitutions="，".join(f"{key}={fmt(value)}" for key,value in row.items())
            analysis.append({"kind":"note","text":safe_text(f"第 {row_index} 组逐点代入：{substitutions}。")})
        rendered="；".join(f"{field['label']}={fmt(result.get(field['key']))} {field.get('unit','')}" for field in method.get("results",[]))
        analysis.append({"kind":"para","text":safe_text("本组数据代入后："+rendered+"。完整逐点中间量见第一部分对应计算明细表。")})
        analysis.extend(experiment.report_analysis(method_id, result))
    discussion=config["discussion"]
    fourth=[{"kind":"h3","text":"拓展方向"},{"kind":"para","text":safe_text(discussion["extensions"])},
            {"kind":"h3","text":"改进建议"},{"kind":"para","text":safe_text(discussion["suggestions"])},
            {"kind":"h3","text":"误差分析"},{"kind":"para","text":safe_text(discussion["errors"])},
            {"kind":"h3","text":"总结"},{"kind":"para","text":"以上结果来自本次提交数据的公式计算与拟合。算法单元测试与合成 fixture 可验证计算链和文档结构，但不能据此断言完整真实实验数据一定正确；真实结论仍需结合原始记录、仪器条件和讲义判据审核。"}]
    if run.get("errors"):
        fourth.insert(-2, {"kind": "para", "text": "未纳入计算的数据：" + "；".join(run["errors"])})
    # 录入层面的提醒（部分支路缺失、符号丢失、参数填错量纲）必须跟着报告走：
    # 只在网页上弹一次提醒不够，下载下来的报告同样是判据。
    # 但范围提示这类逐行提醒可能有几十条，报告里只保留前几条 + 总数，避免正文被刷屏。
    if run.get("warnings"):
        warnings = [str(item) for item in run["warnings"]]
        shown = "；".join(warnings[:3])
        if len(warnings) > 3:
            shown += f"；……共 {len(warnings)} 条提醒（其余见网页端）"
        fourth.insert(-2, {"kind": "para", "text": safe_text("数据合理性提醒：" + shown)})
    return four_section_report(tables, figures, analysis, fourth)


def report_bytes(experiment, data: dict, fmt: str) -> bytes:
    blocks=report_blocks(experiment,data)
    return docbuild.render_docx(blocks,landscape=False) if fmt=="docx" else docbuild.render_pdf(blocks,landscape=False)
