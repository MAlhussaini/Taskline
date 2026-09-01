import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../", import.meta.url);
const staticRoot = new URL("../static/", import.meta.url);

function pngDimensions(buffer) {
  assert.equal(buffer.subarray(1, 4).toString(), "PNG");
  return [buffer.readUInt32BE(16), buffer.readUInt32BE(20)];
}

test("provides an installable mobile manifest and valid icons", async () => {
  const manifest = JSON.parse(await readFile(new URL("manifest.webmanifest", staticRoot), "utf8"));

  assert.equal(manifest.name, "Taskline");
  assert.equal(manifest.start_url, "/");
  assert.equal(manifest.scope, "/");
  assert.equal(manifest.display, "standalone");
  assert.match(manifest.theme_color, /^#[0-9a-f]{6}$/i);
  assert.match(manifest.background_color, /^#[0-9a-f]{6}$/i);

  const expectedIcons = new Map([
    ["/icon-192.png", [192, 192]],
    ["/icon-512.png", [512, 512]],
    ["/icon-maskable-512.png", [512, 512]],
  ]);
  assert.deepEqual(new Set(manifest.icons.map(icon => icon.src)), new Set(expectedIcons.keys()));
  assert.equal(manifest.icons.find(icon => icon.src === "/icon-maskable-512.png").purpose, "maskable");

  for (const [src, dimensions] of expectedIcons) {
    const icon = await readFile(new URL(`static${src}`, projectRoot));
    assert.deepEqual(pngDimensions(icon), dimensions);
  }
});

test("connects the page, install experience, and offline shell", async () => {
  const [html, app, worker] = await Promise.all([
    readFile(new URL("index.html", staticRoot), "utf8"),
    readFile(new URL("app.js", staticRoot), "utf8"),
    readFile(new URL("service-worker.js", staticRoot), "utf8"),
  ]);

  assert.match(html, /<link rel="manifest" href="\/manifest\.webmanifest">/);
  assert.match(html, /name="theme-color" content="#28553f"/);
  assert.match(html, /name="apple-mobile-web-app-capable" content="yes"/);
  assert.match(html, /id="install-app"/);
  assert.match(app, /serviceWorker\.register\('\/service-worker\.js', \{ scope: '\/' \}\)/);
  assert.match(app, /beforeinstallprompt/);
  assert.match(app, /appinstalled/);

  for (const asset of ["/", "/styles.css?v=9", "/app.js?v=9", "/manifest.webmanifest", "/icon-maskable-512.png"]) {
    assert.ok(worker.includes(`'${asset}'`), `${asset} is missing from the offline shell`);
  }
  assert.match(worker, /url\.pathname\.startsWith\('\/api\/'\)/);
  assert.match(worker, /url\.pathname\.startsWith\('\/uploads\/'\)/);
});
