import type {WebResult} from "./research";
export interface LocalPassage { id:number; documentId:number;reference:string;version:number; page:number|null;section?:string|null;excerpt:string }
export function selectPassages<T extends LocalPassage>(items:readonly T[],query:string,limit=8):T[] {
  const words=new Set((query.toLowerCase().match(/[\p{L}\p{N}]{4,}/gu)||[]).filter(x=>!["what","does","with","from","other","would","could","that","this","about"].includes(x)));
  const seen=new Set<number>();
  return items.map((c,i)=>{
    const t=(c.reference+" "+c.section+" "+c.excerpt).toLowerCase();
    const hit=[...words].reduce((n,w)=>n+(t.includes(w)?1:0),0);
    return {c,order:i,score:hit+(i<3?0.01:0)};
  }).sort((a,b)=>b.score-a.score||a.order-b.order).filter(({c})=>{
    if(seen.has(c.id))return false;seen.add(c.id);return true;
  }).slice(0,Math.max(1,limit)).map(x=>x.c);
}
export function composeEvidence<T extends LocalPassage>(local:readonly T[],web:readonly WebResult[]):string {
  const doc=local.slice(0,8).map((c,i)=>{
    const at=(c.page?" page "+c.page:"")+(c.section?" section "+c.section:"");
    return "[D"+(i+1)+"] "+c.reference+" version "+c.version+at+"\n"+c.excerpt.slice(0,1300);
  }).join("\n\n");
  const external=web.slice(0,5).map((r,i)=>"[W"+(i+1)+"] "+r.title+
    "\nURL: "+r.url+(r.publishedDate?"\nPublished: "+r.publishedDate:"")+
    "\nExcerpt: "+r.snippet.slice(0,1400)).join("\n\n");
  return [doc,external].filter(Boolean).join("\n\n");
}
/** This catches fabricated reference labels; it cannot verify the factual entailment of a claim. */
export function validateCitationLabels(answer:string,localCount:number,webCount:number):{answer:string;invalid:string[]} {
  const invalid:string[]=[];
  const cleaned=answer.replace(/\[([DW])(\d{1,4})\]/g,(label:string,kind:string,num:string)=>{
    const n=Number(num);const limit=kind==="D"?localCount:webCount;
    if(n>0&&n<=limit)return label;
    invalid.push(label);
    return "[unverified source]";
  });
  return {answer:cleaned,invalid:[...new Set(invalid)]};
}
