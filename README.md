<h1 align="center">zig-amqp</h1>

<div align="center">
  <strong>AMQP 0.9.1 library for Zig</strong>
</div>

## About

`zig-amqp` is a [Zig](https://ziglang.org) library for writing AMQP 0.9.1 clients (and servers), letting zig programs to connect to, for example, [RabbitMQ](https://www.rabbitmq.com/).

## How to use

See [the examples](https://github.com/malcolmstill/zig-amqp/tree/master/examples) for an idea of how to use the library.

The simplest program is probably a simple declare and publish:

```zig
const std = @import("std");
const amqp = @import("amqp");

var rx_memory: [4096]u8 = undefined;
var tx_memory: [4096]u8 = undefined;

pub fn main() !void {
    var conn = amqp.init(rx_memory[0..], tx_memory[0..]);
    const addr = try std.net.Address.parseIp4("127.0.0.1", 5672);
    try conn.connect(addr);

    var ch = try conn.channel();
    _ = try ch.queueDeclare("simple_publish", amqp.Queue.Options{}, null);

    try ch.basicPublish("", "simple_publish", "hello world", amqp.Basic.Publish.Options{});
}
```

## Status

The project is alpha with only basic functionality working. Contributions welcome.

## Goals

- Easy to use API
- Simple / clean code
- Minimal allocations / customisable allocation