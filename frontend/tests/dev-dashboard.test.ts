import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

/**
 * The developer dashboard shows contribution statistics and must not be a public
 * surface: it is gated by a build-time flag, absent from the navigation, marked
 * noindex, and the endpoint underneath it needs an admin key or dev mode.
 */

const read = (relative: string) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

const dashboard = read("../src/components/dev/DataCollectionDashboard.tsx");
const page = read("../src/app/dev/data-collection/page.tsx");
const api = read("../src/lib/api.ts");

test("the dashboard is gated behind the development flag", () => {
  assert.match(dashboard, /process\.env\.NEXT_PUBLIC_PHYSICSLAB_DEV_MODE === "true"/);
  assert.match(dashboard, /开发者面板未启用/);
  assert.match(dashboard, /if \(!devMode\) return;/);
});

test("it shows sessions, confirmed sessions and sample totals", () => {
  assert.match(dashboard, /"Sessions"/);
  assert.match(dashboard, /"Confirmed"/);
  assert.match(dashboard, /"OCR Samples"/);
  assert.match(dashboard, /stats\.total_sessions/);
  assert.match(dashboard, /stats\.confirmed_sessions/);
  assert.match(dashboard, /stats\.samples_created/);
});

test("it breaks the totals down per experiment", () => {
  assert.match(dashboard, /Object\.entries\(stats\.experiments\)/);
  assert.match(dashboard, /sessions_by_experiment/);
  assert.match(dashboard, /confirmed_by_experiment/);
});

test("the page is excluded from search engines and the public navigation", () => {
  assert.match(page, /robots: \{ index: false, follow: false \}/);
  for (const navigation of ["../src/app/page.tsx", "../src/app/experiments/page.tsx"]) {
    const source = read(navigation);
    assert.ok(!source.includes("/dev/data-collection"), `${navigation} must not link the developer page`);
  }
});

test("the statistics request can carry an admin key", () => {
  assert.match(api, /api\/data-collection\/stats/);
  assert.match(api, /"X-Admin-Key": adminKey/);
  assert.match(api, /cache: "no-store"/);
  assert.match(dashboard, /window\.localStorage\.setItem\("physlab:admin-key"/);
});

test("the dashboard never reads images, only the metadata index", () => {
  assert.ok(!/\.png|\.jpg|glob\(/.test(dashboard), "the dashboard must not touch image files");
  assert.match(dashboard, /samples\.csv/);
});
