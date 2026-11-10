import { app, BrowserWindow, dialog, ipcMain, safeStorage, shell, session } from "electron";
import { join, basename } from "node:path";
import { mkdirSync, existsSync } from "node:fs";
import { KnowledgeStore, type Person, type SourceChunk } from "./store";
import { importGGUF, generate, testChat, testEmbedding, getEmbedding } from "./runtime";
import { extractPages } from "./documents";
import { tavilySearch } from "./search";
import { formatWebResults, safeWebUrl, type WebResult } from "../core/research";
import { hierarchicalSummary, isSummaryRequest } from "../core/knowledge";

let db:KnowledgeStore;
let active:Person|null=null;
let window:BrowserWindow|null=null;
let failedLogins=0;
let lastFailed=0;
let chatBusy=false;
let runningChat:{requestId:string;ownerId:number;conversationId:number;controller:AbortController}|null=null;
const validId=(n:unknown):n is number=>Number.isSafeInteger(n)&&Number(n)>0;
const validText=(n:unknown,max:number):n is string=>typeof n==="string"&&n.trim().length>0&&n.length<=max;
function requireAuth():Person{if(!active)throw new Error("Sign in required");return active;}
function requireAdmin():Person{const u=requireAuth();if(u.role!=="admin")throw new Error("Administrator role required");return u;}
function handler(name:string,fn:(...args:any[])=>unknown) {
  ipcMain.handle(name,async(event,...args)=>{
    if(!window || event.sender.id!==window.webContents.id)return {ok:false,error:"Invalid application window"};
    try{return {ok:true,data:await fn(...args)};}
    catch(e) {const msg=e instanceof Error?e.message:"Request failed";return {ok:false,error:msg.slice(0,220)};}
  });
}
async function searchEncryptionAvailable():Promise<boolean>{
  if(process.platform==="linux" && safeStorage.getSelectedStorageBackend()==="basic_text")return false;
  return safeStorage.isAsyncEncryptionAvailable();
}
async function getKey():Promise<string|null> {
  if(!await searchEncryptionAvailable())return null;
  const value=db.getSetting("tavily_encrypted");
  if(!value)return null;
  try {
    const result=await safeStorage.decryptStringAsync(Buffer.from(value,"base64"));
    if(result.shouldReEncrypt) {
      const updated=await safeStorage.encryptStringAsync(result.result);
      db.setSetting("tavily_encrypted",updated.toString("base64"));
    }
    return result.result;
  }catch{return null;}
}
async function importDoc(reference:string,visibility:"private"|"shared") {
  const u=requireAdmin();
  if(!validText(reference,100)||!["private","shared"].includes(visibility))throw new Error("Invalid document details");
  const selected=await dialog.showOpenDialog(window!,{properties:["openFile","multiSelections"],filters:[{name:"Documents",extensions:["txt","md","csv","pdf","docx","xlsx"]}]});
  if(selected.canceled)return [];
  const ids:number[]=[];
  for(const path of selected.filePaths) {
    const pages=await extractPages(path);
    ids.push(db.addDocument(u.id,basename(path),reference,visibility,pages,path));
  }
  return ids;
}
function sourceLabel(c:SourceChunk,index:number) {
  return "[D"+(index+1)+"] "+c.reference+" v"+c.version+(c.page?" p."+c.page:"")+(c.section?" §"+c.section:"");
}
function bindIPC(){
  handler("auth:state",()=>({needsSetup:db.setupNeeded(),user:active}));
  handler("auth:setup",(name:string,pwd:string)=>{
    if(!db.setupNeeded())throw new Error("Setup already complete");
    active=db.createAccount(name,pwd,"admin");
    return active;
  });
  handler("auth:login",(name:string,pwd:string)=>{
    if(!validText(name,40)||!validText(pwd,256))throw new Error("Invalid username or password");
    if(failedLogins>=5&&Date.now()-lastFailed<30_000)throw new Error("Too many attempts; try again shortly");
    const person=db.authenticate(name,pwd);
    if(!person){failedLogins++;lastFailed=Date.now();throw new Error("Invalid username or password");}
    failedLogins=0;active=person;return person;
  });
  handler("auth:logout",()=>{active=null;return true;});
  handler("users:create",(username:string,password:string,role:"user"|"admin")=>{
    requireAdmin();if(role!=="user"&&role!=="admin")throw new Error("Invalid role");
    return db.createAccount(username,password,role);
  });
  handler("models:list",()=>{requireAuth();return db.listModels();});
  handler("models:import",async(name:string,kind:"chat"|"embedding")=>{
    requireAdmin();
    if(!validText(name,80)||!["chat","embedding"].includes(kind))throw new Error("Invalid model details");
    const files=await dialog.showOpenDialog(window!,{filters:[{name:"GGUF",extensions:["gguf"]}],properties:["openFile"]});
    if(files.canceled)return null;
    const path=importGGUF(files.filePaths[0],join(app.getPath("userData"),"models"));
    db.addModel(name,path,kind);
    return db.listModels();
  });
  handler("models:test",async(id:number)=>{
    requireAdmin();if(!validId(id))throw new Error("Invalid model");
    const model=db.modelForTest(id);
    if(model.kind==="embedding")await testEmbedding(model.path);
    else await testChat(model.path);
    db.markModelTested(id);
    return db.listModels();
  });
  handler("models:enable",(id:number,enabled:boolean)=>{
    requireAdmin();if(!validId(id)||typeof enabled!=="boolean")throw new Error("Invalid model settings");
    db.enableModel(id,enabled);return db.listModels();
  });
  handler("docs:list",()=>db.listDocuments(requireAuth().id));
  handler("docs:import",async(reference:string,visibility:"private"|"shared")=>importDoc(reference,visibility));
  handler("docs:chunks",(id:number)=>{
    const u=requireAuth();if(!validId(id))throw new Error("Invalid document");
    return db.documentChunks(u.id,id,true).map(c=>({ordinal:c.ordinal,page:c.page,section:c.section,text:c.excerpt}));
  });
  handler("docs:open",async(id:number)=>{
    const u=requireAuth();if(!validId(id))throw new Error("Invalid document");
    const path=db.sourcePath(u.id,id);if(!path||!existsSync(path))throw new Error("Source file is no longer available at its imported location");
    const err=await shell.openPath(path);
    if(err)throw new Error("Could not open source document");
    return true;
  });
  handler("docs:reindex",async()=>{
    requireAdmin();
    const model=db.enabledEmbedding();
    if(!model)throw new Error("Enable a tested embedding GGUF first");
    const queue=db.chunkEmbeddingsToIndex(model.id);
    let count=0;
    for(const item of queue){
      const vector=await getEmbedding(model.path,item.text);
      db.saveEmbedding(item.id,model.id,vector);count++;
    }
    return {indexed:count};
  });
  handler("conversations:list",()=>db.listConversations(requireAuth().id));
  handler("conversations:create",(title:string)=>{
    const u=requireAuth();
    return db.createConversation(u.id,validText(title,120)?title:"New conversation");
  });
  handler("conversations:messages",(id:number)=>{
    const u=requireAuth();return db.getMessages(u.id,id);
  });
  handler("conversations:rename",(id:number,title:string)=>{
    const u=requireAuth();if(!validId(id)||!validText(title,120))throw new Error("Invalid conversation title");
    db.renameConversation(u.id,id,title);return true;
  });
  handler("conversations:delete",(id:number)=>{
    const u=requireAuth();if(!validId(id))throw new Error("Invalid conversation");
    if(runningChat?.conversationId===id&&runningChat.ownerId===u.id)throw new Error("Finish or cancel generation first");
    db.deleteConversation(u.id,id);return true;
  });
  handler("settings:preferences",()=>{
    const u=requireAuth();return {theme:db.getUserPreference(u.id,"theme")??"dark",maxTokens:Number(db.getUserPreference(u.id,"maxTokens")??"900")};
  });
  handler("settings:preferences:update",(theme:string,maxTokens:number)=>{
    const u=requireAuth();
    if(!["dark","light","system"].includes(theme)||![256,512,900,1500,2048].includes(maxTokens))throw new Error("Unsupported preference");
    db.setUserPreference(u.id,"theme",theme);
    db.setUserPreference(u.id,"maxTokens",String(maxTokens));
    return true;
  });
  handler("web:open",async(raw:string)=>{
    requireAuth();const url=safeWebUrl(raw);
    if(!url)throw new Error("Unsafe external link");
    await shell.openExternal(url);return true;
  });
  handler("chat:cancel",(requestId:string)=>{
    const u=requireAuth();
    if(runningChat?.requestId!==requestId||runningChat.ownerId!==u.id)return false;
    runningChat.controller.abort();return true;
  });
  handler("chat:ask",async(question:string,modelId:number,conversationId:number,useWeb:boolean,requestId:string)=>{
    if(typeof requestId!=="string"||!/^[0-9a-f]{8}-[0-9a-f-]{20,50}$/i.test(requestId))throw new Error("Invalid request identifier");
    const u=requireAuth();
    if(!validText(question,4000)||!validId(modelId)||!validId(conversationId)||typeof useWeb!=="boolean")throw new Error("Invalid chat request");
    // Before model or search activity, confirm caller owns the conversation.
    const previous=db.getMessages(u.id,conversationId).slice(-8).map(m=>({role:m.role as "user"|"assistant",text:String(m.text)}));
    if(chatBusy)throw new Error("A response is already being generated");
    chatBusy=true;
    const controller=new AbortController();
    runningChat={requestId,ownerId:u.id,conversationId,controller};
    const stream=(chunk:string)=>{
      if(!controller.signal.aborted && active?.id===u.id && window&&!window.isDestroyed())window.webContents.send("chat:chunk",{requestId,conversationId,chunk});
    };
    const options={maxTokens:Number(db.getUserPreference(u.id,"maxTokens")??"900"),onChunk:stream,signal:controller.signal};
    try {
      const modelPath=db.modelForUse(modelId,"chat");
      const named=db.findDocument(u.id,question);
      const summarizeNamed=!!named&&isSummaryRequest(question);
      let sources:SourceChunk[]=[];
      let response="";
      let webResults:WebResult[]=[];
      if(summarizeNamed) {
        sources=db.documentChunks(u.id,named!.id);
        response=await hierarchicalSummary(sources.map((c,i)=>sourceLabel(c,i)+"\n"+c.excerpt),async(text,instruction)=>{
          return generate(modelPath,instruction,text,[],instruction.includes("Summarise the complete document")?options:{maxTokens:options.maxTokens,signal:controller.signal});
        },6500);
      } else {
        let queryEmbedding:undefined|{modelId:number;vector:number[]};
        const embeddingModel=db.enabledEmbedding();
        if(embeddingModel){
          try{queryEmbedding={modelId:embeddingModel.id,vector:await getEmbedding(embeddingModel.path,question)};}
          catch {queryEmbedding=undefined;}
        }
        sources=db.retrieve(u.id,question,queryEmbedding);
        const privateSource=sources.map((s,i)=>sourceLabel(s,i)+"\n"+s.excerpt).join("\n\n");
        let webText="";
        if(useWeb) {
          const key=await getKey();
          if(!key)throw new Error("Web search is not configured");
          // Main-process consent cannot be bypassed by a renderer IPC call.
          const consent=await dialog.showMessageBox(window!,{
            type:"warning",title:"External internet search",
            message:"Send this exact question to Tavily?",
            detail:question,
            buttons:["Send question","Cancel"],defaultId:1,cancelId:1,noLink:true
          });
          if(consent.response!==0)throw new Error("External search cancelled");
          // Only the literal user question is sent to Tavily, NEVER retrieved private source material.
          webResults=await tavilySearch(question,key);
          webText=formatWebResults(webResults);
        }
        response=await generate(modelPath,question,privateSource+"\n\n"+webText,previous,options);
      }
      // Store only after success, and only against the currently authenticated owner.
      if(!active||active.id!==u.id||controller.signal.aborted)throw new Error("Generation cancelled or session changed");
      db.addMessage(u.id,conversationId,"user",question);
      db.addMessage(u.id,conversationId,"assistant",response);
      return {answer:response,citations:sources.map((s,i)=>({
        label:"D"+(i+1),documentId:s.documentId,chunkId:s.id,title:s.title,
        reference:s.reference,version:s.version,page:s.page,section:s.section,excerpt:s.excerpt.slice(0,450)
      })),webResults,searchedWeb:useWeb};
    }finally{chatBusy=false;runningChat=null;}
  });
  handler("settings:status",async()=>{requireAuth();return {hasWebKey:!!(await getKey()),secureStorage:await searchEncryptionAvailable()};});
  handler("settings:searchKey",async(key:string)=>{
    requireAdmin();
    if(typeof key!=="string"||key.length>512)throw new Error("Invalid key");
    if(!key){db.setSetting("tavily_encrypted",null);return true;}
    if(!await searchEncryptionAvailable())throw new Error("Encrypted OS credential storage unavailable");
    const encrypted=await safeStorage.encryptStringAsync(key.trim());
    db.setSetting("tavily_encrypted",encrypted.toString("base64"));
    return true;
  });
}
app.whenReady().then(async()=>{
  if(process.argv.includes("--ephraim-self-test")) {
    try {
      const localGGUF=process.env.EPHRAIM_TEST_GGUF;
      if(!localGGUF)throw new Error("Test model unavailable");
      await testChat(localGGUF);
      console.log("Ephraim packaged local GGUF inference OK");
      app.exit(0);
    }catch{
      console.error("Ephraim packaged local GGUF inference FAILED");
      app.exit(1);
    }
    return;
  }
  mkdirSync(app.getPath("userData"),{recursive:true,mode:0o700});
  db=new KnowledgeStore(join(app.getPath("userData"),"ephraim.sqlite"));
  // Existing keys from v0.1 remain encrypted in the previous 'tavily' setting.
  // Do not transmit, re-encrypt, or log anything without explicit admin action.
  bindIPC();
  window=new BrowserWindow({
    width:1260,height:850,minWidth:920,minHeight:650,show:false,
    webPreferences:{preload:join(__dirname,"../preload/index.js"),sandbox:true,contextIsolation:true,nodeIntegration:false,webSecurity:true}
  });
  window.setMenuBarVisibility(false);
  window.webContents.setWindowOpenHandler(()=>({action:"deny"}));
  window.webContents.on("will-navigate",event=>event.preventDefault());
  window.webContents.session.setPermissionRequestHandler((_wc,_p,callback)=>callback(false));
  window.once("ready-to-show",()=>window?.show());
  if(!app.isPackaged&&process.env.ELECTRON_RENDERER_URL)void window.loadURL(process.env.ELECTRON_RENDERER_URL);
  else void window.loadFile(join(__dirname,"../renderer/index.html"));
});
app.on("window-all-closed",()=>app.quit());
