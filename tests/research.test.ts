import test from "node:test";
import assert from "node:assert/strict";
import {safeWebUrl,normalizeWebResults,formatWebResults} from "../src/core/research";
import {readFileSync} from "node:fs";
test("web result links require safe HTTPS URLs",()=>{
 assert.equal(safeWebUrl("javascript:alert(1)"),null);
 assert.equal(safeWebUrl("file:///tmp/private.txt"),null);
 assert.equal(safeWebUrl("http://example.org/a"),null);
 assert.equal(safeWebUrl("https://127.0.0.1/"),null);
 assert.equal(safeWebUrl("https://user:password@example.org"),null);
 assert.equal(safeWebUrl("https://example.org/a"),"https://example.org/a");
});
test("Tavily response is normalized, deduplicated and bounded",()=>{
 const output=normalizeWebResults({results:[
  {title:"Public article",url:"https://example.org/sop",content:"A".repeat(3000),published_date:"2026-01-13"},
  {title:"duplicate",url:"https://example.org/sop",content:"duplicate"},
  {title:"unsafe",url:"javascript:alert(1)",content:"unsafe"},
  {title:"Another",url:"https://example.org/another",content:"Public excerpt"}
 ]});
 assert.equal(output.length,2);
 assert.equal(output[0].snippet.length,1300);
 assert.equal(output[0].publishedDate,"2026-01-13");
 assert.match(formatWebResults(output),/\[W1\]/);
 assert.doesNotMatch(formatWebResults(output),/javascript:/);
});
test("streaming is request scoped and external research still requires native consent",()=>{
 const main=readFileSync("src/main/index.ts","utf8");
 const preload=readFileSync("src/preload/index.ts","utf8");
 assert.match(main,/active\?\.id===u\.id/);
 assert.match(main,/requestId,conversationId,chunk/);
 assert.match(main,/dialog\.showMessageBox/);
 assert.ok(main.indexOf("consent.response!==0")<main.indexOf("tavilySearch(query,key)"));
 assert.match(preload,/removeListener\("chat:chunk"/);
});
