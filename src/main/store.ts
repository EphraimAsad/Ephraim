import { DatabaseSync } from "node:sqlite";
import { randomBytes, scryptSync, timingSafeEqual, createHash } from "node:crypto";
import { chunksFromPages, findNamedDocument, rerank, type Chunk, type TextPage, type Reference } from "../core/knowledge";

export type Role = "admin" | "user";
export interface Person { id: number; username: string; role: Role }
export interface ModelInfo { id: number; name: string; kind: "chat" | "embedding"; enabled: boolean; tested: boolean }
export interface DocumentInfo { id:number; title:string; reference:string; version:number; status:string; visibility:string; imported:string; pages:number; size:number }
export interface SourceChunk { id:number; documentId:number; title:string; reference:string; version:number; page:number|null; section:string|null; excerpt:string; ordinal:number }
type Row = Record<string,unknown>;
const hash = (value:string) => createHash("sha256").update(value).digest("hex");
const validId = (id:number) => Number.isSafeInteger(id) && id>0;
function secret(password:string,salt:string):Buffer { return scryptSync(password,Buffer.from(salt,"hex"),64); }
function readRows(db:DatabaseSync,sql:string,...args:any[]):Row[] { return db.prepare(sql).all(...args) as Row[]; }
export class KnowledgeStore {
  db:DatabaseSync;
  constructor(path:string) {
    this.db = new DatabaseSync(path);
    this.db.exec("PRAGMA foreign_keys=ON; PRAGMA busy_timeout=3000;");
    this.db.exec([
      "CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','user')), salt TEXT NOT NULL, password_hash TEXT NOT NULL);",
      "CREATE TABLE IF NOT EXISTS models(id INTEGER PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE, enabled INTEGER NOT NULL DEFAULT 0, tested INTEGER NOT NULL DEFAULT 0);",
      "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);",
      "CREATE TABLE IF NOT EXISTS v2_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);",
      "CREATE TABLE IF NOT EXISTS v2_conversations(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES accounts(id), title TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);",
      "CREATE TABLE IF NOT EXISTS v2_messages(id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES v2_conversations(id), role TEXT NOT NULL CHECK(role IN ('user','assistant')), text TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);",
       "CREATE TABLE IF NOT EXISTS v2_conversation_memory(conversation_id INTEGER PRIMARY KEY REFERENCES v2_conversations(id), last_message_id INTEGER NOT NULL, summary TEXT NOT NULL, updated TEXT DEFAULT CURRENT_TIMESTAMP);",
      "CREATE INDEX IF NOT EXISTS idx_v2_conversations_owner ON v2_conversations(owner_id);",
      "CREATE TABLE IF NOT EXISTS v2_documents(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES accounts(id), visibility TEXT NOT NULL CHECK(visibility IN ('private','shared')), status TEXT NOT NULL CHECK(status IN ('draft','approved','superseded')), title TEXT NOT NULL, reference TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL, source_path TEXT, pages INTEGER NOT NULL, size INTEGER NOT NULL, imported TEXT DEFAULT CURRENT_TIMESTAMP);",
      "CREATE INDEX IF NOT EXISTS idx_v2_docs_owner ON v2_documents(owner_id,visibility,status);",
      "CREATE TABLE IF NOT EXISTS v2_chunks(id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL REFERENCES v2_documents(id), ordinal INTEGER NOT NULL, page INTEGER, section TEXT, text TEXT NOT NULL, embedding_model INTEGER, embedding TEXT, UNIQUE(doc_id,ordinal));",
      "CREATE INDEX IF NOT EXISTS idx_v2_chunks_doc ON v2_chunks(doc_id);",
      "CREATE VIRTUAL TABLE IF NOT EXISTS v2_chunks_fts USING fts5(text,content='v2_chunks',content_rowid='id');",
      "CREATE TRIGGER IF NOT EXISTS v2_chunks_ai AFTER INSERT ON v2_chunks BEGIN INSERT INTO v2_chunks_fts(rowid,text) VALUES(new.id,new.text); END;",
      "CREATE TRIGGER IF NOT EXISTS v2_chunks_ad AFTER DELETE ON v2_chunks BEGIN INSERT INTO v2_chunks_fts(v2_chunks_fts,rowid,text) VALUES('delete',old.id,old.text); END;"
    ].join("\n"));
    const cols = readRows(this.db,"PRAGMA table_info(models)").map(x=>x.name);
    if(!cols.includes("kind"))this.db.exec("ALTER TABLE models ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat'");
    this.migrateLegacy();
  }
  close(){this.db.close();}
  setupNeeded():boolean {return Number((this.db.prepare("SELECT count(*) n FROM accounts").get() as Row).n)===0;}
  createAccount(username:string,password:string,role:Role):Person {
    if(!/^[A-Za-z][A-Za-z0-9_.-]{2,39}$/.test(username)||password.length<12||password.length>256||!["admin","user"].includes(role))throw new Error("Invalid username/password (12+ characters)");
    const salt=randomBytes(24).toString("hex");
    const result=this.db.prepare("INSERT INTO accounts(username,role,salt,password_hash) VALUES(?,?,?,?)").run(username,role,salt,secret(password,salt).toString("hex"));
    this.migrateLegacy();
    return {id:Number(result.lastInsertRowid),username,role};
  }
  authenticate(username:string,password:string):Person|null {
    const r=this.db.prepare("SELECT * FROM accounts WHERE username=?").get(username) as Row|undefined;
    if(!r){secret(password,"ba".repeat(24));return null;}
    const valid=timingSafeEqual(secret(password,String(r.salt)),Buffer.from(String(r.password_hash),"hex"));
    return valid?{id:Number(r.id),username:String(r.username),role:r.role as Role}:null;
  }
  private tableExists(name:string):boolean {
    return !!this.db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?").get(name);
  }
  private migrateLegacy():void {
    if(this.db.prepare("SELECT 1 FROM v2_meta WHERE key='legacy_migrated'").get())return;
    const admin=this.db.prepare("SELECT id FROM accounts WHERE role='admin' ORDER BY id LIMIT 1").get() as Row|undefined;
    if(!admin)return;
    this.db.exec("BEGIN IMMEDIATE");
    try {
      if(this.tableExists("docs")) {
        const legacy=readRows(this.db,"SELECT title,version,content FROM docs ORDER BY id");
        for(const d of legacy) {
          this.insertDocument(Number(admin.id),String(d.title),String(d.title).replace(/\.[^.]+$/,""),"private","approved",[{page:null,text:String(d.content)}],null,Number(d.version));
        }
      }
      if(this.tableExists("messages")) {
        const old=readRows(this.db,"SELECT role,text FROM messages ORDER BY id");
        if(old.length){
          const c=this.createConversation(Number(admin.id),"Imported legacy chat");
          for(const m of old)if(m.role==="user"||m.role==="assistant")this.db.prepare("INSERT INTO v2_messages(conversation_id,role,text) VALUES(?,?,?)").run(c,m.role as string,String(m.text));
        }
      }
      this.db.prepare("INSERT INTO v2_meta(key,value) VALUES('legacy_migrated','1')").run();
      this.db.exec("COMMIT");
    }catch(e){this.db.exec("ROLLBACK");throw e;}
  }
  listModels():ModelInfo[] {
    return readRows(this.db,"SELECT id,name,kind,enabled,tested FROM models ORDER BY kind,name").map(r=>({id:Number(r.id),name:String(r.name),kind:r.kind==="embedding"?"embedding":"chat",enabled:!!r.enabled,tested:!!r.tested}));
  }
  addModel(name:string,path:string,kind:"chat"|"embedding"):number {
    if(!name.trim()||name.length>80||!["chat","embedding"].includes(kind))throw new Error("Invalid model");
    return Number(this.db.prepare("INSERT INTO models(name,path,kind) VALUES(?,?,?)").run(name.trim(),path,kind).lastInsertRowid);
  }
  modelForTest(id:number):{path:string;kind:string} {
    if(!validId(id))throw new Error("Invalid model");
    const r=this.db.prepare("SELECT path,kind FROM models WHERE id=?").get(id) as Row|undefined;
    if(!r)throw new Error("Model not found");
    return {path:String(r.path),kind:String(r.kind)};
  }
  deleteModel(id:number):void {
    if(!validId(id))throw new Error("Invalid model");
    const record=this.db.prepare("SELECT id FROM models WHERE id=?").get(id) as Row|undefined;
    if(!record)throw new Error("Model not found");
    this.db.exec("BEGIN IMMEDIATE");
    try {
      // Indexed vectors from a deleted embedding model must not be reused.
      this.db.prepare("UPDATE v2_chunks SET embedding_model=NULL,embedding=NULL WHERE embedding_model=?").run(id);
      this.db.prepare("DELETE FROM models WHERE id=?").run(id);
      this.db.exec("COMMIT");
    }catch(e){this.db.exec("ROLLBACK");throw e;}
  }
  modelForUse(id:number,kind:"chat"|"embedding"):string {
    const r=this.db.prepare("SELECT path FROM models WHERE id=? AND kind=? AND enabled=1 AND tested=1").get(id,kind) as Row|undefined;
    if(!r)throw new Error("Model is not approved");
    return String(r.path);
  }
  enabledEmbedding():{id:number;path:string}|null {
    const r=this.db.prepare("SELECT id,path FROM models WHERE kind='embedding' AND tested=1 AND enabled=1 ORDER BY id DESC LIMIT 1").get() as Row|undefined;
    return r?{id:Number(r.id),path:String(r.path)}:null;
  }
  markModelTested(id:number){this.db.prepare("UPDATE models SET tested=1 WHERE id=?").run(id);}
  enableModel(id:number,enabled:boolean) {
    const m=this.db.prepare("SELECT kind,tested FROM models WHERE id=?").get(id) as Row|undefined;
    if(!m)throw new Error("Model not found");
    if(enabled&&!m.tested)throw new Error("Model must pass an inference/embedding test");
    this.db.exec("BEGIN IMMEDIATE");
    try{
      if(enabled && m.kind==="embedding")this.db.prepare("UPDATE models SET enabled=0 WHERE kind='embedding'").run();
      this.db.prepare("UPDATE models SET enabled=? WHERE id=?").run(enabled?1:0,id);
      this.db.exec("COMMIT");
    }catch(e){this.db.exec("ROLLBACK");throw e;}
  }
  createConversation(owner:number,title="New conversation"):number {
    if(!validId(owner))throw new Error("Invalid user");
    return Number(this.db.prepare("INSERT INTO v2_conversations(owner_id,title) VALUES(?,?)").run(owner,title.slice(0,120)).lastInsertRowid);
  }
  renameConversation(owner:number,id:number,title:string):void {
    this.ownsConversation(owner,id);
    const clean=title.trim();
    if(clean.length===0||clean.length>120)throw new Error("Invalid conversation title");
    this.db.prepare("UPDATE v2_conversations SET title=? WHERE id=? AND owner_id=?").run(clean,id,owner);
  }
  deleteConversation(owner:number,id:number):void {
    this.ownsConversation(owner,id);
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db.prepare("DELETE FROM v2_conversation_memory WHERE conversation_id=?").run(id);
      this.db.prepare("DELETE FROM v2_messages WHERE conversation_id=?").run(id);
      this.db.prepare("DELETE FROM v2_conversations WHERE id=? AND owner_id=?").run(id,owner);
      this.db.exec("COMMIT");
    } catch(e) { this.db.exec("ROLLBACK");throw e; }
  }
  getUserPreference(owner:number,name:"theme"|"maxTokens"|"contextSize"):string|null {
    if(!validId(owner))throw new Error("Invalid account");
    return this.getSetting("user."+owner+"."+name);
  }
  setUserPreference(owner:number,name:"theme"|"maxTokens"|"contextSize",value:string):void {
    if(!validId(owner))throw new Error("Invalid account");
    if(name==="theme"&&!["light","dark","system"].includes(value))throw new Error("Invalid theme");
    if(name==="maxTokens"&&!["256","512","900","1500","2048"].includes(value))throw new Error("Invalid maximum tokens");
    if(name==="contextSize"&&!["4096","8192","16384","32768"].includes(value))throw new Error("Invalid context size");
    this.setSetting("user."+owner+"."+name,value);
  }
  listConversations(owner:number) {
    return readRows(this.db,"SELECT id,title,created FROM v2_conversations WHERE owner_id=? ORDER BY id DESC LIMIT 100",owner);
  }
  private ownsConversation(owner:number,id:number):void {
    if(!validId(id)||!this.db.prepare("SELECT 1 FROM v2_conversations WHERE id=? AND owner_id=?").get(id,owner))throw new Error("Conversation not found");
  }
  getMessages(owner:number,cid:number) {
    this.ownsConversation(owner,cid);
    return readRows(this.db,"SELECT id,role,text,created FROM v2_messages WHERE conversation_id=? ORDER BY id",cid);
  }
  getConversationMemory(owner:number,cid:number):{lastMessageId:number;summary:string}|null {
    this.ownsConversation(owner,cid);
    const row=this.db.prepare("SELECT last_message_id,summary FROM v2_conversation_memory WHERE conversation_id=?").get(cid) as Row|undefined;
    return row?{lastMessageId:Number(row.last_message_id),summary:String(row.summary)}:null;
  }
  saveConversationMemory(owner:number,cid:number,lastMessageId:number,summary:string):void {
    this.ownsConversation(owner,cid);
    if(!validId(lastMessageId)||summary.length>12000)throw new Error("Invalid conversation memory");
    if(!this.db.prepare("SELECT 1 FROM v2_messages WHERE id=? AND conversation_id=?").get(lastMessageId,cid))throw new Error("Memory checkpoint missing");
    this.db.prepare("INSERT INTO v2_conversation_memory(conversation_id,last_message_id,summary) VALUES(?,?,?) ON CONFLICT(conversation_id) DO UPDATE SET last_message_id=excluded.last_message_id,summary=excluded.summary,updated=CURRENT_TIMESTAMP WHERE excluded.last_message_id>v2_conversation_memory.last_message_id").run(cid,lastMessageId,summary);
  }
  getApprovedReferences(owner:number):string[] {
    return this.listDocuments(owner).filter(d=>d.status==="approved").map(d=>d.reference);
  }
  addMessage(owner:number,cid:number,role:"user"|"assistant",text:string) {
    this.ownsConversation(owner,cid);
    if(!["user","assistant"].includes(role)||text.length>30000)throw new Error("Invalid message");
    this.db.prepare("INSERT INTO v2_messages(conversation_id,role,text) VALUES(?,?,?)").run(cid,role,text);
  }
  listDocuments(owner:number) {
    return readRows(this.db,"SELECT id,title,reference,version,visibility,status,imported,pages,size FROM v2_documents WHERE owner_id=? OR visibility='shared' ORDER BY id DESC",owner) as unknown as DocumentInfo[];
  }
  private visibleFilter="(d.owner_id=? OR d.visibility='shared')";
  canReadDocument(owner:number,docId:number,includeOld=false):boolean {
    return !!this.db.prepare("SELECT 1 FROM v2_documents d WHERE d.id=? AND (d.owner_id=? OR d.visibility='shared') AND (?=1 OR d.status='approved')").get(docId,owner,includeOld?1:0);
  }
  private insertDocument(owner:number,title:string,reference:string,visibility:"private"|"shared",status:"draft"|"approved",pages:TextPage[],source:string|null,forcedVersion?:number):number {
    const body=pages.map(p=>p.text).join("\n");
    const version=forcedVersion??Number((this.db.prepare("SELECT COALESCE(MAX(version),0)+1 AS n FROM v2_documents WHERE reference=? AND visibility=? AND owner_id=?").get(reference,visibility,owner) as Row).n);
    const result=this.db.prepare("INSERT INTO v2_documents(owner_id,visibility,status,title,reference,version,content_hash,source_path,pages,size) VALUES(?,?,?,?,?,?,?,?,?,?)").run(owner,visibility,status,title,reference,version,hash(body),source,pages.length,Buffer.byteLength(body));
    const id=Number(result.lastInsertRowid);
    const add=this.db.prepare("INSERT INTO v2_chunks(doc_id,ordinal,page,section,text) VALUES(?,?,?,?,?)");
    for(const c of chunksFromPages(pages))add.run(id,c.ordinal,c.page,c.section,c.text);
    return id;
  }
  addDocument(owner:number,title:string,reference:string,visibility:"private"|"shared",pages:TextPage[],source:string|null):number {
    if(!validId(owner)||!["private","shared"].includes(visibility)||!title.trim()||title.length>160||!/^[\p{L}\p{N}][\p{L}\p{N} _./-]{1,99}$/u.test(reference))throw new Error("Invalid document metadata");
    const total=pages.reduce((n,p)=>n+p.text.length,0);
    if(total<1||total>1_500_000)throw new Error("Document is empty or too large");
    const scopeOwner=owner;
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db.prepare("UPDATE v2_documents SET status='superseded' WHERE reference=? AND visibility=? AND owner_id=? AND status='approved'").run(reference,visibility,scopeOwner);
      const id=this.insertDocument(owner,title,reference,visibility,"approved",pages,source);
      this.db.exec("COMMIT");
      return id;
    }catch(e){this.db.exec("ROLLBACK");throw e;}
  }
  visibleReferences(owner:number):Reference[] {
    return readRows(this.db,"SELECT id,title,reference,version FROM v2_documents d WHERE status='approved' AND "+this.visibleFilter,owner) as unknown as Reference[];
  }
  findDocument(owner:number,question:string):Reference|null {
    return findNamedDocument(question,this.visibleReferences(owner));
  }
  documentChunks(owner:number,documentId:number,includeSuperseded=false):SourceChunk[] {
    if(!this.canReadDocument(owner,documentId,includeSuperseded))throw new Error("Document not available");
    return readRows(this.db,"SELECT c.id,c.doc_id AS documentId,d.title,d.reference,d.version,c.page,c.section,c.text AS excerpt,c.ordinal FROM v2_chunks c JOIN v2_documents d ON d.id=c.doc_id WHERE c.doc_id=? ORDER BY c.ordinal",documentId) as unknown as SourceChunk[];
  }
  sourcePath(owner:number,id:number):string|null {
    if(!this.canReadDocument(owner,id,true))throw new Error("Document unavailable");
    const r=this.db.prepare("SELECT source_path FROM v2_documents WHERE id=?").get(id) as Row;
    return r.source_path?String(r.source_path):null;
  }
  chunkEmbeddingsToIndex(modelId:number):{id:number;text:string}[] {
    return readRows(this.db,"SELECT id,text FROM v2_chunks WHERE embedding_model IS NULL OR embedding_model<>? ORDER BY id LIMIT 4000",modelId).map(r=>({id:Number(r.id),text:String(r.text)}));
  }
  saveEmbedding(chunkId:number,modelId:number,vector:number[]) {
    if(!Array.isArray(vector)||vector.length<2||vector.length>8192||!vector.every(Number.isFinite))throw new Error("Invalid embedding vector");
    this.db.prepare("UPDATE v2_chunks SET embedding_model=?,embedding=? WHERE id=?").run(modelId,JSON.stringify(vector),chunkId);
  }
  retrieve(owner:number,question:string,queryEmbedding?:{modelId:number;vector:number[]},limit=6):SourceChunk[] {
    const tokens=Array.from(new Set((question.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu)||[]))).slice(0,10);
    const words=tokens.map(t=>'"'+t.replace(/"/g,"")+'"').join(" OR ");
    const candidates=new Map<number,{chunk:SourceChunk;lexical:number;embedding:number[]|null}>();
    if(words) {
      const lexical=readRows(this.db,"SELECT c.id,c.doc_id AS documentId,d.title,d.reference,d.version,c.page,c.section,c.text AS excerpt,c.ordinal,bm25(v2_chunks_fts) AS rank FROM v2_chunks_fts JOIN v2_chunks c ON c.id=v2_chunks_fts.rowid JOIN v2_documents d ON d.id=c.doc_id WHERE v2_chunks_fts MATCH ? AND d.status='approved' AND "+this.visibleFilter+" ORDER BY rank LIMIT 80",words,owner);
      lexical.forEach((r,i)=>candidates.set(Number(r.id),{chunk:r as unknown as SourceChunk,lexical:1/(1+Math.max(0,i)/8),embedding:null}));
    }
    if(queryEmbedding) {
      const sem=readRows(this.db,"SELECT c.id,c.doc_id AS documentId,d.title,d.reference,d.version,c.page,c.section,c.text AS excerpt,c.ordinal,c.embedding FROM v2_chunks c JOIN v2_documents d ON d.id=c.doc_id WHERE c.embedding_model=? AND c.embedding IS NOT NULL AND d.status='approved' AND "+this.visibleFilter+" LIMIT 5000",queryEmbedding.modelId,owner);
      for(const row of sem){
        const id=Number(row.id);const previous=candidates.get(id);
        candidates.set(id,{chunk:row as unknown as SourceChunk,lexical:previous?.lexical??0,embedding:JSON.parse(String(row.embedding)) as number[]});
      }
    }
    const rank=rerank(Array.from(candidates.values()).map(c=>({id:c.chunk.id,text:c.chunk.excerpt,lexical:c.lexical,embedding:c.embedding})),queryEmbedding?.vector,Math.max(1,Math.min(20,limit)));
    return rank.map(r=>candidates.get(r.id)!.chunk);
  }
  getSetting(key:string):string|null {
    const row=this.db.prepare("SELECT value FROM settings WHERE key=?").get(key) as Row|undefined;
    return row?String(row.value):null;
  }
  setSetting(key:string,value:string|null){
    if(value===null)this.db.prepare("DELETE FROM settings WHERE key=?").run(key);
    else this.db.prepare("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(key,value);
  }
}
