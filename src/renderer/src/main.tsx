import React, {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import "./style.css";

type User={id:number;username:string;role:"admin"|"user"};
type Model={id:number;name:string;kind:"chat"|"embedding";enabled:boolean;tested:boolean};
type Doc={id:number;title:string;reference:string;version:number;status:string;visibility:string;imported:string;pages:number;size:number};
type Msg={id:number;role:"user"|"assistant";text:string;created:string};
type Conv={id:number;title:string;created:string};
type Citation={label:string;documentId:number;chunkId:number;title:string;reference:string;version:number;page:number|null;section:string|null;excerpt:string};
type Result<T>={ok:true;data:T}|{ok:false;error:string};
declare global{interface Window{ephraim:{invoke:(name:string,...args:unknown[])=>Promise<Result<any>>}}}
async function call<T>(channel:string,...args:unknown[]):Promise<T>{
 const r=await window.ephraim.invoke(channel,...args);
 if(!r.ok)throw new Error(r.error);
 return r.data as T;
}
function App(){
 const [user,setUser]=useState<User|null>(null),[setup,setSetup]=useState(false),[username,setUsername]=useState(""),[password,setPassword]=useState("");
 const [page,setPage]=useState<"chat"|"library"|"models"|"settings">("chat"),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 const [models,setModels]=useState<Model[]>([]),[modelId,setModelId]=useState(0),[docs,setDocs]=useState<Doc[]>([]);
 const [convs,setConvs]=useState<Conv[]>([]),[activeConv,setActiveConv]=useState<number|null>(null),[messages,setMessages]=useState<Msg[]>([]);
 const [question,setQuestion]=useState(""),[web,setWeb]=useState(false),[webKey,setWebKey]=useState(""),[hasWebKey,setHasWebKey]=useState(false),[safeKey,setSafeKey]=useState(false);
 const [modelName,setModelName]=useState(""),[modelKind,setModelKind]=useState<"chat"|"embedding">("chat");
 const [reference,setReference]=useState(""),[visibility,setVisibility]=useState<"private"|"shared">("shared");
 const [account,setAccount]=useState(""),[accountPassword,setAccountPassword]=useState("");
 const [citations,setCitations]=useState<Citation[]>([]),[preview,setPreview]=useState<{name:string;chunks:{page:number|null;section:string|null;text:string}[]}|null>(null);
 async function refresh(){
   const [ms,ds,cs,st]=await Promise.all([
     call<Model[]>("models:list"),call<Doc[]>("docs:list"),call<Conv[]>("conversations:list"),
     call<{hasWebKey:boolean;secureStorage:boolean}>("settings:status")]);
   setModels(ms);setDocs(ds);setConvs(cs);setHasWebKey(st.hasWebKey);setSafeKey(st.secureStorage);
   setModelId(old=>ms.some(m=>m.id===old&&m.enabled&&m.kind==="chat")?old:ms.find(m=>m.enabled&&m.kind==="chat")?.id??0);
 }
 async function act(action:()=>Promise<void>){setBusy(true);setError("");try{await action();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 useEffect(()=>{call<{needsSetup:boolean;user:User|null}>("auth:state").then(s=>{setSetup(s.needsSetup);setUser(s.user);}).catch(e=>setError(String(e)));},[]);
 useEffect(()=>{if(user)void refresh().catch(e=>setError(String(e)));},[user]);
 async function signIn(){await act(async()=>{const u=await call<User>(setup?"auth:setup":"auth:login",username,password);setUser(u);setPassword("");});}
 async function openConversation(id:number){await act(async()=>{setActiveConv(id);setMessages(await call<Msg[]>("conversations:messages",id));setCitations([]);});}
 async function newConversation():Promise<number>{const id=await call<number>("conversations:create","New conversation");setActiveConv(id);setMessages([]);setCitations([]);await refresh();return id;}
 async function send(){
   if(!question.trim()||!modelId||busy)return;
   const q=question.trim();setQuestion("");
   await act(async()=>{

     const id=activeConv??await newConversation();
     const r=await call<{answer:string;citations:Citation[]}>("chat:ask",q,modelId,id,web);
     setMessages(await call<Msg[]>("conversations:messages",id));
     setCitations(r.citations);await refresh();
   });
 }
 async function showSource(d:Doc){
   await act(async()=>{const chunks=await call<{page:number|null;section:string|null;text:string}[]>("docs:chunks",d.id);setPreview({name:d.reference+" v"+d.version+" · "+d.title,chunks});});
 }
 if(!user)return <main className="login"><div className="loginCard"><div className="symbol">✦</div><h1>Ephraim</h1><p>{setup?"Create the first administrator account":"Your private, local intelligence assistant"}</p>
 <form onSubmit={e=>{e.preventDefault();void signIn();}}><label>Username<input required minLength={3} value={username} onChange={e=>setUsername(e.target.value)}/></label>
 <label>Password<input type="password" required minLength={setup?12:1} value={password} onChange={e=>setPassword(e.target.value)}/></label>
 <button disabled={busy}>{setup?"Create administrator":"Sign in"}</button></form>{error&&<p className="error">{error}</p>}</div></main>;
 return <div className="shell"><aside className="sidebar"><div className="brand">✦ <b>Ephraim</b></div><p className="sub">Local intelligence · Private by design</p>
 {(["chat","library","models","settings"] as const).map(p=><button key={p} className={"nav "+(p===page?"active":"")} onClick={()=>setPage(p)}>{p==="chat"?"◫":p==="library"?"▤":p==="models"?"◈":"⚙"} &nbsp;{p[0].toUpperCase()+p.slice(1)}</button>)}
 {page==="chat"&&<><button className="nav newchat" onClick={()=>void act(async()=>{await newConversation();})}>+ New conversation</button><div className="threads">{convs.map(c=><button key={c.id} className={"nav "+(activeConv===c.id?"active":"")} onClick={()=>void openConversation(c.id)}>{c.title} #{c.id}</button>)}</div></>}
 <div className="bottom"><small>{user.username} · {user.role}</small><button className="nav" onClick={()=>void act(async()=>{await call("auth:logout");setUser(null);setMessages([]);setCitations([]);setActiveConv(null);setWeb(false);})}>Sign out</button></div></aside>
 <div className="body"><header><div><h2>{page==="chat"?"Chat":page==="library"?"Knowledge library":page==="models"?"Local GGUF models":"Settings"}</h2><small>Offline-first · No telemetry · Local user data</small></div><span className="privacy">● Local inference</span></header>
 {error&&<div className="alert" role="alert">{error}</div>}
 {page==="chat"&&<><div className="toolbar"><select aria-label="Choose model" value={modelId} onChange={e=>setModelId(Number(e.target.value))}><option value={0}>Choose an approved chat model</option>{models.filter(m=>m.enabled&&m.kind==="chat").map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select>
 <label className="check"><input type="checkbox" checked={web} disabled={!hasWebKey} onChange={e=>setWeb(e.target.checked)}/> External web search {hasWebKey?"(consent each time)":"(not configured)"}</label></div>
 <div className="conversation">{messages.length===0?<div className="welcome"><div className="symbol">✦</div><h1>Ask Ephraim anything</h1><p>Summarise TP 4122, explore approved documents or ask a local model. All conversations are private to this account.</p></div>:
 messages.map(m=><div className={"bubble "+m.role} key={m.id}><b>{m.role==="user"?"You":"Ephraim"}</b><p>{m.text}</p></div>)}
 {citations.length>0&&<section className="sourcecard"><h4>Retrieved supporting sources</h4><p>These passages were provided to the model. Always verify important claims against the original.</p>{citations.map(c=><div key={c.chunkId} className="source"><b>[{c.label}] {c.reference} v{c.version}{c.page?" · page "+c.page:""}{c.section?" · "+c.section:""}</b><button onClick={()=>void act(async()=>{await call("docs:open",c.documentId);})}>Open original</button><p>{c.excerpt}</p></div>)}</section>}</div>
 <form className="compose" onSubmit={e=>{e.preventDefault();void send();}}><textarea rows={2} aria-label="Your question" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask about your documents..." /><button disabled={!modelId||busy||!question.trim()}>{busy?"Working…":"Send ↗"}</button></form></>}
 {page==="library"&&<div className="panel"><h3>Documents and revisions</h3><p>Approved documents can be searched. Older versions are retained but excluded from normal answers.</p>
 {user.role==="admin"&&<div className="formrow"><input value={reference} onChange={e=>setReference(e.target.value)} placeholder="Reference e.g. TP 4122" aria-label="Document reference"/>
 <select value={visibility} onChange={e=>setVisibility(e.target.value as "private"|"shared")}><option value="shared">Shared with local users</option><option value="private">Private to this admin</option></select><button disabled={busy||!reference.trim()} onClick={()=>void act(async()=>{await call("docs:import",reference,visibility);await refresh();})}>Import documents</button></div>}
 {user.role==="admin"&&<button disabled={busy||!models.some(m=>m.kind==="embedding"&&m.enabled)} onClick={()=>void act(async()=>{const result=await call<{indexed:number}>("docs:reindex");window.alert(result.indexed+" chunks embedded");})}>Build semantic index</button>}
 <div className="items">{docs.length?docs.map(d=><div className="item" key={d.id}><div><b>{d.reference} · {d.title}</b><small>Version {d.version} · {d.status} · {d.visibility} · {d.pages} pages</small></div><div className="actions"><button onClick={()=>void showSource(d)}>Read chunks</button><button onClick={()=>void act(async()=>{await call("docs:open",d.id);})}>Open original</button></div></div>):"No documents in your library yet."}</div>
 {preview&&<section className="sourcecard"><div className="formrow"><h3>{preview.name}</h3><button onClick={()=>setPreview(null)}>Close</button></div>{preview.chunks.map((c,i)=><div className="source" key={i}><b>Section {i+1} · {c.page?"Page "+c.page:c.section??"Unknown page"}</b><p>{c.text}</p></div>)}</section>}</div>}
 {page==="models"&&<div className="panel"><h3>Installed models</h3><p>Import GGUF chat and embedding models. Models must pass a real local load/inference test before being enabled.</p>
 {user.role==="admin"&&<div className="formrow"><input aria-label="Model display name" placeholder="Display name" value={modelName} onChange={e=>setModelName(e.target.value)}/><select value={modelKind} onChange={e=>setModelKind(e.target.value as "chat"|"embedding")}><option value="chat">Chat model</option><option value="embedding">Embedding model</option></select><button disabled={busy||!modelName.trim()} onClick={()=>void act(async()=>{await call("models:import",modelName,modelKind);setModelName("");await refresh();})}>Import GGUF</button></div>}
 <div className="items">{models.length?models.map(m=><div className="item" key={m.id}><div><b>{m.name}</b><small>{m.kind} · {m.tested?"Tested":"Not tested"} · {m.enabled?"Enabled":"Disabled"}</small></div>{user.role==="admin"&&<div className="actions"><button disabled={busy} onClick={()=>void act(async()=>{await call("models:test",m.id);await refresh();})}>Test</button><button disabled={busy||(!m.tested&&!m.enabled)} onClick={()=>void act(async()=>{await call("models:enable",m.id,!m.enabled);await refresh();})}>{m.enabled?"Disable":"Enable"}</button></div>}</div>):"No models installed."}</div></div>}
 {page==="settings"&&<div className="panel"><h3>Internet privacy</h3><p>Web search is opt-in and asks permission for each query. Only the literal question is sent to Tavily, not retrieved documents or conversation history. Avoid including sensitive information in the question itself.</p><p>Provider: {hasWebKey?"Configured":"Not configured"} · OS encrypted storage: {safeKey?"Available":"Unavailable"}</p>
 {user.role==="admin"&&<><div className="formrow"><input aria-label="Tavily API key" autoComplete="off" type="password" placeholder="Tavily API key" value={webKey} onChange={e=>setWebKey(e.target.value)}/><button disabled={!safeKey||busy} onClick={()=>void act(async()=>{await call("settings:searchKey",webKey);setWebKey("");await refresh();})}>Save key</button><button disabled={busy} onClick={()=>void act(async()=>{await call("settings:searchKey","");await refresh();})}>Remove key</button></div>
 <h3>Create local user</h3><div className="formrow"><input value={account} onChange={e=>setAccount(e.target.value)} placeholder="Username" aria-label="New username"/><input type="password" autoComplete="new-password" value={accountPassword} onChange={e=>setAccountPassword(e.target.value)} placeholder="Password (12+ characters)" aria-label="New password"/><button disabled={busy} onClick={()=>void act(async()=>{await call("users:create",account,accountPassword,"user");setAccount("");setAccountPassword("");})}>Create</button></div></>}
 <p className="warning">Pre-release: database content and source files are not encrypted at rest. This is not validated for regulated laboratory documents. Enable full-disk encryption and use non-confidential test data until the security review is complete.</p></div>}
 </div></div>;
}
createRoot(document.getElementById("root")!).render(<App/>);
