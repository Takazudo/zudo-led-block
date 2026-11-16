import { build } from 'esbuild';
import { copyFile, readFile } from 'node:fs/promises';
const pkg = JSON.parse(await readFile('node_modules/three/package.json', 'utf8'));
if (pkg.version !== '0.180.0') throw new Error('Review Three.js pin before rebuilding');
await build({ entryPoints: ['preview/a7/scene.js'], outfile: 'doc/public/a7-preview/scene.js', bundle: true, format: 'esm', minify: true, legalComments: 'inline', target: 'es2022' });
await copyFile('node_modules/three/LICENSE', 'doc/public/a7-preview/THREE-LICENSE.txt');
console.log('PASS bundled Three.js ' + pkg.version + ' with MIT licence');
