import test from "node:test";
import assert from "node:assert/strict";
import { chunksFromPages,findNamedDocument,cosine,rerank,hierarchicalSummary,isSummaryRequest } from "../src/core/knowledge";
test("chunking preserves page metadata and overlaps",()=>{
 const chunks=chunksFromPages([{page:1,text:"A".repeat(2600)},{page:2,text:"B".repeat(850)}],1000,100);
 assert.ok(chunks.length>=4);
 assert.equal(chunks[0].page,1);
 assert.equal(chunks.at(-1)?.page,2);
 assert.ok(chunks.every(c=>c.text.length<=1000));
 assert.equal(chunks[0].text.slice(-100),chunks[1].text.slice(0,100));
});
test("named procedure matches exact reference and latest version",()=>{
 const refs=[{id:1,title:"Procedure",reference:"DOC-001",version:2},{id:2,title:"Procedure",reference:"DOC-001",version:3},{id:3,title:"Other",reference:"DOC-00",version:5}];
 assert.equal(findNamedDocument("Summarise DOC-001 in detail",refs)?.id,2);
 assert.equal(findNamedDocument("Summarise DOC-0010",refs),null);
 assert.ok(isSummaryRequest("Summarize DOC-001"));
});
test("hybrid rank prefers semantic match when available",()=>{
 const ranked=rerank([{id:1,text:"irrelevant",lexical:.2,embedding:[1,0]},{id:2,text:"other",lexical:.9,embedding:[0,1]}],[1,0],2);
 assert.equal(ranked[0].id,1);
 assert.equal(cosine([1,0],[0,1]),0);
});
test("hierarchical summary covers every section rather than early excerpts",async()=>{
 const chunks=Array.from({length:8},(_,i)=>"section "+i+" "+String(i).repeat(1100));
 const inputs:string[]=[];
 const output=await hierarchicalSummary(chunks,async(text)=>{inputs.push(text);return "S:"+text.slice(0,110);},4000);
 assert.ok(inputs.some(x=>x.includes("section 7")));
 assert.ok(output.length>0);
 assert.ok(inputs.length>1);
});
