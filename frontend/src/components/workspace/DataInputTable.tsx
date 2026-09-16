"use client";

import { useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { isOutsideRange, rangeLabel, type InputRangeHint } from "@/lib/input-ranges";
import OcrTableImporter from "./OcrTableImporter";

interface Header {
  label: string;
  readOnly?: boolean;
  range?: InputRangeHint;
  unit?: string;
}

interface Props {
  headers: Header[];
  data: string[][];
  onChange: (data: string[][]) => void;
  compact?: boolean;
  ocr?: { experimentId: string; tableId: string };
}

export default function DataInputTable({
  headers,
  data,
  onChange,
  compact,
  ocr,
}: Props) {
  const inputRefs = useRef<(HTMLInputElement | null)[][]>([]);

  const handleChange = useCallback(
    (row: number, col: number, value: string) => {
      const next = data.map((r) => [...r]);
      next[row][col] = value;
      onChange(next);
    },
    [data, onChange]
  );

  const handleKeyDown = useCallback(
    (
      e: React.KeyboardEvent<HTMLInputElement>,
      row: number,
      col: number
    ) => {
      // 方向键在表格内移动焦点（跳过“自动/只读”列，到边界即停）
      if (e.key.startsWith("Arrow")) {
        e.preventDefault();
        const [dr, dc] =
          e.key === "ArrowUp"
            ? [-1, 0]
            : e.key === "ArrowDown"
              ? [1, 0]
              : e.key === "ArrowLeft"
                ? [0, -1]
                : [0, 1];
        if (dr !== 0) {
          const tr = row + dr;
          const el = inputRefs.current[tr]?.[col];
          if (el && !headers[col]?.readOnly) el.focus();
        } else {
          let tc = col + dc;
          while (tc >= 0 && tc < headers.length) {
            if (!headers[tc]?.readOnly) {
              inputRefs.current[row]?.[tc]?.focus();
              break;
            }
            tc += dc;
          }
        }
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        const nextCol = col + (e.shiftKey ? -1 : 1);
        if (nextCol >= 0 && nextCol < headers.length) {
          inputRefs.current[row]?.[nextCol]?.focus();
        } else if (!e.shiftKey && row + 1 < data.length) {
          const firstEditable = headers.findIndex((h) => !h.readOnly);
          inputRefs.current[row + 1]?.[firstEditable >= 0 ? firstEditable : 0]?.focus();
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (row + 1 < data.length) {
          inputRefs.current[row + 1]?.[col]?.focus();
        }
      }
    },
    [data.length, headers]
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent, startRow: number, startCol: number) => {
      e.preventDefault();
      const text = e.clipboardData.getData("text");
      const rows = text
        .split(/[\r\n]+/)
        .map((line) => line.split(/[\t,]/));
      if (rows.length <= 1 && rows[0].length <= 1) return;

      const next = data.map((r) => [...r]);
      for (let i = 0; i < rows.length; i++) {
        const targetRow = startRow + i;
        if (targetRow >= next.length) break;
        for (let j = 0; j < rows[i].length; j++) {
          const targetCol = startCol + j;
          if (targetCol >= headers.length) break;
          if (headers[targetCol].readOnly) continue;
          next[targetRow][targetCol] = rows[i][j].trim();
        }
      }
      onChange(next);
    },
    [data, headers, onChange]
  );

  const editableCoordinates = data.flatMap((row, rowIndex) =>
    row.flatMap((_, columnIndex) =>
      headers[columnIndex]?.readOnly ? [] : [[rowIndex, columnIndex] as const]
    )
  );

  const applyOCR = (values: string[], overwriteExisting: boolean) => {
    const next = data.map((row) => [...row]);
    editableCoordinates.forEach(([rowIndex, columnIndex], index) => {
      const value = values[index]?.trim();
      if (!value) return;
      if (!overwriteExisting && next[rowIndex][columnIndex].trim()) return;
      next[rowIndex][columnIndex] = value;
    });
    onChange(next);
  };

  return (
    <>
      {ocr && editableCoordinates.length > 0 && (
        <OcrTableImporter
          experimentId={ocr.experimentId}
          tableId={ocr.tableId}
          expectedCellCount={editableCoordinates.length}
          onApply={applyOCR}
        />
      )}
      <div className="overflow-hidden rounded-xl border border-stone-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th
                  key={i}
                  scope="col"
                  className={cn(
                    "whitespace-nowrap border-b border-stone-200 bg-stone-50 text-left text-xs font-bold text-stone-500",
                    compact ? "px-3 py-2.5" : "px-4 py-3",
                    i === 0 && "pl-5"
                  )}
                >
                  {h.label}
                  {rangeLabel(h.range, h.unit) && (
                    <span className="mt-0.5 block text-[10px] font-normal text-amber-600">
                      {rangeLabel(h.range, h.unit)}
                    </span>
                  )}
                  {h.readOnly && (
                    <span className="ml-1.5 font-normal text-stone-300" aria-hidden>
                      · 自动
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, ri) => (
              <tr
                key={ri}
                className="transition-colors hover:bg-indigo-50/40"
              >
                {row.map((cell, ci) => {
                  const readonly = headers[ci]?.readOnly;
                  const outside = !readonly && isOutsideRange(cell, headers[ci]?.range);
                  const hint = rangeLabel(headers[ci]?.range, headers[ci]?.unit);
                  return (
                    <td
                      key={ci}
                      className={cn(
                        "border-b border-stone-100 p-0 last:border-b-0",
                        ri === data.length - 1 && "border-b-0"
                      )}
                    >
                      <input
                        ref={(el) => {
                          if (!inputRefs.current[ri]) inputRefs.current[ri] = [];
                          inputRefs.current[ri][ci] = el;
                        }}
                        type={readonly ? "text" : "number"}
                        step="any"
                        inputMode={readonly ? undefined : "decimal"}
                        readOnly={readonly}
                        aria-readonly={readonly || undefined}
                        aria-invalid={outside || undefined}
                        title={outside ? `${hint}；当前值可能需要检查` : hint}
                        value={cell}
                        onChange={(e) => handleChange(ri, ci, e.target.value)}
                        onKeyDown={(e) => handleKeyDown(e, ri, ci)}
                        onWheel={(e) => {
                          // 滚动页面时禁止滚轮改值（防误触）
                          e.currentTarget.blur();
                        }}
                        onPaste={(e) => handlePaste(e, ri, ci)}
                        className={cn(
                          "w-full border-0 bg-transparent outline-none transition-colors",
                          compact ? "py-1.5 text-[13px]" : "py-2.5 text-sm",
                          readonly
                            ? "cursor-default bg-stone-50/70 text-center font-mono font-medium text-stone-400"
                            : outside
                              ? "bg-amber-50 px-3.5 text-right font-medium tabular-nums text-amber-900 ring-1 ring-inset ring-amber-300 focus:bg-amber-50"
                              : "px-3.5 text-right font-medium tabular-nums text-stone-800 focus:bg-indigo-50/70",
                          !readonly && compact && "px-2.5",
                          readonly && (compact ? "px-1 text-xs" : "px-1")
                        )}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}
