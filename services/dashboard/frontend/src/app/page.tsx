'use client'
import { useEffect, useState, useCallback } from 'react'

type Stats = Record<string, number>
type Contest = {
  id: string
  title: string | null
  url: string
  status: string
  trust_score: number
  estimated_value: number | null
  found_at: string
}

const STATUS_LABEL: Record<string, string> = {
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

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  )
}

function ActionButton({
  label,
  endpoint,
  method = 'POST',
  color = 'blue',
  confirm,
  onDone,
}: {
  label: string
  endpoint: string
  method?: 'POST' | 'DELETE'
  color?: 'blue' | 'green' | 'red'
  confirm?: string
  onDone?: (result: Record<string, unknown>) => void
}) {
  const [state, setState] = useState<'idle' | 'loading' | 'done'>('idle')
  const [info, setInfo] = useState('')

  const trigger = async () => {
    if (confirm && !window.confirm(confirm)) return
    setState('loading')
    setInfo('')
    try {
      const res = await fetch(`/api${endpoint}`, { method })
      const data = await res.json()
      if (data.deleted !== undefined) setInfo(`${data.deleted} gelöscht`)
      onDone?.(data)
      setState('done')
      setTimeout(() => { setState('idle'); setInfo('') }, 4000)
    } catch {
      setState('idle')
    }
  }

  const base =
    color === 'green' ? 'bg-green-600 hover:bg-green-700' :
    color === 'red'   ? 'bg-red-500 hover:bg-red-600' :
                        'bg-blue-600 hover:bg-blue-700'

  return (
    <button
      onClick={trigger}
      disabled={state === 'loading'}
      className={`${base} text-white text-sm font-medium px-4 py-2 rounded-lg transition disabled:opacity-60`}
    >
      {state === 'loading' ? 'Läuft…' :
       state === 'done'    ? (info || 'Erledigt!') :
                             label}
    </button>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({})
  const [contests, setContests] = useState<Contest[]>([])
  const [lastUpdate, setLastUpdate] = useState('')

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([
        fetch('/api/contests/stats').then((r) => r.json()),
        fetch('/api/contests?limit=10').then((r) => r.json()),
      ])
      setStats(s)
      setContests(c)
      setLastUpdate(new Date().toLocaleTimeString('de-DE'))
    } catch {}
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [load])

  const total = Object.values(stats).reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          {lastUpdate && (
            <p className="text-xs text-gray-400 mt-1">Zuletzt aktualisiert: {lastUpdate}</p>
          )}
        </div>
        <div className="flex gap-3 flex-wrap">
          <ActionButton label="Jetzt suchen" endpoint="/internal/scrape" />
          <ActionButton label="Teilnehmen starten" endpoint="/internal/participate" color="green" onDone={() => load()} />
          <ActionButton label="E-Mail prüfen" endpoint="/internal/check-email" color="green" />
          <ActionButton
            label="Abgelaufene löschen"
            endpoint="/contests/expired"
            method="DELETE"
            color="red"
            confirm="Alle abgelaufenen Gewinnspiele unwiderruflich löschen?"
            onDone={() => load()}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Gesamt gefunden" value={total} color="text-gray-900" />
        <StatCard label="Gewonnen" value={stats.won ?? 0} color="text-green-600" />
        <StatCard label="In Queue" value={stats.queued ?? 0} color="text-yellow-600" />
        <StatCard label="Fehler" value={stats.error ?? 0} color="text-red-500" />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Neueste Gewinnspiele</h2>
          <a href="/contests" className="text-sm text-blue-600 hover:underline">
            Alle anzeigen
          </a>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                <th className="px-5 py-3 text-left">Titel / URL</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-left">Vertrauen</th>
                <th className="px-5 py-3 text-left">Wert</th>
                <th className="px-5 py-3 text-left">Gefunden</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {contests.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-gray-400">
                    Noch keine Gewinnspiele gefunden. Klicke auf "Jetzt suchen".
                  </td>
                </tr>
              )}
              {contests.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 max-w-xs">
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-gray-800 hover:text-blue-600 truncate block"
                    >
                      {c.title || c.url}
                    </a>
                    <span className="text-xs text-gray-400 truncate block">{c.url}</span>
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLOR[c.status] ?? 'bg-gray-100 text-gray-600'}`}
                    >
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1.5 bg-gray-200 rounded-full">
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
                  <td className="px-5 py-3 text-gray-600">
                    {c.estimated_value ? `${c.estimated_value.toLocaleString('de-DE')} €` : '–'}
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
