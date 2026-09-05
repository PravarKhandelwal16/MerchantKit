import type { ToolCallSummary } from '../api/types';

type StepStatus = 'completed' | 'failed' | 'rejected';

function resolveStatus(step: ToolCallSummary): StepStatus {
  if (!step.success) {
    const errStr = typeof step.error === 'string'
      ? step.error
      : JSON.stringify(step.error ?? '');
    if (errStr.toUpperCase().includes('GUARDRAIL')) return 'rejected';
    return 'failed';
  }
  return 'completed';
}

/** Extract a safe human-readable error message from a ToolCallSummary. */
function safeErrorMessage(step: ToolCallSummary): string | null {
  if (step.success) return null;
  if (!step.error) return null;

  if (typeof step.error === 'string') {
    // Strip any internal code prefix like "[GUARDRAIL_VIOLATION] ..."
    const clean = step.error.replace(/^\[[A-Z_]+\]\s*/, '');
    return clean || null;
  }

  if (typeof step.error === 'object' && step.error !== null) {
    const e = step.error as Record<string, unknown>;
    const msg = e.message ?? e.reason ?? null;
    return msg ? String(msg) : null;
  }

  return null;
}

const statusConfig: Record<
  StepStatus,
  { numberCls: string; nameCls: string; labelCls: string; label: string }
> = {
  completed: {
    numberCls: 'border-emerald-200 bg-emerald-50 text-emerald-600',
    nameCls: 'text-slate-800',
    labelCls: 'text-emerald-600',
    label: 'Completed',
  },
  failed: {
    numberCls: 'border-red-200 bg-red-50 text-red-500',
    nameCls: 'text-slate-800',
    labelCls: 'text-red-600',
    label: 'Failed',
  },
  rejected: {
    numberCls: 'border-amber-200 bg-amber-50 text-amber-600',
    nameCls: 'text-slate-800',
    labelCls: 'text-amber-600',
    label: 'Rejected by guardrail',
  },
};

interface ExecutionTimelineProps {
  steps: ToolCallSummary[];
  isRunning?: boolean;
}

export function ExecutionTimeline({ steps, isRunning = false }: ExecutionTimelineProps) {
  if (steps.length === 0 && !isRunning) {
    return (
      <p className="text-sm text-slate-400">Execution steps will appear here.</p>
    );
  }

  return (
    <ol className="space-y-3">
      {steps.map((step, idx) => {
        const status = resolveStatus(step);
        const cfg = statusConfig[status];
        const errMsg = safeErrorMessage(step);

        return (
          <li key={idx} className="flex items-start gap-3">
            {/* Step number */}
            <span
              className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold ${cfg.numberCls}`}
            >
              {String(idx + 1).padStart(2, '0')}
            </span>

            {/* Content */}
            <div className="min-w-0">
              <p className={`font-mono text-[13px] leading-snug ${cfg.nameCls}`}>
                {step.tool_name}
              </p>
              <p className={`text-[11px] font-medium ${cfg.labelCls}`}>
                {cfg.label}
              </p>
              {/* Show safe error detail for failed/rejected steps */}
              {errMsg && (
                <p className="mt-0.5 text-[11px] text-slate-400 leading-snug break-words">
                  {errMsg}
                </p>
              )}
            </div>
          </li>
        );
      })}

      {/* Spinner entry while backend is processing */}
      {isRunning && (
        <li className="flex items-start gap-3">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-blue-200 bg-blue-50 text-[10px] font-semibold text-blue-500">
            ···
          </span>
          <div>
            <p className="font-mono text-[13px] text-slate-500">Agent processing</p>
            <p className="text-[11px] font-medium text-blue-500">Running</p>
          </div>
        </li>
      )}
    </ol>
  );
}
