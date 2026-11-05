import { useMemo, useState } from 'react'
import { Github, Sparkles, Search, GitBranch, Star, FileCode2, FolderTree, MessageSquareText, ArrowUpRight, LoaderCircle, AlertCircle, Copy, ExternalLink, ShieldCheck, Network, BookOpen, Send } from 'lucide-react'

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default function App() {
  const [url, setUrl] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [question, setQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [messages, setMessages] = useState([])

  const folders = useMemo(() => {
    if (!data?.tree) return []
    return data.tree.filter(p => p.includes('/')).slice(0, 60)
  }, [data])

  async function analyze(e) {
    e?.preventDefault()
    setError('')
    setData(null)
    setMessages([])
    if (!/^https:\/\/(www\.)?github\.com\/[^/]+\/[^/]+\/?/.test(url.trim())) {
      setError('Paste a valid public GitHub repository URL, for example https://github.com/tiangolo/fastapi')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/v1/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() })
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Could not analyze this repository.')
      setData(json)
    } catch (err) {
      setError(`${err.message}. Check that the backend is running at ${API}.`)
    } finally {
      setLoading(false)
    }
  }

  async function ask(e) {
    e.preventDefault()
    if (!question.trim() || !data || chatLoading) return
    const q = question.trim()
    setQuestion('')
    setMessages(m => [...m, { role: 'user', content: q }])
    setChatLoading(true)
    try {
      const res = await fetch(`${API}/api/v1/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repository: data, question: q })
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Question failed.')
      setMessages(m => [...m, { role: 'assistant', content: json.answer, citations: json.citations || [], uncertainty: json.uncertainty }])
    } catch (err) {
      setMessages(m => [...m, { role: 'assistant', content: err.message }])
    } finally {
      setChatLoading(false)
    }
  }

  async function copySummary() {
    if (!data?.report?.summary) return
    await navigator.clipboard.writeText(data.report.summary)
  }

  return <div className="app-shell">
    <div className="ambient ambient-one" /><div className="ambient ambient-two" />
    <header className="topbar">
      <a className="brand" href="#"><span className="brand-mark"><Sparkles size={19}/></span><span>repo<span className="brand-accent">mind</span><small>AI CODEBASE INTELLIGENCE</small></span></a>
      <div className="topbar-right"><span className="status-dot"/> <span>Public repository mode</span><a href="https://github.com/" target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={14}/></a></div>
    </header>

    <main className="main">
      {!data && <section className="hero">
        <div className="eyebrow"><span className="eyebrow-icon"><Sparkles size={14}/></span> YOUR AI REPOSITORY ANALYST</div>
        <h1>Understand any<br/><span>codebase, faster.</span></h1>
        <p className="hero-copy">Turn a GitHub repository into a clear project map. Explore its structure, understand key files, and ask questions grounded in the code.</p>
        <form className="repo-form" onSubmit={analyze}>
          <Github size={21} className="input-icon"/>
          <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://github.com/owner/repository" aria-label="GitHub repository URL"/>
          <button type="submit" disabled={loading}>{loading ? <><LoaderCircle className="spin" size={17}/> Analyzing</> : <>Analyze repo <ArrowUpRight size={17}/></>}</button>
        </form>
        {error && <div className="error-banner"><AlertCircle size={17}/>{error}</div>}
        <div className="hero-foot"><span><ShieldCheck size={15}/> Public repos only in MVP</span><span><GitBranch size={15}/> No code execution</span><span><Sparkles size={15}/> AI-ready analysis</span></div>
        <div className="sample-row"><span>TRY A SAMPLE</span>{['https://github.com/tiangolo/fastapi','https://github.com/pallets/flask'].map(x => <button key={x} onClick={() => setUrl(x)}>{x.split('/').slice(-2).join('/')}</button>)}</div>
        <div className="feature-grid">
          <Feature icon={<FolderTree/>} title="Repository map" desc="See the folders, key files, and dependency manifests."/>
          <Feature icon={<BookOpen/>} title="Readable summary" desc="Get an overview built from repository metadata and source files."/>
          <Feature icon={<MessageSquareText/>} title="Ask the code" desc="Ask questions and inspect relevant file references."/>
        </div>
      </section>}

      {loading && <div className="loading-card"><LoaderCircle className="spin" size={28}/><div><b>Mapping the codebase…</b><p>Fetching repository metadata and supported text files.</p></div></div>}

      {data && <section className="workspace">
        <div className="workspace-heading">
          <div><div className="eyebrow"><span className="status-dot"/> ANALYSIS REPORT</div><h1>{data.repository.full_name}</h1><p>{data.repository.description || 'No repository description provided.'}</p></div>
          <div className="heading-actions"><a className="button secondary" href={data.repository.html_url} target="_blank" rel="noreferrer"><ExternalLink size={16}/> View on GitHub</a><button className="button secondary" onClick={() => {setData(null);setMessages([])}}>New analysis</button></div>
        </div>
        <div className="stat-grid">
          <Stat icon={<Star/>} label="Stars" value={Number(data.repository.stars || 0).toLocaleString()}/>
          <Stat icon={<FileCode2/>} label="Files analyzed" value={data.stats.analyzed_files}/>
          <Stat icon={<FolderTree/>} label="Tree items" value={data.stats.tree_items}/>
          <Stat icon={<GitBranch/>} label="Primary language" value={data.repository.language || 'Unknown'}/>
        </div>
        <div className="content-grid">
          <div className="left-column">
            <section className="panel summary-panel">
              <div className="panel-heading"><div className="panel-icon purple"><Sparkles size={18}/></div><div><h2>Project overview</h2><p>Generated from available repository evidence</p></div><button className="icon-button" title="Copy summary" onClick={copySummary}><Copy size={16}/></button></div>
              <p className="summary-text">{data.report.summary}</p>
              <div className="purpose-box"><span>PROJECT PURPOSE</span><p>{data.report.purpose}</p></div>
              {data.report.ai_enabled === false && <div className="notice"><AlertCircle size={16}/> LLM not configured — showing a heuristic overview. Add provider settings in backend/.env for AI-generated analysis.</div>}
            </section>
            <section className="panel">
              <div className="panel-heading"><div className="panel-icon blue"><Network size={18}/></div><div><h2>Architecture clues</h2><p>Detected entry points and project structure</p></div></div>
              <div className="architecture-columns">
                <InfoList title="Likely entry points" items={data.report.architecture?.likely_entry_points || []}/>
                <InfoList title="Dependency files" items={data.report.architecture?.dependency_files || []}/>
                <InfoList title="Top-level directories" items={data.report.architecture?.top_level_directories || []}/>
              </div>
            </section>
            <section className="panel">
              <div className="panel-heading"><div className="panel-icon green"><BookOpen size={18}/></div><div><h2>Setup notes</h2><p>Start here before running the project</p></div></div>
              <ul className="setup-list">{(data.report.setup_notes || []).map((x,i)=><li key={i}>{x}</li>)}</ul>
              {data.report.limitations?.length > 0 && <div className="limitations"><b>Scope & limitations</b>{data.report.limitations.map((x,i)=><p key={i}>{x}</p>)}</div>}
            </section>
          </div>
          <aside className="right-column">
            <section className="panel file-panel">
              <div className="panel-heading"><div className="panel-icon amber"><FolderTree size={18}/></div><div><h2>Repository explorer</h2><p>Sample of discovered paths</p></div></div>
              <div className="file-list">{(data.tree || []).slice(0,90).map((p,i)=><div className="file-row" key={`${p}-${i}`}><FileCode2 size={14}/><span title={p}>{p}</span></div>)}</div>
              {data.stats.tree_truncated && <p className="muted small">GitHub returned a truncated tree.</p>}
            </section>
            <section className="panel chat-panel">
              <div className="panel-heading"><div className="panel-icon purple"><MessageSquareText size={18}/></div><div><h2>Chat with repo</h2><p>Ask about the indexed code</p></div></div>
              <div className="chat-messages">
                {messages.length === 0 && <div className="chat-empty"><MessageSquareText size={24}/><b>Curious about something?</b><p>Ask how a feature works, where an endpoint lives, or which file starts the app.</p><div className="suggested-questions">{['Where is the app entry point?','What dependencies does this use?','Explain the project structure'].map(q=><button key={q} onClick={()=>setQuestion(q)}>{q}</button>)}</div></div>}
                {messages.map((m,i)=><div className={`message ${m.role}`} key={i}><div className="message-role">{m.role === 'user' ? 'YOU' : 'REPOMIND'}</div><div className="message-content">{m.content}</div>{m.citations?.length > 0 && <div className="citations">{m.citations.map(c=><a key={c.path} href={c.url} target="_blank" rel="noreferrer">{c.path} <ExternalLink size={11}/></a>)}</div>}{m.uncertainty && <small className="muted">{m.uncertainty}</small>}</div>)}
                {chatLoading && <div className="message assistant"><LoaderCircle size={16} className="spin"/> Searching relevant files…</div>}
              </div>
              <form className="chat-form" onSubmit={ask}><input value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask about this codebase…" aria-label="Question about repository"/><button aria-label="Send question" disabled={chatLoading}><Send size={17}/></button></form>
              <p className="chat-disclaimer">Answers may be incomplete. Verify important details against source files.</p>
            </section>
          </aside>
        </div>
      </section>}
      <footer className="footer"><span><Sparkles size={14}/> RepoMind AI <span className="footer-sep">/</span> Built to make code less mysterious.</span><span>MVP v0.1 · Public repositories</span></footer>
    </main>
  </div>
}

function Feature({icon,title,desc}) { return <div className="feature-card"><div className="feature-icon">{icon}</div><h3>{title}</h3><p>{desc}</p></div> }
function Stat({icon,label,value}) { return <div className="stat-card"><div className="stat-top">{icon}<span>{label}</span></div><strong>{value}</strong></div> }
function InfoList({title,items}) { return <div className="info-list"><h3>{title}</h3>{items.length ? items.slice(0,12).map((x,i)=><div className="info-item" key={i}><span className="mini-dot"/><code>{x}</code></div>) : <p className="muted small">Nothing confidently detected.</p>}</div> }
