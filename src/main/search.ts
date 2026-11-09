export async function tavilySearch(question:string,key:string):Promise<string> {
  if(question.length>500) throw new Error("Search query too long");
  const response=await fetch("https://api.tavily.com/search",{
    method:"POST",
    headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},
    body:JSON.stringify({query:question,search_depth:"basic",max_results:5,include_raw_content:false}),
    signal:AbortSignal.timeout(10000)
  });
  if(!response.ok)throw new Error("Web search failed. Check provider configuration and available credits.");
  const data=await response.json() as {results?:{title?:string;url?:string;content?:string}[]};
  return (data.results??[]).slice(0,5).map((r,i)=>`[WEB ${i+1}] ${r.title??"Source"} (${r.url??"unknown"})\n${(r.content??"").slice(0,1600)}`).join("\n\n");
}
