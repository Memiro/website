// The storefront runs as PID 1 in its container, and the kernel drops signals with a
// default action from PID 1: without the handlers below SIGTERM does nothing and every
// deploy waits out the orchestrator's kill timeout. Autostart is switched off so that the
// server handle stays here, where the shutdown can close it.
process.env.ASTRO_NODE_AUTOSTART = "disabled";

// A page being rendered is worth waiting for, an idle keep-alive connection is not.
const DRAIN_TIMEOUT_MS = 5000;

const { startServer } = await import("./dist/server/entry.mjs");
const { server } = startServer();

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.once(signal, () => {
    server.server.close(() => process.exit(0));
    setTimeout(() => {
      server.stop().then(() => process.exit(0), () => process.exit(1));
    }, DRAIN_TIMEOUT_MS).unref();
  });
}
