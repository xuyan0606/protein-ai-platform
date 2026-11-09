export interface UploadBatchResult<T> {
  uploaded: T[]
  failed: number
}

export function hasUploadSession(token: string | null): boolean {
  return Boolean(token)
}

export function isAuthFailureStatus(status: number): boolean {
  return status === 401 || status === 403
}

export async function uploadBatch<T>(
  files: File[],
  upload: (file: File) => Promise<T>,
): Promise<UploadBatchResult<T>> {
  const results = await Promise.allSettled(files.map(upload))
  const uploaded: T[] = []
  let failed = 0

  for (const result of results) {
    if (result.status === 'fulfilled') uploaded.push(result.value)
    else failed += 1
  }

  return { uploaded, failed }
}
