interface Props {
  what: string
  error: string | null
  loading: boolean
  retry: () => void
}

/** Loading and error states with a retry button, shared by every page. */
export default function LoadState({ what, error, loading, retry }: Props) {
  if (error) {
    return (
      <div className="load-state error" role="alert">
        <p>
          Could not load {what}: {error}
        </p>
        <button type="button" onClick={retry}>
          Try again
        </button>
      </div>
    )
  }
  if (loading) {
    return (
      <p className="load-state" role="status">
        Loading {what}…
      </p>
    )
  }
  return null
}
