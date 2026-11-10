import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, symlinkSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validateOwnedModelPath, quarantineManagedModel } from "../src/main/model-files";
import { KnowledgeStore } from "../src/main/store";

test("only managed GGUF copies can be quarantined and removed",()=>{
  const temp=mkdtempSync(join(tmpdir(),"ephraim-model-delete-"));
  try{
    const models=join(temp,"models");mkdirSync(models);
    const file=join(models,"ab".repeat(16)+".gguf");
    const external=join(temp,"original.gguf");
    writeFileSync(file,"GGUF synthetic imported file");
    writeFileSync(external,"GGUF original untouched");
    assert.equal(validateOwnedModelPath(file,models),file);
    assert.throws(()=>validateOwnedModelPath(external,models),/managed/);
    assert.throws(()=>validateOwnedModelPath(join(models,"..","original.gguf"),models),/managed/);
    assert.throws(()=>validateOwnedModelPath(join(models,"not-a-managed-name.gguf"),models),/managed/);
    const owned=quarantineManagedModel(file,models);
    assert.equal(existsSync(file),false);
    owned.rollback();
    assert.ok(existsSync(file));
    const again=quarantineManagedModel(file,models);
    again.commit();
    assert.equal(existsSync(file),false);
    assert.ok(existsSync(external));
  }finally{rmSync(temp,{recursive:true,force:true});}
});
test("symlinks are rejected rather than followed to original files",()=>{
  const temp=mkdtempSync(join(tmpdir(),"ephraim-model-link-"));
  try{
    const models=join(temp,"models");mkdirSync(models);
    const outside=join(temp,"original.gguf");
    const fake=join(models,"cd".repeat(16)+".gguf");
    writeFileSync(outside,"private original");
    try{symlinkSync(outside,fake);}catch(e){
      if(process.platform==="win32" && ["EPERM","EACCES"].includes((e as NodeJS.ErrnoException).code??""))return;
      throw e;
    }
    assert.throws(()=>validateOwnedModelPath(fake,models),/regular managed file/);
    assert.ok(existsSync(outside));
  }finally{rmSync(temp,{recursive:true,force:true});}
});
test("removing an embedding model clears stale vectors and leaves other models intact",()=>{
  const db=new KnowledgeStore(":memory:");
  try{
    const admin=db.createAccount("admin_model","safe-password-test-123","admin");
    const id=db.addModel("Old embedding","/tmp/fake-embed.gguf","embedding");
    const keep=db.addModel("Chat","/tmp/fake-chat.gguf","chat");
    const doc=db.addDocument(admin.id,"Synthetic.txt","QA 001","private",[{page:1,text:"Synthetic laboratory procedure for testing."}],null);
    const chunk=db.documentChunks(admin.id,doc)[0].id;
    db.saveEmbedding(chunk,id,[0.2,0.4]);
    db.deleteModel(id);
    assert.throws(()=>db.modelForTest(id),/not found/);
    assert.equal(db.chunkEmbeddingsToIndex(id).some(row=>row.id===chunk),true);
    assert.equal(db.listModels().length,1);
    assert.equal(db.modelForTest(keep).kind,"chat");
  }finally{db.close();}
});
