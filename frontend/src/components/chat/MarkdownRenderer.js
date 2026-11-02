import React, { useState } from 'react';
import { Icon } from '../ui/Icons';

function citationReference(tag, references) {
  const key = tag.slice(1, -1).toLowerCase();
  const exact = references.findIndex(ref => [ref?.citation_id, ref?.chunk_id].some(value => value != null && String(value).toLowerCase() === key));
  if (exact >= 0) return exact;
  const number = key.match(/(?:chunk|citation)_?(\d+)$|^(\d+)$/)?.slice(1).find(Boolean);
  if (number) {
    const numbered = references.findIndex(ref => Number(ref?.citation_number) === Number(number));
    if (numbered >= 0) return numbered;
    const index = Number(number) - 1;
    if (index >= 0 && index < references.length) return index;
  }
  return references.length === 1 ? 0 : -1;
}

function Inline({ text, references, onCitation, onCitationHover }) {
  const pattern = /(\[(?:chunk_\d+|citation_\d+|\d+)\]|`[^`]+`|\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*))/g;
  const parts = text.split(pattern).filter(Boolean);
  return <>{parts.map((part, index) => {
    if (/^\[(?:chunk_\d+|citation_\d+|\d+)\]$/.test(part)) {
      const refIndex = citationReference(part, references);
      if (refIndex < 0) return <span key={index}>{part}</span>;
      const ref = references[refIndex];
      return <button key={index} className="citation-pill" type="button" onClick={() => onCitation?.(ref, refIndex)} onMouseEnter={() => onCitationHover?.(ref)} onMouseLeave={() => onCitationHover?.(null)} title={`Inspect ${ref?.file_name || 'source'}${ref?.page_number ? `, page ${ref.page_number}` : ''}`} aria-label={`Inspect citation ${refIndex + 1}`}>
        [{ref?.citation_number || refIndex + 1}]
      </button>;
    }
    if (part.startsWith('`')) return <code key={index} className="inline-code">{part.slice(1, -1)}</code>;
    if (part.startsWith('**')) return <strong key={index}><Inline text={part.slice(2, -2)} references={references} onCitation={onCitation} onCitationHover={onCitationHover} /></strong>;
    if (part.startsWith('*')) return <em key={index}><Inline text={part.slice(1, -1)} references={references} onCitation={onCitation} onCitationHover={onCitationHover} /></em>;
    return <React.Fragment key={index}>{part}</React.Fragment>;
  })}</>;
}

function CodeBlock({ code, language }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(code); setCopied(true); window.setTimeout(() => setCopied(false), 1500); } catch (_) { setCopied(false); }
  }
  return <div className="code-block"><div className="code-header"><span>{language || 'Code'}</span><button onClick={copy} title={copied ? 'Code copied' : 'Copy code'} aria-label={copied ? 'Code copied' : 'Copy code'}><Icon name={copied ? 'Check' : 'Copy'} size={14} />{copied ? 'Copied' : 'Copy'}</button></div><pre><code>{code}</code></pre></div>;
}

function splitTable(line) { return line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim()); }

export default function MarkdownRenderer({ content = '', sourceReferences = [], onCitation, onCitationHover }) {
  const lines = String(content).split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }
    const fence = line.match(/^\s*```\s*([\w-]*)/);
    if (fence) {
      const language = fence[1]; const code = []; i += 1;
      while (i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i++]);
      if (i < lines.length) i += 1;
      blocks.push(<CodeBlock key={`code-${blocks.length}`} language={language} code={code.join('\n')} />); continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const Tag = `h${heading[1].length + 1}`;
      blocks.push(<Tag key={`heading-${blocks.length}`}><Inline text={heading[2]} references={sourceReferences} onCitation={onCitation} onCitationHover={onCitationHover} /></Tag>); i += 1; continue;
    }
    if (i + 1 < lines.length && line.includes('|') && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1])) {
      const headers = splitTable(line); i += 2; const rows = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) { rows.push(splitTable(lines[i])); i += 1; }
      blocks.push(<div className="markdown-table-wrap" key={`table-${blocks.length}`}><table><thead><tr>{headers.map((cell, index) => <th key={index}><Inline text={cell} references={sourceReferences} onCitation={onCitation} onCitationHover={onCitationHover} /></th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{headers.map((_, colIndex) => <td key={colIndex}><Inline text={row[colIndex] || ''} references={sourceReferences} onCitation={onCitation} onCitationHover={onCitationHover} /></td>)}</tr>)}</tbody></table></div>); continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)/);
    if (unordered || ordered) {
      const isOrdered = Boolean(ordered); const items = [];
      while (i < lines.length) {
        const item = lines[i].match(isOrdered ? /^\s*\d+[.)]\s+(.+)/ : /^\s*[-*+]\s+(.+)/);
        if (!item) break;
        items.push(item[1]); i += 1;
      }
      const List = isOrdered ? 'ol' : 'ul';
      blocks.push(<List key={`list-${blocks.length}`}>{items.map((item, index) => <li key={index}><Inline text={item} references={sourceReferences} onCitation={onCitation} onCitationHover={onCitationHover} /></li>)}</List>); continue;
    }
    const paragraph = [line]; i += 1;
    while (i < lines.length && lines[i].trim() && !/^\s*```/.test(lines[i]) && !/^#{1,3}\s/.test(lines[i]) && !/^\s*[-*+]\s+/.test(lines[i]) && !/^\s*\d+[.)]\s+/.test(lines[i]) && !(lines[i].includes('|') && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1]))) paragraph.push(lines[i++]);
    blocks.push(<p key={`paragraph-${blocks.length}`}><Inline text={paragraph.join(' ')} references={sourceReferences} onCitation={onCitation} onCitationHover={onCitationHover} /></p>);
  }
  return <div className="markdown-body">{blocks}</div>;
}
