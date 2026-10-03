# # MicroPython USB MTP module

# import machine
# import struct
# from micropython import const

# from .core import Interface, Buffer, split_bmRequestType

# # Control transfer stages
# _STAGE_IDLE = const(0)
# _STAGE_SETUP = const(1)
# _STAGE_DATA = const(2)
# _STAGE_ACK = const(3)

# # Request types
# _REQ_TYPE_STANDARD = const(0x0)
# _REQ_TYPE_CLASS = const(0x1)
# _REQ_TYPE_VENDOR = const(0x2)
# _REQ_TYPE_RESERVED = const(0x3)

# _INTERFACE_CLASS_MTP = const(0x06)
# _INTERFACE_SUBCLASS_MTP = const(0x01)
# _MTP_EP_NUM = const(2)

# # MTP Container format: 4-byte length, 2-byte type, 2-byte code, 4-byte transaction_id, then payload
# MTP_CONTAINER_HEADER_LEN = 12
# MTP_CONTAINER_TYPE_COMMAND = 1
# MTP_CONTAINER_TYPE_RESPONSE = 2
# MTP_CONTAINER_TYPE_DATA = 3

# # Operation codes
# MTP_OP_GET_DEVICE_INFO = 0x1001
# MTP_OP_OPEN_SESSION = 0x1002
# MTP_OP_GET_STORAGE_IDS = 0x1004

# # Response codes
# MTP_RESP_OK = 0x2001
# MTP_RESP_INVALID_OPERATION = 0x2002

# # Length of the bulk transfer endpoints. Maybe should be configurable?
# _BULK_EP_LEN = const(64)
# _EP_IN_FLAG = const(1 << 7)


# class MTPInterface(Interface):

#     def __init__(self, **kwargs):
#         self._session_id = None
#         self._transaction_id = 0

#     def desc_cfg(self, desc, itf_num, ep_num, strs):
#         # MTP needs a Interface Association Descriptor (IAD) wrapping one interface
#         desc.interface_assoc(itf_num, 1, _INTERFACE_CLASS_MTP, _INTERFACE_SUBCLASS_MTP)

#         # Now add the interface descriptor
#         self._itf = itf_num
#         desc.interface(itf_num, _MTP_EP_NUM, _INTERFACE_CLASS_MTP, _INTERFACE_SUBCLASS_MTP)

#         # Two data endpoints, bulk OUT and IN
#         self.ep_out = ep_num + 1
#         self.ep_in = (ep_num + 1) | _EP_IN_FLAG
#         desc.endpoint(self.ep_out, "bulk", _BULK_EP_LEN, 0)
#         desc.endpoint(self.ep_in, "bulk", _BULK_EP_LEN, 0)

#     def num_itfs(self):
#         return 1

#     def num_eps(self):
#         return 2  # total after masking out _EP_IN_FLAG

#     def on_open(self):
#         super().on_open()

#     def on_interface_control_xfer(self, stage, request):
#         # Handle class-specific interface control transfers
#         bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack("BBHHH", request)
#         recipient, req_type, req_dir = split_bmRequestType(bmRequestType)

#         if wIndex != self._c_itf:
#             return False  # Only for the control interface (may be redundant check?)

#         if req_type != _REQ_TYPE_CLASS:
#             return False  # Unsupported request type

#         return True  # allow DATA/ACK stages to complete normally

import os
import struct
import machine
from micropython import const
from usb.device.core import Interface, Buffer, split_bmRequestType

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

# MTP Response codes
_MTP_RESP_OK = const(0x2001)
_MTP_RESP_INVALID_OPERATION = const(0x2002)
_MTP_INVALID_STORAGE_ID = const(0x2008)

# Operation codes
# Appendix D, Table D.1
_MTP_OP_GET_DEVICE_INFO = 0x1001
_MTP_OP_OPEN_SESSION = 0x1002
_MTP_OP_CLOSE_SESSION = 0x1003
_MTP_OP_GET_STORAGE_IDS = 0x1004
_MTP_OP_GET_STORAGE_INFO = 0x1005
_MTP_OP_GET_NUM_OBJECTS = 0x1006
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
_MTP_SUPPORTED_OBJECT_FORMATS = [
    # Appendix A. Table A.1
    0x3000,  # unidentified
    0x3001,  # association (folder)
    0x3002,  # script
    0x3004,  # text
    0x3800,  # undefined image
    0x3801,  # JPEG
    0x3804,  # BMP
    0x3807,  # GIF
    0x380B,  # PNG
]


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
        self.tx_buf = Buffer(2048)  # Response/data transmit buffer
        self.rx_buf = Buffer(2048)  # Command receive buffer

        # Pending response state
        self.pending_response = None
        self.pending_data = None

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
            iInterface=len(strs)
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
        length, container_type, code, txn_id = struct.unpack("<IHHH", data[:12])
        payload = data[12:length] if len(data) > 12 else b""

        container = {
            "type": container_type,
            "code": code,
            "txn_id": txn_id,
            "payload": payload,
        }

        # Dispatch to handler
        if self.mtp_handler:
            response, response_data = self.mtp_handler.handle_command(container)

            # Queue response for transmission
            self.pending_response = response
            self.pending_data = response_data
            self._send_response()

    def _send_response(self):
        """Submit a transfer to send response to the host."""
        if (
            self.is_open()
            and not self.xfer_pending(self.ep_in)
            and self.pending_response
        ):
            # # Send response container first
            # self.submit_xfer(
            #     self.ep_in,
            #     self.pending_response,
            #     self._send_cb,
            # )

            # if not self.is_open() or self.xfer_pending(self.ep_in):
            #     return
            
            # Priority: data first (if pending), then response
            if self.pending_data is not None:
                self.submit_xfer(
                    self.ep_in,
                    self.pending_data,  # Raw bytes, NO container
                    self._send_data_cb,
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

            # If there's data payload, send it next
            # if self.pending_data:
            #     self.submit_xfer(
            #         self.ep_in,
            #         self.pending_data,
            #         self._send_data_cb,
            #     )
            # else:
        self._recv_cmd()  # Resume listening for commands

    # def _send_data_cb(self, ep, res, num_bytes):
    #     """Callback when data payload sent."""
    #     if res == 0:
    #         self.pending_data = None
    #         self._recv_cmd()  # Resume listening for commands

    def _send_data_cb(self, ep, res, num_bytes):
        """Data sent — now queue response."""
        self.pending_data = None
        
        if res == 0 and self.pending_response is not None:
            self.submit_xfer(
                self.ep_in,
                self.pending_response,
                self._send_response_cb,
            )
        else:
            self._recv_cmd()


class MTPHandler:
    """Implements MTP command logic."""

    def __init__(self):
        self.session_id = None
        self.object_handles = []

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
        elif code == _MTP_OP_GET_STORAGE_IDS:
            return self._handle_get_storage_ids(txn_id)
        elif code == _MTP_OP_GET_STORAGE_INFO:
            return self._handle_get_storage_info(txn_id, payload)
        # _MTP_OP_GET_NUM_OBJECTS
        # _MTP_OP_GET_OBJECT_HANDLES
        # _MTP_OP_GET_OBJECT_INFO
        # _MTP_OP_GET_OBJECT
        # _MTP_OP_SEND_OBJECT_INFO
        # _MTP_OP_SEND_OBJECT
        # _MTP_OP_RESET_DEVICE
        # _MTP_OP_MOVE_OBJECT
        # _MTP_OP_COPY_OBJECT
        else:
            # Unknown operation
            return self._build_response(code, _MTP_RESP_INVALID_OPERATION, txn_id)

    def _build_response(self, code, resp_code, txn_id, params=None, data=None):
        """Build MTP response container."""
        payload = b""
        if params:
            payload = struct.pack("<" + "I" * len(params), *params)


        length = 12 + len(payload)
        resp_header = struct.pack("<IHHI", length, _MTP_CONTAINER_TYPE_RESPONSE, resp_code, txn_id)

        if data:
            data_length = 12 + len(data)
            data_header = struct.pack("<IHHI", data_length, _MTP_CONTAINER_TYPE_DATA, code, txn_id)
            resp_data = data_header + data
        else:
            resp_data = None

        return resp_header + payload, resp_data

    def _encode_string(self, string: str):
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

    def _encode_array(self, typecode: str, array: list):
        encoded = struct.pack("<I", len(array))
        # Iterate over array, in case each item is actually multiple
        for item in array:
            encoded += struct.pack(f"<{typecode}", item)
        return encoded

    def _handle_get_device_info(self, txn_id):
        """Minimal device info response."""
        # 5.1.1 DeviceInfo Dataset
        device_info_dataset = b""
        standard_version = struct.pack("<H", 100)  # 1.00
        mtp_vendor_extension_id = struct.pack("<I", 0xFFFFFFFF)
        mtp_version = struct.pack(
            "<H", 0x0064
        )  # In hundreths. PDF is v1.1. Phone uses 0x0064
        mtp_extensions = self._encode_string("hackaday.com: 1.0;")  # TODO: Fill in
        functional_mode = struct.pack("<H", 0x0000)  # Standard mode
        operations_supported = self._encode_array(
            "H",
            [
                # Appendix D, Table D.1
                _MTP_OP_GET_DEVICE_INFO,
                _MTP_OP_OPEN_SESSION,
                _MTP_OP_CLOSE_SESSION,
                _MTP_OP_GET_STORAGE_IDS,
                _MTP_OP_GET_STORAGE_INFO,
                _MTP_OP_GET_NUM_OBJECTS,
                _MTP_OP_GET_OBJECT_HANDLES,
                _MTP_OP_GET_OBJECT_INFO,
                _MTP_OP_GET_OBJECT,
                _MTP_OP_DELETE_OBJECT,
                _MTP_OP_GET_OBJECT_PROP_DESC,
                _MTP_OP_SEND_OBJECT_INFO,
                _MTP_OP_SEND_OBJECT,
                _MTP_OP_RESET_DEVICE,
                _MTP_OP_GET_DEVICE_PROP_DESC,
                _MTP_OP_GET_DEVICE_PROP_VALUE,
                _MTP_OP_SET_DEVICE_PROP_VALUE,
                _MTP_OP_MOVE_OBJECT,
                _MTP_OP_COPY_OBJECT,
                _MTP_OP_GET_OBJECT_PROP_VALUE,
                _MTP_OP_SET_OBJECT_PROP_VALUE,
                _MTP_OP_GET_OBJECT_PROP_LIST
            ],
        )
        events_supported = self._encode_array(
            "H",
            [
                _MTP_EVENT_OBJECT_ADDED,
                _MTP_EVENT_OBJECT_REMOVED,
            ],
        )
        device_properties_supported = self._encode_array(
            "H", [_MTP_DEVICE_PROP_UNDEFINED]
        )
        capture_formats = self._encode_array("H", [])
        playback_formats = self._encode_array(
            "H",
            _MTP_SUPPORTED_OBJECT_FORMATS
        )
        manufacturer = self._encode_string("HackADay")
        model = self._encode_string("SuperconBadge")
        device_version = self._encode_string("0x0A")
        base_id = "".join([hex(b)[2:4].upper() for b in machine.unique_id()])
        serial_number = self._encode_string(
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
        response = self._build_response(
            _MTP_OP_GET_DEVICE_INFO, _MTP_RESP_OK, txn_id, data=device_info_dataset
        )
        return response

    def _handle_open_session(self, txn_id, payload):
        """Initialize session."""
        self._scan_fs("/")
        if len(payload) >= 4:
            self.session_id = struct.unpack("<I", payload[:4])[0]
        response = self._build_response(_MTP_OP_OPEN_SESSION, _MTP_RESP_OK, txn_id)
        return response

    def _handle_get_storage_ids(self, txn_id):
        """Return storage IDs."""
        # 5.2.1 Storage IDs
        storage_ids = self._encode_array("I", [STORAGE_ID])
        response = self._build_response(
            _MTP_OP_GET_STORAGE_IDS, _MTP_RESP_OK, txn_id, data=storage_ids
        )

        return response

    def _handle_get_storage_info(self, txn_id, payload):
        if len(payload) >= 4:
            storage_id = struct.unpack("<HH", payload[:4])
        if storage_id != STORAGE_ID:
            response = self._build_response(
                _MTP_OP_GET_STORAGE_IDS, _MTP_INVALID_STORAGE_ID, txn_id
            )
            return response

        # 5.2.2 StorageInfo Dataset Description
        storage_type = struct.pack("<H", 0x0003)  # Fixed RAM
        filesystem_type = struct.pack("<H", 0x0002)  # Generic hierarchical
        access_capability = struct.pack("<H", 0x0000)  # Read-write
        bsize, frsize, blocks, bfree, _, _, _, _, namemax = os.statvfs()
        max_capacity = struct.pack("<Q", frsize * blocks)
        free_space = struct.pack("<Q", bfree * bsize)
        free_objects = struct.pack("<Q", 0xFFFFFFFF)  # Unused field
        storage_description = self._encode_string("Badge Virtual FS")
        volume_identifier = self._encode_string(machine.unique_id())

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

        response = self._build_response(
            _MTP_OP_GET_STORAGE_INFO, _MTP_RESP_OK, txn_id, data=storage_info
        )
        return response

    def _handle_get_object_handles(self, txn_id, payload):
        """Return object handles"""
        # 5.2.1 Storage IDs
        self._scan_fs("/")

        object_handles = struct.pack("<I", len(self.object_handles) - 1)
        for idx in range(1, len(self.object_handles)):
            # First 16 bits are the "physical storage", which can't be 0.
            # Last 16 bits is the "logical storage", which also can't be 0.
            object_handles.append(struct.pack("<I", 0x00010000 + idx))

        response = self._build_response(
            _MTP_OP_GET_OBJECT_HANDLES, _MTP_RESP_OK, txn_id, data=object_handles
        )

        return response

    def _scan_fs(self, path: str):
        """Scan virtual FS and assign storage ID to all files and directories."""
        if not self.object_handles:
            # Initialize the list with / at ID 0 since that's illegal
            # for MTP for a real file/directory
            self.object_handles.append("/")
        for file_info in os.ilistdir(path):
            filename, filetype, _, _size = file_info
            full_path = path + filename
            if filetype == 0x4000:  # directory
                self._scan_fs(full_path + "/")
            if full_path not in self.object_handles:
                # Don't re-add already-identified filesystem objects
                # in this session
                self.object_handles.append(full_path)
