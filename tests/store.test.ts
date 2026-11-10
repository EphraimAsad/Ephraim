import test from "node:test";
import assert from "node:assert/strict";
import { KnowledgeStore } from "../src/main/store";
function setup(){
 const store=new KnowledgeStore(":memory:");
 const admin=store.createAccount("admin_user","secure-password-0001","admin");
 const alice=store.createAccount("alice_user","secure-password-0002","user");
 const bob=store.createAccount("bobby_user","secure-password-0003","user");
 return {store,admin,alice,bob};
}
test("users cannot access another user's private conversation or messages",()=>{
 const {store,alice,bob}=setup();
 const id=store.createConversation(alice.id,"Private conversation");
 store.addMessage(alice.id,id,"user","private medical context");
 assert.equal(store.listConversations(bob.id).length,0);
 assert.throws(()=>store.getMessages(bob.id,id),/not found/);
 assert.throws(()=>store.addMessage(bob.id,id,"assistant","spoof"),/not found/);
 assert.equal(store.getMessages(alice.id,id).length,1);
 store.close();
});
test("private document and chunks are not exposed to other accounts; shared approved documents are",()=>{
 const {store,admin,alice,bob}=setup();
 const privateId=store.addDocument(admin.id,"Private notes.txt","PRIV 100","private",[{page:1,text:"Lab secret dilution 919123"}],null);
 const sharedId=store.addDocument(admin.id,"Shared.txt","DOC-001","shared",[{page:3,text:"Incubation at 37C for 42 hours"}],null);
 assert.equal(store.listDocuments(alice.id).some(d=>d.id===privateId),false);
 assert.equal(store.listDocuments(alice.id).some(d=>d.id===sharedId),true);
 assert.throws(()=>store.documentChunks(bob.id,privateId),/not available/);
 assert.equal(store.retrieve(bob.id,"secret dilution 919123").length,0);
 assert.equal(store.findDocument(alice.id,"Summarise DOC-001")?.id,sharedId);
 assert.ok(store.retrieve(bob.id,"incubation hours").some(c=>c.documentId===sharedId));
 store.close();
});
test("document versioning supersedes old revisions; newer version is used",()=>{
 const {store,admin,bob}=setup();
 const old=store.addDocument(admin.id,"SOP.txt","DOC-001","shared",[{page:1,text:"Old reagent code ABCD"}],null);
 const current=store.addDocument(admin.id,"SOP.txt","DOC-001","shared",[{page:2,text:"New reagent code EFGH"}],null);
 assert.equal(store.findDocument(bob.id,"Summarise DOC-001")?.id,current);
 assert.equal(store.documentChunks(admin.id,current)[0].page,2);
 assert.equal(store.canReadDocument(bob.id,old),false);
 assert.equal(store.canReadDocument(bob.id,old,true),true);
 assert.throws(()=>store.documentChunks(bob.id,old),/not available/);
 assert.equal(store.documentChunks(bob.id,old,true).length,1);
 assert.ok(store.retrieve(bob.id,"reagent ABCD").every(c=>c.documentId!==old));
 store.close();
});
test("model approval requires successful test and embedding uniqueness",()=>{
 const {store}=setup();
 const chat=store.addModel("Test","/tmp/fake-chat.gguf","chat");
 const a=store.addModel("Embed A","/tmp/embed-a.gguf","embedding");
 const b=store.addModel("Embed B","/tmp/embed-b.gguf","embedding");
 assert.throws(()=>store.enableModel(chat,true),/test/);
 store.markModelTested(chat);store.enableModel(chat,true);
 store.markModelTested(a);store.markModelTested(b);
 store.enableModel(a,true);store.enableModel(b,true);
 assert.equal(store.enabledEmbedding()?.id,b);
 assert.equal(store.listModels().filter(m=>m.kind==="embedding"&&m.enabled).length,1);
 store.close();
});

test("conversation rename and deletion are strictly account scoped",()=>{
 const {store,alice,bob}=setup();
 const a=store.createConversation(alice.id,"Alpha");
 store.addMessage(alice.id,a,"user","synthetic request");
 assert.throws(()=>store.renameConversation(bob.id,a,"Stolen"),/not found/);
 assert.throws(()=>store.deleteConversation(bob.id,a),/not found/);
 store.renameConversation(alice.id,a,"Renamed");
 assert.equal(store.listConversations(alice.id)[0].title,"Renamed");
 store.deleteConversation(alice.id,a);
 assert.equal(store.listConversations(alice.id).length,0);
 assert.throws(()=>store.getMessages(alice.id,a),/not found/);
 store.close();
});
test("appearance and generation settings are per-user and validated",()=>{
 const {store,alice,bob}=setup();
 store.setUserPreference(alice.id,"theme","light");
 store.setUserPreference(alice.id,"maxTokens","512");
 assert.equal(store.getUserPreference(alice.id,"theme"),"light");
 assert.equal(store.getUserPreference(bob.id,"theme"),null);
 assert.equal(store.getUserPreference(bob.id,"maxTokens"),null);
 assert.throws(()=>store.setUserPreference(alice.id,"theme","random"),/theme/);
 assert.throws(()=>store.setUserPreference(alice.id,"maxTokens","unbounded"),/tokens/);
 store.close();
});
