/* Sarvesh Illam home controls. Home Assistant credentials stay server-side. */
(() => {
  // HOST is the go2rtc address selected by the dashboard (including in the
  // Android shell), while the companion alerts/Home API runs on port 8090.
  const apiUrl = new URL(HOST);
  apiUrl.port = "8090";
  apiUrl.pathname = "";
  const API = apiUrl.origin;
  const view = document.getElementById("homeView");
  let config = null;

  const esc = value => String(value).replace(/[&<>'"]/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"})[c]);
  function renderNotice(title, text){
    view.innerHTML = `<div class="home-empty"><div class="home-empty-icon">⌂</div><h2>${esc(title)}</h2><p>${esc(text)}</p></div>`;
  }
  function stateLabel(device){
    if (device.type === "sensor") {
      const unit = device.attributes?.unit_of_measurement || "";
      return `${device.state} ${unit}`.trim();
    }
    if (device.state === "unavailable" || device.state === "unknown") return "Offline";
    if (device.state === "on") {
      const watts = device.attributes?.power;
      return watts == null ? "On" : `On · ${Number(watts).toFixed(1)} W`;
    }
    return "Off";
  }
  function render(states){
    const rooms = new Map();
    for (const device of states) rooms.set(device.room, [...(rooms.get(device.room) || []), device]);
    view.innerHTML = `<div class="home-head"><div><h1>Home</h1><p>Control your connected devices locally.</p></div><button class="home-refresh" id="homeRefresh">↻ Refresh</button></div>` +
      [...rooms].map(([room, devices]) => `<section class="room"><h2>${esc(room)}</h2><div class="device-grid">${devices.map(card).join("")}</div></section>`).join("");
    document.getElementById("homeRefresh").onclick = load;
    view.querySelectorAll("[data-command]").forEach(button => button.onclick = () => command(button));
    view.querySelectorAll("input[data-brightness]").forEach(input => input.onchange = () =>
      command(input, "set", {brightness_pct: Number(input.value)}));
  }
  function card(device){
    const online = !["unavailable", "unknown"].includes(device.state);
    const on = device.state === "on";
    const controllable = device.type !== "sensor" && !device.read_only;
    const brightness = Math.round((device.attributes?.brightness || 255) / 255 * 100);
    return `<article class="device-card ${on ? "is-on" : ""} ${online ? "" : "is-offline"}">
      <div class="device-top"><span class="device-icon">${esc(device.icon)}</span><span class="device-state">${esc(stateLabel(device))}</span></div>
      <h3>${esc(device.name)}</h3><p>${esc(device.read_only ? "State visible · control pending WiZ fix" : device.type === "light" ? "Smart light" : device.type === "sensor" ? "Live measurement" : "Smart plug")}</p>
      ${controllable ? `<div class="device-actions"><button class="device-toggle" data-command="${on ? "turn_off" : "turn_on"}" data-id="${esc(device.id)}" ${online ? "" : "disabled"}>${on ? "Turn off" : "Turn on"}</button></div>` : ""}
      ${device.type === "light" && controllable ? `<label class="brightness">Brightness <span>${brightness}%</span><input data-brightness data-id="${esc(device.id)}" type="range" min="1" max="100" value="${brightness}" ${online ? "" : "disabled"}></label>` : ""}
    </article>`;
  }
  async function command(control, action = control.dataset.command, data = {}){
    const id = control.dataset.id;
    if (!id) return;
    control.disabled = true;
    try {
      const r = await fetch(`${API}/api/home/entities/${encodeURIComponent(id)}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action, data})});
      if (!r.ok) throw new Error();
      setTimeout(load, 350);
    } catch (_) { alert("Device control failed. Check the Sarvesh Illam service and Home Assistant."); }
    finally { control.disabled = false; }
  }
  async function load(){
    try {
      const c = await fetch(`${API}/api/home/config`, {cache:"no-store"});
      config = await c.json();
      if (!config.configured) return renderNotice("Set up your home", "Add the Home Assistant entity IDs in alerts/config.yaml.");
      if (!config.enabled) return renderNotice("Home Assistant is not connected", "Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in .env, then restart the alerts service.");
      const r = await fetch(`${API}/api/home/states`, {cache:"no-store"});
      if (!r.ok) throw new Error();
      render(await r.json());
    } catch (_) { renderNotice("Home unavailable", "Sarvesh Illam could not reach Home Assistant."); }
  }
  window.SarveshHome = {load};
  load();
})();
