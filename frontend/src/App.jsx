import { useState } from "react"
import TripForm from "./components/TripForm.jsx"
import RouteMap from "./components/RouteMap.jsx"
import TripSummary from "./components/TripSummary.jsx"
import ELDLogSheet from "./components/ELDLogSheet.jsx"
import { calculateTrip } from "./api.js"

export default function App() {
  const [trip, setTrip] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleSubmit(payload) {
    setLoading(true)
    setError("")
    try {
      const data = await calculateTrip(payload)
      setTrip(data)
      setTimeout(() => {
        document
          .getElementById("results")
          ?.scrollIntoView({ behavior: "smooth" })
      }, 100)
    } catch (err) {
      setError(err.message || "Something went wrong.")
      setTrip(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-full bg-slate-50">
      {/* Header / hero */}
      <header className="bg-[var(--color-navy)] no-print">
        <div className="mx-auto max-w-5xl px-4 py-12 sm:py-16">
          <div className="flex items-center gap-2 text-blue-300">
            <TruckIcon />
            <span className="text-sm font-semibold uppercase tracking-wider">
              TruckLogix
            </span>
          </div>
          <h1 className="mt-4 text-3xl font-extrabold leading-tight text-white text-balance sm:text-4xl">
            Plan your route. Generate compliant ELD logs.
          </h1>
          <p className="mt-3 max-w-2xl text-pretty text-base text-slate-300">
            Enter your trip details and TruckLogix maps the full route with all
            required stops and produces FMCSA-compliant Driver&apos;s Daily Log
            sheets for every day of the trip.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-20">
        {/* Form sits over the hero edge */}
        <section className="-mt-8 sm:-mt-10">
          <TripForm onSubmit={handleSubmit} loading={loading} />
          {error ? (
            <p
              role="alert"
              className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm font-medium text-red-700 ring-1 ring-red-200"
            >
              {error}
            </p>
          ) : null}
        </section>

        {trip ? (
          <div id="results" className="mt-10 flex flex-col gap-8">
            <section>
              <h2 className="mb-3 text-lg font-bold text-[var(--color-navy)] no-print">
                Route Map
              </h2>
              <RouteMap polyline={trip.polyline} stops={trip.stops} />
            </section>

            <TripSummary trip={trip} />

            <section className="flex flex-col gap-6">
              <div className="flex items-center justify-between no-print">
                <h2 className="text-lg font-bold text-[var(--color-navy)]">
                  Daily Log Sheets
                </h2>
                <button
                  onClick={() => window.print()}
                  className="rounded-lg bg-[var(--color-brand)] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[var(--color-brand-600)]"
                >
                  Download Logs (PDF)
                </button>
              </div>
              {trip.daily_logs.map((day) => (
                <ELDLogSheet key={day.day} day={day} />
              ))}
            </section>
          </div>
        ) : (
          <section className="mt-12 text-center no-print">
            <p className="text-sm text-slate-500">
              Try: Chicago, IL &rarr; Memphis, TN &rarr; Jacksonville, FL with 32
              cycle hours used.
            </p>
          </section>
        )}
      </main>
    </div>
  )
}

function TruckIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2" />
      <path d="M15 18H9" />
      <path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14" />
      <circle cx="17" cy="18" r="2" />
      <circle cx="7" cy="18" r="2" />
    </svg>
  )
}
