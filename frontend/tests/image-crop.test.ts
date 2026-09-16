import assert from "node:assert/strict";
import test from "node:test";

import { cropFromPoints, isUsableCrop } from "../src/lib/image-crop.ts";

test("crop selection normalizes reverse drags and clamps to the image", () => {
  assert.deepEqual(
    cropFromPoints({ x: 0.8, y: 1.2 }, { x: -0.1, y: 0.25 }),
    { x: 0, y: 0.25, width: 0.8, height: 0.75 },
  );
});

test("crop selection rejects accidental clicks and accepts a visible region", () => {
  assert.equal(isUsableCrop(cropFromPoints({ x: 0.2, y: 0.2 }, { x: 0.21, y: 0.9 })), false);
  assert.equal(isUsableCrop(cropFromPoints({ x: 0.2, y: 0.2 }, { x: 0.8, y: 0.9 })), true);
});
