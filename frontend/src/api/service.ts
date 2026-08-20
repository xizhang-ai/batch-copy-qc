import { apiRequest } from "./client";
import type { BoardData, ClassifiedTypeFile, ConnectionStatus, CopyItem, CopyType, ExportPreview, ExportRun, GenerationRun, ItemResponse, ParsedBrief, ParsedTypeBrief, Project, QcRule, ReviewPayload, RewriteSelectionPayload } from "./contracts";

const isMock = () => __USE_MOCK_API__;
const mock = async () => (await import("./mockService")).mockApi;

export const api = {
  mode: isMock() ? "mock" as const : "real" as const,
  async listProjects(): Promise<Project[]> { return isMock() ? (await mock()).listProjects() : apiRequest("/api/projects"); },
  async getProject(projectId: string): Promise<Project> { return isMock() ? (await mock()).getProject(projectId) : apiRequest(`/api/projects/${projectId}`); },
  async createProject(input: Pick<Project, "name" | "brand" | "category">): Promise<Project> { return isMock() ? (await mock()).createProject(input) : apiRequest("/api/projects", { method: "POST", body: JSON.stringify(input) }); },
  async parseProjectBrief(projectId: string, input: { text?: string; file?: File }): Promise<ParsedBrief> {
    if (isMock()) return (await mock()).parseProjectBrief(projectId, input);
    const body = new FormData(); if (input.text) body.set("text", input.text); if (input.file) body.set("file", input.file);
    return apiRequest(`/api/projects/${projectId}/briefs:parse`, { method: "POST", body });
  },
  async saveProjectFindings(projectId: string, parsed: ParsedBrief): Promise<Project> { return isMock() ? (await mock()).saveProjectFindings(projectId, parsed) : apiRequest(`/api/projects/${projectId}`, { method: "PATCH", body: JSON.stringify({ findings: parsed.findings, confirmed: true }) }); },
  async listCopyTypes(projectId: string): Promise<CopyType[]> { return isMock() ? (await mock()).listCopyTypes(projectId) : apiRequest(`/api/projects/${projectId}/copy-types`); },
  async createCopyType(projectId: string): Promise<CopyType> { return isMock() ? (await mock()).createCopyType(projectId) : apiRequest(`/api/projects/${projectId}/copy-types`, { method: "POST", body: JSON.stringify({}) }); },
  async saveCopyType(item: CopyType): Promise<CopyType> { if (isMock()) return (await mock()).saveCopyType(item); const payload = { name: item.name, quantity: item.quantity, type_brief: item.type_brief, input_modes: item.input_modes, requirements: item.requirements, must_include: item.must_include, must_avoid: item.must_avoid, reference_profile: item.reference_profile, brief_review: item.brief_review }; return apiRequest(`/api/copy-types/${item.id}`, { method: "PATCH", body: JSON.stringify(payload) }); },
  async parseCopyTypeBrief(copyTypeId: string, input: { text?: string; file?: File }): Promise<ParsedTypeBrief> {
    if (isMock()) return (await mock()).parseCopyTypeBrief();
    const body = new FormData(); if (input.file) body.set("file", input.file); else if (input.text) body.set("text", input.text);
    return apiRequest(`/api/copy-types/${copyTypeId}/briefs:parse`, { method: "POST", body });
  },
  async deleteCopyType(id: string): Promise<void> { if (isMock()) return (await mock()).deleteCopyType(id); await apiRequest(`/api/copy-types/${id}`, { method: "DELETE" }); },
  async analyzeReferences(copyTypeId: string, examples: CopyType["references"]): Promise<NonNullable<CopyType["reference_profile"]>> { return isMock() ? (await mock()).analyzeReferences() : apiRequest(`/api/copy-types/${copyTypeId}/references:analyze`, { method: "POST", body: JSON.stringify({ examples }) }); },
  async listClassifiedFiles(projectId: string): Promise<ClassifiedTypeFile[]> { return isMock() ? (await mock()).listClassifiedFiles(projectId) : apiRequest(`/api/projects/${projectId}/type-files`); },
  async classifyTypeFiles(projectId: string, files: File[]): Promise<ClassifiedTypeFile[]> { if (isMock()) return (await mock()).classifyTypeFiles(files); const body = new FormData(); files.forEach((file) => body.append("files", file)); return apiRequest(`/api/projects/${projectId}/type-files:classify`, { method: "POST", body }); },
  async assignTypeFile(sourceId: string, copyTypeId: string | null): Promise<void> { if (isMock()) return (await mock()).assignTypeFile(sourceId, copyTypeId); await apiRequest(`/api/brief-sources/${sourceId}`, { method: "PATCH", body: JSON.stringify({ copy_type_id: copyTypeId, confirmed: true }) }); },
  async listRules(projectId: string): Promise<QcRule[]> { return isMock() ? (await mock()).listRules(projectId) : apiRequest(`/api/projects/${projectId}/qc-rules`); },
  async saveRule(rule: QcRule): Promise<QcRule> { return isMock() ? (await mock()).saveRule(rule) : apiRequest(`/api/qc-rules/${rule.id}`, { method: "PATCH", body: JSON.stringify(rule) }); },
  async createRule(projectId: string, rule: Omit<QcRule, "id" | "project_id">): Promise<QcRule> { return isMock() ? (await mock()).createRule(projectId, rule) : apiRequest(`/api/projects/${projectId}/qc-rules`, { method: "POST", body: JSON.stringify(rule) }); },
  async deleteRule(ruleId: string): Promise<void> { if (isMock()) return (await mock()).deleteRule(ruleId); await apiRequest(`/api/qc-rules/${ruleId}`, { method: "DELETE" }); },
  async getBoard(projectId: string): Promise<BoardData> { return isMock() ? (await mock()).getBoard(projectId) : apiRequest(`/api/projects/${projectId}/board`); },
  async createGenerationRun(projectId: string): Promise<GenerationRun> { return isMock() ? (await mock()).createGenerationRun(projectId) : apiRequest(`/api/projects/${projectId}/generation-runs`, { method: "POST", body: JSON.stringify({}) }); },
  async retryQc(itemId: string): Promise<CopyItem> { return isMock() ? (await mock()).retryQc(itemId) : apiRequest(`/api/items/${itemId}/qc:retry`, { method: "POST" }); },
  async getItem(itemId: string): Promise<ItemResponse> { return isMock() ? (await mock()).getItem(itemId) : apiRequest(`/api/items/${itemId}`); },
  async saveItem(itemId: string, patch: Pick<CopyItem, "title" | "body" | "tags" | "version">): Promise<ItemResponse> { return isMock() ? (await mock()).saveItem(itemId, patch) : apiRequest(`/api/items/${itemId}`, { method: "PATCH", body: JSON.stringify(patch) }); },
  async rewriteSelection(itemId: string, payload: RewriteSelectionPayload): Promise<ItemResponse> { return isMock() ? (await mock()).rewriteSelection(itemId, payload) : apiRequest(`/api/items/${itemId}/rewrite-selection`, { method: "POST", body: JSON.stringify(payload) }); },
  async reviewItem(itemId: string, payload: ReviewPayload): Promise<ItemResponse> { return isMock() ? (await mock()).reviewItem(itemId, payload) : apiRequest(`/api/items/${itemId}/review`, { method: "POST", body: JSON.stringify(payload) }); },
  async getConnections(): Promise<ConnectionStatus> { return isMock() ? (await mock()).getConnections() : apiRequest("/api/system/connections"); },
  async getExportPreview(projectId: string): Promise<ExportPreview> {
    const data = await this.getBoard(projectId); const completed = data.items.filter((item) => item.workflow_status === "completed");
    return { completed: completed.length, by_reason: { ai_pass: completed.filter((item) => item.completion_reason === "ai_pass").length, human_pass: completed.filter((item) => item.completion_reason === "human_pass").length, forced_pass: completed.filter((item) => item.completion_reason === "forced_pass").length }, excluded_human_review: data.items.filter((item) => item.workflow_status === "human_review" && item.review_disposition !== "rejected").length, excluded_rejected: data.items.filter((item) => item.review_disposition === "rejected").length, columns: ["序号", "ITEM ID", "帖子类型", "标题", "正文", "话题", "完成方式", "遗留问题", "修改说明"] };
  },
  async listExports(projectId: string): Promise<ExportRun[]> { return isMock() ? (await mock()).listExports(projectId) : apiRequest(`/api/projects/${projectId}/exports`); },
  async createExport(projectId: string): Promise<ExportRun> { if (isMock()) return (await mock()).createExport(projectId); const board = await this.getBoard(projectId); return apiRequest(`/api/projects/${projectId}/exports`, { method: "POST", body: JSON.stringify({ generation_run_id: board.run_id }) }); },
  async retryExport(exportId: string): Promise<ExportRun> { return isMock() ? (await mock()).retryExport(exportId) : apiRequest(`/api/export-runs/${exportId}:retry`, { method: "POST" }); },
  async getExportRun(exportId: string): Promise<ExportRun> { return isMock() ? (await mock()).getExportRun(exportId) : apiRequest(`/api/export-runs/${exportId}`); },
};
