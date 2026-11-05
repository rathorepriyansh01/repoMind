import { useMemo, useState } from 'react';
import {
  Github,
  Sparkles,
  GitBranch,
  FileCode2,
  FolderTree,
  MessageSquareText,
  ArrowUpRight,
  LoaderCircle,
  AlertCircle,
  Copy,
  ExternalLink,
  ShieldCheck,
  Network,
  BookOpen,
  Send,
} from 'lucide-react';

const API =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/*
 * Safely convert any backend value into displayable text.
 * This prevents:
 * "Objects are not valid as a React child"
 */
function displayValue(value, fallback = 'Not available') {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }

  if (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => displayValue(item, ''))
      .filter(Boolean)
      .join(', ') || fallback;
  }

  if (typeof value === 'object') {
    // Common backend object structures
    if (value.name) return String(value.name);
    if (value.title) return String(value.title);
    if (value.path) return String(value.path);
    if (value.finding) return String(value.finding);
    if (value.text) return String(value.text);
    if (value.value) return String(value.value);

    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }

  return fallback;
}

/*
 * Extract a readable name from technology/finding objects.
 */
function getItemLabel(item) {
  if (
    typeof item === 'string' ||
    typeof item === 'number'
  ) {
    return String(item);
  }

  if (item && typeof item === 'object') {
    return (
      item.name ||
      item.title ||
      item.finding ||
      item.kind ||
      item.path ||
      displayValue(item)
    );
  }

  return '';
}

/*
 * Extract file path safely.
 */
function getPath(item) {
  if (typeof item === 'string') {
    return item;
  }

  if (item && typeof item === 'object') {
    return item.path || item.name || item.file_path || '';
  }

  return '';
}

export default function App() {
  const [url, setUrl] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [question, setQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [messages, setMessages] = useState([]);

  const report = data?.report || {};

  const folders = useMemo(() => {
    if (!Array.isArray(data?.tree)) return [];

    return data.tree
      .map(getPath)
      .filter(Boolean)
      .filter((path) => path.includes('/'))
      .slice(0, 60);
  }, [data]);

  function getRepositoryId(repositoryData) {
    if (!repositoryData) return null;

    return (
      repositoryData.repository_id ||
      repositoryData.repository?.id ||
      repositoryData.id ||
      null
    );
  }

  async function analyze(event) {
    event?.preventDefault();

    const repoUrl = url.trim();

    setError('');
    setData(null);
    setMessages([]);

    if (!repoUrl) {
      setError('Please enter a GitHub repository URL.');
      return;
    }

    const githubPattern =
      /^https:\/\/(www\.)?github\.com\/[^/]+\/[^/]+\/?$/;

    if (!githubPattern.test(repoUrl)) {
      setError(
        'Paste a valid public GitHub repository URL, for example: https://github.com/tiangolo/fastapi'
      );
      return;
    }

    setLoading(true);

    try {
      console.log('Sending analysis request:', repoUrl);

      const response = await fetch(`${API}/api/v1/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          url: repoUrl,
          force: false,
        }),
      });

      const json = await response.json();

      console.log('Analyze response:', json);

      if (!response.ok) {
        throw new Error(
          typeof json.detail === 'string'
            ? json.detail
            : 'Could not analyze this repository.'
        );
      }

      // Backend returned repository data directly
      if (
        json.repository_id ||
        (json.id && json.report) ||
        json.repository?.id
      ) {
        setData(json);
        return;
      }

      // Backend returned an async job
      const jobId = json.job_id || json.id;

      if (!jobId) {
        throw new Error(
          'The backend returned a response without repository data or a job ID.'
        );
      }

      const maxAttempts = 60;

      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        await new Promise((resolve) =>
          setTimeout(resolve, 1500)
        );

        const jobResponse = await fetch(
          `${API}/api/v1/jobs/${jobId}`,
          {
            headers: {
              Accept: 'application/json',
            },
          }
        );

        if (!jobResponse.ok) {
          throw new Error(
            'Could not check repository analysis status.'
          );
        }

        const job = await jobResponse.json();

        console.log('Job status:', job);

        if (job.status === 'failed') {
          throw new Error(
            job.error || 'Repository analysis failed.'
          );
        }

        if (
          job.status === 'succeeded' &&
          job.repository_id
        ) {
          const repositoryResponse = await fetch(
            `${API}/api/v1/repositories/${job.repository_id}`,
            {
              headers: {
                Accept: 'application/json',
              },
            }
          );

          if (!repositoryResponse.ok) {
            throw new Error(
              'Repository was analyzed but the result could not be loaded.'
            );
          }

          const repository =
            await repositoryResponse.json();

          console.log(
            'Repository data:',
            repository
          );

          setData(repository);
          return;
        }
      }

      throw new Error(
        'Repository analysis is taking too long. Please try again.'
      );
    } catch (err) {
      console.error('Analyze error:', err);

      setError(
        `${err.message || 'Something went wrong.'} Check that the backend is running at ${API}.`
      );
    } finally {
      setLoading(false);
    }
  }

  async function ask(event) {
    event?.preventDefault();

    if (!question.trim() || !data || chatLoading) {
      return;
    }

    const q = question.trim();
    const repositoryId = getRepositoryId(data);

    if (!repositoryId) {
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content:
            'Repository ID was not found. Please analyze the repository again.',
        },
      ]);
      return;
    }

    setQuestion('');

    setMessages((current) => [
      ...current,
      {
        role: 'user',
        content: q,
      },
    ]);

    setChatLoading(true);

    try {
      const endpoint =
        `${API}/api/v1/repositories/${repositoryId}/chat`;

      console.log('Chat endpoint:', endpoint);

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          question: q,
          chat_id: null,
          stream: false,
        }),
      });

      const json = await response.json();

      console.log('Chat response:', json);

      if (!response.ok) {
        throw new Error(
          typeof json.detail === 'string'
            ? json.detail
            : json.error ||
              'Question failed. Please try again.'
        );
      }

      if (!json.answer) {
        throw new Error(
          'The backend returned an empty answer.'
        );
      }

      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: displayValue(
            json.answer,
            'No answer returned.'
          ),
          citations: Array.isArray(json.citations)
            ? json.citations
            : [],
          uncertainty: json.uncertainty || null,
        },
      ]);
    } catch (err) {
      console.error('Chat error:', err);

      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: `Error: ${
            err.message || 'Unable to get an answer.'
          }`,
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  async function copySummary() {
    const summary =
      report.summary || data?.summary;

    if (!summary) return;

    try {
      await navigator.clipboard.writeText(
        displayValue(summary)
      );
    } catch (err) {
      console.error(
        'Could not copy summary:',
        err
      );
    }
  }

  const repositoryId = getRepositoryId(data);

  const technologies = Array.isArray(
    report.technologies
  )
    ? report.technologies
    : [];

  const limitations = Array.isArray(
    report.limitations
  )
    ? report.limitations
    : [];

  const treePaths = Array.isArray(data?.tree)
    ? data.tree
        .map(getPath)
        .filter(Boolean)
    : folders;

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="topbar">
        <a className="brand" href="#">
          <span className="brand-mark">
            <Sparkles size={19} />
          </span>

          <span>
            repo
            <span className="brand-accent">
              mind
            </span>
            <small>
              AI CODEBASE INTELLIGENCE
            </small>
          </span>
        </a>

        <div className="topbar-right">
          <span className="status-dot" />
          <span>
            Public repository mode
          </span>

          <a
            href="https://github.com/"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
            <ArrowUpRight size={14} />
          </a>
        </div>
      </header>

      <main className="main">
        {!data && !loading && (
          <section className="hero">
            <div className="eyebrow">
              <span className="eyebrow-icon">
                <Sparkles size={14} />
              </span>
              YOUR AI REPOSITORY ANALYST
            </div>

            <h1>
              Understand any
              <br />
              <span>codebase, faster.</span>
            </h1>

            <p className="hero-copy">
              Turn a GitHub repository into a clear
              project map. Explore its structure,
              understand key files, and ask questions
              grounded in the code.
            </p>

            <form
              className="repo-form"
              onSubmit={analyze}
            >
              <Github
                size={21}
                className="input-icon"
              />

              <input
                value={url}
                onChange={(event) =>
                  setUrl(event.target.value)
                }
                placeholder="https://github.com/owner/repository"
                aria-label="GitHub repository URL"
              />

              <button
                type="submit"
                disabled={loading}
              >
                <span>
                  Analyze repo
                  <ArrowUpRight size={17} />
                </span>
              </button>
            </form>

            {error && (
              <div className="error-banner">
                <AlertCircle size={17} />
                {error}
              </div>
            )}

            <div className="hero-foot">
              <span>
                <ShieldCheck size={15} />
                Public repos only in MVP
              </span>

              <span>
                <GitBranch size={15} />
                No code execution
              </span>

              <span>
                <Sparkles size={15} />
                AI-powered analysis
              </span>
            </div>

            <div className="sample-row">
              <span>TRY A SAMPLE</span>

              {[
                'https://github.com/tiangolo/fastapi',
                'https://github.com/pallets/flask',
              ].map((sample) => (
                <button
                  type="button"
                  key={sample}
                  onClick={() => setUrl(sample)}
                >
                  {sample
                    .split('/')
                    .slice(-2)
                    .join('/')}
                </button>
              ))}
            </div>

            <div className="feature-grid">
              <Feature
                icon={<FolderTree />}
                title="Repository map"
                desc="See folders, key files, and project structure."
              />

              <Feature
                icon={<BookOpen />}
                title="Readable summary"
                desc="Get an overview grounded in repository files."
              />

              <Feature
                icon={<MessageSquareText />}
                title="Ask the code"
                desc="Ask questions and inspect source references."
              />
            </div>
          </section>
        )}

        {loading && (
          <div className="loading-card">
            <LoaderCircle
              className="spin"
              size={28}
            />

            <div>
              <b>Mapping the codebase…</b>
              <p>
                Fetching repository metadata and
                indexing source files.
              </p>
            </div>
          </div>
        )}

        {data && (
          <section className="dashboard">
            <div className="dashboard-header">
              <div>
                <div className="eyebrow">
                  <Sparkles size={14} />
                  ANALYSIS COMPLETE
                </div>

                <h1>
                  {displayValue(
                    data.name ||
                      data.repository?.name ||
                      'Repository analysis'
                  )}
                </h1>

                <p className="muted">
                  Repository ID:{' '}
                  {displayValue(
                    repositoryId,
                    'Not available'
                  )}
                </p>
              </div>

              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setData(null);
                  setMessages([]);
                  setQuestion('');
                  setError('');
                }}
              >
                Analyze another
              </button>
            </div>

            <div className="dashboard-grid">
              <div className="left-column">

                {/* SUMMARY */}
                <section className="panel summary-panel">
                  <div className="panel-heading">
                    <div className="panel-icon purple">
                      <BookOpen size={18} />
                    </div>

                    <div>
                      <h2>
                        Repository summary
                      </h2>
                      <p>
                        AI-generated project overview
                      </p>
                    </div>

                    <button
                      type="button"
                      className="icon-button"
                      onClick={copySummary}
                      title="Copy summary"
                    >
                      <Copy size={16} />
                    </button>
                  </div>

                  <div className="summary-text">
                    {displayValue(
                      report.summary ||
                        data.summary,
                      'No summary is available for this repository.'
                    )}
                  </div>
                </section>

                {/* PROJECT INFO */}
                <section className="panel">
                  <div className="panel-heading">
                    <div className="panel-icon blue">
                      <Network size={18} />
                    </div>

                    <div>
                      <h2>
                        Project information
                      </h2>
                      <p>
                        Detected technologies and
                        structure
                      </p>
                    </div>
                  </div>

                  <div className="info-grid">
                    <InfoItem
                      label="Technologies"
                      value={
                        technologies.length > 0
                          ? technologies
                              .map(getItemLabel)
                              .filter(Boolean)
                              .join(', ')
                          : 'Not detected'
                      }
                    />

                    <InfoItem
                      label="Entry points"
                      value={
                        Array.isArray(
                          report.entry_points
                        )
                          ? report.entry_points
                              .map(getItemLabel)
                              .filter(Boolean)
                              .join(', ')
                          : 'Not detected'
                      }
                    />

                    <InfoItem
                      label="Purpose"
                      value={displayValue(
                        report.purpose,
                        'Could not determine from available evidence.'
                      )}
                    />

                    <InfoItem
                      label="Files indexed"
                      value={displayValue(
                        data.stats?.files_indexed ??
                          data.stats?.files ??
                          data.files_count,
                        '—'
                      )}
                    />
                  </div>
                </section>

                {/* TECHNOLOGIES */}
                {technologies.length > 0 && (
                  <section className="panel">
                    <div className="panel-heading">
                      <div className="panel-icon amber">
                        <Sparkles size={18} />
                      </div>

                      <div>
                        <h2>
                          Technology stack
                        </h2>
                        <p>
                          Detected from repository
                          evidence
                        </p>
                      </div>
                    </div>

                    <div className="tag-list">
                      {technologies.map(
                        (technology, index) => {
                          const label =
                            getItemLabel(technology);

                          return (
                            <span
                              className="tag"
                              key={`${label}-${index}`}
                              title={
                                typeof technology ===
                                'object'
                                  ? displayValue(
                                      technology
                                    )
                                  : ''
                              }
                            >
                              {label ||
                                `Technology ${
                                  index + 1
                                }`}
                            </span>
                          );
                        }
                      )}
                    </div>
                  </section>
                )}

                {/* LIMITATIONS */}
                {limitations.length > 0 && (
                  <section className="panel">
                    <div className="panel-heading">
                      <div className="panel-icon amber">
                        <AlertCircle size={18} />
                      </div>

                      <div>
                        <h2>
                          Analysis limitations
                        </h2>
                        <p>
                          Things the analysis could
                          not confirm
                        </p>
                      </div>
                    </div>

                    <ul className="limitations-list">
                      {limitations.map(
                        (item, index) => (
                          <li key={index}>
                            {displayValue(item)}
                          </li>
                        )
                      )}
                    </ul>
                  </section>
                )}
              </div>

              <aside className="right-column">

                {/* REPOSITORY EXPLORER */}
                <section className="panel file-panel">
                  <div className="panel-heading">
                    <div className="panel-icon amber">
                      <FolderTree size={18} />
                    </div>

                    <div>
                      <h2>
                        Repository explorer
                      </h2>
                      <p>
                        Sample of discovered paths
                      </p>
                    </div>
                  </div>

                  <div className="file-list">
                    {treePaths
                      .slice(0, 90)
                      .map((path, index) => (
                        <div
                          className="file-row"
                          key={`${path}-${index}`}
                        >
                          <FileCode2 size={14} />
                          <span title={path}>
                            {path}
                          </span>
                        </div>
                      ))}

                    {treePaths.length === 0 && (
                      <p className="muted">
                        No repository tree data
                        available.
                      </p>
                    )}
                  </div>

                  {data.stats?.tree_truncated && (
                    <p className="muted small">
                      GitHub returned a truncated
                      tree.
                    </p>
                  )}
                </section>

                {/* CHAT */}
                <section className="panel chat-panel">
                  <div className="panel-heading">
                    <div className="panel-icon purple">
                      <MessageSquareText
                        size={18}
                      />
                    </div>

                    <div>
                      <h2>Chat with repo</h2>
                      <p>
                        Ask questions about the
                        indexed code
                      </p>
                    </div>
                  </div>

                  <div className="chat-messages">
                    {messages.length === 0 && (
                      <div className="chat-empty">
                        <MessageSquareText
                          size={24}
                        />

                        <b>
                          Curious about something?
                        </b>

                        <p>
                          Ask how a feature works,
                          where an endpoint lives,
                          or which file starts the
                          application.
                        </p>

                        <div className="suggested-questions">
                          {[
                            'What does this repository do?',
                            'Where is the app entry point?',
                            'What dependencies does this use?',
                            'Explain the project structure.',
                          ].map(
                            (suggestion) => (
                              <button
                                type="button"
                                key={suggestion}
                                onClick={() =>
                                  setQuestion(
                                    suggestion
                                  )
                                }
                              >
                                {suggestion}
                              </button>
                            )
                          )}
                        </div>
                      </div>
                    )}

                    {messages.map(
                      (message, index) => (
                        <div
                          className={`message ${message.role}`}
                          key={`${message.role}-${index}`}
                        >
                          <div className="message-role">
                            {message.role ===
                            'user'
                              ? 'YOU'
                              : 'REPOMIND'}
                          </div>

                          <div className="message-content">
                            {displayValue(
                              message.content
                            )}
                          </div>

                          {Array.isArray(
                            message.citations
                          ) &&
                            message.citations
                              .length > 0 && (
                              <div className="citations">
                                {message.citations.map(
                                  (
                                    citation,
                                    citationIndex
                                  ) => {
                                    const path =
                                      displayValue(
                                        citation?.path,
                                        'Source'
                                      );

                                    const href =
                                      citation?.url ||
                                      '#';

                                    return (
                                      <a
                                        key={`${path}-${citationIndex}`}
                                        href={href}
                                        target="_blank"
                                        rel="noreferrer"
                                      >
                                        {path}

                                        {citation?.start_line &&
                                        citation?.end_line
                                          ? ` (L${citation.start_line}-L${citation.end_line})`
                                          : ''}

                                        <ExternalLink
                                          size={11}
                                        />
                                      </a>
                                    );
                                  }
                                )}
                              </div>
                            )}

                          {message.uncertainty && (
                            <small className="muted">
                              {displayValue(
                                message.uncertainty
                              )}
                            </small>
                          )}
                        </div>
                      )
                    )}

                    {chatLoading && (
                      <div className="message assistant">
                        <LoaderCircle
                          size={16}
                          className="spin"
                        />
                        Searching repository and
                        generating answer…
                      </div>
                    )}
                  </div>

                  <form
                    className="chat-form"
                    onSubmit={ask}
                  >
                    <input
                      value={question}
                      onChange={(event) =>
                        setQuestion(
                          event.target.value
                        )
                      }
                      placeholder="Ask about this codebase…"
                      aria-label="Question about repository"
                      disabled={chatLoading}
                    />

                    <button
                      type="submit"
                      aria-label="Send question"
                      disabled={
                        chatLoading ||
                        !question.trim()
                      }
                    >
                      <Send size={17} />
                    </button>
                  </form>

                  <p className="chat-disclaimer">
                    Answers are grounded in indexed
                    repository files. Verify important
                    details against source code.
                  </p>
                </section>
              </aside>
            </div>
          </section>
        )}

        <footer className="footer">
          <span>
            <Sparkles size={14} />
            RepoMind AI
            <span className="footer-sep">
              /
            </span>
            Built to make code less mysterious.
          </span>

          <span>
            MVP · Public repositories
          </span>
        </footer>
      </main>
    </div>
  );
}

function Feature({ icon, title, desc }) {
  return (
    <div className="feature-card">
      <div className="feature-icon">
        {icon}
      </div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>
  );
}

function InfoItem({ label, value }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      <strong>
        {displayValue(value)}
      </strong>
    </div>
  );
}