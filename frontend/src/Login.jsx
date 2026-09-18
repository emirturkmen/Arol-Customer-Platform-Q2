import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { post, setToken } from './api.js'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { token } = await post('/login', { email, password })
      setToken(token)
      // A QR code may have sent the user here from a machine page.
      const next = sessionStorage.getItem('next') || '/machines'
      sessionStorage.removeItem('next')
      navigate(next)
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }

  return (
    <div className="login-page">
      <div className="card login-card">
        <div className="brand">
          <span className="logo">A</span>
          <div>
            <h1>AROL Customer Platform</h1>
            <p className="subtitle">Fleet management and AI assistance</p>
          </div>
        </div>

        <form onSubmit={submit}>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name.surname@company.example"
              autoComplete="username"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              autoComplete="current-password"
              required
            />
          </label>
          <button type="submit" disabled={busy}>{busy ? 'Signing in...' : 'Sign in'}</button>
        </form>

        {error && <p className="error">{error}</p>}
        <p className="hint">
          Demo accounts use the dataset email addresses, for example{' '}
          <code>elena.fabbri@valgrande.example</code>, with the password <code>arol2026</code>.
        </p>
      </div>
    </div>
  )
}
