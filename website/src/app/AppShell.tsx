import { Suspense, type ComponentType } from 'react'
import { BookOpenText, Github, Menu, X } from 'lucide-react'
import { Loading } from '../shared/components/States'
import { navigationItems } from './navigation'

interface AppShellProps {
  route: string
  menuOpen: boolean
  onMenuToggle: () => void
  View: ComponentType
}

export function AppShell({ route, menuOpen, onMenuToggle, View }: AppShellProps) {
  const groups = ['Benchmark', 'Community'] as const
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#/" aria-label="PolyCodeEval overview">
          <span className="brand-mark">
            <BookOpenText size={20} />
          </span>
          <span>
            <strong>PolyCodeEval</strong>
            <small>Benchmark & Leaderboard</small>
          </span>
        </a>
        <button
          className="icon-button menu-button"
          onClick={onMenuToggle}
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
        >
          {menuOpen ? <X /> : <Menu />}
        </button>
        <nav className={menuOpen ? 'open' : ''} aria-label="Primary navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group}>
              <span className="nav-group-label">{group}</span>
              {navigationItems
                .filter((item) => item.group === group)
                .map(({ path, title, icon: Icon }) => (
                  <a
                    key={path}
                    href={`#${path}`}
                    className={route === path ? 'active' : ''}
                    title={title}
                  >
                    <Icon size={17} />
                    <span>{title}</span>
                  </a>
                ))}
            </div>
          ))}
        </nav>
        <a
          className="github-link"
          href="https://github.com/PolyCodeEval/PolyCodeEval"
          target="_blank"
          rel="noreferrer"
          aria-label="Open PolyCodeEval on GitHub"
        >
          <Github size={19} />
        </a>
      </header>
      <main className="content">
        <Suspense fallback={<Loading label="Loading page" />}>
          <View />
        </Suspense>
      </main>
      <footer className="site-footer">
        <span>PolyCodeEval · Execution-based multi-granularity code generation benchmark</span>
        <a href="https://github.com/PolyCodeEval/PolyCodeEval" target="_blank" rel="noreferrer">
          Repository
        </a>
      </footer>
    </div>
  )
}
