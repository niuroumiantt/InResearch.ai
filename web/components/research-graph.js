import { mountObjectNetwork } from "./object-network.js";
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
  technology: "技术话题", software: "软件",
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
export function researchHref(id, view = "P", tab = "network") {
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
const researchRequests = new Map();
function loadResearchView(path, {refresh = false} = {}) {
  if (refresh) researchRequests.delete(path);
  if (!researchRequests.has(path)) {
    const request = {};
    request.promise = (async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 12000);
      try {
        const response = await fetch(path, {cache:'no-store', signal:controller.signal});
        if (!response.ok) throw new Error("研究服务返回 HTTP " + response.status);
        const data = await response.json();
        if (!data?.graph || !Array.isArray(data.graph.objects) || !Array.isArray(data.graph.relations))
          throw new Error("研究服务返回的数据结构不完整");
        if (path === '/api/research-summary' && (data.schema_version !== 1 ||
            !Array.isArray(data.questions) || !Array.isArray(data.tasks) ||
            !['evidence','statements','answers'].every(key => Array.isArray(data.knowledge?.[key]))))
          throw new Error('研究关联摘要的数据结构不完整');
        return data;
      } finally { clearTimeout(timer); }
    })().catch(error => {
      if (researchRequests.get(path) === request) researchRequests.delete(path);
      throw error;
    });
    researchRequests.set(path, request);
  }
  return researchRequests.get(path).promise;
}
export function loadResearch(options) { return loadResearchView('/api/research', options); }
export function loadResearchSummary(options) { return loadResearchView('/api/research-summary', options); }
export function buildResearchIndex(data) {
  const objects = list(data.graph?.objects);
  const hidden = new Set(objects.filter(o => o.navigation_hidden).map(o => o.id));
  const relations = list(data.graph?.relations).filter(r => !hidden.has(r.source) && !hidden.has(r.target));
  const questions = list(data.questions), knowledge = data.knowledge || {};
  const documents = list(knowledge.documents), evidence = list(knowledge.evidence);
  const statements = list(knowledge.statements), answers = list(knowledge.answers), tasks = list(data.tasks);
  // Catalog registration is a separate layer, never evidence or installed assets.
  const catalog = data.catalog || {}, products = list(catalog.products);
  const catalogDocuments = list(catalog.documents), companies = list(catalog.companies);
  const catalogDocumentById = new Map(catalogDocuments.map(d => [recId(d), d]));
  const companyById = new Map();
  companies.forEach(c => fieldRefs(c, ["id", "company_id"]).forEach(id => companyById.set(id, c)));
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
    byId, evidenceById, documentById, adjacency, forNode,
    catalog, products, catalogDocuments, catalogDocumentById, companies, companyById };
}
export function catalogForNode(index, node, view = "P") {
  if (!node || /demand|workload|application/.test(node.kind || "") || /^(demand|workload):/.test(node.id))
    return { products: [], basis: "demand", direct: 0 };
  const basis = node.id.startsWith("ecosystem:") ? "ecosystem" : node.id === "activity:V2" ? "directory"
    : /system/.test(node.kind || "") || view === "F" ? "context" : "explicit";
  const field = basis === "directory" ? "catalog_node_ids" : basis === "context" ? "related_object_ids" : "object_ids";
  const products = index.products.filter(p => strings(p[node.id.startsWith("ecosystem:") ? "related_object_ids" : field]).includes(node.id));
  return { products, basis, direct: products.filter(p => strings(p.object_ids).includes(node.id)).length };
}
export function catalogMatchesQuery(product, query) {
  const terms = normalize(query).match(/[\p{L}\p{N}]+/gu) || [];
  if (!normalize(query)) return true;
  if (!terms.length) return false;
  const text = normalize([product.company_cn, product.company_en, product.company_id, product.product_line,
    product.category, product.representative_models, ...list(product.models).map(m => m.label)].filter(present).join(" "));
  return terms.every(term => text.includes(term));
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
export function objectViews(o, index) {
  if (o.navigation_hidden) return new Set();
  const direct = strings(o.views || o.view_ids || o.view);
  const via = (index.adjacency.get(o.id) || []).flatMap(viewOfRelation);
  const qv = index.questions.filter(q => refs(q).includes(o.id)).flatMap(q => strings(q.views));
  if (direct.length) return new Set(direct);
  const kind = String(o.kind || "");
  const base = /system/.test(kind) ? "F" : /company|role|industry|value|supplier/.test(kind) ? "V"
    : /demand|workload|application|model|service/.test(kind) ? "D" : /research|question/.test(kind) ? "R" : "P";
  return new Set([base, ...via, ...qv, "R"]);
}
export function navigationForView(index, graph, view) {
  const allowed = new Set(index.objects.filter(o => objectViews(o, index).has(view)).map(o => o.id));
  const covered = new Set();
  function clean(group, path) {
    const ids = [...new Set(strings(group.object_ids))].filter(id => allowed.has(id));
    ids.forEach(id => covered.add(id));
    const children = list(group.children).map((child, i) => clean(child, path + ":" + i)).filter(Boolean);
    return ids.length || children.length ? { id: group.id || path, label: group.label || "浏览分组", object_ids: ids, children } : null;
  }
  const groups = list(graph.navigation?.[view]).map((group, i) => clean(group, view + ":" + i)).filter(Boolean);
  const rest = index.objects.filter(o => allowed.has(o.id) && !covered.has(o.id));
  for (const kind of [...new Set(rest.map(o => o.kind || "unknown"))]) groups.push({
    id: view + ":fallback:" + kind, label: typeText(kind),
    object_ids: rest.filter(o => (o.kind || "unknown") === kind).map(o => o.id), children: []
  });
  return groups;
}
export function navigationPaths(groups, objectId, path = []) {
  return groups.flatMap(group => {
    const next = [...path, group];
    return [...(group.object_ids.includes(objectId) ? [next] : []), ...navigationPaths(group.children, objectId, next)];
  });
}
export function filterNavigation(groups, index, query = "", kind = "", parentMatch = false) {
  const term = normalize(query);
  return groups.map(group => {
    const groupMatch = parentMatch || Boolean(term && normalize(group.label).includes(term));
    const ids = group.object_ids.filter(id => {
      const o = index.byId.get(id);
      return o && (!kind || (o.kind || "unknown") === kind) && (!term || groupMatch ||
        normalize([o.name, o.id, o.description, o.legacy_bom_id, ...strings(o.aliases), ...strings(o.modules)].join(" ")).includes(term));
    });
    const children = filterNavigation(group.children, index, query, kind, groupMatch);
    return ids.length || children.length ? { ...group, object_ids: ids, children } : null;
  }).filter(Boolean);
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
const researchMounts = new WeakMap();
export function mountNodeResearch(container, nodeId) {
  const own = {}; researchMounts.set(container, own);
  const current = () => container.isConnected && researchMounts.get(container) === own;
  container.replaceChildren();
  container.classList.add("rg-3d-panel");
  container.dataset.nodeId = nodeId;
  container.append(element("h3", "", "节点研究 · 证据与关系"));
  container.append(element("p", "", "当前几何为概念示意；现场安装、型号和尺寸须分别核实。"));
  const actions = element("div", "rg-node-actions");
  actions.append(link("打开节点研究 →", researchHref(nodeId), "rg-link-button rg-primary"),
    link("系统连接", researchHref(nodeId, "F"), "rg-link-button"));
  container.append(actions);
  const body = element("div"); container.append(body);
  function load(refresh = false) {
    const request = {}; own.request = request;
    const active = () => current() && own.request === request;
    container.dataset.state = 'loading';
    body.replaceChildren(element('p', '', '正在读取这个节点的研究记录…'));
    loadResearchSummary({refresh}).then(data => {
      if (!active()) return;
      const index = buildResearchIndex(data); const resolvedId = index.byId.get(nodeId)?.redirect_to || nodeId; const object = index.byId.get(resolvedId);
      body.replaceChildren();
      if (!object) { container.dataset.state = 'missing'; body.append(element("p", "", "此类别尚未映射到研究对象。打开工作台查看已有对象。")); return; }
      container.dataset.state = 'ready';
      const linked = index.forNode(resolvedId);
      const status = element("div", "rg-chips"); status.style.marginTop = "10px";
      status.append(chip(linked.questions.length + " 个问题"), chip(linked.evidence.length + " 条证据"), chip(linked.tasks.length + " 个关联任务"));
      body.append(status);
      if (data.reader?.stale || ['not_connected','degraded'].includes(data.reader?.status))
        body.append(element('p', 'rg-muted', '阅读快照未连接或更新延迟；当前显示可用研究记录。'));
      if (!linked.evidence.length) body.append(element("p", "", "尚无精确关联证据。公司、产品和模块资料数量不代表该节点已核实。"));
      const neighbors = element("div", "rg-3d-neighbors");
      for (const r of linked.relations.slice(0, 5)) {
        const other = r.source === resolvedId ? r.target : r.source;
        const direction = r.source === resolvedId ? " → " : " ← ";
        neighbors.append(link(relText(r.type) + direction + (index.byId.get(other)?.name || other),
          researchHref(other, viewOfRelation(r)[0]), ""));
      }
      body.append(neighbors);
    }).catch(error => {
      if (!active()) return;
      container.dataset.state = 'error';
      body.replaceChildren(element("p", "", "研究服务暂不可用，节点数据未载入。" + (error.name === "AbortError" ? "连接超时。" : "")));
      body.append(button('重试', () => { if (current()) load(true); }));
    });
  }
  load();
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
  const phoneLayout = matchMedia("(max-width:700px)");
  const compactPanels = () => {
    root.querySelector('.rg-object-picker').open = !phoneLayout.matches;
    root.querySelector('.rg-workbench-overview').open = !phoneLayout.matches && !new URLSearchParams(location.search).has('node');
  };
  compactPanels(); phoneLayout.addEventListener("change", compactPanels);
  const params = new URLSearchParams(location.search);
  const state = { view: Object.hasOwn(VIEW_INFO, params.get("view")) ? params.get("view") : "P",
    selected: params.get("node") || "", tab: params.get("tab") || "network", trail: [],
    networkHistory: [], topicFilter: params.get("topic") || "", expanded: new Map(), productQuery: "", productCompany: params.get("company") || "", productLimit: 24 };
  search.value = params.get("q") || "";
  let index, data, disposeNetwork=()=>{};
  const tabInfo = { network: "研究图谱", overview: "产品与行业总览", relations: "对象关系", products: "产品与厂商", questions: "研究问题", materials: "材料与证据", statements: "陈述与回答", tasks: "缺口任务" };
  if (!Object.hasOwn(tabInfo, state.tab)) state.tab = "network";
  function saveURL() {
    const q = new URLSearchParams({ node: state.selected, view: state.view, tab: state.tab });
    if (search.value) q.set("q", search.value);
    if (state.tab === "products" && state.productCompany) q.set("company", state.productCompany);
    if (state.tab === "questions" && state.topicFilter) q.set("topic", state.topicFilter);
    history.replaceState(null, "", location.pathname + "?" + q.toString());
  }
  function choose(id, track = true) {
    if (track && state.selected && state.selected !== id) state.trail = [...state.trail, state.selected].slice(-6);
    state.selected = index.byId.get(id)?.redirect_to || id; state.topicFilter = "";
    state.productQuery = ""; state.productCompany = ""; state.productLimit = 24;
    expandSelected();
    renderObjects(); renderDetail(); saveURL();
    if (phoneLayout.matches) root.querySelector(".rg-object-picker").open = false;
  }
  function currentNavigation() { return navigationForView(index, data.graph, state.view); }
  function expandSelected() {
    for (const path of navigationPaths(currentNavigation(), state.selected))
      path.forEach(group => state.expanded.set(state.view + ":" + group.id, true));
  }
  function openNode(id, view, tab = "products") {
    state.view = view; state.tab = tab; kindSelect.value = ""; search.value = "";
    renderViews(); renderKinds(); choose(id);
  }
  function inView(o) { return objectViews(o, index).has(state.view); }
  function renderViews() {
    const nav = document.getElementById("researchViews"); nav.replaceChildren();
    for (const [id, [name, description]] of Object.entries(VIEW_INFO)) {
      const b = button("", () => { state.view = id; kindSelect.value = ""; expandSelected(); renderViews(); renderKinds(); renderObjects(); renderDetail(); saveURL(); }, "rg-view" + (state.view === id ? " active" : ""));
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
    const groups = filterNavigation(currentNavigation(), index, search.value, kindSelect.value);
    const idsIn = group => [...group.object_ids, ...group.children.flatMap(idsIn)];
    const visible = new Set(groups.flatMap(idsIn));
    document.getElementById("researchListCount").textContent = VIEW_INFO[state.view][0] + " · " + visible.size + " 个对象";
    document.getElementById("researchNavigationNote").textContent = "浏览分组 · 不代表现场安装关系";
    document.getElementById("researchNavigationNote").title = data.graph.navigation_note || "";
    const controls = document.getElementById("researchTreeControls"); controls.replaceChildren();
    for (const [name, value] of [["全部展开", true], ["全部收起", false]]) controls.append(button(name, () => {
      const set = rows => rows.forEach(g => { state.expanded.set(state.view + ":" + g.id, value); set(g.children); });
      set(currentNavigation());
      if (!value) { search.value = ""; kindSelect.value = ""; saveURL(); }
      renderObjects();
    }));
    objectsEl.replaceChildren();
    function renderGroup(group) {
      const box = element("details", "rg-tree-group"), key = state.view + ":" + group.id;
      box.open = Boolean(normalize(search.value) || kindSelect.value || state.expanded.get(key));
      box.addEventListener("toggle", () => { if (box.isConnected && !normalize(search.value) && !kindSelect.value) state.expanded.set(key, box.open); });
      const summary = element("summary");
      summary.append(element("span", "", group.label), element("small", "", String(new Set(idsIn(group)).size)));
      box.append(summary);
      const contents = element("div", "rg-tree-children");
      for (const id of group.object_ids) {
        const o = index.byId.get(id);
        const b = button("", () => choose(id), "rg-object" + (id === state.selected ? " active" : ""));
        b.dataset.nodeId = id;
        b.setAttribute("aria-current", id === state.selected ? "true" : "false");
        b.append(element("strong", "", o.name), element("small", "", typeText(o.kind) + " · " + id)); contents.append(b);
      }
      group.children.forEach(child => contents.append(renderGroup(child)));
      box.append(contents); return box;
    }
    groups.forEach(group => objectsEl.append(renderGroup(group)));
    if (!visible.size) objectsEl.append(element("p", "rg-empty", "没有匹配对象。可清空搜索或切换视角。"));
  }
  function renderCatalog(section, node) {
    const selection = catalogForNode(index, node, state.view);
    const intro = element("div", "rg-catalog-note");
    intro.append(element("p", "", "部件类别 → 厂商产品线 → 登记型号标签 → 实际资产。这里接入的是产品线目录；型号规格、当前材料可用性与现场实装仍需核实。"));
    if (selection.basis === "demand") {
      intro.append(element("p", "", "当前是需求／工作负载对象。硬件产品不会仅因同模块而挂入此节点；请从物理部件、功能系统或制造目录浏览，再用证据建立需求与产品的关系。"));
      const actions = element("div", "rg-node-actions");
      const physicalEntry = node.id === "workload:storage" ? ["part:storage-array", "P", "P · 存储部件产品"] : ["space:site", "P", "P · 按设备类别找产品"];
      for (const [id, view, text] of [physicalEntry, ["system:compute", "F", "F · 计算系统产品"], ["activity:V2", "V", "V · 全部产品线与厂商"]])
        if (index.byId.has(id)) actions.append(button(text, () => openNode(id, view)));
      intro.append(actions); section.append(intro); return;
    }
    const description = selection.basis === "ecosystem" ? "根据生态成员与明确产品目录标签关联；不代表经过核验的产品规格或市场覆盖。" : selection.basis === "directory" ? "制造活动下的产品目录入口。此处收录不表示厂商只属于这一产业活动。"
      : selection.basis === "context" ? "按显式 BOM 映射及概念图的装配、空间、系统成员关系查找。这里的相关产品不代表已安装、兼容或已选型。"
      : "按此对象 ID 的显式 BOM 映射查找产品线；不按模块推断产品归属。";
    intro.append(element("p", "", description)); section.append(intro);
    if (!Object.hasOwn(data, "catalog")) { section.append(element("div", "rg-empty", "产品目录尚未由研究服务提供。"), link("打开原产品采集库", "admin/product/")); return; }
    const products = selection.products, filters = element("div", "rg-catalog-filters");
    const input = element("input"); input.type = "search"; input.placeholder = "搜索厂商、产品线、型号标签（支持中文）";
    input.setAttribute("aria-label", "搜索关联产品线"); input.value = state.productQuery;
    const select = element("select"); select.setAttribute("aria-label", "按厂商筛选产品线");
    select.append(element("option", "", "全部厂商／厂商组")); select.firstChild.value = "";
    const companyIds = [...new Set(products.map(p => p.company_id))];
    companyIds.forEach(id => { const p = products.find(p => p.company_id === id), c = index.companyById.get(id);
      const option = element("option", "", (p.company_cn || p.company_en || id) + (c?.is_group ? "（厂商组）" : "")); option.value = id; select.append(option); });
    if (!companyIds.includes(state.productCompany)) state.productCompany = "";
    select.value = state.productCompany; filters.append(input, select); section.append(filters);
    const count = element("p", "rg-caption"), cards = element("div", "rg-cards rg-two-col"), more = element("div", "rg-node-actions");
    const vendorNav = element("nav", "rg-node-actions rg-vendor-index"); vendorNav.setAttribute("aria-label", "厂商快捷定位");
    section.append(count, vendorNav, cards, more);
    function renderProduct(product) {
      const card = element("div", "rg-card rg-product-card"), company = index.companyById.get(product.company_id);
      card.dataset.companyId = product.company_id; card.tabIndex = -1;
      const indexed = strings(product.document_ids).map(id => index.catalogDocumentById.get(id)).filter(d => d?.kind === "indexed_document");
      const plans = strings(product.plan_ids).map(id => index.catalogDocumentById.get(id)).filter(d => d?.kind === "document_plan");
      const mapped = strings(product.object_ids), unknown = strings(product.unmapped_bom_parts);
      const badges = element("div", "rg-chips"); badges.append(chip("厂商产品线"), chip("目录登记 · 待核实", "gold"));
      if (company?.is_group) badges.append(chip("厂商组"));
      card.append(badges, element("h4", "", product.product_line), element("p", "", [product.company_cn, product.company_en].filter(present).join(" · ")));
      card.append(fields([["产品类别", product.category], ["原始型号参考", product.representative_models],
        ["材料登记", indexed.length + " 条历史索引 · " + plans.length + " 项采集计划"],
        ["当前材料", "文件可用性未检查；计划不计为下载或证据"], ["实际资产", "未登记现场安装"]]));
      const mappings = element("div", "rg-product-mappings");
      mappings.append(element("span", "rg-muted", "显式 BOM 映射："));
      mapped.forEach(id => mappings.append(button(index.byId.get(id)?.name || id, () => openNode(id, "P"))));
      if (!mapped.length) mappings.append(chip("尚无对象映射", "gold"));
      if (unknown.length) mappings.append(chip("待核对映射：" + unknown.join("、"), "gold"));
      card.append(mappings);
      if (list(product.models).length) {
        const models = element("details", "rg-product-records"); models.append(element("summary", "", "登记型号标签 " + product.models.length + " · 身份与规格待核实"));
        const entries = element("ul"); list(product.models).forEach(m => entries.append(element("li", "", m.label + " · 历史索引 " + strings(m.document_ids).length + " · 采集计划 " + strings(m.plan_ids).length)));
        models.append(entries); card.append(models);
      }
      if (indexed.length || plans.length) {
        const records = element("details", "rg-product-records"); records.append(element("summary", "", "查看材料登记与采集计划"));
        for (const doc of [...indexed, ...plans]) {
          const row = element("div", "rg-catalog-document");
          row.append(element("strong", "", (doc.kind === "document_plan" ? "采集计划 · " : "历史索引 · ") + (doc.title || [doc.model, doc.doc_type].filter(present).join(" · ") || doc.id)));
          row.append(element("p", "rg-muted", "原记录状态：" + statusText(doc.status) + "；当前文件可用性未检查。"));
          if (doc.file_path || doc.source_path) row.append(element("p", "rg-muted", "登记定位：" + (doc.file_path || doc.source_path)));
          if (doc.source_url || doc.url || doc.reader_url) row.append(link("登记来源", doc.reader_url || doc.url || doc.source_url));
          records.append(row);
        }
        card.append(records);
      }
      const actions = element("div", "rg-node-actions"); actions.append(link("打开此产品线采集档案", product.admin_url || "admin/product/?" + new URLSearchParams({ company: product.company_id, line: product.product_line })));
      if (company?.admin_url) actions.append(link(company.is_group ? "查看厂商组产品线" : "查看厂商产品线", company.admin_url));
      if (product.source_url) actions.append(link("厂商来源", product.source_url));
      card.append(actions); return card;
    }
    function renderResults() {
      const rows = products.filter(p => (!state.productCompany || p.company_id === state.productCompany) && catalogMatchesQuery(p, state.productQuery)).sort((a,b) => a.company_id.localeCompare(b.company_id));
      count.textContent = "当前匹配 " + rows.length + " / " + products.length + " 条产品线 · " + new Set(rows.map(p => p.company_id)).size + " 家厂商／厂商组。计划与历史索引不会计入上方证据数。";
      vendorNav.replaceChildren();
      for (const id of [...new Set(rows.map(p => p.company_id))]) {
        const product = rows.find(p => p.company_id === id);
        vendorNav.append(button((product.company_cn || product.company_en || id) + " · " + rows.filter(p => p.company_id === id).length, () => {
          state.productLimit = Math.max(state.productLimit, rows.findIndex(p => p.company_id === id) + 1);
          renderResults(); const target = [...cards.children].find(c => c.dataset.companyId === id);
          if (target) { target.focus({preventScroll:true}); target.scrollIntoView({block:"start",behavior:"smooth"}); }
        }));
      }
      cards.replaceChildren(); rows.slice(0, state.productLimit).forEach(p => cards.append(renderProduct(p)));
      if (!rows.length) cards.append(element("div", "rg-empty", products.length ? "没有匹配的产品线，请调整搜索或厂商筛选。" : "尚无此对象的显式产品映射。可在制造目录查看全库，或从左侧部件进入产品线；未映射不等于没有供应商。"));
      more.replaceChildren();
      if (rows.length > state.productLimit) more.append(button("再显示 24 条（剩余 " + (rows.length - state.productLimit) + "）", () => { state.productLimit += 24; renderResults(); }));
      more.append(button("查看全部产品线与厂商", () => openNode("activity:V2", "V")), link("产品采集库", "admin/product/"));
    }
    input.addEventListener("input", () => { state.productQuery = input.value; state.productLimit = 24; renderResults(); saveURL(); });
    select.addEventListener("change", () => { state.productCompany = select.value; state.productLimit = 24; renderResults(); saveURL(); });
    renderResults();
  }
  function renderOverview(section, linked, o) {
    section.append(element("p", "rg-caption", "研究导览与背景 · 不代表已完成核验。这里的分类用于研究，不表示现场装配。"));
    if (o.ecosystem_id) {
      const domain = list(data.graph.hardware_domains).find(d => d.id === o.ecosystem_id);
      if (domain) section.append(button("返回 " + domain.name, () => openNode(domain.node_id, "R", "overview")));
    }
    const groups = list(o.research_sections);
    for (const group of groups) {
      const box = element("div", "rg-card rg-overview-group"); box.append(element("h4", "", group.title));
      const links = element("div", "rg-node-actions");
      for (const id of strings(group.object_ids)) { const target = index.byId.get(id); if (target) links.append(button(target.name, () => openNode(id, "R", "network"))); }
      box.append(links); section.append(box);
    }
    if (!groups.length) section.append(element("p", "", "当前以定义、主要方案与产品资料为研究入口；有明确问题和材料后再扩展下一层。"));
    for (const url of strings(o.background_sources)) section.append(link("背景参考 · " + new URL(url).hostname, url));
    const topics = element("div", "rg-overview-topics");
    for (const topic of list(data.graph.research_topics)) {
      const box = element("details", "rg-card"); box.append(element("summary", "", topic.name));
      const qs = linked.questions.filter(q => q.topic_id === topic.id);
      box.append(element("p", "rg-muted", qs.length ? qs.length + " 个已按主题登记的问题；查看问题与证据核验进度。" : "专题综述待补充；未分类的历史问题仍在研究问题栏目。"));
      box.append(button("查看全部研究问题", () => { state.tab = "questions"; renderDetail(); saveURL(); })); topics.append(box);
    }
    section.append(topics);
    const reports = element("div", "rg-card"); reports.append(element("h4", "", "行业报告与数据"), element("p", "", "报告原件、表格数据与结论分别登记。历史报告保留统计期间和修订状态，不能当作当前市场结论。"), button("查看材料与证据", () => { state.tab = "materials"; renderDetail(); saveURL(); })); section.append(reports);
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
    disposeNetwork();disposeNetwork=()=>{};
    detail.replaceChildren();
    const o = index.byId.get(state.selected);
    if (!o) {
      detail.append(element("div", "rg-empty", state.selected ? "研究对象尚未登记：" + state.selected + "。请选择目录中的对象。" : "请选择一个对象，查看结构、证据和下一步任务。"));
      return;
    }
    const linked = index.forNode(o.id);
    const productSelection = catalogForNode(index, o, state.view);
    const paths = navigationPaths(currentNavigation(), o.id);
    if (paths.length) {
      const breadcrumb = element("nav", "rg-breadcrumb"); breadcrumb.setAttribute("aria-label", "浏览分组路径");
      breadcrumb.textContent = "浏览分组：" + [VIEW_INFO[state.view][0], ...paths[0].map(group => group.label), o.name].join(" / ");
      if (paths.length > 1) breadcrumb.append(element("span", "rg-muted", " · 另有 " + (paths.length - 1) + " 条导航路径"));
      detail.append(breadcrumb);
    }
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
    actions.append(button("产品与厂商 · " + productSelection.products.length + " 条产品线", () => { state.tab = "products"; renderDetail(); saveURL(); }));
    if (o.legacy_bom_id) {
      actions.append(link("园区 3D 定位", "bom3d.html?" + new URLSearchParams({ p: o.legacy_bom_id, node: o.id })));
      actions.append(link("机柜参考拆解", "rack3d.html?x=100&node=" + encodeURIComponent(o.id) + "#" + encodeURIComponent(o.legacy_bom_id)));
    }
    actions.append(button("复制节点链接", async () => {
      try { await navigator.clipboard.writeText(location.href); copyButton.textContent = "链接已复制"; }
      catch { copyButton.textContent = "可复制浏览器地址"; }
    }));
    const copyButton = actions.lastElementChild;
    head.append(actions); detail.append(head);
    // One object, three practical questions. Each action retains its object and view.
    const flow = element("nav", "rg-case-flow"); flow.setAttribute("aria-label", "当前对象研究流程");
    const steps = [
      ["已知什么", linked.statements.length + linked.answers.length
        ? `${linked.statements.length} 条陈述 · ${linked.answers.length} 条回答，仍需结合各条证据判断。`
        : "尚无关联陈述或回答；当前对象的背景说明不代表已核实。", "查看陈述与回答", "statements"],
      ["此前做了什么", `${linked.documents.length} 份材料 · ${linked.evidence.length} 条证据，沿记录查看原件和来源。`, "查看材料与证据", "materials"],
      ["现在做哪一步", linked.tasks.length
        ? `${linked.tasks.length} 个关联任务，打开后按任务状态继续处理。`
        : linked.questions.length ? `${linked.questions.length} 个研究问题，选择一个问题核对证据缺口。` : "尚无关联任务或问题，可以先核对已有材料。",
        linked.tasks.length ? "继续处理任务" : linked.questions.length ? "查看研究问题" : "核对已有材料",
        linked.tasks.length ? "tasks" : linked.questions.length ? "questions" : "materials"],
    ];
    steps.forEach(([heading, text, label, tab], i) => {
      const step = element("section", "rg-case-step" + (i === 2 ? " rg-case-next" : ""));
      const action = button(label, () => { state.tab = tab; renderDetail(); saveURL(); detail.querySelector(".rg-section")?.scrollIntoView({block:"start"}); });
      step.append(element("h3", "", heading), element("p", "", text), action); flow.append(step);
    });
    detail.append(flow);
    const nav = element("nav", "rg-detail-tabs"); nav.setAttribute("aria-label", "节点研究内容");
    const countsByTab = { network: null, overview: null, relations: linked.relations.length, products: productSelection.products.length, questions: linked.questions.length, materials: linked.documents.length + linked.evidence.length,
      statements: linked.statements.length + linked.answers.length, tasks: linked.tasks.length };
    for (const [id, label] of Object.entries(tabInfo)) {
      const b = button(label + (countsByTab[id] === null ? "" : " " + countsByTab[id]), () => { state.tab = id; renderDetail(); saveURL(); }, "rg-detail-tab" + (state.tab === id ? " active" : ""));
      b.setAttribute("aria-pressed", String(state.tab === id)); nav.append(b);
    }
    detail.append(nav);
    const section = element("section", "rg-section");
    section.append(element("h3", "", tabInfo[state.tab]));
    if (state.tab === "network") disposeNetwork=mountObjectNetwork(section, {graph:data.graph, centerId:o.id, labelRelation:relText,
      canBack:state.networkHistory.length > 0,
      vendorsForNode:id=>[...new Map(index.products.filter(p=>strings(p.object_ids).includes(id)).map(p=>[p.company_id,{id:p.company_id,name:p.company_cn || p.company_en || p.company_id}])).values()],
      onVendor:(id,company)=>{state.networkHistory.push(o.id);openNode(id,"R","products");state.productCompany=company;renderDetail();saveURL();document.querySelector('.rg-product-card')?.focus({preventScroll:true});},
      onBack:()=>{const id=state.networkHistory.pop();if(id)openNode(id,"R","network");},
      onNavigate:id=>{state.networkHistory.push(o.id);openNode(id,"R","network");document.querySelector('.rg-network-center')?.focus({preventScroll:true});},
      onTopic:id=>{state.topicFilter=id;state.tab="questions";renderDetail();saveURL();}
    });
    else if (state.tab === "overview") renderOverview(section, linked, o);
    else if (state.tab === "relations") renderRelations(section, linked, o);
    else if (state.tab === "products") renderCatalog(section, o);
    else {
      let records, empty;
      if (state.tab === "questions") {
        section.append(element("p", "rg-caption", "问题通过对象 ID 关联。验收条件说明什么证据足以回答它。"));
        if (state.topicFilter) {
          const topic=list(data.graph.research_topics).find(t=>t.id===state.topicFilter);
          section.append(element("p","rg-caption","当前研究角度："+(topic?.name||state.topicFilter)),button("显示全部问题",()=>{state.topicFilter="";renderDetail();saveURL();}));
        }
        records = linked.questions.filter(r=>!state.topicFilter||r.topic_id===state.topicFilter).map(r => [r, "问题"]); empty = state.topicFilter ? "此角度尚无已分类问题；历史未分类问题仍保留在全部问题中。" : "此对象尚无关联研究问题。";
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
      for (const [value, label] of [[index.objects.filter(o => !o.navigation_hidden).length, "研究对象"], [index.questions.length, "问题"], [index.evidence.length, "证据"], [index.tasks.length, "任务"]]) {
        const stat = element("div", "rg-stat"); stat.append(element("b", "", String(value)), element("span", "", label)); summary.append(stat);
      }
      const catalogEntry = document.getElementById("researchCatalog"); catalogEntry.replaceChildren();
      catalogEntry.append(button("产品目录 · " + index.products.length + " 条产品线", () => openNode("activity:V2", "V")));
      catalogEntry.append(element("span", "rg-muted", index.companies.length + " 家厂商／厂商组 · 通过 P 部件、F 系统与 V 制造目录查找；材料状态单列"), link("产品采集库 ↗", "admin/product/"));
      let hardware = document.getElementById("researchHardware");
      if (!hardware) { hardware = element("section", "rg-card"); hardware.id = "researchHardware"; catalogEntry.insertAdjacentElement("afterend", hardware); }
      hardware.replaceChildren(element("h3", "", "按产品生态研究"), element("p", "rg-muted", "先选生态，再进入产品、部件与技术话题；与下方空间/系统视角共用研究对象。"));
      const entries = element("div", "rg-node-actions");
      for (const domain of list(data.graph.hardware_domains)) entries.append(button(domain.name, () => openNode(domain.node_id, "R", "overview")));
      hardware.append(entries);
      if (!state.selected) state.selected = (state.view === "P" && index.byId.has("space:site")) ? "space:site" : index.objects.find(o => inView(o))?.id || index.objects[0]?.id || "";
      state.selected = index.byId.get(state.selected)?.redirect_to || state.selected;
      expandSelected();
      renderViews(); renderKinds(); renderObjects(); renderDetail(); saveURL();
    } catch (error) {
      index = null;
      search.disabled = true; kindSelect.disabled = true;
      objectsEl.replaceChildren();
      document.getElementById("researchViews").replaceChildren();
      document.getElementById("researchSummary").replaceChildren();
      document.getElementById("researchCatalog").replaceChildren();
      document.getElementById("researchTreeControls").replaceChildren();
      document.getElementById("researchNavigationNote").textContent = "";
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
