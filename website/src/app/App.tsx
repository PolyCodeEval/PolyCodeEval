import { useEffect, useState } from 'react'
import { AppShell } from './AppShell'
import { readRoute, routes } from './router'

export default function App() {
  const [route, setRoute] = useState(readRoute)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!window.location.hash)
      history.replaceState(null, '', `${location.pathname}${location.search}#/`)
    const update = () => {
      setRoute(readRoute())
      setMenuOpen(false)
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])

  const View = routes[route] ?? routes['/']
  return (
    <AppShell
      route={route}
      menuOpen={menuOpen}
      onMenuToggle={() => setMenuOpen((open) => !open)}
      View={View}
    />
  )
}
