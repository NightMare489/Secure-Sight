"""Read-only Gemini analytics copilot backed by fixed database tools."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import GeminiConfig
from app.models.alert import Alert
from app.models.camera import Camera


class CopilotService:
    _LOCAL_TZ = ZoneInfo("Africa/Cairo")
    _UNSAFE_SQL = re.compile(
        r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|GRANT|REVOKE|TRIGGER)\b",
        re.IGNORECASE,
    )

    def __init__(self, session: Session, config: GeminiConfig) -> None:
        self._session = session
        self._config = config

    def ask(self, message: str, history: list | None = None) -> dict:
        if not self._config.api_key:
            raise ValueError("Gemini is not configured. Set GEMINI_API_KEY in backend/.env and restart the backend.")
        contents = [
            {"role": item.role, "parts": [{"text": item.text}]}
            for item in (history or [])[-12:]
        ]
        contents.append({"role": "user", "parts": [{"text": message}]})
        evidence: dict = {"incidents": [], "chart": None}
        for _ in range(4):
            response = self._generate(contents)
            parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            calls = [part["functionCall"] for part in parts if "functionCall" in part]
            if not calls:
                answer = " ".join(part.get("text", "") for part in parts).strip()
                return {"answer": answer or "I could not generate an answer.", **evidence}
            contents.append({"role": "model", "parts": parts})
            responses = []
            for call in calls:
                result = self._call_tool(call.get("name", ""), call.get("args", {}))
                if "incidents" in result:
                    evidence["incidents"] = result["incidents"]
                if "chart" in result:
                    evidence["chart"] = result["chart"]
                if "rows" in result:
                    evidence["incidents"] = self._incident_cards_from_rows(result["rows"])
                responses.append({"functionResponse": {"name": call["name"], "response": result}})
            contents.append({"role": "user", "parts": responses})
        return {"answer": "I reached the analytics tool limit for this question.", **evidence}

    def _generate(self, contents: list[dict]) -> dict:
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + urllib.parse.quote(self._config.model) + ":generateContent?key=" + urllib.parse.quote(self._config.api_key)
        payload = {
            "systemInstruction": {"parts": [{"text": self._system_instruction()}]},
            "contents": contents,
            "tools": [{"functionDeclarations": [
                {"name": "get_incidents", "description": "Find incident alerts and their review status or footage. With no dates, search all recorded incidents. Results are newest first.", "parameters": {"type": "OBJECT", "properties": {"start_date": {"type": "STRING", "description": "Local Cairo calendar date, YYYY-MM-DD"}, "end_date": {"type": "STRING", "description": "Local Cairo calendar date, YYYY-MM-DD"}, "camera_id": {"type": "STRING"}, "event_type": {"type": "STRING", "enum": ["ENTER", "LOITERING", "OCCUPANCY_LIMIT"]}, "limit": {"type": "INTEGER"}}}},
                {"name": "get_incident_chart", "description": "Count incidents and return chart-ready data. With no dates, chart all recorded incidents.", "parameters": {"type": "OBJECT", "properties": {"start_date": {"type": "STRING", "description": "Local Cairo calendar date, YYYY-MM-DD"}, "end_date": {"type": "STRING", "description": "Local Cairo calendar date, YYYY-MM-DD"}, "camera_id": {"type": "STRING"}, "group_by": {"type": "STRING", "enum": ["hour", "day", "event_type"]}, "chart_type": {"type": "STRING", "enum": ["bar", "line", "pie"]}}, "required": ["group_by"]}},
                {"name": "find_cameras", "description": "Look up camera IDs from a camera name before querying a named camera.", "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}}},
                {"name": "run_read_only_sql", "description": "Run one SQLite SELECT or WITH...SELECT query for an analytics question that the other tools cannot answer. Allowed tables: alerts(id, zone_id, camera_id, tracker_id, global_person_id, association_confidence, association_method, event_type, timestamp, acknowledged, acknowledged_at, acknowledgement_note, snapshot_path, clip_path), cameras(id, name, source_type, description, is_active), zones(id, camera_id, name, rule_type, dwell_threshold_seconds, occupancy_limit, is_active). Use joins and GROUP BY freely. For footage retrieval, select alerts.id AS alert_id so the UI can show Watch clip buttons. Never use any write or schema command. Results are limited to 100 rows.", "parameters": {"type": "OBJECT", "properties": {"sql": {"type": "STRING", "description": "A single read-only SQLite SELECT query"}}, "required": ["sql"]}},
            ]}],
        }
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as result:
                return json.loads(result.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise ValueError(f"Gemini request failed: {detail}") from exc

    def _call_tool(self, name: str, args: dict) -> dict:
        if name == "get_incidents":
            return self._get_incidents(args)
        if name == "get_incident_chart":
            return self._get_chart(args)
        if name == "find_cameras":
            query = self._session.query(Camera)
            if args.get("name"):
                query = query.filter(Camera.name.ilike(f"%{args['name']}%"))
            return {"cameras": [{"id": camera.id, "name": camera.name, "description": camera.description} for camera in query.limit(50).all()]}
        if name == "run_read_only_sql":
            return self._run_read_only_sql(args.get("sql", ""))
        return {"error": "Unknown tool"}

    def _system_instruction(self) -> str:
        today = datetime.now(self._LOCAL_TZ).date()
        yesterday = today - timedelta(days=1)
        return (
            "You are a surveillance analytics assistant. Use tools for every factual claim. "
            "You are read-only. The local timezone is Africa/Cairo. Today is "
            f"{today.isoformat()} and yesterday is {yesterday.isoformat()}. "
            "For relative dates, use these Cairo calendar dates, never UTC dates. "
            "Do not ask for a date range when the user does not specify one: query all recorded incidents. "
            "For a question about the day with most incidents, call get_incident_chart grouped by day over all history. "
            "For a category pie-chart request, call get_incident_chart grouped by event_type with chart_type pie. "
            "If the user names an event type such as loitering, pass that event_type to get_incidents. "
            "If the user asks for the last/latest/most recent incident or footage, pass limit 1 so only that incident is returned. "
            "If a user names a camera, first call find_cameras to obtain its ID. "
            "For questions the fixed tools do not cover, including cross-camera anonymous identity analysis, use run_read_only_sql before saying data is unavailable. "
            "After tools return, give a short factual answer and refer to returned footage when available."
        )

    def _date_range(self, args: dict) -> tuple[datetime | None, datetime | None]:
        if not args.get("start_date") and not args.get("end_date"):
            return None, None
        today = datetime.now(self._LOCAL_TZ).date()
        start_date = datetime.fromisoformat(args.get("start_date", today.isoformat())).date()
        end_date = datetime.fromisoformat(args.get("end_date", today.isoformat())).date()
        start = datetime.combine(start_date, time.min, tzinfo=self._LOCAL_TZ).astimezone(timezone.utc)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=self._LOCAL_TZ).astimezone(timezone.utc)
        return start, end

    def _base_query(self, args: dict):
        start, end = self._date_range(args)
        query = self._session.query(Alert).filter(Alert.event_type != "EXIT")
        if start is not None and end is not None:
            query = query.filter(Alert.timestamp >= start, Alert.timestamp < end)
        if args.get("camera_id"):
            query = query.filter(Alert.camera_id == args["camera_id"])
        if args.get("event_type"):
            query = query.filter(Alert.event_type == args["event_type"])
        return query, start, end

    def _get_incidents(self, args: dict) -> dict:
        query, start, end = self._base_query(args)
        alerts = query.order_by(Alert.timestamp.desc()).limit(min(int(args.get("limit", 20)), 50)).all()
        return {"filters": {"start": start.isoformat() if start else "all history", "end": end.isoformat() if end else "all history", "camera_id": args.get("camera_id")}, "incidents": [{"id": a.id, "event_type": a.event_type, "timestamp": a.timestamp.isoformat(), "camera_name": a.camera.name if a.camera else "", "zone_name": a.zone.name if a.zone else "", "reviewed": a.acknowledged, "has_clip": bool(a.clip_path), "clip_url": f"/api/v1/alerts/{a.id}/clip" if a.clip_path else None} for a in alerts]}

    def _get_chart(self, args: dict) -> dict:
        query, start, end = self._base_query(args)
        group_by = args.get("group_by", "day")
        if group_by == "event_type":
            key = Alert.event_type
            label = "Event type"
        elif group_by == "hour":
            key = func.strftime("%Y-%m-%d %H:00", Alert.timestamp)
            label = "Hour"
        else:
            key = func.strftime("%Y-%m-%d", Alert.timestamp)
            label = "Day"
        rows = query.with_entities(key.label("bucket"), func.count(Alert.id).label("incidents")).group_by(key).order_by(key).all()
        chart_type = args.get("chart_type", "bar")
        return {"chart": {"chart_type": chart_type, "title": f"Incidents by {group_by}", "x_key": "bucket", "series": [{"key": "incidents", "label": "Incidents"}], "data": [{"bucket": row.bucket, "incidents": row.incidents} for row in rows], "filters_used": {"start": start.isoformat() if start else "all history", "end": end.isoformat() if end else "all history", "camera_id": args.get("camera_id")}}}

    def _run_read_only_sql(self, sql: str) -> dict:
        """Execute a bounded analytics SELECT after deliberately strict validation."""
        normalized = sql.strip()
        if not normalized or ";" in normalized or "--" in normalized or "/*" in normalized:
            return {"error": "Only one plain SELECT query is allowed."}
        if not re.match(r"^(SELECT|WITH)\b", normalized, flags=re.IGNORECASE):
            return {"error": "Only SELECT or WITH...SELECT queries are allowed."}
        if self._UNSAFE_SQL.search(normalized):
            return {"error": "The query contains a blocked command."}
        try:
            result = self._session.execute(
                text(f"SELECT * FROM ({normalized}) AS analytics_result LIMIT 100")
            )
            rows = [dict(row._mapping) for row in result]
            for row in rows:
                # Never leak a local disk path to the model or browser. Clip
                # media is only exposed through the alert endpoint.
                alert_id = row.get("alert_id") or row.get("id")
                if row.get("clip_path"):
                    row.pop("clip_path", None)
                    if alert_id:
                        row["clip_url"] = f"/api/v1/alerts/{alert_id}/clip"
            return {"row_count": len(rows), "rows": rows, "limited_to": 100}
        except Exception as exc:
            return {"error": f"Query could not run: {exc}"}

    def _incident_cards_from_rows(self, rows: list[dict]) -> list[dict]:
        """Turn flexible-SQL footage rows into the frontend's incident cards."""
        cards: list[dict] = []
        seen: set[str] = set()
        for row in rows:
            alert_id = row.get("alert_id") or row.get("id")
            if not alert_id or alert_id in seen:
                continue
            alert = self._session.query(Alert).filter(Alert.id == alert_id).one_or_none()
            if alert is None:
                continue
            seen.add(alert_id)
            cards.append({
                "id": alert.id,
                "event_type": alert.event_type,
                "timestamp": alert.timestamp.isoformat(),
                "camera_name": alert.camera.name if alert.camera else "",
                "zone_name": alert.zone.name if alert.zone else "",
                "reviewed": alert.acknowledged,
                "has_clip": bool(alert.clip_path),
                "clip_url": f"/api/v1/alerts/{alert.id}/clip" if alert.clip_path else None,
            })
        return cards
