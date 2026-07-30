from dataclasses import dataclass

from ..config import Settings
from ..db import Database
from .analytics import AnalyticsService
from .artifacts import TempArtifactStore
from .auth import AuthService
from .chat_actions import ChatActionService
from .chat_context import ChatContextService
from .connector import ConnectorService
from .curriculum import CurriculumService
from .daily_tasks import DailyTaskService
from .growth import GrowthService
from .notifications import NotificationService
from .radar import RadarService
from .radar_jobs import RadarJobService
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
    radar_jobs: RadarJobService
    chat_context: ChatContextService
    chat_actions: ChatActionService
    curriculum: CurriculumService
    analytics: AnalyticsService

    @classmethod
    def build(cls, database: Database, settings: Settings) -> "ServiceContainer":
        factory = database.session_factory
        auth = AuthService(factory, settings)
        curriculum = CurriculumService(factory)
        analytics = AnalyticsService(factory, curriculum)
        growth = GrowthService(factory, curriculum)
        radar = RadarService(factory)
        provider_settings = SettingsService(factory, auth.cipher)
        daily_tasks = DailyTaskService(settings, growth, radar, provider_settings)
        radar_jobs = RadarJobService(factory, settings, radar, provider_settings)
        chat_context = ChatContextService(factory)
        connector = ConnectorService(factory)
        chat_actions = ChatActionService(factory, daily_tasks, growth, radar, curriculum, connector)
        return cls(
            auth=auth,
            growth=growth,
            radar=radar,
            connector=connector,
            weekly=WeeklyService(factory),
            notifications=NotificationService(settings, factory, auth.cipher),
            settings=provider_settings,
            artifacts=TempArtifactStore(settings.temp_upload_dir, auth.cipher),
            daily_tasks=daily_tasks,
            radar_jobs=radar_jobs,
            chat_context=chat_context,
            chat_actions=chat_actions,
            curriculum=curriculum,
            analytics=analytics,
        )
