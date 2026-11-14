"use strict";
const $ = (s) => document.querySelector(s);
const iconPaths = {
  brand: "M4 19 12 5l8 14M8 15h8",
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  chart: "M4 4v16h16M8 15l4-5 4 2 4-7",
  plug: "m9 3 0 5m6-5v5M6 8h12v3a6 6 0 0 1-6 6v4M8 8v-3M16 8v-3",
  plus: "M12 5v14M5 12h14",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  back: "M19 12H5m5-5-5 5 5 5",
  chevron: "m9 5 7 7-7 7",
  chevrons: "m8 9 4-4 4 4m-8 6 4 4 4-4",
  search: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  dots: "M5 12h.01M12 12h.01M19 12h.01",
  refresh: "M20 7v5h-5M4 17v-5h5M6.1 6a8 8 0 0 1 13.5 5M4.4 13A8 8 0 0 0 18 18",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M4 8l-1 4 2 4 3 1 3 4 4-1 2-3 4-2-1-5-3-2-2-4-4 1-3 3z",
  file: "M14 2H5v20h14V7zM14 2v6h5M8 12h8M8 16h6",
  image: "M3 3h18v18H3zM3 16l6-6 5 5 3-3 4 4M15 7h.01",
  code: "m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18",
  book: "M12 5c-3-3-7-3-10-2v16c4-1 7 0 10 2 3-2 6-3 10-2V3c-3-1-7-1-10 2zm0 0v16",
  check: "m5 12 4 4L19 6",
  circle: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  x: "m6 6 12 12M6 18 18 6",
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  bolt: "m13 2-9 12h7l-1 8 10-13h-7z",
  copy: "M9 9h12v12H9zM5 15H3V3h12v2",
  terminal: "m5 7 5 5-5 5M13 17h6",
  flask: "M9 3h6m-5 0v7l-6 9a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-9V3M8 15h8",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  dollar: "M12 2v20m5-16H9a4 4 0 0 0 0 8h6a3 3 0 0 1 0 6H6",
  tokens: "m12 2 10 5-10 5L2 7zm-10 10 10 5 10-5M2 17l10 5 10-5",
  activity: "M2 12h5l3-8 4 16 3-8h5",
  archive: "M3 3h18v5H3zM5 8v13h14V8M10 12h4",
  trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7",
  info: "M12 11v6m0-10h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  globe:
    "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3c-5 5-5 13 0 18 5-5 5-13 0-18",
  shield: "m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6zM8 12l3 3 5-6",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  sliders: "M4 4v5m0 4v7M12 4v9m0 4v3M20 4v1m0 4v11M1 9h6M9 13h6M17 5h6",
};
const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${iconPaths[name] || iconPaths.grid}"/></svg>`;
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fmt = (n) => new Intl.NumberFormat("en-US").format(Math.round(n));
const compact = (n) =>
  n >= 1e6
    ? (n / 1e6).toFixed(2) + "M"
    : n >= 1000
      ? (n / 1000).toFixed(1) + "K"
      : fmt(n);
const money = (n) => (n == null ? "—" : "$" + Number(n).toFixed(2));
let providers = [];
let projects = [];
const state = {
  channel: "all",
  homeTab: "projects",
  projectSort: "recent",
  distributionSort: "usage",
  distributionMetric: "tokens",
  distributionView: "chart",
  codeProject: "",
  range: "7",
  search: "",
  status: "all",
  view: "grid",
  breakdown: "connection",
  recordFilter: "all",
  draft: null,
  discovery: "idle",
  models: [],
  modelSearch: "",
  capability: "all",
  test: { status: "idle", step: 0 },
  discoverNonce: 0,
  testNonce: 0,
};
const activeProjects = () => projects.filter((p) => !p.archived);
const scopeName = () =>
  state.range === "today"
    ? "今日"
    : state.range === "30"
      ? "近 30 天"
      : "近 7 天";
const providerFor = (p) =>
  providers.find(
    (v) =>
      v.id ===
      (p.mode === "gpt"
        ? state.connection?.providers.find((v) => v.default && v.mode === "gpt")
            ?.id
        : p.provider),
  ) || { id: "", name: "连接待配置", models: [], status: "offline" };
const metrics = (p) => usageFor(p, state.channel);
function rangeControl() {
  return `<div class="segmented" aria-label="用量时间范围">${[
    ["today", "今日"],
    ["7", "近 7 天"],
    ["30", "近 30 天"],
  ]
    .map(
      ([v, t]) =>
        `<button data-action="range" data-value="${v}" class="${state.range === v ? "active" : ""}" aria-pressed="${state.range === v}">${t}</button>`,
    )
    .join("")}</div>`;
}
function home() {
  return state.homeTab === "dashboard"
    ? globalUsage()
    : `<div class="list-caption"><span>${activeProjects().length} 个项目 · ${esc(channelName())} · ${scopeName()}</span><span>点击项目横条查看用量与配置</span></div><div class="project-list" id="project-grid">${projectRows()}</div><button class="add-project-row" data-action="new">${icon("plus")}新建项目</button>${footer()}`;
}
function projectCards() {
  return projectRows();
}
function projectDetail(p, tab = "usage") {
  return `${tab === "settings" ? configuration(p) : tab === "requests" ? requestsPage(p) : projectUsage(p)}${footer()}`;
}
function breakdownPanel(p) {
  const rows = splitRows(p);
  return `<article class="panel space-top"><div class="panel-head"><div><h2>连接与模型用量</h2><p>${esc(channelName())} · 按实际调用时的渠道统计 · 名称来自 CC Switch</p></div><div class="mini-tabs">${[
    ["connection", "连接 / 账号"],
    ["model", "模型"],
  ]
    .map(
      ([v, t]) =>
        `<button class="${state.breakdown === v ? "active" : ""}" data-action="breakdown" data-value="${v}">${t}</button>`,
    )
    .join(
      "",
    )}</div></div><div class="table-scroll"><table><thead><tr><th>${state.breakdown === "model" ? "模型" : "连接 / 账号"}</th><th>调用次数</th><th>Token 用量</th><th>成功率</th><th>估算费用（$）</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(r.label)}<small>${esc(r.sub)}</small></td><td>${fmt(r.calls)}</td><td>${compact(r.tokens)}</td><td>${r.success.toFixed(1)}%</td><td>${money(r.cost)}</td></tr>`).join("")}</tbody></table></div>${rows.length ? "" : '<div class="config-empty">所选渠道暂无用量记录</div>'}</article>`;
}
function requestsPage(p) {
  return requestPanel(p);
}
function emptyProject(p) {
  return `<div class="empty-state space-top">${icon("activity")}<h3>准备好接收第一次调用</h3><p>完成项目配置并测试连接后，可从左侧 Python 调用页面查看使用方式。</p><a class="btn secondary" href="#/project/${esc(p.id)}/settings">${icon("settings")}配置项目</a></div>`;
}
function codeText(p) {
  return `from ccask import Ask\n\nwith Ask(\n    project=${JSON.stringify(p.name)},\n    default_memory=False,  # 支持服务端续接的接口可开启\n    memory=10,\n    session_id="我的会话",\n) as bot:\n    reply = bot.ask("你好，请帮我分析这个问题")\n    print(reply.text)\n\n    # 也可以传入图片\n    reply = bot.ask("分析这张图", images=["figure.png"])\n\n    bot.stop_memory()   # 关闭显式历史，问答仍保存\n    bot.start_memory()  # 恢复最近 10 轮历史\n    bot.clear_memory()  # 删除当前会话及名称，下次提问创建新会话`;
}
function codePage(p) {
  return `<div class="code-layout"><div class="code-window"><div class="code-caption"><span class="mono">${esc(p.name)} / quickstart.py</span><button class="btn secondary small" data-action="copy-code" data-id="${esc(p.id)}">${icon("copy")}复制代码</button></div><pre>${esc(codeText(p))}</pre></div><aside class="instruction-box"><h2>调用前，确认这几件事</h2><ul><li>${icon("check")}CC Ask 本地服务已启动。</li><li>${icon("check")}CC Switch 已启用聚合模式。</li><li>${icon("check")}项目模型已选择，并通过连接测试。</li><li>${icon("info")}相同项目名与会话名，可恢复之前的记忆。</li></ul><div class="callout space-top">项目配置保存在网页，Python 只需传入项目名。切换模型或当前账号后，下一次调用自动使用新配置。</div></aside></div>`;
}
const effortLabels = {
  none: "不思考", minimal: "极低", low: "低", medium: "中", high: "高",
  xhigh: "超高", max: "最大", ultra: "极致",
};
function reasoningControl() {
  const d = state.draft || {};
  const model = state.models.find((m) => m.id === d.model)
    || (state.connection?.catalog || []).map(modelView).find((m) => m.id === d.model);
  const known = Array.isArray(model?.reasoningEfforts);
  const levels = known ? model.reasoningEfforts : Object.keys(effortLabels);
  let parameters;
  try {
    parameters = JSON.parse(d.parameterText?.trim() || "{}");
    if (!parameters || Array.isArray(parameters) || typeof parameters !== "object") throw new Error();
  } catch {
    return '<label class="field"><span>思考强度</span><select disabled><option>请先修正高级参数 JSON</option></select></label>';
  }
  const selected = parameters.reasoning?.effort || "";
  const options = [...levels];
  if (selected && !options.includes(selected)) options.unshift(selected);
  const fallback = model?.defaultReasoningEffort;
  const note = known
    ? levels.length ? "按所选模型支持的档位显示。强度越高，通常耗时和用量越多。" : "模型目录未提供可选思考档位，请使用模型默认。"
    : "模型未声明支持档位，请按供应商说明选择，并测试连接。";
  return `<label class="field"><span>思考强度</span><select id="draft-reasoning-effort" aria-label="思考强度"><option value="">模型默认${fallback ? "（" + esc(effortLabels[fallback] || fallback) + "）" : ""}</option>${options.map(v => `<option value="${esc(v)}" ${selected === v ? "selected" : ""}>${esc(effortLabels[v] || v)} (${esc(v)})${known && !levels.includes(v) ? " · 当前模型不支持" : ""}</option>`).join("")}</select><small>${note}</small></label>`;
}
function setReasoningEffort(value) {
  const d = state.draft;
  const parameters = JSON.parse(d.parameterText?.trim() || "{}");
  const reasoning = parameters.reasoning;
  if (reasoning !== undefined && (!reasoning || typeof reasoning !== "object" || Array.isArray(reasoning))) {
    throw new Error("请先将高级参数中的 reasoning 改为 JSON 对象。");
  }
  parameters.reasoning = {...(reasoning || {})};
  if (value) parameters.reasoning.effort = value;
  else delete parameters.reasoning.effort;
  if (!Object.keys(parameters.reasoning).length) delete parameters.reasoning;
  d.parameterText = Object.keys(parameters).length ? JSON.stringify(parameters, null, 2) : "";
  const textarea = document.querySelector('[data-field="parameterText"]');
  if (textarea) textarea.value = d.parameterText;
  invalidateTest();
  refreshModelPanel();
}
function configuration(p = null) {
  const d = state.draft || p || {};
  return `<div class="config-layout"><form id="config-form" class="config-form"><section class="form-section"><div class="form-heading"><span class="step-no">01</span><h2>基本信息</h2></div><label class="field"><span>项目名称</span><input class="input" data-field="name" id="draft-name" placeholder="例如：论文助手" maxlength="60" value="${esc(d.name)}" required><small>在 Python 中通过这个名称关联项目。</small></label><label class="field"><span>项目描述 <span class="muted">可选</span></span><input class="input" data-field="description" placeholder="这个项目主要用来做什么？" maxlength="120" value="${esc(d.description)}"></label></section><section class="form-section"><div class="form-heading"><span class="step-no">02</span><h2>连接与模型</h2><span class="badge">自动识别</span></div><div class="mode-picker" role="group" aria-label="调用方式">${[
    ["gpt", "globe", "GPT 账号", "使用当前官方登录"],
    ["api", "plug", "API 调用", "使用 CC Switch 供应商"],
  ]
    .map(
      ([v, i, t, s]) =>
        `<button class="mode-option ${d.mode === v ? "active" : ""}" type="button" data-action="mode" data-value="${v}" aria-pressed="${d.mode === v}"><span class="mode-icon">${icon(i)}</span><span><b>${t}</b><small>${s}</small></span><i class="radio-mark"></i></button>`,
    )
    .join(
      "",
    )}</div><label class="field"><span>${d.mode === "gpt" ? "当前 GPT 账号" : "选择 API 供应商"}</span>${
    d.mode === "gpt"
      ? `<div class="input" style="height:auto;min-height:42px;display:flex;align-items:center;gap:8px">${icon("globe")}${esc(providerFor(d).account || "请在 CC Switch 激活官方账号")}<span class="badge" style="margin-left:auto">当前账号</span></div><small>在 CC Switch 切换账号，项目会跟随当前登录。</small>`
      : `<select id="draft-provider" aria-label="选择 API 供应商">${providers
          .filter((v) => v.mode === "api")
          .map(
            (v) =>
              `<option value="${esc(v.id)}" ${d.provider === v.id ? "selected" : ""}>${esc(v.name)}${v.status === "offline" ? " · 连接待检查" : ""}</option>`,
          )
          .join(
            "",
          )}</select><small>供应商、API 地址及密钥统一在 CC Switch 管理。</small>`
  }</label><div class="provider-summary">${icon("shield")}所有调用都经过 CC Switch 本机代理<span class="badge ${state.connection?.ready ? "success" : "warning"}"><span class="dot"></span>${state.connection?.ready ? "已连接" : "待检查"}</span></div><div style="border-top:1px solid var(--line);margin-top:20px;padding-top:18px"><div class="discovery-meta"><h3 style="font-size:12px">选择模型</h3><button class="btn ghost small" type="button" data-action="discover">${icon("refresh")}重新识别</button></div><div class="model-tools"><label class="search">${icon("search")}<input class="input" id="model-search" placeholder="搜索已识别的模型…" aria-label="搜索模型" value="${esc(state.modelSearch)}"></label><div class="segmented"><button type="button" data-action="capability" data-value="all" class="${state.capability === "all" ? "active" : ""}">全部</button><button type="button" data-action="capability" data-value="vision" class="${state.capability === "vision" ? "active" : ""}">支持图片</button></div></div><div id="models-panel">${modelsPanel()}</div><button type="button" class="manual-model" data-action="manual-model">模型未在列表中？手动填写 ID</button><div class="discovery-caption">${icon("info")}根据所选连接识别模型及能力，切换连接后会重新识别。</div></div></section><section class="form-section"><div class="form-heading"><span class="step-no">03</span><h2>回答要求</h2><span class="muted tiny" style="margin-left:auto">可选</span></div><label class="field"><span>系统提示词</span><textarea id="draft-instructions" data-field="instructions" rows="5" placeholder="例如：你是一名严谨的科研助手，请用清晰、准确的中文回答。">${esc(d.instructions)}</textarea><small>每次调用都会使用，关闭会话记忆时也有效。</small></label><div id="reasoning-control">${reasoningControl()}</div><details><summary class="body-color tiny">高级参数</summary><label class="field parameters-field"><span>默认请求参数（JSON）</span><textarea class="mono" data-field="parameterText" rows="5" placeholder='{"temperature": 0.7}'>${esc(d.parameterText)}</textarea><small>支持 temperature、top_p、max_output_tokens、reasoning 和 text。</small></label></details></section><div id="config-error"></div><div class="form-footer"><small id="save-hint">配置更新后，从下一次调用生效。</small><div class="actions"><a class="btn secondary" href="${p ? "#/project/" + p.id : "#/projects"}">取消</a><button class="btn" type="submit" id="save-config">${icon("check")}${p ? "保存更改" : "创建项目"}</button></div></div></form><aside class="config-aside"><div id="test-panel">${testPanel()}</div><div class="config-tip"><h3>${icon("tokens")}测试也有清晰的归属</h3><p>连接测试会先保存当前配置，再发送一次最小请求，验证所选模型能否回答，并计入当前项目用量。</p></div><div class="config-tip"><h3>${icon("shield")}换连接，历史仍在</h3><p>修改 API 或在 CC Switch 切换 GPT 账号后，历史用量按原连接保留，项目内可以分别查看。</p></div></aside></div>`;
}
function modelsPanel() {
  const d = state.draft;
  if (state.discovery === "loading")
    return `<div class="recognize-state"><span class="spinner"></span><strong>正在识别支持的模型</strong><p>读取连接配置，并同步该连接的可用模型与输入能力…</p></div>`;
  if (state.discovery === "error")
    return `<div class="recognize-state">${icon("plug")}<strong>暂时无法获取模型列表</strong><p>${esc(state.discoveryError || "可以重试、选择其他供应商，或手动填写模型 ID。")}</p><button type="button" class="btn secondary small" data-action="discover">${icon("refresh")}重试识别</button></div>`;
  if (state.discovery === "idle")
    return `<div class="recognize-state"><span class="spinner"></span><span>准备读取模型列表…</span></div>`;
  const list = state.models.filter(
    (m) =>
      (state.capability !== "vision" || m.vision) &&
      [m.name, m.id]
        .join(" ")
        .toLowerCase()
        .includes(state.modelSearch.toLowerCase()),
  );
  return `<div class="discovery-meta"><small>已识别 ${state.models.length} 个模型${d.mode === "gpt" ? " · 当前账号可用" : ""}</small><small>刚刚更新</small></div><div class="model-list">${list.length ? list.map((m) => `<button type="button" class="model-item ${d.model === m.id ? "selected" : ""}" data-action="model" data-value="${esc(m.id)}" aria-pressed="${d.model === m.id}"><i class="radio-mark"></i><span><b>${esc(m.name)}</b><small class="mono">${esc(m.id)}</small></span><span class="model-tags"><span class="model-tag">文本</span>${m.vision ? `<span class="model-tag">${icon("image")}图片</span>` : ""}${m.reasoning ? `<span class="model-tag">推理</span>` : ""}</span></button>`).join("") : `<div class="model-item-empty">没有匹配的模型，试试其他关键词。</div>`}</div>`;
}
function globalUsage() {
  const m = aggregate(projects);
  return `${charts(m, true)}${distributionPanel()}${footer()}`;
}
function channelName(value = state.channel) {
  return value === "all"
    ? "全部渠道"
    : channelIds(value)
        .map((id) => providers.find((p) => p.id === id).name)
        .join(" + ");
}
function channelControl() {
  return `<div class="channel-control"><span class="filter-label" title="名称来自 CC Switch 配置">渠道</span><div class="segmented channels" aria-label="用量渠道筛选">${[{ id: "all", name: "全部渠道" }, ...providers].map((p) => `<button data-action="channel" data-value="${esc(p.id)}" class="${p.id === "all" ? (state.channel === "all" ? "active" : "") : state.channel !== "all" && channelIds().includes(p.id) ? "active" : ""}" aria-pressed="${p.id === "all" ? state.channel === "all" : channelIds().includes(p.id)}" title="${p.id === "all" ? "合并全部渠道" : "CC Switch · " + esc(p.name) + " · 可多选"}">${esc(p.name)}</button>`).join("")}</div></div>`;
}
function sortOptions(value) {
  return [
    ["recent", "最近使用"],
    ["usage", "按用量"],
    ["calls", "按调用次数"],
    ["cost", "按费用"],
    ["name", "按名称"],
  ]
    .map(
      ([v, t]) =>
        `<option value="${v}" ${value === v ? "selected" : ""}>${t}</option>`,
    )
    .join("");
}
function sortedProjects(list, sort, metric = "tokens") {
  return [...list].sort((a, b) => {
    if (sort === "name")
      return a.name.localeCompare(b.name, "zh-CN", {
        numeric: true,
        sensitivity: "base",
      });
    if (sort === "recent") return lastUse(b) - lastUse(a);
    const key = sort === "calls" ? "calls" : sort === "cost" ? "cost" : metric;
    return (
      metrics(b)[key] - metrics(a)[key] || a.name.localeCompare(b.name, "zh-CN")
    );
  });
}
function projectToolbar() {
  return `<div class="project-toolbar"><label class="search">${icon("search")}<input class="input" id="project-search" aria-label="搜索项目" placeholder="搜索项目名称或模型…" value="${esc(state.search)}"></label><div class="toolbar-right"><select class="filter-select" id="status-filter" aria-label="项目状态"><option value="all" ${state.status === "all" ? "selected" : ""}>全部状态</option><option value="active" ${state.status === "active" ? "selected" : ""}>运行正常</option><option value="pending" ${state.status === "pending" ? "selected" : ""}>待配置</option></select><label class="sort-picker">${icon("sliders")}<select id="project-sort" aria-label="项目排序">${sortOptions(state.projectSort)}</select></label></div></div>`;
}
function fixedHeader(r, p) {
  if (r.page === "project" && p) {
    return `<div class="context-inner"><div class="context-project-heading"><div class="detail-title"><span class="project-icon">${icon(p.icon)}</span><div><h1>${esc(p.name)}</h1><div class="compact-project-meta"><span class="badge ${p.status === "active" ? "success" : "warning"}">${p.status === "active" ? "运行正常" : "待配置"}</span><span class="mono">${esc(p.model || "尚未选择模型")}</span><span class="muted">当前配置 · ${p.mode === "gpt" ? "官方账号" : esc(providerFor(p).name)}</span></div></div></div>${r.tab === "settings" ? "" : `<a class="btn secondary small" href="#/project/${esc(p.id)}/settings">${icon("settings")}配置项目</a>`}<button class="icon-btn" data-action="project-menu" data-id="${esc(p.id)}" aria-label="${esc(p.name)}的更多操作">${icon("dots")}</button></div><nav class="tabs" aria-label="项目功能">${[
      ["usage", "chart", "用量概览"],
      ["requests", "list", "调用记录"],
      ["settings", "sliders", "项目配置"],
    ]
      .map(
        ([id, ic, t]) =>
          `<a href="#/project/${esc(p.id)}/${id}" class="${r.tab === id ? "active" : ""}">${icon(ic)}${t}</a>`,
      )
      .join("")}</nav>${r.tab === "settings" ? "" : usageFilters()}</div>`;
  }
  if (r.page === "new")
    return `<div class="context-inner"><div class="compact-page-heading"><div><h1>创建一个新项目</h1><p>选择连接、识别模型，再测试是否可以调用。</p></div><a class="btn secondary small" href="#/projects">${icon("back")}返回项目</a></div></div>`;
  if (r.page === "python")
    return `<div class="context-inner"><div class="compact-page-heading"><div><h1>Python 调用</h1><p>在这里查看安装、项目调用与记忆管理方式。</p></div><span class="badge">Python 3.7+</span></div><div class="python-project-picker"><label for="python-project">示例项目</label><select id="python-project">${activeProjects()
      .map(
        (p) =>
          `<option value="${esc(p.id)}" ${p.id === state.codeProject ? "selected" : ""}>${esc(p.name)}</option>`,
      )
      .join(
        "",
      )}</select><span class="muted tiny">选择项目，自动生成对应示例</span></div></div>`;
  if (r.page === "settings")
    return `<div class="context-inner"><div class="compact-page-heading"><div><h1>设置</h1><p>选择菜单栏要监控的项目和统计时间范围。</p></div></div></div>`;
  if (r.page === "connections")
    return `<div class="context-inner"><div class="compact-page-heading"><div><h1>连接管理</h1><p>统一查看本机代理、API 供应商与官方账号。</p></div><button class="btn secondary small" data-action="refresh-connections">${icon("refresh")}刷新连接</button></div></div>`;
  return `<div class="context-inner home-context"><div class="home-heading-row"><h1>项目工作台</h1><nav class="tabs home-tabs" aria-label="首页面板"><button class="${state.homeTab === "projects" ? "active" : ""}" data-action="home-tab" data-value="projects">${icon("list")}项目列表<span class="tab-count">${activeProjects().length}</span></button><button class="${state.homeTab === "dashboard" ? "active" : ""}" data-action="home-tab" data-value="dashboard">${icon("chart")}统计面板</button></nav><a class="btn small" href="#/new">${icon("plus")}新建项目</a></div>${usageFilters()}${state.homeTab === "projects" ? projectToolbar() : ""}<div class="fixed-summary">${slimSummary()}</div></div>`;
}
function slimSummary() {
  const m = aggregate(projects);
  return `<div class="slim-summary"><div><span>总调用</span><strong>${fmt(m.calls)}<small>次</small></strong></div><div><span>Token 用量</span><strong>${compact(m.tokens)}</strong></div><div><span title="CC Switch 估算费用 · 美元">估算费用 · $</span><strong>${money(m.cost)}</strong></div><div><span>成功率</span><strong>${m.success.toFixed(1)}<small>%</small></strong></div></div>`;
}
function projectRows() {
  const list = sortedProjects(
    activeProjects().filter(
      (p) =>
        (state.status === "all" || p.status === state.status) &&
        [p.name, p.description, p.model]
          .join(" ")
          .toLowerCase()
          .includes(state.search.toLowerCase()),
    ),
    state.projectSort,
  );
  if (!activeProjects().length)
    return `<div class="empty-state">${icon("grid")}<h3>创建你的第一个项目</h3><p>选好连接和模型，就可以通过 Python 开始调用。</p><a class="btn" href="#/new">${icon("plus")}新建项目</a></div>`;
  if (!list.length)
    return `<div class="empty-state">${icon("search")}<h3>没有匹配的项目</h3><p>换个关键词，或清除筛选。</p><button class="btn secondary small" data-action="clear-search">清除筛选</button></div>`;
  return list
    .map((p) => {
      const m = metrics(p);
      return `<article class="project-row" data-project="${esc(p.id)}"><a class="project-row-main" href="#/project/${esc(p.id)}" aria-label="查看${esc(p.name)}的用量"><span class="project-icon">${icon(p.icon)}</span><div class="project-row-title"><h2>${esc(p.name)}<span class="row-status ${p.status === "active" ? "ready" : ""}" title="${p.status === "active" ? "运行正常" : "待配置"}"></span></h2><p>最近使用 · ${esc(p.last || "尚未调用")}</p></div><div class="project-current"><span class="mono">${esc(p.model || "待选择模型")}</span><small>当前配置 · ${p.mode === "gpt" ? "官方账号" : esc(providerFor(p).name)}</small></div><div class="row-metrics"><div><strong>${fmt(m.calls)}</strong><small>调用次数</small></div><div><strong>${compact(m.tokens)}</strong><small>Token</small></div><div><strong>${money(m.cost)}</strong><small>估算费用</small></div></div></a><button class="icon-btn" data-action="project-menu" data-id="${esc(p.id)}" aria-label="${esc(p.name)}的更多操作">${icon("dots")}</button></article>`;
    })
    .join("");
}
function distributionPanel() {
  const rows = sortedProjects(
      projects,
      state.distributionSort,
      state.distributionMetric,
    ),
    key = state.distributionMetric;
  const total = rows.reduce((n, p) => n + metrics(p)[key], 0),
    max = Math.max(1, ...rows.map((p) => metrics(p)[key]));
  const format = (value) =>
    key === "cost"
      ? money(value)
      : key === "calls"
        ? fmt(value)
        : compact(value);
  return `<section class="panel space-top distribution-panel"><div class="panel-head"><div><h2>项目用量分布</h2><p>${esc(channelName())} · ${scopeName()} · ${rows.length} 个项目</p></div><div class="distribution-controls"><select class="filter-select" id="distribution-metric" aria-label="分布统计指标">${[
    ["tokens", "Token 用量"],
    ["calls", "调用次数"],
    ["cost", "估算费用"],
  ]
    .map(
      ([v, t]) =>
        `<option value="${v}" ${key === v ? "selected" : ""}>${t}</option>`,
    )
    .join(
      "",
    )}</select><label class="sort-picker">${icon("sliders")}<select id="distribution-sort" aria-label="用量分布排序">${sortOptions(state.distributionSort)}</select></label><div class="mini-tabs">${[
    ["chart", "图表"],
    ["table", "明细"],
  ]
    .map(
      ([v, t]) =>
        `<button class="${state.distributionView === v ? "active" : ""}" data-action="distribution-view" data-value="${v}">${t}</button>`,
    )
    .join("")}</div></div></div>${
    state.distributionView === "chart"
      ? `<div class="project-distribution" role="img" aria-label="按${{ tokens: "Token 用量", calls: "调用次数", cost: "估算费用" }[key]}统计的项目用量分布">${rows
          .map((p) => {
            const m = metrics(p),
              value = m[key];
            return `<a class="project-bar-row" data-project="${esc(p.id)}" href="#/project/${esc(p.id)}" aria-label="查看${esc(p.name)}的用量"><span class="bar-project-name">${icon(p.icon)}<span>${esc(p.name)}${p.archived ? "（已归档）" : ""}</span></span><span class="bar-track"><span class="bar-fill" style="width:${(value / max) * 100}%"></span></span><strong>${format(value)}</strong><small>${total ? ((value / total) * 100).toFixed(1) : "0.0"}%</small></a>`;
          })
          .join(
            "",
          )}</div><div class="distribution-caption">柱长表示当前指标，右侧为项目占比。费用采用 CC Switch 美元估算口径。点击横条查看项目。</div>`
      : `<div class="table-scroll"><table><thead><tr><th>项目</th><th>调用次数</th><th>Token 用量</th><th>估算费用（$）</th><th>最近使用</th></tr></thead><tbody>${rows
          .map((p) => {
            const m = metrics(p);
            return `<tr><td><a href="#/project/${esc(p.id)}">${esc(p.name)}</a></td><td>${fmt(m.calls)}</td><td>${compact(m.tokens)}</td><td>${money(m.cost)}</td><td>${esc(p.last || "—")}</td></tr>`;
          })
          .join("")}</tbody></table></div>`
  }</section>`;
}
function pythonPage() {
  const list = activeProjects(),
    p = list.find((p) => p.id === state.codeProject) || list[0];
  const example = p ? codePage(p) : `<div class="empty-state">${icon("code")}<h3>先创建一个项目</h3><p>创建项目后，这里会生成对应的 Python 示例。</p><a class="btn" href="#/new">新建项目</a></div>`;
  return `<div class="python-install"><div class="python-install-heading"><h2>安装本地库</h2><button class="btn secondary small" data-action="copy-install">${icon("copy")}复制安装命令</button></div><p>支持 Python 3.7 及以上版本。在你的 Python 环境中安装后，保持 CC Ask 服务运行。</p><code>${esc(installCommand())}</code></div>${example}${footer()}`;
}
function installCommand() {
  return state.setup?.install_command || `NO_PROXY=127.0.0.1,localhost python -m pip install --upgrade "http://127.0.0.1:8765/api/sdk/${state.setup?.sdk_wheel || "ccask_client-0.1.3-py3-none-any.whl"}"`;
}
function settingsPage() {
  const config = state.setup?.menubar || {project_ids: [], period: "today"};
  const monitor = state.menuUsage;
  const list = activeProjects();
  const rows = monitor?.rows || [];
  return `<section class="panel monitor-settings"><h2>菜单栏用量监控</h2><p>点击 macOS 顶部菜单栏的图标，查看用量统计表或打开主窗口。菜单栏旁的数字表示当前监控范围的 Token 用量，每 5 秒刷新。</p><form id="menubar-form"><label class="field"><span>统计时间</span><select class="input" id="menubar-period">${[["today","今日"],["7d","近 7 天"],["30d","近 30 天"],["all","全部时间"]].map(([value,label]) => `<option value="${value}" ${config.period === value ? "selected" : ""}>${label}</option>`).join("")}</select></label><fieldset class="monitor-projects"><legend>监控项目（可多选）</legend><p>不勾选项目时显示全局用量，包含已归档项目的历史记录。</p>${list.map(p => `<label class="monitor-project"><input type="checkbox" name="monitor-project" value="${esc(p.id)}" ${config.project_ids.includes(p.id) ? "checked" : ""}><span>${esc(p.name)}</span></label>`).join("") || '<p class="muted">创建项目后，可以在这里选择要监控的项目。</p>'}</fieldset><button class="btn" type="submit">保存菜单栏设置</button></form></section><section class="panel monitor-preview"><div class="panel-head"><div><h2>当前监控用量</h2><p>${esc(monitor?.period_label || "今日")} · ${esc(monitor?.scope || "全局用量")} · 费用单位为美元</p></div></div><div class="table-scroll"><table><thead><tr><th>项目</th><th>调用次数</th><th>Token 用量</th><th>估算费用（$）</th><th>成功率</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.label)}</td>${monitorCells(r)}</tr>`).join("")}<tr class="monitor-total"><td>合计</td>${monitorCells(monitor?.summary || {})}</tr></tbody></table></div></section>${footer()}`;
}
function monitorCells(row) {
  return `<td>${fmt(row.requests || 0)}</td><td>${row.total_tokens == null ? "—" : fmt(row.total_tokens)}</td><td>${row.cost == null ? "—" : "$" + Number(row.cost).toFixed(4)}</td><td>${row.success_rate == null ? "—" : (row.success_rate * 100).toFixed(1) + "%"}</td>`;
}
let currentRoute = "";
function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return {
    page: parts[0] || "projects",
    id: parts[1],
    tab: parts[2] || "usage",
  };
}
function render() {
  let r = route();
  if (r.page === "usage") {
    state.homeTab = "dashboard";
    history.replaceState(null, "", "#/projects");
    r = { page: "projects", tab: "usage" };
  }
  if (r.page === "project" && r.tab === "code") {
    state.codeProject = r.id;
    history.replaceState(null, "", "#/python");
    r = { page: "python", tab: "usage" };
  }
  const key = [r.page, r.id, r.tab].join("/"),
    pane = $("#workspace-scroll"),
    oldScroll = pane.scrollTop,
    changed = key !== currentRoute;
  if (changed) {
    state.discoverNonce++;
    invalidateTest();
    state.recordFilter = "all";
    if (r.page === "new" || (r.page === "project" && r.tab === "settings"))
      initDraft(r.id ? projects.find((p) => p.id === r.id) : null);
    currentRoute = key;
  }
  const project = projects.find((p) => p.id === r.id),
    root = $("#app");
  if (r.page === "project" && project) {
    root.innerHTML = projectDetail(project, r.tab);
  } else if (r.page === "new") {
    root.innerHTML = configuration() + footer();
  } else if (r.page === "python") {
    root.innerHTML = pythonPage();
  } else if (r.page === "connections") {
    root.innerHTML = connections();
  } else if (r.page === "settings") {
    root.innerHTML = settingsPage();
  } else {
    const missing = r.page === "project";
    r = { page: missing ? "project" : "projects", tab: "usage" };
    root.innerHTML =
      r.page === "project"
        ? `<div class="empty-state"><h3>项目已归档或不存在</h3><a class="btn secondary" href="#/projects">返回项目</a></div>`
        : home();
  }
  $("#page-context").innerHTML = fixedHeader(r, project);
  $("#page-context").classList.toggle("is-home", r.page === "projects");
  $("#nav-count").textContent = activeProjects().length;
  document
    .querySelectorAll("[data-nav]")
    .forEach((n) =>
      n.classList.toggle(
        "active",
        n.dataset.nav ===
          (r.page === "python"
            ? "python"
            : r.page === "connections"
              ? "connections"
              : r.page === "settings"
                ? "settings"
              : "projects"),
      ),
    );
  hydrateIcons();
  pane.scrollTop = changed ? 0 : oldScroll;
  if (
    state.draft &&
    (r.page === "new" || r.tab === "settings") &&
    state.discovery === "idle"
  )
    discoverModels();
}
function hydrateIcons() {
  document.querySelectorAll("[data-icon]").forEach((n) => {
    n.innerHTML = icon(n.dataset.icon);
    n.removeAttribute("data-icon");
  });
}
function refreshModelPanel() {
  if ($("#reasoning-control")) $("#reasoning-control").innerHTML = reasoningControl();
  if ($("#models-panel")) $("#models-panel").innerHTML = modelsPanel();
  if ($("#test-panel")) $("#test-panel").innerHTML = testPanel();
}
function invalidateTest() {
  state.testNonce++;
  state.test = { status: "idle", step: 0 };
}
function toast(message) {
  const n = $("#toast");
  n.innerHTML = icon("check") + `<span>${esc(message)}</span>`;
  n.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (n.hidden = true), 3400);
}
function showDialog(title, body, actions = "") {
  const d = $("#dialog");
  d.innerHTML = `<div class="dialog-head"><h2>${title}</h2><button class="icon-btn" data-action="close-dialog" aria-label="关闭弹窗">${icon("x")}</button></div>${body}${actions ? `<div class="dialog-actions">${actions}</div>` : ""}`;
  d.showModal();
}
function closeDialog() {
  $("#dialog").close();
}
async function copy(text, label = "调用代码") {
  try {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const previous = document.activeElement;
      const field = document.createElement("textarea");
      field.className = "clipboard-fallback";
      field.value = text;
      document.body.appendChild(field);
      field.select();
      const copied = document.execCommand("copy");
      field.remove();
      previous?.focus();
      if (!copied) throw new Error("copy_failed");
    }
    toast(`${label}已复制。`);
  } catch {
    showDialog(
      `复制${label}`,
      `<div class="code-window"><pre>${esc(text)}</pre></div><p class="form-fields-note">当前浏览器限制剪贴板，可选中上方代码复制。</p>`,
    );
  }
}
function projectMenu(button, id) {
  document.querySelector(".popover")?.remove();
  document.querySelector(".menu-overlay")?.remove();
  const box = button.getBoundingClientRect();
  const overlay = document.createElement("div");
  overlay.className = "menu-overlay";
  overlay.onclick = () => {
    overlay.remove();
    document.querySelector(".popover")?.remove();
  };
  document.body.append(overlay);
  const menu = document.createElement("div");
  menu.className = "popover";
  menu.style.left =
    Math.max(10, Math.min(innerWidth - 180, box.right - 170)) + "px";
  menu.style.top = Math.min(innerHeight - 195, box.bottom + 5) + "px";
  menu.innerHTML = `<a href="#/project/${id}">${icon("chart")}查看项目用量</a><a href="#/project/${id}/settings">${icon("settings")}编辑项目配置</a><button data-action="archive" data-id="${id}">${icon("archive")}归档项目</button><button class="danger-text" data-action="delete-project" data-id="${id}">${icon("trash")}删除项目</button>`;
  menu.addEventListener("click", () => {
    overlay.remove();
    menu.remove();
  });
  document.body.append(menu);
}

// Live service adapter. Templates above share the prototype's layout and styling.
state.connection = null;
state.report = { rollups: [], requests: [] };
state.projectRecords = {};
state.loading = true;
state.saving = false;
const chartColors = ["#0d74ce", "#8145b5", "#16a34a", "#ab6400", "#eb8e90"];
async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json();
  if (!response.ok) {
    const message =
      data.error?.message ||
      (Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join("；")
        : data.detail);
    throw new Error(message || "本地服务请求失败，请重试。");
  }
  return data;
}
function modelView(m) {
  return {
    id: m.id,
    name: m.label || m.id,
    vision: (m.modalities || []).includes("image"),
    reasoning: Boolean(m.reasoning_efforts?.length),
    reasoningEfforts: m.reasoning_efforts ?? null,
    defaultReasoningEffort: m.default_reasoning_effort || "",
  };
}
function updateProviders(connection) {
  const known = connection.providers.map((p) => ({
    ...p,
    account: p.account_id || p.name,
    kind: p.mode === "gpt" ? "官方账号" : "API 供应商",
    status:
      connection.ready &&
      p.routable &&
      (p.mode !== "gpt" || connection.account_ready)
        ? "ready"
        : "offline",
    models: (p.mode === "gpt" && p.default
      ? connection.catalog.filter((m) => !m.id.startsWith("ccs-"))
      : p.models
    ).map(modelView),
  }));
  for (const r of state.report.rollups) {
    if (r.provider_id && !known.some((p) => p.id === r.provider_id)) {
      known.push({
        id: r.provider_id,
        name: r.provider_name,
        mode: "api",
        status: "offline",
        account: r.account_label || "历史连接",
        kind: "历史连接",
        models: [],
      });
    }
  }
  providers = known;
  if (state.channel !== "all" && !channelIds().length) state.channel = "all";
}
function projectView(p) {
  const rows = state.report.rollups.filter((r) => r.project_id === p.id);
  const lastUsedAt = Math.max(0, ...rows.map((r) => r.last_used_at));
  const provider = providerFor({ ...p, provider: p.provider_id });
  return {
    ...p,
    provider: p.provider_id,
    icon: "file",
    calls: rows.reduce((n, r) => n + r.requests, 0),
    status: provider.status === "ready" ? "active" : "pending",
    created: new Date(p.created_at * 1000).toISOString(),
    lastUsedAt: lastUsedAt * 1000,
    last: lastUsedAt ? relativeTime(lastUsedAt) : "",
  };
}
function relativeTime(seconds) {
  const minutes = Math.max(0, Math.floor((Date.now() / 1000 - seconds) / 60));
  return minutes < 1
    ? "刚刚"
    : minutes < 60
      ? minutes + " 分钟前"
      : minutes < 1440
        ? Math.floor(minutes / 60) + " 小时前"
        : new Date(seconds * 1000).toLocaleDateString("zh-CN", {
            timeZone: "Asia/Shanghai",
          });
}
function lastUse(p) {
  return p.lastUsedAt || p.created_at * 1000 || 0;
}
function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
function rangeDays() {
  const end = Date.parse(today() + "T00:00:00+08:00"),
    count = state.range === "today" ? 1 : Number(state.range);
  return Array.from({ length: count }, (_, i) =>
    new Date(end - (count - 1 - i) * 86400000).toLocaleDateString("en-CA", {
      timeZone: "Asia/Shanghai",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }),
  );
}
function selectedRows(p = null, channel = state.channel) {
  const days = new Set(rangeDays()),
    ids = channelIds(channel);
  return state.report.rollups.filter(
    (r) =>
      (!p || r.project_id === p.id) &&
      days.has(r.date) &&
      (channel === "all" || ids.includes(r.provider_id)),
  );
}
function sumRows(rows) {
  const m = {
    calls: 0,
    tokens: 0,
    cost: null,
    successes: 0,
    success: 0,
    latency: 0,
    fresh_input: 0,
    output_tokens: 0,
    cache_read: 0,
    cache_write: 0,
    pending: 0,
    unknown: 0,
  };
  for (const r of rows) {
    m.calls += r.requests;
    m.tokens += r.total_tokens || 0;
    m.successes += r.successes;
    m.latency += ((r.avg_latency_ms || 0) * r.requests) / 1000;
    if (r.cost != null) m.cost = (m.cost || 0) + Number(r.cost);
    for (const key of [
      "fresh_input",
      "output_tokens",
      "cache_read",
      "cache_write",
    ])
      m[key] += r[key] || 0;
    m.pending += r.pending;
    m.unknown += r.unknown_usage;
  }
  m.success = m.calls ? (m.successes / m.calls) * 100 : 0;
  m.latency = m.calls ? m.latency / m.calls : 0;
  return m;
}
function usageFor(p, channel = "all") {
  return sumRows(selectedRows(p, channel));
}
function aggregate(list) {
  const ids = new Set(list.map((p) => p.id));
  return sumRows(selectedRows().filter((r) => ids.has(r.project_id)));
}
function channelIds(value = state.channel) {
  return value === "all"
    ? providers.map((p) => p.id)
    : value.split(",").filter((id) => providers.some((p) => p.id === id));
}
function toggleChannel(id) {
  if (id === "all") {
    state.channel = "all";
    return;
  }
  if (state.channel === "all") {
    state.channel = id;
    return;
  }
  const selected = channelIds(),
    next = selected.includes(id)
      ? selected.filter((v) => v !== id)
      : [...selected, id];
  state.channel =
    !next.length || next.length === providers.length ? "all" : next.join(",");
}
function stats(m, global = false) {
  return `<div class="stats"><div class="stat"><div class="stat-title">${global ? "总调用次数" : "调用次数"}${icon("activity")}</div><div class="stat-value">${fmt(m.calls)}<small>次</small></div><div class="stat-foot">${m.pending ? fmt(m.pending) + " 次等待用量同步" : m.calls ? "当前所选时间与渠道" : "等待首次调用"}</div></div><div class="stat"><div class="stat-title">Token 用量${icon("tokens")}</div><div class="stat-value">${compact(m.tokens)}<small>tokens</small></div><div class="stat-foot">包含输入、输出及缓存</div></div><div class="stat"><div class="stat-title">估算费用<span class="currency-icon">$</span></div><div class="stat-value">${money(m.cost)}<small>USD</small></div><div class="stat-foot">CC Switch 估算费用 · 美元</div></div><div class="stat"><div class="stat-title">调用成功率${icon("check")}</div><div class="stat-value">${m.calls ? m.success.toFixed(1) : "—"}<small>${m.calls ? "%" : ""}</small></div><div class="stat-foot">平均响应 ${m.calls ? m.latency.toFixed(1) + " s" : "—"}</div></div></div>`;
}
function chart(m, scope = "all", p = null) {
  const days = rangeDays(),
    rows = selectedRows(p);
  const series = channelIds().map((id, index) => ({
    id,
    color: chartColors[index % chartColors.length],
    name: providers.find((v) => v.id === id)?.name || id,
    values: days.map((day) =>
      rows
        .filter((r) => r.provider_id === id && r.date === day)
        .reduce((n, r) => n + (r.total_tokens || 0), 0),
    ),
  }));
  const total = {
    id: "total",
    color: "#171717",
    name: "总用量",
    values: days.map((day) =>
      rows
        .filter((r) => r.date === day)
        .reduce((n, r) => n + (r.total_tokens || 0), 0),
    ),
  };
  const max = Math.max(1, ...total.values),
    x = (i) => (days.length === 1 ? 296 : 42 + (i * 508) / (days.length - 1)),
    y = (v) => 164 - (v / max) * 135;
  return `<svg viewBox="0 0 565 204" role="img" aria-label="Token 用量趋势">${[0, 1, 2, 3].map((i) => `<line x1="42" x2="550" y1="${29 + i * 45}" y2="${29 + i * 45}" stroke="var(--line)" stroke-dasharray="3 5"/><text x="0" y="${33 + i * 45}">${compact((max * (3 - i)) / 3)}</text>`).join("")}${[...series, total].map((s) => `<path d="${s.values.map((v, i) => (i ? "L" : "M") + x(i) + "," + y(v)).join(" ")}" fill="none" stroke="${s.color}" stroke-width="${s.id === "total" ? 2.5 : 1.5}"/>${s.values.map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="${s.id === "total" ? 2.5 : 1.5}" fill="${s.color}"><title>${esc(s.name)} · ${days[i]} · ${fmt(v)} Token</title></circle>`).join("")}`).join("")}${days.map((day, i) => (i % Math.ceil(days.length / 7) === 0 || i === days.length - 1 ? `<text x="${x(i)}" y="192" text-anchor="middle">${day.slice(5).replace("-", "/")}</text>` : "")).join("")}</svg>`;
}
function charts(m, global = false, p = null) {
  const parts = [
    ["新增输入", "fresh_input", "var(--ink)"],
    ["模型输出", "output_tokens", "var(--body)"],
    ["缓存读取", "cache_read", "var(--line-strong)"],
    ["缓存写入", "cache_write", "var(--surface)"],
  ];
  return `<div class="chart-layout"><article class="panel"><div class="panel-head"><div><h2>调用用量趋势</h2><p>${scopeName()} · ${esc(channelName())} · Token 消耗</p></div><div class="chart-key interactive-key"><span class="chart-total-key"><i></i>总用量</span>${providers.map((v, i) => `<button class="${channelIds().includes(v.id) ? "selected" : ""}" data-action="trend-channel" data-value="${esc(v.id)}" aria-pressed="${channelIds().includes(v.id)}"><i style="background:${chartColors[i % chartColors.length]}"></i>${esc(v.name)}</button>`).join("")}</div></div><div class="main-chart">${chart(m, global ? "all" : "project", p)}</div></article><article class="panel"><div class="panel-head"><div><h2>Token 构成</h2><p>${esc(channelName())} · 输入、输出与缓存</p></div></div><div class="distribution"><div class="distribution-total">${compact(m.tokens)}<small>TOKENS</small></div><div class="distribution-bar">${parts.map(([_, key, c]) => `<span style="width:${m.tokens ? (m[key] / m.tokens) * 100 : 0}%;background:${c}"></span>`).join("")}</div>${parts.map(([n, key, c]) => `<div class="distribution-item"><i style="background:${c}"></i><span>${n}</span><b>${compact(m[key])}</b></div>`).join("")}</div></article></div>`;
}
function projectUsage(p) {
  const m = metrics(p);
  return `${stats(m)}${charts(m, false, p)}${breakdownPanel(p)}${m.calls ? requestPanel(p, true) : emptyProject(p)}`;
}
function splitRows(p) {
  const grouped = new Map();
  for (const r of selectedRows(p)) {
    const key =
      state.breakdown === "model" ? r.model : r.connection_id || "unresolved";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(r);
  }
  return [...grouped.values()].map((rows) => ({
    label:
      state.breakdown === "model"
        ? rows[0].model
        : rows[0].account_label || rows[0].provider_name,
    sub:
      rows[0].provider_name +
      (state.breakdown === "model"
        ? ""
        : " · " + (rows[0].connection_id?.slice(0, 8) || "连接前失败")),
    ...sumRows(rows),
  }));
}
function requestRows(p) {
  const days = new Set(rangeDays()),
    ids = channelIds();
  return (
    state.projectRecords[p.id] ||
    state.report.requests.filter((r) => r.project_id === p.id)
  ).filter(
    (r) =>
      days.has(
        new Date(r.started_at * 1000).toLocaleDateString("en-CA", {
          timeZone: "Asia/Shanghai",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }),
      ) &&
      (state.channel === "all" || ids.includes(r.provider_id)),
  );
}
const statusLabels = {
  completed: "已完成",
  failed: "调用失败",
  running: "回答中",
  interrupted: "已中断",
};
function requestPanel(p, compactView = false) {
  let rows = requestRows(p).filter(
    (r) => state.recordFilter === "all" || r.status === state.recordFilter,
  );
  const count = rows.length;
  if (compactView) rows = rows.slice(0, 4);
  return `<article class="panel space-top"><div class="panel-head"><div><h2>${compactView ? "最近调用" : "调用记录"}</h2><p>按实际调用时的连接统计</p></div>${compactView ? `<a class="btn ghost small" href="#/project/${p.id}/requests">全部记录${icon("arrow")}</a>` : `<select class="filter-select" id="record-filter" aria-label="调用结果筛选">${[["all", "全部结果"], ...Object.entries(statusLabels)].map(([v, t]) => `<option value="${v}" ${state.recordFilter === v ? "selected" : ""}>${t}</option>`).join("")}</select>`}</div><div class="table-scroll"><table><thead><tr><th>时间 / 类型</th><th>模型</th><th>状态</th><th>Token</th><th>耗时</th><th>费用（$）</th><th></th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(new Date(r.started_at * 1000).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" }))}<small>模型调用</small></td><td class="mono">${esc(r.model)}<small>${esc(r.provider_name)}</small></td><td><span class="badge ${r.status === "completed" ? "success" : "warning"}">${statusLabels[r.status] || esc(r.status)}</span>${r.usage_status === "pending" ? "<small>用量同步中</small>" : ""}</td><td>${r.total_tokens == null ? "—" : fmt(r.total_tokens)}</td><td>${(r.latency_ms / 1000).toFixed(2)} s</td><td>${r.cost == null ? "—" : "$" + Number(r.cost).toFixed(4)}</td><td><button class="table-link" data-action="request-detail" data-id="${p.id}" data-value="${r.id}">详情</button></td></tr>`).join("")}</tbody></table></div>${!rows.length ? '<div class="config-empty">所选时间与渠道暂无调用记录</div>' : ""}${!compactView ? `<div class="table-bottom"><span>显示 ${count} 条记录 · 最近 100 条调用</span><span>上海时区 · Asia/Shanghai</span></div>` : ""}</article>`;
}
function usageFilters() {
  return `<div class="filterline">${channelControl()}<div class="time-control"><span class="filter-label">时间</span>${rangeControl()}</div><span class="filter-sync" title="${esc(state.report.sync_error || "每 5 秒自动同步")}"><span class="dot" style="color:${state.report.sync_error ? "var(--warning)" : "var(--success)"}"></span>${state.loading ? "同步中" : state.report.sync_error ? "同步待检查" : "已同步"}</span></div>`;
}
function initDraft(p = null) {
  state.draft = p
    ? structuredClone(p)
    : {
        id: null,
        name: "",
        description: "",
        icon: "file",
        mode: "gpt",
        provider: null,
        model: "",
        instructions: "",
        parameters: {},
        status: "pending",
      };
  state.draft.parameterText = Object.keys(state.draft.parameters || {}).length
    ? JSON.stringify(state.draft.parameters, null, 2)
    : "";
  state.models = [];
  state.discovery = "idle";
  state.modelSearch = "";
  state.capability = "all";
  state.test = { status: "idle", step: 0 };
  state.discoverNonce++;
  state.testNonce++;
}
async function discoverModels() {
  if (!state.draft) return;
  const nonce = ++state.discoverNonce;
  state.discovery = "loading";
  invalidateTest();
  refreshModelPanel();
  try {
    const connection = await api("/connection");
    if (nonce !== state.discoverNonce) return;
    state.connection = connection;
    updateProviders(connection);
    const provider = providerFor(state.draft);
    state.models = structuredClone(provider.models);
    state.discovery = state.models.length ? "success" : "error";
    state.discoveryError =
      connection.error ||
      "当前连接未提供模型目录。可以手动填写模型 ID，或在 CC Switch 更新模型配置。";
  } catch (e) {
    if (nonce !== state.discoverNonce) return;
    state.discovery = "error";
    state.discoveryError = e.message;
  }
  refreshModelPanel();
}
function chooseMode(mode) {
  const d = state.draft;
  if (!d || d.mode === mode) return;
  d.mode = mode;
  d.provider =
    mode === "api" ? providers.find((p) => p.mode === "api")?.id || null : null;
  d.model = "";
  d.status = "pending";
  state.discovery = "idle";
  state.models = [];
  state.modelSearch = "";
  state.capability = "all";
  invalidateTest();
  render();
}
function draftPayload() {
  const d = state.draft;
  if (!d?.name.trim()) throw new Error("请给项目起一个名字。");
  if (!d.model.trim()) throw new Error("请先选择一个模型，或手动填写模型 ID。");
  if (d.mode === "api" && !d.provider) throw new Error("请选择 API 供应商。");
  let parameters = {};
  try {
    parameters = JSON.parse(d.parameterText.trim() || "{}");
  } catch {
    throw new Error("默认请求参数需要填写有效的 JSON。");
  }
  if (
    !parameters ||
    Array.isArray(parameters) ||
    typeof parameters !== "object"
  )
    throw new Error("默认请求参数需要填写 JSON 对象。");
  return {
    name: d.name.trim(),
    description: d.description || "",
    mode: d.mode,
    provider_id: d.mode === "api" ? d.provider : null,
    model: d.model.trim(),
    instructions: d.instructions,
    parameters,
  };
}
function formError(message) {
  const n = $("#config-error");
  if (n) {
    n.innerHTML = `<div class="form-error" role="alert">${esc(message)}</div>`;
    n.scrollIntoView({ block: "center", behavior: "smooth" });
  } else toast(message);
}
async function persistDraft() {
  const d = state.draft,
    payload = draftPayload();
  const saved = await api("/projects" + (d.id ? "/" + d.id : ""), {
    method: d.id ? "PUT" : "POST",
    body: JSON.stringify(payload),
  });
  d.id = saved.id;
  d.parameters = saved.parameters;
  if (state.draft === d && $("#save-config"))
    $("#save-config").innerHTML = icon("check") + "保存更改";
  const view = projectView(saved),
    index = projects.findIndex((p) => p.id === saved.id);
  if (index < 0) projects.unshift(view);
  else projects[index] = view;
  return saved;
}
async function saveDraft(e) {
  e.preventDefault();
  if (state.saving || state.test.status === "running") return;
  const isNew = !state.draft.id,
    button = $("#save-config");
  state.saving = true;
  button.disabled = true;
  try {
    const saved = await persistDraft();
    location.hash = "#/project/" + saved.id;
    toast(
      isNew
        ? "项目已创建，可以通过 Python 调用。"
        : "项目配置已保存，下一次调用生效。",
    );
  } catch (e) {
    formError(e.message);
  } finally {
    state.saving = false;
    if (button.isConnected) button.disabled = false;
  }
}
function testPanel() {
  const d = state.draft || {},
    p = providerFor(d),
    t = state.test,
    labels = ["代理连接", "账号 / API 验证", "模型响应"];
  return `<section class="test-panel"><h2>确认这个模型可以调用</h2><p>保存当前配置，并发送一次最小请求。</p><div class="test-current">${icon(d.mode === "gpt" ? "globe" : "plug")}<div><strong>${esc(d.model || "请先选择模型")}</strong><small>${esc(p.name)} · 本机代理</small></div></div><button type="button" class="btn secondary" data-action="test" ${!d.model || t.status === "running" || state.saving || state.discovery === "loading" ? "disabled" : ""}>${t.status === "running" ? '<span class="spinner"></span>' : icon("bolt")}${t.status === "running" ? "正在测试…" : t.status === "success" ? "重新测试连接" : "测试连接"}</button>${t.status !== "idle" ? `<div class="test-progress">${labels.map((n, i) => `<div class="test-step ${t.status === "success" ? "done" : t.status === "error" && t.step === i ? "error" : t.status === "running" && t.step === i ? "running" : t.step > i ? "done" : ""}">${t.status === "success" || t.step > i ? icon("check") : t.status === "running" && t.step === i ? '<span class="spinner"></span>' : icon("circle")}<span>${n}</span><small>${t.status === "success" ? "已通过" : t.status === "error" && t.step === i ? "未通过" : t.step > i ? "已通过" : t.step === i ? "检测中" : "等待"}</small></div>`).join("")}</div>` : ""}${t.status === "success" ? `<div class="test-response"><strong>${icon("check")}连接成功，模型已就绪</strong><p>模型回复：${esc(t.text)}</p><p>总耗时 ${(t.latency_ms / 1000).toFixed(2)} s · 用量已归入当前项目</p></div>` : t.status === "error" ? `<div class="test-response error"><strong>${icon("info")}连接未成功</strong><p>${esc(t.error)}</p></div>` : ""}<div class="test-footnote">测试会保存项目配置并产生少量模型用量。</div></section>`;
}
async function testConnection() {
  if (state.test.status === "running" || state.saving) return;
  try {
    draftPayload();
  } catch (e) {
    formError(e.message);
    return;
  }
  const nonce = ++state.testNonce;
  state.test = { status: "running", step: 0 };
  refreshModelPanel();
  // Lock draft controls while the saved configuration is being tested.
  const controls = [
    ...$("#config-form").querySelectorAll("input,textarea,select,button"),
  ];
  controls.forEach((n) => (n.disabled = true));
  try {
    const saved = await persistDraft();
    const connection = await api("/connection");
    if (nonce !== state.testNonce) return;
    if (!connection.ready)
      throw new Error(
        connection.error || "请检查 CC Switch 的本机代理、聚合模式与请求日志。",
      );
    state.test = { status: "running", step: 1 };
    refreshModelPanel();
    if (saved.mode === "gpt" && !connection.account_ready)
      throw new Error("请在 CC Switch 激活 GPT 官方账号并完成登录。");
    state.test = { status: "running", step: 2 };
    refreshModelPanel();
    const result = await api("/projects/" + saved.id + "/test", {
      method: "POST",
    });
    if (nonce !== state.testNonce) return;
    state.test = { status: "success", step: 3, ...result };
  } catch (e) {
    if (nonce !== state.testNonce) return;
    state.test = { status: "error", step: state.test.step, error: e.message };
  } finally {
    controls.forEach((n) => (n.disabled = false));
    if (nonce === state.testNonce) {
      refreshModelPanel();
      await refresh(false);
    }
  }
}
function runtimePanel(c) {
  const s = state.setup || {};
  const checks = [
    [!!c.data_directory && !c.error, "CC Switch 数据目录", c.data_directory || s.cc_dir, "打开 CC Switch 完成初始化，默认目录为 ~/.cc-switch。"],
    [c.proxy_online, "代理运行状态", c.proxy_url, "打开 CC Switch，在 Codex 页面启动本机代理。"],
    [c.aggregation, "聚合模式", "", "在 CC Switch 的 Codex 页面启用聚合模式，并加入需要使用的供应商。"],
    [c.logging, "请求日志", "", "在 CC Switch 的代理设置中开启请求日志，用于同步项目用量。"],
    [c.account_ready, "GPT 登录", "", "使用 GPT 时，在 CC Switch 激活官方账号并完成 Codex 登录。仅用 API 时可忽略此项。"],
    [!!s.codex_path, "Codex 可执行文件", s.codex_path, "请在下方填写 codex 的完整路径，以便自动刷新 GPT 登录。"],
  ];
  return `<section class="panel runtime-panel"><div class="panel-head"><div><h2>本机连接检查</h2><p>数据保存在 ${esc(s.data_dir || "~/.local/share/ccask")} · App 菜单可查看日志</p></div></div>${checks.map(([ok, title, detail, help]) => `<div class="runtime-check"><strong>${ok ? "✓" : "!"} ${title}</strong><span>${esc(ok ? detail || "已就绪" : help)}</span></div>`).join("")}<form id="runtime-form"><label class="field"><span>手动指定 Codex 路径（留空恢复自动查找）</span><input class="input mono" id="codex-path" value="${esc(s.configured_codex_path || "")}" placeholder="/opt/homebrew/bin/codex"></label><button class="btn secondary small" type="submit">保存路径</button></form></section>`;
}
function connections() {
  const c = state.connection || {}, ready = c.ready;
  const rows = providers.map((p) => {
    const count = activeProjects().filter((v) => v.mode === "gpt" ? p.mode === "gpt" && p.default : v.provider === p.id).length;
    const description = p.mode === "gpt" ? (p.default ? "当前激活的官方账号" : "在 CC Switch 激活后可使用") : "CC Switch API 供应商";
    const inputs = p.models.some((m) => m.vision) ? "文本 / 图片" : p.models.length ? "文本 · 按模型配置" : "待识别";
    return `<article class="source-row"><span class="project-icon">${icon(p.mode === "gpt" ? "globe" : "plug")}</span><div class="source-row-title"><h2>${esc(p.name)}</h2><p>${description}</p></div><div class="source-row-fact"><span>${p.mode === "gpt" ? "绑定账号" : "模型列表"}</span><strong>${p.mode === "gpt" ? esc(p.account || "待激活") : p.models.length + " 个已识别模型"}</strong></div><div class="source-row-fact"><span>关联项目</span><strong>${count} 个项目</strong></div><div class="source-row-fact source-row-inputs"><span>输入支持</span><strong>${inputs}</strong></div><span class="badge ${p.status === "ready" ? "success" : "warning"}"><span class="dot"></span>${p.status === "ready" ? "可用" : "待检查"}</span><button class="btn secondary small" data-action="connection-info" data-value="${esc(p.id)}">${icon("info")}连接说明</button></article>`;
  }).join("");
  return `${runtimePanel(c)}<div class="callout connection-status">${icon("shield")}${ready ? "本机代理已就绪" : esc(c.error || "请在 CC Switch 检查代理与聚合配置")}<span class="mono">${esc(c.proxy_url || "代理未配置")}</span><span class="badge ${c.aggregation ? "success" : "warning"}">${c.aggregation ? "聚合模式" : "聚合未开启"}</span></div><div class="connection-list">${rows || '<div class="empty-state"><p>在 CC Switch 配好供应商后，点击“刷新连接”。</p></div>'}</div>${footer()}`;
}
function footer() {
  return `<footer class="footer"><span>${icon("shield")}全部模型调用统一经过 CC Switch</span><span>每 5 秒同步 · 费用按 CC Switch 美元记录</span></footer>`;
}
async function refresh(showToast = false) {
  if (state.refreshing) {
    await state.refreshFinished;
    return refresh(showToast);
  }
  state.refreshing = true;
  let finishRefresh;
  state.refreshFinished = new Promise((resolve) => {
    finishRefresh = resolve;
  });
  try {
    await api("/usage/sync", { method: "POST" });
    const [connection, list, report, setup, monitor] = await Promise.all([
      api("/connection"),
      api("/projects?include_archived=true"),
      api("/usage"),
      api("/setup"),
      api("/menubar"),
    ]);
    state.report = report;
    state.connection = connection;
    state.installPath = setup.install_path;
    state.setup = setup;
    state.menuUsage = monitor;
    document.documentElement.classList.toggle("desktop-shell", setup.desktop);
    updateProviders(connection);
    projects = list.map(projectView);
    const r = route();
    if (r.page === "project" && r.id)
      state.projectRecords[r.id] = (
        await api("/usage?project_id=" + encodeURIComponent(r.id))
      ).requests;
    state.loading = false;
    state.loadError = "";
    updateSidebar();
    const editing =
      r.page === "new" || r.page === "settings" || (r.page === "project" && r.tab === "settings");
    const interacting = document.activeElement?.matches(
      "input,textarea,select",
    );
    if ((!editing && !interacting) || !currentRoute) render();
    if (showToast) toast("项目、用量与连接已刷新。");
  } catch (e) {
    state.loading = false;
    state.loadError = e.message;
    if (!currentRoute)
      $("#app").innerHTML =
        `<div class="empty-state"><h3>读取项目失败</h3><p>${esc(e.message)}</p><button class="btn secondary" data-action="retry-load">重新加载</button></div>`;
    toast(e.message);
  } finally {
    state.refreshing = false;
    finishRefresh();
  }
}
function updateSidebar() {
  const c = state.connection || {};
  $("#connection-mini").innerHTML =
    `<div><span class="dot" style="color:${c.ready ? "var(--success)" : "var(--warning)"}"></span>${c.ready ? "CC Switch 已连接" : "CC Switch 待检查"}</div><small>${esc(c.proxy_url || c.error || "所有模型调用的统一出口")}</small>`;
}
function showRequest(id, value) {
  const p = projects.find((p) => p.id === id),
    r = requestRows(p).find((r) => r.id === value);
  if (!r) return;
  const facts = [
    ["项目", p.name],
    ["请求 ID", r.id],
    ["模型", r.model],
    ["连接 / 账号", r.account_label || r.provider_name],
    ["状态", statusLabels[r.status] || r.status],
    ["新增输入 Token", r.fresh_input == null ? "—" : fmt(r.fresh_input)],
    ["输出 Token", r.output_tokens == null ? "—" : fmt(r.output_tokens)],
    ["缓存读取", r.cache_read == null ? "—" : fmt(r.cache_read)],
    ["缓存写入", r.cache_write == null ? "—" : fmt(r.cache_write)],
    ["总 Token", r.total_tokens == null ? "—" : fmt(r.total_tokens)],
    ["耗时", (r.latency_ms / 1000).toFixed(2) + " s"],
    [
      "CC Switch 估算费用（美元）",
      r.cost == null ? "—" : "$" + Number(r.cost).toFixed(6),
    ],
  ];
  showDialog(
    "调用详情",
    `<div class="request-facts">${facts.map(([k, v]) => `<div><span>${k}</span><span>${esc(v)}</span></div>`).join("")}</div>${r.error_code ? `<div class="callout">${esc(r.error_code)}</div>` : r.usage_status === "pending" ? '<div class="callout">正在等待 CC Switch 同步本次用量。</div>' : ""}`,
  );
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-action]");
  if (!b) return;
  const a = b.dataset.action,
    v = b.dataset.value,
    id = b.dataset.id;
  if (
    state.test.status === "running" &&
    ["mode", "model", "discover", "confirm-model"].includes(a)
  )
    return;
  if (a === "range") {
    state.range = v;
    render();
  } else if (a === "new") location.hash = "#/new";
  else if (a === "clear-search") {
    state.search = "";
    state.status = "all";
    render();
  } else if (a === "breakdown") {
    state.breakdown = v;
    render();
  } else if (a === "mode") chooseMode(v);
  else if (a === "discover") discoverModels();
  else if (a === "model") {
    state.draft.model = v;
    invalidateTest();
    refreshModelPanel();
  } else if (a === "capability") {
    state.capability = v;
    document
      .querySelectorAll('[data-action="capability"]')
      .forEach((n) => n.classList.toggle("active", n.dataset.value === v));
    refreshModelPanel();
  } else if (a === "test") testConnection();
  else if (a === "copy-code") copy(codeText(projects.find((p) => p.id === id)));
  else if (a === "copy-install") copy(installCommand(), "安装命令");
  else if (a === "project-menu") projectMenu(b, id);
  else if (a === "close-dialog") closeDialog();
  else if (a === "manual-model")
    showDialog(
      "手动填写模型 ID",
      '<p class="dialog-description">输入供应商提供的模型 ID，能力以实际连接测试为准。</p><label class="field parameters-field"><span>模型 ID</span><input id="manual-model-id" class="input mono" maxlength="300" placeholder="例如：my-model-id" autocomplete="off"></label>',
      '<button class="btn secondary" data-action="close-dialog">取消</button><button class="btn" data-action="confirm-model">使用此模型</button>',
    );
  else if (a === "confirm-model") {
    const value = $("#manual-model-id").value.trim();
    if (!value) {
      $("#manual-model-id").focus();
      return;
    }
    state.draft.model = value;
    if (!state.models.some((m) => m.id === value))
      state.models.push({ id: value, name: value, vision: false });
    state.discovery = "success";
    invalidateTest();
    closeDialog();
    refreshModelPanel();
  } else if (a === "archive") {
    const p = projects.find((p) => p.id === id);
    showDialog(
      "归档这个项目？",
      `<p class="dialog-description">“${esc(p.name)}”将从项目列表中移除，历史用量仍保留在总览中。</p>`,
      '<button class="btn secondary" data-action="close-dialog">取消</button><button class="btn" data-action="confirm-archive" data-id="' +
        id +
        '">归档项目</button>',
    );
  } else if (a === "confirm-archive") {
    b.disabled = true;
    try {
      await api("/projects/" + id + "/archive", { method: "POST" });
      closeDialog();
      if (route().id === id) location.hash = "#/projects";
      await refresh();
      toast("项目已归档，历史用量仍计入总览。");
    } catch (e) {
      toast(e.message);
      b.disabled = false;
    }
  } else if (a === "delete-project") {
    const p = projects.find((p) => p.id === id);
    showDialog(
      "删除这个项目？",
      `<p class="dialog-description">删除“${esc(p.name)}”后，该项目的配置、会话记忆、调用记录和用量将一起永久清除，总览也会扣除对应的调用次数、Token 和费用。此操作无法撤销。</p>`,
      `<button class="btn secondary" data-action="close-dialog">取消</button><button class="btn danger" data-action="confirm-delete-project" data-id="${esc(id)}">删除项目及用量</button>`,
    );
  } else if (a === "confirm-delete-project") {
    b.disabled = true;
    try {
      // Wait for a refresh already in flight, then load a fresh post-deletion report.
      await api("/projects/" + id, { method: "DELETE" });
      projects = projects.filter((p) => p.id !== id);
      state.report.rollups = state.report.rollups.filter(
        (r) => r.project_id !== id,
      );
      state.report.requests = state.report.requests.filter(
        (r) => r.project_id !== id,
      );
      delete state.projectRecords[id];
      if (state.draft?.id === id) state.draft = null;
      closeDialog();
      if (route().id === id) location.hash = "#/projects";
      render();
      await refresh();
      toast("项目已删除，相关用量、调用记录和会话已清除。");
    } catch (e) {
      toast(e.message);
      b.disabled = false;
    }
  } else if (a === "request-detail") showRequest(id, v);
  else if (a === "connection-info") {
    const p = providers.find((p) => p.id === v);
    showDialog(
      esc(p.name),
      `<p class="dialog-description">${p.mode === "gpt" ? "项目跟随 CC Switch 当前激活的官方账号。历史用量按原账号和连接保存。" : "在 CC Switch 管理此供应商的 API 地址、密钥和聚合配置。项目独立选择其模型。"}</p><div class="callout space-top">${p.status === "ready" ? "本机代理与路由已就绪，可在项目配置中测试模型实际响应。" : "请检查本机代理、聚合模式、请求日志及当前账号配置。"}</div>`,
    );
  } else if (a === "refresh-connections" || a === "retry-load") {
    b.disabled = true;
    await refresh(true);
    if (b.isConnected) b.disabled = false;
  } else if (a === "channel" || a === "trend-channel") {
    toggleChannel(v);
    render();
  } else if (a === "home-tab") {
    state.homeTab = v;
    $("#workspace-scroll").scrollTop = 0;
    render();
  } else if (a === "distribution-view") {
    state.distributionView = v;
    render();
  }
});
document.addEventListener("input", (e) => {
  const n = e.target;
  if (n.dataset.field && state.draft) {
    state.draft[n.dataset.field] = n.value;
    invalidateTest();
    refreshModelPanel();
  } else if (n.id === "project-search") {
    state.search = n.value;
    $("#project-grid").innerHTML = projectCards();
  } else if (n.id === "model-search") {
    state.modelSearch = n.value;
    refreshModelPanel();
  }
});
document.addEventListener("change", (e) => {
  const n = e.target,
    fields = {
      "project-sort": "projectSort",
      "distribution-sort": "distributionSort",
      "distribution-metric": "distributionMetric",
      "python-project": "codeProject",
    };
  if (fields[n.id]) {
    state[fields[n.id]] = n.value;
    render();
  } else if (n.id === "status-filter") {
    state.status = n.value;
    $("#project-grid").innerHTML = projectCards();
  } else if (n.id === "draft-reasoning-effort") {
    try { setReasoningEffort(n.value); } catch (e) { formError(e.message); }
  } else if (n.id === "draft-provider") {
    state.draft.provider = n.value;
    state.draft.model = "";
    state.modelSearch = "";
    state.models = [];
    $("#model-search").value = "";
    discoverModels();
  } else if (n.id === "record-filter") {
    state.recordFilter = n.value;
    render();
  }
});
document.addEventListener("submit", async (e) => {
  if (e.target.id === "menubar-form") {
    e.preventDefault();
    const button = e.target.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const project_ids = [...e.target.querySelectorAll('input[name="monitor-project"]:checked')].map(n => n.value);
      await api("/settings/menubar", {method: "PUT", body: JSON.stringify({project_ids, period: $("#menubar-period").value})});
      await refresh();
      render();
      toast("菜单栏设置已保存，5 秒内更新。");
    } catch (err) { toast(err.message); }
    finally { if (button.isConnected) button.disabled = false; }
  }
  if (e.target.id === "runtime-form") {
    e.preventDefault();
    try {
      await api("/settings", {method: "PUT", body: JSON.stringify({codex_path: $("#codex-path").value.trim()})});
      toast("Codex 路径已保存");
      await refresh();
    } catch (err) { toast(err.message); }
  }
  if (e.target.id === "config-form") saveDraft(e);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelector(".popover")?.remove();
    document.querySelector(".menu-overlay")?.remove();
  }
});
window.addEventListener("hashchange", async () => {
  document.querySelector(".popover")?.remove();
  document.querySelector(".menu-overlay")?.remove();
  render();
  const r = route();
  if (r.page === "project" && r.id) {
    try {
      state.projectRecords[r.id] = (
        await api("/usage?project_id=" + encodeURIComponent(r.id))
      ).requests;
      if (route().id === r.id && route().tab !== "settings") render();
    } catch (e) {
      toast(e.message);
    }
  }
});
hydrateIcons();
$("#app").innerHTML =
  '<div class="empty-state"><span class="spinner"></span><p>正在读取项目与用量…</p></div>';
refresh();
setInterval(() => {
  if (!document.hidden && !$("#dialog").open && state.test.status !== "running")
    refresh();
}, 5000);
