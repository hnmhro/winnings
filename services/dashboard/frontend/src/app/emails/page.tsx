'use client'
import { useEffect, useState } from 'react'

type Email = {
  id: string
  subject: string
  sender: string
  classification: string
  win_description: string | null
  win_value: number | null
  action_required: string | null
  action_deadline: string | null
  notified: boolean
  received_at: string
}

const CLASS_LABEL: Record<string, string> = {
  WIN_NOTIFICATION: 'Gewinn!',
  CONFIRMATION: 'Bestätigung',
  NEWSLETTER: 'Newsletter',
  SPAM: 'Spam',
  UNKNOWN: 'Unbekannt',
}

const CLASS_COLOR: Record<string, string> = {
  WIN_NOTIFICATION: 'bg-green-100 text-green-700 font-semibold',
  CONFIRMATION: 'bg-blue-100 text-blue-700',
  NEWSLETTER: 'bg-gray-100 text-gray-600',
  SPAM: 'bg-red-100 text-red-500',
  UNKNOWN: 'bg-gray-100 text-gray-500',
}

export default function Emails() {
  const [emails, setEmails] = useState<Email[]>([])
  const [wins, setWins] = useState<Email[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/emails?limit=50').then((r) => r.json()),
      fetch('/api/emails/wins').then((r) => r.json()),
    ]).then(([all, w]) => {
      setEmails(all)
      setWins(w)
      setLoading(false)
    })
  }, [])

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">E-Mails & Gewinne</h1>

      {wins.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-green-700">Gewinn-Benachrichtigungen</h2>
          {wins.map((w) => (
            <div
              key={w.id}
              className="bg-green-50 border border-green-200 rounded-xl p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-semibold text-green-800 text-lg">{w.subject}</p>
                  <p className="text-sm text-green-600 mt-0.5">Von: {w.sender}</p>
                </div>
                {w.win_value && (
                  <span className="text-2xl font-bold text-green-700 whitespace-nowrap">
                    {w.win_value.toLocaleString('de-DE')} €
                  </span>
                )}
              </div>
              {w.win_description && (
                <p className="mt-3 text-green-800">{w.win_description}</p>
              )}
              {w.action_required && (
                <div className="mt-3 bg-white border border-green-200 rounded-lg px-4 py-3">
                  <p className="text-sm font-medium text-gray-700">Aktion erforderlich:</p>
                  <p className="text-sm text-gray-800 mt-0.5">{w.action_required}</p>
                  {w.action_deadline && (
                    <p className="text-xs text-red-600 mt-1">
                      Frist: {new Date(w.action_deadline).toLocaleDateString('de-DE')}
                    </p>
                  )}
                </div>
              )}
              <p className="text-xs text-green-500 mt-3">
                Empfangen: {new Date(w.received_at).toLocaleString('de-DE')}
              </p>
            </div>
          ))}
        </div>
      )}

      {wins.length === 0 && !loading && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 text-center text-blue-600">
          Noch keine Gewinn-Benachrichtigungen. Das System prüft alle 15 Minuten das Postfach.
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Alle E-Mails</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                <th className="px-5 py-3 text-left">Betreff</th>
                <th className="px-5 py-3 text-left">Absender</th>
                <th className="px-5 py-3 text-left">Typ</th>
                <th className="px-5 py-3 text-left">Empfangen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && (
                <tr>
                  <td colSpan={4} className="px-5 py-8 text-center text-gray-400">Lädt…</td>
                </tr>
              )}
              {!loading && emails.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-8 text-center text-gray-400">
                    Noch keine E-Mails verarbeitet.
                  </td>
                </tr>
              )}
              {emails.map((e) => (
                <tr
                  key={e.id}
                  className={`hover:bg-gray-50 transition-colors ${e.classification === 'WIN_NOTIFICATION' ? 'bg-green-50' : ''}`}
                >
                  <td className="px-5 py-3 font-medium text-gray-800 max-w-xs truncate">
                    {e.subject}
                  </td>
                  <td className="px-5 py-3 text-gray-500 text-xs">{e.sender}</td>
                  <td className="px-5 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${CLASS_COLOR[e.classification] ?? 'bg-gray-100 text-gray-500'}`}>
                      {CLASS_LABEL[e.classification] ?? e.classification}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-400 text-xs">
                    {new Date(e.received_at).toLocaleString('de-DE')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
