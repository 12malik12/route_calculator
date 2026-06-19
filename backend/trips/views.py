from dataclasses import asdict

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import ors
from .hos import simulate
from .serializers import TripRequestSerializer


def _format_clock(hours: float) -> str:
    """Convert global trip hours into a 'Day N HH:MM' label."""
    day = int(hours // 24) + 1
    rem = hours % 24
    h = int(rem)
    m = int(round((rem - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"Day {day} {h:02d}:{m:02d}"


@api_view(["POST"])
def calculate_trip(request):
    serializer = TripRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    current_name = data["current_location"]
    pickup_name = data["pickup_location"]
    dropoff_name = data["dropoff_location"]
    cycle_hours_used = data["cycle_hours_used"]

    # 1. Geocode all three addresses, reporting which field failed.
    coords = {}
    field_errors = {}
    for field, label, name in (
        ("current_location", "Current location", current_name),
        ("pickup_location", "Pickup location", pickup_name),
        ("dropoff_location", "Dropoff location", dropoff_name),
    ):
        try:
            coords[field] = ors.geocode(name)
        except ors.GeocodeError as exc:
            field_errors[field] = str(exc)

    if field_errors:
        first = next(iter(field_errors.values()))
        return Response(
            {"detail": first, "field_errors": field_errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cur = coords["current_location"]
    pick = coords["pickup_location"]
    drop = coords["dropoff_location"]

    # 2. Get road distances + full polyline.
    route = ors.directions([cur, pick, drop])
    legs = route["legs_miles"]
    leg1 = legs[0] if len(legs) > 0 else 0.0
    leg2 = legs[1] if len(legs) > 1 else 0.0
    geometry = route["geometry"]

    # Resolve a readable place name for where a mid-route stop happens, so
    # fuel/rest stops report a real city/state instead of raw coordinates or
    # the city being driven toward. Results are cached per rounded coordinate
    # to avoid redundant reverse-geocode calls for nearby stops.
    _name_cache: dict = {}

    def locate(mile: float) -> str:
        lon, lat = ors.point_at_mile(geometry, mile)  # [lon, lat]
        key = (round(lon, 2), round(lat, 2))
        if key not in _name_cache:
            _name_cache[key] = ors.reverse_geocode(lon, lat)
        return _name_cache[key]

    # 3. Simulate the trip under HOS rules.
    result = simulate(
        leg1_miles=leg1,
        leg2_miles=leg2,
        cycle_hours_used=cycle_hours_used,
        current_name=current_name,
        pickup_name=pickup_name,
        dropoff_name=dropoff_name,
        locate=locate,
    )

    # 4. Attach coordinates to each stop by interpolating along the polyline.
    fixed_coords = {
        "current": [cur[0], cur[1]],
        "pickup": [pick[0], pick[1]],
        "dropoff": [drop[0], drop[1]],
    }
    stops_out = []
    for stop in result["stops"]:
        s = asdict(stop)
        if stop.type in fixed_coords:
            coord = fixed_coords[stop.type]
        else:
            coord = ors.point_at_mile(geometry, stop.mile)
        stops_out.append({
            "type": s["type"],
            "label": s["label"],
            "lat": coord[1],
            "lng": coord[0],
            "arrival": _format_clock(s["arrival"]),
            "departure": _format_clock(s["departure"]),
            "duration_hours": round(s["departure"] - s["arrival"], 2),
        })

    # Convert polyline to [lat, lng] for Leaflet.
    polyline = [[c[1], c[0]] for c in geometry]

    total_miles = round(route["total_miles"])
    total_hours = result["total_hours"]

    return Response({
        "total_distance_miles": total_miles,
        "total_duration_hours": round(total_hours, 2),
        "total_duration_label": _duration_label(total_hours),
        "num_days": result["num_days"],
        "fuel_stops": sum(1 for s in result["stops"] if s.type == "fuel"),
        "rest_stops": sum(1 for s in result["stops"] if s.type in ("rest", "restart")),
        "cycle_hours_used": cycle_hours_used,
        "cycle_hours_remaining": round(70 - cycle_hours_used, 2),
        "stops": stops_out,
        "polyline": polyline,
        "daily_logs": result["daily_logs"],
    })


def _duration_label(hours: float) -> str:
    days = int(hours // 24)
    rem = hours - days * 24
    h = int(rem)
    m = int(round((rem - h) * 60))
    parts = []
    if days:
        parts.append(f"{days}d")
    parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    return " ".join(parts)
