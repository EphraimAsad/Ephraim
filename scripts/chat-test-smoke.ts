import { testChat } from "../src/main/runtime";
const model=process.argv[2];
if(!model)throw new Error("Usage: npx tsx scripts/chat-test-smoke.ts path/to/model.gguf");
await testChat(model);
console.log("Ephraim application chat model-test pathway succeeded.");
