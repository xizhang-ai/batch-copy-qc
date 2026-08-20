import type {
  BoardData, ClassifiedTypeFile, ConnectionStatus, CopyType, ExportRun,
  ParsedBrief, Project, QcRule,
} from "./contracts";

const now = "2026-08-21T00:42:00+09:00";

export const fixtureProjects: Project[] = [
  { id: "p-demo", name: "清爽气泡水 8 月种草", category: "即饮饮料", brand: "微沫", status: "confirmed", updated_at: now },
  { id: "p-draft", name: "无糖薄荷糖秋季内容", category: "糖果", brand: "风庭", status: "draft", updated_at: "2026-08-20T17:10:00+09:00" },
];

export const fixtureParsedBrief: ParsedBrief = {
  source_name: "清爽气泡水项目brief.md",
  findings: [
    { id: "bf-1", section: "project_content", label: "品牌与 SKU", value: "微沫青柚气泡水 · 330ml 罐装", evidence: "品牌微沫，主推青柚味 330ml 罐装。", confidence: "high" },
    { id: "bf-2", section: "project_content", label: "目标人群", value: "通勤久坐、在意糖分的 22–32 岁上班族", evidence: "面向 22–32 岁办公室人群，重点沟通低负担。", confidence: "high" },
    { id: "bf-3", section: "copy_requirements", label: "典型场景", value: "午后犯困、火锅聚餐、下班追剧", evidence: "场景可以从午后、火锅和追剧切入。", confidence: "high" },
    { id: "bf-4", section: "copy_requirements", label: "表达方式", value: "第一人称体验，先场景后产品事实", evidence: "不要像产品说明书，要有真实生活开场。", confidence: "medium" },
    { id: "bf-5", section: "qc_requirements", label: "禁止宣称", value: "不得出现减肥、燃脂、零负担", evidence: "严禁减肥、燃脂、零负担等功效暗示。", confidence: "high" },
    { id: "bf-6", section: "qc_requirements", label: "事实依据", value: "仅可使用营养成分表和品牌提供的配料表", evidence: "所有成分与规格描述以附件事实表为准。", confidence: "high" },
    { id: "bf-7", section: "needs_confirmation", label: "活动价格", value: "", evidence: "8 月活动价格待电商侧确认。", confidence: "low" },
  ],
};

export const fixtureCopyTypes: CopyType[] = [{
  id: "ct-commute",
  project_id: "p-demo",
  name: "通勤包里常备",
  quantity: 4,
  sources: ["reference", "manual"],
  input_modes: ["reference_examples", "description_requirements"],
  type_brief: "用通勤下午犯困的真实情境，写成一篇轻松的日常分享。",
  requirements: {
    title_direction: "具体场景 + 意外发现，不用夸张感叹",
    body_structure: "困扰开场 → 随手拿出 → 口味体验 → 产品事实 → 适合谁",
    tone: "像同事间分享，轻松克制",
    persona: "每天地铁通勤的普通上班族",
    scenario: "下午三点工位、地铁回家",
    topic_requirements: "品牌、青柚气泡水、办公室饮品",
  },
  must_include: ["青柚味", "330ml", "配料事实"],
  must_avoid: ["减肥", "燃脂", "全网最好喝"],
  references: [{
    id: "ref-1",
    title: "下午三点，我终于没再点甜咖啡",
    body: "下午开会前总想喝点有味道的，最近会从冰箱拿一罐气泡饮。青柚的香气比较清爽，配午饭也不会抢味。",
    topics: ["办公室饮品", "打工人日常"],
    raw_text: "下午三点，我终于没再点甜咖啡\n下午开会前总想喝点有味道的……\n#办公室饮品 #打工人日常",
  }],
  reference_profile: {
    title_hook: "时间点 + 习惯变化",
    structure_rhythm: "短场景开头，中段两段体验，结尾回到使用人群",
    point_of_view: "第一人称回顾",
    tone: "自然、克制、少感叹号",
    persona: "规律通勤的办公室职员",
    scenario: "工作日下午与午餐搭配",
    information_density: "每段一个信息点",
    ending: "用适用场景收束，不强行号召购买",
    topic_strategy: "3–5 个精准话题",
    source_facts: ["参考帖中的甜咖啡和个人作息属于来源事实，不得带入"],
    avoid_expressions: ["终于没再点", "从冰箱拿一罐"],
    confirmed: true,
  },
}];

export const fixtureClassifiedFiles: ClassifiedTypeFile[] = [
  { id: "file-1", filename: "聚餐场景参考.md", suggested_type: "聚餐解腻分享", evidence: "多次出现火锅、朋友聚餐和冰饮搭配", confidence: "medium" },
];

export const fixtureRules: QcRule[] = [
  { id: "rule-1", project_id: "p-demo", scope: "project", level: "hard", category: "claim", statement: "不得出现减肥、燃脂、零负担等功效暗示", source_kind: "explicit_project_qc", source_evidence: "项目 Brief 禁止宣称", enabled: true },
  { id: "rule-2", project_id: "p-demo", scope: "project", level: "hard", category: "fact", statement: "规格、成分和口味必须能在事实表中找到依据", source_kind: "explicit_project_qc", source_evidence: "项目 Brief 产品事实", enabled: true },
  { id: "rule-3", project_id: "p-demo", copy_type_id: "ct-commute", scope: "type", level: "soft", category: "style", statement: "使用第一人称真实通勤场景，不使用营销口播", source_kind: "explicit_type_qc", source_evidence: "通勤包里常备 · 描述要求", enabled: true },
  { id: "rule-4", project_id: "p-demo", copy_type_id: "ct-commute", scope: "type", level: "soft", category: "structure", statement: "一定要有：青柚味、330ml、配料事实", source_kind: "derived_type_constraint", source_evidence: "来自帖子类型约束", enabled: true },
  { id: "rule-5", project_id: "p-demo", scope: "project", level: "pending", category: "other", statement: "活动价格确认后才能写入正文", source_kind: "explicit_project_qc", source_evidence: "活动价格仍待确认", enabled: true },
];

export const fixtureBoard: BoardData = {
  project_id: "p-demo",
  run_id: "run-20260821-01",
  run_status: "running",
  updated_at: now,
  items: [
    { id: "XHS-0042", copy_type_id: "ct-commute", copy_type_name: "通勤包里常备", ordinal: 1, title: "下午三点的清爽备选", body: "工位坐久了，下午总想喝点有味道的。最近包里会多放一罐青柚气泡水，330ml 刚好是一轮会议的量。入口先是淡淡青柚香，再有细细的气泡感。配料信息都按包装写清楚，不把饮料说成什么神奇解法。", tags: ["办公室饮品", "青柚气泡水", "打工人日常"], workflow_status: "pending_ai_qc", version: 1, auto_rewrite_count: 0, findings: [], updated_at: now },
    { id: "XHS-0043", copy_type_id: "ct-commute", copy_type_name: "通勤包里常备", ordinal: 2, title: "正在核对产品事实", body: "", tags: [], workflow_status: "ai_qc_running", version: 1, auto_rewrite_count: 0, progress: "审查官正在核对 6 条规则 · 62%", findings: [], updated_at: now },
    { id: "XHS-0044", copy_type_id: "ct-commute", copy_type_name: "通勤包里常备", ordinal: 3, title: "正在收紧夸张表达", body: "", tags: [], workflow_status: "ai_rewrite_running", version: 2, auto_rewrite_count: 1, progress: "修改 2 处表达，完成后将重新 QC", findings: [], updated_at: now },
    { id: "XHS-0045", copy_type_id: "ct-commute", copy_type_name: "通勤包里常备", ordinal: 4, title: "午后想喝点有味道的", body: "下午容易犯困的时候，我会喝一罐冰冰的青柚气泡水。330ml 不占地方，青柚味很清新，喝完完全零负担。配料表里写了赤藓糖醇，入口不会太甜。", tags: ["办公室饮品", "气泡水", "下午茶"], workflow_status: "human_review", review_disposition: "open", version: 3, auto_rewrite_count: 2, similarity_score: 0.18, findings: [
      { id: "f-1", level: "hard", category: "禁止宣称", status: "open", message: "出现禁止宣称“零负担”", evidence: "喝完完全零负担", suggestion: "删除功效或负担暗示，改为可感知的口味体验", field: "body", auto_fixable: true, confidence: 0.99 },
      { id: "f-2", level: "hard", category: "事实依据", status: "open", message: "“赤藓糖醇”未在当前事实表中找到", evidence: "配料表里写了赤藓糖醇", suggestion: "核对附件；若无依据则删除", field: "body", auto_fixable: false, confidence: 0.86 },
    ], updated_at: now },
    { id: "XHS-0039", copy_type_id: "ct-commute", copy_type_name: "通勤包里常备", ordinal: 5, title: "下班路上的一口青柚气泡", body: "地铁到站前想喝点清爽的，330ml 的青柚气泡水刚好能放进通勤包侧袋。", tags: ["通勤日常", "青柚气泡水"], workflow_status: "completed", completion_reason: "ai_pass", version: 1, auto_rewrite_count: 0, similarity_score: 0.12, findings: [], updated_at: now },
    { id: "XHS-0040", copy_type_id: "ct-commute", copy_type_name: "通勤包里常备", ordinal: 6, title: "火锅局里负责清爽的那一罐", body: "周末聚餐我带了几罐青柚味气泡水。", tags: ["朋友聚餐", "气泡水"], workflow_status: "completed", completion_reason: "human_pass", version: 2, auto_rewrite_count: 1, findings: [], updated_at: now },
    { id: "XHS-0041", copy_type_id: "ct-commute", copy_type_name: "通勤包里常备", ordinal: 7, title: "冰箱里常备的小罐清爽", body: "青柚味和细气泡很适合配重口味晚餐。", tags: ["晚餐搭配", "青柚"], workflow_status: "completed", completion_reason: "forced_pass", version: 4, auto_rewrite_count: 2, findings: [], updated_at: now },
  ],
};

export const fixtureConnections: ConnectionStatus = {
  model: { configured: true, adapter: "CLIPROXY", model: "generation / qc 已分离" },
  feishu: { configured: false, adapter: "Fake Adapter", target: "等待 .env 配置" },
};

export const fixtureExports: ExportRun[] = [{
  id: "export-20260820-01", project_id: "p-demo", generation_run_id: "run-20260820-02",
  status: "succeeded", sheet_id: "fake-sheet-001", sheet_title: "8月种草·第2批",
  row_count: 8, adapter: "fake", created_at: "2026-08-20T16:30:00+09:00",
}];
