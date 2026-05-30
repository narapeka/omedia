from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from app.domain.depot import Depot
from app.domain.media import MediaExtensionPolicy, MediaType
from app.domain.origin import Origin
from app.engines.scan.depot import scan_depot_detail_tree, scan_depot_summary
from app.engines.scan.source import scan_ad_hoc_source_summary, scan_origin_summary
from app.engines.scan.types import AdHocSourceScan, DepotDetailScan, DepotSummaryScan, OriginSummaryScan
from app.infra.fs.browse import DirectoryListing, list_directories
from app.services.depot.candidate import sort_depot_candidates_for_read


class InventoryService:
    def __init__(
        self,
        extensions: MediaExtensionPolicy,
        *,
        min_non_subtitle_file_size_bytes: int | None = None,
    ):
        self.extensions = extensions
        self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes

    def origin_summary(self, origin: Origin) -> OriginSummaryScan:
        return scan_origin_summary(
            origin,
            self.extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
        )

    def origin_summaries(self, origins: Sequence[Origin]) -> list[OriginSummaryScan]:
        return [self.origin_summary(origin) for origin in origins]

    def depot_summary(self, depot: Depot) -> DepotSummaryScan:
        return scan_depot_summary(depot, self.extensions)

    def depot_summaries(self, depots: Sequence[Depot]) -> list[DepotSummaryScan]:
        return [self.depot_summary(depot) for depot in depots]

    def depot_detail(self, depot: Depot) -> DepotDetailScan:
        detail = scan_depot_detail_tree(depot, self.extensions)
        return replace(detail, candidates=sort_depot_candidates_for_read(detail.candidates))

    def ad_hoc_source(self, source_root: Path, media_type: MediaType) -> AdHocSourceScan:
        return scan_ad_hoc_source_summary(
            source_root,
            media_type,
            extensions=self.extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
        )

    def browse_directories(self, path: Path | None) -> DirectoryListing:
        return list_directories(path)

