import { useSpeechToText } from '../lib/speech/useSpeechToText'
const SHOW_STT_DEBUG = String(import.meta.env.VITE_STT_DEBUG || 'false').toLowerCase() === 'true'

export default function SpeechToTextControl({
  token,
  disabled = false,
  onTranscriptChange,
  onError,
}) {
  const {
    isRecording,
    isConnecting,
    isModelReady,
    transcript,
    debugState,
    startRecording,
    stopRecording,
  } = useSpeechToText({
    token,
    onTranscript: (text) => onTranscriptChange?.(text),
    onError,
  })

  return (
    <div className="flex items-center gap-2 shrink-0">
      <button
        type="button"
        className={`shrink-0 w-12 h-12 flex items-center justify-center rounded-2xl transition-all shadow-md active:scale-95 ${
          isRecording
            ? 'bg-red-500 text-white hover:bg-red-600'
            : 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700'
        }`}
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled || isConnecting}
        aria-label={isRecording ? 'Stop recording' : 'Start recording'}
        title={isRecording ? 'Stop recording' : 'Start recording'}
      >
        {isConnecting ? (
          <span className="w-5 h-5 border-2 border-current/30 border-t-current rounded-full animate-spin block"></span>
        ) : isRecording ? (
          <span className="w-3 h-3 rounded-sm bg-current block"></span>
        ) : (
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 15a3 3 0 0 0 3-3V7a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Zm5-3a1 1 0 1 1 2 0 7 7 0 0 1-6 6.93V21h3a1 1 0 1 1 0 2H8a1 1 0 1 1 0-2h3v-2.07A7 7 0 0 1 5 12a1 1 0 1 1 2 0 5 5 0 1 0 10 0Z" />
          </svg>
        )}
      </button>
      {isRecording && (
        <div className="hidden lg:block min-w-[130px] text-[11px] text-slate-500 dark:text-slate-400">
          {`Listening${isModelReady ? '' : '... loading model'}`}
        </div>
      )}
      {SHOW_STT_DEBUG && (
      <div className="hidden xl:flex flex-col min-w-[220px] rounded-xl border border-cardBorder bg-card px-3 py-2 text-[10px] text-slate-500 dark:text-slate-400 leading-4">
        <span><strong className="text-slate-700 dark:text-slate-200">STT</strong> {debugState.stage}</span>
        <span>bytes: {debugState.bytesSent}</span>
        <span>partials/finals: {debugState.partialCount}/{debugState.finalCount}</span>
        <span>text len: {debugState.lastTranscriptLength}</span>
        <span className="truncate max-w-[190px]">{debugState.lastEvent || transcript || 'idle'}</span>
      </div>
      )}
    </div>
  )
}
