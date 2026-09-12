'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '@/lib/api';
import type { AgentChatResponse, ChatMessage } from '@/types/api';
import { cn } from '@/lib/utils';
import toast from 'react-hot-toast';
import {
  Brain,
  Loader2,
  MessageSquareText,
  Send,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';

interface UiMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: string[];
  timestamp: Date;
}

const QUICK_PROMPTS = [
  'Which of my matches close this week?',
  'What skill appears most often in my matches?',
  'Show me high-paying remote roles',
  'Summarize my top 5 matches',
];

export default function AgentChatPage() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      const userMsg: UiMessage = { role: 'user', content: text.trim(), timestamp: new Date() };
      const updatedMessages = [...messages, userMsg];
      setMessages(updatedMessages);
      setInput('');
      setIsLoading(true);

      // Build history for API (exclude the new message since it goes in `message` field)
      const history: ChatMessage[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        const res = await api.post<AgentChatResponse>('/api/agent/chat', {
          messages: history,
          message: text.trim(),
        });

        const assistantMsg: UiMessage = {
          role: 'assistant',
          content: res.data.reply,
          toolCalls: res.data.tool_calls_made,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch {
        toast.error('Failed to get a response from the agent.');
        // Remove the user message on error so they can retry
        setMessages(messages);
      } finally {
        setIsLoading(false);
        inputRef.current?.focus();
      }
    },
    [messages, isLoading],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 4rem)' }}>
      {/* Header */}
      <div className="flex-shrink-0 mb-4">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <MessageSquareText className="w-7 h-7 text-nexus-accent" />
          AI Career Agent
        </h1>
        <p className="text-nexus-text-muted mt-1">
          Ask questions about your matches, deadlines, and career opportunities
        </p>
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-4 pr-2 pb-4"
      >
        {messages.length === 0 ? (
          /* Welcome state */
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-20 h-20 bg-nexus-accent/15 rounded-2xl flex items-center justify-center mb-6">
              <Brain className="w-10 h-10 text-nexus-accent" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              Welcome to the NEXUS Career Agent
            </h2>
            <p className="text-nexus-text-muted max-w-md mb-6">
              I can query your saved listings, analyze skill trends, alert you about upcoming deadlines,
              and more. Try one of the quick actions below!
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  className="nexus-btn-secondary text-sm"
                >
                  <Zap size={14} className="text-nexus-warning" />
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Chat messages */
          messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                'flex gap-3 animate-slide-up',
                msg.role === 'user' ? 'justify-end' : 'justify-start',
              )}
            >
              {msg.role === 'assistant' && (
                <div className="flex-shrink-0 w-8 h-8 bg-nexus-accent/15 rounded-lg flex items-center justify-center mt-1">
                  <Brain size={16} className="text-nexus-accent" />
                </div>
              )}

              <div
                className={cn(
                  'max-w-[70%] space-y-2',
                  msg.role === 'user' ? 'items-end' : 'items-start',
                )}
              >
                {/* Tool call badges */}
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-1">
                    {msg.toolCalls.map((tool, j) => (
                      <span
                        key={j}
                        className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-500/15 text-amber-400 text-xs rounded-md font-medium"
                      >
                        <Wrench size={11} />
                        {tool}
                      </span>
                    ))}
                  </div>
                )}

                {/* Message bubble */}
                <div
                  className={cn(
                    'px-4 py-3 rounded-xl text-sm leading-relaxed whitespace-pre-wrap',
                    msg.role === 'user'
                      ? 'bg-nexus-accent text-white rounded-br-md'
                      : 'bg-nexus-surface-2 text-nexus-text border border-nexus-border rounded-bl-md',
                  )}
                >
                  {msg.content}
                </div>

                {/* Timestamp */}
                <span className="text-[10px] text-nexus-text-dim px-1">
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>

              {msg.role === 'user' && (
                <div className="flex-shrink-0 w-8 h-8 bg-nexus-surface-2 rounded-lg flex items-center justify-center mt-1 border border-nexus-border">
                  <Sparkles size={14} className="text-nexus-text-muted" />
                </div>
              )}
            </div>
          ))
        )}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex gap-3 animate-fade-in">
            <div className="w-8 h-8 bg-nexus-accent/15 rounded-lg flex items-center justify-center">
              <Brain size={16} className="text-nexus-accent" />
            </div>
            <div className="px-4 py-3 bg-nexus-surface-2 border border-nexus-border rounded-xl rounded-bl-md">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 bg-nexus-accent rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-nexus-accent rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-nexus-accent rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick prompts (when chat has messages) */}
      {messages.length > 0 && (
        <div className="flex-shrink-0 flex flex-wrap gap-1.5 pb-2">
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => sendMessage(prompt)}
              disabled={isLoading}
              className="px-3 py-1 bg-nexus-surface-2 border border-nexus-border text-nexus-text-muted text-xs rounded-full hover:text-nexus-text hover:border-nexus-accent/40 transition-all disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="flex-shrink-0 flex gap-3 pt-2 border-t border-nexus-border">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask me about your career matches…"
          disabled={isLoading}
          rows={1}
          className="nexus-input resize-none min-h-[44px] max-h-[120px]"
          style={{ height: 'auto' }}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = 'auto';
            target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
          }}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={isLoading || !input.trim()}
          className="nexus-btn-primary flex-shrink-0 px-4"
        >
          {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}
