#!/usr/bin/env node
// turk-hukuku-ictihat-mcp: Python tabanlı MCP sunucusunu uvx ile başlatan ince sarmalayıcı.
// Sunucunun kendisi PyPI'daki turk-hukuku-ictihat-mcp paketidir; bu paket yalnızca npx ergonomisi sağlar.
const { spawnSync } = require("node:child_process");

const r = spawnSync(
  "uvx",
  ["--from", "turk-hukuku-ictihat-mcp==0.4.0", "turk-hukuku-ictihat"],
  { stdio: "inherit" }
);

if (r.error && r.error.code === "ENOENT") {
  console.error("Hata: 'uv' bulunamadi. Bu sunucu Python tabanlidir ve uvx ile calisir.");
  console.error("uv kurulumu: https://docs.astral.sh/uv/getting-started/installation/");
  console.error("Alternatif: pip install turk-hukuku-ictihat-mcp && turk-hukuku-ictihat");
  process.exit(1);
}
process.exit(r.status === null ? 1 : r.status);
