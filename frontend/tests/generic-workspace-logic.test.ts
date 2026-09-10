import test from "node:test";
import assert from "node:assert/strict";

import {
  completionState,
  nextGridCell,
  type CompletionMethod,
} from "../src/components/workspace/generic-workspace-logic.ts";

const methods: CompletionMethod[] = [
  {
    id: "required-a",
    name: "必做 A",
    required: true,
    paramKeys: ["gain"],
    columnKeys: ["x", "y"],
  },
  {
    id: "optional-b",
    name: "选做 B",
    required: false,
    paramKeys: [],
    columnKeys: ["x"],
  },
];

test("required method is incomplete until every param and table cell is filled", () => {
  const draft = {
    "required-a": {
      params: { gain: "2" },
      rows: [
        { x: "1", y: "2" },
        { x: "3", y: "" },
      ],
    },
    "optional-b": { params: {}, rows: [{ x: "" }] },
  };

  assert.deepEqual(completionState(methods, draft), {
    requiredCount: 1,
    completedRequiredCount: 0,
    requiredAllComplete: false,
    missingRequiredNames: ["必做 A"],
    completedMethodIds: [],
  });

  draft["required-a"].rows[1].y = "4";
  assert.equal(completionState(methods, draft).requiredAllComplete, true);

  draft["required-a"].params.gain = "";
  assert.equal(completionState(methods, draft).requiredAllComplete, false);
});

test("optional methods never block required report readiness", () => {
  const draft = {
    "required-a": {
      params: { gain: "2" },
      rows: [
        { x: "1", y: "2" },
        { x: "3", y: "4" },
      ],
    },
    "optional-b": { params: {}, rows: [{ x: "" }] },
  };
  const state = completionState(methods, draft);
  assert.equal(state.requiredAllComplete, true);
  assert.deepEqual(state.completedMethodIds, ["required-a"]);
});

test("arrow keys move in four directions and stop at table boundaries", () => {
  assert.deepEqual(nextGridCell("ArrowUp", 1, 1, 3, 3), [0, 1]);
  assert.deepEqual(nextGridCell("ArrowDown", 1, 1, 3, 3), [2, 1]);
  assert.deepEqual(nextGridCell("ArrowLeft", 1, 1, 3, 3), [1, 0]);
  assert.deepEqual(nextGridCell("ArrowRight", 1, 1, 3, 3), [1, 2]);
  assert.equal(nextGridCell("ArrowUp", 0, 1, 3, 3), null);
  assert.equal(nextGridCell("ArrowRight", 2, 2, 3, 3), null);
  assert.equal(nextGridCell("Enter", 1, 1, 3, 3), null);
});
