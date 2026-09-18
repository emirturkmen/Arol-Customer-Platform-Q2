import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, getToken, logout } from './api.js'

export default function Fleet() {
  const [machines, setMachines] = useState(null)
  const [user, setUser] = useState(null)
  const [help, setHelp] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (!getToken()) return navigate('/')
    api('/me').then(setUser)
    api('/machines').then(setMachines).catch(() => navigate('/'))
  }, [navigate])

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="logo">A</span>
          <div>
            <h1>My fleet</h1>
            {user && <p className="subtitle">{user.companyName}</p>}
          </div>
        </div>
        <div className="topbar-right">
          {user && (
            <span className="user-chip">
              {user.name}
              <span className={'badge ' + user.visibility}>{user.visibility}</span>
            </span>
          )}
          {/* the help text is in a panel, so it does not push the machines down */}
          <div className="help-wrap">
            <button className="ghost" aria-expanded={help} onClick={() => setHelp(!help)}>
              Help
            </button>
            {help && (
              <div className="card help-panel">
                <h2>How to use this platform</h2>
                <ol>
                  <li>
                    <b>Open a machine.</b> Scan the QR code applied to it, or pick it from the
                    list on this page. Both lead to the same page.
                  </li>
                  <li>
                    <b>Read or ask.</b> The machine page carries its as-built configuration, its
                    use-and-maintenance manual, and an assistant that answers questions about
                    that machine.
                  </li>
                  <li>
                    <b>Check the answer.</b> Answers taken from the manual cite their pages;
                    clicking a page number opens the manual there.
                  </li>
                </ol>
                {user && (
                  <p className="muted">
                    You are signed in with <b>{user.visibility}</b> access, so the assistant
                    answers about{' '}
                    {user.visibility === 'technician'
                      ? 'machines, manuals, telemetry, alarms and maintenance, and declines questions about quotations and orders.'
                      : user.visibility === 'commercial'
                        ? 'machines, manuals, quotations and orders, and declines questions about telemetry, alarms and maintenance.'
                        : 'every data domain of your company: machines and manuals, telemetry and alarms, quotations and orders.'}
                  </p>
                )}
              </div>
            )}
          </div>
          <button className="ghost" onClick={() => { logout(); navigate('/') }}>Sign out</button>
        </div>
      </header>

      {machines === null && <p className="muted">Loading your machines...</p>}
      {machines !== null && machines.length === 0 && (
        <p className="muted">Your company does not own any machine.</p>
      )}

      <div className="machine-grid">
        {(machines || []).map((m) => (
          <Link key={m.machineId} className="card machine-card" to={'/machines/' + m.serialNumber}>
            <strong>{m.machineId}</strong>
            <span className="badge model">{m.modelCode}</span>
            <span className="muted">Serial {m.serialNumber}</span>
            <span className="muted">{m.plantLocation}</span>
            <span className="open">Open assistant</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
