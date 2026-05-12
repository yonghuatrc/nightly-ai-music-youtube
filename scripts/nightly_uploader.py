#!/usr/bin/env python3
"""
nightly_uploader.py — YouTube Data API v3 uploader with OAuth auto-refresh

Uploads video files to YouTube with resumable upload, thumbnail support,
and scheduling capability. Uses OAuth 2.0 with automatic token refresh.

Prerequisites:
    pip3 install google-auth google-auth-oauthlib google-api-python-client

First-time setup:
    1. Download OAuth client secret from Google Cloud Console
     2. Save as /mnt/d/Hermes/secrets/youtube-oauth.json
    3. Run: python3 nightly_uploader.py --setup-auth
    4. Follow browser prompt to authorize

Usage:
    python3 nightly_uploader.py --video video.mp4 --title "Title" --desc "Desc" --tags "tag1,tag2"
    python3 nightly_uploader.py --setup-auth

Module usage:
    from nightly_uploader import upload_video
    result = upload_video("video.mp4", "My Title", "Description", ["tag1", "tag2"])
"""

import os
import sys
import json
import time
import argparse
import pathlib


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CREDENTIALS_PATH = "/mnt/d/Hermes/secrets/youtube-oauth.json"
TOKEN_PATH = "/mnt/d/Hermes/secrets/youtube-oauth-token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# Quota costs (YouTube Data API v3)
QUOTA_UPLOAD_COST = 1600  # videos.insert with snippet + status
QUOTA_THUMBNAIL_COST = 50  # thumbnails.set


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
_GOOGLE_DEPS_AVAILABLE = False
_GOOGLE_DEPS_ERROR = None

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    _GOOGLE_DEPS_AVAILABLE = True
except ImportError as e:
    _GOOGLE_DEPS_ERROR = str(e)


def _check_deps():
    """Check Google API deps. Returns (ok, message)."""
    if _GOOGLE_DEPS_AVAILABLE:
        return True, "dependencies OK"
    msg = (
        "Missing Google API dependencies. Install with:\n"
        "  pip3 install google-auth google-auth-oauthlib google-api-python-client\n"
        f"Error: {_GOOGLE_DEPS_ERROR}"
    )
    return False, msg


# ---------------------------------------------------------------------------
# OAuth authentication
# ---------------------------------------------------------------------------
def _get_authenticated_service():
    """Get authenticated YouTube API service. Handles token refresh."""
    ok, msg = _check_deps()
    if not ok:
        raise RuntimeError(msg)

    credentials = None

    # Load saved token
    if os.path.exists(TOKEN_PATH):
        try:
            credentials = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            credentials = None

    # Refresh or re-auth
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _save_credentials(credentials)
        except Exception:
            credentials = None

    # Fresh OAuth flow
    if not credentials or not credentials.valid:
        if not os.path.exists(CREDENTIALS_PATH):
            raise FileNotFoundError(
                f"OAuth credentials not found at {CREDENTIALS_PATH}\n"
                "Download client_secret JSON from Google Cloud Console and save it there."
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            credentials = flow.run_local_server(port=0)
            _save_credentials(credentials)
        except Exception as e:
            raise RuntimeError(f"OAuth authentication failed: {e}")

    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def _save_credentials(credentials):
    """Save credentials token to disk."""
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f)


def setup_auth():
    """Interactive first-time OAuth setup. Opens browser for consent."""
    ok, msg = _check_deps()
    if not ok:
        print(f"ERROR: {msg}", file=sys.stderr)
        return False

    if not os.path.exists(CREDENTIALS_PATH):
        print(f"ERROR: OAuth credentials not found at {CREDENTIALS_PATH}", file=sys.stderr)
        print("Download client_secret JSON from Google Cloud Console and save it as:", CREDENTIALS_PATH)
        return False

    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        credentials = flow.run_local_server(port=0)
        _save_credentials(credentials)
        print("[nightly:uploader] OAuth setup complete — token saved")
        return True
    except Exception as e:
        print(f"[nightly:uploader] Auth setup failed: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Video upload
# ---------------------------------------------------------------------------
def upload_video(
    video_path,
    title,
    description,
    tags,
    category_id="10",
    privacy="private",
    thumbnail_path=None,
    publish_at=None,
):
    """
    Upload a video to YouTube with resumable upload.

    Args:
        video_path: Path to MP4 video file
        title: Video title (max 100 chars)
        description: Video description
        tags: List of tag strings
        category_id: YouTube category ID (default 10 = Music)
        privacy: Privacy status: "private", "unlisted", "public"
        thumbnail_path: Optional path to thumbnail image
        publish_at: Optional RFC 3339 datetime for scheduled publishing.
                    When set, privacy is forced to "private".

    Returns:
        dict with keys: video_id, youtube_url, status, error (if failed)
    """
    result = {
        "video_id": "",
        "youtube_url": "",
        "status": "failed",
        "error": None,
    }

    ok, msg = _check_deps()
    if not ok:
        result["error"] = msg
        print(f"[nightly:uploader] {msg}", file=sys.stderr)
        return result

    if not os.path.exists(video_path):
        result["error"] = f"Video file not found: {video_path}"
        print(f"[nightly:uploader] {result['error']}", file=sys.stderr)
        return result

    if not os.path.exists(CREDENTIALS_PATH):
        result["error"] = f"OAuth credentials missing: {CREDENTIALS_PATH}"
        print(f"[nightly:uploader] {result['error']}", file=sys.stderr)
        return result

    # Truncate title to YouTube's 100 char limit
    if len(title) > 100:
        title = title[:97] + "..."

    try:
        youtube = _get_authenticated_service()
    except Exception as e:
        result["error"] = f"Auth failed: {e}"
        print(f"[nightly:uploader] {result['error']}", file=sys.stderr)
        return result

    # Build request body
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],  # YouTube limit: 30 tags
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Scheduling: must be private, with publishAt
    if publish_at:
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at

    # Resumable upload
    media = MediaFileUpload(
        video_path,
        mimetype="video/*",
        resumable=True,
        chunksize=256 * 1024,  # 256KB chunks
    )

    print(f"[nightly:uploader] Uploading: {os.path.basename(video_path)}")
    print(f"[nightly:uploader] Title: {title[:80]}")

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        # Resumable upload with progress and retry
        response = _resumable_upload(request)
        video_id = response.get("id", "")

        if not video_id:
            result["error"] = "Upload completed but no video ID returned"
            print(f"[nightly:uploader] {result['error']}", file=sys.stderr)
            return result

        result["video_id"] = video_id
        result["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
        result["status"] = "ok"
        print(f"[nightly:uploader] Uploaded: {result['youtube_url']}")

        # Set thumbnail if provided
        if thumbnail_path and os.path.exists(thumbnail_path):
            _set_thumbnail(youtube, video_id, thumbnail_path)

        # Log quota usage if available
        print(f"[nightly:uploader] Quota used: ~{QUOTA_UPLOAD_COST} units (videos.insert)")

    except HttpError as e:
        result["error"] = f"YouTube API error: {e}"
        print(f"[nightly:uploader] {result['error']}", file=sys.stderr)
    except Exception as e:
        result["error"] = str(e)
        print(f"[nightly:uploader] Upload exception: {e}", file=sys.stderr)

    return result


def _resumable_upload(request, max_retries=5):
    """Handle resumable upload with exponential backoff on 429."""
    response = None
    retries = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100) if status.progress() else 0
                if pct % 20 == 0:  # Log every 20%
                    print(f"[nightly:uploader] Progress: {pct}%")
        except HttpError as e:
            should_retry = (
                e.resp.status == 429
                or (500 <= e.resp.status < 600)
            )
            if should_retry and retries < max_retries:
                wait = 2 ** retries
                print(f"[nightly:uploader] HTTP {e.resp.status}, retrying in {wait}s...")
                time.sleep(wait)
                retries += 1
            else:
                raise
        except ConnectionError as e:
            if retries < max_retries:
                wait = 2 ** retries
                print(f"[nightly:uploader] ConnectionError, retrying in {wait}s...")
                time.sleep(wait)
                retries += 1
            else:
                raise

    return response


def _set_thumbnail(youtube, video_id, thumbnail_path):
    """Set custom thumbnail for a video."""
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/png"),
        ).execute()
        print(f"[nightly:uploader] Thumbnail set")
    except Exception as e:
        print(f"[nightly:uploader] Thumbnail upload failed (non-fatal): {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Upload video to YouTube via Data API v3"
    )
    parser.add_argument("--video", type=str, help="Path to MP4 video file")
    parser.add_argument("--title", type=str, help="Video title")
    parser.add_argument("--desc", type=str, default="", help="Video description")
    parser.add_argument("--tags", type=str, default="", help="Comma-separated tags")
    parser.add_argument("--category", type=str, default="10", help="Category ID (default: 10=Music)")
    parser.add_argument("--privacy", type=str, default="private",
                        choices=["private", "unlisted", "public"])
    parser.add_argument("--thumbnail", type=str, default=None, help="Thumbnail image path")
    parser.add_argument("--publish-at", type=str, default=None,
                        help="RFC 3339 publish time for scheduling")
    parser.add_argument("--setup-auth", action="store_true",
                        help="Run interactive OAuth setup (credentials from /mnt/d/Hermes/secrets/youtube-oauth.json)")
    args = parser.parse_args()

    if args.setup_auth:
        ok = setup_auth()
        sys.exit(0 if ok else 1)

    if not args.video or not args.title:
        parser.error("--video and --title are required for upload mode")

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    result = upload_video(
        video_path=args.video,
        title=args.title,
        description=args.desc,
        tags=tags_list,
        category_id=args.category,
        privacy=args.privacy,
        thumbnail_path=args.thumbnail,
        publish_at=args.publish_at,
    )

    if result["status"] == "ok":
        print(f"Uploaded: {result['youtube_url']}")
        sys.exit(0)
    else:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
