# Realtime voice with private function tools

Use this reference when live speech must retrieve current company data.

## Session design

- Register only the read-only tools needed for voice and set tool choice to automatic.
- Instruct the voice model to call tools for current equipment values, history, and CCP facts; require units and KST timestamps.
- Do not rely on a startup context snapshot for live values.

## Browser and server responsibilities

The browser handles the Realtime WebRTC data channel but never receives the private data-platform key.

1. Listen for the completed function-call arguments event.
2. Send the validated tool name and arguments to a same-origin FastAPI endpoint protected by the same AI access gate.
3. Execute the tool on the server and return a JSON string.
4. Send a `function_call_output` conversation item with the original call ID over the data channel.
5. Send `response.create` so the voice model speaks from the returned data.

Deduplicate call IDs, ignore late results after session teardown, and return tool failures as structured output so the model can explain the failure. Test the server tool endpoint with a real read-only call; microphone and spoken end-to-end behavior still require browser verification.
