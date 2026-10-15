import { useBackendStatus } from '../hooks/useBackendStatus'
import { config } from '../config/env'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { StatusBadge } from './ui/StatusBadge'

export function BackendStatusCard() {
  const { status, refresh } = useBackendStatus()

  return (
    <Card title="Server connection">
      <div aria-live="polite">
        {status.state === 'checking' && <StatusBadge tone="neutral" label="Checking…" />}
        {status.state === 'online' && <StatusBadge tone="success" label="Online" />}
        {status.state === 'degraded' && <StatusBadge tone="warning" label="Degraded" />}
        {status.state === 'offline' && <StatusBadge tone="danger" label="Unreachable" />}

        {status.state === 'offline' && <p>{status.message}</p>}

        {(status.state === 'online' || status.state === 'degraded') && (
          <dl className="definition-list">
            <dt>Service</dt>
            <dd>
              {status.health.service} v{status.health.version}
            </dd>
            <dt>Environment</dt>
            <dd>{status.health.environment}</dd>
            {status.readiness.checks.map((check) => (
              <div key={check.name}>
                <dt>{check.name}</dt>
                <dd>
                  {check.status === 'ok' ? 'OK' : 'Error'}
                  {check.detail ? ` — ${check.detail}` : ''}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
      <p>
        API: <code>{config.apiBaseUrl}</code>
      </p>
      <Button variant="secondary" onClick={refresh} disabled={status.state === 'checking'}>
        Check again
      </Button>
    </Card>
  )
}
