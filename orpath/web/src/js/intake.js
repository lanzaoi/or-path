/* ==========================================================================
   Shared Intake Import Client (/api/intake/import)
   ========================================================================== */

async function orpathIntakeImport(payload, signal) {
  const fetchOpts = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  };
  if (signal) fetchOpts.signal = signal;
  const response = await fetch("/api/intake/import", fetchOpts);
  const data = await response.json();
  return { ok: response.ok, status: response.status, data };
}
