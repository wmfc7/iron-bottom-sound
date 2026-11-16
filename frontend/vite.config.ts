import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";
import soloBrowserPresence from "./solo-browser-presence.mjs";
export default defineConfig({plugins:[react(),soloBrowserPresence()],server:{port:5173,proxy:{"/api":{target:"http://127.0.0.1:8000",rewrite:p=>p.replace(/^\/api/,"")},"/assets":{target:"http://127.0.0.1:8000"}}}});
