import test from "node:test";
import assert from "node:assert/strict";
import {fitConversationToPrompt,prefixWithinTokens} from "../src/core/conversation";

const count=(text:string)=>text.length;
const render=(history:string)=>"Instructions\nHistory:\n"+history+"\nQuestion: next";
test("all conversation messages are retained when the selected context fits",()=>{
  const messages=[{role:"user" as const,text:"first"},{role:"assistant" as const,text:"answer"},{role:"user" as const,text:"followup"}];
  const prompt=fitConversationToPrompt(messages,count,1000,render);
  assert.ok(prompt.includes("User: first"));
  assert.ok(prompt.includes("Assistant: answer"));
  assert.ok(prompt.includes("User: followup"));
});
test("small context keeps newest exchanges within its budget",()=>{
  const messages=Array.from({length:150},(_,i)=>({role:i%2?"assistant" as const:"user" as const,text:"message-"+i}));
  const prompt=fitConversationToPrompt(messages,count,120,render);
  assert.ok(prompt.includes("message-149"));
  assert.ok(!prompt.includes("message-0\n"));
  assert.ok(count(prompt)<=120);
});
test("newest oversized message is partially preserved",()=>{
  const prompt=fitConversationToPrompt([{role:"assistant",text:"x".repeat(1000)+"important-tail"}],count,90,render);
  assert.ok(prompt.includes("important-tail"));
  assert.ok(prompt.includes("earlier content omitted"));
  assert.ok(count(prompt)<=90);
});
test("evidence prefix fits and fixed instructions never overflow",()=>{
  assert.equal(prefixWithinTokens("abcdefghij",count,4),"abcd");
  assert.throws(()=>fitConversationToPrompt([],count,5,render),/exceeds/);
});
