import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { join, basename } from "node:path";
import { existsSync } from "node:fs";
import { createAccount, authenticate, setupNeeded, initStore, listModels, getModelPathForTest, getModelPath, importModel, markTested, enableModel, listDocuments, addDocument, retrieve, history, addMessage, setSearchKey, getSearchKey, hasSearchKey, type Person } from "./store";
import { extractText } from "./documents";
import { respond, testModel } from "./llm";
import { tavilySearch } from "./search";

let user:Person|null=null;
let window:BrowserWindow|null=null;
function requireAuth(){if(!user)throw new Error("Please sign in.");return user;}
function requireAdmin(){if(requireAuth().role!=="admin")throw new Error("Administrator permissions required.");}
const validText=(s:unknown,max:number):s is string=>typeof s==="string" && s.length>0 && s.length<=max;
const validId=(n:unknown):n is number=>Number.isSafeInteger(n)&&Number(n)>0;
function bind(name:string,handler:(...args:any[])=>unknown){
  ipcMain.handle(name,async(_event,...args)=>{try{return {ok:true,data:await handler(...args)};}catch(error){return {ok:false,error:error instanceof Error?error.message:"Operation failed"};}});
}
function ipc(){
  bind("auth:state",()=>({needsSetup:setupNeeded(),user}));
  bind("auth:setup",(name:string,password:string)=>{if(!setupNeeded())throw new Error("Already configured");createAccount(name,password,"admin");user=authenticate(name,password);return user;});
  bind("auth:login",(name:string,password:string)=>{if(!validText(name,40)||!validText(password,256))throw new Error("Invalid credentials");const found=authenticate(name,password);if(!found)throw new Error("Invalid credentials");user=found;return user;});
  bind("auth:logout",()=>{user=null;return true;});
  bind("users:create",(name:string,password:string,role:"admin"|"user")=>{requireAdmin();createAccount(name,password,role);return true;});
  bind("models:list",()=>{requireAuth();return listModels();});
  bind("models:import",async(name:string)=>{requireAdmin();if(!validText(name,80))throw new Error("Invalid model name");const choice=await dialog.showOpenDialog(window!,{properties:["openFile"],filters:[{name:"GGUF Models",extensions:["gguf"]}]});if(choice.canceled)return null;importModel(choice.filePaths[0],name);return listModels();});
  bind("models:test",async(id:number)=>{requireAdmin();if(!validId(id))throw new Error("Invalid model id");await testModel(getModelPathForTest(id));markTested(id);return listModels();});
  bind("models:enable",(id:number,enabled:boolean)=>{requireAdmin();if(!validId(id)||typeof enabled!=="boolean")throw new Error("Invalid request");enableModel(id,enabled);return listModels();});
  bind("docs:list",()=>{requireAuth();return listDocuments();});
  bind("docs:import",async()=>{requireAdmin();const choice=await dialog.showOpenDialog(window!,{properties:["openFile","multiSelections"],filters:[{name:"Documents",extensions:["txt","md","csv","json","pdf","docx","xlsx"]}]});if(choice.canceled)return null;for(const path of choice.filePaths){const text=await extractText(path);addDocument(basename(path),text);}return listDocuments();});
  bind("chat:history",()=>{requireAuth();return history();});
  bind("chat:ask",async(question:string,modelId:number,web:boolean)=>{requireAuth();if(!validText(question,4000)||!validId(modelId)||typeof web!=="boolean")throw new Error("Invalid question");const citations=retrieve(question);let webText="";if(web){const key=getSearchKey();if(!key)throw new Error("No search provider configured");webText=await tavilySearch(question,key);}
    const context=citations.map((c,i)=>`[DOC ${i+1}] ${c.title} v${c.version}\n${c.excerpt}`).join("\n\n")+"\n"+webText;
    const answer=await respond(getModelPath(modelId),question,context);
    addMessage("user",question);addMessage("assistant",answer);
    return {answer,citations:citations.map(c=>({id:c.id,title:c.title,version:c.version})),searchedWeb:web};
  });
  bind("settings:status",()=>{requireAuth();return {hasWebKey:hasSearchKey()};});
  bind("settings:searchKey",(key:string)=>{requireAdmin();if(typeof key!=="string"||key.length>512)throw new Error("Invalid key");setSearchKey(key);return {hasWebKey:hasSearchKey()};});
}
app.whenReady().then(()=>{
  initStore();ipc();
  window=new BrowserWindow({
    width:1250,height:850,minWidth:850,minHeight:650,show:false,
    webPreferences:{preload:join(__dirname,"../preload/index.js"),nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}
  });
  window.webContents.setWindowOpenHandler(()=>({action:"deny"}));
  window.webContents.on("will-navigate",e=>e.preventDefault());
  window.webContents.session.setPermissionRequestHandler((_webContents,_permission,callback)=>callback(false));
  window.once("ready-to-show",()=>window?.show());
  if(!app.isPackaged && process.env.ELECTRON_RENDERER_URL)window.loadURL(process.env.ELECTRON_RENDERER_URL);
  else window.loadFile(join(__dirname,"../renderer/index.html"));
});
app.on("window-all-closed",()=>{app.quit();});
