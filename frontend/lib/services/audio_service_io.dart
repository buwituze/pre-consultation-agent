// IO implementation for mobile and desktop platforms
// This file is used when dart:io is available (Android, iOS, Windows, macOS, Linux)

import 'dart:io';
import 'package:record/record.dart';

String getPlatformName() {
  if (Platform.isAndroid) {
    return 'android';
  } else if (Platform.isIOS) {
    return 'ios';
  } else if (Platform.isWindows) {
    return 'windows';
  } else if (Platform.isMacOS) {
    return 'macos';
  } else if (Platform.isLinux) {
    return 'linux';
  }
  return 'unknown';
}

AudioEncoder getAudioEncoder() {
  if (Platform.isAndroid || Platform.isIOS || Platform.isMacOS) {
    // Mobile and macOS prefer AAC/M4A
    return AudioEncoder.aacLc;
  } else {
    // Windows and Linux use WAV
    return AudioEncoder.wav;
  }
}

String getFileExtension() {
  if (Platform.isAndroid || Platform.isIOS || Platform.isMacOS) {
    return 'm4a';
  } else {
    return 'wav';
  }
}

Future<void> deleteFile(String path) async {
  final file = File(path);
  if (await file.exists()) {
    await file.delete();
  }
}
