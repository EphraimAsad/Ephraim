import {generate} from "../src/main/runtime";
const model=process.argv[2];
if(!model)throw new Error("Provide a local test GGUF path");
const answer=await generate(model,
  "In one short sentence, what does the supplied synthetic source say?",
  "[D1] Synthetic source: The sample instrument operates at 25 degrees.",
  [{role:"user",text:"We are discussing a synthetic instrument."}],
  {contextSize:2048,maxTokens:96,memorySummary:"Discussion concerns a fictional demonstration only."}
);
if(!answer.trim())throw new Error("A conversational evidence prompt produced no text");
console.log("Ephraim conversational evidence smoke test passed");
