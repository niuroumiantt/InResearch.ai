/* Shared, read-only research UI. Identity comes from the API; no module-wide
   task counts or marketing documents are promoted to object-level evidence. */
const VIEW_INFO = {
  P: ["物理结构", "空间、装配与部件"],
  F: ["功能系统", "电力、冷却与数据流"],
  V: ["产业价值链", "制造、持有与运营"],
  D: ["需求传导", "应用、模型与算力"],
  R: ["研究问题", "证据、陈述与缺口"]
};
const RELATION_LABELS = {
  part_of: "装配属于", contains: "包含", spatially_contains: "空间包含",
  located_in: "位于", contains_space: "空间包含", has_part: "包含部件",
  member_of_system: "参与系统", supplies_power_to: "供电给",
  coolant_flows_to: "冷却液流向", transfers_heat_to: "传热给", cools: "冷却",
  port_connected_to: "端口连接", connected_to: "连接", carries_data_to: "数据通路",
  manufactured_by: "制造方", owned_by: "所有方", operated_by: "运营方",
  leased_to: "出租给", deployed_on: "部署于", consumes_capacity_from: "使用算力",
  monitors: "监测", controls: "控制", maps_to: "映射", researches: "研究",
  supplies: "供应", depends_on: "依赖", drives_demand: "需求传导",
  supports: "支持", contradicts: "矛盾", instance_of: "型号/类型",
  references: "参考", serves: "服务", uses: "使用", research_scope: "研究归属",
  powers: "供电给", requires: "需要", demand_transmission: "需求传导"
};
const STATUS_LABELS = {
  unknown: "未知", open: "待研究", gap: "证据缺口", pending: "待处理",
  planned: "计划中", unanswered: "待回答", in_progress: "进行中",
  partial: "部分完成", supported: "有证据支持", verified: "已核实",
  answered: "已有回答", complete: "已完成", completed: "已完成",
  accepted: "已验收", conflict: "存在冲突", disputed: "有争议",
  draft: "草稿", candidate: "候选", needs_review: "待复核", needs_evidence: "待补证据",
  not_disclosed: "未披露", not_applicable: "不适用", missing: "缺失",
  downloaded: "已下载", needs_manual: "需人工处理", superseded: "已被替代",
  blocked: "待解除阻塞", not_connected: "尚未连接", running: "运行中", idle: "空闲",
  failed: "失败", stopped: "已停止", legacy_metadata: "旧资料索引", unverified: "未核实"
};
const TYPE_LABELS = {
  component_type: "部件类别", physical_type: "物理类别", asset_instance: "现场资产",
  asset: "资产对象", site: "园区", building: "建筑", space: "空间",
  system: "系统", system_instance: "系统实例", product_variant: "产品型号",
  product: "产品", company: "公司", role: "角色", value_chain: "产业环节",
  industry: "产业", demand: "需求", workload: "工作负载",
  research: "研究主题", question: "研究问题", reference: "参考对象",
  conceptual: "概念对象", assembly: "装配", component: "部件",
  physical: "物理对象", functional_system: "功能系统", research_scope: "研究范围",
  space_type: "空间类型", workload_type: "工作负载", resource: "资源",
  demand_scope: "需求层", activity_scope: "产业活动", software: "软件", technology: "技术路线"
};
const REQUIREMENT_LABELS = {
  primary_source: "一手来源", locator: "原文页/节/表定位", scope: "适用范围",
  definition: "定义", composition: "组成", interface_spec: "接口规格",
  units: "单位与口径", conditions: "适用条件", test_method: "测试方法",
  operating_conditions: "运行工况", counterevidence: "反面及冲突证据",
  alternatives: "替代方案", comparable_scope: "同口径比较", tradeoffs: "取舍",
  supply_chain: "供应链", cost_boundary: "成本边界", time_region: "时间与区域"
};
const requirementsText = value => Array.isArray(value) ? [...new Set(value)].map(x => REQUIREMENT_LABELS[x] || x).join(" · ") : value;
const list = value => Array.isArray(value) ? value : Array.isArray(value?.records) ? value.records : [];
const strings = value => (Array.isArray(value) ? value : value == null ? [] : [value])
  .map(x => typeof x === "string" ? x : x?.id || x?.object_id || "").filter(Boolean);
const recId = row => String(row?.id || row?.document_id || row?.doc_id || row?.source_id || row?.evidence_id || row?.statement_id || row?.answer_id || row?.task_id || row?.wid || "");
const present = value => value !== undefined && value !== null && value !== "";
const readable = value => typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "");
const normalize = value => String(value ?? "").normalize("NFKC").toLocaleLowerCase().trim();
const statusText = value => STATUS_LABELS[value] || value || "未知";
const typeText = value => TYPE_LABELS[value] || value || "未分类";
const relText = value => RELATION_LABELS[value] || value || "关系类型未知";
const refs = row => [...strings(row?.object_ids), ...strings(row?.object_id), ...strings(row?.node_id), ...strings(row?.node_ids), ...strings(row?.subject_id), ...strings(row?.target_object_id)];
const fieldRefs = (row, fields) => fields.flatMap(k => strings(row?.[k]));
function element(tag, cls, text) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
}
function button(text, fn, cls = "rg-button") {
  const el = element("button", cls, text); el.type = "button"; el.addEventListener("click", fn); return el;
}
export function researchHref(id, view = "P", tab = "relations") {
  const q = new URLSearchParams({ node: id, view, tab });
  return "research.html?" + q.toString();
}
export function safeURL(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value, location.href);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    return url.href;
  } catch { return null; }
}
function link(text, url, cls = "rg-link-button") {
  const target = safeURL(url);
  if (!target) return element("span", "rg-muted", text + "（链接不可用）");
  const a = element("a", cls, text); a.href = target;
  if (new URL(target).origin !== location.origin) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
  return a;
}
function chip(text, tone) {
  const el = element("span", "rg-chip", text); if (tone) el.dataset.tone = tone; return el;
}
function representation(value) {
  const raw = typeof value === "object" ? value?.kind || value?.status || value?.type : value;
  const labels = {
    actual_verified: ["现场已核实", "green"], verified_instance: ["现场已核实", "green"],
    actual: ["现场对象 · 依据见记录", "blue"], instance: ["现场对象 · 依据见记录", "blue"],
    vendor_reference: ["厂商参考 · 实装未知", "blue"], reference: ["参考对象 · 实装未知", "blue"],
    conceptual: ["概念示意 · 实装未知", "gold"], concept: ["概念示意 · 实装未知", "gold"],
    unknown_placeholder: ["未知占位", "gold"], unknown: ["依据状态未知", "gold"]
  };
  return labels[raw] || [raw ? "依据状态：" + raw : "依据状态未知", "gold"];
}
function fields(rows) {
  const dl = element("dl", "rg-fields");
  for (const [label, value] of rows) if (present(value)) {
    dl.append(element("dt", "", label), element("dd", "", readable(value)));
  }
  return dl;
}
let pendingResearch;
export async function loadResearch({ refresh = false } = {}) {
  if (refresh) pendingResearch = null;
  if (!pendingResearch) pendingResearch = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("/api/research", { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("研究服务返回 HTTP " + response.status);
      const data = await response.json();
      if (!data?.graph || !Array.isArray(data.graph.objects) || !Array.isArray(data.graph.relations))
        throw new Error("研究服务返回的数据结构不完整");
      return data;
    } finally { clearTimeout(timer); }
  })().catch(error => { pendingResearch = null; throw error; });
  return pendingResearch;
}
export function buildResearchIndex(data) {
  const objects = list(data.graph?.objects), relations = list(data.graph?.relations);
  const questions = list(data.questions), knowledge = data.knowledge || {};
  const documents = list(knowledge.documents), evidence = list(knowledge.evidence);
  const statements = list(knowledge.statements), answers = list(knowledge.answers), tasks = list(data.tasks);
  const byId = new Map(objects.map(o => [o.id, o]));
  const evidenceById = new Map(evidence.map(e => [recId(e), e]));
  const documentById = new Map();
  documents.forEach(d => fieldRefs(d, ["id", "doc_id", "source_id"]).forEach(id => documentById.set(id, d)));
  const adjacency = new Map(objects.map(o => [o.id, []]));
  for (const relation of relations) {
    adjacency.get(relation.source)?.push(relation);
    if (relation.target !== relation.source) adjacency.get(relation.target)?.push(relation);
  }
  function forNode(id) {
    const qs = questions.filter(q => refs(q).includes(id));
    const qids = new Set(qs.map(recId));
    const questionLinked = row => fieldRefs(row, ["question_id", "question_ids"]).some(x => qids.has(x));
    const directOrQuestion = row => refs(row).includes(id) || questionLinked(row);
    const aa = answers.filter(directOrQuestion);
    const statementIds = new Set(aa.flatMap(r => fieldRefs(r, ["statement_id", "statement_ids"])));
    const ss = statements.filter(r => directOrQuestion(r) || statementIds.has(recId(r)));
    const eids = new Set([...ss, ...aa].flatMap(r => fieldRefs(r, ["evidence_id", "evidence_ids"])));
    const rs = adjacency.get(id) || [];
    rs.forEach(r => fieldRefs(r, ["evidence_id", "evidence_ids"]).forEach(x => eids.add(x)));
    const ee = evidence.filter(e => directOrQuestion(e) || eids.has(recId(e)));
    const dids = new Set([...ee, ...ss, ...aa].flatMap(r => fieldRefs(r, ["document_id", "document_ids", "doc_id", "source_id"])));
    const dd = documents.filter(d => directOrQuestion(d) || fieldRefs(d, ["id", "doc_id", "source_id"]).some(x => dids.has(x)));
    return { questions: qs, statements: ss, answers: aa, evidence: ee, documents: dd,
      tasks: tasks.filter(directOrQuestion), relations: rs };
  }
  return { objects, relations, questions, documents, evidence, statements, answers, tasks,
    byId, evidenceById, documentById, adjacency, forNode };
}
function viewOfRelation(r) {
  const explicit = strings(r.views || r.view_ids || r.view);
  if (explicit.length) return explicit;
  if (/power|cool|heat|data|connect|system|monitor|control|flow/.test(r.type)) return ["F"];
  if (/manufactur|owned|operat|leased|suppl|value|role|sell|procure/.test(r.type)) return ["V"];
  if (/demand|deploy|capacity|workload|consum|use|requires/.test(r.type)) return ["D"];
  if (/research|question|evidence|support|contradict/.test(r.type)) return ["R"];
  return ["P"];
}
function objectViews(o, index) {
  const direct = strings(o.views || o.view_ids || o.view);
  const via = (index.adjacency.get(o.id) || []).flatMap(viewOfRelation);
  const qv = index.questions.filter(q => refs(q).includes(o.id)).flatMap(q => strings(q.views));
  if (direct.length) return new Set([...direct, "R"]);
  const kind = String(o.kind || "");
  const base = /system/.test(kind) ? "F" : /company|role|industry|value|supplier/.test(kind) ? "V"
    : /demand|workload|application|model|service/.test(kind) ? "D" : /research|question/.test(kind) ? "R" : "P";
  return new Set([base, ...via, ...qv, "R"]);
}
function evidenceList(card, row, index) {
  const ids = fieldRefs(row, ["evidence_id", "evidence_ids"]);
  if (!ids.length) { card.append(element("p", "rg-muted", "尚无关联证据；陈述状态以记录为准。")); return; }
  const wrap = element("div", "rg-cards");
  for (const id of ids) {
    const e = index.evidenceById.get(id);
    const info = element("div", "rg-relation-meta");
    info.append(element("strong", "", "证据 " + id));
    if (e) {
      info.append(element("div", "", [e.locator, e.quote || e.excerpt || e.text].filter(present).join(" · ")));
      addDocumentLinks(info, e, index);
    } else info.append(element("div", "", "关联证据记录未载入"));
    wrap.append(info);
  }
  card.append(wrap);
}
function addDocumentLinks(target, record, index) {
  const ids = fieldRefs(record, ["document_id", "document_ids", "doc_id", "source_id"]);
  for (const id of [...new Set(ids)]) {
    const doc = index.documentById.get(id);
    const url = doc?.reader_url || doc?.url || doc?.source_url;
    target.append(url ? link(doc?.title || id, url, "rg-material-link") : element("span", "rg-muted", "材料 " + id + " · 暂无可用原文链接"));
  }
}
function recordCard(record, category, index) {
  const card = element("div", "rg-card");
  const badges = element("div", "rg-chips");
  badges.append(chip(category), chip(statusText(record.status)));
  if (record.kind || record.type) badges.append(chip(record.kind || record.type));
  card.append(badges);
  const title = record.title || record.text || record.question || record.claim || record.answer || record.summary || record.name || recId(record);
  card.append(element("h4", "", readable(title)));
  if (record.description && record.description !== title) card.append(element("p", "", readable(record.description)));
  if (record.text && record.text !== title) card.append(element("p", "", readable(record.text)));
  card.append(fields([
    ["记录 ID", recId(record)], ["适用范围", record.scope || record.applicability],
    ["文件定位", record.stored_path], ["覆盖情况", record.coverage],
    ["回答引用", record.statement_ids],
    ["时点", record.as_of || record.published_date || record.pub_date],
    ["版本", record.version || record.revision], ["原文定位", record.locator],
    ["内容摘录", record.quote || record.excerpt], ["验收条件", record.acceptance || record.acceptance_criteria],
    ["证据要求", requirementsText(record.evidence_requirements)], ["缺口", record.gap || record.missing],
    ["下一步", record.action || record.next_action], ["负责人", record.owner || record.assignee],
    ["优先级", record.priority || record.pri], ["未披露说明", record.unknown_reason || record.reason],
    ["数据值", Object.hasOwn(record, "value") ? record.value === null ? "未知 / 未披露" : String(record.value) + (record.unit ? " " + record.unit : "") : undefined]
  ]));
  if (category === "陈述" || category === "回答") evidenceList(card, record, index);
  if (category === "证据") addDocumentLinks(card, record, index);
  if (category === "材料") {
    const url = record.reader_url || record.url || record.source_url;
    card.append(url ? link("打开原文 ↗", url) : element("p", "rg-muted", "尚无可用原文链接；文件索引不代表已核实内容。"));
  }
  return card;
}
/* A compact version used inside both Three.js dossiers. */
export function mountNodeResearch(container, nodeId) {
  container.replaceChildren();
  container.classList.add("rg-3d-panel");
  container.dataset.nodeId = nodeId;
  container.append(element("h3", "", "节点研究 · 证据与关系"));
  container.append(element("p", "", "当前几何为概念示意；现场安装、型号和尺寸须分别核实。"));
  const actions = element("div", "rg-node-actions");
  actions.append(link("打开节点研究 →", researchHref(nodeId), "rg-link-button rg-primary"),
    link("系统连接", researchHref(nodeId, "F"), "rg-link-button"));
  container.append(actions);
  const body = element("div"); body.append(element("p", "", "正在读取这个节点的研究记录…")); container.append(body);
  loadResearch().then(data => {
    if (!container.isConnected || container.dataset.nodeId !== nodeId) return;
    const index = buildResearchIndex(data), object = index.byId.get(nodeId);
    body.replaceChildren();
    if (!object) { body.append(element("p", "", "此类别尚未映射到研究对象。打开工作台查看已有对象。")); return; }
    const linked = index.forNode(nodeId);
    const status = element("div", "rg-chips"); status.style.marginTop = "10px";
    status.append(chip(linked.questions.length + " 个问题"), chip(linked.evidence.length + " 条证据"), chip(linked.tasks.length + " 个关联任务"));
    body.append(status);
    if (!linked.evidence.length) body.append(element("p", "", "尚无精确关联证据。公司、产品和模块资料数量不代表该节点已核实。"));
    const neighbors = element("div", "rg-3d-neighbors");
    for (const r of linked.relations.slice(0, 5)) {
      const other = r.source === nodeId ? r.target : r.source;
      const direction = r.source === nodeId ? " → " : " ← ";
      neighbors.append(link(relText(r.type) + direction + (index.byId.get(other)?.name || other),
        researchHref(other, viewOfRelation(r)[0]), ""));
    }
    body.append(neighbors);
  }).catch(error => {
    if (!container.isConnected) return;
    body.replaceChildren(element("p", "", "研究服务暂不可用，节点数据未载入。" + (error.name === "AbortError" ? "连接超时。" : "")));
  });
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
async function startWorkbench() {
  const root = document.getElementById("researchApp");
  if (!root) return;
  const status = document.getElementById("researchStatus");
  const detail = document.getElementById("researchDetail");
  const search = document.getElementById("researchSearch");
  const kindSelect = document.getElementById("researchKind");
  const objectsEl = document.getElementById("researchObjects");
  const params = new URLSearchParams(location.search);
  const state = { view: Object.hasOwn(VIEW_INFO, params.get("view")) ? params.get("view") : "P",
    selected: params.get("node") || "", tab: params.get("tab") || "relations", trail: [] };
  search.value = params.get("q") || "";
  let index, data;
  const tabInfo = { relations: "对象关系", questions: "研究问题", materials: "材料与证据", statements: "陈述与回答", tasks: "缺口任务" };
  if (!Object.hasOwn(tabInfo, state.tab)) state.tab = "relations";
  function saveURL() {
    const q = new URLSearchParams({ node: state.selected, view: state.view, tab: state.tab });
    if (search.value) q.set("q", search.value);
    history.replaceState(null, "", location.pathname + "?" + q.toString());
  }
  function choose(id, track = true) {
    if (track && state.selected && state.selected !== id) state.trail = [...state.trail, state.selected].slice(-6);
    state.selected = id;
    renderObjects(); renderDetail(); saveURL();
  }
  function inView(o) { return objectViews(o, index).has(state.view); }
  function renderViews() {
    const nav = document.getElementById("researchViews"); nav.replaceChildren();
    for (const [id, [name, description]] of Object.entries(VIEW_INFO)) {
      const b = button("", () => { state.view = id; kindSelect.value = ""; renderViews(); renderKinds(); renderObjects(); renderDetail(); saveURL(); }, "rg-view" + (state.view === id ? " active" : ""));
      b.setAttribute("aria-pressed", String(state.view === id));
      b.append(element("b", "", id + " · " + name), element("small", "", description)); nav.append(b);
    }
  }
  function renderKinds() {
    const current = kindSelect.value;
    kindSelect.replaceChildren(element("option", "", "所有对象类型")); kindSelect.firstChild.value = "";
    [...new Set(index.objects.filter(inView).map(o => o.kind || "unknown"))].sort().forEach(kind => {
      const option = element("option", "", typeText(kind)); option.value = kind; kindSelect.append(option);
    });
    kindSelect.value = current;
  }
  function renderObjects() {
    const term = normalize(search.value);
    const visible = index.objects.filter(inView).filter(o => !kindSelect.value || (o.kind || "unknown") === kindSelect.value)
      .filter(o => !term || normalize([o.name, o.id, o.description, o.legacy_bom_id, ...strings(o.modules)].join(" ")).includes(term));
    document.getElementById("researchListCount").textContent = VIEW_INFO[state.view][0] + " · " + visible.length + " 个对象";
    objectsEl.replaceChildren();
    for (const o of visible) {
      const b = button("", () => choose(o.id), "rg-object" + (o.id === state.selected ? " active" : ""));
      b.setAttribute("aria-current", o.id === state.selected ? "true" : "false");
      b.append(element("strong", "", o.name), element("small", "", typeText(o.kind) + " · " + o.id)); objectsEl.append(b);
    }
    if (!visible.length) objectsEl.append(element("p", "rg-empty", "没有匹配对象。可清空搜索或切换视角。"));
  }
  function renderRelations(section, linked, o) {
    const all = linked.relations;
    const selected = state.view === "R" ? all : all.filter(r => viewOfRelation(r).includes(state.view));
    section.append(element("p", "rg-caption", "箭头表示记录的关系方向；装配归属、空间位置、系统连接分别展示。当前视角 " + selected.length + " 条 / 此对象全部 " + all.length + " 条。"));
    if (selected.length < all.length) section.append(button("查看此对象全部关系", () => { state.view = "R"; renderViews(); renderKinds(); renderObjects(); renderDetail(); saveURL(); }));
    if (!selected.length) { section.append(element("div", "rg-empty", "这个对象在当前视角尚无关系记录。未知连接不会由模型外形推断。")); return; }
    const groups = new Map();
    for (const r of selected) {
      const label = VIEW_INFO[viewOfRelation(r)[0]]?.[0] || "其他关系";
      if (!groups.has(label)) groups.set(label, []); groups.get(label).push(r);
    }
    for (const [title, rows] of groups) {
      const group = element("div", "rg-relation-group"); group.append(element("h4", "", title));
      const cards = element("div", "rg-cards");
      for (const r of rows) {
        const card = element("div", "rg-card");
        const row = element("div", "rg-relation");
        const from = index.byId.get(r.source), to = index.byId.get(r.target);
        const middle = element("div", "rg-relation-label");
        middle.append(element("b", "", relText(r.type) + " →"), element("span", "", r.type));
        row.append(button(from?.name || r.source, () => choose(r.source)), middle, button(to?.name || r.target, () => choose(r.target)));
        card.append(row);
        const meta = element("div", "rg-relation-meta");
        const rep = representation(r.representation || o.representation);
        meta.textContent = [r.id, rep[0], r.status ? statusText(r.status) : "", r.description || r.notes || ""].filter(present).join(" · ");
        card.append(meta);
        if (fieldRefs(r, ["evidence_id", "evidence_ids"]).length) evidenceList(card, r, index);
        cards.append(card);
      }
      group.append(cards); section.append(group);
    }
  }
  function renderDetail() {
    detail.replaceChildren();
    const o = index.byId.get(state.selected);
    if (!o) {
      detail.append(element("div", "rg-empty", state.selected ? "研究对象尚未登记：" + state.selected + "。请选择目录中的对象。" : "请选择一个对象，查看结构、证据和下一步任务。"));
      return;
    }
    const linked = index.forNode(o.id);
    if (state.trail.length) {
      const trail = element("nav", "rg-path"); trail.setAttribute("aria-label", "浏览足迹");
      trail.append(element("span", "rg-muted", "浏览足迹"));
      state.trail.forEach(id => trail.append(button(index.byId.get(id)?.name || id, () => choose(id, false), "")));
      detail.append(trail);
    }
    const head = element("section", "rg-node");
    const titleRow = element("div", "rg-node-title-row"), title = element("div");
    title.append(element("div", "rg-node-id", o.id), element("h2", "", o.name || o.id));
    const badges = element("div", "rg-chips"), rep = representation(o.representation);
    badges.append(chip(typeText(o.kind)), chip(rep[0], rep[1]));
    for (const module of strings(o.modules)) badges.append(chip(module));
    titleRow.append(title, badges); head.append(titleRow);
    if (o.description && o.representation === "conceptual") head.append(element("div", "rg-muted", "类别背景 · 待原文核实"));
    head.append(element("p", "", o.description || "这个对象的说明尚未补充。查看关联问题和证据，确认下一步需要核实的内容。"));
    if (!inView(o)) head.append(element("p", "rg-caption", "当前对象保留选中；可从左侧切换到此视角的其他对象。"));
    const counts = element("div", "rg-chips");
    counts.append(chip(linked.questions.length + " 个问题"), chip(linked.documents.length + " 份材料"),
      chip(linked.evidence.length + " 条证据"), chip(linked.tasks.length + " 个关联任务"));
    head.append(counts);
    const actions = element("div", "rg-node-actions");
    if (o.legacy_bom_id) {
      actions.append(link("园区 3D 定位", "bom3d.html?" + new URLSearchParams({ p: o.legacy_bom_id, node: o.id })));
      actions.append(link("机柜参考拆解", "rack3d.html?x=100&node=" + encodeURIComponent(o.id) + "#" + encodeURIComponent(o.legacy_bom_id)));
    }
    actions.append(button("复制节点链接", async () => {
      try { await navigator.clipboard.writeText(location.href); actions.querySelector("button").textContent = "链接已复制"; }
      catch { actions.querySelector("button").textContent = "可复制浏览器地址"; }
    }));
    head.append(actions); detail.append(head);
    const nav = element("nav", "rg-detail-tabs"); nav.setAttribute("aria-label", "节点研究内容");
    const countsByTab = { relations: linked.relations.length, questions: linked.questions.length, materials: linked.documents.length + linked.evidence.length,
      statements: linked.statements.length + linked.answers.length, tasks: linked.tasks.length };
    for (const [id, label] of Object.entries(tabInfo)) {
      const b = button(label + " " + countsByTab[id], () => { state.tab = id; renderDetail(); saveURL(); }, "rg-detail-tab" + (state.tab === id ? " active" : ""));
      b.setAttribute("aria-pressed", String(state.tab === id)); nav.append(b);
    }
    detail.append(nav);
    const section = element("section", "rg-section");
    section.append(element("h3", "", tabInfo[state.tab]));
    if (state.tab === "relations") renderRelations(section, linked, o);
    else {
      let records, empty;
      if (state.tab === "questions") {
        section.append(element("p", "rg-caption", "问题通过对象 ID 关联。验收条件说明什么证据足以回答它。"));
        records = linked.questions.map(r => [r, "问题"]); empty = "此对象尚无关联研究问题。";
      } else if (state.tab === "materials") {
        section.append(element("p", "rg-caption", "材料是原文件；证据是可定位的内容。已有材料不等于规格或现场安装已核实。"));
        records = [...linked.evidence.map(r => [r, "证据"]), ...linked.documents.map(r => [r, "材料"])];
        empty = "尚无精确关联的材料或证据。文件目录数量和同模块资料不会计入这里。";
      } else if (state.tab === "statements") {
        section.append(element("p", "rg-caption", "数值、非数字陈述、未知和争议分别按原记录展示。缺失值不会自动换算或补齐。"));
        records = [...linked.statements.map(r => [r, "陈述"]), ...linked.answers.map(r => [r, "回答"])];
        empty = "尚无关联陈述或回答。当前节点保留未知，不从 3D 外形生成事实。";
      } else {
        section.append(element("p", "rg-caption", "只展示指向此对象或其研究问题的任务。同模块的其他任务不会归到此节点。"));
        records = linked.tasks.map(r => [r, "任务"]); empty = "当前没有精确关联的缺口任务；这不表示研究已完成。";
      }
      const cards = element("div", "rg-cards");
      for (const [record, category] of records) cards.append(recordCard(record, category, index));
      section.append(records.length ? cards : element("div", "rg-empty", empty));
    }
    detail.append(section);
  }
  async function load(refresh = false) {
    status.className = "rg-status"; status.replaceChildren(element("span", "", "正在连接研究服务…"));
    try {
      data = await loadResearch({ refresh }); index = buildResearchIndex(data);
      search.disabled = false; kindSelect.disabled = false;
      const reader = data.reader || {};
      status.replaceChildren(element("span", "", "研究数据已载入 · 架构版本 " + (data.graph.version || "未标记")));
      if (present(reader.status)) status.append(element("span", "", "阅读服务：" + statusText(reader.status)));
      if (reader.message || reader.note) status.append(element("span", "", reader.message || reader.note));
      if (reader.model) status.append(element("span", "", "阅读模型：" + reader.model));
      if (reader.received_at || reader.generated) status.append(element("span", "", "快照：" + (reader.received_at || reader.generated)));
      if (reader.stale) { status.classList.add("offline"); status.append(element("span", "", "阅读快照已过期，不能据此判断当前进度")); }
      if (Array.isArray(reader.recent_failures) && reader.recent_failures.length)
        status.append(element("span", "", "最近 " + reader.recent_failures.length + " 个阅读失败待处理"));
      if (reader.counts && typeof reader.counts === "object") {
        const counts = Object.entries(reader.counts).filter(([, v]) => typeof v === "number").map(([k, v]) => statusText(k) + " " + v);
        if (counts.length) status.append(element("span", "", "阅读队列：" + counts.join(" · ")));
      }
      status.append(button("刷新", () => load(true)));
      const summary = document.getElementById("researchSummary"); summary.replaceChildren();
      for (const [value, label] of [[index.objects.length, "研究对象"], [index.questions.length, "问题"], [index.evidence.length, "证据"], [index.tasks.length, "任务"]]) {
        const stat = element("div", "rg-stat"); stat.append(element("b", "", String(value)), element("span", "", label)); summary.append(stat);
      }
      if (!state.selected) state.selected = (state.view === "P" && index.byId.has("space:site")) ? "space:site" : index.objects.find(o => inView(o))?.id || index.objects[0]?.id || "";
      renderViews(); renderKinds(); renderObjects(); renderDetail(); saveURL();
    } catch (error) {
      index = null;
      search.disabled = true; kindSelect.disabled = true;
      objectsEl.replaceChildren();
      document.getElementById("researchViews").replaceChildren();
      document.getElementById("researchSummary").replaceChildren();
      document.getElementById("researchListCount").textContent = "研究数据未载入";
      status.className = "rg-status error";
      status.replaceChildren(element("span", "", "研究服务未连接。" + (error.name === "AbortError" ? "请求超时。" : error.message)));
      status.append(button("重新连接", () => load(true)));
      detail.replaceChildren(element("div", "rg-empty", "对象、材料和任务尚未载入。请连接提供 /api/research 的研究服务后重试；静态页面不会显示虚构的加载成功或完成状态。"));
    }
  }
  search.addEventListener("input", () => { if (index) { renderObjects(); saveURL(); } });
  kindSelect.addEventListener("change", () => { if (index) renderObjects(); });
  await load();
}
if (typeof document !== "undefined" && document.getElementById("researchApp")) startWorkbench();
