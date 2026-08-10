"""Collect a small, source-linked fact packet from MLB's public JSON endpoints.

No prose is invented here. The downstream writer receives only these facts and
their source URLs. Player configuration is deliberately editable because active
Japanese MLB players change during a season.
"""
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PLAYERS_PATH = ROOT / "config" / "japanese_players.json"
FACTS_DIR = ROOT / "data" / "facts"
MLB_API = os.getenv("MLB_STATS_API", "https://statsapi.mlb.com/api")


def _get(session, path, **params):
    response = session.get(f"{MLB_API}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json(), response.url


def _game_facts(game, player_by_id):
    game_pk = game.get("gamePk")
    if not game_pk:
        return []
    session = requests.Session()
    feed, source_url = _get(session, f"/v1.1/game/{game_pk}/feed/live")
    box = feed.get("liveData", {}).get("boxscore", {})
    facts = []
    for side in ("away", "home"):
        team = box.get("teams", {}).get(side, {})
        team_name = team.get("team", {}).get("name", "")
        for raw_id, entry in team.get("players", {}).items():
            try:
                player_id = int(raw_id.replace("ID", ""))
            except ValueError:
                continue
            configured = player_by_id.get(player_id)
            if not configured:
                continue
            batting = entry.get("stats", {}).get("batting", {})
            pitching = entry.get("stats", {}).get("pitching", {})
            # The boxscore's players map includes active roster members who did not
            # appear. Do not turn roster presence into a false "played today" fact.
            if not batting and not pitching:
                continue
            facts.append({
                "kind": "game",
                "player_id": player_id,
                "player_name": configured["name_ja"],
                "player_name_en": configured["name_en"],
                "priority": configured.get("priority", 0),
                "team": team_name,
                "game_pk": game_pk,
                "game_date": game.get("officialDate"),
                "status": game.get("status", {}).get("detailedState"),
                "batting": batting,
                "pitching": pitching,
                "source": source_url,
                "source_label": f"MLB game feed {game_pk}"
            })
    return facts


def _profile_facts(session, players):
    facts = []
    season = date.today().year
    for player in sorted(players, key=lambda p: p.get("priority", 0), reverse=True)[:4]:
        data, source_url = _get(
            session, f"/v1/people/{player['id']}",
            hydrate=f"currentTeam,stats(group=[hitting,pitching],type=[season],season={season})"
        )
        person = (data.get("people") or [{}])[0]
        facts.append({
            "kind": "profile",
            "player_id": player["id"],
            "player_name": player["name_ja"],
            "player_name_en": player["name_en"],
            "priority": player.get("priority", 0),
            "team": person.get("currentTeam", {}).get("name", ""),
            "primary_position": person.get("primaryPosition", {}).get("name", ""),
            "season_stats": person.get("stats", []),
            "source": source_url,
            "source_label": f"MLB player profile {player['id']}"
        })
    return facts


def main(target_date=None):
    target = date.fromisoformat(target_date) if target_date else date.today() - timedelta(days=1)
    players = json.loads(PLAYERS_PATH.read_text(encoding="utf-8"))
    player_by_id = {p["id"]: p for p in players}
    session = requests.Session()
    session.headers["User-Agent"] = "MLBJapanesePlayersChannel/1.0"
    schedule, schedule_url = _get(
        session, "/v1/schedule", sportId=1,
        startDate=target.isoformat(), endDate=target.isoformat(), hydrate="team"
    )
    facts = []
    for day in schedule.get("dates", []):
        for game in day.get("games", []):
            facts.extend(_game_facts(game, player_by_id))
    if not facts:
        facts = _profile_facts(session, players)
    facts.sort(key=lambda f: f.get("priority", 0), reverse=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    FACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = FACTS_DIR / f"{run_id}.json"
    packet = {
        "target_date": target.isoformat(),
        "collected_at": datetime.now().astimezone().isoformat(),
        "schedule_source": schedule_url,
        "facts": facts[:8]
    }
    out.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[mlb] collected {len(packet['facts'])} player fact records -> {out}")
    return out


if __name__ == "__main__":
    main()
