import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api, getToken } from './api.js'
import Chat from './Chat.jsx'

// The page a QR code opens: machine data, the manual and the assistant.
export default function Machine() {
  const { machineRef } = useParams()
  const [machine, setMachine] = useState(null)
  const [tab, setTab] = useState('assistant')
  const [manualPage, setManualPage] = useState(null)
  const [user, setUser] = useState(null)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!getToken()) {
      sessionStorage.setItem('next', '/machines/' + machineRef)
      return navigate('/')
    }
    api('/machines/' + machineRef).then(setMachine).catch((e) => setError(e.message))
    // Needed for the suggestions: they depend on the visibility of the account.
    api('/me').then(setUser).catch(() => setUser(null))
  }, [machineRef, navigate])

  if (error) {
    return (
      <div className="page">
        <div className="card notice">
          <p className="error">{error}</p>
          <Link to="/machines">Back to my fleet</Link>
        </div>
      </div>
    )
  }
  if (!machine) return <div className="page"><p className="muted">Loading...</p></div>

  const manualUrl = `/api/machines/${machine.serialNumber}/manual?token=${getToken()}`

  return (
    <div className="page machine">
      <header className="topbar">
        <div className="brand">
          {/* the logo goes back to the fleet */}
          <Link className="logo" to="/machines" title="Back to my fleet">A</Link>
          <div>
            <h1>{machine.machineId}</h1>
            <p className="subtitle">
              <span className="badge model">{machine.model.modelCode}</span>
              Serial {machine.serialNumber} &middot; {machine.plantLocation}
            </p>
          </div>
        </div>
        <Link className="ghost" to="/machines">My fleet</Link>
      </header>

      <p className="config">{machine.configurationProfile}</p>

      <nav className="tabs">
        {['assistant', 'manual', 'qr'].map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>
            {name === 'qr' ? 'QR code' : name}
          </button>
        ))}
      </nav>

      {/* hidden and not unmounted: unmounting would throw the conversation away */}
      <div hidden={tab !== 'assistant'}>
        {/* clicking a citation switches to the manual tab at that page */}
        <Chat
          machine={machine}
          visibility={user && user.visibility}
          onOpenPage={(page) => { setManualPage(page); setTab('manual') }}
        />
      </div>
      {tab === 'manual' && (
        <div className="card manual">
          <iframe
            key={manualPage}
            src={manualUrl + (manualPage ? `#page=${manualPage}` : '')}
            title="Use and maintenance manual"
          />
          <a href={manualUrl} target="_blank" rel="noreferrer">Open the PDF in a new tab</a>
        </div>
      )}
      {tab === 'qr' && (
        <div className="card qr">
          <p>Print this code and apply it to the machine.</p>
          <img src={`/api/machines/${machine.serialNumber}/qr?token=${getToken()}`} alt="Machine QR code" />
          <p className="muted">{window.location.origin}/machines/{machine.serialNumber}</p>
        </div>
      )}
    </div>
  )
}
