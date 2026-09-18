import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { isCollectionMode, withCollectionMode } from "../src/lib/collection-mode.ts";

/**
 * "AI 实验共建" must be a *mode of the same workspace*, never a second flow:
 * both entries resolve to the same pages, the ordinary entry creates no
 * collection session, and only the co-build entry shows the contribution surface.
 */

const read = (relative: string) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

const home = read("../src/app/page.tsx");
const list = read("../src/app/experiments/page.tsx");
const detail = read("../src/app/experiments/[id]/client-page.tsx");
const detailPage = read("../src/app/experiments/[id]/page.tsx");
const workspacePage = read("../src/app/experiments/[id]/workspace/page.tsx");
const panel = read("../src/components/workspace/DataContributionPanel.tsx");
const intro = read("../src/components/workspace/CoBuildIntroCard.tsx");
const thanks = read("../src/components/workspace/ContributionThanksDialog.tsx");
const hook = read("../src/hooks/useDataCollection.ts");

test("the mode flag parses and propagates through links", () => {
  assert.equal(isCollectionMode(new URLSearchParams("mode=collection")), true);
  assert.equal(isCollectionMode(new URLSearchParams("mode=co-build")), true);
  assert.equal(isCollectionMode(new URLSearchParams("mode=true")), true);
  assert.equal(isCollectionMode(new URLSearchParams("mode=other")), false);
  assert.equal(isCollectionMode(new URLSearchParams("")), false);
  assert.equal(isCollectionMode(null), false);

  assert.equal(withCollectionMode("/experiments/multimeter", true), "/experiments/multimeter?mode=collection");
  assert.equal(withCollectionMode("/experiments?x=1", true), "/experiments?x=1&mode=collection");
  assert.equal(withCollectionMode("/experiments/multimeter", false), "/experiments/multimeter");
});

test("the home page offers both entries", () => {
  assert.match(home, /href="\/experiments"/);
  assert.match(home, /href="\/experiments\?mode=collection"/);
  assert.match(home, /普通实验 · 选择实验，开始处理/);
  assert.match(home, /AI 实验共建/);
});

test("both entries lead to the same experiment pages", () => {
  // the co-build entry only adds a query flag — no separate route or page copy
  assert.ok(!list.includes('href="/experiments/cobuild'), "no duplicated catalogue route");
  assert.match(list, /withCollectionMode\(`\/experiments\/\$\{exp\.id\}`/);
  assert.match(detail, /withCollectionMode\(`\/experiments\/\$\{experiment\.id\}\/workspace`/);
  assert.ok(
    !/[a-z-]*cobuild[a-z-]*\/page\.tsx/.test(intro),
    "the explainer links into the existing workspace",
  );
  assert.match(intro, /withCollectionMode\(`\/experiments\/\$\{experimentId\}\/workspace`, true\)/);
});

test("the co-build entry explains itself before entering the workspace", () => {
  assert.match(intro, /参与 PhysLab AI 实验共建/);
  assert.match(intro, /你的实验过程不会受到影响/);
  assert.match(intro, /学习真实实验记录/);
  for (const promise of ["自愿参与", "不影响实验完成", "上传前请脱敏个人信息", "可以随时撤回贡献"]) {
    assert.ok(intro.includes(promise), promise);
  }
  assert.match(intro, /开始共建实验/);
});

test("the contribution surface is only mounted in co-build mode", () => {
  assert.match(panel, /const collectionMode = useCollectionMode\(\)/);
  assert.match(panel, /if \(!collection\.enabled \|\| !collectionMode\) return null;/);
  // uploads only ever happen from the co-build entry, and they say so to the API
  const api = read("../src/lib/api.ts");
  assert.match(api, /form\.append\("collection_mode", "true"\)/);
});

test("the ordinary entry cannot create a session", () => {
  // no upload UI outside the panel, and commit needs a session from an upload
  assert.match(hook, /if \(!enabled \|\| !consent \|\| !file \|\| sessionId\) return;/);
  assert.match(hook, /if \(!enabled \|\| !consent \|\| !sessionId\) return;/);
  for (const source of [home, list, detail]) {
    assert.ok(!source.includes("createDataCollectionSession"), "ordinary pages must not upload");
  }
});

test("the thank-you dialog appears after a committed contribution", () => {
  assert.match(hook, /setShowThanks\(true\)/);
  assert.match(thanks, /collection\.showThanks/);
  assert.match(thanks, /感谢参与 PhysLab AI 实验共建！/);
  for (const item of ["实验数据识别", "OCR 模型训练", "实验助手能力"]) {
    assert.ok(thanks.includes(item), item);
  }
  assert.match(thanks, /本次贡献/);
  assert.match(thanks, /个 OCR 数据样本/);
  assert.match(thanks, /继续使用 PhysLab/);
});

test("the dialog shows no session id, path or internal detail", () => {
  assert.ok(!thanks.includes("sessionId"), "no session id may be rendered");
  assert.ok(!/sessions\//.test(thanks) && !thanks.includes("session_id"), "no storage path or id");
  assert.ok(!/UUID|uuid/.test(thanks), "no internal identifier wording");
});

test("the dialog can withdraw the contribution", () => {
  assert.match(thanks, /撤回本次贡献/);
  assert.match(thanks, /collection\.withdraw\(\)/);
  assert.match(hook, /deleteDataCollectionSession\(sessionId\)/);
});

test("pages that read the mode keep a Suspense boundary for static export", () => {
  for (const [name, source] of [["detail", detailPage], ["workspace", workspacePage]] as const) {
    assert.match(source, /Suspense/, name);
  }
  assert.match(list, /Suspense/);
});
