"""MicroPython USB MTP module"""

import os
import struct

import machine
from micropython import const
from usb.device.core import Buffer, Interface

# MTP Constants
_EP_IN_FLAG = const(1 << 7)
_BULK_EP_LEN = const(64)
_INT_EP_LEN = const(28)

# MTP Class Definitions
_MTP_INTERFACE_CLASS = const(0x06)  # Still Image Device
_MTP_INTERFACE_SUBCLASS = const(0x01)
_MTP_INTERFACE_PROTOCOL = const(0x01)  # PTP

# Control transfer stages
_STAGE_SETUP = const(1)
_STAGE_DATA = const(2)
_STAGE_ACK = const(3)

# MTP Container types
_MTP_CONTAINER_TYPE_COMMAND = const(1)
_MTP_CONTAINER_TYPE_DATA = const(2)
_MTP_CONTAINER_TYPE_RESPONSE = const(3)

# MTP Response codes Table F.1
_MTP_RESP_OK = const(0x2001)
_MTP_RESP_INVALID_OPERATION = const(0x2002)
_MTP_RESP_PARAMETER_NOT_SUPPORTED = const(0x2006)
_MTP_RESP_INVALID_STORAGE_ID = const(0x2008)
_MTP_RESP_INVALID_OBJECT_HANDLE = const(0x2009)
_MTP_RESP_SPECIFICATION_BY_FORMAT_UNSUPPORTED = const(0x2014)
_MTP_RESP_NO_VALID_OBJECT_INFO = const(0x2015)
_MTP_RESP_INVALID_PARENT_OBJECT = const(0x201A)
_MTP_RESP_INVALID_PARAMETER = const(0x201D)
_MTP_RESP_INVALID_DATASET = const(0xA806)
_MTP_RESP_SPECIFICATION_BY_GROUP_NOT_SUPPORTED = const(0xA807)
_MTP_RESP_SPECIFICATION_BY_DEPTH_UNSUPPORTED = const(0xA808)

# Operation codes
# Appendix D, Table D.1
_MTP_OP_GET_DEVICE_INFO = 0x1001
_MTP_OP_OPEN_SESSION = 0x1002
_MTP_OP_CLOSE_SESSION = 0x1003
_MTP_OP_GET_STORAGE_IDS = 0x1004
_MTP_OP_GET_STORAGE_INFO = 0x1005
# _MTP_OP_GET_NUM_OBJECTS = 0x1006
_MTP_OP_GET_OBJECT_HANDLES = 0x1007
_MTP_OP_GET_OBJECT_INFO = 0x1008
_MTP_OP_GET_OBJECT = 0x1009
_MTP_OP_DELETE_OBJECT = 0x100B
_MTP_OP_SEND_OBJECT_INFO = 0x100C
_MTP_OP_SEND_OBJECT = 0x100D
_MTP_OP_RESET_DEVICE = 0x1010
_MTP_OP_GET_DEVICE_PROP_DESC = 0x1014
_MTP_OP_GET_DEVICE_PROP_VALUE = 0x1015
_MTP_OP_SET_DEVICE_PROP_VALUE = 0x1016
_MTP_OP_MOVE_OBJECT = 0x1019
_MTP_OP_COPY_OBJECT = 0x101A
_MTP_OP_GET_OBJECT_PROP_DESC = 0x9802
_MTP_OP_GET_OBJECT_PROP_VALUE = 0x9803
_MTP_OP_SET_OBJECT_PROP_VALUE = 0x9804
_MTP_OP_GET_OBJECT_PROP_LIST = 0x9805

# Event codes
# Appendix G, Table G.1
_MTP_EVENT_UNDEFINED = 0x4000
# _MTP_EVENT_CANCEL_TRANSACTION = 0x4001  # Don't know how to support this yet
_MTP_EVENT_OBJECT_ADDED = 0x4002
_MTP_EVENT_OBJECT_REMOVED = 0x4003
_MTP_EVENT_ = 0x4003
_MTP_EVENT_DEVICE_PROP_CHANGED = 0x4006
_MTP_EVENT_OBJECT_INFO_CHANGED = 0x4007


# Device Property codes
# Apendix C, Table C.1
_MTP_DEVICE_PROP_UNDEFINED = 0x5000
_MTP_DEVICE_PROP_SYNCHRONIZATION_PARTNER = 0xD401
_MTP_DEVICE_PROP_DEVICE_FRIENDLY_NAME = 0xD402
_MTP_DEVICE_PROP_PERCEIVED_DEVICE_TYPE = 0xD407

STORAGE_ID = 0x00010001

# Supported formats
_MTP_OBJECT_FORMAT_UNIDENTIFIED = const(0x3000)
_MTP_OBJECT_FORMAT_ASSOCIATION = const(0x3001)
_MTP_OBJECT_FORMAT_SCRIPT = const(0x3002)
_MTP_OBJECT_FORMAT_TEXT = const(0x3004)
_MTP_OBJECT_FORMAT_UNDEFINED_IMAGE = const(0x3800)
_MTP_OBJECT_FORMAT_JPEG = const(0x3801)
_MTP_OBJECT_FORMAT_BMP = const(0x3804)
_MTP_OBJECT_FORMAT_GIF = const(0x3807)
_MTP_OBJECT_FORMAT_PNG = const(0x380B)

_MTP_SUPPORTED_OBJECT_FORMATS = [
    # Appendix A. Table A.1
    _MTP_OBJECT_FORMAT_UNIDENTIFIED,
    _MTP_OBJECT_FORMAT_ASSOCIATION,
    _MTP_OBJECT_FORMAT_SCRIPT,
    _MTP_OBJECT_FORMAT_TEXT,
    _MTP_OBJECT_FORMAT_UNDEFINED_IMAGE,
    _MTP_OBJECT_FORMAT_JPEG,
    _MTP_OBJECT_FORMAT_BMP,
    _MTP_OBJECT_FORMAT_GIF,
    _MTP_OBJECT_FORMAT_PNG,
]

# B.1
_MTP_OBJECT_PROP_STORAGE_ID = const(0xDC01)
_MTP_OBJECT_PROP_OBJECT_FORMAT = const(0xDC02)
_MTP_OBJECT_PROP_PROTECTION_STATUS = const(0xDC03)
_MTP_OBJECT_PROP_OBJECT_SIZE = const(0xDC04)
_MTP_OBJECT_PROP_ASSOCIATION_TYPE = const(0xDC05)
_MTP_OBJECT_PROP_OBJECT_FILE_NAME = const(0xDC07)
_MTP_OBJECT_PROP_PARENT_OBJECT = const(0xDC0B)
_MTP_OBJECT_PROP_PERSISTENT_UNIQUE_OBJECT_IDENTIFIER = const(0xDC41)
_MTP_OBJECT_PROP_NAME = const(0xDC44)
_MTP_SUPPORTED_OBJECT_PROPERTIES = [
    _MTP_OBJECT_PROP_STORAGE_ID,
    _MTP_OBJECT_PROP_OBJECT_FORMAT,
    _MTP_OBJECT_PROP_PROTECTION_STATUS,
    _MTP_OBJECT_PROP_OBJECT_SIZE,
    _MTP_OBJECT_PROP_ASSOCIATION_TYPE,
    _MTP_OBJECT_PROP_OBJECT_FILE_NAME,
    _MTP_OBJECT_PROP_PARENT_OBJECT,
    _MTP_OBJECT_PROP_PERSISTENT_UNIQUE_OBJECT_IDENTIFIER,
    _MTP_OBJECT_PROP_NAME,
]

# Datatypes: 3.2.1
_MTP_DATATYPE_UINT16 = const(0x0004)
_MTP_DATATYPE_UINT32 = const(0x0006)
_MTP_DATATYPE_UINT128 = const(0x000A)
_MTP_DATATYPE_STR = const(0xFFFF)

_MTP_STRUCT_OBJECT_INFO = "<IHHIHIIIIIIIHII"


def _encode_string(string: str) -> bytes:
    # Max len (including null terminator) is 255
    if len(string) > 254:
        string = string[:255]
    num_chars = struct.pack("<B", len(string) + (1 if len(string) > 0 else 0))
    encoded = num_chars
    for c in string:
        encoded += (c.encode() + b"\0")[:2]
    if len(string) > 0:
        encoded += b"\0\0"
    return encoded


def _decode_string(data: bytes) -> str:
    if len(data) < 1:
        return None
    strlen = struct.unpack("<B", data)[0]
    string = ""
    for c in data[1:(strlen*2):2]:
        string += c.decode()
    return string


def _encode_array(typecode: str, array: list):
    encoded = struct.pack("<I", len(array))
    # Iterate over array, in case each item is actually multiple
    for item in array:
        encoded += struct.pack(f"<{typecode}", item)
    return encoded


class FsObject:
    def __init__(self, basename, parent_path, parent_handle, size, handle, isdir):
        print(basename, parent_path, parent_handle, size, handle, isdir)
        self.basename: str = basename
        self.parent_path: str = parent_path
        self.parent_handle: int = parent_handle  # uint32
        self.size: int = size  # uint32
        self.handle: int = handle  # uint32
        self.format_code: int = 0
        self.isdir = isdir
        self.full_path = (
            self.parent_path + ("/" if self.parent_path != "/" else "") + self.basename
        )
        print(self.full_path)

        parts = basename.split(".", 1)
        if isdir:
            self.format_code = _MTP_OBJECT_FORMAT_ASSOCIATION
        elif len(parts) == 1:
            self.format_code = _MTP_OBJECT_FORMAT_UNIDENTIFIED
        elif parts[1] == "py":
            self.format_code = _MTP_OBJECT_FORMAT_TEXT
        elif parts[1] == "pyc":
            self.format_code = _MTP_OBJECT_FORMAT_SCRIPT
        elif parts[1] == "jpg" or parts[1] == "jpeg":
            self.format_code = _MTP_OBJECT_FORMAT_JPEG
        elif parts[1] == "bmp":
            self.format_code = _MTP_OBJECT_FORMAT_BMP
        elif parts[1] == "gif":
            self.format_code = _MTP_OBJECT_FORMAT_GIF
        elif parts[1] == "png":
            self.format_code = _MTP_OBJECT_FORMAT_PNG
        else:
            self.format_code = _MTP_OBJECT_FORMAT_UNIDENTIFIED

    def get_property(self, prop_code: int) -> tuple[int, bytes]:
        if prop_code == _MTP_OBJECT_PROP_STORAGE_ID:
            return _MTP_DATATYPE_UINT32, struct.pack("<I", STORAGE_ID)
        elif prop_code == _MTP_OBJECT_PROP_OBJECT_FORMAT:
            return _MTP_DATATYPE_UINT16, struct.pack("<H", self.format_code)
        elif prop_code == _MTP_OBJECT_PROP_PROTECTION_STATUS:
            return _MTP_DATATYPE_UINT16, struct.pack("<H", 0)
        elif prop_code == _MTP_OBJECT_PROP_OBJECT_SIZE:
            return _MTP_DATATYPE_UINT32, struct.pack("<I", self.size)
        elif prop_code == _MTP_OBJECT_PROP_ASSOCIATION_TYPE:
            if self.isdir:
                association_type = 0x0001
            else:
                association_type = 0x0000
            return _MTP_DATATYPE_UINT16, struct.pack("<H", association_type)
        elif prop_code == _MTP_OBJECT_PROP_OBJECT_FILE_NAME:
            return _MTP_DATATYPE_STR, _encode_string(self.basename)
        elif prop_code == _MTP_OBJECT_PROP_PARENT_OBJECT:
            return _MTP_DATATYPE_UINT32, struct.pack("<I", self.parent_handle)
        elif prop_code == _MTP_OBJECT_PROP_PERSISTENT_UNIQUE_OBJECT_IDENTIFIER:
            return _MTP_DATATYPE_UINT128, struct.pack("<16I", hash(self.full_path))
        elif prop_code == _MTP_OBJECT_PROP_NAME:
            return _MTP_DATATYPE_STR, _encode_string(self.basename)
        else:
            return 0, 0


class ObjectHandles:
    def __init__(self):
        # Don't need the key:value lookup of a dict. Not hashable probably, so can't use set.
        self.objects: list[FsObject] = []

    def reset(self):
        del self.objects[:-1]

    def add(self, dirname: str, basename: str, size: int, isdir: bool):
        full_path = dirname + ("/" if dirname != "/" else "") + basename
        if any(full_path == o.full_path for o in self.objects):
            return
        if dirname == "/":
            parent_handle = 0xFFFFFFFF
        else:
            parent_handle = self.get_handle(dirname)
        handle = len(self.objects) + 1
        self.objects.append(
            FsObject(basename, dirname, parent_handle, size, handle, isdir)
        )

    def get_children(self, handle: int = 0, path: str = "") -> list[FsObject]:
        children = []
        for obj in self.objects:
            if (handle and handle == obj.parent_handle) or (
                path and path == obj.parent_path
            ):
                children.append(obj)
        return children

    def get_children_handles(self, handle: int) -> list[int]:
        if handle == 0x00000000:  # Get all
            return [o.handle for o in self.objects]
        return [o.handle for o in self.objects if o.parent_handle == handle]

    def get(self, handle: int) -> FsObject:
        objs = [o for o in self.objects if o.handle == handle]
        if len(objs) == 1:
            return objs[0]
        return None

    def get_handle(self, full_path: str) -> int:
        objs = [o for o in self.objects if o.full_path == full_path]
        if len(objs) == 1:
            return objs[0].handle
        return None


class MTPInterface(Interface):
    """
    USB MTP (Media Transfer Protocol) interface.
    Implements the Picture Transfer Protocol (PTP) device class.
    """

    def __init__(self, mtp_handler=None):
        """
        Args:
            mtp_handler: Object with methods like handle_command(container)
                         that returns (response_container, data_payload)
        """
        Interface.__init__(self)
        self.mtp_handler = mtp_handler

        # Endpoint numbers (will be assigned during desc_cfg)
        self.ep_out = None
        self.ep_in = None
        self.ev_ep_in = None

        # Buffers for bulk transfers
        # self.tx_buf = Buffer(2048)  # Response/data transmit buffer
        self.rx_buf = Buffer(2048)  # Command receive buffer

        # Pending response state
        self.pending_response = None
        self.pending_data = None
        # For sending files back
        self.response_filename = None
        self.pending_file = None

        self.pending_rx_object = None

    def desc_cfg(self, desc, itf_num, ep_num, strs):
        """
        Add MTP interface descriptor to the configuration.

        Called by USBDevice framework to add descriptors.
        """
        # Single interface, no IAD needed
        desc.interface(
            itf_num,
            3,  # bNumEndpoints: 2 (bulk IN, bulk OUT, interrupt IN)
            _MTP_INTERFACE_CLASS,
            _MTP_INTERFACE_SUBCLASS,
            _MTP_INTERFACE_PROTOCOL,
            iInterface=len(strs),
        )

        # Bulk OUT endpoint (device receives commands from host)
        self.ep_out = ep_num
        desc.endpoint(self.ep_out, "bulk", _BULK_EP_LEN, 0)

        # Bulk IN endpoint (device sends responses/data to host)
        self.ep_in = ep_num | _EP_IN_FLAG
        desc.endpoint(self.ep_in, "bulk", _BULK_EP_LEN, 0)

        # Interrupt IN endpoint (device sends events to host)
        self.ev_ep_in = (ep_num + 1) | _EP_IN_FLAG
        desc.endpoint(self.ev_ep_in, "interrupt", _INT_EP_LEN, 6)

        strs.append("MTP")

    def num_itfs(self):
        """Number of interfaces in this descriptor group."""
        return 1

    def num_eps(self):
        """Number of endpoints (after masking _EP_IN_FLAG)."""
        return 3

    def on_open(self):
        """Called when host opens this interface."""
        super().on_open()
        # Start listening for incoming commands
        self._recv_cmd()

    def on_interface_control_xfer(self, stage, request):
        """
        Handle class-specific control transfers.
        MTP typically doesn't use control transfers, only bulk.
        """
        # Not used for MTP — all data via bulk endpoints
        return False

    def _recv_cmd(self):
        """Submit a transfer to receive an MTP command from the host."""
        if (
            self.is_open()
            and not self.xfer_pending(self.ep_out)
            and self.rx_buf.writable() >= _BULK_EP_LEN
        ):
            self.submit_xfer(
                self.ep_out,
                self.rx_buf.pend_write(_BULK_EP_LEN),
                self._recv_cb,
            )

    def _recv_cb(self, ep, res, num_bytes):
        """Callback when command data arrives."""
        if res == 0 and num_bytes > 0:
            self.rx_buf.finish_write(num_bytes)

            # Parse and dispatch the MTP command
            data = bytes(self.rx_buf.pend_read())
            self._process_command(data)
            self.rx_buf.finish_read(num_bytes)

            # Continue listening
            self._recv_cmd()

    def _process_command(self, data):
        """
        Parse incoming MTP container and dispatch to handler.

        Args:
            data: Raw bytes from bulk endpoint
        """
        if len(data) < 12:
            return  # Invalid container header

        # Parse MTP container header
        length, container_type, code, txn_id = struct.unpack("<IHHI", data[:12])
        payload = data[12:length] if len(data) > 12 else b""

        container = {
            "type": container_type,
            "code": code,
            "txn_id": txn_id,
            "payload": payload,
        }

        # Dispatch to handler
        if self.mtp_handler:
            response, response_data, response_filename = (
                self.mtp_handler.handle_command(container)
            )
            self.pending_response = response
            self.pending_data = response_data
            self.response_filename = response_filename
            self._send_response(txn_id)

    def _send_response(self, txn_id):
        """Submit a transfer to send response to the host."""
        if (
            self.is_open()
            and not self.xfer_pending(self.ep_in)
            and self.pending_response
        ):
            # Priority: data first (if pending), then response
            if self.pending_data is not None:
                self.submit_xfer(
                    self.ep_in,
                    self.pending_data,  # Raw bytes, NO container
                    self._send_data_cb,
                )
            # Send a file if prepared
            elif self.response_filename is not None:
                file_size = os.stat(self.response_filename)[6]  # size in bytes
                data_length = 12 + file_size
                data_header = struct.pack(
                    "<IHHI",
                    data_length,
                    _MTP_CONTAINER_TYPE_DATA,
                    _MTP_OP_GET_OBJECT,
                    txn_id,
                )
                self.pending_file = open(self.response_filename, "rb")  # noqa: SIM115
                bytes_read = self.pending_file.read(
                    _BULK_EP_LEN - 12
                )  # Max bulk transfer minus header
                first_bytes = data_header + bytes_read
                if len(first_bytes) == _BULK_EP_LEN:
                    cb = self._send_file_cb
                else:
                    cb = self._send_file_done_cb
                self.submit_xfer(
                    self.ep_in,
                    first_bytes,
                    cb,
                )
            elif self.pending_response is not None:
                self.submit_xfer(
                    self.ep_in,
                    self.pending_response,  # Response container header
                    self._send_response_cb,
                )

    def _send_response_cb(self, ep, res, num_bytes):
        """Callback when response sent."""
        if res == 0:
            self.pending_response = None
        else:
            print(f"Prev xfer failed: res={res}")

        self._recv_cmd()  # Resume listening for commands

    def _send_data_cb(self, ep, res, num_bytes):
        """Data sent — now queue response."""

        if res != 0:
            print(f"Data xfer failed: res={res}")
            self._recv_cmd()
            return

        print(f"Data transfer complete: {num_bytes} bytes")
        self.pending_data = None

        # Only now queue the response
        if self.pending_response is not None:
            print("Queueing response container")
            self.submit_xfer(
                self.ep_in,
                self.pending_response,
                self._send_response_cb,
            )
        else:
            self._recv_cmd()

    def _send_file_cb(self, ep, res, num_bytes):
        """Reads the next chunk of file and transmits it"""
        if res != 0:
            print(f"File xfer failed: res={res}")
            self.pending_file.close()
            self.pending_file = None
            self.response_filename = None
            self._recv_cmd()
            return

        print(f"Sent partial file: {num_bytes} bytes")
        if (
            self.is_open()
            and not self.xfer_pending(self.ep_in)
            and self.pending_file is not None
        ):
            next_bytes = self.pending_file.read(_BULK_EP_LEN)
            if (
                len(next_bytes) == _BULK_EP_LEN
            ):  # If sent everything, there must be more
                cb = self._send_file_cb
            else:
                cb = self._send_file_done_cb
            self.submit_xfer(
                self.ep_in,
                next_bytes,
                cb,
            )

    def _send_file_done_cb(self, ep, res, num_bytes):
        if self.pending_file:
            self.pending_file.close()
            self.pending_file = None
            print(f"Sent remaining file: {num_bytes} bytes")
            print(f"File transfer  complete: {self.response_filename} bytes")
            self.response_filename = None
        if (
            self.is_open()
            and not self.xfer_pending(self.ep_in)
            and self.pending_response is not None
        ):
            self.submit_xfer(
                self.ep_in,
                self.pending_response,  # Response container header
                self._send_response_cb,
            )


class MTPHandler:
    """Implements MTP command logic."""

    def __init__(self):
        self.session_id = None
        self.object_handles = ObjectHandles()

    def handle_command(self, container):
        """
        Process an MTP command.

        Returns:
            (response_container_bytes, response_data_bytes or None)
        """
        code = container["code"]
        txn_id = container["txn_id"]
        payload = container["payload"]

        if code == _MTP_OP_GET_DEVICE_INFO:
            return self._handle_get_device_info(txn_id)
        elif code == _MTP_OP_OPEN_SESSION:
            return self._handle_open_session(txn_id, payload)
        elif code == _MTP_OP_CLOSE_SESSION:
            return self._handle_close_session(txn_id)
        elif code == _MTP_OP_GET_STORAGE_IDS:
            return self._handle_get_storage_ids(txn_id)
        elif code == _MTP_OP_GET_STORAGE_INFO:
            return self._handle_get_storage_info(txn_id, payload)
        # _MTP_OP_GET_NUM_OBJECTS
        elif code == _MTP_OP_GET_OBJECT_HANDLES:
            return self._handle_get_object_handles(txn_id, payload)
        elif code == _MTP_OP_GET_OBJECT_INFO:
            return self._handle_get_object_info(txn_id, payload)
        elif code == _MTP_OP_GET_OBJECT_PROP_LIST:
            return self._handle_get_object_prop_list(txn_id, payload)
        elif code == _MTP_OP_GET_OBJECT:
            return self._handle_get_object(txn_id, payload)
        elif code == _MTP_OP_SEND_OBJECT_INFO:
            return self._handle_send_object_info(txn_id, payload)
        elif code == _MTP_OP_SEND_OBJECT:
            return self._handle_send_object(txn_id, payload)
        # _MTP_OP_RESET_DEVICE
        # _MTP_OP_MOVE_OBJECT
        # _MTP_OP_COPY_OBJECT
        else:
            # Unknown operation
            return self._build_response(code, _MTP_RESP_INVALID_OPERATION, txn_id)

    def _build_response(
        self,
        code,
        resp_code,
        txn_id,
        params=None,
        data: bytes | None = None,
        filename: str | None = None,
    ):
        """Build MTP response container."""
        payload = b""
        if params:
            payload = struct.pack("<" + "I" * len(params), *params)

        length = 12 + len(payload)
        resp_header = struct.pack(
            "<IHHI", length, _MTP_CONTAINER_TYPE_RESPONSE, resp_code, txn_id
        )

        if data:
            data_length = 12 + len(data)
            data_header = struct.pack(
                "<IHHI", data_length, _MTP_CONTAINER_TYPE_DATA, code, txn_id
            )
            resp_data = data_header + data
        else:
            resp_data = None

        return resp_header + payload, resp_data, filename

    def _handle_get_device_info(self, txn_id):
        """Minimal device info response."""
        # 5.1.1 DeviceInfo Dataset
        device_info_dataset = b""
        standard_version = struct.pack("<H", 100)  # 1.00
        mtp_vendor_extension_id = struct.pack("<I", 0xFFFFFFFF)
        mtp_version = struct.pack(
            "<H", 0x0064
        )  # In hundreths. PDF is v1.1. Phone uses 0x0064
        mtp_extensions = _encode_string("")  # TODO: Fill in
        functional_mode = struct.pack("<H", 0x0000)  # Standard mode
        operations_supported = _encode_array(
            "H",
            [
                # Appendix D, Table D.1
                _MTP_OP_GET_DEVICE_INFO,
                _MTP_OP_OPEN_SESSION,
                _MTP_OP_CLOSE_SESSION,
                _MTP_OP_GET_STORAGE_IDS,
                _MTP_OP_GET_STORAGE_INFO,
                # _MTP_OP_GET_NUM_OBJECTS,
                _MTP_OP_GET_OBJECT_HANDLES,
                _MTP_OP_GET_OBJECT_INFO,
                _MTP_OP_GET_OBJECT,
                # _MTP_OP_DELETE_OBJECT,
                # _MTP_OP_GET_OBJECT_PROP_DESC,
                _MTP_OP_SEND_OBJECT_INFO,
                _MTP_OP_SEND_OBJECT,
                # _MTP_OP_RESET_DEVICE,
                # _MTP_OP_GET_DEVICE_PROP_DESC,
                # _MTP_OP_GET_DEVICE_PROP_VALUE,
                # _MTP_OP_SET_DEVICE_PROP_VALUE,
                # _MTP_OP_MOVE_OBJECT,
                # _MTP_OP_COPY_OBJECT,
                # _MTP_OP_GET_OBJECT_PROP_VALUE,
                # _MTP_OP_SET_OBJECT_PROP_VALUE,
                _MTP_OP_GET_OBJECT_PROP_LIST,
            ],
        )
        events_supported = _encode_array(
            "H",
            [
                _MTP_EVENT_OBJECT_ADDED,
                _MTP_EVENT_OBJECT_REMOVED,
            ],
        )
        device_properties_supported = _encode_array("H", [_MTP_DEVICE_PROP_UNDEFINED])
        capture_formats = _encode_array("H", [])
        playback_formats = _encode_array("H", _MTP_SUPPORTED_OBJECT_FORMATS)
        manufacturer = _encode_string("")
        model = _encode_string("")
        device_version = _encode_string("")
        base_id = "".join([hex(b)[2:4].upper() for b in machine.unique_id()])
        serial_number = _encode_string(
            "0" * (32 - len(base_id)) + base_id
        )  # must be 32-char hex string
        device_info_dataset = device_info_dataset + (
            standard_version
            + mtp_vendor_extension_id
            + mtp_version
            + mtp_extensions
            + functional_mode
            + operations_supported
            + events_supported
            + device_properties_supported
            + capture_formats
            + playback_formats
            + manufacturer
            + model
            + device_version
            + serial_number
        )
        return self._build_response(
            _MTP_OP_GET_DEVICE_INFO, _MTP_RESP_OK, txn_id, data=device_info_dataset
        )

    def _handle_open_session(self, txn_id, payload):
        """Initialize session."""
        self._scan_fs("/")
        if len(payload) >= 4:
            self.session_id = struct.unpack("<I", payload[:4])[0]
        return self._build_response(_MTP_OP_OPEN_SESSION, _MTP_RESP_OK, txn_id)

    def _handle_close_session(self, txn_id):
        self.object_handles.reset()
        return self._build_response(_MTP_OP_CLOSE_SESSION, _MTP_RESP_OK, txn_id)

    def _handle_get_storage_ids(self, txn_id):
        """Return storage IDs."""
        # 5.2.1 Storage IDs
        storage_ids = _encode_array("I", [STORAGE_ID])
        return self._build_response(
            _MTP_OP_GET_STORAGE_IDS, _MTP_RESP_OK, txn_id, data=storage_ids
        )

    def _handle_get_storage_info(self, txn_id, payload):
        if len(payload) >= 4:
            storage_id = struct.unpack("<I", payload[:4])[0]
        if storage_id != STORAGE_ID:
            return self._build_response(
                _MTP_OP_GET_STORAGE_IDS, _MTP_RESP_INVALID_STORAGE_ID, txn_id
            )

        # 5.2.2 StorageInfo Dataset Description
        storage_type = struct.pack("<H", 0x0003)  # Fixed RAM
        filesystem_type = struct.pack("<H", 0x0002)  # Generic hierarchical
        access_capability = struct.pack("<H", 0x0000)  # Read-write
        bsize, frsize, blocks, bfree, _, _, _, _, _, _ = os.statvfs("/")
        max_capacity = struct.pack("<Q", frsize * blocks)
        free_space = struct.pack("<Q", bfree * bsize)
        free_objects = struct.pack("<Q", 0xFFFFFFFF)  # Unused field
        storage_description = _encode_string("Micropython")
        volume_identifier = _encode_string(
            "".join([hex(b)[2:4] for b in machine.unique_id()])
        )

        storage_info = (
            storage_type
            + filesystem_type
            + access_capability
            + max_capacity
            + free_space
            + free_objects
            + storage_description
            + volume_identifier
        )

        return self._build_response(
            _MTP_OP_GET_STORAGE_INFO, _MTP_RESP_OK, txn_id, data=storage_info
        )

    def _handle_get_object_handles(self, txn_id, payload):
        """Return object handles"""
        # D.2.7 GetObjectHandles

        if len(payload) >= 12:
            storage_id, object_format_code, parent_id = struct.unpack(
                "<III", payload[0:12]
            )
        else:
            return self._build_response(
                _MTP_OP_GET_OBJECT_HANDLES, _MTP_RESP_INVALID_PARAMETER, txn_id
            )

        if storage_id != STORAGE_ID:
            self._build_response(
                _MTP_OP_GET_OBJECT_HANDLES, _MTP_RESP_INVALID_STORAGE_ID, txn_id
            )
        if object_format_code != 0x00000000:
            # Don't support filtering by format code
            # TODO eventually support this?
            return self._build_response(
                _MTP_OP_GET_OBJECT_HANDLES,
                _MTP_RESP_SPECIFICATION_BY_FORMAT_UNSUPPORTED,
                txn_id,
            )
        self._scan_fs("/")
        if parent_id != 0xFFFFFFFF and self.object_handles.get(parent_id) is None:
            return self._build_response(
                _MTP_OP_GET_OBJECT_HANDLES, _MTP_RESP_INVALID_OBJECT_HANDLE, txn_id
            )
        handles = self.object_handles.get_children_handles(parent_id)
        data = _encode_array("I", handles)

        return self._build_response(
            _MTP_OP_GET_OBJECT_HANDLES, _MTP_RESP_OK, txn_id, data=data
        )

    def _scan_fs(self, path: str):
        """Scan virtual FS and assign storage ID to all files and directories."""
        for file_info in os.ilistdir(path):
            filename, filetype, _, size = file_info
            full_path = path + ("/" if path != "/" else "") + filename
            isdir = filetype == 0x4000  # directory
            self.object_handles.add(path, filename, size, isdir)
            if isdir:
                self._scan_fs(full_path)

    def _handle_get_object_info(self, txn_id, payload):
        # D.2.8
        if len(payload) >= 4:
            object_handle = struct.unpack("<I", payload[:4])[0]
        object = self.object_handles.get(object_handle)
        if object is None:
            return self._build_response(
                _MTP_OP_GET_STORAGE_IDS, _MTP_RESP_INVALID_OBJECT_HANDLE, txn_id
            )

        # 5.3.1 ObjectInfo Dataset Description
        object_info = struct.pack(
            _MTP_STRUCT_OBJECT_INFO,
            STORAGE_ID,
            object.format_code,  # ObjectFormatCode
            0x0000,  # Protection Status - Unprotected
            object.size,  # Compressed Size
            0x0000,  # Thumb Format
            0x00000000,  # Thumb Compressed Size
            0x00000000,  # Thumb Pix Width
            0x00000000,  # Thumb Pix Height
            0x00000000,  # Image Pix Width
            0x00000000,  # Image Pix Height
            0x00000000,  # Image Bit Depth
            object.parent_handle,  # Parent Object
            0x0001 if object.isdir else 0x0000,  # Association Type
            0x00000000,  # Association Description
            0x0000000,  # Sequence Number
        ) + (
            _encode_string(object.basename)  # Filename
            + _encode_string("")  # Date Created
            + _encode_string("")  # Date Modified
            + _encode_string("")
        )  # Keywords

        return self._build_response(
            _MTP_OP_GET_OBJECT_INFO, _MTP_RESP_OK, txn_id, data=object_info
        )

    def _handle_get_object_prop_list(self, txn_id, payload):
        # E.2.1
        if len(payload) < 20:  # 5 uint32's
            return self._build_response(
                _MTP_OP_GET_OBJECT_PROP_LIST, _MTP_RESP_INVALID_OBJECT_HANDLE, txn_id
            )
        object_handle, object_format_code, object_prop_code, _, depth = struct.unpack(
            "<IIIII", payload[:20]
        )
        if object_handle == 0xFFFFFFFF:  # All objects
            objects = self.object_handles.objects
        elif object_handle == 0x00000000:  # Objects in /
            objects = self.object_handles.get_children_handles(0xFFFFFFFF)
        else:
            objects = [self.object_handles.get(object_handle)]
            if objects[0] is None:
                return self._build_response(
                    _MTP_OP_GET_OBJECT_PROP_LIST,
                    _MTP_RESP_INVALID_OBJECT_HANDLE,
                    txn_id,
                )
        if object_format_code != 0x00000000:
            return self._build_response(
                _MTP_OP_GET_OBJECT_PROP_LIST,
                _MTP_RESP_SPECIFICATION_BY_FORMAT_UNSUPPORTED,
                txn_id,
            )
        if object_prop_code == 0xFFFFFFFF:
            prop_codes_requested = _MTP_SUPPORTED_OBJECT_PROPERTIES
        elif (
            object_prop_code == 0x00000000
        ):  # Get group code from 4th param not supported
            return self._build_response(
                _MTP_OP_GET_OBJECT_PROP_LIST,
                _MTP_RESP_SPECIFICATION_BY_GROUP_NOT_SUPPORTED,
                txn_id,
            )
        else:
            prop_codes_requested = [object_prop_code]
        if depth == 0x00000000 and object_handle == 0x00000000:
            objects = []
        elif depth == 1:
            objects = self.object_handles.get_children_handles(object_handle)
        elif depth > 1:
            return self._build_response(
                _MTP_OP_GET_OBJECT_PROP_LIST,
                _MTP_RESP_SPECIFICATION_BY_DEPTH_UNSUPPORTED,
                txn_id,
            )
        # else depth = 0, so objects = [object_handle], set above

        prop_list = []
        for object in objects:
            for prop_code in prop_codes_requested:
                datatype, value = object.get_property(prop_code)
                prop_list.append((object.handle, prop_code, datatype, value))
        object_prop_list_bytes = struct.pack("<I", len(prop_list))
        for prop in prop_list:
            object_prop_list_bytes += struct.pack("<IHH", prop[0], prop[1], prop[2])
            object_prop_list_bytes += prop[3]
        return self._build_response(
            _MTP_OP_GET_OBJECT_PROP_LIST,
            _MTP_RESP_OK,
            txn_id,
            data=object_prop_list_bytes,
        )

    def _handle_get_object(self, txn_id, payload):
        # D.2.9
        if len(payload) >= 4:
            object_handle = struct.unpack("<I", payload[:4])[0]
        object = self.object_handles.get(object_handle)
        if object is None:
            return self._build_response(
                _MTP_OP_GET_OBJECT, _MTP_RESP_INVALID_OBJECT_HANDLE, txn_id
            )
        if object.isdir:
            return self._build_response(
                _MTP_OP_GET_OBJECT, _MTP_RESP_INVALID_OBJECT_HANDLE, txn_id
            )

        return self._build_response(
            _MTP_OP_GET_OBJECT, _MTP_RESP_OK, txn_id, filename=object.full_path
        )

    def _handle_send_object_info(self, txn_id, payload):
        # D.2.12
        if len(payload) < 4 or struct.unpack("<I", payload[:4])[0] not in (0x00000000, STORAGE_ID):
            return self._build_response(
                _MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_INVALID_STORAGE_ID, txn_id
            )
        if len(payload) < 8:
            return self._build_response(
                _MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_INVALID_OBJECT_HANDLE, txn_id
            )
        parent_object_handle = struct.unpack("<I", payload[4:8])[0]
        if parent_object_handle == 0xFFFFFFFF:
            parent_path = "/"
        else:
            parent_object = self.object_handles.get(parent_object_handle)
            if parent_object is None:
                return self._build_response(
                    _MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_INVALID_OBJECT_HANDLE, txn_id
                )
            if not parent_object.isdir:
                return self._build_response(
                    _MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_INVALID_PARENT_OBJECT, txn_id
                )
            parent_path = parent_object.full_path
        # Parse ObjectInfo dataset 5.3.1
        print(f"ObjectInfo payload len {len(payload)} bytes")
        if len(payload) < (struct.calcsize(_MTP_STRUCT_OBJECT_INFO) + 8 + 4):  # 2 Params, ObjectInfo, Name len
            return self._build_response(
                _MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_INVALID_DATASET, txn_id
            )
        (
            storage_id,
            object_format_code,
            _,  # Thumb format
            object_compressed_size,
            _,  # Thumb format
            _,  # Thumb compressed size
            _,  # Thumb pix width
            _,  # Thumb pix height
            parent_object_handle2,
            association_type,
            _,  # Association Description
            _  # Sequence number
        ) = struct.unpack(_MTP_STRUCT_OBJECT_INFO, payload[8:8 + _MTP_STRUCT_OBJECT_INFO])
        if storage_id not in (0x00000000, STORAGE_ID):
            return self._build_response(
                _MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_INVALID_STORAGE_ID, txn_id
            )
        if parent_object_handle2 not in (0x00000000, parent_object_handle):
            return self._build_response(
                _MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_INVALID_PARENT_OBJECT, txn_id
            )
        filename = _decode_string(payload[8 + _MTP_STRUCT_OBJECT_INFO:])
        full_path = parent_path + filename
        print(f"About to receive {full_path}")
        print(f"New format code {object_format_code}")
        if self.object_handles.get_handle(full_path) is None:
            self.object_handles.add(parent_path, filename, object_compressed_size, bool(association_type))
        self.pending_rx_object_handle = self.object_handles.get_handle(full_path)
        return self._build_response(_MTP_OP_SEND_OBJECT_INFO, _MTP_RESP_OK, txn_id)


    def _handle_send_object(self, txn_id, payload):
        # D.2.13
        if not self.pending_rx_object_handle:
            return self._build_response(_MTP_OP_SEND_OBJECT, _MTP_RESP_NO_VALID_OBJECT_INFO, txn_id)
        object = self.object_handles.get(self.pending_rx_object_handle)
        path = object.full_path
        with open(path, "wb") as f:
            f.write(payload)
        self.pending_rx_object_handle = None
        return self._build_response(_MTP_OP_SEND_OBJECT, _MTP_RESP_OK, txn_id)
