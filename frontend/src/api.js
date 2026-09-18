// Small fetch helper: adds the session token and returns the JSON.

export function getToken() {
  return localStorage.getItem('token')
}

export function setToken(token) {
  localStorage.setItem('token', token)
}

export function logout() {
  localStorage.removeItem('token')
}

export async function api(path, options = {}) {
  const response = await fetch('/api' + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + getToken(),
      ...options.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Request failed')
  }
  return response.json()
}

export function post(path, body) {
  return api(path, { method: 'POST', body: JSON.stringify(body) })
}
