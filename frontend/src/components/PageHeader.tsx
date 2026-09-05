interface PageHeaderProps {
  title: string;
  description: string;
}

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <div className="mb-8 border-b border-slate-200 pb-4">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-0.5 text-sm text-slate-500">{description}</p>
    </div>
  );
}
