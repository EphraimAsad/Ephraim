import {normalizeWebResults, type WebResult} from "../core/research";
export async function tavilySearch(question:string,key:string):Promise<WebResult[]> {
  if(question.length>500 || !question.trim())throw new Error("Search query must be 1–500 characters");
  const response=await fetch("https://api.tavily.com/search",{
    method:"POST",
    headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},
    body:JSON.stringify({query:question,search_depth:"basic",max_results:5,include_raw_content:false}),
    signal:AbortSignal.timeout(10000)
  });
  if(!response.ok)throw new Error("Web search failed. Check provider configuration and available credits.");
  return normalizeWebResults(await response.json());
}

/** Fetch richer evidence only from vetted HTTPS URLs already returned by Tavily.
 * Web extraction is part of the explicitly approved public research operation.
 */
export async function tavilyExtract(urls:string[],key:string):Promise<Map<string,string>> {
  const {safeWebUrl}=await import("../core/research");
  const allowed=[...new Set(urls.map(safeWebUrl).filter((x):x is string=>!!x))].slice(0,3);
  if(!allowed.length)return new Map();
  const response=await fetch("https://api.tavily.com/extract",{
    method:"POST",
    headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},
    body:JSON.stringify({urls:allowed,extract_depth:"basic",include_images:false}),
    signal:AbortSignal.timeout(12000)
  });
  if(!response.ok)return new Map();
  const payload=await response.json() as {results?:Array<{url?:string;raw_content?:string}>};
  const extracted=new Map<string,string>();
  for(const row of payload.results??[]){
    const url=safeWebUrl(row.url);
    if(url&&allowed.includes(url)&&typeof row.raw_content==="string"){
      extracted.set(url,row.raw_content.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g," ").slice(0,2400));
    }
  }
  return extracted;
}
