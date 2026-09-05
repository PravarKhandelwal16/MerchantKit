interface StatusBadgeProps {
  value: string;
}

const paymentStatusColors: Record<string, string> = {
  PAID: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  FAILED: 'bg-red-50 text-red-700 border-red-200',
  PAYMENT_INITIATED: 'bg-blue-50 text-blue-700 border-blue-200',
  PENDING: 'bg-amber-50 text-amber-700 border-amber-200',
  NOT_CREATED: 'bg-slate-50 text-slate-600 border-slate-200',
};

const policyDecisionColors: Record<string, string> = {
  APPROVED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  ALLOWED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  REJECTED: 'bg-red-50 text-red-700 border-red-200',
  ACTIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export function StatusBadge({ value }: StatusBadgeProps) {
  const cls =
    paymentStatusColors[value] ??
    policyDecisionColors[value] ??
    'bg-slate-50 text-slate-600 border-slate-200';

  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${cls}`}>
      {value}
    </span>
  );
}
