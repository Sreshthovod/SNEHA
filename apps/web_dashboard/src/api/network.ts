/** Reports whether the last API call reached the server, for the connection banner. */
type Listener = (reachable: boolean) => void
const listeners = new Set<Listener>()
let reachable = true

export function reportReachable(value: boolean): void {
  if (value === reachable) return
  reachable = value
  listeners.forEach((listener) => listener(value))
}

export function isServerReachable(): boolean {
  return reachable
}

export function onReachabilityChange(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
