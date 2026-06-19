function Stat({ label, value, sub }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl bg-slate-50 px-5 py-4 ring-1 ring-slate-200">
      <span className="text-2xl font-bold text-[var(--color-navy)]">{value}</span>
      <span className="text-sm font-medium text-slate-600">{label}</span>
      {sub ? <span className="text-xs text-slate-400">{sub}</span> : null}
    </div>
  )
}

export default function TripSummary({ trip }) {
  return (
    <div className="rounded-2xl bg-white p-6 shadow-xl ring-1 ring-slate-200 sm:p-8">
      <h2 className="mb-5 text-lg font-bold text-[var(--color-navy)]">
        Trip Summary
      </h2>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat
          label="Total Distance"
          value={`${trip.total_distance_miles.toLocaleString()} mi`}
        />
        <Stat label="Estimated Trip Time" value={trip.total_duration_label} />
        <Stat label="Driving Days" value={trip.num_days} />
        <Stat label="Fuel Stops" value={trip.fuel_stops} />
        <Stat
          label="Rest Stops"
          value={trip.rest_stops}
          sub={`${trip.cycle_hours_remaining} cycle hrs left`}
        />
      </div>
    </div>
  )
}
