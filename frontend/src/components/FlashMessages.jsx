export default function FlashMessages({ messages, onDismiss }) {
  if (!messages?.length) return null

  return (
    <div className="fixed top-4 right-4 z-[80] flex w-[min(92vw,420px)] flex-col gap-2">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`rounded-xl border px-4 py-3 shadow-lg backdrop-blur ${
            msg.type === 'success'
              ? 'border-emerald-300 bg-emerald-50/95 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-200'
              : 'border-red-300 bg-red-50/95 text-red-800 dark:border-red-800 dark:bg-red-950/80 dark:text-red-200'
          }`}
          role="alert"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="m-0 text-sm font-medium">{msg.text}</p>
            <button
              type="button"
              className="text-xs opacity-70 hover:opacity-100"
              onClick={() => onDismiss(msg.id)}
            >
              Close
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
