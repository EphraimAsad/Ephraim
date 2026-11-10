import type {ConversationMessage} from "./conversation";

export type ResearchMode = "chat"|"local"|"web"|"combined"|"summary";
export interface ResearchPlan { mode:ResearchMode; needLocal:boolean; needWeb:boolean; reason:string; localQueries:string[]; webQueries:string[]; }
const compare=/\b(compare|compared|comparison|versus|vs\.?|alternatives?|other (?:methods|approaches|options)|differences?|advantages?|disadvantages?)\b/i;
const external=/\b(latest|recent|currently|today|this year|online|internet|web|publicly|published|guidelines?|standard(?:s)?|research|look up|search for)\b/i;
const localWords=/\b(document|file|procedure|policy|manual|internal|our method|uploaded|knowledge library|approved version)\b/i;
const followup=/^(?:what about|how about|and |which (?:one|method)|does (?:that|it)|is (?:that|it)|why (?:is|does|would)|what (?:is|are|if)|could (?:it|that)|tell me more|compared with)/i;
const lowSignal=/^(?:hi|hello|hey|thanks|thank you|okay|ok|yes|no|great|good morning|good evening)[!.\s]*$/i;

/** Return public search terms only from the user's own words.
 * Never incorporate local document text, metadata, model tool arguments or generated summaries.
 * The exact outgoing query still requires native user confirmation.
 */
export function publicTerms(text:string,localReferences:readonly string[]):string {
  let s=text.normalize("NFKC").replace(/[\x00-\x1f]/g," ").slice(0,1500);
  for(const ref of localReferences.filter(Boolean).sort((a,b)=>b.length-a.length)){
    const i=s.toLowerCase().indexOf(ref.toLowerCase());
    if(i>=0)s=s.slice(0,i)+" [private reference omitted] "+s.slice(i+ref.length);
  }
  // Internal IDs have no useful meaning on the public web.
  s=s.replace(/\b(?:TP|SOP|WI|DOC)[ -]?[A-Z]*\d+[A-Z0-9./-]*\b/gi," ");
  s=s.replace(/\[private reference omitted\]/gi," ");
  s=s.replace(/\b(?:this document|our procedure|our internal method|our policy|our document|my file)\b/gi," ");
  s=s.replace(/\bl[\s.]*mono(?:cytogenes)?\b/gi,"Listeria monocytogenes");
  s=s.replace(/[^\p{L}\p{N}\s.,:;()/+-]/gu," ");
  return s.replace(/\s+/g," ").trim().slice(0,330);
}
export function recentUserTopic(history:readonly ConversationMessage[]):string {
  return [...history].reverse().filter(x=>x.role==="user").slice(0,4).map(x=>x.text).find(x=>x.length>18&&!lowSignal.test(x))??"";
}
export function buildWebQueries(question:string,history:readonly ConversationMessage[],localReferences:readonly string[]):string[] {
  const base=publicTerms(question,localReferences);
  const prior=publicTerms(recentUserTopic(history),localReferences);
  let q=base;
  if((followup.test(question.trim())||base.length<28) && prior && prior.toLowerCase()!==base.toLowerCase())q=(prior+" "+base).slice(0,400);
  if(q.length<9)return [];
  const queries=[q];
  if(compare.test(question) && q.length>16)queries.push((q+" published alternatives methods validation comparison").slice(0,480));
  return [...new Set(queries)].slice(0,2);
}
export function buildLocalQueries(question:string,history:readonly ConversationMessage[],reference?:string):string[] {
  const recent=recentUserTopic(history);
  return [...new Set([question,reference||"",...(followup.test(question)||question.length<35?[recent]:[])].map(x=>x.trim()).filter(Boolean))].slice(0,3);
}
export function planResearch(
  question:string,history:readonly ConversationMessage[],
  options:{webEnabled:boolean;namedReference?:string|null;localReferences?:readonly string[];hasLocalDocuments:boolean}
):ResearchPlan {
  const named=!!options.namedReference;
  const previousTopic=recentUserTopic(history);
  const recentlyLocal=localWords.test(previousTopic)||
    (options.localReferences??[]).some(ref=>ref.length>=4&&previousTopic.toLowerCase().includes(ref.toLowerCase()));
  const wantLocal=named || localWords.test(question) || (followup.test(question)&&recentlyLocal);
  const wantWeb=options.webEnabled&&(external.test(question) || (compare.test(question)&&(wantLocal||options.hasLocalDocuments)));
  const summary=/\b(summarise|summarize|summary|recap)\b/i.test(question)&&named;
  const mode:ResearchMode=summary&&!wantWeb?"summary":(wantLocal&&wantWeb?"combined":wantLocal?"local":wantWeb?"web":"chat");
  return {mode,needLocal:mode==="local"||mode==="combined"||mode==="summary",
    needWeb:mode==="web"||mode==="combined",
    reason:mode==="combined"?"Local and public evidence requested":mode==="web"?"Public information requested":mode==="local"?"Local document evidence requested":mode==="summary"?"Full named-document summary requested":"General conversation",
    localQueries:buildLocalQueries(question,history,options.namedReference??undefined),
    webQueries:wantWeb?buildWebQueries(question,history,options.localReferences??[]):[]};
}
