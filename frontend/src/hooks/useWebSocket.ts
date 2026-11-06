import { useCallback, useEffect, useRef, useState } from 'react'

export type WsStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

export interface UseWebSocketReturn {
  status: WsStatus
  lastMessage: MessageEvent | null
  sendMessage: (data: string | Blob | BufferSource) => void
  disconnect: () => void
}

/**
 * Reusable WebSocket hook.
 *
 * Connects when `url` is non-null, disconnects when it becomes null or the
 * component unmounts. Exposes the last raw MessageEvent so callers can parse
 * JSON however they need without coupling the hook to a specific schema.
 *
 * @param url  Full WebSocket URL (e.g. "ws://localhost:8000/api/v1/session/ws/abc123")
 *             Pass null to stay disconnected.
 */
export function useWebSocket(url: string | null): UseWebSocketReturn {
  const wsRef  = useRef<WebSocket | null>(null)
  const [status,      setStatus]      = useState<WsStatus>('idle')
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null)

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen    = null
      wsRef.current.onclose   = null
      wsRef.current.onerror   = null
      wsRef.current.onmessage = null
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('closed')
  }, [])

  useEffect(() => {
    if (!url) {
      disconnect()
      setStatus('idle')
      return
    }

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen    = () => setStatus('open')
    ws.onclose   = () => setStatus('closed')
    ws.onerror   = () => setStatus('error')
    ws.onmessage = (evt) => setLastMessage(evt)

    return () => {
      ws.onopen    = null
      ws.onclose   = null
      ws.onerror   = null
      ws.onmessage = null
      ws.close()
    }
  }, [url, disconnect])

  const sendMessage = useCallback(
    (data: string | Blob | BufferSource) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data)
      }
    },
    [],
  )

  return { status, lastMessage, sendMessage, disconnect }
}
