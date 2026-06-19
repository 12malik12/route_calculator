"""Unit tests for the HOS simulation engine (hos.py).

Covers two logic bugs:
  1. Cycle-hour limit must be enforced mid-driving-block, not only after it.
  2. Daily log From/To headers must reflect the driver's actual interpolated
     position, not stale input strings, on mid-drive day boundaries.
"""
from django.test import SimpleTestCase

from .hos import (
    CYCLE_LIMIT,
    DRIVING,
    ON,
    RESTART_DURATION,
    OFF,
    Event,
    elapsed_distance_at_hour,
    get_position_at_hour,
    simulate,
)


def _onduty_before_first_restart(events):
    """Max cumulative driving+on-duty hours reached before any 34h restart."""
    cumulative = 0.0
    peak = 0.0
    for ev in events:
        # A 34-hour OFF block is the restart marker; stop accumulating there.
        if ev.status == OFF and abs((ev.end - ev.start) - RESTART_DURATION) < 0.01:
            break
        if ev.status in (DRIVING, ON):
            cumulative += ev.end - ev.start
            peak = max(peak, cumulative)
    return peak


class CycleLimitTests(SimpleTestCase):
    def test_cycle_balance_never_exceeded_before_restart(self):
        # Long trip guarantees the cycle limit is reached mid-drive.
        for used in (1.0, 5.0, 7.0, 15.0, 40.0):
            result = simulate(
                leg1_miles=600.0,
                leg2_miles=2200.0,
                cycle_hours_used=used,
                current_name="Start",
                pickup_name="Pickup",
                dropoff_name="Dropoff",
            )
            remaining_balance = CYCLE_LIMIT - used
            peak = _onduty_before_first_restart(result["events"])
            self.assertLessEqual(
                peak,
                remaining_balance + 0.011,
                msg=f"cycle_hours_used={used}: on-duty {peak} exceeded "
                    f"balance {remaining_balance} before restart",
            )

    def test_restart_inserted_and_cycle_resets(self):
        result = simulate(
            leg1_miles=600.0,
            leg2_miles=2200.0,
            cycle_hours_used=63.0,  # only 7h of cycle left
            current_name="Start",
            pickup_name="Pickup",
            dropoff_name="Dropoff",
        )
        restarts = [
            ev for ev in result["events"]
            if ev.status == OFF and abs((ev.end - ev.start) - RESTART_DURATION) < 0.01
        ]
        self.assertTrue(restarts, "expected a 34-hour restart to be inserted")
        # On-duty hours before the first restart must not exceed the 7h balance.
        peak = _onduty_before_first_restart(result["events"])
        self.assertLessEqual(peak, 7.0 + 0.011)


class DailyHeaderPositionTests(SimpleTestCase):
    def _events(self):
        # 0-10h driving (550mi), crossing the 24h boundary would need more, so
        # build a synthetic multi-day drive: drive, rest, drive again.
        return [
            Event(DRIVING, 0.0, 11.0, "A", "Driving toward B"),    # 605 mi
            Event(OFF, 11.0, 21.0, "rest", "10-hour rest"),
            Event(DRIVING, 21.0, 32.0, "A", "Driving toward B"),   # +605 mi
        ]

    def test_elapsed_distance_interpolates_mid_segment(self):
        events = self._events()
        # At hour 26 we are 5h into the second driving block (21-32h).
        miles = elapsed_distance_at_hour(events, 26.0)
        # 11h * 55 (first block) + 5h * 55 (partial second) = 605 + 275 = 880
        self.assertAlmostEqual(miles, 880.0, places=3)

    def test_named_location_only_at_true_endpoints(self):
        events = self._events()
        total = 1210.0
        leg1 = 605.0

        # Hour 0 -> start name.
        self.assertEqual(
            get_position_at_hour(
                events, 0.0, current_name="START", pickup_name="PICK",
                dropoff_name="DROP", leg1_miles=leg1, total_miles=total,
                locate=lambda m: f"MID-{int(m)}",
            ),
            "START",
        )
        # Hour 11 -> exactly at leg1 distance -> pickup name.
        self.assertEqual(
            get_position_at_hour(
                events, 11.0, current_name="START", pickup_name="PICK",
                dropoff_name="DROP", leg1_miles=leg1, total_miles=total,
                locate=lambda m: f"MID-{int(m)}",
            ),
            "PICK",
        )
        # Mid-drive boundary (hour 26) -> reverse-geocoded, NOT a stale input.
        mid = get_position_at_hour(
            events, 26.0, current_name="START", pickup_name="PICK",
            dropoff_name="DROP", leg1_miles=leg1, total_miles=total,
            locate=lambda m: f"MID-{int(m)}",
        )
        self.assertTrue(mid.startswith("MID-"))
        self.assertNotIn(mid, {"START", "PICK", "DROP"})

    def test_daily_log_headers_not_stale_input(self):
        # Multi-day trip; interior day headers should not all be input strings.
        result = simulate(
            leg1_miles=600.0,
            leg2_miles=1800.0,
            cycle_hours_used=0.0,
            current_name="CITY_START",
            pickup_name="CITY_PICK",
            dropoff_name="CITY_DROP",
            locate=lambda m: f"EnRoute-{int(m)}",
        )
        logs = result["daily_logs"]
        self.assertGreater(len(logs), 1)
        # Day 1 starts at the true origin.
        self.assertEqual(logs[0]["from_location"], "CITY_START")
        # Final day ends at the true dropoff.
        self.assertEqual(logs[-1]["to_location"], "CITY_DROP")
        # At least one interior boundary uses a calculated EnRoute position.
        interior = [
            l["from_location"] for l in logs[1:]
        ] + [l["to_location"] for l in logs[:-1]]
        self.assertTrue(
            any(loc.startswith("EnRoute-") for loc in interior),
            msg=f"expected calculated positions in interior headers, got {interior}",
        )
