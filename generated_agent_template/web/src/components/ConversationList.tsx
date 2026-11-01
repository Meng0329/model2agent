import type { ReactNode } from "react";
import type { AgentUiInput, Conversation } from "../types";
import { ChatCircle, Plus, Trash, UploadSimple, Table, TextT, ListNumbers, X } from "@phosphor-icons/react";

export default function ConversationList({
  conversations, activeId, onSelect, onCreate, onDelete, onClose,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (c: Conversation) => void;
  onCreate: () => void;
  onDelete: (c: Conversation) => void;
  onClose?: () => void;
}) {
  return (
    <div className="flex h-full flex-col bg-surface-2" style={{ borderRight: "1px solid var(--color-border-soft)" }}>
      <div className="flex items-center justify-between px-3 py-3">
        <span className="text-sm font-semibold text-ink">会话</span>
        <div className="flex items-center gap-1">
          {onClose && (
            <button
              onClick={onClose}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-subink transition hover:bg-surface-2 hover:text-accent"
              title="收起会话"
            >
              <X size={15} />
            </button>
          )}
          <button
            onClick={onCreate}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-white transition hover:opacity-90"
            title="新建会话"
          >
            <Plus size={15} weight="bold" />
          </button>
        </div>
      </div>
      <div className="scroll-thin flex-1 overflow-y-auto px-2 pb-3">
        {conversations.length === 0 && (
          <div className="px-2 py-8 text-center text-xs text-subink">还没有会话</div>
        )}
        {conversations.map((c) => {
          const active = c.id === activeId;
          return (
            <div
              key={c.id}
              onClick={() => onSelect(c)}
              className="group mb-1.5 cursor-pointer rounded-xl border px-3 py-2.5 transition"
              style={{
                borderColor: active ? "var(--color-accent-border)" : "transparent",
                background: active ? "var(--color-accent-soft)" : "transparent",
              }}
            >
              <div className="flex items-center gap-2">
                <ChatCircle size={15} className="shrink-0 text-subink" />
                <span className="min-w-0 flex-1 truncate text-sm text-ink">{c.title || "新会话"}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(c); }}
                  className="opacity-0 transition group-hover:opacity-100"
                  title="删除"
                >
                  <Trash size={14} className="text-subink hover:text-err" />
                </button>
              </div>
              {c.last_preview ? (
                <div className="mt-1 truncate pl-6 text-[11px] text-subink">{c.last_preview}</div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const ICONS: Record<string, ReactNode> = {
  image: <UploadSimple size={16} />,
  tabular: <Table size={16} />,
  text: <TextT size={16} />,
  vector: <ListNumbers size={16} />,
};

export function InputModeIcon({ input }: { input: AgentUiInput }) {
  return ICONS[input.mode] ?? <UploadSimple size={16} />;
}
