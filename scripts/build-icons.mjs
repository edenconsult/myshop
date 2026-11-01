// Builds static/icons/sprite.svg from the icons the templates ask for.
// Names come from {% icon 'name' %} calls, so the sprite only ships what is used.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import iconData from "@iconify-json/material-symbols/icons.json" with { type: "json" };

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "static", "icons", "sprite.svg");
const iconCall = /\{%-?\s*icon\s+["']([a-z0-9_]+)["']/g;
const fontSpan = /class="[^"]*material-symbols-outlined[^"]*"/;

function htmlFiles(dir, found = []) {
  for (const entry of readdirSync(dir)) {
    if (["node_modules", ".git", ".venv", "__pycache__", "CACHE"].includes(entry)) continue;
    const path = join(dir, entry);
    const stats = statSync(path);
    if (stats.isDirectory()) htmlFiles(path, found);
    else if (entry.endsWith(".html")) found.push(path);
  }
  return found;
}

const names = new Set();
const stale = [];
for (const file of htmlFiles(root)) {
  const text = readFileSync(file, "utf8");
  for (const match of text.matchAll(iconCall)) names.add(match[1]);
  if (fontSpan.test(text)) stale.push(relative(root, file));
}

if (names.size === 0) {
  console.error("No {% icon %} calls found in any template — refusing to write an empty sprite.");
  process.exit(1);
}

const symbols = [];
const missing = [];
for (const name of [...names].sort()) {
  const key = name.replaceAll("_", "-");
  const alias = iconData.aliases?.[key];
  const icon = iconData.icons[key] ?? (alias ? iconData.icons[alias.parent] : undefined);
  if (!icon) {
    missing.push(name);
    continue;
  }
  const box = icon.viewBox ?? { minX: 0, minY: 0, width: 24, height: 24 };
  symbols.push(
    `  <symbol id="${name}" viewBox="${box.minX} ${box.minY} ${box.width} ${box.height}">${icon.body}</symbol>`,
  );
}

if (missing.length) {
  console.error(`Unknown Material Symbols name(s): ${missing.join(", ")}`);
  process.exit(1);
}

mkdirSync(dirname(out), { recursive: true });
writeFileSync(
  out,
  `<svg xmlns="http://www.w3.org/2000/svg" style="display: none">\n${symbols.join("\n")}\n</svg>\n`,
);

console.log(`sprite: ${symbols.length} icons -> ${relative(root, out)}`);
if (stale.length) {
  console.warn(
    `WARNING: icon-font markup still present in:\n  ${stale.join("\n  ")}`,
  );
}
