from enum import IntEnum

class ErrorNumber(IntEnum):
    # UNIX error number equivalents (negative values)
    NotPermitted = -1
    NoSuchFile = -2
    NoSuchProcess = -3
    InterruptedSyscall = -4
    InOutError = -5
    NoSuchDeviceOrAddress = -6
    ArgumentListTooLong = -7
    ExecutableFormatError = -8
    BadFileNumber = -9
    NoChildProcess = -10
    TryAgain = -11
    OutOfMemory = -12
    AccessDenied = -13
    BadAddress = -14
    NotABlockDevice = -15
    Busy = -16
    FileExists = -17
    CrossDeviceLink = -18
    NoSuchDevice = -19
    NotDirectory = -20
    IsDirectory = -21
    InvalidArgument = -22
    FileTableOverflow = -23
    TooManyOpenFiles = -24
    NotTypewriter = -25
    TextFileBusy = -26
    FileTooLarge = -27
    NoSpaceLeft = -28
    IllegalSeek = -29
    ReadOnly = -30
    TooManyLinks = -31
    BrokenPipe = -32
    OutOfDomain = -33
    OutOfRange = -34
    DeadlockWouldOccur = -35
    NameTooLong = -36
    NoLocksAvailable = -37
    NotImplemented = -38
    DirectoryNotEmpty = -39
    TooManySymbolicLinks = -40
    NoData = -61
    SeveredLink = -67
    NoSuchExtendedAttribute = NoData
    NotSupported = -252

    # Aaru error numbers (positive values)
    NoError = 0
    HelpRequested = 1
    NothingFound = 2
    AlreadyDumped = 3
    NotVerifiable = 4
    BadSectorsImageNotVerified = 5
    CorrectSectorsImageNotVerified = 6
    BadImageSectorsNotVerified = 7
    BadImageBadSectors = 8
    CorrectSectorsBadImage = 9
    CorrectImageSectorsNotVerified = 10
    CorrectImageBadSectors = 11
    UnexpectedException = 12
    UnexpectedArgumentCount = 13
    MissingArgument = 14
    CannotOpenFile = 15
    EncodingUnknown = 16
    UnrecognizedFormat = 17
    CannotOpenFormat = 18
    InvalidSidecar = 19
    InvalidResume = 20
    FormatNotFound = 21
    TooManyFormats = 22
    UnsupportedMedia = 23
    DataWillBeLost = 24
    CannotCreateFormat = 25
    WriteError = 26
    CannotOpenDevice = 27
    CannotRemoveDatabase = 28
    SectorNotFound = 29
    NotOpened = 30

    # UNIX error number aliases
    EPERM = NotPermitted
    ENOENT = NoSuchFile
    ESRCH = NoSuchProcess
    EINTR = InterruptedSyscall
    EIO = InOutError
    ENXIO = NoSuchDeviceOrAddress
    E2BIG = ArgumentListTooLong
    ENOEXEC = ExecutableFormatError
    EBADF = BadFileNumber
    ECHILD = NoChildProcess
    EAGAIN = TryAgain
    ENOMEM = OutOfMemory
    EACCES = AccessDenied
    EFAULT = BadAddress
    ENOTBLK = NotABlockDevice
    EBUSY = Busy
    EEXIST = FileExists
    EXDEV = CrossDeviceLink
    ENODEV = NoSuchDevice
    ENOTDIR = NotDirectory
    EISDIR = IsDirectory
    EINVAL = InvalidArgument
    ENFILE = FileTableOverflow
    EMFILE = TooManyOpenFiles
    ENOTTY = NotTypewriter
    ETXTBSY = TextFileBusy
    EFBIG = FileTooLarge
    ENOSPC = NoSpaceLeft
    ESPIPE = IllegalSeek
    EROFS = ReadOnly
    EMLINK = TooManyLinks
    EPIPE = BrokenPipe
    EDOM = OutOfDomain
    ERANGE = OutOfRange
    EDEADLK = DeadlockWouldOccur
    ENAMETOOLONG = NameTooLong
    ENOLCK = NoLocksAvailable
    ENOSYS = NotImplemented
    ENOLINK = SeveredLink
    ENOTSUP = NotSupported
    ENOTEMPTY = DirectoryNotEmpty
    ELOOP = TooManySymbolicLinks
    ENOATTR = NoSuchExtendedAttribute
    ENODATA = NoData