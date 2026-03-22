import { useCallback, useEffect, useRef, useState } from 'react'

import { createWebSocketUrl } from '../api'

const TARGET_SAMPLE_RATE = 16000
const WORKLET_PROCESSOR_NAME = 'pcm-stream-processor'

const workletProcessorSource = `
class PcmStreamProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]
    if (input && input[0]) {
      this.port.postMessage(input[0])
    }
    return true
  }
}

registerProcessor('${WORKLET_PROCESSOR_NAME}', PcmStreamProcessor)
`

function downsampleBuffer(buffer, inputSampleRate, outputSampleRate) {
  if (outputSampleRate === inputSampleRate) {
    return buffer
  }
  const ratio = inputSampleRate / outputSampleRate
  const newLength = Math.round(buffer.length / ratio)
  const result = new Float32Array(newLength)
  let offsetResult = 0
  let offsetBuffer = 0
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio)
    let accum = 0
    let count = 0
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accum += buffer[i]
      count += 1
    }
    result[offsetResult] = count > 0 ? accum / count : 0
    offsetResult += 1
    offsetBuffer = nextOffsetBuffer
  }
  return result
}

function floatTo16BitPCM(float32Array) {
  const buffer = new ArrayBuffer(float32Array.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < float32Array.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, float32Array[i]))
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
  }
  return buffer
}

export function useSpeechToText({ token, onTranscript, onError }) {
  const [isRecording, setIsRecording] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [isModelReady, setIsModelReady] = useState(false)
  const [debugState, setDebugState] = useState({
    stage: 'idle',
    bytesSent: 0,
    partialCount: 0,
    finalCount: 0,
    lastEvent: '',
    lastTranscriptLength: 0,
  })

  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const sourceNodeRef = useRef(null)
  const processorNodeRef = useRef(null)
  const workletUrlRef = useRef(null)
  const stopRequestedRef = useRef(false)

  const cleanupAudio = useCallback(async () => {
    processorNodeRef.current?.disconnect()
    sourceNodeRef.current?.disconnect()
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop())
    }
    mediaStreamRef.current = null
    sourceNodeRef.current = null
    processorNodeRef.current = null
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      await audioContextRef.current.close()
    }
    audioContextRef.current = null
    if (workletUrlRef.current) {
      URL.revokeObjectURL(workletUrlRef.current)
      workletUrlRef.current = null
    }
  }, [])

  const stopRecording = useCallback(async () => {
    if (stopRequestedRef.current) return
    stopRequestedRef.current = true
    setIsRecording(false)
    await cleanupAudio()
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'stop' }))
    } else if (ws && ws.readyState < WebSocket.CLOSING) {
      ws.close()
    }
  }, [cleanupAudio])

  const startRecording = useCallback(async () => {
    if (!token || isRecording || isConnecting) return

    setIsConnecting(true)
    setIsModelReady(false)
    stopRequestedRef.current = false
    setTranscript('')
    setDebugState({
      stage: 'connecting',
      bytesSent: 0,
      partialCount: 0,
      finalCount: 0,
      lastEvent: 'connecting websocket',
      lastTranscriptLength: 0,
    })

    try {
      const ws = new WebSocket(
        createWebSocketUrl('/api/stt/ws', {
          token,
        }),
      )
      ws.binaryType = 'arraybuffer'

      ws.onmessage = async (event) => {
        const payload = JSON.parse(event.data)
        if (payload.type === 'ready') {
          setIsModelReady(true)
          setDebugState((prev) => ({
            ...prev,
            stage: 'ready',
            lastEvent: 'backend ready',
          }))
        }
        if (payload.type === 'interim' || payload.type === 'commit' || payload.type === 'final') {
          const fullText = String(payload.fullText || payload.text || '').trim()
          setTranscript(fullText)
          if (fullText) {
            onTranscript?.(fullText, payload.type === 'final')
          }
          setDebugState((prev) => ({
            ...prev,
            stage: payload.type,
            partialCount: prev.partialCount + (payload.type === 'interim' ? 1 : 0),
            finalCount: prev.finalCount + (payload.type === 'final' ? 1 : 0),
            lastEvent: `${payload.type} received`,
            lastTranscriptLength: fullText.length,
          }))
          if (payload.type === 'final') {
            ws.close()
          }
        }
        if (payload.type === 'state') {
          setDebugState((prev) => ({
            ...prev,
            stage: payload.status || 'state',
            lastEvent: `state: ${payload.status || 'unknown'}`,
          }))
        }
        if (payload.type === 'error') {
          setDebugState((prev) => ({
            ...prev,
            stage: 'error',
            lastEvent: payload.message || 'backend error',
          }))
          onError?.(payload.message || 'Speech transcription failed.')
          await stopRecording()
        }
      }

      ws.onerror = () => {
        setDebugState((prev) => ({
          ...prev,
          stage: 'error',
          lastEvent: 'websocket error',
        }))
        onError?.('Speech transcription websocket failed.')
      }

      ws.onclose = async () => {
        wsRef.current = null
        setIsConnecting(false)
        setIsModelReady(false)
        setDebugState((prev) => ({
          ...prev,
          stage: stopRequestedRef.current ? 'closed' : 'disconnected',
          lastEvent: 'websocket closed',
        }))
        if (!stopRequestedRef.current) {
          await cleanupAudio()
          setIsRecording(false)
        }
      }

      ws.onopen = async () => {
        try {
          wsRef.current = ws
          setDebugState((prev) => ({
            ...prev,
            stage: 'starting',
            lastEvent: 'microphone access requested',
          }))
          ws.send(
            JSON.stringify({
              type: 'start',
              sampleRate: TARGET_SAMPLE_RATE,
            }),
          )

          const mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
              channelCount: 1,
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          })
          mediaStreamRef.current = mediaStream

          const audioContext = new window.AudioContext()
          audioContextRef.current = audioContext
          const blob = new Blob([workletProcessorSource], { type: 'application/javascript' })
          const workletUrl = URL.createObjectURL(blob)
          workletUrlRef.current = workletUrl
          await audioContext.audioWorklet.addModule(workletUrl)
          const source = audioContext.createMediaStreamSource(mediaStream)
          const processor = new AudioWorkletNode(audioContext, WORKLET_PROCESSOR_NAME)
          sourceNodeRef.current = source
          processorNodeRef.current = processor

          processor.port.onmessage = ({ data }) => {
            if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
            const inputData = data instanceof Float32Array ? data : new Float32Array(data)
            const downsampled = downsampleBuffer(
              inputData,
              audioContext.sampleRate,
              TARGET_SAMPLE_RATE,
            )

            const payload = floatTo16BitPCM(downsampled)
            wsRef.current.send(payload)
            setDebugState((prev) => ({
              ...prev,
              stage: 'streaming',
              bytesSent: prev.bytesSent + payload.byteLength,
              lastEvent: 'audio chunk sent',
            }))
          }

          source.connect(processor)
          processor.connect(audioContext.destination)
          setIsRecording(true)
          setIsConnecting(false)
          setDebugState((prev) => ({
            ...prev,
            stage: 'recording',
            lastEvent: 'recording started',
          }))
        } catch (error) {
          await cleanupAudio()
          ws.close()
          setIsConnecting(false)
          setIsRecording(false)
          setDebugState((prev) => ({
            ...prev,
            stage: 'error',
            lastEvent: error?.message || 'microphone access failed',
          }))
          onError?.(error?.message || 'Unable to access microphone.')
        }
      }
    } catch (error) {
      setIsConnecting(false)
      setIsRecording(false)
      await cleanupAudio()
      setDebugState((prev) => ({
        ...prev,
        stage: 'error',
        lastEvent: error?.message || 'unable to start',
      }))
      onError?.(error?.message || 'Unable to start speech transcription.')
    }
  }, [
    cleanupAudio,
    isConnecting,
    isRecording,
    onError,
    onTranscript,
    stopRecording,
    token,
  ])

  useEffect(() => () => {
    stopRecording()
  }, [stopRecording])

  return {
    isRecording,
    isConnecting,
    isModelReady,
    transcript,
    debugState,
    startRecording,
    stopRecording,
  }
}
