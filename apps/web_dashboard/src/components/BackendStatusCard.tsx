import { useBackendStatus } from '../hooks/useBackendStatus'
import { config } from '../config/env'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { StatusBadge } from './ui/StatusBadge'

/** Plain connection status first; service details for support staff behind "Technical details". */
export function BackendStatusCard() {
  const { status, refresh } = useBackendStatus()

  return (
    <Card
      title="Connection to SNEHA"
      actions={
        <Button variant="secondary" onClick={refresh} disabled={status.state === 'checking'}>
          Check again
        </Button>
      }
    >
      <div aria-live="polite">
        <p>
          {status.state === 'checking' && <StatusBadge tone="neutral" label="Checking…" />}
          {status.state === 'online' && <StatusBadge tone="success" label="Connected" />}
          {status.state === 'degraded' && <StatusBadge tone="warning" label="Connected, some parts are slow or unavailable" />}
          {status.state === 'offline' && <StatusBadge tone="danger" label="Can't reach SNEHA" />}
        </p>
        {status.state === 'offline' && <p>{status.message}</p>}
      </div>
      <details className="details">
        <summary>Technical details</summary>
        {(status.state === 'online' || status.state === 'degraded') && (
          <dl className="definition-list definition-list--compact">
            <dt>Service</dt>
            <dd>
              {status.health.service} v{status.health.version}
            </dd>
            <dt>Environment</dt>
            <dd>{status.health.environment}</dd>
            {status.readiness.checks.map((check) => (
              <div key={check.name}>
                <dt>{check.name.charAt(0).toUpperCase() + check.name.slice(1)}</dt>
                <dd>
                  {check.status === 'ok' ? 'OK' : 'Error'}
                  {check.detail ? ` — ${check.detail}` : ''}
                </dd>
              </div>
            ))}
          </dl>
        )}
        <p className="field__hint">
          API: <code>{config.apiBaseUrl}</code>
        </p>
      </details>
    </Card>
  )
}
