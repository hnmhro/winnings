'use client'
import { useEffect, useState, useCallback } from 'react'

type Contest = {
  id: string
  title: string | null
  url: string
  source: string | null
  status: string
  trust_score: number
  estimated_value: number | null
  prize_description: string | null
  participation_type: string
  found_at: string
  participated_at: string | null
}

const STATUSES = ['alle', 'found', 'queued', 'participating', 'done', 'won', 'lost', 'error']

const STATUS_LABEL: Record<string, string> = {
  alle: 'Alle',
  found: 'Gefunden',
  queued: 'In Queue',
  participating: 'Läuft',
  done: 'Fertig',
  won: 'Gewonnen',
  lost: 'Nicht gewonnen',
  skipped: 'Übersprungen',
  error: 'Fehler',
}

const STATUS_COLOR: Record<string, string> = {
  found: 'bg-blue-100 text-blue-700',
  queued: 'bg-yellow-100 text-yellow-700',
  participating: 'bg-purple-100 text-purple-700',
  done: 'bg-gray-100 text-gray-600',
  won: 'bg-green-100 text-green-700',
  lost: 'bg-red-100 text-red-600',
  skipped: 'bg-gray-100 text-gray-500',
  error: 'bg-red-100 text-red-700',
}

export default function Contests() {
  const [filter, setFilter] = useState('alle')
  const [contests, setContests] = useState<Contest[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const url =
        filter === 'alle'
          ? '/api/contests?limit=100'
          : `/api/contests?status=${filter}&limit=100`
      const data = await fetch(url).then((r) => r.json())
      setContests(data)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Gewinnspiele</h1>
        <span className="text-sm text-gray-400">{contests.length} Einträge</span>
      </div>

      <div className="flex gap-2 flex-wrap">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition ${
              filter === s
                ? 'bg-blue-600 text-white'
                : 'bg-white border border-gray-200 text-gray-600 hover:border-blue-400'
            }`}
          >
            {STATUS_LABEL[s] ?? s}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                <th className="px-5 py-3 text-left">Titel / URL</th>
                <th className="px-5 py-3 text-left">Quelle</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-left">Typ</th>
                <th className="px-5 py-3 text-left">Vertrauen</th>
                <th className="px-5 py-3 text-left">Gewinn</th>
                <th className="px-5 py-3 text-left">Gefunden</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-gray-400">
                    Lädt…
                  </td>
                </tr>
              )}
              {!loading && contests.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-gray-400">
                    Keine Gewinnspiele mit Status "{STATUS_LABEL[filter]}"
                  </td>
                </tr>
              )}
              {contests.map((c) => (
                <tr
                  key={c.id}
                  className={`hover:bg-gray-50 transition-colors ${c.status === 'won' ? 'bg-green-50' : ''}`}
                >
                  <td className="px-5 py-3 max-w-xs">
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-gray-800 hover:text-blue-600 truncate block"
                    >
                      {c.title || 'Ohne Titel'}
                    </a>
                    <span className="text-xs text-gray-400 truncate block">{c.url}</span>
                  </td>
                  <td className="px-5 py-3 text-gray-500 text-xs">{c.source ?? '–'}</td>
                  <td className="px-5 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLOR[c.status] ?? 'bg-gray-100 text-gray-600'}`}>
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500 capitalize text-xs">
                    {c.participation_type ?? '–'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-200 rounded-full">
                        <div
                          className="h-1.5 bg-blue-500 rounded-full"
                          style={{ width: `${(c.trust_score ?? 0) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">
                        {((c.trust_score ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-600 text-xs">
                    {c.prize_description
                      ? <span title={c.prize_description} className="truncate block max-w-[140px]">{c.prize_description}</span>
                      : c.estimated_value
                      ? `${c.estimated_value.toLocaleString('de-DE')} €`
                      : '–'}
                  </td>
                  <td className="px-5 py-3 text-gray-400 text-xs">
                    {new Date(c.found_at).toLocaleDateString('de-DE')}
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
