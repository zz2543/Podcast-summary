import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { chatEpisode, type ChatMessage } from "@/api/client";

interface ChatPanelProps {
  episodeId: string;
  open: boolean;
  onClose: () => void;
}

export function ChatPanel({ episodeId, open, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (open) setTimeout(() => textareaRef.current?.focus(), 320);
  }, [open]);

  const send = async () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");

    const history = [...messages];
    const userMsg: ChatMessage = { role: "user", content: text };
    const assistantMsg: ChatMessage = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);

    const { stream, abort } = chatEpisode(episodeId, text, history);
    abortRef.current = abort;

    try {
      const reader = stream.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: "assistant",
            content: next[next.length - 1].content + value,
          };
          return next;
        });
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: "assistant",
            content: "抱歉，出现了错误，请稍后重试。",
          };
          return next;
        });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const handleClose = () => {
    abortRef.current?.();
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={handleClose}
        className={`fixed inset-0 z-40 transition-all duration-300 ${
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        style={{ backdropFilter: open ? "blur(1px)" : "none", background: "rgba(0,0,0,0.08)" }}
      />

      {/* Floating glass panel — margins on all sides, clears the bottom dock */}
      <div
        style={{
          position: "fixed",
          top: "56px",   /* flush below h-14 header */
          right: "0",
          bottom: "82px",
          width: "min(400px, 30vw)",
          /* glass */
          background: "rgba(246, 246, 250, 0.82)",
          backdropFilter: "blur(52px) saturate(220%)",
          WebkitBackdropFilter: "blur(52px) saturate(220%)",
          borderTop: "1px solid rgba(255,255,255,0.72)",
          borderLeft: "1px solid rgba(255,255,255,0.72)",
          borderBottom: "1px solid rgba(255,255,255,0.72)",
          borderRight: "none",
          borderRadius: "24px 0 0 24px",
          boxShadow:
            "0 0 0 0.5px rgba(255,255,255,0.9) inset, " +
            "0 2px 0 rgba(255,255,255,0.85) inset, " +
            "-20px 0 60px rgba(0,0,0,0.14), " +
            "-4px 0 16px rgba(0,0,0,0.08)",
          transform: open ? "translateX(0)" : "translateX(calc(100% + 2px))",
          transition: "transform 0.35s cubic-bezier(0.32, 0.72, 0, 1)",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            borderBottom: "1px solid rgba(0,0,0,0.06)",
            boxShadow: "0 1px 0 rgba(255,255,255,0.9)",
          }}
          className="flex shrink-0 items-center justify-between px-5 py-4"
        >
          <span className="font-display text-sm font-semibold tracking-tight text-text">
            与文稿对话
          </span>
          <button
            onClick={handleClose}
            style={{
              background: "rgba(0,0,0,0.06)",
              border: "1px solid rgba(0,0,0,0.06)",
            }}
            className="flex h-7 w-7 items-center justify-center rounded-full text-text-muted transition-all hover:bg-black/10 hover:text-text"
          >
            <X className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>

        {/* Messages — flex-1 so it takes remaining space */}
        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {messages.length === 0 && (
            <p className="mt-16 text-center text-xs text-text-subtle">
              可以问我关于这期播客的任何问题
            </p>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "user" ? (
                <div
                  style={{
                    background: "rgba(29,29,31,0.88)",
                    boxShadow:
                      "0 1px 0 rgba(255,255,255,0.12) inset, 0 2px 8px rgba(0,0,0,0.2)",
                  }}
                  className="max-w-[82%] rounded-[18px] rounded-tr-[6px] px-3.5 py-2.5 text-sm leading-relaxed text-white whitespace-pre-wrap break-words"
                >
                  {msg.content}
                </div>
              ) : (
                <div
                  style={{
                    background: "rgba(255,255,255,0.62)",
                    backdropFilter: "blur(16px) saturate(180%)",
                    WebkitBackdropFilter: "blur(16px) saturate(180%)",
                    border: "1px solid rgba(255,255,255,0.8)",
                    boxShadow:
                      "0 1px 0 rgba(255,255,255,0.95) inset, 0 2px 12px rgba(0,0,0,0.07)",
                  }}
                  className="max-w-[82%] rounded-[18px] rounded-tl-[6px] px-3.5 py-2.5 text-sm leading-relaxed text-text whitespace-pre-wrap break-words"
                >
                  {msg.content}
                  {streaming && i === messages.length - 1 && (
                    <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-text-muted align-middle opacity-70" />
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input row — shrink-0 so it's never cut off */}
        <div
          style={{
            borderTop: "1px solid rgba(0,0,0,0.06)",
            boxShadow: "0 -1px 0 rgba(255,255,255,0.9)",
          }}
          className="shrink-0 p-3"
        >
          <div
            style={{
              background: "rgba(255,255,255,0.6)",
              backdropFilter: "blur(20px) saturate(180%)",
              WebkitBackdropFilter: "blur(20px) saturate(180%)",
              border: "1px solid rgba(255,255,255,0.75)",
              boxShadow:
                "0 1px 0 rgba(255,255,255,0.95) inset, 0 2px 10px rgba(0,0,0,0.06)",
            }}
            className="flex items-end gap-2 rounded-2xl px-3 py-2"
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题… (Enter 发送)"
              disabled={streaming}
              className="flex-1 resize-none bg-transparent text-sm text-text outline-none placeholder:text-text-subtle disabled:opacity-50"
              style={{ maxHeight: "96px", overflowY: "auto" }}
            />
            <button
              onClick={send}
              disabled={!input.trim() || streaming}
              style={{
                background:
                  input.trim() && !streaming
                    ? "rgba(29,29,31,0.9)"
                    : "rgba(0,0,0,0.10)",
                boxShadow:
                  input.trim() && !streaming
                    ? "0 1px 0 rgba(255,255,255,0.15) inset, 0 2px 6px rgba(0,0,0,0.22)"
                    : "none",
                transition: "all 0.18s ease",
              }}
              className="mb-0.5 shrink-0 rounded-xl px-3 py-1.5 text-xs font-semibold text-white disabled:text-text-subtle"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
