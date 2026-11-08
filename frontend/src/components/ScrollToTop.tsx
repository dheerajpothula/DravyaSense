import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * ScrollToTop — resets window scroll position on route change.
 *
 * React Router v6 with BrowserRouter does not restore scroll position
 * automatically.  When the user navigates to a new path (e.g. "Back to
 * Site" → "/"), the browser keeps the previous scroll position, which
 * can show a mid-page section instead of the top.
 *
 * This component listens for pathname changes and instantly scrolls
 * the window to the top.  It does NOT fire on in-page section scrolls
 * (those use element.scrollIntoView via refs, not route changes).
 *
 * The dashboard layout uses its own internal scroll container
 * (<main overflow-y-auto>), so window scrolling only affects the
 * landing page — making this safe for both contexts.
 */
export default function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return null
}
