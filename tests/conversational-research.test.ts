import test from "node:test";
import assert from "node:assert/strict";
import {planResearch,buildWebQueries,publicTerms} from "../src/core/orchestrator";
import {selectPassages,composeEvidence,validateCitationLabels} from "../src/core/evidence";
import {KnowledgeStore} from "../src/main/store";

test("combined local and public research is selected for a generic procedure comparison",()=>{
  const query="How does DOC-001 for L. mono compare against other published approaches?";
  const plan=planResearch(query,[],{webEnabled:true,hasLocalDocuments:true,namedReference:"DOC-001",localReferences:["DOC-001"]});
  assert.equal(plan.mode,"combined");
  assert.equal(plan.needLocal,true);
  assert.equal(plan.needWeb,true);
  assert.ok(plan.webQueries.length>0);
  assert.ok(plan.webQueries.every(q=>!q.includes("DOC-001")));
  assert.ok(plan.webQueries.some(q=>q.includes("Listeria monocytogenes")));
});
test("follow-up public questions use prior user context but never indexed document text",()=>{
  const previous=[{role:"user" as const,text:"What published methods are available for detecting a synthetic organism in water?"},{role:"assistant" as const,text:"Private lab protocol details must never go to the public provider."}];
  const queries=buildWebQueries("What about the latest approaches?",previous,["DOC-001"]);
  assert.ok(queries[0].includes("synthetic organism"));
  assert.ok(!queries.join(" ").includes("Private lab protocol"));
  assert.equal(publicTerms("Compare internal DOC-001 versus a published standard",["DOC-001"]).includes("DOC-001"),false);
});
test("small-talk and no-web plans don't trigger external calls",()=>{
  const plan=planResearch("Thanks!",[],{webEnabled:true,hasLocalDocuments:true});
  assert.equal(plan.mode,"chat");
  assert.equal(plan.needWeb,false);
  const offline=planResearch("Compare our procedure with alternatives",[],{webEnabled:false,hasLocalDocuments:true});
  assert.equal(offline.needWeb,false);
});
test("multi-query local retrieval deduplicates and preserves distinct evidence",()=>{
  const documents=[
    {id:1,documentId:1,reference:"DOC-001",version:2,page:1,section:null,excerpt:"A synthetic incubation method uses controlled conditions"},
    {id:2,documentId:1,reference:"DOC-001",version:2,page:2,section:null,excerpt:"The test requires a confirmation step"}
  ];
  const chosen=selectPassages([...documents,...documents],"confirmation incubation",8);
  assert.equal(chosen.length,2);
  assert.match(composeEvidence(chosen,[{title:"Example public method",url:"https://example.org/",snippet:"Public method",publishedDate:null}]),/\[D1\][\s\S]*\[W1\]/);
});
test("fabricated citation labels are flagged without treating labels as proof",()=>{
  const result=validateCitationLabels("Supported [D1] public [W1] invented [D9].",1,1);
  assert.equal(result.answer.includes("[D9]"),false);
  assert.deepEqual(result.invalid,["[D9]"]);
});
test("rolling memory checkpoints remain account-scoped and disappear with their conversation",()=>{
  const db=new KnowledgeStore(":memory:");
  const a=db.createAccount("research_a","strong-password-901","admin");
  const b=db.createAccount("research_b","strong-password-902","user");
  const id=db.createConversation(a.id,"Current work");
  db.addMessage(a.id,id,"user","Earlier context");
  const message=db.getMessages(a.id,id)[0];
  db.saveConversationMemory(a.id,id,Number(message.id),"Synthetic summary");
  assert.equal(db.getConversationMemory(a.id,id)?.summary,"Synthetic summary");
  assert.throws(()=>db.getConversationMemory(b.id,id),/not found/);
  assert.throws(()=>db.saveConversationMemory(b.id,id,Number(message.id),"Stolen"),/not found/);
  db.deleteConversation(a.id,id);
  assert.throws(()=>db.getConversationMemory(a.id,id),/not found/);
  db.close();
});
test("public documentation and desktop placeholders contain no procedure identifiers",async()=>{
  const {readFileSync}=await import("node:fs");
  for(const path of ["README.md","src/renderer/src/main.tsx"]){
    const content=readFileSync(path,"utf8");
    assert.doesNotMatch(content,/\bTP\s*[- ]?\d+/i);
  }
});
