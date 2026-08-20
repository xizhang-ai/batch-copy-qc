import type { ApiErrorShape } from "./contracts";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(code: string, message: string, status = 0, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function assertSameOriginPath(path: string) {
  if (!path.startsWith("/") || path.startsWith("//") || /^[a-z][a-z\d+.-]*:/i.test(path)) {
    throw new ApiError("API_URL_REJECTED", "API 请求只能使用同源相对路径");
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  assertSameOriginPath(path);
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: init.body instanceof FormData
        ? init.headers
        : { "Content-Type": "application/json", ...init.headers },
    });
  } catch (error) {
    throw new ApiError("API_NETWORK_ERROR", error instanceof Error ? error.message : "网络连接失败");
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("API_RESPONSE_INVALID", "服务返回了无法识别的数据", response.status);
  }

  if (!response.ok) {
    const parsed = payload as Partial<ApiErrorShape>;
    throw new ApiError(
      parsed.error?.code ?? "API_REQUEST_FAILED",
      parsed.error?.message ?? "请求失败",
      response.status,
      parsed.error?.details ?? {},
    );
  }

  return payload as T;
}
