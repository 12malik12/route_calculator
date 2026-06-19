import { useEffect, useRef } from "react"

const STATUS_ROWS = [
  { key: "off_duty", label: "1. Off Duty" },
  { key: "sleeper_berth", label: "2. Sleeper Berth" },
  { key: "driving", label: "3. Driving" },
  { key: "on_duty", label: "4. On Duty (Not Driving)" },
]

const ROW_INDEX = {
  off_duty: 0,
  sleeper_berth: 1,
  driving: 2,
  on_duty: 3,
}

function formatHour(h) {
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  const m = mm === 60 ? 0 : mm
  const carry = mm === 60 ? 1 : 0
  return `${String((hh + carry) % 24).padStart(2, "0")}:${String(m).padStart(2, "0")}`
}

function drawSheet(canvas, day) {
  const ctx = canvas.getContext("2d")
  const dpr = window.devicePixelRatio || 1

  // Logical drawing dimensions.
  const W = 920
  const labelW = 180
  const totalW = 70
  const gridW = W - labelW - totalW
  const headerH = 70
  const hourLabelH = 22
  const rowH = 42
  const gridTop = headerH + hourLabelH
  const gridH = rowH * 4
  const H = gridTop + gridH + 18

  canvas.width = W * dpr
  canvas.height = H * dpr
  canvas.style.width = "100%"
  canvas.style.height = "auto"
  ctx.scale(dpr, dpr)

  ctx.fillStyle = "#ffffff"
  ctx.fillRect(0, 0, W, H)

  // --- Header ---
  ctx.fillStyle = "#1a2744"
  ctx.font = "bold 20px Inter, sans-serif"
  ctx.textBaseline = "top"
  ctx.fillText("Driver's Daily Log", 10, 8)

  ctx.font = "600 13px Inter, sans-serif"
  ctx.fillStyle = "#334155"
  ctx.fillText(`Day ${day.day}`, 10, 36)

  // From / To block, placed in the center of the header to avoid the title.
  ctx.font = "400 12px Inter, sans-serif"
  ctx.fillStyle = "#475569"
  const fromText = `From: ${day.from_location}`
  const toText = `To: ${day.to_location}`
  const infoX = 300
  ctx.fillText(fromText, infoX, 14)
  ctx.fillText(toText, infoX, 34)

  const milesText = `Total Miles Driving: ${day.total_miles}`
  ctx.font = "600 12px Inter, sans-serif"
  ctx.fillStyle = "#1a2744"
  const milesW = ctx.measureText(milesText).width
  ctx.fillText(milesText, W - milesW - 10, 24)

  const gridLeft = labelW
  const gridRight = labelW + gridW

  // --- Hour labels (midnight -> noon -> midnight) ---
  ctx.textAlign = "center"
  ctx.font = "10px Inter, sans-serif"
  ctx.fillStyle = "#64748b"
  for (let h = 0; h <= 24; h++) {
    const x = gridLeft + (gridW * h) / 24
    let label = String(h % 24)
    if (h === 0) label = "Mid"
    else if (h === 12) label = "Noon"
    else if (h === 24) label = "Mid"
    ctx.fillText(label, x, headerH)
  }
  ctx.textAlign = "left"

  // --- Grid background ---
  for (let r = 0; r < 4; r++) {
    const y = gridTop + r * rowH
    // Alternating row shading.
    ctx.fillStyle = r % 2 === 0 ? "#f8fafc" : "#ffffff"
    ctx.fillRect(gridLeft, y, gridW, rowH)
  }

  // Vertical hour lines + 15-min ticks.
  for (let h = 0; h <= 24; h++) {
    const x = gridLeft + (gridW * h) / 24
    ctx.strokeStyle = h % 12 === 0 ? "#94a3b8" : "#cbd5e1"
    ctx.lineWidth = h % 12 === 0 ? 1.2 : 0.6
    ctx.beginPath()
    ctx.moveTo(x, gridTop)
    ctx.lineTo(x, gridTop + gridH)
    ctx.stroke()

    if (h < 24) {
      // quarter-hour ticks within each hour
      for (let q = 1; q < 4; q++) {
        const qx = x + (gridW / 24) * (q / 4)
        for (let r = 0; r < 4; r++) {
          const rowTop = gridTop + r * rowH
          const tickH = q === 2 ? 8 : 4
          ctx.strokeStyle = "#e2e8f0"
          ctx.lineWidth = 0.5
          ctx.beginPath()
          ctx.moveTo(qx, rowTop)
          ctx.lineTo(qx, rowTop + tickH)
          ctx.moveTo(qx, rowTop + rowH)
          ctx.lineTo(qx, rowTop + rowH - tickH)
          ctx.stroke()
        }
      }
    }
  }

  // Horizontal row lines.
  ctx.strokeStyle = "#94a3b8"
  ctx.lineWidth = 1
  for (let r = 0; r <= 4; r++) {
    const y = gridTop + r * rowH
    ctx.beginPath()
    ctx.moveTo(gridLeft, y)
    ctx.lineTo(gridRight, y)
    ctx.stroke()
  }
  // Outer border around full grid (including labels + totals).
  ctx.strokeStyle = "#1a2744"
  ctx.lineWidth = 1.4
  ctx.strokeRect(gridLeft, gridTop, gridW, gridH)

  // --- Row labels ---
  ctx.fillStyle = "#1a2744"
  ctx.font = "600 12px Inter, sans-serif"
  ctx.textBaseline = "middle"
  STATUS_ROWS.forEach((row, r) => {
    const y = gridTop + r * rowH + rowH / 2
    ctx.fillText(row.label, 10, y)
  })

  // --- Status totals on the right ---
  ctx.textAlign = "center"
  ctx.font = "bold 13px Inter, sans-serif"
  STATUS_ROWS.forEach((row, r) => {
    const y = gridTop + r * rowH + rowH / 2
    const val = day.totals[row.key] ?? 0
    ctx.fillStyle = "#1a2744"
    ctx.fillText(val.toFixed(1), gridRight + totalW / 2, y)
  })
  ctx.font = "9px Inter, sans-serif"
  ctx.fillStyle = "#64748b"
  ctx.fillText("Hrs", gridRight + totalW / 2, gridTop - 10)
  ctx.textAlign = "left"
  ctx.textBaseline = "top"

  // --- Status line (the duty graph) ---
  const xForHour = (h) => gridLeft + (gridW * h) / 24
  const yForRow = (statusKey) =>
    gridTop + ROW_INDEX[statusKey] * rowH + rowH / 2

  const segs = [...day.segments].sort((a, b) => a.start_hour - b.start_hour)
  ctx.strokeStyle = "#1d4ed8"
  ctx.lineWidth = 3
  ctx.lineJoin = "round"
  ctx.lineCap = "round"

  let prevY = null
  segs.forEach((seg) => {
    const x1 = xForHour(seg.start_hour)
    const x2 = xForHour(seg.end_hour)
    const y = yForRow(seg.status)
    // Vertical connector when the status changes.
    if (prevY !== null && prevY !== y) {
      ctx.beginPath()
      ctx.moveTo(x1, prevY)
      ctx.lineTo(x1, y)
      ctx.stroke()
    }
    // Horizontal status line.
    ctx.beginPath()
    ctx.moveTo(x1, y)
    ctx.lineTo(x2, y)
    ctx.stroke()
    prevY = y
  })
}

export default function ELDLogSheet({ day }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (canvasRef.current) {
      drawSheet(canvasRef.current, day)
    }
  }, [day])

  const remarks = [...day.segments]
    .sort((a, b) => a.start_hour - b.start_hour)
    .filter((s) => s.remark)

  return (
    <div className="print-break rounded-2xl bg-white p-5 shadow-xl ring-1 ring-slate-200 sm:p-6">
      <canvas ref={canvasRef} className="w-full" role="img"
        aria-label={`Daily log grid for day ${day.day}`} />

      <div className="mt-4 border-t border-slate-200 pt-4">
        <h4 className="mb-2 text-sm font-bold text-[var(--color-navy)]">
          Remarks
        </h4>
        {remarks.length === 0 ? (
          <p className="text-sm text-slate-400">No status changes recorded.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            {remarks.map((s, i) => (
              <li key={i} className="text-sm text-slate-600">
                <span className="font-semibold text-slate-800">
                  {formatHour(s.start_hour)}
                </span>{" "}
                — {s.remark}{" "}
                <span className="text-slate-400">({s.location})</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
