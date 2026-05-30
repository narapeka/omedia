declare const __OMEDIA_API_BASE_URL__: string | undefined

const apiBaseUrl = (__OMEDIA_API_BASE_URL__ ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details?: unknown,
  ) {
    super(message)
  }
}

export async function apiRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  const isEmpty = response.status === 204 || response.status === 205 || !response.body
  const contentType = response.headers.get('content-type') ?? ''
  const payload = isEmpty ? undefined : contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    const error = payload?.error
    throw new ApiError(
      error?.message ?? response.statusText,
      response.status,
      error?.code ?? 'api.error',
      error?.details,
    )
  }

  return payload as T
}
