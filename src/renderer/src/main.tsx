import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
type Resp<T>={ok:true;data:T}|{ok:false;error:string};
type User={id:number;username:string;role:"admin"|"user"};
type Model={id:number;name:string;enabled:boolean;tested:boolean};
type Doc={id:number;title:string;version:number;imported:string;size:number};
type Message={id:number;role:"user"|"assistant";text:string};
declare global {interface Window {ephraim:{invoke:(name:string,...args:unknown[])=>Promise<Resp<any>>}}}
async function invoke<T>(name:string,...args:unknown[]):Promise<T> {
 const r=await window.ephraim.invoke(name,...args);if(!r.ok)throw new Error(r.error);return r.data as T;
}
function App(){
 const [user,setUser]=useState<User|null>(null),[needsSetup,setNeedsSetup]=useState(false);
 const [username,setUsername]=useState(""),[password,setPassword]=useState("");
 const [error,setError]=useState(""),[busy,setBusy]=useState(false);
 const [page,setPage]=useState<"chat"|"library"|"models"|"settings">("chat");
 const [models,setModels]=useState<Model[]>([]),[docs,setDocs]=useState<Doc[]>([]);
 const [messages,setMessages]=useState<Message[]>([]),[question,setQuestion]=useState("");
 const [modelId,setModelId]=useState(0),[web,setWeb]=useState(false),[hasKey,setHasKey]=useState(false);
 const [key,setKey]=useState(""),[modelName,setModelName]=useState(""),[accountName,setAccountName]=useState(""),[accountPass,setAccountPass]=useState("");
 const [citations,setCitations]=useState<string[]>([]);
 async function refresh(){
  const [mm,dd,hh,ss]=await Promise.all([
   invoke<Model[]>("models:list"),invoke<Doc[]>("docs:list"),invoke<Message[]>("chat:history"),invoke<{hasWebKey:boolean}>("settings:status")
  ]);
  setModels(mm);setDocs(dd);setMessages(hh);setHasKey(ss.hasWebKey);
  setModelId(old=>mm.some(m=>m.id===old&&m.enabled)?old:(mm.find(m=>m.enabled)?.id||0));
 }
 useEffect(()=>{invoke<{needsSetup:boolean;user:User|null}>("auth:state").then(s=>{setUser(s.user);setNeedsSetup(s.needsSetup);}).catch(e=>setError(String(e)));},[]);
 useEffect(()=>{if(user)refresh().catch(e=>setError(String(e)));},[user]);
 async function action(f:()=>Promise<void>){setBusy(true);setError("");try{await f();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 async function signIn(){await action(async()=>{const u=await invoke<User>(needsSetup?"auth:setup":"auth:login",username,password);setUser(u);setPassword("");});}
 async function ask(){
  if(!question.trim()||!modelId)return;
  const q=question.trim();setQuestion("");
  await action(async()=>{const r=await invoke<{answer:string;citations:{title:string;version:number}[]}>("chat:ask",q,modelId,web);setMessages(await invoke<Message[]>("chat:history"));setCitations(r.citations.map(c=>c.title+" v"+c.version));});
 }
 if(!user)return <main className="login"><div className="loginCard"><div className="symbol">✦</div><h1>Ephraim</h1><p>{needsSetup?"Create the first administrator account":"Sign in to your local knowledge assistant"}</p>
 <form onSubmit={e=>{e.preventDefault();void signIn();}}><label>Username<input required minLength={3} value={username} onChange={e=>setUsername(e.target.value)}/></label>
 <label>Password<input required type="password" minLength={needsSetup?12:1} value={password} onChange={e=>setPassword(e.target.value)}/></label>
 <button disabled={busy}> {needsSetup?"Create administrator":"Sign in"}</button></form>{error&&<p className="error">{error}</p>}</div></main>;
 return <div className="shell"><aside className="sidebar"><div className="brand">✦ <b>Ephraim</b></div><p className="sub">Local intelligence, private by design</p>
 {(["chat","library","models","settings"] as const).map(p=><button className={"nav "+(page===p?"active":"")} key={p} onClick={()=>setPage(p)}>{p==="chat"?"◫":p==="library"?"▤":p==="models"?"◈":"⚙"} &nbsp; {p[0].toUpperCase()+p.slice(1)}</button>)}
 <div className="bottom"><small>{user.username} · {user.role}</small><button className="nav" onClick={()=>void action(async()=>{await invoke("auth:logout");setUser(null);setMessages([]);})}>Sign out</button></div></aside>
 <div className="body">
 <header><div><h2>{page==="chat"?"New conversation":page==="library"?"Knowledge library":page==="models"?"AI models":"Settings"}</h2><small>All local by default · No telemetry</small></div><span className="privacy">● Local mode</span></header>
 {error&&<div className="alert" role="alert">{error}</div>}
 {page==="chat"&&<><div className="toolbar"><select aria-label="Chat model" value={modelId} onChange={e=>setModelId(Number(e.target.value))}><option value={0}>Select approved model</option>{models.filter(m=>m.enabled).map(m=><option value={m.id} key={m.id}>{m.name}</option>)}</select>
 <label className="check"><input type="checkbox" checked={web} disabled={!hasKey} onChange={e=>setWeb(e.target.checked)}/> Web search {hasKey?"(question sent externally)":"(not configured)"}</label></div>
 <div className="conversation">{messages.length===0?<div className="welcome"><div className="symbol">✦</div><h1>What would you like to explore?</h1><p>Ask about your documents, or start a conversation with a local model.</p></div>:messages.map(m=><div className={"bubble "+m.role} key={m.id}><b>{m.role==="user"?"You":"Ephraim"}</b><p>{m.text}</p></div>)}
 {citations.length>0&&<small>Sources for last answer: {citations.join(" · ")}</small>}</div>
 <form className="compose" onSubmit={e=>{e.preventDefault();void ask();}}><textarea aria-label="Message" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask Ephraim anything..." rows={2}/><button disabled={busy||!modelId||!question.trim()}>{busy?"Thinking…":"Send ↗"}</button></form></>}
 {page==="library"&&<div className="panel"><h3>Documents</h3><p>Imported documents remain on this computer. Text matching supports source-backed chat.</p>{user.role==="admin"&&<button disabled={busy} onClick={()=>void action(async()=>{await invoke("docs:import");await refresh();})}>+ Import documents</button>}
 <div className="items">{docs.length===0?"No documents imported yet.":docs.map(d=><div className="item" key={d.id}><span>▤ &nbsp; {d.title}</span><small>Version {d.version} · {d.imported}</small></div>)}</div></div>}
 {page==="models"&&<div className="panel"><h3>GGUF model library</h3><p>Only approved models can be used for chats. No Ollama installation is required.</p>
 {user.role==="admin"&&<div className="formrow"><input aria-label="Display name for model" placeholder="Model display name" value={modelName} onChange={e=>setModelName(e.target.value)}/><button disabled={busy||!modelName.trim()} onClick={()=>void action(async()=>{await invoke("models:import",modelName);setModelName("");await refresh();})}>Import GGUF</button></div>}
 <div className="items">{models.length===0?"No GGUF models installed.":models.map(m=><div className="item" key={m.id}><span>◈ &nbsp; <b>{m.name}</b> <small>{m.tested?"Tested":"Not tested"} · {m.enabled?"Available":"Disabled"}</small></span>{user.role==="admin"&&<div className="actions"><button disabled={busy} onClick={()=>void action(async()=>{await invoke("models:test",m.id);await refresh();})}>Test</button><button disabled={busy||(!m.tested&&!m.enabled)} onClick={()=>void action(async()=>{await invoke("models:enable",m.id,!m.enabled);await refresh();})}>{m.enabled?"Disable":"Enable"}</button></div>}</div>)}</div></div>}
 {page==="settings"&&<div className="panel"><h3>Privacy and internet search</h3><p>Internet search is opt-in for each chat. When enabled, Ephraim sends only your question to Tavily, not retrieved private documents.</p><p>Status: {hasKey?"Provider configured":"No provider configured"}</p>
 {user.role==="admin"&&<><div className="formrow"><input type="password" aria-label="Tavily API key" autoComplete="off" placeholder="Tavily API key (never committed)" value={key} onChange={e=>setKey(e.target.value)}/><button disabled={busy} onClick={()=>void action(async()=>{await invoke("settings:searchKey",key);setKey("");await refresh();})}>Save key</button><button disabled={busy} onClick={()=>void action(async()=>{await invoke("settings:searchKey","");await refresh();})}>Clear</button></div>
 <h3>Create a standard user</h3><div className="formrow"><input aria-label="New username" placeholder="Username" value={accountName} onChange={e=>setAccountName(e.target.value)}/><input aria-label="New password" type="password" autoComplete="new-password" placeholder="Password (12+ characters)" value={accountPass} onChange={e=>setAccountPass(e.target.value)}/><button disabled={busy} onClick={()=>void action(async()=>{await invoke("users:create",accountName,accountPass,"user");setAccountName("");setAccountPass("");})}>Create</button></div></>}
 <p className="warning">Early prototype: local documents and chat database are not encrypted at rest. Do not import regulated or confidential records until a security review is complete.</p></div>}
 </div></div>;
}
createRoot(document.getElementById("root")!).render(<App/>);
