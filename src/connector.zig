const std = @import("std");
const os = std.os;
const fs = std.fs;
const WireBuffer = @import("wire.zig").WireBuffer;
const proto = @import("protocol.zig");

// TODO: think up a better name for this
pub const Connector = struct {
    file: fs.File,
    rx_buffer: WireBuffer = undefined,
    tx_buffer: WireBuffer = undefined,
    channel: u16,

    const Self = @This();

    // dispatch reads from our socket and dispatches methods in response
    // Where dispatch is invoked in initialising a request, we pass in an expected_response
    // ClassMethod that specifies what (synchronous) response we are expecting. If this value
    // is supplied and we receive an incorrect (synchronous) method we error, otherwise we
    // dispatch and return true. In the case
    // (expected_response supplied), if we receive an asynchronous response we dispatch it
    // but return true.
    pub fn dispatch(self: *Self, expected_response: ?ClassMethod) !bool {
        const n = try os.read(self.file.handle, self.rx_buffer.mem[0..]);
        self.rx_buffer.reset();
        self.tx_buffer.reset();

        // 1. Attempt to read a frame header
        const header = try self.rx_buffer.readFrameHeader();

        switch (header.@"type") {
            .Method => {
                // 2a. The frame header says this is a method, attempt to read
                // the method header
                const method_header = try self.rx_buffer.readMethodHeader();
                const class = method_header.class;
                const method = method_header.method;

                var sync_resp_ok = false;

                // 3a. If this is a synchronous call, we expect expected_response to be
                // non-null and to provide the expected class and method of the response
                // that we're waiting on. That class and method is checked for being
                // a synchronous response and then we compare the class / method from the
                // header with expected_response and error if they don't match.
                if (expected_response) |expected| {
                    const is_synchronous = try proto.isSynchronous(class, method);

                    if (is_synchronous) {
                        // if (class != expected.class) return error.UnexpectedResponseClass;
                        // if (method != expected.method) return error.UnexpectedResponseClass;
                        if (class == expected.class and method == expected.method) {
                            sync_resp_ok = true;
                        } else {
                            // TODO: we might receive an unexpecte close with a CHANNEL_ERROR
                            //       we should signal a separate error perhaps

                            if (class == proto.CHANNEL_CLASS and method == proto.Channel.CLOSE_METHOD) {
                                std.debug.warn("Likely CHANNEL_ERROR\n", .{});
                                try proto.dispatchCallback(self, class, method);
                                // TODO: we need to deallocate the channel here. Which means we need
                                //       access to Connection
                            }

                            return error.UnexpectedSync;
                        }
                    } else {
                        sync_resp_ok = true;
                    }
                }

                // 4a. Finally dispatch the class / method
                // const connection: *proto.Connection = @fieldParentPtr(proto.Connection, "conn", self);
                try proto.dispatchCallback(self, class, method);
                return sync_resp_ok;
            },
            .Heartbeat => {
                if (std.builtin.mode == .Debug) std.debug.warn("Got heartbeat\n", .{});
                return false;
            },
            else => {
                return false;
            },
        }
    }
};

pub const ClassMethod = struct {
    class: u16 = 0,
    method: u16 = 0,
};
