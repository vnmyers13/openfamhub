"""Phase 3b: the family media library (photos and videos) and the wall's
read-only access to it."""
import asyncio
import io
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from pillow_heif import register_heif_opener

from app.services import media as media_service
from tests.test_phase2 import SETUP, _cookie, _h, _member

GPS_IFD = 0x8825
ORIENTATION = 0x0112


@pytest.fixture(autouse=True)
def _isolated_media(tmp_path, monkeypatch):
    """Keep test files out of the repo's data/ folder."""
    monkeypatch.setattr(media_service, "MEDIA_ROOT", tmp_path / "media")
    from app.core.security import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


@pytest.fixture
def jobs(setup_db, monkeypatch):
    """Run background video jobs against the test session and let tests wait for them."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def shared_session():
        yield setup_db

    monkeypatch.setattr(media_service, "session_factory", shared_session)
    return media_service.wait_for_jobs


def jpeg_with_gps(size=(3000, 2000), orientation=None) -> bytes:
    img = Image.new("RGB", size, (200, 30, 30))
    exif = Image.Exif()
    exif[GPS_IFD] = {1: "N", 2: (40.0, 44.0, 55.0), 3: "W", 4: (73.0, 59.0, 11.0)}
    if orientation:
        exif[ORIENTATION] = orientation
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    data = buf.getvalue()
    assert Image.open(io.BytesIO(data)).getexif().get_ifd(GPS_IFD), "fixture should carry GPS"
    return data


def png_with_alpha() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (800, 600), (0, 128, 255, 120)).save(buf, "PNG")
    return buf.getvalue()


def heic_photo() -> bytes:
    register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (30, 200, 90)).save(buf, "HEIF")
    data = buf.getvalue()
    assert data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"mif1"}
    return data


def ffmpeg() -> str:
    return media_service.ffmpeg_exe()


def make_video(tmp_path: Path, seconds=2, size="640x480", name="clip.mp4") -> bytes:
    out = tmp_path / name
    subprocess.run(
        [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={size}:rate=15",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-metadata", "location=+40.7128-074.0060/", "-metadata", "title=Secret place",
         str(out)],
        check=True,
    )
    return out.read_bytes()


def metadata_of(path: Path) -> str:
    """ffmpeg's description of a file (stderr of `ffmpeg -i`)."""
    return subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr


async def upload(client, who, data: bytes, filename="photo.jpg", content_type="image/jpeg"):
    return await client.post(
        "/api/media",
        content=data,
        headers={**_h(who), "Content-Type": content_type, "X-Filename": filename},
    )


async def pair_wall(client, admin):
    device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
    res = await client.post("/api/wall/pair", json={"token": device["token"]})
    return {"Cookie": _cookie(res, "wall_token")}


class TestPhotoUploads:
    async def test_photo_is_stored_without_gps_and_wall_sized(self, client, admin):
        res = await upload(client, admin, jpeg_with_gps())
        assert res.status_code == 201, res.text
        item = res.json()
        assert item["kind"] == "photo" and item["status"] == "ready"
        assert (item["width"], item["height"]) == (1920, 1280)

        for variant in ("wall", "thumb"):
            r = await client.get(item[f"{variant}_url"], headers=_h(admin))
            assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
            img = Image.open(io.BytesIO(r.content))
            assert not img.getexif().get_ifd(GPS_IFD), f"{variant} still has GPS"
            assert max(img.size) <= (1920 if variant == "wall" else 400)

    async def test_no_original_with_location_is_kept_on_disk(self, client, admin):
        item = (await upload(client, admin, jpeg_with_gps())).json()
        for f in media_service.MEDIA_ROOT.rglob("*"):
            if f.is_file():
                assert not Image.open(f).getexif().get_ifd(GPS_IFD), f
        assert item["original_name"] == "photo.jpg"

    async def test_camera_rotation_is_applied(self, client, admin):
        # Orientation 6 = rotate 90° clockwise: a landscape sensor image shown portrait.
        item = (await upload(client, admin, jpeg_with_gps(orientation=6))).json()
        assert item["width"] < item["height"]

    async def test_png_with_transparency_is_accepted(self, client, admin):
        res = await upload(client, admin, png_with_alpha(), "drawing.png", "image/png")
        assert res.status_code == 201, res.text

    @pytest.mark.parametrize("data,name", [
        (b"%PDF-1.7 not a photo", "doc.pdf"),
        (b"hello, this is text", "notes.txt"),
        (b"MZ\x90\x00 an executable", "setup.exe"),
    ])
    async def test_disallowed_types_are_rejected(self, client, admin, data, name, setup_db):
        res = await upload(client, admin, data, name, "image/jpeg")  # the header is not trusted
        assert res.status_code == 415
        assert (await client.get("/api/media", headers=_h(admin))).json() == []

    async def test_heic_is_accepted_and_stored_as_jpeg_renditions(self, client, admin):
        res = await upload(client, admin, heic_photo(), "IMG_0001.HEIC", "image/heic")
        assert res.status_code == 201, res.text
        item = res.json()
        assert item["kind"] == "photo" and item["status"] == "ready"
        assert item["original_name"] == "IMG_0001.HEIC"

        wall = await client.get(item["wall_url"], headers=_h(admin))
        assert wall.status_code == 200 and wall.headers["content-type"] == "image/jpeg"
        assert Image.open(io.BytesIO(wall.content)).format == "JPEG"

    async def test_avif_is_not_implicitly_enabled_with_heif_support(self, client, admin):
        avif = b"\x00\x00\x00\x18ftypavif\x00\x00\x00\x00avifmif1" + b"\x00" * 64
        res = await upload(client, admin, avif, "image.avif", "image/avif")
        assert res.status_code == 415

    async def test_a_broken_image_is_rejected_and_not_listed(self, client, admin):
        res = await upload(client, admin, b"\xff\xd8\xff\xe0" + b"\x00" * 200, "broken.jpg")
        assert res.status_code == 400
        assert (await client.get("/api/media", headers=_h(admin))).json() == []

    async def test_photos_over_the_size_limit_are_rejected(self, client, admin, monkeypatch):
        monkeypatch.setattr(media_service, "MAX_PHOTO_BYTES", 10_000)
        res = await upload(client, admin, jpeg_with_gps())
        assert res.status_code == 413

    async def test_oversized_uploads_are_refused_before_reading(self, client, admin, monkeypatch):
        monkeypatch.setattr(media_service, "MAX_UPLOAD_BYTES", 1000)
        res = await upload(client, admin, b"\x00" * 5000, "huge.mp4", "video/mp4")
        assert res.status_code == 413

    async def test_viewers_and_strangers_cannot_upload(self, client, admin):
        viewer = await _member(client, admin, name="Grandma", role="viewer")
        assert (await upload(client, viewer, jpeg_with_gps())).status_code == 403
        res = await client.post("/api/media", content=b"x", headers={"X-Filename": "a.jpg"})
        assert res.status_code == 401

    async def test_members_can_upload(self, client, admin):
        kid = await _member(client, admin)
        assert (await upload(client, kid, png_with_alpha(), "art.png", "image/png")).status_code == 201


class TestVideoUploads:
    async def test_video_is_converted_and_its_metadata_removed(self, client, admin, jobs, tmp_path):
        res = await upload(client, admin, make_video(tmp_path), "beach.mp4", "video/mp4")
        assert res.status_code == 202, res.text
        assert res.json()["status"] == "processing"
        await jobs()

        item = next(i for i in (await client.get("/api/media", headers=_h(admin))).json())
        assert item["status"] == "ready", item
        assert item["kind"] == "video" and 1.5 <= item["duration_s"] <= 2.5
        wall = await client.get(item["wall_url"], headers=_h(admin))
        assert wall.status_code == 200 and wall.headers["content-type"] == "video/mp4"
        out = tmp_path / "out.mp4"
        out.write_bytes(wall.content)
        info = metadata_of(out)
        assert "h264" in info and "location" not in info and "Secret place" not in info
        thumb = await client.get(item["thumb_url"], headers=_h(admin))
        assert thumb.headers["content-type"] == "image/jpeg"

    async def test_large_videos_are_scaled_down_for_the_wall(self, client, admin, jobs, tmp_path):
        res = await upload(client, admin, make_video(tmp_path, seconds=1, size="2560x1440"), "big.mp4", "video/mp4")
        assert res.status_code == 202
        await jobs()
        item = (await client.get("/api/media", headers=_h(admin))).json()[0]
        assert item["status"] == "ready" and (item["width"], item["height"]) == (1920, 1080)

    async def test_videos_that_run_too_long_are_rejected(self, client, admin, monkeypatch, tmp_path):
        monkeypatch.setattr(media_service, "MAX_VIDEO_SECONDS", 1)
        res = await upload(client, admin, make_video(tmp_path, seconds=3), "long.mp4", "video/mp4")
        assert res.status_code == 400
        assert "long" in res.json()["detail"]

    async def test_videos_support_range_requests(self, client, admin, jobs, tmp_path):
        await upload(client, admin, make_video(tmp_path), "clip.mp4", "video/mp4")
        await jobs()
        item = (await client.get("/api/media", headers=_h(admin))).json()[0]
        res = await client.get(item["wall_url"], headers={**_h(admin), "Range": "bytes=0-99"})
        assert res.status_code == 206 and len(res.content) == 100

    async def test_a_video_that_fails_to_convert_is_marked_failed(self, client, admin, jobs, monkeypatch, tmp_path):
        async def broken(*args, **kwargs):
            raise media_service.MediaError("ffmpeg exited with code 1")

        monkeypatch.setattr(media_service, "transcode_video", broken)
        await upload(client, admin, make_video(tmp_path), "clip.mp4", "video/mp4")
        await jobs()
        item = (await client.get("/api/media", headers=_h(admin))).json()[0]
        assert item["status"] == "failed" and "ffmpeg" in item["error"]

    async def test_interrupted_jobs_are_marked_failed_at_startup(self, admin, setup_db):
        from app.models.media import Media

        stuck = Media(family_id="f", kind="video", status="processing", original_name="x.mp4")
        setup_db.add(stuck)
        await setup_db.flush()
        await media_service.fail_interrupted(setup_db)
        assert stuck.status == "failed"


class TestLibrary:
    async def test_list_is_newest_first_and_family_only(self, client, admin, setup_db):
        from app.models.media import Media

        first = (await upload(client, admin, jpeg_with_gps(), "first.jpg")).json()
        second = (await upload(client, admin, png_with_alpha(), "second.png", "image/png")).json()
        setup_db.add(Media(family_id="another-family", kind="photo", status="ready", original_name="theirs.jpg"))
        await setup_db.flush()
        items = (await client.get("/api/media", headers=_h(admin))).json()
        assert [i["id"] for i in items] == [second["id"], first["id"]]

    async def test_another_familys_files_are_not_served(self, client, admin, setup_db):
        from app.models.media import Media

        theirs = Media(family_id="another-family", kind="photo", status="ready", original_name="theirs.jpg")
        setup_db.add(theirs)
        await setup_db.flush()
        assert (await client.get(f"/api/media/{theirs.id}/wall", headers=_h(admin))).status_code == 404
        assert (await client.delete(f"/api/media/{theirs.id}", headers=_h(admin))).status_code == 404

    async def test_unknown_variants_and_items_are_404(self, client, admin):
        item = (await upload(client, admin, png_with_alpha(), "a.png", "image/png")).json()
        assert (await client.get(f"/api/media/{item['id']}/original", headers=_h(admin))).status_code == 404
        assert (await client.get("/api/media/nope/wall", headers=_h(admin))).status_code == 404

    async def test_uploader_or_admin_can_delete_and_files_go(self, client, admin):
        kid = await _member(client, admin, name="Kid")
        sib = await _member(client, admin, name="Sib", pin="2468")
        item = (await upload(client, kid, png_with_alpha(), "art.png", "image/png")).json()
        assert (await client.delete(f"/api/media/{item['id']}", headers=_h(sib))).status_code == 403
        assert (await client.delete(f"/api/media/{item['id']}", headers=_h(kid))).status_code == 200
        assert (await client.get(item["wall_url"], headers=_h(kid))).status_code == 404
        assert not any(p.is_file() for p in media_service.MEDIA_ROOT.rglob("*"))

        other = (await upload(client, kid, png_with_alpha(), "art2.png", "image/png")).json()
        assert (await client.delete(f"/api/media/{other['id']}", headers=_h(admin))).status_code == 200

    async def test_the_old_public_photos_route_is_gone(self, client, admin):
        item = (await upload(client, admin, png_with_alpha(), "a.png", "image/png")).json()
        for f in media_service.MEDIA_ROOT.rglob("wall.jpg"):
            rel = f.relative_to(media_service.MEDIA_ROOT)
            assert (await client.get(f"/photos/media/{rel}")).status_code == 404
        assert item["wall_url"].startswith("/api/media/")


class TestWallAccess:
    async def test_an_unpaired_wall_cannot_read_media(self, client, admin):
        item = (await upload(client, admin, png_with_alpha(), "a.png", "image/png")).json()
        assert (await client.get("/api/wall/media")).status_code == 401
        assert (await client.get(f"/api/wall/media/{item['id']}/wall")).status_code == 401

    async def test_a_paired_wall_reads_ready_family_media(self, client, admin, setup_db):
        from app.models.media import Media

        item = (await upload(client, admin, png_with_alpha(), "a.png", "image/png")).json()
        setup_db.add(Media(family_id="another-family", kind="photo", status="ready", original_name="x.jpg"))
        me = (await client.get("/api/auth/me", headers=_h(admin))).json()
        setup_db.add(Media(family_id=me["family_id"], kind="video", status="processing", original_name="y.mp4"))
        await setup_db.flush()

        wall = await pair_wall(client, admin)
        listed = (await client.get("/api/wall/media", headers=wall)).json()
        assert [i["id"] for i in listed] == [item["id"]]
        assert listed[0]["wall_url"] == f"/api/wall/media/{item['id']}/wall"
        res = await client.get(listed[0]["wall_url"], headers=wall)
        assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"

    async def test_a_wall_cannot_read_another_familys_file(self, client, admin, setup_db):
        from app.models.media import Media

        theirs = Media(family_id="another-family", kind="photo", status="ready", original_name="x.jpg")
        setup_db.add(theirs)
        await setup_db.flush()
        wall = await pair_wall(client, admin)
        assert (await client.get(f"/api/wall/media/{theirs.id}/wall", headers=wall)).status_code == 404
