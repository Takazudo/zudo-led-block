import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export function createViewer({ onError }) {
  const $ = (id) => document.getElementById(id);
  const host = $('stage');
  const renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0xe9eee5, 0);
  renderer.outputColorSpace = T.SRGBColorSpace;
  host.append(renderer.domElement);
  const scene = new T.Scene();
  const camera = new T.OrthographicCamera(-70, 70, 70, -70, 0.1, 3000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.minZoom = 0.2;
  controls.maxZoom = 20;
  controls.minDistance = 3;
  controls.maxDistance = 1800;
  const parent = new T.Group();
  // CadQuery GLB adds -90° X; another -90° gives CAD X-right, Y-down, Z-rear -> screen X, -Y, -Z.
  parent.rotation.x = -Math.PI / 2;
  scene.add(parent, new T.HemisphereLight(0xffffff, 0x73826a, 2.8));
  for (const [position, intensity] of [[[80,120,100], 2.6], [[-90,20,-100], 2]]) {
    const light = new T.DirectionalLight(0xffffff, intensity);
    light.position.set(...position); scene.add(light);
  }
  let disposed = false, frame = 0, model = null, manifest = null, variant = null;
  let selected = '', view = 'iso', parts = new Map(), fetchController = null;
  const events = new AbortController();
  const on = (element, event, listener) => element.addEventListener(event, listener, { signal: events.signal });
  function render() {
    if (disposed || frame) return;
    frame = requestAnimationFrame(() => { frame = 0; if (!disposed) renderer.render(scene, camera); });
  }
  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    renderer.setSize(w, h); camera.updateProjectionMatrix();
    if (model) fit(); else render();
  }
  const observer = new ResizeObserver(resize); observer.observe(host);
  controls.addEventListener('change', render);
  on(renderer.domElement, 'webglcontextlost', (event) => { event.preventDefault(); onError(new Error('WebGL context lost')); });
  function free(root) {
    const geometries = new Set(), materials = new Set();
    root?.traverse((o) => { if (o.geometry) geometries.add(o.geometry); if (o.material) for (const m of [].concat(o.material)) materials.add(m); });
    for (const g of geometries) g.dispose();
    for (const m of materials) { for (const v of Object.values(m)) if (v?.isTexture) v.dispose(); m.dispose(); }
  }
  function bounds() {
    parent.updateMatrixWorld(true);
    const box = new T.Box3();
    for (const { object } of parts.values()) if (object.visible) box.union(new T.Box3().setFromObject(object));
    return box;
  }
  function fit(direction) {
    const box = bounds();
    if (box.isEmpty()) { $('status').textContent = '表示部品がありません。すべて表示で戻せます。'; render(); return; }
    const center = box.getCenter(new T.Vector3());
    const dir = direction?.clone() ?? camera.position.clone().sub(controls.target).normalize();
    if (dir.lengthSq() < .1) dir.set(1,.45,1);
    dir.normalize();
    const right = new T.Vector3().crossVectors(camera.up, dir).normalize();
    const up = new T.Vector3().crossVectors(dir, right).normalize();
    const aspect = host.clientWidth / host.clientHeight;
    let halfHeight = 1;
    for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
      const p = new T.Vector3(x,y,z).sub(center);
      halfHeight = Math.max(halfHeight, Math.abs(p.dot(up)), Math.abs(p.dot(right)) / aspect);
    }
    halfHeight *= 1.15;
    camera.left = -halfHeight * aspect; camera.right = halfHeight * aspect;
    camera.top = halfHeight; camera.bottom = -halfHeight; camera.zoom = 1;
    const distance = box.getSize(new T.Vector3()).length() * 2 + 10;
    controls.target.copy(center); camera.position.copy(center).addScaledVector(dir, distance);
    camera.near = .1; camera.far = Math.max(3000, distance * 5); camera.updateProjectionMatrix();
    controls.update(); ready(); render();
  }
  function preset(name) {
    view = name;
    const directions = { iso: [1,1,1], front: [0,0,1], side: [1,0,0], rear: [0,0,-1] };
    fit(new T.Vector3(...directions[name]));
    for (const b of document.querySelectorAll('[data-view]')) b.setAttribute('aria-pressed', String(b.dataset.view === name));
  }
  function ready() { if (variant) $('status').textContent = `表示中 — ${variant.label}`; }
  function inspect(name) {
    selected = name;
    $('part').value = name;
    $('isolate').disabled = !name;
    for (const [key, part] of parts) part.object.traverse((o) => {
      if (o.isMesh) for (const m of [].concat(o.material)) if (m.emissive) m.emissive.setHex(key === name ? 0x244b71 : 0x000000);
    });
    const info = variant?.nodes[name];
    $('part-info').textContent = info ? `${name} — ${info.role} 形状区分: ${info.kind}（設計モデル・実物未確認）` : 'クリック、または一覧から部品を選んでください。';
    render();
  }
  function visibility() {
    const enabled = new Set([...$('groups').querySelectorAll('input:checked')].map((e) => e.value));
    for (const part of parts.values()) part.object.visible = enabled.has(part.group);
    if (selected && !parts.get(selected)?.object.visible) inspect('');
    fit();
  }
  function explode() {
    const amount = $('explode').checked ? 1 : 0;
    for (const part of parts.values()) {
      part.object.position.copy(part.original);
      const offset = new T.Vector3(...manifest.groups[part.group].explode);
      if (part.group === 'leaves' || part.group === 'diffusers') offset.x *= part.name.startsWith('left') ? -1 : 1;
      // Offsets are defined in display coordinates; preserve the GLB's assembled transforms.
      const inverse = part.object.parent.getWorldQuaternion(new T.Quaternion()).invert();
      part.object.position.add(offset.multiplyScalar(amount).applyQuaternion(inverse));
    }
    fit();
  }
  function reset() {
    $('explode').checked = false;
    for (const input of $('groups').querySelectorAll('input')) input.checked = true;
    for (const part of parts.values()) { part.object.visible = true; part.object.position.copy(part.original); }
    inspect(''); preset('iso');
  }
  on($('part'), 'change', () => inspect($('part').value));
  on($('groups'), 'change', visibility);
  on($('explode'), 'change', explode);
  on($('fit'), 'click', () => fit());
  on($('reset'), 'click', reset);
  on($('show-all'), 'click', () => { for (const e of $('groups').querySelectorAll('input')) e.checked = true; visibility(); });
  on($('isolate'), 'click', () => {
    if (!selected) return;
    const group = parts.get(selected).group;
    for (const e of $('groups').querySelectorAll('input')) e.checked = e.value === group;
    visibility();
  });
  for (const b of document.querySelectorAll('[data-view]')) on(b, 'click', () => preset(b.dataset.view));
  let down = null;
  on(renderer.domElement, 'pointerdown', (e) => { down = [e.clientX,e.clientY]; });
  on(renderer.domElement, 'pointerup', (e) => {
    if (!down || Math.hypot(e.clientX-down[0],e.clientY-down[1]) > 5) return;
    const rect = renderer.domElement.getBoundingClientRect();
    const ray = new T.Raycaster();
    ray.setFromCamera(new T.Vector2((e.clientX-rect.left)/rect.width*2-1, -(e.clientY-rect.top)/rect.height*2+1),camera);
    const hits = ray.intersectObjects([...parts.values()].filter((p) => p.object.visible).map((p) => p.object), true);
    let hit = hits[0]?.object;
    while (hit && !hit.userData.partName) hit = hit.parent;
    if (hit) inspect(hit.userData.partName);
  });
  on(host, 'keydown', (e) => {
    if (!model) return;
    const offset = camera.position.clone().sub(controls.target);
    if (['+','=','-'].includes(e.key)) { camera.zoom = T.MathUtils.clamp(camera.zoom * (e.key === '-' ? 1/1.1 : 1.1), controls.minZoom, controls.maxZoom); camera.updateProjectionMatrix(); }
    else if (e.key.startsWith('Arrow')) {
      const x = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0;
      const y = e.key === 'ArrowUp' ? 1 : e.key === 'ArrowDown' ? -1 : 0;
      if (e.shiftKey) {
        const move = new T.Vector3(x * 3, y * 3, 0).applyQuaternion(camera.quaternion);
        controls.target.add(move); camera.position.add(move);
      } else {
        const s = new T.Spherical().setFromVector3(offset); s.theta += x*.12; s.phi -= y*.12; s.makeSafe(); offset.setFromSpherical(s);
      }
    } else return;
    e.preventDefault(); camera.position.copy(controls.target).add(offset); controls.update(); render();
  });
  async function fetchFile(url, signal, binary = false) {
    const response = await fetch(url, { signal });
    if (!response.ok) throw new Error(`モデル読込 HTTP ${response.status}`);
    return binary ? response.arrayBuffer() : response.json();
  }
  async function load(id) {
    fetchController?.abort(); fetchController = new AbortController();
    const request = fetchController;
    const timer = setTimeout(() => request.abort(), 25000);
    $('status').textContent = 'モデルを読み込み中…';
    try {
      manifest ??= await fetchFile('./manifest.json', request.signal);
      const next = manifest.variants.find((v) => v.variant === id);
      if (!next) throw new Error('Unknown variant');
      const bytes = await fetchFile('./' + next.target, request.signal, true);
      const gltf = await new GLTFLoader().parseAsync(bytes, '');
      if (disposed || request.signal.aborted) { free(gltf.scene); return; }
      free(model); if (model) parent.remove(model);
      model = gltf.scene; parent.add(model); variant = next; parts = new Map();
      const importedMaterials = new Set();
      model.traverse((o) => { if(o.material) for(const m of [].concat(o.material)) importedMaterials.add(m); });
      model.traverse((object) => {
        const index = gltf.parser.associations.get(object)?.nodes;
        const name = index === undefined ? null : gltf.parser.json.nodes[index].name;
        if (!name || !next.nodes[name]) return;
        object.userData.partName = name;
        object.traverse((o) => { if (o.isMesh) {
          o.material = [].concat(o.material).map((m) => { const copy = m.clone(); copy.side = T.DoubleSide; if (copy.opacity < 1) { copy.transparent = true; copy.depthWrite = false; } return copy; });
          if (o.material.length === 1) o.material = o.material[0];
        }});
        parts.set(name, {name, object, original: object.position.clone(), group: next.nodes[name].group});
      });
      for (const material of importedMaterials) material.dispose();
      if (parts.size !== Object.keys(next.nodes).length) throw new Error('部品対応表とモデルが一致しません');
      $('groups').replaceChildren();
      for (const [key, group] of Object.entries(manifest.groups)) {
        const label = document.createElement('label'); label.className = 'check';
        const input = document.createElement('input'); input.type = 'checkbox'; input.value = key; input.checked = true;
        label.append(input, document.createTextNode(group.label)); $('groups').append(label);
      }
      $('part').replaceChildren(new Option('部品を選択',''), ...[...parts.keys()].map((n) => new Option(n,n)));
      $('dimensions').textContent = `前面 ${next.width_mm} × ${manifest.height_mm} mm / PMMA ${manifest.pmma_mm} mm。奥行き目標 ${manifest.depth_target_mm} mm（PMMA 裏面から、実測寸法ではありません）`;
      $('source').textContent = `モデル出典: ${manifest.source_revision} / SHA-256 ${next.sha256} / ${next.bytes.toLocaleString()} bytes / mm`;
      reset(); resize();
    } finally { clearTimeout(timer); }
  }
  function dispose() {
    if (disposed) return;
    disposed = true; fetchController?.abort(); events.abort(); observer.disconnect();
    cancelAnimationFrame(frame); controls.removeEventListener('change',render); controls.dispose();
    free(model); scene.clear(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
  }
  resize();
  return { load, dispose };
}
