import { useEffect, useRef, useState } from 'react'
import { api, post } from './api.js'

// Icons are inline SVG, so we do not add an icon library for six of them.
const icon = (path) => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{path}</svg>
)
const BotIcon = icon(<>
  <rect x="4" y="8" width="16" height="12" rx="3" /><path d="M12 8V4" /><circle cx="12" cy="3" r="1" />
  <path d="M9 13h.01M15 13h.01M9.5 17h5" />
</>)
const BookIcon = icon(<>
  <path d="M4 5a2 2 0 0 1 2-2h13v18H6a2 2 0 0 1-2-2z" /><path d="M9 3v18" />
</>)
const PulseIcon = icon(<path d="M3 12h4l3 8 4-16 3 8h4" />)
const TagIcon = icon(<>
  <path d="M3 7a2 2 0 0 1 2-2h6l8 8-8 8-8-8z" /><circle cx="8" cy="10" r="1.4" />
</>)
const SendIcon = icon(<path d="M4 12l16-8-6 16-3-6z" />)

const AGENTS = {
  manuals: { label: 'Manuals agent', icon: BookIcon },
  diagnostics: { label: 'Diagnostics agent', icon: PulseIcon },
  commercial: { label: 'Commercial agent', icon: TagIcon },
  general: { label: 'Assistant', icon: BotIcon },
}

// One suggestion per agent, with the data domain it needs. We only show the ones
// this account may read, using the same mapping as DOMAIN_PERMISSIONS in access.py.
const SUGGESTIONS = [
  { domain: 'identity', text: 'Which safety procedures must I follow before maintenance?' },
  { domain: 'operational', text: 'Why is this machine generating repeated alarms?' },
  { domain: 'commercial', text: 'Which quotations were issued to my company?' },
]
const VISIBLE_DOMAINS = {
  full: ['identity', 'operational', 'commercial'],
  technician: ['identity', 'operational'],
  commercial: ['identity', 'commercial'],
}

// The model writes **bold** and dashed lists. We render those two here instead
// of adding a markdown library.
function formatted(text) {
  return (text || '').split('\n').map((line, i) => {
    const bullet = /^\s*[-*]\s+/.test(line)
    const parts = line.replace(/^\s*[-*]\s+/, '').split(/\*\*(.+?)\*\*/g)
    return (
      <p key={i} className={bullet ? 'bullet' : undefined}>
        {parts.map((part, j) => (j % 2 ? <strong key={j}>{part}</strong> : part))}
      </p>
    )
  })
}

// The greeting lists only the topics this account may read, like the suggestions.
function greeting(machine, visibility) {
  const domains = VISIBLE_DOMAINS[visibility] || ['identity']
  const topics = ['its manual and configuration']
  if (domains.includes('operational')) topics.push('its telemetry, alarms and maintenance')
  if (domains.includes('commercial')) topics.push('its quotations and orders')
  const list = topics.length > 1
    ? topics.slice(0, -1).join(', ') + ' or ' + topics[topics.length - 1]
    : topics[0]
  return `Hello, I am the AROL assistant for machine ${machine.machineId}. Ask me about ${list}.`
}

export default function Chat({ machine, onOpenPage, visibility }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const list = useRef(null)

  // Load the last turns of this machine, so a reload does not empty the panel.
  useEffect(() => {
    api('/chat/history?machine=' + machine.serialNumber)
      .then((rows) => setMessages(rows.map((r) => ({
        role: r.role, agent: r.agent, content: r.content, sources: r.sources,
      }))))
      .catch(() => {})
  }, [machine.serialNumber])

  // Scroll the message list, not the page.
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight
  }, [messages, busy])

  async function ask(question) {
    if (!question || busy) return
    setMessages((m) => [...m, { role: 'user', content: question }])
    setInput('')
    setBusy(true)
    try {
      const reply = await post('/chat', { message: question, machine: machine.serialNumber })
      setMessages((m) => [...m, { role: 'assistant', ...reply }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: 'Error: ' + e.message }])
    }
    setBusy(false)
  }

  return (
    <div className="chat">
      <div className="chat-header">
        <span className="avatar general">{BotIcon}</span>
        <div>
          <strong>AROL assistant</strong>
          <span className="status">
            <i className="dot-online" /> online &middot; machine {machine.machineId}
          </span>
        </div>
      </div>

      <div className="messages" ref={list}>
        {/* not stored with the conversation: it depends on the account */}
        <div className="row assistant">
          <span className="avatar general">{BotIcon}</span>
          <div className="message assistant"><p>{greeting(machine, visibility)}</p></div>
        </div>

        {messages.map((m, i) => {
          const agent = AGENTS[m.agent] || AGENTS.general
          return (
            <div key={i} className={'row ' + m.role}>
              {m.role === 'assistant' && (
                <span className={'avatar ' + (m.agent || 'general')}>{agent.icon}</span>
              )}
              <div className={'message ' + m.role}>
                {m.agent && m.agent !== 'general' && (
                  <span className={'agent ' + m.agent}>{agent.icon}{agent.label}</span>
                )}
                {formatted(m.answer || m.content)}
                {m.sources && m.sources.length > 0 && (
                  <span className="sources">
                    Manual {m.sources[0].serialNumber}, pages{' '}
                    {/* the tool returns them by relevance, sorted here so they read as a list */}
                    {[...new Set(m.sources.map((s) => s.page))]
                      .sort((a, b) => a - b)
                      .map((page, k) => (
                        <span key={page}>
                          {k > 0 && ', '}
                          <button className="page-link" onClick={() => onOpenPage(page)}>
                            {page}
                          </button>
                        </span>
                      ))}
                  </span>
                )}
              </div>
            </div>
          )
        })}

        {busy && (
          <div className="row assistant">
            <span className="avatar general">{BotIcon}</span>
            <div className="message assistant typing">
              <span className="dot" /><span className="dot" /><span className="dot" />
            </div>
          </div>
        )}

        {messages.length === 0 && !busy && visibility && (
          <div className="suggestions">
            {SUGGESTIONS
              .filter((s) => (VISIBLE_DOMAINS[visibility] || []).includes(s.domain))
              .map((s) => (
                <button key={s.domain} onClick={() => ask(s.text)}>{s.text}</button>
              ))}
          </div>
        )}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ask(input.trim()) }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this machine..."
        />
        <button type="submit" className="send" disabled={busy} aria-label="Send">
          {SendIcon}
        </button>
      </form>
    </div>
  )
}
