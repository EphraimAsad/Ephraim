import { app, safeStorage } from "electron";
import { DatabaseSync } from "node:sqlite";
import { createHash, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import { mkdirSync, copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { basename, extname, join } from "node:path";

export type Role = "admin" | "user";
export interface Person { id: number; username: string; role: Role }
export interface ModelInfo { id: number; name: string; enabled: boolean; tested: boolean }
export interface DocInfo { id: number; title: string; version: number; imported: string; size: number }
const appData = () => app.getPath("userData");
const sha256 = (s: string) => createHash("sha256").update(s).digest("hex");
let db: DatabaseSync;
export function initStore(): void {
  mkdirSync(appData(), { recursive: true });
  db = new DatabaseSync(join(appData(), "ephraim.sqlite"));
  db.exec("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;");
  db.exec(`CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','user')), salt TEXT NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS models(id INTEGER PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE, enabled INTEGER NOT NULL DEFAULT 0, tested INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, title TEXT NOT NULL, version INTEGER NOT NULL, imported TEXT DEFAULT CURRENT_TIMESTAMP, size INTEGER NOT NULL, content TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(title, content, content='docs', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN INSERT INTO docs_fts(rowid,title,content) VALUES(new.id,new.title,new.content); END;
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('user','assistant')), text TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);`);
}
export function setupNeeded(): boolean {
  return (db.prepare("SELECT COUNT(*) AS n FROM accounts").get() as {n:number}).n === 0;
}
function passwordDigest(password:string,salt:string) {
  return scryptSync(password, Buffer.from(salt, "hex"), 64).toString("hex");
}
export function createAccount(username:string,password:string,role:Role) {
  if (!/^[a-zA-Z][\w.-]{2,39}$/.test(username) || password.length < 12 || password.length > 256) throw new Error("Use a valid username and a password of at least 12 characters.");
  if (role !== "admin" && role !== "user") throw new Error("Invalid role");
  const salt=randomBytes(24).toString("hex");
  db.prepare("INSERT INTO accounts(username,role,salt,password_hash) VALUES(?,?,?,?)").run(username,role,salt,passwordDigest(password,salt));
}
export function authenticate(username:string,password:string):Person|null {
  const record = db.prepare("SELECT * FROM accounts WHERE username=?").get(username) as (Person & {salt:string,password_hash:string})|undefined;
  if (!record) { passwordDigest(password,"ab".repeat(24)); return null; }
  const check=Buffer.from(passwordDigest(password,record.salt),"hex");
  if (!timingSafeEqual(check,Buffer.from(record.password_hash,"hex"))) return null;
  return {id:record.id,username:record.username,role:record.role};
}
export function listModels():ModelInfo[] {
  return (db.prepare("SELECT id,name,enabled,tested FROM models ORDER BY name").all() as {id:number,name:string,enabled:number,tested:number}[]).map(m=>({...m,enabled:!!m.enabled,tested:!!m.tested}));
}
export function getModelPath(id:number):string {
  const m=db.prepare("SELECT path FROM models WHERE id=? AND enabled=1 AND tested=1").get(id) as {path:string}|undefined;
  if(!m) throw new Error("Model is not approved");
  return m.path;
}
export function getModelPathForTest(id:number):string {
  const m=db.prepare("SELECT path FROM models WHERE id=?").get(id) as {path:string}|undefined;
  if(!m) throw new Error("Model not found");
  return m.path;
}
export function importModel(source:string,name:string):void {
  if(extname(source).toLowerCase()!==".gguf" || !existsSync(source)) throw new Error("Select a GGUF model");
  if(!name.trim() || name.length>80) throw new Error("Invalid model name");
  const dir=join(appData(),"models");mkdirSync(dir,{recursive:true});
  const target=join(dir,randomBytes(16).toString("hex")+".gguf");
  copyFileSync(source,target);
  db.prepare("INSERT INTO models(name,path) VALUES(?,?)").run(name.trim(),target);
}
export function markTested(id:number):void { db.prepare("UPDATE models SET tested=1 WHERE id=?").run(id); }
export function enableModel(id:number,enable:boolean):void {
  if(enable && !(db.prepare("SELECT 1 FROM models WHERE id=? AND tested=1").get(id))) throw new Error("Model must pass a local load test");
  db.prepare("UPDATE models SET enabled=? WHERE id=?").run(enable?1:0,id);
}
export function listDocuments():DocInfo[] {
  return db.prepare("SELECT id,title,version,imported,size FROM docs ORDER BY id DESC") .all() as unknown as DocInfo[];
}
export function addDocument(name:string,content:string):void {
  if(!content.trim()) throw new Error("No extractable text found");
  if(content.length>1_500_000) throw new Error("Document exceeds 1.5 million characters");
  const version=(db.prepare("SELECT COALESCE(MAX(version),0)+1 AS n FROM docs WHERE title=?").get(name) as {n:number}).n;
  db.prepare("INSERT INTO docs(title,version,size,content,sha256) VALUES(?,?,?,?,?)").run(name,version,Buffer.byteLength(content),content,sha256(content));
}
export interface Citation { id:number; title:string; version:number; excerpt:string }
export function retrieve(query:string):Citation[] {
  const exact=db.prepare("SELECT id,title,version,substr(content,1,17000) AS excerpt FROM docs WHERE lower(title) LIKE lower(?) ORDER BY version DESC LIMIT 1").all("%"+query.trim().replace(/[%_]/g,"")+"%") as Citation[];
  if(exact.length) return exact;
  const tokens=Array.from(new Set((query.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu)||[]))).slice(0,12);
  if(!tokens.length) return [];
  const fts=tokens.map(t=>'"'+t.replace(/"/g,"")+'"').join(" OR ");
  return db.prepare("SELECT d.id,d.title,d.version,snippet(docs_fts,1,'','', ' … ',32) AS excerpt FROM docs_fts JOIN docs d ON d.id=docs_fts.rowid WHERE docs_fts MATCH ? ORDER BY bm25(docs_fts) LIMIT 5").all(fts) as Citation[];
}
export function history() {
  return db.prepare("SELECT id,role,text,created FROM messages ORDER BY id DESC LIMIT 60").all().reverse();
}
export function addMessage(role:"user"|"assistant",text:string) {
  db.prepare("INSERT INTO messages(role,text) VALUES(?,?)").run(role,text);
}
export function setSearchKey(key:string):void {
  if(!safeStorage.isEncryptionAvailable() || (process.platform==="linux" && safeStorage.getSelectedStorageBackend()==="basic_text")) throw new Error("Secure OS key storage is unavailable");
  if(!key.trim()) {db.prepare("DELETE FROM settings WHERE key='tavily'").run();return;}
  const value=safeStorage.encryptString(key.trim()).toString("base64");
  db.prepare("INSERT INTO settings(key,value) VALUES('tavily',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(value);
}
export function getSearchKey():string|null {
  const row=db.prepare("SELECT value FROM settings WHERE key='tavily'").get() as {value:string}|undefined;
  if(!row || !safeStorage.isEncryptionAvailable())return null;
  return safeStorage.decryptString(Buffer.from(row.value,"base64"));
}
export function hasSearchKey():boolean {
 return !!db.prepare("SELECT 1 FROM settings WHERE key='tavily'").get();
}
