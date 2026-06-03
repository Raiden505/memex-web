"use client";

import Icon from "@/components/ui/Icon";
import type { ForgetCandidate } from "@/types";

interface ForgetConfirmProps {
  candidates: ForgetCandidate[];
  onConfirm: (ids: string[]) => void;
  onCancel: () => void;
}

export default function ForgetConfirm({ candidates, onConfirm, onCancel }: ForgetConfirmProps) {
  const n = candidates.length;

  return (
    <div className="rounded-2xl border border-outline-variant/50 bg-surface-container-lowest p-4 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
      <p className="font-body-md text-body-md text-on-surface-variant mb-3">
        {n === 1 ? "1 memory will be deleted:" : `${n} memories will be deleted:`}
      </p>
      <ul className="mb-4 space-y-2">
        {candidates.map((c) => (
          <li key={c.id} className="flex gap-3">
            <span className="shrink-0 font-metadata text-metadata text-outline pt-0.5">
              {c.created_at.slice(0, 10)}
            </span>
            <span className="font-body-md text-body-md text-on-surface line-clamp-2">{c.content}</span>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <button
          onClick={() => onConfirm(candidates.map((c) => c.id))}
          className="flex items-center gap-1.5 rounded-xl bg-error px-4 py-2 font-label-md text-label-md text-on-error hover:opacity-90 transition-opacity"
        >
          <Icon name="delete" size={15} />
          Delete
        </button>
        <button
          onClick={onCancel}
          className="rounded-xl border border-outline-variant px-4 py-2 font-label-md text-label-md text-on-surface-variant hover:bg-surface-container transition-colors"
        >
          Keep
        </button>
      </div>
    </div>
  );
}
