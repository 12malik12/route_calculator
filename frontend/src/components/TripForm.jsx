import { useState } from "react"

const FIELDS = [
  {
    name: "current_location",
    label: "Current Location",
    placeholder: "e.g. Chicago, IL",
  },
  {
    name: "pickup_location",
    label: "Pickup Location",
    placeholder: "e.g. Memphis, TN",
  },
  {
    name: "dropoff_location",
    label: "Dropoff Location",
    placeholder: "e.g. Jacksonville, FL",
  },
]

export default function TripForm({ onSubmit, loading }) {
  const [values, setValues] = useState({
    current_location: "",
    pickup_location: "",
    dropoff_location: "",
    cycle_hours_used: "",
  })

  function update(name, value) {
    setValues((v) => ({ ...v, [name]: value }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    onSubmit({
      current_location: values.current_location.trim(),
      pickup_location: values.pickup_location.trim(),
      dropoff_location: values.dropoff_location.trim(),
      cycle_hours_used: Number(values.cycle_hours_used || 0),
    })
  }

  const ready =
    values.current_location &&
    values.pickup_location &&
    values.dropoff_location &&
    values.cycle_hours_used !== ""

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl bg-white p-6 shadow-xl ring-1 ring-slate-200 sm:p-8"
    >
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.name} className="flex flex-col gap-1.5">
            <label
              htmlFor={f.name}
              className="text-sm font-semibold text-slate-700"
            >
              {f.label}
            </label>
            <input
              id={f.name}
              type="text"
              required
              value={values[f.name]}
              placeholder={f.placeholder}
              onChange={(e) => update(f.name, e.target.value)}
              className="rounded-lg border border-slate-300 px-3.5 py-2.5 text-slate-900 outline-none transition focus:border-[var(--color-brand)] focus:ring-2 focus:ring-blue-100"
            />
          </div>
        ))}

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="cycle_hours_used"
            className="text-sm font-semibold text-slate-700"
          >
            Current Cycle Hours Used
          </label>
          <input
            id="cycle_hours_used"
            type="number"
            min="0"
            max="70"
            step="0.5"
            required
            value={values.cycle_hours_used}
            placeholder="0 – 70"
            onChange={(e) => update("cycle_hours_used", e.target.value)}
            className="rounded-lg border border-slate-300 px-3.5 py-2.5 text-slate-900 outline-none transition focus:border-[var(--color-brand)] focus:ring-2 focus:ring-blue-100"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || !ready}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-brand)] px-5 py-3 text-base font-semibold text-white transition hover:bg-[var(--color-brand-600)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? (
          <>
            <span
              className="h-5 w-5 animate-spin rounded-full border-2 border-white/40 border-t-white"
              aria-hidden="true"
            />
            Calculating Route…
          </>
        ) : (
          "Calculate Route"
        )}
      </button>
    </form>
  )
}
