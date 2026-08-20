import type { CopyItem, ItemResponse } from "../../api/contracts";

export function mergeItemResponse(current: CopyItem, response: ItemResponse): CopyItem {
  const defined = Object.fromEntries(Object.entries(response).filter(([, value]) => value !== undefined)) as Partial<CopyItem>;
  return {
    ...current,
    ...defined,
    id: response.id,
    copy_type_name: response.copy_type_name ?? current.copy_type_name,
    findings: Array.isArray(response.findings) ? response.findings : current.findings,
    tags: Array.isArray(response.tags) ? response.tags : current.tags,
  };
}
