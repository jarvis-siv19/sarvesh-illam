# CCTV

A local dashboard for two CP Plus DVRs (Dahua OEM), 4 cameras each. Pulls RTSP
off the DVRs with [go2rtc](https://github.com/AlexxIT/go2rtc) and restreams to
the browser over WebRTC/MSE — no cloud, no vendor app.

The stock mobile app (gCMOB) only reaches the cameras through a proprietary P2P
relay, which is unusable for desktop viewing or automation. Local RTSP is the
way in.

## Layout

| File | Purpose |
| --- | --- |
| `go2rtc.yaml` | Stream definitions. Credentials come from the environment. |
| `www/` | Dashboard, served by go2rtc itself at `http://<LAN_IP>:1984/`. |
| `run.sh` | Loads `.env`, starts go2rtc. |
| `.env.example` | Template for `.env`. |
| `cctv.m3u` | Jellyfin Live TV playlist (optional). |

`www/video-stream.js` and `www/video-rtc.js` are vendored from go2rtc v1.9.14 —
setting `api.static_dir` replaces go2rtc's embedded web assets, so the player
component must be shipped alongside the dashboard. If you upgrade the go2rtc
binary, re-vendor both files from the matching tag.

## Setup

Download the go2rtc binary for your platform from the
[releases page](https://github.com/AlexxIT/go2rtc/releases) into this directory
and make it executable:

```sh
chmod +x go2rtc
```

Create a dedicated stream user on each DVR (Main Menu → Account) — don't reuse
the admin login. Both DVRs are assumed to share the same username/password.
Avoid special characters in the password, or they must be URL-encoded in the
RTSP URL.

Then configure and run:

```sh
cp .env.example .env   # fill in credentials and DVR addresses
./run.sh
```

Open `http://<LAN_IP>:1984/` from any device on the LAN — desktop, phone, or TV
browser. Phones get a scrollable column layout with swipe navigation in the
focus view, and "Add to Home Screen" installs it as a full-screen app. The page
also still works opened directly as a `file://` on the host machine.

Give the host machine a fixed address (DHCP reservation on the router, or a
manual IP) — it's baked into `LAN_IP` and into every device's bookmark.

## How it works

go2rtc pulls each camera from the DVR **once** and fans it out to every viewer,
so ten browser tabs still cost the DVR a single RTSP connection. It relays H.264
packets without transcoding, so the host machine does almost no work — it's
copying bytes, not re-encoding.

Each camera exposes two streams:

- **main** (`camN`) — 1280×720, used for the single-camera focus view
- **sub** (`camN_sub`) — 352×288, used for the multiview grid

### The DVR is the bottleneck, not the host

A DVR is a cheap embedded box whose real job is recording 4 channels to disk
24/7; serving live RTSP is a side gig it does with leftover CPU and NIC headroom,
and its firmware caps concurrent sessions. Four simultaneous **main** streams
from one DVR causes `i/o timeout` drops.

So the grid uses sub-streams and only the focus view upgrades to main. This limit
is **per-DVR** — each unit has its own CPU, NIC, and session cap, so a second DVR
adds capacity rather than competing for it. All 8 sub-streams (4 per DVR) run
concurrently without drops. The rule in practice: don't open several HD focus
views against the *same* DVR at once.

## Networking notes

Pin each DVR's address static **on the DVR itself** (Main Menu → Network →
TCP/IP). A router DHCP reservation is unreliable here: these units present a
**different MAC address on each reboot**, so the reservation won't match.

When hunting for a DVR on the network:

```sh
nmap -p 554,80,8000,37777 --open -n -T4 192.168.0.0/24
```

Identify each hit with an unauthenticated RTSP `OPTIONS` — the 401 response
names the exact unit in its auth realm, which is the only reliable way to tell
two DVRs apart (a single DVR can answer on more than one IP if it's holding a
stale DHCP lease alongside its static address):

```sh
printf 'OPTIONS rtsp://HOST:554/ RTSP/1.0\r\nCSeq: 1\r\n\r\n' | nc -w 4 HOST 554
# RTSP/1.0 401 Unauthorized
# WWW-Authenticate: Digest realm="Login to <SERIAL>", ...
```

RTSP URLs follow the Dahua scheme and require **Digest** auth:

```
rtsp://<user>:<pass>@<host>:554/cam/realmonitor?channel=<N>&subtype=<0|1>
```

## Security

`.env` is gitignored and holds the only copy of the credentials. `go2rtc.yaml`
references them as `${VAR}`, which go2rtc expands from the environment at
startup — and values sourced this way are masked as `***` in its HTTP API.

`api.origin: "*"` in `go2rtc.yaml` is required for the `file://` dashboard to
embed feeds cross-origin. It makes the API accessible from any page you visit
while go2rtc is running, which is an acceptable trade on a trusted LAN — but
don't expose port 1984 to the internet.

## Alerts service

`alerts/` is a Python service (managed with [uv](https://docs.astral.sh/uv/))
that watches every camera through go2rtc's local RTSP server — the DVRs see no
extra connections — and pushes alerts to Telegram plus an event feed the
dashboard shows in its bell menu.

```sh
cd alerts && ./run.sh     # http://localhost:8090/api/events
```

What it detects today:

- **Camera down** — no frames for 30 s (with recovery notice)
- **Image black / camera covered** — brightness or sharpness collapsing
  against that camera's *own* per-mode baseline. Absolute thresholds don't
  work here: a camera whose IR floods the scene sits at luma ~130 at night
  while one facing an unlit yard legitimately sits at ~2, so "dark" is only
  meaningful relative to what each camera normally sees.
- **Day/night (IR) tracking** — each camera's IR switch is detected from
  frame saturation (with hysteresis and a grace window), thresholds adapt,
  and the dashboard shows a 🌙 on night-mode tiles.

### Telegram setup

1. Message **@BotFather** on Telegram → `/newbot` → copy the token.
2. Message your new bot once (anything), then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy
   `message.chat.id` from the response.
3. Add both to `.env`:

```sh
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

Without these the service still runs — events just stay local (log + dashboard).

## Status

Both DVRs live, 8 cameras on the LAN dashboard, camera-health alerts running.

Planned: person detection on all cameras, no-helmet rider alert on the parking
feed, Home Assistant integration, launchd agents for go2rtc + alerts.
