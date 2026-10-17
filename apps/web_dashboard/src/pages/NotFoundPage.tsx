import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui/PageHeader'

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" lede="The page you asked for does not exist." />
      <Link to="/" className="button">
        Go to the start page
      </Link>
    </>
  )
}
