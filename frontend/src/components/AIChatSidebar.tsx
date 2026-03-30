"use client";

import { useEffect, useRef, useState } from "react";

let nextMsgId = 0;
export type ChatMessage = { id: number; role: "user" | "assistant"; content: string };

type AIChatSidebarProps = {
  isOpen: boolean;
  onClose: () => void;
  onBoardUpdated: () => void;
};

export const AIChatSidebar = ({ isOpen, onClose, onBoardUpdated }: AIChatSidebarProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const send = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMessage: ChatMessage = { id: nextMsgId++, role: "user", content: text };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: messages }),
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const data = (await response.json()) as { assistant_text: string; board_updated: boolean };
      setMessages([...nextMessages, { id: nextMsgId++, role: "assistant", content: data.assistant_text }]);
      if (data.board_updated) {
        onBoardUpdated();
      }
    } catch {
      setError("Could not reach the AI. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div
      className={`fixed inset-y-0 right-0 z-40 flex w-[360px] flex-col border-l border-[var(--stroke)] bg-white shadow-[var(--shadow)] transition-transform duration-300 ${isOpen ? "translate-x-0" : "translate-x-full"}`}
      aria-label="AI chat sidebar"
      data-testid="ai-chat-sidebar"
    >
      <div className="flex items-center justify-between border-b border-[var(--stroke)] px-5 py-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
            AI Assistant
          </p>
          <h2 className="mt-1 font-display text-base font-semibold text-[var(--navy-dark)]">
            Board Chat
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close AI chat sidebar"
          className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
        >
          Close
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4"
        data-testid="ai-chat-messages"
      >
        {messages.length === 0 && !isLoading && (
          <p className="mt-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Ask the AI to create, move, or edit cards
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`rounded-2xl px-4 py-3 text-sm leading-6 ${msg.role === "user"
              ? "ml-6 self-end bg-[var(--navy-dark)] text-white"
              : "mr-6 self-start border border-[var(--stroke)] bg-[var(--surface)] text-[var(--navy-dark)]"
            }`}
            data-testid={`chat-message-${msg.role}`}
          >
            {msg.content}
          </div>
        ))}
        {isLoading && (
          <div
            className="mr-6 self-start rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]"
            data-testid="ai-chat-thinking"
          >
            Thinking...
          </div>
        )}
        {error && (
          <p
            className="text-center text-xs font-semibold uppercase tracking-[0.15em] text-[var(--secondary-purple)]"
            data-testid="ai-chat-error"
          >
            {error}
          </p>
        )}
      </div>

      <div className="border-t border-[var(--stroke)] px-4 py-4">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          rows={3}
          disabled={isLoading}
          aria-label="Chat message input"
          className="w-full resize-none rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--navy-dark)] outline-none placeholder:text-[var(--gray-text)] focus:border-[var(--primary-blue)] disabled:opacity-50"
        />
        <button
          type="button"
          onClick={() => void send()}
          disabled={!input.trim() || isLoading}
          className="mt-2 w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-white transition hover:brightness-110 disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  );
};
