// Thin fetch wrappers. Same-origin (FastAPI serves both API and this app);
// every helper rejects on non-2xx so callers can't mistake failure for data.
async function req(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) {
    // Surface the server's own words. A refused pool build explains itself in
    // `detail` — the cost estimate, the spend cap, or which sources do not
    // cover the channel — and a bare status code would throw away exactly the
    // sentence the screen exists to show.
    let detail = "";
    try { detail = (await r.json()).detail || ""; } catch { /* not JSON */ }
    throw new Error(detail || `${opts.method || "GET"} ${path} -> ${r.status}`);
  }
  return r.json();
}

export const listStories = () => req("/api/stories");
export const storyDetail = (id) => req(`/api/stories/${id}`);
export const getProgress = (id) => req(`/api/progress/${id}`);
export const markEnded = (id) => req(`/api/stories/${id}/ended`, { method: "POST" });
export const markRead = (id) => req(`/api/stories/${id}/read`, { method: "POST" });
export const skipStory = (id) => req(`/api/stories/${id}/skip`, { method: "POST" });
export const unskipStory = (id) => req(`/api/stories/${id}/unskip`, { method: "POST" });
export const rate = (id, score) =>
  req(`/api/ratings/${id}`, { method: "PUT", body: JSON.stringify({ score }) });
export const clearRating = (id) => req(`/api/ratings/${id}`, { method: "DELETE" });
export const getTaste = () => req("/api/taste");
const tastePath = (kind, value) =>
  `/api/taste/${encodeURIComponent(kind)}/${encodeURIComponent(value)}`;
export const setTaste = (kind, value, score) =>
  req(tastePath(kind, value), { method: "PUT", body: JSON.stringify({ score }) });
export const suppressTaste = (kind, value) =>
  req(tastePath(kind, value),
      { method: "PUT", body: JSON.stringify({ suppress: true }) });
export const clearTaste = (kind, value) =>
  req(tastePath(kind, value), { method: "DELETE" });
export const getSettings = () => req("/api/settings");
export const putSettings = (body) =>
  req("/api/settings", { method: "PUT", body: JSON.stringify(body) });
export const addBookmark = (id, position_s, note) =>
  req(`/api/stories/${id}/bookmarks`, {
    method: "POST", body: JSON.stringify({ position_s, note }),
  });
export const deleteBookmark = (bid) =>
  req(`/api/bookmarks/${bid}`, { method: "DELETE" });
export const listVoices = () => req("/api/voices");
// channels (R12)
export const listChannels = () => req("/api/channels");
export const createChannel = (body) =>
  req("/api/channels", { method: "POST", body: JSON.stringify(body) });
export const updateChannel = (id, body) =>
  req(`/api/channels/${id}`, { method: "PUT", body: JSON.stringify(body) });
export const activateChannel = (id) =>
  req(`/api/channels/${id}/activate`, { method: "POST" });

// pool builds (Entry 43) — the "Grace-initiated" build of AMENDMENT_04 A,
// reachable from the phone instead of only a terminal.
export const listPoolJobs = () => req("/api/pool-jobs");
export const buildPool = (id, approve_spend = false) =>
  req(`/api/channels/${id}/build`,
      { method: "POST", body: JSON.stringify({ approve_spend }) });
export const cancelBuild = (id) =>
  req(`/api/channels/${id}/build/cancel`, { method: "POST" });

// render control (AMENDMENT_06)
export const listRenders = () => req("/api/renders");
export const pauseRender = (id) => req(`/api/renders/${id}/pause`, { method: "POST" });
export const resumeRender = (id) => req(`/api/renders/${id}/resume`, { method: "POST" });
export const cancelRender = (id) => req(`/api/renders/${id}/cancel`, { method: "POST" });
export const setVoice = (id, voice) =>
  req(`/api/stories/${id}/voice`, { method: "POST", body: JSON.stringify({ voice }) });

// Progress saves fire from pagehide/visibilitychange too — keepalive lets the
// request survive the page being backgrounded/killed (iOS rule 3).
export function saveProgress(id, position_s) {
  return fetch(`/api/progress/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ position_s }),
    keepalive: true,
  });
}
