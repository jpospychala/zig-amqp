// The Table struct presents a "view" over our rx buffer that we
// can query without needing to allocate memory into, say, a hash
// map. For small tables (I assume we'll only see smallish tables)
// this should be fine performance-wise.
const std = @import("std");
const mem = std.mem;
const WireBuffer = @import("wire.zig").WireBuffer;

pub const Table = struct {
    // a slice of our rx_buffer (with its own head and end)
    buf: WireBuffer = undefined,
    len: usize = 0,

    const Self = @This();

    pub fn init(buffer: []u8) Table {
        var t = Table{
            .buf = WireBuffer.init(buffer),
            .len = 0,
        };
        t.buf.writeU32(0);
        return t;
    }

    // Lookup a value in the table. Note we need to know the type
    // we expect at compile time. We might not know this at which
    // point I guess I need a union. By the time we call lookup we
    // should already have validated the frame, so I think we maybe
    // can't error here.
    pub fn lookup(self: *Self, comptime T: type, key: []const u8) ?T {
        defer self.buf.reset();
        _ = self.buf.readU32();

        while (self.buf.isMoreData()) {
            const current_key = self.buf.readShortString();
            const correct_key = std.mem.eql(u8, key, current_key);
            const t = self.buf.readU8();
            switch (t) {
                'F' => {
                    const table = self.buf.readTable();
                    if (@TypeOf(table) == T and correct_key) return table;
                },
                't' => {
                    const b = self.buf.readBool();
                    if (@TypeOf(b) == T and correct_key) return b;
                },
                's' => {
                    const s = self.buf.readShortString();
                    if (@TypeOf(s) == T and correct_key) return s;
                },
                'S' => {
                    const s = self.buf.readLongString();
                    if (@TypeOf(s) == T and correct_key) return s;
                },
                else => {
                    // TODO: support all types as continue will return garbage
                    continue;
                },
            }
        }

        return null;
    }

    pub fn insertTable(self: *Self, key: []const u8, table: *Table) void {
        self.buf.writeShortString(key);
        self.buf.writeU8('F');
        self.buf.writeTable(table);
        self.updateLength();
    }

    pub fn insertBool(self: *Self, key: []const u8, boolean: bool) void {
        self.buf.writeShortString(key);
        self.buf.writeU8('t');
        self.buf.writeBool(boolean);
        self.updateLength();
    }

    // Apparently actual implementations don't use 's' for short string
    // (and therefore) I assume they don't use short strings (in tables)
    // at all
    // pub fn insertShortString(self: *Self, key: []u8, string: []u8) void {
    //     self.buf.writeShortString(key);
    //     self.buf.writeU8('s');
    //     self.buf.writeShortString(string);
    //     self.updateLength();
    // }

    pub fn insertLongString(self: *Self, key: []const u8, string: []const u8) void {
        self.buf.writeShortString(key);
        self.buf.writeU8('S');
        self.buf.writeLongString(string);
        self.updateLength();
    }

    fn updateLength(self: *Self) void {
        mem.writeInt(u32, @ptrCast(&self.buf.mem[0]), @intCast(self.buf.head - @sizeOf(u32)), .big);
    }

    pub fn print(self: *Self) void {
        for (self.buf.mem[0..self.buf.head]) |x| {
            std.debug.print("0x{x:0>2} ", .{x});
        }
        std.debug.print("\n", .{});
    }
};
