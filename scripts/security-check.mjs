import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
const files=execFileSync("git",["ls-files","-z"]).toString().split("\0").filter(Boolean);
const badNames=/(^|\/)(\.env($|\.)|id_rsa|credentials\.json|private-data|secrets|user-data)(\/|$)/i;
const badExt=/\.(gguf|sqlite3?|db|pem|p12|pfx|key)$/i;
const badContent=[
 /-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----/,
 /(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}/,
 /(?:sk-proj-|sk_live_)[A-Za-z0-9_-]{20,}/,
 /(?:tvly-)[A-Za-z0-9_-]{25,}/,
 /AKIA[0-9A-Z]{16}/
];
const errors=[];
for(const file of files) {
 if(badNames.test(file)||badExt.test(file)){errors.push("Sensitive path: "+file);continue;}
 if(!/\.(tsx?|mjs|jsx?|json|ya?ml|md|html|css|txt)$/.test(file))continue;
 const text=readFileSync(file,"utf8");
 if(badContent.some(re=>re.test(text)))errors.push("Potential secret in "+file);
}
if(errors.length){console.error(errors.join("\n"));process.exit(1);}
console.log("Tracked-file secret patterns passed (not a historical audit).");
