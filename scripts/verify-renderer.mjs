import { readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

const output = resolve("out/renderer");
const html = readFileSync(join(output, "index.html"), "utf8");
const matches = Array.from(html.matchAll(/(?:src|href)=(["'])(.*?)\1/g), m => m[2]);
const assets = matches.filter(item => /\.(?:js|css)(?:\?|$)/.test(item));
if (!assets.some(item => item.endsWith(".js"))) throw Error("No renderer JavaScript bundle found");
if (!assets.some(item => item.endsWith(".css"))) throw Error("No renderer stylesheet found");
for (const asset of assets) {
  if (asset.startsWith("/") || asset.includes("://") || asset.includes("..") || !asset.startsWith("./")) {
    throw Error("Packaged renderer has an unsafe or non-relative asset URL");
  }
  if (!existsSync(join(output, asset))) throw Error("Referenced renderer bundle is missing");
}
console.log("Renderer file:// asset paths verified: " + assets.length + " local assets");
