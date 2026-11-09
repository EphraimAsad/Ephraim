import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
test("renderer is sandboxed and navigation disabled",()=>{
 const s=readFileSync("src/main/index.ts","utf8");
 for(const field of ["contextIsolation:true","sandbox:true","nodeIntegration:false","setWindowOpenHandler","will-navigate","requireAdmin()"])assert.ok(s.includes(field),field);
});
test("web sends literal question only, never retrieved context",()=>{
 const s=readFileSync("src/main/index.ts","utf8");
 assert.match(s,/tavilySearch\(question,key\)/);
 assert.doesNotMatch(s,/tavilySearch\(privateSource/);
});
test("messages are tied to owner conversation",()=>{
 const s=readFileSync("src/main/index.ts","utf8");
 assert.match(s,/db\.getMessages\(u\.id,conversationId\)/);
 assert.match(s,/db\.addMessage\(u\.id,conversationId/);
});
