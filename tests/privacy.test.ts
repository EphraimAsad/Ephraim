import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
test("web search is explicitly optional and only submits the question",()=>{
 const main=readFileSync("src/main/index.ts","utf8");
 assert.match(main,/if\(web\)/);
 assert.match(main,/tavilySearch\(question,key\)/);
 assert.doesNotMatch(main,/tavilySearch\(context/);
});
test("renderer has isolated and sandboxed privileges",()=>{
 const main=readFileSync("src/main/index.ts","utf8");
 assert.match(main,/nodeIntegration:false/);
 assert.match(main,/contextIsolation:true/);
 assert.match(main,/sandbox:true/);
 assert.match(main,/setWindowOpenHandler/);
});
test("model activation requires successful load",()=>{
 const store=readFileSync("src/main/store.ts","utf8");
 assert.match(store,/tested=1/);
 assert.match(store,/Model must pass a local load test/);
});
test("admin-only model import and key updates",()=>{
 const main=readFileSync("src/main/index.ts","utf8");
 assert.match(main,/bind\("models:import"[\s\S]*?requireAdmin\(\)/);
 assert.match(main,/bind\("settings:searchKey"[\s\S]*?requireAdmin\(\)/);
});
test("never commit model and secret files",()=>{
 const ignore=readFileSync(".gitignore","utf8");
 for(const pattern of ["*.gguf",".env","*.db","*.pem"])assert.ok(ignore.includes(pattern));
});
