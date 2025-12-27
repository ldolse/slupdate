import pytest
from rom_management.processing.models import (
    ProcessStatus,
    ResultObject,
    Action,
    ProgressPayload,
    PendingInputPayload,
    CompletePayload,
    SuccessPayload,
    ErrorPayload,
    BaseProcessingItem,
    MediaProcessingItem,
    PartProcessingItem,
)


class TestProcessStatus:
    """Test ProcessStatus enum values"""

    def test_status_values(self):
        assert ProcessStatus.SUCCESS.value == "success"
        assert ProcessStatus.PENDING_INPUT.value == "pending_input"
        assert ProcessStatus.COMPLETE.value == "complete"
        assert ProcessStatus.ERROR.value == "error"
        assert ProcessStatus.PROGRESS.value == "progress"


class TestAction:
    """Test Action enum values and display names"""

    def test_validation_actions_values(self):
        """Test that validation actions have correct internal values"""
        assert Action.SCAN_MD5.value == "scan_md5"
        assert Action.SKIP.value == "skip"
        assert Action.SKIP_ALL.value == "skip_all"
        assert Action.SCAN_ALL_MD5.value == "scan_all_md5"

    def test_validation_actions_display_names(self):
        """Test that validation actions have human-readable display names"""
        assert Action.SCAN_MD5.display_name == "Scan this archive with MD5 (slow)"
        assert Action.SKIP.display_name == "Skip current item"
        assert Action.SKIP_ALL.display_name == "Skip all remaining items"
        assert Action.SCAN_ALL_MD5.display_name == "Scan all with MD5"

    def test_chd_build_actions_values(self):
        """Test that CHD build actions have correct internal values"""
        assert Action.RETRY.value == "retry"
        assert Action.OVERWRITE.value == "overwrite"
        assert Action.SKIP_EXISTING.value == "skip_existing"

    def test_chd_build_actions_display_names(self):
        """Test that CHD build actions have human-readable display names"""
        assert Action.RETRY.display_name == "Retry current item"
        assert Action.OVERWRITE.display_name == "Overwrite this CHD"
        assert Action.SKIP_EXISTING.display_name == "Skip this CHD"

    def test_common_actions_values(self):
        """Test that common actions have correct internal values"""
        assert Action.STOP.value == "stop"
        assert Action.CONTINUE.value == "continue"

    def test_common_actions_display_names(self):
        """Test that common actions have human-readable display names"""
        assert Action.STOP.display_name == "Stop processing"
        assert Action.CONTINUE.display_name == "Continue"


class TestBaseProcessingItem:
    """Test base processing item class"""

    def test_base_processing_item(self):
        item = BaseProcessingItem("test_item")
        assert item.raw_item == "test_item"
        assert item.display_name == "test_item"

    def test_base_processing_item_with_dict(self):
        test_dict = {"name": "test"}
        item = BaseProcessingItem(test_dict)
        assert item.raw_item == test_dict
        assert item.display_name == str(test_dict)


class TestMediaProcessingItem:
    """Test media processing item class"""

    def test_media_processing_item_display_name_with_dat_entry(self):
        """Mock CDMedia object with dat_game_entry"""
        mock_media = type(
            "MockMedia",
            (),
            {"dat_game_entry": type("MockGameEntry", (), {"name": "Test Game"})()},
        )()

        item = MediaProcessingItem(mock_media)
        assert item.media == mock_media
        assert item.display_name == "Test Game"

    def test_media_processing_item_display_name_without_dat_entry(self):
        """Mock CDMedia object without dat_game_entry"""
        mock_media = type("MockMedia", (), {})()

        item = MediaProcessingItem(mock_media)
        assert item.media == mock_media
        assert item.display_name == str(mock_media)


class TestPartProcessingItem:
    """Test part processing item class"""

    def test_part_processing_item_display_name_with_name(self):
        """Mock Part object with name"""
        mock_part = type("MockPart", (), {"name": "Test Part"})()

        item = PartProcessingItem(mock_part)
        assert item.part == mock_part
        assert item.display_name == "Test Part"

    def test_part_processing_item_display_name_without_name(self):
        """Mock Part object without name"""
        mock_part = type("MockPart", (), {})()

        item = PartProcessingItem(mock_part)
        assert item.part == mock_part
        assert item.display_name == str(mock_part)


class TestResultObjectProgress:
    """Test ResultObject progress creation and helper methods"""

    def test_create_progress(self):
        mock_item = BaseProcessingItem("test")
        result = ResultObject.progress(
            processed=50,
            total=100,
            percentage=50.0,
            message="Processing...",
            failed=2,
            succeeded=48,
        )

        assert result.status == ProcessStatus.PROGRESS
        assert result.payload is not None
        assert isinstance(result.payload, ProgressPayload)
        assert result.payload.processed == 50
        assert result.payload.total == 100
        assert result.payload.percentage == 50.0
        assert result.payload.message == "Processing..."
        assert result.payload.failed == 2
        assert result.payload.succeeded == 48
        assert result.is_progress()

    def test_create_progress_minimal(self):
        result = ResultObject.progress(processed=10, total=20, percentage=50.0)

        assert result.is_progress()
        assert result.payload.message is None
        assert result.payload.failed == 0
        assert result.payload.succeeded == 0


class TestResultObjectPendingInput:
    """Test ResultObject pending input creation"""

    def test_create_pending_input(self):
        mock_item = BaseProcessingItem("test")
        actions = [Action.SCAN_MD5, Action.SKIP, Action.STOP]

        result = ResultObject.pending_input(
            query_id="confirm_scan_md5",
            message="Scan full file?",
            item=mock_item,
            valid_actions=actions,
        )

        assert result.status == ProcessStatus.PENDING_INPUT
        assert isinstance(result.payload, PendingInputPayload)
        assert result.payload.query_id == "confirm_scan_md5"
        assert result.payload.message == "Scan full file?"
        assert result.payload.item == mock_item
        assert result.payload.valid_actions == actions
        assert result.requires_input()

    def test_create_pending_input_with_options_context(self):
        mock_item = BaseProcessingItem("test")
        actions = [Action.OVERWRITE, Action.SKIP_EXISTING, Action.STOP]
        options_context = {"existing_version": "5.0"}

        result = ResultObject.pending_input(
            query_id="chd_already_exists",
            message="CHD already exists",
            item=mock_item,
            valid_actions=actions,
            options_context=options_context,
        )

        assert result.requires_input()
        assert result.payload.options_context == options_context


class TestResultObjectComplete:
    """Test ResultObject complete creation"""

    def test_create_complete(self):
        result = ResultObject.complete(
            total_processed=100, succeeded=95, failed=5, stopped_early=False
        )

        assert result.status == ProcessStatus.COMPLETE
        assert isinstance(result.payload, CompletePayload)
        assert result.payload.total_processed == 100
        assert result.payload.succeeded == 95
        assert result.payload.failed == 5
        assert result.payload.stopped_early is False
        assert result.is_complete()

    def test_create_complete_stopped_early(self):
        result = ResultObject.complete(
            total_processed=50, succeeded=45, failed=0, stopped_early=True
        )

        assert result.is_complete()
        assert result.payload.stopped_early is True

    def test_create_complete_minimal(self):
        result = ResultObject.complete(total_processed=10)

        assert result.is_complete()
        assert result.payload.succeeded == 0
        assert result.payload.failed == 0
        assert result.payload.stopped_early is False


class TestResultObjectSuccess:
    """Test ResultObject success creation"""

    def test_create_success_with_message(self):
        result = ResultObject.success(
            message="Step completed successfully", metadata={"file": "test.zip"}
        )

        assert result.status == ProcessStatus.SUCCESS
        assert isinstance(result.payload, SuccessPayload)
        assert result.payload.message == "Step completed successfully"
        assert result.payload.metadata == {"file": "test.zip"}
        assert result.is_success()

    def test_create_success_minimal(self):
        result = ResultObject.success()

        assert result.is_success()
        assert result.payload.message is None
        assert result.payload.metadata is None


class TestResultObjectError:
    """Test ResultObject error creation"""

    def test_create_error_with_exception(self):
        exception = Exception("Test exception")
        result = ResultObject.error(
            error_type="FileNotFound",
            message="File not found",
            exception=exception,
            context={"path": "/test/path"},
        )

        assert result.status == ProcessStatus.ERROR
        assert isinstance(result.payload, ErrorPayload)
        assert result.payload.error_type == "FileNotFound"
        assert result.payload.message == "File not found"
        assert result.payload.exception == exception
        assert result.payload.context == {"path": "/test/path"}
        assert result.is_error()

    def test_create_error_minimal(self):
        result = ResultObject.error(
            error_type="ValidationError", message="Invalid data"
        )

        assert result.is_error()
        assert result.payload.exception is None
        assert result.payload.context is None


class TestResultObjectHelperMethodsMutuallyExclusive:
    """Ensure each result type is correctly classified by helper methods"""

    def test_all_status_types_mutually_exclusive(self):
        """Verify each result type has exactly one True helper method"""
        success = ResultObject.success()
        pending = ResultObject.pending_input(
            "query", "msg", BaseProcessingItem("item"), [Action.STOP]
        )
        complete = ResultObject.complete(10)
        error = ResultObject.error("Test", "test message")
        progress = ResultObject.progress(5, 10, 50.0)

        assert [
            success.is_success(),
            success.requires_input(),
            success.is_complete(),
            success.is_error(),
            success.is_progress(),
        ].count(True) == 1
        assert [
            pending.is_success(),
            pending.requires_input(),
            pending.is_complete(),
            pending.is_error(),
            pending.is_progress(),
        ].count(True) == 1
        assert [
            complete.is_success(),
            complete.requires_input(),
            complete.is_complete(),
            complete.is_error(),
            complete.is_progress(),
        ].count(True) == 1
        assert [
            error.is_success(),
            error.requires_input(),
            error.is_complete(),
            error.is_error(),
            error.is_progress(),
        ].count(True) == 1
        assert [
            progress.is_success(),
            progress.requires_input(),
            progress.is_complete(),
            progress.is_error(),
            progress.is_progress(),
        ].count(True) == 1
