/* Scene identity, stage controls and URL handling have no research/data dependencies. */
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
export function safeURL(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value, location.href);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    return url.href;
  } catch { return null; }
}
export function bindResearchMeshNodes(meshes) {
  for (const mesh of meshes) if (mesh.userData?.part) {
    mesh.userData.legacy_bom_id = mesh.userData.part;
    mesh.userData.node_id = "part:" + mesh.userData.part;
    mesh.userData.representation = "conceptual";
  }
}
export function installStageControl(stages, slider, apply) {
  const select = element("select", "rg-stage-control"); select.setAttribute("aria-label", "选择拆解阶段");
  stages.forEach(([at, title]) => {
    const option = element("option", "", title); option.value = String(Math.round(at * 100)); select.append(option);
  });
  select.addEventListener("change", () => { slider.value = select.value; slider.dispatchEvent(new Event("input", { bubbles: true })); });
  const sync = () => {
    let selected = stages[0]?.[0] || 0;
    for (const [at] of stages) if (Number(slider.value) / 100 >= at) selected = at;
    select.value = String(Math.round(selected * 100));
  };
  slider.addEventListener("input", sync);
  slider.insertAdjacentElement("afterend", select); sync();
  return sync;
}
