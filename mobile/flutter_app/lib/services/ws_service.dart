import 'dart:async';
import 'dart:math';
import 'package:web_socket_channel/web_socket_channel.dart';

class WsService {
  String url;
  WebSocketChannel? _channel;
  StreamController<dynamic> _controller = StreamController.broadcast();
  bool _connected = false;
  bool _manuallyClosed = false;

  WsService({required this.url});

  Stream<dynamic> get stream => _controller.stream;

  void connect() {
    if (_connected) return;
    _manuallyClosed = false;
    _connectWithBackoff();
  }

  void _connectWithBackoff() async {
    int attempt = 0;
    while (!_manuallyClosed) {
      try {
        _channel = WebSocketChannel.connect(Uri.parse(url));
        _connected = true;
        _channel!.stream.listen((msg) {
          _controller.add(msg);
        }, onError: (err) {
          _controller.addError(err);
        }, onDone: () {
          _connected = false;
          _channel = null;
        });
        // connected successfully - break out of the loop
        break;
      } catch (e) {
        attempt += 1;
        final wait = min(30, pow(2, attempt));
        _controller.addError('ws_connect_failed: $e, retrying in ${wait}s');
        await Future.delayed(Duration(seconds: wait.toInt()));
      }
    }
  }

  void disconnect() {
    _manuallyClosed = true;
    _channel?.sink.close();
    _channel = null;
    _connected = false;
  }

  void dispose() {
    disconnect();
    _controller.close();
  }
}
