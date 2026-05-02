import { useEffect, useRef, useState } from "react";

/**
 * Smooths the chat “typing” line: even if the server sends large SSE chunks, the UI
 * advances a few characters at a time toward the latest buffer.
 */
export function useRevealedStreamText(target: string, streaming: boolean): string {
  const [display, setDisplay] = useState("");
  const targetRef = useRef(target);

  useEffect(() => {
    targetRef.current = target;
  }, [target]);

  useEffect(() => {
    if (target === "") {
      setDisplay("");
    }
  }, [target]);

  useEffect(() => {
    // Render the latest streamed text immediately (no artificial batching delay).
    if (streaming) {
      setDisplay(targetRef.current);
      return;
    }
    setDisplay(targetRef.current);
  }, [streaming, target]);

  return display;
}
