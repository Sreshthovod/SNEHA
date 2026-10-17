import { useEffect } from 'react'

export const APP_TITLE = 'SNEHA'

/** Sets `document.title` to "<parts> – SNEHA" (WCAG 2.4.2). Empty parts are skipped. */
export function useDocumentTitle(...parts: Array<string | null | undefined | false>) {
  const title = [...parts.filter(Boolean), APP_TITLE].join(' – ')
  useEffect(() => {
    document.title = title
  }, [title])
}

/**
 * Moves keyboard focus to the first element matching one of `selectors` inside `root`,
 * waiting briefly for content that is still loading. Returns a cancel function.
 */
export function focusWhenReady(root: () => HTMLElement | null, selectors: string[], fallback?: () => HTMLElement | null) {
  let tries = 0
  let timer: number | undefined
  const attempt = () => {
    const container = root()
    let target: HTMLElement | null = null
    if (container) {
      for (const s of selectors) {
        target = container.querySelector<HTMLElement>(s)
        if (target) break
      }
    }
    if (!target && tries < 20) {
      tries += 1
      timer = window.setTimeout(attempt, 50)
      return
    }
    target = target ?? fallback?.() ?? container
    if (!target) return
    if (!target.hasAttribute('tabindex') && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(target.tagName))
      target.setAttribute('tabindex', '-1')
    target.focus({ preventScroll: true })
    target.scrollIntoView?.({ block: 'nearest' })
  }
  timer = window.setTimeout(attempt, 0)
  return () => window.clearTimeout(timer)
}
