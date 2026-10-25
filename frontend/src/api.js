export const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

function detailMessage(payload, fallback) {
  if (!payload) return fallback
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg || item).join(' ')
  return fallback
}

export async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(detailMessage(payload, `Request failed (${response.status})`))
  return payload
}

export async function getHealth() {
  return api('/api/v1/health')
}

export async function getReady() {
  return api('/api/v1/ready')
}

export async function analyzeRepository(url, force, onProgress) {
  const started = await api('/api/v1/analyze', {
    method: 'POST',
    body: JSON.stringify({ url, force: Boolean(force) }),
  })
  for (;;) {
    const job = await api(`/api/v1/jobs/${started.job_id}`)
    if (onProgress) onProgress(job)
    if (job.status === 'succeeded') return job.repository_id
    if (job.status === 'failed') throw new Error(job.error || 'Analysis failed.')
    await new Promise((resolve) => setTimeout(resolve, 700))
  }
}

export async function listRepositories() {
  const data = await api('/api/v1/repositories')
  return data.items || []
}

export async function getRepository(id) {
  return api(`/api/v1/repositories/${id}`)
}

export async function getFile(id, path) {
  return api(`/api/v1/repositories/${id}/files?path=${encodeURIComponent(path)}`)
}

export async function listChats(id) {
  const data = await api(`/api/v1/repositories/${id}/chats`)
  return data.items || []
}

export async function getChat(id, chatId) {
  return api(`/api/v1/repositories/${id}/chats/${chatId}`)
}

export async function deleteChat(id, chatId) {
  return api(`/api/v1/repositories/${id}/chats/${chatId}`, { method: 'DELETE' })
}

export async function sendChat({ repositoryId, question, chatId, onDelta, signal }) {
  const response = await fetch(`${API}/api/v1/repositories/${repositoryId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, chat_id: chatId, stream: true }),
    signal,
  })
  const contentType = response.headers.get('content-type') || ''
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(detailMessage(payload, 'Question failed.'))
  }
  if (!contentType.includes('text/event-stream') || !response.body) {
    const payload = await response.json()
    if (onDelta && payload.answer) onDelta(payload.answer)
    return payload
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let answer = ''
  let finalPayload = { chat_id: chatId, citations: [], mode: 'llm' }
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() || ''
    for (const frame of frames) {
      const line = frame.split('\n').find((item) => item.startsWith('data:'))
      if (!line) continue
      const data = JSON.parse(line.slice(5).trim() || '{}')
      if (data.delta) {
        answer += data.delta
        if (onDelta) onDelta(answer)
      }
      if (data.done) {
        finalPayload = { ...finalPayload, ...data, answer: answer || data.answer }
      }
    }
  }
  return { ...finalPayload, answer }
}
