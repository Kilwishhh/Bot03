import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class WebSocketExample extends StatefulWidget {
  final String url;
  WebSocketExample({required this.url});
  @override
  _WebSocketExampleState createState() => _WebSocketExampleState();
}

class _WebSocketExampleState extends State<WebSocketExample> {
  WebSocketChannel? channel;
  List<String> messages = [];

  void connect() {
    channel = WebSocketChannel.connect(Uri.parse(widget.url));
    channel!.stream.listen((event) {
      setState(() => messages.insert(0, event.toString()));
    }, onDone: () {
      setState(() => channel = null);
    }, onError: (e) {
      setState(() => messages.insert(0, 'error: $e'));
    });
  }

  void disconnect() {
    channel?.sink.close();
    channel = null;
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(children: [
          ElevatedButton(onPressed: channel==null?connect:disconnect, child: Text(channel==null? 'Connect':'Disconnect'))
        ],),
        SizedBox(height:8),
        Expanded(child: ListView.builder(
          itemCount: messages.length,
          itemBuilder: (c,i) => ListTile(title: Text(messages[i])),
        ))
      ],
    );
  }
}
