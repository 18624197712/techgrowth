from dataclasses import dataclass

from ..config import Settings
from ..db import Database
from .artifacts import TempArtifactStore
from .auth import AuthService
from .connector import ConnectorService
from .daily_tasks import DailyTaskService
from .growth import GrowthService
from .notifications import NotificationService
from .radar import RadarService
from .settings import SettingsService
from .weekly import WeeklyService


@dataclass(slots=True)
class ServiceContainer:
    auth: AuthService
    growth: GrowthService
    radar: RadarService
    connector: ConnectorService
    weekly: WeeklyService
    notifications: NotificationService
    settings: SettingsService
    artifacts: TempArtifactStore
    daily_tasks: DailyTaskService

    @classmethod
    def build(cls, database: Database, settings: Settings) -> "ServiceContainer":
        factory = database.session_factory
        auth = AuthService(factory, settings)
        growth = GrowthService(factory)
        radar = RadarService(factory)
        provider_settings = SettingsService(factory, auth.cipher)
        daily_tasks = DailyTaskService(settings, growth, radar, provider_settings)
        return cls(
            auth=auth,
            growth=growth,
            radar=radar,
            connector=ConnectorService(factory),
            weekly=WeeklyService(factory),
            notifications=NotificationService(settings, factory, auth.cipher),
            settings=provider_settings,
            artifacts=TempArtifactStore(settings.temp_upload_dir, auth.cipher),
            daily_tasks=daily_tasks,
        )
