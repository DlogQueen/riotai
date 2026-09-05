# In the Raw — social media for actual life

Everyone else is having a great week. They are not.

In the Raw is a full social network — accounts, profiles, feeds, following, posting,
commenting, reacting — built for the part of life that does not photograph well.
It runs inside this project at **`/real`**, and as an Android app in
`android/` (see `android/README.md`).

## The rules, which are the product

Anyone can build a feed. The design decisions below are the actual thing:

| | |
|---|---|
| **Posts must name a state** | Nine of them: rough day, grinding, nothing special, small win, spiraling, healing, angry, numb, okay actually. There is no "living my best life" and there never will be. |
| **Reactions, not likes** | *been there · i see you · holding this · proud of you · same.* You cannot "like" somebody's worst week, so you can't here. |
| **Counts are private** | Reaction counts go to the author of the post. Follower counts go to the person being followed. Nobody else sees a number, so nobody performs one. |
| **The feed is a clock** | Strictly chronological. No ranking, no suggested posts, no engagement scoring. |
| **Posts are immutable** | You can delete a post. You cannot edit it. Deleting is honest; quietly rewriting yesterday is not. |
| **Profiles ask harder questions** | Not just a bio: what you're actually dealing with, what's going okay, what you're bad at, where you're at right now. |
| **Nothing that manufactures habit** | No ads, no streaks, no reach, no growth loop, no "you haven't posted in 3 days." |

Your profile's current state follows your last post automatically — the profile
tells the truth without you having to maintain it.

## Running it

```bash
pip install -r requirements.txt
python3 server.py          # or ./START.sh
open http://localhost:5001/real
```

SQLite locally (`real_life.db`, gitignored). Set `SUPABASE_URL` and
`SUPABASE_KEY` for production and it uses Supabase instead — run
`real_schema.sql` in the SQL editor first.

**Set `SECRET_KEY` in production.** Sessions are signed with it; the built-in
development fallback is not a secret. Add it as a plain environment variable in
your host's project settings (on Vercel: Settings → Environment Variables) —
deliberately not wired into `vercel.json`, since an `@secret` reference there
fails the deploy until the secret exists.

## The map

| File | What's in it |
|---|---|
| `real_db.py` | Users, posts, comments, reactions, follows. Dual backend, no SQL joins — rows get stitched in Python so SQLite and Postgres behave identically. |
| `real_routes.py` | The Flask blueprint: auth, feed, profiles, posting, reacting, following. |
| `real_schema.sql` | Supabase tables, indexes, RLS policies. |
| `templates/real/` | The interface. Serif for what people write, sans for the chrome. |

## Known edges

- Auth is password + Flask session. No email verification, password reset, or
  rate limiting yet — add those before real strangers use it.
- RLS policies are permissive (`allow all` under the anon key), matching the
  rest of this project. Authorization lives in the Flask layer.
- Text posts only. Images are deliberately not in v1: the moment you add
  images you have to decide about filters, and that argument deserves its own day.
- No moderation, blocking, or reporting yet. A site about people's worst weeks
  needs those before it needs anything else — that's the next thing to build.
