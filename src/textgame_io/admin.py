"""Admin interface for game servers — list sessions, stats, ban/allow users.

Added as extra routes on the Starlette app. Protected by a simple token.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from textgame_io.server import GameServer


def add_admin_routes(app, server: GameServer, admin_token: str = "") -> None:
    """Add admin API routes to an existing Starlette app.

    If admin_token is set, all admin endpoints require:
      Authorization: Bearer <admin_token>
    """

    def _check_auth(request: Request) -> bool:
        if not admin_token:
            return True
        auth = request.headers.get("authorization", "")
        return auth == f"Bearer {admin_token}"

    async def list_sessions(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        sessions = []
        for sid, session in server.sessions.items():
            sessions.append({
                "session_id": sid,
                "config": session.config.model_dump(),
                "state_keys": list(session.state.keys()),
            })
        return JSONResponse({
            "active_sessions": len(sessions),
            "sessions": sessions,
        })

    async def get_stats(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        return JSONResponse({
            "active_sessions": len(server.sessions),
            "total_sessions_created": getattr(server, "_total_sessions", len(server.sessions)),
        })

    async def kick_session(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        data = await request.json()
        session_id = data.get("session_id", "")
        session = server.get_session(session_id)
        if not session:
            return JSONResponse({"error": "session not found"}, status_code=404)

        await server.handle_disconnect(session)
        server.remove_session(session_id)
        return JSONResponse({"status": "kicked", "session_id": session_id})

    from starlette.routing import Route

    admin_routes = [
        Route("/admin/sessions", list_sessions, methods=["GET"]),
        Route("/admin/stats", get_stats, methods=["GET"]),
        Route("/admin/kick", kick_session, methods=["POST"]),
    ]

    for route in admin_routes:
        app.routes.append(route)
