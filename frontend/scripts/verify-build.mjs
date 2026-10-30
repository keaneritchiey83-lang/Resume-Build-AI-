// Check the actual Vite production bundle without requiring any extra packages.
import { existsSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const dist = resolve(import.meta.dirname, "../dist");
const index = join(dist, "index.html");
if (!existsSync(index)) {
  throw new Error("Missing dist/index.html. Run npm run build first.");
}
const html = readFileSync(index, "utf8");
if (!html.includes("Global Career Architecture AI")) {
  throw new Error("Production index is missing the application title.");
}
const assets = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+)"/g)]
  .map((match) => match[1]);
if (!assets.some((asset) => asset.endsWith(".js"))) {
  throw new Error("Vite did not emit a production JavaScript bundle.");
}
for (const asset of assets) {
  const assetFile = join(dist, asset);
  if (!existsSync(assetFile) || statSync(assetFile).size === 0) {
    throw new Error(`Missing or empty production asset: ${asset}`);
  }
}
console.log(`PASS: frontend production bundle includes ${assets.length} referenced assets`);
