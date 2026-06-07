'use client';

import { useState, useRef, useEffect } from 'react';
import { motion } from 'motion/react';
import { 
  Search, Play, Square, AlertCircle, CheckCircle, 
  Globe, Home, Link as LinkIcon, Filter, ExternalLink,
  AlertTriangle, Activity
} from 'lucide-react';

type LinkResult = {
  url: string;
  status: number;
  ok: boolean;
  isInternal: boolean;
  error?: string;
};

export default function Crawler() {
  const [url, setUrl] = useState('');
  const [maxLinks, setMaxLinks] = useState(50);
  const [isCrawling, setIsCrawling] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const [results, setResults] = useState<LinkResult[]>([]);
  const [totalLinks, setTotalLinks] = useState(0);
  const [filter, setFilter] = useState<'all' | 'broken' | 'working'>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'internal' | 'external'>('all');
  
  const eventSourceRef = useRef<EventSource | null>(null);

  const startCrawl = (e: React.FormEvent) => {
    e.preventDefault();
    
    let targetUrl = url;
    if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
      targetUrl = 'https://' + targetUrl;
      setUrl(targetUrl);
    }

    try {
      new URL(targetUrl);
    } catch {
      setMessages(['Invalid URL format.']);
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setIsCrawling(true);
    setMessages([]);
    setResults([]);
    setTotalLinks(0);

    const es = new EventSource(`/api/crawl?url=${encodeURIComponent(targetUrl)}&max=${maxLinks}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'info') {
        setMessages(prev => [...prev, data.message]);
      } else if (data.type === 'start') {
        setTotalLinks(data.total);
      } else if (data.type === 'result') {
        setResults(prev => [...prev, data.data]);
      } else if (data.type === 'done') {
        setMessages(prev => [...prev, data.message]);
        setIsCrawling(false);
        es.close();
      } else if (data.type === 'error') {
        setMessages(prev => [...prev, `Error: ${data.message}`]);
        setIsCrawling(false);
        es.close();
      }
    };

    es.onerror = () => {
      setMessages(prev => [...prev, 'Connection lost or error occurred.']);
      setIsCrawling(false);
      es.close();
    };
  };

  const stopCrawl = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      setIsCrawling(false);
      setMessages(prev => [...prev, 'Crawling stopped by user.']);
    }
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const filteredResults = results.filter(r => {
    if (filter === 'broken' && r.ok) return false;
    if (filter === 'working' && !r.ok) return false;
    if (typeFilter === 'internal' && !r.isInternal) return false;
    if (typeFilter === 'external' && r.isInternal) return false;
    return true;
  });

  const brokenCount = results.filter(r => !r.ok).length;
  const workingCount = results.filter(r => r.ok).length;
  const progress = totalLinks > 0 ? (results.length / totalLinks) * 100 : 0;

  return (
    <div className="w-full max-w-6xl mx-auto p-6 space-y-8">
      {/* Header & Input */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8">
        <div className="flex flex-col md:flex-row gap-6 items-start md:items-center justify-between">
          <div className="space-y-2 flex-1 w-full">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Link Crawler</h1>
            <p className="text-slate-500">Find broken internal and external links on any webpage.</p>
            
            <form onSubmit={startCrawl} className="flex flex-col sm:flex-row gap-3 pt-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
                <input 
                  type="url" 
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                  required
                  disabled={isCrawling}
                />
              </div>
              <div className="relative w-full sm:w-32">
                <input 
                  type="number" 
                  value={maxLinks}
                  onChange={(e) => setMaxLinks(parseInt(e.target.value) || 50)}
                  min="1"
                  max="500"
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                  title="Max links to check"
                  disabled={isCrawling}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-medium">MAX</span>
              </div>
              {isCrawling ? (
                <button 
                  type="button"
                  onClick={stopCrawl}
                  className="flex items-center justify-center gap-2 px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-xl font-medium transition-colors cursor-pointer"
                >
                  <Square className="w-4 h-4 fill-current" />
                  Stop
                </button>
              ) : (
                <button 
                  type="submit"
                  className="flex items-center justify-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium transition-colors cursor-pointer"
                >
                  <Play className="w-4 h-4 fill-current" />
                  Crawl
                </button>
              )}
            </form>
          </div>
        </div>
      </div>

      {/* Dashboard Stats */}
      {(results.length > 0 || isCrawling) && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <LinkIcon className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Checked</span>
            </div>
            <div className="text-3xl font-semibold text-slate-900">
              {results.length} <span className="text-lg text-slate-400 font-normal">/ {totalLinks || '?'}</span>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
            <div className="flex items-center gap-2 text-emerald-600 mb-2">
              <CheckCircle className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Working</span>
            </div>
            <div className="text-3xl font-semibold text-slate-900">{workingCount}</div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
            <div className="flex items-center gap-2 text-red-500 mb-2">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Broken</span>
            </div>
            <div className="text-3xl font-semibold text-slate-900">{brokenCount}</div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
            <div className="flex items-center gap-2 text-indigo-500 mb-2">
              <Activity className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Status</span>
            </div>
            <div className="text-lg font-medium text-slate-900 flex items-center gap-2 mt-2">
              {isCrawling ? (
                <>
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
                  </span>
                  Crawling...
                </>
              ) : (
                <>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-slate-300"></span>
                  Idle
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      {isCrawling && totalLinks > 0 && (
        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
          <motion.div 
            className="bg-indigo-500 h-2 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      )}

      {/* Logs */}
      {messages.length > 0 && (
        <div className="bg-slate-900 rounded-xl p-4 text-xs font-mono text-slate-300 h-32 overflow-y-auto shadow-inner">
          {messages.map((msg, i) => (
            <div key={i} className="py-1 border-b border-slate-800 last:border-0">
              <span className="text-slate-500 mr-2">[{new Date().toLocaleTimeString()}]</span>
              {msg}
            </div>
          ))}
        </div>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row gap-4 justify-between items-center">
            <h2 className="font-semibold text-slate-800 flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-400" />
              Results
            </h2>
            <div className="flex gap-2">
              <select 
                value={filter} 
                onChange={(e) => setFilter(e.target.value as any)}
                className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                <option value="all">All Status</option>
                <option value="broken">Broken Only</option>
                <option value="working">Working Only</option>
              </select>
              <select 
                value={typeFilter} 
                onChange={(e) => setTypeFilter(e.target.value as any)}
                className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                <option value="all">All Types</option>
                <option value="internal">Internal Only</option>
                <option value="external">External Only</option>
              </select>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">URL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredResults.map((result, idx) => (
                  <motion.tr 
                    key={idx}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      {result.ok ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                          <CheckCircle className="w-3.5 h-3.5" />
                          {result.status} OK
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          {result.status || 'ERR'}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {result.isInternal ? (
                        <span className="inline-flex items-center gap-1 text-slate-500">
                          <Home className="w-3.5 h-3.5" /> Internal
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-indigo-500">
                          <Globe className="w-3.5 h-3.5" /> External
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 max-w-md truncate">
                      <div className="flex items-center gap-1.5">
                        <a 
                          href={result.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-slate-700 hover:text-indigo-600 hover:underline truncate"
                          title={result.url}
                        >
                          {result.url}
                        </a>
                        <ExternalLink className="w-3 h-3 text-slate-400 flex-shrink-0" />
                      </div>
                      {result.error && (
                        <div className="text-xs text-red-500 mt-1 truncate" title={result.error}>
                          {result.error}
                        </div>
                      )}
                    </td>
                  </motion.tr>
                ))}
                {filteredResults.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-6 py-8 text-center text-slate-500">
                      No links match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
