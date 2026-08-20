import { ApiError } from "./client";
import { fixtureBoard, fixtureClassifiedFiles, fixtureConnections, fixtureCopyTypes, fixtureExports, fixtureParsedBrief, fixtureProjects, fixtureRules } from "./fixtures";
import type { BoardData, ClassifiedTypeFile, ConnectionStatus, CopyItem, CopyType, ExportRun, GenerationRun, ParsedBrief, ParsedTypeBrief, Project, QcRule, ReviewPayload, RewriteSelectionPayload } from "./contracts";

const delay = (ms = 120) => new Promise((resolve) => window.setTimeout(resolve, ms));
const clone = <T,>(value: T): T => structuredClone(value);
let projects = clone(fixtureProjects);
let copyTypes = clone(fixtureCopyTypes);
let rules = clone(fixtureRules);
let board = clone(fixtureBoard);
let exportsHistory = clone(fixtureExports);
let classifiedFiles = clone(fixtureClassifiedFiles);

function emptyCopyType(projectId: string): CopyType {
  return { id: crypto.randomUUID(), project_id: projectId, name: "", quantity: 1, sources: ["manual"], input_modes: [], type_brief: "", requirements: { title_direction: "", body_structure: "", tone: "", persona: "", scenario: "", topic_requirements: "" }, must_include: [], must_avoid: [], references: [] };
}
function projectOrThrow(projectId: string) {
  const project = projects.find((item) => item.id === projectId);
  if (!project) throw new ApiError("PROJECT_NOT_FOUND", "项目不存在", 404);
  return project;
}

export const mockApi = {
  async listProjects(): Promise<Project[]> { await delay(); return clone(projects); },
  async getProject(projectId: string): Promise<Project> { await delay(); return clone(projectOrThrow(projectId)); },
  async createProject(input: Pick<Project, "name" | "brand" | "category">): Promise<Project> { const project: Project = { ...input, id: crypto.randomUUID(), status: "draft", updated_at: new Date().toISOString() }; projects = [project, ...projects]; await delay(); return clone(project); },
  async parseProjectBrief(projectId: string, input: { text?: string; file?: File }): Promise<ParsedBrief> { projectOrThrow(projectId); await delay(420); return clone({ ...fixtureParsedBrief, source_name: input.file?.name ?? "粘贴文本" }); },
  async saveProjectFindings(projectId: string, parsed: ParsedBrief): Promise<Project> { const project = projectOrThrow(projectId); project.status = "confirmed"; project.structured = { findings: parsed.findings }; project.updated_at = new Date().toISOString(); await delay(); return clone(project); },
  async listCopyTypes(projectId: string): Promise<CopyType[]> { await delay(); return clone(copyTypes.filter((item) => item.project_id === projectId)); },
  async createCopyType(projectId: string): Promise<CopyType> { const item = emptyCopyType(projectId); copyTypes = [...copyTypes, item]; await delay(); return clone(item); },
  async saveCopyType(item: CopyType): Promise<CopyType> { copyTypes = copyTypes.map((entry) => entry.id === item.id ? clone(item) : entry); await delay(); return clone(item); },
  async parseCopyTypeBrief(): Promise<ParsedTypeBrief> { await delay(350); return { requirements: { title_direction: "具体场景与轻微反差", body_structure: "场景 → 体验 → 产品事实 → 适用人群", tone: "自然克制", persona: "普通消费者", scenario: "从 Brief 原文识别的生活场景", topic_requirements: "品牌、产品与场景精准话题" }, sources: ["brief"], parsed_finding_count: 8, project_change_suggestions: [{ id: "type-brief-project-1", section: "brand", value: "微沫实验室", source_quote: "品牌：微沫实验室", confidence: 0.92, decision: "pending" }], conflicts: [{ id: "type-brief-conflict-1", section: "unclassified_requirement", value: "活动价待电商确认", source_quote: "活动：价格待确认", confidence: 0.68, decision: "pending" }] }; },
  async deleteCopyType(id: string): Promise<void> { copyTypes = copyTypes.filter((item) => item.id !== id); await delay(); },
  async analyzeReferences(): Promise<NonNullable<CopyType["reference_profile"]>> { await delay(500); return clone(fixtureCopyTypes[0].reference_profile!); },
  async listClassifiedFiles(projectId: string): Promise<ClassifiedTypeFile[]> { await delay(); return projectId === "p-demo" ? clone(classifiedFiles) : []; },
  async classifyTypeFiles(files: File[]): Promise<ClassifiedTypeFile[]> { await delay(420); const created = files.map((file) => ({ id: crypto.randomUUID(), filename: file.name, suggested_type: "待建立的新类型", evidence: "文件包含重复出现的场景与表达要求", confidence: "medium" as const })); classifiedFiles = [...classifiedFiles, ...created]; return clone(created); },
  async assignTypeFile(sourceId: string, copyTypeId: string | null): Promise<void> { classifiedFiles = classifiedFiles.map((file) => file.id === sourceId ? { ...file, assigned_type_id: copyTypeId } : file); await delay(); },
  async listRules(projectId: string): Promise<QcRule[]> { await delay(); return clone(rules.filter((rule) => rule.project_id === projectId)); },
  async saveRule(rule: QcRule): Promise<QcRule> { rules = rules.map((entry) => entry.id === rule.id ? clone(rule) : entry); await delay(); return clone(rule); },
  async createRule(projectId: string, rule: Omit<QcRule, "id" | "project_id">): Promise<QcRule> { const created = { ...rule, id: crypto.randomUUID(), project_id: projectId }; rules = [...rules, created]; await delay(); return clone(created); },
  async deleteRule(ruleId: string): Promise<void> { rules = rules.filter((item) => item.id !== ruleId); await delay(); },
  async getBoard(projectId: string): Promise<BoardData> { await delay(80); return clone({ ...board, project_id: projectId, items: projectId === "p-demo" ? board.items : [] }); },
  async createGenerationRun(projectId: string): Promise<GenerationRun> { board.run_id = `run-${Date.now()}`; board.run_status = "running"; await delay(240); return { id: board.run_id, project_id: projectId, status: "running", total_requested: copyTypes.filter((item) => item.project_id === projectId).reduce((sum, item) => sum + item.quantity, 0) }; },
  async retryQc(itemId: string): Promise<CopyItem> { const item = board.items.find((entry) => entry.id === itemId)!; item.workflow_status = "pending_ai_qc"; item.updated_at = new Date().toISOString(); await delay(); return clone(item); },
  async getItem(itemId: string): Promise<CopyItem> { const item = board.items.find((entry) => entry.id === itemId)!; await delay(40); return clone(item); },
  async saveItem(itemId: string, patch: Pick<CopyItem, "title" | "body" | "tags" | "version">): Promise<CopyItem> { const item = board.items.find((entry) => entry.id === itemId)!; Object.assign(item, patch, { version: item.version + 1, updated_at: new Date().toISOString() }); await delay(); return clone(item); },
  async rewriteSelection(itemId: string, payload: RewriteSelectionPayload): Promise<CopyItem> { const item = board.items.find((entry) => entry.id === itemId)!; if (item.version !== payload.expected_version) throw new ApiError("ITEM_VERSION_CONFLICT", "文案已产生新版本，请重新加载后再修改", 409); const source = item[payload.field]; const replacement = `${payload.selected_text}（已按“${payload.instruction}”调整）`; item[payload.field] = source.slice(0, payload.selection_start) + replacement + source.slice(payload.selection_end); item.version += 1; item.workflow_status = "human_review"; item.updated_at = new Date().toISOString(); await delay(450); return clone(item); },
  async reviewItem(itemId: string, payload: ReviewPayload): Promise<CopyItem> { const item = board.items.find((entry) => entry.id === itemId)!; if (payload.action === "force_pass") { if (!payload.legacy_issues?.length) throw new ApiError("FORCE_PASS_ISSUES_REQUIRED", "强制通过必须填写遗留问题", 400); if (payload.legacy_issues.some((issue) => !issue.trim())) throw new ApiError("REQUEST_VALIDATION_FAILED", "遗留问题不能包含空白项", 422); if (!payload.reason?.trim()) throw new ApiError("FORCE_PASS_REASON_REQUIRED", "强制通过必须填写放行理由", 400); } if (payload.action === "pass") { item.workflow_status = "completed"; item.completion_reason = "human_pass"; } if (payload.action === "force_pass") { item.workflow_status = "completed"; item.completion_reason = "forced_pass"; } if (payload.action === "reject") { item.workflow_status = "human_review"; item.review_disposition = "rejected"; } item.updated_at = new Date().toISOString(); await delay(); return clone(item); },
  async getConnections(): Promise<ConnectionStatus> { await delay(); return clone(fixtureConnections); },
  async listExports(projectId: string): Promise<ExportRun[]> { await delay(); return clone(exportsHistory.filter((item) => item.project_id === projectId)); },
  async createExport(projectId: string): Promise<ExportRun> { const created: ExportRun = { id: crypto.randomUUID(), project_id: projectId, generation_run_id: board.run_id, status: "succeeded", sheet_id: `fake-${Date.now()}`, sheet_title: "8月种草·当前批次", row_count: board.items.filter((item) => item.workflow_status === "completed").length, adapter: "fake", created_at: new Date().toISOString() }; exportsHistory = [created, ...exportsHistory]; await delay(450); return clone(created); },
  async retryExport(exportId: string): Promise<ExportRun> { const run = exportsHistory.find((item) => item.id === exportId)!; run.status = "succeeded"; run.safe_error = undefined; await delay(350); return clone(run); },
  async getExportRun(exportId: string): Promise<ExportRun> { await delay(80); return clone(exportsHistory.find((item) => item.id === exportId)!); },
};
