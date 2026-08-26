WebSocket usage (mobile scaffold)

This Flutter scaffold includes a simple WebSocket service implementation (lib/services/ws_service.dart) and a Home screen connect button.

- The Home screen Connect WS button attempts to connect to: ws://127.0.0.1:8000/ws (same host as backendBase in lib/main.dart)
- The backend must expose a websocket endpoint at /ws returning simple JSON/text messages for the client to display
- The scaffold's WebSocket usage is an example only — production apps should manage a single shared WsService instance, handle reconnect/backoff, and show connection state reliably.

If you want, I can wire the backend to expose a /ws streaming endpoint that publishes signals/events in real-time (read-only). Let me know and I will add that server-side endpoint.