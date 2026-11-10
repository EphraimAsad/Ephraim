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
