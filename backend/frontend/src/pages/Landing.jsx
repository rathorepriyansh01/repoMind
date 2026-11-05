import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Github, Sparkles, ShieldCheck, GitBranch, ArrowUpRight, LoaderCircle, AlertCircle, FolderTree, BookOpen, MessageSquareText } from 'lucide-react'
import { analyzeRepository } from '../api'

const SAMPLE_URLS = [
  'https://github.com/tiangolo/fastapi',
  'https://github.com/pallets/flask',
]

export function isGithubRepoUrl(value) {
  return /^https:\/\/(www\.)?github\.com\/[^/\s]+\/[^/\s]+/i.test(value.trim())
}

export default function Landing() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')

  async function onSubmit(event) {
    event?.preventDefault()
    setError('')
    if (!isGithubRepoUrl(url)) {
      setError('Paste a valid public GitHub repository URL, for example https://github.com/tiangolo/fastapi')
      return
    }
    setLoading(true)
    try {
      const id = await analyzeRepository(url.trim(), false, (job) => setProgress(job.progress || 'Analyzing'))
      navigate(`/repo/${id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setProgress('')
    }
  }

  return (
    <section className="hero">
      <div className="eyebrow"><span className="eyebrow-icon"><Sparkles size={14} /></span> YOUR AI REPOSITORY ANALYST</div>
      <h1>Understand any<br /><span>codebase, faster.</span></h1>
      <p className="hero-copy">
        Paste a public GitHub URL. RepoMind fetches real metadata and source files, builds a grounded report,
        and lets you ask questions with citations — without executing repository code.
      </p>
      <form className="repo-form" onSubmit={onSubmit}>
        <Github size={21} className="input-icon" />
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/owner/repository" aria-label="GitHub repository URL" />
        <button type="submit" disabled={loading}>
          {loading ? <><LoaderCircle className="spin" size={17} /> {progress || 'Analyzing'}</> : <>Analyze repository <ArrowUpRight size={17} /></>}
        </button>
      </form>
      {error && <div className="error-banner" role="alert"><AlertCircle size={17} />{error}</div>}
      <div className="hero-foot">
        <span><ShieldCheck size={15} /> Public repositories only</span>
        <span><GitBranch size={15} /> No code execution</span>
        <span><Sparkles size={15} /> LLM optional for chat synthesis</span>
      </div>
      <div className="sample-row">
        <span>TRY A SAMPLE</span>
        {SAMPLE_URLS.map((item) => (
          <button type="button" key={item} onClick={() => setUrl(item)}>{item.split('/').slice(-2).join('/')}</button>
        ))}
      </div>
      <div className="privacy-note">
        Public GitHub data is requested from the official GitHub API. Selected file excerpts may be sent to your configured LLM provider. API keys stay on the server. Private repositories are not supported.
      </div>
      <div className="feature-grid">
        <Feature icon={<FolderTree />} title="Evidence-based map" desc="Metadata, tree, dependencies, and architecture clues from actual files." />
        <Feature icon={<BookOpen />} title="Setup without guesswork" desc="Install steps are generated only from detected manifests and configs." />
        <Feature icon={<MessageSquareText />} title="Grounded chat" desc="Questions retrieve indexed chunks and cite file paths and line ranges." />
      </div>
    </section>
  )
}

function Feature({ icon, title, desc }) {
  return <div className="feature-card"><div className="feature-icon">{icon}</div><h3>{title}</h3><p>{desc}</p></div>
}
