"use client";

import { useRef, useCallback } from "react";

interface Header {
  label: string;
  readOnly?: boolean;
}

interface Props {
  headers: Header[];
  data: string[][];
  onChange: (data: string[][]) => void;
  compact?: boolean;
}

export default function DataInputTable({
  headers,
  data,
  onChange,
  compact,
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

  return (
    <div className="overflow-x-auto rounded-2xl border border-gray-100 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th
                key={i}
                className="px-4 py-3 text-left text-xs font-semibold text-gray-400 bg-gray-50/80 border-b border-gray-100 whitespace-nowrap"
              >
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, ri) => (
            <tr key={ri} className="hover:bg-blue-50/30 transition-colors">
              {row.map((cell, ci) => (
                <td key={ci} className="border-b border-gray-50">
                  <input
                    ref={(el) => {
                      if (!inputRefs.current[ri]) inputRefs.current[ri] = [];
                      inputRefs.current[ri][ci] = el;
                    }}
                    type={headers[ci]?.readOnly ? "text" : "number"}
                    step="any"
                    readOnly={headers[ci]?.readOnly}
                    value={cell}
                    onChange={(e) => handleChange(ri, ci, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(e, ri, ci)}
                    onPaste={(e) => handlePaste(e, ri, ci)}
                    className={`w-full border-0 bg-transparent px-4 outline-none ${
                      compact ? "py-2 text-xs" : "py-2.5 text-sm"
                    } ${
                      headers[ci]?.readOnly
                        ? "text-gray-300 bg-gray-50/50 font-mono"
                        : "text-gray-900 focus:bg-blue-50/50"
                    }`}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
