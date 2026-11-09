import { readFileSync, statSync } from "node:fs";
import { extname } from "node:path";
import mammoth from "mammoth";
import ExcelJS from "exceljs";
export async function extractText(path:string):Promise<string> {
  if(statSync(path).size>15_000_000) throw new Error("Files over 15 MB are not supported");
  const ext=extname(path).toLowerCase();
  if([".txt",".md",".csv",".json"].includes(ext))return readFileSync(path,"utf8");
  if(ext===".docx")return (await mammoth.extractRawText({path})).value;
  if(ext===".pdf") {
    const { PDFParse }=await import("pdf-parse");
    const parser=new PDFParse({data:new Uint8Array(readFileSync(path))});
    try {return (await parser.getText()).text;} finally {await parser.destroy();}
  }
  if(ext===".xlsx") {
    const workbook=new ExcelJS.Workbook(); await workbook.xlsx.readFile(path);
    const pieces:string[]=[];
    workbook.eachSheet(sheet=>{
      pieces.push("# "+sheet.name);
      sheet.eachRow(row=>pieces.push(row.values?.toString()??""));
    });
    return pieces.join("\n");
  }
  throw new Error("Unsupported file format");
}
