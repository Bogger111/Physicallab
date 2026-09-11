import assert from "node:assert/strict";
import test from "node:test";

import {
  POLARIZATION_WORKSPACE_STEPS,
  SOUND_LIGHT_WORKSPACE_STEPS,
} from "../src/components/workspace/workspace-entry-flow.ts";

for (const [name, steps] of [
  ["polarization", POLARIZATION_WORKSPACE_STEPS],
  ["sound-light", SOUND_LIGHT_WORKSPACE_STEPS],
] as const) {
  test(`${name} opens directly on data entry`, () => {
    assert.equal(steps[0], "input");
  });

  test(`${name} does not insert a record-sheet step before entry`, () => {
    assert.equal(steps.some((step) => (step as string) === "record"), false);
  });
}
