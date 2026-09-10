export interface CompletionMethod {
  id: string;
  name: string;
  required: boolean;
  paramKeys: string[];
  columnKeys: string[];
}

export type CompletionDraft = Record<
  string,
  { rows: Record<string, string>[]; params: Record<string, string> }
>;

function filled(value: string | undefined): boolean {
  return typeof value === "string" && value.trim() !== "";
}

export function isMethodComplete(
  method: CompletionMethod,
  draft: CompletionDraft
): boolean {
  const source = draft[method.id];
  if (!source || source.rows.length === 0) return false;
  return (
    method.paramKeys.every((key) => filled(source.params[key])) &&
    source.rows.every((row) => method.columnKeys.every((key) => filled(row[key])))
  );
}

export function completionState(
  methods: CompletionMethod[],
  draft: CompletionDraft
) {
  const completedMethodIds = methods
    .filter((method) => isMethodComplete(method, draft))
    .map((method) => method.id);
  const required = methods.filter((method) => method.required);
  const missing = required.filter((method) => !completedMethodIds.includes(method.id));
  return {
    requiredCount: required.length,
    completedRequiredCount: required.length - missing.length,
    requiredAllComplete: missing.length === 0,
    missingRequiredNames: missing.map((method) => method.name),
    completedMethodIds,
  };
}

export function nextGridCell(
  key: string,
  row: number,
  column: number,
  rowCount: number,
  columnCount: number
): [number, number] | null {
  const delta: Record<string, [number, number]> = {
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1],
  };
  const movement = delta[key];
  if (!movement) return null;
  const nextRow = row + movement[0];
  const nextColumn = column + movement[1];
  if (
    nextRow < 0 ||
    nextRow >= rowCount ||
    nextColumn < 0 ||
    nextColumn >= columnCount
  ) {
    return null;
  }
  return [nextRow, nextColumn];
}
