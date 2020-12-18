import xml.etree.ElementTree as Tree
import sys

BITFIELD_TYPES = ['bit', 'no-ack', 'no-local', 'no-wait', 'redelivered']

def generate(file):
    print(f'const std = @import("std");')
    print(f'const fs = std.fs;')
    print(f'const Connector = @import("connector.zig").Connector;')
    print(f'const ClassMethod = @import("connector.zig").ClassMethod;')
    print(f'const WireBuffer = @import("wire.zig").WireBuffer;')
    print(f'const Table = @import("table.zig").Table;')

    tree = Tree.parse(file)
    amqp = tree.getroot()
    if amqp.tag == "amqp":
        print("// amqp")
        generateLookup(amqp)
        generateIsSyncrhonous(amqp)
        for child in amqp:
            if child.tag == "constant":
                print(f"pub const {nameCleanUpper(child)}: u16 = {child.attrib['value']};")
            if child.tag == "class":
                generateInterface(child)
                generateImplementation(child)
                generateClass(child)

def generateLookup(amqp):
    print(f"pub fn dispatchCallback(conn: *Connector, class: u16, method: u16) !void {{")
    print(f"switch (class) {{")
    for child in amqp:
        if child.tag == "class":
            klass = child
            index = klass.attrib['index']
            print(f"// {klass.attrib['name']}")
            print(f"{index} => {{")
            generateLookupMethod(klass)
            print(f"}},")
    print(f"else => return error.UnknownClass}}")
    print(f"}}")

def generateLookupMethod(klass):
    print(f"switch (method) {{")
    class_name_upper = nameCleanUpper(klass)
    class_name_cap = nameCleanCap(klass)
    for child in klass:
        if child.tag == "method":
            method = child
            bit_field_count = 0
            method_name = nameClean(method)
            method_name_cap = nameCleanCap(method)
            index = method.attrib['index']
            print(f"// {method_name}")
            print(f"{index} => {{")
            print(f"const {method_name} = {class_name_upper}_IMPL.{method_name} orelse return error.MethodNotImplemented;")
            for child in method:
                if child.tag == 'field':
                    field = child
                    if fieldType(field) in BITFIELD_TYPES:
                        if bit_field_count % 8 == 0:
                            print(f"const bitset{bit_field_count//8} = conn.rx_buffer.readU8();")
                        print(f"{fieldConstness(field)} {nameClean(field)} = if (bitset{bit_field_count//8} & (1 << {bit_field_count}) == 0) true else false;")
                        bit_field_count += 1
                    else:
                        bit_field_count = 0
                        print(f"{fieldConstness(field)} {nameClean(field)} = conn.rx_buffer.{generateRead(field)}(); ")
            print(f"try conn.rx_buffer.readEOF();")
            print(f"if (std.builtin.mode == .Debug) std.debug.warn(\"{class_name_cap}.{method_name_cap}\\n\", .{{}});")
            print(f"try {method_name}(conn, ")
            for child in method:
                if child.tag == 'field':
                    field = child
                    if not ('reserved' in field.attrib):
                        print(f"{addressOf(field)}{nameClean(field)}, ")
            print(f");")
            print(f"}},")
    print(f"else => return error.UnknownMethod, ")            
    print(f"}}")

def generateIsSyncrhonous(amqp):
    print(f"pub fn isSynchronous(class_id: u16, method_id: u16) !bool {{")
    print(f"switch (class_id) {{")
    for child in amqp:
        if child.tag == "class":
            klass = child
            index = klass.attrib['index']
            print(f"// {klass.attrib['name']}")
            print(f"{index} => {{")
            generateIsSyncrhonousMethod(klass)
            print(f"}},")
    print(f"else => return error.UnknownClass}}")
    print(f"}}")

def generateIsSyncrhonousMethod(method):
    print(f"switch (method_id) {{")
    for child in method:
        if child.tag == "method":
            method = child
            method_name = nameClean(method)
            is_synchronous = 'synchronous' in method.attrib and method.attrib['synchronous'] == '1'
            index = method.attrib['index']
            print(f"// {method_name}")
            print(f"{index} => {{")
            if is_synchronous:
                print(f"return true;")
            else:
                print(f"return false;")
            print(f"}},")
    print(f"else => return error.UnknownMethod, ")            
    print(f"}}")

def generateInterface(klass):
    class_name = nameClean(klass)
    print(f"pub const {class_name}_interface = struct {{")
    for child in klass:
        if child.tag == "method":
            method = child
            generateInterfaceMethod(method, class_name, nameCleanCap(klass))
    print(f"}};\n")

def generateInterfaceMethod(method, klass, klass_upper):
    method_name = nameClean(method)
    print(f"{method_name}: ?fn(*Connector, ")
    for child in method:
        if child.tag == 'field':
            field = child
            if not ('reserved' in field.attrib):
                print(f"{nameClean(field)}: {generateArg(field)}, ")
    print(f") anyerror!void,")

def generateImplementation(klass):
    class_name_upper = nameCleanUpper(klass)
    class_name = nameClean(klass)
    print(f"pub var {class_name_upper}_IMPL = {class_name}_interface {{")
    for child in klass:
        if child.tag == 'method':
            method = child
            method_name = nameClean(method)
            print(f".{method_name} = null,")
    print(f"}};\n")

def generateClass(c):
    # print(f"pub const {nameClean(c)} = struct {{")
    # print(f"const _{nameClean(c)} = @import(\"{nameClean(c)}.zig\");")
    print(f"pub const {nameCleanUpper(c)}_CLASS = {c.attrib['index']}; // CLASS")
    print(f"pub const {nameCleanCap(c)} = struct {{")
    # print(f"conn: Connector,")
    # print(f"connection: *connection.Connection,")
    # print(f"file: fs.File,")
    # print(f"rx_buffer: WireBuffer,")
    # print(f"tx_buffer: WireBuffer,")
    print(f"const Self = @This();")
    for child in c:
        if child.tag == "method":
            method = child
            print(f"// METHOD =============================")
            print(f"pub const {nameCleanUpper(method)}_METHOD = {method.attrib['index']};")
            if isClientInitiatedRequest(method):
                generateClientInitiatedRequest(method, nameClean(c), nameCleanCap(c), nameCleanUpper(c))
            if isClientResponse(method):
                generateClientResponse(method, nameCleanCap(c), nameCleanUpper(c))

    print(f"}};")

def isClientInitiatedRequest(method):
    isRequestSentToServer = False
    expectsResponse = False
    for child in method:
        if child.tag == 'chassis' and 'name' in child.attrib and child.attrib['name'] == 'server':
            isRequestSentToServer = True
        if child.tag == 'response':
            expectsResponse = True
    return isRequestSentToServer and expectsResponse

def isClientResponse(method):
    isRequestSentToServer = False
    expectsResponse = False
    for child in method:
        if child.tag == 'chassis' and 'name' in child.attrib and child.attrib['name'] == 'server':
            isRequestSentToServer = True
        if child.tag == 'response':
            expectsResponse = True
    return isRequestSentToServer and not expectsResponse

def generateClientInitiatedRequest(method, klass, klass_cap, klass_upper):
    # print(method)
    method_name = nameCleanUpper(method)
    reply_method = nameCleanUpper(method) + '_OK'
    print(f"pub fn {nameClean(method)}_sync(conn: *Connector,")
    for method_child in method:
        if method_child.tag == 'field' and not ('reserved' in method_child.attrib and method_child.attrib['reserved'] == '1'):
            print(f"{nameClean(method_child)}: {generateArg(method_child)}, ", end = '')
    print(f") !void {{")
    # Send message
    print(f"conn.tx_buffer.writeFrameHeader(.Method, conn.channel, 0);")
    print(f"conn.tx_buffer.writeMethodHeader({klass_upper}_CLASS, {klass_cap}.{method_name}_METHOD);")
    # Generate writes
    bit_field_count = 0
    for method_child in method:
        if method_child.tag == 'field':
            field = method_child
            if ('reserved' in method_child.attrib and method_child.attrib['reserved'] == '1'):
                print(f"const {nameClean(method_child)} = {generateReserved(method_child)};")
            # What we do depends on the field type
            if fieldType(field) in BITFIELD_TYPES:
                if bit_field_count % 8 == 0:
                    print(f"var bitset{bit_field_count//8}: u8 = 0; const _bit: u8 = 1;")
                print(f"if ({nameClean(field)}) bitset{bit_field_count//8} |= (_bit << {bit_field_count}) else bitset{bit_field_count//8} &= ~(_bit << {bit_field_count});")
                # print(f"}}")
                # if bit_field_count % 8 == 0:
                #     print(f"conn.tx_buffer.writeU8(bitset{bit_field_count//8});")                
                bit_field_count += 1
            else:
                if bit_field_count > 0:
                    print(f"conn.tx_buffer.writeU8(bitset{bit_field_count//8});")  
                bit_field_count = 0
                print(f"conn.tx_buffer.{generateWrite(method_child, nameClean(method_child))};")

    if bit_field_count > 0:
        print(f"conn.tx_buffer.writeU8(bitset{bit_field_count//8});")                
    # Send message
    print(f"conn.tx_buffer.updateFrameLength();")
    print(f"const n = try std.os.write(conn.file.handle, conn.tx_buffer.extent());")
    print(f"conn.tx_buffer.reset();")
    print(f"var received_response = false;")
    # print(f"var parent = @fieldParentPtr(_{klass}.{klass_cap}, \"proto\", self);")
    print(f"while (!received_response) {{ const expecting: ClassMethod = .{{ .class = {klass_upper}_CLASS, .method = {klass_cap}.{reply_method}_METHOD }};")
    print(f"received_response = try conn.dispatch(expecting); }}")
    print(f"}}")

def generateClientResponse(method, klass_cap, klass_upper):
    method_name = nameCleanUpper(method)
    print(f"pub fn {nameClean(method)}_resp(conn: *Connector,")
    for method_child in method:
        if method_child.tag == 'field' and not ('reserved' in method_child.attrib and method_child.attrib['reserved'] == '1'):
            print(f"{nameClean(method_child)}: {generateArg(method_child)}, ", end = '')
    print(f") !void {{")
    print(f"conn.tx_buffer.writeFrameHeader(.Method, conn.channel, 0);")
    print(f"conn.tx_buffer.writeMethodHeader({klass_upper}_CLASS, {klass_cap}.{method_name}_METHOD);")
    # Generate writes
    bit_field_count = 0
    for method_child in method:
        if method_child.tag == 'field':
            field = method_child
            if ('reserved' in method_child.attrib and method_child.attrib['reserved'] == '1'):
                print(f"const {nameClean(method_child)} = {generateReserved(method_child)};")
            # What we do depends on the field type
            if fieldType(field) in BITFIELD_TYPES:
                if bit_field_count % 8 == 0:
                    print(f"var bitset{bit_field_count//8}: u8 = 0; const _bit: u8 = 1;")
                print(f"if ({nameClean(field)}) bitset{bit_field_count//8} |= (_bit << {bit_field_count}) else bitset{bit_field_count//8} &= ~(_bit << {bit_field_count});")              
                bit_field_count += 1
            else:
                if bit_field_count > 0:
                    print(f"conn.tx_buffer.writeU8(bitset{bit_field_count//8});")   

                bit_field_count = 0
                print(f"conn.tx_buffer.{generateWrite(method_child, nameClean(method_child))};")

    if bit_field_count > 0:
        print(f"conn.tx_buffer.writeU8(bitset{bit_field_count//8});")            
    # Send message
    print(f"conn.tx_buffer.updateFrameLength();")
    print(f"const n = try std.os.write(conn.file.handle, conn.tx_buffer.extent());")
    print(f"conn.tx_buffer.reset();")
    print(f"}}")

def addressOf(field):
    field_type = None
    if 'domain' in field.attrib:
        field_type = field.attrib['domain']
    if 'type' in field.attrib:
        field_type = field.attrib['type']

    if field_type in ['peer-properties', 'table']:
        return '&'
    return ''

def fieldType(field):
    field_type = None
    if 'domain' in field.attrib:
        field_type = field.attrib['domain']
    if 'type' in field.attrib:
        field_type = field.attrib['type']
    return field_type

def generateRead(field):
    field_type = fieldType(field)

    if field_type == 'octet':
        return 'readU8'
    if field_type in ['longlong', 'delivery-tag']:
        return 'readU64'        
    if field_type in ['long', 'message-count']:
        return 'readU32'
    if field_type in ['short', 'class-id', 'method-id', 'reply-code']:
        return 'readU16'
    if field_type in ['bit', 'no-ack', 'no-local', 'no-wait', 'redelivered']:
        return 'readBool'
    if field_type in ['queue-name', 'exchange-name']:
        return 'readShortString'
    if field_type in ['consumer-tag', 'reply-text']:
        return 'readShortString'
    if field_type in ['shortstr', 'path']:
        return 'readShortString'
    if field_type in ['longstr']:
        return 'readLongString'
    if field_type in ['peer-properties', 'table']:
        return 'readTable'
    return 'void'

def generateWrite(field, name):
    field_type = None
    if 'domain' in field.attrib:
        field_type = field.attrib['domain']
    if 'type' in field.attrib:
        field_type = field.attrib['type']

    if field_type == 'octet':
        return 'writeU8(' + name + ')'
    if field_type in ['longlong', 'delivery-tag']:
        return 'writeU64(' + name + ')'
    if field_type in ['long', 'message-count']:
        return 'writeU32(' + name + ')'
    if field_type in ['short', 'class-id', 'method-id', 'reply-code']:
        return 'writeU16(' + name + ')'
    if field_type in ['bit', 'no-ack', 'no-local', 'no-wait', 'redelivered']:
        return 'writeBool(' + name + ')'
    if field_type in ['queue-name', 'exchange-name']:
        return 'writeShortString(' + name + ')'
    if field_type in ['consumer-tag', 'reply-text']:
        return 'writeShortString(' + name + ')'
    if field_type in ['shortstr', 'path']:
        return 'writeShortString(' + name + ')'
    if field_type in ['longstr']:
        return 'writeLongString(' + name + ')'
    if field_type in ['peer-properties', 'table']:
        return f"writeTable({name})"
    return 'void'    

def generateArg(field):
    field_type = None
    if 'domain' in field.attrib:
        field_type = field.attrib['domain']
    if 'type' in field.attrib:
        field_type = field.attrib['type']

    if field_type == 'octet':
        return 'u8'
    if field_type in ['longlong', 'delivery-tag']:
        return 'u64'            
    if field_type in ['long', 'message-count']:
        return 'u32'
    if field_type in ['short', 'class-id', 'method-id', 'reply-code']:
        return 'u16'
    if field_type in ['bit', 'no-ack', 'no-local', 'no-wait', 'redelivered']:
        return 'bool'
    if field_type in ['queue-name', 'exchange-name']:
        return '[]const u8'
    if field_type in ['path', 'shortstr']:
        return '[]const u8'        
    if field_type in ['consumer-tag', 'reply-text', 'longstr']:
        return '[]const u8'
    if field_type in ['peer-properties', 'table']:
        return '?*Table'
    return 'void'

def generateReserved(field):
    field_type = None
    if 'domain' in field.attrib:
        field_type = field.attrib['domain']
    if 'type' in field.attrib:
        field_type = field.attrib['type']

    if field_type == 'octet':
        return '0'
    if field_type in ['longlong', 'delivery-tag']:
        return '0'
    if field_type in ['long', 'message-count']:
        return '0'
    if field_type in ['short', 'class-id', 'method-id', 'reply-code']:
        return '0'
    if field_type in ['bit', 'no-ack', 'no-local', 'no-wait', 'redelivered']:
        return 'false'
    if field_type in ['queue-name', 'exchange-name']:
        return ''
    if field_type in ['consumer-tag', 'reply-text']:
        return ''
    if field_type in ['shortstr', 'path']:
        return '""'
    if field_type in ['longstr']:
        return '""'
    if field_type in ['peer-properties', 'table']:
        return ''
    return 'void'

def fieldConstness(field):
    field_type = None
    if 'domain' in field.attrib:
        field_type = field.attrib['domain']
    if 'type' in field.attrib:
        field_type = field.attrib['type']

    if field_type in ['peer-properties', 'table']:
        return 'var'
    
    return 'const'

def nameClean(tag):
    name = tag.attrib['name'].replace('-', '_')

    if name == "return":
        return "@\"return\""
    if name == "type":
        return "tipe"        
    return name

def nameCleanUpper(tag):
    name = tag.attrib['name'].replace('-', '_').upper()    
    return name

def nameCleanCap(tag):
    name = tag.attrib['name'].replace('-', '_').capitalize()    
    return name       

generate(sys.argv[1])