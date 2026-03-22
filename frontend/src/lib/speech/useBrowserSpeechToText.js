import { useCallback, useEffect, useRef, useState } from 'react'


function getSpeechRecognitionClass() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}


export function isBrowserSpeechAvailable() {
  return Boolean(getSpeechRecognitionClass())
}


export function useBrowserSpeechToText({ onTranscript, onError }) {
  const [isRecording, setIsRecording] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isReady, setIsReady] = useState(false)

  const recognitionRef = useRef(null)
  const finalTranscriptRef = useRef('')

  const stopRecording = useCallback(() => {
    const recognition = recognitionRef.current
    if (!recognition) return
    try {
      recognition.stop()
    } catch {
      // Ignore stop race errors from browser speech API.
    }
  }, [])

  const startRecording = useCallback(() => {
    const RecognitionClass = getSpeechRecognitionClass()
    if (!RecognitionClass) {
      onError?.('Google STT is not available in this browser.')
      return
    }

    setIsConnecting(true)
    finalTranscriptRef.current = ''

    const recognition = new RecognitionClass()
    recognition.lang = 'en-US'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setIsConnecting(false)
      setIsRecording(true)
      setIsReady(true)
    }

    recognition.onerror = (event) => {
      const message = event?.error || 'Browser speech recognition failed.'
      onError?.(message)
      setIsConnecting(false)
      setIsRecording(false)
    }

    recognition.onend = () => {
      setIsConnecting(false)
      setIsRecording(false)
    }

    recognition.onresult = (event) => {
      let interimTranscript = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        const text = (result[0]?.transcript || '').trim()
        if (!text) continue
        if (result.isFinal) {
          finalTranscriptRef.current = `${finalTranscriptRef.current} ${text}`.trim()
        } else {
          interimTranscript = `${interimTranscript} ${text}`.trim()
        }
      }
      const composed = `${finalTranscriptRef.current} ${interimTranscript}`.trim()
      if (composed) {
        onTranscript?.(composed, !interimTranscript)
      }
    }

    recognitionRef.current = recognition
    recognition.start()
  }, [onError, onTranscript])

  useEffect(() => {
    return () => {
      stopRecording()
      recognitionRef.current = null
    }
  }, [stopRecording])

  return {
    isRecording,
    isConnecting,
    isReady,
    startRecording,
    stopRecording,
  }
}

