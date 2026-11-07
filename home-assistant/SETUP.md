# Run Home Assistant for Sarvesh Illam

Start the local automation server from the repository root:

```sh
./stack.sh start homeassistant
./stack.sh logs homeassistant
```

Open `http://<MAC_LAN_IP>:8123` and complete the first-user setup. This web page
is only the administration surface; day-to-day control is through Sarvesh
Illam at port 1984.

## Connect the Philips bulb

1. Pair the bulb to the 2.4 GHz home Wi-Fi using the WiZ app. This one-time
   step is required to provision Wi-Fi credentials to the bulb.
2. In WiZ settings, enable **Allow local communication**.
3. In Home Assistant, open **Settings → Devices & services → Add integration**,
   select **WiZ**, and add/discover the bulb. On Docker Desktop for Mac,
   automatic multicast discovery can be unreliable; use the bulb's LAN IP for
   manual setup if it is not discovered.
4. Copy the entity ID shown by Home Assistant, usually similar to
   `light.philips_smart_bulb`.

## Connect the Wipro plug

1. Pair it to 2.4 GHz Wi-Fi using **Wipro Next Smart Home**. This is likewise
   a one-time device-provisioning step.
2. In Home Assistant, add the **Tuya** integration. If the Wipro account cannot
   be linked, stop here and record the exact plug model and app/device-info
   screen: Wipro models are not uniform and the correct integration depends on
   the model/backend.
3. Copy the resulting entity ID, normally similar to `switch.wipro_smart_plug`.

## Connect Home Assistant to the dashboard

1. In Home Assistant, click your user profile (bottom-left) → **Security** →
   **Long-lived access tokens** → **Create token**. Save it immediately.
2. In this repository's `.env`, set:

   ```env
   HOME_ASSISTANT_URL=http://127.0.0.1:8123
   HOME_ASSISTANT_TOKEN=the-token-you-created
   ```

3. Edit `alerts/config.yaml` and replace the two placeholder `entity_id`
   values with the actual Philips and Wipro IDs.
4. Start/restart the local bridge:

   ```sh
   ./stack.sh restart home
   ```

5. Refresh Sarvesh Illam and select **Home**. Device state and controls will
   appear once the bridge can reach Home Assistant. WiZ lights expose power,
   brightness, colour temperature, RGB colour, and available effects.

## Music-reactive WiZ lighting

The dashboard can make the configured WiZ light react to nearby music using a
browser microphone. On the Home tab, select **Start music reactive** and allow
microphone access. It does not use Spotify credentials or send audio off the
LAN.

One dashboard/app at a time owns the microphone source. Other clients can take
over or stop it; an inactive source is released automatically after 12 seconds.
Change the target dashboard entity in `alerts/config.yaml`:

```yaml
music_reactive:
  light_id: philips_bulb
  source_timeout: 12
```

Home Assistant is optional. Stop it with `./stack.sh stop homeassistant`; local
Smarteefi control continues through the independent `home` service.
