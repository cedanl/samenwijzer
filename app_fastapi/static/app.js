// Samenwijzer gedeelde frontend-helpers.

// Stream een SSE-antwoord van een POST-endpoint (fetch + ReadableStream).
// Events zijn regels "data: {json}\n\n" met {chunk} | {done} | {error}.
async function swStream(url, body, { onChunk, onDone, onError }) {
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok || !resp.body) throw new Error("stream mislukt");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();
      for (const ev of events) {
        if (!ev.startsWith("data: ")) continue;
        const data = JSON.parse(ev.slice(6));
        if (data.chunk) onChunk?.(data.chunk);
        if (data.done) onDone?.(data);
        if (data.error) onError?.(data.error);
      }
    }
  } catch (err) {
    onError?.(String(err));
  }
}

// Kleine helper: element maken met class + tekst.
function swEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text != null) el.textContent = text;
  return el;
}
