from pathlib import Path

from techgrowth_api.worker import build_scheduler


def test_worker_registers_all_required_jobs(client, settings) -> None:
    scheduler = build_scheduler(settings, client.app.state.services)

    assert {job.id for job in scheduler.get_jobs()} == {
        "collect-radar",
        "daily-task",
        "weekly-review",
        "cleanup-artifacts",
    }
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "hour='8'" in str(jobs["collect-radar"].trigger)
    assert "minute='0'" in str(jobs["collect-radar"].trigger)
    assert "hour='8'" in str(jobs["daily-task"].trigger)
    assert "minute='10'" in str(jobs["daily-task"].trigger)


def test_worker_compose_healthcheck_tracks_the_worker_process() -> None:
    compose_path = Path(__file__).resolve().parents[3] / "compose.yaml"
    compose = compose_path.read_text(encoding="utf-8")
    worker_service = compose.split("\n  worker:\n", 1)[1].split("\n  db:\n", 1)[0]

    assert 'test: ["CMD", "python", "-c", "import os; os.kill(1, 0)"]' in worker_service


def test_api_image_accepts_a_pypi_mirror_for_production_builds() -> None:
    dockerfile_path = Path(__file__).resolve().parents[1] / "Dockerfile"
    dockerfile = dockerfile_path.read_text(encoding="utf-8")

    assert "ARG PIP_INDEX_URL=https://pypi.org/simple" in dockerfile
