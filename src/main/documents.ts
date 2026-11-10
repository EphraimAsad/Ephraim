import { readFileSync, statSync } from "node:fs";
import { extname } from "node:path";
import mammoth from "mammoth";
import ExcelJS from "exceljs";
import type { TextPage } from "../core/knowledge";
const MAX_FILE = 15_000_000;
export async function extractPages(path:string):Promise<TextPage[]> {
  if(statSync(path).size>MAX_FILE)throw new Error("File exceeds 15 MB");
  const ext=extname(path).toLowerCase();
  if([".txt",".md",".csv"].includes(ext))return [{page:null,text:readFileSync(path,"utf8")}];
  if(ext===".docx") {
    const result=await mammoth.extractRawText({path});
    return [{page:null,text:result.value}];
  }
  if(ext===".xlsx") {
    const wb=new ExcelJS.Workbook();
    await wb.xlsx.readFile(path);
    const sections:TextPage[]=[];
    wb.eachSheet(sheet=>{
      const lines:string[]=[];
      sheet.eachRow(row=>lines.push((row.values as any[]).slice(1).map(v=>typeof v==="object"?JSON.stringify(v):String(v??"")).join(" | ")));
      sections.push({page:null,section:sheet.name,text:lines.join("\n")});
    });
    return sections;
  }
  if(ext===".pdf") {
    const { PDFParse }=await import("pdf-parse");
    const parser=new PDFParse({data:new Uint8Array(readFileSync(path))});
    try {
      // Extract each page separately so citations correspond to source PDF pages.
      const info=await parser.getInfo();
      const total=info.total??0;
      if(total>500)throw new Error("PDF exceeds 500 pages");
      const pages:TextPage[]=[];
      for(let p=1;p<=total;p++){
        const result=await parser.getText({partial:[p],pageJoiner:""});
        pages.push({page:p,text:result.text});
      }
      return pages;
    }finally{await parser.destroy();}
  }
  throw new Error("Unsupported document type");
}
