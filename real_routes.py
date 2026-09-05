"""
RAW - social media for actual life.

The whole point, stated once so it doesn't get lost:

  * Every post has to name a real state. There is no "living my best life."
  * Reactions are not likes. You cannot "like" someone's worst week.
  * Reaction counts are visible to the author of a post and to nobody else.
  * Follower counts are visible to the person being followed and to nobody else.
  * The feed is chronological. There is no algorithm and there will not be one.
  * Posts cannot be edited. You can delete one. You cannot polish it.
"""

from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

import real_db as db

real = Blueprint('real', __name__, url_prefix='/real')

MAX_POST = 1200
MAX_COMMENT = 600

# Shown on the composer. Rotates daily so it never becomes wallpaper.
PROMPTS = [
    "How is it actually going?",
    "What did today cost you?",
    "What's the unglamorous part?",
    "What are you avoiding?",
    "What went fine? Just fine is fine.",
    "What would you not post anywhere else?",
    "What's the thing you keep not saying?",
]


# ── Session helpers ────────────────────────────────────────────────────────────

def current_user():
    uid = session.get('real_uid')
    return db.get_user(uid) if uid else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('real_uid'):
            return redirect(url_for('real.login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@real.app_template_filter('ago')
def ago(iso: str) -> str:
    if not iso:
        return ''
    try:
        then = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    if secs < 60:
        return 'just now'
    if secs < 3600:
        return f'{int(secs // 60)}m ago'
    if secs < 86400:
        return f'{int(secs // 3600)}h ago'
    if secs < 604800:
        return f'{int(secs // 86400)}d ago'
    return then.strftime('%b %-d')


@real.app_template_filter('joined')
def joined(iso: str) -> str:
    """Profiles show the month you arrived, not a countdown."""
    if not iso:
        return ''
    try:
        return datetime.fromisoformat(iso).strftime('%B %Y')
    except ValueError:
        return iso


@real.context_processor
def inject():
    return {
        'me': current_user(),
        'STATES': db.STATES,
        'REACTIONS': db.REACTIONS,
        'prompt': PROMPTS[datetime.now(timezone.utc).timetuple().tm_yday % len(PROMPTS)],
    }


# ── Post hydration ─────────────────────────────────────────────────────────────

def hydrate(posts: list, viewer, with_comments: bool = False) -> list:
    """Stitch authors, reactions and comments onto raw post rows."""
    if not posts:
        return []

    post_ids = [p['id'] for p in posts]
    reactions = db.reactions_for_posts(post_ids)
    comments = db.comments_for_posts(post_ids) if with_comments else {}

    needed = {p['user_id'] for p in posts}
    for rows in comments.values():
        needed.update(c['user_id'] for c in rows)
    authors = db.get_users(needed)

    viewer_id = viewer['id'] if viewer else None
    out = []
    for p in posts:
        rows = reactions.get(p['id'], [])
        mine = {r['kind'] for r in rows if r['user_id'] == viewer_id}
        is_author = viewer_id == p['user_id']

        counts = {}
        if is_author:
            for r in rows:
                counts[r['kind']] = counts.get(r['kind'], 0) + 1

        out.append({
            **p,
            'author': authors.get(p['user_id']),
            'state_meta': db.STATES.get(p['state'], db.STATES['mundane']),
            'my_reactions': mine,
            # Only ever populated for the author. Everyone else gets {}.
            'reaction_counts': counts,
            'is_mine': is_author,
            'comments': [
                {**c, 'author': authors.get(c['user_id']), 'is_mine': c['user_id'] == viewer_id}
                for c in comments.get(p['id'], [])
            ],
            'comment_count': len(comments.get(p['id'], [])),
        })
    return out


# ── Auth ───────────────────────────────────────────────────────────────────────

@real.route('/join', methods=['GET', 'POST'])
def join():
    if current_user():
        return redirect(url_for('real.feed'))

    if request.method == 'POST':
        handle = db.normalize_handle(request.form.get('handle'))
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        name = (request.form.get('display_name') or '').strip()

        if not db.handle_is_valid(handle):
            flash('Handle needs 3-20 characters: lowercase letters, numbers, underscores.')
        elif '@' not in email or '.' not in email:
            flash('That email does not look like an email.')
        elif len(password) < 8:
            flash('Password needs at least 8 characters.')
        elif db.get_user_by_handle(handle):
            flash('That handle is taken.')
        elif db.get_user_by_email(email):
            flash('There is already an account on that email.')
        else:
            user = db.create_user(handle, email, generate_password_hash(password), name or handle)
            session['real_uid'] = user['id']
            return redirect(url_for('real.edit_profile'))

    return render_template('real/join.html')


@real.route('/login', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('real.feed'))

    if request.method == 'POST':
        who = (request.form.get('who') or '').strip()
        password = request.form.get('password') or ''
        user = db.get_user_by_email(who) if '@' in who else db.get_user_by_handle(who)
        if user and check_password_hash(user['password_hash'], password):
            session['real_uid'] = user['id']
            nxt = request.args.get('next') or request.form.get('next')
            return redirect(nxt if nxt and nxt.startswith('/real') else url_for('real.feed'))
        flash('That combination did not work.')

    return render_template('real/login.html')


@real.route('/logout', methods=['POST'])
def logout():
    session.pop('real_uid', None)
    return redirect(url_for('real.landing'))


# ── Pages ──────────────────────────────────────────────────────────────────────

@real.route('/')
def landing():
    if current_user():
        return redirect(url_for('real.feed'))
    return render_template('real/landing.html')


@real.route('/feed')
@login_required
def feed():
    me = current_user()
    ids = db.following_ids(me['id']) + [me['id']]
    posts = hydrate(db.posts_by_users(ids, limit=60), me, with_comments=True)
    return render_template('real/feed.html', posts=posts, empty_hint=len(ids) == 1)


@real.route('/everyone')
@login_required
def everyone():
    me = current_user()
    posts = hydrate(db.recent_posts(limit=60), me, with_comments=True)
    return render_template('real/feed.html', posts=posts,
                           heading='Everyone', subheading='Every post on here, newest first. Still no algorithm.',
                           empty_hint=False)


@real.route('/people')
@login_required
def people():
    me = current_user()
    following = set(db.following_ids(me['id']))
    users = [u for u in db.list_users(limit=100) if u['id'] != me['id']]
    return render_template('real/people.html', users=users, following=following)


@real.route('/u/<handle>')
@login_required
def profile(handle):
    me = current_user()
    user = db.get_user_by_handle(handle)
    if not user:
        abort(404)

    posts = hydrate(db.posts_by_user(user['id'], limit=60), me, with_comments=True)
    is_me = user['id'] == me['id']

    return render_template(
        'real/profile.html',
        user=user,
        posts=posts,
        is_me=is_me,
        state_meta=db.STATES.get(user['current_state'], db.STATES['mundane']),
        i_follow=db.is_following(me['id'], user['id']),
        follows_me=db.is_following(user['id'], me['id']),
        # Counts are the owner's business. Nobody performs numbers here.
        follower_count=len(db.follower_ids(user['id'])) if is_me else None,
        following_count=len(db.following_ids(user['id'])) if is_me else None,
    )


@real.route('/settings', methods=['GET', 'POST'])
@login_required
def edit_profile():
    me = current_user()
    if request.method == 'POST':
        db.update_profile(me['id'], request.form.to_dict())
        flash('Profile saved.')
        return redirect(url_for('real.profile', handle=me['handle']))
    return render_template('real/settings.html', user=me)


@real.route('/p/<int:post_id>')
@login_required
def post_detail(post_id):
    me = current_user()
    post = db.get_post(post_id)
    if not post:
        abort(404)
    return render_template('real/post.html', post=hydrate([post], me, with_comments=True)[0])


# ── Actions ────────────────────────────────────────────────────────────────────

@real.route('/post', methods=['POST'])
@login_required
def new_post():
    me = current_user()
    body = (request.form.get('body') or '').strip()
    state = request.form.get('state') or 'mundane'

    if not body:
        flash('Nothing to say is fine. Blank posts are not.')
    elif len(body) > MAX_POST:
        flash(f'That is longer than {MAX_POST} characters. Trim it or split it.')
    else:
        db.create_post(me['id'], body, state)
        db.update_profile(me['id'], {'current_state': state})

    return redirect(request.referrer or url_for('real.feed'))


@real.route('/p/<int:post_id>/delete', methods=['POST'])
@login_required
def remove_post(post_id):
    me = current_user()
    post = db.get_post(post_id)
    if not post:
        abort(404)
    if post['user_id'] != me['id']:
        abort(403)
    db.delete_post(post_id)
    return redirect(url_for('real.feed'))


@real.route('/p/<int:post_id>/react', methods=['POST'])
@login_required
def react(post_id):
    me = current_user()
    if not db.get_post(post_id):
        abort(404)
    payload = request.get_json(silent=True) or {}
    kind = request.form.get('kind') or payload.get('kind') or ''
    on = db.toggle_reaction(post_id, me['id'], kind)
    if request.headers.get('X-Requested-With') == 'fetch':
        return jsonify({'on': on, 'kind': kind})
    return redirect(request.referrer or url_for('real.feed'))


@real.route('/p/<int:post_id>/comment', methods=['POST'])
@login_required
def comment(post_id):
    me = current_user()
    if not db.get_post(post_id):
        abort(404)
    body = (request.form.get('body') or '').strip()
    if not body:
        flash('Empty comment.')
    elif len(body) > MAX_COMMENT:
        flash(f'Comments cap at {MAX_COMMENT} characters.')
    else:
        db.create_comment(post_id, me['id'], body)
    return redirect(request.referrer or url_for('real.post_detail', post_id=post_id))


@real.route('/c/<int:comment_id>/delete', methods=['POST'])
@login_required
def remove_comment(comment_id):
    me = current_user()
    c = db.get_comment(comment_id)
    if not c:
        abort(404)
    if c['user_id'] != me['id']:
        abort(403)
    db.delete_comment(comment_id)
    return redirect(request.referrer or url_for('real.feed'))


@real.route('/u/<handle>/follow', methods=['POST'])
@login_required
def follow_user(handle):
    me = current_user()
    user = db.get_user_by_handle(handle)
    if not user:
        abort(404)
    if db.is_following(me['id'], user['id']):
        db.unfollow(me['id'], user['id'])
    else:
        db.follow(me['id'], user['id'])
    return redirect(request.referrer or url_for('real.profile', handle=handle))


@real.route('/state', methods=['POST'])
@login_required
def set_state():
    me = current_user()
    db.update_profile(me['id'], {'current_state': request.form.get('state') or ''})
    return redirect(request.referrer or url_for('real.feed'))
