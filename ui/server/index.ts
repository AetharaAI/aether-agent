import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = parseInt(process.env.PORT || "3000", 10);

// Serve static files from the dist/public directory
const publicDir = path.join(__dirname, "..", "dist");
app.use(express.static(publicDir));

// For client-side routing (SPA), return index.html for all non-file routes
app.get("*", (_req, res) => {
  res.sendFile(path.join(publicDir, "index.html"));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Aether UI server running on port ${PORT}`);
});
