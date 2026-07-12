/**
 * Consume a `text/event-stream` response from the backend.
 *
 * Not using the browser's `EventSource` here on purpose: it can only issue
 * GET requests and can't send a JSON body, and cross-origin credentialed
 * requests are awkward with it. The backend's /chat and /report endpoints
 * are POST + need the workspace cookie, so we read the stream by hand via
 * `fetch` + `ReadableStream` and parse `data: {...}\n\n` frames ourselves.
 */
export async function consumeSSE<TEvent = unknown>(
  response: Response,
  onEvent: (event: TEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("Response has no body to stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line ("\n\n"). A frame may still
    // be incomplete at the end of `buffer` if it arrived split across two
    // chunks, so only split on the frames we're sure are complete.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const payload = line.slice("data: ".length);
      try {
        onEvent(JSON.parse(payload) as TEvent);
      } catch {
        // Malformed frame — skip rather than aborting the whole stream.
      }
    }
  }
}
