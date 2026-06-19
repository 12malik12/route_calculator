// API client for the Django backend. Requests go through the Vite proxy
// (see vite.config.js) so the same-origin "/api" path reaches Django.
export async function calculateTrip(payload) {
  const res = await fetch("https://route-calculator-bi9w.onrender.com/api/trip/calculate/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  let data = null
  try {
    data = await res.json()
  } catch {
    // ignore parse errors; handled below
  }

  if (!res.ok) {
    const message =
      (data && (data.detail || Object.values(data).flat().join(" "))) ||
      `Request failed (${res.status})`
    throw new Error(message)
  }
  return data
}
