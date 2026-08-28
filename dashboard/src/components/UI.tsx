export function StateBadge({ state }: { state: string }) {
  return <span className={`state-badge state-${state.toLowerCase()}`}>{state}</span>;
}

export function SideBadge({ side }: { side: string }) {
  return <span className={`side-${side.toLowerCase()}`}>{side}</span>;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty-state">
      <div style={{ fontSize: 18, fontWeight: 600 }}>{title}</div>
      {hint && <p>{hint}</p>}
    </div>
  );
}

export function ErrorBanner({ children }: { children: React.ReactNode }) {
  return <div className="error-banner">⚠ {children}</div>;
}

export function SuccessBanner({ children }: { children: React.ReactNode }) {
  return <div className="success-banner">✓ {children}</div>;
}
