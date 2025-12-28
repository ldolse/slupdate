from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from media_registry import CDMedia
    from softwarelist import Part
    from rom_management.exceptions import HandlerException


class ProcessStatus(Enum):
    """Status codes for process execution results"""

    SUCCESS = "success"
    PENDING_INPUT = "pending_input"
    COMPLETE = "complete"
    ERROR = "error"
    PROGRESS = "progress"


class Action(Enum):
    """Enumeration of all possible user actions across all processes"""

    def __init__(self, value: str, display_name: str):
        self._value_ = value  # Internal identifier for handle_user_action()
        self.display_name = display_name  # Human-readable for menus

    # Validation actions
    SCAN_MD5 = ("scan_md5", "Scan this archive with MD5 (slow)")
    SKIP = ("skip", "Skip current item")
    SKIP_ALL = ("skip_all", "Skip all remaining items")
    SCAN_ALL_MD5 = ("scan_all_md5", "Scan all with MD5")

    # CHD build actions
    RETRY = ("retry", "Retry current item")
    OVERWRITE = ("overwrite", "Overwrite this CHD")
    SKIP_EXISTING = ("skip_existing", "Skip this CHD")
    SET_OVERWRITE_PREFERENCE = ("set_overwrite_pref", "Always overwrite older CHDs")
    SET_SKIP_PREFERENCE = ("set_skip_pref", "Always skip existing CHDs")

    # Common actions
    STOP = ("stop", "Stop processing")
    CONTINUE = ("continue", "Continue")


@dataclass
class CloneCDConversionParams:
    """Parameters for CloneCD conversion operations"""

    output_format: str  # 'cue' or 'cdrdao'
    preserve_subchannel: bool = True


@dataclass
class LibcryptPatchingParams:
    """Parameters for Libcrypt DRM patching operations"""

    lsd_file_path: str
    patch_options: Optional[dict] = None


@dataclass
class CHDConversionParams:
    """Parameters for CHD conversion operations"""

    chd_path: str
    force_rebuild: bool = False
    compression_level: Optional[int] = None


class BaseProcessingItem(ABC):
    """Base class for all items that can be processed"""

    def __init__(self, item: Any):
        self._item = item

    @property
    def raw_item(self) -> Any:
        """Get the underlying raw item object"""
        return self._item

    @property
    def display_name(self) -> str:
        """Get a human-readable name for this item"""
        return str(self._item)


class MediaProcessingItem(BaseProcessingItem):
    """Processing item for media (CDMedia) objects"""

    def __init__(self, media: "CDMedia"):
        super().__init__(media)
        self._media = media

    @property
    def media(self) -> "CDMedia":
        """Get the CDMedia object"""
        return self._media

    @property
    def display_name(self) -> str:
        if hasattr(self._media, "dat_game_entry") and self._media.dat_game_entry:
            return self._media.dat_game_entry.name
        return str(self._media)


class PartProcessingItem(BaseProcessingItem):
    """Processing item for software Part objects"""

    def __init__(self, part: "Part"):
        super().__init__(part)
        self._part = part

    @property
    def part(self) -> "Part":
        """Get the Part object"""
        return self._part

    @property
    def display_name(self) -> str:
        if hasattr(self._part, "name") and self._part.name:
            return self._part.name
        return str(self._part)


class BasePayload(ABC):
    """Base class for all payload types"""

    pass


@dataclass
class ProgressPayload(BasePayload):
    """Payload for progress updates - automatically continues processing"""

    processed: int
    total: int
    percentage: float
    message: Optional[str] = None
    failed: int = 0
    succeeded: int = 0
    metadata: Optional[dict] = None


@dataclass
class PendingInputPayload(BasePayload):
    """Payload when user input is required"""

    query_id: str  # The key to find the BaseMenu handler
    message: str  # Message to display to user
    item: BaseProcessingItem  # The object being processed
    valid_actions: List[Action]  # List of valid user actions
    options_context: Optional[dict] = None  # Additional context for menu options


@dataclass
class CompletePayload(BasePayload):
    """Payload when process is complete"""

    total_processed: int
    succeeded: int = 0
    failed: int = 0
    stopped_early: bool = False
    metadata: Optional[dict] = None
    destination_menu: Optional[str] = "main_menu"


@dataclass
class SuccessPayload(BasePayload):
    """Payload for successful step completion"""

    message: Optional[str] = None
    metadata: Optional[dict] = None


@dataclass
class ErrorPayload(BasePayload):
    """Payload for errors"""

    error_type: str
    message: str
    exception: Optional[Exception] = None
    context: Optional[dict] = None
    destination_menu: Optional[str] = "main_menu"


@dataclass
class NavigationPayload(BasePayload):
    """Payload for successful navigation from MenuItem execution"""

    target_menu: str
    payload: Optional[dict] = None


@dataclass
class ResultObject:
    """Structured result object returned by all process steps"""

    status: ProcessStatus
    payload: Optional[BasePayload] = None

    def is_success(self) -> bool:
        """Check if the step succeeded without needing user input"""
        return self.status == ProcessStatus.SUCCESS

    def requires_input(self) -> bool:
        """Check if the step requires user interaction"""
        return self.status == ProcessStatus.PENDING_INPUT

    def is_complete(self) -> bool:
        """Check if the entire process is finished"""
        return self.status == ProcessStatus.COMPLETE

    def is_error(self) -> bool:
        """Check if an error occurred"""
        return self.status == ProcessStatus.ERROR

    def is_progress(self) -> bool:
        """Check if this is a progress update"""
        return self.status == ProcessStatus.PROGRESS

    @staticmethod
    def progress(
        processed: int,
        total: int,
        percentage: float,
        message: Optional[str] = None,
        failed: int = 0,
        succeeded: int = 0,
        metadata: Optional[dict] = None,
    ) -> "ResultObject":
        """Create a progress result"""
        return ResultObject(
            status=ProcessStatus.PROGRESS,
            payload=ProgressPayload(
                processed=processed,
                total=total,
                percentage=percentage,
                message=message,
                failed=failed,
                succeeded=succeeded,
                metadata=metadata,
            ),
        )

    @staticmethod
    def pending_input(
        query_id: str,
        message: str,
        item: BaseProcessingItem,
        valid_actions: List[Action],
        options_context: Optional[dict] = None,
    ) -> "ResultObject":
        """Create a result requiring user input"""
        return ResultObject(
            status=ProcessStatus.PENDING_INPUT,
            payload=PendingInputPayload(
                query_id=query_id,
                message=message,
                item=item,
                valid_actions=valid_actions,
                options_context=options_context,
            ),
        )

    @staticmethod
    def complete(
        total_processed: int,
        succeeded: int = 0,
        failed: int = 0,
        stopped_early: bool = False,
        metadata: Optional[dict] = None,
        destination_menu: Optional[str] = "main_menu",
    ) -> "ResultObject":
        """Create a result indicating the process is complete"""
        return ResultObject(
            status=ProcessStatus.COMPLETE,
            payload=CompletePayload(
                total_processed=total_processed,
                succeeded=succeeded,
                failed=failed,
                stopped_early=stopped_early,
                metadata=metadata,
                destination_menu=destination_menu,
            ),
        )

    @staticmethod
    def success(
        message: Optional[str] = None, metadata: Optional[dict] = None
    ) -> "ResultObject":
        """Create a success result"""
        return ResultObject(
            status=ProcessStatus.SUCCESS,
            payload=SuccessPayload(message=message, metadata=metadata),
        )

    @staticmethod
    def error(
        error_type: str,
        message: str,
        exception: Optional[Exception] = None,
        context: Optional[dict] = None,
        destination_menu: Optional[str] = "main_menu",
    ) -> "ResultObject":
        """Create an error result"""
        return ResultObject(
            status=ProcessStatus.ERROR,
            payload=ErrorPayload(
                error_type=error_type,
                message=message,
                exception=exception,
                context=context,
                destination_menu=destination_menu,
            ),
        )
