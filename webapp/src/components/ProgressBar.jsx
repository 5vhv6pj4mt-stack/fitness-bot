export default function ProgressBar({ label, current, goal, color }) {
  const pct = goal ? Math.min((current / goal) * 100, 100) : 0
  return (
    <div className="prog-bar">
      <div className="prog-bar-header">
        <span className="prog-bar-label">{label}</span>
        <span className="prog-bar-value">{Math.round(current)} / {goal}</span>
      </div>
      <div className="prog-track">
        <div className="prog-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}
