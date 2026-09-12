const $ = (id) => document.getElementById(id);
const cellKey = (x, y) => `${x},${y}`;
let lastMap;

function setConnection(connected) {
  document.body.classList.toggle("connected", connected);
  $("connection-text").textContent = connected ? "LIVE TELEMETRY" : "RECONNECTING";
}

function renderMap(data) {
  const map = data.map;
  if (!lastMap || lastMap.width !== map.width || lastMap.height !== map.height) {
    $("map").style.gridTemplateColumns = `repeat(${map.width}, minmax(20px, 1fr))`;
    lastMap = map;
  }
  const blocked = new Set(map.static_blocked.map(([x, y]) => cellKey(x, y)));
  const dynamic = new Set(map.dynamic_blocked.map(([x, y]) => cellKey(x, y)));
  const charge = new Set(map.charging.map(([x, y]) => cellKey(x, y)));
  const intersections = new Set(map.intersections.map(([x, y]) => cellKey(x, y)));
  const taskCells = new Set(data.tasks.flatMap((task) => [task.pickup, task.dropoff]).map(([x, y]) => cellKey(x, y)));
  const robots = new Map(data.robots.map((robot) => [cellKey(...robot.position), robot]));
  const html = [];
  for (let y = 0; y < map.height; y++) for (let x = 0; x < map.width; x++) {
    const key = cellKey(x, y);
    const classes = ["cell"];
    if (blocked.has(key)) classes.push("blocked");
    if (dynamic.has(key)) classes.push("dynamic");
    if (charge.has(key)) classes.push("charge");
    if (intersections.has(key)) classes.push("intersection");
    if (taskCells.has(key)) classes.push("task");
    const robot = robots.get(key);
    html.push(`<div class="${classes.join(" ")}">${robot ? `<span class="robot-marker ${robot.status.toLowerCase()}" title="${robot.id} • ${robot.status}">${robot.id.replace("R","")}</span>` : ""}</div>`);
  }
  $("map").innerHTML = html.join("");
  $("map-size").textContent = `${map.width} × ${map.height}`;
}

function renderRobots(robots) {
  $("online").textContent = robots.length;
  $("online-detail").textContent = robots.length ? `${robots.filter((r) => r.status !== "OFFLINE").length} operational` : "waiting for telemetry";
  $("robot-count").textContent = `${robots.length} unit${robots.length === 1 ? "" : "s"}`;
  $("robot-list").innerHTML = robots.length ? robots.map((robot) => {
    const batteryClass = robot.battery < 20 ? "low" : "";
    return `<div class="robot-row"><div class="robot-main"><strong class="robot-id">${robot.id}</strong><span class="status ${robot.status.toLowerCase()}">${robot.status}</span></div><div class="battery ${batteryClass}">${robot.battery}%${robot.task ? ` · ${robot.task}` : ""}</div></div>`;
  }).join("") : '<div class="empty">No robot telemetry received yet.</div>';
  const avg = robots.length ? robots.reduce((sum, robot) => sum + robot.battery, 0) / robots.length : null;
  $("battery").textContent = avg === null ? "—" : `${Math.round(avg)}%`;
}

function renderTasks(tasks) {
  const active = tasks.filter((task) => task.status === "assigned").length;
  $("active-tasks").textContent = active;
  $("task-detail").textContent = `${tasks.filter((task) => task.status === "queued").length} queued`;
  $("task-list").innerHTML = tasks.length ? tasks.map((task) => `<div class="task-row"><div><div class="task-title">${task.id}</div><div class="task-meta">${task.pickup.join(", ")} → ${task.dropoff.join(", ")}</div></div><div class="task-state">${task.robot || "QUEUED"}</div></div>`).join("") : '<div class="empty">No tasks in this scenario.</div>';
}

function renderEvents(events) {
  $("event-list").innerHTML = events.length ? events.map((event) => `<div class="event-row"><div><div class="event-kind">${event.type.replaceAll("_", " ").toUpperCase()}</div><div class="event-meta">at tick ${event.at_tick}</div></div><div class="task-meta">${event.robot_id || event.aisle_id || ""}</div></div>`).join("") : '<div class="empty">No events have fired.</div>';
}

function render(data) {
  $("scenario").textContent = `${data.scenario} · live operational view`;
  $("tick").textContent = data.tick;
  renderMap(data); renderRobots(data.robots); renderTasks(data.tasks); renderEvents(data.events);
}

function connect() {
  const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket.onopen = () => setConnection(true);
  socket.onmessage = (event) => render(JSON.parse(event.data));
  socket.onclose = () => { setConnection(false); setTimeout(connect, 1500); };
  socket.onerror = () => socket.close();
}
connect();
