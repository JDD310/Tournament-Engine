import { Link } from 'react-router-dom'

// Shown for unknown paths and for tournaments the API doesn't know. It says
// the same thing either way, so it gives nothing away about which IDs exist.
export default function NotFoundPage() {
  return (
    <main className="not-found">
      <h1>Page not found</h1>
      <p>
        We couldn't find that tournament or page. The link may be mistyped or incomplete, so check
        it with whoever shared it.
      </p>
      <p>
        <Link to="/">Go to the home page</Link>
      </p>
    </main>
  )
}
