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
  const sections:string[]=[];
  const l=local.slice(0,7),w=web.slice(0,5);
  // Interleaving makes both local and public evidence available even with a
  // small GGUF context window, instead of truncating all web results away.
  for(let i=0;i<Math.max(l.length,w.length);i++){
    if(i<l.length){
      const c=l[i];
      const at=(c.page?" page "+c.page:"")+(c.section?" section "+c.section:"");
      sections.push("[D"+(i+1)+"] "+c.reference+" version "+c.version+at+"\n"+c.excerpt.slice(0,1000));
    }
    if(i<w.length){
      const r=w[i];
      sections.push("[W"+(i+1)+"] "+r.title+"\nURL: "+r.url+
        (r.publishedDate?"\nPublished: "+r.publishedDate:"")+
        "\nExcerpt: "+r.snippet.slice(0,1300));
    }
  }
  return sections.join("\n\n");
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
