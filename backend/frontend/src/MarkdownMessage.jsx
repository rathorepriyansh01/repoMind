import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import rehypeHighlight from 'rehype-highlight'
import { Copy } from 'lucide-react'

function CodeBlock({ className, children }) {
  const text = String(children).replace(/\n$/, '')
  return (
    <div className="code-block">
      <button type="button" className="copy-mini" onClick={() => navigator.clipboard.writeText(text)} aria-label="Copy code">
        <Copy size={12} />
      </button>
      <pre><code className={className}>{text}</code></pre>
    </div>
  )
}

export default function MarkdownMessage({ text }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize, rehypeHighlight]}
        components={{
          a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>,
          code({ inline, className, children }) {
            if (inline) return <code className="inline-code">{children}</code>
            return <CodeBlock className={className}>{children}</CodeBlock>
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
