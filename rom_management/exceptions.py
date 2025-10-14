from typing import Optional

class HandlerException(Exception):
    """Base exception for handler-related issues"""
    def __init__(self, message: str, menu_class_name: Optional[str] = None):
        """
        Args:
            message (str): Error message
            menu_class_name (Optional[str]): Name of the menu class to show after handling this exception
        """
        super().__init__(message)
        self.menu_class_name = menu_class_name  # Store class name as string

class UserActionRequiredException(HandlerException):
    """Exception that requires user intervention"""
    def __init__(self, message: str, menu_class_name: Optional[str] = None):
        super().__init__(message, menu_class_name)

class SkipCurrentItemException(HandlerException):
    """Exception to skip current item and continue"""
    def __init__(self, message: str):
        super().__init__(message)

class StopProcessingException(HandlerException):
    """Exception to stop all processing"""
    def __init__(self, message: str):
        super().__init__(message)

class CHDAlreadyExistsException(HandlerException):
    """Exception raised when a CHD already exists during processing"""
    def __init__(self, chd_path: str, existing_version: Optional[str] = None,
                 menu_class_name: Optional[str] = None):
        self.chd_path = chd_path
        self.existing_version = existing_version
        super().__init__(f"CHD already exists at {chd_path}", menu_class_name)