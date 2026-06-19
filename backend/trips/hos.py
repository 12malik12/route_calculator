"""Hours-of-Service (HOS) trip simulation engine.

Simulates an FMCSA property-carrying driver trip on a single continuous clock
(measured in hours from 0). Produces an ordered list of duty-status events and
a list of physical stops (for map markers).

Rules enforced:
  * 11 hours max driving per shift
  * 14-hour on-duty driving window per shift
  * 10 consecutive hours off duty between shifts
  * 30-minute break required after 8 cumulative hours driving
  * Fuel stop (30 min on-duty) at least every 1000 miles
  * 1 hour on-duty at pickup and 1 hour on-duty at dropoff
  * 70 hours on-duty in a rolling 8-day window (34-hour restart when exceeded)
  * Average speed 55 mph
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

# Duty statuses
OFF = "off_duty"
SB = "sleeper_berth"
DRIVING = "driving"
ON = "on_duty"

AVG_SPEED = 55.0
MAX_DRIVE_PER_SHIFT = 11.0
MAX_ONDUTY_WINDOW = 14.0
REQUIRED_REST = 10.0
DRIVE_BEFORE_BREAK = 8.0
BREAK_DURATION = 0.5
FUEL_INTERVAL_MILES = 1000.0
FUEL_DURATION = 0.5
PICKUP_DURATION = 1.0
DROPOFF_DURATION = 1.0
CYCLE_LIMIT = 70.0
RESTART_DURATION = 34.0


@dataclass
class Event:
    status: str
    start: float          # global clock hours
    end: float            # global clock hours
    location: str
    remark: str = ""


@dataclass
class Stop:
    type: str             # current | pickup | dropoff | fuel | rest | restart | break
    label: str
    arrival: float
    departure: float
    mile: float           # overall trip mile where the stop occurs


@dataclass
class Simulator:
    cycle_hours_used: float
    current_name: str
    pickup_name: str
    dropoff_name: str
    # Optional resolver: given an overall trip mile, returns a human-readable
    # location string (e.g. coordinates) for where a mid-route stop happens.
    locate: Optional[Callable[[float], str]] = None

    clock: float = 0.0
    shift_start: float = 0.0
    drive_this_shift: float = 0.0
    drive_since_break: float = 0.0
    miles_since_fuel: float = 0.0
    overall_miles: float = 0.0
    cycle_onduty: float = 0.0

    events: List[Event] = field(default_factory=list)
    stops: List[Stop] = field(default_factory=list)

    def __post_init__(self):
        self.cycle_onduty = self.cycle_hours_used

    # -- low level helpers -------------------------------------------------
    def _here(self, fallback: str) -> str:
        """Location label for a stop at the current mile.

        Uses the coordinate resolver when available so mid-route stops report
        where they actually happen instead of the city being driven toward.
        """
        if self.locate is not None:
            try:
                return self.locate(self.overall_miles)
            except Exception:
                pass
        return fallback

    def _add_event(self, status: str, duration: float, location: str, remark: str = ""):
        if duration <= 0:
            return
        start = self.clock
        end = self.clock + duration
        self.events.append(Event(status, start, end, location, remark))
        self.clock = end
        if status in (DRIVING, ON):
            self.cycle_onduty += duration

    def _take_rest(self, location: str):
        """10-hour off-duty/sleeper rest that resets the shift counters."""
        location = self._here(location)
        self.stops.append(
            Stop("rest", "10-Hour Rest", self.clock, self.clock + REQUIRED_REST,
                 self.overall_miles)
        )
        self._add_event(SB, REQUIRED_REST, location, "10-hour rest period")
        self.shift_start = self.clock
        self.drive_this_shift = 0.0
        self.drive_since_break = 0.0

    def _take_restart(self, location: str):
        """34-hour restart resets the 70-hour cycle."""
        location = self._here(location)
        self.stops.append(
            Stop("restart", "34-Hour Restart", self.clock, self.clock + RESTART_DURATION,
                 self.overall_miles)
        )
        self._add_event(OFF, RESTART_DURATION, location, "34-hour cycle restart")
        self.shift_start = self.clock
        self.drive_this_shift = 0.0
        self.drive_since_break = 0.0
        self.cycle_onduty = 0.0

    def _take_break(self, location: str):
        location = self._here(location)
        self.stops.append(
            Stop("break", "30-Min Break", self.clock, self.clock + BREAK_DURATION,
                 self.overall_miles)
        )
        self._add_event(ON, BREAK_DURATION, location, "30-minute rest break")
        self.drive_since_break = 0.0

    def _take_fuel(self, location: str):
        location = self._here(location)
        self.stops.append(
            Stop("fuel", f"Fuel Stop ({location})", self.clock,
                 self.clock + FUEL_DURATION, self.overall_miles)
        )
        self._add_event(ON, FUEL_DURATION, location, "Fueling")
        self.miles_since_fuel = 0.0

    # -- main drive routine ------------------------------------------------
    def drive(self, miles: float, origin: str, destination: str):
        remaining = miles
        while remaining > 0.01:
            # 70-hour cycle check: restart if we've hit (or all but hit) the
            # limit. A small epsilon avoids a stall when a driving chunk was
            # capped exactly at the remaining cycle balance.
            if self.cycle_onduty >= CYCLE_LIMIT - 0.01:
                self._take_restart(destination)

            # Mandatory 10-hour rest when out of driving time in this shift.
            window_left = MAX_ONDUTY_WINDOW - (self.clock - self.shift_start)
            drive_left = MAX_DRIVE_PER_SHIFT - self.drive_this_shift
            if drive_left <= 0.01 or window_left <= 0.01:
                self._take_rest(destination)
                continue

            # 30-minute break after 8 cumulative driving hours.
            if self.drive_since_break >= DRIVE_BEFORE_BREAK:
                self._take_break(destination)
                continue

            # Fuel stop every 1000 miles.
            if self.miles_since_fuel >= FUEL_INTERVAL_MILES:
                self._take_fuel(destination)
                continue

            # Determine how far we can drive before the next constraint.
            hours_to_break = DRIVE_BEFORE_BREAK - self.drive_since_break
            miles_to_fuel = FUEL_INTERVAL_MILES - self.miles_since_fuel
            cycle_left = CYCLE_LIMIT - self.cycle_onduty   # 70h rolling cycle cap
            limits = [
                remaining / AVG_SPEED,          # rest of this segment
                drive_left,                     # 11h driving cap
                window_left,                    # 14h window
                hours_to_break,                 # 8h break trigger
                miles_to_fuel / AVG_SPEED,      # 1000mi fuel trigger
                cycle_left,                     # 70h cycle cap
            ]
            chunk_hours = max(min(limits), 0.0)
            if chunk_hours <= 0.01:
                # Safety valve: force a rest to avoid an infinite loop.
                self._take_rest(destination)
                continue

            chunk_miles = chunk_hours * AVG_SPEED
            self._add_event(
                DRIVING, chunk_hours, origin,
                f"Driving toward {destination}",
            )
            self.drive_this_shift += chunk_hours
            self.drive_since_break += chunk_hours
            self.miles_since_fuel += chunk_miles
            self.overall_miles += chunk_miles
            remaining -= chunk_miles

    def stop_event(self, stop_type: str, label: str, duration: float, location: str, remark: str):
        # Ensure the driver has window/cycle room to perform on-duty work.
        if self.cycle_onduty + duration > CYCLE_LIMIT:
            self._take_restart(location)
        window_left = MAX_ONDUTY_WINDOW - (self.clock - self.shift_start)
        if window_left < duration:
            self._take_rest(location)
        self.stops.append(
            Stop(stop_type, label, self.clock, self.clock + duration, self.overall_miles)
        )
        self._add_event(ON, duration, location, remark)


def simulate(
    leg1_miles: float,
    leg2_miles: float,
    cycle_hours_used: float,
    current_name: str,
    pickup_name: str,
    dropoff_name: str,
    locate: Optional[Callable[[float], str]] = None,
) -> dict:
    sim = Simulator(
        cycle_hours_used=cycle_hours_used,
        current_name=current_name,
        pickup_name=pickup_name,
        dropoff_name=dropoff_name,
        locate=locate,
    )

    # Origin marker.
    sim.stops.append(Stop("current", current_name, 0.0, 0.0, 0.0))

    # 1. Drive to pickup.
    sim.drive(leg1_miles, current_name, pickup_name)
    # 2. Pickup (1h on-duty).
    sim.stop_event("pickup", pickup_name, PICKUP_DURATION, pickup_name,
                   "Loading at pickup")
    # 3. Drive to dropoff.
    sim.drive(leg2_miles, pickup_name, dropoff_name)
    # 4. Dropoff (1h on-duty).
    sim.stop_event("dropoff", dropoff_name, DROPOFF_DURATION, dropoff_name,
                   "Unloading at dropoff")

    total_hours = sim.clock
    daily_logs = build_daily_logs(
        sim.events,
        current_name=current_name,
        pickup_name=pickup_name,
        dropoff_name=dropoff_name,
        leg1_miles=leg1_miles,
        total_miles=leg1_miles + leg2_miles,
        locate=locate,
    )

    return {
        "events": sim.events,
        "stops": sim.stops,
        "total_hours": total_hours,
        "num_days": len(daily_logs),
        "daily_logs": daily_logs,
    }


def elapsed_distance_at_hour(events: List[Event], hour: float) -> float:
    """Cumulative miles driven by global clock `hour`.

    Sums completed driving segments before `hour` plus the partial distance of
    any driving segment in progress at `hour`. This reflects the driver's true
    position along the route at an arbitrary moment (e.g. a midnight boundary
    with no discrete stop event).
    """
    miles = 0.0
    for ev in events:
        if ev.status != DRIVING:
            continue
        if ev.end <= hour:
            miles += (ev.end - ev.start) * AVG_SPEED
        elif ev.start < hour < ev.end:
            miles += (hour - ev.start) * AVG_SPEED
        # segments starting at/after `hour` contribute nothing
    return miles


def get_position_at_hour(
    events: List[Event],
    hour: float,
    *,
    current_name: str,
    pickup_name: str,
    dropoff_name: str,
    leg1_miles: float,
    total_miles: float,
    locate: Optional[Callable[[float], str]],
) -> str:
    """Readable location of the driver at global clock `hour`.

    Returns the literal named input only when the driver's calculated position
    truly is that location (trip start, pickup arrival, dropoff arrival);
    otherwise reverse-geocodes the interpolated mile along the route.
    """
    mile = elapsed_distance_at_hour(events, hour)
    eps = 0.5  # miles tolerance for "exactly at" a named location
    if mile <= eps:
        return current_name
    if abs(mile - leg1_miles) <= eps:
        return pickup_name
    if mile >= total_miles - eps:
        return dropoff_name
    if locate is not None:
        try:
            return locate(mile)
        except Exception:
            pass
    return current_name


def build_daily_logs(
    events: List[Event],
    *,
    current_name: str,
    pickup_name: str,
    dropoff_name: str,
    leg1_miles: float,
    total_miles: float,
    locate: Optional[Callable[[float], str]] = None,
) -> List[dict]:
    """Split global events into 24-hour day buckets with per-day status totals."""
    if not events:
        return []
    total_span = events[-1].end
    num_days = int(total_span // 24) + (1 if total_span % 24 > 0 else 0)
    num_days = max(num_days, 1)

    def position(hour: float) -> str:
        return get_position_at_hour(
            events, hour,
            current_name=current_name,
            pickup_name=pickup_name,
            dropoff_name=dropoff_name,
            leg1_miles=leg1_miles,
            total_miles=total_miles,
            locate=locate,
        )

    days: List[dict] = []
    for d in range(num_days):
        day_start = d * 24.0
        day_end = day_start + 24.0
        segments = []
        for ev in events:
            if ev.end <= day_start or ev.start >= day_end:
                continue
            s = max(ev.start, day_start) - day_start
            e = min(ev.end, day_end) - day_start
            if e - s <= 0:
                continue
            segments.append({
                "status": ev.status,
                "start_hour": round(s, 3),
                "end_hour": round(e, 3),
                "location": ev.location,
                "remark": ev.remark,
            })

        totals = {OFF: 0.0, SB: 0.0, DRIVING: 0.0, ON: 0.0}
        for seg in segments:
            totals[seg["status"]] += seg["end_hour"] - seg["start_hour"]

        # Any uncovered time at the start/end of the day counts as off duty.
        covered = sum(totals.values())
        if covered < 24.0:
            totals[OFF] += 24.0 - covered

        driving_segs = [s for s in segments if s["status"] == DRIVING]
        miles = round(
            sum((s["end_hour"] - s["start_hour"]) * AVG_SPEED for s in driving_segs)
        )

        # From/To reflect the driver's actual interpolated position at the day's
        # start and end (clamped to trip end), not the nearest stop event.
        from_loc = position(day_start)
        to_loc = position(min(day_end, total_span))

        days.append({
            "day": d + 1,
            "from_location": from_loc,
            "to_location": to_loc,
            "total_miles": miles,
            "segments": segments,
            "totals": {k: round(v, 2) for k, v in totals.items()},
        })
    return days
