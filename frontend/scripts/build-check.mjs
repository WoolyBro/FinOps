/**
 * Type-check and build without touching the dev server's .next.
 *
 * Use this for verification while `npm run dev` is running. `npm run build`
 * writes to .next and will break a live dev server.
 */
import { spawnSync } from "node:child_process";

const result = spawnSync("npx", ["next", "build"], {
  stdio: "inherit",
  shell: true,
  env: { ...process.env, NEXT_DIST_DIR: ".next-verify" },
});

process.exit(result.status ?? 1);
