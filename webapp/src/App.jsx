import { useState, Component } from 'react'
import Dashboard from './pages/Dashboard'
import Workout from './pages/Workout'
import Nutrition from './pages/Nutrition'
import Progress from './pages/Progress'
import Program from './pages/Program'

class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(e) { return { error: e } }
  render() {
    if (this.state.error) return (
      <div style={{ padding: 24, color: '#f87171', fontSize: 14 }}>
        <b>Ошибка приложения:</b><br />
        {this.state.error.message}<br />
        <pre style={{ marginTop: 8, fontSize: 11, whiteSpace: 'pre-wrap', opacity: 0.7 }}>
          {this.state.error.stack}
        </pre>
      </div>
    )
    return this.props.children
  }
}

const TABS = [
  {
    id: 'dashboard',
    label: 'Главная',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    id: 'workout',
    label: 'Тренировка',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M6 4v16M18 4v16M6 12h12M2 8h4M18 8h4M2 16h4M18 16h4" />
      </svg>
    ),
  },
  {
    id: 'nutrition',
    label: 'Питание',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7z" />
        <circle cx="12" cy="9" r="2" />
      </svg>
    ),
  },
  {
    id: 'progress',
    label: 'Прогресс',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    id: 'program',
    label: 'Программа',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')

  return (
    <ErrorBoundary>
      {tab === 'dashboard' && <Dashboard onGoWorkout={() => setTab('workout')} onGoProfile={() => setTab('profile')} />}
      {tab === 'workout' && <Workout onGoProgress={() => setTab('progress')} />}
      {tab === 'nutrition' && <Nutrition />}
      {tab === 'progress' && <Progress />}
      {tab === 'program' && <Program onGoWorkout={() => setTab('workout')} />}

      <nav className="navbar">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`nav-tab${tab === t.id ? ' active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </nav>
    </ErrorBoundary>
  )
}
