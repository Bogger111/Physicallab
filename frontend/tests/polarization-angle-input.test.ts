import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const sourcePath = fileURLToPath(
  new URL("../src/app/experiments/[id]/workspace/client-page.tsx", import.meta.url)
);
const source = readFileSync(sourcePath, "utf8");

test("quarter-wave fast-axis angle is a freely editable numeric input", () => {
  const control = source.match(
    /1\/4 波片快轴 θ_qwp<\/span>([\s\S]*?)<\/label>/
  )?.[1];

  assert.ok(control, "quarter-wave angle control should exist");
  assert.match(control, /<input/);
  assert.match(control, /type="number"/);
  assert.match(control, /step="any"/);
  assert.match(control, /onWheel=/);
  assert.match(control, />\s*°\s*<\/span>/);
  assert.doesNotMatch(control, /<select/);
});

test("quarter-wave angle preserves a user-entered zero", () => {
  assert.match(source, /theta_qwp:\s*numberOrNull\(thetaQwp\)\s*\?\?\s*30/);
});
