import test from "node:test";
import assert from "node:assert/strict";
import {KnowledgeStore} from "../src/main/store";

test("conversation retrieval does not lose the latest messages after 100 records",()=>{
  const store=new KnowledgeStore(":memory:");
  const user=store.createAccount("history_user","secure-password-9001","admin");
  const id=store.createConversation(user.id,"Long history");
  for(let i=0;i<130;i++)store.addMessage(user.id,id,i%2?"assistant":"user","turn "+i);
  const history=store.getMessages(user.id,id);
  assert.equal(history.length,130);
  assert.equal(history[0].text,"turn 0");
  assert.equal(history[129].text,"turn 129");
  store.close();
});
test("context size settings are validated and account scoped",()=>{
  const store=new KnowledgeStore(":memory:");
  const a=store.createAccount("context_a","secure-password-9001","admin");
  const b=store.createAccount("context_b","secure-password-9002","user");
  store.setUserPreference(a.id,"contextSize","32768");
  assert.equal(store.getUserPreference(a.id,"contextSize"),"32768");
  assert.equal(store.getUserPreference(b.id,"contextSize"),null);
  assert.throws(()=>store.setUserPreference(a.id,"contextSize","65536"),/context/);
  store.close();
});