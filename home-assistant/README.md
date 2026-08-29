# Sarvesh Illam automations

1. Connect the Philips bulb and Wipro plug in Home Assistant and copy their
   entity IDs into `alerts/config.yaml`.
2. Copy `automations.yaml` into Home Assistant's automations configuration, or
   recreate it in the visual automation editor.
3. Replace `cam1` and `light.philips_bulb` with the real entrance camera and
   light.
4. Test the light action manually, then set
   `home_assistant.publish_camera_events: true` in `alerts/config.yaml` and
   restart the alerts service.

The included automation is intentionally limited to a light and is active only
at night. Keep smart plugs manual or scheduled unless the connected appliance
is known to be safe for unattended operation.
