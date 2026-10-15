import { Card } from '../components/ui/Card'
import { useAuth } from '../state/auth'

export function UnsupportedRolePage() {
  const { user } = useAuth()
  return (
    <Card title="This dashboard is for caregivers and clinicians">
      {user?.role === 'patient' ? (
        <p>Please use the SNEHA app on the phone. It has your activities and memories.</p>
      ) : (
        <p>
          Administrator accounts do not have access to patient information. Account tasks are
          done with the operator tools described in the deployment guide.
        </p>
      )}
    </Card>
  )
}
