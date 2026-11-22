// Builds a single self-contained HTML file of the A7 preview for offline use (no server, no hosting).
// Usage: node scripts/a7-preview-offline.mjs <out.html>
import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';

const out = process.argv[2];
if (!out) throw new Error('usage: node scripts/a7-preview-offline.mjs <out.html>');
const pkg = JSON.parse(await readFile('node_modules/three/package.json', 'utf8'));
if (pkg.version !== '0.180.0') throw new Error('Review Three.js pin before rebuilding');

const sha = (b) => createHash('sha256').update(b).digest('hex');
const manifestText = await readFile('preview/a7/manifest.json', 'utf8');
const manifest = JSON.parse(manifestText);
const files = { './manifest.json': manifestText };
for (const v of manifest.variants) {
  const bytes = await readFile('doc/public/a7-preview/' + v.target);
  if (sha(bytes) !== v.sha256) throw new Error('GLB does not match manifest; run pnpm preview:build: ' + v.target);
  files['./' + v.target] = bytes.toString('base64');
}
const bundle = await build({
  entryPoints: ['preview/a7/boot.js'], bundle: true, write: false, format: 'iife', minify: true,
  legalComments: 'inline', target: 'es2022',
});
const js = bundle.outputFiles[0].text.replaceAll('</script', '<\\/script');
const css = await readFile('preview/a7/viewer.css', 'utf8');
const poster = (await readFile('doc/public/a7-preview/poster.png')).toString('base64');
const licence = await readFile('node_modules/three/LICENSE', 'utf8');
let html = await readFile('preview/a7/index.html', 'utf8');
const replace = (from, to) => {
  if (!html.includes(from)) throw new Error('offline template drift: ' + from);
  html = html.replace(from, to);
};
replace('<link rel="stylesheet" href="./viewer.css">', `<style>${css}</style>`);
replace('src="./poster.png"', `src="data:image/png;base64,${poster}"`);
replace('<script type="module" src="./boot.js"></script>',
  `<script>globalThis.A7_OFFLINE_FILES=${JSON.stringify(files)};</script><script>${js}</script>`);
html = html.replace('<main>', `<main><p class="notice">オフライン単体版（ローカルで開くファイル）。source revision ${manifest.source_revision}。サイト内リンクは公開サイト用で、このファイル単体では開けません。</p>`);
html = html.replace('</body>', `<!-- Three.js ${pkg.version} licence:\n${licence.replaceAll('--', '- -')}\n--></body>`);
await writeFile(out, html);
console.log(`PASS offline preview ${out} ${Buffer.byteLength(html)} bytes sha256 ${sha(html)}`);
