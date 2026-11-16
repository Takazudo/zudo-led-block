const $ = (id) => document.getElementById(id);
let active = null;
let generation = 0;
let loading = false;
function close() {
  generation++;
  loading = false;
  active?.dispose();
  active = null;
  $('poster').hidden = false;
  $('axis').hidden = true;
  $('close').hidden = true;
  $('controls').disabled = true;
  $('variant').disabled = true;
  $('start').disabled = false;
  $('status').textContent = '待機中 — 開始するまで 3D は読み込みません';
}
async function start() {
  if (active || loading) return;
  loading = true;
  const token = ++generation;
  $('start').disabled = true;
  $('error').hidden = true;
  $('close').hidden = false;
  $('status').textContent = '読み込み中…';
  try {
    const { createViewer } = await import('./scene.js');
    if (token !== generation) return;
    active = createViewer({ onError: fail });
    await active.load($('variant').value);
    if (token !== generation) return;
    loading = false;
    $('poster').hidden = true;
    $('axis').hidden = false;
    $('variant').disabled = false;
    $('controls').disabled = false;
    $('stage').focus();
  } catch (error) { if (token === generation) fail(error); }
}
function fail(error) {
  close();
  $('error').textContent = '3D を表示できません。WebGL 対応を確認して再試行するか、下の「側面図を見る」を利用してください。' + (error?.message ? ` (${error.message})` : '');
  $('error').hidden = false;
  $('status').textContent = '読み込みエラー';
}
$('start').addEventListener('click', start);
$('close').addEventListener('click', () => { close(); $('start').focus(); });
$('variant').addEventListener('change', async () => {
  if (!active) return;
  const token = generation;
  $('controls').disabled = true;
  $('variant').disabled = true;
  try { await active.load($('variant').value); if (token === generation) { $('controls').disabled = false; $('variant').disabled = false; } }
  catch (error) { if (token === generation) fail(error); }
});
window.addEventListener('pagehide', close);
