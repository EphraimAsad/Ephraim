export interface WebResult { title:string; url:string; snippet:string; publishedDate:string|null }
export function safeWebUrl(value:unknown):string|null {
  if(typeof value!=="string"||value.length>2048)return null;
  try {
    const u=new URL(value);
    if(u.protocol!=="https:"||!u.hostname||u.username||u.password||u.hostname.includes(":"))return null;
    if(/^(localhost|.*\.localhost|.*\.local)$/i.test(u.hostname))return null;
    if(/^(127\.|10\.|192\.168\.|169\.254\.|0\.|172\.(1[6-9]|2\d|3[01])\.|::1$)/i.test(u.hostname))return null;
    return u.href;
  }catch{return null;}
}
export function normalizeWebResults(input:unknown):WebResult[] {
  if(!input||typeof input!=="object")return [];
  const rows=(input as {results?:unknown}).results;
  if(!Array.isArray(rows))return [];
  const found:WebResult[]=[];
  const seen=new Set<string>();
  for(const row of rows.slice(0,12)){
    if(!row||typeof row!=="object")continue;
    const r=row as Record<string,unknown>;
    const url=safeWebUrl(r.url);
    if(!url||seen.has(url))continue;
    seen.add(url);
    const title=typeof r.title==="string"?r.title.trim().slice(0,160):"Source";
    const snippet=typeof r.content==="string"?r.content.trim().slice(0,1300):"";
    const publishedDate=typeof r.published_date==="string"&&/^\d{4}-\d{2}-\d{2}/.test(r.published_date)?r.published_date.slice(0,10):null;
    found.push({url,title,snippet,publishedDate});
    if(found.length===5)break;
  }
  return found;
}
export function formatWebResults(rows:WebResult[]):string {
  return rows.map((r,i)=>"[W"+(i+1)+"] "+r.title+"\nURL: "+r.url+(r.publishedDate?"\nPublished: "+r.publishedDate:"")+"\nExcerpt: "+r.snippet).join("\n\n");
}
