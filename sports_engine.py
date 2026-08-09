"""
COACH'S SPORTS TALK
Pulls real, live college football data from ESPN's public scoreboard/summary
endpoints (the same free, unauthenticated JSON feeds ESPN's own site widgets
use - no API key required, no scraping of HTML) and shapes it into short,
model-friendly snapshots so Coach can "call" a game or host a live talk
segment grounded in real scores instead of guessing.

This is a fun/personal project use of a public endpoint - not affiliated with
or endorsed by ESPN. If ESPN ever changes or rate-limits this feed, these
calls will start failing gracefully (see the try/except in every function).
"""

import requests
from datetime import datetime, timedelta

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
SCOREBOARD_URL = f"{BASE}/scoreboard"
SUMMARY_URL = f"{BASE}/summary"
TEAM_LOGO = "https://a.espncdn.com/i/teamlogos/ncaa/500/{id}.png"

TIMEOUT = 8


def _get(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _simplify_event(ev: dict) -> dict:
    comp = (ev.get('competitions') or [{}])[0]
    status = ev.get('status', {})
    stype = status.get('type', {})
    situation = comp.get('situation', {})

    competitors = []
    for c in comp.get('competitors', []):
        team = c.get('team', {})
        competitors.append({
            'id': team.get('id'),
            'name': team.get('displayName'),
            'abbr': team.get('abbreviation'),
            'score': c.get('score', '0'),
            'homeAway': c.get('homeAway'),
            'rank': c.get('curatedRank', {}).get('current') if c.get('curatedRank', {}).get('current', 99) != 99 else None,
            'color': team.get('color'),
            'logo': TEAM_LOGO.format(id=team.get('id')) if team.get('id') else None,
        })
    # away first, then home, for a natural "X at Y" reading order
    competitors.sort(key=lambda c: 0 if c['homeAway'] == 'away' else 1)

    return {
        'id': ev.get('id'),
        'name': ev.get('name'),
        'shortName': ev.get('shortName'),
        'date': ev.get('date'),
        'week': (ev.get('week') or {}).get('number'),
        'state': stype.get('state'),          # 'pre' | 'in' | 'post'
        'completed': stype.get('completed', False),
        'detail': stype.get('shortDetail') or stype.get('detail'),
        'period': status.get('period'),
        'clock': status.get('displayClock'),
        'venue': (comp.get('venue') or {}).get('fullName'),
        'competitors': competitors,
        'situation': {
            'down': situation.get('shortDownDistanceText'),
            'possession': situation.get('possessionText'),
            'lastPlay': (situation.get('lastPlay') or {}).get('text'),
        } if situation else None,
    }


def get_scoreboard(days_ahead: int = 35, team: str = None, limit: int = 100) -> list:
    """Live/upcoming/recent games. Scans forward from today if nothing's on
    today's slate (very common in the offseason) so the UI is never empty.
    days_ahead defaults wide enough (~5 weeks) to reach the next kickoff even
    from the depths of the off-season; widens further once if still empty."""
    today = datetime.utcnow()

    def fetch(span_days):
        start = today.strftime('%Y%m%d')
        end = (today + timedelta(days=span_days)).strftime('%Y%m%d')
        data = _get(SCOREBOARD_URL, {'dates': f'{start}-{end}', 'limit': limit})
        return [_simplify_event(ev) for ev in data.get('events', [])]

    try:
        events = fetch(days_ahead)
        if not events:
            events = fetch(120)  # off-season fallback: look up to ~4 months out
    except Exception as e:
        print(f"❌ [SPORTS] Scoreboard fetch failed: {e}")
        return []

    if team:
        needle = team.lower()
        events = [
            e for e in events
            if any(needle in (c['name'] or '').lower() or needle in (c['abbr'] or '').lower()
                   for c in e['competitors'])
        ]

    # Live games first, then soonest upcoming, then most recent final
    def sort_key(e):
        order = {'in': 0, 'pre': 1, 'post': 2}
        return (order.get(e['state'], 3), e['date'])
    events.sort(key=sort_key)
    return events


def get_game_snapshot(event_id: str) -> dict:
    """Detailed live snapshot of one game: score, situation, last plays, big scoring plays."""
    try:
        data = _get(SUMMARY_URL, {'event': event_id})
    except Exception as e:
        print(f"❌ [SPORTS] Summary fetch failed: {e}")
        return {}

    header_comp = (data.get('header', {}).get('competitions') or [{}])[0]
    status = header_comp.get('status', {})
    stype = status.get('type', {})
    situation = header_comp.get('situation', {})

    competitors = []
    for c in header_comp.get('competitors', []):
        team = c.get('team', {})
        competitors.append({
            'name': team.get('displayName'),
            'abbr': team.get('abbreviation'),
            'score': c.get('score'),
            'homeAway': c.get('homeAway'),
        })
    competitors.sort(key=lambda c: 0 if c['homeAway'] == 'away' else 1)

    recent_plays = []
    drives = data.get('drives', {})
    current_drive = drives.get('current')
    last_drives = drives.get('previous', [])
    if current_drive:
        last_drives = last_drives + [current_drive]
    for drive in last_drives[-2:]:
        for play in drive.get('plays', [])[-3:]:
            recent_plays.append(play.get('text'))

    scoring_plays = [
        f"{sp.get('team', {}).get('abbreviation', '')}: {sp.get('text', '').strip()}"
        for sp in data.get('scoringPlays', [])[-5:]
    ]

    return {
        'id': event_id,
        'state': stype.get('state'),
        'detail': stype.get('shortDetail') or stype.get('detail'),
        'period': status.get('period'),
        'clock': status.get('displayClock'),
        'competitors': competitors,
        'situation': {
            'down': situation.get('shortDownDistanceText'),
            'possession': situation.get('possessionText'),
            'lastPlay': (situation.get('lastPlay') or {}).get('text'),
        } if situation else None,
        'recent_plays': [p for p in recent_plays if p],
        'scoring_plays': scoring_plays,
    }


def snapshot_to_text(snap: dict) -> str:
    """Render a game snapshot as short plain text to hand to the model."""
    if not snap or not snap.get('competitors'):
        return "No live data available for this game right now."

    a, b = (snap['competitors'] + [{}, {}])[:2]
    lines = [
        f"{a.get('name', '?')} {a.get('score', '?')} — {b.get('score', '?')} {b.get('name', '?')}",
        f"Status: {snap.get('detail', 'unknown')}"
        + (f", Q{snap['period']} {snap['clock']}" if snap.get('period') else ''),
    ]
    situation = snap.get('situation')
    if situation and (situation.get('down') or situation.get('possession')):
        lines.append(f"Situation: {situation.get('down', '')} — {situation.get('possession', '')}".strip(' —'))
    if snap.get('recent_plays'):
        lines.append("Recent plays: " + " | ".join(snap['recent_plays'][-4:]))
    if snap.get('scoring_plays'):
        lines.append("Scoring plays so far: " + " | ".join(snap['scoring_plays']))
    return '\n'.join(lines)
