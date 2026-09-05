/**
 * Regenerate src/api/generated/schema.d.ts from the Python API.
 *
 *   npm run generate:api-types     rewrite the committed file
 *   npm run verify:api-types       fail if the committed file is stale
 *
 * Python is the source of truth. This script never writes types of its own:
 * it asks `AniRec.api.openapi_export` for the OpenAPI document that FastAPI
 * builds from the Pydantic models in AniRec/api/models.py, then hands it to
 * openapi-typescript. Nothing in the generated file is hand-maintained, which
 * is the whole point - the previous hand-mirrored types.ts could drift from
 * the Python models silently, and a renamed field would have surfaced as
 * `undefined` at runtime rather than as a type error at build time.
 *
 * The verify mode exists so CI can answer "did someone change a Pydantic
 * model without regenerating?" without needing to commit a second copy of
 * the schema for comparison.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HERE, "..");
const REPO_ROOT = resolve(FRONTEND, "..");
const OUTPUT = join(FRONTEND, "src", "api", "generated", "schema.d.ts");
const SCRATCH = join(FRONTEND, "node_modules", ".cache", "anirec-openapi");

const verifyOnly = process.argv.includes("--verify");

/** The repo's virtualenv first; a PATH python only as a fallback. */
function resolvePython() {
  const candidates = [
    join(REPO_ROOT, ".venv", "Scripts", "python.exe"),
    join(REPO_ROOT, ".venv", "bin", "python"),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return process.platform === "win32" ? "python" : "python3";
}

function generate() {
  const python = resolvePython();
  const schema = execFileSync(python, ["-m", "AniRec.api.openapi_export"], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    // The export builds the app against a temp directory, but keep the
    // process from picking up a developer's token/origin overrides too.
    env: { ...process.env, ANIREC_API_TOKEN: "", ANIREC_ALLOWED_ORIGIN: "" },
  });

  mkdirSync(SCRATCH, { recursive: true });
  const schemaPath = join(SCRATCH, "openapi.json");
  writeFileSync(schemaPath, schema, "utf8");

  // The CLI's JS entry point run under this same Node, rather than the
  // `npx` shim: spawning a .cmd directly fails with EINVAL on current Node
  // for Windows, and going through a shell to work around that would mean
  // quoting paths correctly on two platforms for no benefit.
  const generatedPath = join(SCRATCH, "schema.d.ts");
  const cli = join(FRONTEND, "node_modules", "openapi-typescript", "bin", "cli.js");
  execFileSync(process.execPath, [cli, schemaPath, "-o", generatedPath], {
    cwd: FRONTEND,
    stdio: ["ignore", "ignore", "inherit"],
  });

  const banner = [
    "/**",
    " * GENERATED FILE - DO NOT EDIT.",
    " *",
    " * Source of truth: AniRec/api/models.py, via FastAPI's OpenAPI document.",
    " * Regenerate with:  npm run generate:api-types",
    " * Verify in CI with: npm run verify:api-types",
    " */",
    "",
  ].join("\n");

  return banner + readFileSync(generatedPath, "utf8");
}

const next = generate();

if (verifyOnly) {
  const current = existsSync(OUTPUT) ? readFileSync(OUTPUT, "utf8") : "";
  if (current !== next) {
    console.error(
      "API types are out of date with the Python models.\n" +
        "Run: npm run generate:api-types",
    );
    process.exit(1);
  }
  console.log("API types are in sync with AniRec/api/models.py");
} else {
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, next, "utf8");
  console.log(`wrote ${OUTPUT.replace(REPO_ROOT, ".")}`);
}

rmSync(SCRATCH, { recursive: true, force: true });
