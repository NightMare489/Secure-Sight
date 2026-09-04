import { FormEvent, useEffect, useRef, useState } from 'react';
import { BarChart3, Bot, Send, Trash2, User } from 'lucide-react';
import toast from 'react-hot-toast';
import { alertsApi } from '../api/alerts';
import { copilotApi, type CopilotHistoryMessage, type CopilotResult } from '../api/copilot';

const STORAGE_KEY = 'securesight-copilot-history';
const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#06b6d4', '#ec4899', '#ef4444'];

type ChatMessage = CopilotHistoryMessage & { id: string; result?: CopilotResult };

function renderAnswer(text: string) {
  return text.split('**').map((part, index) => index % 2 ? <strong key={index}>{part}</strong> : <span key={index}>{part}</span>);
}

function Chart({ chart }: { chart: NonNullable<CopilotResult['chart']> }) {
  const max = Math.max(1, ...chart.data.map((row) => row.incidents));
  const total = chart.data.reduce((sum, row) => sum + row.incidents, 0);
  const gradient = chart.data.reduce<{ offset: number; values: string[] }>((acc, row, index) => {
    const end = acc.offset + (total ? row.incidents / total * 100 : 0);
    acc.values.push(`${COLORS[index % COLORS.length]} ${acc.offset}% ${end}%`);
    acc.offset = end;
    return acc;
  }, { offset: 0, values: [] }).values.join(', ');
  return <section className="chat-chart"><h4><BarChart3 size={16} /> {chart.title}</h4>{chart.chart_type === 'pie' ? <div className="chat-pie-layout"><div className="chat-pie" role="img" aria-label={chart.title} style={{ background: `conic-gradient(${gradient})` }} /> <div>{chart.data.map((row, index) => <p key={row.bucket}><span style={{ background: COLORS[index % COLORS.length] }} />{row.bucket}: <strong>{row.incidents}</strong></p>)}</div></div> : <div className="chat-bars">{chart.data.map((row) => <div key={row.bucket}><span title={`${row.incidents} incidents`} style={{ height: `${Math.max(5, row.incidents / max * 130)}px` }} /><small>{row.bucket}</small><b>{row.incidents}</b></div>)}</div>}</section>;
}

function IncidentMedia({ result }: { result: CopilotResult }) {
  if (!result.incidents.length) return null;
  return <section className="chat-media"><h4>Matching incidents</h4>{result.incidents.map((incident) => <article key={incident.id} className="chat-incident"><div className="chat-incident-meta"><strong>{incident.event_type}</strong><span>{incident.camera_name} / {incident.zone_name}</span><small>{new Date(incident.timestamp).toLocaleString()} · {incident.reviewed ? 'Reviewed' : 'Unreviewed'}</small></div>{incident.has_clip ? <video controls preload="metadata" src={alertsApi.clipUrl(incident.id)} /> : <small className="chat-clip-pending">Clip is still being prepared.</small>}</article>)}</section>;
}

export default function CopilotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
  });
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)); }, [messages]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  const ask = async (event: FormEvent) => {
    event.preventDefault();
    const prompt = message.trim();
    if (!prompt || loading) return;
    const history = messages.slice(-12).map(({ role, text }) => ({ role, text }));
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', text: prompt };
    setMessages((current) => [...current, userMessage]);
    setMessage(''); setLoading(true);
    try {
      const result = await copilotApi.ask(prompt, history);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'model', text: result.answer, result }]);
    } catch (error: any) { toast.error(error.response?.data?.error || 'Copilot request failed'); }
    finally { setLoading(false); }
  };

  return <div className="copilot-page fade-in">
    <header className="copilot-header"><div><h1><Bot size={28} /> Analytics Copilot</h1><p>Ask about incidents, charts, cameras, and recorded footage.</p></div><button className="btn btn-ghost" onClick={() => setMessages([])} disabled={!messages.length}><Trash2 size={16} /> New chat</button></header>
    <main className="copilot-thread">{messages.length === 0 && <div className="copilot-welcome"><Bot size={32} /><h2>How can I help with your cameras?</h2><p>Try “show the latest loitering footage” or “draw a chart of incidents by day.”</p></div>}{messages.map((entry) => <article key={entry.id} className={`chat-message ${entry.role}`}><div className="chat-avatar">{entry.role === 'user' ? <User size={18} /> : <Bot size={18} />}</div><div className="chat-bubble"><p>{entry.role === 'model' ? renderAnswer(entry.text) : entry.text}</p>{entry.result?.chart && <Chart chart={entry.result.chart} />}{entry.result && <IncidentMedia result={entry.result} />}</div></article>)}{loading && <article className="chat-message model"><div className="chat-avatar"><Bot size={18} /></div><div className="chat-bubble chat-thinking"><i /><i /><i /></div></article>}<div ref={bottomRef} /></main>
    <form className="copilot-composer" onSubmit={ask}><input className="input" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask Gemini about your surveillance data…" autoFocus /><button className="btn btn-primary btn-icon" aria-label="Send message" disabled={loading || !message.trim()}><Send size={18} /></button></form>
  </div>;
}
