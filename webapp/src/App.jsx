import { useState, Component } from 'react'
import Dashboard from './pages/Dashboard'
import Workout from './pages/Workout'
import Nutrition from './pages/Nutrition'
import Progress from './pages/Progress'
import Program from './pages/Program'
import Profile from './pages/Profile'

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
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <polyline points="9,22 9,12 15,12 15,22"/>
      </svg>
    ),
  },
  {
    id: 'workout',
    label: 'Тренировка',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6.5 6.5l11 11"/><path d="M21 3L3 21"/>
        <circle cx="5" cy="19" r="2"/><circle cx="19" cy="5" r="2"/>
      </svg>
    ),
  },
  {
    id: 'nutrition',
    label: 'Питание',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12,6 12,12 16,14"/>
      </svg>
    ),
  },
  {
    id: 'progress',
    label: 'Прогресс',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/>
      </svg>
    ),
  },
  {
    id: 'program',
    label: 'Программа',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
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
      {tab === 'profile' && <Profile onBack={() => setTab('dashboard')} />}

      <nav className="navbar" style={{ display: tab === 'profile' ? 'none' : 'flex' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`nav-tab${tab === t.id ? ' active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.icon}
            <span className="nav-label">{t.label}</span>
          </button>
        ))}
      </nav>
    </ErrorBoundary>
  )
}
