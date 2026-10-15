import { useEffect, useState } from 'react'
import { downloadFile } from '../api/files'

/** Shows a protected photo by fetching it with the sign-in token into a temporary blob URL. */
export function ProtectedImage(props: { fileId: string; alt: string }) {
  // Remount per file so state starts fresh without resetting it inside an effect.
  return <ProtectedImageInner key={props.fileId} {...props} />
}

function ProtectedImageInner({ fileId, alt }: { fileId: string; alt: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl: string | null = null
    downloadFile(fileId, controller.signal)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [fileId])

  if (failed) return <p className="photo photo--missing">Photo unavailable</p>
  if (!url) return <p className="photo photo--loading" role="status">Loading photo…</p>
  return <img className="photo" src={url} alt={alt} />
}
