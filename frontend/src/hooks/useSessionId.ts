import { useState } from 'react'
import { v4 as uuidv4 } from 'uuid'

const SESSION_KEY = 'ft_session_id'

export function useSessionId(): string {
  const [sessionId] = useState<string>(() => {
    let id = localStorage.getItem(SESSION_KEY)
    if (!id) {
      id = uuidv4()
      localStorage.setItem(SESSION_KEY, id)
    }
    return id
  })
  return sessionId
}
