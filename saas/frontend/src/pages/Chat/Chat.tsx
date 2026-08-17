import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Paperclip } from "lucide-react";
import { api } from "../../api/client";
import type { ChatMessage, ChatSession, ChatSuggestion } from "../../api/types";
import { cn } from "../../lib/cn";

const CATEGORY_LABELS: Record<string, string> = {
  web: "Web",
  code: "Code",
  cloud: "Cloud",
  recon: "Recon",
  network: "Network",
  threat_intel: "Threat Intel",
  compliance: "Compliance",
};

export default function Chat() {
  const [category, setCategory] = useState("web");
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const queryClient = useQueryClient();

  const { data: suggestionsData } = useQuery({
    queryKey: ["chat-suggestions"],
    queryFn: () => api.get<{ categories: string[]; suggestions: Record<string, ChatSuggestion[]> }>("/api/chat/suggestions"),
  });

  const createSession = useMutation({
    mutationFn: (cat: string) => api.post<ChatSession>("/api/chat/sessions", { category: cat }),
  });

  const sendMessage = useMutation({
    mutationFn: async (content: string) => {
      let currentSession = session;
      if (!currentSession) {
        currentSession = await createSession.mutateAsync(category);
        setSession(currentSession);
        queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      }
      return api.post<ChatMessage[]>(`/api/chat/sessions/${currentSession.id}/messages`, { content });
    },
    onSuccess: (newMessages) => {
      setMessages((prev) => [...prev, ...newMessages]);
      setInput("");
    },
  });

  function submit(content: string) {
    if (!content.trim() || sendMessage.isPending) return;
    sendMessage.mutate(content);
  }

  const suggestions = suggestionsData?.suggestions[category] ?? [];

  if (session || messages.length > 0) {
    return (
      <div className="mx-auto flex h-full max-w-3xl flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto pb-4">
          {messages.map((m) => (
            <div
              key={m.id}
              className={cn(
                "max-w-[85%] rounded-xl px-4 py-2.5 text-sm",
                m.role === "user" ? "ml-auto bg-white text-black" : "bg-[rgba(255,255,255,0.05)] text-white"
              )}
            >
              {m.content}
            </div>
          ))}
          {sendMessage.isPending && <div className="text-xs text-[#666]">Strix is thinking…</div>}
        </div>
        <ChatInput value={input} onChange={setInput} onSubmit={submit} busy={sendMessage.isPending} />
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center">
      <h1 className="mb-6 text-2xl font-semibold text-white">What do you want to secure today?</h1>
      <div className="w-full">
        <ChatInput value={input} onChange={setInput} onSubmit={submit} busy={sendMessage.isPending} />
      </div>

      <div className="mt-6 flex flex-wrap justify-center gap-1.5">
        {Object.keys(CATEGORY_LABELS).map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-sm transition-colors",
              category === cat ? "border-white bg-white text-black" : "border-[#2a2a2a] text-[#aaa] hover:text-white"
            )}
          >
            {CATEGORY_LABELS[cat]}
          </button>
        ))}
      </div>

      <div className="mt-6 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {suggestions.map((s) => (
          <button
            key={s.title}
            onClick={() => submit(s.prompt)}
            className="rounded-xl border border-[#222] bg-[rgba(255,255,255,0.02)] p-4 text-left hover:border-[#333]"
          >
            <div className="mb-1 text-sm font-medium text-white">{s.title}</div>
            <div className="text-xs text-[#888]">{s.prompt}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function ChatInput({
  value,
  onChange,
  onSubmit,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: (v: string) => void;
  busy: boolean;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(value);
      }}
      className="rounded-xl border border-[#2a2a2a] bg-[rgba(255,255,255,0.02)] p-3"
    >
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit(value);
          }
        }}
        rows={2}
        placeholder="Tell Strix what to do…"
        className="w-full resize-none bg-transparent text-sm text-white outline-none placeholder:text-[#555]"
      />
      <div className="mt-2 flex items-center justify-between">
        <button type="button" className="flex items-center gap-1.5 rounded-lg border border-[#2a2a2a] px-2.5 py-1.5 text-xs text-[#888] hover:text-white">
          <Paperclip size={13} /> Add repositories
        </button>
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-black disabled:opacity-40"
        >
          <ArrowUp size={15} />
        </button>
      </div>
    </form>
  );
}
