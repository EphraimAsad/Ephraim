/** Keep as much of the current conversation as fits in the selected model context. */
export interface ConversationMessage { role:"user"|"assistant"; text:string }
export type CountTokens = (text:string)=>number;

/** Retain a prefix of retrieved evidence without exceeding its token budget. */
export function prefixWithinTokens(text:string, countTokens:CountTokens, budget:number):string {
  if(budget<=0)return "";
  if(countTokens(text)<=budget)return text;
  let lo=0,hi=text.length;
  while(lo<hi){
    const mid=Math.ceil((lo+hi)/2);
    if(countTokens(text.slice(0,mid))<=budget)lo=mid;
    else hi=mid-1;
  }
  let result=text.slice(0,lo);
  while(result && countTokens(result)>budget)result=result.slice(0,-1);
  return result;
}

/** Prefer complete recent exchanges; trim the newest oversized message only if necessary.
 * Callers must pass only messages from the authenticated conversation in chronological order.
 */
export function fitConversationToPrompt(
  messages:readonly ConversationMessage[],
  countTokens:CountTokens,
  maxPromptTokens:number,
  render:(history:string)=>string
):string {
  if(countTokens(render(""))>maxPromptTokens)throw new Error("Question or retrieved evidence exceeds the selected model context. Increase context size or shorten the question.");
  const selected:string[]=[];
  for(let i=messages.length-1;i>=0;i--){
    const message=messages[i];
    const role=message.role==="user"?"User":"Assistant";
    const line=role+": "+message.text;
    const candidate=[line,...selected];
    if(countTokens(render(candidate.join("\n")))>maxPromptTokens){
      if(selected.length===0){
        const prefix=role+": [earlier content omitted]\n";
        let lo=0,hi=message.text.length;
        while(lo<hi){
          const mid=Math.ceil((lo+hi)/2);
          const excerpt=prefix+message.text.slice(-mid);
          if(countTokens(render(excerpt))<=maxPromptTokens)lo=mid;
          else hi=mid-1;
        }
        if(lo>0)selected.unshift(prefix+message.text.slice(-lo));
      }
      break;
    }
    selected.unshift(line);
  }
  while(selected.length>0 && countTokens(render(selected.join("\n")))>maxPromptTokens)selected.shift();
  return render(selected.join("\n"));
}
