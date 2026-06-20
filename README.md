# TruckLogix

Trip planner + ELD log generator for truckers. You give it a current location, pickup, dropoff, and how many cycle hours you've already burned through, and it spits out a route map plus daily log sheets that actually follow the FMCSA Hours of Service rules instead of just faking it.

Built this for a full-stack assessment. Sounded simple when I read the brief — four inputs, two outputs — but the HOS math ended up being way more involved than I expected. More on that below.

## Live

 **App:** [https://route-calculator-5896.vercel.app/?_vercel_share=zA7SRhjUxzMFXSlMa8ppIm2fnh4FZsl6]
- **API:** [https://dashboard.render.com/web/srv-d8qiu0ok1i2s7383gkv0]
Easiest way to see it working: punch in Chicago as current location, Memphis as pickup, Jacksonville as dropoff, and set cycle hours used to something like 30. You'll get a multi-day trip with a fuel stop and at least one mandatory rest period.

## How it works

Four inputs:
- Current location
- Pickup location
- Dropoff location
- Cycle hours already used (out of the 70hr/8-day limit)

What you get back:
- A map of the actual driving route (not a straight line between points — it follows real roads), with markers for the start, pickup, dropoff, fuel stops, and rest stops
- A summary card with total miles, trip duration, driving days, stop counts
- A daily log sheet for every day of the trip, drawn out like the real paper FMCSA form — the 24-hour grid, the four duty status rows, the works

## The HOS rules, since that's the part that actually has to be correct

- 11 hours of driving max per shift
- 14-hour on-duty window — once that's up, you're done driving even if you haven't hit the 11hr cap yet
- 10 hours off duty required before starting a new shift
- 30-min break required after 8 cumulative hours driving
- 70hr/8-day cycle — if a driver runs out of cycle hours mid-route, the app forces a 34-hour restart before letting them keep going
- A fuel stop every 1,000 miles
- 1 hour each for pickup and dropoff (on-duty, not driving)

This all gets simulated hour by hour on the backend instead of estimated after the fact, which matters more than it sounds — I had a bug for a while where the cycle-hour check only ran *after* a full driving block instead of during it, so a driver with like 7 hours left in their cycle could still get assigned an 8-hour driving block before the restart kicked in. Took a minute to catch since the totals still added up to 24 hours per day, just... incorrectly.

Also ran into a fun one with geocoding — typing "Washington" with no state attached is genuinely ambiguous (DC? state? random town in another state?), so a few city names needed better handling before the routing would behave.

## Stack

- Backend: Django + DRF
- Frontend: React + Vite
- Map: Leaflet, OpenStreetMap tiles
- Routing/geocoding: OpenRouteService (free tier, you'll need your own key)
- Hosting: frontend on Vercel, backend on Render

## Repo layout

```
backend/
├── manage.py
├── requirements.txt
├── trips/
│   ├── hos.py          # the actual HOS simulation — the core of the app
│   ├── ors.py            # OpenRouteService calls: geocode, route, reverse-geocode
│   ├── views.py
│   ├── serializers.py
│   └── tests.py
└── trucklogix/
    ├── settings.py
    └── urls.py

frontend/
└── src/
    ├── App.jsx
    ├── api.js
    └── components/
        ├── TripForm.jsx
        ├── RouteMap.jsx
        ├── TripSummary.jsx
        └── ELDLogSheet.jsx
```

## Running it yourself

Backend:
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Grab a free API key from openrouteservice.org and put it in a `.env` in the backend folder — nothing geocodes without it.

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Set the API base URL to wherever your backend's actually running.

## API

```
POST /api/trip/calculate/
```

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Memphis, TN",
  "dropoff_location": "Jacksonville, FL",
  "cycle_hours_used": 30
}
```

Comes back with the route polyline, every stop along the way, and the daily logs broken down to the hour.

## Assumptions (straight from the brief)

- Property-carrying driver, 70hr/8-day cycle, no adverse driving conditions
- Fuel at least once every 1,000 miles
- 1 hour each for pickup and dropoff

## If I had more time

- PDF export for the logs instead of relying on the browser's print dialog
- Save a driver profile so you're not re-typing the same current location every time
- Handle team drivers / sleeper berth splits — right now it assumes one driver doing everything solo
