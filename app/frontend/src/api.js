// Thin fetch wrappers. Same-origin (FastAPI serves both API and this app);
// every helper rejects on non-2xx so callers can't mistake failure for data.
async function req(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`${opts.method || "GET"} ${path} -> ${r.status}`);
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
export const addBookmark = (id, position_s, note) =>
  req(`/api/stories/${id}/bookmarks`, {
    method: "POST", body: JSON.stringify({ position_s, note }),
  });
export const deleteBookmark = (bid) =>
  req(`/api/bookmarks/${bid}`, { method: "DELETE" });
export const listVoices = () => req("/api/voices");
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
