interface StatusDotProps {
  online: boolean;
  label: string;
  neutral?: boolean;
}

export function StatusDot({ online, label, neutral = false }: StatusDotProps) {
  const color = neutral
    ? 'bg-slate-400'
    : online
    ? 'bg-emerald-500'
    : 'bg-red-500';

  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-500">
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${color}`} />
      {label}
    </span>
  );
}
