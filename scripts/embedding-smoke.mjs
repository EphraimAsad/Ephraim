import {getLlama} from "node-llama-cpp";
import {readFileSync} from "node:fs";
const modelPath=process.argv[2];
if(!modelPath||readFileSync(modelPath).subarray(0,4).toString()!=="GGUF")throw new Error("Valid local embedding GGUF required");
const llama=await getLlama({gpu:false,build:"never"});
const model=await llama.loadModel({modelPath});
const context=await model.createEmbeddingContext({contextSize:512,batchSize:512});
try{
  const first=Array.from((await context.getEmbeddingFor("The sample was incubated at 37 degrees Celsius.")).vector);
  const second=Array.from((await context.getEmbeddingFor("The sample was incubated at 37 degrees Celsius.")).vector);
  if(first.length<32||first.length!==second.length||!first.every(Number.isFinite))throw new Error("Invalid embedding vector");
  const distance=first.reduce((a,v,i)=>a+Math.abs(v-second[i]),0);
  if(distance>1e-3)throw new Error("Repeated embedding was not reproducible");
  console.log("Real GGUF embeddings succeeded; dimensions: "+first.length);
}finally{await context.dispose();await model.dispose();}
