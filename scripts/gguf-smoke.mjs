import { getLlama, LlamaChatSession } from "node-llama-cpp";
import { readFileSync } from "node:fs";
const file=process.argv[2];
if(!file)throw new Error("Usage: node scripts/gguf-smoke.mjs ./path/to/test.gguf");
if(readFileSync(file).subarray(0,4).toString()!=="GGUF")throw new Error("Invalid GGUF test asset");
const llama=await getLlama({gpu:false,build:"never"});
const model=await llama.loadModel({modelPath:file});
const context=await model.createContext({contextSize:1024});
try{
  const session=new LlamaChatSession({contextSequence:context.getSequence()});
  let streamed="";let chunks=0;
  const answer=await session.prompt("Return one word describing the colour of grass.",{maxTokens:30,onTextChunk:(part)=>{streamed+=part;chunks++;}});
  if(!answer.trim())throw new Error("Local GGUF model produced an empty answer");
  if(chunks<1 || !streamed.trim())throw new Error("GGUF token streaming produced no updates");
  console.log("Real GGUF CPU inference and streaming succeeded; response length: "+answer.length+", chunk events: "+chunks);
}finally{
  await context.dispose();
  await model.dispose();
}
