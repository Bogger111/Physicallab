import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

/**
 * The "数据特征参考" card is only as good as its numbers, so the data shipped to
 * the frontend is checked here as well: structure, handwriting precision, and
 * the fact that the card stays informational (no inputs, no calculation).
 */

const experimentsDir = fileURLToPath(
  new URL("../../backend/experiments/", import.meta.url)
);

const FOLDERS: Record<string, string> = {
  polarization: "polarization",
  "sound-light": "soundlight",
  multimeter: "multimeter",
  bridge: "bridge",
  "solar-cell": "solar_cell",
  gmr: "gmr",
  nmr: "nmr",
  viscosity: "viscosity",
  "surface-tension": "surface_tension",
  "thermal-conductivity": "thermal_conductivity",
  michelson: "michelson",
  "photoelectric-franck-hertz": "photoelectric_franck_hertz",
};

interface ReferenceEntry {
  name: string;
  field: string | null;
  example: string[];
  pattern: string[];
}

interface ReferenceDocument {
  experiment_id: string;
  note: string;
  data_reference: ReferenceEntry[];
}

function readReference(experimentId: string): ReferenceDocument {
  const path = `${experimentsDir}${FOLDERS[experimentId]}/data_reference.json`;
  return JSON.parse(readFileSync(path, "utf8")) as ReferenceDocument;
}

const readSource = (relative: string) =>
  readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

const PUBLISHED = Object.keys(FOLDERS);

test("every published experiment ships a typical-data reference", () => {
  for (const experimentId of PUBLISHED) {
    const document = readReference(experimentId);
    assert.equal(document.experiment_id, experimentId);
    assert.ok(document.note.length > 0, `${experimentId}: missing disclaimer`);
    assert.ok(
      document.data_reference.length >= 3 && document.data_reference.length <= 6,
      `${experimentId}: ${document.data_reference.length} entries`
    );
  }
});

test("reference entries are card-ready", () => {
  for (const experimentId of PUBLISHED) {
    for (const entry of readReference(experimentId).data_reference) {
      assert.ok(entry.name.trim().length > 0, experimentId);
      assert.ok(
        entry.example.length >= 3 && entry.example.length <= 6,
        `${experimentId}/${entry.name}: ${entry.example.length} examples`
      );
      assert.ok(
        entry.pattern.length >= 1 && entry.pattern.length <= 3,
        `${experimentId}/${entry.name}: ${entry.pattern.length} pattern lines`
      );
      for (const value of entry.example) {
        assert.match(value, /\d/, `${experimentId}/${entry.name}: ${value}`);
      }
      if (entry.field !== null) {
        assert.match(entry.field, /^[a-z0-9_]+\.rows\.\*\.\w+$/, entry.field);
      }
    }
  }
});

test("reference values keep handwriting precision", () => {
  for (const experimentId of PUBLISHED) {
    for (const entry of readReference(experimentId).data_reference) {
      for (const value of entry.example) {
        assert.ok(!/e-/i.test(value) && !value.includes("×10"), value);
        for (const token of value.match(/-?\d+(?:\.\d+)?/g) ?? []) {
          const decimals = token.split(".")[1]?.length ?? 0;
          assert.ok(decimals <= 4, `${experimentId}: ${value} is not handwriting precision`);
          assert.ok(token.replace(/[-.]/g, "").length <= 6, `${experimentId}: ${value} too precise`);
        }
      }
    }
  }
});

test("the card never claims to be an answer key", () => {
  for (const experimentId of PUBLISHED) {
    const document = readReference(experimentId);
    assert.ok(document.note.includes("参考"), document.note);
    for (const entry of document.data_reference) {
      for (const value of [...entry.example, ...entry.pattern]) {
        assert.ok(!value.includes("正确答案"), value);
      }
    }
    for (const line of document.data_reference.flatMap((entry) => entry.pattern)) {
      assert.ok(!/答案|填入/.test(line), line);
    }
  }
});

test("the catalogue wires every reference to its experiment", () => {
  const source = readSource("../src/lib/experiments.ts");
  for (const experimentId of PUBLISHED) {
    assert.ok(
      source.includes(`"${experimentId}":`) || source.includes(`${experimentId}:`),
      `experiments.ts does not register ${experimentId}`
    );
  }
  assert.match(source, /dataReferenceById/);
  assert.match(source, /dataReference: dataReferenceById\["sound-light"\]/);
  assert.match(source, /dataReference: dataReferenceById\.polarization/);
  assert.match(source, /dataReference: dataReferenceById\[config\.id\]/);
  assert.match(source, /dataReference: dataReferenceById\["photoelectric-franck-hertz"\]/);
});

test("the experiment page renders the card and the card is read-only", () => {
  const page = readSource("../src/app/experiments/[id]/client-page.tsx");
  assert.match(page, /import DataReferenceCard from "@\/components\/DataReferenceCard"/);
  assert.match(page, /\{experiment\.dataReference && \(\s*<DataReferenceCard dataReference=\{experiment\.dataReference\} \/>/);

  const card = readSource("../src/components/DataReferenceCard.tsx");
  assert.match(card, /数据特征参考/);
  assert.match(card, /dataReference\.data_reference/, "the card must read the reference entries");
  assert.match(card, /entry\.example\.map/, "the card must render the example values");
  assert.match(card, /entry\.pattern\.map/, "the card must render the pattern lines");
  assert.ok(!card.includes("<input"), "the card must not accept input");
  assert.ok(!/fetch\(/.test(card), "the card must not call the API");
});

test("the reference files are not shipped as training data", () => {
  const layouts = readdirSync(experimentsDir).filter((name) => !name.startsWith("."));
  const withReference = layouts.filter((folder) => {
    try {
      readFileSync(`${experimentsDir}${folder}/data_reference.json`, "utf8");
      return true;
    } catch {
      return false;
    }
  });
  assert.ok(withReference.length >= PUBLISHED.length, withReference.join(","));
});
