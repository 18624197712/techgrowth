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
