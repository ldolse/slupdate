from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from media_registry import CDMedia
    from softwarelist import Part


class ProcessStatus(Enum):
    """Status codes for process execution results"""

    SUCCESS = "success"
    PENDING_INPUT = "pending_input"
    COMPLETE = "complete"
    ERROR = "error"
    PROGRESS = "progress"
    SKIP = "skip"
    NOT_APPLICABLE = "not_applicable"


class CHDExistingPreference(Enum):
    """Preference for handling existing CHD files during CHD build process.

    Precedence order (highest to lowest): TRUST > OVERWRITE > SKIP
    """

    ASK = "ask"  # Prompt user each time (default)
    TRUST = "trust"  # Trust existing CHD, add to validated_chds
    OVERWRITE = "overwrite"  # Remove existing CHD and rebuild
    SKIP = "skip"  # Skip without validating (don't add to validated_chds)


class Action(Enum):
    """Enumeration of all possible user actions across all processes"""

    def __init__(self, value: str, display_name: str):
        self._value_ = value  # Internal identifier for handle_user_action()
        self.display_name = display_name  # Human-readable for menus

    # Common Actions
    SKIP = ("skip", "Skip current item")
    SKIP_ALL = ("skip_all", "Skip all remaining items")

    # Handler actions (generic, used with category context)
    HANDLE = ("handle", "Handle this item")
    HANDLE_ALL = ("handle_all", "Handle all remaining items")

    # CHD build actions
    TRUST_EXISTING = ("trust_existing", "Trust this existing CHD")
    RETRY = ("retry", "Retry current item")
    OVERWRITE = ("overwrite", "Overwrite this CHD")
    SET_OVERWRITE_PREFERENCE = ("set_overwrite_pref", "Always overwrite older CHDs")
    SET_TRUST_PREFERENCE = ("set_trust_pref", "Always trust existing CHDs")

    # Hash validation actions
    UPDATE = ("update", "Update hash and filename")
    UPDATE_ALL = ("update_all", "Update all remaining items")

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
        self._handler_state = {}  # Handlers store state here
        self._completed_handlers = set()  # Track which handlers have run

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
        self._handler_state = {}  # Handlers store state here
        self._completed_handlers = set()  # Track which handlers have run

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
    category: Optional[str] = None  # Category name for contextual HANDLE/SKIP labels


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

    def is_skip(self) -> bool:
        """Check if this is a skip result"""
        return self.status == ProcessStatus.SKIP

    def is_not_applicable(self) -> bool:
        """Check if this handler is not applicable for this item"""
        return self.status == ProcessStatus.NOT_APPLICABLE

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
        category: Optional[str] = None,
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
                category=category,
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
    def skip(
        message: Optional[str] = None,
        category: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "ResultObject":
        """Create a skip result.

        Args:
            message: Message to display when skipping
            category: Category name for contextual menu labels (e.g., "MD5 hash")
            metadata: Additional metadata
        """
        return ResultObject(
            status=ProcessStatus.SKIP,
            payload=SuccessPayload(message=message, metadata=metadata),
        )

    @staticmethod
    def not_applicable(message: Optional[str] = None) -> "ResultObject":
        """Create a not applicable result - handler not relevant for this item.

        This is used in validate_preconditions() to indicate the handler
        should not be included, without prompting the user.

        Args:
            message: Optional message explaining why handler is not applicable
        """
        return ResultObject(
            status=ProcessStatus.NOT_APPLICABLE,
            payload=SuccessPayload(message=message),
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
