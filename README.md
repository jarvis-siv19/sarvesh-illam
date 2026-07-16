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
| `dashboard.html` | Self-contained 8-tile dashboard. Open as a `file://` URL. |
| `run.sh` | Loads `.env`, starts go2rtc. |
| `.env.example` | Template for `.env`. |
| `cctv.m3u` | Jellyfin Live TV playlist (optional). |

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

Open `dashboard.html` in a browser. go2rtc's own UI is at http://localhost:1984.

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

## Status

Both DVRs live, 8 cameras in the dashboard.

Planned: OpenCV analytics over the sub-streams, Home Assistant integration, and
a launchd agent to keep go2rtc up across reboots.
