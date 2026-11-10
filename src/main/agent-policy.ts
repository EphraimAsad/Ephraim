/** A request-scoped, read-only tool gate. Never trust model-supplied arguments. */
export type ToolName = "list_documents"|"search_documents"|"read_document"|"get_document_versions"|"search_public_web";
export const MAX_TOOL_CALLS=5;
export const MAX_WEB_CALLS=1;
export class ToolGate {
  private count=0;
  private webCount=0;
  private readonly calls:ToolName[]=[];
  constructor(private readonly assertSession:()=>void,private readonly webEnabled:boolean){}
  async run<T>(name:ToolName,job:()=>Promise<T>):Promise<T> {
    this.assertSession();
    if(this.count>=MAX_TOOL_CALLS)throw new Error("Tool call limit reached");
    if(name==="search_public_web"){
      if(!this.webEnabled)throw new Error("Internet tool is disabled");
      if(this.webCount>=MAX_WEB_CALLS)throw new Error("Only one web lookup is allowed per answer");
      this.webCount++;
    }
    this.count++;
    this.calls.push(name);
    const result=await job();
    this.assertSession();
    return result;
  }
  used():ToolName[]{return [...this.calls];}
}
export function queryArg(value:unknown,max=280):string {
  if(typeof value!=="string"||!value.trim()||value.length>max)throw new Error("Invalid tool query");
  const clean=value.trim();
  if(/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(clean))throw new Error("Invalid control characters");
  return clean;
}
export function documentIdArg(value:unknown):number {
  if(typeof value!=="number"||!Number.isSafeInteger(value)||value<1)throw new Error("Invalid document ID");
  return value as number;
}
export interface AgentToolHandlers {
  listDocuments:()=>Promise<unknown>;
  searchDocuments:(query:string)=>Promise<unknown>;
  readDocument:(id:number)=>Promise<unknown>;
  getDocumentVersions:(reference:string)=>Promise<unknown>;
  searchPublicWeb?:()=>Promise<unknown>;
}
