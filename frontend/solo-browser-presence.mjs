// Vite dev-server-only solo browser presence tracker.
// This plugin is inert during Host/Guest production builds and LAN play.
import {mkdirSync, writeFileSync} from "node:fs";
import {dirname, resolve} from "node:path";

// Vite bundles config modules into a temporary file, so import.meta.url can
// point at the temp config rather than the original source location.
const root = process.env.IBS_ROOT ? resolve(process.env.IBS_ROOT) : resolve(process.cwd(), "..");
const presencePath = resolve(root, "tmp", "runtime", "solo-presence.json");
const SESSION_PATTERN = /^[a-f0-9]{32}$/;
const CLIENT_PATTERN = /^[a-f0-9-]{20,80}$/i;

export default function soloBrowserPresence() {
  const session = process.env.IBS_SOLO_MONITOR_ID || "";
  if (!SESSION_PATTERN.test(session)) return {name: "ibs-solo-browser-presence-disabled"};

  const clients = new Map();
  const closedClients = new Set();
  let everSeen = false;
  const writeState = () => {
    mkdirSync(dirname(presencePath), {recursive: true});
    // The watchdog retries transient reads while this small file is written.
    writeFileSync(presencePath, JSON.stringify({
      session, seen: everSeen, active: clients.size, updatedAt: Date.now()
    }), "utf8");
  };

  return {
    name: "ibs-solo-browser-presence",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!req.url?.startsWith("/__ibs_solo_presence?")) return next();
        const url = new URL(req.url, "http://127.0.0.1:5173");
        const client = url.searchParams.get("client") || "";
        const requestedSession = url.searchParams.get("session") || "";
        if (req.method !== "POST" || requestedSession !== session || !CLIENT_PATTERN.test(client)) {
          res.statusCode = 403;
          res.end();
          return;
        }
        const now = Date.now();
        // Ignore stale clients after crashes: one active tab should not keep a
        // long-dead tab registered forever.
        for (const [id, last] of clients) {
          if (now - last > 130000) clients.delete(id);
        }
        if (url.searchParams.get("close") === "1") {
          clients.delete(client);
          closedClients.add(client);
        } else if (!closedClients.has(client)) {
          // A pending heartbeat may arrive AFTER the close beacon.
          everSeen = true;
          clients.set(client, now);
        }
        try { writeState(); res.statusCode = 204; }
        catch { res.statusCode = 500; }
        res.setHeader("Cache-Control", "no-store");
        res.end();
      });
    },
    transformIndexHtml() {
      // Inject only while Vite is serving the source, NOT into built game assets.
      // One random ID per browser tab; pagehide includes tab close / navigation.
      const js = `(() => {
        const client = (globalThis.crypto?.randomUUID?.() ||
          (Date.now().toString(16) + Math.random().toString(16).slice(2) + 'abcdefghijkl'));
        const endpoint = '/__ibs_solo_presence?session=${session}&client=' + encodeURIComponent(client);
        let leaving = false;
        const beat = () => {
          if (!leaving) fetch(endpoint, {method: 'POST', cache: 'no-store', keepalive: true}).catch(() => {});
        };
        beat();
        const interval = setInterval(beat, 3000);
        window.addEventListener('pagehide', () => {
          leaving = true;
          clearInterval(interval);
          if (!navigator.sendBeacon?.(endpoint + '&close=1', '')) {
            fetch(endpoint + '&close=1', {method: 'POST', keepalive: true}).catch(() => {});
          }
        });
      })();`;
      return [{tag: "script", children: js, injectTo: "body"}];
    }
  };
}
