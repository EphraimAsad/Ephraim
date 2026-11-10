export interface TextPage { page: number | null; section?: string | null; text: string }
export interface Chunk { page: number | null; section: string | null; ordinal: number; text: string }
export interface Candidate { id: number; text: string; lexical: number; embedding?: number[] | null }
export interface Ranked { id: number; score: number }
export interface Reference { id: number; title: string; reference: string; version: number }

const collapse = (s: string) => s.replace(/\r/g, "").replace(/[ \t]+/g, " ").trim();
export function chunksFromPages(pages: TextPage[], maxChars = 1700, overlap = 180): Chunk[] {
  if (maxChars < 400 || overlap < 0 || overlap >= maxChars / 2) throw new Error("Invalid chunk settings");
  const chunks: Chunk[] = [];
  for (const page of pages) {
    const text = collapse(page.text);
    let start = 0;
    while (start < text.length) {
      let end = Math.min(start + maxChars, text.length);
      if (end < text.length) {
        const boundary = Math.max(text.lastIndexOf("\n", end), text.lastIndexOf(". ", end));
        if (boundary > start + maxChars * .6) end = boundary + 1;
      }
      const part = text.slice(start, end).trim();
      if (part) chunks.push({ ordinal: chunks.length, page: page.page, section: page.section ?? null, text: part });
      if (end === text.length) break;
      start = Math.max(start + 1, end - overlap);
    }
  }
  return chunks;
}
export function normalizedReference(s:string):string {
  return s.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}]+/gu," ").trim();
}
export function findNamedDocument(question:string, references:Reference[]):Reference|null {
  const q=" "+normalizedReference(question)+" ";
  const matches=references.filter(r=> {
    const ref=normalizedReference(r.reference);
    const title=normalizedReference(r.title.replace(/\.[^.]+$/,""));
    return (ref.length>=4 && q.includes(" "+ref+" ")) || (title.length>=8 && q.includes(" "+title+" "));
  });
  return matches.sort((a,b)=>b.version-a.version||b.reference.length-a.reference.length)[0]??null;
}
export function cosine(a:readonly number[],b:readonly number[]):number {
  if(a.length!==b.length||a.length===0)return 0;
  let dot=0,na=0,nb=0;
  for(let i=0;i<a.length;i++) {dot+=a[i]*b[i];na+=a[i]*a[i];nb+=b[i]*b[i];}
  return na&&nb?dot/Math.sqrt(na*nb):0;
}
export function rerank(candidates:Candidate[],queryEmbedding?:readonly number[],limit=6):Ranked[] {
  const scored=candidates.map(c=>{
    const semantic=queryEmbedding&&c.embedding?Math.max(0,cosine(queryEmbedding,c.embedding)):0;
    const lexical=Math.max(0,c.lexical);
    return {id:c.id,score:queryEmbedding&&c.embedding?(.62*semantic+.38*lexical):lexical};
  });
  return scored.sort((a,b)=>b.score-a.score||a.id-b.id).slice(0,limit);
}
export function isSummaryRequest(question:string):boolean {
  return /\b(summari[sz]e|summary|overview|recap)\b/i.test(question);
}
export async function hierarchicalSummary(
  chunks:readonly string[],
  summarize:(input:string,instruction:string)=>Promise<string>,
  batchChars=6500
):Promise<string> {
  if(chunks.length===0)throw new Error("No text to summarise");
  let parts=chunks.map((s,i)=>"[Section "+(i+1)+"]\n"+s);
  for(let pass=0;pass<6;pass++) {
    const batches:string[]=[];
    let current="";
    for(const part of parts) {
      if(part.length>batchChars)throw new Error("Section exceeds available model context");
      if(current && current.length+part.length+2>batchChars) {batches.push(current);current="";}
      current+=(current?"\n\n":"")+part;
    }
    if(current)batches.push(current);
    if(batches.length===1) {
      return summarize(batches[0],"Summarise the complete document. Preserve the key conditions, numerical values, safety limitations and referenced sections. Include only supported facts.");
    }
    const outputs:string[]=[];
    for(let i=0;i<batches.length;i++) {
      const answer=await summarize(batches[i],"Summarise this portion faithfully. Retain numerical values and section markers; do not invent details.");
      if(answer.length>batchChars*.65)throw new Error("Intermediate summary is too long");
      outputs.push("[Part "+(i+1)+"]\n"+answer);
    }
    if(outputs.join("\n").length>=parts.join("\n").length*.98)throw new Error("Summary did not compress enough for final synthesis");
    parts=outputs;
  }
  throw new Error("Document too long to summarise safely within the available context");
}
