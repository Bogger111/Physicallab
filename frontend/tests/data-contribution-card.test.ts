import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

/**
 * The contribution card is user-facing: it must thank the contributor, explain
 * what was saved and what comes next, keep the voluntary/withdraw/redacted
 * promises visible, and never leak internals (full UUID, storage path).
 */

const read = (relative: string) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

const panel = read("../src/components/workspace/DataContributionPanel.tsx");
const hook = read("../src/hooks/useDataCollection.ts");
const api = read("../src/lib/api.ts");

test("the contribution card thanks the contributor and names the experiment", () => {
  assert.match(panel, /感谢参与 PhysLab 数据共建！/);
  assert.match(panel, /实验类型/);
  assert.match(panel, /collection\.experimentName \?\? experimentName/);
});

test("the card states what was saved and what happens next", () => {
  assert.match(panel, /图片已安全保存/);
  assert.match(panel, /数据确认后生成 OCR 训练样本/);
  assert.match(panel, /已生成 OCR 训练样本/);
  assert.match(panel, /当前贡献/);
});

test("the card reports how many OCR samples the contribution produces", () => {
  assert.match(panel, /预计生成/);
  assert.match(panel, /个 OCR 样本/);
  assert.match(panel, /collection\.estimatedSamples/);
  assert.match(hook, /estimatedSamples/);
  assert.match(api, /estimated_samples\?: number/);
});

test("the voluntary / withdraw / redacted promises stay visible", () => {
  assert.match(panel, /自愿参与，随时可撤回/);
  assert.match(panel, /已做脱敏处理/);
  assert.match(panel, /随时可以撤回删除/);
  assert.match(panel, /去除 EXIF 拍摄信息/);
});

test("the withdraw button deletes the session through the API", () => {
  assert.match(panel, /撤回贡献/);
  assert.match(panel, /collection\.withdraw\(\)/);
  assert.match(hook, /deleteDataCollectionSession\(sessionId\)/);
  assert.match(api, /method: "DELETE"/);
});

test("the card never renders internals", () => {
  // only a short reference is displayed, never the full identifier
  assert.match(panel, /collection\.sessionId\.slice\(0, 8\)/);
  assert.ok(!panel.includes("{collection.sessionId}"), "the full session UUID must not be rendered");
  assert.ok(!/sessions\//.test(panel), "storage paths must not be rendered");
  assert.ok(!panel.includes("data_collection"), "storage paths must not be rendered");
  assert.ok(!panel.includes("collection_root"), "storage paths must not be rendered");
});

test("the contribution flow still requires explicit consent before upload", () => {
  assert.match(panel, /disabled=\{!collection\.consent \|\| !collection\.file/);
  assert.match(hook, /if \(!enabled \|\| !consent \|\| !file \|\| sessionId\) return;/);
});
