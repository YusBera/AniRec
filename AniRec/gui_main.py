"""Side-effect-free PySide6 entry point for the AniRec desktop application."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from .application.pipeline import PipelineOrchestrator
from .errors import AuthError
from .gui.main_window import MainWindow
from .gui.resources import app_icon
from .gui.texts import UI_TEXT
from .gui.theme import ThemeManager
from .infrastructure.logging_config import close_logger, configure_logging
from .infrastructure.csv_storage import CsvStorage
from .infrastructure.mal_client import MALClient
from .metadata import (
    APP_NAME,
    APP_VERSION,
    ORGANIZATION_DOMAIN,
    ORGANIZATION_NAME,
)
from .services import (
    AnimeDataService,
    AnimeGraphService,
    AuthService,
    DataManagementService,
    OnboardingService,
    ProfileService,
    ResultService,
    RecommendationService,
    RecommendationStateService,
    SettingsService,
    TokenStore,
)


SAFE_STARTUP_ERROR = UI_TEXT.startup_error


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the process-wide QApplication and apply central metadata."""
    existing = QApplication.instance()
    application = (
        existing
        if isinstance(existing, QApplication)
        else QApplication(list(argv) if argv is not None else sys.argv)
    )
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setOrganizationDomain(ORGANIZATION_DOMAIN)
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
    application.setWindowIcon(app_icon())
    return application


def present_startup_error(message: str) -> None:
    """Show a stable user-safe startup error without technical details."""
    if QApplication.instance() is not None:
        QMessageBox.critical(None, APP_NAME, message)


def main(
    argv: Sequence[str] | None = None,
    *,
    root_override: str | Path | None = None,
    window_factory: Callable[[], QWidget] | None = None,
    error_presenter: Callable[[str], None] = present_startup_error,
) -> int:
    """Launch one QApplication and return its process exit code."""
    logger: logging.Logger | None = None
    try:
        logger = configure_logging(root_override=root_override, logger_name="AniRec.gui")
        application = create_application(argv)
        theme_manager = ThemeManager(application)
        startup_settings = SettingsService(root_override=root_override).load()
        theme_manager.apply(startup_settings.theme, font_scale=startup_settings.font_scale)
        if window_factory is not None:
            window = window_factory()
        else:
            settings = SettingsService(root_override=root_override)
            tokens = TokenStore(root_override=root_override)
            profiles = ProfileService(
                root_override=root_override,
                mal_client=MALClient(),
                token_store=tokens,
            )
            auth = AuthService(token_store=tokens)

            def access_token_provider() -> str:
                profile = profiles.active_profile()
                if profile is None:
                    raise AuthError("No active profile is available.")
                return auth.get_access_token(profile.profile_id, settings.load())

            orchestrator = PipelineOrchestrator(
                anime_data=AnimeDataService(),
                profiles=profiles,
                recommendations=RecommendationService(),
                storage=CsvStorage(),
                access_token_provider=access_token_provider,
                client_id_provider=lambda: settings.load().client_id or "",
                anime_graph=AnimeGraphService(),
            )
            onboarding = OnboardingService(
                settings=settings,
                profiles=profiles,
                tokens=tokens,
                root_override=root_override,
            )
            window = MainWindow(
                profile_service=profiles,
                result_service=ResultService(root_override=root_override),
                onboarding_service=onboarding,
                auth_service=auth,
                pipeline_orchestrator=orchestrator,
                recommendation_state_service=RecommendationStateService(
                    root_override=root_override
                ),
                settings_service=settings,
                token_store=tokens,
                data_management_service=DataManagementService(
                    root_override=root_override
                ),
                theme_manager=theme_manager,
            )
        window.show()
        logger.info("AniRec GUI started.")
        return application.exec()
    except Exception:
        if logger is not None:
            logger.exception("AniRec GUI startup failed.")
        try:
            error_presenter(SAFE_STARTUP_ERROR)
        except Exception:
            if logger is not None:
                logger.exception("AniRec startup error dialog failed.")
        return 1
    finally:
        if logger is not None:
            close_logger(logger)


if __name__ == "__main__":
    raise SystemExit(main())
