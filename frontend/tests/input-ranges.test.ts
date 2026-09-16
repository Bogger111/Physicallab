import test from "node:test";
import assert from "node:assert/strict";

import {
  RANGE_EXPERIMENT_IDS,
  getInputRange,
  isOutsideRange,
  rangeLabel,
} from "../src/lib/input-ranges.ts";

test("every published experiment has frontend range guidance", () => {
  assert.deepEqual(new Set(RANGE_EXPERIMENT_IDS), new Set([
    "polarization", "sound-light", "multimeter", "bridge", "photoelectric",
    "franck-hertz", "solar-cell", "gmr", "nmr", "viscosity",
    "surface-tension", "thermal-conductivity", "michelson",
  ]));
});

test("range warnings are advisory and format a student-facing label", () => {
  const hint = getInputRange("polarization", "halfwave", "c_min");
  assert.equal(isOutsideRange("59", hint), false);
  assert.equal(isOutsideRange("60", hint), true);
  assert.equal(rangeLabel(hint, "′"), "建议 0–59.99 ′");
  assert.equal(isOutsideRange("", hint), false);
});
