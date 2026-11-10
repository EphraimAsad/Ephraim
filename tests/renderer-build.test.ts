import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
test("packaged renderer is configured for file-relative assets",()=>{
  const config=readFileSync("electron.vite.config.ts","utf8");
  assert.match(config,/renderer:\s*\{[\s\S]*?base:\s*["']\.\/["']/);
});
test("renderer provides a visible fallback if JS cannot load",()=>{
  const html=readFileSync("src/renderer/index.html","utf8");
  assert.match(html,/id="root"/);
  assert.match(html,/application interface did not load correctly/);
});
test("rendered UI test must prove React mounted, not just HTML loaded",()=>{
  const main=readFileSync("src/main/index.ts","utf8");
  const renderer=readFileSync("src/renderer/src/main.tsx","utf8");
  assert.match(main,/diagnostic:uiReady/);
  assert.match(renderer,/diagnostic:uiReady/);
  assert.match(main,/EPHRAIM_UI_TEST_MARKER_FILE/);
});
