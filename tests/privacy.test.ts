import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
test("search is opt-in and only literal question is transmitted",()=>{
 const code=readFileSync("src/main/index.ts","utf8");
 assert.ok(code.includes("if(useWeb)"));
 assert.ok(code.includes("tavilySearch(question,key)"));
 assert.ok(!code.includes("tavilySearch(privateSource"));
});
test("privileged changes require administrator role",()=>{
 const code=readFileSync("src/main/index.ts","utf8");
 for(const method of ['models:import','models:test','models:enable','docs:reindex','settings:searchKey','users:create']){
   const index=code.indexOf('handler("'+method+'"');
   assert.ok(index>=0,method);
   assert.ok(code.slice(index,index+400).includes("requireAdmin()"),method);
 }
});
test("no external navigation from renderer",()=>{
 const code=readFileSync("src/main/index.ts","utf8");
 assert.ok(code.includes('setWindowOpenHandler'));
 assert.ok(code.includes('will-navigate'));
 assert.ok(code.includes('sandbox:true'));
});
