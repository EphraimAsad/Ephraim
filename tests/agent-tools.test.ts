import test from "node:test";
import assert from "node:assert/strict";
import {ToolGate,MAX_TOOL_CALLS,queryArg,documentIdArg} from "../src/main/agent-policy";
import {createAgentFunctions} from "../src/main/agent-functions";

test("tool limits and disabled external research are enforced",async()=>{
  const gate=new ToolGate(()=>{},false);
  await assert.rejects(()=>gate.run("search_public_web",async()=>true),/disabled/);
  for(let i=0;i<MAX_TOOL_CALLS;i++)assert.equal(await gate.run("list_documents",async()=>true),true);
  await assert.rejects(()=>gate.run("list_documents",async()=>true),/limit/);
});
test("tool session changes block access before and after callbacks",async()=>{
  let valid=true;
  const gate=new ToolGate(()=>{if(!valid)throw new Error("session changed")},true);
  await assert.rejects(()=>gate.run("search_documents",async()=>{valid=false;return "private"}),/session changed/);
});
test("web calls are capped to one per reply",async()=>{
  const gate=new ToolGate(()=>{},true);
  assert.equal(await gate.run("search_public_web",async()=>1),1);
  await assert.rejects(()=>gate.run("search_public_web",async()=>2),/one web lookup/);
});
test("model arguments reject invalid IDs, excessive queries, control characters",()=>{
  for(const id of [0,-1,1.1,"1",null])assert.throws(()=>documentIdArg(id),/Invalid/);
  assert.equal(documentIdArg(2),2);
  for(const q of ["","X".repeat(281),"hello\0world",1])assert.throws(()=>queryArg(q),/Invalid/);
});
test("native function schemas are exposed only for available capabilities",async()=>{
  const seen:string[]=[];
  const handlers={
    listDocuments:async()=>{seen.push("list");return [{id:1}]},
    searchDocuments:async(q:string)=>{seen.push(q);return []},
    readDocument:async(id:number)=>{seen.push(String(id));return []},
    getDocumentVersions:async(q:string)=>{seen.push(q);return []}
  };
  const noWeb=createAgentFunctions(new ToolGate(()=>{},false),handlers);
  assert.deepEqual(Object.keys(noWeb).sort(),["get_document_versions","list_documents","read_document","search_documents"]);
  assert.equal(JSON.parse(await noWeb.list_documents.handler({})).length,1);
  assert.deepEqual(seen,["list"]);
  const withWeb=createAgentFunctions(new ToolGate(()=>{},true),{...handlers,searchPublicWeb:async()=>[{title:"public"}]});
  assert.ok("search_public_web" in withWeb);
});
test("model cannot use a tool to bypass the account-owned document boundary",async()=>{
  const {KnowledgeStore}=await import("../src/main/store");
  const db=new KnowledgeStore(":memory:");
  try{
    const admin=db.createAccount("admin_tools","secure-tool-test-000","admin");
    const other=db.createAccount("other_tools","secure-tool-test-001","user");
    const id=db.addDocument(admin.id,"Private.txt","PRIV 001","private",[{page:1,text:"Confidential synthetic data 1984"}],null);
    const handlers={
      listDocuments:async()=>db.listDocuments(other.id),
      searchDocuments:async(q:string)=>db.retrieve(other.id,q),
      readDocument:async(n:number)=>db.documentChunks(other.id,n),
      getDocumentVersions:async()=>db.listDocuments(other.id)
    };
    const funcs=createAgentFunctions(new ToolGate(()=>{},false),handlers);
    const result=await funcs.read_document.handler({document_id:id});
    assert.ok(!result.includes("Confidential synthetic data"));
    assert.match(result,/unavailable|access denied|not available/i);
  }finally{db.close();}
});
