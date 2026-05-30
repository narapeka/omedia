from __future__ import annotations

from typing import Sequence

from app.domain.match import MatchResult
from app.domain.media import MediaCandidate
from app.domain.tv import TVEpisodeCatalog
from app.engines.match.hint import HintExtractor
from app.engines.plan.tv.planner import TVEpisodePlanner
from app.infra.db.store import Store
from app.infra.http.requester import ProviderRequester
from app.infra.llm.client import LLM_REQUESTER_POLICY, OpenAICompatibleExtractor
from app.infra.tmdb.client import TMDBHttpClient, TMDB_REQUESTER_POLICY
from app.infra.tmdb.metadata import TMDBMetadataService
from app.services.config.values import StartupSettings
from app.services.identify.match import MatchService


class MatchRuntime:
    def __init__(self, settings: StartupSettings, *, store: Store | None = None):
        self.settings = settings
        self.store = store
        self.languages = ("zh-CN", "en-US")
        self._tmdb: TMDBMetadataService | None = None
        self._llm: OpenAICompatibleExtractor | None = None
        self._matcher: MatchService | None = None
        self._tv_episode_planner: TVEpisodePlanner | None = None

    @property
    def tmdb(self) -> TMDBMetadataService:
        if self._tmdb is None:
            providers = self.settings.providers
            tmdb_requester = ProviderRequester(
                name="tmdb",
                rate_limit=providers.tmdb_rate_limit,
                proxy=providers.tmdb_proxy,
                policy=TMDB_REQUESTER_POLICY,
            )
            self._tmdb = TMDBMetadataService(
                TMDBHttpClient(
                    providers.require_tmdb_key(),
                    base_url=providers.tmdb_base_url,
                    requester=tmdb_requester,
                ),
                store=self.store,
            )
        return self._tmdb

    @tmdb.setter
    def tmdb(self, value: TMDBMetadataService) -> None:
        self._tmdb = value
        self._matcher = None

    @property
    def llm(self) -> OpenAICompatibleExtractor:
        if self._llm is None:
            providers = self.settings.providers
            self._llm = OpenAICompatibleExtractor(
                providers.require_llm_key(),
                base_url=providers.llm_base_url,
                model=providers.llm_model,
                requester=ProviderRequester(
                    name="llm",
                    rate_limit=providers.llm_rate_limit,
                    proxy=providers.llm_proxy,
                    policy=LLM_REQUESTER_POLICY,
                ),
            )
        return self._llm

    @property
    def matcher(self) -> MatchService:
        self.settings.providers.require_identify()
        if self._matcher is None:
            self._matcher = MatchService(
                self.tmdb,
                media_name_extractor=HintExtractor(self.settings.organize.extensions),
                llm_extractor=self.llm,
                languages=self.languages,
            )
        return self._matcher

    @property
    def tv_episode_planner(self) -> TVEpisodePlanner:
        if self._tv_episode_planner is None:
            self._tv_episode_planner = TVEpisodePlanner(
                extensions=self.settings.organize.extensions,
                episode_extractor=self,
                episode_catalog_provider=self,
            )
        return self._tv_episode_planner

    def match(self, candidate: MediaCandidate) -> MatchResult:
        return self.matcher.match(candidate)

    def match_batch(self, candidates: Sequence[MediaCandidate]) -> dict[str, MatchResult]:
        return self.matcher.match_batch(
            candidates,
            llm_batch_size=self.settings.providers.llm_batch_size,
        )

    def extract_episodes(
        self,
        *,
        show_name: str,
        filenames: Sequence[str],
        tmdb_context: str = "",
        chunk_size: int = 100,
    ):
        return self.llm.extract_episodes(
            show_name=show_name,
            filenames=filenames,
            tmdb_context=tmdb_context,
            chunk_size=chunk_size,
        )

    def tv_episode_titles(
        self,
        *,
        tmdb_id: int | None,
        season_numbers: Sequence[int],
    ) -> dict[int, dict[int, str]]:
        if not tmdb_id:
            return {}
        return self.tmdb.get_tv_episode_titles(tmdb_id, season_numbers, self.languages)

    def tv_episode_catalog(self, *, tmdb_id: int | None) -> TVEpisodeCatalog:
        if not tmdb_id:
            return TVEpisodeCatalog.empty()
        return self.tmdb.get_tv_episode_catalog(tmdb_id, self.languages)

    def tv_season_years(
        self,
        *,
        tmdb_id: int | None,
        season_numbers: Sequence[int],
    ) -> dict[int, int]:
        if not tmdb_id:
            return {}
        return self.tmdb.get_tv_season_years(tmdb_id, season_numbers, self.languages)

    def clear_tmdb_cache(self) -> int:
        if self._tmdb is not None:
            return self._tmdb.clear_cache()
        return self.store.clear_tmdb_details() if self.store is not None else 0
